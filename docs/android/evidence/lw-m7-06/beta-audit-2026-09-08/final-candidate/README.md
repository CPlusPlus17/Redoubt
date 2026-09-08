# Final candidate runtime audit — 2026-09-08

The final candidate passes the baseline, search, suggestion, about:config,
update-privacy, branding and pref gates. The two strict zero-traffic assertions
remain red, as E12 requires. This is emulator evidence; physical-device coverage
and beta release authorization remain separate requirements.

## Candidate identity

All APKs are from `librewolf-android-apk-153.0esr-1-beta-20260908/apk/`:

| APK | Unsigned SHA-256 |
| --- | --- |
| arm64-v8a | `500af705ed3cf213ea29d61f8740da3dcbbc1418ad0a41d5fb19f5a3aab95723` |
| armeabi-v7a | `3ec70b156247a7f30884e3ad1fbb984d5ad38b765f8912d05016cacbf1f56c29` |
| universal | `65afc33437804c2ad8316a88560e6a9e0c3095c386ff5a6eb05c70cb71ba9f0c` |
| x86_64 | `5293ff6cffd3d2a56fbe8ac8c26a2cb936f628992d0fd16cf1ced8103bd5b08b` |

The installed x86_64 APK has SHA-256
`2da5f1d2786f5c206884448b34908b7c229f4a9c50d371b9e6ee4fc9b6259300`.
It was signed only with a disposable test key. All 3,118 uncompressed ZIP entries
match the unsigned candidate, including manifest and DEX payloads; see
[payload identity](payload-identity.json). No release keystore was used.

[Artifact inspection](artifact-inspection.json) binds the four ZIPs, native ELF
architectures and engine hashes to their packaged AAR inputs. The universal APK
contains all three real engines. The x86_64 `omni.ja` also contains the current
`settings/android.cfg` bytes. Runtime reports Redoubt `153.0esr-1`, build ID
`20260906190000`, on an API 30 x86_64 emulator with SwiftShader. Exact emulator
arguments and device interfaces are in [runtime provenance](runtime-provenance.json).
Candidate source/build, Fenix tests and independent APK reproducibility are
documented in [LW-M6-08](../../../lw-m6-08/).

## Authoritative results

| Check | Result and evidence |
| --- | --- |
| E2 native payloads | All four APKs inspected; ARM32/ARM64/x86_64 ELF identities match their AAR inputs. See `artifact-inspection.json`. |
| E3 baseline | `baseline-smoke.json`: 7/7 pass, including HTTP, trusted HTTPS, composited WebGL, decoded video, denied getUserMedia and a running extension. |
| WebGL control | `webgl-render.png` has the expected composited pixel `[51,102,153,255]` while protected readback remains reported separately. `baseline-self-test.err` records an actual WebGL FAIL under a wrong expected value, with the complete negative-control suite returning exit 0. No privacy pref was relaxed. |
| Suggestions | `check-no-suggest-verified.json`, exit 0: 60 seconds of typed-but-unsubmitted input produced zero payload packets outside explicitly identified background flows. Enter produced 16,148 outbound TCP payload bytes on the default engine connection and a complete real results document containing the submitted token. The suggestions switch was OFF by default and an ON→OFF round trip succeeded. |
| about:config | `check-aboutconfig-final-verified.json`, exit 0: release-configured app, 30 pref rows, enable=true on the default branch without a user override, one UI click changes the test pref and its true user value survives a restart. |
| Search/defaults | `check-search.json`, exit 0. |
| Update privacy | `check-update-privacy.json`, exit 0: the update check and settings row are compiled out because this candidate has no real update-signing key. |
| Strings | `check-strings.json`, exit 0: 234,644 resource values and 36 UI stops checked, zero unexplained shipped-brand leaks. One remote uBlock Origin description mentions Firefox and is recorded separately. |
| Static SDK removal | `static-smoke.json`: no GMS and no Adjust checks pass. |
| E4 prefs | Generator exit 0, reviewed byte-identical baseline diff, then audit exit 0. See `pref-baseline-regeneration.json`, before/generated text, empty `pref-baseline-diff.out` and `pref-audit-final.out`. All 58 rows retain SHA-256 `2ac8b4f96efb7445696da272f06a21f63521b8b8be9f33df27a0504de1b8268a`. Of 137 must-lock keys, 20 are covered by the runtime dump; this audit does not itself cover the other 117. |
| E11 honest DNS | Quad9 `9.9.9.9`; `honest-dns-resolution.json` records routable telemetry/ads controls and security-host DNS answers. The final capture has 11 non-exempt outbound transport events, as detailed below. |
| E12 effective decision | `effective-remote-settings.json` compares the effective runtime string to `settings/android.cfg`: all seven approved entries match; the eleven packaged-only FromDump entries remain present. Full runtime data is `prefs-all.json`. Hostnames do not prove which encrypted collection paths were requested. |

