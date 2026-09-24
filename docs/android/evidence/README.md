# Evidence

The measurements behind this project's claims, harvested 2026-08-22 from the
per-task working directories (`~/lw-*/evidence/`) before those directories were
deleted to reclaim ~773 GB.

**Why this is in the repository.** `HANDOVER.md` §7 flagged that claims like
"provably zero-GMS" had no durable citation anywhere in the repo — the proof
existed only as files on one machine, inside directories that looked like
disposable build trees. A `make clean` or a full disk would have taken them.
90 MB of evidence was sitting inside ~773 GB of regenerable containers.

Each subdirectory is named for the task that produced it.

| directory | what it proves |
|---|---|
| `lw-m2-04/` | the APK runs *our* GeckoView — build config screenshots, `omni.ja` inspection |
| `lw-m3-09/` | pref state before/after, `prefs-all.json` pairs |
| `lw-m4-05/` | GMS/Play Integrity removal |
| `lw-m4-09/` | **`release-r8-crash.logcat`** — the only record of the R8 boot failure (LW-M6-07) |
| `lw-m4-14/` | the three Gradle unit-test runs: main-only, full-patch, reverse-applied |
| `lw-m4-15/` | toolkit Nimbus patch |
| `lw-m4-16/` | the 63,646-class dexdump analysis behind the GMS string count |
| `lw-m6-07/` | the R8 fix: boot, page load, smoke suite against the release APK |

## What was changed in harvesting

- Files over 2 MB are **gzipped**. Gradle logs compress ~20:1; the set went
  from 90 MB to 13 MB.
- Two binary artefacts were **excluded** rather than committed — 33 MB of
  `.zip` that git would carry forever. They were negative controls for
  LW-M4-16, rebuildable from the recorded inputs. Their hashes, so the claim
  stays checkable if a copy resurfaces:

      ed5e859b99feb20e5d30d5192d2536035edd797b3bee4f737fe2306804b6822c  neg-reader.zip
      3dea9c7ae39e9b19b11adaac0762beb6b93a262256277592da46bc640f1d1f39  neg-literal.zip

Nothing else was filtered. Directory structure and filenames are unchanged.

## Reading this critically

These files are evidence, not conclusions, and several of the conclusions
originally drawn from them were **wrong** — see `HANDOVER.md` §9. In particular
the LW-M4-16 dexdump was used to call an artefact "provably zero-GMS" when the
strings were absent because R8 had deleted the classes from a build that could
not boot. The measurement was accurate; the inference was not.

Check what build a file came from before citing it. Several artefacts here
predate both the R8 fix (LW-M6-07) and the cfg-loading fix (LW-M3-11), so they
describe builds that either would not boot or never applied the privacy
configuration.
