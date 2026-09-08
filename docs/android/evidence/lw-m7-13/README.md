# LW-M7-13: verified offline cookie-banner rules

Implementation and source tests recorded on 2026-09-09, based on repository
`982a3fb` and the immutable `librewolf-153.0esr-1-beta-20260908` source tree.
This is an integration handoff, **not completion of the task's APK and runtime
acceptance criteria**. No build tree, guest, installed app or frozen beta file
was changed by this work.

## Change and provenance

The Android production `CookieBannerListService` reads a fixed application
resource, verifies its byte count and SHA256, validates the entire collection,
then imports rules through the existing service implementation. It does not
construct a cookie Remote Settings client, register its sync listener, or call
its `get` method. Both Remote Settings collection allowlists and all network
blockers remain unchanged. Desktop retains the Remote Settings path.

The source's existing snapshot is packaged without changing one byte:

| Property | Pinned value |
| --- | --- |
| Source file | `services/settings/dumps/main/cookie-banner-rules-list.json` |
| Application resource | `resource://app/defaults/settings/main/cookie-banner-rules-list.json` |
| Byte count | 262208 |
| SHA256 | `0ddab9560f17710fa1613825b1b8be0e190107dd679e2cd53c5a1822524958fd` |
| Collection timestamp | `1725526980846` (`2024-09-05T09:03:00.846Z`) |
| Records | 558 unique IDs; 1601 domain entries; 9 global rules |

