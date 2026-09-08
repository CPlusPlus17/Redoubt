# Human decisions and beta reporting readiness — 2026-09-08

Produced by the Codex `human_criteria` agent on the shared build host. This audit
read the goal attachment, `AGENTS.md`, the current files, Git history, and GitHub's
read-only API. It did not contact testers, file an issue, change labels, publish
templates, or create a new owner decision.

## E8 and E9: recorded owner decisions

`SIGNING.md`, "Decision: Redoubt ships single-holder", records Manuel Gysin's
2026-09-06 choice to ship with one holder. That is the alternative explicitly
allowed by E8. The document separately says LW-M6-01's two-holder acceptance
criterion remains unmet; the beta exception must not be used to mark that task
fully complete.

`PARITY.md` §5 records Manuel Gysin's 2026-09-06 approval of the public wording,
verbatim. E9's signoff exists. Publishing the wording with a reachable parity table
is a public-release requirement, separate from this recorded approval.

Both decisions, and the solo triage decision below, were inspected in commit
`aca09eb3f8c81131be4819f0529e8ff9e2f0feca` (committed 2026-09-07, title
"Owner decisions recorded: single-holder custody, parity wording signed off,
triage owner named"). This is the repository's recorded provenance, not a claim
that this agent observed the original conversation with the owner.

## E10: owner recorded; live reporting setup incomplete

`TRIAGE.md` §0 names Manuel Gysin and records the deliberate decision to operate
without a backup, dated 2026-09-06. Its later role descriptions and checklist now
use that same exception. No second person was invented and no new approval was
recorded. BETA's criterion needs to express the existing solo-owner exception
instead of simultaneously demanding a named backup and claiming the row is met.

The local `.github/ISSUE_TEMPLATE/android-bug.yml` exists. It previously used
Markdown-template metadata (`about`) in a YAML issue form, which requires
`description`. The local repair fixes that key, adds a closed-beta private-link
source option, and asks for optional total device RAM so memory reports can be
interpreted. All seven required triage fields remain required.

The local `config.yml` already used a real private vulnerability-reporting URL.
Its stale assertion that the domain was unregistered was removed. Both YAML
examples in `TRIAGE.md` now exactly match the files.

The prior statement that the form was already live was contradicted by these
read-only checks on 2026-09-08:

```text
$ gh api repos/CPlusPlus17/Redoubt --jq '{default_branch,has_issues,private}'
{"default_branch":"main","has_issues":true,"private":false}

$ git ls-remote origin refs/heads/main
71177a33973c02b52e99c79ca8def1e5f5f9e018  refs/heads/main

$ gh api repos/CPlusPlus17/Redoubt/contents/.github/ISSUE_TEMPLATE/android-bug.yml
HTTP 404: Not Found

$ gh api repos/CPlusPlus17/Redoubt/contents/.github/ISSUE_TEMPLATE
HTTP 404: Not Found

$ gh api repos/CPlusPlus17/Redoubt/labels --paginate --jq '.[].name'
accessibility
bug
documentation
duplicate
enhancement
good first issue
help wanted
invalid
question
wontfix

$ gh api repos/CPlusPlus17/Redoubt/private-vulnerability-reporting
{"enabled":true}
```

The API could read repository metadata and labels; the missing template was not
inferred from a failed login. No `Android`, `Type Bug`, `beta`, or
`Status Known issue` label was present. `TRIAGE.md`'s previous claim of 48 existing
capitalised labels has been corrected to distinguish the proposed vocabulary
from actual repository settings.

## Local validation

The required metadata and body structures were checked against GitHub's official
[issue-form syntax](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)
and [element schema](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-githubs-form-schema),
read on 2026-09-08. A one-off Python/PyYAML validation rejected duplicate keys and
checked allowed keys, required metadata, field types, unique IDs, dropdown
choices, required fields, contact URLs, and byte equality of the embedded examples.
It produced:

```text
PASS: documented form structure, duplicate-key rejection, 15 elements / 14 unique IDs, dropdown choices and validations
PASS: seven required triage fields, beta source, optional total RAM, HTTPS contact configuration
PASS: both TRIAGE.md YAML examples exactly match local files
NOT VERIFIED: GitHub rendering, submission enforcement, label application; form is absent from live main

$ python3 docs/android/board.py --check
ok: 89 tasks, 17 waves, 0 warning(s)
```

`git diff --check` also passed. These local checks do not replace LW-M7-04's manual
test-issue verification. No Android code changed in this subtask.

## Remaining external work and scope

The local form is reviewable. For the planned reporting process to be usable,
the maintainer must settle/create the labels, publish the corrected form and
configuration to the default branch, and verify the live chooser and required
fields through the task's test-issue procedure. A feature-branch push alone would
not publish an issue form. No step in this paragraph was performed by this audit.

The beta's 14-day period starts at its first install; public-launch triage starts
when the download page goes live. Device assignments and beta findings must be
recorded as they become real. The final GO/NO-GO, second-build upgrades on tester
devices, and public download page belong to completing the beta/public release;
they are not substitutes for, or additional claims of, beta entry readiness.

Recommended BETA corrections based on already-recorded decisions and evidence:

- E10: name the dated solo-owner alternative and report local preparation versus
  the missing live form accurately.
- E2: remove the superseded assertion that only per-ABI APKs exist.
- E7 summary: custody is explicitly part of E7, not an unrelated optional item.
- §3: separate beta and public-launch calendars.
- §4: release `about:config` is reachable, as its existing runtime evidence shows.
- N2: follow E12's seven approved security collections; keep telemetry, experiments,
  ads, crash reporting, Google endpoints, and unapproved collection sync as failures.
  Do not change the strict zero-Remote-Settings harness checks to conceal traffic.
