/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

package org.mozilla.fenix.settings

import android.content.ComponentName
import android.content.Context
import android.content.ContextWrapper
import android.content.SharedPreferences
import android.content.Intent
import android.content.pm.PackageManager
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import io.mockk.every
import io.mockk.mockk
import io.mockk.mockkStatic
import io.mockk.unmockkStatic
import kotlinx.coroutines.test.runTest
import mozilla.components.service.fxa.AccountServices
import mozilla.components.support.ktx.android.content.isMainProcess
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.mozilla.fenix.FenixApplication

@RunWith(AndroidJUnit4::class)
class AccountServicesPreferenceTest {
    private val context: Context get() = ApplicationProvider.getApplicationContext()
    private val preferences get() = context.getSharedPreferences(
        "mozilla.components.service.fxa.account-services",
        Context.MODE_PRIVATE,
    )

    @Before
    fun setUp() {
        mockkStatic("mozilla.components.support.ktx.android.content.ContextKt")
        every { any<Context>().isMainProcess() } returns true
        preferences.edit().clear().commit()
        AccountServices.initialize(context, defaultEnabled = true)
    }

    @After
    fun tearDown() {
        unmockkStatic("mozilla.components.support.ktx.android.content.ContextKt")
        preferences.edit().clear().commit()
        AccountServices.initialize(context, defaultEnabled = true)
    }

    @Test
    fun `production Fenix attachBaseContext defaults off without creating a saved choice`() {
        // Bypass the legacy Robolectric application's opted-in override, and call the
        // real FenixApplication.attachBaseContext, without starting native onCreate work.
        ProductionPolicyApplication().attachProductionContext(context)
        assertFalse(AccountServices.isEnabled)
        assertFalse(preferences.contains("enabled"))
    }

    @Test
    fun `production Fenix attachBaseContext preserves each explicit saved choice`() {
        for (choice in listOf(true, false)) {
            preferences.edit().putBoolean("enabled", choice).commit()
            val before = preferences.all
            ProductionPolicyApplication().attachProductionContext(context)
            assertEquals(choice, AccountServices.isEnabled)
            assertEquals(before, preferences.all)
        }
    }

    @Test
    fun `production child attachment never accesses app storage and closes account admission`() {
        preferences.edit().putBoolean("enabled", true).commit()
        val before = preferences.all
        val child = object : ContextWrapper(context) {
            override fun getSharedPreferences(name: String, mode: Int): SharedPreferences =
                error("Isolated child must not access app preferences")

            override fun getSystemService(name: String): Any? =
                error("Child attachment must not query a system service")
        }
        every { child.isMainProcess() } returns false
        val application = ProductionPolicyApplication()
        application.attachProductionContext(child)
        assertFalse(AccountServices.isEnabled)
        assertTrue(application.baseContext === child)
        assertEquals(before, preferences.all)
        assertFalse(AccountServices.commitChoiceForRestart(child, true))
    }

    private class ProductionPolicyApplication : FenixApplication() {
        fun attachProductionContext(context: Context) = super.attachBaseContext(context)
    }

    @Test
    fun `failed commit neither cancels work nor restarts`() = runTest {
        val calls = mutableListOf<String>()
        assertFalse(applyAccountServicesChange(
            commit = { calls += "commit"; false },
            cancel = { calls += "cancel" },
            restart = { calls += "restart" },
        ))
        assertEquals(listOf("commit"), calls)
    }

    @Test
    fun `persistence exception reports failure without cancelling or restarting`() = runTest {
        assertFalse(applyAccountServicesChange(
            commit = { throw IllegalStateException("read-only preference storage") },
            cancel = { error("Must not cancel") },
            restart = { error("Must not restart") },
        ))
    }

    @Test
    fun `durable decision precedes cancellation and process restart`() = runTest {
        val calls = mutableListOf<String>()
        assertTrue(applyAccountServicesChange(
            commit = { calls += "commit"; true },
            cancel = { calls += "cancel" },
            restart = { calls += "restart" },
        ))
        assertEquals(listOf("commit", "cancel", "restart"), calls)
    }

    @Test
    fun `cancellation failure still reaches process termination boundary`() = runTest {
        var restarted = false
        try {
            applyAccountServicesChange(
                commit = { true },
                cancel = { throw IllegalStateException("WorkManager cancellation timeout") },
                restart = { restarted = true },
            )
            error("Cancellation exception was unexpectedly swallowed")
        } catch (_: IllegalStateException) {
            assertTrue(restarted)
        }
    }

    @Test
    fun `restart targets enabled launcher alias without forwarding authentication data`() {
        val context: Context = mockk()
        val packageManager: PackageManager = mockk()
        every { context.packageName } returns "org.redoubtbrowser"
        every { context.packageManager } returns packageManager
        every { packageManager.getLaunchIntentForPackage("org.redoubtbrowser") } returns
            Intent().setComponent(ComponentName("org.redoubtbrowser", "AlternateIcon"))
                .setData(android.net.Uri.parse("https://account.invalid/callback?code=secret"))
                .putExtra("authToken", "must-not-forward")
        val restart = AccountServicesPreference.restartIntent(context)!!
        assertEquals(ComponentName("org.redoubtbrowser", "AlternateIcon"), restart.component)
        assertNull(restart.data)
        assertFalse(restart.hasExtra("authToken"))
        assertTrue(restart.getBooleanExtra(AccountServicesPreference.OPEN_SETTINGS, false))
        assertTrue(restart.flags and Intent.FLAG_ACTIVITY_NEW_TASK != 0)
        assertTrue(restart.flags and Intent.FLAG_ACTIVITY_CLEAR_TASK != 0)
    }

    @Test
    fun `missing launcher is rejected before any preference change`() {
        val context: Context = mockk()
        val packageManager: PackageManager = mockk()
        every { context.packageName } returns "org.redoubtbrowser"
        every { context.packageManager } returns packageManager
        every { packageManager.getLaunchIntentForPackage(any()) } returns null
        assertNull(AccountServicesPreference.restartIntent(context))
    }
}
