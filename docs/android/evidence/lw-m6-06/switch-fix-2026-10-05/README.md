# Update-check switch fix (2026-10-05)

**Defect** (found in device acceptance of the 157.0-2 build, CI run 37234607054, commit
`0ef74fad`; `docs/android/evidence/lw-m7-01/release-157.0-2/acceptance/` on branch
`release/157.0-2-acceptance`, commit `fd6a4104`, row 9 and probe 9a): the "Check for updates" row in
`patches/android/update-check.patch` was a plain `SwitchPreferenceCompat`. `SettingsFragment`
sets no `sharedPreferencesName`, so androidx persisted the switch to the default
SharedPreferences file (`org.redoubtbrowser_preferences.xml`). `UpdateCheck.isEnabled` reads
`components.settings.preferences` (`fenix_preferences`). The switch turned on and showed ON,
but the check never ran.

**Fix** (same patch): `UpdateCheck.bindSwitch`, called from
`SettingsFragment.setupPreferences`, reads the checked state from `isEnabled` and installs
upstream's `SharedPreferenceUpdater`, which writes `components.settings.preferences` under
the row's key. This is how upstream wires its own switches that live in `fenix_preferences`
(`CustomizationFragment`'s gesture switches). The row is `android:persistent="false"`, so
androidx keeps no second copy. Binding writes nothing: a value that is absent reads as off. A
value that 157.0-2 left in the default file is ignored, not migrated. `isEnabled` gained a
`compiledIn` parameter (default `isCompiledIn`) so that the test build, which has no key, can
ask it. New Robolectric test: `UpdateCheckSwitchTest`, 4 tests.

## Runs

| File | What | Result |
| --- | --- | --- |
| `check-patchfail-android-157.txt` | `./scripts/check-patchfail.sh --targets=android` against `firefox-157.0.source.tar.xz` (common.txt + android.txt) | exit 0, no reject, no fuzz/offset on update-check.patch |
| `jvm-harness-157-tree.txt` | `scripts/tests/test-update-check-jvm.sh` against the 157 tree (patched), Kotlin 2.4.0, android-37.1 `android.jar`, in the `librewolf-android-build:fx157` image | `UpdateCheck.kt` compiles with `-Werror`; wiring check passes; 11/11 `UpdateCheckerTest`; 14/14 cross-checks |
| `jvm-harness-old-patch.txt` | the same harness with `--patch` = `update-check.patch` at `0ef74fad` (the 157.0-2 code) | exit 2: "lost the switch wiring" (the new step 1 catches the defect) |
| `robolectric-158-tree.txt` | `./mach gradle fenix:testDebugUnitTest --tests 'org.mozilla.fenix.lw.*' --tests org.mozilla.fenix.settings.SettingsFragmentTest` | `:fenix:compileDebugKotlin` and `:fenix:compileDebugUnitTestKotlin` pass (`-Werror`); 4/4 `UpdateCheckSwitchTest`, 11/11 `UpdateCheckerTest`, `DohProviderMigrationTest` and `SettingsFragmentTest` pass, 0 failures |
| `robolectric-negative-control.txt` | the same, `UpdateCheckSwitchTest` only, with the `SharedPreferenceUpdater` line removed from `bindSwitch` (androidx persistence only, as in 157.0-2) | "turning the switch on enables the check…" fails with an `AssertionError`, so the test detects the defect |

**Limits of these runs.** The Robolectric runs used the Firefox **158** working tree
(`ff158/work/buildrepo/librewolf-158.0-1`, the only tree on this host with a built GeckoView
AAR for Fenix's unit tests). It was mounted as an overlay (`podman -v …:O`), so the tree itself
was not modified. The fixed `UpdateCheck.kt`, `UpdateCheckSwitchTest.kt` and
`UpdateCheckerTest.kt` were copied in byte-for-byte from the patched 157 tree. The
`SettingsFragment.kt` and `preferences.xml` changes were applied as the same text edit. Every
symbol the fix uses was checked in the patched 157 tree: `SharedPreferenceUpdater.kt` is
identical in 157 and 158, both use `androidx.preference` 1.2.1 (`TwoStatePreference`), and
`Settings.FENIX_PREFERENCES` is `fenix_preferences`. The 157 Fenix module itself was not
compiled, because no 157 GeckoView AAR is on this host. The on-device proof is still the ON
half of `android-smoke.sh --check-update-privacy` on a new build.
