"""kate-plusplus command line: install, apply, theme, backup, restore, doctor, update, uninstall."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import unicodedata
import time
from datetime import datetime
from pathlib import Path

from . import core, menus, ports, shortcuts, theme, window
from .core import (APP, BACKUP_DIR, BIN_LINK, CAELESTIA_SCHEME, DIM, BOLD, RESET, ACCENT,
                   GREEN, YELLOW, RED, KDEGLOBALS, REPO, STATE_DIR, USER_CONFIG, VERSION,
                   XDG_CONFIG, XDG_DATA, banner, info, section, step, warn, fail, ask, have, run)

SESSION = "Notepad"
SCRATCH_SESSION = "Scratchpad"
SCRATCH_ID = "kate-scratchpad"
MIMES = [
    "text/plain", "text/markdown", "text/x-markdown", "text/x-log", "application/json",
    "application/x-yaml", "application/yaml", "application/toml", "application/xml", "text/xml",
    "text/x-csrc", "text/x-chdr", "text/x-c++src", "text/x-python", "text/x-script.python",
    "application/x-shellscript", "text/x-lua", "text/css", "text/javascript",
    "application/javascript", "text/x-diff", "text/x-patch", "application/x-desktop",
]
THEME_NAMES = {"caelestia": "Kate++ Caelestia", "plasma": "Kate++ Plasma",
               "dark": "Kate++ Dark", "light": "Kate++ Light"}
SYSTEMD_DIR = XDG_CONFIG / "systemd/user"
HYPR_FILE_LUA = core.KPP_CONFIG_DIR / "hyprland.lua"
HYPR_FILE_CONF = core.KPP_CONFIG_DIR / "hyprland.conf"
CAELESTIA_DIR = XDG_CONFIG / "caelestia"


def entrypoint() -> str:
    """The command systemd units and desktop files should call."""
    if str(REPO).startswith("/usr/") and Path(f"/usr/bin/{APP}").exists():
        return f"/usr/bin/{APP}"
    return str(BIN_LINK)


def need_kate() -> core.Kate:
    kate = core.detect_kate()
    if not kate:
        fail("Kate isn't installed yet. Install it first, e.g.\n"
             "      Arch / EndeavourOS:  sudo pacman -S kate\n"
             "      Fedora:              sudo dnf install kate\n"
             "      Debian / Ubuntu:     sudo apt install kate\n"
             "      Any distro:          flatpak install flathub org.kde.kate")
    return kate


def resolve_profile(cfg) -> str:
    p = cfg.get("general", "profile").lower()
    if p in ("caelestia", "generic"):
        return p
    return "caelestia" if core.is_caelestia() else "generic"


def _slug(text):
    # decompose accents (é → e + ◌́, or already-decomposed input) and drop the marks
    t = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
    t = t.strip().lower()
    for quote in ("'", "\u2019", "\u2018", "\u02bc", "`", "\u00b4"):   # ' ’ ‘ ʼ ` ´
        t = t.replace(quote, "")
    return "-".join(t.replace("_", " ").replace("-", " ").split())


def _key(text):
    """Comparison key: case, accents, spaces, hyphens and underscores don't matter."""
    return _slug(text).replace("-", "")


# Themes bundled with Kate (KSyntaxHighlighting 6). Used when no listing tool is installed.
KATE_THEMES = (
    "Atom One Dark", "Atom One Light", "Breeze Dark", "Breeze Light", "Catppuccin Frappé",
    "Catppuccin Latte", "Catppuccin Macchiato", "Catppuccin Mocha", "Dracula", "Falcon",
    "GitHub Dark", "GitHub Light", "Homunculus", "Monokai", "Nord", "Oblivion", "Printing",
    "Radical", "Solarized Dark", "Solarized Light", "Tokyo Night", "Tokyo Night Light",
    "Tokyo Night Storm", "VSCodium Dark", "Vim Dark", "ayu Dark", "ayu Light", "ayu Mirage",
    "gruvbox Dark", "gruvbox Light",
)


def kate_builtin_themes():
    """Theme names Kate itself ships: asked from KSyntaxHighlighting when possible."""
    for tool in ("ksyntaxhighlighter6", "kate-syntax-highlighter"):
        if have(tool):
            out = run(tool, "--list-themes").stdout or ""
            ours = {name for name, *_rest in ports.PORTS.values()}   # installed by Kate++ itself
            names = [n.strip() for n in out.splitlines()
                     if n.strip() and not n.strip().startswith("Kate++") and n.strip() not in ours]
            if names:
                return names
    return list(KATE_THEMES)


def resolve_theme_source(cfg, profile) -> str | None:
    """Returns a Kate++ source (caelestia/plasma/dark/light), 'port:<slug>',
    'kate:<Theme Name>', or None to leave Kate's colours alone."""
    raw = cfg.get("theme", "source").strip()
    src = _slug(raw)
    if src == "none":
        return None
    if src == "auto":
        if profile == "caelestia" and CAELESTIA_SCHEME.is_file():
            return "caelestia"
        if core.is_plasma() and KDEGLOBALS.is_file() and theme.plasma_ui(KDEGLOBALS):
            return "plasma"
        return "dark" if core.system_prefers_dark() else "light"
    if src == "caelestia" and not CAELESTIA_SCHEME.is_file():
        warn("theme source 'caelestia' chosen but no Caelestia scheme found; using Kate++ Dark")
        return "dark"
    if src == "plasma" and not (KDEGLOBALS.is_file() and theme.plasma_ui(KDEGLOBALS)):
        warn("theme source 'plasma' chosen but no KDE colours found; using Kate++ Dark")
        return "dark"
    if src in THEME_NAMES:
        return src
    key = _key(raw)
    for family, (dark_variant, light_variant) in ports.FAMILIES.items():
        if key == _key(family):
            return "port:" + (dark_variant if core.system_prefers_dark() else light_variant)
    for slug, (name, *_rest) in ports.PORTS.items():
        if key in (_key(slug), _key(name)) or key in map(_key, ports.ALIASES.get(slug, ())):
            return "port:" + slug
    builtin = kate_builtin_themes()
    for name in builtin:
        if _key(name) == key:
            return "kate:" + name
    warn(f"theme '{raw}' not found; using auto. Try one of: " + ", ".join(
        sorted({*(n for n, *_ in ports.PORTS.values()), *builtin}, key=str.lower)))
    return resolve_theme_source(core.Config(), profile)


def theme_path(kate, slug):
    return kate.data / "org.kde.syntax-highlighting/themes" / f"{APP}-{slug}.theme"


