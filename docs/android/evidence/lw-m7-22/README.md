# LW-M7-22 real cookie-banner behavior

Implementation candidate; **live installed-APK acceptance is pending**. This
subtask has not run real adb, installed or built an APK, changed a guest, or
modified the frozen Gecko source. Host tests exercise the actual grader,
fixture server, exact preference-row selection and absent/connected fake-adb
failure paths. They do not establish native cookie behavior.

## First integration command

Run from the repository root against an already installed non-debuggable release
and an initialized, dedicated English test profile. Enable only the existing
transport-only Marionette configuration first, using the existing root-owned
setup. The script itself never writes that configuration or any browser pref.
Both real global cookie controls must start enabled. A saved Off choice leaves
the run pending and is not treated as a shipped-default failure; use the actual
Settings controls to prepare an existing test profile.

```sh
python3 scripts/android-cookie-banner-smoke.py \
  --adb /path/to/platform-tools/adb \
  --serial emulator-5554 \
  --package org.redoubtbrowser \
  --apk /path/to/the-installed-release.apk \
  --dedicated-test-profile \
  --core-only \
  --work /path/to/cookie-evidence
```

`--core-only` deliberately exits **3/PENDING** after the packaged global-rule
checks and explicit click control. It cannot produce a full acceptance PASS.
Omit it to exercise normal restart, existing consent, private isolation,
last-private-session teardown, available UI controls and optional native
domain-rule injection.

Missing APK/device/transport, tainted production test prefs, unavailable controls
and missing controlled-origin setup are explicit pending conditions. A failed
exercised condition returns **1/FAIL**. **0/PASS** requires every named acceptance
checkpoint, no pending criteria and unchanged installed APK hashes. Source gaps
cannot be excused by successful unrelated checks.

## Evidence needed for a rejection

The parser-loaded page uses the **actual packaged global rules**:

| Rule | Presence | Reject | Accept |
|---|---|---|---|
| `cookiebot` | `#CybotCookiebotDialog` | `#CybotCookiebotDialogBodyButtonDecline` | `#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll` |
| `didomi` | `div#didomi-host` | No opt-out selector | `button#didomi-notice-agree-button` |

Each real button callback increments a page counter, sets its own fixture cookie
and sends an action request carrying that cookie to the fixture server. Periodic
page requests provide an independent working allowed network control. Acceptance
requires agreement between callback counts, the page cookie, action count and
actual Cookie request headers. Cosmetic disappearance, an exception, missing
results, a blocked endpoint or a cookie without a callback cannot pass.

The Didomi fixture must remain unaccepted throughout a host-timed observation
window of at least seven seconds and at least two seconds beyond the effective
native post-load clicking timeout. Only after that assertion does the runner
perform a real WebDriver element click, require a trusted input event in the
callback, and prove the accept endpoint and cookie work. This explicit positive
control never substitutes for rejection-only protection.

Page metadata binds run ID, case ID, document ID and exact origin. Reloads and
private-mode selection are checked using the current active Gecko document;
stale or mixed-origin results cannot pass. Graphics transport/UI utilities are
imported read-only from LW-M7-18. Its old embedded App setup and main driver are
not executed. The script records hashes for both helper inputs and the installed
base/split APKs.

The production list service is queried only **after awaiting its existing
`initForTest()` promise**. `isEnabled` alone is insufficient. Runtime inventory
must contain 558 rules including nine global rules, exact Cookiebot/Didomi
selectors and the real `duh.de` opt-out rule. The actual packaged resource must
have 262208 bytes and SHA256
`0ddab9560f17710fa1613825b1b8be0e190107dd679e2cd53c5a1822524958fd`.
Both `testRules` and `testSkipRemoteSettings` must be unset, and the native testing
pref must not be supplied as a user value. Extra transport entries also taint
acceptance. The runner never inserts rules, changes preferences, writes domain
exceptions, clears native execution counts or forces a consent callback.

## Lifecycle and controls

Normal consent is a fixture website cookie created by the real reject callback.
The runner revisits it across an actual process termination/relaunch and checks
that the page recognizes its existing consent without another action. A fresh
Cookiebot case in the new process must still reject successfully. This is
application-level existing-consent behavior; native preservation of an existing
domain-rule cookie is measured separately below.

The same case in private browsing must not inherit normal consent. The runner
opens/closes private tabs through real Fenix controls, verifies last-private-
context teardown, repeats the case in a new private session with no old cookie,
then verifies that normal consent remains intact. A dedicated profile with no
pre-existing private windows is required.

Native clicking permits only three completed attempts per base domain and
session by default, including attempts that find no matching banner. Lifecycle
stages therefore use actual restarts or private-session teardown. The effective
limit is recorded and is never disabled by the harness. A missing callback after
cooldown is not counted as evidence of a user exception or existing consent.

The runner targets the LW-M7-23 UI candidate audited at commit `a23461b`, patch
SHA256 `be33b14682940c88a86bb4c4f375d358b0c40068db4336c24514f984aca9e8e7`.
Those controls must be compiled into the installed APK. Source selectors have
been reviewed; actual layout, storage and native behavior remain runtime gates.
Root subsequently identified a native private-session write race and is
coordinating its fix. The audited UI hashes are historical source receipts;
the final native fix and actual private teardown/new-session checks are required
before accepting a release. The selectors remain the UI contract.

| Route/control | Exact selector |
|---|---|
| Settings deep link | `redoubt://settings` (override with `--scheme` for the actual build) |
| Normal global switch title | `Cookie Banner Blocker in normal browsing` |
| Private global switch title | `Cookie Banner Blocker in private browsing` |
| Site panel entry | `cookie_banner_site_controls` |
| Site switch / reset | `cookie_banner_site_switch` / `cookie_banner_site_reset` |
| Site status / scope | `cookie_banner_site_status` / `cookie_banner_site_scope` |

