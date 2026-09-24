/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

package mozilla.components.browser.engine.gecko.permission

import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.async
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import mozilla.components.concept.engine.permission.SitePermissions.Status
import mozilla.components.concept.engine.permission.SitePermissionsStorage
import mozilla.components.support.test.any
import mozilla.components.support.test.mock
import mozilla.components.support.test.whenever
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.Mockito.never
import org.mockito.Mockito.verify
import org.mockito.Mockito.verifyNoInteractions
import org.mozilla.geckoview.GeckoResult
import org.mozilla.geckoview.GeckoRuntime
import org.mozilla.geckoview.GeckoSession.PermissionDelegate.ContentPermission
import org.mozilla.geckoview.StorageController

@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(AndroidJUnit4::class)
class OriginBoundPermissionsStorageTest {
    private val dispatcher = StandardTestDispatcher()
    private val controller = mock<StorageController>()
    private val disk = mock<SitePermissionsStorage>()
    private val runtime = mock<GeckoRuntime>()
    private lateinit var storage: GeckoSitePermissionsStorage

    @Before
    fun setup() {
        Dispatchers.setMain(dispatcher)
        whenever(runtime.storageController).thenReturn(controller)
        storage = GeckoSitePermissionsStorage(runtime, disk)
    }

    @After
    fun tearDown() { Dispatchers.resetMain() }

    @Test
    fun `engine-only session and private records are visible without any Room row`() = runTest(dispatcher) {
        val normal = originPermission()
        val privateRecord = originPermission(privateMode = true)
        val otherContainer = originPermission(contextId = "other")
        val permissions = result(listOf(normal, privateRecord, otherContainer))
        whenever(controller.allPermissions).thenReturn(permissions)
        assertEquals(listOf(normal.toOriginBoundPermission()), storage.listOriginBoundPermissions(false, null))
        assertEquals(listOf(privateRecord.toOriginBoundPermission()), storage.listOriginBoundPermissions(true, null))
        assertEquals(listOf(otherContainer.toOriginBoundPermission()), storage.listOriginBoundPermissions(false, "other"))
        verifyNoInteractions(disk)
    }

    @Test
    fun `revocation removes only the selected exact origin and preserves session lifetime`() = runTest(dispatcher) {
        val selected = originPermission()
        val anotherPort = originPermission(uri = "https://frame.test:9443")
        val permissions = result(listOf(anotherPort, selected))
        whenever(controller.allPermissions).thenReturn(permissions)
        val write = result<Void>(null)
        whenever(controller.setPermissionWithLifetime(selected, ContentPermission.VALUE_PROMPT, false)).thenReturn(write)
        assertTrue(storage.updateOriginBoundPermission(selected.toOriginBoundPermission()!!, Status.NO_DECISION))
        verify(controller).setPermissionWithLifetime(selected, ContentPermission.VALUE_PROMPT, false)
        verify(controller, never()).setPermissionWithLifetime(anotherPort, ContentPermission.VALUE_PROMPT, false)
        verifyNoInteractions(disk)
    }

    @Test
    fun `stale snapshot or ended private session cannot recreate an exception`() = runTest(dispatcher) {
        val previous = originPermission(privateMode = true).toOriginBoundPermission()!!
        val permissions = result(emptyList<ContentPermission>())
        whenever(controller.allPermissions).thenReturn(permissions)
        assertFalse(storage.updateOriginBoundPermission(previous, Status.ALLOWED, true))
        verify(controller, never()).setPermissionWithLifetime(any(), org.mockito.Mockito.anyInt(), org.mockito.Mockito.anyBoolean())
        verifyNoInteractions(disk)
    }

    @Test
    fun `editing a private record forces session lifetime`() = runTest(dispatcher) {
        val record = originPermission(privateMode = true)
        val permissions = result(listOf(record))
        whenever(controller.allPermissions).thenReturn(permissions)
        val write = result<Void>(null)
        whenever(controller.setPermissionWithLifetime(record, ContentPermission.VALUE_DENY, false)).thenReturn(write)
        assertTrue(storage.updateOriginBoundPermission(record.toOriginBoundPermission()!!, Status.BLOCKED, true))
        verify(controller).setPermissionWithLifetime(record, ContentPermission.VALUE_DENY, false)
    }

    @Test
    fun `storage update waits for the exact engine write acknowledgement`() = runTest(dispatcher) {
        val record = originPermission()
        val permissions = result(listOf(record))
        whenever(controller.allPermissions).thenReturn(permissions)
        val write = mock<GeckoResult<Void>>()
        var acknowledge: GeckoResult.OnValueListener<Void, Void>? = null
        whenever(write.then<Void>(any(), any())).thenAnswer { invocation ->
            acknowledge = invocation.getArgument(0)
            mock<GeckoResult<Void>>()
        }
        whenever(controller.setPermissionWithLifetime(record, ContentPermission.VALUE_DENY, false)).thenReturn(write)
        val update = async { storage.updateOriginBoundPermission(record.toOriginBoundPermission()!!, Status.BLOCKED) }
        runCurrent()
        assertFalse(update.isCompleted)
        requireNotNull(acknowledge).onValue(null)
        assertTrue(update.await())
    }

    private fun <T> result(value: T?): GeckoResult<T> = mock<GeckoResult<T>>().also { result ->
        whenever(result.then<Void>(any(), any())).thenAnswer { invocation ->
            invocation.getArgument<GeckoResult.OnValueListener<T, Void>>(0).onValue(value)
            mock<GeckoResult<Void>>()
        }
    }
}
