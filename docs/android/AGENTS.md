# Working agreement — Redoubt

Read this before touching a task. It is short on purpose; everything in it exists
because getting it wrong costs someone a day.

## Claiming a task

1. `python3 docs/android/board.py --ready --done <comma-separated finished ids>`
2. Pick a task whose `agent_safe` is `yes` (unless you are a human — the `no`
   tasks are gated on key custody, trademark decisions or physical devices).
3. Branch as `android/<task-id>`, e.g. `android/LW-M1-08`.
4. `python3 docs/android/board.py --show LW-M1-08` is the complete brief. If it is
   not enough to work from, that is a bug in the board — fix the board in the same
   PR rather than guessing.

## Ownership

Every task declares `owns`. **Only write files your task owns.** Two tasks in the
same wave never own the same path — `board.py --check` enforces it, and CI runs
that check. If your task genuinely needs to modify a file it does not own, stop
and add a `depends_on` edge instead of editing it anyway.

The one exception is `shared_edit`: the patch-list files
(`assets/patches/{common,desktop,android}.txt`) are append-only and line-oriented,
and several straddler tasks legitimately add lines to them at once. The rule there
is **only ever add or change the line for your own patch**. Git resolves the rest.

`tree_paths` declares which files *inside the extracted Firefox tree* your patches
touch. It is collision-checked the same way, because two patches editing the same
tree file must be ordered, not parallel — otherwise the second one's context drifts.

## Definition of done

A task is done when **all** of these hold:

- every line in `acceptance` is true
- `verify` runs and passes (or, for `manual:` verifies, the named human signed off
  and that is recorded in the PR)
- `board.py --check` still exits 0
- from M2 onward: `./scripts/android-smoke.sh` is green
- from M3 onward: `./scripts/android-pref-audit.sh` is green
- **if you touched the Kotlin layer: `./mach gradle fenix:testDebugUnitTest` passes.**
  A Gradle build compiling is NOT the tests passing — unit tests are a separate task
  and a patch can break 31 of them while the APK builds and installs fine.
  The suite cannot go fully green (libmegazord.so is an Android ELF; the host JVM
  cannot load it), so "passes" means **`python3 docs/android/board.py
  --check-fenix-tests` exits 0** — it subtracts the checked-in allowlist and errors
  on anything new, on a count that grew, and on a listed class that did not run at
  all. Do not hand-derive the residue and do not quote a bare failure count; quote
  that command's output, which names the results directory and its timestamp. See
  BUILD.md, "Running the Fenix unit test suite".

"It builds" is not done. "It launched" is not done — see landmine L1. **"It compiled"
is not "its tests pass"** — that one has now shipped twice: LW-M4-03 broke five tests
in NimbusSystemTest without noticing (LW-M4-13 exists to clean it up), and LW-M4-10
then broke 31 more, in a batch whose brief explicitly warned about the first case.
Run the tests.

## The five landmines

These are verified failure modes, not hypotheticals. Each one passes a naive gate.

### L1 — webgl-permission silently kills all WebGL on Android

Applying the common half of `webgl-permission.patch` to Android compiles
`librewolf.webgl.prompt` as `true`. `IsWebGLAllowed_impl` then fails closed,
`RecvShowWebGLPermissionPrompt` early-returns because GeckoView has no XUL
`<browser>`, and the only observers that would answer the prompt live in the
`browser/` half that Android never gets. Result: **every** WebGL context fails, with
no crash and no console error. A smoke test of "installs and browses" passes.

The fix ships in the same commit as the split (LW-M1-08): either
`lockPref("librewolf.webgl.prompt", false)` for Android, or a per-platform default
in `StaticPrefList.yaml`. Never in a follow-up.

### L2 — the pref precedence is not what you assume

**Five** stages reach the pref store on Android, not two, and this table replaces
an earlier one here that listed two and got the direction backwards. Measured
2026-08-25 by reading the tree; every row carries the code that decides it.

