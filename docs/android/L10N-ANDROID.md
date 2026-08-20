# Localisation and branding for the Fenix UI

**Owner: LW-M4-12.** The mechanism is `patches/android/l10n-strings.patch`,
which adds `mobile/android/lw-brand/` to the tree and hooks it into the Gradle
build. This file says what it does, what it is measured to achieve, what it
deliberately does *not* cover, and how to re-sync it on a rebase.

---

## The problem, and the half of it that turned out not to be a problem

LW-M0-03 found that `--with-l10n-base` "works on Android but covers almost
nothing": `mobile/android/locales/en-US` holds two `.ftl` files, so the
repository's `l10n/` overlay and the `firefox-l10n` pin from LW-M0-04 have
**zero** effect on the Fenix UI. That is correct and it is still correct.

What follows from it is *not* that the Fenix UI is unlocalised. Check the tree
before you fix that:

```sh
ls firefox-153.0.4/mobile/android/fenix/app/src/main/res | grep -c '^values-'   # 130
head -1 firefox-153.0.4/mobile/android/fenix/l10n.toml                          # basepath = "."
```

`basepath = "."` means mozilla-l10n/android-l10n is synced **into the tree**,
and the source tarball we GPG-verify already contains the result — 4,969
`values*/…xml` files across 81 resource directories, 250,412 translated string
rows once compiled into the APK. Measured on the pre-LW-M4-12 build:
`aapt2 dump resources` shows `app_name_private_5` in 120 locales, Japanese and
Serbian included. The UI *is* localised, by the tarball, before we touch
anything.

So the real gap is the one the task's risk line names: **the strings say
Firefox and Mozilla**, in 120 locales, and shipping them puts Mozilla's marks
in our chrome. Measured on the pre-patch APK: **6,259 string values** carrying
the mark, across 116 distinct resources.

Two properties of that surface decide the whole design.

**37 locales spell the mark in their own script.** Serbian writes Фајерфокс,
Arabic فايرفوكس, Malayalam ഫയർഫോക്സ്, Sinhala ෆයර්ෆොක්ස්, Santali ᱯᱷᱟᱭᱟᱨᱯᱷᱚᱠᱥ, Amharic
ሞዚላ. Desktop's answer to this problem is the `sed s/Firefox/LibreWolf/` over
`appstrings.properties` in `scripts/librewolf-patches.py`; an ASCII substitution
sees **none** of those. A mechanism that only fixes the Latin spellings has
moved the problem, not solved it.

**Some `<string>` entries are not prose.** `pref_key_enable_firefox_labs`,
`mozac_error_asleep` and fourteen others have a value that is *their own name*:
they are SharedPreferences keys and error-page illustration selectors, looked
up by value at runtime. A `sed` over `strings.xml` rewrites them and silently
breaks stored preferences and image lookups. There are 16 of them in this tree.

---

## The mechanism

```
mobile/android/lw-brand/
  lw_brand_strings.py      the rewriter, the scanner and the derive/resync tools
  brand-map.txt            brand name, word stems, URL rules, skips
  android-l10n-pin.txt     the pinned, hash-verified android-l10n commit
  brand-strings.gradle     the Gradle glue
  ui_brand_scan.py         host-side: walks the running UI and reports marks
```

and one hook, at the end of `mobile/android/shared-settings.gradle`:

```groovy
gradle.projectsLoaded { ->
    gradle.rootProject.apply from: new File(
        gradle.mozconfig.topsrcdir, "mobile/android/lw-brand/brand-strings.gradle")
}
```

### Why a build step and not a patch, and not a sed

- **Not diff hunks.** Carrying the rewritten bytes would be a multi-megabyte
  patch over 131 locale directories that rejects on every rebase, because
  upstream churns translations constantly.
- **Not a `sed` in `scripts/librewolf-patches.py`.** That is landmine L4 — an
  out-of-patch tree mutation that `make check-patchfail` cannot see — and it is
  the mechanism that breaks the 16 identifier strings above.
- **A Gradle step whose input is the tree and whose output is a generated
  resource directory.** The source tree is never modified, the transform is
  visible as `:<module>:lwBrandStrings` in the build log, and its decisions are
  written to `<module>/build/lw-brand/dropped.txt`.

### Why `res.srcDirs` is *replaced*, not appended to

