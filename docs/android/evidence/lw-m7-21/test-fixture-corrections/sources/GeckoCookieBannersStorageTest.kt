/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

package mozilla.components.browser.engine.gecko.cookiebanners

import android.os.Handler
import android.os.Looper
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.mozilla.geckoview.GeckoResult
import junit.framework.TestCase.assertEquals
import junit.framework.TestCase.assertFalse
import junit.framework.TestCase.assertNull
import junit.framework.TestCase.assertTrue
import kotlinx.coroutines.test.runTest
import mozilla.components.concept.engine.EngineSession.CookieBannerHandlingMode.DISABLED
import mozilla.components.concept.engine.EngineSession.CookieBannerHandlingMode.REJECT_OR_ACCEPT_ALL
import mozilla.components.support.test.mock
import mozilla.components.support.test.whenever
import org.junit.Before
import org.junit.Test
import org.mockito.Mockito
import org.mockito.Mockito.doNothing
import org.mockito.Mockito.doReturn
import org.mockito.Mockito.spy
import org.mockito.Mockito.verify
import org.mozilla.geckoview.GeckoRuntime
import org.mozilla.geckoview.StorageController

@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
class GeckoCookieBannersStorageTest {
    private lateinit var runtime: GeckoRuntime
    private lateinit var geckoStorage: GeckoCookieBannersStorage
    private lateinit var storageController: StorageController
    private lateinit var reportSiteDomainsRepository: ReportSiteDomainsRepository