| # | stage | when | branch |
|---|---|---|---|
| 1 | packaged defaults (`greprefs.js`, `omni.ja defaults/pref/*.js`) | `Preferences.cpp:3917` | default |
| 2 | `MOZ_DEFAULT_PREFS` (`.../gecko/mozglue/GeckoLoader.java:83-105`) | `Preferences.cpp:3963` | default |
| 3 | profile `prefs.js` / `user.js` | `nsAppRunner.cpp:5986` | user |
| 4 | **autoconfig — our `librewolf.cfg`** | `nsAppRunner.cpp:6002` | `pref()`→user, `defaultPref()`→default, `lockPref()`→default+lock |
| 5a | `GeckoView:ResetUserPrefs` | after `profile-after-change` | **clears** user |
| 5b | Fenix `Pref.commit()` → `GeckoView:SetDefaultPrefs` | ~65 fire at startup, more on settings screens | default |

**Later wins, so we are stage 4 of 5 — three things run after us.**

Two names in that sequence are traps. `NS_PREFSERVICE_READ_TOPIC_ID` is spelled
`"prefservice:before-read-userprefs"` (`nsIPrefService.idl:232`) but fires in
`FinishInitializingUserPrefs`, *after* `prefs.js` was read — autoconfig runs after
the profile, not before it. And `NS_CreateServicesFromCategory("pref-config-startup")`
sits at `Preferences.cpp:3936`, thirty lines *before* the `getenv`, which reads as
"autoconfig wins" — it does not; that call only constructs `nsReadConfig`, whose
`Init()` merely registers an observer (`nsReadConfig.cpp:73-83`).

`Pref.commit()` is **not** a settings-screen event. Roughly 65 of them fire on every
cold start from `GeckoEngine.kt:1986-2074`, driven by `Core.kt`'s `DefaultSettings`
immediately after `GeckoRuntime.create` returns. Anyone who tests "does my pref
survive?" by not opening Settings is testing nothing.

Consequences, per cfg verb:

* **`lockPref` survives all five.** Stage 5b cannot touch it —
  `Pref::SetDefaultValue` opens with `if (!IsLocked())` and returns `NS_OK` without
  writing (`Preferences.cpp:876-902`) — and reads on a locked pref take the default
  anyway (`Preferences.cpp:1265-1270`).
* **Unlocked `defaultPref` survives 1–5a and is clobbered by 5b**, at startup, with
  no user interaction. This is the whole reason LW-M3-04 exists.
* **Bare `pref()` is wiped by 5a** for the 113 names in the reset universe — 77
  literal `Pref<>` names plus 36 built as `ROOT + name + ".suffix"` across three
  `SafeBrowsingProvider` trees (`ContentBlocking.java:1815-1826`). Those 36 are
  invisible to a literal grep, which is how a hand-built list misses them. See L2b.

**`MOZ_DEFAULT_PREFS` cannot bootstrap autoconfig.** `general.config.filename` is
read at `Preferences.cpp:3933` and the env var is parsed at `:3963` — same function,
thirty lines apart. Put `general.config.filename` in the env channel and
`nsReadConfig` is never constructed, so autoconfig silently never runs. It has to
come from a packaged default pref file, which is what
`autoconfig-resource-fallback.patch` ships.

