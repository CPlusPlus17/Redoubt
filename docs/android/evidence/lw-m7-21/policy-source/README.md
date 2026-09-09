# Next integrated policy source

`guest-before-source.tar.gz` was captured read-only after native attempt 3 failed.
The capture verified all 100 parent source/asset hashes and no running Podman
container, and retains 76 requested candidate paths with explicit absent files.
No release key or profile is an input.

`prepare.py` composes the reviewed Sync, final native cookie-controls and Suggest
patches against those actual guest bytes. It verifies each author's before/after
hashes. Where earlier patches add extra changes, it reverses/replays only those
intersecting candidates and verifies both composition orders. The expanded cookie
baseline omits uBO-readiness in api.txt and GeckoViewStartup.sys.mjs; those two
preexisting changes are preserved and pinned explicitly. The resulting guest
patches carry only rebased line coordinates/context from this measured source.
Root GNU patch dry/apply checks pass for every stage with zero fuzz/offset, and
all per-stage final hashes match. `input-plan.json` binds both original and rebased
patches, the captured baseline, revised mozconfig and 164 final source/asset files.

`apply.py` requires the terminal native3 service and exact failed-run receipt,
no active container, the revised config and matching 100-file parent manifest.
It archives original guest files before applying, checks each stage before and
after, and writes a separate 164-file manifest. Build/test/runtime acceptance
requires subsequent runs; this source plan itself establishes none of them.

The prepared extended test driver now requires the new Sync, cookie and Suggest
classes, archives seven result directories before execution, and retains the full
Fenix allowance gate plus fresh XML and mandatory-class checks. Native xpcshell
and GeckoView instrumentation need the separate test-enabled driver (LW-M7-27).


Application completed as runner: all 100 parent, per-stage 23/36/20 and 164 final
hashes matched, with zero fuzz/offset. `guest-application.tar.gz` retains original
source bytes, all before/after rows and patch logs plus the prior guest mozconfig
and native driver. The initial backup command named three prepared drivers absent
from the guest; it was corrected to archive the two existing files before transfer.
No source was changed by that failed archive attempt.

Native attempt 4 started at 2026-09-09 00:53:49 UTC, invocation
`367f4a0c473843b4832ee42f0c9e2ff2`, using this 164-file manifest and revised
`--disable-debug-symbols` configuration. Actual configure output now omits Rust
`debuginfo=2`; optimization and PHC remain enabled. The build is still running.
LW-M7-30/29/31 changes are not part of that source set. No target test or new APK
runtime result is claimed by this receipt.
