# Native4 APK compilation failure

The queued APK build failed on2026-09-09 at02:53UTC,185seconds after start.
Native4 compilation and the merged AAR had already passed. Kotlin2.3.21 rejected
`FxSuggestAdmission.Snapshot` under `-Werror`: its internal primary constructor
was exposed through generated copy visibility. Full Fenix/other target tests and
runtime stages did not run. Existing APKs in the output directory are older
artifacts and are not results of this failed build.

Read-only `capture.py` preserved the complete Gradle log, source/resource/driver
receipts, failed checkpoint identity, memory state and four actual source files.
Root verified every enclosed member hash and size. `guest-evidence.tar.gz` SHA256
is `4dfeea9827fe65cc7863471ed73359c4bfc14e998e9258659995de1b9cc215ec`.
The165-file failed-source manifest is
`be181f8e7c01c02bdc3d8c3d45668619642d810a1ce72e07a1796c3de0b6d4e1`.
No source changed during capture. The inherited OOM counters did not increase.

The correction and its separate source overlay are in
`../admission-copy-correction/`; successful native evidence remains immutable.
