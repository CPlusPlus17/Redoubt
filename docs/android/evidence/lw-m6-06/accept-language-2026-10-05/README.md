# Update check: no Accept-Language (2026-10-05)

**Finding** (157.0-2 device acceptance, CI run 37248744119,
`docs/android/evidence/lw-m7-01/release-157.0-2/acceptance/run-37248744119/update-check/device-local/server-requests.jsonl`):
both update-check requests carried `Accept-Language: en-US`, the user's locale. Gecko adds it
by default to every HTTP channel. DISTRIBUTION.md said "no locale". The value differs between
users, so the header said something about who was asking.

**Change** (`patches/android/update-check.patch`): `UpdateChecker.REQUEST_HEADERS` is
`User-Agent: Redoubt-UpdateCheck/1`, `Accept-Language: ""` and `Accept: ""`. With Gecko 157, an
empty value removes the header. The path, checked in a patched 157 tree:

1. `GeckoViewFetchClient.toWebRequest` passes each header to `WebRequest.Builder.addHeader`.
   `WebMessage` stores the empty value as it is (`TreeMap`, no filtering).
2. `widget/android/WebExecutorSupport.cpp` `SetupHttpChannel` calls
   `nsIHttpChannel::SetRequestHeader(key, value, false)`.
3. `HttpBaseChannel::SetRequestHeaderInternal` goes to `nsHttpHeaderArray::SetHeader`. For an
   empty value with merge off, that removes the existing entry (`nsHttpHeaderArray.cpp:51-64`).
4. The defaults were added before step 2. `NS_NewChannel` runs `HttpBaseChannel::Init`, which
   calls `nsHttpHandler::AddStandardRequestHeaders` (`Accept`, `Accept-Language`,
   `Accept-Encoding`, `User-Agent`). `Accept-Language` is set only there
   (`nsHttpHandler.cpp:785-805`). Nothing in `netwerk/protocol/http` sets it again.

Some headers are added after the caller's headers, so this method cannot remove them. All of
them are the same on every install of a build:

- `Sec-GPC: 1` is set by `nsHttpChannel::SetGlobalPrivacyControl` at connect time
  (`nsHttpChannel.cpp:8130`).
- `Sec-Fetch-*` is set by `SecFetch::AddSecFetchHeader` in `AsyncOpen`.
- The rest are `Priority`, `Pragma` and `Cache-Control: no-cache` (from `useCaches = false`),
  `Connection` and `Host`.

`Accept-Encoding` is not removed either. `nsHttpHandler::AddAcceptAndDictionaryHeaders` can set
it again when a compression dictionary matches, so a test could not pin its removal. Its value
depends only on the Gecko build. `Accept` is removed only because nothing needs it. Its value is
the constant `*/*`.

`UpdateCheckerTest` changes:

- The exact header list is pinned.
- A new test, `the request sends no Accept-Language, so not the user's locale`, models the
  rule from steps 3 and 4. It starts from Gecko's defaults with a non-English locale, applies
  the caller's headers, and asserts that `Accept-Language` and `Accept` do not reach the wire.

## Runs

| File | What | Result |
| --- | --- | --- |
| `check-patchfail-android-157.txt` | `./scripts/check-patchfail.sh --targets=android` against `firefox-157.0.source.tar.xz` | exit 0, no reject; `update-check.patch` applies with no fuzz or offset |
| `lint-and-order.txt` | `scripts/lint-patch-scope.py`, `scripts/check-patch-order.py` | both exit 0 |
| `jvm-harness-157-tree.txt` | `scripts/tests/test-update-check-jvm.sh`; concept-fetch sources from the patched 157 tree, Kotlin 2.4.0, android-37.1 `android.jar`, `librewolf-android-build:fx157` image, `--network=none` | `UpdateCheck.kt` compiles with `-Werror`; 12/12 `UpdateCheckerTest`; 14/14 cross-checks |
| `jvm-harness-negative-control.txt` | the same harness on this patch with only the `headers =` line put back to `MutableHeaders("User-Agent" to USER_AGENT)` (157.0-2's request) | exit 2; both header tests fail, and the new one prints `Accept-Language reaches the wire` |
| `robolectric-158-tree.txt`, `junit-xml/`, `robolectric-run.sh` | `./mach gradle :fenix:testDebugUnitTest --tests 'org.mozilla.fenix.lw.*' --tests org.mozilla.fenix.settings.SettingsFragmentTest` | `:fenix:compileDebugKotlin` and `:fenix:compileDebugUnitTestKotlin` pass (`-Werror`); `UpdateCheckerTest` 12/12, `UpdateCheckSwitchTest` 4/4, `DohProviderMigrationTest` 9/9, `SettingsFragmentTest` 25/25; 0 failures |

**Limits.** The Robolectric run used the same method as
`../switch-fix-2026-10-05/README.md`:

- It ran on the Firefox **158** working tree (`ff158/work/buildrepo/librewolf-158.0-1`) and
  the `apk3` Gradle output, in the `fx158` image. Tree, output and mozbuild state were mounted
  as overlays (`podman -v …:O`), so none of them was modified.
- `robolectric-run.sh` reverse-applies the old `SettingsFragment.kt` and `preferences.xml`
  hunks of `update-check.patch` (at `0ef74fad`, the version that tree carries). It then
  applies this patch's hunks for those two files and writes this patch's four new files.

The Gecko side (steps 1 to 4) was read in the source, not run. These tests use a fake `Client`,
so they prove what `UpdateChecker` asks for. They do not prove what Gecko sends. The measurement
of what a device puts on the wire is the request log of an acceptance probe against a local
server, as in the 157.0-2 run above. That log should show no `Accept-Language` and no `Accept`
on the next build.
