#!/usr/bin/env python3
"""
Validator and query tool for the Redoubt task board.

    python3 docs/android/board.py --check          # graph + ownership integrity
    python3 docs/android/board.py --waves          # parallel wave assignment
    python3 docs/android/board.py --ready          # tasks startable right now
    python3 docs/android/board.py --ready --done LW-M0-01,LW-M0-04
    python3 docs/android/board.py --show LW-M1-08  # one task in full
    python3 docs/android/board.py --stats          # effort, critical path
    python3 docs/android/board.py --check-fenix-tests   # subtract the LW-M2-09 allowlist

The --check pass is what keeps parallel agents from colliding. It enforces:

  * ids unique, well-formed, and consistent with their milestone
  * every depends_on target exists
  * no dependency cycles
  * no two tasks in the same wave own the same path
  * no two tasks in the same wave patch the same file in the extracted tree
  * a path in one task's `owns` is never in another same-wave task's `shared_edit`
  * required fields present and non-empty

Subcommands referenced by task `verify` lines but not yet implemented (they need
artifacts a later task produces) exit 2 with the id of the task that owns them.
"""

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("error: PyYAML required — pip install pyyaml")

BOARD = Path(__file__).resolve().parent / "tasks.yaml"

REQUIRED = ("id", "title", "milestone", "depends_on", "owns", "what",
            "acceptance", "verify", "effort_h", "skills", "agent_safe",
            "isolation", "risk")

# verify-subcommands that only become meaningful once their owning task lands
DEFERRED = {}

# The two GeckoView classes that declare prefs Fenix owns at runtime. A pref
# declared here and shipped unlocked by us is landmine L2: our value survives
# startup and is then overwritten the moment Fenix touches it.
GV_PREF_DECLARERS = (
    "mobile/android/geckoview/src/main/java/org/mozilla/geckoview/GeckoRuntimeSettings.java",
    "mobile/android/geckoview/src/main/java/org/mozilla/geckoview/ContentBlocking.java",
)
LOCK_MARKER = "[ANDROID: LOCK]"
DECISIONS = Path(__file__).resolve().parent / "must-not-lock.txt"

# Bare pref() calls on GeckoView-declared prefs that LW-M3-09 is chartered to fix.
# Declared debt, not tolerated debt: these three warn, anything NOT in this set is a
# hard error. A permanently-red gate teaches people to ignore it; a ratchet does not.
# Shrink this set as LW-M3-09 lands; never grow it.
BARE_PREF_BACKLOG = {
    "browser.contentblocking.category",     # the measured casualty: reads "standard" on Android
    "devtools.console.stdout.chrome",
    "devtools.debugger.remote-enabled",
}


def load():
    doc = yaml.safe_load(BOARD.read_text())
    tasks = {t["id"]: t for t in doc["tasks"]}
    return doc, tasks


def waves(tasks):
    """Longest-path layering. Wave N can run fully in parallel."""
    depth, visiting = {}, set()

    def d(tid):
        if tid in depth:
            return depth[tid]
        if tid in visiting:
            raise ValueError(f"dependency cycle through {tid}")
        visiting.add(tid)
        deps = tasks[tid].get("depends_on") or []
        depth[tid] = 0 if not deps else 1 + max(d(x) for x in deps)
        visiting.discard(tid)
        return depth[tid]

    for tid in tasks:
        d(tid)
    return depth


def check(doc, tasks):
    errs, warns = [], []

    for tid, t in tasks.items():
        for f in REQUIRED:
            if f not in t or t[f] in (None, "", []):
                if f == "depends_on":       # legitimately empty for roots
                    continue
                errs.append(f"{tid}: missing or empty field '{f}'")
        if not tid.startswith("LW-"):
            errs.append(f"{tid}: id must start with LW-")
        elif tid.split("-")[1] != t.get("milestone"):
            errs.append(f"{tid}: id milestone != milestone field {t.get('milestone')!r}")
        if t.get("agent_safe") not in (True, False):
            errs.append(f"{tid}: agent_safe must be yes/no, got {t.get('agent_safe')!r}")
        if t.get("isolation") not in ("none", "worktree"):
            errs.append(f"{tid}: isolation must be none|worktree")
        if len(t.get("title", "")) > 70:
            warns.append(f"{tid}: title is {len(t['title'])} chars (>70)")
        for dep in t.get("depends_on") or []:
            if dep not in tasks:
                errs.append(f"{tid}: depends_on unknown task {dep}")

    if errs:
        return errs, warns

    try:
        depth = waves(tasks)
    except ValueError as e:
        return [str(e)], warns

    by_wave = defaultdict(list)
    for tid, w in depth.items():
        by_wave[w].append(tid)

    for w, members in sorted(by_wave.items()):
        for field in ("owns", "tree_paths"):
            claims = defaultdict(list)
            for tid in members:
                for p in tasks[tid].get(field) or []:
                    claims[p].append(tid)
            for path, holders in sorted(claims.items()):
                if len(holders) > 1:
                    errs.append(
                        f"wave {w}: {field} collision on {path} "
                        f"between {', '.join(sorted(holders))} — order them with depends_on"
                    )
        owned = {p for tid in members for p in (tasks[tid].get("owns") or [])}
        for tid in members:
            for p in tasks[tid].get("shared_edit") or []:
                if p in owned:
                    errs.append(
                        f"wave {w}: {p} is shared_edit for {tid} but owned exclusively "
                        f"by another task in the same wave"
                    )
    return errs, warns


def cmd_check(doc, tasks):
    errs, warns = check(doc, tasks)
    for w in warns:
        print(f"warn:  {w}")
    for e in errs:
        print(f"error: {e}")
    if errs:
        print(f"\n{len(errs)} error(s)")
        return 1
    depth = waves(tasks)
    print(f"ok: {len(tasks)} tasks, {max(depth.values()) + 1} waves, "
          f"{len(warns)} warning(s)")
    return 0


