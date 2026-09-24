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

The retained unit finished with exit zero. All four actual APK resource checks
passed. Root captured50 members and independently checked every member hash and
all four structured resource verdicts. The archive SHA-256 is
`cc94c2d38b7cd1b3f42ad7195db992a38412a3de4d30018b1ef92b7933ef18b7`.
The x86_64 APK SHA-256 is
`7ce0d286a108d4434267e4377f4d82720c29e841c8d65c5a32612a8017857146`.
`result.json` records all four APK sizes and hashes. Binaries remain in the guest.

`capture-config.py` records the exact source/test selection; `inputs.json` is the
actual reviewed guest configuration. This is a development APK checkpoint using
disposable debug signing. Runtime acceptance is recorded separately.
