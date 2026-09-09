# Process-corrected APK build

The reviewed configuration SHA-256 is
`4989eee9c037eb41b326b372347aa6205b994b6fb39f7f174cc6daa317b36aae`.
It selects source167 `4ff8b616…` and the actual successful full-suite invocation
`c02a8b984fae45dc859eff2b556b82f0`. All23 recovery repository dependencies matched
the reviewed host bytes. The previously uncopied original `test_contracts.py`
was copied exactly from its existing parent pin; all four original driver files
then matched. No original executable driver was changed.

Root started `redoubt-account-process-apk-20260909.service`, invocation
`598783f0987b4c139fb0053c501f5628`, with `RemainAfterExit=yes`. The driver validated
the selected source/test/native/history inputs before entering its canonical
APK build at06:05:25 UTC. It reuses native4 and writes fresh
`account-process-apk-output` and `evidence/account-process-apk` namespaces.

The build is running. All four APK resource checks and runtime remain pending.
`capture-config.py` records the exact source/test selection; `inputs.json` is the
actual reviewed guest configuration.
