# Root replay

Root independently reconstructed all212 current inputs from the declared Git
revision, replayed all151 historical inputs and19 outputs, and reproduced all14
new outputs byte for byte. `root-verification.json` records the comparison.
`frozen-repository-inputs.tar.gz` retains the complete212-file current input set,
so mutable working-tree receipts are not needed to recover this snapshot. The
historical c7a8 Git objects are still needed by `compose.py` for its explicit
historical replay. No guest source staging or target verdict is recorded here.
