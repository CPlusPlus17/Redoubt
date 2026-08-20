# Rebasing Redoubt onto a new Firefox ESR

**Owner: LW-M7-01.** This file is the procedure for moving the Android track from
one Firefox ESR version to the next — normally a dot release (`153.0esr` →
`153.1esr`), once a year a major one (`153.x` → the next ESR series).

It is written to be executed by a maintainer who did not write it. If a step here
is not enough to act on, that is a defect in this file; fix it in the same pull
request as the rebase rather than working it out again next time.

That standard has already been applied to this file once: a skeptical pass found
three defects in the first revision — a mechanism asserted as executed that an
execution falsifies (6d), a copy-paste path that walked into the trap another
section existed to prevent (appendix A), and a "retired" shim that two helper
scripts still recreated on every run (appendix C). Everything below carries the
command that produced it. **If a claim here has no command next to it, do not
trust it — run something.**

**Every number in this file was measured** against the tree in this checkout, by
running the command shown. Where something was not run, it says so. The §0 cost
table, the section 6 pref checks and the section 7 gate outputs were re-measured
on **2026-08-17**; everything else dates from **2026-08-16**.

---

## 0. Before you start

### What a rebase actually costs

A rebase is not a clean-apply exercise, and the patch set is not expected to apply
without fuzz. Measured today, on `firefox-153.0.4.source.tar.xz`:

| run | patches applied | hunks needing fuzz | patches that reject at `--fuzz=0` |
|---|---|---|---|
| `./scripts/check-patchfail.sh` | 60 (24 common + 36 desktop) | **31**, across 24 patches | **23** |
| `./scripts/check-patchfail.sh --targets=android --use-desktop-tarball` | 28 (24 common + 4 android) | **13** | **12** |

Both default runs exit 0. Both `--fuzz=0` runs exit 1. **That is the healthy
state**, not a problem to fix before starting: fuzz means `patch` matched the hunk
against slightly drifted context, which is exactly what you want it to do across a
version bump. `--fuzz=0` is a *report*, not a gate.

(The board brief for this task quoted 30 fuzzy hunks and 22 zero-fuzz rejects. The
numbers above are what the same commands print today; the patch set moved under it
during the M1 wave. Re-measure rather than trusting either figure.)

### Time and disk

- ~770 MB tarball download, ~4.7 GB extracted, ~10 GB after a build's object
  directory. **Two tracks means two of everything** — the desktop tree is not
  reused (`docs/android/TRACK.md` §6).
- `check-patchfail` extracts its own throwaway copy each run: ~2 minutes per run
  including the extract. It is safe to run concurrently with anything else.
- A full `./mach build` for one ABI was 22 minutes and peaked at 31 GB of
  anonymous memory (`docs/android/BUILD.md`). Budget accordingly.

### Read first

- [`AGENTS.md`](AGENTS.md) — the five landmines. L1 (WebGL) and L2 (pref
  precedence) both re-arm on every rebase.
- [`TRACK.md`](TRACK.md) — why Android is on ESR and what that costs.
- [`PATCH-SCOPE.md`](PATCH-SCOPE.md) — which patches reach Android and why.

---

## 1. Decide there is a rebase to do

**Nothing in this repository watches the ESR channel.** `make check` runs
`scripts/update-version.py`, which walks the *desktop* Firefox release series
with `curl -I` and, when it finds a newer one, writes **two** files in the repo
root: `./version` (`open('./version', 'w')`) **and** `./release`, through
`exec('echo 1 > release')` on the next line. It touches neither
`version.android` nor `release.android`, and there is no `make check-android`.
This is deliberate — an ESR dot release should be adopted by a human who has read
the advisory — but it means the trigger is manual.

(Two details worth knowing before you read a diff it produced: it writes
`./version` **without a trailing newline**, and it only writes anything at all
when the version it found differs from the one on disk. Do not treat a
no-write run as "checked and up to date on the Android track" — it never looked
at the ESR channel.)

Check these two first, in this order:

1. **<https://whattrainisitnow.com/calendar/>** — the "Matching ESR" column gives
   the ESR point release scheduled against each Firefox major. Under the two-week
   cadence that is roughly every fortnight.
2. **<https://www.mozilla.org/en-US/security/advisories/>** — find the MFSA for the
   new ESR and read it. You need to know what you are shipping.

Then check the one thing ESR does not give you:

3. **Any advisory titled "Security Vulnerabilities fixed in Firefox for Android"**
   with no ESR counterpart. There is no Firefox for Android ESR channel, so
   Android-layer fixes are never uplifted to `mozilla-esr153` (`TRACK.md` §3c).
   Each one has to be triaged by hand and either backported into our tree or
   published as a known gap. **Do not skip this because the rebase itself is
   clean** — a clean rebase says nothing about an Android-only CVE.

> ⚠️ **Do not run `make check` during an Android rebase.** It bumps the *desktop*
> track's `./version` and will put an unrelated desktop version bump in your
> rebase commit.

---

## 2. Bump the Android track

Two files, edited by hand:

```sh
printf '153.1esr\n' > version.android     # the new ESR version, exactly as
                                          # archive.mozilla.org spells it
printf '1\n'        > release.android     # reset to 1 on any version change
```

`release.android` is the LibreWolf build number *within* a Firefox version. Bump it
(and only it) when re-cutting the same Firefox with a patch or settings change; reset
it to `1` whenever `version.android` changes.

Confirm the Makefile picked both up:

```sh
make help TARGETS=android | grep -A5 'Release track'
```

Expected: the `android tracks Firefox ESR` line shows the new pair, and
`in effect for this invocation` shows the same pair. If it shows the desktop pair,
`TARGETS` did not reach the Makefile.

Nothing else needs editing for a version bump. `$(ff_source_tarball)`,
`$(ff_source_url)`, `$(lw_source_dir)` and `$(version_files)` are all derived from
those two files (`Makefile:44-65, 121-129, 193`).

---

## 3. Fetch and verify the tarball

```sh
make fetch TARGETS=android
```

Dry-run it first if you want to see what it will do — `make -n` is a real dry run
in this Makefile and touches nothing:

```sh
make -n fetch TARGETS=android
```

which prints (verified today, with `version.android` = `153.0esr`):

```
curl -so public_key.asc "https://keys.openpgp.org/vks/v1/by-fingerprint/14F26682D0916CDD81E37B6D61B7B526D98F0353"
gpg --import public_key.asc
rm -f public_key.asc
curl -so firefox-153.0esr.source.tar.xz.asc "https://archive.mozilla.org/pub/firefox/releases/153.0esr/source/firefox-153.0esr.source.tar.xz.asc"
curl -so firefox-153.0esr.source.tar.xz "https://archive.mozilla.org/pub/firefox/releases/153.0esr/source/firefox-153.0esr.source.tar.xz"
gpg --verify firefox-153.0esr.source.tar.xz.asc firefox-153.0esr.source.tar.xz
```

Three things to know about that recipe:

