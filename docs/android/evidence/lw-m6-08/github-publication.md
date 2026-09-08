# Beta reporting publication — published 2026-09-08

The user approved publication with “1. what i must do? 2. approved”. The eleven
label definitions in `github-labels.json` were created first. The two approved
form files were then committed and pushed to the default `main` branch as
[`c65d2e4`](https://github.com/CPlusPlus17/Redoubt/commit/c65d2e448124b570bf6acabcb3f99fd09a014300).
The previous default head was `71177a3`; it was fetched and checked immediately
before publishing. The commit adds only `.github/ISSUE_TEMPLATE/android-bug.yml`
and `.github/ISSUE_TEMPLATE/config.yml`.

[Live publication evidence](github-publication-live.json) verifies both remote
files against the approved local bytes and all eleven labels against their
names, colours and descriptions. The repository now has 21 labels: the ten
existing defaults plus eleven approved additions. Creation receipts are in
[github-labels-published.json](github-labels-published.json). Private vulnerability
reporting remains enabled, and the published contact configuration points there.

GitHub’s [public form preview](https://github.com/CPlusPlus17/Redoubt/blob/main/.github/ISSUE_TEMPLATE/android-bug.yml)
renders the parsed name, description, labels and actual field controls, including
required markers and the closed-beta source option. This proves GitHub accepts
and renders the published form. Its own embedded `issueTemplate` metadata reports
`structured=true`, `valid=true`, and `errors=[]`; every parsed entry also has no
errors. [Preview evidence](github-form-preview.json) and the retained
[raw HTML](github-form-preview.html.gz) bind that result to the published commit
and file blob. E10’s live-form requirement is met.

The [new Android issue link](https://github.com/CPlusPlus17/Redoubt/issues/new?template=android-bug.yml)
and [issue chooser](https://github.com/CPlusPlus17/Redoubt/issues/new/choose)
require GitHub sign-in. Authenticated submission, automatic label application and
empty-field rejection have not been exercised; these remain LW-M7-04’s separate
manual check. No test issue was created. The `issueTemplates` GraphQL query
returned an empty list and is not used as evidence of either presence or absence.

`github-reporting.patch` retains the exact reviewed two-file proposal.
`final-github-state.json` and the earlier human-criteria audit describe the
prepublication state; they are historical evidence, not the current live inventory.
Additional proposed triage vocabulary beyond these eleven labels still needs
mapping or creation before relying on it.
