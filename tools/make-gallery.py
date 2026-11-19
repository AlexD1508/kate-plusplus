#!/usr/bin/env python3
"""Regenerate the README theme gallery images (assets/themes.png, assets/intensity.png).

Needs: ksyntaxhighlighter6, firefox, ImageMagick (magick) and the JetBrains Mono font.
Usage:  python3 tools/make-gallery.py
"""
import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
from kpp import ports, theme as T  # noqa: E402

SAMPLE = """use std::collections::HashMap;

/// Count how often each word appears.
fn word_counts(text: &str) -> HashMap<String, usize> {
    let mut counts = HashMap::new();
    for word in text.split_whitespace() {
        *counts.entry(word.into()).or_default() += 1;
    }
    counts // TODO: ignore punctuation
}

const LIMIT: u32 = 0x40;
let ratio = 3.14 * LIMIT as f64;
println!("{} notes, {:.1}%", counts.len(), ratio);
"""

# Example Caelestia schemes (Material You tokens) for a rose and a forest wallpaper.
ROSE = {"surface": "191113", "onSurface": "efdee0", "onSurfaceVariant": "d6c2c4", "primary": "ffb1c0",
        "outline": "9f8c8e", "primaryContainer": "713341", "onPrimaryContainer": "ffd9de",
        "surfaceContainerLow": "22191b", "surfaceContainerHigh": "312829",
        "surfaceContainerHighest": "3c3234", "error": "ffb4ab", "errorContainer": "93000a",
        "onErrorContainer": "ffdad6"}
FOREST = {"surface": "0f1512", "onSurface": "dee4df", "onSurfaceVariant": "bfc9c3", "primary": "87d6bb",
          "outline": "89938e", "primaryContainer": "005141", "onPrimaryContainer": "a3f2d6",
          "surfaceContainerLow": "171d1a", "surfaceContainerHigh": "252b29",
          "surfaceContainerHighest": "303634", "error": "ffb4ab", "errorContainer": "93000a",
          "onErrorContainer": "ffdad6"}

POPULAR = [(f"{name} · by {ports.designer(slug)}", ports.build(slug)) for slug, (name, *_) in ports.PORTS.items()]

GALLERIES = {
    "themes": [
        ("Caelestia · rose wallpaper", T.caelestia_ui(ROSE), "balanced"),
        ("Caelestia · forest wallpaper", T.caelestia_ui(FOREST), "balanced"),
        ("KDE Plasma · Breeze Dark", T.derive_ui("141618", "fcfcfc", "3daee9", "da4453", "a1a9b1"), "balanced"),
        ("Kate++ Dark", T.static_ui("dark"), "balanced"),
        ("Kate++ Light", T.static_ui("light"), "balanced"),
    ],
    "intensity": [
        ("syntax-colors = soft", T.static_ui("dark"), "soft"),
        ("syntax-colors = balanced", T.static_ui("dark"), "balanced"),
        ("syntax-colors = vivid", T.static_ui("dark"), "vivid"),
    ],
}

CSS = """*{box-sizing:border-box}html{zoom:2}body{margin:0;background:#0d1117;font-family:'JetBrainsMono Nerd Font','JetBrains Mono',monospace}
.wrap{padding:30px;display:flex;flex-wrap:wrap;gap:26px;justify-content:center;width:1820px}
.card{width:560px;border-radius:18px;overflow:hidden;box-shadow:0 18px 40px #0009,0 0 0 1px #ffffff14}
.bar{display:flex;align-items:center;justify-content:space-between;padding:14px 18px 8px}
.dots i{display:inline-block;width:11px;height:11px;border-radius:50%;background:currentColor;opacity:.22;margin-right:7px}
.label{font:600 13px 'Inter','Noto Sans',sans-serif;letter-spacing:.02em;padding:4px 11px;border:1px solid;border-radius:999px}
.code{padding:6px 0 18px;font-size:14px;line-height:1.6}
.ln{display:flex;padding:0 18px}.n{flex:0 0 22px;text-align:right;margin-right:18px}.c{white-space:pre}"""


def card(work, slug, label, theme):
    td = work / "data/org.kde.syntax-highlighting/themes"
    T.write_theme(td / f"{slug}.theme", theme)
    out = work / f"{slug}.html"
    subprocess.run(["ksyntaxhighlighter6", "-t", slug, "-s", "Rust", "-o", str(out), str(work / "sample.rs")],
                   check=True, env={"XDG_DATA_HOME": str(work / "data"), "PATH": "/usr/bin:/bin"})
    pre = re.search(r"<pre>(.*)</pre>", out.read_text(), re.S).group(1).strip("\n")
    ec, ts = theme["editor-colors"], theme["text-styles"]
    bg, fg, cur = ec["BackgroundColor"], ts["Normal"]["text-color"], ec["CurrentLine"]
    ln, acc = ec["LineNumbers"], ts["Keyword"]["text-color"]
    rows = []
    for i, line in enumerate(pre.split("\n"), 1):
        hl = i == 5
        rows.append(f'<div class="ln" style="{"background:" + cur if hl else ""}">'
                    f'<span class="n" style="color:{acc if hl else ln}">{i}</span>'
                    f'<span class="c">{line or " "}</span></div>')
    return (f'<div class="card" style="background:{bg};color:{fg}"><div class="bar">'
            f'<span class="dots"><i></i><i></i><i></i></span>'
            f'<span class="label" style="color:{acc};border-color:{acc}55">{html.escape(label)}</span></div>'
            f'<div class="code">{"".join(rows)}</div></div>')


def main():
    for tool in ("ksyntaxhighlighter6", "firefox", "magick"):
        if not shutil.which(tool):
            sys.exit(f"missing tool: {tool}")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "sample.rs").write_text(SAMPLE)
        profile = work / "profile"
        profile.mkdir()
        built = {name: [(label, T.build_theme(f"{name}-{i}", ui, inten))
                        for i, (label, ui, inten) in enumerate(entries)]
                 for name, entries in GALLERIES.items()}
        built["popular"] = POPULAR
        for name, entries in built.items():
            cards = []
            for i, (label, th) in enumerate(entries):
                th = dict(th, metadata=dict(th["metadata"], name=f"{name}-{i}"))
                cards.append(card(work, f"{name}-{i}", label, th))
            page = work / f"{name}.html"
            page.write_text(f"<html><head><meta charset=utf-8><style>{CSS}</style></head>"
                            f"<body><div class=wrap>{''.join(cards)}</div></body></html>")
            raw = work / f"{name}-raw.png"
            rows = (len(entries) + 2) // 3
            subprocess.run(["firefox", "--headless", "--no-remote", "--profile", str(profile),
                            "--window-size", f"3640,{rows * 900 + 100}", "--screenshot", str(raw),
                            page.as_uri()], check=True, capture_output=True, timeout=120)
            dest = ROOT / "assets" / f"{name}.png"
            subprocess.run(["magick", str(raw), "-bordercolor", "#0d1117", "-border", "1", "-fuzz", "2%",
                            "-trim", "+repage", "-bordercolor", "#0d1117", "-border", "40",
                            "-resize", "1800x", "-strip", str(dest)], check=True)
            print(f"wrote {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
