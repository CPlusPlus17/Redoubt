# LW-M7-10 — honest static parity gates

Produced by the `parity_gates` agent on Fedora, 2026-09-08. This is evidence for
the host verification scripts only. It contains no new APK, device result or
claim that Android has achieved network or fingerprinting parity.

Both previous wrappers returned zero after a successful `adb get-state`, although
they only printed instructions for future behavior tests. They also ignored
rejection of their positive self-test control, accepted preferences inside
comments, and could omit a missing Android cfg while grading the remaining file.
The network parser additionally ignored `lockPref`.

The wrappers now return 3/PENDING whenever live verification is requested,
including when adb is connected. Without device arguments, zero means explicitly
labelled **CONFIGURED ONLY**. HTTPS-only's effective Fenix switch, compiled TLS
defaults, negotiated TLS, certificate behavior, DNS behavior and fingerprint
coherence are all explicitly unmeasured. LW-M7-11 owns live probes.

Static checks parse literal calls without executing configuration code. They
handle line/block comments, quoted strings, multiline calls and template strings
without interpolation. Each input must exist and parse completely. Unknown
JavaScript, conflicting preference types and unsupported syntax fail closed.
The parser models fresh cfg user/default branches, lock replacement, unlock and
clear operations. A user write equal to its default clears that user value, so a
later default can become effective. This behavior was read in the frozen source:
`extensions/pref/autoconfig/src/prefcalls.js` (`pref`, `defaultPref`, `lockPref`,
`unlockPref`, `clearPref`) and `modules/libpref/Preferences.cpp`
(`SetDefaultValue`, `SetUserValue`, lines 876–943). Packaged defaults, existing
profiles, subsequent overrides and Fenix writes are outside this model.

The network expectations match the supplied LibreWolf cfg: DoH mode 5 means
explicitly off, with the Quad9 and dns4all URIs configured for opting in. Neither
URI establishes actual fallback behavior. CRLite must be mode 2; mode 3 defers
revoked results to OCSP and does not meet this baseline with OCSP disabled.
Absent `security.tls.version.min` and the main HTTPS-only switch are reported as
unmeasured rather than silently proving a compiled or Fenix default. Letterboxing
is checked only against the disabled default; its optional implementation and
fingerprint coherence remain outside this gate.

Validation:

- [29 black-box tests](black-box-tests.txt) pass. They exercise the actual shell
  scripts with temporary cfgs and fake adb/checker processes, including the
  observed false-success paths and always-pass/always-fail self-test mutations.
- Both embedded Python programs executed against the real composition of
  `common.cfg` and `android.cfg`: [network](network-composed-cfg.txt) and
  [RFP](rfp-composed-cfg.txt). Both self-tests required acceptance of that
  composition and their synthetic positive, plus rejection of every weakened
  control: [network](network-self-test.txt), [RFP](rfp-self-test.txt).
- [Bash syntax](shell-syntax.txt), [whitespace](diff-check.txt), and
  [board structure](board-check.txt) pass. The board reports 97 tasks, 21 waves,
  zero warnings.
- [Receipt](receipt.json) records exact input hashes, the settings commit,
  composition order, commands and exit codes. The worktree has no initialized
  settings submodule, so the cfg checks used a task-private concatenation of the
  initialized main checkout's two files, identified by those hashes.

No Android application source changed in this task. APK compilation, the Fenix
unit suite, smoke tests and live preference/behavior audits belong to the
integrated feature candidate and have not been run for this script-only change.
