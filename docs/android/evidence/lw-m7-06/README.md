# Device evidence — 2026-09-06 build

The first device session run against a build that carries LW-M4-06, LW-M4-11 and
LW-M6-06. Everything here was produced by `scripts/android-smoke.sh` against
`fenix-x86_64-release.apk` from `librewolf-android-apk-153.0esr-1/`, on the
headless emulator the harness boots itself (android-30/default, x86_64, 3072 MB).

Build under test, as the harness read it off the running app:

    Redoubt 153.0esr-1   buildID=20260905183254   applicationId org.redoubtbrowser

## Results

| check | task | exit | what it establishes |
|---|---|---|---|
| `--check-search` | LW-M4-06 | **0** | **All three acceptance lines at once.** Settings > Search lists DuckDuckGo No-AI, Startpage, Mojeek and Wikipedia (en); the default reads `DuckDuckGo No-AI`; a real typed query landed on `https://noai.duckduckgo.com/?q=…&ia=web` with **no** partner or attribution parameter. |
| `--check-aboutconfig` | LW-M4-09 | **0** | about:config reachable on a release-configured (non-debuggable) build; 30 pref rows, `general.aboutConfig.enable=true` on the default branch with no user value, an edit through the page survived a restart, 48 prefs locked. |
| `--check-strings` | LW-M4-12 | **0** | Resource table only: 234,644 text rows, **0 unexplained** brand values, 297 allowed URL-keeps, 3 internal `value==name`. The running-app traversal **did not run** in this pass (no `--emulator`), so the rendered-UI half is still open. |
| `--check-update-privacy` | LW-M6-06 | **0** | Store-build half only. No `Check for updates` row (the feature is compiled out without `-PlwUpdateCheckPubkey`) and no update-host traffic across launch + Settings. **The opt-in path is untested** — it cannot be reached until a build is made with a verification key. |
| `--pref-dump` → baseline | LW-M3-05 | **0** | `docs/android/expected-prefs.txt` generated from this build, 60 rows; `./scripts/android-pref-audit.sh` then exits **0**. This gate had never been runnable — the baseline did not exist. |
| `--first-run-capture` | LW-M4-10 | **1** | **10 outbound events before any navigation.** See below. |
| `--check-no-suggest` | LW-M4-11 | **1** | Fails its own positive control, not its subject. See below. |

## `--first-run-capture`: 10 events, and why they are not a surprise

Every one is Remote Settings:

    dns/tcp/sni   firefox.settings.services.mozilla.com        151.101.129.91
    dns/tcp/sni   firefox-settings-attachments.cdn.mozilla.net 151.101.193.91
    tcp/sni       content-signature-2.cdn.mozilla.net          34.149.226.178
    app uid bytes rx +690,022  tx +13,522

This is **not** a leak that a patch failed to close. It is LibreWolf's own
configuration doing what it says: `settings/common.cfg:709` ships
`librewolf.services.settings.allowedCollections` with **33 allow-listed
collections** (`security-state/*`, `main/tracking-protection-lists`,
`blocklists/addons`, …) that the desktop `rs-blocker.patch` permits to sync over
the network, plus 11 more in `allowedCollectionsFromDump`. Read off the running
build, both prefs are present and populated — so the cfg layer *is* applied here.

Both Remote Settings blockers are in the tree and doing their jobs:
`rs-blocker-android.patch` returns an error from the Rust crate's `make_request`
and an empty changeset from `fetch_changes`; the common `rs-blocker.patch`
gates the JS client per collection. What reaches the network is what the
allowlist deliberately allows.

So the conflict is between two of this project's own goals, and it is already
written down: `common.cfg:715` says of those two lists, *"LW-M4-08 owns their
Android contents"*. **LW-M4-08 is not done.** Until it decides what Android's
allowlist should be, M4's headline claim — no outbound request between install
and first navigation — cannot hold, and `--first-run-capture` is red for a
reason that is a decision, not a defect.

Note also `FenixApplication.kt:736` registers a **2-hourly** `WorkManager`
Remote Settings sync (`DefaultRemoteSettingsChecker: Register sync work for
Remote Settings`, visible in logcat on every launch). That cadence matches the
periodic traffic seen in the 2026-09-02/04 capture.

## `--check-no-suggest`: the subject passes, the control does not

What the run measured about LW-M4-11 itself is good:

- **0 outbound events** in the 60 s window with `lwsmokeq17884` sitting unsent in
  the toolbar — no keystroke leak, which is the whole point of the task;
- **0 events** to any sponsored-tile host (`ads.mozilla.org`,
  `contile.services.mozilla.com`) since launch;
- the **Show search suggestions** switch is present in Settings > Search and
  reads **OFF** — acceptance line 3, user-toggleable, off by default.

It still fails, because the check refuses to pass on those three alone: after
pressing Enter it requires the search to appear on the wire, as proof the capture
was alive. That control saw nothing, three runs in a row.

The control is wrong, not the build. Driving the identical sequence by hand on
the same APK — tap `ADDRESSBAR_URL_BOX` at (493, 147), `input text`, idle 60 s,
`input keyevent 66` — the text is still in the field after the idle
(`ADDRESSBAR_EDIT_MODE` still present) and Enter **does** navigate to the engine's
results page. `--check-search`, which types and presses Enter without idling,
issues a real query on this same build and passes.

Two things were tried and did not fix it, both kept because both are right
anyway: the harness now keeps the display awake for a run (nothing did before,
and several checks idle far longer than the screen timeout), and the post-Enter
window grew from 15 s to `max(45, capture_seconds//2)`. **The cause is not yet
identified**, and the honest state is that LW-M4-11 is *unverified* — its
evidence is one working positive control away, not a rewrite.

Do not "fix" this by deleting the control. A quiet window with no proof the
capture was alive is exactly the false green this check exists to prevent.

## Reading this critically

- Every result here is from **one** x86_64 emulator, API 30. Nothing here says
  anything about a physical device, an ARM ABI, or a low-RAM one — which is what
  `BETA.md` §2 exists to arrange.
- `--check-update-privacy` and `--check-strings` each passed **half** of what
  they can test. Both halves are named above; neither is a full verification.
- The APK is `CN=Android Debug`, v2-only. It is not a release artefact.
