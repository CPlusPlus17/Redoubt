#!/usr/bin/env python3
"""Render the Google Play listing graphics (LW-M6-12, docs/android/PLAY.md).

  icon-512.png                 512x512, 32-bit PNG with alpha (Play: app icon)
  feature-graphic-1024x500.png 1024x500, 24-bit PNG, no alpha (Play: feature graphic)

Both are drawn from the launcher mark itself, the FORT path and SLATE colour in
scripts/gen-android-brand.py (LW-M4-07), so the store listing and the installed
app agree. The mark sits on the adaptive-icon 108-unit canvas; the icon keeps
that framing (the mark fills the middle half, as on a launcher), and Play applies
its own rounded mask to the square, so the square is opaque slate.

Needs Pillow and a Noto Sans (or DejaVu Sans) font for the feature graphic's
text. Run from anywhere; writes next to this file.
"""
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SRC = (REPO / "scripts" / "gen-android-brand.py").read_text(encoding="utf-8")
FORT = re.search(r'FORT = \((.*?)\)\n', SRC, re.S).group(1)
FORT = "".join(re.findall(r'"([^"]*)"', FORT))
SLATE = re.search(r'SLATE = "(#[0-9A-Fa-f]{6})"', SRC).group(1)
TAGLINE = ("A privacy-hardened browser", "for Android, built from source")

POINTS = [(float(x), float(y)) for x, y in re.findall(r"(\d+(?:\.\d+)?),(\d+(?:\.\d+)?)", FORT)]
SS = 4  # supersampling factor for smooth polygon edges


def mark(draw, x0, y0, size):
    """Draw the fort, its 108-unit canvas mapped to a size x size box at (x0, y0)."""
    k = size / 108.0
    draw.polygon([(x0 + x * k, y0 + y * k) for x, y in POINTS], fill="white")


def font(px):
    for name in ("/usr/share/fonts/google-noto-vf/NotoSans[wght].ttf",
                 "/usr/share/fonts/google-noto/NotoSans-Regular.ttf",
                 "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"):
        if Path(name).exists():
            return ImageFont.truetype(name, px)
    sys.exit("make-graphics: no Noto Sans / DejaVu Sans font found")


def icon():
    n = 512 * SS
    im = Image.new("RGBA", (n, n), SLATE)
    mark(ImageDraw.Draw(im), 0, 0, n)
    im = im.resize((512, 512), Image.LANCZOS)
    im.save(HERE / "icon-512.png", optimize=True)


def feature():
    w, h = 1024 * SS, 500 * SS
    im = Image.new("RGB", (w, h), SLATE)
    d = ImageDraw.Draw(im)
    mark(d, -10 * SS, 25 * SS, 450 * SS)
    d.text((404 * SS, 282 * SS), "Redoubt", font=font(96 * SS), fill="white", anchor="ls")
    sub = font(34 * SS)
    d.text((404 * SS, 338 * SS), TAGLINE[0], font=sub, fill="#CBD5E1", anchor="ls")
    d.text((404 * SS, 384 * SS), TAGLINE[1], font=sub, fill="#CBD5E1", anchor="ls")
    im = im.resize((1024, 500), Image.LANCZOS)
    im.save(HERE / "feature-graphic-1024x500.png", optimize=True)


if __name__ == "__main__":
    icon()
    feature()
    for f in ("icon-512.png", "feature-graphic-1024x500.png"):
        im = Image.open(HERE / f)
        print(f"{f}: {im.size[0]}x{im.size[1]} {im.mode} {(HERE / f).stat().st_size} bytes")
