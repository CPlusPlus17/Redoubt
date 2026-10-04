Fixtures for `scripts/update-manifest.py` (`test-update-manifest.py`,
`test-update-check-jvm.sh`). Both are AGP `output-metadata.json` files in the
shape `scripts/android-apk.sh` copies into `<outdir>/apk/`, reduced to the
fields the generator reads.

- `beta5-output-metadata.json`: Beta 5's real versionCodes, from
  `docs/android/evidence/lw-m7-41/migration/build/apk-badging.txt`.
- `beta6-output-metadata.json`: a hypothetical next build 24 build-hours later
  (Fenix codes move by `1 << 3` per hour). Not a real release.