def theme_options(cfg, quiet=False):
    """Validated (accent, background, intensity) from config.ini."""
    intensity = cfg.get("theme", "syntax-colors").lower()
    if intensity not in theme.INTENSITY:
        if not quiet:
            warn(f"syntax-colors '{intensity}' unknown; using balanced")
        intensity = "balanced"
    accent, background = cfg.get("theme", "accent"), cfg.get("theme", "background")
    for name, val in (("accent", accent), ("background", background)):
        if val:
            try:
                theme.norm(val)
            except ValueError:
                if not quiet:
                    warn(f"{name} = {val} is not a hex colour like #7aa2f7; ignoring it")
                if name == "accent":
                    accent = ""
                else:
                    background = ""
    return accent, background, intensity


def adaptive_theme(source, accent, background, intensity):
    """Theme dict for a resolved Kate++ adaptive source (caelestia/plasma/dark/light)."""
    if source in ("dark", "light"):
        ui = theme.static_ui(source)
    elif source == "caelestia":
        ui = theme.caelestia_ui(json.loads(CAELESTIA_SCHEME.read_text(encoding="utf-8"))["colours"])
    elif source == "plasma":
        ui = theme.plasma_ui(KDEGLOBALS)
    else:
        return None
    return theme.build_theme(THEME_NAMES[source], theme.apply_overrides(ui, accent, background), intensity)


def build_themes(cfg, kate, source) -> str | None:
    """Write the active theme (+ Kate++ Dark/Light so they're always selectable)."""
    accent, background, intensity = theme_options(cfg)
    for slug in ports.PORTS:
        theme.write_theme(theme_path(kate, slug), ports.build(slug))
    for variant in ("dark", "light"):
        own = source == variant
        theme.write_theme(theme_path(kate, variant),
                          adaptive_theme(variant, accent if own else "", background if own else "", intensity))
    if source in ("caelestia", "plasma"):
        theme.write_theme(theme_path(kate, source), adaptive_theme(source, accent, background, intensity))
    return theme_display_name(source)


def theme_display_name(source):
    if not source:
        return None
    if source.startswith("port:"):
        return ports.PORTS[source[5:]][0]
    if source.startswith("kate:"):
        return source[5:]
    return THEME_NAMES.get(source)


# ======================================================================= install / apply

def install_files(kate, state):
    shortcuts.install(kate, REPO, state)
    step("Notepad++ keyboard shortcuts  (merged: every other key keeps Kate's default)")

    dst = kate.data / "katepart5/script/commands/kate-plusplus.js"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO / "kate-scripts/kate-plusplus.js", dst)
    step("Notepad++ tools  (JSON, Base64, URL, dates, line clean-up)")

    icon = XDG_DATA / "icons/hicolor/scalable/apps/kate-plusplus.svg"
    icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO / "assets/icon.svg", icon)


def language_menu(cfg, kate, *, quiet=False):
    if not cfg.flag("features", "language-menu"):
        menus.remove(kate)
        return
    st = menus.ensure(kate)
    if quiet:
        return
    if st == "present":
        step("Language menu on the menu bar  (pick Java, Python, … for any tab)")
    else:
        info("Language menu: appears after Kate's first start (added automatically)")



def session_files(kate):
    d = kate.data / "kate"
    return sorted(d.glob("sessions/*.katesession")) + [p for p in (d / "anonymous.katesession",) if p.exists()]


def ensure_sessions(kate):
    sessions = kate.data / "kate/sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    main = sessions / f"{SESSION}.katesession"
    if not main.exists():
        anon = kate.data / "kate/anonymous.katesession"
        if anon.exists():
            shutil.copyfile(anon, main)
        else:
            main.write_text("[Open Documents]\nCount=0\n", encoding="utf-8")
    step(f"Memory: \"{SESSION}\" session with stash (no save prompts, tabs survive restarts)")


# Kate's LSP client (group "lspclient" in katerc): colour by meaning + inline hints.
LSP = "[lspclient]"
SMART_KEYS = ("SemanticHighlighting", "InlayHints", "AutoHover", "SignatureHelp", "Diagnostics")

# Extra directories Kate's default server table searches after PATH (lspclient settings.json).
_GO_DIRS = ("%{ENV:GOPATH}/bin", "%{ENV:HOME}/go/bin")
_CARGO_DIRS = ("%{ENV:CARGO_HOME}/bin", "%{ENV:HOME}/.cargo/bin")
SERVER_DIRS = {"gopls": _GO_DIRS, "rust-analyzer": _CARGO_DIRS}


def server_installed(cmd):
    """Found the way Kate finds it: on PATH, or in the server's extra default directories."""
    if have(cmd):
        return True
    for d in SERVER_DIRS.get(cmd, ()):
        env = re.match(r"%\{ENV:(\w+)\}", d)
        base = os.environ.get(env.group(1)) if env else None
        if base and os.access(Path(base + d[env.end():]) / cmd, os.X_OK):
            return True
    return False


# (command, language, install hint) for the doctor overview
LANGUAGE_SERVERS = [
    # Commands are the ones Kate's built-in server table starts (pylsp for Python, …);
    # other servers (e.g. pyright) need a custom entry in Kate's LSP Client settings.
    (("pylsp",), "Python",
     "Arch: pacman -S python-lsp-server · Debian/Ubuntu: apt install python3-pylsp · "
     "else: pipx install python-lsp-server  (Kate's default Python server)"),
    (("clangd",), "C / C++", "install clangd  (Debian/Ubuntu: apt install clangd · Arch: pacman -S clang)"),
    (("typescript-language-server",), "JavaScript / TypeScript",
     "npm i -g typescript typescript-language-server"),
    (("rust-analyzer",), "Rust", "rustup component add rust-analyzer"),
    (("jdtls",), "Java", "install jdtls (Eclipse JDT Language Server)"),
    (("bash-language-server",), "Bash", "npm i -g bash-language-server"),
    (("lua-language-server",), "Lua", "install lua-language-server"),
    (("gopls",), "Go", "go install golang.org/x/tools/gopls@latest"),
    (("marksman",), "Markdown", "install marksman"),
]


PRE_INSTALL = STATE_DIR / "katerc.before-kate-plusplus"


def managed_keys():
    """Every katerc key Kate++ may set: config/kate.ini plus the ones built from config.ini."""
    r = "[KTextEditor Renderer]"
    keys = [(g, k) for g, k, _ in core.read_settings_ini(REPO / "config/kate.ini")]
    return keys + [(r, "Text Font"), (r, "Line Height Multiplier"), (r, "Color Theme"),
                   (r, "Auto Color Theme Selection"), ("[KTextEditor View]", "Scroll Bar MiniMap")]
    # Keys added later (e.g. [lspclient]) are deliberately not here: versions without per-key
    # records never set them, so the fallback must not delete a user's own values. Their
    # records are trustworthy even on an incomplete legacy upgrade, and the fallback restores them.


