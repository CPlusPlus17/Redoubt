/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

package mozilla.components.service.fxa

import android.content.Context
import mozilla.components.support.base.log.logger.Logger

/**
 * Process-wide account-service admission policy. Embedders initialize it before
 * content providers/workers run. Other A-C consumers retain their existing default.
 *
 * A committed change closes admission for this process in BOTH directions. Only
 * a new process reads the new choice and can enable services. Restart, rather
 * than coroutine cancellation, ends synchronous Rust sync and retained accounts.
 */
object AccountServices {
    internal const val PREFERENCES = "mozilla.components.service.fxa.account-services"
    internal const val ENABLED = "enabled"

    @Volatile
    var isEnabled: Boolean = true
        private set

    @Volatile
    internal var generation: Long = 0
        private set

    private val logger = Logger("AccountServices")
    private var restarting = false

    /**
     * Close admission in a non-main process without reading app storage. Call during
     * application attachment, before providers or other account consumers can run.
     * This process cannot commit a restart choice; only the main process owns it.
     */
    @Synchronized
    fun disableForProcess() {
        isEnabled = false
        generation += 1
        restarting = true
    }

    /** Read a saved explicit choice without writing a default or account data. */
    @Synchronized
    fun initialize(context: Context, defaultEnabled: Boolean = true) {
        isEnabled = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
            .getBoolean(ENABLED, defaultEnabled)
        generation += 1
        restarting = false
    }

    /**
     * Commit before cancelling anything. A failed disk write must not change the
     * running policy; SharedPreferences updates memory even when commit fails,
     * so attempt to restore its previous key/value as well. If rollback also fails,
     * durability is unknown; never report a saved transition. No account/engine store is edited.
     */
    @Synchronized
    fun commitChoiceForRestart(context: Context, enabled: Boolean): Boolean {
        if (restarting) return false
        val preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
        val hadChoice = preferences.contains(ENABLED)
        val oldChoice = preferences.getBoolean(ENABLED, isEnabled)
        if (!preferences.edit().putBoolean(ENABLED, enabled).commit()) {
            val rollback = preferences.edit()
            if (hadChoice) rollback.putBoolean(ENABLED, oldChoice) else rollback.remove(ENABLED)
            if (!rollback.commit()) {
                logger.warn("Account choice write and rollback failed; saved choice is unverified")
            }
            return false
        }
        // Prevent queued callers from starting service work during shutdown.
        isEnabled = false
        generation += 1
        restarting = true
        return true
    }
}
