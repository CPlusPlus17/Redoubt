/* Compile-only stand-ins for the Fenix classes UpdateCheck.kt touches. The
 * signatures are the 157 tree's; the bodies are never run by the tests (they
 * exercise UpdateChecker, which takes everything injected). If upstream changes
 * one of these signatures, this harness will not notice: the real
 * `./mach gradle fenix:testDebugUnitTest` remains the authority. */
package org.mozilla.fenix

import android.content.SharedPreferences

object BuildConfig {
    const val LW_UPDATE_CHECK_PUBKEY = ""
    const val LW_UPDATE_CHECK_ENDPOINT = ""
}

@Suppress("ClassName")
object R {
    object string {
        const val pref_key_lw_update_check = 1
        const val lw_update_check_available_title = 2
        const val lw_update_check_available_message = 3
        const val lw_update_check_open_download = 4
        const val lw_update_check_later = 5
    }
}

enum class BrowserDirection { FromHome }

open class HomeActivity : android.app.Activity() {
    fun openToBrowser(from: BrowserDirection) {}
}

class Settings(val preferences: SharedPreferences)
class Core(val client: mozilla.components.concept.fetch.Client)
class FenixBrowserUseCases {
    fun loadUrlOrSearch(searchTermOrURL: String, newTab: Boolean) {}
}
class UseCases(val fenixBrowserUseCases: FenixBrowserUseCases)
class Components(val settings: Settings, val core: Core, val useCases: UseCases)
