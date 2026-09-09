# Five-test-overlay source composition snapshot

This local audit reconstructs Tasks31 → 29 → 35 → 36 in registry order on the
retained native4 + Task30 base, four historical Kotlin compiler corrections,
and five later test-only corrections. It does not build or run target tests.

The frozen repository input is `499f4e0438b0b1cbf315a6b72138aa2aff5bdbbb`.
All 122 declared input files are checked by size and SHA-256. Compared with the
previous 118-file snapshot, four existing pins changed: current Task14 patch,
Task36's matching predecessor receipt, and two Task35 ordering receipts refreshed
for the four-fixture stage. Four added files bind the fifth test correction.
`input-revision.json` retains these exact changes.

The Task35 ordering receipts in this snapshot retain the prior A8 Task14 digest.
They are historical inputs, not a claim of a refreshed B10 full-patch ordering
receipt. Source composition applies current B10 scoped sections directly and
checks every Task35 and Task36 before/after source hash. The Task36 followup
separately proves the B10 change touches only one test-file patch section.

The actual completed APK compiler checkpoint `202a41bedcc148ef9faf7d2180eec463`
is bound to the preserved165 manifest
`c53736e87152ba6de7ae232efd0a26197601027e4553be3f5f4bd7e6045601ae`.
Its archived build exit is explicitly checked as zero. This checkpoint's later
resource-verifier failure remains recorded; it is not a result for the later
unit-test corrections or the new native/API/UI composition.

The four-fixture parent manifest remains preserved separately:
`46e33df9a7121a161af8e83151b44a2517b17d8609be59dc992e94e1335f4cbd`.
The fifth overlay adds only an `ExperimentalCoroutinesApi` import and a class
`OptIn` annotation to `OriginBoundPermissionsFeatureTest.kt`. All eight authored
tests and their assertions remain identical. Original and final bytes are checked
against the correction receipt, and all five final test bodies are independently
derived from their registered full patches.

Expected current165 with all five fixtures:
`659bf836ec885425b596bf077236190e8df30b2285df625ff3988c5dc93129b6`.
Target test results for this manifest must be retained separately. The parent's
four-fixture target run is not promoted into a five-fixture test verdict.

## Result

- 84 materialized source files; 230 total bindings.
- All 83 prior materialized bodies remain byte-identical. Only the fifth test
  file's existing row changes in the230 manifest.
- 32 replacements, 43 creates and 9 retained inputs. The five test overlays
  must already match expected current165 before the proposed native staging.
- 146 unchanged native4 bodies remain compiled manifest bindings; their bytes
  require a live preflight before staging.
- 65 additional preflights: 22 existing body hashes and 43 absent paths.
- All 13 generated Suggest resources and Task30's exact empty raw resource are
  preserved. Every standalone and composed transition matches with zero fuzz
  and zero composed offsets.
- Two fresh output directories yield byte-identical listed outputs.

Final230 manifest: `7af4e037a693c46a86403d1d4bf31df66b81891c4a3857a73d222ca66fff597b`.
Archive of84 materialized bodies: `15eaae9fc0b9b0a3edaa94eeafb879da018c9017646ee3296cf1b732de630175`.
This is a source plan, not a complete source tree or target acceptance.

## Reproduce and retain

```sh
python3 audit.py --repo /path/to/checkout-499f4e0 --output /new/private/output
```

The command reads the repository and writes only the new external output
directory. It does not use the VM, device, network, build or target runner.
`proposed-staging.json` binds before/after hashes and actions for every materialized
path; `proposed-source-sha256.txt` binds the full union. `revision-comparison.json`
compares the preserved four-fixture snapshot, receipt
`e9c71b5cb207b845dd3e468749babb2b1ad87aaf3db1be5f6c66a1be7b6a9100`.
Keep all historical native, compiler and test captures and both composition
handoffs unchanged when integrating later source or target evidence.
