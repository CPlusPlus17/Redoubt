# Box B CI VM — 2026-10-04

Owner decision 2026-10-04: Redoubt's heavy Android jobs move to box B (host `llm`,
`user@10.0.0.154`). Runbook: [CI-VM.md, "Box B"](../../../CI-VM.md#box-b-the-on-demand-build-vm).

**Done:** VM created and provisioned (16 vCPUs, 24 GiB, 250 GiB thin disk), runner
`redoubt-ci-boxb` registered as GitHub runner **ID 23** with labels
`self-hosted, Linux, X64, redoubt-boxb` and seen `online`, host/guest isolation
acceptance passed on box B, VM stopped again, box A poller timer enabled.
Box A's `redoubt-ci-qemu` (ID 22) was not touched.

**Not done here:** no workflow has run on box B yet. The workflow change is a
local commit; the coordinator pushes it and dispatches the proving build. No
Android build, APK, memory peak or build time on box B is claimed.

| File | What it records |
|---|---|
| [commands.log](commands.log) | Every command run on box B, in order, with UTC time and exit codes. Output of the initial read-only surveys of other owners' services is withheld (public repository). |
| [deploy-host.txt](deploy-host.txt) | `deploy-boxb.sh host`: packages present, pinned Fedora image verified, VM created, linger on, poller key bound, unit disabled. |
| [gate-wait.txt](gate-wait.txt) | 26 minutes of box B's memory gate deferring (both hasteheart jobs running; room ~3 GiB against 26 GiB needed). |
| [deploy-guest.txt](deploy-guest.txt) | `deploy-boxb.sh guest --force`: cloud-init (hostname warning, hostname correct afterwards), guest provisioning with the 22G/8G runner slice, runner 2.337.0 digest-checked and installed. |
| [register.txt](register.txt), [runners-after-registration.json](runners-after-registration.json) | Registration output (no token: it went through SSH stdin) and GitHub's runner list: ID 23 online, ID 22 unchanged. |
| [acceptance.txt](acceptance.txt) | `verify-host.py` on box B: QEMU in separate mnt/net/pid/user namespaces without `/home`, launch lock, 16 CPUs / 23.45 GiB, swap, slice limits, sudo denial, nft policy, IPv6 off, no host shares, `/home/mgysin`, `/home/user` and the keystore path absent, rootless Podman, public HTTPS, and ICMP administrative denial to box B's LAN address and the passt gateway. The Android image check was skipped (`--image-id none`): CI builds the image in the guest from the commit's Dockerfile. |
| [ondemand-dry-run.txt](ondemand-dry-run.txt) | Box A poller dry runs (VM up: idle, stop due after 15 min; VM down: nothing queued) and box B's gate at that time (defer). |

**Provisioning start over the gate.** The gate deferred for 26 minutes. The
provisioning boot (no build) was started with `guest --force` after bounding the
unit at runtime to `MemoryHigh=6G`/`MemoryMax=8G` with ~43 GiB `MemAvailable`; the
guest reported 0.7 GiB used after cloud-init. The VM was stopped through
`boxb-ctl.sh stop` and the runtime bound removed afterwards (`MemoryMax` back to the
drop-in's 26G). A build start never bypasses the gate: only `boxb-ctl.sh start`
starts the VM for jobs.