def cmd_waves(doc, tasks):
    depth = waves(tasks)
    by_wave = defaultdict(list)
    for tid, w in depth.items():
        by_wave[w].append(tid)
    for w, members in sorted(by_wave.items()):
        members.sort()
        print(f"\nwave {w}  ({len(members)} tasks can run in parallel)")
        for tid in members:
            t = tasks[tid]
            flag = "" if t["agent_safe"] else "  [needs a human]"
            print(f"    {tid}  {t['title']}{flag}")
    print(f"\nmax useful concurrency: {max(len(m) for m in by_wave.values())} agents")
    return 0


def cmd_ready(doc, tasks, done):
    done = set(done)
    unknown = done - set(tasks)
    if unknown:
        print(f"error: unknown task id(s): {', '.join(sorted(unknown))}")
        return 1
    ready = [t for tid, t in tasks.items()
             if tid not in done and all(d in done for d in (t.get("depends_on") or []))]
    if not ready:
        print("nothing ready — check --waves for what is blocking")
        return 0
    ready.sort(key=lambda t: t["id"])
    print(f"{len(ready)} task(s) startable with {len(done)} done:\n")
    for t in ready:
        flag = "" if t["agent_safe"] else "  [needs a human]"
        iso = "  (worktree)" if t["isolation"] == "worktree" else ""
        print(f"  {t['id']}  {t['title']}{flag}{iso}")
        print(f"      effort {t['effort_h']}h   skills: {', '.join(t['skills'])}")
    return 0


def cmd_show(doc, tasks, tid):
    t = tasks.get(tid)
    if not t:
        print(f"error: no such task {tid}")
        return 1
    print(yaml.safe_dump(t, sort_keys=False, width=88, allow_unicode=True))
    return 0


REPO = Path(__file__).resolve().parent.parent.parent

# Options whose absence from the Android mozconfig is a PARITY LOSS, not a
# platform difference. Each may be omitted only if a comment in mozconfig.android
# names it and says why — that is the whole contract this check enforces.
HARDENING = (
    "--enable-hardening",
    "--enable-stl-hardening",
    "--enable-replace-malloc",
    "--enable-jemalloc",
    "--enable-rust-simd",
)
# Compiler flags that must appear in both CFLAGS and CXXFLAGS. On a release build
# these are the only thing zero-initialising locals — toolchain.configure adds
# -ftrivial-auto-var-init=pattern on debug builds only.
HARDENING_FLAGS = ("-ftrivial-auto-var-init=zero", "-fwrapv")

# An option may only be absent if a comment DELIBERATELY declares it omitted with
# this exact marker. A bare "is the name mentioned anywhere in the comments" test
# is not good enough: every flag is named in the comment that explains why it is
# there, so the escape hatch fired unconditionally and deleting -fwrapv from the
# live CFLAGS line produced a warning while the gate still exited 0. Found by the
# skeptical verification of LW-M2-05.
OMIT_MARKER = "MOZCONFIG-OMIT:"


def _mozconfig_options(path):
    """{normalised option -> raw line} from the non-comment lines, plus the
    concatenated comment text for the escape-hatch lookup."""
    opts, comments, raw = {}, [], []
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            comments.append(s)
            continue
        raw.append(s)
        if s.startswith("ac_add_options "):
            key = s[len("ac_add_options "):].strip().split("=")[0]
        elif s.startswith("export "):
            key = s[len("export "):].strip().split("=")[0]
        elif s.startswith("mk_add_options "):
            key = s[len("mk_add_options "):].strip().split("=")[0]
        else:
            continue
        opts[key] = s
    return opts, "\n".join(comments), raw


def cmd_diff_mozconfig(strict):
    desktop_p = REPO / "assets" / "mozconfig"
    android_p = REPO / "assets" / "mozconfig.android"
    if not android_p.exists():
        print(f"error: {android_p} does not exist — LW-M0-03 has not landed")
        return 2

    d_opts, _, _ = _mozconfig_options(desktop_p)
    a_opts, a_comments, a_raw = _mozconfig_options(android_p)

    errs, warns = [], []

    def deliberately_omitted(name):
        """A comment must say `MOZCONFIG-OMIT: <name>` — merely mentioning the
        name is not enough, see OMIT_MARKER."""
        return any(name in line.split(OMIT_MARKER, 1)[1]
                   for line in a_comments.splitlines() if OMIT_MARKER in line)

    for opt in HARDENING:
        if opt in a_opts:
            continue
        if deliberately_omitted(opt):
            warns.append(f"{opt}: absent, declared omitted with {OMIT_MARKER}")
        else:
            errs.append(
                f"{opt}: present in assets/mozconfig, absent from mozconfig.android, "
                f"and no `{OMIT_MARKER} {opt}` comment declares that deliberate — "
                f"a silently dropped hardening option"
            )

    for var in ("CFLAGS", "CXXFLAGS"):
        line = a_opts.get(var, "")
        for flag in HARDENING_FLAGS:
            if flag in line:
                continue
            if deliberately_omitted(flag):
                warns.append(f"{flag} missing from {var}, declared omitted with {OMIT_MARKER}")
            else:
                errs.append(f"{flag} missing from Android {var} and no `{OMIT_MARKER} {flag}` "
                            f"comment declares that deliberate")

    # desktop-only paths must never appear in a real option line (comments are fine —
    # they carry the source citations that justify each decision)
    for s in a_raw:
        if "browser/" in s and "mobile/android" not in s:
            errs.append(f"desktop path in an active option line: {s}")

    for opt in sorted(set(d_opts) - set(a_opts) - set(HARDENING)):
        msg = f"{opt}: in desktop config, not in Android config"
        if opt in a_comments:
            continue
        (errs if strict else warns).append(msg + " and not mentioned in any comment")

    for w in warns:
        print(f"warn:  {w}")
    for e in errs:
        print(f"error: {e}")
    if errs:
        print(f"\n{len(errs)} error(s)")
        return 1
    print(f"ok: hardening parity holds ({len(warns)} documented difference(s))")
    return 0


