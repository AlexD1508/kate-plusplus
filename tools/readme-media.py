#!/usr/bin/env python3
"""Shoot the README screenshots with real Kate windows, without touching your own Kate.

Every scene is a throw-away $HOME with a fresh `kate-plusplus install` (or none, for stock
Kate), its own private D-Bus, and a fullscreen (opaque) window on an invisible headless
Hyprland monitor, captured with grim. Only your Qt style (qtengine / kdeglobals) and the
Caelestia colour scheme are copied in, so the shots look like your desktop. Hyprland only.

    python3 tools/readme-media.py OUT_DIR [scene ...]

Scenes: stock, kpp, languages, prettify, panels, theme-<source> (e.g. theme-dark,
theme-rose-pine). Then build the animations with tools/make-before-after.py (stock → Kate++)
and tools/make-crossfade.py (theme tour, Prettify).

The demo files go to /tmp/Notes (a short path in Kate's breadcrumbs). The tool creates that
folder itself and refuses to run if it already exists, so it never deletes anything of yours.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
sys.path.insert(0, str(ROOT / "lib"))
from kpp import core  # noqa: E402

NOTES_PY = '''import json, os
from dataclasses import dataclass

# Load notes and count words  (TODO: cache results)
@dataclass
class Note:
    title: str
    words: int = 0
    pinned: bool = False


def load(path: str, limit: int = 0x40) -> list[Note]:
    """Read every Markdown note under *path*."""
    notes = []
    for name in sorted(os.listdir(path))[:limit]:
        if not name.endswith(".md"):
            continue
        with open(f"{path}/{name}", encoding="utf-8") as f:
            text = f.read()
        notes.append(Note(name.removesuffix(".md"), len(text.split())))
    return notes or [Note("empty", 0)]


def summary(notes: list[Note]) -> dict:
    total = sum(n.words for n in notes)
    return {"notes": len(notes), "words": total, "avg": round(total / max(len(notes), 1), 1)}


if __name__ == "__main__":
    print(json.dumps(summary(load(os.path.expanduser("~/Notes"))), indent=2))
'''

IDEAS_MD = '''# Weekend ideas

A quick list, nothing serious. **Kate++** keeps it even if I never save.

## Projects
- [x] Theme picker with a live preview
- [ ] Tiny CLI that counts my notes
- [ ] Try *Rosé Pine* for a week

## Groceries
| Item    | Qty |
|---------|-----|
| Coffee  | 2   |
| Oranges | 6   |

> Tip: Ctrl+Alt+Shift+B tidies the whole file.
'''

CONFIG_JSON = '''{
  "theme": "auto",
  "editor": { "font": "JetBrains Mono", "size": 11, "minimap": true },
  "recent": ["notes.py", "ideas.md"],
  "backups": { "every_minutes": 10, "keep_days": 2 }
}
'''

MESSY_JSON = ('{"name":"kate-plusplus","themes":["caelestia","rose-pine","kanagawa"],"editor":{"font":'
              '"JetBrains Mono","size":11,"minimap":true,"ligatures":true},"backups":{"every_minutes":10,'
              '"keep_days":2},"shortcuts":{"duplicate_line":"Ctrl+D","prettify":"Ctrl+Alt+Shift+B"}}\n')

DEMO = {"config.json": CONFIG_JSON, "ideas.md": IDEAS_MD, "notes.py": NOTES_PY, "data.json": MESSY_JSON}
DEMO_DIR = Path("/tmp/Notes")


def sh(*cmd, env=None, check=True, quiet=True):
    return subprocess.run(cmd, env=env, check=check, text=True,
                          stdout=subprocess.PIPE if quiet else None,
                          stderr=subprocess.PIPE if quiet else None)


def hypr(expr):
    return sh("hyprctl", "dispatch", expr, check=False).stdout.strip()


class Monitor:
    """An invisible headless output; its workspace holds the fullscreen Kate."""

    def __enter__(self):
        before = {m["name"] for m in json.loads(sh("hyprctl", "monitors", "-j").stdout)}
        sh("hyprctl", "output", "create", "headless")
        time.sleep(1)
        new = [m for m in json.loads(sh("hyprctl", "monitors", "-j").stdout) if m["name"] not in before]
        self.name, self.ws = new[0]["name"], new[0]["activeWorkspace"]["id"]
        return self

    def __exit__(self, *exc):
        sh("hyprctl", "output", "remove", self.name, check=False)


def sandbox(work: Path, scene: str, kpp: bool, theme_source: str | None):
    home = work / scene
    (home / ".config").mkdir(parents=True)
    for src, dst in ((HOME / ".config/qtengine", home / ".config/qtengine"),
                     (HOME / ".config/kdeglobals", home / ".config/kdeglobals"),
                     (HOME / ".local/state/caelestia/scheme.json", home / ".local/state/caelestia/scheme.json")):
        if src.is_dir():
            shutil.copytree(src, dst)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    files = DEMO_DIR      # created (and owned) by main(); every scene rewrites the demo files
    for name, text in DEMO.items():
        (files / name).write_text(text, encoding="utf-8")
    if kpp:
        cfg = home / ".config/kate-plusplus/config.ini"
        cfg.parent.mkdir(parents=True)
        text = (ROOT / "config/config.ini").read_text(encoding="utf-8")
        text = text.replace("profile = auto", "profile = caelestia")
        if theme_source:
            text = "\n".join(f"source = {theme_source}" if line.startswith("source =") else line
                             for line in text.splitlines()) + "\n"
        cfg.write_text(text, encoding="utf-8")
        env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "KPP_TEST": "1",
               "XDG_CURRENT_DESKTOP": "Hyprland"}
        sh(sys.executable, str(ROOT / "bin/kate-plusplus"), "install", "--yes", env=env)
        # like a real first day: Kate starts once (it writes its full menu file and the session
        # layout), then apply adds the Language menu the background job would add
        first_run(home)
        sh(sys.executable, str(ROOT / "bin/kate-plusplus"), "apply", "--yes", env=env)
    return home, files


def first_run(home: Path):
    """Start Kate once offscreen and quit, so the session file holds the panel layout."""
    script = '''
    kate -n >/dev/null 2>&1 & pid=$!
    for _ in $(seq 60); do
        svc=$(gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
              --method org.freedesktop.DBus.ListNames | grep -o "org.kde.kate-[0-9]*" | head -1) || true
        [[ -n $svc ]] && gdbus introspect --session --dest "$svc" \
              --object-path /kate/MainWindow_1/actions/file_quit >/dev/null 2>&1 && break
        svc=
        sleep 0.5
    done
    if [[ -z $svc ]]; then kill $pid 2>/dev/null; echo "Kate did not start" >&2; exit 1; fi
    sleep 2
    if ! gdbus call --session --dest "$svc" --object-path /kate/MainWindow_1/actions/file_quit \
            --method org.qtproject.Qt.QAction.trigger >/dev/null; then
        kill $pid 2>/dev/null; echo "Kate did not quit" >&2; exit 1
    fi
    for _ in $(seq 40); do kill -0 $pid 2>/dev/null || exit 0; sleep 0.5; done
    kill $pid; echo "Kate did not quit in time" >&2; exit 1'''
    # a failure stops the scene: without the first-start layout the shot would be wrong
    sh("env", "-i", f"HOME={home}", "PATH=/usr/bin:/bin", "QT_QPA_PLATFORM=offscreen",
       "dbus-run-session", "--", "bash", "-c", script)


def show_panels(home: Path, visible):
    """Open the given side panels (tool-view ids) in the Notepad session."""
    f = home / ".local/share/kate/sessions/Notepad.katesession"
    lines = f.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        for tv in visible:
            if line.startswith(f"Kate-MDI-ToolView-{tv}-Visible="):
                line = f"Kate-MDI-ToolView-{tv}-Visible=true"
        out.append(line)
    f.write_text("\n".join(out) + "\n", encoding="utf-8")


def shoot(mon: Monitor, home: Path, files, out: Path, keys=(), settle=9, then=(), focus=False):
    """Capture `out` after `keys`; `then` = further (keys, out) captures in the same window.
    Without focus only plain letters reach the window; menus and shortcuts need `focus`,
    which borrows keyboard focus for a few seconds and gives it back afterwards."""
    args = " ".join(str(f) for f in files)
    session = "-s Notepad" if (home / ".local/share/kate/sessions/Notepad.katesession").exists() else ""
    cmd = (f"env HOME={home} XDG_CONFIG_HOME={home}/.config XDG_DATA_HOME={home}/.local/share "
           f"XDG_STATE_HOME={home}/.local/state XDG_CACHE_HOME={home}/.cache "
           f"dbus-run-session -- kate -n {session} {args}")
    hypr(f'hl.dsp.exec_cmd({json.dumps(cmd)}, {{ workspace = "{mon.ws} silent" }})')
    time.sleep(settle)
    pid = kate_pid(home)
    # fullscreen for Hyprland (opaque, no gaps, no wallpaper) but not for Kate, which would
    # otherwise add its own "Full Screen" button to the menu bar
    hypr(f'hl.dsp.window.fullscreen_state({{ internal = 2, client = 0, action = "set", window = "pid:{pid}" }})')
    time.sleep(1.5)
    back = None
    if focus:
        back = json.loads(sh("hyprctl", "activewindow", "-j").stdout or "{}").get("address")
        hypr(f'hl.dsp.focus({{ window = "pid:{pid}" }})')
        time.sleep(0.8)
    for mods, key, wait in keys:
        hypr(f'hl.dsp.send_shortcut({{ mods = "{mods}", key = "{key}", window = "pid:{pid}" }})')
        time.sleep(wait)
    sh("grim", "-o", mon.name, str(out))
    for more_keys, more_out in then:
        for mods, key, wait in more_keys:
            hypr(f'hl.dsp.send_shortcut({{ mods = "{mods}", key = "{key}", window = "pid:{pid}" }})')
            time.sleep(wait)
        sh("grim", "-o", mon.name, str(more_out))
    if back:
        hypr(f'hl.dsp.focus({{ window = "address:{back}" }})')
    stop(home)


def kate_pid(home: Path):
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            if (p / "comm").read_text().strip() == "kate" and \
                    f"HOME={home}".encode() in (p / "environ").read_bytes().split(b"\0"):
                return int(p.name)
        except OSError:
            continue
    return None


def stop(home: Path):
    pid = kate_pid(home)
    if pid:
        os.kill(pid, 15)
        time.sleep(1.5)


PANELS_LEFT = "kate_plugin_symbolviewer"
PANELS_RIGHT = "ktexteditorpreviewplugin"


def scene(mon, work, name, out):
    target = out / f"{name}.png"
    if name == "stock":
        home, d = sandbox(work, name, kpp=False, theme_source=None)
        shoot(mon, home, [d / f for f in DEMO], target)
    elif name == "kpp":
        home, d = sandbox(work, name, kpp=True, theme_source=None)
        show_panels(home, [PANELS_LEFT])
        shoot(mon, home, [d / f for f in DEMO], target)
    elif name == "languages":
        home, d = sandbox(work, name, kpp=True, theme_source=None)
        shoot(mon, home, [d / "notes.py"], target, focus=True,
              keys=[("ALT", "L", 1.0), ("", "Right", 1.0)] + [("", "Down", 0.15)] * 10 + [("", "Right", 1.0), ("", "Down", 0.3), ("", "Down", 0.8)])
    elif name == "panels":
        home, d = sandbox(work, name, kpp=True, theme_source=None)
        show_panels(home, [PANELS_LEFT, PANELS_RIGHT])
        shoot(mon, home, [d / "notes.py", d / "ideas.md"], target)
    elif name == "prettify":
        home, d = sandbox(work, name, kpp=True, theme_source=None)
        shoot(mon, home, [d / "data.json"], out / "prettify-before.png",
              focus=True, then=[([("CTRL ALT SHIFT", "B", 3.0)], out / "prettify-after.png")])
        target = out / "prettify-*.png"
    elif name.startswith("theme-"):
        home, d = sandbox(work, name, kpp=True, theme_source=name[len("theme-"):])
        shoot(mon, home, [d / "notes.py"], target)
    else:
        raise SystemExit(f"unknown scene {name}")
    core.info(f"shot {target}")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    out = Path(sys.argv[1]).resolve()
    try:
        DEMO_DIR.mkdir()   # ours from here on; never a folder that was already there
    except FileExistsError:
        raise SystemExit(f"{DEMO_DIR} already exists; move it away first "
                         "(this tool only removes a folder it created itself)")
    out.mkdir(parents=True, exist_ok=True)
    scenes = sys.argv[2:] or ["stock", "kpp", "languages", "panels"]
    with tempfile.TemporaryDirectory(prefix="kpp-media-") as w, Monitor() as mon:
        work = Path(w)
        try:
            for s in scenes:
                scene(mon, work, s, out)
        finally:
            for s in scenes:
                if (work / s).exists():
                    stop(work / s)
            shutil.rmtree(DEMO_DIR, ignore_errors=True)


if __name__ == "__main__":
    main()