**Some prefs are unreachable from `librewolf.cfg` entirely.** Everything read before
`nsAppRunner.cpp:6002` — the ~48 JS-engine startup prefs (upstream says so outright
at `nsAppRunner.cpp:5998-6001`: "AutoConfig files can't override JS engine start-up
prefs"), and anything read in `XRE_mainStartup` before XPCOM exists. `about:config`
will happily show your value while the engine runs on the compiled-in one. As of
2026-08-25 **none of the 255 pref names we set is in that window** — but that is an
accident of current call ordering, not a guarantee, and the 197 `mirror: once`
StaticPrefs seal collectively on first access of any one of them.

**`lockPref` is therefore mandatory for anything Fenix mutates at runtime** — 89
`Pref<>`/`PrefWithoutDefault<>` declarations across `GeckoRuntimeSettings.java` and
`ContentBlocking.java`, plus the three `SafeBrowsingProvider` child trees, giving
113 names in the reset universe. That list is generated by LW-M3-04, not
hand-maintained, precisely because 36 of the names are constructed rather than
written.

The counterweight: over-locking makes visible settings toggles do nothing. LW-M3-04
maintains a must-not-lock allowlist for prefs the settings fragment owns.

**And the sting in the tail, checked by LW-M3-03: `MOZ_DEFAULT_PREFS` as shipped
carries no lock.** The parser *can* express one — as a pref-**attribute**,
`modules/libpref/parser/src/lib.rs:30` `<pref-attr> = "sticky" | "locked"`
(default pref files only; `Token::Locked` at `:176`, consumed at `:508`
`is_locked = true` inside the `PrefValueKind::Default` branch) — so
`pref("x", v, locked);` is valid in exactly the mode `Preferences.cpp:3963` parses
this channel in. The channel is lock-free only because
`GeckoLoader.setupInitialPrefs` builds bare `pref("name", value);` lines with no
attribute, and emitting one would mean patching GeckoView Java — which is what
closing the channel means. All 38 `lockPref`s in `common.cfg` therefore need a real
`Preferences::Lock` call (the autoconfig path), or they are advisory only.

**LW-M3-08 RAN, AND AUTOCONFIG WORKS ON ANDROID.** With a `resource://gre/`
fallback for the `isBinDir` lookup and `librewolf.cfg` + `local-settings.js`
packaged by name, logcat shows
`D/MCD opened resource://gre/defaults/autoconfig/librewolf.cfg: 0x0`, prefs set
only by the `.cfg` appear in `about:config` on a fresh profile, and — the proof
that matters — a `lockPref`'d `devtools.debugger.remote-enabled` stayed `false` 🔒
after toggling "Remote debugging via USB" ON in Fenix Settings, while an unlocked
control pref flipped in the same session and process. Verified twice, on
independently booted emulators.

So for `lockPref` and `defaultPref`, L2 is DEFEATED: Android ships the same
`librewolf.cfg` as desktop, and locks are real `Preferences::Lock` calls that Fenix
cannot overwrite. LW-M3-02 lands it.

### L2b — the third channel: `GeckoView:ResetUserPrefs` wipes bare `pref()`

The spike found a channel nobody had counted. `GeckoView:ResetUserPrefs` fires at
startup **after** autoconfig has run, and clears the **user branch**. Recall from
above that a bare `pref()` in a `.cfg` writes the USER branch, not the default one.
So:

| construct | branch | survives on Android? |
|---|---|---|
| `lockPref` | default + locked | **yes** — and beats Fenix at runtime |
| `defaultPref` | default | **yes** |
| bare `pref()` | user | **NO — cleared by ResetUserPrefs** |

Measured on the running build: only **16 of 25** bare `pref()` calls persisted.
`browser.contentblocking.category` reads `standard` despite `pref(..., "strict")`
at `common.cfg:117`. We ship 24 bare `pref()` calls in `common.cfg`, so this is a
real and currently-silent gap — see LW-M3-09.

One more trap in the same area, also from LW-M3-01: a bare `pref()` in a `.cfg` does
**not** set the default branch. `extensions/pref/autoconfig/src/prefcalls.js:12-18`
routes it through `Services.prefs.getBranch(null)` — the **user** branch, rewritten
at every startup. Only `defaultPref`/`lockPref` touch the default branch. Compiling
the 26 bare `pref()` calls 1:1 into `MOZ_DEFAULT_PREFS` (which writes defaults)
would be a silent downgrade in which a stale profile value wins.

### L3 — patch scope cannot be decided by path prefix

`patches/ui-patches/neterror.patch` looks like pure `toolkit/` and is not: it edits
`toolkit/themes/shared/desktop-jar.inc.mn`. The desktop boundary is in the
*filename*, inside a shared directory.

Conversely **most of `devtools/` must be allowed** in common — `devtools/moz.build:11-16`
adds `platform/`, `server/`, `shared/` and `startup/` to `DIRS` with no guard, so
they ship on Android.

But **`devtools/client/` is desktop-only**, and an earlier version of this file got
that wrong by saying "`devtools/` must be allowed". `devtools/moz.build:5-8` adds
`client/` only when `MOZ_DEVTOOLS == "all"`, and `browser/moz.configure:17` is the
*only* `imply_option` that sets it — Android keeps the `toolkit/moz.configure:41-46`
default of `"server"`. So the correct rule is a carve-out *inside* an
otherwise-common tree, which is the same shape as the trap in the paragraph above,
just pointing the other way. `scripts/lint-patch-scope.py` encodes the narrow rule.

Scope rules are therefore file-level, with explicit allow and deny lists
(`scripts/lint-patch-scope.py`, LW-M0-08). A prefix rule passes neterror.patch and
lets desktop-only code into the Android build.

### L4 — mutations outside the patch set are invisible

`scripts/librewolf-patches.py` changes the tree in ways `make check-patchfail`
cannot see:

- the OpenAI deletions against `toolkit/components/ml/` — **now assert** (LW-M0-05)
- the l10n fetch — **now pinned and hash-verified** (LW-M0-04)
- the search-config and icon file copies — still bare `cp`
- the `version.txt` rewrite — still unconditional
- the pref-pane patch and its four `browser/` file copies, applied from their own
  call site on **every** target including Android — LW-M1-13 (line numbers are
  deliberately omitted here; this script has been edited by six tasks and any
  number quoted would already be wrong)

When upstream renames one of those paths, a bare `rm` or `cp` fails *open* — the
build succeeds and the change silently does not happen. When you add a new
out-of-patch mutation, make it assert.

### L5 — the patch checkers used to fail open (both fixed)

`scripts/check-patchfail.sh:32-47` discards `patch`'s exit code and decides
success by grepping its output for `rej$`. A hunk whose target file is **missing**
makes patch print "Skipping patch. / 1 out of 1 hunk ignored", write no `.rej`, and
exit 1 — and check-patchfail reports success. stderr is not captured either.

So any pure-deletion or pure-addition patch gets a silent false green from the very
tool that exists to catch landmine L4. This was found with a working counter-demo
(rename the target, watch the detector stay quiet) and it is why LW-M0-05 chose to
assert in the patcher rather than express deletions as diff hunks: a deletion hunk
*looks* like check-patchfail coverage and is not.

**Fixed in check-patchfail.sh by LW-M0-11** — patch's exit status is now the
authoritative signal, stderr is captured, `< /dev/null` stops a missing target
hanging on patch's invisible `File to patch:` prompt, and the `.rej` scan is kept as
a second signal. Note fuzz is *not* treated as failure: **30** hunks apply with fuzz
on the current 59-patch desktop set, and 22 distinct patches reject at `--fuzz=0`.

**`scripts/fuzzfail.sh` had the identical blind spot and LW-M1-11 fixed it**, with a
three-way classification: exit 0 is clean, a `.rej` means ordinary fuzz and gets
regenerated, and *exit non-zero with no `.rej`* is the L5 shape — reported, never
regenerated. It also closed a second fail-open there: the regeneration subshell's
exit status was discarded and nobody checked that a `.nofuzz` had appeared.

**`scripts/git-patchtree.sh` — FIXED, and this paragraph said otherwise for too
long.** It used to hardcode `firefox-$(cat version)` in the repo root, `rm -rf` it,
and always rebuild against the desktop tarball. LW-M1-15 landed all of that: a
private `mktemp -d` scratch directory with a cleanup trap (`:483`), and the
target/version split so an android patch rebuilds against `./version.android` and the
ESR tarball. LW-M1-16 then made `fuzzfail.sh` forward its own `--targets` here
instead of refusing to regenerate.

**Corrected 2026-08-26**, after this stale paragraph was quoted into an agent brief as
a live blocker and a coder spent a cycle "fixing" a script that needed no changes —
then reported it fixed, having modified nothing. Verify a landmine against the code
before you plan around it; this file is not a gate and nothing checks it.

Useful to know: check-patchfail does **not** need a librewolf source directory. It
extracts the Firefox tarball into its own `mktemp -d` scratch directory under the
repo root and removes it on exit, including on interrupt — so it is safe to run
concurrently and never touches a shared tree.

## Patch ordering constraints

**Eleven** pairs share a file and only apply in one order. This said "four",
then "five", then "nine"; `scripts/check-patch-order.py` is the authority the CI
gate actually runs and it now enforces eleven. Do not reorder the lists by hand.

| `autoconfig-setEnv` | `profile-directory` | `prefcalls.js` |
| `firefox-in-ua` | `moz-configure` | `toolkit/moz.configure` |
| `fpp-canvas-fix` | `webgl-permission-common` | `dom/canvas/ClientWebGLContext.cpp` |
| `mozilla_dirs` | `xdg-dir` | `toolkit/xre/nsXREDirProvider.cpp` |
| `webgl-permission-common` | `android/webgl-prompt-default` | `modules/libpref/init/StaticPrefList.yaml` |
| `xmas-common` | `android/autoconfig-resource-fallback` | `lw/moz.build` |
| `android/no-adjust` | `android/no-glean` | `app/build.gradle` + 4 more |
| `android/no-adjust` | `android/no-gms` | `gradle/libs.versions.toml` + more |
| `android/no-glean` | `android/no-gms` | `app/build.gradle` + more |
| `android/no-adjust` | `android/no-crashreporter` | `app/build.gradle`, `Analytics.kt` (+ `Components.kt`, order-free) |
| `android/no-gms` | `android/no-crashreporter` | `focus-android/app/build.gradle` (+ 2 more, order-free) |

Two of the five are **cross-list** (common→desktop, common→android). They hold
because common is applied first, but a checker comparing positions *within* one
list cannot see them at all — after swapping `mozilla_dirs`/`xdg-dir`, no single
list holds both patches, so there is literally nothing to compare. Model the apply
sequence, not per-list position.

Do not try to derive the *direction* of a constraint from patch content.
LW-M1-10 measured both obvious heuristics on this tree: "hunks overlap or abut"
catches 1 of 5 and false-positives on 6 order-free pairs; "later patch quotes lines
the earlier one adds" catches a different 1 of 5 and false-positives on JS
boilerplate. The constraints are a declared table; derivation's job is to *flag new
shared-file pairs for review*, not to decide them.

Since LW-M1-01 the last pair is **cross-list**: `mozilla_dirs` is common (its
`XP_UNIX` hunks compile on Android) and `xdg-dir` is desktop (all three hunks sit
inside a `MOZ_WIDGET_GTK` guard). The constraint still holds, because `common.txt`
is applied before any target list — but a checker that only compares positions
*within* one list will not see it. `scripts/enable-patch.sh` already models this;
`scripts/check-patch-order.py` (LW-M1-10) must too.

## The settings submodule

`settings/` is a git submodule pointing at `codeberg.org/librewolf/settings`. Tasks
marked `submodule: settings` need **two** PRs: one in that repo, and a submodule
bump here. Do not commit a detached submodule pointer.

## Evidence outside the repo evaporates

Everything a task leaves in `/home/mgysin/lw-*` — build trees, APKs, objdirs, pcaps,
pref dumps — is gone. Verified 2026-08-25: `lw-batch-combined`, `lw-m2-04`,
`lw-m2-01b`, `lw-m3-09` and the whole Android SDK no longer exist. Only the podman
image and this repo survived.

The cost is concrete. Every number in `docs/android/parity/bare-prefs.md` is now
unverifiable, and one open question there — whether a particular run should be
discounted — **cannot be settled**, because the run's `result.json` is gone.

So: **if a claim is meant to outlive your task, its evidence goes in
`docs/android/evidence/<task-id>/` inside the repo.** Not a path in your report, not
a directory under `$HOME`. A citation to a file that no longer exists is worse than
no citation, because it reads as verified.

Corollary for anyone writing a verify command: assume the device, the APK and the
build tree are absent. A verify that can only run on the machine that happened to
build something is not a verify. Say what it needs, and make it fail loudly rather
than silently pass when its input is missing.

## When two models share a task: planner + coder

The setup, from 2026-08-26: box A (Gemma, planning and vision) reasons, reads and
orchestrates; box B (Qwen, coding) implements, on an **explicit** `@coder` hand-off.
Opportunistic auto-delegation was tried twice with a local orchestrator and did not
hold. Treat the explicitness as a feature: every hand-off is a deliberate, visible
boundary, and boundaries are where this project's defects live.

**The failure mode this creates is the one that has already cost us three rounds.**
Our recurring defect is a claim passed forward as established — the `locked_pref`
claim survived three hand-offs because each reader treated the previous writer's
assertion as measurement. A planner/coder split adds a seam per task where exactly
that happens: the planner writes "GeckoView declares it at `ContentBlocking.java:1818`",
the coder implements against it without opening the file, and the report says
"implemented as specified" — true, and worthless, because nobody checked the premise.

So:

1. **Every claim carries its provenance.** Mark each as *read it*, *inferred*, or
   *taken from the brief, not checked*. The third is allowed; silently promoting it
   to the first is not. A brief is a hypothesis, not evidence.
2. **The box that runs the gate owns the green.** The planner may not report a gate
   it did not execute. "Definition of done" means the commands ran, in one box, and
   that box says which.
3. **If a fact is load-bearing, the coder opens the file.** A file:line in a brief
   costs one `sed` to confirm and a rewrite to get wrong. My own briefs have shipped
   a wrong path (`GeckoLoader.java` is under `.../gecko/mozglue/`) and a line range
   two short.
4. **One evidence directory per task, not per box** — `docs/android/evidence/<task-id>/`.
   Name which box produced each artefact, because "we measured it" stops being
   answerable once two machines are involved.
5. **Ownership and stand-off lists are per task, not per box.** Two models in one
   working tree are still one writer. The tree has no second index.

## Scratch files: use a task-private subdirectory

The scratchpad is **shared** between concurrently running agents. Generic temp
names collide. This is not hypothetical: during the M1 wave, two agents both used
`common-body.diff` / `desktop-header.txt`, and one produced split patches
containing the *other task's* content. It was caught by a content check before
landing — but the failure is silent, and a patch that applies cleanly while
containing the wrong hunks is about the worst artefact this project can produce.

Put everything under `<scratchpad>/<task-id>/`. Never write a generic filename at
the scratchpad root.

`check-patchfail.sh` and `fuzzfail.sh` used to share a hardcoded `tmpdir92` and
`rm -rf` it on start, so two concurrent runs destroyed each other. LW-M1-11 gave
both a `mktemp -d` scratch directory with a cleanup trap, so they are now safe to
run concurrently. `scripts/git-patchtree.sh` still is not — see L5.

## Isolation

Tasks with `isolation: worktree` mutate the extracted Firefox source tree. Run them
in a separate git worktree or a separate extracted tree — the tree is ~10GB and two
agents sharing one will corrupt each other's builds in ways that look like compiler
bugs.

## When you find the board is wrong

You will. The estimates are estimates, the classification in `PATCH-SCOPE.md` is a
heuristic until LW-M1-01 reviews it, and some dependency edges will turn out to be
missing. Fix `tasks.yaml` in the same PR as the work, keep the task id stable, and
say what changed in the PR description. Never renumber an id — they are referenced
from commit messages and issues.

## What not to do

- Do not drop a patch from `common.txt` to make a build error go away. That is a
  parity loss and it is the exact thing this project exists to avoid. If a patch
  truly cannot apply on Android, record it in `PATCH-SCOPE.md` with a reason so it
  shows up in the M5 parity matrix.
- Do not put a signing key, keystore passphrase, or any key material in CI, in a
  container image, or in any repo. See LW-M6-01.
- Do not soften the parity wording. Redoubt will have a weaker
  process sandbox than LibreWolf desktop, and the plan is to say so on the download
  page.
