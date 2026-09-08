# LW-M7-09: Android privacy defaults

Implementation handoff, 2026-09-08. This evidence was produced by the entry_audit
agent in the isolated `android/LW-M7-09` checkout. **Static checks passed; Kotlin
compilation, the full Fenix unit gate and built-APK behavior are pending the root
agent's combined VM run. This task is not yet complete.**

[privacy-defaults.patch](../../../../patches/android/privacy-defaults.patch)
SHA256: `986e012fb5d7df0625aa3eee9e35561e29abdff2bce08e4daa936c02373541ce`.
The patch is intentionally unregistered in this handoff: root owns patch-list,
PATCH-SCOPE and shared-file order integration. It changes only the 15 tree paths
in [source-files.json](source-files.json), all declared by LW-M7-09.

| Setting | New absent-value default / behavior |
| --- | --- |
| HTTPS-only | Enabled for all tabs; existing mode choices remain writable |
| Tracking protection | Strict policy, including strict social protection, total cookie protection, bounce tracking protection and no convenience exceptions |
| Quit cleanup | Enabled; only cookies/site data and cache selected. Tabs, history, permissions and downloaded files remain unselected |
| Cleanup switch | Off preserves category selection. On preserves a nonempty selection; an empty selection becomes cookies/site data plus cache only |
| Password saving, login autofill, address/card autofill | Disabled by default; stored choices remain intact |
| DNS over HTTPS | Explicit OFF (5). Quad9 configured URI, DNS4All fallback URI, and all seven ordered provider choices match `settings/common.cfg` |
| Existing DNS providers | Previous Cloudflare, NextDNS or custom URL remains selected as a custom provider when DoH is enabled |

The five XML resources agree with the Kotlin defaults. Tracking and password
radio fallback values are derived from effective Settings values so a stored
choice with an absent companion key does not display two selected choices.
The cleanup screen refreshes checkboxes from Fenix Settings before handling
changes. No automatic migration deletes data or overwrites stored values.

## Source and migration evidence

The source base is the immutable `librewolf-153.0esr-1-beta-20260908` patched
Android tree, represented here by the thirteen original changed files in
[before-source.tar.gz](before-source.tar.gz). The two new files are fragment
tests. All thirteen originals were compared byte for byte against that frozen
tree when generating the patch. No files in the beta tree were edited.
`a9c18e7` is the isolated repository implementation starting point; later
cherry-picked commits only expanded task metadata. The settings submodule is
`2206f8d1e59c0a0c0f69ee3fe5121eb353426687`.

Read-code evidence is archived in
[migration-source-excerpts.txt](migration-source-excerpts.txt). It establishes:

- Fenix Settings uses `fenix_preferences`. These affected boolean/string delegates
  do not request `persistDefaultIfNotExists`; their default reads do not write.
  The integer delegate also reads its fallback without writing. Therefore an
  absent old preference can inherit the new default without a migration write.
- `SharedPreferenceUpdater`, radio changes, the HTTPS switch listener and the DoH
  provider setters persist values without recording whether the origin was an
  explicit user choice or some older programmatic caller. A stored old value is
  not sufficient evidence of an untouched profile. It is preserved.
- `RadioButtonPreference` reads the Fenix preference store with its XML/default
  fallback; `setDefaultValue(Boolean)` changes only that fallback. Ordinary
  preference inflation also has Android's preference-store state, so XML and
  screen binding must agree with Fenix Settings. This patch does not claim that
  every XML inflation writes Fenix Settings.
- The old cleanup master listener writes every category on either transition.
  Those stored values cannot now be classified as explicit category choices or
  automatic consequences of that listener. They are retained. Its future
  behavior is corrected without resetting existing selections.
- A stored Standard or Custom ETP choice wins over an absent Strict key. A stored
  rejection of Strict retains the former implicit Standard choice. Existing
  explicit Strict values are retained as well.

**Migration limit:** the acceptance phrase “untouched older defaults upgrade” is
covered only for absent preferences. No provenance marker was found that could
safely distinguish previously persisted defaults from user choices, so this is
not a claim that every existing beta profile acquires all new defaults. A
user-selected “apply LibreWolf defaults” action remains a separate open solution
for ambiguous stored profiles; this patch does not silently apply one.

## Checks and remaining proof

Replay without a device or original extracted source:

```sh
git submodule update --init settings
python3 docs/android/evidence/lw-m7-09/verify-static.py
```

[static-verification.json](static-verification.json) records the actual successful
run: archive hashes, 15 exact patched output hashes, zero-fuzz/no-offset patch
application, five parseable XML resources, the ordered desktop DNS catalog, and
`board.py --check`: `ok: 97 tasks, 21 waves, 0 warning(s)`.
The verifier deliberately labels these static checks and does not substitute
for compilation. [test-inventory.json](test-inventory.json) inventories the
Kotlin tests authored/updated, including actual policy construction, stored
values across two Settings instances, cleanup selections through UI listeners,
radio view binding and legacy DNS-provider retention. Existing expectations
that intentionally changed were updated, rather than adding failure allowances.

Required integration gates remain:

1. Compile the affected Kotlin and resources in the real Android target.
2. Run `./mach gradle fenix:testDebugUnitTest` and the repository's
   `board.py --check-fenix-tests` against that run. Authored tests have not yet
   been executed by this agent.
3. Run smoke and preference audit on the new APK. Verify HTTPS upgrade and its
   user control, an effective strict policy, real cookie/cache deletion on the
   supported Quit flow while history/permissions remain, no automatic password
   saving/autofill, and DoH OFF/provider controls in the effective engine.
4. Verify fresh and upgraded profiles through two starts, including stored
   alternatives and visits to the settings screens.

Changing Quit defaults does not implement or prove cleanup after Android task
removal, process death or force-stop. Gecko preference locks can also make a
visible opt-in control ineffective; this patch makes no such runtime claim.
Those lifecycle and effective-control checks remain part of the broader parity
goal and must not be inferred from a checked box or this static evidence.
