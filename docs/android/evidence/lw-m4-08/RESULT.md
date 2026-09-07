# LW-M4-08 — the allowlist decision, and what it measurably changed

Decision taken 2026-09-06 by the maintainer: **keep the seven collections that
carry security state, drop the twenty-six that serve features Redoubt does not
ship.** Implemented in `settings/android.cfg` with a reason per dropped group;
`settings/common.cfg` is untouched, so desktop is unaffected.

Verified live on the device, not just in the file. The pref dump from a running
build reads exactly seven entries:

    security-state/*                 blocklists/gfx
    blocklists/addons                blocklists/plugins
    blocklists/addons-bloomfilters   main/tracking-protection-lists
                                     main/hijack-blocklists

## What it changed

First-run capture, emulator pointed at Quad9 so nothing is sinkholed, same
build, same harness, same 60-second window:

| allowlist | events | bytes received | bytes sent |
|---|---|---|---|
| 33 collections (desktop's) | 6 | 1,324,658 | 24,804 |
| 7 collections (Android's) | 6 | **636,739** | **11,637** |

**52% less data received, and the same six events.** Both halves of that matter.

The byte reduction is the decision working: twenty-six collections and their
attachments are no longer fetched.

The unchanged event count is the part that must not be glossed. One poll of the
changes endpoint plus a content-signature fetch serves whatever remains, so the
*number of requests* is a function of syncing anything at all, not of how much.
Going to zero requires an empty list, which would freeze certificate revocation,
the add-on blocklist and the tracking-protection lists at whatever shipped in the
binary — a revoked certificate trusted until the next release. That trade was put
to the maintainer and refused.

## Consequences to carry forward

1. **M4's "zero outbound requests between install and first navigation" does not
   hold, and is not going to.** Publish the measured number instead. It is six
   requests to three Mozilla Remote Settings hosts, and the reason is that the
   browser keeps its revocation and blocklist data current.
2. `--first-run-capture` and `--check-no-remote-settings` stay red **by design**.
   Both assert zero. Neither should be "fixed" by weakening it; the decision
   above is what makes them red, and `BETA.md` E3 records that.
3. Nothing telemetry-shaped is in that traffic. Measured through a resolver that
   does not sinkhole: no telemetry, Adjust, ads, crash-reporting or Google
   endpoint appears, before or after this change.
