# LW-M4-12 — proof that `--check-strings` can FAIL

`--check-strings` passing is not by itself evidence of anything: a check that
cannot fail is a rubber stamp, and this project has already shipped one green
that came from deleted classes rather than clean code (`LW-M6-07`). This
directory is the fixture pair that shows the check discriminates.

**These are FIXTURES.** They are not builds of this browser and they are not
evidence about the shipped app. Each is a ~1.3 KB APK produced by `aapt2
compile` + `aapt2 link` over four string resources, with no dex and no code.
Their only purpose is to drive the check to both outcomes.

| fixture | resource table | expected | result |
|---|---|---|---|
| `fixture-clean.apk` | 2 strings, no brand | PASS | PASS, `unexplained: 0`, rc 0 |
| `fixture-branded.apk` | the same 2 **plus** `"Firefox couldn't open this page"` and `"Sync your data with your Mozilla account"` | FAIL | FAIL, `unexplained: 2`, rc 1 |

Both source `strings.xml` files are here alongside the APKs, so the input that
produces each verdict is readable without unpacking anything.

`fixture-run.log` holds all three runs — the two fixtures and, for contrast,
the real debug APK (`~/lw-m4-16-debug-apk/apk/fenix-x86_64-debug.apk`), which
passes over **247,547** text rows with `unexplained: 0`, `allowed(url-keep):
300`, `internal(value==name): 3`.

## What the check does and does not cover

Its own detail line says so on every run, which is the property that matters
more than the count:

    running-app traversal: NOT RUN (no device -- pass --emulator or --serial).
    This run covers the compiled resource surface ONLY; text the app renders
    from anywhere other than a string resource is not covered by it

So a pass here is a statement about the compiled resource table across every
locale — complete over that surface — and **not** a statement about the running
UI. It distinguishes "could not run" (exit 2, harness error) from "ran and
found nothing" (exit 0). Both branches are exercised in `fixture-run.log`.

## Reproducing

    A2=<path to aapt2>   # e.g. inside any build tree's gradle-home caches:
    # find ~ -name aapt2 -type f
    LW_SMOKE_PACKAGE=org.redoubtbrowser.fixture \
      ./scripts/android-smoke.sh --check-strings --apk fixture-branded.apk --aapt2 "$A2"

Rebuild the fixtures with the pinned toolchain if they are ever lost:

    aapt2 compile -o res.zip --dir res
    aapt2 link -o fixture.apk -I <sdk>/platforms/android-37.0/android.jar \
      --manifest AndroidManifest.xml res.zip --auto-add-overlay

## Not done

No device and no emulator exist on this host, so the running-app half of
`--check-strings` has never executed. The fixtures prove the **static** half
discriminates; they say nothing about the traversal.
