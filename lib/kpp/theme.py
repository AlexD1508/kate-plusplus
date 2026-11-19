"""Kate++ theme engine.

Builds KSyntaxHighlighting themes with *harmonised* syntax colours: every
token family keeps its familiar hue (strings green, numbers orange, functions
blue, ...), nudged a little toward the accent, at matched lightness and soft
chroma in OKLCH. Calm to look at, yet every token class stays easy to tell
apart. Keywords use the accent itself; other hues keep their distance from it.
Every foreground is checked against the background and lifted until it meets
a contrast floor, so no user tweak can make code hard to read.

Colour sources: Caelestia (wallpaper scheme), KDE Plasma (kdeglobals), or
the built-in Kate++ Dark / Light palettes. User overrides sit on top.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

# ----------------------------------------------------------------- colour maths


def _to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _from_lin(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def norm(h: str) -> str:
    h = h.strip().lstrip("#").lower()
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) not in (6, 8) or any(ch not in "0123456789abcdef" for ch in h):
        raise ValueError(f"not a hex colour: {h!r}")
    return h[:6]


def hex_to_oklch(h):
    r, g, b = (_to_lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b2 = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return L, math.hypot(a, b2), math.degrees(math.atan2(b2, a)) % 360


def _oklch_to_lin(L, C, H):
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
            -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
            -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)


def oklch_to_hex(L, C, H):
    while C > 0 and not all(-1e-4 <= v <= 1 + 1e-4 for v in _oklch_to_lin(L, C, H)):
        C -= 0.002  # pull into sRGB gamut
    rgb = _oklch_to_lin(L, max(C, 0), H)
    return "".join(f"{round(min(1, max(0, _from_lin(v))) * 255):02x}" for v in rgb)


def luminance(h):
    r, g, b = (_to_lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def is_dark(bg):
    return luminance(bg) < 0.2


def ensure_contrast(fg, bg, minimum):
    L, C, H = hex_to_oklch(fg)
    lighten = is_dark(bg)
    for _ in range(80):
        if contrast(fg, bg) >= minimum:
            break
        L = min(0.99, L + 0.01) if lighten else max(0.02, L - 0.01)
        fg = oklch_to_hex(L, C, H)
    return fg


def mix(a, b, t):
    return "".join(f"{round(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t):02x}"
                   for i in (0, 2, 4))


def hue_distance(a, b):
    return abs(((a - b + 180) % 360) - 180)


def harmonise(base_hue, accent_hue, amount=0.18, cap=22):
    """Nudge a token hue a little toward the accent so the palette feels related."""
    diff = ((accent_hue - base_hue + 180) % 360) - 180
    return (base_hue + max(-cap, min(cap, diff * amount))) % 360


def assign_hues(accent_hue, keep_away=40):
    """Harmonised hue per token family. Keywords use the accent, so any family that
    would land near it moves to the most open spot on the wheel: as far as possible
    from the accent *and* every other family, preferring spots near its usual hue."""
    hues = {k: harmonise(h, accent_hue) for k, h in HUES.items()}
    clash = sorted((k for k, h in hues.items() if hue_distance(h, accent_hue) < keep_away),
                   key=lambda k: hue_distance(hues[k], accent_hue))
    placed = {k: h for k, h in hues.items() if k not in clash}
    for k in clash:
        taken = [accent_hue, *placed.values()]
        placed[k] = max(range(0, 360, 2), key=lambda h: (
            round(min(hue_distance(h, t) for t in taken) / 6),  # openness, in 6° steps
            -hue_distance(h, HUES[k])))                          # then: close to its usual hue
    return placed


# ----------------------------------------------------------------- palettes

HUES = {"green": 145, "teal": 190, "blue": 252, "purple": 305,
        "gold": 88, "orange": 55, "red": 22}

INTENSITY = {"soft": 0.55, "balanced": 1.0, "vivid": 1.6}

STATIC = {
    "dark": {"bg": "1b1c22", "fg": "e3e3ea", "accent": "c3a6ff", "error": "ff8f8f"},
    "light": {"bg": "fbfaff", "fg": "1d1d24", "accent": "6a3fd6", "error": "b3261e"},
}


def derive_ui(bg, fg, accent, error, fg_muted=None):
    """Full set of editor surface roles from four base colours."""
    dark = is_dark(bg)
    return {
        "bg": bg, "fg": fg, "accent": accent, "error": error,
        "fg_muted": fg_muted or mix(fg, bg, 0.22),
        "comment": mix(fg, bg, 0.45),
        "selection": mix(bg, accent, 0.32 if dark else 0.24),
        "on_selection": fg,
        "current_line": mix(bg, fg, 0.035),
        "raised": mix(bg, fg, 0.08),
        "raised2": mix(bg, fg, 0.14),
        "line_numbers": mix(bg, fg, 0.33),
        "error_bg": mix(bg, error, 0.28),
        "on_error_bg": fg,
    }


def caelestia_ui(c):
    c = {k: norm(v) for k, v in c.items() if isinstance(v, str)}
    return {
        "bg": c["surface"], "fg": c["onSurface"], "fg_muted": c["onSurfaceVariant"],
        "accent": c["primary"], "comment": c["outline"],
        "selection": c["primaryContainer"], "on_selection": c["onPrimaryContainer"],
        "current_line": c["surfaceContainerLow"], "raised": c["surfaceContainerHigh"],
        "raised2": c["surfaceContainerHighest"],
        "line_numbers": mix(c["surface"], c["outline"], 0.55),
        "error": c["error"], "error_bg": c["errorContainer"], "on_error_bg": c["onErrorContainer"],
    }


def _kde_rgb(value):
    parts = [int(p) for p in value.split(",")[:3]]
    return "".join(f"{p:02x}" for p in parts)


def read_kdeglobals(path: Path):
    groups, group = {}, None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            group = groups.setdefault(line, {})
        elif "=" in line and group is not None:
            k, v = line.split("=", 1)
            group[k.strip()] = v.strip()
    return groups


def plasma_ui(path: Path):
    g = read_kdeglobals(path)
    view = g.get("[Colors:View]", {})
    sel = g.get("[Colors:Selection]", {})
    general = g.get("[General]", {})
    try:
        bg = _kde_rgb(view["BackgroundNormal"])
        fg = _kde_rgb(view["ForegroundNormal"])
    except (KeyError, ValueError):
        return None
    accent_raw = general.get("AccentColor") or sel.get("BackgroundNormal") or "61,174,233"
    error = _kde_rgb(view.get("ForegroundNegative", "218,68,83"))
    muted = _kde_rgb(view["ForegroundInactive"]) if "ForegroundInactive" in view else None
    return derive_ui(bg, fg, _kde_rgb(accent_raw), error, muted)


def static_ui(variant):
    s = STATIC[variant]
    return derive_ui(s["bg"], s["fg"], s["accent"], s["error"])


def apply_overrides(ui, accent=None, background=None):
    if not (accent or background):
        return ui
    bg = norm(background) if background else ui["bg"]
    acc = norm(accent) if accent else ui["accent"]
    fg = ui["fg"]
    if background and contrast(fg, bg) < 7:  # pick a readable text colour for a custom bg
        fg = "ececf1" if is_dark(bg) else "1d1d24"
    if background:
        return derive_ui(bg, fg, acc, ui["error"])
    out = dict(ui, accent=acc)
    out["selection"] = mix(bg, acc, 0.32 if is_dark(bg) else 0.24)
    out["on_selection"] = fg
    return out


# ----------------------------------------------------------------- theme build

def build_theme(name, ui, intensity="balanced"):
    """The harmonised Kate++ theme for a set of surface colours."""
    dark = is_dark(ui["bg"])
    _, _, acc_h = hex_to_oklch(ui["accent"])
    L, C = (0.81, 0.085) if dark else (0.50, 0.12)
    C *= INTENSITY.get(intensity, 1.0)
    p = {k: oklch_to_hex(L, C, h) for k, h in assign_hues(acc_h).items()}
    tokens = {
        "keyword": ui["accent"], "function": p["blue"], "builtin": p["purple"],
        "preproc": p["red"], "type": p["gold"], "string": p["green"], "special": p["teal"],
        "number": p["orange"], "comment": ui["comment"],
    }
    return assemble(name, ui, tokens, token_floor=6.0, comment_floor=4.6)


def assemble(name, ui, tokens, token_floor=4.5, comment_floor=4.5, keyword_style=None,
             copyright=None, license="MIT"):
    """Turn surface roles (`ui`) and token colours into a KSyntaxHighlighting theme.

    tokens needs: keyword, function, builtin, preproc, type, string, special, number, comment.
    Optional: control, import, attribute, constant, operator, others, annotation, variable.
    Every foreground is lifted to its contrast floor against the background."""
    bg = ui["bg"]
    lift = lambda c, f=token_floor: ensure_contrast(norm(c), bg, f)  # noqa: E731
    t = {k: lift(v) for k, v in tokens.items() if k != "comment"}
    t["comment"] = lift(tokens["comment"], comment_floor)
    for key, fallback in (("control", "keyword"), ("import", "builtin"), ("attribute", "type"),
                          ("constant", "number"), ("others", "builtin"), ("annotation", "special")):
        t.setdefault(key, t[fallback])
    fg = ensure_contrast(ui["fg"], bg, 10.0)
    muted = ensure_contrast(ui["fg_muted"], bg, 7.0)
    t.setdefault("operator", muted)
    t.setdefault("variable", fg)
    sel_fg = ensure_contrast(ui["on_selection"], ui["selection"], 7.0)
    line_numbers = ensure_contrast(ui["line_numbers"], bg, 2.6)
    kw = keyword_style if keyword_style is not None else {"bold": True}

    def s(color, **kw_):
        d = {"text-color": "#" + color, "selected-text-color": "#" + sel_fg}
        for k, v in kw_.items():
            d[k.replace("_", "-")] = ("#" + v) if k.endswith("color") else v
        return d

    styles = {
        "Normal": s(fg), "Variable": s(t["variable"]), "Operator": s(t["operator"]),
        "Keyword": s(t["keyword"], **kw), "ControlFlow": s(t["control"], **kw),
        "Function": s(t["function"]), "Extension": s(t["function"], bold=True),
        "BuiltIn": s(t["builtin"]), "Import": s(t["import"]), "Others": s(t["others"]),
        "Preprocessor": s(t["preproc"]),
        "Attribute": s(t["attribute"]), "DataType": s(t["type"]),
        "String": s(t["string"]), "VerbatimString": s(t["string"]), "Char": s(t["string"]),
        "SpecialString": s(t["special"]), "SpecialChar": s(t["special"]),
        "Annotation": s(t["annotation"]),
        "DecVal": s(t["number"]), "BaseN": s(t["number"]), "Float": s(t["number"]),
        "Constant": s(t["constant"], bold=True),
        "Comment": s(t["comment"], italic=True), "Documentation": s(t["comment"], italic=True),
        "CommentVar": s(t["builtin"], italic=True),
        "RegionMarker": s(ensure_contrast(t["special"], ui["raised"], token_floor),
                          background_color=ui["raised"]),
        "Information": s(t["string"]), "Warning": s(t["number"], bold=True),
        "Alert": s(ensure_contrast(ui["on_error_bg"], ui["error_bg"], 6.0),
                   background_color=ui["error_bg"], bold=True),
        "Error": s(ensure_contrast(ui["error"], bg, 4.6), underline=True),
    }
    e = lambda c: "#" + c  # noqa: E731
    editor = {
        "BackgroundColor": e(bg), "TextSelection": e(ui["selection"]),
        "CurrentLine": e(ui["current_line"]),
        "SearchHighlight": e(mix(bg, t["type"], 0.30)),
        "ReplaceHighlight": e(mix(bg, t["string"], 0.30)),
        "BracketMatching": e(ui["raised2"]), "IconBorder": e(bg),
        "LineNumbers": e(line_numbers), "CurrentLineNumber": e(t["keyword"]),
        "Separator": e(ui["raised"]), "CodeFolding": e(ui["current_line"]),
        "IndentationLine": e(ui["raised"]), "WordWrapMarker": e(ui["raised"]),
        "TabMarker": e(ui["raised2"]),
        "ModifiedLines": e(t["type"]), "SavedLines": e(t["string"]),
        "SpellChecking": e(ui["error"]),
        "MarkBookmark": e(t["keyword"]), "MarkBreakpointActive": e(ui["error"]),
        "MarkBreakpointReached": e(t["type"]), "MarkBreakpointDisabled": e(line_numbers),
        "MarkExecution": e(t["function"]), "MarkWarning": e(t["number"]), "MarkError": e(ui["error"]),
        "TemplateBackground": e(ui["current_line"]), "TemplatePlaceholder": e(ui["raised2"]),
        "TemplateFocusedPlaceholder": e(ui["selection"]),
        "TemplateReadOnlyPlaceholder": e(ui["raised"]),
    }
    return {
        "metadata": {"name": name, "revision": 1, "license": license,
                     "copyright": copyright or ["kate-plusplus contributors"], "read-only": False},
        "text-styles": styles,
        "editor-colors": editor,
    }


def write_theme(path: Path, theme):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_text(json.dumps(theme, indent=4) + "\n", encoding="utf-8")
    os.replace(tmp, path)
