# Device evidence — 2026-09-06 build

> **Superseded in part.** Everything below the "Final artifact" section was measured
> against a two-ABI build (`buildID 20260905183254`). The artifact a beta would ship
> is the three-ABI one built later the same day, and the checks were re-run against
> it — see the next section. Where the two disagree, the final one wins.

The first device session run against a build that carries LW-M4-06, LW-M4-11 and
LW-M6-06. Everything here was produced by `scripts/android-smoke.sh` against
`fenix-x86_64-release.apk` from `librewolf-android-apk-153.0esr-1/`, on the
headless emulator the harness boots itself (android-30/default, x86_64, 3072 MB).

Build under test, as the harness read it off the running app:

    Redoubt 153.0esr-1   buildID=20260905183254   applicationId org.redoubtbrowser


## Final artifact — three ABIs, `buildID 20260906190000`

The first build in this project's history carrying **all three shipped ABIs** in one
fat AAR, and therefore the first universal APK whose every ABI directory holds a real
Gecko engine.

    fenix-armeabi-v7a-release.apk   117 MB
    fenix-arm64-v8a-release.apk     121 MB
    fenix-x86_64-release.apk        127 MB
    fenix-universal-release.apk     278 MB   armeabi-v7a + arm64-v8a + x86_64,
                                             libxul.so present under each

It took four attempts. What blocked the first three is written up in `BUILD.md`
("MOZ_BUILD_DATE is baked in per objdir"): the build ID is fixed when an objdir is
*configured*, so three objdirs configured on three different runs produced AARs whose
`modules/AppConstants.sys.mjs` differed, and the merger rejected them with a message
about *architecture-specific* versions that points at 32-bit ARM and means nothing of
the kind. All three objdirs were wiped and rebuilt in one run with `--build-date`.

### Re-run against this artifact

| check | task | exit | result |
|---|---|---|---|
| `--check-search` | LW-M4-06 | **0** | engine list, default and a real partner-code-free query — **verified on the shipping artifact** |
| `--check-aboutconfig` | LW-M4-09 | **0** | reachable on a release-configured build, edit survives restart |
| `--check-strings` | LW-M4-12 | **0** | **both halves now.** Resource table: 234,644 rows, 0 unexplained. Running-app traversal: 36 screen stops, **0 branded strings shipped by this APK** (1 more is remote content, reported and not attributed to the build) |
| `--check-no-gms` / `--check-no-adjust` | LW-M4-05 / -02 | **0** | no GMS or Adjust strings in any dex |
| `fenix:testDebugUnitTest` → `board.py --check-fenix-tests` | LW-M2-09 | **0** | see below |
| `--first-run-capture` | LW-M4-10 | **1** | 6 outbound events before navigation, all Remote Settings |
| `--check-no-remote-settings` | LW-M4-08 | **1** | 3 events, to the three Remote Settings hosts |
| `--check-no-suggest` | LW-M4-11 | **1** | fails its positive control; see below |

### The Fenix unit suite, run for the first time

`AGENTS.md` has made `board.py --check-fenix-tests` the Definition of done for every
Kotlin change since M2, and it had never run — the gate returned 0 on missing input and
no results directory had ever existed here.

    598 classes / 5,426 tests, 11m19s
    93 failing = 90 environmental + 3 known-real + 0 unexpected  →  exit 0

The first run surfaced one class that was not allow-listed,
`settings.autofill.ui.AutofillSettingsMiddlewareTest` (3 tests). Checked rather than
waved through: all three fail with `Could not initialize class
mozilla.appservices.autofill.UniffiLib`, the same host-JVM/`libmegazord.so` cause as
the three classes already listed. It is back on the allowlist — which
`fenix-test-allowlist.yaml`'s own header predicted, since that is how it left.

### `--check-update-privacy`, both halves

The shipping APK is built **without** an update-check key, so the feature is compiled
out: no row, no traffic, and that half passes. To exercise the other half a throwaway
ECDSA P-256 key pair was generated (scratchpad only — no key material is in this
repository) and a variant APK built with `LW_UPDATE_CHECK_PUBKEY`. On that build:

- the **Check for updates** row appears — so `-PlwUpdateCheckPubkey` compiles it in;
- it reads **OFF** by default, and flipping it through the UI works;
- after relaunch, **no request to the update host was captured**, so the opt-in path is
  still unproven. Note the endpoint is compiled in by default
  (`https://redoubtbrowser.org/updates/android/latest.json`), so a missing endpoint is
  not the explanation.

### `--check-no-suggest`: now localised

Three more runs, with the display kept awake and the post-Enter window polling for
180 s instead of sleeping 15 s. The subject still measures clean — 0 events while a
query sits unsent, no sponsored-tile host, the switch present and OFF — and the control
still sees nothing. What changed is that the harness now says which of its two
explanations applies:

> Enter produced NO outbound event in 180s of polling, **and the app DID leave edit
> mode, i.e. the search ran and the capture missed it** — so the quiet typing window
> proves nothing. Chase the capture, not the browser.

That conclusion was **wrong**, and the correction is the useful part. Adding a second,
independent measurement — the kernel's per-uid byte accounting, which has no view of
handshakes and no parsing step — gives `rx+0 tx+0` across the same 180 seconds. So the
capture was not missing anything: **no request was made at all.**

Two other theories died on the way, both cheaply and both worth not re-running:

- *"the emulator's pcap writer buffers."* It does not, measurably: on this harness's own
  emulator a launch added **773 KB** to the capture and one navigation added **2.6 MB**,
  in windows of 45 seconds.
- *"Fenix warmed a connection when the toolbar opened, so Enter reused it and produced
  no DNS/SYN/SNI."* Plausible, and ruled out by the byte counters — a reused connection
  still moves bytes.

What is left is that **Enter is consumed without issuing a query**. The app does leave
`ADDRESSBAR_EDIT_MODE`, which is why this looked like a successful search from the UI,
but leaving edit mode only means the keystroke was taken. Whether `input keyevent 66`
commits this Compose field after a 60-second idle is the open question, and it is a
question about driving the UI, not about the patch or the capture.

**LW-M4-11 stays unverified.** Its subject still measures clean every time — nothing
leaves while a query sits unsent, no sponsored-tile host, the switch present and OFF —
and the control is right to refuse to pass on that alone.

---

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