def _list_entries(path):
    """Non-comment, non-blank entries from a patch list, inline comments stripped."""
    out = []
    for line in path.read_text().splitlines():
        s = line.split("#")[0].strip()
        if s:
            out.append(s)
    return out


def _straddlers(path):
    """Entries tagged `# STRADDLER -> LW-M1-0x` — parked in desktop until split."""
    out = []
    for line in path.read_text().splitlines():
        if "STRADDLER" in line:
            s = line.split("#")[0].strip()
            if s:
                out.append(s)
    return out


def cmd_check_scope():
    """Cross-check PATCH-SCOPE.md's declared counts against the live lists and
    against the patch files actually on disk. Catches the failure where the lists
    are edited and the document that explains them silently rots."""
    ld = REPO / "assets" / "patches"
    doc_p = REPO / "docs" / "android" / "PATCH-SCOPE.md"
    for p in (ld / "common.txt", ld / "desktop.txt", ld / "android.txt", doc_p):
        if not p.exists():
            print(f"error: {p} does not exist")
            return 2

    common = _list_entries(ld / "common.txt")
    desktop = _list_entries(ld / "desktop.txt")
    android = _list_entries(ld / "android.txt")
    parked = _straddlers(ld / "desktop.txt")
    errs, warns = [], []

    # 1. every listed patch exists on disk
    for name in common + desktop + android:
        if not (REPO / name).exists():
            errs.append(f"listed but missing on disk: {name}")

    # 2. no patch appears in more than one list
    seen = {}
    for label, entries in (("common", common), ("desktop", desktop), ("android", android)):
        for name in entries:
            if name in seen:
                errs.append(f"{name} is in both {seen[name]}.txt and {label}.txt")
            seen[name] = label

    # 3. every patch file on disk is accounted for. Some patches are applied from
    #    their own call sites in librewolf-patches.py rather than from a list —
    #    derive that set from the script rather than hardcoding it, because
    #    LW-M1-09 folds xmas into the lists and any hardcoded set goes stale.
    patcher = (REPO / "scripts" / "librewolf-patches.py").read_text()
    SEPARATE = {m.group(1) for m in
                re.finditer(r"""patch\(\s*['"]\.\./(patches/[^'"]+\.patch)['"]""", patcher)}
    # Patches that exist on disk but are DELIBERATELY in no list yet — a spike
    # artefact whose landing is a separate task. Declared in PATCH-SCOPE.md under
    # "## Pending" as a `- <path> (LW-...)` bullet, so the exemption is visible and
    # attributable rather than a silent hole. An undeclared unlisted patch is still
    # an error: that is the case this check exists for.
    pending = {m.group(1): m.group(2) for m in re.finditer(
        r"^-\s+(patches/\S+\.patch)\s+\((LW-[A-Z0-9-]+)\)", doc_p.read_text(), re.M)}
    on_disk = {str(p.relative_to(REPO)) for p in REPO.glob("patches/**/*.patch")}
    unaccounted = on_disk - set(seen) - SEPARATE - set(pending)
    for name in sorted(unaccounted):
        errs.append(f"patch file on disk is in no list and is not separately applied: {name}")
    for name, owner in sorted(pending.items()):
        if name not in on_disk:
            errs.append(f"PATCH-SCOPE.md declares {name} pending, but it is not on disk")
        elif name in seen:
            errs.append(f"{name} is declared pending in PATCH-SCOPE.md but IS listed in "
                        f"{seen[name]}.txt — drop the pending declaration")
        else:
            warns.append(f"pending, not in any list: {name} ({owner} lands it)")
    for name in sorted(SEPARATE - on_disk):
        errs.append(f"separately-applied patch is missing from disk: {name}")

    # 4. the counts stated in PATCH-SCOPE.md match reality
    # The android bucket is optional in the text only while android.txt is empty;
    # once a split adds an Android patch the categories must still sum to the total,
    # which is the check that actually catches drift.
    doc = doc_p.read_text()
    stated = re.search(
        r"\*\*(\d+) common(?: / (\d+) android)? / (\d+) desktop-only / "
        r"(\d+) straddlers = (\d+)\s*\n?\s*patch files",
        doc)
    if not stated:
        errs.append("PATCH-SCOPE.md has no parseable 'N common [/ N android] / "
                    "N desktop-only / N straddlers = N patch files' summary")
    else:
        s_common, s_android, s_desktop, s_strad, s_total = stated.groups()
        s_common, s_desktop, s_strad, s_total = (
            int(s_common), int(s_desktop), int(s_strad), int(s_total))
        s_android = int(s_android) if s_android is not None else 0
        # The separately-applied patches are counted in the doc too: whichever of
        # them is a straddler counts there, the rest count as desktop-only.
        sep_strad = len({p for p in SEPARATE if "xmas" in p})
        real_desktop = len(desktop) - len(parked) + (len(SEPARATE) - sep_strad)
        real_strad = len(parked) + sep_strad
        for label, stated_n, real_n in (
            ("common", s_common, len(common)),
            ("android", s_android, len(android)),
            ("desktop-only", s_desktop, real_desktop),
            ("straddlers", s_strad, real_strad),
            ("total", s_total, len(on_disk) - len(pending)),
        ):
            if stated_n != real_n:
                errs.append(f"PATCH-SCOPE.md says {stated_n} {label}, lists have {real_n}")
        if s_android and " android " not in stated.group(0):
            errs.append("android.txt is non-empty but PATCH-SCOPE.md's summary has no android term")
        parts = s_common + s_android + s_desktop + s_strad
        if parts != s_total:
            errs.append(f"PATCH-SCOPE.md's own arithmetic does not add up: "
                        f"{s_common}+{s_android}+{s_desktop}+{s_strad} = {parts}, not {s_total}")
    if android and not re.search(r"/ \d+ android /", doc):
        errs.append(f"android.txt has {len(android)} entries but PATCH-SCOPE.md's summary "
                    f"omits the android category entirely")

    for w in warns:
        print(f"warn:  {w}")
    for e in errs:
        print(f"error: {e}")
    if errs:
        print(f"\n{len(errs)} error(s)")
        return 1
    print(f"ok: {len(on_disk) - len(pending)} listed patch files — {len(common)} common, "
          f"{len(desktop) - len(parked)} desktop, {len(android)} android, "
          f"{len(parked)} straddlers parked; PATCH-SCOPE.md agrees")
    return 0


