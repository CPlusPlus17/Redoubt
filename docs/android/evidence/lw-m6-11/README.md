# Android beta publication — 2026-09-08

Published [Redoubt Android 153.0esr-1 — Beta 1](https://github.com/CPlusPlus17/Redoubt/releases/tag/android-153.0esr-1-beta.1)
at **2026-09-08 19:58:13 UTC**, release ID `385019160`. It is a public prerelease,
created and published with `--latest=false`.

The owner's request, “can we add them to the gh releasE?”, authorized publishing
the exact four APKs covered by the earlier
[custody decision](../lw-m6-10/custody-decision.md). This request supersedes the
earlier private-link beta channel. The custody exception remains limited to those
artifacts. Publication does not complete physical-device testing, the 14-day
beta, a second-build upgrade test, or the stable-release GO/NO-GO.

## Published files and verification

The five release assets are the ARM64, ARM32, universal and x86_64 signed APKs
and `SHA256SUMS.signed`. The latter is a checksum manifest for signed APKs; the
manifest itself is not cryptographically signed. Exact names, sizes and approved
SHA-256 values are in [publication-plan.json](publication-plan.json).

The following checks ran on the Fedora host, using public certificate verification
only; no Android release key or passphrase was accessed:

1. Verified the local approved APKs' release fingerprint, v2+v3 signatures, absence
   of v1 signatures, and ZIP payload identity with the unsigned candidate.
   [Local signature log](local-signature-verification.txt).
2. Created a draft prerelease and uploaded the five original files. GitHub reported
   every asset uploaded with the exact approved size and SHA-256 digest.
   [Verified draft metadata](draft-release-verified.json).
3. Downloaded all five draft assets using `gh release download`. Every downloaded
   file matched its approved hash and size; `sha256sum -c SHA256SUMS.signed`
   passed all four APKs. The signature verifier passed the release certificate,
   v2+v3/no-v1 and exact candidate payload checks for all four downloaded APKs.
   [Download receipt](downloaded-assets-verification.json),
   [checksum output](downloaded-checksums.txt),
   [signature and candidate output](downloaded-signature-verification.txt).
4. Published the draft with `--draft=false --prerelease --latest=false`.
   An unauthenticated request verified the release page, release API and asset
   API returned HTTP 200. All five asset IDs remained unchanged, with the same
   approved sizes and digests. An anonymous download of the checksum manifest
   also returned HTTP 200 and the approved hash. The published notes exactly
   match [release-notes.md](release-notes.md).
   [Published release metadata](published-release.json),
   [public access receipt](public-access-verification.json).

## Public source

Both repositories have the signed tag `android-153.0esr-1-beta.1`:

| Repository | Tagged commit |
|---|---|
| `CPlusPlus17/Redoubt` | `938834697e908e53f792eab549771d094722bbd0` |
| `CPlusPlus17/Redoubt-settings` | `2206f8d1e59c0a0c0f69ee3fe5121eb353426687` |

GitHub verifies both tag signatures. A fresh recursive clone of the public tag
resolved the pinned settings gitlink and had clean working trees. All six tracked
candidate inputs and eleven frozen verification sources matched their recorded
hashes. The cloned task-board check passed with 93 tasks, 19 waves and no warnings.
[Tag receipt](published-source-tags.json),
[clone output](public-source-checkout.txt),
[source verification](public-source-verification.json).

The source tag is fixed. The published release notes received two documentation
clarifications after tagging: physical-device testing is still required, and the
checksum file itself is not signed. Neither change affects source or APK inputs.
Publication receipts and current status updates are committed after the source
tag. The default branches and `android-port` were not advanced by publication.

The preparation and candidate test evidence remain in the
[completion audit](../lw-m6-10/completion-audit.md). No additional application build
was required for this asset publication; downloaded artifacts are the exact
already-built and approved files.

Final local validation: `python3 docs/android/board.py --check` exits 0 with
`ok: 93 tasks, 19 waves, 0 warning(s)`; `git diff --check` passes.
