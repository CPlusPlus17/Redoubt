# The upgrade path, tested before the key exists

`BETA.md` §3 makes a second build mandatory during the window, and says why:

> A beta that never exercises the upgrade path has not tested the one thing the
> signing key exists for.

That path had never been exercised, and it is a **no-go condition** (N5): a second
build failing to install over the first ends the beta on the spot. Waiting for the
real signing ceremony to find out would be finding out at the worst moment.

So it was tested with a throwaway key. Everything is identical to the real thing
except the key's identity.

## What was done, 2026-09-06

Two genuinely different builds of the same tree, signed with **one** throwaway
RSA key, v1 off / v2 on / v3 on — the exact invocation in `SIGNING.md`:

    build A   versionCode 2016183142   fingerprint 9174536afd646c6a…
    build B   versionCode 2016183238   fingerprint 9174536afd646c6a…   (same key)

On a clean emulator: install A, launch it, then install B **over it** with a plain
`adb install -r` — no uninstall, which is what a real user's updater does.

    Success
    Install command complete in 1328 ms
    versionCode=2016183238        (was 2016183142)
    app launches, 1 process, empty crash buffer

## What this establishes, and what it does not

**Established.** A v2+v3-signed Redoubt APK installs on a device; a later build
signed with the same key replaces it in place, keeping app data; the upgraded app
starts. The mechanism behind N5 works, and the `apksigner` invocation in
`SIGNING.md` produces artifacts Android accepts as an upgrade of one another.

**Not established.** That the *release* key does this — that is E7 and it needs the
ceremony. But the only variable left is which key, and the failure mode N5 warns
about (`INSTALL_FAILED_UPDATE_INCOMPATIBLE`, signatures do not match) is a property
of *changing* keys, not of any particular one. Keep signing every build with the
one key and this path stays open; sign one build with a different key and it closes
permanently for every installed user.

That failure was seen for real during this session, from the other direction: the
smoke harness hit `INSTALL_FAILED_UPDATE_INCOMPATIBLE` on eight checks in a row
because each build container generates its own debug keystore. It is not
hypothetical, and on a released app there is no `adb uninstall` to recover with.
