# Actual cleanup source inputs

Root read these paths from the isolated guest at2026-09-09T03:10:34Z, without
changing source or running a build. The archive contains51 existing source files;
13 other requested paths were absent. Twelve existing paths match the then-active
165-file manifest `4fd7e3fa27b5f187bdc18b23f711dcc444f49a7d880095049f29f4177e1740ce`.
All captured files were checked before and after capture. `source-inputs.json`
records hashes, sizes, absences and which files were bound to that manifest.

Archive SHA256:
`f32424a86e6123e7158baddf7d471366381ebbfc0ae7dafe56c195fb611a6eb7`.
These inputs support Task37 source design and implementation; they establish
neither cleanup completion nor compiled/runtime behavior. In particular,
`DeleteBrowsingDataOnQuitFragmentTest.kt` already exists and must be preserved.
