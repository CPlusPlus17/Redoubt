# Corrected current167 and proposed232 source plan

This audit preserves the original native164, compiled APK165, failed APK/test
captures and five-fixture165 plan. It derives initial167 from the actual captured
165 plus the HomeActivity routing correction, Cookie settings reload fixture,
startup metrics fixture and new four-case Home test. It then applies the separate
navigation fixture correction, preserving initial167 `f55095bfee92ddfac6f480c9cdef29bbb20acc67377130233e52b765bcbd4f9a`.

Final current167 is `501d04614edbc847b416cd5b6f1dac42dd0728a63125a3d9902c90d07a579c8b`.
This is an expected source manifest, not a target test result. The production
HomeActivity correction requires a new APK; fixture results remain separate.

The exact input repository snapshot is `c7a8b6938837ad5f72ae70994fb28c3cb12c4d14` with151
size/hash-bound repository inputs. Task20's routing9f → GNU-format28 → final
navigation-fixtureAC0 patch history is retained explicitly. Both full current20
(24files) and current26 (21files) reconstruct their exact source hashes. The
31 → 29 → 35 → 36 candidate then replays in registry order with zero fuzz and
zero composed offsets. Current35/36/26 dependency receipts are included.

Results:232 full source bindings,88 materialized bodies; all84 previous materialized
bodies are unchanged. Exactly four source rows differ or are added versus230.
There are32 proposed replacements,43 creates and13 retained materialized inputs
relative to the final current167 base. All13 generated Suggest resources and
Task30's empty raw seed are preserved.144 unchanged native bindings remain
manifest-only and require live verification;65 additional before/absence checks
are required beyond current167. This is not a complete Gecko source tree.

The old GNU dry-run failure in Task20 was found against exact before bytes;
the owner retained it and corrected patch context without changing production
source. This final audit uses AC0 and does not normalize or bypass patch content.

Final232 manifest: `d25b091510a518b620d17ce7f5060941e9ba54bd6c6b614620d1bd1e3f4bed15`.
88-body archive: `648305b2cad064dcc1d16008dbe8d8649eb9aa15c80d150960d3d8f9490887ce`.
All19 top-level replay outputs match in two fresh final directories.
The initial four-source correction and later navigation fixture have distinct
records in `third-target-overlays.json`; the earlier five fixtures remain in
`test-overlays.json`. `revision-comparison.json` compares the immutable230/84
handoff. All prior native, compiler and test captures remain historical.

Reproduce:

```sh
python3 audit.py --repo /path/to/checkout-c7a8b69 --output /new/private/output
```

The command reads repository inputs and writes only the new external output.
No VM, device, network, target build or tests are accessed. The separate Task37
increment must be applied in a separate reviewed245 composition; its historical
243 plan is not relabelled as current. No runtime or native acceptance is inferred.
