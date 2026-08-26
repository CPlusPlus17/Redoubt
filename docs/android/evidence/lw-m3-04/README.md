# LW-M3-04: Generate the must-lock pref list from the Fenix sources

## What was delivered

1. **`scripts/gen-android-locks.py`** — parses both Java files and the
   constructed SafeBrowsingProvider names. Supports:
   - Default mode: writes the sorted must-lock list to `docs/android/must-lock.txt`
   - `--check`: regenerates and diffs against the stored copy (exit 0 on no diff)
   - `--stdout`: prints to stdout
   - Tree resolution follows board.py's convention (LW_TREE, error on ambiguity)

2. **`docs/android/must-lock.txt`** — the generated list: 137 unique pref names
   (77 `Pref<>` + 24 `PrefWithoutDefault<>` + 36 SafeBrowsingProvider constructed).

3. **`docs/android/must-not-lock.txt`** — the allowlist of prefs that must NOT
   be locked because a settings fragment owns them. Four entries, each naming
   the owning UI and the file:line that proves it.

4. **Cross-check (the bug report):** 26 prefs are set in our cfg files AND are
   in the must-lock universe. Of those, 2 are already `lockPref` (survive) and
   24 are `defaultPref` (transient — clobbered by stage 5b at next startup).

## Count verification

The user's brief stated: 77 literal `new Pref<>`, 24 literal
`new PrefWithoutDefault<>`, 12 per provider × 3 providers = 36 constructed.
The parser reproduces all three numbers exactly:

```
#   new Pref<>:            77 names
#   new PrefWithoutDefault: 24 names
#   SafeBrowsingProvider:  36 constructed names (3 providers x 12 suffixes)
#   TOTAL:                 137 unique pref names
```

The two decompositions the user warned about:
- "77+36 = 113" is the always-present reset universe (hasDefault() → true)
- "89+24 = 113" is the count of declaration sites (89 = 77 literal + 12 constructor)
- The full must-lock set is 137 (all unique names, including the 24
  PrefWithoutDefault which are "only in play once set")

## Cross-check: 26 transient prefs

These prefs are set in our cfg AND are in the must-lock universe (Fenix writes
them at runtime via Pref.commit()):

| Pref | Verb | Location | In must-not-lock? |
|------|------|----------|-------------------|
| browser.contentblocking.category | lockPref | android.cfg:341 | **YES** — contradiction |
| browser.crashReports.requestedNeverShowAgain | lockPref | common.cfg:640 | no |
| browser.safebrowsing.malware.enabled | defaultPref | common.cfg:368 | no |
| browser.safebrowsing.phishing.enabled | defaultPref | common.cfg:369 | no |
| browser.safebrowsing.provider.google.gethashURL | defaultPref | common.cfg:373 | no |
| browser.safebrowsing.provider.google.updateURL | defaultPref | common.cfg:374 | no |
| browser.safebrowsing.provider.google4.dataSharingURL | defaultPref | android.cfg:432 | no |
| browser.safebrowsing.provider.google4.gethashURL | defaultPref | common.cfg:371 | no |
| browser.safebrowsing.provider.google4.updateURL | defaultPref | common.cfg:372 | no |
| cookiebanners.service.mode | defaultPref | common.cfg:173 | no |
| cookiebanners.service.mode.privateBrowsing | defaultPref | common.cfg:174 | no |
| devtools.console.stdout.chrome | defaultPref | android.cfg:398 | no |
| devtools.debugger.remote-enabled | lockPref | android.cfg:361 | no |
| network.cookie.cookieBehavior.optInPartitioning | defaultPref | common.cfg:122 | no |
| network.cookie.cookieBehavior.optInPartitioning.pbmode | defaultPref | common.cfg:123 | no |
| network.lna.block_trackers | defaultPref | android.cfg:237 | no |
| network.trr.mode | defaultPref | common.cfg:259 | no |
| network.trr.uri | defaultPref | common.cfg:260 | no |
| privacy.globalprivacycontrol.enabled | defaultPref | common.cfg:304 | **YES** |
| privacy.globalprivacycontrol.functionality.enabled | defaultPref | common.cfg:306 | no |
| privacy.globalprivacycontrol.pbmode.enabled | defaultPref | common.cfg:305 | no |
| privacy.query_stripping.allow_list | defaultPref | common.cfg:158 | no |
| privacy.trackingprotection.allow_list.baseline.enabled | defaultPref | common.cfg:118 | no |
| privacy.trackingprotection.allow_list.convenience.enabled | defaultPref | common.cfg:119 | no |
| security.enterprise_roots.enabled | defaultPref | common.cfg:340 | no |
| signon.autofillForms | defaultPref | common.cfg:543 | no |

