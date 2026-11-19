"""Interactive theme picker: browse every theme with a live, real-colour code preview.

`kate-plusplus theme --pick`. Arrow keys / j k browse, Enter applies, q / Esc cancels.
Pure stdlib (termios/tty); falls back to a numbered list when there's no terminal.
"""
from __future__ import annotations

import os
import select
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import core, ports

# A short Python sample, pre-split into (text, KSyntaxHighlighting style) segments so the
# preview needs no highlighter for Kate++'s own themes.
SAMPLE = [
    [("import", "Import"), (" json", "Normal")],
    [],
    [("# Count words in every note  ", "Comment"), ("TODO", "Alert"), (": cache", "Comment")],
    [("@dataclass", "Attribute")],
    [("class", "Keyword"), (" Note:", "Normal")],
    [("    words: ", "Normal"), ("int", "DataType"), (" = ", "Operator"), ("0", "DecVal")],
    [],
    [("def", "Keyword"), (" ", "Normal"), ("load", "Function"), ("(path: ", "Normal"),
     ("str", "DataType"), (") -> ", "Operator"), ("list", "BuiltIn"), (":", "Normal")],
    [("    for", "ControlFlow"), (" name ", "Normal"), ("in", "ControlFlow"), (" ", "Normal"),
     ("sorted", "BuiltIn"), ("(path):", "Normal")],
    [("        if", "ControlFlow"), (" name.endswith(", "Normal"), ('".md"', "String"), ("):", "Normal")],
    [("            return", "ControlFlow"), (" ", "Normal"), ("3.14", "Float"),
     (" * ", "Operator"), ("0x40", "BaseN"), ("  ", "Normal"), ("# ok", "Comment")],
]
SAMPLE_TEXT = "\n".join("".join(t for t, _ in line) for line in SAMPLE) + "\n"
WIDTH = 64


@dataclass
class Entry:
    label: str        # shown in the list
    source: str       # value written to [theme] source
    group: str        # "Kate++", "Popular", "Kate"
    note: str = ""


def entries(builtin_names) -> list[Entry]:
    out = [
        Entry("Auto", "auto", "Kate++", "follows Caelestia / Plasma, else Dark or Light"),
        Entry("Kate++ Dark", "dark", "Kate++", "harmonised, readable"),
        Entry("Kate++ Light", "light", "Kate++", "harmonised, readable"),
    ]
    if core.CAELESTIA_SCHEME.is_file():
        out.insert(1, Entry("Kate++ Caelestia", "caelestia", "Kate++", "your wallpaper colours"))
    for slug, (name, *_rest) in ports.PORTS.items():
        out.append(Entry(name, slug if slug != "rose-pine" else "rose-pine-main", "Popular",
                         f"by {ports.designer(slug)}"))
    for name in builtin_names:
        out.append(Entry(name, name, "Kate", "ships with Kate"))
    return out


# ----------------------------------------------------------------- colours

def _fg(h):
    h = h.lstrip("#")
    return f"\033[38;2;{int(h[0:2], 16)};{int(h[2:4], 16)};{int(h[4:6], 16)}m"


def _bg(h):
    h = h.lstrip("#")
    return f"\033[48;2;{int(h[0:2], 16)};{int(h[2:4], 16)};{int(h[4:6], 16)}m"


def theme_dict(entry: Entry, cfg=None):
    """Theme dict exactly as `apply` would build it (adaptive themes honour config overrides),
    or None for Kate's own themes."""
    from . import cli   # cli is fully loaded by the time the picker runs
    if entry.group == "Popular":
        slug = "rose-pine" if entry.source == "rose-pine-main" else entry.source
        return ports.build(slug)
    if entry.group != "Kate++":
        return None
    cfg = cfg or core.load_config()
    cfg = _with_source(cfg, entry.source)
    resolved = cli.resolve_theme_source(cfg, cli.resolve_profile(cfg))
    if resolved is None or ":" in resolved:
        return None
    accent, background, intensity = cli.theme_options(cfg, quiet=True)
    return cli.adaptive_theme(resolved, accent, background, intensity)


def _with_source(cfg, source):
    import configparser
    p = configparser.ConfigParser(interpolation=None)
    p.read_dict({s: dict(cfg.parser[s]) for s in cfg.parser.sections()})
    if not p.has_section("theme"):
        p.add_section("theme")
    p.set("theme", "source", source)
    return core.Config(p)


def render(t: dict, width: int = WIDTH) -> list[str]:
    """The sample in a theme's real colours, one ANSI string per line, padded to `width`."""
    bg = t["editor-colors"]["BackgroundColor"]
    styles = t["text-styles"]
    lines = []
    for segs in SAMPLE:
        out, used = [_bg(bg)], 0
        for text, style in segs:
            s = styles.get(style, styles["Normal"])
            seg_bg = _bg(s["background-color"]) if "background-color" in s else ""
            attrs = ("\033[1m" if s.get("bold") else "") + ("\033[3m" if s.get("italic") else "")
            out.append(f"{seg_bg}{attrs}{_fg(s['text-color'])}{text}\033[22;23m{_bg(bg)}")
            used += len(text)
        out.append(" " * max(0, width - used) + "\033[0m")
        lines.append(" " + "".join(out))
    return lines