The obvious shape — ship an overlay directory and add it to the source set — does
not work. AGP lets a **higher-priority source set** override a resource (flavor
over buildType over main), but two `srcDirs` inside the *same* source set that
define the same resource are a duplicate-resource **error**. Fenix has no spare
source set to put an overlay in. So the task copies each resource directory,
rewrites the `values*/` XML on the way through, and replaces the source set's
`res.srcDirs` with the copy. Everything that reads resources
(`merge*Resources`, `generate*Resources`, `package*Resources`, `pre*Build`,
`lint*`) is given an explicit `dependsOn` on the rewrite task, because AGP does
not infer a dependency from `srcDirs`.

### The rewrite rules

For each `<string>`, `<plurals>` and `<string-array>` text node:

1. **Skip internal keys.** A resource whose value equals its own name is never
   touched. This is mechanical, not a hand-maintained list.
2. **Phrases first.** `Firefox Fenix` → `LibreWolf`, so the word pass cannot
   turn a two-word product name into "LibreWolf LibreWolf".
3. **Mask URLs.** A URL span is matched, and only the `url` / `url-keep` tables
   apply inside it, keyed on the **host**. A host rule for `mozilla.org` must
   not quietly rewrite `addons.mozilla.org`, so matching is host-equality and
   never substring.
4. **Word substitution.** A word containing a declared stem has the
   **same-script run** around that stem replaced by the brand. Not the whole
   word, and not just the stem:

   | input | whole word | stem only | same-script run |
   |---|---|---|---|
   | `Firefox를` (ko) | `LibreWolf` — particle lost | `LibreWolf를` ✓ | `LibreWolf를` ✓ |
   | `የfirefox` (am) | `LibreWolf` — prefix lost | `የLibreWolf` ✓ | `የLibreWolf` ✓ |
   | `Mozilli` (hr) | `LibreWolf` ✓ | `LibreWolfli` ✗ | `LibreWolf` ✓ |

   Only the third column is right in all three cases. Losing the Slavic
   declension on the brand is a deliberate, stated cost: brand names commonly
   do not decline.
5. **Fail closed.** After the rewrite, a *translated* entry is **deleted** —
   so Android falls back to the rewritten English string — if any of these
   hold:
   - a declared stem still matches (a spelling in a locale we know about that
     the substitution somehow left behind);
   - a URL still carries the mark and its host is in neither table;
   - the rewritten **English** value mentions LibreWolf and the rewritten
     translation does not. This last one is what covers a transliteration the
     map has no stem for: we cannot spell it, so we cannot detect it, so we
     refuse to ship the entry.
6. **The English pass has no fallback below it**, so any of those conditions in
   `values/` is a hard **error** that fails the build rather than a drop.

On this tree that costs **43 (string, locale) pairs** out of 250,412 — 0.017 %
— all in the Fenix module, listed with their reason in
`build/lw-brand/dropped.txt`. Sixteen locales are affected; the worst are `skr`
(16) and `ml` (11).

### Where the word stems come from, and why the pin exists

`brand-map.txt` carries 43 stems. The Latin ones are typed by hand. **Every
non-Latin one is derived, not transcribed** — a mis-typed Malayalam or Sinhala
stem fails silently, and there is no way to eyeball the difference.

The derivation is `lw_brand_strings.py derive`, and its corpus is the pinned
android-l10n archive. For each locale it takes the translations whose English
source mentions the mark but which do not contain it verbatim, and ranks the
words in them by document frequency against the words in that locale's
*unbranded* translations. It reports the candidates; a human picks. The picks
are then checked mechanically against the whole 507,643-row corpus: **a stem is
only listed if every string in which it fires has an English source that
mentions Firefox or Mozilla.** That check rejected six plausible-looking
candidates, including `فائر` (which also matches فائروال, "firewall") and
`mozill` (which also matches the `mozilla.org` in an example URL).

That is the pin's job, and it is why `android-l10n-pin.txt` exists and is
verified. Note carefully what it does *not* pin: **the translations we ship do
not come from it.** They come from the GPG-verified source tarball, because
`l10n.toml`'s `basepath = "."` means upstream already synced them in.
Re-downloading them would be a second, weaker supply chain for bytes we already
have. What the archive supplies is the *detector*, and a tampered corpus yields
a brand map with a missing stem — hence `verify_sha256` before it is unpacked,
on the same principle as `assets/l10n-pin.txt`. `read_pin()` and
`verify_sha256()` in `lw_brand_strings.py` are ports of the functions of the
same names in `scripts/librewolf-patches.py`; the file format is identical.

