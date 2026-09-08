# Prepared beta reporting publication — not published

The default branch was fetched and verified at
`71177a33973c02b52e99c79ca8def1e5f5f9e018` on 2026-09-08. The current public
repository has no `.github/ISSUE_TEMPLATE/` directory and no planned Android
labels; the read-only API evidence is in the beta audit's `human-criteria.md`.
No GitHub releases were listed, and the most recent Actions runs are historical,
not evidence for the current candidate.

`github-reporting.patch` adds only the corrected Android form and private
security contact configuration to that default branch. It was prepared in the
isolated local worktree
`/home/mgysin/redoubt-artifacts/lw-m6-08-session/reporting-publish`; the form matches
the schema-checked file in the main working checkout. The patch contains no
workflow changes, browser binaries or signing material.

`github-labels.json` contains the eleven proposed label definitions: the four
Android routing labels, the reproduction label, three channel labels, Type Bug,
beta and Status Known issue. Existing labels are preserved. Additional triage
vocabulary in TRIAGE.md needs mapping or creation if the maintainer chooses to
use it; it is not asserted to exist.

Publication approval was requested during preparation. Until it is given, these
are local review artifacts. After approval: re-read the default branch to avoid
overwriting concurrent work, apply the two-file change, add the missing labels,
and inspect GitHub's live form. E10 remains open until live availability is
verified; a feature-branch push or a locally valid YAML file alone is insufficient.
The LW-M7-04 manual submission test remains separately recorded until performed.
