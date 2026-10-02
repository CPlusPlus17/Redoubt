# 153.4.0esr rc2: full device acceptance with the committed harness, 2026-10-02

No rc3 exists. The product did not change after rc2: the defect A, B and C fixes were all made in
the harness (`c35662c4`, `f7f519f6`). So this run is against the **rc2 APK**, using the harness as
committed at `11fd562e`. Rows 8a–8d were added later. They rerun `--check-no-suggest`, and its negative control, after the
harness change that attributes the typing window by connection (harness sha256 `dba0f279…ce46`).

## What was tested

| | |
| --- | --- |
| Candidate source | `0a134441b77a888f365e81da02beee71d6e3b9c4` (rc2; see [`../README.md`](../README.md) and [`../apk-identity.txt`](../apk-identity.txt)) |
| x86_64 unsigned | `1ac3b01d9716ed5c53e7510ba8ba609c6bac2bd6dc6988192bdf3770124d95e8` |
| x86_64 installed | `77348e7d72bb4183adfec9cf79236d726280c0cd6a8666e8d507b6d6f495af83`. Signed with the throwaway key (cert `31e9a40f…b760`, `CN=Redoubt throwaway test key 2026-10-02, O=NOT A RELEASE KEY`), not the release key. Apart from `META-INF/`, every zip entry (CRC and size) equals the unsigned APK's |
| Beta 2 (negative control only) | installed `9b63f2edbe18310842b4689551243ed2ae61015f8ba044ac8bd90f15ae380427`, signed with the same throwaway key. Apart from `META-INF/`, every entry equals `~/Documents/librewolf/librewolf-android-apk-153.0esr-1-rc-unsigned/apk/fenix-x86_64-release-unsigned.apk` (`503bfd79…955d`, source `764fc91c`) |
| Repository HEAD for every run | `11fd562ea0e0f5f6dcd5e6350e273cc309f734df`, with 0 uncommitted changes under `scripts/` |
| `scripts/android-smoke.sh` | sha256 `aabbb7a70126f10415eebba4daae484aebffadb2157f246d9c531610ccc43ad5` (last changed in `c35662c4`) |
| `scripts/android-graphics-smoke.py` | sha256 `ce0072ea63fa3fdd1b183bcab3f7adfed279842c6fe090ef5834eec9e96a4612` (last changed in `f7f519f6`) |

Each run records the HEAD, the dirty count, both harness hashes and the installed APK hash
**at the moment it started**, in `smoke/exit-status.jsonl`. `smoke/run-check.sh`,
`smoke/batch1.sh` and `smoke/batch2.sh` are the exact wrappers used. The run's harness JSON also
records `harness_sha256` from inside the driver.

## Conditions

- **Emulator:** one emulator, emulator-5584, android-30 `default` x86_64 (no GMS), swangle. The
  harness booted it from a new AVD (`--emulator --keep-emulator`, first check) under
  `build/rc2/final/runtime/work`, with `-dns-server 9.9.9.9 -tcpdump`. Every later check reused it
  with `--serial`. It was shut down at the end.
- **Network and profile:** AMO was reachable. There was **no Retry priming and no iptables**. Every
  check ran on a fresh profile, because the harness runs `pm clear` before each one.
- **Logcat:** each `--serial` run also streamed `logcat -v threadtime` to `smoke/<check>/<check>.logcat.gz`.
  The first check booted the emulator itself, so it has no stream; its own logcats are in
  `launcher-start-*`.
- **First batch attempt:** the first attempt of batch 1 exited 2 before installing anything. The
  APK had been copied away from its `output-metadata.json`, so the harness could not determine the
  applicationId. Those two empty results were deleted and the batch was rerun. Every result below
  comes from the rerun.

## Results

