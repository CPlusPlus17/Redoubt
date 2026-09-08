# Beta candidate audit — 2026-09-08

Produced by Codex agent `/root/entry_audit` on the build host. The authoritative
candidate results are in [final-candidate/](final-candidate/). Files immediately
in this directory are diagnostics against the older handoff payload and do not
establish readiness of the replacement candidate.

## What the old evidence missed

* The original unsigned handoff differed from both the previously tested APK and
  the reproducibility hashes. Its manifest and Glean app-version string used the
  build's wall-clock-derived version code. `artifact-inspection.json`,
  `manifest-difference.txt` and `classes2-difference.txt` record the comparison.
  The replacement build fixes deterministic version/time inputs; root's M6-08
  evidence owns its build and reproducibility results.
* The baseline WebGL probe interpreted protected `readPixels` output as a broken
  renderer. `webgl-diagnostic.json` and its two PNGs prove actual rendering:
  the compositor captured a uniformly blue canvas with pixel `[51,102,153,255]`,
  and a deliberately red shader produced `[255,0,0,255]`. Granting only the local
  fixture's canvas permission also restored exact readback; removing it restored
  placeholder output. No privacy pref was changed. The shipping harness now
  reads the composited canvas without changing canvas permissions.
* The emulator acquires `wlan0` at `10.0.2.16` after initially exposing `radio0` at
  `10.0.2.15`. The old capture filters sampled only the initial address. The saved
  `check-no-suggest.pcap` contains search DNS/TLS traffic from `.16` which the old
  result omitted. Thus the old explanation that all missing search events were
  merely reused connections is not established by that run. A first analysis in
  this audit also reused only `.15`; that analysis is withdrawn.
* Independently, handshake-only summaries cannot detect query payloads on reused
  TLS connections. The typing gate now checks transport payloads, tracks complete
  SNI fields by full connection tuple, and requires both outgoing search-connection
  bytes and a fully loaded engine document containing the submitted query. Its
  post-capture setting check exercises ON and restores OFF. Unknown traffic does
  not count as proof of silence.

The harness retains old and newly discovered interface addresses, parses IPv6
transport headers, validates packet boundaries, and refuses incomplete fixed
capture windows. Complete SNI fields remain usable if unrelated later TLS
extensions span another packet; truncated hostnames cannot impersonate an
allowlisted prefix. The tests include all of these failure shapes.

First-run and Remote Settings commands still intentionally assert zero traffic
and remain red under E12. Transport events are not HTTP request counts, and a
packet capture does not itself establish Android UID ownership. First-run
summaries retain the explicitly enumerated OS endpoint/transport exclusions in
`is_os_noise`; the stricter connection-scoped payload accounting is specific to
`--check-no-suggest`.
