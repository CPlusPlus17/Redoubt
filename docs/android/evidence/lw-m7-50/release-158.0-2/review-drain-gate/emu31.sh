#!/bin/bash
# API 31 google_apis x86_64 emulator for 158.0-2 tests, serial emulator-5574, wiped at boot.
E=/home/mgysin/redoubt-artifacts/iso-158-2/emu; S=/home/mgysin/redoubt-artifacts/iso-158-2/sdk31
A=$E/avd; mkdir -p $A/iso31.avd $E/emuhome
printf 'avd.ini.encoding=UTF-8\npath=%s/iso31.avd\npath.rel=avd/iso31.avd\ntarget=android-31\n' $A > $A/iso31.ini
cat > $A/iso31.avd/config.ini <<CFG
avd.ini.encoding = UTF-8
abi.type = x86_64
hw.cpu.arch = x86_64
hw.cpu.ncore = 4
image.sysdir.1 = system-images/android-31/google_apis/x86_64/
tag.id = google_apis
AvdId = iso31
avd.ini.displayname = iso31
hw.ramSize = 4096
hw.lcd.width = 1080
hw.lcd.height = 1920
hw.lcd.density = 420
disk.dataPartition.size = 6442450944
hw.audioInput = no
hw.audioOutput = no
hw.gpu.enabled = yes
hw.gpu.mode = swangle
hw.keyboard = yes
PlayStore.enabled = false
image.androidVersion.api = 31
fastboot.forceColdBoot = yes
CFG
export ANDROID_SDK_ROOT=$S ANDROID_HOME=$S ANDROID_AVD_HOME=$A ANDROID_EMULATOR_HOME=$E/emuhome ANDROID_USER_HOME=$E/emuhome
exec $S/emulator/emulator -avd iso31 -no-window -no-audio -no-boot-anim -gpu swangle -no-snapshot -no-metrics -port 5574 -wipe-data > $E/emu31.log 2>&1
