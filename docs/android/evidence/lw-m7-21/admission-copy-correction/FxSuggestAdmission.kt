/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

package mozilla.components.feature.fxsuggest

/** Effective Firefox Suggest choices, distinct from ordinary search-engine suggestions. */
data class FxSuggestChoices(
    val enabled: Boolean = true,
    val web: Boolean = true,
    val sponsored: Boolean = true,
    val online: Boolean = true,
) {
    val localEnabled: Boolean get() = enabled && (web || sponsored)
    val onlineEnabled: Boolean get() = enabled && web && online
}

/**
 * Embedders install their choice reader before content providers/workers run.
 * Existing A-C embedders keep their existing behavior unless they configure a policy.
 * A generation also rejects results from an earlier off/on cycle.
 */
object FxSuggestAdmission {
    @ConsistentCopyVisibility
    data class Snapshot internal constructor(val choices: FxSuggestChoices, internal val generation: Long)

    private var reader: () -> FxSuggestChoices = { FxSuggestChoices() }
    private var previous = FxSuggestChoices()
    private var generation = 0L

    @Synchronized
    fun configure(readChoices: () -> FxSuggestChoices) {
        reader = readChoices
        previous = reader()
        generation += 1
    }

    /** Notify on every explicit choice change, including an off/on cycle between awaits. */
    @Synchronized
    fun choicesChanged() {
        generation += 1
    }

    @Synchronized
    fun snapshot(): Snapshot {
        val choices = reader()
        if (choices != previous) {
            previous = choices
            generation += 1
        }
        return Snapshot(choices, generation)
    }

    fun isCurrent(snapshot: Snapshot): Boolean = snapshot == this.snapshot()
}
