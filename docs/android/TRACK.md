# Release track — Redoubt

**Task:** LW-M0-07 · **Status:** decided, pending maintainer sign-off (see the last
section) · **Written:** 2026-08-15 against the stock Firefox 153.0.4 tree and the
Mozilla release calendar as of that date.

---

## Decision

**Redoubt tracks Firefox ESR. LibreWolf desktop stays on Firefox
release.** The Android track starts at **esr153** (`version.android` = `153.0esr`,
`release.android` = `1`) and follows the ESR series — dot releases as they ship,
one major rebase a year when Mozilla cuts the next ESR.

This upholds the recommendation on record in
[`ROADMAP.md`](ROADMAP.md#release-track), but three of the four numbers in that
table are wrong and one of them is wrong in a way that matters. They are corrected
below. The decision survives the correction — it survives it *more* strongly than
the roadmap argued, because the release track got twice as expensive in July 2026.

---

## 1. What the current tarball actually is

The roadmap says the adoption cost is *"zero, esr153 is the tree in the current
tarball"*. **That is false.** The current tarball is the **release** channel.

Evidence, from the stock tree extracted at `firefox-153.0.4/`:

| file | contents |
|---|---|
| `browser/config/version.txt` | `153.0.4` |
| `browser/config/version_display.txt` | `153.0.4` — **no `esr` suffix** |
| `config/milestone.txt` | `153.0.4` |

`build/moz.configure/init.configure:1151` computes the channel from exactly that
string:

```python
is_esr=app_version_display.endswith("esr") or None,
```

and `:1179-1180` turn it into `MOZ_ESR`. With `version_display.txt` = `153.0.4`,
**`MOZ_ESR` is unset in this tree**. The Makefile fetched it from
`archive.mozilla.org/pub/firefox/releases/153.0.4/source/`, the release-channel
path. `./version` says `153.0.4`, and 153.0.4 is a release-channel version number;
an ESR one would read `153.0esr` or `153.1.0esr`.

**What *is* true:** 153 is the version Mozilla cut ESR from, so the roadmap's
instinct was right even though its claim was not. The same tree proves it —
`taskcluster/config.yml:19-25` lists `esr153` as a live release branch next to
`esr140` and `esr115`, and `taskcluster/kinds/merge-automation/kind.yml:44-89` has
`release-to-esr: firefox-esr153` and `bump-esr153` targets. ESR 153 shipped
2026-07-21 as `firefox-153.0esr.source.tar.xz` (767 M) at
`archive.mozilla.org/pub/firefox/releases/153.0esr/source/` — verified to exist; a
different artifact of almost exactly the same size as the 153.0.4 release tarball
(766 MiB), because esr153 branched from 153.0 and has not diverged much yet.

### Why the distinction is not pedantry

`MOZ_ESR` is not inert. In this tree it changes:

| site | effect on ESR |
|---|---|
| `xpcom/io/nsLocalFileCommon.cpp:72` | `.jnlp` is **not** in the dangerous-extension list |
| `toolkit/components/reputationservice/ApplicationReputation.cpp:279` | same, for download reputation |
| `toolkit/components/search/SearchUtils.sys.mjs:361` | search configuration channel becomes `"esr"` |
| `toolkit/modules/RustSharedRemoteSettingsService.sys.mjs:44` | Remote Settings channel becomes `"esr"` |
| `toolkit/components/enterprisepolicies/EnterprisePoliciesParent.sys.mjs:594` | the install is treated as *enterprise* |
| `toolkit/components/backgroundtasks/defaults/backgroundtasks.js:61` | background-update throttling default flipped |
| `browser/branding/official/pref/firefox-branding.js:24` | ESR update / release-note URLs |

Two of those land on work already on the board: the search-configuration channel
affects M4's search work and M2's `--enable-appservices-in-tree`, and the
`.jnlp` difference is a download-handling behaviour change that the M5 parity
matrix should have a row for. The policy-engine one is Android-irrelevant (the
engine is compiled out — see `ROADMAP.md`, "What makes this hard") but matters if
desktop is ever asked to follow.

**Adoption cost today is therefore *near zero for the patch set* and *not zero for
the build*.** The 53 patches apply to both trees because both are Firefox 153; but
adopting esr153 means a second 767 MB tarball, a second ~10 GB extracted tree on
every builder and on the Forgejo `epsilon` runner, and the plumbing in this task.
Say "one tarball, no patch rebase" — not "zero".

---

## 2. Rebase cadence — the real numbers

### Sources

- **F1** — Mozilla's public release calendar,
  <https://whattrainisitnow.com/calendar/>, read 2026-08-15.
- **F2** — the Mozilla Foundation Security Advisory index,
  <https://www.mozilla.org/en-US/security/advisories/>, read 2026-08-15. Every
  advisory carries a date and a product/version, so this is the ground truth for
  "how many times did each channel actually have to ship".
- **F3** — the `dev-platform` announcement of the cadence change, 2026-07-14/17,
  and its coverage (The Register, gHacks, OMG!Ubuntu, Linuxiac).
- **F4** — <https://endoflife.date/firefox>, read 2026-08-15, for ESR support
  windows. Treat with care: it lists "153.0.4" as the latest ESR 153 version,
  which is the release-channel number — it makes the same conflation the roadmap
  made.

### The cadence change the roadmap did not name

**Firefox moves to a two-week major release cadence starting with Firefox 155 on
2026-09-01** (F3). F1 confirms it: 155 Sep 1, 156 Sep 15, 157 Sep 29, 158 Oct 13,
159 Oct 27, 160 Nov 10, 161 Nov 24, 162 Dec 8, 163 Jan 12 2027, 164 Jan 26 2027 —
exactly 14 days apart. That is **26 majors a year**. The roadmap's "26" is right,
and it is right for a reason that became public roughly a month before the roadmap
was written: until 2026-08-18 the observed rate was 4-weekly (7 majors, 147 on
Jan 13 → 153 on Jul 21 = 189 days, a 27-day mean, ~13.5/year, F2).

### Corrected table

| | desktop — release | android — esr153 |
|---|---|---|
| majors per year | **26** from 2026-09-01 (F1, F3); 13.5 observed before it (F2) | **1** |
| dot releases per year | **~20** — 11 out-of-band security releases in the 204 days 2026-01-13 → 2026-08-04 (F2) | **~21 observed, ~26 scheduled** — see below |
| total releases we must cut per year | ~46 | ~27 |
| **hard rebases** (patches break, Fenix churns) | **26** | **1** |
| adoption cost today | — | one 767 MB tarball, one extra ~10 GB tree; no patch rebase |
| co-maintainer of the same base | — | Tor Browser Stable (verified, §4) |

**The roadmap's "~12 dot releases per year" for ESR is wrong by about 2×.** ESR 140
shipped 11 security releases in the 189 days from 2026-01-13 to 2026-07-21 (140.7,
140.7.1, 140.8, 140.9, 140.9.1, 140.10, 140.10.1, 140.10.2, 140.11, 140.12,
140.13 — F2), an annualised **~21**. Under the new cadence it gets worse: F1
schedules an ESR 153 point release on *every* release date — 153.1 Aug 18, 153.2
Sep 1, 153.3 Sep 15, 153.4 Sep 29, 153.5 Oct 13, 153.6 Oct 27, 153.7 Nov 10, 153.8
Nov 24, 153.9 Dec 8, 153.10 Jan 12, 153.11 Jan 26 — **~26 a year**.

### What that means for the argument

Choosing ESR does **not** meaningfully reduce the number of releases we cut
(~46 → ~27, a factor of 1.7). It reduces the number of releases where the 53-patch
set, the three-way patch split, the pref delivery and the eleven M4 Kotlin removals
all have to be re-derived against a moved tree: **26 a year → 1 a year.**

That is the entire argument, and it is stronger than the roadmap's version. The
per-release cost of a dot rebase is a tarball fetch, `check-patchfail`, the pref
audit and the smoke test — automatable, and LW-M7-01 automates it. The per-release
cost of a major rebase is a person. Twenty-six of those a year, on top of desktop's
twenty-six, is where the port dies.

---

## 3. The security-latency cost of ESR

This is the strongest argument *against* ESR for a browser that markets itself on
security, the roadmap does not quantify it, and LW-M7-05 has to publish a
turnaround target against it. There are three distinct latencies.

### 3a. Out-of-band fixes: median 14 days, worst observed 21

Mozilla ships an ESR point release alongside each major, and *sometimes* alongside
an out-of-band release-channel fix. From F2, every release-channel out-of-band
security release in 2026 and whether ESR 140 got one the same day:

| release-channel fix | date | same-day ESR? | ESR latency |
|---|---|---|---|
| Firefox 147.0.2 (MFSA 2026-06) | Jan 27 | no | ESR 140.7.1, Feb 16 → **20 d** |
| Firefox 147.0.4 (MFSA 2026-10) | Feb 16 | yes — same advisory as ESR 140.7.1 / 115.32.1 | 0 d |
| Firefox 148.0.2 (MFSA 2026-19) | Mar 10 | no | ESR 140.9, Mar 24 → **14 d** |
| Firefox 149.0.2 (MFSA 2026-25) | Apr 7 | yes — ESR 140.9.1 (MFSA 2026-27) | 0 d |
| Firefox 150.0.1 (MFSA 2026-35) | Apr 28 | yes — ESR 140.10.1 (MFSA 2026-36) | 0 d |
| Firefox 150.0.2 (MFSA 2026-40) | May 7 | yes — ESR 140.10.2 (MFSA 2026-41) | 0 d |
| Firefox 150.0.3 (MFSA 2026-45) | May 12 | no | ESR 140.11, May 19 → **7 d** |
| Firefox 151.0.3 (MFSA 2026-54) | Jun 2 | no | ESR 140.12, Jun 16 → **14 d** |
| Firefox 152.0.4 (MFSA 2026-62) | Jun 30 | no | ESR 140.13, Jul 21 → **21 d** |
| Firefox 152.0.6 (MFSA 2026-67) | Jul 14 | no | ESR 140.13, Jul 21 → **7 d** |

Six of ten had no same-day ESR counterpart. For those six: **median 14 days, mean
13.8, maximum 21.**

The worst case is verified end to end and is the one to quote. **MFSA 2026-67,
Firefox 152.0.6, 2026-07-14, impact Critical**, fixing CVE-2026-15718 (invalid
pointer in JavaScript: WebAssembly) and CVE-2026-15719 (site isolation in DOM:
Navigation), both annotated *"exploit code for this is public however we are not
aware of any attacks in the wild"*. Both CVEs first appear on the ESR side in
**MFSA 2026-70, Firefox ESR 140.13, 2026-07-21 — seven days later.** For seven days
an ESR user was exposed to two Critical bugs with public exploit code that a
release user was not.

### 3b. Fixes that never arrive: up to a year

Mozilla's ESR policy backports Critical and High and leaves much of the rest. On
2026-07-21 Firefox 153 (MFSA 2026-68) listed **63 CVEs**; the same-day ESR 140.13
advisory (MFSA 2026-70) listed **32**, of which 29 overlap. **34 of the 63 CVEs
fixed in Firefox 153 had no ESR fix that day.**

Caveat, stated because it is load-bearing: an unknown fraction of those 34 do not
affect ESR 140 at all — the code was written after 140 branched. So 34 is an
**upper bound** on the gap, not a count of live unpatched bugs. The direction is
not in doubt; the magnitude is uncertain, and nobody outside Mozilla can resolve it
from public data. What is certain is that the residue waits for the next ESR major,
i.e. up to ~13 months.

### 3c. The one specific to this project: there is no Firefox for Android ESR

Firefox for Android ships from Nightly, Beta and Release GeckoView. **There is no
ESR channel** — the last time one existed was Fennec on ESR 68 in 2019. Mozilla
therefore has no product built from `mozilla-esr153`'s `mobile/android`, and no
reason to uplift Android-layer fixes to it.

This is not hypothetical. **MFSA 2026-73, 2026-08-04, impact High**, "Security
Vulnerabilities fixed in Firefox for Android 153.0.3", CVE-2026-18809, an
information disclosure affecting Firefox for Android *and* Firefox Focus for
Android. It is Android-only, it names no ESR version, and as of 2026-08-15 no ESR
release has carried it. The next scheduled ESR 153 point release is 153.1 on
2026-08-18 — 14 days after the release-channel fix, and whether it carries this
CVE at all depends on whether the bug is in Gecko or in the Kotlin layer.

**Redoubt on ESR inherits this gap and must close it by hand.** That
is a standing obligation, not a one-off: someone reads every "Firefox for Android"
MFSA and decides per advisory whether to backport into our tree.

It is the strongest argument against this track, and it does not overturn it — it
converts into a named piece of work. Twenty-six hard rebases a year is not
survivable by this team. One advisory stream to watch is.

### What LW-M7-05 should publish

Not a number we cannot hit. The honest statement:

> A Gecko security fix that Mozilla ships out of band to Firefox release reaches
> Redoubt when it reaches Firefox ESR — historically the same day
> for roughly half of them, and a median of 14 days (worst observed 21 days) for
> the rest. LibreWolf's own turnaround on top of that is <N> days from the ESR
> tarball to a published APK. Android-only advisories with no ESR counterpart are
> triaged individually and we publish the outcome.

`<N>` is ours to set and ours to meet; the rest is Mozilla's cadence and we should
say so rather than absorb it into a single number that looks like a promise.

---

## 4. Tor Browser — verified, not assumed

The roadmap claims Tor Browser as a co-maintainer of the same base. Checked:

- **Tor Browser Stable 15.0 is built on Firefox ESR 140 — desktop *and* Android.**
  Tor Browser 15.0.11 (2026-04-28) shipped with GeckoView bumped to `140.10.1esr`,
  i.e. Tor Browser for Android is built from the ESR branch's `mobile/android`.
  That is precisely the configuration Redoubt would be.
- **Tor Browser Stable 16.0 will be based on Firefox ESR 153**, expected mid-Q3
  2026; alpha 16.0a9 (2026-07) already runs on esr153. There is no 15.5 — they go
  straight from ESR 140 to ESR 153.
- So they are on the same base, on the same platform, and they got there first.
  If Fenix-from-an-ESR-branch did not build, they would have found out before us.
  **This is genuine co-maintenance, not coincidence.**

One qualification the roadmap does not have. On 2025-12-01 the Tor Project changed
its model ("The Future of Tor Browser Alpha"): **from 16.0a1, Tor Browser Alpha is
based on Firefox Rapid Release, not ESR.** Only Stable remains on ESR. Their stated
reasons are the ones we are relying on in reverse — cascading delays, developer
stress in the compressed ESR transition window, and poor feature continuity.

Two consequences for us. First, the ESR base is no longer where all of Tor's
attention is, so the co-maintenance benefit is real but eroding; re-check it at
each ESR transition rather than assuming it. Second, they are now the closest thing
to a controlled experiment on exactly our question, and their answer was to keep
the *shipping* product on ESR and take the rapid-release pain only in an alpha they
do not have to support.

**ESR 140 reaches end of life on 2026-09-29** (F4, and F1 shows 140.17 on Sep 29 as
its last scheduled point release). ESR 153 is the only forward-looking ESR from that
date. Adopting esr153 now is adopting the current ESR, not one about to expire.

---

## 5. Reversal cost

If Android ships on ESR and we later want release:

1. **The version jump is the cost, and it compounds.** Switching means jumping from
   esr153 to whatever release is current, all at once. At 26 majors a year, a
   switch six months in is a ~13-major jump with no intermediate green build to
   bisect against. That is strictly worse than 13 incremental rebases would have
   been. **The reversal cost grows linearly with how long we stay on ESR** — this
   is the one property that makes the decision feel one-way, and it is a schedule
   cost, not an architectural one.
2. **Nothing in the patch set or the build encodes ESR.** `version.android` is one
   line. The plumbing in §6 is version-agnostic. `MOZ_ESR` changes the behaviour of
   the seven sites in §1 and nothing we wrote.
3. **Two of those seven need re-validation on a switch.** The search-configuration
   channel (`SearchUtils.sys.mjs:361`) and the Remote Settings channel
   (`RustSharedRemoteSettingsService.sys.mjs:44`) both flip between `"esr"` and the
   update channel. M4's search work and M2's `--enable-appservices-in-tree` must be
   validated against whichever we ship, and re-validated if we switch.
4. **Users see a version discontinuity** (153.x → 16x.x). Cosmetic on its own.
5. **The asymmetry matters:** release → ESR later is *cheap* (wait for the next ESR
   cut, land on it, one ordinary major rebase). ESR → release later is
   *expensive* (1). So "start on release, switch to ESR later" is the
   cheap-to-reverse option and it is the honest counter-argument to this decision.
   It is outweighed by the 328–638 hours it takes to reach an APK: on the release
   track the tree the port is being built against would move under it ~26 times
   during development, and M4's eleven Kotlin tasks would be rebased across every
   one of them.
6. **What would make it genuinely irreversible:** coupling the track to LW-M6-01's
   `applicationId` and signing key. A new `applicationId` has no upgrade path from
   any existing install and the key cannot be replaced. Nothing about the track
   requires touching either — **keep them uncoupled**, and this stays a schedule
   decision.

---

## 6. The version-divergence model

### The question

`$(lw_source_dir)` is `librewolf-$(version)-$(release)`. One extracted tree cannot
be two Firefox versions at once. So what happens when desktop wants 153.0.4 and
Android wants 153.0esr?

### Should the files exist at all?

Yes — and the reason is timing, not symmetry. If `version.android` merely mirrored
`./version`, the mechanism would be an empty maintenance cost and should not be
built. It does not mirror it: the tracks diverge **today**, because
`archive.mozilla.org` serves 153.0.4 and 153.0esr as two different tarballs, and
they diverge further every fortnight from 2026-09-01.

The alternative — do M1–M5 against the shared 153.0.4 tree and switch to ESR at M6
— looks cheaper and is not. M4's eleven de-Mozilla-ing tasks are done against
`mobile/android` source. Done against release-Firefox-160-ish and then moved to
esr153, that is a **backport across ~13 majors**, which is harder than the forward
port it replaces. Doing them against the tree we intend to ship is the cheap order.
This is the one question in §8 where the maintainer could reasonably decide the
other way, so it is called out explicitly there.

### The model

`./version` + `./release` name the **desktop** track. `./version.android` +
`./release.android` name the **Android** track. `TARGETS` selects which pair is in
effect for one `make` invocation:

| `TARGETS` | version pair in effect |
|---|---|
| `desktop` (default) | `./version`, `./release` — unchanged from before this task |
| contains `android`, not `desktop` | `./version.android`, `./release.android` |
| contains both | `./version`, `./release`, plus a guard that refuses to build (below) |

Because everything downstream is already written in terms of `$(version)` and
`$(release)`, overriding those two variables *is* the whole mechanism:

- `$(ff_source_tarball)` → `firefox-153.0esr.source.tar.xz`
- `$(ff_source_url)` → `.../releases/153.0esr/source/firefox-153.0esr.source.tar.xz`
- `$(ff_source_dir)` → `firefox-153.0esr`
- `$(lw_source_dir)` → `librewolf-153.0esr-1`
- `$(lw_source_tarball)` → `librewolf-153.0esr-1.source.tar.gz`

The two tracks therefore get separate tarballs, separate extracted trees and
separate output archives for free, and **an Android build never touches the desktop
tree.** No new `FF_CHANNEL` case is needed: ESR tarballs live under the same
`releases/<version>/source/firefox-<version>.source.tar.xz` layout — `153.0esr` is
just a version string to `archive.mozilla.org`. Verified against the live listing.

`$(version_files)` follows the same switch, so a desktop version bump does not
invalidate the Android tree or vice versa.

### `TARGETS=desktop,android` stops being buildable

Once the tracks diverge there is no single tree to apply both platform patch sets
to. The Makefile refuses, via `$(lw_tree_guard)`, which is:

- **empty** when the tracks agree or only one platform is requested — and make
  drops a recipe line that expands to nothing entirely, so the default
  `make -n dir` output is byte-identical to what LW-M0-01 left;
- **a recipe-time `exit 1`** otherwise, *not* a parse-time `$(error)`, so `make -n`
  stays a real dry run and **LW-M0-01's own check,
  `make -n dir TARGETS=desktop,android | grep -- '--targets=desktop,android'`,
  still passes.**

`TARGETS=desktop,android` thus remains a valid plumbing check and stops being a
valid build. `TARGETS=common,android` — the combination `ROADMAP.md`'s M0 exit
criterion names — resolves to the Android track and works.

### Known defect: `targets_stamp` thrashes between tracks

`targets_stamp` is `librewolf-targets-$(subst $(comma),-,$(TARGETS))` and its recipe does
`rm -f librewolf-targets-*`. It records *which patch sets* a tree was built with,
but not *which version* — and with two coexisting trees that is not enough.
Alternating `make dir` and `make dir TARGETS=android` deletes the other track's
stamp each time, so every switch re-extracts a tree that was already correct:
~10 GB and tens of minutes of churn per switch.

**Not fixed here, deliberately.** The fix renames the stamp, which changes
`make -n dir` output and forces one re-extract for every existing desktop builder —
neither is acceptable inside a task whose job is to leave desktop alone. The fix
itself is two lines, for whoever owns the Makefile next (LW-M0-02, or a new M0
task):

```make
targets_stamp := librewolf-targets-$(version)-$(release)-$(subst $(comma),-,$(TARGETS))
# and in its recipe:
#	@rm -f librewolf-targets-$(version)-$(release)-*
```

### Known gap: nothing watches the ESR channel

`make check` runs `scripts/update-version.py`, which writes `./version` only.
`version.android` is deliberately **not** bumped automatically — an ESR dot release
should be adopted by a human who has read the advisory. But there is no
`make check-android` either, so nothing tells the maintainer that 153.1esr shipped.
That belongs with LW-M7-01's rebase runbook and LW-M7-05's turnaround target; it is
not plumbing this task can add without owning `scripts/`.

### Disk

Two tracks means two extracted trees, ~10 GB each, plus two ~770 MB tarballs, on
every builder and on the Forgejo `epsilon` runner. LW-M0-06 (toolchain image) and
the CI skeleton need to budget for it.

---

## 7. Corrections owed to other documents

This task does not own these files. Recorded here so they are not lost.

| where | says | should say |
|---|---|---|
| `ROADMAP.md` "Release track" table | "adoption cost today — zero, esr153 is the tree in the current tarball" | the current tarball is release-channel 153.0.4; adopting esr153 costs one extra tarball and one extra tree, and no patch rebase |
| `ROADMAP.md` "Release track" table | android (esr) "~12" dot releases per year | ~21 observed for ESR 140 in 2026, ~26 scheduled for esr153 under the two-week cadence |
| `ROADMAP.md` "Release track" table | desktop "26 majors per year" | correct — but note it becomes 26 only on 2026-09-01 (Firefox 155); it was 13.5 when the roadmap was written |
| `ROADMAP.md` M0 exit | "`make dir TARGETS=common,android` produces a tree" | say *which* tree — it is now the esr153 tree, not the desktop one |
| `tasks.yaml` LW-M0-07 `what:` | repeats "zero adoption cost … esr153 is the tree in the current tarball" and "~12 dots" | as above |
| `Makefile:44` and `Makefile:62` | `ff_source_tarball` is assigned twice; the second drops `FF_BETA_SUFFIX` | pre-existing, unrelated to this task, but it means `FF_BETA_SUFFIX` has no effect on the tarball name |

---

## 8. Maintainer sign-off

An agent cannot sign this off — LW-M0-07's `verify` is
`manual: maintainer sign-off recorded in TRACK.md`. The block below is what is
being agreed to. Nothing here is binding until it is filled in.

**By signing, the maintainer agrees to all of:**

1. **The track.** Redoubt tracks Firefox ESR, starting at esr153;
   LibreWolf desktop stays on Firefox release. One Android major rebase a year,
   ~26 dot rebases a year (§2).
2. **The published latency.** Redoubt will be behind LibreWolf
   desktop on out-of-band Gecko security fixes by a median of 14 days and up to
   21 days, and LW-M7-05 will publish that rather than a number we cannot hit
   (§3a, §3-final).
3. **The watch obligation.** Because there is no Firefox for Android ESR, a named
   person reads every "Firefox for Android" MFSA and decides per advisory whether
   to backport into our tree (§3c). This is recurring work not currently budgeted
   anywhere on the board.
4. **The extra tree.** Every builder and the CI runner carry a second ~10 GB
   extracted tree and a second ~770 MB tarball from now on (§6).
5. **`TARGETS=desktop,android` is no longer a buildable combination** — it remains
   a valid dry-run plumbing check (§6).
6. **The track stays uncoupled from LW-M6-01.** The `applicationId` and the signing
   key are decided on their own merits; nothing about ESR-vs-release may be used to
   justify either (§5.6).

**Questions the maintainer must answer, not just tick:**

- **Q1 — switch now or at M6?** `version.android` is set to `153.0esr` today, which
  means M1–M5 do their work against the ESR tree. The alternative is to leave it at
  `153.0.4`, do the port against the shared tree, and switch at M6. §6 argues for
  now (M4's Kotlin work would otherwise become a ~13-major backport); the cost is a
  second 10 GB tree from M1 onward. **Which?**
- **Q2 — who owns the Android advisory watch (§3c), and with what response time?**
  If the answer is "nobody", the honest move is to say so on the download page,
  because it is a real difference from desktop LibreWolf.
- **Q3 — what is `<N>`,** our own turnaround from an ESR tarball to a published APK
  across our own F-Droid repo, Accrescent and direct APK (§3-final)? LW-M7-05
  cannot be written without it.
- **Q4 — do we accept the erosion of the Tor co-maintenance argument?** Tor Browser
  Alpha left ESR in Dec 2025; only Stable remains (§4). Should this decision be
  re-examined at each ESR transition, and by what trigger?
- **Q5 — may the `ROADMAP.md` and `tasks.yaml` corrections in §7 be landed,** and by
  whom? This task does not own those files.
- **Q6 — who fixes the `targets_stamp` defect in §6,** and does it go into LW-M0-02
  or a new M0 task?

```
Decision:            Android tracks Firefox ESR (esr153); desktop stays on release
Recorded by:         LW-M0-07 (agent), 2026-08-15
Evidence reviewed:   sections 1-5 of this document

Maintainer:          ______________________________
Date:                ______________________________
Agreed items 1-6:    [ ] yes   [ ] with the exceptions noted below
Q1 answer:           ______________________________
Q2 answer:           ______________________________
Q3 answer (N days):  ______________________________
Q4 answer:           ______________________________
Q5 answer:           ______________________________
Q6 answer:           ______________________________
Exceptions / notes:
```

---

## Appendix — how to re-derive these numbers

Every figure above comes from a public source that can be re-read at the next ESR
transition. Do that rather than trusting this file a year from now.

- **Cadence:** <https://whattrainisitnow.com/calendar/> — the "Matching ESR" column
  gives the ESR point releases scheduled against each major.
- **Actual releases shipped, both channels:**
  <https://www.mozilla.org/en-US/security/advisories/> — dated, one entry per
  product per release. Count entries, do not estimate.
- **Latency:** for each release-channel out-of-band advisory, find the first ESR
  advisory containing the same CVE ids. The advisories list CVEs explicitly, so
  this is a set difference, not a judgement call.
- **The not-backported gap:** diff the CVE list of a major's advisory against the
  same-day ESR advisory. Remember the caveat in §3b.
- **ESR support windows:** <https://endoflife.date/firefox>, cross-checked against
  the last scheduled point release for that ESR series on the calendar.
- **Channel of a tree in hand:** `cat browser/config/version_display.txt`. If it
  does not end in `esr`, `MOZ_ESR` is unset and it is not an ESR tree
  (`build/moz.configure/init.configure:1151`).
