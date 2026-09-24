# Cookie runtime harness source contracts

Read-only source audit for LW-M7-22. These are source findings, not evidence that
an installed release has executed them. `source-inputs.json` records exact file
hashes and distinguishes the frozen tree from the generated LW-M7-23 candidate.

The frozen tree is `/home/mgysin/Documents/librewolf/librewolf-153.0esr-1-beta-20260908`.
The controls candidate is `/home/mgysin/redoubt-artifacts/feature-parity/lw-m7-23/after`,
commit `a23461b`, patch SHA256
`be33b14682940c88a86bb4c4f375d358b0c40068db4336c24514f984aca9e8e7`.

| Opened source | Contract used by the harness |
|---|---|
| `services/settings/dumps/main/cookie-banner-rules-list.json` | 558 unique rule IDs; nine global rules. Exact Cookiebot reject/accept selectors, accept-only Didomi and the real `duh.de` opt-out cookie rule are pinned. The runtime reads the packaged resource and native rules independently. |
| `toolkit/components/cookiebanners/CookieBannerChild.sys.mjs` | A real document triggers the native actor after DOMContentLoaded; matching buttons receive an actual click. A completed attempt can consume the per-site budget even when no banner matches. The fixture markup and listeners exist during parser execution. |
| `toolkit/components/cookiebanners/CookieBannerParent.sys.mjs` | Effective normal/private modes and domain exceptions determine rule selection. Global rules are a fallback to domain rules. The per-site/session attempt limit means a missing later callback can be cooldown, so the runner uses actual process or private-session lifetimes. |
| `toolkit/components/cookiebanners/nsCookieBannerService.cpp` | `GetDomainPref` checks initialization and calls effective-TLD `GetBaseDomain`; missing records return `MODE_UNSET` (3). Exceptions are registrable-domain scoped, not origin keyed. Private execution state is cleared on `last-pb-context-exited`. Both global modes Off disables the service; inventory is not awaited in that state. |
| `toolkit/components/cookiebanners/nsCookieInjector.cpp` | Injection occurs at `NS_HTTP_ON_MODIFY_REQUEST_BEFORE_COOKIES_TOPIC` for top-document requests. Existing cookies are preserved unless they match the rule's unset value. The harness requires the actual first request header, parser-visible value and native store record, then uses an ordinary page button to set existing consent for the same domain/path. |
| `netwerk/cookie/nsICookieManager.idl` | The `cookies` array excludes private cookies. `getCookiesWithOriginAttributes` is required to observe a particular normal/private jar. The harness filters observations to the fixture cookie only. |
| `dom/security/nsHTTPSOnlyUtils.cpp` | Loopback HTTP is a special exception. An invented `*.localhost` HTTP subdomain is not an adequate substitute for the controlled HTTPS setup required by real registrable-domain UI and native injection. |
| `lw/librewolf.cfg:173` | Both cookie modes use `defaultPref(..., 1)`. The nearby `[ANDROID: LOCK]` text is a comment, not a `lockPref` call. Runtime controls still must prove effective mode changes; a saved Off choice must not be overwritten or mislabeled a broken default. |
| `security/manager/ssl/nsITransportSecurityInfo.idl`, `nsIX509Cert.idl`, `uriloader/base/nsIWebProgressListener.idl` | TLS observations expose secure state, certificate override/error state and the successfully verified leaf-to-root certificate chain. The origin preflight requires a clean verified chain ending in the supplied CA fingerprint, exact final URL and this run's private server challenge. No certificate bypass is used. |
| `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/home/intent/HomeDeepLinkIntentProcessor.kt`, `patches/android/branding.patch` | The actual Settings deep-link route is `<compiled scheme>://settings`; this branding supplies `redoubt`. The runner permits an explicit scheme for the actual installed package. |

The LW-M7-13 evidence and `patches/android/cookie-banner-rules.patch` define the
production packaged-list loading change. The runner awaits the existing
`initForTest()` promise before reading native rules, without supplying test
rules, enabling test-skip flags or writing Remote Settings data. Host tests
cannot substitute for the root-owned APK module/snapshot verification.

The generated LW-M7-23 files below were opened to bind real UI behavior:

- `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/SettingsFragment.kt`:
  independent normal/private switches write their real Settings choice, update
  the matching engine mode and reload the selected session. Global toggles use
  exact displayed titles and the switch in that title's own row.
- `mobile/android/fenix/app/src/main/res/xml/preferences.xml` and
  `res/values/strings.xml`: exact visible global titles and site-dialog strings.
- `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/cookiebannerhandling/CookieBannerSiteDialogFragment.kt`:
  stable switch/reset/status/scope IDs; captured tab, URL and private context;
  explicit domain/scheme/lifetime labels; disabled controls while reading or
  while global mode is Off; errors shown instead of success; explicit Close.
- `CookieBannerSiteController.kt` in that same directory: acknowledged storage
  changes and readback precede reload; On and Reset remove an exception; Off
  adds the disabled exception; global Off preserves it. No implicit clearing of
  cookies or saved site data occurs on this route. An acknowledged service call
  is not a claim of a native database fsync; an actual restart is required.
- `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/trustpanel/ui/ProtectionPanel.kt`:
  the shared site-control entry is exposed by its stable resource/test ID.

The runner's protocol, current-document checks, APK hashes, real private-tab UI,
process restart and transport-only configuration guard come from
`scripts/android-graphics-smoke.py` read-only. That module extracts only its
protocol foundation from `scripts/android-smoke.sh`; the old App setup and main
smoke driver are not run by this harness.

Remaining runtime boundaries: source scope labels do not prove sibling-domain,
HTTP-versus-HTTPS or unrelated-domain behavior; separate mapped-origin cases
would be needed. The allowed fixture endpoint establishes working page requests,
not a complete browser network capture. UI rendering, storage propagation,
service reinitialization, cookies and lifecycle behavior are all pending until
the target APK and controlled HTTPS fixtures run successfully.