CFG_KINDS = ("defaultPref", "lockPref", "clearPref", "setEnv", "pref")
# Recorded totals for the whole split. Quoted in ROADMAP.md and tasks.yaml too —
# change all three together or --check-cfg-split will say so.
CFG_EXPECTED = {"defaultPref": 178, "lockPref": 60, "pref": 26,
                "clearPref": 2, "setEnv": 1}
CFG_EXPECTED_LW_PREFS = 12


def _cfg_calls(text):
    """[(kind, name, value)] from a .cfg.

    Paren-balancing and string-aware on purpose: a regex to the last ')' on the
    line is wrong, because trailing comments contain parentheses. LW-M3-01 hit
    exactly that and it produced three false failures.
    """
    calls = []
    i, n = 0, len(text)
    while i < n:
        # skip comments and strings so a '(' inside them never starts a call
        if text.startswith("//", i):
            i = text.find("\n", i)
            if i == -1:
                break
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        if text[i] in "\"'":
            q, i = text[i], i + 1
            while i < n and text[i] != q:
                i += 2 if text[i] == "\\" else 1
            i += 1
            continue
        for kind in CFG_KINDS:
            if text.startswith(kind, i) and not (text[i - 1:i].isalnum() or text[i - 1:i] == "."):
                j = i + len(kind)
                while j < n and text[j] in " \t":
                    j += 1
                if j < n and text[j] == "(":
                    depth, k, instr, q = 0, j, False, ""
                    while k < n:
                        c = text[k]
                        if instr:
                            if c == "\\":
                                k += 2
                                continue
                            if c == q:
                                instr = False
                        elif c in "\"'":
                            instr, q = True, c
                        elif c == "(":
                            depth += 1
                        elif c == ")":
                            depth -= 1
                            if depth == 0:
                                break
                        k += 1
                    inner = text[j + 1:k]
                    parts = inner.split(",", 1)
                    name = parts[0].strip().strip("\"'")
                    value = " ".join(parts[1].split()) if len(parts) > 1 else ""
                    calls.append((kind, name, value))
                    i = k + 1
                    break
        else:
            i += 1
            continue
    return calls


def cmd_check_cfg_split():
    S = REPO / "settings"
    files = {n: S / f"{n}.cfg" for n in ("librewolf", "common", "desktop", "android")}
    for n, p in files.items():
        if not p.exists():
            print(f"error: {p} does not exist — LW-M3-01 has not landed")
            return 2
    text = {n: p.read_text() for n, p in files.items()}
    errs, warns = [], []

    # A — librewolf.cfg is exactly common + desktop, byte for byte
    if text["common"] + text["desktop"] != text["librewolf"]:
        errs.append("A: librewolf.cfg is not the byte concatenation of common.cfg + desktop.cfg")

    calls = {n: _cfg_calls(t) for n, t in text.items()}

    # B — conservation against the last committed librewolf.cfg
    import subprocess
    try:
        ref = subprocess.run(["git", "-C", str(S), "show", "HEAD:librewolf.cfg"],
                             capture_output=True, text=True, timeout=20)
        if ref.returncode == 0:
            before, after = Counter(_cfg_calls(ref.stdout)), Counter(calls["common"] + calls["desktop"])
            for triple in sorted(set(before) | set(after)):
                if before[triple] != after[triple]:
                    errs.append(f"B: {triple[0]}({triple[1]}) changed: "
                                f"{before[triple]} before, {after[triple]} after")
        else:
            warns.append("B: skipped — settings/ is not a readable git checkout")
    except Exception as e:                                     # noqa: BLE001
        warns.append(f"B: skipped — {e}")

    # C — overrides are LEGITIMATE; only genuine ambiguity is an error.
    #
    # An earlier version of this rule errored whenever a pref appeared in two
    # fragments. That was wrong, and it contradicted the design LW-M3-09 was told
    # to follow: the fragments are CONCATENATED and evaluated in order (common
    # first, then the target's), so a later android.cfg line deliberately
    # overriding an earlier common.cfg line is exactly how a platform override
    # works — it is how the bare-pref()/L2b fix is expressed while leaving desktop
    # semantics untouched. Forbidding it would have forced a blanket rewrite of
    # common.cfg, changing desktop behaviour to fix an Android-only problem.
    #
    # What IS an error: the same fragment setting a pref twice (genuinely
    # ambiguous — nothing says which wins by intent rather than by accident).
    # What is dead weight, and warned about: a target fragment restating common's
    # value AND construct, which achieves nothing.
    for n in ("common", "desktop", "android"):
        seen_n = {}
        for kind, name, value in calls[n]:
            if name in seen_n:
                errs.append(f"C: {n}.cfg sets {name} twice — which one is intended?")
            seen_n[name] = (kind, value)
    common_by_name = {c[1]: (c[0], c[2]) for c in calls["common"]}
    for n in ("desktop", "android"):
        for kind, name, value in calls[n]:
            if name in common_by_name and common_by_name[name] == (kind, value):
                warns.append(f"C: {n}.cfg restates {name} with common.cfg's exact "
                             f"construct and value — dead weight, drop it")

    # D — recorded totals. These apply to common + desktop ONLY, because those two
    # must conserve the original librewolf.cfg exactly. android.cfg is new content
    # (policy translations that have no desktop counterpart — LW-M3-06), so folding
    # it in here would make every legitimate Android addition look like corruption.
    tally = Counter(c[0] for c in calls["common"] + calls["desktop"])
    for kind, want in CFG_EXPECTED.items():
        if tally[kind] != want:
            errs.append(f"D: {tally[kind]} {kind} in common+desktop, expected {want}")
    lw = {c[1] for c in calls["common"] + calls["desktop"]
          if c[1].startswith("librewolf.")}
    if len(lw) != CFG_EXPECTED_LW_PREFS:
        errs.append(f"D: {len(lw)} distinct librewolf.* prefs in common+desktop, "
                    f"expected {CFG_EXPECTED_LW_PREFS}")
    # (The dead-weight check used to live here and compared VALUE only, so it fired
    # on the legitimate construct promotion that fixes landmine L2b — reporting
    # "re-states the same value" about a change from bare pref() to lockPref, which
    # is the whole point of the fix. Rule C now does it properly, comparing construct
    # AND value.)

    # E — fragment hygiene. autoconfig's skipFirstLine eats line 1 of whatever it
    # evaluates, so a fragment starting with a pref call would silently lose it.
    if text["common"].splitlines()[:1] != ["null;"]:
        errs.append("E: common.cfg line 1 must be exactly `null;` (autoconfig skips it)")
    for n in ("desktop", "android"):
        first = (text[n].splitlines() or [""])[0]
        if any(first.strip().startswith(k) for k in CFG_KINDS):
            errs.append(f"E: {n}.cfg line 1 is a pref call — it would be dropped if "
                        f"this fragment were ever evaluated on its own")

    # F — letterboxing is not a parity gap: desktop ships it false
    lb = "privacy.resistFingerprinting.letterboxing"
    if lb in {c[1] for c in calls["android"]}:
        errs.append(f"F: {lb} must not be set in android.cfg")
    d_lb = [c for c in calls["desktop"] if c[1] == lb]
    if not d_lb:
        errs.append(f"F: {lb} is missing from desktop.cfg")
    elif "false" not in d_lb[0][2]:
        errs.append(f"F: {lb} must be false in desktop.cfg, got `{d_lb[0][2]}`")

    for w in warns:
        print(f"warn:  {w}")
    for e in errs:
        print(f"error: {e}")
    if errs:
        print(f"\n{len(errs)} error(s)")
        return 1
    print(f"ok: {len(calls['common'])} common / {len(calls['desktop'])} desktop / "
          f"{len(calls['android'])} android calls; librewolf.cfg regenerates exactly")
    return 0


