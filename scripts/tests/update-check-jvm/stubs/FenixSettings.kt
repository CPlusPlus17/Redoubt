/* Compile-only: org.mozilla.fenix.settings.SharedPreferenceUpdater, the listener
 * UpdateCheck.bindSwitch puts on the Settings row. Signature from the 157 tree
 * (fenix/app/src/main/java/org/mozilla/fenix/settings/SharedPreferenceUpdater.kt);
 * the body does what upstream's does, without core-ktx's edit {}, and is never
 * run here: the switch needs an Android Context, so UpdateCheckSwitchTest runs
 * only under `./mach gradle fenix:testDebugUnitTest` (Robolectric). */
package org.mozilla.fenix.settings

import androidx.preference.Preference
import org.mozilla.fenix.ext.components

open class SharedPreferenceUpdater : Preference.OnPreferenceChangeListener {
    override fun onPreferenceChange(preference: Preference, newValue: Any?): Boolean {
        val newBooleanValue = newValue as? Boolean ?: return false
        preference.context.components.settings.preferences.edit().putBoolean(preference.key, newBooleanValue).apply()
        return true
    }
}