The build asserts that `brand-map.txt`'s `derived-from|<commit>` equals the
pin's `commit`, so the word list cannot drift from its source unnoticed.

---

## What was measured

All numbers below are from the built `fenix-x86_64-debug.apk`, read with
`aapt2 dump resources` over the compiled `resources.arsc` — an oracle
independent of the rewriter — and from the app running on an Android 11 (API
30) `default` x86_64 emulator.

| | before | after |
|---|---|---|
| text rows in the APK (string + plurals + string-array) | 250,452 | 250,412 |
| values matching a declared brand stem | **6,259** | **0** |
| values matching a plain ASCII `firefox\|mozilla\|fenix` | 6,199 | **300** |
| `application-label`, all 130 locale variants | `Firefox Fenix` | `LibreWolf` |

The 300 are **not** a residue; they are the enumerated exceptions, and there
are exactly three of them:

| resource | rows | why it stays |
|---|---|---|
| `sign_in_instructions` | 109 | contains `https://firefox.com/pair`, the Mozilla-account pairing endpoint. The prose around it *is* rewritten ("On your computer open LibreWolf and go to …"); the host is not, because rewriting it makes the instruction wrong. |
| `pair_instructions_2` | 107 | same endpoint, on the QR-code screen. |
| `search_add_custom_engine_suggest_string_example_2` | 84 | a worked example of a third-party suggestion URL. The `client=firefox` in it is Google's API vocabulary, not our chrome, and changing it makes the example stop working. |

Plus 16 internal key strings (`pref_key_*`, `mozac_error_*`,
`mozac_support_base_locale_preference_key_locale`) whose value is their own
name. Those are never rendered.

**Never write "no Firefox strings" without naming those two groups.**

### The running app

`ui_brand_scan.py` navigates by deep link — `fenix-dev://settings_search_engine`
and the other fifteen routes `HomeDeepLinkIntentProcessor` accepts — so
navigation does not depend on reading localised labels; it then scrolls each
screen and opens its rows, dumping the accessibility tree at every stop and
matching every `text` and `content-desc` against the same stems the rewrite
uses. It reports a stem hit as a failure and an allowed-URL hit separately, so
the enumerated exceptions are *observed* rather than assumed away.

Runs so far, all on the same APK:

| locale | script | screens visited | brand strings | enumerated exceptions observed |
|---|---|---|---|---|
| en-US | Latin | 33 | 1 (the AMO description below) | 1 × `firefox.com/pair` |
| sr | Cyrillic | 34 | 1 (the same one) | 2 × `firefox.com/pair` |
| fa | Arabic | 34 | 1 (the same one) | 2 × `firefox.com/pair` |
| si | Sinhala | 34 | 1 (the same one) | 2 × `firefox.com/pair` |
| ml | Malayalam | 34 | 1 (the same one) | 2 × `firefox.com/pair` |

The four non-en-US locales are chosen precisely because their translations
spelled the mark in their own script — Фајерфокс, فایرفاکس, ෆයර්ෆොක්ස්,
ഫയർഫോക്സ്. On the running app the sign-in screen now reads:

```
sr  На вашем рачунару отворите LibreWolf и посетите страницу https://firefox.com/pair
fa  در رایانه خود LibreWolf را باز کرده و به https://firefox.com/pair بروید
si  පරිගණකයෙහි LibreWolf විවෘත කර https://firefox.com/pair වෙත යන්න
ml  താങ്കളുടെ കമ്പ്യൂട്ടറിൽ LibreWolf തുറന്ന് https://firefox.com/pair എന്നതിലേക്ക് പോകുക
```

— the prose brand rewritten, the endpoint left alone, the sentence still in the
target language, and no transliterated mark anywhere. The locale is switched
with `setprop persist.sys.locale <BCP47>` plus a zygote restart on a rooted
AOSP emulator image; the app's data is wiped between locales.

Spot checks from the rewritten resources, across scripts:

```
[en-US] Welcome to LibreWolf              [de] %1$s wird von LibreWolf hergestellt.
[ko]    %1$s는 LibreWolf에서 제작했습니다.        [pl] Pomóż nam ulepszać LibreWolf
[sr]    …знајте да вам LibreWolf аутоматска заштита чува леђа.
[fa]    %1$s توسط LibreWolf تولید شده است.
[si]    LibreWolf වෙත පිළිගනිමු                [ml] %1$s നിർമ്മിച്ചത് LibreWolf.
```

