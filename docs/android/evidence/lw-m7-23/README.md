# LW-M7-23 — normal/private cookie-banner controls

Implementation is ready for target integration; **this task is not complete**.
The isolated source tests do not establish that an Android control changes an
unlocked Gecko preference, that a content preference survives restart, or that a
real banner was refused. The target build, full Fenix gate, browser-engine-gecko
tests and installed-APK LW-M7-22 lifecycle/consent gates remain required.

## What changed

- Settings exposes independent normal and private Cookie Banner Blocker switches.
  Each maps to mode `0` (disabled) or `1` (reject only), never mode `2` (accept
  fallback). `Core` already passes both Settings getters to GeckoEngine on startup;
  the Settings listener also updates the corresponding engine setting immediately.
- Normal uses the new `pref_key_cookie_banner_normal_mode` key. Private retains
  `pref_key_cookie_banner_private_mode`. Absent keys default to true locally,
  independent of Nimbus's channel maps. Opening/inflating settings preserves
  stored true and false values. An old false seeded by XML cannot be distinguished
  from a user's false, so it is deliberately preserved; this is **not** a reset of
  existing profiles to new defaults.
- Both Trust Panel and legacy quick settings open the same domain dialog. The old
  private-only row is hidden to avoid duplicate entries; the old navigation
  destination remains as an adapter for restored navigation state.
- Site Off writes a disabled exception; On and Reset remove the exception and
  inherit the global rejection-only mode. Global Off disables domain changes and
  preserves exceptions. No switch or reset clears cookies, authentication, cache
  or other site data. The former `clearSiteData` implementation is removed even
  from the superseded controller.
- Storage set/remove now await their actual GeckoResult. The JS handler reports
  native errors with `onError` instead of leaving a result pending indefinitely.
  Reads and writes preserve the caller's Job and use a cancellable wait. Dialog
  operations have a ten-second bound; dismissal cancels waiting. Cancellation
  cannot undo a native write that was already dispatched, and the UI does not
  claim that it can. A late result cannot revive a cancelled wait or reload a new
  tab. Operations are serialized, recheck the captured tab/URL/private context,
  read back the applied mode, and expose failure instead of reporting success.

Acknowledgment here means that the native service call returned successfully.
`CookieBannerDomainPrefService::SetPref` uses the content-pref service asynchronously
for normal persistence; this patch does not add a SQLite fsync or promise immediate
force-stop durability. Restart persistence is a required installed-APK gate.

## Native private-session lifetime follow-up

The old native setter/remover had no active-context fence and can process teardown
inside `EnsureInitCompleted` before modifying the private map. Cancellation of a
Kotlin wait cannot undo a request that is already queued. The new private route
captures an immutable token, checks the original dialog/tab again after capture,
and sends the token to scoped native setters/removers. Those reject inactive or
stale tokens both before and after the nested initialization loop. Normal and
legacy unscoped APIs retain their signatures and behavior. Both global modes Off
shows disabled domain controls without requesting a token from the stopped service.

`CanonicalBrowsingContext::{DecreasePrivateCount,PrivateBrowsingSessionGeneration}`
advances the token generation at the actual private-context count's 1→0 boundary,
before observer dispatch, including `browser.privatebrowsing.autostart=true`.
The existing `last-pb-context-exited` notification keeps its autostart condition.
The separate `last-private-context-exited` notification expires only newly scoped
private entries. Both listeners preserve a current-generation scoped entry created
by an earlier teardown observer opening a replacement session. Unscoped temporary
and persistent-private entries retain their legacy cleanup rules. Native reads
also ignore stale scoped entries if an observer has not yet reached this service.
Observer registration failure prevents token issuance.

`test-native-fence.py` compiles and executes the actual C++ counter, accessor,
token helpers, observer bodies, and setter/remover prefixes through both lifetime
checks: **43 assertions pass**. Platform/IO/container boundaries are mocked and
normal setter/remover storage bodies are not compiled by this test. This is not
a native Gecko build or a substitute for target tests. Added Android xpcshell
contains five named tasks, including the actual held-init/nested-teardown and
earlier-observer replacement ordering, inactive and stale dispatch, normal/private
isolation, and autostart lifetime/legacy behavior. `CookieBannerPrivateSessionTest`
defines three GeckoView transport/context tests. Both target suites remain unrun.
The public Java methods are recorded in `mobile/android/geckoview/api.txt`; actual
API snapshot generation and target compilation remain required.

The dialog checks tab identity, URL and private state, not WindowGlobal identity:
a same-URL navigation is not a document identity fence. This is a domain setting;
a changed URL or tab is never reloaded, and a closed dialog cannot accept a newly
arriving token for a replacement session.

## Scope and source evidence

Gecko `nsCookieBannerService::{GetDomainPref,SetDomainPrefInternal,RemoveDomainPref}`
uses `Services.eTLD`/`GetBaseDomain`, not an exact-origin principal. The existing
`CookieBannerDomainPrefService` separates normal and private stores: normal writes
are persistent, ordinary private writes are temporary and clear on
`last-pb-context-exited`. The special persistent-private API is never used by these
controls. Scope is the registrable domain (eTLD+1), including subdomains and HTTP
and HTTPS, with separate normal/private choices. The dialog displays that scope
and the appropriate lifetime. IP addresses, public suffixes, internal pages,
unavailable native modes and changed tabs cannot produce a successful update.

