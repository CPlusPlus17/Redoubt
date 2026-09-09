# Target rerun after the coroutine API opt-in

`inputs.json` pins the complete rerun drivers and the five cumulative test fixture
bodies. `stage-optin-fixture.py` checks the prior failed run, all 165 source bodies,
the prior staging receipt, all three native inputs and all four compiled APKs
before changing the single permissions test class. The four earlier fixes are
required to be present and remain byte-identical.

The new test source manifest is
`659bf836ec885425b596bf077236190e8df30b2285df625ff3988c5dc93129b6`.
The compiled APK source manifest remains
`c53736e87152ba6de7ae232efd0a26197601027e4553be3f5f4bd7e6045601ae`.
Both identities accompany the test and runtime evidence.

The checkpoint reruns the complete Fenix task and all previously selected component
classes with Gradle build-cache reuse disabled and prior XML moved aside. It runs
the existing Fenix allowlist gate and the fresh-results gate without changing
either. Only a passing test stage permits the fresh emulator smoke, uBlock Origin
lifecycle and preference audit of the same compiled APKs.

This document records preparation; target success requires the actual new service,
logs and gate outputs. Production compilation and APK resource checks were already
verified separately and are not rerun for the test annotation.
