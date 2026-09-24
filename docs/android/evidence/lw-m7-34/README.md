# LW-M7-34 — original uBO update fixtures

**Original files prepared and verified offline; real update acceptance remains pending.** No Gecko signature check, Gecko version comparison, APK install, add-on install, VM action or device action was performed by this task.

| Fixture | Original AMO version/file | Bytes | SHA256 |
| --- | --- | ---: | --- |
| 1.73.0 | [6396396 / 4940584](https://addons.mozilla.org/api/v5/addons/addon/ublock-origin/versions/6396396/) | 4,679,419 | `bccc51a773150af4af6e1fd62c7bfdeb7238b79ff2381b998fa9f2e38f64786a` |
| 1.74.0 | [6437252 / 4981431](https://addons.mozilla.org/api/v5/addons/addon/ublock-origin/versions/6437252/) | 4,617,614 | `175756d74468c9ba45863f7fc333d3be670f82d5b066314e915814dd547d1652` |

The retained XPIs are unchanged response bodies from the original [1.73.0 download](https://addons.mozilla.org/firefox/downloads/file/4940584/ublock_origin-1.73.0.xpi) and [1.74.0 download](https://addons.mozilla.org/firefox/downloads/file/4981431/ublock_origin-1.74.0.xpi). Each has its original per-version JSON response and a separate transport receipt with the URL, HTTP result, timestamp, body hash and size. Downloads used urllib's ordinary TLS certificate verification. Original files are never rewritten by the helper. The web tool refused the API URL, so the successful direct HTTPS API responses were retained with urllib.

Both original manifests declare ID `uBlock0@raymondhill.net`, manifest version 2, Firefox minimum 115.0 and Android minimum 115.0. Both original AMO responses list Firefox and Android compatibility from 115.0 through `*`. Version 1.74.0 matches the entire relevant packaged pin in `assets/ubo-extension.json`, including URL/hash/size/Android minimum. Their required/optional/host permission arrays are identical. This pair therefore does not provide permission-increase update coverage.

Both contain the exact LW-M7-28 parser input `/banner_ads/*$~xmlhttprequest,domain=~clickbd.com` at line 346 of `assets/thirdparties/easylist/easylist.txt`. `inspection.json` records each original filter member's size and hash, manifest fields/hash, ZIP integrity and signature-member hashes. Filter files are inspected inside the XPIs instead of duplicating another 4 MB in evidence.

ZIP signature members, HTTPS download provenance, matching metadata and file hashes are **not Gecko `signedState` verification**. The original API field `is_mozilla_signed_extension` is retained as returned (false in both responses); this helper does not use it as a Gecko signature verdict. The real target must accept the ordinary signed extension with signature enforcement enabled, and report its actual signed state.

Verify the retained originals without network or writes:

```sh
python3 docs/android/evidence/lw-m7-34/fixtures.py
```

Explicitly fetch missing originals from the fixed URLs, then verify:

```sh
python3 docs/android/evidence/lw-m7-34/fixtures.py --fetch
```

Only `--fetch` permits network. It uses bounded reads, HTTPS and a narrow Mozilla host allowlist; it does not replace an existing original or silently change pins. `--write-receipt` explicitly regenerates the derived `inspection.json`; it never rewrites an XPI or original AMO response. `fixture-pins.json` holds the expected original hashes. The verifier checks original transport receipts, metadata/file IDs, public/listed status, manifest identity and Android minimum, unique ZIP entries/CRC, actual filter input and the current packaged pin/parser constants. A mismatch or missing file exits with failure. `FIXTURES_VERIFIED_TARGET_PENDING` means fixture preparation only.

`file-picker-checklist.md` gives the actual About-wordmark → Settings → document-picker route, signed-state/comparator observations, version transition, preserved user choices and restart/parser evidence requirements. `observe-installed.js` is a read-only target observation body for the existing chrome Marionette transport; it has not been executed here. `source-bindings.json` binds the actual source opened for those controls. Use the checklist on a dedicated root-managed profile with the source-bound candidate; do not edit preferences, reinstall stamps, manifests, signing state or update URLs to obtain a result.

The archived payload is about 9.4 MB. It contains no fixture signing key, modified XPI, build artifact or device report. Periodic update scheduling, permission-increase prompts and signed-update acceptance remain distinct pending work even after these files are prepared.