def set_katerc(kate, state, settings):
    """Write Kate settings, remembering each key's value from before Kate++ first touched it,
    so uninstall can put back exactly that (or remove the key if there was none).

    The original comes from the pre-install backup when there is one, and the record is saved
    *before* katerc changes, so an error in between can't lose it. `katerc_complete` says
    whether the records describe the true originals: always for new installs; for upgrades
    from versions without records only when the pre-install backup exists (then every
    managed key is seeded from it at once)."""
    if "katerc_complete" not in state or "katerc_before" not in state:   # missing records or flag
        records = state.setdefault("katerc_before", {})
        legacy = bool(state.get("version"))          # installed by a version without (full) records
        if legacy and PRE_INSTALL.exists():
            # ColorScheme too (window colours write it), but it stays out of managed_keys() so
            # the record-less fallback never deletes a scheme the user picked
            for group, key in managed_keys() + [(UI, "ColorScheme")]:
                k = f"{group}\t{key}"
                if k not in records:
                    records[k] = core.read_rc_value(PRE_INSTALL, group, key)
        state["katerc_complete"] = not legacy or PRE_INSTALL.exists()
        core.save_state(state)
    before = state["katerc_before"]
    new = False
    for group, key, _ in settings:
        k = f"{group}\t{key}"
        if k not in before:
            source = PRE_INSTALL if PRE_INSTALL.exists() else kate.katerc
            before[k] = core.read_rc_value(source, group, key)
            new = True
    if new:
        core.save_state(state)
    core.merge_rc(kate.katerc, settings)


def restore_katerc(kate, state) -> bool:
    """Put recorded values back. Returns False when there were no records to restore from."""
    before = state.get("katerc_before", {})
    if not before or not state.get("katerc_complete", False):
        return False
    changes = []
    for k, old in before.items():
        group, key = k.split("\t", 1)
        changes.append((group, key, "@delete" if old is None else old))
    core.merge_rc(kate.katerc, changes)
    return True


def remove_managed_katerc(kate, state=None):
    """Fallback without complete records or a backup: remove the settings older versions
    managed (their originals are unknown), and put back exactly the recorded originals of
    keys only newer versions write: those were recorded before Kate++ first touched them."""
    legacy = managed_keys()
    changes = [(g, k, "@delete") for g, k in legacy]
    old_keys = {f"{g}\t{k}" for g, k in legacy} | {f"{UI}\tColorScheme"}   # scheme: see do_uninstall
    for rec, old in (state or {}).get("katerc_before", {}).items():
        if rec not in old_keys:
            group, key = rec.split("\t", 1)
            changes.append((group, key, "@delete" if old is None else old))
    core.merge_rc(kate.katerc, changes)


UI = "[UiSettings]"


def window_colors(cfg, kate, source, theme_name, state):
    """Match Kate's window colours to the editor theme, or leave them to the desktop.

    - Caelestia / Plasma sources, or window-colors = system: the window follows the desktop.
    - Otherwise Kate++ writes a matching colour scheme and selects it.
    - A scheme the user picked in Kate by hand is never overwritten."""
    mode = cfg.get("theme", "window-colors").lower()
    if mode not in ("match", "system"):
        warn(f"window-colors = {mode} isn't a choice; use match or system. Using match for now")
        mode = "match"
    current = core.read_rc_value(kate.katerc, UI, "ColorScheme")
    ours = current is not None and current.startswith(window.PREFIX)
    # Only a brand-new install may replace a scheme that's already set (once; uninstall restores
    # it). An existing install (state has a version) treats any non-Kate++ scheme as the user's.
    first_run = "window_scheme" not in state and not state.get("version")
    manual = bool(current) and not ours and not first_run and current != state.get("window_scheme")

    if manual:   # state["window_scheme"] keeps naming only what Kate++ wrote
        info(f"Window colours: keeping '{current}' you picked in Kate "
             f"{DIM}(choose Default there to let Kate++ match again){RESET}")
        return
    follow_desktop = mode == "system" or source in (None, "caelestia", "plasma")
    roles = None
    if not follow_desktop:
        if source.startswith("kate:"):
            roles = window.roles_from_kate_theme(source[5:])
        else:
            slug = source.split(":", 1)[-1]
            roles = window.roles_from_theme(json.loads(theme_path(kate, slug).read_text(encoding="utf-8")))
    if roles is None:
        window.remove_schemes(kate)
        if current and (ours or first_run):
            set_katerc(kate, state, [(UI, "ColorScheme", "@delete")])
        state["window_scheme"] = ""
        if not follow_desktop:
            info("Window colours follow your desktop (couldn't read this theme's colours)")
        return
    sid = window.write_scheme(kate, theme_name, roles)
    set_katerc(kate, state, [(UI, "ColorScheme", sid)])
    state["window_scheme"] = sid
    step(f"Window colours match {theme_name}")


def kate_settings(cfg, kate, theme_name, state):
    settings = core.read_settings_ini(REPO / "config/kate.ini")
    r = "[KTextEditor Renderer]"
    font = cfg.get("editor", "font")
    if font.lower() == "auto":
        font = core.installed_font("JetBrainsMono Nerd Font", "JetBrains Mono", "JetBrainsMono NF") \
            or "Monospace"
    try:
        size = max(6, min(40, int(float(cfg.get("editor", "font-size")))))
        spacing = max(1.0, min(2.0, float(cfg.get("editor", "line-spacing"))))
    except ValueError:
        warn("font-size / line-spacing must be numbers; using 11 / 1.15")
        size, spacing = 11, 1.15
    settings += [
        (r, "Text Font", f"{font},{size},-1,2,400,0,0,0,0,0,0,0,0,0,0,1"),
        (r, "Line Height Multiplier", f"{spacing:g}"),
        ("[KTextEditor View]", "Scroll Bar MiniMap", str(cfg.flag("editor", "minimap")).lower()),
    ]
    if cfg.flag("editor", "smart-highlighting"):   # off: Kate's own LSP settings stay untouched
        settings += [(LSP, key, "true") for key in SMART_KEYS]
    if theme_name:
        settings += [(r, "Auto Color Theme Selection", "false"), (r, "Color Theme", theme_name)]
    set_katerc(kate, state, settings)
    step(f"Editor: {font} {size}pt · tabs, minimap, function list, macros, stash")


def hotkey_modmask(hotkey):
    bits = {"SUPER": 64, "WIN": 64, "MOD4": 64, "SHIFT": 1, "CTRL": 4, "CONTROL": 4, "ALT": 8}
    parts = [p.strip().upper() for p in hotkey.split("+") if p.strip()]
    return sum(bits.get(p, 0) for p in parts[:-1]), (parts[-1] if parts else "")


def hotkey_taken(hotkey):
    r = run("hyprctl", "binds", "-j")
    if r.returncode != 0:
        return None
    mask, key = hotkey_modmask(hotkey)
    try:
        for b in json.loads(r.stdout):
            if b.get("modmask") == mask and str(b.get("key", "")).upper() == key:
                return b.get("description") or b.get("dispatcher") or "something else"
    except ValueError:
        return None
    return None


