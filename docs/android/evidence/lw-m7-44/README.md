# LW-M7-44: disabling uBlock Origin while it starts no longer pauses browsing

Date: 2026-10-06. Branch `fix/ubo-user-disable`, off origin/main 19f866ea (157.0-3).

## The report

The video investigation (`../video-playback/README.md`, item 4) found this on 157.0-2:
turning uBO off through AddonManager showed "uBlock Origin setup failed / Browsing is
paused".

## Cause

`LibreWolfUboPreinstaller` (LW-M3-07) runs once per process start. It holds every
engine session until uBO's live blocking listener is registered, through Gecko's
`awaitBlockingResponseListener`. Any disable or uninstall stops the extension, and
the shutdown rejects that wait with "Blocking extension stopped before becoming
ready". The preinstaller then re-reads the registry for 5 s. It continued only for a
strictly newer enabled copy, which is an AMO update. In every other case it failed
closed, and that included the user's own disable or removal.

The guard only fires during that startup window. What each action does:

| Action | Before startup readiness | After readiness / on a later start |
|---|---|---|
| Disable (Settings > Add-ons, or `AddonManager` `disable()`) | **Failure dialog (bug)** | No effect; a restart gives `Ready(installed=true, enabled=false)` |
| Uninstall of a provisioned copy | **Failure dialog (bug)** | No effect; a restart gives `Ready(installed=false, …)` |
| Uninstall during the very first install | Failure dialog (kept; a restart also requires Retry) | n/a |
| Private-browsing permission change (Gecko `addon.reload()`) | Failure dialog (kept, see below) | No effect |
| AMO update to a newer version | Handled: the wait restarts on the new version | No effect |
| uBO's own power button | Not reachable before readiness; it is uBO-internal state and the extension keeps running | No effect |

In the 157.0-2 build, Retry already recovers from every case in the table. The fix
removes the dialog only for the deliberate cases.

## Fix (ubo-preinstall.patch, Kotlin only)

After the settle window, two cases now end the wait as `Ready` without filtering:

- a copy whose GeckoView `disabledFlags` include `USER`;
- an absent copy, but only on the existing-installation path, where uBO was already
  provisioned.

A restart would accept the same state. The check runs at the end of the window
because Gecko's `reload()` sets `userDisabled` for a moment, and by then that has
cleared. Nothing else changes. Reloads, blocklist, signature and app disablement,
and a removal during the first installation still fail closed.

Who can set `userDisabled`: the user (Fenix add-ons manager) or chrome-privileged
code (Marionette, remote debugging). Web content cannot, and no tab runs before the
wait ends anyway. Other WebExtensions cannot either: `management.setEnabled` only
covers themes and policy installs, and Android has no policy engine.

### Follow-up: the settle must hold still (review finding)

An independent review found a fail-open timing gap. `settleRegistry` read the
registry once, at the end of the 5 s window. Gecko's `reload()` sets
`userDisabled: true`, waits for the old instance to shut down, then clears it and
starts the copy again (`XPIDatabase.sys.mjs`, `AddonWrapper.reload`). If that
shutdown outlasted the window on a slow device, the wait ended as
`Ready(enabled=false)`, and the held first page loaded unfiltered just before uBO
came back.

The fix keeps the 5 s window. After it, the registry must read the same for 3 more
polls (750 ms). A reload that clears its flag in that time reads enabled, because a
starting copy reports Gecko's `isActive`, so it never matches the user-disabled
case and the wait fails closed. Any change restarts the count. If the registry is
still changing 5 s after the window, the wait fails closed with "uBlock Origin's
add-on state did not settle during startup". A newer enabled copy (an AMO update)
is still taken as soon as it appears.

This is a timing guard, not proof. A reload whose shutdown alone takes longer than
about 5.75 s would still look like a stable user disable.

`navigator.mozAddonManager` on AMO hosts can also disable an add-on. That is not
exploitable during the hold, because no tab runs until the wait ends; the source now
says so.

