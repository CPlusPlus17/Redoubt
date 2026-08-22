# Bug reports for Firefox / Fenix upstream

Defects found in the Fenix (mobile/android) source while building the LibreWolf
Android port. These are **Firefox/Fenix** upstream bugs, distinct from the
LibreWolf build-tooling reports in `UPSTREAM-REPORTS.md`.

Written as **reproductions, not patches**: each is a couple of minutes to confirm
from a clean 153.0.4 tree and a few lines to fix. Nobody needs to accept anyone's
code.

Status: **DRAFT — pending owner sign-off and filing.** No bug link recorded yet.
Per the M5 ground rules, public wording is not filed or published without the
project owner's sign-off. The bug link, once filed, is to be recorded against
`LW-M5-01` in `tasks.yaml`.

---

## 1. `shouldUseNimbus` does not control `fission.webContentIsolationStrategy`, contradicting its own description

**Fenix, `mobile/android/fenix/app/nimbus.fml.yaml` (feature `fission`) and `GeckoProvider.kt` / `Core.kt`.**

The FML declares a `shouldUseNimbus` switch for the `fission` feature whose
description makes a specific promise (`nimbus.fml.yaml:509-514`):

```yaml
      shouldUseNimbus:
        description: >
            If true, the values for both SHIP and Fission set in this file apply.
            Otherwise, the values from modules/libpref/init/StaticPrefList.yaml apply.
        type: Boolean
        default: false
```

So the contract is: **flag on** → the FML values apply; **flag off (the default)** →
Gecko's own `StaticPrefList.yaml` values apply.

The same feature has two variables, `enabled` and `isolationStrategy`
(`nimbus.fml.yaml:515-535`). `isolationStrategy` is the web-content isolation
strategy: `0` = isolate nothing, `1` = isolate everything, `2` = isolate high value.
Its base `default: 0`, raised to `2` only for the `nightly` and `developer`
channels. On `release` it is therefore `0`.

**What the flag actually does.** `shouldUseNimbus` is read in exactly one place in
the non-test tree, `GeckoProvider.kt:137`:

```kotlin
if (FxNimbus.features.fission.value().shouldUseNimbus) {
    builder
        .fissionEnabled(FxNimbus.features.fission.value().enabled)
}
```

It gates **only** `.fissionEnabled(...)`. It never touches the isolation strategy.
The isolation strategy is applied **unconditionally** in `Core.kt:207-208`:

```kotlin
webContentIsolationStrategy =
    WebContentIsolationStrategy.fromValue(FxNimbus.features.fission.value().isolationStrategy),
```

regardless of `shouldUseNimbus`.

**The contradiction.** Gecko's own default for this pref is `1`
(`modules/libpref/init/StaticPrefList.yaml:6660-6663`, `value: 1`). With
`shouldUseNimbus` at its default (`false`), the description promises the
`StaticPrefList.yaml` value — i.e. `1` — applies. It does not: `Core.kt` applies the
FML value, which on `release` is `0` (isolate nothing). So a reader who trusts the
flag's description would believe that leaving Nimbus off restores Gecko's own
isolation default; instead it silently yields a **weaker** isolation than Gecko's
default, and the flag is not a switch for that pref at all.

In short, the flag is a *partial* gate: it controls one of the two `fission` FML
variables (`enabled`) but not the other (`isolationStrategy`), while its
description claims it selects the whole feature's source (FML vs StaticPrefList).
Either the description overstates the flag, or the flag should also gate
`isolationStrategy` (or `Core.kt` should fall back to the StaticPrefList value when
the flag is off). As written, the description and the code disagree.

**Reproduction** (clean 153.0.4 tree, `release` channel):

```sh
# 1. The flag's contract says "off -> StaticPrefList applies".
grep -n 'fission.webContentIsolationStrategy' modules/libpref/init/StaticPrefList.yaml
#    -> value: 1   (Gecko's own default)

# 2. The FML base default on release is 0 (only nightly/developer raise it to 2).
sed -n '515,535p' mobile/android/fenix/app/nimbus.fml.yaml

# 3. The flag is read in exactly one non-test place and gates only .fissionEnabled.
grep -rn 'shouldUseNimbus' mobile/android/fenix/app/src/main/java/org/mozilla/fenix/
#    -> GeckoProvider.kt:137  (gates .fissionEnabled only)

# 4. The isolation strategy is applied unconditionally, independent of the flag.
sed -n '207,208p' mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Core.kt
```

On a `release` build the effective value is therefore `0`, not the `1` the flag's
description says should apply when the flag is off.

**Suggested direction** (for the maintainer to choose): make `shouldUseNimbus`
gate the isolation-strategy application too, or have `Core.kt` fall back to the
StaticPrefList value when the flag is off, or fix the description to state that it
only controls `enabled`. The cleanest is for the flag to be an all-or-nothing
selector for the `fission` feature as its name and description imply.
