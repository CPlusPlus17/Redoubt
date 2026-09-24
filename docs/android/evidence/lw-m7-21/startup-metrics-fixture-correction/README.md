# Explicit Suggest choices in the startup metrics fixture

The actual full Fenix run failed at FenixApplicationTest.kt:229 because the test
expected sponsored and nonsponsored Suggest metrics to be true while leaving
both preferences at their new false defaults. The existing test already supplies
explicit values for the other measured choices. This correction also supplies
true for these two choices, preserving every assertion and all eight tests.

No production source or default changes. The original complete Task26 patch,
manifest and pristine archive are retained here. The new test input is captured
from the failed run, reversed through its only touching predecessor, no-adjust,
then reconstructed by the existing complete nine-predecessor source checker.
All21 final files match their pins; the eight existing startup tests join the
previous19 authored Kotlin definitions. Target rerun remains required.

The current Task20 predecessor digest is refreshed from the retained primitive
matcher and custom-tab corrections. Both of its shared Task26 bodies remain
unchanged and the complete source replay verifies them. Source26 output hashes
and production patch sections from before this fixture correction remain intact.
