# QEMU runner migration — 2026-09-08

**Complete:** GitHub runner `redoubt-ci-qemu` (ID 22) replaced host runner
`redoubt-fedora` (ID 2). Existing production labels are preserved. The host
registration is revoked and its user service is inactive and masked.

The actual [Actions preflight](https://github.com/CPlusPlus17/Redoubt/actions/runs/34257944277)
passed on runner 22, job `102168382763`, at remote `android-port` commit
`56c5d8ed0e4f9f3be3d42f01ad6b7b6fb62ba04e`. Checkout and all five board/scope gates
passed; full build and artifact-publication steps were deliberately skipped by
the workflow's `preflight` input. This proves scheduling and runner readiness,
not compilation of the newer local beta candidate in the VM.

| Evidence | What it establishes |
|---|---|
| [verified-inputs.json](verified-inputs.json), [Fedora signature](fedora-checksum-signature.txt) | Signed Fedora checksum and image digest; official runner archive digest; identical host/guest OCI archive; exact imported Android image identity. |
| [guest-provision-final.txt](guest-provision-final.txt) | Completed provisioner with persistent DNS, firewall, restricted user, rootless Podman and disk swap. |
| [restart-health.txt](restart-health.txt), [earlier boot ID](boot-before-restart.txt) | A different guest boot returned with both services active, DNS configured, IPv6 disabled and cloud-init clean. |
| [acceptance-before-cutover.txt](acceptance-before-cutover.txt) | KVM/resources, QEMU namespace separation, absent host home, duplicate-launch lock, guest privileges, rootless container tools and network controls passed before routing production labels. |
| [acceptance-after-cutover.txt](acceptance-after-cutover.txt) | Same checks passed after retirement, including host runner inactivity. A temporary host TCP listener was positively tested locally; guest probes received ICMP administrative denial. |
| [preflight-run.json](preflight-run.json), [preflight-jobs.json](preflight-jobs.json), [preflight-log.txt](preflight-log.txt) | GitHub's run conclusion, exact runner ID and actual workflow log. |
| [runners-before-cutover.json](runners-before-cutover.json), [runners-after-cutover.json](runners-after-cutover.json), [host-runner-retired.txt](host-runner-retired.txt) | New runner online, old registration absent, old host unit masked with PID 0. |
| [source-files.sha256](source-files.sha256) | Local scripts and documentation implementing this deployment. |

The guest has 8 vCPUs, 24 GiB configured RAM (23.45 GiB usable), a 400 GiB sparse
overlay, 16 GiB disk swap and 8 GiB zram. The image provides Clang 21 and Java 17;
Fedora's Java 25 satisfies the outer workflow's tool-presence check. No full-build
memory or timing claim is made.

No host home directory, keystore, existing Actions credentials or GitHub CLI
credentials were transferred into the guest. Registration used a fresh temporary
token; the host administration key lives outside QEMU's namespace. Host/kernel
and hypervisor trust, persistent state between jobs, and abrupt recovery on passt
failure remain limitations described in the [runbook](../../CI-VM.md).

The APKs previously signed on Fedora retain that provenance. This deployment
establishes the current CI boundary; it does not retroactively establish offline
signing or close BETA E7's historical custody requirement.