**Action items (not implemented — outside this task's file ownership):**
- The 22 `defaultPref` entries (minus the 2 already `lockPref`) should be
  converted to `lockPref` in the cfg files, EXCEPT the 4 in must-not-lock.txt.
- The 4 must-not-lock prefs (browser.contentblocking.category,
  dom.security.https_only_mode, privacy.globalprivacycontrol.enabled,
  privacy.fingerprintingProtection) must stay as `defaultPref` (or be removed
  from cfg) to keep the settings toggles functional.
- **Contradiction found:** `browser.contentblocking.category` is currently
  `lockPref` in android.cfg:341 AND is in must-not-lock.txt. One of them is
  wrong. If the user must be able to change their tracking protection level,
  the lockPref must be removed.

## board.py `_gv_declared_prefs` fix (for the maintainer)

The current parser at board.py:643-660 matches only literal string names:
```python
re.finditer(r'\bPref(?:WithoutDefault)?<[^>]*>\s*\(\s*"([^"]+)"', line)
```

This is blind to the 36 constructed SafeBrowsingProvider names
(`ROOT + mName + ".suffix"`). The fix: after the existing literal-name loop,
add a match for the constructed pattern and expand it using the ROOT constant
and the three default provider names found in the same file:

```python
# After the existing literal-name matching in _gv_declared_prefs:
text = p.read_text(errors="replace")
if "ContentBlocking.java" in Path(rel).name:
    root_m = re.search(r'private\s+static\s+final\s+String\s+ROOT\s*=\s*"([^"]+)"', text)
    if root_m:
        root = root_m.group(1)
        suffixes = [m.group(1) for m in re.finditer(
            r'new\s+Pref<[^>]*>\s*\(\s*ROOT\s*\+\s*mName\s*\+\s*"(\.[^"]+)"', text)]
        providers = set(m.group(1) for m in re.finditer(
            r'public\s+static\s+final\s+SafeBrowsingProvider\s+\w+\s*=\s*\n?\s*'
            r'SafeBrowsingProvider\.withName\("([^"]+)"', text))
        for prov in providers:
            for sfx in suffixes:
                name = root + prov + sfx
                if name not in found:
                    found[name] = f"{Path(rel).name}:constructed"
```

This keeps one parser (in board.py) and does not import from gen-android-locks.py.
The two can coexist: board.py's is for the policy check, gen-android-locks.py's
is for list generation. They must agree on the set of names.

## NOT verified

- The must-not-lock list is a first pass. It contains 4 prefs where I could
  name the owning settings UI from the code. There may be more (e.g.,
  `signon.autofillForms` has a "Form autofill" toggle in Settings > Privacy,
  and `browser.translations.automaticallyPopup` has a translations toggle)
  that I did not include because I could not verify the exact file:line of
  the setter in this tree. Adding them is a maintainer decision.
- The `board.py --check-policies` gate has NOT been re-run after the proposed
  fix (I did not edit board.py). The maintainer needs to apply the fix above
  and verify the 5 currently-blind prefs (common.cfg:371-374, :384,
  android.cfg:432) are now caught.

## Files owned and written

1. `scripts/gen-android-locks.py` (new)
2. `docs/android/must-lock.txt` (new, generated)
3. `docs/android/must-not-lock.txt` (new)
4. `docs/android/evidence/lw-m3-04/README.md` (this file)