| # | Check | Exit | Result | Evidence |
| --- | --- | --- | --- | --- |
| 1 | `--check-launcher-start` (rc2) | 0 | **PASS**. Fresh profile and restart both log `uBlock Origin startup ready: Ready(installed=true, enabled=true)`. No setup-failure dialog after 46 s | `smoke/check-launcher-start/` |
| 2 | `--check-launcher-start` against **Beta 2** (negative control) | 1 | **FAIL, as expected.** Both phases show the "uBlock Origin setup failed" dialog, the preinstaller logged a startup failure, and no readiness line was logged. The check can see the defect it guards | `smoke/beta2-check-launcher-start/` |
| 3 | `--check-aboutconfig` | 0 | **PASS**. 30 rows. `general.aboutConfig.enable=true` on the default branch with no user value. An edit through the page's toggle survives a restart | `smoke/check-aboutconfig/` |
| 3a | about:config CSP (diagnostic probe, not a gate) | n/a | **0 CSP / script-src-attr errors from about:config** in the console service, with a working positive control. Logcat also has 0, but it is **not** a usable witness; see below | `aboutconfig-csp/` |
| 4 | `--check-ubo-preinstall` | 0 | **PASS**. The bundled-list script is blocked on first navigation, and the pinned AMO-signed add-on is active | `smoke/check-ubo-preinstall/` |
| 5 | `--check-ubo-lifecycle` | 0 | **PASS**: all 10 rows (disable, restart, remove, APK reinstall) | `smoke/check-ubo-lifecycle/` |
| 6 | `--check-ubo` | 0 | **PASS** | `smoke/check-ubo/` |
| 7 | `--check-search` | 0 | **PASS** on a fresh profile. The uBO sheet is acknowledged by the harness, the query goes to `noai.duckduckgo.com` with no partner parameter, and the 4 engines are as configured. **Defect B is fixed** | `smoke/check-search/` |
| 8 | `--check-no-suggest` (harness `aabbb7a7`, byte rule) | 1 | **FAIL** under that harness's rule: 16 outbound payload packets (642 B) in the typing window, of which 3 (138 B) are classed background (Remote Settings) and 13 (504 B) are not; the 13 failed the check. The sheet was acknowledged (defect B fixed), the pre-typing wait settled after 106 s, no suggestion endpoint or sponsored host was contacted, the switch is OFF and the round trip passes. Every red packet is an HTTP/2-sized keep-alive or close record on a connection opened **before** typing. **Not attributed to the search toolbar**; see below. **Superseded by rows 8a–8d** | `smoke/check-no-suggest/` (includes `typing-window-connection-trace.txt`) |
| 8a | `--check-no-suggest --no-suggest-negative-control` (harness `dba0f279`, per-connection rule) | 1 | **FAIL, as expected.** "Show search suggestions" was turned ON through Settings before typing (`False -> True`) and restored OFF afterwards. Typing then opened 3 new TLS connections to **`ac.duckduckgo.com`** (40.114.177.156:443; 3,404 + 2,107 + 2,107 B out) after a udp/53 query for it, plus 2 new DoT connections to 10.0.2.3:853: 6 typing flows. In the same window the 7 pre-existing AMO/uBO-host flows were graded `keepalive`. The check sees what it guards | `no-suggest-attribution/check-no-suggest-negative-control/` |
| 8b | `--check-no-suggest` (harness `dba0f279`) | 0 | **PASS**. Fresh profile, sheet acknowledged, quiet after 107 s. Typing window: 7 `keepalive` + 3 `background` flows, 0 typing flows. The byte rule would still have failed it: 13 non-background packets, 504 B, all keep-alive or close records | `no-suggest-attribution/check-no-suggest-1/` |
| 8c | `--check-no-suggest` (harness `dba0f279`) | 0 | **PASS**. Quiet after 103 s; 7 `keepalive` + 3 `background`, 0 typing flows (again 13 packets / 504 B under the old rule) | `no-suggest-attribution/check-no-suggest-2/` |
| 8d | `--check-no-suggest` (harness `dba0f279`) | 0 | **PASS**. Quiet after 106 s; 7 `keepalive` + 3 `background`, 0 typing flows (again 13 packets / 504 B under the old rule) | `no-suggest-attribution/check-no-suggest-3/` |
| 9 | baseline suite, including the **full graphics acceptance** | 0 | **PASS**, 8 of 8: https-only interstitial, page-load http/https, **webgl**, video, getUserMedia, extension, pref-dump. Graphics acceptance `acceptanceComplete: true`, **161 checks passed**. These include `ui-canvas-allow-private`, `ui-webgl-allow-private`, `private-choices-isolated-and-cleared-on-last-private-close`, every `frame-*` row and `frame-origin-port-and-revoke-isolation`, `session-exceptions-expire-on-process-restart`, `remembered-exceptions-survive-process-restart`, and `quiet-review-opens-permissions-in-normal-and-private-tabs` | `smoke/baseline-smoke/` (`graphics-summary.json`, `graphics-runner-tail.log`, `graphics-acceptance.tar.xz`) |
| 10 | `--check-update-privacy` | 0 | **PASS**. The row is compiled out, and no update-host traffic was seen across launch and Settings | `smoke/check-update-privacy/` |
| 11 | `--check-https-only` | 0 | **PASS** | `smoke/check-https-only/` |
| 12 | `--check-no-gms --check-no-adjust` (with `--serial`, so the baseline runs again) | 0 | **PASS**: both static checks, plus the whole baseline again, including a **second full graphics acceptance pass** | `smoke/static-no-gms-no-adjust/` |
| 13 | `--check-strings` | 0 | **PASS**. 234,764 rows, 0 unexplained. 36 screen stops, 0 branded strings shipped by the APK. 1 remote AMO description is reported, not gated | `smoke/check-strings/` |
| 14 | `--self-test` | 0 | **PASS** (`SELF-TEST OK`). All 7 probes reported FAIL when fed a wrong expectation | `smoke/self-test/` |
| 15 | `--first-run-capture` | 1 | **expected red (E12)**. 107 events, app UID rx +20,720,714 B / tx +422,109 B | `smoke/first-run-capture/`, `first-run-host-comparison.json` |
| 16 | `--check-no-remote-settings` | 1 | **expected red (E12)**. 4 events to the 3 Remote Settings hosts | `smoke/check-no-remote-settings/` |