The [preceding data audit](../lw-m7-08/translation-cookie-data-audit.md#official-endpoint-reads-made-for-this-audit)
records a complete HTTP 200 read of the [official collection](https://firefox.settings.services.mozilla.com/v1/buckets/main/collections/cookie-banner-rules-list/records?_limit=1000),
with the same ETag, 558 records and no next page. Its canonical data-array hash
matched the source snapshot:
`ffd2c6142052af84b4d0d23e4d8ef5f3d6a8399f13f155417316677df7efe02e`.
That observation establishes source/endpoint parity at audit time; it is not a
new Remote Settings signature verification. Future updates require reviewing
and repinning a complete snapshot in an application release; builds and apps
must not fetch an unpinned replacement.

Only known transport metadata (`schema` and `last_modified`) is removed before
validation by Gecko's existing JSON schema. Unknown top-level rule fields reach
the validator and fail. All records are validated before any insertion; duplicate
or empty IDs, invalid metadata and unsupported nonempty targeting expressions
also fail. Existing schema permissiveness inside nested objects is unchanged.
The actionless `disabled` rule and all global rules are retained: deleting them
could change domain handling or allow global rules on deliberately excluded
sites. Snapshot integrity protects the exact reviewed values, beyond the schema's
structural checks.

Three source files change: the production loader, the Android packaging list,
and the existing xpcshell test. The fourth owned source path, the snapshot,
is intentionally unchanged. `SharedUtils.checkContentHash` supplies the existing
pure integrity helper; importing it does not create a Remote Settings client.
[source-files.json](source-files.json) pins before/after bytes of all eight
source dependencies. [source-baseline.tar.gz](source-baseline.tar.gz) contains
the originals, including the unchanged snapshot, real schema validator and its
license, so the source test is replayable without another Firefox checkout.

## Tests performed

[source-tests.log](source-tests.log) records **23 passing tests executing the
actual patched JavaScript**, Gecko's actual hash utility and vendored schema
validator. Gecko module/platform boundaries and native cookie objects are faked;
these tests do not execute Gecko's cookie injector or page actors.

Coverage includes missing/unreadable/truncated/same-size-corrupt data; schema,
metadata, envelope, targeting and duplicate failures; complete 558-rule import;
normal-only/private-only/both-disabled modes; interrupted and overlapping loads;
shutdown/reinitialization; existing test-pref overrides and validation; observer
deduplication; and the unchanged desktop import/sync/conversion path. Android
fixtures assert zero cookie Remote Settings construction/get/subscription calls.
The packaging test executes the actual `moz.build` with its output DSL mocked:
Android adds exactly one snapshot, while desktop/iOS outputs are identical.

The existing xpcshell test gains Android packaged-data and override cases.
Only the four Remote Settings-specific cases are desktop-only; the generic
test-pref case still runs on Android using its existing skip-source override.
Both production and xpcshell JavaScript pass Node syntax checking. **The new
xpcshell cases have not yet run in Gecko.** No production test-only API was added.

Replay from repository root, with Python 3, Node and `patch` available:

```sh
python3 scripts/tests/test-cookie-banner-snapshot.py
python3 scripts/tests/test-cookie-banner-snapshot.py --source /path/to/patched/gecko
python3 scripts/tests/test-cookie-banner-snapshot.py --apk /path/to/candidate.apk
```

The default run verifies the archived originals, applies the patch with zero
fuzz and no offsets, checks all resulting source hashes, validates packaging
and the snapshot, and runs the 23 source tests. `--apk` additionally checks
the exact snapshot, production module and schema inside `assets/omni.ja`, then
prints the APK hash. It has not yet been run against a newly built candidate.

[integration-checks.json](integration-checks.json) binds the checks to patch
SHA256 `c7265a76ace9371f7f6333a6ca12584fe45424a77d7dea659828c53abb7044b5`:
board validation, patch order, scope lint, and a zero-fuzz/no-offset dry run
against the immutable beta source pass. `board.py --check-scope` reports only
the expected root-owned `PATCH-SCOPE.md` count update (29→30 Android patches,
89→90 total). Root will update that document during integration. The new patch
shares `moz.build` only with desktop-only `add-mojeek`, so there is no newly
co-applied shared-file ordering edge.

## Remaining acceptance and runtime requirements

| Task criterion | Evidence now | Required before completion |
| --- | --- | --- |
| Exact APK data, import without cookie traffic | Source pin, Android packaging evaluation, no-client source tests | Build; `--apk`; fresh-profile actual service rule inventory; capture with a working allowed network control |
| Bad data cannot initialize successfully | Actual JS `init()` rejection with zero imported rules/observers for missing or corrupt input | Gecko/xpcshell execution and packaged resource load |
| Real supported rejection or opt-out action | Existing import conversions exercised | Page callback/request or cookie proof through native actors/injector |
| Accept-only, existing consent, domain exceptions | Existing rejection-only native implementation unchanged | Actual page/cookie and exception controls |
| Normal/private lifecycle and allowed control | Actual JS lifecycle tests | Actual normal/private browsing, disable/re-enable, restart and private-session teardown |

Native `nsCookieBannerService::Init` sets `mIsInitialized` before asynchronously
loading the list. Its `isEnabled` property is therefore **not a data-readiness
assertion**. Runtime inventory must await the pre-existing list service
`initForTest()` promise and inspect loaded rules; a true mode/isEnabled value
alone cannot establish successful loading. Missing data rejects that promise;
the native readiness contract was not expanded by this patch.

Required harness/fixture work for the integration owner:

1. Run the target's xpcshell test
   `toolkit/components/cookiebanners/test/unit/test_cookiebannerlistservice.js`
   in its supported Gecko environment, build the APK, and run the existing
   Android smoke and preference gates. Bind every runtime result to APK and
   module hashes. Confirm production `testRules` and `testSkipRemoteSettings`
   overrides are unset. The global-rule pref must be recorded, not silently
   enabled by the harness (its source default is true).
2. Serve a controlled page using a **real packaged global rule**: for example
   `#CybotCookiebotDialog` containing reject button
   `#CybotCookiebotDialogBodyButtonDecline` and accept button
   `#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll`. Each button must
   independently record an action/cookie and send a fixture request. Assert
   reject=1 and accept=0. A hidden banner alone is not a pass, especially with
   uBlock Origin installed. The page needs no production test-rule injection.
3. Use an accept-only packaged global rule, e.g. `div#didomi-host` with
   `button#didomi-notice-agree-button`; assert no acceptance in mode 1. Confirm
   the button and endpoint work with a separate explicit manual/automation
   click after the protected window. Test domain exceptions and preexisting
   consent with separate asserted state. The cookie-injector path additionally
   needs an actual domain-rule fixture, such as a controlled `duh.de` host
   mapping and matching origin, to prove `cookie_dismiss=true`; merely querying
   rules for that URI is only an inventory test.
4. Repeat relevant checks in normal and private browsing, disable both modes
   then re-enable, close the last private session, and restart. Keep packet
   capture alongside a successful allowed request. Attribute the forbidden
   cookie collection claim using its path/client evidence; allowed security
   Remote Settings traffic on the same hostname is not a cookie-traffic failure.

These runtime fixtures and smoke-harness paths were not delegated to LW-M7-13;
no changes outside this task's owned paths were made.
