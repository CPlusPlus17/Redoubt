# APK retry: Suggest compiled, Fenix nullable context failed

Invocation2364069cd7cb4cc5ab2f142f42f90ac6 ran at03:02:35UTC on2026-09-09.
The corrected Suggest Kotlin component compiled successfully, then Fenix failed
three nullable Fragment.context accesses in the card-selector list. Full tests
and runtime did not run. The unchanged-state assertion is authored but unrun.

The complete failed log, source/overlay/driver receipts and actual source files
are retained in `guest-evidence.tar.gz`, SHA256
`84bdb1cbc6dfc7b3f42da8442c093791c6c6ca1f9afb1391ad630625eb46761a`.
Root verified every enclosed file hash/size. Failed source manifest:
`395ce6827e94f48cb634be86726d39b7e96f6e4fcb515173b2fff0865c34555d`.
All165 source files matched before/after read-only capture. The next correction
and separate staging receipt are in `../search-context-correction/`.
