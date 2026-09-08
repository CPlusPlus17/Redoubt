# Privacy-defaults patch integration, 2026-09-08

Produced by the human_criteria agent on the Fedora host in the detached
LW-M7-12 integration worktree based on `a059f34`. The shared beta source tree
and the VM source/build were not modified. This evidence establishes patch
registration, scope and application; compilation, Fenix tests and APK behavior
are separate LW-M7-12 gates owned by the root agent.

`privacy-defaults.patch` is registered after the existing Fenix default changes
and the uBO patches. There are 24 common, 29 Android and 36 desktop patch files,
89 total. The Android apply sequence contains 53 patches.

## Measured application

[android-full-patch-apply.log](android-full-patch-apply.log) and
[android-full-patch-apply-result.json](android-full-patch-apply-result.json)
record `scripts/check-patchfail.sh --targets=android`: exit 0, all 53 patches
applied to a freshly extracted Firefox 153.0esr archive in a private temporary
directory. The archive and lists were supplied through symlinks in a private
driver directory because this detached worktree has no source archive. The
checker removed its extraction afterward. Existing historical patches still
report their ordinary offsets/fuzz; the checker preserves GNU patch's exit
status and checks for rejects.

[privacy-pair-replay.json](privacy-pair-replay.json) binds the source archive,
all 53 patches and the two shared source files to SHA256 values. Its baseline
replays the applicable list entries into those files from the pristine archive.
For each pair it then reverses the old partner, applies both possible orders,
and compares complete output files. **All five pairs apply in both orders at
`--fuzz=0` and produce byte-identical files.** Offsets are permitted; dropped
context is not.

| Partner | Shared files | Review finding |
|---|---|---|
| `no-adjust` | `Settings.kt` | Marketing onboarding default is separate from the privacy preference properties. |
| `no-gms` | `Settings.kt` | Removal of the push-server preference is separate from the privacy defaults. |
| `no-onboarding` | `Settings.kt`, `SettingsTest.kt` | Onboarding function, flag and assertions are separate from privacy defaults and assertions. |
| `no-suggest` | `Settings.kt`, `SettingsTest.kt` | Suggestion, trending and Contile changes are separate from privacy defaults. Some hunk coordinates abut, but both-order replay establishes that context still applies. |
| `search-config` | `Settings.kt` | The remote-search-configuration constant is separate from privacy defaults. |

There are no shared files between privacy-defaults and either new uBO patch.
The prior uBO integration retains its measured `no-adjust` constraint and seven
order-free pairs. The order checker now derives and classifies 91 pairs and
enforces 12 constraints; privacy-defaults adds no new required ordering pair.

The replay can be repeated without an existing Firefox tree:

```sh
python3 docs/android/evidence/lw-m7-12/patch-integration/replay-privacy-pairs.py \
  --archive /path/to/firefox-153.0esr.source.tar.xz \
  --output /tmp/privacy-pair-replay.json
```

## Repository gates and input boundary

[repository-gates.json](repository-gates.json) records exit 0 for the patch
order checker, scope inventory, task board, patch-scope linter and diff check,
with input hashes. The task board reports 98 tasks, 22 waves and no warnings;
the linter reports 89 patch files and no violations.

The full-application result above used the three feature patch versions at
`a059f34`, whose hashes appear in the pair replay. The separate Kotlin nullable
error-callback fix `1a762df` was produced while this check ran and is not silently
included in this snapshot. It changes only the content of a newly added
installer file and has its own zero-fuzz patch dry-run. The final combined
build and input comparison must name the updated installer source hash; these
application results do not claim that later source was compiled or tested.