def setup_overlay(cfg, kate, state):
    style = core.hyprland_style()
    hotkey = cfg.get("features", "notepad-hotkey") or "SUPER + J"
    if not style:
        warn("Notepad overlay needs Hyprland; skipped")
        return False
    if state.get("overlay_hotkey") != hotkey:
        taken = hotkey_taken(hotkey)
        if taken:
            warn(f"{hotkey} is already used ({taken}). Pick another key in {USER_CONFIG}"
                 " (notepad-hotkey) and run `kate-plusplus apply`.")
            return False

    scratch_cmd = kate.cmd + ["-n", "-s", SCRATCH_SESSION, "--desktopfile", SCRATCH_ID]
    # app definition for Caelestia's overlay toggle
    cli_json = CAELESTIA_DIR / "cli.json"
    data = json.loads(cli_json.read_text(encoding="utf-8")) if cli_json.exists() else {}
    data.setdefault("toggles", {})["notepad"] = {
        "kate": {"enable": True, "match": [{"class": SCRATCH_ID}], "command": scratch_cmd, "move": True}}
    core.atomic_write(cli_json, json.dumps(data, indent=4, ensure_ascii=False) + "\n")

    if style == "lua":
        text = (REPO / "hyprland/kate-plusplus.lua").read_text(encoding="utf-8")
        core.atomic_write(HYPR_FILE_LUA, text.replace("@HOTKEY@", hotkey))
        core.set_block(CAELESTIA_DIR / "hypr-user.lua", "--",
                       [f'pcall(dofile, os.getenv("HOME") .. "/.config/{APP}/hyprland.lua")'])
    else:
        mask, key = hotkey_modmask(hotkey)
        mods = " ".join(p.strip().upper() for p in hotkey.split("+")[:-1])
        text = (REPO / "hyprland/kate-plusplus.conf").read_text(encoding="utf-8")
        core.atomic_write(HYPR_FILE_CONF, text.replace("@HOTKEY_CONF@", f"{mods}, {key}"))
        core.set_block(CAELESTIA_DIR / "hypr-user.conf", "#", [f"source = ~/.config/{APP}/hyprland.conf"])

    desktop = (REPO / "desktop/kate-scratchpad.desktop").read_text(encoding="utf-8")
    core.atomic_write(XDG_DATA / f"applications/{SCRATCH_ID}.desktop",
                      desktop.replace("@KATE@", " ".join(kate.cmd)))
    if kate.kind == "native":
        pin_main_session()
    run("hyprctl", "reload")
    state["overlay_hotkey"] = hotkey
    step(f"Notepad overlay on {BOLD}{hotkey}{RESET}")
    return True


DESKTOP_MARK = "X-KatePlusPlus=true"


