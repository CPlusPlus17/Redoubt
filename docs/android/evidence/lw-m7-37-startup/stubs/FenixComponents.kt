package org.mozilla.fenix.components
import kotlinx.coroutines.flow.StateFlow
import mozilla.components.browser.state.store.BrowserStore
import mozilla.components.concept.engine.Engine
import org.mozilla.fenix.utils.Settings
class Components { val settings: Settings get() = error("stub"); val core: Core get() = error("stub"); val useCases: UseCases get() = error("stub") }
class Core { val store: BrowserStore get() = error("stub"); val engine: Engine get() = error("stub")
  val historyStorage: History get() = error("stub"); val permissionStorage: PermissionStorage get() = error("stub")
  val sessionStorage: SessionStorage get() = error("stub") }
class SessionStorage { fun clear() {} }
class History { suspend fun deleteEverything() {} }
class PermissionStorage { suspend fun deleteAllSitePermissions() {} }
class UseCases { val tabsUseCases: Tabs get() = error("stub"); val downloadUseCases: Downloads get() = error("stub") }
class Tabs { val removeAllTabs: RemoveAll get() = error("stub") }
class RemoveAll { operator fun invoke(recoverable: Boolean = true) {} }
class Downloads { val removeAllDownloads: RemoveAllDownloads get() = error("stub") }
class RemoveAllDownloads { operator fun invoke() {} }
// Verbatim from ubo-preinstall.patch:
interface LibreWolfUboStartupGate {
    val state: StateFlow<LibreWolfUboPreinstaller.State>
    suspend fun awaitReady()
}
class LibreWolfUboPreinstaller {
    sealed interface State {
        data object Preparing : State
        data class Ready(val installed: Boolean, val enabled: Boolean) : State
        data class Failed(val reason: String) : State
    }
}