def _constructed_prefs(path, rel):
    """Pref names GeckoView BUILDS rather than writes, e.g. the SafeBrowsingProvider
    trees: `new Pref<>(ROOT + mName + ".updateURL", null)` with
    `ROOT = "browser.safebrowsing.provider."` and one provider per `withName("...")`.

    A literal-string scan cannot see any of these, and this checker was blind to all
    36 of them until 2026-08-26 — while common.cfg:371-374, :384 and android.cfg:432
    set six such prefs. The gate whose entire job is "GeckoView declares this, did you
    acknowledge the lock?" was answering "no such pref" for a whole subtree. Found
    while briefing LW-M3-04, which exists because a hand-built list misses exactly
    this shape.

    Deliberately derives the pieces from the file instead of hardcoding the 36 names:
    a provider added upstream should widen the check on its own.
    """
    text = path.read_text(errors="replace")
    roots = dict(re.findall(r'\b(\w+)\s*=\s*"([^"]*\.)"\s*;', text))
    # Comment lines excluded deliberately: ContentBlocking.java:1537 is a javadoc
    # example `.withName("custom-provider")`, and scraping it invented 12 pref names
    # for a provider that does not ship. Caught by the count assertion below.
    code = "\n".join(l for l in text.splitlines()
                     if not l.lstrip().startswith(("*", "//", "/*")))
    names = sorted(set(re.findall(r'withName\(\s*"([^"]+)"', code)))
    out = {}
    for m in re.finditer(r'Pref(?:WithoutDefault)?<[^>]*>\s*\(\s*'
                         r'(\w+)\s*\+\s*(\w+)\s*\+\s*"([^"]+)"', text):
        root_id, _var, suffix = m.groups()
        root = roots.get(root_id)
        if root is None:
            continue
        line_no = text[:m.start()].count("\n") + 1
        for n in names:
            out.setdefault(f"{root}{n}{suffix}",
                           f"{Path(rel).name}:{line_no} (built as {root_id}+name+\"{suffix}\")")
    return out


def _gv_declared_prefs(tree):
    """Pref names declared in GeckoRuntimeSettings.java / ContentBlocking.java.

    These are the `Pref<>("name")` / `PrefWithoutDefault<>("name")` field
    declarations — the prefs GeckoView writes at runtime.
    """
    found = {}
    for rel in GV_PREF_DECLARERS:
        p = tree / rel
        if not p.exists():
            continue
        found.update(_constructed_prefs(p, rel))
        for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
            for m in re.finditer(r'\bPref(?:WithoutDefault)?<[^>]*>\s*\(\s*"([^"]+)"', line):
                found.setdefault(m.group(1), f"{Path(rel).name}:{i}")
        # the declaration is often split across two lines: `new PrefWithoutDefault<>(`
        # then the string. Catch that shape too.
        text = p.read_text(errors="replace")
        for m in re.finditer(r'Pref(?:WithoutDefault)?<[^>]*>\s*\(\s*\n?\s*"([^"]+)"', text):
            if m.group(1) not in found:
                line_no = text[:m.start()].count("\n") + 1
                found[m.group(1)] = f"{Path(rel).name}:{line_no}"
    return found