def _is_ours(path: Path) -> bool:
    """True only for launcher files Kate++ wrote: the marker must be a line of its own."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return any(line.strip() == DESKTOP_MARK for line in text.splitlines())


def pin_main_session():
    """Local copy of Kate's launcher that always opens the Notepad session, so files you
    open from the launcher / file manager never land in the hidden scratchpad."""
    src = next((p for p in (Path("/usr/share/applications/org.kde.kate.desktop"),
                            Path("/usr/local/share/applications/org.kde.kate.desktop")) if p.exists()), None)
    if not src:
        return
    dest = XDG_DATA / "applications/org.kde.kate.desktop"
    if dest.is_symlink() or (dest.exists() and not _is_ours(dest)):   # incl. a dangling link
        warn(f"Not touching your own {dest}; Kate files may open in the Scratchpad session "
             "while it runs. Add `-s Notepad` to its Exec= lines to avoid that.")
        return
    out = []
    for line in src.read_text(encoding="utf-8").splitlines():
        if line.startswith("Exec=kate") and " -s " not in line:
            line = line.replace("Exec=kate", f"Exec=kate -s {SESSION}", 1)
        out.append(line)
    out.append(DESKTOP_MARK)
    core.atomic_write(dest, "\n".join(out) + "\n")


def remove_overlay():
    cli_json = CAELESTIA_DIR / "cli.json"
    if cli_json.exists():
        try:
            data = json.loads(cli_json.read_text(encoding="utf-8"))
            if data.get("toggles", {}).pop("notepad", None) is not None:
                if not data["toggles"]:
                    data.pop("toggles")
                core.atomic_write(cli_json, json.dumps(data, indent=4, ensure_ascii=False) + "\n")
        except ValueError:
            warn(f"{cli_json} isn't valid JSON; remove the 'notepad' toggle by hand")
    for f, prefix in ((CAELESTIA_DIR / "hypr-user.lua", "--"), (CAELESTIA_DIR / "hypr-user.conf", "#")):
        if f.exists() and APP in f.read_text(encoding="utf-8"):
            core.set_block(f, prefix, None)
    for f in (HYPR_FILE_LUA, HYPR_FILE_CONF, XDG_DATA / f"applications/{SCRATCH_ID}.desktop"):
        f.unlink(missing_ok=True)
    own = XDG_DATA / "applications/org.kde.kate.desktop"
    if own.exists() and _is_ours(own):
        own.unlink()   # only Kate++'s own copy; same lenient decoding as when it was written
    if have("hyprctl"):
        run("hyprctl", "reload")


MIMEAPPS = XDG_CONFIG / "mimeapps.list"
DEFAULTS_GROUP = "[Default Applications]"
KATE_DESKTOP = "org.kde.kate.desktop"


def set_default_editor(state):
    """Point the file types at Kate, remembering only what *you* had set explicitly."""
    before = state.setdefault("mime_before", {})
    for m in MIMES:
        if m not in before:
            before[m] = core.read_rc_value(MIMEAPPS, DEFAULTS_GROUP, m) or ""
    core.merge_rc(MIMEAPPS, [(DEFAULTS_GROUP, m, KATE_DESKTOP) for m in MIMES], mode=0o644)
    if have("update-desktop-database"):
        run("update-desktop-database", str(XDG_DATA / "applications"))
    step("Kate opens text, Markdown, JSON, YAML, logs and config files")


def restore_default_editor(state):
    before = state.pop("mime_before", None)
    if not before or not MIMEAPPS.exists():
        return
    changes = []
    for mime, app in before.items():
        if core.read_rc_value(MIMEAPPS, DEFAULTS_GROUP, mime) == KATE_DESKTOP:
            changes.append((DEFAULTS_GROUP, mime, app if app and app != KATE_DESKTOP else "@delete"))
    core.merge_rc(MIMEAPPS, changes, mode=0o644)


def install_unit(name, enable_unit):
    text = (REPO / "systemd" / name).read_text(encoding="utf-8").replace("@BIN@", entrypoint())
    core.atomic_write(SYSTEMD_DIR / name, text)
    return enable_unit


def setup_systemd(cfg, source):
    if not core.has_systemd_user():
        if cfg.flag("features", "backups"):
            warn("No systemd user session: automatic backups are off (run `kate-plusplus backup` yourself)")
        return
    wanted = []
    if cfg.flag("features", "backups") or cfg.flag("features", "language-menu"):
        install_unit("kate-plusplus-backup.service", None)
        wanted.append(install_unit("kate-plusplus-backup.timer", "kate-plusplus-backup.timer"))
    watch = {"caelestia": CAELESTIA_SCHEME, "plasma": KDEGLOBALS}.get(source)
    if watch:
        install_unit("kate-plusplus-theme.service", None)
        text = (REPO / "systemd/kate-plusplus-theme.path").read_text(encoding="utf-8")
        text = text.replace("%h/.local/state/caelestia/scheme.json", str(watch))
        core.atomic_write(SYSTEMD_DIR / "kate-plusplus-theme.path", text)
        wanted.append("kate-plusplus-theme.path")
    run("systemctl", "--user", "daemon-reload")
    for unit in ("kate-plusplus-backup.timer", "kate-plusplus-theme.path"):
        if unit not in wanted and (SYSTEMD_DIR / unit).exists():
            run("systemctl", "--user", "disable", "--now", unit)
            for f in SYSTEMD_DIR.glob(unit.rsplit(".", 1)[0] + ".*"):
                f.unlink()
    for unit in wanted:
        run("systemctl", "--user", "enable", "--now", unit)
    if cfg.flag("features", "backups"):
        days = cfg.get("features", "backup-keep-days")
        step(f"Safety snapshots every 10 min, kept {days} days")
    if watch:
        step("Theme follows your colours automatically")


def remove_systemd():
    if not have("systemctl"):
        return
    for unit in ("kate-plusplus-backup.timer", "kate-plusplus-theme.path"):
        run("systemctl", "--user", "disable", "--now", unit)
    for f in SYSTEMD_DIR.glob("kate-plusplus-*"):
        f.unlink()
    run("systemctl", "--user", "daemon-reload")


def link_cli():
    if str(REPO).startswith("/usr/"):
        return
    BIN_LINK.parent.mkdir(parents=True, exist_ok=True)
    target = REPO / "bin" / APP
    if BIN_LINK.is_symlink() or BIN_LINK.exists():
        if BIN_LINK.resolve() == target.resolve():
            return
        BIN_LINK.unlink()
    BIN_LINK.symlink_to(target)
    if str(BIN_LINK.parent) not in os.environ.get("PATH", "").split(":"):
        warn(f"{BIN_LINK.parent} isn't on your PATH; add it to use the `{APP}` command")


def do_apply(args, first_install=False):
    kate = need_kate()
    state = core.load_state()
    created = core.ensure_user_config()
    cfg = core.load_config()
    profile = resolve_profile(cfg)

    if not core.QUIET:
        flavour = "Caelestia · Hyprland" if profile == "caelestia" else "Generic Linux"
        banner(f"{'Installing' if first_install else 'Applying'} · {flavour} · Kate {kate.version} ({kate.kind})")

    if first_install and not args.yes:
        print("  This sets Kate up like Notepad++ and backs up your current Kate settings first.")
        print(f"  {DIM}Options live in {USER_CONFIG}{RESET}\n")
        if not ask("Continue?"):
            fail("Nothing changed.", 0)

    core.wait_for_kate_closed(kate)

    section("Safety first")
    if kate.katerc.exists() and not PRE_INSTALL.exists() and not core.load_state():
        PRE_INSTALL.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(kate.katerc, PRE_INSTALL)
        step(f"Original Kate settings saved  {DIM}{PRE_INSTALL}{RESET}")
    snap = make_backup(kate, force=True, label="pre-apply")
    if snap:
        step(f"Snapshot of sessions & tabs   {DIM}{snap.name}{RESET}")
    elif not kate.katerc.exists():
        step("Fresh Kate: nothing to back up yet")

    section("Kate")
    install_files(kate, state)
    language_menu(cfg, kate)
    ensure_sessions(kate)
    source = resolve_theme_source(cfg, profile)
    theme_name = build_themes(cfg, kate, source)
    kate_settings(cfg, kate, theme_name, state)
    window_colors(cfg, kate, source, theme_name, state)
    if theme_name:
        detail = (f"{cfg.get('theme', 'syntax-colors')} syntax colours" if source in THEME_NAMES
                  else "ships with Kate" if source.startswith("kate:")
                  else f"by {ports.designer(source[5:])}")
        step(f"Theme: {theme_name}  {DIM}({detail}){RESET}")

    section("System")
    overlay = False
    if profile == "caelestia" and cfg.flag("features", "notepad-overlay"):
        overlay = setup_overlay(cfg, kate, state)
    if not overlay and state.get("overlay_hotkey"):
        remove_overlay()
        state.pop("overlay_hotkey", None)
        info("Notepad overlay removed")
    if cfg.flag("features", "default-editor"):
        set_default_editor(state)
    elif "mime_before" in state:
        restore_default_editor(state)
        info("Default-editor associations restored")
    setup_systemd(cfg, source)
    link_cli()

    state.update({"version": VERSION, "profile": profile, "kate": kate.kind,
                  "theme_source": source, "repo": str(REPO), "applied": datetime.now().isoformat(timespec="seconds")})
    core.save_state(state)

    if not core.QUIET:
        print(f"\n  {GREEN}{BOLD}Done!{RESET} Open Kate and it's straight back in your tabs.\n")
        if first_install or created:
            print(f"  {BOLD}Try it{RESET}")
            if overlay:
                print(f"    {ACCENT}{cfg.get('features', 'notepad-hotkey'):<16}{RESET} pop-up notepad")
            for k, v in (("Ctrl+D", "duplicate line"), ("Ctrl+H", "find & replace"),
                         ("Ctrl+Shift+R / P", "record / play macro"),
                         ("Ctrl+Alt+I", "command bar: type a tool name, e.g. \"Format JSON\""),
                         ("Ctrl+Alt+Shift+M", "format JSON")):
                print(f"    {ACCENT}{k:<16}{RESET} {v}")
            print(f"\n  {DIM}Tweak anything: {APP} config   ·   Health check: {APP} doctor{RESET}\n")


# ======================================================================= theme

def do_pick_theme(args):
    from . import picker
    core.QUIET = False   # picking is interactive: the choices must be visible even with --quiet
    need_kate()
    core.ensure_user_config()
    current = core.load_config().get("theme", "source")
    chosen = picker.pick(picker.entries(kate_builtin_themes()), current)
    if chosen is None:
        info("No change.")
        return
    core.set_user_config({("theme", "source"): chosen.source})
    step(f"Theme set to {chosen.label}  {DIM}(source = {chosen.source}){RESET}")
    args.pick = False
    do_theme(args)
    # keep the colour watcher in step with the new source (Caelestia/Plasma follow live changes)
    cfg = core.load_config()
    source = resolve_theme_source(cfg, resolve_profile(cfg))
    quiet, core.QUIET = core.QUIET, True
    try:
        setup_systemd(cfg, source)
    finally:
        core.QUIET = quiet
    state = core.load_state()
    if state:
        state["theme_source"] = source
        core.save_state(state)


def do_theme(args):
    if getattr(args, "pick", False):
        return do_pick_theme(args)
    kate = need_kate()
    cfg = core.load_config()
    profile = resolve_profile(cfg)
    source = resolve_theme_source(cfg, profile)
    name = build_themes(cfg, kate, source)
    state = core.load_state()
    installed = bool(state.get("version"))
    changed = False
    if not name:
        core.info("Theme source is 'none'; Kate's own colours are left alone")
    else:
        step(f"{name} regenerated")
        r = "[KTextEditor Renderer]"
        current = core.read_rc_value(kate.katerc, r, "Color Theme")
        auto = core.read_rc_value(kate.katerc, r, "Auto Color Theme Selection")
        if current != name or auto != "false":
            # Safe while Kate runs: Kate only writes back settings it changed itself. Goes through
            # set_katerc so uninstall can restore the previous values exactly.
            set_katerc(kate, state, [(r, "Auto Color Theme Selection", "false"), (r, "Color Theme", name)])
            changed = True
    # Window colours follow the theme too (only once installed: a first install decides
    # whether an existing scheme may be replaced, so it is left to apply).
    if installed:
        before = core.read_rc_value(kate.katerc, UI, "ColorScheme")
        window_colors(cfg, kate, source, name, state)
        changed = changed or core.read_rc_value(kate.katerc, UI, "ColorScheme") != before
    if changed or installed:
        core.save_state(state)
    if changed and core.kate_running(kate):
        info(f"Restart Kate to see {name or 'the new colours'}")
    return None


# ======================================================================= backups

def _backup_sources(kate):
    return [p for p in (kate.katerc, kate.config / "katemetainfos", kate.data / "kate") if p.exists()]


def _fingerprint(paths):
    h = hashlib.sha256()
    for root in paths:
        files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
        for f in files:
            h.update(str(f).encode())
            try:
                h.update(f.read_bytes())
            except OSError:
                pass
    return h.hexdigest()


def make_backup(kate, force=False, label="auto"):
    paths = _backup_sources(kate)
    if not paths:
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    fp = _fingerprint(paths)
    last = BACKUP_DIR / ".last-fingerprint"
    if not force and last.exists() and last.read_text().strip() == fp:
        return None
    name = BACKUP_DIR / f"kate-{datetime.now():%Y%m%d-%H%M%S}-{label}.tar.gz"
    with tarfile.open(name, "w:gz") as tar:
        for p in paths:
            tar.add(p, arcname=str(p.relative_to(core.HOME)))
    last.write_text(fp)
    return name


def list_backups():
    return sorted(BACKUP_DIR.glob("kate-*.tar.gz"), reverse=True)


def prune_backups(days):
    snaps = list_backups()
    cutoff = time.time() - days * 86400
    for old in snaps[10:]:  # always keep the newest 10
        if old.stat().st_mtime < cutoff:
            old.unlink()


def do_maintain(args):
    """Background job (every 10 min): snapshot if backups are on, and re-add the Language
    menu if a Kate update rebuilt Kate's menu file."""
    kate = core.detect_kate()
    if not kate:
        return
    cfg = core.load_config()
    # each step on its own: a failed snapshot must not stop the menu repair, and vice versa
    if cfg.flag("features", "backups"):
        try:
            do_backup(args)
        except Exception as e:  # noqa: BLE001 - background job: report and continue
            warn(f"snapshot failed: {e}")
    try:
        language_menu(cfg, kate, quiet=True)
    except Exception as e:  # noqa: BLE001 - e.g. Kate is rewriting its menu file right now
        warn(f"Language menu check failed (will retry next run): {e}")