- **The key is pinned by fingerprint** (`14F2 6682 D091 6CDD 81E3 7B6D 61B7 B526
  D98F 0353`, Mozilla's release signing key) in the URL, so the import is not
  trust-on-first-use. Check the fingerprint in the `gpg --import` output against
  that string. If it differs, stop.
- **No ESR-specific `FF_CHANNEL` is needed.** ESR tarballs live under the same
  `releases/<version>/source/` layout as a release build; `153.1esr` is just a
  version string to `archive.mozilla.org`.
- **`curl` has no `--fail` here**, so a 404 saves the error body as the tarball.
  You will find out at `gpg --verify`, which fails loudly. If gpg reports "no
  valid OpenPGP data", check the URL exists before suspecting the signature.

### The artifact name is not the directory name

`firefox-153.0esr.source.tar.xz` unpacks to **`firefox-153.0/`**, not to
`firefox-153.0esr/`. Mozilla does not keep the two in step.

LW-M0-14 made the Makefile *derive* the directory from the tarball rather than
assume it — `$(ff_tarball_dir)` runs `tar tf … | awk` at recipe time and takes the
first real member. Before that, `make dir TARGETS=android` died on
`mv firefox-153.0esr librewolf-153.0esr-1` after the download and the extract, which
is the expensive place to find out.

**What this means for you:**

- Do not hardcode `firefox-$(cat version.android)` in anything you write during a
  rebase. Ask the tarball:
  ```sh
  tar tf firefox-153.1esr.source.tar.xz | head -3
  ```
- `make clean` removes both the derived name and the guessed one, so it works
  whichever way the next ESR is packaged — but only while the tarball is still on
  disk to ask. Run `make clean` before `make distclean`, never the other way.
- If a future ESR *does* unpack to a matching name, nothing changes; the derivation
  yields the same string.

---

## 4. Check the patches — both targets

Run both. The Android list is 28 patches, of which 24 are shared with desktop, so a
desktop-only check tells you almost nothing about Android and vice versa.

```sh
./scripts/check-patchfail.sh --targets=desktop          > patchfail-desktop.out 2>&1; echo $?
./scripts/check-patchfail.sh --targets=android          > patchfail-android.out 2>&1; echo $?
```

Both must exit **0**.

`check-patchfail.sh` extracts the tarball into its own `mktemp -d` scratch
directory under the repo root and removes it on every exit path, including `^C`. It
never touches a shared tree and two runs cannot collide, so run them in parallel if
you like.

**Which tarball each run wants:** the desktop run wants
`firefox-$(cat version).source.tar.xz`; the android run wants
`firefox-$(cat version.android).source.tar.xz`. The script refuses to download
either — it is run casually and must not start a 766 MB fetch. If the ESR tarball
is not on disk yet:

```sh
./scripts/check-patchfail.sh --targets=android --use-desktop-tarball
```

This is the deliberate escape hatch for checking the Android list before the real
base has landed. It prints a loud `!!! WARNING` at the top *and* at the bottom, and
its result is **indicative only** — you are testing the Android patches against the
wrong Firefox. Never accept a rebase on the strength of a `--use-desktop-tarball`
run.

### Reading the output

- **`success: All patches where applied successfully.`** and exit 0 — done, go to
  step 5's zero-fuzz report.
- **`Hunk #N succeeded at … with fuzz M`** — normal. 31 of these on desktop today.
- **`error: Some patches failed!`** with a list of `[patches/…]` — real rejects.
  Go to step 5.

`check-patchfail.sh` uses `patch`'s **exit status** as the authoritative signal and
captures stderr; the `.rej` scan is a second signal. That matters because a hunk
whose target file was *renamed upstream* — the most common shape of rebase
breakage — makes `patch` print "can't find file to patch" on stderr, write no
`.rej`, and exit 1. The pre-LW-M0-11 version grepped stdout for `rej$` and reported
success (landmine L5). If you ever add a check of your own here, do not reinvent
that bug.

### The zero-fuzz report

```sh
make check-fuzz          # -sh -c "./scripts/check-patchfail.sh --fuzz=0" > patchfail-fuzz.out
```

**`make check-fuzz` exits 0, always — its exit status carries no information.**
The recipe (`Makefile:462-463`) is prefixed with `-`, so make ignores the
status: the underlying `check-patchfail.sh --fuzz=0` does exit 1 (23 desktop
patches and 12 Android patches reject at zero fuzz today), make prints
`make: [Makefile:463: check-fuzz] Error 1 (ignored)` and returns 0. That is
deliberate — a non-zero exit here is not a failure — but it means you cannot
gate on `make check-fuzz`. Read `patchfail-fuzz.out` as a worklist of patches
whose context has drifted far enough to be worth regenerating, not as a red
build.

And note what it covers: `make check-fuzz` passes no `--targets`, so
`patchfail-fuzz.out` is the **desktop** worklist only. For the Android one — and
for a status you can branch on — call the script rather than the target:

```sh
./scripts/check-patchfail.sh --fuzz=0 --targets=android > patchfail-fuzz-android.out 2>&1
echo $?                  # 1 today, and that is the healthy state
```

(Add `--use-desktop-tarball` if the ESR tarball is not on disk yet; the result is
then indicative only, exactly as in step 4.)

---

## 5. Fix the rejects

### 5a. Fuzz that is worth regenerating

```sh
make fixfuzz             # ./scripts/fuzzfail.sh
```

For each patch that rejects at `--fuzz=0`, this rebuilds it at zero fuzz through
`scripts/git-patchtree.sh` and writes the result next to it as `<patch>.nofuzz`. It
classifies three ways:

| `patch` result | meaning | what fuzzfail does |
|---|---|---|
| exit 0 | clean at zero fuzz | nothing |
| `.rej` written | ordinary fuzz or a real reject | regenerate `<patch>.nofuzz` |
| **exit ≠ 0 and no `.rej`** | the landmine-L5 shape: the target file is gone | **report, never regenerate** |

The third row is the important one. There is nothing to regenerate against when the
file has been renamed or deleted upstream, and a `.nofuzz` written anyway would be
a confident wrong answer. Those patches are listed under `patches that need a
human, not a fuzz rebuild:` and are step 5b's work.

Review each `.nofuzz` before promoting it:

```sh
diff -u patches/foo.patch patches/foo.patch.nofuzz
mv patches/foo.patch.nofuzz patches/foo.patch
```

Then re-run step 4 and confirm the fuzz count dropped.

> **Dependency: LW-M1-16.** `make fixfuzz` had stopped regenerating anything at
> all — `fuzzfail.sh` was still calling `git-patchtree.sh` in the bare form that
> LW-M1-15 removed, so every fuzzy patch came back as "needs a human" and the run
> wrote no `.nofuzz`. It slipped because the verify was `make -n fixfuzz`, which
> prints commands without running any, and so cannot see a runtime failure.
>
> This runbook is written against the intended behaviour. **What was verified for
> this file:** the working-tree copies of both scripts carry the fixes — no
> `git config` call remains anywhere in `fuzzfail.sh`, and it drives
> `git-patchtree.sh` through the documented `-o` form with `--targets` and
> `--use-desktop-tarball` forwarded. **What was not verified:** a regeneration was
> not actually run for this task, because it writes `.nofuzz` files under
> `patches/`, which LW-M7-01 does not own. Before relying on `make fixfuzz` in a
> real rebase, run it once on one patch and confirm the `.nofuzz` file appears.
> A `make -n` is not a check.

> **Never re-introduce the global git-config write.** `fuzzfail.sh` used to set
> `commit.gpgsign` in the maintainer's *global* git configuration and restore it to
> a hardcoded `true`, so anyone who had it unset got commit signing switched on for
> every repository they own, and `^C` between the two calls left signing globally
> off. `git-patchtree.sh` now passes `-c commit.gpgsign=false` per invocation
> instead. A repository script must not write a user's global git settings, ever.

### 5b. Real rejects

For a patch that genuinely no longer applies, get an editable tree:

```sh
./scripts/git-patchtree.sh --edit --targets=android patches/ui-patches/neterror-common.patch
```

This builds a throwaway git repository whose first commit is the pristine files and
whose second is the patch, keeps it (with its `.rej` files) and prints the path plus
the exact `git diff` command to produce the new patch. Fix the tree by hand, diff,
write the patch back, re-run step 4.

`--targets=android` matters: without it you get a tree built from the *desktop*
tarball, and a patch regenerated against the wrong Firefox will apply cleanly in
`check-patchfail` and still be wrong.

### 5c. What you may not do

**Do not drop a patch from `common.txt` to make an error go away.** That is a
parity loss and it is the thing this project exists to avoid. If a patch truly
cannot apply on Android, record it in `PATCH-SCOPE.md` with a reason so it shows up
in the M5 parity matrix.

If you move a patch between lists, re-run `scripts/check-patch-order.py`: five pairs
share a file in the extracted tree and only apply in one order, and **two of the
five are cross-list**, so a checker comparing positions within one list cannot see
them at all. The table is in `AGENTS.md`.

---

## 6. The check a rebase actually needs: did upstream silently revert one of our prefs?

**This is the failure mode.** A patch reject is loud — `check-patchfail` prints it,
CI goes red, you cannot miss it. What you *can* miss is Mozilla changing something
about a pref such that our value stops taking effect, while every patch still
applies and every gate stays green. Nobody finds out until a user does.

There is no single tool for this today. The four checks below are what exists.
Run all four.

> **Ordering.** This section is placed here because it is the most important thing
> in the file, not because it comes next chronologically. 6a and 6c read the
> **patched** tree, which does not exist until `make dir TARGETS=android` in step 8;
> 6b needs the *old* and *new* extracted trees side by side; 6d needs a plain
> `firefox-*/` extract. In practice: do step 8, then come back here, then re-run the
> gates in step 7. Nothing in section 6 modifies anything, so running it twice is
> free.

### 6a. Prefs we set that the new tree has never heard of

The commonest silent revert is an upstream **rename or removal**. `defaultPref` on a
name nothing reads is not an error — autoconfig accepts any string — so our
hardening quietly evaporates and the pref page still shows our value.

There is no script for this in `scripts/` yet. Save the following as
`scripts/pref-orphans.sh` (see "Follow-ups" — this file does not own `scripts/`):

```sh
#!/bin/sh
# pref-orphans.sh TREE CFG...   -- names we set that the tree never mentions
set -eu
tree=$1; shift
[ $# -gt 0 ] || { echo "usage: $0 TREE CFG..." >&2; exit 2; }
[ -f "$tree/modules/libpref/init/StaticPrefList.yaml" ] || {
    echo "error: '$tree' is not a Firefox source tree" >&2; exit 2; }

s=$(mktemp -d) || exit 2
trap 'rm -rf "$s"' EXIT
trap 'rm -rf "$s"; exit 130' INT
trap 'rm -rf "$s"; exit 143' TERM

# 1. every pref name our config sets. Comments are stripped first, but only
#    when '//' is not preceded by ':' - otherwise a "https://..." value would
#    truncate the line. Newlines are folded so multi-line calls still match.
sed -E 's,([^:])//.*,\1,' "$@" \
  | tr '\n' ' ' \
  | grep -oE '(defaultPref|lockPref|clearPref|pref)[[:space:]]*\([[:space:]]*"[^"]+"' \
  | sed -E 's/.*"([^"]+)"/\1/' | sort -u > "$s/ours"

# 2. names for which the tree declares a default.
{ grep -ohE '^[[:space:]]*pref\([[:space:]]*"[^"]+"' \
      "$tree/modules/libpref/init/all.js" \
      "$tree/browser/app/profile/firefox.js" \
      "$tree/mobile/android/app/geckoview-prefs.js" 2>/dev/null \
    | sed -E 's/.*"([^"]+)"/\1/'
  grep -oE '^-?[[:space:]]*name:[[:space:]]*[A-Za-z0-9._-]+' \
      "$tree/modules/libpref/init/StaticPrefList.yaml" \
    | sed -E 's/.*name:[[:space:]]*//'
} | sort -u > "$s/declared"

comm -23 "$s/ours" "$s/declared" > "$s/candidates"

# 3. a pref needs no declared default to be real (PrefWithoutDefault), so the
#    survivors are checked against the whole tree as literal strings. -a so a
#    match inside a binary test fixture is not silently dropped.
if [ -s "$s/candidates" ]; then
    ( cd "$tree" && grep -rhoaFf "$s/candidates" . 2>/dev/null ) | sort -u > "$s/used"
else
    : > "$s/used"
fi
comm -23 "$s/candidates" "$s/used" > "$s/orphans"

n=$(grep -c . "$s/orphans" || true)
if [ "$n" -eq 0 ]; then
    printf 'pref-orphans: %s pref(s) checked, none orphaned.\n' "$(grep -c . "$s/ours")"
    exit 0
fi
printf 'pref-orphans: %s of %s pref(s) appear nowhere in %s:\n' \
    "$n" "$(grep -c . "$s/ours")" "$tree"
sed 's/^/  /' "$s/orphans"
exit 1
```

Run it against the **patched** tree, not the stock one — our own `librewolf.*`
prefs are created by our patches and will otherwise all report as orphans:

```sh
chmod +x scripts/pref-orphans.sh
./scripts/pref-orphans.sh librewolf-153.1esr-1 settings/common.cfg settings/android.cfg
./scripts/pref-orphans.sh librewolf-153.1esr-1 settings/common.cfg settings/desktop.cfg
```

**Two design decisions in that script that came out of running it, not out of
reading it:**

1. **Stage 3 has no `--include` filter.** An earlier version restricted the
   whole-tree grep to `*.cpp *.h *.js *.mjs *.yaml *.rs *.java *.kt …` and reported
   `extensions.gleanPingAddons.daily.interval` as an orphan. It is not: it is
   registered in `toolkit/mozapps/extensions/extensions.manifest`, a file type the
   filter excluded. Removing the filter entirely cost nothing measurable (2.2 s vs
   2.1 s over 468 527 files) and removed a whole class of false negative.
2. **Stage 3 exists at all.** A pref with no declared default anywhere is still a
   real pref — `PrefWithoutDefault<>("network.lna.block_trackers")` is the case
   that previously produced a confident and exactly-backwards "no lock needed".
   Stage 2 alone would have flagged 33 names today; stage 3 clears 22 of them.

**Expected output, and how to triage it.** The triage rules below were derived by
running the script against the **stock** `firefox-153.0.4/` tree with `common.cfg` +
`android.cfg` — deliberately the harder case, because a stock tree also surfaces our
own `librewolf.*` prefs and so exercises every category at once. It reported 11 of
188 prefs. That breakdown is the shape to expect every time:

| reported name | verdict |
|---|---|
| `librewolf.cfg.version`, `librewolf.console.logging_disabled`, `librewolf.debugger.force_detach`, `librewolf.eme.gmp-clearkey.enabled`, `librewolf.getBrowserInfo.setToFirefoxDefaults`, `librewolf.services.settings.allowedCollections`, `librewolf.services.settings.allowedCollectionsFromDump`, `librewolf.uBO.assetsBootstrapLocation` | **ours** — created by our own patches. Absent from a *stock* tree, present in a patched one. Run against the patched tree and these disappear. |
| `permissions.default.media-key-system-access` | **false positive** — the name is built at runtime. `extensions/permissions/PermissionManager.cpp:830` does `GetBranch("permissions.default.", …)`, so the leaf is never a literal. The permission type string `"media-key-system-access"` *is* in the tree, at `dom/media/eme/MediaKeySystemAccessPermissionRequest.cpp:42`. |
| `app.update.lastUpdateTime.glean-addons-daily` | **false positive** — `toolkit/components/timermanager/UpdateTimerManager.sys.mjs:7` builds it from the template `"app.update.lastUpdateTime.%ID%"`. |
| `network.gio.supported-protocols` | **genuine orphan.** The string `supported-protocols` appears **nowhere** in the 153.0.4 tree and `netwerk/protocol/gio/` does not exist. `settings/common.cfg:200` still sets it, commented "disable gio as it could bypass proxy". Nothing reads it. |

**The triage rule for anything this reports:** split the name at the last dot and
grep the tree for the trailing component on its own. If the suffix turns up as a
string literal somewhere, the full name is being constructed at runtime and this is
a false positive. If neither the full name nor a distinctive fragment appears
anywhere, and the subsystem directory is gone, it is a genuine orphan — find what
replaced the pref and set *that*, or delete our line and note why.

`network.gio.supported-protocols` above is a live example: it is a real
privacy-motivated setting in `settings/common.cfg` that has been doing nothing since
GIO was removed upstream. That is what this check is for, and it found one on the
very first run.

### 6b. Upstream defaults that moved

The second shape: the pref still exists, we still set it, but Mozilla changed
*their* default. Usually harmless — our `defaultPref` still wins — but it is the
signal that the surrounding behaviour changed, and it is the only way to notice
that a value we chose for a reason now means something else (an enum gaining a
member, a timeout changing units, a boolean's polarity being inverted around a
rename).

This is a **two-tree diff**, so run it while both the old and the new extracted
trees are still on disk. Save as `scripts/pref-defaults.sh`:

```sh
#!/bin/sh
# pref-defaults.sh TREE  -- "name<TAB>default" for every pref the tree declares
set -eu
tree=${1:?usage: $0 TREE}
[ -f "$tree/modules/libpref/init/StaticPrefList.yaml" ] || {
    echo "error: '$tree' is not a Firefox source tree" >&2; exit 2; }

{
  # StaticPrefList.yaml: name and value are separate keys of one mapping.
  awk '
    /^-[[:space:]]*name:[[:space:]]*/ { n = $3; v = ""; next }
    /^[[:space:]]+value:[[:space:]]*/ {
        if (n == "") next
        sub(/^[[:space:]]*value:[[:space:]]*/, "")
        sub(/[[:space:]]+#.*$/, "")
        printf "%s\t%s\n", n, $0
        n = ""
    }
  ' "$tree/modules/libpref/init/StaticPrefList.yaml"

  # the three .js default files: pref("name", value);
  cat "$tree/modules/libpref/init/all.js" \
      "$tree/browser/app/profile/firefox.js" \
      "$tree/mobile/android/app/geckoview-prefs.js" 2>/dev/null \
  | sed -nE 's/^[[:space:]]*pref\([[:space:]]*"([^"]+)"[[:space:]]*,[[:space:]]*(.*)\)[[:space:]]*;.*$/\1\t\2/p'
} | sort -u
```

Then:

```sh
./scripts/pref-defaults.sh librewolf-153.0esr-1 > /tmp/defaults-old.tsv   # the tree you are leaving
./scripts/pref-defaults.sh librewolf-153.1esr-1 > /tmp/defaults-new.tsv   # the tree you are moving to

# names whose upstream default row changed at all
comm -3 /tmp/defaults-old.tsv /tmp/defaults-new.tsv | sed -E 's/^\t//' | cut -f1 | sort -u > /tmp/drifted.txt

# every pref name our config sets. Same extraction as stage 1 of pref-orphans.sh;
# 6c wants this file too, so it is written to /tmp/ours.txt rather than piped.
sed -E 's,([^:])//.*,\1,' settings/common.cfg settings/android.cfg | tr '\n' ' ' \
  | grep -oE '(defaultPref|lockPref|clearPref|pref)[[:space:]]*\([[:space:]]*"[^"]+"' \
  | sed -E 's/.*"([^"]+)"/\1/' | sort -u > /tmp/ours.txt

# the drifted ones that are ours — this is the list to read line by line
comm -12 /tmp/drifted.txt /tmp/ours.txt
```

`/tmp/ours.txt` is 188 names today (`common.cfg` + `android.cfg`). Swap in
`settings/desktop.cfg` for the desktop answer.

The final `comm` prints the prefs where **we have an opinion and Mozilla changed
theirs**. It is normally a handful of lines. Read every one and decide whether our
value still expresses what we meant.

Notes from running this:

- It produces 6 299 rows on 153.0.4. Duplicate rows for one name are normal and
  expected — `network.cookie.cookieBehavior` appears as `0` (StaticPrefList) and `5`
  (`firefox.js`), `toolkit.telemetry.unified` as both `false` and `true` from two
  `#ifdef` branches. The check is a *diff of two trees produced the same way*, so
  duplicates cancel.
- The pipeline was verified end to end by flipping two known values in a synthetic
  "old" file and confirming both names came out of the final `comm` — not by
  reading it.

### 6c. Prefs that became `mirror: once`

A `StaticPrefList.yaml` entry with `mirror: once` snapshots its value into a C++
variable the first time the accessor runs. There is no guarantee that happens after
autoconfig has evaluated `librewolf.cfg`. A pref that *moves into* that category
upstream can therefore keep showing our value in `about:config` while the code that
matters uses Mozilla's.

```sh
# /tmp/ours.txt again — repeated so this block runs on its own, without 6b.
sed -E 's,([^:])//.*,\1,' settings/common.cfg settings/android.cfg | tr '\n' ' ' \
  | grep -oE '(defaultPref|lockPref|clearPref|pref)[[:space:]]*\([[:space:]]*"[^"]+"' \
  | sed -E 's/.*"([^"]+)"/\1/' | sort -u > /tmp/ours.txt

awk '/^- name:/{n=$3} /mirror: once/{print n}' \
    librewolf-153.1esr-1/modules/libpref/init/StaticPrefList.yaml | sort -u > /tmp/mirror-once.txt
comm -12 /tmp/ours.txt /tmp/mirror-once.txt
```

**Expected output: empty.** On 153.0.4 there are 198 `mirror: once` entries (185
distinct names) and **none** of them is a pref we set (re-measured 2026-08-17).
Any line here is a real finding and needs a per-pref decision, not a bulk answer.

### 6d. Prefs Fenix overwrites at runtime — landmine L2

This is the Android-specific silent revert, and a rebase is exactly when it appears:
Mozilla adds a `Pref<>` field to `GeckoRuntimeSettings.java` or
`ContentBlocking.java` for a pref we already ship. Our value survives startup and is
then overwritten the moment Fenix's settings load, because `MOZ_DEFAULT_PREFS`
cannot express a lock at all (there is no `locked_pref` token in the parser —
`AGENTS.md` L2).

**Name the tree. Do not let the gate look for one.**

```sh
mkdir -p /tmp/rebase-tree && tar -xf firefox-153.1esr.source.tar.xz -C /tmp/rebase-tree
LW_TREE=/tmp/rebase-tree/firefox-153.1 python3 docs/android/board.py --check-policies
```

`LW_TREE` takes any path, inside the repo or outside it, absolute or relative to
the repo root (all three verified). Without it the gate globs `firefox-*/mobile`
under the repo root, which is fine when exactly one tree is there and an error
when more than one is — see trap 2.

Expected output, both lines:

```
# reading pref declarations from firefox-153.1
ok: 101 prefs declared by GeckoView; 21 of them shipped by us, all acknowledged as needing a lock
```

It re-derives the declarations from the tree on every run, so it picks up a new
one automatically.

**Three things to know about this gate. All three were confirmed by running it,
not by reading it — one of them used to be documented backwards for exactly that
reason (trap 2).**

1. **It fails open when no tree is present.** With no `firefox-*/` directory under
   the repo root and no `LW_TREE`, it prints
   `warn:  no extracted Firefox tree found — cannot check pref declarations`
   and **exits 0**. And `make dir` *moves* the extracted tree to
   `librewolf-<version>-<release>/`, which the glob does not match — so after a
   normal rebase there is no tree left for it to find and this gate passes
   vacuously. **Insist on `ok:` in the output**; exit 0 alone does not distinguish
   "checked and clean" from "did not check". Passing `LW_TREE` removes the trap
   entirely: a path with no `mobile/` directory is an error (exit 2), not a warning.
2. **Two trees on disk is an error, not a coin flip.** The gate used to take the
   first `firefox-*` match in sort order and never say which, so on a builder that
   had both the desktop tree and the ESR tree it silently answered about the wrong
   one. It now refuses:
   ```
   error: more than one extracted Firefox tree — refusing to guess which one this check should read:
            /home/you/librewolf/firefox-153.0
            /home/you/librewolf/firefox-153.0.4
          set LW_TREE=<one of these> and re-run
   ```
   and exits **2**. So the fix for the old trap — engineering a name that sorts
   first — is not only unnecessary, it now *causes* the failure. Do not do it.
   Set `LW_TREE` and read the `# reading pref declarations from …` line the gate
   prints; that line is the answer to "which tree did it check", and it prints on
   every successful run.

   > The old workaround rested on a false mechanism, which is worth recording so
   > nobody re-derives it: `sorted()` here sorts `pathlib.Path` objects, and those
   > compare as tuples of path *parts*, so `/` is never compared as a character at
   > all. The claim that `firefox-153.0.4` wins because `.` (0x2E) sorts before `/`
   > (0x2F) is backwards — executed on real directories, `firefox-153.0` sorts
   > first, as the error message above (produced by a real run against two trees)
   > shows. A string-sort intuition applied to `Path` objects is how that got
   > written down; check the type before reasoning about the order.
3. **A nonsense parse still prints `ok:`.** The gate only errors when it finds
   *zero* `Pref<>` declarations. Pointed at a tree containing exactly one, it
   printed `ok: 1 prefs declared by GeckoView; 0 of them shipped by us, all
   acknowledged as needing a lock` and exited 0 (verified 2026-08-17 against a
   hand-built one-declaration tree). So read the count: **101 today.** A sudden
   drop to a handful means it parsed the wrong tree or the GeckoView layout moved,
   not that the risk went away.

### 6e. What does *not* exist yet — say so out loud

**`scripts/android-pref-audit.sh` (LW-M3-05) does not exist.** Neither does
`docs/android/expected-prefs.txt`. The task that owns them is the runtime pref
audit: launch the app, walk every settings screen without toggling anything, dump
the *effective* value of every pref we ship, and diff against a checked-in baseline.
That is the only check that would catch a revert happening at runtime rather than in
source — which is precisely the L2 shape 6d can only *predict* from a Java
declaration.

Until it lands, sections 6a–6d are static analysis of source files. They cannot see:

- a pref whose effective value differs from its declared default because something
  writes it during startup;
- a Fenix code path that writes a pref without declaring it in one of the two
  classes `--check-policies` parses;
- any pref set through `GeckoRuntimeSettings` builder methods rather than a
  `Pref<>` field.

**Do not record a rebase as pref-verified on the strength of 6a–6d.** Record it as
"source-level pref checks clean; runtime audit not available (LW-M3-05)".

`./scripts/android-smoke.sh` (LW-M2-07) does not exist either. When it does, the
rebase gate list gains `./scripts/android-smoke.sh --emulator` and
`./scripts/android-pref-audit.sh`, and `AGENTS.md`'s definition of done already
names both.

The one runtime check you can do by hand today, and should, is **landmine L1**:
confirm `librewolf.webgl.prompt` compiled to `false`.

```sh
grep -rn 'webgl.prompt' librewolf-153.1esr-1/obj-*/dist/include/mozilla/StaticPrefList_librewolf.h
```

If it says `true`, every WebGL context on Android fails — with no crash and no
console error, and a smoke test of "installs and browses" still passes. Check the
generated header, not the patch: "it compiles to false in the generated header"
beats "the patch sets it to false".

---

## 7. Run the gates

All eight must be green. Run them from the repo root.

```sh
esr_tree=/tmp/rebase-tree/firefox-153.1                # edit: the ESR tree 6d extracted

python3 docs/android/board.py --check                  # board integrity
python3 docs/android/board.py --check-scope            # lists vs PATCH-SCOPE.md
python3 docs/android/board.py --check-cfg-split        # common+desktop+android == librewolf.cfg
LW_TREE="$esr_tree" \
  python3 docs/android/board.py --check-policies       # landmine L2 — name the tree, see 6d
python3 docs/android/board.py --diff-mozconfig         # no hardening flag silently dropped
python3 scripts/lint-patch-scope.py                    # no desktop-only file in a common patch
python3 scripts/check-patch-order.py                   # the five ordering constraints
./scripts/check-patchfail.sh --targets=android         # every Android patch still applies
```

Expected output on a clean tree (measured 2026-08-17, with the 153.0.4 tree
extracted in the repo root):

```
ok: 79 tasks, 17 waves, 0 warning(s)
ok: 64 patch files — 24 common, 36 desktop, 4 android, 0 straddlers parked; PATCH-SCOPE.md agrees
ok: 182 common / 85 desktop / 2 android calls; librewolf.cfg regenerates exactly
# reading pref declarations from firefox-153.0.4
ok: 101 prefs declared by GeckoView; 21 of them shipped by us, all acknowledged as needing a lock
ok: hardening parity holds (0 documented difference(s))
lint-patch-scope: OK - 64 patch file(s), no scope violations
patch order ok: 5/5 declared constraint(s) enforced across 2 target sequence(s); 36 shared-file pair(s) derived and classified.
success: All patches where applied successfully.
```

The task count in the first line moves whenever the board does — read it as "the
gate ran", not as a fixture.

`--diff-mozconfig` is the one people forget. It compares `assets/mozconfig.android`
against `assets/mozconfig` and fails when a hardening flag present on desktop is
missing on Android without a documented reason. A new ESR that adds a
`--disable-…` option desktop picks up and Android does not is exactly the drift it
exists to catch. It no longer accepts a flag's mere *mention* in a comment as an
excuse for its absence: an omission has to carry an explicit
`MOZCONFIG-OMIT: <name>` marker, or the gate fails.

**Read the words, not just the exit status.** `--check-policies` still has a
pass-that-did-not-check state (no tree at all, section 6d trap 1) — which is why
the run above names the tree — and `check-patchfail` exits 0 on a
`--use-desktop-tarball` run that tested the wrong Firefox. An exit code of 0 is
necessary and not sufficient.

---

## 8. Build

```sh
make dir TARGETS=android
```

This re-extracts (the `$(version_files)` prerequisite changed), moves the tree to
`librewolf-153.1esr-1/` and runs
`python3 scripts/librewolf-patches.py 153.1esr 1 --targets=android`, which applies
`assets/patches/common.txt` then `assets/patches/android.txt` and exits 1 on the
first patch that does not apply.

Watch its output for the mutations that are **not** patches and that
`check-patchfail` cannot see (landmine L4):

- the OpenAI deletions against `toolkit/components/ml/` — these assert, so a
  rename upstream is a loud failure;
- the l10n fetch — pinned by commit and sha256 in `assets/l10n-pin.txt`. If a
  rebase needs newer strings, bump the pin using the procedure written in the head
  of that file, and **do not refresh the hash without diffing the trees**;
- the search-config and icon file copies, and the `version.txt` rewrite — still
  bare `cp`, so an upstream rename fails *open*: the build succeeds and the change
  silently does not happen. If you touch a path in that area, make it assert.

Then build per [`BUILD.md`](BUILD.md) — the container, the `lw/l10n` directory, the
SELinux `:z` mount suffix and the `-j` guidance are all there and are not repeated
here.

```sh
podman build -f assets/Dockerfile.android -t librewolf-android-build .
# … then the sequence in BUILD.md §3-§5, ending in ./mach build
```

A green `./mach build` for one ABI is ~22 minutes and ~31 GB of anonymous memory.
Three ABIs is closer to 3× than 1×.

---

## 9. Sign and publish

**Nothing in this section is implemented yet.** Written now so the rebase procedure
is complete when it is, and so nobody improvises the parts that must not be
improvised.

### The rules that already bind

- **The signing key never exists in CI, in a container image, or in any
  repository.** CI produces an *unsigned* APK plus published sha256 sums; a
  maintainer signs offline on their own machine as a separate step. That boundary
  is structural, not a convention (`LW-M6-05`), and one convenience commit putting
  the key in CI undoes the whole custody model (`LW-M6-01`).
- **Only signed releases are published.** Publishing without a signature is blocked,
  not discouraged. The desktop source release already works this way — see
  `.forgejo/workflows/source-release.yaml` and commit `71177a3`.
- **The `applicationId` and the signing key are never changed.** Either one strands
  every installed user with no upgrade path, and Android has no key recovery outside
  Play App Signing, which we do not use.

### What is owed, and by whom

| piece | task | status |
|---|---|---|
| release keystore + custody policy (`docs/android/SIGNING.md`) | LW-M6-01 | not started — needs a two-maintainer ceremony, not an agent |
| reproducible build + verification | LW-M6-02 | not started |
| LibreWolf F-Droid repository | LW-M6-03 | not started |
| Accrescent, direct APK, Obtainium metadata | LW-M6-04 | not started |
| `.forgejo/workflows/android-release.yaml` | LW-M6-05 | not started |
| in-app update checking | LW-M6-06 | not started |

Until LW-M6-05 exists there is no Android release workflow at all.
`.forgejo/workflows/android-test.yaml` is a *patch-set check* — it fetches the ESR
tarball, runs the board check, the scope lint, the order check, `check-patchfail
--targets=android` and `make dir TARGETS=android`, and it deliberately builds no
Gecko and references no secrets. It will go green on a rebase pull request without
proving anything about an APK.

### Interim procedure for a rebase before M6 lands

1. Push the rebase branch; `android-test.yaml` runs the patch-set check on it.
2. Build locally per step 8 and record the result in the pull request: `./mach
   build` exit status, the L1 header check from 6e, and the outputs of all eight
   gates.
3. Do **not** publish an artifact. There is no signing key and no distribution
   channel yet.

---

## 10. Record the rebase

In the pull request, state:

- old and new `version.android` / `release.android`;
- the MFSA the new ESR carries, and **any Firefox-for-Android advisory with no ESR
  counterpart** that is still open against our tree (step 1.3);
- the two `check-patchfail` runs, with exit status and whether the Android one used
  `--use-desktop-tarball`;
- fuzz counts before and after, and every patch you regenerated or hand-fixed;
- the output of the four pref checks in section 6, **including which of them did not
  run**;
- the eight gate outputs;
- `./mach build` status and the `librewolf.webgl.prompt` header check.

Do not soften the parity wording. Redoubt has a weaker process
sandbox than LibreWolf desktop, ESR is a median of 14 days (worst observed 21)
behind release on out-of-band Gecko fixes, and there is no Firefox for Android ESR
channel at all. Those stay stated.

---

## Appendix A — the whole thing as one block

In execution order, which is not quite section order: the pref checks need the
patched tree, so `make dir` comes before them.

```sh
# 1. decide (manual: whattrainisitnow calendar + MFSA index + Android-only advisories)

# 2. bump
printf '153.1esr\n' > version.android
printf '1\n'        > release.android
make help TARGETS=android | grep -A5 'Release track'   # confirm the pair is in effect

# 3. fetch + verify
make fetch TARGETS=android

# 4. check patches, both targets
./scripts/check-patchfail.sh --targets=desktop; echo "desktop=$?"   # want 0
./scripts/check-patchfail.sh --targets=android; echo "android=$?"   # want 0
make check-fuzz                        # ALWAYS exits 0 (`-` in the recipe); the
                                       # signal is patchfail-fuzz.out, not $?
./scripts/check-patchfail.sh --fuzz=0 --targets=android > patchfail-fuzz-android.out 2>&1
echo "android fuzz0=$?"                # 1 today, and that is healthy

# 5. fix rejects
make fixfuzz                           # review each .nofuzz before promoting it
# ./scripts/git-patchtree.sh --edit --targets=android <patch>   # for real rejects
# then re-run step 4 and confirm the fuzz count dropped

# 7. gates (first pass — everything that does not need a tree)
python3 docs/android/board.py --check
python3 docs/android/board.py --check-scope
python3 docs/android/board.py --check-cfg-split
python3 docs/android/board.py --diff-mozconfig
python3 scripts/lint-patch-scope.py
python3 scripts/check-patch-order.py
./scripts/check-patchfail.sh --targets=android
# the eighth gate, --check-policies, needs a tree and is run in the 6d block below

# 8. patch the tree, then build
make dir TARGETS=android               # leaves librewolf-153.1esr-1/
# … then BUILD.md for the container build
grep -rn 'webgl.prompt' librewolf-153.1esr-1/obj-*/dist/include/mozilla/StaticPrefList_librewolf.h

# 6. prefs — needs the patched tree above
#    (neither pref-*.sh exists in scripts/ yet; copy both out of section 6 first)
./scripts/pref-orphans.sh librewolf-153.1esr-1 settings/common.cfg settings/android.cfg
./scripts/pref-orphans.sh librewolf-153.1esr-1 settings/common.cfg settings/desktop.cfg

#    6b/6c share this list of every pref name we set
sed -E 's,([^:])//.*,\1,' settings/common.cfg settings/android.cfg | tr '\n' ' ' \
  | grep -oE '(defaultPref|lockPref|clearPref|pref)[[:space:]]*\([[:space:]]*"[^"]+"' \
  | sed -E 's/.*"([^"]+)"/\1/' | sort -u > /tmp/ours.txt

#    6b — upstream defaults that moved (needs BOTH trees still on disk)
old_tree=librewolf-153.0esr-1                    # edit: the tree you are leaving
new_tree=librewolf-153.1esr-1                    # edit: the tree you are moving to
./scripts/pref-defaults.sh "$old_tree" > /tmp/defaults-old.tsv
./scripts/pref-defaults.sh "$new_tree" > /tmp/defaults-new.tsv
comm -3 /tmp/defaults-old.tsv /tmp/defaults-new.tsv | sed -E 's/^\t//' | cut -f1 | sort -u > /tmp/drifted.txt
comm -12 /tmp/drifted.txt /tmp/ours.txt          # read every line

#    6c — prefs that became `mirror: once`. Expected output: empty.
awk '/^- name:/{n=$3} /mirror: once/{print n}' \
    librewolf-153.1esr-1/modules/libpref/init/StaticPrefList.yaml | sort -u > /tmp/mirror-once.txt
comm -12 /tmp/ours.txt /tmp/mirror-once.txt

#    6d needs a plain firefox tree, which `make dir` consumed. Re-extract one and
#    NAME it — do not drop it in the repo root next to the desktop tree, because
#    two firefox-*/ directories now make this gate error out (6d trap 2).
mkdir -p /tmp/rebase-tree && tar -xf firefox-153.1esr.source.tar.xz -C /tmp/rebase-tree
LW_TREE=/tmp/rebase-tree/firefox-153.1 python3 docs/android/board.py --check-policies
# want: "# reading pref declarations from firefox-153.1" then "ok: … prefs declared"

# 9. sign + publish — not implemented (LW-M6-01..06)
# 10. record everything in the pull request
```

---

## Appendix B — what each gate cannot see

Keep this honest; it is the difference between a rebase that was checked and one
that merely went green.

| gate | blind to |
|---|---|
| `check-patchfail.sh` | anything `scripts/librewolf-patches.py` does outside the patch lists — the `cp`s and the `version.txt` rewrite (L4). With `--use-desktop-tarball`, blind to the actual ESR tree. |
| `check-fuzz` (`--fuzz=0`) | nothing about correctness — it reports drift. And `make check-fuzz` is blind to its own result: the recipe is `-`-prefixed, so the target exits 0 whatever the script did. |
| `lint-patch-scope.py` | prefs, build flags, runtime behaviour. It answers one question: is a desktop-only file inside a common patch. |
| `check-patch-order.py` | the *direction* of a new constraint. It flags new shared-file pairs for review; the five declared constraints are a table, not a derivation. |
| `board.py --check-scope` | whether a patch still applies. It compares lists to a document. |
| `board.py --check-cfg-split` | whether the prefs still exist upstream. It proves the three `.cfg` files reassemble into `librewolf.cfg`, nothing more. |
| `board.py --check-policies` | anything, if no `firefox-*/` tree is present and no `LW_TREE` is set — it warns and exits 0. It no longer guesses between several trees (that is an error now), but it also cannot tell you the tree you named is the right one: read the `# reading pref declarations from …` line it prints. |
| `board.py --diff-mozconfig` | flags that exist on both sides but changed meaning upstream. |
| **all of them** | a pref whose *effective runtime value* is wrong. That is LW-M3-05, and it does not exist. |

---

## Appendix C — `assets/patches.txt` is gone

`assets/patches.txt` was a generated `common + desktop` concatenation, kept after
LW-M0-02 split the monolith so out-of-tree builders had one file to read. **It has
been deleted.** During a rebase there is nothing to regenerate and nothing to keep
in sync: the lists the build reads are

```
assets/patches/common.txt     24 entries — applied to every target
assets/patches/desktop.txt    36 entries — desktop builds only
assets/patches/android.txt     4 entries — Android builds only
```

`scripts/librewolf-patches.py` reads `assets/patches/*.txt` directly, and LW-M1-11
taught `check-patchfail.sh` and `fuzzfail.sh` the target lists, so no build,
workflow, container image or test consumed the shim by the time it was removed. The
`Makefile` says so explicitly in the comment above `patch_lists :=` ("a generated
shim … that nothing in this recipe reads any more, so it is deliberately not a
prerequisite"), and the source release tars `$(lw_source_dir)` — the patched Firefox
tree — not this repository, so the shim never reached a downstream builder through
`make all` either.

### The code that produced and consumed it is gone too

Deleting the file was only half the retirement. Three of the four scripts that
touched it needed changing, and until they were, the deletion did not hold: two
of them wrote the file back unconditionally, on every run.

(Function names, not line numbers — this set of scripts has been edited by a dozen
tasks and any number quoted here would already be wrong.)

| file | what it did | state now |
|---|---|---|
| `scripts/enable-patch.sh` — `regenerate_shim()`, called at the end of every run | wrote the file after every edit, with no existence guard | **removed** (function, `SHIM` variable, call site and the "Regenerated the …" line). |
| `scripts/disable-patch.sh` — the same function, same call site | same | **removed**, same four pieces. |
| `scripts/librewolf-patches.py` — `check_compat_shim()`, called from `librewolf_patches()` | read it to warn on membership drift; with the file gone it printed `warning: can't read … No such file or directory` on every invocation | **removed**, function and call. |
| `scripts/check-patchfail.sh` — the `shim_warn` block and the warning it prints at the end | reads it for a set-membership drift warning | **inert, not removed.** The read is guarded by `[ -f … ]`, so with the file gone the warning cannot fire. It is dead code in a file no task in this thread owns; see follow-up 6. |

**How that was proved, in both directions** (2026-08-17, all in a scratch copy of
the repo so nothing here changed):

- *Before:* `./scripts/disable-patch.sh --list desktop patches/msix.patch` in a
  scratch tree with no `assets/patches.txt` **created** a 59-line
  `assets/patches.txt`. The resurrection was real, not theoretical.
- *After:* enabling a probe patch and then disabling it again — once for each of
  `common`, `desktop` and `android` — left all three list files **byte-identical**
  to their starting state (`sha256sum -c`, three OKs per round trip) and created
  no `assets/patches.txt`. The ordering-insertion path was exercised too
  (removing `autoconfig-setEnv` and re-adding it puts it back *before*
  `profile-directory`, as the constraint requires) and it also leaves no shim.
- *Patcher:* `python3 scripts/librewolf-patches.py -n 153.0esr 1 --targets=android`
  and the desktop equivalent now both exit 0 with **no** `warning:` line of any
  kind.
- *check-patchfail:* a full `./scripts/check-patchfail.sh --targets=desktop` run
  exits 0 and prints no `patches.txt` line at all.

If you ever find `assets/patches.txt` back on disk, something regenerated it.
Delete it and find what wrote it — there is no longer any code that is supposed
to.

---

## Follow-ups this file could not make itself

LW-M7-01 owned `docs/android/REBASE.md` and `assets/patches.txt`; the correction
pass that followed it also owned `scripts/librewolf-patches.py`,
`scripts/enable-patch.sh` and `scripts/disable-patch.sh`. Everything below belongs
to a file neither owned, and is recorded here so it is not lost:

1. **`scripts/pref-orphans.sh` and `scripts/pref-defaults.sh`** are embedded in
   section 6 rather than added to `scripts/`. Both were written and run for this
   task; `pref-orphans.sh` was tested on its clean path (exit 0), its finding path
   (exit 1 with the name printed) and both error paths (not-a-tree and no-cfg, exit
   2). They should become real scripts and be wired into
   `.forgejo/workflows/android-test.yaml`.
2. **`network.gio.supported-protocols` in `settings/common.cfg:200` is dead** —
   `netwerk/protocol/gio/` does not exist in Firefox 153 and the string
   `supported-protocols` appears nowhere in the tree. It belongs to the `settings`
   submodule, which needs its own pull request.
3. **`board.py --check-policies` still fails open when there is no tree at all.**
   The tree-guessing half of this is **fixed** — ambiguity is an error, `LW_TREE`
   overrides, and the chosen tree is printed (6d) — but with no tree and no
   `LW_TREE` it still warns and exits 0. Remaining fix in `board.py`: exit
   non-zero, or make the tree mandatory.
4. **`.forgejo/workflows/android-test.yaml` runs four of the eight gates** —
   `board.py --check`, `lint-patch-scope.py` (still wrapped as advisory, though it
   passes today), `check-patch-order.py` and `check-patchfail --targets=android`. It
   does not run `--check-scope`, `--check-cfg-split`, `--check-policies` or
   `--diff-mozconfig`, and `--check-policies` would fail open there anyway because
   `make dir` leaves no `firefox-*` tree behind — pass `LW_TREE` when wiring it in.
5. **`docs/android/PATCH-SCOPE.md` still documents the shim as live**, in the
   present tense, at seven places: `:8`, `:23-24` ("survives only as a generated
   `common + desktop` shim for downstream builders and is retired by …"), `:26`
   and the regeneration command at `:31`, `:35` ("`check-patchfail.sh` applies the
   shim top to bottom"), `:62` and `:261`. Two of those describe code that no
   longer exists at all — `check_compat_shim()` and the shim walk in
   `check-patchfail.sh`, which has read the real lists since LW-M1-11.
   Separately, `docs/android/README.md`'s "Start here" block lists five gates, not
   eight, and does not link this file, and
   `.forgejo/workflows/android-test.yaml:106` still says check-patchfail "walks the
   common+desktop shim".
6. **Three files still mention the retired shim** (none of them recreates it, and
   none is owned here):
   - `assets/patches/common.txt:8-12` — the only one that is actively *wrong*.
     Present tense, and a standing instruction: the shim "is GENERATED from this
     file plus desktop.txt … and must be regenerated whenever the *membership* of
     either changes - it is what scripts/check-patchfail.sh, scripts/fuzzfail.sh
     and the enable/disable helpers still read. The patcher compares it as a set
     and warns if the two disagree. LW-M7-01 retires it." Every clause is false
     now: nothing regenerates it, nothing reads it, and the patcher check is gone.
     Delete the paragraph.
   - `assets/patches/desktop.txt:6` and `:30` — both historical and both still
     true as written ("the order these entries had in the pre-split
     assets/patches.txt", "LW-M1-12 … regenerated the assets/patches.txt shim").
     They describe the past, so they are not wrong; they are just the last
     mentions of a file a reader can no longer find. Worth a "(since removed)".
   - `scripts/check-patchfail.sh` — the `shim_warn` block, its `[ -f … ]` guard and
     the multi-line warning it can no longer print, plus the "Which lists are
     walked" comment that still explains the shim. Dead but harmless.
   `Makefile` also still names `assets/patches.txt` in the comment above
   `patch_lists :=`, correctly, to explain why it is *not* a prerequisite; that one
   can stay.
7. **The board does not describe the current state.** `LW-M7-01` in
   `docs/android/tasks.yaml` still declares
   `owns: [docs/android/REBASE.md, assets/patches.txt]` — the second path no longer
   exists — and `tasks.yaml:935` still names `check_compat_shim()`, a function that
   is gone. There is also no board entry for the correction pass that produced this
   revision: it was briefed as `LW-M7-07`, and `board.py --show LW-M7-07` answers
   `error: no such task`. M7 stops at `LW-M7-06`.
