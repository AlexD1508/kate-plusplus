"""Shared plumbing: output, paths, environment detection, user config, safe file edits."""
from __future__ import annotations

import configparser
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

VERSION = "1.1.0"
APP = "kate-plusplus"
REPO = Path(__file__).resolve().parents[2]
HOME = Path.home()

XDG_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config")
XDG_DATA = Path(os.environ.get("XDG_DATA_HOME") or HOME / ".local/share")
XDG_STATE = Path(os.environ.get("XDG_STATE_HOME") or HOME / ".local/state")

KPP_CONFIG_DIR = XDG_CONFIG / APP
USER_CONFIG = KPP_CONFIG_DIR / "config.ini"
STATE_DIR = XDG_STATE / APP
STATE_FILE = STATE_DIR / "state.json"
BACKUP_DIR = XDG_DATA / APP / "backups"
BIN_LINK = HOME / ".local/bin" / APP

CAELESTIA_SCHEME = XDG_STATE / "caelestia/scheme.json"
KDEGLOBALS = XDG_CONFIG / "kdeglobals"

# ----------------------------------------------------------------- output

_TTY = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
QUIET = False


def _c(code):
    return f"\033[{code}m" if _TTY else ""


BOLD, DIM, RESET = _c("1"), _c("2"), _c("0")
ACCENT, GREEN, YELLOW, RED = _c("38;5;141"), _c("38;5;114"), _c("38;5;179"), _c("38;5;203")


def banner(subtitle=""):
    if QUIET:
        return
    print(f"\n  {ACCENT}{BOLD}Kate++{RESET}  {DIM}Notepad++ comfort for Kate · v{VERSION}{RESET}")
    if subtitle:
        print(f"  {DIM}{subtitle}{RESET}")
    print()


def section(title):
    if not QUIET:
        print(f"\n  {BOLD}{title}{RESET}")


def step(msg):
    if not QUIET:
        print(f"  {GREEN}✓{RESET} {msg}")


def info(msg):
    if not QUIET:
        print(f"  {DIM}·{RESET} {msg}")


def warn(msg):
    sys.stdout.flush()
    print(f"  {YELLOW}!{RESET} {msg}", file=sys.stderr)


def fail(msg, code=1):
    print(f"\n  {RED}✗{RESET} {msg}\n", file=sys.stderr)
    sys.exit(code)


def ask(question, default=True):
    """Yes/no question; works even when the script itself is piped (curl | bash)."""
    hint = "Y/n" if default else "y/N"
    try:
        with open("/dev/tty") as tty:
            sys.stdout.write(f"  {ACCENT}?{RESET} {question} {DIM}[{hint}]{RESET} ")
            sys.stdout.flush()
            answer = tty.readline().strip().lower()
    except OSError:
        return default
    return default if not answer else answer.startswith("y")


def prompt(question, default=""):
    try:
        with open("/dev/tty") as tty:
            sys.stdout.write(f"  {ACCENT}?{RESET} {question} ")
            sys.stdout.flush()
            return tty.readline().strip() or default
    except OSError:
        return default


# ----------------------------------------------------------------- shell helpers

def have(cmd):
    return shutil.which(cmd) is not None


# KPP_TEST=1: never touch the real systemd user manager or compositor (used by the test-suite).
_SANDBOXED = {"systemctl", "hyprctl"} if os.environ.get("KPP_TEST") else set()


def run(*cmd, check=False, quiet=True):
    if cmd and cmd[0] in _SANDBOXED:
        return subprocess.CompletedProcess(cmd, 0, "", "")
    try:
        return subprocess.run(cmd, check=check, text=True,
                              stdout=subprocess.PIPE if quiet else None,
                              stderr=subprocess.PIPE if quiet else None)
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, 127, "", "")


_lock_depth = 0


