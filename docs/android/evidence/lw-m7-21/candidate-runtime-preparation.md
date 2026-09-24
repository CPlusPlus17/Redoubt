# Native4 checkpoint runtime preparation

The updated `run-candidate-smoke.sh` consumes the successfully completed extended
APK build and its source manifest. It verifies all four APK hashes, all APK source
bindings and the retained packaged shortcut check before booting a fresh dedicated
emulator workspace. It rejects an existing device or running Podman container.
The old feature APK receipt is no longer an input.

The first profile runs the existing real uBO install/enable/disable persistence
regression. A separate fresh profile runs the default browser suite, which now
requires the complete graphics consent/rendering/lifetime runner when the native
prompt is enabled. The effective preference audit remains a separate required
result. Each run keeps its own packet capture and emulator files; repeated
invocations do not reuse or overwrite earlier runtime workspaces.

These three results are a build checkpoint, not complete feature acceptance.
The cookie HTTPS fixture, actual add-on UI lifecycle and signed update, immediate
private-permission regression, translation DOM/offline behavior and other feature
controls still need their dedicated installed-APK runs. The current native4
source does not include LW-M7-31 or LW-M7-29; their future candidate behavior
cannot be tested against this APK. The LW-M7-31 predecessor mode may be used for
an explicitly labelled baseline measurement after a separate fresh profile is
prepared.

Root checked Bash syntax for the updated coordinator. No emulator or APK test
has run as part of this preparation. Native4 remains active. The resource staging
helper and APK coordinator were copied into the guest repository and their hashes
match root; that transfer did not change any active native source or start Gradle.
