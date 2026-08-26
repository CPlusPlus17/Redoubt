---
name: dual-box-goal
description: Write a goal/brief for the local two-box OpenCode setup — Gemma (box A, 4090) plans and reads images, Qwen (box B, 5090) writes code behind an explicit @coder hand-off. Use whenever the user asks for "a goal for Qwen", "a goal for Gemma", "the next goal", a brief to hand to the local agents, or wants work delegated off this session to the local boxes. Also use when adapting an existing task from docs/android/tasks.yaml into something the local pair can execute.
---

# Writing a goal for the two-box setup

## The one golden rule

**Implementation goes through `@coder`.** Gemma plans; `@coder` (box B) writes the
code. If the brief does not say `@coder`, Gemma does everything itself on box A —
that is the failure the user hit repeatedly. Opportunistic auto-delegation was tested
twice with a local orchestrator and does not hold; explicit hand-off does.

So every goal that produces code contains a literal `@coder` on the implementation
step. Not "hand this to the coder" — the token itself.

## Shape

```
<One-line goal.>

Context: <files that exist, constraints, what is there today>

Plan it first: <design decisions, which files change, edge cases>
Then @coder implement it: <what to build + acceptance criteria>
Then verify: <how we know it works — commands, gates>
```

Keep the three verbs in that order and on their own lines. They are what routes the
work; prose that merely implies them does not.

## Rules that make the split safe

Box B runs in **its own subagent context**. It does not see Gemma's reasoning, so
spell out what Gemma decided: exact paths, function names, acceptance criteria. A
`@coder` step that says "implement the design above" arrives with no design.

One `@coder` per implementation step. Chain across messages rather than bundling
(`@coder do X`, then next message `@coder now add tests`).

**Provenance, and this is the one that matters here.** This project's recurring
defect is a claim passed forward as established — the `locked_pref` claim survived
three hand-offs because each reader treated the previous writer's assertion as
measurement. A planner/coder split adds one seam per task where exactly that
happens: the planner writes a `file:line`, the coder builds on it without opening
the file, and the report says "implemented as specified" — true, and worthless.

So in every brief:

* Mark load-bearing claims as **hypothesis, not measurement**, and say so out loud
  when they came from this session's grep rather than from a run. Name which ones
  box B must confirm before building on them. Briefs written from here have already
  shipped a wrong path and a two-line-short range.
* State that **the box that runs a gate owns the green** — the planner may not
  report a gate it did not execute.
* See `docs/android/AGENTS.md`, "When two models share a task: planner + coder".

## Project-specific content every Redoubt goal needs

* **Board entry.** Open with `python3 docs/android/board.py --show <TASK-ID>` and
  check the task's `what:` is not stale before quoting it — several have been.
* **Ownership and stand-off.** Name the files box B owns and the files it must not
  touch. The working tree is shared and has no second index; `docs/android/tasks.yaml`,
  `docs/android/board.py` and `docs/android/AGENTS.md` are this session's.
* **Registration.** A new patch must land in `assets/patches/android.txt` *and*
  `docs/android/PATCH-SCOPE.md` or `--check-scope` fails.
* **Gates for "done".** `board.py --check`, `--check-scope`, `--check-cfg-split`,
  `--check-policies`, `--diff-mozconfig`, `--check-fenix-tests`, plus
  `lint-patch-scope.py`, `check-patch-order.py`, `check-patchfail.sh`.
* **Test allowlist interaction.** If the change touches a class in
  `docs/android/fenix-test-allowlist.yaml`, its `tests:` is a **ceiling** — more
  failures is a hard error, fewer is a warning to lower the count.
* **Evidence in-repo**, `docs/android/evidence/<task-id>/`, naming which box produced
  each artefact. Anything outside the repo has already evaporated once.
* **No commit, no push** unless the user asked.

## Honesty requirements to state in the brief

* Name the device-bound half. There is no emulator here, so runtime gates get
  written and dispatched but not run — that is acceptable and must be declared, not
  glossed. `LW-M4-08` landed exactly this way.
* Never write "zero requests" without naming the exceptions.
* A gate must fail closed: a dead capture produces no events and therefore contains
  no forbidden hostname either. Say so when asking for one.
* An unresolved item marked unresolved beats a confident wrong one.

## Vision

Gemma has vision on box A. Point it at screenshots, mockups, and the smoke harness
artefacts (`--first-run-capture`, `--network-capture`) — several open tasks are
blocked on "needs eyes on a device" rather than on reasoning. For those, the brief's
"Plan it first" step can be *look at this and tell me what it shows*.

## Output

Write the goal as **text in the reply** for the user to paste. Do not send it
anywhere, do not spawn agents to do the work, and do not implement the task here
unless asked — the point is to hand it to the boxes.