**Tally (rows 1–16, harness `aabbb7a7`):** 14 PASS and 1 expected negative-control FAIL (Beta 2). Two rows
are expected red under E12. One row FAILed: `--check-no-suggest` (row 8).

**After the harness change (rows 8a–8d, harness `dba0f279`):** `--check-no-suggest` PASSes 3 of 3 on fresh
profiles, and its negative control FAILs as expected on `ac.duckduckgo.com`. No row is red apart from
the E12 rows and the two negative controls.

### about:config CSP (3a): why logcat alone proves nothing, and what does

`aboutconfig-csp/aboutconfig-csp-probe.py` ran on the same emulator right after row 3, on a fresh
profile, and reused the committed harness's own client and probes (`work/harness/driver.py`). It
opened about:config, waited for 30 rows, drove the page's own filter box, and toggled a pref it had
created (the toggle took effect). It then read the whole console service.

- **Console service:** 0 `Content-Security-Policy` / `script-src-attr` messages whose source is
  about:config. As a positive control, the probe deliberately triggered an inline handler under
  `script-src 'none'` in a web page. The query caught that violation: category
  `CSP_CSPEventHandlerScriptViolation2`, source `about:srcdoc`, text "blocked an event handler
  (script-src-attr)". So the query does see this class of error, and about:config produced none.
  Stage C's failing build produced 13 of these (`../../diag/new-153.4-aboutconfig-csp.json`).
- **Logcat:** 0 CSP lines, both in the probe's stream (4,019 lines) and in row 3's stream
  (`smoke/check-aboutconfig/check-aboutconfig.logcat.gz`, 1,686 lines). However, **this release
  build does not forward console errors to logcat.** Neither the probe's `Cu.reportError` marker nor
  the positive-control CSP violation appeared there. So a clean logcat cannot show the absence of
  CSP errors on this build. The console-service result above is the evidence.

### `--check-no-suggest` (row 8): what the red packets are

The packets in the typing window are listed in the check JSON (`typing_payloads`).
`typing-window-connection-trace.txt` traces their TCP connections in both directions.

