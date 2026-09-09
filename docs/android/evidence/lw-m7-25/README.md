# Native build allocation adjustment

Native attempt 2 (`redoubt-parity-native2-20260909.service`, invocation
`6ec57743c75748f49e10a0d155fb6366`) began at 2026-09-08 23:21:38 UTC.
GeckoView Java compilation passed the corrected cancellation delegate. The
first ABI then reached native JavaScript-engine compilation and gkrust-shared.
It has not produced a successful all-ABI result.

At 23:56:48 UTC the guest command reported 15,974 MiB total RAM, 93 MiB available,
8,333 MiB swap used, and memory full pressure averages 21.19/21.25/20.03 percent.
Rust PID 62682 held 12,047,164 KiB RSS; three clang processes held another
510,756/198,436/187,128 KiB. These values were read from `free`, `/proc/pressure`
and `ps` through SSH. The same command's unprivileged log read failed with
permission denied; that is not a missing build log. Later status commands timed
out, including an SSH server-alive timeout. The last retrieved compiler log
showed elapsed 19:23 and `js/src/vm`; a quiet log alone does not establish a hang.

`host-before.json` records available host memory and pressure before adjustment.
`previous-inside.sh` preserves the old installed 16 GiB launcher. The host had
about 20 GiB available and no measured host memory pressure. No unrelated host
process was changed.

Root requested graceful ACPI shutdown through the existing QMP helper, preserving
the VM disk and build intermediates. The replacement launcher allocates 20 GiB.
The native-only wrapper caps a container at 17 GiB RAM plus up to 6 GiB swap,
under an 18 GiB / 6 GiB limit on the entire runner user slice. Inspection of the
previous journal showed Podman's container scope was a sibling of the driver
service; the previous service cap therefore did not encompass the container.
Existing Fenix/APK/test container limits stay at their previous values beneath
the new shared user ceiling. This allocation is a measured followup to the earlier
24 GiB host OOM and 16 GiB guest pressure, not proof that all native builds fit.

The VM shut down cleanly and synchronized its filesystems (`graceful-shutdown.txt`).
The compiler received SIGTERM (`MACH_EXIT=143` at 00:03:12 UTC); the driver service
then timed out while stopping its remaining catatonit child at 00:03:57. This is
an interrupted attempt, not a compiler result. `guest-interruption.tar.gz` pins
the original logs and all 89 matching source hashes after reboot; the complete
service journal is also retained compressed.

The full isolation/cutover check passed with 20 GiB and the shared runner limits
(`isolation-after-restart.txt`, `runner-slice-limits.txt`). The reviewed add-on/home
followup then applied with zero fuzz/offsets and all 100 final source hashes
matched (`lw-m7-12/followup-source/guest-application.tar.gz`). Its first invocation
failed before mutation because Podman inherited an inaccessible administrator
working directory; the driver now selects the runner repository explicitly.

Native attempt 3 began at 2026-09-09 00:09:39 UTC, invocation
`7b886043b1ff4f47b4d72e0d7590797e`, using that 100-file manifest and the new native
wrapper (`native-attempt-3-start.txt`). Its build result and observed peak remain
pending. No release signing or publication occurs in this work.


Attempt 3 failed at 00:29:30 UTC: driver exit 1, armeabi-v7a mach exit 2.
The gkrust compiler was killed by SIGKILL and the runner cgroup recorded one
OOM kill. Its peak was 19,019,694,080 bytes RAM and 6,442,450,944 bytes swap.
Both source checks still matched all 100 inputs. Neither remaining ABI ran;
the existing AAR directories contain earlier artifacts. The log's literal
`PASS armeabi-v7a END` is a pass-name marker, not a successful exit verdict.
`native-third-attempt/` retains the full per-ABI log, source/config hashes,
build resource profile, service journal, cgroup observations and result.

The recorded rustc command combined release optimization, fat LTO and
`-C debuginfo=2`. The pinned configure source unconditionally chooses Rust
level 2 whenever debug symbols are enabled, even for a lower C++ symbol level.
The archived root Cargo release profiles do not enable debug data independently.
The next configuration adds the supported `--disable-debug-symbols` option.
Optimization, Rust LTO and the hardening options remain unchanged; diagnostic
symbols will be unavailable. This is a build-memory adjustment, with no claim
that the revised build fits until it actually finishes.


Native attempt 4 began 2026-09-09 00:53:49 UTC, invocation
`367f4a0c473843b4832ee42f0c9e2ff2`, after the source-bound Sync, final cookie-session
fence and Suggest candidates were applied. Its 164-file source manifest and all
application receipts live under LW-M7-21/policy-source. The start receipt pins
the revised mozconfig and records the inherited cgroup OOM count of 1 from
attempt 3; that counter alone must not be attributed to attempt 4. The new
configure output has `MOZ_RUST_DEFAULT_FLAGS = --cap-lints warn`, without the
previous debug-info override. Compilation and final memory outcome are pending.
