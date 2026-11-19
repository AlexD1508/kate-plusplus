"""Notepad++ shortcuts, merged the way Kate's own "Configure Shortcuts" dialog stores them.

KDE apps read per-user shortcut changes from ~/.local/share/kxmlgui5/<component>/<file>.
When that local file has a *lower* version than the app's built-in one, KXMLGUI keeps the
built-in menus and merges only the <ActionProperties> from the local file, so exactly the
listed shortcuts change and every other key keeps its default.

(Kate++ 1.0.0 used a KDE "shortcut scheme" instead. Schemes replace *all* shortcuts with the
ones they list, which left Backspace, Delete, arrows, … without keys.)
"""
from __future__ import annotations

import shutil
import xml.dom.minidom as minidom
from pathlib import Path

from . import core

LOCAL_VERSION = "1"          # lower than any built-in version → merge, never replace
MARK = "kate-plusplus"       # attribute on actions we own, so uninstall removes only ours
LEGACY_SCHEME = "Notepad++"


def overrides(repo: Path):
    """[(component, file, [(action, shortcut), ...]), ...] from shortcuts/*.xml."""
    out = []
    for f in sorted((repo / "shortcuts").glob("*.xml")):
        root = minidom.parse(str(f)).documentElement
        actions = [(a.getAttribute("name"), a.getAttribute("shortcut"))
                   for a in root.getElementsByTagName("Action")]
        out.append((root.getAttribute("component"), root.getAttribute("file"), actions))
    return out


def _target(kate, component, file):
    return kate.data / "kxmlgui5" / component / file


def _load_or_new(path: Path, component: str):
    if path.exists():
        try:
            return minidom.parse(str(path))
        except Exception:  # unreadable: keep a copy and start fresh
            shutil.copy2(path, path.with_suffix(path.suffix + ".broken"))
    impl = minidom.getDOMImplementation()
    doctype = impl.createDocumentType("gui", None, "kpartgui.dtd")
    doc = impl.createDocument(None, "gui", doctype)
    doc.documentElement.setAttribute("name", component)
    doc.documentElement.setAttribute("version", LOCAL_VERSION)
    return doc


def _action_properties(doc):
    root = doc.documentElement
    for el in root.getElementsByTagName("ActionProperties"):
        if el.parentNode is root:
            return el
    el = doc.createElement("ActionProperties")
    el.setAttribute("scheme", "Default")
    root.appendChild(el)
    return el


def _save(path: Path, doc):
    text = doc.toprettyxml(indent=" ")
    text = "\n".join(line for line in text.splitlines() if line.strip()) + "\n"
    core.atomic_write(path, text, 0o644)


def install(kate, repo: Path, state: dict):
    """Merge our overrides; remember what each action was before so uninstall can restore it."""
    before = state.setdefault("shortcuts_before", {})
    for component, file, actions in overrides(repo):
        path = _target(kate, component, file)
        key = f"{component}/{file}"
        if key not in before:
            before[key] = {"existed": path.exists(), "actions": {}}
        doc = _load_or_new(path, component)
        props = _action_properties(doc)
        existing = {a.getAttribute("name"): a for a in props.getElementsByTagName("Action")}
        for name, shortcut in actions:
            el = existing.get(name)
            if el is None:
                el = doc.createElement("Action")
                el.setAttribute("name", name)
                props.appendChild(el)
                before[key]["actions"].setdefault(name, None)
            elif not el.hasAttribute(MARK):
                before[key]["actions"].setdefault(name, el.getAttribute("shortcut"))
            el.setAttribute("shortcut", shortcut)
            el.setAttribute(MARK, "true")
        _save(path, doc)
    remove_legacy_scheme(kate)


def uninstall(kate, repo: Path, state: dict):
    before = state.get("shortcuts_before", {})
    for component, file, _ in overrides(repo):
        path = _target(kate, component, file)
        info = before.get(f"{component}/{file}", {"existed": True, "actions": {}})
        if not path.exists():
            continue
        doc = _load_or_new(path, component)
        props = _action_properties(doc)
        for el in list(props.getElementsByTagName("Action")):
            if el.getAttribute(MARK) != "true":
                continue
            old = info["actions"].get(el.getAttribute("name"))
            if old is None:
                props.removeChild(el)
            else:
                el.setAttribute("shortcut", old)
                el.removeAttribute(MARK)
        user_entries = [a for a in props.getElementsByTagName("Action") if a.getAttribute(MARK) != "true"]
        if not info.get("existed") and not user_entries:
            path.unlink()      # Kate++ created it and nothing of the user's is in it
        else:
            _save(path, doc)   # keep shortcuts the user changed in Kate after installing
    remove_legacy_scheme(kate)


def remove_legacy_scheme(kate):
    """Clean up the 1.0.0 shortcut-scheme files and switch Kate back to its default scheme."""
    for comp in ("kate", "katepart", "keyboardmacros"):
        f = kate.data / comp / "shortcuts" / LEGACY_SCHEME
        if f.exists():
            f.unlink()
            for d in (f.parent, f.parent.parent):
                try:
                    d.rmdir()
                except OSError:
                    break
    if core.read_rc_value(kate.katerc, "[Shortcut Schemes]", "Current Scheme") == LEGACY_SCHEME:
        core.merge_rc(kate.katerc, [("[Shortcut Schemes]", "Current Scheme", "@delete")])


def installed(kate, repo: Path) -> bool:
    for component, file, actions in overrides(repo):
        path = _target(kate, component, file)
        if not path.exists():
            return False
        names = {a.getAttribute("name") for a in minidom.parse(str(path)).getElementsByTagName("Action")
                 if a.getAttribute(MARK) == "true"}
        if not {n for n, _ in actions} <= names:
            return False
    return True
