#!/bin/bash
# Three fresh-profile baseline runs (graphics acceptance included) with the committed harness.
export SERIAL=emulator-5582
R=/home/mgysin/redoubt-artifacts/esr-153.4/build/defc/runtime
for n in 1 2 3; do $R/run-check.sh baseline-defc-r$n; done
echo BATCH DONE
