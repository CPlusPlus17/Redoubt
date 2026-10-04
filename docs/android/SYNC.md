# Sync with LibreWolf desktop

Redoubt can sync with LibreWolf on the desktop (or Firefox) through **Firefox Sync**
and a Mozilla account. It is **off by default on both sides**, so you opt in on each
device.

**Status:** tested end to end by the maintainer on 2026-10-04, with a Redoubt
157.0-1 beta and LibreWolf desktop.

## Set it up

1. **LibreWolf desktop.** Set `identity.fxaccounts.enabled` to `true`. Put it in
   your `librewolf.overrides.cfg` so it survives updates, or set it in
   `about:config` for this profile only. Restart LibreWolf, then sign in to your
   Mozilla account from the menu.
2. **Redoubt.** In Settings, turn on accounts and Sync. Redoubt asks to restart,
   which is how the opt-in takes effect (`patches/android/sync-opt-in.patch`,
   LW-M7-20). Sign in with the same account and choose what to sync.

## What syncs

Bookmarks, history, passwords, open tabs (and "Send tab"), and addresses and
payment cards. Add-ons do not sync to Android.

## Things to know

- **Encryption.** Your synced data is end-to-end encrypted with a key derived
  from your account password, so Mozilla cannot read it. Mozilla does see that
  the account exists, your IP address, when you sync, and roughly how much data
  you store.
- **No instant delivery.** Redoubt ships without Google services, and the push
  server option is removed (`no-gms.patch`). Sync runs at app start, on a
  schedule, or when you trigger it. A tab sent from the desktop arrives at the
  next sync, not immediately.
- **Desktop history.** LibreWolf clears history on shutdown by default, so
  there is little history to sync unless you change that.
- **Your own server.** You can run Mozilla's sync storage server
  (`syncstorage-rs`) yourself. On the desktop, point
  `identity.sync.tokenserver.uri` at it. Redoubt keeps Fenix's custom Mozilla
  account server and custom Sync token server settings on its hidden Sync Debug
  screen. Using your own server is **not tested** with Redoubt yet.
- **Not affiliated.** Firefox Sync is Mozilla's service, and LibreWolf is a
  separate project. Neither supports Redoubt, so report Redoubt sync problems on
  the [Redoubt issue tracker](https://github.com/CPlusPlus17/Redoubt/issues).
