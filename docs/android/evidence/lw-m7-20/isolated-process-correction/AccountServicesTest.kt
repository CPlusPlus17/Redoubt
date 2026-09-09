/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

package mozilla.components.service.fxa

import android.content.Context
import android.content.SharedPreferences
import androidx.test.ext.junit.runners.AndroidJUnit4
import mozilla.components.support.test.mock
import mozilla.components.support.test.robolectric.testContext
import mozilla.components.support.test.whenever
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.Mockito.verify
import org.mockito.Mockito.verifyNoInteractions

@RunWith(AndroidJUnit4::class)
class AccountServicesTest {
    private val preferences get() = testContext.getSharedPreferences(AccountServices.PREFERENCES, Context.MODE_PRIVATE)

    @Before
    fun setUp() {
        preferences.edit().clear().commit()
        AccountServices.initialize(testContext, defaultEnabled = true)
    }

    @After
    fun tearDown() {
        preferences.edit().clear().commit()
        AccountServices.initialize(testContext, defaultEnabled = true)
    }

    @Test
    fun `non-main admission closes without reading or changing a saved parent choice`() {
        preferences.edit().putBoolean(AccountServices.ENABLED, true).commit()
        AccountServices.initialize(testContext, defaultEnabled = false)
        val before = preferences.all
        val previousGeneration = AccountServices.generation
        val inaccessibleContext: Context = mock()

        AccountServices.disableForProcess()

        assertFalse(AccountServices.isEnabled)
        assertEquals(previousGeneration + 1, AccountServices.generation)
        assertFalse(AccountServices.commitChoiceForRestart(inaccessibleContext, true))
        verifyNoInteractions(inaccessibleContext)
        assertEquals(before, preferences.all)
        AccountServices.initialize(testContext, defaultEnabled = false)
        assertTrue(AccountServices.isEnabled)
    }

    @Test
    fun `first install is off without persisting an invented choice`() {
        AccountServices.initialize(testContext, defaultEnabled = false)
        assertFalse(AccountServices.isEnabled)
        assertFalse(preferences.contains(AccountServices.ENABLED))
    }

    @Test
    fun `explicit true survives disabled product default`() {
        preferences.edit().putBoolean(AccountServices.ENABLED, true).commit()
        AccountServices.initialize(testContext, defaultEnabled = false)
        assertTrue(AccountServices.isEnabled)
    }

    @Test
    fun `explicit false survives an enabled embedder default`() {
        preferences.edit().putBoolean(AccountServices.ENABLED, false).commit()
        AccountServices.initialize(testContext, defaultEnabled = true)
        assertFalse(AccountServices.isEnabled)
    }

    @Test
    fun `enable is durable but no service starts until new process initialization`() {
        AccountServices.initialize(testContext, defaultEnabled = false)
        assertTrue(AccountServices.commitChoiceForRestart(testContext, true))
        assertTrue(preferences.getBoolean(AccountServices.ENABLED, false))
        assertFalse(AccountServices.isEnabled)
        AccountServices.initialize(testContext, defaultEnabled = false)
        assertTrue(AccountServices.isEnabled)
    }

    @Test
    fun `disable closes admission and remains disabled on the next process`() {
        assertTrue(AccountServices.isEnabled)
        assertTrue(AccountServices.commitChoiceForRestart(testContext, false))
        assertFalse(AccountServices.isEnabled)
        AccountServices.initialize(testContext, defaultEnabled = false)
        assertFalse(AccountServices.isEnabled)
    }

    @Test
    fun `second dialog cannot replace an already committed restart decision`() {
        assertTrue(AccountServices.commitChoiceForRestart(testContext, false))
        assertFalse(AccountServices.commitChoiceForRestart(testContext, true))
        assertFalse(preferences.getBoolean(AccountServices.ENABLED, true))
    }

