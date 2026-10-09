# Device checks: the ten-minute phone pass

**Owner: LW-M7-49.** The emulator measured the honoured layer of `PARITY.md`
rows 5, 7, 8 and 9 (`evidence/lw-m7-49/`). What an emulator cannot show is a
real phone's screen, fonts, GPU and network. These steps cover that on the
owner's phone in about ten minutes. They need no adb, no root and no setting
changed in Redoubt.

Record the Redoubt version (Settings > About Redoubt) and the date before you
start. Use a normal tab, not a private one.

| # | PARITY row | what | time |
|---|---|---|---|
| 1 | 5 HTTPS-only | interstitial, exception, silent upgrade | 2 min |
| 2 | 9 RFP | fingerprint coherence on the real device | 3 min |
| 3 | 8 TLS floor | TLS 1.0/1.1 refused, 1.2 loads | 2 min |
| 4 | 7 revocation | CRLite refuses a revoked certificate | 3 min |

## 1. HTTPS-only (row 5) and 2. RFP coherence (row 9)

One page covers both. It is served from your own computer on the home
network; it loads nothing from anywhere else. The page needs JavaScript, so it
is not on redoubtbrowser.org (`site-check.py` forbids scripts there).

1. On a computer on the same Wi-Fi, in the repository:

   ```sh
   python3 scripts/android-device-probe.py
   ```

   It prints a URL such as `http://192.168.1.20:8765/rfp-probe?post=1`. If the
   computer's firewall blocks port 8765, open it for the duration or pass
   `--port`.
2. Type that URL into Redoubt's address bar.
3. **Row 5, expect:** Redoubt's "Secure site not available" page with a
   **Continue to HTTP site** button. (The computer serves plain HTTP only, so
   this is the HTTPS-only interstitial, not an error.) Tap the button.
4. **Row 9, expect:** the page fills with JSON, and within a few seconds the
   computer prints `RFP coherence on the device: PASS` with every graded line
   `ok`, and writes `rfp-device-report.json`. The graded values must be:
   `userAgent` `Mozilla/5.0 (Android 10; Mobile; rv:<N>.0) Gecko/<N>.0
   Firefox/<N>.0`, `platform` and `oscpu` `Linux armv81`, `hardwareConcurrency`
   4, time zone `Atlantic/Reykjavik` (your phone is on Europe/Zurich, so this
   proves the spoof), `screen` equal to the window size, timer step 16.67 ms.
5. Keep the JSON. Its "recorded only" part (real window size, DPR, fonts,
   WebGL, canvas) is what the emulator could not measure; send it or commit it
   under `docs/android/evidence/lw-m7-49/device/`.
6. **Row 5 again, exception scope:** reload the same URL; it must load directly
   (the exception holds for that address). Then open the second URL the
   script printed (same computer, port + 1): it must show the interstitial
   again. Close Redoubt fully (swipe it away), reopen it and load the first URL:
   on the emulator the exception was stored for the session only
   (`expireType=1`), so expect the interstitial again. The restart itself was
   not measured on the emulator; this step is the first measurement of it.
   Then stop the script with Ctrl-C.

Optional, public site: `http://example.com/` must end on `https://example.com/`
without any interstitial (silent upgrade).

## 3. TLS version floor (row 8)

These pages are BadSSL's public test servers (read-only, no login). Expect:

| URL | expect |
|---|---|
| `https://tls-v1-0.badssl.com:1010/` | Redoubt's error page, no content |
| `https://tls-v1-1.badssl.com:1011/` | Redoubt's error page, no content |
| `https://tls-v1-2.badssl.com:1012/` | the green BadSSL page loads |

If the 1.0 or 1.1 page loads, row 8 is broken on the device: stop and record
the version. (Emulator, 2026-10-10: 1.0 and 1.1 refused with
`SSL_ERROR_PROTOCOL_VERSION_ALERT`.)

## 4. Certificate revocation, CRLite (row 7)

CRLite filters arrive through Remote Settings after the first start with a
network, about 30-45 s on the emulator. Leave Redoubt open on Wi-Fi for two
minutes first.

| URL | expect |
|---|---|
| `https://badssl.com/` | loads (control) |
| `https://revoked.badssl.com/` | Redoubt's certificate error page; it must not load |

On the emulator `revoked.badssl.com` was refused with
`SEC_ERROR_REVOKED_CERTIFICATE`, and loaded once CRLite was turned off, so a
refusal here is CRLite working. Do **not** use Let's Encrypt's
`revoked-isrgroot*.letsencrypt.org` as a test: their certificates are re-issued
and revoked every few days, and CRLite had not caught up with one revoked two
days earlier (`evidence/lw-m7-49/README.md`). That is CRLite's publication lag,
the same on desktop.

If `revoked.badssl.com` loads after two minutes on Wi-Fi, try once more after
ten minutes. If it still loads, the filters did not reach the phone: record it,
it is a row 7 failure on the device.

## Recording the result

Fill this in and add it to `evidence/lw-m7-49/device/` (with
`rfp-device-report.json`):

```
date:            2026-10-__
phone / Android: ______ / __
Redoubt:         ______ (Settings > About)
1 HTTPS-only:    interstitial yes/no | exception holds yes/no | other port interstitial yes/no | after restart interstitial yes/no
2 RFP:           PASS/FAIL (failed items: ______)
3 TLS:           1.0 refused yes/no | 1.1 refused yes/no | 1.2 loads yes/no
4 revocation:    badssl.com loads yes/no | revoked.badssl.com refused yes/no
```

Then update the row's "device" column in `PARITY.md` with the date and the
evidence path.
