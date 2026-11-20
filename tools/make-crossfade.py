#!/usr/bin/env python3
"""Crossfade animations for the README from tools/readme-media.py shots (looping GIF).

    python3 tools/make-crossfade.py tour SHOTS_DIR          → assets/theme-tour.gif
    python3 tools/make-crossfade.py prettify SHOTS_DIR      → assets/prettify.gif

Each picture is a 1:1 crop of the top-left of a 1920×1080 shot (crisp text) with a small
label, shown for a while, then eased into the next. Needs ImageMagick.
"""
import math
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOUR = [("caelestia", "Caelestia · follows your wallpaper"), ("rose-pine", "Rosé Pine"),
        ("kanagawa-wave", "Kanagawa"), ("everforest-dark", "Everforest"),
        ("night-owl", "Night Owl"), ("synthwave-84", "Synthwave '84"), ("light", "Kate++ Light")]
PRETTIFY = [("prettify-before", "One long line of JSON"), ("prettify-after", "Ctrl+Alt+Shift+B")]
PRESETS = {  # name: (shots, prefix, crop W×H, hold in 1/100 s, output)
    "tour": (TOUR, "theme-", (1280, 720), 170, "theme-tour.gif"),
    "prettify": (PRETTIFY, "", (1120, 560), 200, "prettify.gif"),
}
W, H = 1280, 720
FADE, FADE_CS = 7, 6      # a 7-frame eased crossfade, 6/100 s per frame


def magick(*args):
    subprocess.run(["magick", *map(str, args)], check=True)


def card(src, text, out):
    """Crop and add a pill label in the bottom-right corner."""
    pad, h, size = 22, 46, 24
    w = 28 + len(text) * 13
    x1, y1 = W - 26, H - 26
    x0, y0 = x1 - w, y1 - h
    magick(src, "-crop", f"{W}x{H}+0+0", "+repage",
           "-fill", "#0d1117e0", "-draw", f"roundrectangle {x0},{y0},{x1},{y1} 16,16",
           "-font", "DejaVu-Sans-Bold", "-pointsize", str(size), "-fill", "white",
           "-gravity", "SouthEast", "-annotate", f"+{26 + pad - 8}+{26 + 11}", text, out)


def main():
    global W, H
    if len(sys.argv) < 3 or sys.argv[1] not in PRESETS:
        sys.exit(__doc__)
    items, prefix, (W, H), hold, name = PRESETS[sys.argv[1]]
    shots = Path(sys.argv[2])
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "assets" / name
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        cards = []
        for i, (src, label) in enumerate(items):
            c = t / f"card{i}.png"
            card(shots / f"{prefix}{src}.png", label, c)
            cards.append(c)
        seq = []          # (frame, delay in 1/100 s): one long frame per theme, short fade frames
        for i, c in enumerate(cards):
            nxt = cards[(i + 1) % len(cards)]
            seq.append((c, hold))
            for k in range(1, FADE + 1):
                e = 0.5 - 0.5 * math.cos(math.pi * k / (FADE + 1))   # ease in-out
                f = t / f"x{i}_{k}.png"
                magick(c, nxt, "-compose", "blend", "-define", f"compose:args={round(e * 100)}",
                       "-composite", f)
                seq.append((f, FADE_CS))
        args = []
        for f, d in seq:
            args += ["-delay", str(d), f]
        # one palette per frame (themes differ a lot), then let ImageMagick store only changes
        magick(*args, "-dither", "None", "-colors", "160", "-layers", "Optimize", "-loop", "0", out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
