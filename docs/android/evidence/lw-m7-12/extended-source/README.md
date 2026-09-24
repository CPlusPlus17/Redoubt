# Integrated source for the next native build

Root applied the reviewed cookie-rule, graphics-permission and translation
patches inside the isolated QEMU guest after verifying all 31 existing compiled
uBO/privacy-default source hashes. Each new patch passed a zero-fuzz dry run,
actual application and exact before/after hash checks. Translation staging
validated the pinned catalog and compressed/decompressed WASM without a network
fetch. `guest-application.tar.gz` preserves the original pre-change files,
application logs, comparisons and final source manifest.

The final manifest binds 89 source/asset files, including unchanged dependencies.
It combines the final Fenix source inventory with the three tasks' resulting file
hashes and both staged translation assets; later patches take precedence on
shared files. The input plan was recorded at repository `818c024`. Its expected
hashes come from committed source inventories and the graphics task's recorded
`a759e38` baseline. No frozen host source was edited.

The all-three-ABI native rebuild started at 2026-09-08 23:11:33 UTC as guest user
service `redoubt-parity-native-20260909.service`, invocation
`6353935d4f434577b7f764bc21835e08`. `run-extended-native.sh` verifies the manifest
before/after building and records terminal results independently. It deliberately
omits `--skip-existing`, uses four compiler jobs, and retains the bounded OCI
wrapper (14 GiB RAM, 22 GiB combined RAM/swap, six CPUs). The build remains
pending at this receipt; source application is not compilation or runtime proof.

Followup: that first build failed in GeckoView Java compilation. See
`../native-first-attempt/` for the preserved failure, and `../../lw-m7-21/` for
the exact cancellation-interface correction and subsequent build. This original
application archive and plan retain the first integrated patch/source hashes.