def do_backup(args):
    kate = need_kate()
    cfg = core.load_config()
    snap = make_backup(kate, force=not args.quiet, label="auto" if args.quiet else "manual")
    try:
        days = float(cfg.get("features", "backup-keep-days"))
    except ValueError:
        days = 2
    prune_backups(days)
    if snap:
        step(f"Snapshot saved  {DIM}{snap}{RESET}")
    else:
        info("Nothing changed since the last snapshot")


def _human(ts):
    delta = time.time() - ts
    if delta < 90:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)} min ago"
    if delta < 86400:
        return f"{int(delta // 3600)} h ago"
    return f"{int(delta // 86400)} days ago"


def do_restore(args):
    kate = need_kate()
    snaps = list_backups()
    if not snaps:
        fail(f"No snapshots yet in {BACKUP_DIR}")
    banner("Restore a snapshot of your Kate sessions and unsaved tabs")
    choice = args.snapshot
    if not choice:
        for i, s in enumerate(snaps[:15], 1):
            st = s.stat()
            print(f"   {ACCENT}{i:>2}{RESET}  {datetime.fromtimestamp(st.st_mtime):%a %d %b %H:%M}"
                  f"  {DIM}{_human(st.st_mtime):>12} · {st.st_size // 1024} KB{RESET}")
        choice = core.prompt("\n  Which one? (number, Enter = cancel)")
        if not choice:
            fail("Cancelled.", 0)
    try:
        snap = snaps[int(choice) - 1] if choice.isdigit() else Path(choice)
    except IndexError:
        fail("No snapshot with that number")
    if not snap.exists():
        fail(f"{snap} not found")
    core.wait_for_kate_closed(kate, "restore your tabs")
    safety = make_backup(kate, force=True, label="before-restore")
    shutil.rmtree(kate.data / "kate", ignore_errors=True)
    with tarfile.open(snap) as tar:
        tar.extractall(core.HOME, filter="data") if hasattr(tarfile, "data_filter") else tar.extractall(core.HOME)
    step(f"Restored {snap.name}")
    if safety:
        info(f"What you had before is in {safety.name} (restore it the same way)")


# ======================================================================= doctor

