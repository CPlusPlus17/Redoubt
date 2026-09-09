/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

package mozilla.components.feature.fxsuggest

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.work.ListenableWorker
import androidx.work.testing.TestListenableWorkerBuilder
import kotlinx.coroutines.test.runTest
import mozilla.appservices.suggest.SuggestionQuery
import mozilla.components.feature.fxsuggest.client.SuggestMerinoClient
import mozilla.components.support.test.mock
import mozilla.components.support.test.robolectric.testContext
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class FxSuggestAdmissionTest {
    private var choices = FxSuggestChoices(enabled = false, web = false, sponsored = false, online = false)

    @Before
    fun setUp() {
        FxSuggestAdmission.configure { choices }
        GlobalFxSuggestDependencyProvider.initialize { error("Disabled work resolved the Suggest dependency factory") }
    }

    @After
    fun tearDown() {
        GlobalFxSuggestDependencyProvider.initialize(mock<FxSuggestStorage>())
        GlobalFxSuggestDependencyProvider.storage = null
        FxSuggestAdmission.configure { FxSuggestChoices() }
    }

    @Test
    fun `master and online choices have separate effective boundaries`() {
        assertFalse(FxSuggestAdmission.snapshot().choices.localEnabled)
        choices = FxSuggestChoices(enabled = true, web = false, sponsored = true, online = true)
        assertTrue(FxSuggestAdmission.snapshot().choices.localEnabled)
        assertFalse(FxSuggestAdmission.snapshot().choices.onlineEnabled)
        choices = choices.copy(web = true, online = false)
        assertTrue(FxSuggestAdmission.snapshot().choices.localEnabled)
        assertFalse(FxSuggestAdmission.snapshot().choices.onlineEnabled)
    }

    @Test
    fun `off-on cycle invalidates an earlier admitted operation even when final choices match`() {
        choices = FxSuggestChoices()
        val admitted = FxSuggestAdmission.snapshot()
        assertTrue(FxSuggestAdmission.isCurrent(admitted))
        choices = choices.copy(enabled = false)
        FxSuggestAdmission.choicesChanged()
        choices = choices.copy(enabled = true)
        FxSuggestAdmission.choicesChanged()
        assertFalse(FxSuggestAdmission.isCurrent(admitted))
    }

    @Test
    fun `disabled worker completes before dependency provider or storage construction`() = runTest {
        val worker = TestListenableWorkerBuilder<FxSuggestIngestionWorker>(testContext).build()
        assertEquals(ListenableWorker.Result.success(), worker.doWork())
        assertNull(GlobalFxSuggestDependencyProvider.storage)
    }

    @Test
    fun `disabled scheduling needs no WorkManager initialization`() {
        FxSuggestIngestionScheduler(testContext).startPeriodicIngestion()
        assertNull(GlobalFxSuggestDependencyProvider.storageIfEnabled())
    }

    @Test
    fun `disabled storage query ingestion and startup ingestion never initialize native store`() = runTest {
        val storage = FxSuggestStorage(testContext, remoteSettingsService = mock())
        assertTrue(storage.query(SuggestionQuery(keyword = "test", providers = emptyList(), limit = 1)).isEmpty())
        assertTrue(storage.ingest())
        storage.runStartupIngestion()
        storage.cancelReads()
        assertFalse(storage.store.isInitialized())
    }

    @Test
    fun `retained suggestion provider and cancellation cannot resolve storage while off`() = runTest {
        val provider = FxSuggestSuggestionProvider(
            loadUrlUseCase = mock(),
            includeSponsoredSuggestions = true,
            includeNonSponsoredSuggestions = true,
            sponsoredSuggestionDescription = "Sponsored",
        )
        assertTrue(provider.onInputChanged("test").isEmpty())
        provider.onInputCancelled()
        assertNull(GlobalFxSuggestDependencyProvider.storage)
    }

    @Test
    fun `default Merino client stays native-free before explicit online consent`() {
        val client = SuggestMerinoClient()
        assertNull(client.makeRequest("test stock"))
        choices = FxSuggestChoices(enabled = true, web = true, sponsored = false, online = false)
        assertNull(client.makeRequest("test stock"))
    }

    @Test
    fun `enabling a local choice resolves storage lazily once without enabling online requests`() {
        val storage: FxSuggestStorage = mock()
        var constructions = 0
        GlobalFxSuggestDependencyProvider.initialize { constructions += 1; storage }
        assertNull(GlobalFxSuggestDependencyProvider.storageIfEnabled())
        assertEquals(0, constructions)
        choices = FxSuggestChoices(enabled = true, web = true, sponsored = false, online = false)
        assertEquals(storage, GlobalFxSuggestDependencyProvider.storageIfEnabled())
        assertEquals(storage, GlobalFxSuggestDependencyProvider.storageIfEnabled())
        assertEquals(1, constructions)
        assertFalse(FxSuggestAdmission.snapshot().choices.onlineEnabled)
    }
}
