**Redoubt 158.0-3 lets you turn on DRM video, also with content isolation (Android 14 and later; see the limits for 12 and 13).** It installs over 158.0-2 as an update and keeps your settings. Requires Android 8.0 or later.

## What's new since 158.0-2

- **DRM (Widevine) can be turned on.** DRM stays **off by default**. To use it, go to
  *Settings → Site settings → DRM-controlled content* and choose *Ask to allow* or
  *Allowed*. Until 158.0-3 this setting had no effect, because a hidden preference kept DRM
  off.
- **DRM works with content isolation (Android 14+).** In 158.0-2, with DRM turned on in
  about:config, a page asking for DRM crashed its tab again and again. The isolated page process
  now never asks the Android DRM service itself; the main app process answers once, and the
  DRM session runs in the decoder process, as in upstream Firefox 159. Under isolation,
  DRM video plays as H.264 with AAC audio.
- **"Report broken site" is removed** from the menu. In Redoubt it either discarded the report while saying it was sent, or handed the page address to webcompat.com.

Unchanged: Firefox 158.0 engine from the same official source, uBlock Origin 1.75.0, the
opt-in update check, content isolation on Android 12+, the same signing key.

## Known limitations

- **Android 12 and 13: DRM video stops after a few seconds** on sites whose license server uses
  the Widevine service certificate, which is common (found in the 158.0-3 acceptance). Android 12-13 drop the signal that asks for the license after the
  Widevine service certificate, so only the unencrypted start of a stream plays. Nothing
  crashes. Android 14 and later, and Android 8-11, are not affected.
- Under isolation (Android 12+), DRM sites that offer only VP9 or Opus streams do not play.
- DRM was tested with a public Widevine test stream on emulators (Android 11, 12, 14) and two
  phones (Android 15 and 17); not with a streaming service account.
