# Compiler and test-fixture lineage followup

This review updates seven existing repository evidence pins while leaving every
semantic counterpart, desktop patch effect, policy leaf and pane control intact.
The prior five audit files are retained in `before-review.tar.gz`, and the prior
Android registry is retained separately.

The checker follows actual archived full patches through three graphics stages:

1. Bundle compiler correction: `11401e72…`.
2. Permission Mockito fixture correction: `a8b3d525…`.
3. Fenix coroutine test opt-in: `b10c3b13…`.

It verifies the independent Sync Boolean matcher correction (`d9ebe535…`) and
cookie fixture corrections (`60516378…` then `2b822a87…`), all eight
before/after fixture test bodies, unchanged test counts and unchanged production
patch sections at each test-only step. The coroutine
opt-in additionally must differ by exactly its import and class annotation.
Historical reviewed source ranges stay bound to their original patches.

A separate production correction restores the existing custom-tab early return
before HomeActivity inspects the account-settings extra. Ordinary HomeActivity
still consumes a true flag and navigates. The exact move is checked against both
source bodies, and four newly authored regression cases are bound separately.
The startup metrics fixture explicitly selects its two Suggest choices; all
eight existing tests and their assertions are retained.

The routing patch is separately retained at `9f`, the GNU format-only correction
at `28`, and the normal-navigation fixture correction at `AC0`. The format correction
changes no source output. The final fixture preserves all four test names,
actions and assertions after intent construction, while replacing a copied spy
with a real activity whose lazy navigation getter captures the correct instance.

The current Task35 ordering receipt and Task36 predecessor receipt must name the
current patches. Task23's current predecessor and corrected test bodies must
match too. The Android registry change is constrained to the single Task37
registration line; it supplies no completion claim for the full session cleanup
coordinator.

Run `python3 docs/android/evidence/lw-m7-17/check-coverage.py` for the full audit.
Run `python3 docs/android/evidence/lw-m7-17/fixture-lineage-followup/test-checker.py`
for adversarial checks of the new lineage guard. These are host evidence checks;
they do not compile or execute Kotlin, GeckoView, native persistence or browser
behavior. Actual target failures and reruns retain their separate source-bound
receipts. Task35/36 target acceptance remains pending.