def cmd_check_policies():
    """Catch the failure LW-M3-06 actually made: a cfg shipping a pref that
    GeckoView declares, without acknowledging that it needs a lock.

    "I grepped and did not find it" is not evidence that nothing writes a pref.
    This checks the real declarations instead of a name search.
    """
    S = REPO / "settings"
    # Tree selection must be explicit or unambiguous — NEVER "whichever sorts
    # first". An earlier version did exactly that and silently read the wrong tree
    # when a builder had both a desktop and an ESR tree on disk: pathlib compares
    # part tuples, so firefox-153.0 wins over firefox-153.0.4, and the answer was
    # wrong with no way for the reader to tell. Found by the skeptical
    # verification of LW-M7-01.
    import os
    override = os.environ.get("LW_TREE")
    if override:
        # Resolve a relative LW_TREE against the REPO ROOT, not the caller's cwd.
        # REBASE.md told maintainers relative paths work; they only worked from
        # the repo root, and the runbook is explicitly meant to be run from a
        # scratch directory. Making the doc's claim true is better than narrowing
        # the doc.
        cands = [Path(override) if Path(override).is_absolute() else REPO / override]
    else:
        # BOTH naming schemes. `firefox-<version>` is the extracted DESKTOP tarball
        # (./version, 153.0.4); the Android build works in `librewolf-<version>-<rel>`
        # off ./version.android (153.0esr). The glob was "firefox-*/mobile", so this
        # ANDROID check could never select the ANDROID tree — it silently read the
        # desktop one and was right only because the two agree today (ContentBlocking
        # .java and GeckoRuntimeSettings.java are byte-identical across both, checked
        # 2026-08-26). They are different release tracks and need not stay that way.
        # Surfaced by LW-M3-04's gen-android-locks.py, which globbed wider and
        # reported the ambiguity this one could not see.
        cands = sorted({p.parent for p in list(REPO.glob("firefox-*/mobile"))
                        + list(REPO.glob("librewolf-*/mobile"))})
        vfile = REPO / "version.android"
        if len(cands) > 1 and vfile.exists():
            want = vfile.read_text().strip()
            preferred = [c for c in cands if want in c.name]
            if len(preferred) == 1:
                print(f"# two trees on disk; preferring {preferred[0].name} "
                      f"(matches version.android = {want})")
                cands = preferred
    if not cands:
        # Exit 2, not 0: a check whose input is missing has no answer, and a gate
        # that prints "warn" and exits 0 is the fail-open shape landmine L5 warns
        # about — it was quoted as green from machines with no tree on disk.
        print("error: no extracted Firefox tree found — cannot check pref declarations")
        print("       (extract one with `make dir TARGETS=android`, or set LW_TREE=/path/to/tree)")
        print("       An unanswerable check is not a pass: exit 2.")
        return 2
    if len(cands) > 1:
        print("error: more than one extracted Firefox tree — refusing to guess which one "
              "this check should read:")
        for c in cands:
            print(f"         {c}")
        print("       set LW_TREE=<one of these> and re-run")
        return 2
    tree = cands[0]
    if not (tree / "mobile").is_dir():
        print(f"error: {tree} has no mobile/ directory — not an Android-capable tree")
        return 2
    print(f"# reading pref declarations from {tree.name}")

    declared = _gv_declared_prefs(tree)
    decisions = set()
    if DECISIONS.exists():
        for ln in DECISIONS.read_text().splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                decisions.add(ln)
    else:
        print(f"error: {DECISIONS} is missing — it is what classifies every unlocked "
              f"GeckoView-declared pref, and without it this check cannot answer its "
              f"own question")
        return 2
    if not declared:
        print(f"error: found no Pref<> declarations in {', '.join(GV_PREF_DECLARERS)} "
              f"— the parser is broken or the tree layout changed")
        return 2

    # A pref common.cfg sets and android.cfg overrides is HANDLED on Android: the
    # android composition is common + android, later wins. Without this, the checker
    # reports the very pattern LW-M3-09 landed as the fix — android.cfg:432 promotes
    # browser.safebrowsing.provider.google4.dataSharingURL from common.cfg's bare
    # pref() to a defaultPref, which is correct, and the first version of this check
    # called it "new debt". Same class of false positive as Rule C in
    # --check-cfg-split, which forbade overrides until it was rewritten.
    android_overrides = set()
    ap = S / "android.cfg"
    if ap.exists():
        for line in ap.read_text().splitlines():
            m = re.match(r'\s*(defaultPref|lockPref|pref)\s*\(\s*"([^"]+)"', line)
            if m:
                android_overrides.add(m.group(2))

    errs, warns, checked = [], [], 0
    for name in ("common", "android"):
        p = S / f"{name}.cfg"
        if not p.exists():
            continue
        lines = p.read_text().splitlines()
        # Walk forward tracking the governing comment block. The file's convention
        # is that a comment governs every pref call following it until the NEXT
        # comment block starts — e.g. common.cfg's
        # "// [ANDROID: LOCK] both of the next two" covers two calls, the first of
        # which spans several lines. A naive backward scan stops at that call's
        # closing paren and reports a false positive.
        block, in_block = [], False
        for i, line in enumerate(lines):
            stripped = line.strip()
            is_comment = stripped.startswith(("*", "/*", "//", "*/"))
            if is_comment:
                if not in_block:
                    block, in_block = [], True
                block.append(line)
                continue
            if stripped:
                in_block = False
            m = re.match(r'\s*(defaultPref|lockPref|pref)\s*\(\s*"([^"]+)"', line)
            if not m:
                continue
            kind, pref = m.group(1), m.group(2)
            if pref not in declared:
                continue
            if name == "common" and pref in android_overrides:
                continue          # android.cfg has the last word on Android
            checked += 1
            if kind == "lockPref":
                continue                      # already locked, nothing to acknowledge
            if kind == "pref":
                # Doubly doomed on Android (landmine L2b): a bare pref() writes the
                # USER branch, which GeckoView:ResetUserPrefs clears at startup
                # AFTER autoconfig — so the value is gone before Fenix even gets a
                # chance to overwrite it. An [ANDROID: LOCK] marker acknowledges the
                # Fenix problem but does nothing about this one.
                msg = (f"{name}.cfg:{i + 1} ships {pref} as a bare pref() — user branch, "
                       f"wiped by GeckoView:ResetUserPrefs — AND GeckoView declares it at "
                       f"{declared[pref]}. Needs lockPref or defaultPref")
                if pref in BARE_PREF_BACKLOG:
                    warns.append(msg + " (known: LW-M3-09 backlog)")
                else:
                    errs.append(msg + " — and it is NOT in BARE_PREF_BACKLOG, so it is new debt")
                continue
            # A MARKER IS NOT AN ANSWER. Until 2026-08-27 this check passed on the
            # string "[ANDROID: LOCK]" appearing in a nearby comment, so 23 of the 26
            # GeckoView-declared prefs we ship were effectively defaultPref with the
            # gate green over all of them — including network.trr.mode, which stage 5b
            # provably overwrites on every cold start. A comment recorded that someone
            # had thought about the question; it never recorded the answer.
            #
            # Now every unlocked GeckoView-declared pref must be classified in
            # docs/android/must-not-lock.txt, which says WHICH answer and why.
            if pref not in decisions:
                errs.append(
                    f"{name}.cfg:{i + 1} ships {pref} as {kind}, GeckoView declares it at "
                    f"{declared[pref]}, and it is not classified in "
                    f"{DECISIONS.name}. Add it under MUST-NOT-LOCK (naming the settings "
                    f"UI that owns it) or SAFE-UNLOCKED (saying why no stage-5b writer "
                    f"reaches it) — or make it a real lockPref. An [ANDROID: LOCK] "
                    f"comment no longer satisfies this check.")
            # No warning for the [ANDROID: LOCK] marker on a classified-but-unlocked
            # pref. A first draft of this check warned on exactly that and was wrong:
            # settings/common.cfg:53 defines the marker as "this pref is one GeckoView
            # declares", NOT "this pref is locked". It flags membership of the danger
            # set; must-not-lock.txt now supplies the answer. Warning on all seven
            # would have been noise, and a gate nobody reads is the failure mode the
            # ratchets in this file exist to avoid.

    for w in warns:
        print(f"warn:  {w}")
    for e in errs:
        print(f"error: {e}")
    if errs:
        print(f"\n{len(errs)} error(s)")
        return 1
    print(f"ok: {len(declared)} prefs declared by GeckoView; {checked} of them shipped by us, "
          f"every unlocked one classified in must-not-lock.txt")
    return 0