    @Test
    fun `failed commit retains current service policy and restores previous in-memory choice`() {
        val context: Context = mock()
        val prefs: SharedPreferences = mock()
        val write: SharedPreferences.Editor = mock()
        val rollback: SharedPreferences.Editor = mock()
        whenever(context.getSharedPreferences(AccountServices.PREFERENCES, Context.MODE_PRIVATE)).thenReturn(prefs)
        whenever(prefs.contains(AccountServices.ENABLED)).thenReturn(true)
        whenever(prefs.getBoolean(AccountServices.ENABLED, true)).thenReturn(true)
        whenever(prefs.edit()).thenReturn(write, rollback)
        whenever(write.putBoolean(AccountServices.ENABLED, false)).thenReturn(write)
        whenever(write.commit()).thenReturn(false)
        whenever(rollback.commit()).thenReturn(true)
        assertFalse(AccountServices.commitChoiceForRestart(context, false))
        assertTrue(AccountServices.isEnabled)
        verify(rollback).putBoolean(AccountServices.ENABLED, true)
        verify(rollback).commit()
    }

    @Test
    fun `failed first write removes the spurious in-memory explicit choice`() {
        val context: Context = mock()
        val prefs: SharedPreferences = mock()
        val write: SharedPreferences.Editor = mock()
        val rollback: SharedPreferences.Editor = mock()
        whenever(context.getSharedPreferences(AccountServices.PREFERENCES, Context.MODE_PRIVATE)).thenReturn(prefs)
        whenever(prefs.contains(AccountServices.ENABLED)).thenReturn(false)
        whenever(prefs.edit()).thenReturn(write, rollback)
        whenever(write.putBoolean(AccountServices.ENABLED, false)).thenReturn(write)
        whenever(write.commit()).thenReturn(false)
        whenever(rollback.commit()).thenReturn(true)
        assertFalse(AccountServices.commitChoiceForRestart(context, false))
        assertTrue(AccountServices.isEnabled)
        verify(rollback).remove(AccountServices.ENABLED)
    }

    @Test
    fun `failed write and failed rollback retain running state without claiming durable restoration`() {
        val context: Context = mock()
        val prefs: SharedPreferences = mock()
        val write: SharedPreferences.Editor = mock()
        val rollback: SharedPreferences.Editor = mock()
        whenever(context.getSharedPreferences(AccountServices.PREFERENCES, Context.MODE_PRIVATE)).thenReturn(prefs)
        whenever(prefs.contains(AccountServices.ENABLED)).thenReturn(true)
        whenever(prefs.getBoolean(AccountServices.ENABLED, true)).thenReturn(true)
        whenever(prefs.edit()).thenReturn(write, rollback)
        whenever(write.putBoolean(AccountServices.ENABLED, false)).thenReturn(write)
        whenever(write.commit()).thenReturn(false)
        whenever(rollback.commit()).thenReturn(false)
        val generation = AccountServices.generation
        assertFalse(AccountServices.commitChoiceForRestart(context, false))
        assertTrue(AccountServices.isEnabled)
        assertEquals(generation, AccountServices.generation)
        verify(rollback).putBoolean(AccountServices.ENABLED, true)
        verify(rollback).commit()
        // Neither false receipt proves the disk value. A later process must read
        // the persisted value rather than treat this running state as a saved one.
        whenever(prefs.getBoolean(AccountServices.ENABLED, true)).thenReturn(false)
        AccountServices.initialize(context, defaultEnabled = true)
        assertFalse(AccountServices.isEnabled)
    }

    @Test
    fun `account state and engine selections are not cleared by service transitions`() {
        val account = testContext.getSharedPreferences(FXA_STATE_PREFS_KEY, Context.MODE_PRIVATE)
        val engines = testContext.getSharedPreferences(mozilla.components.service.fxa.manager.SyncEnginesStorage.SYNC_ENGINES_KEY, Context.MODE_PRIVATE)
        account.edit().putString(FXA_STATE_KEY, "retained-authenticated-account").commit()
        engines.edit().putBoolean("history", false).putBoolean("bookmarks", true).commit()
        val beforeAccount = account.all
        val beforeEngines = engines.all
        assertTrue(AccountServices.commitChoiceForRestart(testContext, false))
        org.junit.Assert.assertEquals(beforeAccount, account.all)
        org.junit.Assert.assertEquals(beforeEngines, engines.all)
        account.edit().clear().commit()
        engines.edit().clear().commit()
    }
}
