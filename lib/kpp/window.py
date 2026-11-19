"""Matching window colours: a KDE colour scheme derived from the active editor theme.

Kate applies `[UiSettings] ColorScheme=<id>` from `~/.local/share/color-schemes/<id>.colors`
to its whole window (menus, tabs, sidebars, status bar). Kate++ writes one scheme for the
active theme so picking e.g. Rosé Pine colours the window too.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from . import core
from .theme import contrast, ensure_contrast, is_dark, mix

PREFIX = "KatePlusPlus"


def scheme_id(theme_name: str) -> str:
    """'Rosé Pine' → KatePlusPlusRosePine, 'Kate++ Dark' → KatePlusPlusDark."""
    name = theme_name.replace("Kate++", "").replace("é", "e").replace("+", "Plus")
    return PREFIX + re.sub(r"[^A-Za-z0-9]", "", name)


def roles_from_theme(t: dict) -> dict:
    """The colours a window scheme needs, taken from a KSyntaxHighlighting theme dict."""
    ec, ts = t["editor-colors"], t["text-styles"]
    c = lambda k: ec[k].lstrip("#")[:6]                      # noqa: E731
    s = lambda k: ts[k]["text-color"].lstrip("#")[:6]        # noqa: E731
    return {"bg": c("BackgroundColor"), "fg": s("Normal"), "current_line": c("CurrentLine"),
            "selection": c("TextSelection"), "muted": s("Comment"), "accent": s("Keyword"),
            "link": s("Function"), "visited": s("BuiltIn"), "positive": s("String"),
            "neutral": s("DecVal"), "negative": s("Error")}


def roles_from_kate_theme(name: str) -> dict | None:
    """Colours of a theme bundled with Kate, read by highlighting a tiny sample with it."""
    sample = 'int main() {\n  return 42; // c\n  auto s = "s";\n  foo();\n}\n'
    for tool in ("ksyntaxhighlighter6", "kate-syntax-highlighter"):
        if not core.have(tool):
            continue
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "s.cpp"
            src.write_text(sample, encoding="utf-8")
            r = subprocess.run([tool, "-t", name, "-s", "C++", "-f", "html", str(src)],
                               capture_output=True, text=True)
        if r.returncode != 0 or "<body" not in r.stdout:
            return None
        html = r.stdout
        body = re.search(r'<body style="background-color:#([0-9a-fA-F]{6});color:#([0-9a-fA-F]{6})', html)
        if not body:
            return None
        bg, fg = body.group(1).lower(), body.group(2).lower()

        def color_of(text, fallback):
            m = re.search(r'<span style="color:#([0-9a-fA-F]{6})[^"]*">' + re.escape(text), html)
            return m.group(1).lower() if m else fallback

        accent = color_of("return", color_of("int", fg))
        return {"bg": bg, "fg": fg, "current_line": mix(bg, fg, 0.05),
                "selection": mix(bg, accent, 0.35), "muted": color_of("// c", mix(fg, bg, 0.45)),
                "accent": accent, "link": color_of("foo", accent), "visited": color_of("auto", accent),
                "positive": color_of('"s"', accent), "neutral": color_of("42", accent),
                "negative": "e06c75" if is_dark(bg) else "c62828"}
    return None


def _rgb(h: str) -> str:
    return ",".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def scheme_text(display_name: str, sid: str, r: dict) -> str:
    bg, fg = r["bg"], r["fg"]
    dark = is_dark(bg)
    window = r["current_line"] if contrast(r["current_line"], bg) < 1.6 else mix(bg, fg, 0.04)
    button = mix(window, fg, 0.08)
    tooltip = mix(bg, fg, 0.10)
    sel_bg = ensure_contrast(r["accent"], bg, 3.0)
    sel_fg = bg if contrast(bg, sel_bg) >= contrast(fg, sel_bg) else fg
    inactive = ensure_contrast(r["muted"], window, 3.0)

    def group(back, back_alt, fore=fg, inact=inactive):
        vals = {
            "BackgroundNormal": back, "BackgroundAlternate": back_alt,
            "ForegroundNormal": fore, "ForegroundInactive": inact,
            "ForegroundActive": ensure_contrast(r["accent"], back, 3.0),
            "ForegroundLink": ensure_contrast(r["link"], back, 3.0),
            "ForegroundVisited": ensure_contrast(r["visited"], back, 3.0),
            "ForegroundNegative": ensure_contrast(r["negative"], back, 3.0),
            "ForegroundNeutral": ensure_contrast(r["neutral"], back, 3.0),
            "ForegroundPositive": ensure_contrast(r["positive"], back, 3.0),
            "DecorationFocus": r["accent"], "DecorationHover": mix(r["accent"], back, 0.4),
        }
        return "\n".join(f"{k}={_rgb(v)}" for k, v in sorted(vals.items()))

    sections = {
        "Colors:View": group(bg, r["current_line"]),
        "Colors:Window": group(window, mix(window, fg, 0.03)),
        "Colors:Button": group(button, mix(button, fg, 0.04)),
        "Colors:Selection": group(sel_bg, mix(sel_bg, bg, 0.2), sel_fg, mix(sel_fg, sel_bg, 0.3)),
        "Colors:Tooltip": group(tooltip, mix(tooltip, fg, 0.04)),
        "Colors:Complementary": group(mix(bg, "000000" if dark else "ffffff", 0.3), window),
        "Colors:Header": group(window, mix(window, fg, 0.03)),
        "Colors:Header][Inactive": group(window, mix(window, fg, 0.03)),
    }
    out = [f"# Generated by Kate++ to match the '{display_name}' editor theme.", ""]
    for name, body in sections.items():
        out += [f"[{name}]", body, ""]
    out += ["[General]", f"ColorScheme={sid}", f"Name=Kate++ {display_name}", "shadeSortColumn=true", "",
            "[KDE]", "contrast=4", "",
            "[WM]", f"activeBackground={_rgb(window)}", f"activeForeground={_rgb(fg)}",
            f"inactiveBackground={_rgb(window)}", f"inactiveForeground={_rgb(inactive)}", ""]
    return "\n".join(out)


def schemes_dir(kate) -> Path:
    return kate.data / "color-schemes"   # native: ~/.local/share, Flatpak: the app's data dir


def write_scheme(kate, display_name: str, roles: dict) -> str:
    sid = scheme_id(display_name)
    # write the new scheme first: if that fails, the one katerc points at is still there
    core.atomic_write(schemes_dir(kate) / f"{sid}.colors", scheme_text(display_name, sid, roles), 0o644)
    for old in schemes_dir(kate).glob(f"{PREFIX}*.colors"):   # then keep only the active one
        if old.stem != sid:
            old.unlink()
    return sid


def remove_schemes(kate):
    for f in schemes_dir(kate).glob(f"{PREFIX}*.colors"):
        f.unlink()
