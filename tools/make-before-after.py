#!/usr/bin/env python3
"""Build the README's before → after wipe animation from two screenshots.

Usage:  python3 tools/make-before-after.py before.png after.png [out.gif]
Needs ImageMagick (magick) and ffmpeg.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
from kpp import core  # noqa: E402
W, H = 1280, 720          # output size
STEPS = 28                # frames per wipe
HOLD = 22                 # frames to hold each side (at 20 fps)


def magick(*args):
    subprocess.run(["magick", *map(str, args)], check=True)


def label(img, text, left, out):
    """Pill label in a bottom corner (keeps menus and toolbars visible)."""
    y0, y1 = H - 96, H - 50
    x0, x1 = (24, 200) if left else (W - 200, W - 24)
    magick(img, "-fill", "#0d1117d9", "-draw", f"roundrectangle {x0},{y0},{x1},{y1} 14,14",
           "-font", "DejaVu-Sans-Bold", "-pointsize", "24", "-fill", "white",
           "-gravity", "SouthWest" if left else "SouthEast", "-annotate", "+46+60", text, out)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    before, after = Path(sys.argv[1]), Path(sys.argv[2])
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "assets/before-after.gif"
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        b, a = t / "b.png", t / "a.png"
        magick(before, "-resize", f"{W}x{H}!", t / "b0.png")
        magick(after, "-resize", f"{W}x{H}!", t / "a0.png")
        label(t / "b0.png", "Kate", True, b)
        label(t / "a0.png", "Kate++", False, a)

        frames = []
        # ease-in-out positions of the divider, before → after and back
        ease = [0.5 - 0.5 * __import__("math").cos(__import__("math").pi * i / STEPS) for i in range(STEPS + 1)]
        xs = [W] * HOLD + [round(W * (1 - e)) for e in ease] + [0] * (HOLD * 2) + \
             [round(W * e) for e in ease] + [W] * HOLD
        for n, x in enumerate(xs):
            f = t / f"f{n:03d}.png"
            if x >= W:
                magick(b, f)
            elif x <= 0:
                magick(a, f)
            else:
                magick(a, "(", b, "-crop", f"{x}x{H}+0+0", "+repage", ")", "-geometry", "+0+0", "-composite",
                       "-fill", "white", "-draw", f"rectangle {x-2},0 {x+1},{H}",
                       "-fill", "white", "-draw", f"circle {x},{H//2} {x+20},{H//2}",
                       "-fill", "#8b5cf6", "-draw", f"polygon {x-12},{H//2} {x-5},{H//2-7} {x-5},{H//2+7}",
                       "-fill", "#8b5cf6", "-draw", f"polygon {x+12},{H//2} {x+5},{H//2-7} {x+5},{H//2+7}", f)
            frames.append(f)
        palette = t / "palette.png"
        pattern = str(t / "f%03d.png")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", "20", "-i", pattern,
                        "-vf", "palettegen=max_colors=192:stats_mode=diff", str(palette)], check=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", "20", "-i", pattern, "-i", str(palette),
                        "-lavfi", "paletteuse=dither=sierra2_4a:diff_mode=rectangle", "-loop", "0", str(out)], check=True)
    core.info(f"wrote {out}")


if __name__ == "__main__":
    main()