    @Before
    fun setup() {
        Dispatchers.setMain(StandardTestDispatcher())
        storageController = mock()
        runtime = mock()
        reportSiteDomainsRepository = mock()

        whenever(runtime.storageController).thenReturn(storageController)

        geckoStorage = spy(GeckoCookieBannersStorage(runtime, reportSiteDomainsRepository))
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `set waits for the native result before completing`() = runTest {
        val result = GeckoResult<Void>(Handler(Looper.getMainLooper()))
        whenever(storageController.setCookieBannerModeForDomain("https://example.org", 0, true)).thenReturn(result)
        val update = async { geckoStorage.addException("https://example.org", true) }
        runCurrent()
        assertFalse(update.isCompleted)
        result.complete(null)
        shadowOf(Looper.getMainLooper()).idle()
        update.await()
        assertTrue(update.isCompleted)
        verify(storageController).setCookieBannerModeForDomain("https://example.org", 0, true)
    }

    @Test
    fun `remove surfaces native failure instead of completing successfully`() = runTest {
        val result = GeckoResult<Void>(Handler(Looper.getMainLooper()))
        whenever(storageController.removeCookieBannerModeForDomain("https://example.org", false)).thenReturn(result)
        val update = async { runCatching { geckoStorage.removeException("https://example.org", false) } }
        runCurrent()
        assertFalse(update.isCompleted)
        val failure = IllegalStateException("native failure")
        result.completeExceptionally(failure)
        shadowOf(Looper.getMainLooper()).idle()
        val actual = update.await().exceptionOrNull()
        // Coroutine stack-trace recovery may copy the exception while preserving its cause.
        assertEquals(failure.javaClass, actual?.javaClass)
        assertEquals(failure.message, actual?.message)
        assertTrue(generateSequence(actual) { it.cause }.any { it === failure })
    }

    @Test
    fun `cancelled write wait remains cancelled when the native reply arrives late`() = runTest {
        val result = GeckoResult<Void>(Handler(Looper.getMainLooper()))
        whenever(storageController.setCookieBannerModeForDomain("https://example.org", 0, false)).thenReturn(result)
        val update = async { geckoStorage.addException("https://example.org", false) }
        runCurrent()
        update.cancelAndJoin()
        result.complete(null)
        shadowOf(Looper.getMainLooper()).idle()
        assertTrue(update.isCancelled)
    }

    @Test
    fun `a read with no native callback can be cancelled`() = runTest {
        val result = GeckoResult<Int>(Handler(Looper.getMainLooper()))
        whenever(storageController.getCookieBannerModeForDomain("https://example.org", false)).thenReturn(result)
        val read = async { geckoStorage.findExceptionFor("https://example.org", false) }
        runCurrent()
        assertFalse(read.isCompleted)
        read.cancelAndJoin()
        result.complete(1)
        shadowOf(Looper.getMainLooper()).idle()
        assertTrue(read.isCancelled)
    }

    @Test
    fun `private storage keeps its captured token for writes reads and repeated scoping`() = runTest {
        val uri = "https://example.org"
        val tokenResult = GeckoResult<String>(Handler(Looper.getMainLooper()))
        whenever(storageController.getCookieBannerPrivateSessionToken()).thenReturn(tokenResult)
        val capture = async { geckoStorage.forCurrentPrivateSession() }
        runCurrent()
        assertFalse(capture.isCompleted)
        tokenResult.complete("session-one")
        shadowOf(Looper.getMainLooper()).idle()
        val scoped = capture.await()
        assertTrue(scoped === scoped.forCurrentPrivateSession())

        val setResult = GeckoResult<Void>(Handler(Looper.getMainLooper()))
        whenever(storageController.setCookieBannerModeForPrivateSession(uri, 0, "session-one")).thenReturn(setResult)
        val set = async { scoped.addException(uri, true) }
        runCurrent()
        assertFalse(set.isCompleted)
        setResult.complete(null)
        shadowOf(Looper.getMainLooper()).idle()
        set.await()

        val readResult = GeckoResult<Int>(Handler(Looper.getMainLooper()))
        whenever(storageController.getCookieBannerModeForPrivateSession(uri, "session-one")).thenReturn(readResult)
        val read = async { scoped.findExceptionFor(uri, true) }
        runCurrent()
        readResult.complete(0)
        shadowOf(Looper.getMainLooper()).idle()
        assertEquals(DISABLED, read.await())

        val removeResult = GeckoResult<Void>(Handler(Looper.getMainLooper()))
        whenever(storageController.removeCookieBannerModeForPrivateSession(uri, "session-one")).thenReturn(removeResult)
        val remove = async { scoped.removeException(uri, true) }
        runCurrent()
        removeResult.complete(null)
        shadowOf(Looper.getMainLooper()).idle()
        remove.await()
        verify(storageController).getCookieBannerPrivateSessionToken()
        verify(storageController).setCookieBannerModeForPrivateSession(uri, 0, "session-one")
        verify(storageController).getCookieBannerModeForPrivateSession(uri, "session-one")
        verify(storageController).removeCookieBannerModeForPrivateSession(uri, "session-one")
        assertTrue(runCatching { scoped.addException(uri, false) }.exceptionOrNull() is IllegalArgumentException)
        assertTrue(runCatching { scoped.addPersistentExceptionInPrivateMode(uri) }.exceptionOrNull() is IllegalStateException)
    }

    @Test
    fun `native token failure cannot fall back to unscoped private storage`() = runTest {
        val result = GeckoResult<String>(Handler(Looper.getMainLooper()))
        whenever(storageController.getCookieBannerPrivateSessionToken()).thenReturn(result)
        val capture = async { runCatching { geckoStorage.forCurrentPrivateSession() } }
        runCurrent()
        val failure = IllegalStateException("NS_ERROR_NOT_AVAILABLE")
        result.completeExceptionally(failure)
        shadowOf(Looper.getMainLooper()).idle()
        val actual = capture.await().exceptionOrNull()
        // Coroutine stack-trace recovery may copy the exception while preserving its cause.
        assertEquals(failure.javaClass, actual?.javaClass)
        assertEquals(failure.message, actual?.message)
        assertTrue(generateSequence(actual) { it.cause }.any { it === failure })
        verify(storageController).getCookieBannerPrivateSessionToken()
        Mockito.verifyNoMoreInteractions(storageController)
    }

    @Test
    fun `cancelled capture never returns storage when a new session token arrives late`() = runTest {
        val result = GeckoResult<String>(Handler(Looper.getMainLooper()))
        whenever(storageController.getCookieBannerPrivateSessionToken()).thenReturn(result)
        val capture = async { geckoStorage.forCurrentPrivateSession() }
        runCurrent()
        capture.cancelAndJoin()
        result.complete("replacement-session")
        shadowOf(Looper.getMainLooper()).idle()
        assertTrue(capture.isCancelled)
        verify(storageController).getCookieBannerPrivateSessionToken()
        Mockito.verifyNoMoreInteractions(storageController)
    }

    @Test
    fun `GIVEN a cookie banner mode WHEN adding an exception THEN add an exception for the given uri and browsing mode`() =
        runTest {
            val uri = "https://www.mozilla.org"

            doReturn(Unit).`when`(geckoStorage)
                .setGeckoException(uri = uri, mode = DISABLED, privateBrowsing = false)

            geckoStorage.addException(uri = uri, privateBrowsing = false)

            verify(geckoStorage).setGeckoException(uri, DISABLED, false)
        }

    @Test
    fun `GIVEN uri and browsing mode WHEN removing an exception THEN remove the exception`() =
        runTest {
            val uri = "https://www.mozilla.org"

            doReturn(Unit).`when`(geckoStorage).removeGeckoException(uri, false)

            geckoStorage.removeException(uri = uri, privateBrowsing = false)

            verify(geckoStorage).removeGeckoException(uri, false)
        }

    @Test
    fun `GIVEN uri and browsing mode WHEN querying an exception THEN return the matching exception`() =
        runTest {
            val uri = "https://www.mozilla.org"

            doReturn(REJECT_OR_ACCEPT_ALL).`when`(geckoStorage)
                .queryExceptionInGecko(uri = uri, privateBrowsing = false)

            val result = geckoStorage.findExceptionFor(uri = uri, privateBrowsing = false)
            assertEquals(REJECT_OR_ACCEPT_ALL, result)
        }

    @Test
    fun `GIVEN error WHEN querying an exception THEN return null`() =
        runTest {
            val uri = "https://www.mozilla.org"

            doReturn(null).`when`(geckoStorage)
                .queryExceptionInGecko(uri = uri, privateBrowsing = false)

            val result = geckoStorage.findExceptionFor(uri = uri, privateBrowsing = false)
            assertNull(result)
        }

    @Test
    fun `GIVEN uri and browsing mode WHEN checking for an exception THEN indicate if it has exceptions`() =
        runTest {
            val uri = "https://www.mozilla.org"

            doReturn(REJECT_OR_ACCEPT_ALL).`when`(geckoStorage)
                .queryExceptionInGecko(uri = uri, privateBrowsing = false)

            var result = geckoStorage.hasException(uri = uri, privateBrowsing = false)

            assertFalse(result!!)

            Mockito.reset(geckoStorage)

            doReturn(DISABLED).`when`(geckoStorage)
                .queryExceptionInGecko(uri = uri, privateBrowsing = false)

            result = geckoStorage.hasException(uri = uri, privateBrowsing = false)

            assertTrue(result!!)
        }

    @Test
    fun `GIVEN an error WHEN checking for an exception THEN indicate if that an error happened`() =
        runTest {
            val uri = "https://www.mozilla.org"

            doReturn(null).`when`(geckoStorage)
                .queryExceptionInGecko(uri = uri, privateBrowsing = false)

            val result = geckoStorage.hasException(uri = uri, privateBrowsing = false)

            assertNull(result)
        }

    @Test
    fun `GIVEN a cookie banner mode WHEN adding a persistent exception in private mode THEN add a persistent exception for the given uri in private browsing mode`() =
        runTest {
            val uri = "https://www.mozilla.org"

            doNothing().`when`(geckoStorage)
                .setPersistentPrivateGeckoException(uri = uri, mode = DISABLED)

            geckoStorage.addPersistentExceptionInPrivateMode(uri = uri)

            verify(geckoStorage).setPersistentPrivateGeckoException(uri, DISABLED)
        }

    @Test
    fun `GIVEN site domain url WHEN checking if site domain is reported THEN the report site domain repository gets called`() =
        runTest {
            val reportSiteDomainUrl = "mozilla.org"

            geckoStorage.isSiteDomainReported(reportSiteDomainUrl)

            verify(reportSiteDomainsRepository).isSiteDomainReported(reportSiteDomainUrl)
        }

    @Test
    fun `GIVEN site domain url  WHEN saving a site domain THEN the save method from repository should get called`() =
        runTest {
            val reportSiteDomainUrl = "mozilla.org"

            geckoStorage.saveSiteDomain(reportSiteDomainUrl)

            verify(reportSiteDomainsRepository).saveSiteDomain(reportSiteDomainUrl)
        }
}
