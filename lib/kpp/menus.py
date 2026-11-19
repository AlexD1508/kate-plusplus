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
MARK = "kate-plusplus"
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


def status(kate) -> str:
    """present | missing | pending (Kate hasn't written its full menu file yet)."""
    path = _file(kate)
    if not path.exists():
        return "pending"
    doc = minidom.parse(str(path))
    bar = _menubar(doc)
    if bar is None:
        return "pending"
    top = [n for n in bar.childNodes if n.nodeType == n.ELEMENT_NODE
           and n.tagName == "Action" and n.getAttribute("name") == ACTION]
    return "present" if top else "missing"


def ensure(kate) -> str:
    st = status(kate)
    if st != "missing":
        return st
    path = _file(kate)
    doc = minidom.parse(str(path))
    bar = _menubar(doc)
    entry = doc.createElement("Action")
    entry.setAttribute("name", ACTION)
    entry.setAttribute(MARK, "true")
    settings = next((n for n in bar.childNodes if n.nodeType == n.ELEMENT_NODE
                     and n.tagName == "Menu" and n.getAttribute("name") == "settings"), None)
    bar.insertBefore(entry, settings) if settings is not None else bar.appendChild(entry)
    props = next((n for n in doc.documentElement.childNodes if n.nodeType == n.ELEMENT_NODE
                  and n.tagName == "ActionProperties"), None)
    if props is None:
        props = doc.createElement("ActionProperties")
        doc.documentElement.appendChild(props)
    label = next((a for a in props.getElementsByTagName("Action")
                  if a.getAttribute("name") == ACTION), None)
    if label is None:
        label = doc.createElement("Action")
        label.setAttribute("name", ACTION)
        props.appendChild(label)
    label.setAttribute("text", LABEL)
    label.setAttribute(MARK, "true")
    _save(path, doc)
    return "present"


def remove(kate):
    path = _file(kate)
    if not path.exists():
        return
    doc = minidom.parse(str(path))
    changed = False
    bar = _menubar(doc)
    if bar is not None:
        for n in list(bar.childNodes):
            if n.nodeType == n.ELEMENT_NODE and n.tagName == "Action" and n.getAttribute("name") == ACTION:
                bar.removeChild(n)
                changed = True
    for props in doc.documentElement.getElementsByTagName("ActionProperties"):
        for a in list(props.getElementsByTagName("Action")):
            if a.getAttribute("name") == ACTION and a.hasAttribute("text"):
                a.removeAttribute("text")
                changed = True
                if not a.getAttribute("shortcut"):
                    props.removeChild(a)
    if changed:
        _save(path, doc)
