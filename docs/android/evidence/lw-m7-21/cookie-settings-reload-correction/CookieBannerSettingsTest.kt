/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

package org.mozilla.fenix.settings.cookiebannerhandling

import androidx.fragment.app.FragmentActivity
import androidx.preference.SwitchPreferenceCompat
import io.mockk.every
import io.mockk.mockk
import io.mockk.verify
import mozilla.components.browser.state.store.BrowserStore
import mozilla.components.concept.engine.EngineSession.CookieBannerHandlingMode.DISABLED
import mozilla.components.concept.engine.EngineSession.CookieBannerHandlingMode.REJECT_ALL
import mozilla.components.concept.fetch.Client
import mozilla.components.feature.session.SessionUseCases
import mozilla.components.support.test.robolectric.testContext
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.mozilla.fenix.R
import org.mozilla.fenix.ext.components
import org.mozilla.fenix.ext.getPreferenceKey
import org.mozilla.fenix.helpers.FenixGleanTestRule
import org.mozilla.fenix.settings.SettingsFragment
import org.mozilla.fenix.utils.Settings
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import java.io.IOException
import mozilla.components.concept.engine.Settings as EngineSettings

@RunWith(RobolectricTestRunner::class)
class CookieBannerSettingsTest {
    private lateinit var settings: Settings
    private val engineSettings = mockk<EngineSettings>(relaxed = true)

    @get:Rule
    val gleanRule = FenixGleanTestRule(testContext)

    @Before
    fun setUp() {
        settings = Settings(testContext)
        every { testContext.components.settings } returns settings
        every { testContext.components.core.engine.settings } returns engineSettings
        every { testContext.components.core.engine.profiler } returns mockk(relaxed = true)
        val client = mockk<Client>()
        every { client.fetch(any()) } throws IOException("test")
        every { testContext.components.core.client } returns client
        val store = BrowserStore()
        every { testContext.components.core.store } returns store
        every { testContext.components.addonManager } returns mockk(relaxed = true)
        every { testContext.components.analytics } returns mockk(relaxed = true)
        every { testContext.components.backgroundServices } returns mockk(relaxed = true)
        every { testContext.components.useCases.sessionUseCases } returns SessionUseCases(store)
    }

    @Test
    fun `fresh defaults expose both controls and use rejection only`() {
        assertTrue(settings.shouldShowCookieBannerUI)
        assertTrue(settings.shouldUseCookieBanner)
        assertTrue(settings.shouldUseCookieBannerPrivateMode)
        assertEquals(REJECT_ALL, settings.getCookieBannerHandling())
        assertEquals(REJECT_ALL, settings.getCookieBannerHandlingPrivateMode())
        val fragment = fragment()
        assertTrue(preference(fragment, false).isVisible)
        assertTrue(preference(fragment, true).isVisible)
        assertTrue(preference(fragment, false).isChecked)
        assertTrue(preference(fragment, true).isChecked)
    }

    @Test
    fun `explicit normal and private false survive XML inflation and new Settings instances`() {
        settings.shouldUseCookieBanner = false
        settings.shouldUseCookieBannerPrivateMode = false
        repeat(2) {
            val fragment = fragment()
            assertFalse(preference(fragment, false).isChecked)
            assertFalse(preference(fragment, true).isChecked)
            val reopened = Settings(testContext)
            assertFalse(reopened.shouldUseCookieBanner)
            assertFalse(reopened.shouldUseCookieBannerPrivateMode)
        }
    }

    @Test
    fun `old private key false is preserved while absent normal key takes local default`() {
        settings.preferences.edit().putBoolean("pref_key_cookie_banner_private_mode", false).commit()
        val fragment = fragment()
        assertFalse(preference(fragment, true).isChecked)
        assertTrue(preference(fragment, false).isChecked)
        assertFalse(Settings(testContext).shouldUseCookieBannerPrivateMode)
    }

    @Test
    fun `normal control updates only its engine mode and persists both directions`() {
        val fragment = fragment()
        change(fragment, false, false)
        assertFalse(Settings(testContext).shouldUseCookieBanner)
        assertTrue(settings.shouldUseCookieBannerPrivateMode)
        verify { engineSettings.cookieBannerHandlingMode = DISABLED }
        verify(exactly = 0) { engineSettings.cookieBannerHandlingModePrivateBrowsing = any() }
        change(fragment, false, true)
        assertTrue(Settings(testContext).shouldUseCookieBanner)
        verify { engineSettings.cookieBannerHandlingMode = REJECT_ALL }
    }

    @Test
    fun `private control updates only its engine mode and persists both directions`() {
        val fragment = fragment()
        change(fragment, true, false)
        assertFalse(Settings(testContext).shouldUseCookieBannerPrivateMode)
        assertTrue(settings.shouldUseCookieBanner)
        verify { engineSettings.cookieBannerHandlingModePrivateBrowsing = DISABLED }
        verify(exactly = 0) { engineSettings.cookieBannerHandlingMode = any() }
        change(fragment, true, true)
        assertTrue(Settings(testContext).shouldUseCookieBannerPrivateMode)
        verify { engineSettings.cookieBannerHandlingModePrivateBrowsing = REJECT_ALL }
    }

    private fun fragment(): SettingsFragment {
        val activity = Robolectric.buildActivity(FragmentActivity::class.java).create().get()
        return SettingsFragment().also {
            activity.supportFragmentManager.beginTransaction().add(it, "cookie-banner-settings").commitNow()
            it.setupCookieBannerPreference(settings)
        }
    }

    private fun preference(fragment: SettingsFragment, privateMode: Boolean): SwitchPreferenceCompat {
        val key = if (privateMode) R.string.pref_key_cookie_banner_private_mode else R.string.pref_key_cookie_banner_normal_mode
        return requireNotNull(fragment.findPreference(testContext.getPreferenceKey(key)))
    }

    private fun change(fragment: SettingsFragment, privateMode: Boolean, enabled: Boolean) {
        val preference = preference(fragment, privateMode)
        assertTrue(preference.callChangeListener(enabled))
        preference.isChecked = enabled
    }
}