- Times in the trace are epoch − 1790932500. The pcap record at the check's `typing_capture_offset`
  is at +12.3 s, and the record at `enter_capture_offset` is at +70.8 s, so typing began at or
  before +12.3 s.
- The window held 16 outbound payload packets (642 B). The harness classed 3 of them (138 B, Remote
  Settings) as background, and the other **13 (504 B) failed the check**. All 16 went out on **10 TLS
  connections that were already open before typing**: 7 to AMO and uBO's filter-list hosts (the 13)
  and 3 to Remote Settings. Between −1 s and Enter (+70.8 s)
  the device sent no SYN, no DNS query (udp/53 or DoT 853) and no QUIC packet (udp/443). The
  first ones after that are the DoT lookup and the connection for `noai.duckduckgo.com`.
- Payloads were 39 B or 46 B, and each was answered by a reply of the same size (the server's
  ack sequence advances by exactly that size). The same connections sent the same 39/46 B
  exchange about 59 s before typing started. For example, `raw.githubusercontent.com` port 48794
  exchanged one at −46.6 s, again at +12.3 s, then sent 39 B + 24 B and closed at +65.4 s. This
  matches a periodic HTTP/2 keep-alive (PING / PING-ACK sized), followed by an idle-timeout close.
  It does not look like a request.
- No suggestion endpoint, no sponsored host and no search host was contacted before Enter.

The harness at `aabbb7a7` counts these packets as typing traffic. Its pre-typing wait
(`quiet_s` = 20 s) is shorter than the roughly 59 s keep-alive period, so pings from connections
opened during startup are bound to fall inside the 60 s window. **This run does not show a product
leak, but by that harness's rule the check FAILs, and row 8 stays recorded as a FAIL.** Beyond what
is in this run, this was not verified by decrypting the traffic.

### `--check-no-suggest` after the harness change (rows 8a–8d)

`ac1c6ee4` changed the rule to attribute the typing window **by connection**, and `86a8fd02` only
reworded its PASS line. `docs/android/SMOKE.md` ("how the typing window is judged") describes the
rule. In short, a flow is typing traffic if it opens in the window (SYN, first datagram, or a
DNS answer for its address), sends any DNS query, is any non-background UDP, goes to a configured
search or suggestion host, or sends anything but one TLS record of at most 46 B. 46 B is one 17-byte
HTTP/2 PING/GOAWAY frame in a TLS 1.2 AES-GCM record, and is the size rc2 actually sent. Every flow
and its verdict are recorded in each run's JSON under `typing_flow_attribution`.

| | |
| --- | --- |
| `scripts/android-smoke.sh` | sha256 `dba0f279e5ca6eec7a51c1ac9d43e320536a88943c7494dca7e33b67a824ce46` (`86a8fd02`), recorded at the start of every run in `no-suggest-attribution/exit-status.jsonl` and by the driver as `harness_sha256` |
| HEAD at start | `86a8fd02` for 8a, `0927a58c` (SMOKE.md only) for 8b–8d; 0 uncommitted changes under `scripts/` for every run |
| APK | the same installed `77348e7d…af83` |
| Conditions | as above: one emulator (emulator-5584, rebooted from the same AVD with `-dns-server 9.9.9.9 -tcpdump`), `pm clear` before each run (the uBO sheet appeared and was acknowledged in all four), AMO reachable, no priming, no iptables. Every run streamed logcat |
| Wrapper | `no-suggest-attribution/run-check-attr.sh`: `smoke/run-check.sh` with only the output directory changed |

- **Re-grade of row 8.** `no-suggest-attribution/regrade-rc2-row8.py` runs the new attribution on row 8's
  own capture and offsets (the pcap kept on the build host as `work/capture-rc2-final-acceptance.pcap`).
  It gives 7 `keepalive` + 3 `background` flows and 0 typing flows (`regrade-rc2-row8.json`).
- **Negative control (8a).** The detail reads `NEGATIVE CONTROL (suggestions ON before typing):
  suggestion traffic to ac.duckduckgo.com was caught on 4 connection(s)`. Those 4 are the udp/53
  query and the 3 TLS connections. The other 2 typing flows are DoT lookups. The post-Enter search
  control and the OFF restore both passed.
