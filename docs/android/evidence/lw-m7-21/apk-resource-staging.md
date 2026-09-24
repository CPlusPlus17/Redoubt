# Fenix resource stage after native compilation

`stage-apk-resource.py` prepares the LW-M7-30 empty shortcut resource only after
the isolated native build records a successful completion and no build container
remains. It verifies the complete native source manifest and all three Maven
archives, checks the reviewed original resource and patch hashes, then applies
the one resource change with zero fuzz and no offsets. It checks native source
and archive hashes again and records a new APK source manifest containing the
original native bindings plus the resource. Existing staging can only be reused
when its receipt, source bytes and native inputs still agree.

`run-extended-apk.sh` invokes this stage before Gradle, retains both manifests,
and checks the packaged APK resource on successful compilation. It does not
add later permission or Suggest implementation candidates to the active native4
build. Those require a separately reviewed native build and artifact binding.

Root ran Python syntax, Bash syntax and board checks for this preparation. The
stage has **not run in the guest**, and the resource is not yet compiled into an
APK. Fresh/upgrade/manual-add behavior remains pending. Native4 is still running
with its original 164-entry source manifest.
