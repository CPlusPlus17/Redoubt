# Dedicated HTTPS cookie fixture preparation

`https-fixture.py` creates an ephemeral test authority and a seven-day leaf
certificate for `cookies.fixture.test`, `sub.cookies.fixture.test` and `duh.de`.
The authority and server private keys remain in the guest-only directory
`/home/runner/work/feature-parity-20260908/fixture-private-https-20260909` (mode0700;
keys0600), outside the repository. Only the public CA and manifest are retained
here. No release key is accessed. Do not archive the private state directory.

The bridge listens only on IPv4 loopback, normally port48762, and forwards only
to the cookie runner's HTTP listener at 127.0.0.1:48761. It accepts only the
three controlled Host values, origin-form URLs and bounded GET/POST bodies.
It preserves Cookie and response headers, uses ordinary TLS validation on the
client, and never connects to a public server. The cookie runner remains the
owner of native rule, parser/request, challenge and lifecycle evidence.

Root executed real TLS/HTTP checks on Fedora and inside the CI guest:
`host-tls-check.txt` and `guest-tls-check.txt`. They verify all three certificate
names and cookie-preserving forwarding; reject an untrusted CA and wrong TLS
hostname; and reject unrelated Host, proxy-form URL and oversized bodies before
the backend is reached. Check-only private keys were deleted afterward. The
separate prepared guest authority is still available for the browser run.
The first local check used an unsupported HTTPConnection context-manager form;
using contextlib.closing fixed the test client before the retained passing runs.

No emulator was started alongside native4. No DNS, hosts file, browser trust,
policy preference or rule was changed by these checks. Browser mapping and
native cookie behavior remain NOT RUN.

## Remaining device integration

After the native/APK build is terminal, use the dedicated disposable x86_64
emulator and source-bound release-type test APK. Route only that emulator's
three controlled hostnames to its loopback HTTPS port, with an adb reverse
443→48762 connection. Prefer a temporary emulator hosts mount when supported;
otherwise boot a separate writable-system emulator image. Preserve the original
hosts file and verify the mapping through Gecko itself. Do not edit the shared
SDK system image, host DNS or another device.

Trust only the prepared public CA in that browser's dedicated profile. The
pinned nsIX509CertDB.idl:354–364 declares `addCertFromBase64(base64, trust)`;
use the real certificate DB with SSL CA trust (`C,,`) and verify the returned
certificate SHA256. This is test trust setup, never a certificate-error bypass.
Keep a receipt of the profile identity, CA hash and installed APK. Remove that
specific trust entry during cleanup or discard the dedicated test profile.
Do not alter product security preferences to make the fixture work.

Start the bridge inside the guest:

```sh
python3 docs/android/evidence/lw-m7-32/https-fixture.py serve \
  --state /home/runner/work/feature-parity-20260908/fixture-private-https-20260909
```

Then run `scripts/android-cookie-banner-smoke.py` with `--fixture-port 48761`,
`--site-origin https://cookies.fixture.test`, `--injection-origin https://duh.de`
and the exact `ca_der_sha256` from `fixture-public-manifest.json`, alongside the
normal exact-APK/dedicated-profile inputs. Its independent anonymous Gecko
probe must receive this run's private challenge over clean TLS, with no redirect
or certificate override and the expected verified root. Failure leaves the
native domain tests pending; a reachable live duh.de is never accepted.

Record mapping/trust cleanup, stop the loopback bridge and remove its adb
reverse entry. TLS transport checks alone are not proof of banner rejection,
native cookie injection, domain exceptions or private-session cleanup.
