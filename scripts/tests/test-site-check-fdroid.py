#!/usr/bin/env python3
"""Hermetic tests for the F-Droid rules of scripts/site-check.py (LW-M6-03).

The F-Droid repository is hosted in the owner's Hetzner Object Storage bucket
(docs/android/FDROID.md); only its human page, site/fdroid.html, is on the site.
Each case copies site-check.py, README.md and site/ into a temporary tree,
writes assets/fdroid/deploy.conf and the fingerprint pin, renders fdroid.html
from the real template the way `fdroid-repo.sh publish-page` does, and checks
the verdict. No network, no keys.

Usage: python3 scripts/tests/test-site-check-fdroid.py
"""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
FP = "C06A44BE77F6D540B68C0069CB2FC7BA6C25E8E1D613A8B87721DFFC75454B8F"  # throwaway
BUCKET, LOC = "redoubt-fdroid-test", "fsn1"
HOST = f"{BUCKET}.{LOC}.your-objectstorage.com"


def render(url, fp=FP, keep=5):
    """What publish-page writes (scripts/fdroid-repo.sh, cmd_publish_page)."""
    host_path = re.sub(r"^https?://", "", url)
    t = (ROOT / "assets/fdroid/fdroid.html.in").read_text()
    spaced = " ".join(fp[i:i + 8] for i in range(0, 64, 8))
    for k, v in {"@REPO_URL@": url, "@REPO_HOSTPATH@": host_path,
                 "@REPO_HOST@": host_path.split("/")[0],
                 "@ARCHIVE_URL@": url[:-len("/repo")] + "/archive", "@FINGERPRINT@": fp,
                 "@LOCATION_NAME@": "Falkenstein, Germany", "@KEEP_VERSIONS@": str(keep),
                 "@FINGERPRINT_SPACED@": spaced}.items():
        t = t.replace(k, v)
    return t


class SiteCheckFdroid(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="site-check-fdroid."))
        (self.tmp / "scripts").mkdir()
        shutil.copy(ROOT / "scripts/site-check.py", self.tmp / "scripts/site-check.py")
        shutil.copy(ROOT / "README.md", self.tmp / "README.md")
        shutil.copytree(ROOT / "site", self.tmp / "site")
        for leftover in ("fdroid.html", "fdroid-qr.svg"):
            (self.tmp / "site" / leftover).unlink(missing_ok=True)
        (self.tmp / "assets/fdroid").mkdir(parents=True)
        self.conf()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def conf(self, bucket="", loc=LOC, extra=""):
        (self.tmp / "assets/fdroid/deploy.conf").write_text(
            f"# test\nS3_BUCKET={bucket}\nS3_LOCATION={loc}\nKEEP_VERSIONS=5\n{extra}")

    def page(self, url=f"https://{HOST}/repo", pin=FP, fp=FP):
        (self.tmp / "site/fdroid.html").write_text(render(url, fp))
        (self.tmp / "site/fdroid-qr.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        if pin is not None:
            (self.tmp / "assets/fdroid/repo-fingerprint").write_text(pin.lower() + "\n")

    def check(self):
        r = subprocess.run([sys.executable, str(self.tmp / "scripts/site-check.py"),
                            str(self.tmp / "site")], capture_output=True, text=True)
        return r.returncode, r.stdout

    def assertPass(self):
        rc, out = self.check()
        self.assertEqual(rc, 0, out)

    def assertFail(self, needle):
        rc, out = self.check()
        self.assertEqual(rc, 1, out)
        self.assertIn(needle, out)

    def test_today_no_bucket_no_page(self):
        self.assertPass()

    def test_rendered_page_for_the_bucket(self):
        self.conf(BUCKET)
        self.page()
        self.assertPass()

    def test_https_links_to_repo_and_archive_on_fdroid_page(self):
        self.conf(BUCKET)
        self.page()
        p = self.tmp / "site/fdroid.html"
        p.write_text(p.read_text().replace(
            "</main>", f'<p><a href="https://{HOST}/repo">r</a> <a href="https://{HOST}/archive">a</a></p></main>'))
        self.assertPass()

    def test_bucket_link_from_another_page(self):
        self.conf(BUCKET)
        p = self.tmp / "site/index.html"
        p.write_text(p.read_text().replace("</main>", f'<p><a href="https://{HOST}/repo">r</a></p></main>'))
        self.assertFail("is not on the allowlist")

    def test_page_without_bucket(self):
        self.page()
        self.assertFail("names no bucket")

    def test_page_for_another_host(self):
        self.conf(BUCKET)
        self.page(url="https://other-bucket.fsn1.your-objectstorage.com/repo")
        self.assertFail("is not on the allowlist")

    def test_page_for_a_local_test_server(self):
        self.conf(BUCKET)
        self.page(url="http://10.0.0.135:9000/redoubt-fdroid/repo")
        self.assertFail("is not on the allowlist")

    def test_fingerprint_differs_from_pin(self):
        self.conf(BUCKET)
        self.page(pin="00" * 32)
        self.assertFail("differ from assets/fdroid/repo-fingerprint")

    def test_page_without_pin(self):
        self.conf(BUCKET)
        self.page(pin=None)
        self.assertFail("repo-fingerprint is missing")

    def test_test_override_committed(self):
        self.conf(BUCKET, extra="PUBLIC_BASE_URL=http://127.0.0.1:9000/x\n")
        self.assertFail("throwaway-test override")

    def test_endpoint_override_committed(self):
        self.conf(BUCKET, extra="S3_ENDPOINT=http://127.0.0.1:9000\n")
        self.assertFail("throwaway-test override")

    def test_unknown_location(self):
        self.conf(BUCKET, loc="ash")
        self.assertFail("S3_LOCATION")

    def test_committed_apk(self):
        (self.tmp / "site/x.apk").write_bytes(b"PK")
        self.assertFail("APKs committed under site/")

    def test_old_pages_layout(self):
        (self.tmp / "site/fdroid/repo").mkdir(parents=True)
        (self.tmp / "site/fdroid/repo/entry.json").write_text("{}")
        self.assertFail("site/fdroid/ exists")


if __name__ == "__main__":
    unittest.main(verbosity=2)
