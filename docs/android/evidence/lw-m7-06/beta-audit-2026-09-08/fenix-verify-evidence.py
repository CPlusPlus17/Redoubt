#!/usr/bin/env python3
"""Verify the retained final Fenix run against live sources and candidate APKs."""
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET

base = Path(__file__).resolve().parent
repo = base.parents[4]
source = repo / "librewolf-153.0esr-1"
clone = repo / "librewolf-153.0esr-1-beta-20260908"
results = source / "obj-x86_64/gradle/build/mobile/android/fenix/app/test-results/testDebugUnitTest"
manifest = json.loads(gzip.decompress((base / "fenix-source-sha256.json.gz").read_bytes()))


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


changed = [name for name, digest in manifest.items()
           if not (source / name).is_file() or sha256(source / name) != digest]
clone_changed = [name for name, digest in manifest.items()
                 if not (clone / name).is_file() or sha256(clone / name) != digest]
started = datetime.datetime.fromisoformat((base / "fenix-started.txt").read_text().strip())
xml = sorted(results.glob("TEST-*.xml"))
stale = [p.name for p in xml if p.stat().st_mtime < started.timestamp()]
totals = {key: sum(int(ET.parse(p).getroot().get(key, 0)) for p in xml)
          for key in ("tests", "failures", "errors", "skipped")}
with tarfile.open(base / "fenix-junit-xml.tar.gz") as archive:
    members = archive.getmembers()
    mismatches = [m.name for m in members
                  if archive.extractfile(m).read() != (results / m.name).read_bytes()]
    archive_names_match = sorted(m.name for m in members) == sorted(p.name for p in xml)
    with tempfile.TemporaryDirectory(prefix="lw-fenix-archive-") as temp:
        archive.extractall(temp, filter="data")
        gate = subprocess.run(
            ["python3", "docs/android/board.py", "--check-fenix-tests", "--results", temp],
            cwd=repo, text=True, capture_output=True,
        )
        # Preserve the captured evidence when replay uses a new temporary path.
        if not (base / "fenix-archive-gate.txt").exists():
            (base / "fenix-archive-gate.txt").write_text(gate.stdout + gate.stderr)
default_gate = subprocess.run(
    ["python3", "docs/android/board.py", "--check-fenix-tests"],
    cwd=repo, text=True, capture_output=True,
)
(base / "fenix-gate-default.txt").write_text(default_gate.stdout + default_gate.stderr)
candidate = json.loads((base / "fenix-final-candidate.json").read_text())
apk_changed = [entry["path"] for entry in candidate["apks"]
               if sha256(repo / entry["path"]) != entry["sha256"]]
raw_log = base / "fenix-unit-tests.log"
log_bytes = raw_log.read_bytes() if raw_log.exists() else gzip.decompress((base / "fenix-unit-tests.log.gz").read_bytes())
recorded_log_hash = next(line.split()[0] for line in (base / "fenix-provenance-after.txt").read_text().splitlines()
                         if line.endswith("/fenix-unit-tests.log"))
log_hash_matches = hashlib.sha256(log_bytes).hexdigest() == recorded_log_hash
log = log_bytes.decode()
failed_tasks = re.findall(r"^> Task (\S+) FAILED$", log, re.MULTILINE)
report = {
    "run_started_utc": started.isoformat(),
    "oldest_xml_utc": datetime.datetime.fromtimestamp(min(p.stat().st_mtime for p in xml), datetime.timezone.utc).isoformat(),
    "newest_xml_utc": datetime.datetime.fromtimestamp(max(p.stat().st_mtime for p in xml), datetime.timezone.utc).isoformat(),
    "source_file_count": len(manifest),
    "source_files_changed_since_test_start": changed,
    "release_clone_sources_different": clone_changed,
    "stale_xml": stale,
    "xml_class_count": len(xml),
    "xml_totals": totals,
    "xml_archive_count": len(members),
    "xml_archive_names_match_live_results": archive_names_match,
    "xml_archive_content_mismatches": mismatches,
    "archive_gate_exit": gate.returncode,
    "default_gate_exit": default_gate.returncode,
    "final_candidate_apk_hashes_changed": apk_changed,
    "gradle_failed_tasks": failed_tasks,
    "decompressed_log_matches_original_sha256": log_hash_matches,
}
(base / "fenix-integrity.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
assert not changed and not clone_changed and not stale and not mismatches and not apk_changed
assert archive_names_match and gate.returncode == 0 and default_gate.returncode == 0
assert len(xml) == 598 and totals["tests"] == 5426
assert failed_tasks == [":fenix:testDebugUnitTest"]
assert log_hash_matches