@contextlib.contextmanager
def exclusive():
    """One Kate++ pass at a time across apply, theme, the background job and uninstall (waits).
    It locks the XDG state folder itself (~/.local/state), so there is no lock file to create
    or to clean up, and uninstall can't leave one behind. Re-entrant within one process."""
    global _lock_depth
    if _lock_depth:
        _lock_depth += 1
        try:
            yield
        finally:
            _lock_depth -= 1
        return
    import fcntl
    XDG_STATE.mkdir(parents=True, exist_ok=True)   # the standard XDG folder, never removed
    fd = os.open(XDG_STATE, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        _lock_depth = 1
        try:
            yield
        finally:
            _lock_depth = 0
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def missing_dirs(path: Path) -> list:
    """The folders above `path` that don't exist yet (deepest first): writing `path` creates them."""
    out = []
    d = Path(path).parent
    while not d.exists() and d != d.parent:
        out.append(str(d))
        d = d.parent
    return out


def remove_empty_dirs(dirs):
    """Remove folders Kate++ created, deepest first, but only while they are empty."""
    for d in dirs or ():
        try:
            Path(d).rmdir()
        except OSError:
            break   # not empty (or already gone): leave it and its parents alone


def atomic_write(path: Path, text: str, mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode is None:
        mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".kpp-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


# ----------------------------------------------------------------- environment

@dataclass
class Kate:
    kind: str                 # native | flatpak
    cmd: list[str]
    config: Path              # where katerc lives
    data: Path                # Kate's XDG data home
    version: str = ""

    @property
    def katerc(self):
        return self.config / "katerc"


def detect_kate() -> Kate | None:
    if have("kate"):
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        try:
            out = subprocess.run(["kate", "--version"], text=True, capture_output=True, env=env, timeout=15).stdout
        except (OSError, subprocess.TimeoutExpired):
            out = ""
        m = re.search(r"(\d+\.\d+\.\d+)", out)
        return Kate("native", ["kate"], XDG_CONFIG, XDG_DATA, m.group(1) if m else "")
    if have("flatpak") and run("flatpak", "info", "org.kde.kate").returncode == 0:
        base = HOME / ".var/app/org.kde.kate"
        out = run("flatpak", "info", "org.kde.kate").stdout or ""
        m = re.search(r"Version:\s*(\S+)", out)
        return Kate("flatpak", ["flatpak", "run", "org.kde.kate"], base / "config", base / "data",
                    m.group(1) if m else "")
    return None


def kate_running(kate: Kate) -> bool:
    if os.environ.get("KPP_TEST"):   # tests use a throw-away $HOME; a real running Kate is unrelated
        return False
    if kate.kind == "flatpak":
        return "org.kde.kate" in (run("flatpak", "ps", "--columns=application").stdout or "")
    return run("pgrep", "-x", "kate").returncode == 0


def wait_for_kate_closed(kate: Kate, why="change Kate's settings"):
    if os.environ.get("KPP_TEST") or not kate_running(kate):
        return
    warn(f"Kate is open. Please close it so Kate++ can {why}.")
    info("Your open tabs are safe: they'll be right there when you reopen it.")
    if not os.isatty(0) and not Path("/dev/tty").exists():
        fail("Close Kate and run the command again.")
    import time
    shown = False
    try:
        while kate_running(kate):
            if not shown:
                info(f"{DIM}Waiting for Kate to close… (Ctrl+C to cancel){RESET}")
                shown = True
            time.sleep(0.7)
    except KeyboardInterrupt:
        fail("Cancelled. Nothing was changed.", 130)
    step("Kate closed")


def is_caelestia() -> bool:
    return have("caelestia") and CAELESTIA_SCHEME.is_file()


def hyprland_style() -> str | None:
    """lua | conf | None — how Caelestia's Hyprland user config is loaded."""
    if (XDG_CONFIG / "hypr/hyprland.lua").is_file():
        return "lua"
    if (XDG_CONFIG / "hypr/hyprland.conf").is_file():
        return "conf"
    return None


def is_plasma() -> bool:
    desk = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    return "kde" in desk or "plasma" in desk


def has_systemd_user() -> bool:
    if os.environ.get("KPP_TEST"):
        return True
    return have("systemctl") and run("systemctl", "--user", "show-environment").returncode == 0


def system_prefers_dark() -> bool:
    r = run("gsettings", "get", "org.gnome.desktop.interface", "color-scheme")
    if r.returncode == 0 and r.stdout:
        if "dark" in r.stdout:
            return True
        if "light" in r.stdout:
            return False
    if KDEGLOBALS.is_file():
        from .theme import read_kdeglobals, _kde_rgb, is_dark
        view = read_kdeglobals(KDEGLOBALS).get("[Colors:View]", {})
        if "BackgroundNormal" in view:
            return is_dark(_kde_rgb(view["BackgroundNormal"]))
    return True


def installed_font(*families):
    if not have("fc-list"):
        return None
    out = (run("fc-list", ":", "family").stdout or "").lower()
    names = {n.strip() for line in out.splitlines() for n in line.split(",")}
    for fam in families:
        if fam.lower() in names:
            return fam
    return None


# ----------------------------------------------------------------- user config

DEFAULTS = {
    "general": {"profile": "auto"},
    "features": {"notepad-overlay": "false", "notepad-hotkey": "SUPER + J",
                 "default-editor": "true", "backups": "true", "language-menu": "true", "backup-keep-days": "2"},
    "theme": {"source": "auto", "accent": "", "background": "", "syntax-colors": "balanced",
              "window-colors": "match"},
    "editor": {"font": "auto", "font-size": "11", "line-spacing": "1.15", "minimap": "true",
               "ligatures": "true", "smart-highlighting": "true", "auto-save": "off",
               "breadcrumbs": "true", "format-on-save": "false"},
}


_INLINE_COMMENT = re.compile(r"\s+#\s.*$|\s+#$")


def strip_comment(value: str) -> str:
    """'#7aa2f7' is a colour, '  # note' is a comment."""
    return _INLINE_COMMENT.sub("", value).strip()


@dataclass
class Config:
    parser: configparser.ConfigParser = field(default_factory=configparser.ConfigParser)

    def get(self, section, key):
        return strip_comment(self.parser.get(section, key, fallback=DEFAULTS[section][key]))

    def flag(self, section, key):
        return self.get(section, key).lower() in ("1", "true", "yes", "on")

    def strict_flag(self, section, key):
        """Like flag(), but a value that is neither true nor false (e.g. a typo such as
        'tru') warns and falls back to the default instead of silently meaning false."""
        value = self.get(section, key).lower()
        if value in ("1", "true", "yes", "on"):
            return True
        if value in ("0", "false", "no", "off"):
            return False
        default = DEFAULTS[section][key]
        warn(f"[{section}] {key} = {value!r} isn't true or false; using {default}")
        return default.lower() in ("1", "true", "yes", "on")


def load_config() -> Config:
    p = configparser.ConfigParser(interpolation=None)
    p.read_dict(DEFAULTS)
    if USER_CONFIG.is_file():
        p.read(USER_CONFIG, encoding="utf-8")
    return Config(p)


def ensure_user_config(overrides: dict[tuple[str, str], str] | None = None) -> bool:
    """Create config.ini from the template. Returns True if it was created."""
    created = not USER_CONFIG.is_file()
    if created:
        atomic_write(USER_CONFIG, (REPO / "config/config.ini").read_text(encoding="utf-8"), 0o644)
    if overrides:
        set_user_config(overrides)
    return created


_SECT = configparser.ConfigParser.SECTCRE   # same rules load_config() uses
_OPT = configparser.ConfigParser.OPTCRE


def _classify(lines):
    """[(kind, name)] per line, following ConfigParser's reading order: full-line comments,
    then continuation lines (indented deeper than the option they belong to, even across
    blank lines), then section headers (also `[editor] # notes`), then options (any
    capitalisation, `=` or `:`). kind is "section", "option" or None."""
    out, optname, indent = [], False, 0
    for line in lines:
        text = line.strip()
        if text[:1] in ("#", ";"):
            out.append((None, None))
            continue
        if not text:
            out.append((None, None))         # blank lines don't end a multi-line value
            continue
        cur = len(line) - len(line.lstrip())
        if optname and cur > indent:
            out.append((None, None))         # continuation of the previous option's value
            continue
        m = _SECT.match(text)
        if m:
            optname = False
            out.append(("section", m.group("header")))   # exactly as ConfigParser: "[ editor ]" ≠ "editor"
            continue
        m = _OPT.match(text)
        if m:
            optname, indent = True, cur
            out.append(("option", m.group("option").strip().lower()))
            continue
        optname = False
        out.append((None, None))
    return out


def _template_options(lines):
    """{section: [(key, block_lines)]}: each option with the comment lines just above it."""
    out, section, pending = {}, None, []
    for line, (kind, name) in zip(lines, _classify(lines)):
        if kind == "section":
            section, pending = name, []
            out.setdefault(section, [])
        elif line.strip().startswith("#"):
            pending.append(line)
        elif kind == "option" and section:
            out[section].append((name, pending + [line]))
            pending = []
        else:
            pending = []
    return out


def _parse(text):
    p = configparser.ConfigParser(interpolation=None)
    p.read_string(text)
    return p


def upgrade_user_config() -> list[str]:
    """Add options introduced by newer Kate++ versions to an existing config.ini, with their
    comments and default values. Existing values and the user's own edits are never touched.
    Sections and options are matched the way ConfigParser reads them, and the result is
    parsed before it is written: if it wouldn't load, or any existing value would change,
    the user's file is left exactly as it was. Returns the added keys."""
    if not USER_CONFIG.is_file():
        return []
    template = _template_options((REPO / "config/config.ini").read_text(encoding="utf-8").splitlines())
    try:
        original = USER_CONFIG.read_text(encoding="utf-8")
    except OSError as exc:
        warn(f"Couldn't read {USER_CONFIG} to add new options ({exc}); using their defaults")
        return []
    lines = original.splitlines()
    added, where = [], []
    for section, options in template.items():
        kinds = _classify(lines)
        start = next((i for i, (k, n) in enumerate(kinds) if k == "section" and n == section), None)
        if start is None:
            missing = options
        else:
            end = next((i for i in range(start + 1, len(lines)) if kinds[i][0] == "section"), len(lines))
            present = {n for k, n in kinds[start + 1:end] if k == "option"}
            missing = [(key, block) for key, block in options if key not in present]
        if not missing:
            continue
        block = [line for _, b in missing for line in b]
        if start is None:
            lines += ["", f"[{section}]", *block]
        else:
            ins = end
            while ins > start + 1 and not lines[ins - 1].strip():
                ins -= 1
            lines[ins:ins] = block
        added += [key for key, _ in missing]
        where += [(section, key) for key, _ in missing]
    if not added:
        return []
    text = "\n".join(lines) + "\n"
    try:
        before, after = _parse(original), _parse(text)
        unchanged = all(after.get(sec, key, raw=True) == before.get(sec, key, raw=True)
                        for sec in before.sections() for key in before[sec])
        unchanged = unchanged and all(after.has_option(sec, key) for sec, key in where)
    except configparser.Error:
        unchanged = False
    if not unchanged:
        warn(f"Couldn't add new options to {USER_CONFIG} safely; it was left unchanged. "
             f"Missing options use their defaults: {', '.join(added)}")
        return []
    try:
        atomic_write(USER_CONFIG.resolve(), text)   # a symlinked config (dotfiles) stays a symlink
    except OSError as exc:
        warn(f"Couldn't write {USER_CONFIG} to add new options ({exc}); using their defaults")
        return []
    return added


def set_user_config(values: dict[tuple[str, str], str]):
    """Change values in config.ini in place, keeping comments and layout."""
    lines = USER_CONFIG.read_text(encoding="utf-8").splitlines()
    for (section, key), value in values.items():
        sec, done, insert_at = None, False, None
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith("[") and s.endswith("]"):
                if sec == section and insert_at is None:
                    insert_at = i
                sec = s[1:-1]
                continue
            if sec == section and re.match(rf"^\s*{re.escape(key)}\s*=", line):
                m = _INLINE_COMMENT.search(line.split("=", 1)[1])
                comment = "  " + m.group(0).strip() if m else ""
                lines[i] = f"{key} = {value}{comment}"
                done = True
                break
        if not done:
            if sec == section and insert_at is None:
                insert_at = len(lines)
            if insert_at is None:
                lines += ["", f"[{section}]"]
                insert_at = len(lines)
            lines.insert(insert_at, f"{key} = {value}")
    atomic_write(USER_CONFIG, "\n".join(lines) + "\n")


# ----------------------------------------------------------------- install state

def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict):
    # owner-only: it can hold copies of private settings (e.g. a 0600 formatting file)
    atomic_write(STATE_FILE, json.dumps(state, indent=2) + "\n", 0o600)


def installed(state: dict) -> bool:
    """A Kate++ install is recorded, not just the leftovers of an interrupted uninstall."""
    return bool(state) and not state.get("uninstall_pending")


# ----------------------------------------------------------------- KConfig rc files

_GROUP = re.compile(r"^\s*(\[[^\]]*\])+\s*$")


def read_settings_ini(path: Path):
    out, group = [], None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        if _GROUP.match(line):
            group = line
        elif "=" in line and group:
            k, v = line.split("=", 1)
            out.append((group, k.strip(), v.strip()))
        else:
            raise ValueError(f"{path}: cannot parse: {raw}")
    return out


def merge_rc(target: Path, settings, mode=0o600):
    """Set/delete individual keys in a KConfig file, leaving everything else as-is."""
    lines = target.read_text(encoding="utf-8").splitlines() if target.exists() else []
    for group, key, value in settings:
        start = next((i + 1 for i, l in enumerate(lines) if l.strip() == group), None)
        if start is None:
            if value != "@delete":
                if lines and lines[-1].strip():
                    lines.append("")
                lines += [group, f"{key}={value}"]
            continue
        end = start
        while end < len(lines) and not _GROUP.match(lines[end]):
            end += 1
        hit = next((i for i in range(start, end)
                    if "=" in lines[i] and lines[i].split("=", 1)[0].strip() == key), None)
        if value == "@delete":
            if hit is not None:
                del lines[hit]
        elif hit is not None:
            lines[hit] = f"{key}={value}"
        else:
            ins = end
            while ins > start and not lines[ins - 1].strip():
                ins -= 1
            lines.insert(ins, f"{key}={value}")
    # drop groups we emptied
    tidy = []
    for i, line in enumerate(lines):
        if _GROUP.match(line):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j >= len(lines) or _GROUP.match(lines[j]):
                continue
        if not line.strip() and (not tidy or not tidy[-1].strip()):
            continue
        tidy.append(line)
    atomic_write(target, "\n".join(tidy).strip("\n") + "\n", mode)


def read_rc_value(target: Path, group: str, key: str):
    if not target.exists():
        return None
    current = None
    for line in target.read_text(encoding="utf-8").splitlines():
        if _GROUP.match(line):
            current = line.strip()
        elif current == group and "=" in line and line.split("=", 1)[0].strip() == key:
            return line.split("=", 1)[1].strip()
    return None


# ----------------------------------------------------------------- marked blocks

MARK = APP


def set_block(path: Path, prefix: str, body: list[str] | None):
    """Add/replace (body) or remove (None) our marked block in someone else's file."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    end = f"{prefix} <<< {MARK} <<<"
    pattern = re.compile(rf"\n*{re.escape(prefix)} >>> {MARK} >>>.*?{re.escape(end)}\n?", re.S)
    text = pattern.sub("\n", text).rstrip("\n")
    if body is not None:
        begin = f"{prefix} >>> {MARK} >>> (managed by Kate++; remove with `kate-plusplus uninstall`)"
        text += ("\n\n" if text else "") + "\n".join([begin, *body, end])
    if text or path.exists():
        atomic_write(path, text + "\n")