`sr`, `fa`, `si` and `ml` are locales whose translations spelled the mark in
their own script; they are the ones that prove the mechanism is more than a
`sed`.

### What the runtime scan found that the APK scan could not

One string, and it is the reason a runtime traversal is worth its 20 minutes.
On **Settings → Add-ons**, in both en-US and Serbian, the recommended-add-on
list renders:

> The best privacy tool and ad blocker extension for Firefox. Stop trackers,
> speed up websites and block ads everywhere including YouTube and Facebook.

That is **not a string resource**. It is the add-on author's own description,
fetched at runtime from Mozilla's add-on collection API, so it is in no APK,
changes without a rebuild, and this pass can never reach it. Rewriting it would
mean editing a third party's description of their own extension, which we are
not going to do.

It is recorded here rather than waved away, because the trademark question it
raises is real: our Add-ons screen displays text that says "for Firefox". The
surface belongs to whoever owns the add-on collection — **LW-M4-04** ships uBO
and **LW-M3-07** looked at the collection endpoint — and the decision is
theirs, not this task's. Nothing else was found, in any of the five locales.

### What the runtime scan does not prove

It proves the rewritten resources are the ones the running app uses, and it
catches marks that do **not** come from string resources at all. It does not
prove that a screen it never reached is clean — it prints the screens it
visited and their count, so that is auditable rather than implied. The
resource-level proof is the complete one: it covers every string in every
locale, including screens no walker reaches.

For the non-resource surface, the Fenix and android-components Kotlin was also
searched for brand literals bound to a UI text parameter (`text =`, `title =`,
`contentDescription =`, `message =`, …). Every hit is a `@Preview` /
`PreviewParameterProvider` fixture, an `androidTest` fixture, a log message, a
class name or a SUMO URL slug — for example
`ProfilerReusableComposable.kt:202`'s `listOf("Firefox", "Graphics", …)`, which
is inside `@Preview private fun ProfilerDialogueCardPreview`. That is a static
classification and it is weaker than the resource measurement; it is recorded
so the next person knows it was checked and how.

### The unit tests

Six Fenix unit tests asserted against the English brand as a **literal** —
`assertEquals("Finish setting up Firefox", …)`, `"A note from Firefox"`,
`"Firefox Fenix won't save passwords…"` — and went red the moment the resources
were rewritten. The patch fixes them by reading the brand from the same
resource the code under test uses (`R.string.firefox`, `R.string.app_name`),
which is brand-agnostic: they pass with the rewrite on *and* off.

Measured as a controlled A/B in one tree with one variable — the
`gradle.projectsLoaded` hook in `shared-settings.gradle`, added and removed,
everything else including the test fixes held constant:

| | tests | failed |
|---|---|---|
| hook **off** | 5,418 | 89 |
| hook **on** | 5,418 | 89 |

The two failure sets are identical, test name for test name: **no new
failures, none fixed**. 87 of the 89 are the known environmental residue
(`UnsatisfiedLinkError` / `NoClassDefFoundError`, libmegazord absent from the
container — LW-M2-09); the other two, `LensCameraFragmentTest` (a MockK stub
gap) and `HomeSettingsFragmentTest`, fail with the hook off as well and are not
this task's.

---

## Re-syncing on a rebase

Upstream syncs android-l10n into the tree on its own schedule, so a new
Firefox tarball brings new translations and, occasionally, new branded strings.

**1. Does the tree still rewrite cleanly?** This is the load-bearing check, and
it is the one that fails loudly:

```sh
python3 mobile/android/lw-brand/lw_brand_strings.py selftest
./mach gradle fenix:assembleDebug --no-configuration-cache
```

A new branded URL, or an English string the map cannot clean, is a build
error naming the resource. That is deliberate: those two cases need a human
decision, and failing the build is how they get one.

**2. Did the drop set grow?** Compare `build/lw-brand/dropped.txt` against the
previous build. A jump means a locale started spelling the mark in a way the
map has no stem for — which is exactly the case the fail-closed rule protects
against, but it costs a translation each time, so it is worth re-deriving.

