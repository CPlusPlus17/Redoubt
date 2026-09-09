# Task37 on the preserved fifth-fixture source plan

This is a historical source composition, **not staged, compiled or target-tested**.
The Task20 production correction and later Task23/26 test fixes were still being
integrated when this snapshot was prepared. They are excluded here and require a
separate reviewed revision before the next native build. No guest was accessed.

The exact prior handoff is preserved in `parent-handoff.tar.gz` (SHA-256
`332e7ff92cce3431d9d9ffd19d0216e9fa8291f847676343f828721984fe831f`).
Its internal file inventory is checked in full. Its historical current165 manifest
is `659bf836ec885425b596bf077236190e8df30b2285df625ff3988c5dc93129b6`,
and its proposed230 manifest is
`7af4e037a693c46a86403d1d4bf31df66b81891c4a3857a73d222ca66fff597b`.
Original compiled APK, failed tests, earlier source plans and ordering receipts
remain unmodified in that archive; none becomes an acceptance result for Task37.

The overlay applies the complete 15-file Task37 patch from `2456b0c`, SHA-256
`d2756b4f5fe27adef63114a78ae7338ffbc13d0da60933ac03636b39721c5248`.
Both shared GeckoView test-support files match Task35's exact output before
application. Eleven additional existing files match the retained actual guest
capture; the two new test paths have captured absence records. The original
source capture, baseline and all before/after hashes are pinned in `inputs.json`.
Application has zero fuzz and zero offsets, and every unrelated body is unchanged.

The resulting source manifest has **243 bindings**, SHA-256
`02a4d0f252a6cf7ca76c7f30454a51792c0bcd67afffa8d72f6b553a3ef69c2e`.
The 97-file materialized archive is
`a9852502e370321b2f568c12c398d812e95446a1e19b7397cbe73cfede539ca0`.
All 146 unchanged native source bindings remain included in the full manifest;
their bodies require live verification. The archive is not a complete Gecko tree.
All existing generated Suggest resources and Task30's empty raw resource are
preserved byte for byte.

The proposed staging plan retains 43 replacements, 45 creates and 9 materialized
unchanged inputs. Its full preflight checks 198 existing hashes and 45 absences:
the historical current165 inventory plus 78 additional inputs. It checks the
actual pre-staging bytes, not the hypothetical230 intermediate tree. The two
test-support files explicitly retain their original live-before hash and their
35 → 37 transition history. The after check covers all 243 hashes.

## Replay and read-only preflight

Run from any directory, using the retained repository checkout:

```sh
python3 docs/android/evidence/lw-m7-37/composition-fifth-fixture/check.py
python3 docs/android/evidence/lw-m7-37/composition-fifth-fixture/compose.py --output /new/private/output
```

The local check reconstructs the real archived source twice in fresh temporary
directories, compares every retained output, and rejects modified existing files,
unexpected new files, dangling symlinks at create paths, traversal and duplicate
manifest entries. These are source/preflight checks, not native behavior tests.

An authorized operator may explicitly run the read-only live check below; it was
**not run on the guest** for this handoff. A newer live source baseline will fail
this historical `before` check and needs a separate composition revision.

```sh
python3 docs/android/evidence/lw-m7-37/composition-fifth-fixture/preflight.py \
  --handoff /path/to/this/handoff \
  --receipt-sha256 3c474cc04697fe72e79c7e62afe4a9cf0ef49f9f3992aaaf9cb8bb4f4f712393 \
  --source /explicit/source/tree --mode before
```

Use `--mode after` only to verify a separately authorized staging operation. This
helper never creates, replaces, installs or builds source. Its receipt pins every
output it consumes. Successful staging alone would still leave C++/IDL/Kotlin
compilation, nine cookie xpcshell cases and five FrameLoader instrumentation
methods pending. Full writer/cache admission and cleanup journal-success wiring
remain absent, as documented in `../native-implementation.md`.
