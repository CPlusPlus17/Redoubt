# Cookie settings reload fixture correction

The actual third target run fails all five `CookieBannerSettingsTest` methods
inside `setUp`, before any test body. The retained XML points to line55 and
`ReloadUrlUseCase.invoke$default` line163. Kotlin evaluates the omitted `tabId`
argument by reading `store.state.selectedTabId`; the recursively mocked use case
has no constructed private store. Stubbing the no-argument invocation therefore
fails before MockK records the intended call.

The fixture now supplies one real `BrowserStore()` to both `core.store` and a
real `SessionUseCases(store)`. This replaces the nested translation-state mock
and the no-argument reload stub. The valid initial browsing state has no selected
tab; the production reload default reads that state and returns normally. No
store mock, fabricated reload success or production change is introduced.
All five existing test bodies and assertions remain byte-identical.

`source-overlay.json` binds the actual five-fixture165 parent, old and new full
cookie patches, original and corrected test bytes, and the inspected source.
`original-source-sha256.txt` preserves the real target manifest. The failing XML
and original full Task23 source receipt are retained. `SessionUseCases.kt` was
read from the actual target capture; `BrowserStore.kt` was inspected in the
frozen host source and is explicitly labelled as such.

Run:

```sh
python3 docs/android/evidence/lw-m7-21/cookie-settings-reload-correction/verify-source.py
```

This reconstructs both complete37-file Task23 outputs with zero fuzz and offsets,
checks that exactly one test patch section changed, verifies the five unchanged
test bodies and binds the original setup failures. It does not run the corrected
Robolectric class. Root must execute the full target suite before accepting the
fixture correction; no allowlist or required class gate is relaxed.
