#!/bin/bash
# The throwaway-signed test APKs differ from the CI's unsigned APKs only by signature entries. usage: apk-identity.sh OUT
R=/home/mgysin/redoubt-artifacts/release-158.0-3/accept2
BT=/home/mgysin/.local/state/codex-desktop/tmp/fivur-android-sdk36/build-tools/36.0.0
{ for a in x86_64 arm64-v8a; do
  u=$R/ci/redoubt-android-unsigned/fenix-$a-release-unsigned.apk; s=$R/apk/fenix-$a-158.0-3-throwaway.apk
  echo "== $a"; echo "unsigned (CI) sha256 $(sha256sum $u | cut -c1-64)"; echo "throwaway-signed sha256 $(sha256sum $s | cut -c1-64)"
  python3 - $s $u <<'PY'
import sys, zipfile, hashlib
def h(p): z = zipfile.ZipFile(p); return {i.filename: hashlib.sha256(z.read(i)).hexdigest() for i in z.infolist() if not i.is_dir()}
S, U = h(sys.argv[1]), h(sys.argv[2])
sig = sorted(k for k in S if k.startswith("META-INF/") and k not in U)
print("entries: %d signed, %d unsigned; non-signature entries differing: %d" % (len(S), len(U), sum(1 for k in set(S) | set(U) if k not in sig and S.get(k) != U.get(k))))
print("signature-only entries in the signed APK:", sig)
PY
  $BT/apksigner verify -v --print-certs $s 2>/dev/null | grep -E "^Verifies|Verified using|Signer #1 certificate (DN|SHA-256)"
done; } > $1
