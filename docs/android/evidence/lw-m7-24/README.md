# Ordinary home-section defaults

Source candidate only; **not compiled, installed or behavior-tested**.

The four Fenix sections corresponding to desktop `FirefoxHome.TopSites=false`
and `Highlights=false` now default off: top sites, recent tabs, bookmarks and
recently visited/history. The same four nightly overrides are off; release,
beta, nightly and developer resolved maps are checked by `replay.py`. Parsing
the before/after FML confirms no other feature value changed.

The actual Settings getters use boolean preferences with these generated FML
defaults. Stored explicit true/false values still win. HomeSettingsFragment
reads those getters into its existing switches; its visibility checks do not
depend on these four FML values. The new patch changes neither those controls
nor any bookmark/history store. Existing ambiguous stored defaults are preserved.
Three new Robolectric tests use real Settings and SharedPreferences to check
fresh fallbacks, mixed stored choices and off/on/off through object recreation.
They are authored but have not run in the target build.

`source-baseline.tar.gz` and `source-files.json` bind the exact two patch paths.
`replay.log` records zero-fuzz/no-offset application to the frozen predecessor,
and both orders of the shared FML file with no-nimbus produce identical bytes.
The home-first order shifts later no-nimbus hunks by two lines, without fuzz.
The root registry declares that pair order-free. No frozen source or guest was
modified; the private candidate is under the host's lw-m7-24 artifact directory.

Remaining: integrate with the next Fenix candidate, compile generated FML and
the target tests, run the full Fenix gate, then verify fresh/explicit-choice/
restart home and customization UI with populated history/bookmarks. Settings
object recreation is not process-restart evidence. Firefox Suggest, automatic
default shortcuts/bookmarks, advertisements and other home content remain
separate mapped requirements; this patch does not mark those complete.
