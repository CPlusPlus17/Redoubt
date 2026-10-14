# Security policy

Redoubt is a privacy-hardened Android browser built from Firefox's source and
LibreWolf's privacy configuration. It is an independent project: please report
Redoubt security issues here, not to LibreWolf or Mozilla.

## Reporting a vulnerability

Report privately, either way:

- through [GitHub private vulnerability reporting](https://github.com/CPlusPlus17/Redoubt/security/advisories/new), or
- by email to **security@redoubtbrowser.org** (no GitHub account needed).

Please do not open a public issue for a vulnerability.

Also report it privately if a downloaded APK's signing certificate does not
match the fingerprint in the [README](../README.md#install-and-verify), or if
any download channel serves a build we did not sign.

## Supported versions

Only the latest release on the
[Releases page](https://github.com/CPlusPlus17/Redoubt/releases) receives fixes.

For the full process (scope, what counts as a Redoubt issue versus a Firefox or
Gecko one, and how fixes ship), see
[`docs/android/SECURITY.md`](../docs/android/SECURITY.md).
