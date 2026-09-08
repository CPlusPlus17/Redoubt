# Offline signing tools — LW-M6-08

For the complete build and entry audit, see [beta-readiness.md](beta-readiness.md).

Produced by the Codex `human_criteria` agent on 2026-09-08, on the Linux build
host. No release keystore was opened, copied, or used. The tests generate two
temporary RSA keys and public fingerprint documents, then delete their temporary
directory. These are signing-tool checks, not release signing or custody evidence.

## What changed

The offline `sign.sh` resolves the bundle independently of the working directory,
accepts keystore and signer paths containing spaces, and checks exact manifests
for all four APKs and all four tools. Literal filename comparison prevents a
manifest entry such as `unsignedXapk` from matching `unsigned.apk` as a regular
expression. Missing or duplicated tool entries cannot leave an unchecked verifier.

Each signed APK must pass the verifier against the bundled public `SIGNING.md`
before any final APK is moved out of the temporary workspace. A signing or
verification failure removes that workspace and propagates a nonzero status.
Existing signed APKs or `SHA256SUMS.signed` are refused. Successful signing emits
four APKs and their signed checksum manifest, with v4 sidecars disabled.

The verifier now accepts an explicit public signing document, quotes signer paths
as command arrays, requires exactly one signer, and tests both the positive path
and the actual wrong-key error in its self-test. Missing APK inputs return the
documented exit 2; invalid signatures return 1.

The optional `--unsigned-dir` argument binds signed intake to the trusted
candidate directory. It requires the full four-APK checksum manifest, verifies
each candidate's checksum, and compares complete ZIP entry sets, sizes,
compression methods, and streaming SHA-256 payload hashes. It rejects duplicate
entries, unknown signed filenames, missing counterparts, and changes to the
Android manifest or any other entry. No `META-INF` entry is excluded: v1 is
forbidden, and v2/v3 signatures live outside the ZIP entry payloads. An explicitly
empty directory argument fails rather than silently disabling the check.

Python is needed only for this optional intake check. The four-APK offline test
places a failing `python3` stub on PATH and still signs/verifies successfully;
the holder's signing helper does not use the candidate-binding flag.

## A real v1 false pass found by integration tests

The initial real-cryptography run passed 19 of 20 tests. The remaining test signed
an APK with v1, v2, and v3 enabled; the verifier incorrectly returned PASS and
claimed no v1 signature. The reduced fixture retains Redoubt's real binary Android
manifest. For this manifest, default apksigner verification reports the schemes
it uses and can report v1=false even when v1 signature entries exist.

The fix also inspects the APK's `META-INF` entries for JAR signature files,
using `unzip -Z1` or the JDK `jar tf` fallback. It rejects `.SF`, `.RSA`, `.DSA`,
`.EC`, and `SIG-*` entries. Archive inspection errors fail verification. This is
why the offline handoff now lists an archive-listing tool explicitly.

## Validation

Command:

```sh
python3 scripts/tests/test-android-signing.py
```

Result: **29 tests passed in 8.322 seconds**; full output is
[`signing-tests.out`](signing-tests.out). The fixture is an 84,642-byte ZIP holding
the real `AndroidManifest.xml` extracted from the existing unsigned x86_64 APK,
plus a small payload. It supports real APK signing and verification; it is not
an installable application and does not prove Android runtime behavior.

The test suite covers:

- Four real v2+v3 signatures with interactive password prompts, correct fingerprint,
  no v1 or v4 files, all output checksums correct, and unchanged unsigned inputs.
- Running from outside a bundle with spaces in its path, passing a relative key
  path, and both JAR and executable signer paths containing spaces.
- Wrong fingerprint, genuine v1 presence, v2-only signatures, corrupted signed APK,
  missing Android manifest, missing APK, and missing public signing document.
- Missing checksum manifests/tools, modified APK checksum, filename-regex mismatch,
  and a duplicated tool entry replacing an omitted tool.
- Refusal to overwrite existing output; propagation of injected exit 37 both
  before signing and after the first artifact has been signed and verified,
  leaving no partial final APK set.
- Verifier tool failure cannot report success; the self-test exercises a real
  positive result and a real wrong-key rejection.
- Intake accepts all four correctly signed candidate payloads. APKs signed with
  the correct temporary key but containing changed ordinary data or a changed
  binary Android manifest pass signature-only verification and fail intake.
  Duplicate ZIP names, missing counterparts, unknown signed filenames, incomplete
  manifests, failed candidate checksums, and an empty directory argument fail.

Only failure injection uses stubs; valid signatures and cryptographic rejection
cases use the actual bundled `apksigner.jar`. No test failure is skipped when the
APK, JAR, Java, or keytool inputs are absent. The suite accepts explicit `--apk`
and `--apksigner` paths for another machine. The `jar tf` fallback and execution on
macOS were not exercised here; this run used Linux and `unzip`.

`bash -n scripts/android-verify-signature.sh`,
`sh -n docs/android/evidence/lw-m6-01/sign.sh`, and `git diff --check` passed.
`python3 docs/android/board.py --check` reported
`ok: 90 tasks, 17 waves, 0 warning(s)`.

## Staged handoff

The tested scripts and current public signing document were copied into
`librewolf-android-apk-153.0esr-1-beta-20260908/apk/` after the normal candidate
build completed. The older `librewolf-android-apk-153.0esr-1-unsigned/apk/` has
matching tool copies. The APKs and their original `SHA256SUMS` were preserved
in both directories. Both manifests pass in each directory, and the staged
scripts/document match repository sources byte for byte; see
[`bundle-verification.out`](bundle-verification.out). The tool checksum manifest
is also retained here as [`SHA256SUMS.tools`](SHA256SUMS.tools).

The handoff intake command explicitly supplies the new candidate bundle's
`apksigner.jar` and candidate
directory, so a missing host-wide `apksigner` is not a dependency trap.

The candidate still needs the holder's offline release signature and separate
custody confirmation. Test signatures cannot satisfy E7, and this evidence makes
no claim about the other beta entry criteria or artifact reproducibility.
