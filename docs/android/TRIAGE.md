# Android issue triage — `github.com/CPlusPlus17/Redoubt/issues`

Task: **LW-M7-04**. Wave 0, on purpose: the first week after launch is when triage
is most needed and least likely to get written.

This document describes the triage process and the local issue-template files.
**Live state checked 2026-09-08:** the form and configuration exist in this
worktree, but neither is on the GitHub default branch. The planned Android labels
are also absent. Publication and the test-issue verification in
[§6](#6-maintainer-checklist) remain outstanding; see the
[read-only audit](evidence/lw-m7-06/beta-audit-2026-09-08/human-criteria.md).

The issue tracker is **this repository's own GitHub tracker**
(`github.com/CPlusPlus17/Redoubt/issues`). GitHub reads issue templates from that
repository's default branch; labels are repository settings.

---

## 0. Triage owner — LAUNCH BLOCKER

```
OWNER:        Manuel Gysin                  (launch-window triage owner)
BACKUP:       -- none --                    (see the note below)
WINDOW OPEN:  __________  (date the download page goes live — LW-M7-02)
WINDOW CLOSE: __________  (OPEN + 14 days, or the exit condition in §5)
```

**Named 2026-09-06.** The recorded owner decision is to operate without a backup.
Redoubt is a solo project. The owner carries both responsibilities below; there is
no automatic cover when the owner is unavailable:

- the daily pass and the 30-day `Android Needs Repro` decay rule (§3);
- triage throughout the launch window (§5).

Same decision shape as the single-holder key custody in `SIGNING.md`: an accepted
risk of a solo project, written down rather than left blank.

**Shipping with `OWNER` blank is a launch blocker.** Not a nice-to-have, not a
follow-up: if this field is empty, the Android download page (LW-M7-02) does not go
live and the F-Droid repo (LW-M6-03) does not get its first published index.

The reason is specific rather than procedural. On launch day this tracker gets a
burst of reports from people on hardware nobody on the project owns, through three
distribution channels that have never carried a release, on a build with **no crash
reporter** — Socorro is removed in M4, so a crash produces no crash ID and no
automatic report. Every signal we get in that window arrives as a hand-written
issue. A tracker with 40 unsorted Android issues and no owner is
indistinguishable from a tracker with 39 duplicates and one exploitable Gecko bug,
and that is the failure this task exists to prevent.

The named owner performs the daily pass ([§5](#5-the-launch-window-rotation)).
If a backup joins later, record that person's name here. The dated solo-owner
decision above is the accepted exception to having a backup.

The closed beta starts its own 14-day feedback period at the first install
(`BETA.md` §3). The public-launch dates above begin when the download page goes
live; they do not start the beta or replace its results log.

---

## 1. Labels

### 1.1 Naming: proposed vocabulary and current live state

The earlier claim that this repository already had 48 capitalised labels was
incorrect. On 2026-09-08 its live labels were `accessibility`, `bug`,
`documentation`, `duplicate`, `enhancement`, `good first issue`, `help wanted`,
`invalid`, `question`, and `wontfix`. None of the Android labels below exists yet.

The capitalised names below retain this plan's proposed vocabulary. These are
planned families, not an inventory of live repository settings:

| family | examples |
|---|---|
| platform | `Linux`, `macOS`, `Windows`, `FreeBSD` |
| distribution | `Build Flatpak`, `Build AppImage`, `Build AUR`, `Build Debian`, `Build Fedora`, … |
| area | `Component Builds`, `Component Patches`, `Component Settings`, `Component UI`, `Component Website` |
| workflow | `Type Bug`, `Status Upstream`, `Prio High`, `Needed Info`, `Flag Caution`, … |

The shorthand-to-proposed-name mapping is:

| board id | label to create |
|---|---|
| `android` | **`Android`** |
| `android-build` | **`Android Build`** |
| `android-prefs` | **`Android Prefs`** |
| `android-security` | **`Android Security`** |

The naming choice remains part of the publication checklist in [§6](#6-maintainer-checklist).
If the maintainer chooses lowercase names, rename all four consistently and change
the `labels:` lists in [§2](#2-the-issue-template) to match — the tracker will not
create a label from a template reference, so a mismatch produces unlabelled issues
with no error anywhere.

### 1.2 The required four

Colours are `#RRGGBB` as the GitHub label editor expects. The three `Android *`
sub-labels share a green hue so the family reads as a block in the sidebar;
`Android Security` deliberately breaks the family in red so it is visible in an
unsorted list without reading any text. GitHub picks black or white label text
automatically from background luminance — no separate text colour to set.

---

#### `Android` — `#0B6E4F`

> **Description (paste into GitHub):**
> `Issues related to the Android release of Redoubt`

**Means:** the report is about the Android build. This is the platform label, the
exact sibling of `Linux`, `macOS`, `Windows` and `FreeBSD`.

**Does not mean:** anything about cause, severity or area. It is a routing label,
nothing else.

**Boundary that makes it survive:** *every* Android issue carries it, including ones
that also carry `Android Build`, `Android Prefs` or `Android Security`, and including
ones that turn out to be upstream Gecko bugs. It is never removed during triage, not
even on close. Platform labels are what maintainers filter on; an Android issue
without `Android` is invisible. If you only apply one label to an issue, apply this
one.

**Composes with:** `Type Bug` / `Type Feature` / `Type Question` / `Type Discussion`
(always pick one), `Prio *`, `Status *`, `Needed Info`, `Component Patches`,
`Component Settings`, `Broken Upstream`.

**Do not also create `Build Android`.** Android has three distribution channels and
they get their own `Build *` labels ([§1.3](#13-channel-labels-strongly-recommended)).
A single `Build Android` label would collapse exactly the distinction that the
channel question in the issue template exists to capture.

---

#### `Android Build` — `#3F9E7C`

> **Description:**
> `The Android build itself fails: toolchain, Gradle, fat-AAR, mozconfig`

**Means:** Redoubt does not build, or builds wrong, from source. The
Rust/NDK toolchain, the mozconfig, the fat-AAR step across the three ABIs, the Fenix
Gradle stage, patch application on the Android target, reproducibility mismatches.
Reporters here are almost always packagers or contributors, not users.

**Does not mean:**
- a built APK that misbehaves at runtime — that is a plain `Android` bug;
- which channel the reporter installed from — that is `Build F-Droid` / `Build Accrescent` / `Build APK`;
- a release-pipeline or CI failure with no source-tree cause — that is `Component: Infrastructure`.

**Boundary:** if the reporter never ran a compiler, it is not `Android Build`. That
single question keeps this label from becoming "anything to do with Android",
which is how a build label dies.

**Composes with:** `Component Builds` — and the split between them matters. Use
`Component Builds` when the breakage is in shared build machinery that also hits
desktop (the Makefile, `scripts/librewolf-patches.py`, patch ordering). Use
`Android Build` when it is Android-specific. Use **both** when a shared change broke
only the Android target — that pairing is the standing search for whoever is doing
rebase work (LW-M7-01).

---

#### `Android Prefs` — `#8FCFB6`

> **Description:**
> `A LibreWolf pref is not delivered, not applied, or locked when it should not be, on Android`

**Means:** the pref *plumbing* on Android. Android does not get autoconfig
(`librewolf.cfg` is resolved relative to `NS_GRE_DIR`, which is empty on Android) and
does not get the enterprise-policy engine (gated on
`MOZ_WIDGET_TOOLKIT != "android"`), so every LibreWolf pref arrives through a
different mechanism than on desktop — and that mechanism has its own failure modes:

- a pref that has our value on desktop and Firefox's value on Android;
- a pref that has our value at startup and Fenix's value after the settings screen
  is opened (`MOZ_DEFAULT_PREFS` runs before the profile, Fenix's runtime
  `Pref.commit()` runs after — landmine L2);
- a settings toggle that visibly does nothing because we over-locked the pref
  behind it (also L2, the other direction);
- a pref that cannot be edited in `about:config` because it is `lockPref`-ed
  (LW-M4-09's known interaction with LW-M3-04).

That last one is the highest-volume subcategory to expect and it is usually
**working as designed** — see [§3.2](#32-close-immediately-with-the-boilerplate).

**Does not mean:** disagreement with a pref's *value*. "RFP breaks this site" and
"why is WebGL off" are `Component Settings` questions about LibreWolf's
configuration, and the answer is the same on both platforms. `Android Prefs` is
"the value we ship did not arrive", not "the value we ship is wrong".

**Boundary:** ask *"would this report also be true on desktop LibreWolf?"* If yes,
it is `Component Settings`. If it is Android-only, it is `Android Prefs`.

**Composes with:** `Component Settings` (which owns the settings submodule and pref
values), `Component Patches`, `Status Known issue`, `Status Won't fix`.

---

#### `Android Security` — `#B60205`

> **Description:**
> `Android issue with a security consequence — triage before anything else`

**Means:** a defect in our Android build with a security consequence. Memory-safety
bugs reachable in our APK, a security patch from the shared set that did not apply
on Android, a pref whose absence has a security effect (an unexpected outbound
request, a TLS or HTTPS-Only regression), APK signature or fingerprint mismatch, or
anything suggesting a distribution channel served something we did not sign.

**Does not mean:**
- **the known sandbox gap.** `MOZ_SANDBOX` is off on Android, `toolkit.mozbuild:37`
  never traverses `security/sandbox`, and every `security.sandbox.*` pref is inert.
  We publish this rather than hide it. Reports of it are correct observations of a
  documented gap, not vulnerabilities — see [§3.2](#32-close-immediately-with-the-boilerplate),
  boilerplate **B2**.
- general privacy anxiety, hardening wishlists, or "is Redoubt as secure
  as X" comparisons. Those are `Type Question` or `Type Discussion`.

**Boundary:** the label means *a maintainer looks at this today*. If applying it to
an issue would not change what anyone does in the next 24 hours, it is the wrong
label. Diluting it is how the one real report gets lost.

**Handling is different from every other label:** an exploitable bug **must not stay
in a public issue**. See [§3.3](#33-security-escalation). The label exists for
already-public reports that need marking, and for tracking the public half of a
coordinated fix. It is not the reporting channel.

**Composes with:** `Prio/Urgent`, `Prio High`, `Broken Upstream` +
`Status Upstream` (Gecko bugs go to Mozilla's security process, not Bugzilla's
public queue), `Status Known issue` (for published parity gaps that keep getting
re-reported).

### 1.3 Channel labels (strongly recommended)

The public-release plan has three channels with three different update paths and three
different ways to be broken while the APK is fine. Without these, "everyone on
Accrescent is stuck on the old version" reads as thirty unrelated bug reports. They
use the proposed `Build *` family.

| label | colour | description |
|---|---|---|
| `Build F-Droid` | `#1976D2` | `Issues specific to the Redoubt F-Droid repository` |
| `Build Accrescent` | `#5E35B1` | `Issues specific to the Accrescent release of Redoubt` |
| `Build APK` | `#455A64` | `Issues specific to the direct APK download or Obtainium updates` |

The closed beta uses direct APKs from a private link. Its source option in the
form maps to `Build APK` when channel labelling is relevant, and the maintainer
adds `beta` to identify beta findings. That label also needs to be created before
the form is used for beta triage.

Apply the channel label whenever the reporter's answer to the channel question
([§2](#2-the-issue-template)) is plausibly relevant: install failures, update
failures, signature warnings, "the store shows an old version", wrong ABI. Do not
apply it to ordinary rendering bugs — the channel is irrelevant there and the label
loses meaning.

`Build F-Droid` covers **our own** repo. A report about a third-party F-Droid repo
(IzzyOnDroid, or anyone mirroring us) gets boilerplate **B5** — we cannot support a
binary we did not build, and there is no `Build ThirdParty` label because such
issues are closed, not tracked.

### 1.4 One more, recommended

| label | colour | description |
|---|---|---|
| `Android Needs Repro` | `#D9A441` | `Confirmed-plausible Android report that a maintainer must reproduce on a device` |

This one is load-bearing and [§3.5](#35-needs-a-build-to-reproduce-when-nobody-can-build)
explains why. In short: it is a claim on **maintainer** time, and it is the only
correct alternative to `Needed Info` for a report that is complete but unverified.
Without it, complete reports get `Needed Info` (whose proposed policy is
*"Closing in ten days if no details are provided"*) and auto-die at day ten with
nothing more the reporter could have supplied.

### 1.5 Everything else composes

`Type *`, `Prio *`, `Status *`, `Needed *`, `Flag *`, `Component *`,
`Broken Upstream` and `Docs *` are proposed shared labels; they do not currently
exist on this tracker. Before applying the rules below, create the names used by
the chosen workflow or consistently map them to existing labels. The form itself
needs `Android` and `Type Bug`; beta findings also need `beta`, and retained beta
issues need `Status Known issue` (`BETA.md` G3).

Avoid adding `Android UI`, `Android Performance`, `Android Extensions`
and the rest — `Android` + a shared `Component *` label already expresses each
of those, and a label set nobody can hold in their head stops being applied in week
three.

---

## 2. The issue template

### 2.1 Form choice: YAML issue form, not Markdown

GitHub accepts both. Templates live on the **default branch** of the repository in
`.github/ISSUE_TEMPLATE/`, as a Markdown file (`.md`) or a YAML issue form
(`.yml`/`.yaml`), with a sibling `config.yml` holding `blank_issues_enabled` and
`contact_links`.

**Chosen: `.github/ISSUE_TEMPLATE/android-bug.yml`** — a YAML issue form.

Why, given that a Markdown template is simpler:

1. **`required: true` is enforced by the forge.** A Markdown template is a
   suggestion; the submit button does not care whether the reporter deleted the
   "Device:" line. Roughly the whole cost of Android triage is chasing device, OS
   version and channel after the fact, and the form makes those three
   non-optional at zero maintainer cost.
2. **The channel question needs a fixed vocabulary.** As free text, "F-Droid",
   "fdroid", "the store", "idk, my launcher" are four different answers to the same
   question and none of them are searchable. As a dropdown it is one of six known
   strings, which is what makes `Build *` labelling mechanical.
3. **`labels:` auto-applies `Android` and `Type Bug` on submit.** The one label that
   must never be missing stops depending on a human remembering.

Some reporters prefer a single freeform report. `blank_issues_enabled: true` in
`config.yml` below keeps that path open. Submitted form responses become a normal
Markdown issue body and can be edited after submission.

A Markdown fallback is in [Appendix A](#appendix-a--markdown-fallback-template) for
the case where the form is rejected or a maintainer prefers it.

### 2.2 `.github/ISSUE_TEMPLATE/android-bug.yml`

Create the labels in [§1](#1-labels) **first** — GitHub will not create a label
from a template reference, so an unknown label in the form's `labels:` list is
simply not applied.

```yaml
name: Android bug report
description: Something is wrong in Redoubt
title: "[Android] "
labels:
  - Android
  - Type Bug
body:
  - type: markdown
    attributes:
      value: |
        Thanks for reporting. Redoubt has **no crash reporter** — we
        removed the telemetry and crash-reporting stack — so what you write here is
        genuinely all we get. The device and version fields below are what let us
        tell your report apart from the other thirty filed today.

        **Security bugs do not belong in a public issue.** If this is a
        memory-safety bug, a signature mismatch, or anything that looks like a
        compromised download, close this form and use the private contact path
        linked on the new-issue page instead.

  - type: textarea
    id: what-happens
    attributes:
      label: What happens
      description: What you did, what you expected, what you got instead.
      placeholder: |
        1. Open …
        2. Tap …
        3. Expected: … / Actually: …
    validations:
      required: true

  - type: input
    id: device
    attributes:
      label: Device model
      description: >-
        The marketing name and, if you know it, the model number. Android
        Settings → About phone.
      placeholder: "Pixel 6a (GX7AS) / Samsung Galaxy A54 (SM-A546B)"
    validations:
      required: true

  - type: input
    id: total-ram
    attributes:
      label: Total device RAM (optional)
      description: >-
        Especially useful for slowdowns, background kills, or crashes during the
        closed beta. Give the device's total RAM, not currently free memory.
        Leave this blank if you do not know.
      placeholder: "3 GB / 4 GB / 8 GB"

  - type: input
    id: android-version
    attributes:
      label: Android version
      description: >-
        Android Settings → About phone → Android version. Include the vendor skin
        or custom ROM if you are on one — it changes the answer often enough to
        matter.
      placeholder: "Android 14, One UI 6.1 / Android 15, GrapheneOS"
    validations:
      required: true

  - type: dropdown
    id: apk-source
    attributes:
      label: Where did you install the APK from?
      description: >-
        If you are not sure, this is the single most useful thing you can find out.
        Obtainium and F-Droid both show the source repository in the app's detail
        page.
      options:
        - Closed beta APK from the maintainer's private link
        - The Redoubt F-Droid repository
        - Accrescent
        - Direct APK download from our site
        - Obtainium (tracking the direct APK)
        - A different F-Droid repository or mirror (say which, below)
        - I built it from source
        - I do not know
    validations:
      required: true

  - type: input
    id: app-version
    attributes:
      label: Redoubt version and build ID
      description: >-
        Redoubt → Settings → About Redoubt. Paste the whole version line,
        including the build ID.
      placeholder: "153.0.4-1 (Build #20260815120000)"
    validations:
      required: true

  - type: input
    id: cpu-abi
    attributes:
      label: CPU architecture (optional)
      description: >-
        arm64-v8a on essentially every phone since 2017; armeabi-v7a on older or
        very low-end devices; x86_64 on emulators. Only fill this in if you know it.
      placeholder: "arm64-v8a"

  - type: dropdown
    id: aboutconfig
    attributes:
      label: Have you changed anything in about:config?
      description: >-
        Redoubt ships about:config on release builds. Changed prefs
        are shown first and marked as modified.
      options:
        - "No, everything is at its default"
        - "Yes — the changes are listed below"
        - "I do not remember"
    validations:
      required: true

  - type: textarea
    id: aboutconfig-detail
    attributes:
      label: Which prefs did you change?
      description: >-
        One `pref.name = value` per line. Also list anything you changed in
        Redoubt's own Settings screens, and any extensions you installed beyond
        the preinstalled uBlock Origin.
      render: text

  - type: dropdown
    id: fresh-profile
    attributes:
      label: Does it still happen with a clean profile?
      description: >-
        **This deletes your bookmarks, history and logins — export them first.**
        "Delete browsing data" inside Redoubt is NOT enough; it leaves your
        about:config changes in place. A clean profile means Android Settings →
        Apps → Redoubt → Storage → **Clear storage**, or uninstall and reinstall.
        If you would rather not lose your data, choose the last option — that is a
        fine answer and we will not close the issue for it.
      options:
        - "Yes, it still happens on a clean profile"
        - "No, a clean profile fixes it"
        - "I have not tried"
        - "I would rather not wipe my profile"
    validations:
      required: true

  - type: dropdown
    id: fenix-comparison
    attributes:
      label: Does it also happen in Firefox for Android?
      description: >-
        The most useful single test you can run. If stock Firefox does the same
        thing, it is an upstream Gecko bug and we will route it to Mozilla instead
        of sitting on it. Installing Firefox alongside Redoubt is safe; they do
        not share data.
      options:
        - "Yes, Firefox for Android does it too"
        - "No, Firefox for Android is fine"
        - "I have not tried"
        - "Not applicable (this is about a Redoubt-specific feature)"
    validations:
      required: true

  - type: input
    id: site
    attributes:
      label: Affected site (optional)
      description: >-
        If it is site-specific, the exact URL. If the site is private or sensitive,
        say so instead of pasting it.

  - type: textarea
    id: logs
    attributes:
      label: Logs (optional, very welcome)
      description: >-
        There is no crash reporter, so `adb logcat` is the only way we see a crash.
        With USB debugging on and the device connected:
        `adb logcat -d > redoubt.txt` right after reproducing, then attach the
        file. Read it first — logcat can contain URLs you have visited.
      render: shell

  - type: checkboxes
    id: confirmations
    attributes:
      label: Before you file
      options:
        - label: >-
            I searched the existing issues, including closed ones, for this problem.
          required: true
        - label: >-
            This is not a security vulnerability. (If it is, use the private
            contact path instead — see the top of this form.)
          required: true
        - label: >-
            I understand that Redoubt has a weaker process sandbox
            than LibreWolf on desktop, that this is documented and deliberate, and
            that my report is about something else.
          required: false
```

### 2.3 `.github/ISSUE_TEMPLATE/config.yml`

```yaml
blank_issues_enabled: true
contact_links:
  - name: Security vulnerability — do NOT open a public issue
    url: https://github.com/CPlusPlus17/Redoubt/security/advisories/new
    about: >-
      Memory-safety bugs, APK signature mismatches, or anything suggesting a
      distribution channel served a build we did not sign. Report these privately
      through GitHub's security advisories. The full process, including the
      signature- and channel-compromise cases, is in docs/android/SECURITY.md.
  - name: Questions, support and general chat
    url: https://github.com/CPlusPlus17/Redoubt/issues
    about: >-
      "How do I …" and "why does Redoubt …" — open a normal issue for now.
      Update this link when a public support page or chat room is available.
```

The security URL is this repository's private vulnerability-reporting page;
`gh api repos/CPlusPlus17/Redoubt/private-vulnerability-reporting` returned
`{"enabled":true}` on 2026-09-08. The questions link uses the existing issue
tracker until a public support page is available. Neither link requires a
placeholder substitution. The configuration still needs publication to the default
branch and a live chooser check (steps 6–7 below).

`blank_issues_enabled: true` is deliberate. Forcing every report through a form
also blocks the person who has read the code and wants to explain a race condition
in four paragraphs, and we lose more from blocking them than we gain from the last
few percent of form compliance.

---

## 3. Triage rules

### 3.1 The daily pass

In this order. It takes ten to twenty minutes at launch volume.

1. **Security scan, first, always.** Read every new issue's title and first
   paragraph for signs of a real vulnerability before doing anything else.
   [§3.3](#33-security-escalation) if anything qualifies. Do this before triaging
   anything, because the whole point of ordering is that a real report never waits
   behind duplicate build questions.
2. **Unlabelled issues.** The form applies `Android` + `Type Bug` on submit, so
   anything Android-related without those came in as a blank issue. Label it.
3. **Close what closes.** [§3.2](#32-close-immediately-with-the-boilerplate),
   using the boilerplate verbatim.
4. **Route the rest.** Upstream or ours ([§3.4](#34-upstream-gecko-or-ours)); add
   the area label; add the channel label if the channel is relevant.
5. **The `Android Needs Repro` queue.** Anything sitting there more than three days
   gets a comment saying where it stands, even if that comment is "not reproduced
   yet, still queued". Silence is what turns one bug into five duplicates.

**Every new Android issue gets a label and a human reply within 24 hours during the
launch window.** A label is not a reply. "Thanks, labelled, looking at it" is.

### 3.2 Close immediately, with the boilerplate

These are closed on sight, politely, with the canned reply. Everything else gets
read properly.

| report | labels on close | reply |
|---|---|---|
| "Put it on the Play Store" | `Android`, `Type Feature`, `Status Not Planned` | **B1** |
| "There is no sandbox / no site isolation / `security.sandbox.*` does nothing" | `Android`, `Android Security`, `Status Known issue` | **B2** |
| Missing device / Android version / channel (blank issue) | `Android`, `Needed Info` | **B3** — *do not close yet;* `Needed Info` already means "closing in ten days if no details are provided" |
| Reproduces identically in stock Firefox for Android | `Android`, `Broken Upstream`, `Status Upstream` | **B4** |
| Built by a third party (someone else's F-Droid repo, a repack, a modded APK) | `Android`, `Status Won't fix` | **B5** |
| "Why did you reverse the IronFox recommendation / why not just use IronFox" | `Android`, `Type Discussion` | **B7** |
| Duplicate | `Android`, `Status Duplicate` | link the original, one line, no template needed |
| "Pref X cannot be edited in about:config" where X is deliberately locked | `Android`, `Android Prefs`, `Status Known issue` | **B8** |

Two things that look closable and are **not**:

- **"It is slow / it runs out of memory on my phone."** This is the single most
  likely real defect at launch. Site isolation (LW-M5-01) plus `isolatedProcess`
  plus the app zygote (LW-M5-02) cost memory that is invisible on a flagship and
  decisive on a 3 GB device — which is exactly why LW-M7-06 weights the closed beta
  toward low-RAM hardware. Label `Android`, keep it open, ask for the device and
  total RAM, and make sure the beta owner sees it.
- **"WebGL does not work on any site."** Never close this as a site bug. It is the
  signature of landmine L1 — see [§3.4](#34-upstream-gecko-or-ours). Escalate.

#### Boilerplate replies

Paste verbatim. They are deliberately not curt; a first-week reporter who gets a
brush-off does not file the second, better report.

**B1 — Play Store**

```
Thanks for asking. The Play Store is out of scope for Redoubt on Android, and it
is a deliberate decision rather than a to-do item.

Play requires either Google's app signing (which means handing over the signing key)
or Play App Signing enrollment, and our release model is that the key never exists
anywhere but offline: CI publishes unsigned artifacts and hashes, and a maintainer
signs by hand. That is not compatible with Play, so this is not something we plan to
revisit.

Redoubt is available from our own F-Droid repository, from Accrescent,
and as a direct APK that works with Obtainium. All three carry the same signing
fingerprint, which is published on the download page.

Closing as not planned — but please do file anything else you run into.
```

**B2 — the sandbox gap**

```
You are reading this correctly, and it is documented rather than accidental.

Gecko's content-process sandbox (MOZ_SANDBOX) is not built on Android: the build
system never traverses security/sandbox on this platform, so every security.sandbox.*
preference you can see in about:config is inert. That is upstream Gecko's situation
on Android, not something LibreWolf turned off, and we cannot turn it on from where
we sit.

What we do instead is use Android's own containment, which stock Firefox for Android
does not: isolated processes, the app zygote, and per-site process isolation
(fission.webContentIsolationStrategy), which Android Firefox ships disabled. That
recovers most of the gap and we do not claim it recovers all of it.

Our position, in full: Redoubt ships the same privacy configuration and
the same Gecko-level security patches as LibreWolf desktop, on a platform whose
process containment is weaker — and we publish exactly where. See PARITY.md for the
row-by-row version.

Closing as a known issue. If you have found a way in which the containment we DO have
fails to hold, that is a different and very welcome report — please use the private
security contact for it.
```

*Until LW-M5-06 lands, replace the `PARITY.md` reference with "the security section
of the Android download page" — do not link a URL that 404s.*

**B3 — missing information**

```
Thanks for the report. To tell this apart from the other reports open right now, we
need three things that are not in the issue yet:

- your device model (Android Settings → About phone)
- your Android version, including the vendor skin or custom ROM if you are on one
- where you installed the APK from (our F-Droid repo, Accrescent, direct download,
  Obtainium, or built from source)

and, if you have it, your Redoubt version and build ID from Settings → About
Redoubt.

There is no crash reporter in this build, so we genuinely cannot see any of this from
here. The "Android bug report" template collects all of it if you would rather refile.

Tagged as needing info — it will close automatically in ten days if we do not hear
back, and reopening it later is fine.
```

**B4 — upstream**

```
Thanks — that is a useful test result, and it points away from us.

If stock Firefox for Android does the same thing on the same version, the bug is in
Gecko rather than in anything Redoubt changes, and it needs to go to Mozilla:

  https://bugzilla.mozilla.org/enter_bug.cgi?product=Fenix

One caveat worth knowing: Redoubt tracks Firefox ESR, so we are usually
behind the Firefox release you compared against. If the version numbers differ a lot,
the bug may already be fixed upstream and simply not have reached our branch yet.

Marking as upstream and closing here. If you file it with Mozilla, please link the
Bugzilla bug in a comment so anyone who finds this issue can follow it.
```

**B5 — third-party build**

```
Thanks for the report, but we cannot act on this one: that build is not ours.

We publish Redoubt through our own F-Droid repository, Accrescent, and
a direct APK download. Anything else — a mirror, a repackage, a modified APK — is
built and signed by someone we do not control, so we cannot tell whether the problem
is in our source or in their build, and we cannot verify what is actually in the
binary you are running.

You can check what you have installed against the signing fingerprint published on
our download page. If it matches, please reopen this and say so — that would mean the
build IS ours and this reply is wrong. If it does not match, please report it to
whoever produced it.

Closing as won't fix.
```

**B6 — security report filed publicly** (see [§3.3](#33-security-escalation); post
this *before* deleting anything)

```
Thank you for finding this, and please contact us privately about it:

  <private security contact>

We are going to remove this issue shortly so that the details are not public while a
fix is unreleased. That is not a dismissal of the report — we have a copy, we are
treating it as valid, and you will hear back from us at the address above. If you have
a preference about credit in the eventual advisory, tell us there.

Apologies for the abruptness; the alternative is leaving it up.
```

**B7 — the IronFox reversal**

```
Fair question, and the short answer is that our previous answer was "use IronFox",
that was honest advice at the time, and it changed because we now have an Android
build of our own rather than because anything got worse over there.

IronFox has served users who wanted a hardened Android browser for years, does real
work we did not do, and remains a reasonable choice. The comparison on our FAQ is
meant to be factual about what differs rather than a pitch, and if you think a
specific line of it is unfair, say which line — that is a correction we would make.

Moving this to a discussion; the FAQ has the longer version.
```

**B8 — locked pref**

```
That one is locked on purpose, and it is worth explaining why the lock exists rather
than just leaving it as "won't fix".

On Android, LibreWolf's preferences arrive through a different mechanism than on
desktop, and Firefox's own settings code rewrites some of them after startup — after
our values have already been applied. For those prefs, locking is the only thing that
makes our value stick; without it, the setting would appear to work and then silently
revert. The visible cost is that you cannot edit it in about:config.

If you want the opposite value for a specific reason, tell us which pref and what for.
The set of locked prefs is a judgement call rather than a law, and the list has been
wrong before.

Closing as a known issue.
```

### 3.3 Security escalation

**What qualifies:** memory-safety bugs reachable in our APK; a security patch from
the shared set that silently did not apply on Android; an APK whose signing
fingerprint does not match the published one; any sign that F-Droid, Accrescent or
the direct download served a binary we did not sign; unexpected outbound network
requests from a build that should make none before first navigation; a demonstrated
way past the containment we *do* have (isolated processes, the app zygote, the
locked isolation strategy).

**What does not qualify:** the documented sandbox gap (**B2**); "Redoubt is less
secure than $BROWSER" comparisons; hardening wishlists; anything that is a privacy
preference argument rather than a defect.

**Where it goes:** the private disclosure path in `docs/android/SECURITY.md`
(**LW-M7-05**). The same rule holds regardless: **not the public tracker.**

**If it arrives as a public issue anyway** — which it will, at least once, in week
one:

1. **Do not comment on the technical content.** Not to confirm it, not to ask a
   clarifying question. A maintainer replying "yes, that's exploitable" is worth more
   to an attacker than the original report.
2. **Copy the full issue and every comment somewhere private** before touching it.
   This step is not optional and it is the one people skip.
3. Post **B6**, with the real contact address substituted.
4. **Delete the issue** (GitHub: the issue page → `⋯` → Delete issue). Editing the
   text out is not enough — GitHub keeps the edit history and it is visible to
   ordinary users.
   Deleting is destructive and irreversible, which is exactly why step 2 comes first.
5. Continue privately. Tell the reporter what will happen and roughly when.
6. Once fixed and released, open a **new** public issue with `Android`,
   `Android Security`, `Status Known issue`, describing the fix and crediting the
   reporter if they want it, and link it from the original's replacement.

For a **Gecko** security bug, do not file it in public Bugzilla either — Mozilla has
its own security-bug process and public Bugzilla defeats it. Route it there and hold
our side until Mozilla's embargo lifts.

For a **channel compromise** (fingerprint mismatch, unexpected APK): treat it as an
incident, not an issue. Pull the affected channel's index before investigating —
`Prio/Urgent` on the tracking issue — and assume it is real until it is disproved.
This is the one category where over-reacting is cheap and under-reacting is not.

### 3.4 Upstream Gecko or ours

Work the ladder top down and stop at the first answer. Most reports resolve at step 1
or 2.

**1. Does stock Firefox for Android do it too?**
Yes → `Broken Upstream` + `Status Upstream`, boilerplate **B4**. This is the
strongest single signal and it is why the template asks. Caveat: we track **esr153**
and Firefox release runs far ahead, so a version mismatch weakens the comparison in
both directions — something fixed upstream months ago can still be live for us. When
it matters, compare against **Tor Browser for Android**, which shares our ESR base
(ROADMAP.md, "Release track").

**2. Does it survive a clean profile?**
No → it is configuration, theirs or ours. Ask which prefs they changed; if flipping
one of ours fixes it, it is `Android Prefs` or `Component Settings` — not a Gecko
bug — and the useful outcome is a documented pref, not a patch.

**3. Does it also happen on LibreWolf desktop with the same prefs?**
Yes → shared, `Component Patches` or `Component Settings`, and drop `Android`?
**No — keep `Android`.** Keep the platform label and add the shared area label. The
reporter is on Android and that is how they will find the issue again.
No, Android only → it is ours, and it is almost certainly the Android *plumbing*:
pref delivery (`Android Prefs`), a patch that applies differently on this target
(`Component Patches` + `Android`), or something removed in M4.

**4. Is it a feature that exists in Firefox for Android and simply is not there?**
Then it is probably ours *by intent*. M4 removes Glean, Adjust, Nimbus, Socorro,
Play Integrity, Firebase, sponsored tiles, onboarding and search suggestions. A
feature gated behind a Nimbus flag is permanently off in our build and on in stock
Firefox, which looks exactly like a Gecko regression and is not one. Before
labelling anything in this shape as a bug, check whether we removed the thing.

**The two Android-specific smells worth memorising**, because both are silent and
both will arrive misdiagnosed:

- **"WebGL fails on every site, with no error."** Landmine L1. `librewolf.webgl.prompt`
  compiled as `true` on Android makes every WebGL context fail closed, with no crash
  and no console message, because the code that would answer the permission prompt
  lives in the desktop-only half. This is ours, it is total rather than
  site-specific, and it passes every smoke test that does not check for a live
  context. Never route it upstream and never close it as a site issue.
- **"A toggle in Settings does nothing."** Landmine L2, over-locking. Fenix's runtime
  `Pref.commit()` runs after our defaults land, so anything Fenix mutates must be
  locked to stick — and locking a pref that the settings UI owns makes its switch
  visibly inert. `Android Prefs`, ours, and the fix is the must-not-lock allowlist,
  not the settings code.

### 3.5 "Needs a build to reproduce" when nobody can build

Assume **no reporter can build Redoubt.** It is a multi-hour Gecko
build with an Android NDK toolchain and a fat-AAR step across three ABIs. Asking a
reporter to bisect, apply a patch, or test a dev build is asking them to leave, and
they will.

So `Android Needs Repro` means one thing:

> **A maintainer, on hardware we control, has to reproduce this. The reporter has
> already done everything they can do.**

The rules that follow from that, all of which exist because the opposite happens by
default:

1. **It never pairs with `Needed Info`.** `Needed Info` on this tracker means
   "closing in ten days if no details are provided". Applying it to a complete report
   nobody has reproduced yet closes a real bug for the reporter's failure to do
   something impossible. If the report is complete, it is `Android Needs Repro` and
   it is our queue, not theirs.
2. **It is never a reason to close for inactivity.** There is no inactivity — there
   is nothing for the reporter to be active about.
3. **Not reproduced is a result, and it gets said out loud.** "Two of us tried on a
   Pixel 6a and a Galaxy A54, Android 14 and 15, and could not reproduce" is a
   comment worth writing. It tells the reporter what we did, invites the detail that
   distinguishes their device, and is honest in a way that closing silently is not.
4. **What we ask for instead of a build:** `adb logcat` output (with the command in
   the ask, and the warning that logcat contains visited URLs); the exact modified
   prefs from about:config; the version and build ID; a screen recording for anything
   visual; and whether stock Firefox for Android does it too. That is the ceiling of
   what a reporter can provide, and asking for anything past it wastes both sides'
   time.
5. **The device set is the beta's device set.** LW-M7-06 assembles a device spread
   weighted toward low-RAM hardware. That is the reproduction fleet — whoever owns
   this queue needs to know who holds which device, so record it next to the OWNER
   block above.
6. **It has a decay rule.** Anything in `Android Needs Repro` for more than 30 days
   without a reproduction attempt gets `Status Icebox` and a comment saying so.
   Not closed, not pretended to be active. A queue that only grows is a queue nobody
   reads.

---

## 4. Reports we expect in week one

Written down so the rotation owner recognises them rather than diagnosing each one
from scratch. This is a prediction, not data; correct it after the first week.

| expect | first move |
|---|---|
| "Which one do I install / is F-Droid the official one" | `Type Question`, point at the download page, consider FAQ text if it repeats |
| Sandbox / site-isolation observations | **B2**, `Status Known issue` |
| Play Store requests | **B1** |
| Update did not arrive on one channel | channel label + `Component: Infrastructure`; check the channel index before assuming it is the app |
| Slow / OOM on low-RAM devices | keep open, get device + RAM, route to the beta owner — treat as a real defect |
| Site breakage from RFP or ETP | `Component Settings`; the same on desktop, so check there first |
| "Extension X does not work" | `Android`, then ask whether it works in stock Firefox for Android — the add-on story is Fenix's, not ours |
| A real Gecko bug | ladder in [§3.4](#34-upstream-gecko-or-ours) |
| A real security report, filed publicly | [§3.3](#33-security-escalation), immediately |

---

## 5. The launch-window rotation

**Window:** opens the day the Android download page goes live (LW-M7-02); runs
14 days minimum. Closes when both hold for three consecutive days: fewer than three
new Android issues per day, and nothing open in `Android Security` or
`Android Needs Repro` untouched for more than three days. Otherwise it extends a
week at a time.

**Roles:** the `OWNER` named in [§0](#0-triage-owner--launch-blocker) carries this
window alone under the recorded 2026-09-06 decision. `BACKUP` remains empty until
someone accepts that role. Response targets below still apply; the solo-owner
decision does not provide coverage during an absence or change those targets.

**The daily commitment:** one pass ([§3.1](#31-the-daily-pass)), ten to twenty
minutes at expected volume. Not "monitor the tracker" — one pass, at a time of day
the owner picks and keeps.

**Response targets during the window:**

| | target |
|---|---|
| security-shaped report, acknowledged and removed from public view | 4 hours waking, 24 hours absolute |
| any new Android issue: label + human reply | 24 hours |
| `Android Needs Repro`: status comment | every 3 days |
| everything else | best effort |

Post-window these relax to whatever the tracker's normal cadence is. The point of
the window is the first fortnight specifically.

**Handover** (owner → backup if one is appointed, or window → normal): a comment on the tracking issue
listing what is open in `Android Security` and `Android Needs Repro`, anything
promised to a reporter and not delivered, and any pattern seen more than twice.
That last item is the output that outlives the rotation — three reports of the same
thing is a docs fix, a FAQ entry, or a bug, and the person who noticed is the only
one who knows.

**After the window:** whoever holds it writes five lines here on what the label set
got wrong. Label sets are always wrong on contact and the fix is cheap in week
three, expensive in month six.

---

## 6. Maintainer checklist

The local files and owner decision are prepared. Publishing templates and creating
labels need write access to `github.com/CPlusPlus17/Redoubt` and remain pending
as of 2026-09-08. Order matters: labels before templates, because GitHub will not
create a label from a template reference.

1. **Create the four required labels** ([§1.2](#12-the-required-four)). Repository →
   Issues → Labels → New label. Name, description and colour are given verbatim for
   each:
   `Android` `#0B6E4F` · `Android Build` `#3F9E7C` · `Android Prefs` `#8FCFB6` ·
   `Android Security` `#B60205`
   Reconcile the proposed shared labels with the current defaults first (§1.1).
   The current form additionally requires `Type Bug`. For the beta, create `beta`
   and `Status Known issue`; create or map every shared label used by the triage
   rules before relying on those rules.
2. **Create the three channel labels** ([§1.3](#13-channel-labels-strongly-recommended)):
   `Build F-Droid` `#1976D2` · `Build Accrescent` `#5E35B1` · `Build APK` `#455A64`
3. **Create `Android Needs Repro`** `#D9A441` ([§1.4](#14-one-more-recommended)).
   If you skip this one, delete [§3.5](#35-needs-a-build-to-reproduce-when-nobody-can-build)'s
   rules too rather than leaving policy that references a label that does not exist.
4. **Confirm the repository has a default branch with at least one commit.** Issue
   templates are read from the default branch only. (This repository is the source
   tree, so it already has one — this step is a guard, not a gap.)
5. **Publish `.github/ISSUE_TEMPLATE/android-bug.yml` on the default branch**
   ([§2.2](#22-githubissue_templateandroid-bugyml)). It already exists locally;
   a local commit or a feature-branch push does not make the form live.
6. **Publish `.github/ISSUE_TEMPLATE/config.yml` on the default branch**
   ([§2.3](#23-githubissue_templateconfigyml)). The local configuration points to
   this repository's private vulnerability reporting, which was enabled when
   checked on 2026-09-08. Recheck the security contact before publication.
7. **File a test issue through the new template** and confirm: the chooser shows
   "Android bug report"; the security contact link appears above the templates;
   `Android` and `Type Bug` are applied automatically on submit; the form refuses to
   submit with device, Android version, channel, app version, about:config,
   fresh-profile or the Firefox-comparison field empty. Then delete the test issue.
   This is the `verify` for LW-M7-04.
8. **Confirm the named `OWNER` and recorded solo-owner decision** in
   [§0](#0-triage-owner--launch-blocker). Both were recorded on 2026-09-06.
   Appointing a backup later does not require revisiting that decision. An empty
   owner field would still block the Android launch.
9. **Record who holds which device** from the LW-M7-06 beta fleet, next to the OWNER
   block. The `Android Needs Repro` queue is unworkable without it.
10. *(optional)* Create an `android-launch` milestone on the tracker and put the
    launch-window issues in it, so the retrospective in
    [§5](#5-the-launch-window-rotation) has something to read.
11. *(optional)* Build the two saved searches the daily pass uses — filter the issue
    list by `Android` + `Android Security`, and by `Android Needs Repro`, then
    bookmark the resulting URLs. GitHub filters issues by label name (for example
    `is:issue label:"Android Security"`), so the saved-search URLs only exist once
    those labels exist and cannot be written here.

Not in scope for this checklist, owned by other tasks: reopening or updating
**issue #2169** and the FAQ's IronFox recommendation are **LW-M7-03**; the Android
disclosure process is **LW-M7-05**; `PARITY.md` is **LW-M5-06**.

---

## 7. What this document does not decide

- **Label names and colours are a publication plan.** The live tracker has the
  default labels listed in §1.1. Reconcile the proposed vocabulary consistently
  before publishing the form; no labels were changed by this audit.
- **The security contact is configured locally.** Private vulnerability reporting
  was enabled on 2026-09-08, but the issue chooser configuration is not published.
- **The parity wording is approved.** `PARITY.md` §5 records owner signoff dated
  2026-09-06. Its publication with the parity table is separate public-release work.
- **Live form verification remains outstanding.** Read-only API checks proved the
  template is absent from the default branch. No issue was submitted, and local
  schema checks do not satisfy LW-M7-04's manual verification.

---

## Appendix A — Markdown fallback template

Use only if the YAML form in [§2.2](#22-githubissue_templateandroid-bugyml) is
rejected or a maintainer prefers Markdown. It asks the same questions and enforces
none of them, which is the entire trade.

Path: `.github/ISSUE_TEMPLATE/android-bug.md`

```markdown
---
name: Android bug report
about: Something is wrong in Redoubt
title: "[Android] "
labels:
  - Android
  - Type Bug
---

<!--
  Redoubt has NO crash reporter, so what you write here is all we get.
  Please do not delete the fields below — an issue without device, Android version
  and install source cannot be told apart from the others filed today.

  SECURITY BUGS DO NOT GO HERE. Memory-safety bugs, signature mismatches or a
  suspicious download go to the private security contact on the new-issue page.
-->

### What happens

<!-- What you did, what you expected, what you got instead. -->

### Device and build

- **Device model:**              <!-- e.g. Pixel 6a — Settings → About phone -->
- **Total device RAM (optional):** <!-- total RAM, e.g. 3 GB / 4 GB / 8 GB -->
- **Android version:**           <!-- e.g. Android 14, One UI 6.1 / GrapheneOS -->
- **Installed from:**            <!-- closed beta APK from private link /
                                      Redoubt F-Droid repo / Accrescent / direct APK
                                      from our site / Obtainium / another F-Droid
                                      repo (which?) / built from source / not sure -->
- **Redoubt version + build ID:**  <!-- Settings → About Redoubt, whole line -->
- **CPU architecture (optional):**   <!-- arm64-v8a on nearly all phones -->

### Configuration

- **Changed anything in about:config?**  <!-- no / yes (list below) / do not remember -->

<!-- One `pref.name = value` per line, plus any Settings changes and any extensions
     beyond the preinstalled uBlock Origin. -->

### Narrowing it down

- **Still happens with a clean profile?**  <!-- yes / no / not tried / would rather not -->

  <!-- A clean profile means Android Settings → Apps → Redoubt → Storage → Clear
       storage, or uninstall and reinstall. THIS DELETES BOOKMARKS, HISTORY AND
       LOGINS — export first. "Delete browsing data" inside Redoubt is not enough;
       it leaves about:config changes in place. "Would rather not" is a fine answer. -->

- **Does stock Firefox for Android do it too?**  <!-- yes / no / not tried / n-a -->

  <!-- The most useful test you can run. If Firefox does it too, it is an upstream
       Gecko bug and we will route it to Mozilla. -->

- **Affected site (optional):**

### Logs (optional, very welcome)

<!-- No crash reporter, so `adb logcat` is the only way we see a crash:
       adb logcat -d > redoubt.txt
     right after reproducing, then attach it. Read it first — it contains URLs you
     have visited. -->

### Before you file

- [ ] I searched existing issues, including closed ones.
- [ ] This is not a security vulnerability.
- [ ] I know Redoubt has a weaker process sandbox than desktop, that
      this is documented and deliberate, and my report is about something else.
```
