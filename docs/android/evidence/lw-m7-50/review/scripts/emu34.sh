#!/bin/bash
F=/home/mgysin/redoubt-artifacts/iso-proto/fix
S=/home/mgysin/redoubt-artifacts/iso-proto/sdk34
export ANDROID_SDK_ROOT=$S ANDROID_HOME=$S ANDROID_AVD_HOME=$F/avd ANDROID_EMULATOR_HOME=$F/emuhome ANDROID_USER_HOME=$F/emuhome
exec $S/emulator/emulator -avd iso34 -no-window -no-boot-anim -gpu swangle -no-snapshot -no-metrics -port 5594 -wipe-data > $F/emu34.log 2>&1