FENIX_ALLOWLIST = Path(__file__).resolve().parent / "fenix-test-allowlist.yaml"
# Where Gradle writes the JUnit XML, relative to the repo root.
FENIX_RESULTS_GLOB = "*/obj-*/gradle/build/mobile/android/fenix/app/test-results/testDebugUnitTest"


def _junit_failures(results):
    """(files, total_tests, {class: failing_tests}, {classes seen}) from a
    Gradle JUnit XML dir.

    Reads the XML, not the console log. A log is only as good as whoever
    remembered to `tee` it, and `grep TEST-UNEXPECTED-FAIL` over a log that was
    never captured prints nothing — which is exactly what a clean run prints.
    The XML is written by the task itself and cannot be forgotten.
    """
    import xml.etree.ElementTree as ET
    total, by_class, seen = 0, Counter(), set()
    files = sorted(results.glob("TEST-*.xml"))
    for f in files:
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError as e:
            raise ValueError(f"{f.name}: {e}")
        total += int(root.get("tests") or 0)
        if root.get("name"):
            seen.add(root.get("name"))
        for tc in root.iter("testcase"):
            cls = tc.get("classname") or "<unknown>"
            seen.add(cls)
            if any(c.tag in ("failure", "error") for c in tc):
                by_class[cls] += 1
    return files, total, by_class, seen


def cmd_check_fenix_tests(results_arg):
    """Subtract the LW-M2-09 expected-failure allowlist from a real run.

    The Definition of done requires `./mach gradle fenix:testDebugUnitTest` to
    pass, and it cannot: libmegazord.so is an Android ELF and the suite runs on
    the host JVM. Without a machine-checked subtraction the gate is prose, and a
    gate that cannot return a clean answer trains people to ignore it.
    """
    import os
    if not FENIX_ALLOWLIST.exists():
        print(f"error: {FENIX_ALLOWLIST.name} is missing — the allowlist is the gate")
        return 2
    doc = yaml.safe_load(FENIX_ALLOWLIST.read_text()) or {}

    override = results_arg or os.environ.get("LW_FENIX_RESULTS")
    if override:
        cands = [Path(override) if Path(override).is_absolute() else REPO / override]
    else:
        cands = sorted(REPO.glob(FENIX_RESULTS_GLOB))
    if not cands:
        # Exit 2, not 0. AGENTS.md makes "--check-fenix-tests exits 0" the
        # Definition of done for every Kotlin change; with a 0 here it was met by
        # never running the suite. An absent result is not a pass (same rule the
        # function already applies to an empty XML directory below).
        print("error: no Fenix test results on disk — nothing to check")
        print("       run `./mach gradle fenix:testDebugUnitTest` in the build container,")
        print("       or point at a results dir: --results <dir> / LW_FENIX_RESULTS=<dir>")
        print("       An absent result is not a pass: exit 2.")
        return 2
    if len(cands) > 1:
        # Same rule as --check-policies: never "whichever sorts first".
        print("error: more than one Fenix test-results directory — refusing to guess:")
        for c in cands:
            print(f"         {c}")
        print("       pass --results <one of these>")
        return 2
    results = cands[0]
    if not results.is_dir():
        print(f"error: {results} is not a directory")
        return 2

    try:
        files, total, failing, seen = _junit_failures(results)
    except ValueError as e:
        print(f"error: unreadable JUnit XML in {results}: {e}")
        return 2
    if not files:
        print(f"error: no TEST-*.xml in {results} — an absent result is not a pass")
        return 2
    if total == 0:
        print(f"error: {len(files)} XML files in {results} report 0 tests — "
              f"the run did not execute")
        return 2

    newest = max(f.stat().st_mtime for f in files)
    stamp = __import__("datetime").datetime.fromtimestamp(newest).isoformat(" ", "seconds")
    try:
        shown = results.relative_to(REPO)
    except ValueError:
        shown = results
    print(f"# {len(files)} classes / {total} tests from {shown}")
    print(f"# newest result written {stamp} — check this against the change you are testing")

    allowed = {e["class"]: e for e in (doc.get("allowlist") or [])}
    known = {e["class"]: e for e in (doc.get("known_real") or [])}
    both = set(allowed) & set(known)
    if both:
        print("error: class listed in both allowlist and known_real: " + ", ".join(sorted(both)))
        return 2

    errs, warns = [], []
    for cls, n in sorted(failing.items()):
        entry = allowed.get(cls) or known.get(cls)
        if entry is None:
            errs.append(f"NEW failing class {cls} ({n} test(s)) — not allowlisted. "
                        f"This is the signal the gate exists to surface.")
            continue
        cap = int(entry.get("tests") or 0)
        if n > cap:
            kind = "environmental" if cls in allowed else "known-real"
            errs.append(f"{cls}: {n} failing, {kind} ceiling is {cap} — "
                        f"{n - cap} more than declared, so a real regression is "
                        f"hiding behind an expected name")
    absent = [c for c in sorted({**allowed, **known}) if c not in seen]
    if absent:
        # The one false green that matters: a partial run — a single class, an
        # aborted task, the wrong Gradle module — has nothing beyond the allowlist
        # in it *because it barely ran*, and would otherwise print "ok".
        errs.append(f"{len(absent)} listed class(es) did not run at all — this is not "
                    f"the full suite, or they were renamed/deleted:")
        errs.extend(f"    {c}" for c in absent)
    for cls, entry in sorted({**allowed, **known}.items()):
        if cls not in seen:
            continue
        n = failing.get(cls, 0)
        cap = int(entry.get("tests") or 0)
        if n == 0:
            warns.append(f"{cls} ran and passed — drop the entry "
                         f"(this is how AutofillSettingsMiddlewareTest left the list)")
        elif n < cap:
            warns.append(f"{cls}: {n} failing, declared {cap} — lower the count")

    env = sum(n for c, n in failing.items() if c in allowed)
    real = sum(n for c, n in failing.items() if c in known)
    unexpected = sum(n for c, n in failing.items() if c not in allowed and c not in known)
    print(f"# failing {sum(failing.values())} = {env} environmental "
          f"+ {real} known-real + {unexpected} unexpected")

    for w in warns:
        print(f"warn:  {w}")
    for e in errs:
        print(f"error: {e}")
    if errs:
        n_err = sum(1 for e in errs if not e.startswith("    "))
        print(f"\n{n_err} problem(s) — this run is NOT clean")
        return 2
    print("\nok: no failures beyond the documented allowlist")
    return 0


