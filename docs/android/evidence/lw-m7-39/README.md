# LW-M7-39: DRM under isolation, and the DRM switch (2026-10-15)

Owner decision 2026-10-15, verbatim: "lets analyse this in more detail and try to fix".
Design, root cause and options: `docs/android/ISOLATION-MEDIA.md` section 9. Patches:
`patches/android/isolation-eme.patch` (new) and `patches/android/drm-permission-default.patch`
(listed now; held back since 2026-10-14, `evidence/lw-m7-51/`). Settings half: Redoubt-settings
commit `bddc198f` (branch `android-drm-permission`, local, NOT pushed).

Every hash below is from `sha256sum` or `git rev-parse`.

2026-10-16: the Android 12-13 stall found in the 158.0-3 acceptance (no license request after the
service certificate, playback stops at ~8 s) is fixed by `isolation-eme.patch` item 7; cause,
builds and measurements in `api31-33-fix/`.

## Inputs

- Tarball `firefox-158.0.source.tar.xz`, sha256 `fc77f780…a2bb` (GPG-verified earlier, LW-M7-50).
- Branch `fix/drm-isolation` off `origin/main` `962581ef`; builds were made from the worktree state
  before the commit (`build-v3/commands.log` records HEAD, the settings commit, a hash of the
  uncommitted diff and the input patch hashes). The committed `isolation-eme.patch`
  (`f82ebded…d2ec`), `drm-permission-default.patch` (`bda3bdba…c2bc`) and `android.txt`
  (`c402c64e…1309`) are byte-identical to build v3's inputs.
- Upstream patches read (not applied except 2075686): bug 2067689 parts 3 and 5
  (`1f0f1a842b9b`, `4bd4a6112307`), bug 2075686 (`476a6689…`, sha256 `cef6703c…84d8`, backported
  verbatim). All FIXED for Firefox 159 (159.0b2 on 2026-10-15).

## Builds (x86_64, release variant, C/C++ -Werror, Rust lints capped, throwaway key)

| build | change | APK (throwaway-signed) sha256 | outcome |
|---|---|---|---|
| v1 | items 1-4 | `97670d0c…26db` | no crash; Widevine plays but every stream stops at 7.9 s (`diagnostics-api34/v1-stall/`) |
| v2 | + item 5 (expiration 0 -> NaN) | `d5f1f941…17a8` | streams play to the end; 2 of 9 first plays on a fresh profile fail (`diagnostics-api34/v2-first-play-race/`) |
| v3 | + item 6 (RDD Init waits for the MediaCrypto; no provisioning retry loop) | `f82b4f92…e7ec` | everything below |

`build-v3/`: `commands.log`, `SHA256SUMS`, `build-times.txt`, unit test XML and summary
(`PhoneFeatureTest` 9/9, `SettingsTest` 129/129). Build scripts: `scripts/` is the device side;
the chain script is the one of `evidence/lw-m7-51/scripts/build/chain.sh` with this worktree.

## Device runs (one emulator at a time, `scripts/batch.sh`)

- `device-api34-v3/` (API 34 google_apis, isolation ON): `--check-eme` x2 PASS; UI flow
  (`v3-api34-flow/`: default Blocked + Recommended, Allowed, Widevine playback pinned low 60 s /
  ABR 40 s / switch to 576p 48 s, Ask to allow prompt, Blocked); five `first*` flows (fresh
  profile, Allowed, play 40 s): all pass; `--check-isolation` x2, `--check-video` x2 PASS;
  `v3-baseline-smoke`: all rows but `webgl` (API 34 harness limit); `batch.out` has the per-flow
  counts (0 `Failed to query crypto scheme support`, 0 tab deaths, parent line present).
- `device-api30-v3/` (API 30, isolation OFF): `--check-eme` x2 PASS (Java path), the same UI flow
  and two first-play flows pass (VP9+AAC chosen: the Java path offers VP9), `--check-isolation`,
  `--check-video` PASS.
- `controls-api34/`: 158.0-2 (`0080b12f…b3b9`): `--check-eme` FAILS `eme-prefs`/`eme-no-crash`;
  with `media.eme.enabled` true as a user pref (= about:config): crash loop reproduced
  (`crash-excerpt.txt`), all four rows FAIL. `ctl-158.0-2-first-run-capture`: shows no app
  traffic, like this build's `v3-first-run-capture-*` on the same day: the capture is not
  working, so no first-run network claim is made.
- Owner's phone (10.0.0.168): not reachable (ping) on 2026-10-15; no dev APK installed.

## Gates (`gates/`)

`static-gates.txt` (check-patch-order, lint-patch-scope, board --check/--check-scope/
--check-cfg-split/--diff-mozconfig --strict, site-check: all rc=0), `patchfail.rc` and the
two logs (android, desktop: success), `scripts-tests.txt` (same three usage-only exits as on
main, 163 harness unit tests OK), `ordering-swap.txt` (`scripts/ordering-swap.py`: the
drm-permission-default pairs are order-free as measured under LW-M7-51, same hashes;
isolation-eme needs isolation-media-codecs-in-content first, and is order-free with the three
webgl patches when kept after it, "third measurement"; the plain swaps that move it ahead of its
prerequisite fail by construction).

## Scripts (`scripts/`)

`eme-server.py`, `eme-probe.html`, `ui.py`, `drm-flow.py` (from `lw-m7-51`, plus `Play`,
`PlayLow`, `PlaySwitch` and the URL quoting fix: an unquoted `&` in `adb shell am start` ended
the command and Chrome opened the page, which cost one v2 run), `play.html` (Shaka 5.2.12 from
cdnjs, the public "Angel One" Widevine stream and license proxy), `run-check.sh`, `batch.sh`,
`ordering-swap.py`.
