#!/bin/bash
# emu.sh LEVEL PORT : x86_64 emulator for the LW-M7-39 api31-33-fix runs, wiped at boot (fresh userdata).
# LEVEL 30 = "default" image (as the earlier API 30 runs), others google_apis. SDK view drm-a12/sdk/apiLEVEL.
L=$1; P=$2
E=/home/mgysin/redoubt-artifacts/drm-a12/emu; S=/home/mgysin/redoubt-artifacts/drm-a12/sdk/api$L
TAG=google_apis; [ "$L" = 30 ] && TAG=default
A=$E/avd; mkdir -p $A/a$L.avd $E/emuhome
printf 'avd.ini.encoding=UTF-8\npath=%s/a%s.avd\npath.rel=avd/a%s.avd\ntarget=android-%s\n' $A $L $L $L > $A/a$L.ini
cat > $A/a$L.avd/config.ini <<CFG
avd.ini.encoding = UTF-8
abi.type = x86_64
hw.cpu.arch = x86_64
hw.cpu.ncore = 4
image.sysdir.1 = system-images/android-$L/$TAG/x86_64/
tag.id = $TAG
AvdId = a$L
avd.ini.displayname = a$L
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
image.androidVersion.api = $L
fastboot.forceColdBoot = yes
CFG
export ANDROID_SDK_ROOT=$S ANDROID_HOME=$S ANDROID_AVD_HOME=$A ANDROID_EMULATOR_HOME=$E/emuhome ANDROID_USER_HOME=$E/emuhome
exec $S/emulator/emulator -avd a$L -no-window -no-audio -no-boot-anim -gpu swangle -no-snapshot -no-metrics -port $P -wipe-data > $E/emu$L.log 2>&1
