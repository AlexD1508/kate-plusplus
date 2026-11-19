"""Notepad++-style "Language" menu on Kate's menu bar.

Kate already has the full, grouped list of languages (the Tools → Highlighting submenu,
action `tools_highlighting`). Kate++ places that same action directly on the menu bar and
names it "Language". This lives in Kate's own per-user menu file
(~/.local/share/kxmlgui5/katepart/katepart5ui.rc), which Kate writes in full the first time
it starts and rebuilds after Kate updates, so Kate++ (re)adds the entry on `apply` and from
its background job.
"""
from __future__ import annotations

import xml.dom.minidom as minidom

from . import core

ACTION = "tools_highlighting"
MARK = "kate-plusplus"            # on elements Kate++ created
ORIG = "kate-plusplus-orig-text"  # on a user's element Kate++ relabelled: its previous text
LABEL = "&Language"


def _file(kate):
    return kate.data / "kxmlgui5" / "katepart" / "katepart5ui.rc"


def _menubar(doc):
    for el in doc.documentElement.getElementsByTagName("MenuBar"):
        if el.parentNode is doc.documentElement:
            return el
    return None


def _save(path, doc):
    text = doc.toprettyxml(indent=" ")
    core.atomic_write(path, "\n".join(l for l in text.splitlines() if l.strip()) + "\n", 0o644)


def _top_entries(bar):
    return [n for n in bar.childNodes if n.nodeType == n.ELEMENT_NODE
            and n.tagName == "Action" and n.getAttribute("name") == ACTION]


def _props(doc):
    return next((n for n in doc.documentElement.childNodes if n.nodeType == n.ELEMENT_NODE
                 and n.tagName == "ActionProperties"), None)


def status(kate) -> str:
    """present | missing | pending (Kate hasn't written its full menu file yet)."""
    path = _file(kate)
    if not path.exists():
        return "pending"
    bar = _menubar(minidom.parse(str(path)))
    if bar is None:
        return "pending"
    return "present" if _top_entries(bar) else "missing"


def ensure(kate) -> str:
    st = status(kate)
    if st != "missing":
        return st          # already there (Kate++'s or the user's own): leave it alone
    path = _file(kate)
    doc = minidom.parse(str(path))
    bar = _menubar(doc)
    entry = doc.createElement("Action")
    entry.setAttribute("name", ACTION)
    entry.setAttribute(MARK, "true")
    settings = next((n for n in bar.childNodes if n.nodeType == n.ELEMENT_NODE
                     and n.tagName == "Menu" and n.getAttribute("name") == "settings"), None)
    bar.insertBefore(entry, settings) if settings is not None else bar.appendChild(entry)
    props = _props(doc)
    if props is None:
        props = doc.createElement("ActionProperties")
        doc.documentElement.appendChild(props)
    label = next((a for a in props.getElementsByTagName("Action")
                  if a.getAttribute("name") == ACTION), None)
    if label is None:                       # ours: removed again on uninstall
        label = doc.createElement("Action")
        label.setAttribute("name", ACTION)
        label.setAttribute(MARK, "true")
        props.appendChild(label)
    elif not label.hasAttribute(MARK) and not label.hasAttribute(ORIG):
        label.setAttribute(ORIG, label.getAttribute("text"))   # the user's: remember their text
    label.setAttribute("text", LABEL)
    _save(path, doc)
    return "present"


def remove(kate):
    """Undo only what Kate++ did: its menu-bar entry and its label."""
    path = _file(kate)
    if not path.exists():
        return
    doc = minidom.parse(str(path))
    changed = False
    bar = _menubar(doc)
    if bar is not None:
        for n in _top_entries(bar):
            if n.getAttribute(MARK) == "true":
                bar.removeChild(n)
                changed = True
    props = _props(doc)
    if props is not None:
        for a in list(props.getElementsByTagName("Action")):
            if a.getAttribute("name") != ACTION:
                continue
            if a.getAttribute(MARK) == "true":
                props.removeChild(a)
                changed = True
            elif a.hasAttribute(ORIG):
                orig = a.getAttribute(ORIG)
                a.removeAttribute(ORIG)
                if orig:
                    a.setAttribute("text", orig)
                elif a.hasAttribute("text"):
                    a.removeAttribute("text")
                changed = True
    if changed:
        _save(path, doc)