The global switch must belong to its exact title row; the next preference's
switch cannot substitute. The global sequence turns both modes Off, requires
the service to become disabled, restarts the actual app and verifies both saved
choices remain Off. A real page click proves the otherwise unhandled reject
button still works. Re-enabling normal must leave private disabled; re-enabling
private must restore actual rejection. Every change uses the Fenix UI and reads
effective engine values. The production readiness promise is awaited again when
the service is enabled, never while both modes are disabled.

The site sequence requires the UI's precise registrable-domain, all-subdomains,
HTTP/HTTPS and normal/private lifetime labels. Off, On and Reset must change the
effective native domain mode, then produce a replacement document and the
expected real callback behavior. Consent cookies remain present throughout.
While the corresponding global mode is Off, both site controls must be disabled
and the existing exception must remain stored. The normal exception survives an
actual process restart. The private exception must disappear after closing the
last private tab, and rejection must work in the next private session.

Site-domain scope is checked against the engine's base-domain result and the UI
label; this harness does not claim separate HTTP, sibling-subdomain or unrelated-
domain behavioral coverage from that label check. Those need additional mapped
origins for their own runtime evidence. No control stage clears site data.

## Controlled HTTPS origins and native injection

Plain `http://localhost:<port>` with adb reverse is sufficient for the bounded
global-rule core and needs no HTTPS-only exception. Native per-site preferences
call Gecko's effective-TLD service; bare localhost and IP literals cannot supply
the registrable domain that those controls require. Use an externally prepared
controlled HTTPS origin for those stages:

```sh
python3 scripts/android-cookie-banner-smoke.py \
  --adb /path/to/adb --serial emulator-5554 \
  --apk /path/to/the-installed-release.apk --dedicated-test-profile \
  --fixture-port 48761 \
  --site-origin https://cookies.fixture.test \
  --injection-origin https://duh.de \
  --fixture-ca-sha256 <SHA256-of-the-trusted-fixture-CA-certificate> \
  --work /path/to/cookie-evidence
```

The operator must already route those **actual HTTPS origins** to the runner's
HTTP fixture at `127.0.0.1:48761`, using a certificate trusted by the test profile.
Before any controlled-origin page navigation, the runner starts on loopback and
uses an anonymous Gecko HTTPS probe to verify the mapping. The response must
contain this host fixture's private 256-bit challenge, which is never sent in
the request/URL and cannot be echoed by an unrelated live origin. The final URL
must match exactly with no redirect, the request must have secure TLS with no
certificate override or error, and its successfully verified certificate chain
must end in the supplied CA SHA256. The public CA fingerprint is an input from
the operator's prepared setup; a certificate error bypass is not a substitute.
Failed verification leaves that coverage pending and refuses its page
navigation. The global core can continue on explicitly recorded loopback.

The runner performs no DNS/hosts edits, proxy changes, CA installation, TLS
bypass or HTTPS-only preference change. The mapped origin must reach this run's
unique fixture; reaching an unrelated public website cannot satisfy its
registration and document checks. Pick a site origin whose packaged domain
rules do not override the global rules; `duh.de` is reserved for the separate
native-injector case, not the Cookiebot global fixture.

The native domain fixture requires the real `duh.de` domain because its packaged
rule injects `cookie_dismiss=true`. A rule inventory lookup for that URI does not
prove injection. This case requires an empty initial normal jar, the cookie on
the first actual document request, matching parser-visible state and a matching
native cookie-store record. A separate actual page button establishes an
`existing-consent` cookie for the same domain/path; a new navigation must
preserve it. Private injection must use the private jar, avoid inheriting that
normal value, clear on last-private-context teardown and leave normal consent
unchanged. Private cookies are read with `getCookiesWithOriginAttributes` because
`nsICookieManager.cookies` intentionally excludes them.

No mapping means this coverage remains explicitly pending. A prior test's
`cookie_dismiss` cookie also makes fresh-injection attribution pending. The
runner does not clear unrelated state or wipe profiles. Test tabs and website
consent cookies can remain for inspection, especially after failure; use the
dedicated profile's real controls before repeating the fresh-injection case.

## Host validation and remaining integration

```sh
python3 docs/android/evidence/lw-m7-22/test-cookie-banner-smoke.py
python3 docs/android/board.py --check
```

The evidence directory records executed host commands and source hashes in
`host-validation.json`, `host-tests.txt`, `board-check.txt` and
`source-inputs.json`; `source-audit.md` explains the source contracts. Task22
started at `6176f4d`, before task23 metadata existed. Integration must add
`LW-M7-23` to task22's `depends_on` alongside 12, 13 and 18 when replaying onto
main's task registry.
Per-run `cookie-results.json` is written incrementally and includes checks,
pending criteria, effective preferences, native inventory, fixture responses,
UI XML, optional screenshots and artifact hashes. Cookie request evidence copies
only the fixture cookie, not unrelated cookies from a profile. Failed behavior
cannot be reduced to an empty successful report.

Root still must run the installed-APK check, the LW-M7-13 packaged-module/snapshot
verification, affected Android test/build gates and existing smoke/pref audits.
This runner's allowed callback requests do not constitute a packet capture of
all browser traffic. Attribution of forbidden cookie-collection network traffic
needs the separate network evidence and a working allowed control; it must not
be inferred from an empty capture or an unrelated Remote Settings hostname.
