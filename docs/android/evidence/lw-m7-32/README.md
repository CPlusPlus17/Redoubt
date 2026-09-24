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

## Executable emulator setup and recovery (source candidate)

`emulator-setup.py run` prepares this fixture, invokes the existing Task22 cookie
runner, and performs cleanup in `finally`. It expects an **already running,
dedicated, rootable AOSP emulator**, an **already installed non-debuggable release
APK**, and an **externally prepared fresh test profile**. It does not start an
emulator, install or wipe an APK/profile, open a private-key directory, or run the
TLS bridge itself. Run it only after the native build is terminal, on the same
machine as the adb server and the bridge (the planned CI guest).

The public-input check is safe without a device:

```sh
python3 docs/android/evidence/lw-m7-32/emulator-setup.py check-inputs
```

The controlled run, once root has prepared the emulator, installed APK and bridge:

```sh
python3 docs/android/evidence/lw-m7-32/emulator-setup.py run \
  --serial emulator-5554 \
  --apk /absolute/path/to/the-exact-installed-release.apk \
  --expected-profile /exact/ProfD/path/in/org.redoubtbrowser \
  --fresh-dedicated-profile \
  --work /absolute/path/to/a-new-cookie-tls-run
```

Replace the profile placeholder with the actual native value of
`Services.dirsvc.get("ProfD", Ci.nsIFile).path`, obtained from the existing
read-only Marionette transport or the fresh-profile preparation receipt. The
helper requires the exact path within `/data/user/0/org.redoubtbrowser/` or
`/data/data/org.redoubtbrowser/`; it does not guess a profile from a directory
name. The fresh-profile flag is an explicit operator declaration. The helper
additionally verifies zero cookies and no preexisting matching fixture CA before
import; it does not claim these two observations prove the entire profile has
never been used. The cookie runner independently checks its own consent and
exception preconditions. A profile-path mismatch aborts before cert import.

The helper:

- Pins the selected `emulator-NNNN` serial, boot UUID, AOSP build identity and
  all installed APK hashes/build flags. If `adb root` is needed, it refuses
  existing device routes that an adbd restart might disturb.
- Preserves original hosts bytes/hash and rejects existing entries for the three
  controlled names. It copies hosts to a unique emulator `/data/local/tmp/`
  directory, preserves its SELinux label and uses a temporary `mount --bind`.
  It checks the source/target inode and hash before accepting or unmounting it.
  It never edits the shared SDK image, host DNS, or SELinux enforcement. A mount
  or namespace failure remains PENDING; there is no automatic remount fallback.
- Adds only adb reverse443→48762 and its own temporary loopback bootstrap route.
  Shell-visible mapping is insufficient: ordinary Gecko DNS lookups, with only
  cache bypass and no forced resolver mode, must resolve **every** controlled
  name exclusively to127.0.0.1. It then runs the same strict anonymous HTTPS
  verifier used by Task22 against an unpredictable setup challenge, requiring
  no redirect, no certificate override, no TLS error and the exact verified CA.
- Creates or reuses only the exact seven-line transport config already accepted
  by Task18/22. It enables Android's debug-app config entry point only when
  necessary; this does not turn the release APK into a debuggable build. It
  records native policy values and rejects production cookie test overrides.
  It does not inject product preferences, DNS overrides, cookie rules or a
  certificate-error exception.
- Imports the exact public CA through `addCertFromBase64(..., "C,,")`; checks
  the returned DER fingerprint, database key and native profile; force-stops
  and restarts the app; and verifies native trust again. Existing matching CA
  records are refused, so cleanup never changes a preexisting certificate.
- Runs a temporary48761 HTTP challenge backend during setup, then stops it and
  removes its HTTP reverse before calling Task22. Task22 receives its normal
  fixture port, exact CA and three controlled HTTPS names and owns a separate
  challenge and all cookie/UI/native behavior grading. The helper journals
  cleanup responsibility for the child-created HTTP reverse before spawning it,
  so an interrupted child can be recovered. It terminates only its own child
  process on interruption.
- Deletes only its exact CA identity, restarts and verifies trust is absent;
  removes only unchanged owned routes/config/mount; restores original hosts;
  and returns adbd to its earlier privilege state when it enabled root. An
  existing valid transport config/debug-app selection is preserved as original
  state. If cert cleanup cannot complete, it retains the owned transport needed
  to retry cleanup and reports that explicitly.

State and incremental events are in `WORK/setup.json` (mode0600); actual cookie
results are separately under `WORK/cookie/`. Setup always leaves its own
`acceptanceComplete:false`: only the existing cookie runner can report completed
cookie acceptance. `--core-only` passes through to that runner and remains
partial/PENDING. A missing device, absent/wrong APK, unknown profile, wrong CA,
public/live-origin response, tainted config or incomplete cleanup cannot return
successful full acceptance.

For interruption recovery, use the same work directory and same emulator boot:

```sh
python3 docs/android/evidence/lw-m7-32/emulator-setup.py cleanup \
  --serial emulator-5554 --work /absolute/path/to/the-cookie-tls-run
```

Recovery is bound to the journal's original boot/profile/certificate. It refuses
a reused serial with a different boot or any replacement mount/route/config.
It can remove an expired fixture CA because cleanup does not require that CA to
remain within its validity period. A SIGKILL or lost device connection cannot
promise automatic cleanup; the journal preserves the exact remaining ownership
for the recovery command. Keep the dedicated emulator/profile until cleanup is
recorded, or have root explicitly discard that disposable environment.

`test_emulator_setup.py` supplies20 host-only negative/ownership tests. Actual
public hash/self-signature/time verification passed on Fedora; no adb/device,
Gecko certificate import, namespace mapping or cookie suite was executed for this
candidate. Those target gates remain **NOT RUN**, including whether this AOSP
image propagates the temporary mount to the resolver used by Gecko. The helper
checks the resulting DNS and TLS behavior instead of assuming propagation.

`source-bindings.json` pins the opened native IDLs/runtime entry point and the
runner/verifier inputs. GeckoViewRuntime's existing debug config entry point is
in `GeckoRuntime.java:503–525,603–609`; certificate APIs are in
`nsIX509CertDB.idl:145,186,246,364,370`; fingerprint/DB key and DNS record methods
are in the accompanying pinned IDLs. These are source bindings, not target runs.