## Evidence

- `build/`: an x86_64 GeckoView build plus Fenix `assembleRelease` on the patched
  157.0-3 tree, with `-Werror` (`fenix-compile.txt`). The final `android-apk.sh`
  exit 1 comes from its universal-APK ABI check, which a single-ABI build always
  trips. The same thing happened in the video-bug proof build. The x86_64 APK is
  complete.
- `unit-tests/` (replaced by the follow-up run): `LibreWolfUboPreinstallerTest` 30/30
  and `LibreWolfUboPreinstallMiddlewareTest` 4/4, run after the settle follow-up. The
  3 newest tests cover:
  - a reload whose `userDisabled` clears 5.25 s into the settle is not accepted
    and fails closed, on the first-run and the existing-installation paths;
  - a user disable that appears at 4.75 s and then holds still is accepted at
    5.75 s, and not before;
  - a registry that flips on every poll stays held until 10 s, then fails with
    "did not settle".

  The first run, before the follow-up, was 27/27 with 4 new tests:
  - first-run user disable;
  - later-start disable and removal;
  - reload and non-user disable still fail;
  - Retry adopts a later disable.

  `LibreWolfUboPreinstallMiddlewareTest` passed 4/4.
- `build/followup-*`: the follow-up rebuilt the x86_64 fat AAR and Fenix
  `assembleRelease` with `-Werror` from a fresh `make android-dir` of the patched
  157.0-3 tree (`followup-fenix-compile.txt`, `followup-commands.log`). The tree had
  been deleted after the first run. The unit tests then ran in the same container
  and objdir as `unittest.sh`. The `android-apk.sh` exit 1 is the same single-ABI
  universal-APK check as before. Gates on the follow-up: `check-patchfail.sh
  --targets=android` against the GPG-verified `firefox-157.0.source.tar.xz` applied
  every patch, and `check-patch-order`, `lint-patch-scope`, `board.py --check` and
  `--check-scope` were all ok.
- `device/`: API 34 x86_64 emulator, `android-smoke.sh --check-ubo-user-disable`.
  Both APKs were re-signed with the throwaway key, and their hashes are in
  `build/SHA256SUMS`.
  - `old/` (157.0-2, release asset c4eb178b…):
    - reload-control ok;
    - **user-disable FAILED**: dialog shown (`ubo-user-disable-user-disable.png`),
      failure logged, and the held page never loaded. This reproduces the report.
  - `fix/`:
    - reload-control ok: the dialog is still shown, so the guard is still live;
    - **user-disable ok**: "uBlock Origin was disabled by the user during startup",
      `Ready(installed=true, enabled=false)`, and the held page loaded unfiltered
      with both scripts reaching the origin;
    - Marionette mutated uBO 4.8–5.0 s after launch, inside the wait.
  - `fix-lifecycle/`: the existing `--check-ubo-lifecycle` passes 10/10 on the fix.
    It covers disable after readiness, retention across a restart, removal, and APK
    reinstall.
  - `old-provision-timeout/`: a first 157.0-2 attempt hit a harness error. The
    provisioning page did not finish within `wait_for_initial_document`'s 15 s.
    This is unrelated to the fix, and the rerun in `old/` is the result.

The device runs predate the settle follow-up and were not repeated. With the
follow-up, a stable user disable ends the wait at least 750 ms later than in those
runs. This is covered by the unit tests only.

Not exercised: disabling with taps in Settings > Add-ons inside the window. The window
lasts a few seconds, and the harness reaches the same Gecko `disable()` through
AddonManager. Also not exercised: uBO's popup power button.

## Open owner questions

- On a restart, any disabled copy is accepted as `Ready(enabled=false)`, including
  blocklisted or signature-disabled ones. This leniency predates this change and is
  not addressed here.
- A private-browsing permission toggle during the few-second startup window still
  shows the dialog, and Retry recovers. A same-version reload cannot be told apart
  from a genuine failure without matching Gecko's error text.
