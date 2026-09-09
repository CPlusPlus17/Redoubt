# Fenix permission-dialog compiler failure

Context correction resolved the three prior nullable-access errors. The next
actual Fenix compiler pass failed `-Werror` because the permission dialog uses
the deprecated AndroidX bundleOf factory. No full tests/runtime ran.

Invocationdd05803acb2349149c35c6f47448d994, source manifest
`4fd7e3fa27b5f187bdc18b23f711dcc444f49a7d880095049f29f4177e1740ce`.
Root's read-only capture checks all165 source files before/after and retains
all three source-overlay receipts, full log, actual source and failed service.
ArchiveSHA256 `d03977f07735713f082f1ba5e9c70975b305c9776248dedef4bc0fb90bb0dc43`.
Every enclosed file size/hash was independently verified on the host.