def do_doctor(args):
    banner("Health check")
    ok = lambda m: print(f"  {GREEN}✓{RESET} {m}")       # noqa: E731
    bad = lambda m: print(f"  {RED}✗{RESET} {m}")        # noqa: E731
    meh = lambda m: print(f"  {YELLOW}!{RESET} {m}")     # noqa: E731
    kate = core.detect_kate()
    state = core.load_state()
    cfg = core.load_config()
    print(f"  {DIM}Kate++ {VERSION} · {sys.platform} · Python {sys.version.split()[0]} · "
          f"{os.environ.get('XDG_CURRENT_DESKTOP', '?')} · {os.environ.get('XDG_SESSION_TYPE', '?')}{RESET}\n")
    if not kate:
        bad("Kate is not installed")
        return 1
    ok(f"Kate {kate.version} ({kate.kind})")
    (ok if state else bad)(f"Installed: {state.get('version', 'no')}  profile {state.get('profile', '-')}")
    (ok if USER_CONFIG.exists() else meh)(f"Config: {USER_CONFIG}")
    scheme = core.read_rc_value(kate.katerc, "[Shortcut Schemes]", "Current Scheme")
    if scheme and scheme != "Default":
        bad(f"Shortcut scheme '{scheme}' is active: it can disable normal keys. Run `kate-plusplus apply`")
    (ok if shortcuts.installed(kate, REPO) else bad)("Notepad++ shortcuts (merged into Kate's defaults)")
    if cfg.flag("features", "language-menu"):
        st = menus.status(kate)
        {"present": ok, "missing": bad, "pending": meh}[st]({
            "present": "Language menu on the menu bar",
            "missing": "Language menu missing (Kate was updated?) → kate-plusplus apply",
            "pending": "Language menu appears after Kate's first start"}[st])
    (ok if (kate.data / "katepart5/script/commands/kate-plusplus.js").exists() else bad)("Notepad++ tools script")
    stash = core.read_rc_value(kate.katerc, "[General]", "Stash unsaved file changes") == "true"
    (ok if stash else bad)("Stash (no save prompts, tabs survive restarts)")
    t = core.read_rc_value(kate.katerc, "[KTextEditor Renderer]", "Color Theme")
    src = state.get("theme_source")
    if src and src.startswith("kate:"):
        (ok if t == src[5:] else meh)(f"Theme {t}  {DIM}(ships with Kate){RESET}")
    elif src:
        f = theme_path(kate, src.split(":", 1)[-1])
        (ok if f.exists() else bad)(f"Theme {t}  {DIM}({f.name}){RESET}")
    else:
        meh("Theme: Kate's own (source = none)")
    ws = state.get("window_scheme")
    cur = core.read_rc_value(kate.katerc, "[UiSettings]", "ColorScheme")
    if cur and cur == ws:
        ok(f"Window colours match the theme {DIM}({ws}){RESET}")
    elif cur and not cur.startswith(window.PREFIX):
        ok(f"Window colours: '{cur}', your own choice in Kate "
           f"{DIM}(choose Default there to let Kate++ match the theme){RESET}")
    elif cur:
        meh(f"Window colours: '{cur}' is an old Kate++ scheme → kate-plusplus apply")
    else:
        ok("Window colours follow your desktop")
    if state.get("profile") == "caelestia":
        if have("caelestia"):
            ok("Caelestia CLI")
        qt = os.environ.get("QT_QPA_PLATFORMTHEME", "")
        plugin_dirs = [Path("/usr/lib/qt6/plugins/platformthemes"), Path("/usr/lib64/qt6/plugins/platformthemes")]
        has_engine = qt != "qtengine" or any(
            any(d.glob("*qtengine*")) or any(d.glob("libqt6engine*")) for d in plugin_dirs if d.exists())
        (ok if has_engine else bad)(f"Qt platform theme '{qt or '-'}'"
                                    + ("" if has_engine else " is set but not installed (yay -S qtengine)"))
        if state.get("overlay_hotkey"):
            bound = hotkey_taken(state["overlay_hotkey"])
            (ok if bound else meh)(f"Notepad overlay {state['overlay_hotkey']}"
                                   + ("" if bound else " (not bound yet; reload Hyprland)"))
    if core.has_systemd_user():
        for unit, want in (("kate-plusplus-backup.timer", cfg.flag("features", "backups")
                            or cfg.flag("features", "language-menu")),
                           ("kate-plusplus-theme.path", src in ("caelestia", "plasma"))):
            active = run("systemctl", "--user", "is-active", unit).stdout.strip() == "active"
            if want:
                (ok if active else bad)(f"{unit} {'running' if active else 'not running'}")
    snaps = list_backups()
    if snaps:
        ok(f"{len(snaps)} snapshots, newest {_human(snaps[0].stat().st_mtime)}")
    elif cfg.flag("features", "backups"):
        meh("No snapshots yet")
    if cfg.flag("editor", "smart-highlighting"):
        found = [lang for cmds, lang, _ in LANGUAGE_SERVERS if any(server_installed(c) for c in cmds)]
        (ok if found else meh)("Smart highlighting on · language servers: "
                               + (", ".join(found) if found else "none installed yet"))
        for cmds, lang, hint in LANGUAGE_SERVERS:
            if lang not in found and lang in ("Python", "C / C++", "JavaScript / TypeScript", "Java", "Bash"):
                info(f"{lang}: {DIM}{hint}{RESET}")
    if have("xdg-mime"):
        d = (run("xdg-mime", "query", "default", "text/plain").stdout or "").strip()
        (ok if d == "org.kde.kate.desktop" or not cfg.flag("features", "default-editor") else meh)(
            f"text/plain opens with {d or 'nothing set'}")
    print()
    return 0


# ======================================================================= update / uninstall / config

def do_update(args):
    if str(REPO).startswith("/usr/"):
        info("Installed from a package: update it with your package manager (e.g. yay -Syu),")
        info("then run `kate-plusplus apply`.")
        return
    if not (REPO / ".git").exists():
        fail(f"{REPO} isn't a git checkout; reinstall with the one-line installer")
    banner("Update")
    before = run("git", "-C", str(REPO), "rev-parse", "HEAD").stdout.strip()
    r = run("git", "-C", str(REPO), "pull", "--ff-only", "--quiet")
    if r.returncode != 0:
        fail(f"git pull failed:\n{r.stderr}")
    after = run("git", "-C", str(REPO), "rev-parse", "HEAD").stdout.strip()
    if before == after:
        step("Already up to date")
        return
    step("Downloaded the latest Kate++")
    os.execv(sys.executable, [sys.executable, str(REPO / "bin" / APP), "apply", "--yes"])


