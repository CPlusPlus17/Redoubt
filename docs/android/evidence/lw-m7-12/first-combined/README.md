# First combined compile

The isolated guest applied uBO readiness, uBO installation and privacy-defaults
patches to the frozen beta source. `source-application.log` and `input-sha256.txt`
record those exact inputs. `final-source-comparison.json` compares all 31
resulting source files against the committed implementation inventories; every
hash matches. Normalizing patch-file whitespace did not change compiled source.

`gecko-and-fenix-tests.log.gz` records successful `mach build -j4`, including
the cancellable GeckoView API, followed by a failed Fenix Kotlin compile. The
failure is a nullable `Throwable?` passed to `resumeWithException`; no Fenix
unit tests ran in this attempt. `compile-exit.txt` is 1.

Commit `1a762df` fixes that adapter with an explicit exception when Gecko supplies
no cause. The subsequent unit run was interrupted by a host OOM killing QEMU;
see `../../lw-m7-15/`. Neither attempt proves a completed Fenix suite or a
working feature APK.
