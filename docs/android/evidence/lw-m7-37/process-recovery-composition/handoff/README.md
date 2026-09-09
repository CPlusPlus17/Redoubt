# Process-corrected source candidate with Task37

This local source-only composition applies the exact unchanged 15-path Task37 patch onto the retained process-corrected232 handoff. Run `python3 compose.py --repo /path/to/repository --output /new/private/output`. The six Task37 inputs are pinned in inputs.json; the complete parent handoff, including its independently reproducible historical232 audit, is retained in parent-handoff.tar.gz. No guest or build operations occur.

The union remains245 paths, with107 actual source bodies and138 unchanged native manifest-only bindings. All101 earlier materialized bodies are unchanged; only the six process-correction hashes differ from historical2459a911. The exact current167 parent is4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739. Staging requires200 existing hashes and45 absent paths to match before mutation. The new six bodies are retain-bound-input rows because they are already present in current167; they must never be applied as scoped20-only whole-file replacements.

Two fresh local executions produced byte-identical10 outputs. This is not target acceptance. All Task37 native compilation and cleanup runtime gates remain separate, and the full cleanup coordinator is still unfinished. Recovery tests and APK/runtime for corrected167 are separate receipts. The prior501d167 and9a911245 evidence remains immutable.
