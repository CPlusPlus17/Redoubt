# Bug reports for LibreWolf upstream

Three defects found in `librewolf/source` while building an Android port. All three
affect the **desktop** build and are independent of that port — they are worth
reporting whether or not anything else here goes anywhere.

Verified present at upstream `HEAD` = **71177a3** ("Ensure we only publish signed
releases", 2026-08-12).

These are written as **reproductions, not patches**. Each is a few minutes to
confirm and a few minutes to fix. Nobody needs to accept anyone's code.

---

## 1. The l10n fetch is unpinned and unverified — supply chain

**`scripts/librewolf-patches.py:163`**

```python
exec(f"curl -so {tmpdir}/l10n.zip 'https://codeload.github.com/mozilla-l10n/firefox-l10n/zip/refs/heads/main'")
```

Every release build downloads a **moving branch head** over plain `curl -so`, with
no commit pin and no hash check, and unpacks it into `lw/l10n`. Whoever controls
that branch at the moment a release is built controls the localised strings shipped
to users. `-o` (rather than `-fL`) also means an HTTP error page is saved *as*
`l10n.zip` rather than failing.

Two builds of the same LibreWolf version are therefore not guaranteed to contain
the same localisation content, which also undercuts reproducibility.

**Suggested fix.** Record a commit sha and the archive's sha256 in a small file,
fetch `.../zip/<sha>` instead of `refs/heads/main`, and verify before unzipping.
Note the extracted top-level directory is then `firefox-l10n-<sha>` rather than
`firefox-l10n-main`.

Empirically, codeload archives for a fixed commit were byte-stable across four
downloads over ~25 minutes (the zip entry mtimes are the commit date, not the
generation time). GitHub does not contractually guarantee that, so the pin can
legitimately need re-recording after a GitHub-side change — worth saying so in
whatever file holds the hash, so the next person diagnoses rather than just bumps it.

---

## 2. `check-patchfail` reports success while testing zero patches — fails open

**`scripts/check-patchfail.sh`, the patch loop (~lines 32-47 at HEAD)**

```sh
patch $* -p1 -i ../../$curpatch > ../patch.tmp
...
for j in $(grep -n rej$ ../patch.tmp | awk '{ print $(NF); }'); do
```

`patch`'s **exit status is discarded**. Failure is detected only by grepping stdout
for `rej$`, and stderr is not captured into `patch.tmp` at all.

When a patch's target file is **missing** — the normal consequence of an upstream
rename — GNU patch prints `can't find file to patch` / `Skipping patch.` /
`1 out of 1 hunk ignored`, writes **no `.rej` file**, and exits 1. The detector sees
nothing and the script reports success.

**Reproduction.** Take any patch, rename one of its target paths so it no longer
exists in the tree, and run `make check-patchfail`. Result: `patch` exits 1, no
`.rej` is produced, the report is empty, and the run is declared successful. The
patch silently did not apply.

This matters most for the case it is least able to see: a patch that deletes or
creates whole files produces no `.rej` by construction, so it can never be caught
by a `.rej`-only detector.

**Suggested fix.** Capture `patch`'s exit status and make it authoritative; add
`2>&1` so stderr reaches the scanned output; keep the `.rej` scan as a second
signal rather than the only one. Also worth `< /dev/null` — with stdout redirected,
a missing target can otherwise block on patch's invisible `File to patch:` prompt.

Note fuzz is **not** a failure and should stay non-fatal: 31 hunks apply with fuzz
on a pristine 153.0.4 tree today.

*(The same `.rej`-only pattern is in `scripts/fuzzfail.sh`.)*

---

## 3. A beta download silently overwrites the release tarball, then fails to extract

**`Makefile:16` and `Makefile:34`**

```make
16: ff_source_tarball := firefox-$(version)$(FF_BETA_SUFFIX).source.tar.xz
...
34: ff_source_tarball := firefox-$(version).source.tar.xz
```

`ff_source_tarball` is assigned twice with `:=`. Because `:=` is immediate, the
*first* value is what `ff_source_url` (lines 18-24) is built from, and the *second*
is what everything after line 34 uses. So the URL and the local filename disagree.

**Reproduction**, against a clean checkout at `HEAD` (this repository's own copy of
the Makefile has since been changed, so run it on upstream):

```sh
mkdir -p /tmp/m && git show HEAD:Makefile > /tmp/m/Makefile && cp version release /tmp/m/
make -C /tmp/m -n test-beta FF_BETA_SUFFIX=b9
```

Emits:

```
curl -so firefox-153.0.4.source.tar.xz \
  "https://archive.mozilla.org/.../153.0.4b9-candidates/build1/source/firefox-153.0.4b9.source.tar.xz"
```

The **URL is correct** — it fetches the b9 candidate. The **local filename is not**:
it is saved as the plain release name. Three consequences, in order of nastiness:

1. **A beta tarball silently overwrites the release tarball of the same version.**
   If `firefox-153.0.4.source.tar.xz` is already on disk from a normal build, a
   `make test-beta` replaces it with b9 content under the release name, and nothing
   says so. The GPG verification passes, because the `.asc` was fetched from the
   same beta URL — so signature checking does not catch it either.
2. A later release build reuses that file, because the name matches and the
   `$(ff_source_tarball)` target is satisfied. It builds b9 while believing it built
   153.0.4.
3. Extraction fails anyway: `ff_source_dir := firefox-$(version)` is
   `firefox-153.0.4`, but the b9 tarball unpacks to `firefox-153.0.4b9/`, so the
   `mv` cannot find its source.

(3) is the visible symptom; (1) is the one worth fixing carefully, since it
mislabels an artefact on disk in a way the signature check cannot detect.

**Suggested fix.** Delete the second assignment. Note `ff_source_dir` needs the
suffix too, or (3) persists — and it may be worth deriving the extracted directory
from the tarball rather than from `$(version)`, since the same mismatch bites for
ESR (`firefox-153.0esr.source.tar.xz` unpacks to `firefox-153.0/`).

---

## Provenance

Found while porting to Android with AI assistance. Reported as reproductions
specifically so that none of that matters: each is verifiable from the repository
in a couple of minutes, and the fixes are a few lines that a maintainer would
rather write themselves than review.
