# CI memory interruption and recovery

The host kernel killed QEMU at 2026-09-08 21:56:39 UTC. The service recorded an
OOM result, exit 137 and a 28.1 GiB peak, then restarted it at 21:56:51 UTC.
The SSH command returned 255 with a connection timeout. The previous guest
boot and Fenix output end at approximately 21:09 UTC; there is no terminal
Gradle or Fenix-gate receipt for that run. The missing receipt is an interrupted
run, not a test pass or a demonstrated add-on-test deadlock.

Preserved evidence:

- `host-kernel-oom.txt`, `host-service-oom.txt`: actual host events.
- `parity-second-combined/`: applied source, patch hash and full interrupted
  test log, compressed without changing its content.
- `boundary-after-restart.txt`: complete isolation and resource check after
  reducing the allocation from 24 to 16 GiB. It verifies KVM, eight CPUs,
  available disk swap, rootless build tools, no host-home mount and the blocked
  host/private-network canaries. The host Actions runner stays disabled.

Runner 22 was online and idle before the controlled restart. Only the VM's
memory allocation and the matching verification threshold changed. The
existing 16 GiB disk swap and 8 GiB zram remain; zram is not extra physical RAM.
No unrelated host processes were terminated and no host credentials were copied.

The next full Fenix/extension-support run started at 22:06:42 UTC as guest user
service `redoubt-parity-fenix-20260909.service`, invocation
`082ac96ea67d4e1e9fa5da8854f098da`. Its replayable `run-fenix-suite.sh` limits the
container to 14 GiB RAM and 22 GiB combined RAM/swap. It records boot ID,
start/finish, logs, memory statistics, XML and separate Gradle/board exit codes
under guest `evidence/parity-third-combined/`. The service continued running
after its launch SSH connection closed. Its terminal result and the subsequent
APK build remain pending.