def cmd_stats(doc, tasks):
    depth = waves(tasks)
    lo = hi = 0
    per_ms = defaultdict(lambda: [0, 0, 0])
    for t in tasks.values():
        a, _, b = t["effort_h"].partition("-")
        a, b = int(a), int(b or a)
        lo, hi = lo + a, hi + b
        m = per_ms[t["milestone"]]
        m[0] += 1
        m[1] += a
        m[2] += b
    print(f"{len(tasks)} tasks, {lo}-{hi}h total, {max(depth.values()) + 1} waves\n")
    for ms in sorted(per_ms):
        n, a, b = per_ms[ms]
        print(f"  {ms}   {n:2d} tasks   {a:4d}-{b:4d}h")
    n_human = sum(1 for t in tasks.values() if not t["agent_safe"])
    n_wt = sum(1 for t in tasks.values() if t["isolation"] == "worktree")
    print(f"\n  {n_human} task(s) need a human; {n_wt} need worktree isolation")

    # critical path by effort_h upper bound
    memo = {}

    def cp(tid):
        if tid in memo:
            return memo[tid]
        t = tasks[tid]
        _, _, b = t["effort_h"].partition("-")
        cost = int(b or t["effort_h"])
        deps = t.get("depends_on") or []
        best = max((cp(d) for d in deps), key=lambda r: r[0], default=(0, []))
        memo[tid] = (best[0] + cost, best[1] + [tid])
        return memo[tid]

    total, path = max((cp(tid) for tid in tasks), key=lambda r: r[0])
    print(f"\ncritical path ({total}h if every task on it runs at its upper estimate):")
    for tid in path:
        print(f"    {tid}  {tasks[tid]['title']}")
    return 0


def main():
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("--check", action="store_true")
    p.add_argument("--waves", action="store_true")
    p.add_argument("--ready", action="store_true")
    p.add_argument("--done", default="", help="comma-separated completed task ids")
    p.add_argument("--show", metavar="TASK_ID")
    p.add_argument("--stats", action="store_true")
    p.add_argument("--diff-mozconfig", action="store_true")
    p.add_argument("--check-scope", action="store_true")
    p.add_argument("--check-cfg-split", action="store_true")
    p.add_argument("--check-policies", action="store_true")
    p.add_argument("--check-fenix-tests", action="store_true")
    p.add_argument("--results", metavar="DIR", default="",
                   help="--check-fenix-tests: Gradle JUnit XML directory")
    for flag in DEFERRED:
        p.add_argument(flag, action="store_true")
    p.add_argument("--strict", action="store_true",
                   help="--diff-mozconfig: also fail on undocumented non-hardening drops")
    args, extra = p.parse_known_args()

    if args.diff_mozconfig:
        return cmd_diff_mozconfig(args.strict)
    if args.check_scope:
        return cmd_check_scope()
    if args.check_cfg_split:
        return cmd_check_cfg_split()
    if args.check_policies:
        return cmd_check_policies()
    if args.check_fenix_tests:
        return cmd_check_fenix_tests(args.results)

    for flag, owner in DEFERRED.items():
        if getattr(args, flag.lstrip("-").replace("-", "_")):
            print(f"error: {flag} is not implemented yet — it is delivered by {owner}")
            return 2

    doc, tasks = load()
    if args.check:
        return cmd_check(doc, tasks)
    if args.waves:
        return cmd_waves(doc, tasks)
    if args.ready:
        return cmd_ready(doc, tasks, [x for x in args.done.split(",") if x])
    if args.show:
        return cmd_show(doc, tasks, args.show)
    if args.stats:
        return cmd_stats(doc, tasks)
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
