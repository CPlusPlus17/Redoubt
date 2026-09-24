/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

package org.mozilla.fenix

import android.content.Intent
import androidx.fragment.app.FragmentManager
import androidx.navigation.NavController
import androidx.navigation.fragment.NavHostFragment
import io.mockk.Called
import io.mockk.every
import io.mockk.mockk
import io.mockk.spyk
import io.mockk.verify
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.mozilla.fenix.components.share.SEND_TO_DEVICES_ACTION
import org.mozilla.fenix.customtabs.ExternalAppBrowserActivity
import org.mozilla.fenix.settings.AccountServicesPreference
import org.mozilla.fenix.settings.account.AuthCustomTabActivity
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class HomeActivityAccountSettingsTest {
    @Test
    fun `normal activity consumes account settings request and opens settings`() {
        val navController = mockk<NavController>(relaxed = true)
        val navHost = mockk<NavHostFragment>()
        val fragments = mockk<FragmentManager>()
        every { navHost.navController } returns navController
        every { fragments.findFragmentById(R.id.container) } returns navHost
        // The real lazy navHost must capture this activity, not a copied spy.
        val activity = object : HomeActivity() {
            override fun getSupportFragmentManager(): FragmentManager = fragments
        }
        val intent = Intent().putExtra(AccountServicesPreference.OPEN_SETTINGS, true)

        activity.handleNewIntent(intent)

        verify(exactly = 1) {
            navController.navigate(NavGraphDirections.actionGlobalSettingsFragment())
        }
        assertFalse(intent.hasExtra(AccountServicesPreference.OPEN_SETTINGS))
    }

    @Test
    fun `normal activity does not consume false account settings flag`() {
        val activity = spyk(HomeActivity())
        val fragments = mockk<FragmentManager>()
        every { activity.supportFragmentManager } returns fragments
        // A send-to-devices request without a URL takes the existing early return.
        val intent = Intent(SEND_TO_DEVICES_ACTION)
            .putExtra(AccountServicesPreference.OPEN_SETTINGS, false)

        activity.handleNewIntent(intent)

        assertTrue(intent.hasExtra(AccountServicesPreference.OPEN_SETTINGS))
        assertFalse(intent.getBooleanExtra(AccountServicesPreference.OPEN_SETTINGS, true))
        verify { fragments wasNot Called }
    }

    @Test
    fun `external custom tab ignores even a true account settings flag`() {
        assertCustomTabIgnoresSettingsRequest(spyk(ExternalAppBrowserActivity()))
    }

    @Test
    fun `auth custom tab ignores even a true account settings flag`() {
        assertCustomTabIgnoresSettingsRequest(spyk(AuthCustomTabActivity()))
    }

    private fun assertCustomTabIgnoresSettingsRequest(activity: HomeActivity) {
        val intent = mockk<Intent>()
        every { intent.getBooleanExtra(AccountServicesPreference.OPEN_SETTINGS, false) } returns true
        val fragments = mockk<FragmentManager>()
        every { activity.supportFragmentManager } returns fragments

        activity.handleNewIntent(intent)

        verify { intent wasNot Called }
        verify { fragments wasNot Called }
    }
}
