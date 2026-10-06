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

## Evidence

- `build/`: an x86_64 GeckoView build plus Fenix `assembleRelease` on the patched
  157.0-3 tree, with `-Werror` (`fenix-compile.txt`). The final `android-apk.sh`
  exit 1 comes from its universal-APK ABI check, which a single-ABI build always
  trips. The same thing happened in the video-bug proof build. The x86_64 APK is
  complete.
- `unit-tests/`: `LibreWolfUboPreinstallerTest` 27/27, with 4 new tests:
  - first-run user disable;
  - later-start disable and removal;
  - reload and non-user disable still fail;
  - Retry adopts a later disable.

  `LibreWolfUboPreinstallMiddlewareTest` passed 4/4.
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