The desktop counterpart in `browser/base/content/browser-siteProtections.js` also
uses `contentPrincipal.baseDomain` and the same service calls. Its private branch
explicitly avoids clearing normal data; Redoubt's new normal/private controls both
keep cleanup separate from changing the banner exception.

Frozen `lw/librewolf.cfg:173–174` contains
`defaultPref("cookiebanners.service.mode", 1)` and its private counterpart. The
`[ANDROID: LOCK]` comments do not constitute locking. This source inspection does
not replace measuring the effective pref and lock state while tapping each real
control. No config file, native rule loader, packaged rules snapshot, Remote
Settings allowlist, JS attachment blocker or Rust attachment blocker changes here.

`source-files.json` pins the exact before/after source bytes and the predecessor
patch hashes. `source-baseline.tar.gz` contains the frozen beta originals after
applying only the required, recorded `ubo-preinstall`, `privacy-defaults`, and
`canvas-webgl-permissions` hunks. The original frozen tree was read only. The
baseline commit is `fb1e2f2`; no guest files or release artifacts were changed.
The concept storage interface now carries the scoped storage contract; the
EngineSession enum remains the single additional read-only compilation input.
All 24 original before-hash entries are unchanged. Original receipts are preserved
byte-for-byte under `initial-a23461b/`. `followup-integration.json` records a separate
zero-fuzz composition of root LW-M7-20 Sync SettingsFragment hunks followed by
this patch; it does not rewrite that historical baseline.

## Reproducible local checks

```sh
python3 scripts/tests/test-cookie-banner-controls.py
python3 scripts/tests/test-cookie-banner-controls.py --kotlin-cache /path/to/gradle-home/caches/modules-2/files-2.1
python3 docs/android/board.py --check
```

The first command validates archived hashes, reapplies the patch with zero fuzz
and zero offset, checks the parsed XML/routes/scope labels and executes **19 tests
against the actual GeckoView module event handler**. Only platform/native service
boundaries are mocked. Those tests require one terminal callback on success,
native failure and invalid URI, preserve normal/private flags, verify global
fallback behavior, and reject any site-data clearing call.

The optional cache argument performs no download. It compiles the actual
`CookieBannerSiteController.kt` and its checked-in `CookieBannerSiteControllerTest`
with Kotlin 2.3.21 and `-Werror`, using the actual concept storage interface and
verbatim mode enum (the unrelated EngineSession body is omitted). **All 16 JUnit
tests pass**: normal/private mutations, no persistent-private call, global-Off
preservation, pending acknowledgment, failure, cancellation/late completion,
stale navigation, unexpected/absent modes, readback mismatch and concurrent
Off/Reset serialization, late private-token capture, inactive-session failure and
normal-mode capture isolation. Android views and native storage are not included in
this standalone compilation. The exact replay and output are in `source-tests.txt`.

Target test definitions additionally cover five Fenix default/XML/inflation and
engine-listener cases, seven new GeckoResult acknowledgment/token/cancellation cases,
and the replacement of the old private-only row. The old controller test now
asserts no engine use when changing a banner exception. These target tests have
**not** been run in this worktree.

Board check: 106 tasks, 25 waves, zero warnings. Patch scope lint passes.
The recorded global scope/count and order checks remain pending root integration:
this branch adds one Android patch (32→33 and 92→93 in this isolated base), and ten
new shared-file pairs require classification in the root-owned checker. See
`integration-checks.json` and individual receipts. The required new ordering is
`canvas-webgl-permissions.patch` before `cookie-banner-controls.patch`: the new
routes use its permissions container/callback and the strings append after its
block. Its new Java API snapshot and startup event registration also compose
after that predecessor. LW-M7-20 adds a further disjoint SettingsFragment pairing
in the root tree; its measured composition is in `followup-integration.json`.
Other shared pairs edit disjoint feature regions: no-adjust, no-crashreporter,
no-gms, no-onboarding, no-suggest, privacy-defaults, search-config, ubo-preinstall,
and update-check. Root owns the final combined order/count update.

## Installed-APK routes and remaining acceptance

Global preference titles:

- `Cookie Banner Blocker in normal browsing`
- `Cookie Banner Blocker in private browsing`

Both site panels expose `cookie_banner_site_controls`. The dialog exports
`cookie_banner_site_switch`, `cookie_banner_site_reset`, `cookie_banner_site_status`
and `cookie_banner_site_scope`. The last identifies the actual registrable domain,
HTTP/HTTPS and normal/private lifetime. The old navigation destination
`CookieBannerPanelDialogFragment` opens this same dialog.

LW-M7-22 must use an HTTP/HTTPS fixture with a registrable domain, such as the
controlled mapped `duh.de` fixture; `localhost`/IP is not suitable for domain
exceptions. Required checks include real global Off/On with effective Gecko mode
and lock state, normal exception restart persistence, subdomain/scheme scope,
normal/private isolation, last-private-context expiry, Off/On/Reset cookie
retention, and rejection/no-acceptance callbacks from the actual native banner
implementation. Banner disappearance alone must never count as refusal. The
runner owns fixture-only page data and must not write preferences, domain stores
or retry counters to obtain a pass.