## Network windows and limits

`first-run-capture-final.json` is the authoritative first-run window, with original
capture byte offsets **56,963,909–57,653,048**. It reports **11** non-exempt outbound
events, including three SNI names: `firefox.settings.services.mozilla.com`,
`firefox-settings-attachments.cdn.mozilla.net` and
`content-signature-2.cdn.mozilla.net`. The other events are connection attempts,
including IPv6. This command exits 1 because its zero-traffic assertion remains
unchanged. The separate `check-no-remote-settings-final.json` window is
**57,654,160–58,340,301**, with 12 total events, 11 non-exempt events and three
Remote Settings SNI hits; it also exits 1.

The earlier final-candidate `first-run-capture-honest-dns.json` recorded **14**
events in a different window. It is retained, not substituted for the final 11.
Older evidence reporting six events omitted the later `.16` interface and IPv6;
that number is not a valid count of these captures. Each raw `.pcap` has a
matching `*-pcap-window.json` mapping its byte offsets to the original capture.
[Current-parser replay](event-pcap-replay.json) independently reconstructs the
distinct counts and hosts from the archived raw files.

These are transport events, not HTTP requests or Android UID attribution.
First-run and Remote Settings summaries retain the enumerated historical OS
endpoint/transport exclusions in `is_os_noise`. The zero UID byte deltas are
not evidence of zero traffic. The suggestions gate uses stricter, separate
connection-tuple payload accounting; an allowed hostname does not exempt another
connection sharing its CDN address. Complete SNI fields are required, incomplete
typing-window tails fail closed, and traffic on reused TLS sessions remains
visible. Its scope is absence of unexplained outbound payload during the measured
typing window, with explicitly identified security/OS background activity retained.

The saved `check-no-suggest-verified.pcap` includes startup before typing. Its
`*-command.json` records the original archive start, typing/Enter offsets are in
the result, and [replay](verified-pcap-replay.json) reproduces zero suspect typing
packets and all 16,148 search TCP payload bytes with the frozen parser.

The QEMU pcap timestamps lag the host clock by about one hour. A fresh isolated
local ICMP control measured **3,600.62 seconds** of lag while host and Android
`date +%s` agreed within one second; see `clock-comparison.json` and
`clock-control.pcap`. We do not infer a cause. Byte offsets, host command receipts
and candidate hashes bind these captures to their executions; pcap timestamps
must not be interpreted as host UTC without this measured offset.

## Harness provenance and replay

Frozen `scripts/android-smoke.sh` SHA-256:
`ad3930ee8ae5de208b9b9f852d06c10e04a69218618b9a70632ee1ca649fc265`.
Regression test SHA-256:
`0f5aaec3361c47b13c7f7afec0ef15916dece64381a85fe9204a68872a45d863`.
The complete hashes, including Android config, are in `harness-source.sha256`.
From the repository root, replay the 23 deterministic regression tests and diff
validation with:

```sh
python3 scripts/tests/test-android-smoke.py
git diff --check -- scripts/android-smoke.sh scripts/tests/test-android-smoke.py
```

Both commands pass; their exact output is archived. A second agent independently
ran all 23 tests and reviewed the final change. Tests cover reused TLS payloads,
connection/SNI attribution, partial capture boundaries, IPv6, interface changes,
PNG decoding, and bounded read-only document retries.

The successful suggestion command recorded its loaded source at start as
`16e25a06cebde3ddfeb1ce159dd1a01f0845a35fb95acc5686d12d787bb70b90`;
only the unrelated about:config code changed afterward. Final about:config was
run on the frozen hash above. Earlier baseline/UI/pref runs exercised unchanged
probe functions; they are not retroactively labeled as having loaded the final
file. `runtime-provenance.json` describes its measured source state, and
`final-exit-status.jsonl` explicitly labels its hashes as on-disk-at-completion.
The first-run/Remote Settings final runs used parser state
`ea24053a370686d6c01d07618240c4889251f7b6433e84b4ed70feb6c729dab1`;
their event parsing is unchanged in the frozen file.

Failed intermediate `check-no-suggest-final` and about:config attempts are
diagnostics, superseded by the explicitly named verified results above. The
former loaded an overly strict SNI parser before its fix. The latter exposed
actual document unloads while an asynchronous probe was waiting. The final
about:config implementation retries only page inspection and idempotent filtering
at most three times for that exact error; its pref-changing click is separate,
synchronous and never retried. The successful result records the observed retry
and the subsequent single click and persisted value. The underlying reason for
the document replacement is not established by these observations.
