# Repeated lifecycle failure with detailed evidence

Guest service `redoubt-parity-smoke4-20260909.service`, invocation
`eef4f39d729c4dbfa82f54c9daa0754b`, tested the same development APK as attempt 3.
The archive includes input hashes, terminal receipts, full request/DOM/add-on
objects checkpointed by the updated harness, and the packet capture.

The fresh page blocked the EasyList-matching script and executed the allowed
control. The ordinary AMO-signed uBO 1.74.0 had one live blocking listener and
private browsing permission. Disabling it stopped filtering and removed its
listener. After an immediate force-stop/restart, its add-on metadata remained
`userDisabled=true`, `active=false`, but its policy had one live blocking listener
and the test request was blocked again. This is a reproduced inconsistency;
metadata alone is insufficient to validate the disabled choice.

Removal after that inconsistent state left the app's automation connection
unavailable. Its captured logcat is preserved. The original `/dev/tty` UI dump
command saved only a completion message, so that file contains no UI hierarchy.
The harness now dumps an actual file and reads it. The next run also observes
Gecko's in-memory and on-disk startup cache without flushing either; source
inspection found JSONFile's 1,500-ms deferred cache save versus the extension
DB's 20-ms save. That is a hypothesis to measure, not yet a confirmed cause.

The HTTP navigation again hit the socket deadline before the actual interstitial
could be inspected. The corrected harness bounds WebDriver's navigation wait
below that deadline and classifies transport failures separately. This attempt
has no HTTPS behavior verdict. The separate live pref audit passed against the
three deliberately revised default expectations: zero violations and zero other
diffs among its curated keys. Its settings-screen traversal remains a placeholder.

Overall service exit 1. This candidate is not smoke-green.
