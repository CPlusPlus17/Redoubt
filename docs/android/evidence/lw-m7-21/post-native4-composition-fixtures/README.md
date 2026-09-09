# Four-test-overlay source composition snapshot

This handoff reconstructs Tasks31 → 29 → 35 → 36 in registry order on the
retained native4 + Task30 base, the four historical Kotlin compiler corrections,
and four subsequent test-only corrections. It is a local source composition
receipt. It does not execute target tests or establish acceptance of the new
native/API/UI implementation.

The input repository snapshot is `a883243b9eb1b9c82aa455e24a9e0adba2e98c0a`.
All 118 declared input files are hash/size checked. Of the earlier 105 pins,
eight changed: three test-corrected patches (14/20/23), Task36's matching
predecessor receipt, two Task35 ordering bindings from the Bundle correction,
and Task30's resource-checker documentation/code. Task30's source patch and
empty raw resource remain unchanged. The 13 additional pins bind the actual
compiled165 checkpoint and exact test-fixture evidence.

The captured APK compiler checkpoint `202a41bedcc148ef9faf7d2180eec463` has
compiler exit 0 and a subsequent resource-verifier failure. Its before/after
165-file checks bind manifest
`c53736e87152ba6de7ae232efd0a26197601027e4553be3f5f4bd7e6045601ae`.
That manifest is preserved verbatim. The test corrections are separate overlays;
this prior APK compiler result does not compile those unit-test fixtures.

The exact four test corrections produce expected current165 manifest
`46e33df9a7121a161af8e83151b44a2517b17d8609be59dc992e94e1335f4cbd`.
Their original bodies match the actual captured165 hashes, and all four corrected
bodies are independently derived from their registered full patches. The original
failed test reports remain separate. Root's subsequent target rerun is outside
this composition audit's execution scope.

## Result

- 83 materialized files; 230 total source bindings.
- All 79 bodies in the prior Bundle handoff remain byte-identical. Only four
  existing test-file rows change in the 230-file manifest.
- 32 source replacements, 43 creates and 8 retained inputs. The four test
  overlays must already match expected current165 before the proposed native
  source staging operation; `test-overlays.json` records their separate history.
- 147 unchanged native4 bodies remain manifest bindings rather than local
  materialized source. Verify them on the real staging tree before any mutation.
- 65 additional before/absence preflights are required: 22 existing bodies and
  43 absent paths, beyond the current165 manifest.
- All 13 generated Suggest resources and the exact empty Task30 raw resource
  are retained. Every standalone before/after hash and composed transition
  matches, with zero fuzz and zero composed offsets.
- Two independent fresh output directories yield byte-identical listed outputs.

Final230 manifest SHA:
`a5929163b40645d8aec27e071a3da73ccf974bd6e6843995c8b5555078b61f17`.
This remains a source plan, not a complete Gecko source archive or target result.

## Reproduce and retain

```sh
python3 audit.py --repo /path/to/checkout-a883243 --output /new/private/output
```

`audit-inputs.json` supplies default input pins. The command only reads its
repository and writes a new output directory outside it. It does not access a
VM, device, network, build or target runner.

`proposed-source-sha256.txt` binds the full union; `proposed-staging.json`
records every materialized path, its before/after hash, action and lineage.
`composed-source-subset.tar.gz` retains the 83 reconstructed bodies.
`revision-comparison.json` compares this result with the immutable earlier Bundle
handoff (receipt `f1d24854e0209646be0125dab6272a44ca07929da2d1792fe9b3b3eb4541b186`).
`repeat-check.json` records the independently repeated output hashes.

Keep this four-test-overlay snapshot immutable when adding any later test
correction. Future target test/native staging manifests must retain original
compiled evidence and bind the entire expected union; no source audit result is
substituted for target compilation, tests, persistence or browser behavior.