**3. Re-derive the word list.** Bump the pin first (the procedure is in
`android-l10n-pin.txt`, and it is the same two-step, both-lines procedure as
`assets/l10n-pin.txt`), then:

```sh
python3 mobile/android/lw-brand/lw_brand_strings.py resync --tree mobile/android
```

That downloads the pinned archive, **verifies its sha256 before unpacking it**,
re-derives the candidates and prints them with a `*` against every one an
existing stem already covers, and a `<-- NO STEM IN MAP` marker against every
locale where none does. Review those, add stems, and update
`derived-from|<commit>` in `brand-map.txt` to the new pin — the build refuses to
run if the two disagree, so this cannot be skipped by accident.

**Do not just edit `derived-from`.** It is the only thing tying the word list to
the corpus it came from.

**4. Re-measure the APK.** The check that matters is the one over the compiled
resources, not a grep over the tree:

```sh
aapt2 dump resources fenix-x86_64-debug.apk > dump.txt
# then: every string/plurals/array value, matched against brand-map.txt's stems.
# 0 stem hits; the ASCII hits must be exactly the three enumerated resources.
```

**5. Re-run the UI scan** in en-US and at least three transliterating locales:

```sh
python3 mobile/android/lw-brand/ui_brand_scan.py \
    --serial emulator-5602 --package org.mozilla.fenix.debug \
    --scheme fenix-dev --label sr
```

---

## Hand-offs and open ends

- **`scripts/android-smoke.sh --check-strings` is still a stub** and exits 3.
  LW-M4-12 does not own that script, so it could not be implemented here.
  `ui_brand_scan.py` is written to be the body of that check: it already
  reports evidence rather than a verdict, separates stem hits from allowed-URL
  hits, and names the screens it visited. **LW-M2-07** owns wiring it in.
  Until that happens the board's declared verify for LW-M4-12 does not run —
  do not read its exit 3 as a pass.
- **LW-M4-07 (branding) owns the product name.** This pass sets `app_name` to
  `LibreWolf` through the `phrase` table because the acceptance for LW-M4-12 is
  "no user-visible Firefox or Mozilla string" and the launcher label is the most
  visible string there is. If LW-M4-07 chooses a different name, change the
  three `phrase` lines. The applicationId is untouched and is still
  `org.mozilla.fenix.debug`; that is LW-M4-07's one-way decision.
- **Mozilla accounts / sync is an unowned gap.** The two `firefox.com/pair`
  exceptions exist only because the Android build still ships the FxA pairing
  UI. Desktop LibreWolf sets `identity.fxaccounts.enabled=false`;
  `settings/android.cfg` records the Android side as gap **G2** with owner
  "M4", and no task in `docs/android/tasks.yaml` owns it. If that build decides
  not to ship Mozilla accounts, both exceptions disappear and the enumerated
  list drops to one.
- **The M2 smoke gate is 6/7, not green.** `./scripts/android-smoke.sh` on the
  APK built with this change passes `page-load-http`, `page-load-https`,
  `video`, `getusermedia`, `extension` and `pref-dump`, and fails `webgl`. That
  failure is **not** this change: it reproduces identically on the unmodified
  pre-change APK on the same device, and again on a third AVD, with a different
  garbage pixel each time (`[156,111,36,230]`, `[111,14,49,248]`,
  `[90,63,31,83]`) — the signature of an uninitialised SwiftShader framebuffer
  on a host running three emulators at once, not of a dead WebGL stack.
  `librewolf.webgl.prompt` reads `False` in every run, so landmine L1 is not
  what is happening; the harness says so itself in the failure text. It is
  still a red gate and it is recorded as one.
- **Ordering.** The patch shares exactly one tree file with another patch:
  `ContinuousOnboardingFeatureTest.kt`, with `no-onboarding.patch`. Measured
  order-free (both orders exit 0, no `.rej`, byte-identical result) and
  recorded in `scripts/check-patch-order.py`'s `REVIEWED_ORDER_FREE`.
- **Focus is rewritten too.** `focus-android` is an Android module like any
  other, so `lwBrandStrings` runs on it. We do not ship Focus; nothing was done
  to verify its UI.
- **Cost of the pass:** ~24 s to rewrite all 81 resource directories from cold,
  and it is up-to-date-checked per module, so an incremental Gradle build pays
  nothing. Measured Gradle wall clock for `fenix:assembleDebug` after the change:
  2 min 9 s from a warm object directory.
