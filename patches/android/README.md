# patches/android

Android-only patches. Everything here is listed in `assets/patches/android.txt`
and applied **after** `common.txt` when `android` is in `--targets`.

Three patches live here today, all pulled in by the M1 straddler splits; it
fills up further in M4. See `docs/android/PATCH-SCOPE.md` for what belongs on
Android at all, and `docs/android/AGENTS.md` for the landmines.

## Naming

One concern per patch. Kebab-case, `.patch` suffix, no version number, no date,
no bug id in the filename:

```
no-glean.patch          good
no_glean.patch          no — snake_case is legacy (dbus_name, mozilla_dirs)
glean-153.patch         no — the version moves, the patch stays
android-fixes.patch     no — "fixes" is not one concern
```

This matches `patches/` and `patches/ui-patches/`, where the file is named after
the *thing it changes*, not the file it edits. Removals read as `no-<thing>` —
`no-glean`, `no-adjust`, `no-nimbus`, `no-gms`. Do not prefix names with
`android-`; the directory already says that.

If a patch needs more than one sentence to describe what it does, it is probably
two patches.

## Header comment

`patch` ignores free text before the first `---`, so every patch here **must**
open with a comment block naming the upstream file(s) it modifies and why
LibreWolf diverges from Mozilla there. A reviewer three releases from now has
only this block to decide whether a rejected hunk should be rebased or dropped.

`patches/remove-openai.patch` is the worked example: read its `LibreWolf note:`
block. It records what the diff cannot express (two paths deleted out-of-band by
`scripts/librewolf-patches.py`), why the context lines must not be relaxed, and
what breaks if they are. Aim for that. `patches/ui-patches/lw-logo-devtools.patch`
shows the shorter `# LibreWolf <name>.patch / # Author / # Description` form,
which is fine for a one-hunk change.

State at minimum:

- the upstream file(s) touched
- what LibreWolf wants instead, and why
- anything that happens outside the diff (file copies, `rm`, generated files) —
  landmine L4

## No duplication with common

A patch that also has to touch shared Gecko code does **not** get an Android copy
here. It belongs in `common.txt` as one patch, with the Android-specific
behaviour gated at runtime (a pref, `#ifdef MOZ_WIDGET_ANDROID`, an
`AppConstants.platform` check).

Two near-identical patches under `patches/` and `patches/android/` drift the
moment upstream renames a symbol, and only one of them will reject — the other
applies cleanly and is silently wrong. That is the failure this directory's
convention exists to prevent.

The corollary: if a desktop patch expresses a requirement Android still has but
whose *implementation* is `browser/`-only, the Android counterpart lives here as
its own patch with its own task — it is not the desktop patch forced onto Fenix.

## Registering a patch

Adding a file to this directory does nothing. It must also be a line in
`assets/patches/android.txt`.

Since LW-M0-13, `scripts/enable-patch.sh --list android <patch>` does this
correctly: it edits `assets/patches/android.txt` and then regenerates the
`assets/patches.txt` shim. (Before LW-M0-13 it appended only to the shim, which
drives no build, so the patch was silently never applied.) Adding the line by
hand is equally fine — just do not forget it, and do not hand-sort the lists:
order is load-bearing.

## Scope check

`scripts/lint-patch-scope.py` (LW-M0-08) parses the `--- a/… +++ b/…` headers of
every listed patch and **rejects any patch in `android.txt` that touches
`browser/`**. CI runs it. `browser/` is desktop-only front-end code that the
Android build never compiles, so a hunk against it is either dead weight or a
sign the patch should have been split.

## Who writes what

Every patch here is owned by exactly one board task
(`python3 docs/android/board.py --show <id>`). If your patch is not on this list,
check that a task owns it before writing it.

Written, on disk and listed in `assets/patches/android.txt`:

| patch | task |
|---|---|
| `disable-data-reporting-android.patch` | LW-M1-02 — `MOZ_SERVICES_HEALTHREPORT` off for Android; `mobile/android/moz.configure:131-132` implies the opposite of `browser/moz.configure`, so the common half alone leaves data reporting on. Apply *with* `patches/disable-data-reporting-common.patch`, never instead of it |
| `neterror-jar.patch` | LW-M1-07 — packages `illustrations/warning.svg` for `toolkit/themes/mobile`, which never includes `desktop-jar.inc.mn`. The entry must go in `toolkit/themes/mobile/global/jar.mn` and **never** in `shared/minimal-toolkit.jar.inc.mn`, which `desktop-jar.inc.mn:10` includes |
| `webgl-prompt-default.patch` | LW-M1-08 — landmine L1: `librewolf.webgl.prompt` defaults to false on Android, where the prompt's UI and observers are `browser/`-only. Without it every WebGL context fails silently |

Planned, not yet written:

| patch | task |
|---|---|
| `build-fixes.patch` | LW-M2-02 — make the common set build on Android |
| `appservices.patch` | LW-M2-05 — `--enable-appservices-in-tree`, search dumps |
| `pref-delivery.patch` | LW-M3-03 — `MOZ_DEFAULT_PREFS` into the startup path |
| `ubo-preinstall.patch` | LW-M3-07 — preinstall uBlock Origin |
| `no-glean.patch` | LW-M4-01 — remove Glean from the Fenix layer |
| `no-adjust.patch` | LW-M4-02 — remove the Adjust attribution SDK |
| `no-nimbus.patch` | LW-M4-03 — disable Nimbus experiments |
| `no-crashreporter.patch` | LW-M4-04 — remove Socorro and its upload path |
| `no-gms.patch` | LW-M4-05 — strip Play Integrity, Firebase, push |
| `search-config.patch` | LW-M4-06 — LibreWolf search configuration |
| `branding.patch` | LW-M4-07 — branding and applicationId |
| `rs-blocker-android.patch` | LW-M4-08 — remote-settings blocker for Android |
| `about-config.patch` | LW-M4-09 — about:config on release builds |
| `no-onboarding.patch` | LW-M4-10 — onboarding, promos, first-run calls |
| `no-suggest.patch` | LW-M4-11 — search suggestions and contile |
| `l10n-strings.patch` | LW-M4-12 — localise Fenix, de-brand its strings |
| `fission-isolation.patch` | LW-M5-01 — `isolate-high-value` |
| `isolated-process.patch` | LW-M5-02 — `isolatedProcess` and the app zygote |
| `update-check.patch` | LW-M6-06 — in-app update check without a store |

LW-M1-06 was expected to add one more, and did not: Android packaging does not
ship pingsender (`mobile/android/installer/package-manifest.in` never mentions
it, and `pingsender/moz.build:5-6` builds no binary there), so no exclusion patch
was needed. The evidence is recorded as a comment block in
`assets/patches/android.txt` — as it is for LW-M1-03 and LW-M1-04, which also
turned out to need nothing here. A checked absence and an overlooked one look
identical in a patch list, so write the block.