def render_builtin(name: str, width: int = WIDTH) -> list[str] | None:
    """Kate's bundled themes via KSyntaxHighlighting's own ANSI output."""
    tool = next((t for t in ("ksyntaxhighlighter6", "kate-syntax-highlighter") if core.have(t)), None)
    if not tool:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "sample.py"
        f.write_text(SAMPLE_TEXT, encoding="utf-8")
        r = subprocess.run([tool, "-f", "ansi", "-t", name, "-s", "Python", str(f)],
                           capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout:
        return None
    out = []
    plain = SAMPLE_TEXT.splitlines()
    for i, line in enumerate(r.stdout.replace("\033[K", "").rstrip("\n").split("\n")[:len(SAMPLE)]):
        pad = " " * max(0, width - len(plain[i] if i < len(plain) else ""))
        out.append(" " + line + pad + "\033[0m")
    return out


def preview(entry: Entry) -> list[str]:
    t = theme_dict(entry)
    if t is not None:
        return render(t)
    lines = render_builtin(entry.label)
    return lines or [f" {core.DIM}(install ksyntaxhighlighter6 to preview Kate's own themes){core.RESET}"]


# ----------------------------------------------------------------- terminal UI

KEYS = {b"[A": "up", b"[B": "down", b"[5~": "pgup", b"[6~": "pgdn", b"[H": "home", b"[F": "end",
        b"OA": "up", b"OB": "down", b"OH": "home", b"OF": "end"}


def _read_key(fd, timeout=0.05):
    """One key press. Escape sequences may arrive in several short reads, so bytes are
    collected until the sequence is complete or nothing more arrives within `timeout`."""
    ch = os.read(fd, 1)
    if ch != b"\x1b":
        return ch.decode(errors="ignore")
    seq = b""
    while True:
        if not select.select([fd], [], [], timeout)[0]:
            return "esc" if not seq else KEYS.get(seq, "")   # lone ESC = cancel
        seq += os.read(fd, 1)
        if seq in KEYS:
            return KEYS[seq]
        if len(seq) >= 4 or (len(seq) >= 2 and seq[-1:].isalpha() or seq.endswith(b"~")):
            return KEYS.get(seq, "")


def _layout(height):
    """(list rows, preview lines) that fit a terminal `height` lines tall."""
    header, gaps = 3, 3
    preview_lines = len(SAMPLE)
    rows = height - header - gaps - preview_lines
    if rows < 5:                                   # small terminal: shorten the preview first
        preview_lines = max(3, height - header - gaps - 5)
        rows = max(3, height - header - gaps - preview_lines)
    return rows, preview_lines


def _screen(items, sel, current_source, rows, preview_lines=None):
    A, D, B, R = core.ACCENT, core.DIM, core.BOLD, core.RESET
    out = ["\033[H\033[2J", f"\n  {A}{B}Kate++{R}  {D}Pick a theme · ↑↓ / j k browse · Enter apply · q cancel{R}\n"]
    top = max(0, min(sel - rows // 2, len(items) - rows))
    for i in range(top, min(len(items), top + rows)):
        e = items[i]
        mark = f"{A}›{R}" if i == sel else " "
        cur = f" {D}(current){R}" if _same(e.source, current_source) else ""
        label = f"{B}{e.label}{R}" if i == sel else e.label
        out.append(f"  {mark} {D}{e.group:<8}{R} {label}{cur}  {D}{e.note}{R}")
    out.append("")
    out += preview(items[sel])[:preview_lines or len(SAMPLE)]
    return "\n".join(out)


def _same(a, b):
    from .cli import _key  # local import: cli imports this module
    return bool(b) and _key(a) == _key(b)


def pick_interactive(items, current_source):
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    import shutil
    sel = next((i for i, e in enumerate(items) if _same(e.source, current_source)), 0)
    sys.stdout.write("\033[?1049h\033[?25l")
    try:
        tty.setcbreak(fd)
        while True:
            rows, preview_lines = _layout(shutil.get_terminal_size((80, 24)).lines)
            sys.stdout.write(_screen(items, sel, current_source, rows, preview_lines))
            sys.stdout.flush()
            k = _read_key(fd)
            if k in ("up", "k"):
                sel = (sel - 1) % len(items)
            elif k in ("down", "j"):
                sel = (sel + 1) % len(items)
            elif k == "pgup":
                sel = max(0, sel - rows)
            elif k == "pgdn":
                sel = min(len(items) - 1, sel + rows)
            elif k in ("home", "g"):
                sel = 0
            elif k in ("end", "G"):
                sel = len(items) - 1
            elif k in ("\n", "\r"):
                return items[sel]
            elif k in ("q", "esc", "\x03"):
                return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\033[?25h\033[?1049l")
        sys.stdout.flush()


def pick_list(items, current_source):
    for i, e in enumerate(items, 1):
        cur = " (current)" if _same(e.source, current_source) else ""
        core.info(f"{core.ACCENT}{i:>2}{core.RESET}  {e.label}{cur}  {core.DIM}{e.group} · {e.note}{core.RESET}")
    if sys.stdin.isatty():
        choice = core.prompt("\n  Which theme? (number, Enter = cancel)")
    else:                                   # piped / scripted: read the number from stdin
        choice = (sys.stdin.readline() or "").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(items):
        return items[int(choice) - 1]
    return None


def pick(items, current_source):
    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            return pick_interactive(items, current_source)
        except KeyboardInterrupt:
            return None
    return pick_list(items, current_source)
