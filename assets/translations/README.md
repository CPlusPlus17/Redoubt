# Reviewed Android translation inputs

`catalog.json` is the complete pinned v2 metadata snapshot; model attachments
are fetched only by explicit operations and checked against its pins.
`bergamot-translator.wasm.zst` is the unmodified WASM 4.0 attachment, verified in
both compressed and expanded forms. Builds stage these checked-in inputs
without network access using `scripts/package-translation-assets.py`.

[provenance.json](provenance.json) records exact origin URLs, collection receipts,
hashes, sizes and license sources. Mozilla identifies both the WASM and released
generation 3 model weights as MPL-2.0; the model records omit a license field, so
the provenance links the maintainer's explicit clarification. The source for the
bundled WASM is [Mozilla translations revision 1de4a085](https://github.com/mozilla/translations/tree/1de4a085d3a7afb625c51a60aabb5ad298e4059f).

Refresh only through a reviewed application change that updates the complete
catalog, pins, compatibility and behavior evidence. See
[the implementation receipt](../../docs/android/evidence/lw-m7-16/README.md).
