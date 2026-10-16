# Gates on the merge e2e41245 (before the push to main)

Run in a temporary worktree at the signed `--no-ff` merge of `fix/drm-api31-33` (c57d7ba1, which also
carries the review fixes: the item 7 header wording and the evidence README) onto main `d76fcf19`.

| check | result |
| --- | --- |
| `check-patchfail.sh --targets=android` / `--targets=desktop` | exit 0 / 0; 73 / 66 patches (`patchfail-*.out.gz`) |
| `check-patch-order.py`, `lint-patch-scope.py` | ok: 40/40 constraints, 183 pairs; OK, 118 patch files |
| `board.py --check`, `--check-scope`, `--check-cfg-split`, `--diff-mozconfig --strict` | ok (137 tasks; 117 listed patch files; cfg regenerates; 0 differences) |
| `site-check.py site` | PASS, 10 pages |
| `scripts/tests/` | all exit 0 except `test-android-signing.py`, `test-android-version-code.py` and `test-update-check-jvm.sh`, which need a built APK, Gradle classes or a tree, as on main before; `test-android-signing.py` against this build's x86_64 APK: 29 tests OK |

`actionlint` is not installed on this host; the merge changes no workflow or script.
