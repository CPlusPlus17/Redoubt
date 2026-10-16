#!/usr/bin/env python3
"""api31-33-fix (LW-M7-39): the DRM lines of a flow logcat, for the repository (full captures stay in
~/redoubt-artifacts/drm-a12/runs). Kept: Gecko EME/RemoteCDM log lines, NdkMediaDrm, the Redoubt
isolation-eme lines, Widevine (WVCdm), MediaDrm/MediaCrypto, process deaths, fatal errors.
count.py gives the same numbers on the trimmed file. usage: trim-logcat.py IN(.gz) OUT.gz"""
import gzip, re, sys
src, dst = sys.argv[1], sys.argv[2]
op = gzip.open if src.endswith(".gz") else open
lines = op(src, "rt", errors="replace").read().splitlines()
pat = re.compile(r"/EME |/MediaKeys |/RemoteCDM |MediaKeySession|NdkMediaDrm|Redoubt isolation-eme|WVCdm|MediaDrm|MediaCrypto|has died|FATAL EXCEPTION|Fatal signal|ANR in |Failed to query crypto")
keep = [l for l in lines if pat.search(l)]
with gzip.open(dst, "wt") as o:
    o.write("# trimmed by trim-logcat.py: %d of %d lines kept\n" % (len(keep), len(lines)))
    o.write("\n".join(keep) + "\n")
print(dst, len(keep), "of", len(lines))