def do_uninstall(args):
    kate = need_kate()
    banner("Uninstall")
    if not args.yes and not ask("Remove Kate++ from this account? Your notes and tabs stay."):
        fail("Nothing changed.", 0)
    core.wait_for_kate_closed(kate)
    state = core.load_state()
    snap = make_backup(kate, force=True, label="before-uninstall")
    remove_overlay()
    remove_systemd()
    restore_default_editor(state)
    shortcuts.uninstall(kate, REPO, state)
    menus.remove(kate)
    (kate.data / "katepart5/script/commands/kate-plusplus.js").unlink(missing_ok=True)
    for f in (kate.data / "org.kde.syntax-highlighting/themes").glob(f"{APP}-*.theme"):
        f.unlink()
    (XDG_DATA / "icons/hicolor/scalable/apps/kate-plusplus.svg").unlink(missing_ok=True)
    window.remove_schemes(kate)
    if PRE_INSTALL.exists() and (args.yes or ask("Put your Kate settings back to how they were before Kate++?")):
        shutil.copy2(PRE_INSTALL, kate.katerc)
        step("Original Kate settings restored")
    elif restore_katerc(kate, state):  # exactly what each key was before Kate++
        step("Your previous Kate settings restored")
    else:                               # older install without records and without a backup
        remove_managed_katerc(kate, state)
        scheme = core.read_rc_value(kate.katerc, "[UiSettings]", "ColorScheme")
        if scheme and scheme.startswith(window.PREFIX):   # its file is gone; a manual pick stays
            core.merge_rc(kate.katerc, [("[UiSettings]", "ColorScheme", "@delete")])
        step("Kate++ settings removed (no record of your earlier values was available)")
    shutil.rmtree(STATE_DIR, ignore_errors=True)
    if BIN_LINK.is_symlink():
        BIN_LINK.unlink()
    step("Kate++ removed")
    info(f"Kept: your sessions & tabs, {USER_CONFIG.parent} and snapshots in {BACKUP_DIR}")
    if snap:
        info(f"Last snapshot: {snap.name}")


def do_config(args):
    core.ensure_user_config()
    if args.print:
        print(USER_CONFIG.read_text(encoding="utf-8"))
        return
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    kate = core.detect_kate()
    if editor:
        os.system(f'{editor} "{USER_CONFIG}"')
    elif kate:
        run(*kate.cmd, "-n", "--startanon", "-b", str(USER_CONFIG), quiet=True)
    else:
        print(USER_CONFIG)
        return
    if ask("Apply the changes now?"):
        args.yes = True
        do_apply(args)


# ======================================================================= menu

def do_menu(args):
    state = core.load_state()
    banner("Notepad++ comfort for Kate")
    if not state:
        print("  Not installed yet on this account.\n")
        if ask("Install now?"):
            args.yes = True
            do_apply(args, first_install=True)
        return
    print(f"  {DIM}profile{RESET} {state.get('profile')}   {DIM}theme{RESET} "
          f"{theme_display_name(state.get('theme_source')) or 'Kate default'}   "
          f"{DIM}overlay{RESET} {state.get('overlay_hotkey') or 'off'}\n")
    items = [("Apply settings", "re-apply config.ini", do_apply),
             ("Edit settings", "open config.ini", do_config),
             ("Pick a theme", "browse themes with a live preview", do_pick_theme),
             ("Regenerate theme", "after changing colours", do_theme),
             ("Snapshot now", "back up sessions & unsaved tabs", do_backup),
             ("Restore a snapshot", "bring back older tabs", do_restore),
             ("Health check", "find problems", do_doctor),
             ("Update", "get the latest Kate++", do_update),
             ("Uninstall", "remove Kate++, keep your notes", do_uninstall)]
    for i, (name, hint, _) in enumerate(items, 1):
        print(f"   {ACCENT}{i}{RESET}  {name:<20} {DIM}{hint}{RESET}")
    choice = core.prompt("\n  Choose (Enter = quit)")
    if not choice.isdigit() or not 1 <= int(choice) <= len(items):
        return
    args.yes, args.quiet, args.snapshot, args.print = False, False, None, False
    fn = items[int(choice) - 1][2]
    fn(args)


# ======================================================================= entry

def main(argv=None):
    p = argparse.ArgumentParser(prog=APP, description="Kate++ — Notepad++ comfort for Kate.")
    p.add_argument("--version", action="version", version=f"Kate++ {VERSION}")
    sub = p.add_subparsers(dest="cmd")
    for name, help_ in (("install", "first-time setup"), ("apply", "re-apply config.ini")):
        s = sub.add_parser(name, help=help_)
        s.add_argument("-y", "--yes", action="store_true", help="don't ask questions")
        s.add_argument("--profile", choices=("auto", "caelestia", "generic"))
        s.add_argument("--hotkey", help='notepad overlay key, e.g. "SUPER + J"')
        s.add_argument("--overlay", action="store_true", help="turn on the pop-up notepad (Caelestia)")
        s.add_argument("--no-overlay", action="store_true")
        s.add_argument("--no-default-editor", action="store_true")
        s.add_argument("--no-backups", action="store_true")
    t = sub.add_parser("theme", help="regenerate the editor theme, or --pick one with a live preview")
    t.add_argument("--quiet", action="store_true")
    t.add_argument("--pick", action="store_true", help="browse all themes with a live preview")
    sub.add_parser("backup", help="snapshot sessions & unsaved tabs").add_argument("--quiet", action="store_true")
    sub.add_parser("maintain", help="background job: snapshots + keep the Language menu").add_argument(
        "--quiet", action="store_true")
    sub.add_parser("restore", help="restore a snapshot").add_argument("snapshot", nargs="?")
    sub.add_parser("doctor", help="health check")
    sub.add_parser("update", help="update Kate++")
    sub.add_parser("uninstall", help="remove Kate++").add_argument("-y", "--yes", action="store_true")
    sub.add_parser("config", help="edit config.ini").add_argument("--print", action="store_true")
    args = p.parse_args(argv)

    if getattr(args, "quiet", False):
        core.QUIET = True
    for attr in ("yes", "quiet", "snapshot", "print", "pick"):
        if not hasattr(args, attr):
            setattr(args, attr, False if attr != "snapshot" else None)

    if args.cmd in ("install", "apply"):
        overrides = {}
        if args.profile:
            overrides[("general", "profile")] = args.profile
        if args.hotkey:
            overrides[("features", "notepad-hotkey")] = args.hotkey
        if args.overlay or args.hotkey:
            overrides[("features", "notepad-overlay")] = "true"
        if args.no_overlay:
            overrides[("features", "notepad-overlay")] = "false"
        if args.no_default_editor:
            overrides[("features", "default-editor")] = "false"
        if args.no_backups:
            overrides[("features", "backups")] = "false"
        if overrides:
            core.ensure_user_config(overrides)
        first = args.cmd == "install" and not core.load_state()
        return do_apply(args, first_install=first)

    handlers = {"theme": do_theme, "backup": do_backup, "maintain": do_maintain, "restore": do_restore, "doctor": do_doctor,
                "update": do_update, "uninstall": do_uninstall, "config": do_config}
    if args.cmd in handlers:
        return handlers[args.cmd](args)
    if sys.stdin.isatty() or Path("/dev/tty").exists():
        return do_menu(args)
    p.print_help()
