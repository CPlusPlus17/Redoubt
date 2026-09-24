# Full Fenix regression rerun

The four source changes are the reviewed HomeActivity custom-tab correction,
the real-store cookie settings test fixture, explicit Suggest choices in the
startup metrics fixture, and the new four-case account intent regression class.
All prior165 source bindings are checked, as are the existing metrics test bytes
and absence of the new class. The resulting167 manifest is
`f55095bfee92ddfac6f480c9cdef29bbb20acc67377130233e52b765bcbd4f9a`.
Root and coverage_map independently derived exactly the same manifest.

`inputs.json` pins all four bodies and the complete staging/test inputs. The
guarded stage preserves prior sources and receipts, checks the native inputs and
historical APKs, and writes only the four reviewed files. Full Fenix and all prior
component selections run with fresh XML and no Gradle build-cache reuse. The
five implicated Fenix classes and the new class must pass; all component skips
are now rejected. The existing Fenix allowance remains unchanged.

This candidate contains a production Kotlin change. Its test receipt retains the
old compiled APK manifest only as history. APK rebuild/resource verification and
runtime checks require separate current evidence after the tests pass.