- **Superseded run.** The first run after `ac1c6ee4` (harness `e5ecbc8e…`, the first line of
  `exit-status.jsonl`) PASSed too. It booted the emulator, so it has no logcat stream. Its PASS line
  still used the old wording, and it was rerun under `dba0f279` rather than counted. Its output is not
  copied here.
- **Unit tests** (`no-suggest-attribution/unit-tests/`, HEAD `0927a58c`, harness `dba0f279`):
  `scripts/tests/test-*.py` all exit 0. `test-android-smoke.py` ran 81 tests (65 before, plus 16 for
  the attribution on synthetic captures). Among them: a pre-existing keep-alive passes, a new connection
  during typing fails, a large payload on an old connection fails, and DNS during typing fails.
  `test-android-graphics-smoke.py` ran 30. `test-android-signing.py` and `test-android-version-code.py`
  exit 2 without their required arguments, as in `gates/`.

### First-run capture compared with rc2's own run

Both runs used the same APK. Compared with the rc2 first-run capture, `malware-filter.pages.dev`
is the only new named host. It is the mirror for uBO's URLhaus list in the bundled uBO 1.75.0
`assets/assets.json`. The other differences are raw CDN addresses with no DNS name in the capture.
No named host disappeared. Event count: 107 now, 91 in rc2. rx: 20.7 MB now, 23.6 MB in rc2.

## Gates and unit tests (`gates/`)

All were run after the device batch, on the tree being committed (HEAD `11fd562e` plus the
LW-M7-14 test fix and this directory).

- `check-patchfail.sh --targets=android` (153.4.0esr): 0, "All patches where applied successfully".
- `lint-patch-scope`: 0. `check-patch-order`: 0. `board.py --check`: ok, 122 tasks, 32 waves, 0 warnings.
  `board.py --check-scope`: ok.
- `scripts/tests/test-*.py`: all 0. `test-android-smoke.py` ran 65 tests, `test-android-graphics-smoke.py` ran 30.
  The exceptions are `test-android-signing.py` and `test-android-version-code.py`, which exit 2 without
  their required APK, classes or gradle-home arguments, as before. `test-android-signing.py` was then
  run with `--apk` (the rc2 unsigned x86_64) and `--apksigner …/apksigner.jar`: 29 tests OK.
  `test-android-version-code.py` was not run with arguments.

## Also in this commit

- **LW-M7-14 unit-test mock** (`docs/android/evidence/lw-m7-14/`): the `Services.perms` double said
  `EXPIRE_SESSION: 2`. The real value is 1 (`nsIPermissionManager.idl`). The literal asserts and
  the fixture seeds used 2 as well. All of them now use 1, and the `.tap` was regenerated against
  the rc2 tree with the command now written in the file header: still 37/37. This is evidence only;
  no shipped byte changes.
- **Not changed:** the `pinned uBO 1.74.0` code comment in `patches/android/ubo-readiness.patch`
  (line 124) is stale, since the pin is now 1.75.0. That comment is in Gecko JS that is packed into
  `omni.ja`, so fixing it changes shipped bytes and would require a Gecko rebuild (a new rc). It is
  left for the next rc that rebuilds Gecko anyway. The patch header (lines 3–8) already notes that
  the comment is stale.

## Not run or not shown

- No physical device, no ABI other than x86_64, and no release-key signing.
- No `--strings-locale` sweep, no Fenix unit-test run, and no Mullvad upgrade rerun (rc2's
  `../upgrade/` stands).
- Row 8 (`--check-no-suggest` under `aabbb7a7`) ran once. The harness change and its runs are rows 8a–8d.
- The pcaps and the AVD are not archived. They remain on the build host in
  `build/rc2/final/runtime/work/`: rows 1–16 in `capture-rc2-final-acceptance.pcap` (renamed from
  `capture.pcap` before the reboot, which would have deleted it), and rows 8a–8d in `capture.pcap`.
