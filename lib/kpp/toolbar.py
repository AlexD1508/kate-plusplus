"""A "Prettify" button on Kate's main toolbar (next to Undo / Redo).

Kate's Format plugin describes its GUI in kxmlgui5/formatplugin/ui.rc; the built-in file has
an empty main-toolbar section meant for exactly this. Kate writes the full file to your
config the first time it starts (with Kate++'s shortcut in it), and Kate++ then adds the
`format_document` action to that toolbar section and gives it a name and an icon. Until
Kate has written the full file the button is "pending"; `apply` and the background job add
it later. Kate++ marks what it adds, so uninstall removes exactly that.
"""
from __future__ import annotations

import xml.dom.minidom as minidom

from . import core

ACTION = "format_document"
MARK = "kate-plusplus"                 # on the toolbar entry Kate++ added
LABEL_MARK = "kate-plusplus-label"     # on the action whose text/icon Kate++ set
TEXT = "Prettify"
ICON = "tools-wizard"


def _file(kate):
    return kate.data / "kxmlgui5" / "formatplugin" / "ui.rc"


def _root_child(doc, tag, name=None):
    return next((n for n in doc.documentElement.childNodes if n.nodeType == n.ELEMENT_NODE
                 and n.tagName == tag and (name is None or n.getAttribute("name") == name)), None)


def _toolbar(doc):
    return _root_child(doc, "ToolBar", "mainToolBar")


def _entries(bar):
    return [n for n in bar.childNodes if n.nodeType == n.ELEMENT_NODE
            and n.tagName == "Action" and n.getAttribute("name") == ACTION]


def _pretty(doc):
    return "\n".join(line for line in doc.toprettyxml(indent=" ").splitlines() if line.strip())


def _save(path, doc):
    core.atomic_write(path, _pretty(doc) + "\n", 0o644)


def status(kate) -> str:
    """present | missing | pending (Kate hasn't written the plugin's full GUI file yet)."""
    path = _file(kate)
    if not path.exists():
        return "pending"
    try:
        bar = _toolbar(minidom.parse(str(path)))
    except Exception:  # noqa: BLE001 - a file being rewritten: try again later
        return "pending"
    if bar is None:
        return "pending"
    return "present" if _entries(bar) else "missing"


def ensure(kate) -> str:
    path = _file(kate)
    if status(kate) == "pending":
        return "pending"
    original = path.read_text(encoding="utf-8")
    doc = minidom.parseString(original)
    bar = _toolbar(doc)
    if not _entries(bar):                      # a button of the user's own stays as it is
        entry = doc.createElement("Action")
        entry.setAttribute("name", ACTION)
        entry.setAttribute(MARK, "true")
        bar.appendChild(entry)
    props = _root_child(doc, "ActionProperties")
    if props is None:
        props = doc.createElement("ActionProperties")
        doc.documentElement.appendChild(props)
    action = next((a for a in props.getElementsByTagName("Action") if a.getAttribute("name") == ACTION), None)
    if action is None:
        action = doc.createElement("Action")
        action.setAttribute("name", ACTION)
        props.appendChild(action)
    if action.getAttribute(LABEL_MARK) == "true" or not (action.hasAttribute("text") or action.hasAttribute("icon")):
        action.setAttribute("text", TEXT)     # also the name in Edit → so both read "Prettify"
        action.setAttribute("icon", ICON)
        action.setAttribute(LABEL_MARK, "true")
    if _pretty(doc) != _pretty(minidom.parseString(original)):
        _save(path, doc)
    return "present"


def remove(kate):
    """Undo only what Kate++ added: its toolbar entry and the name/icon it set."""
    path = _file(kate)
    if not path.exists():
        return
    try:
        doc = minidom.parse(str(path))
    except Exception:  # noqa: BLE001 - unreadable: leave it alone
        return
    changed = False
    bar = _toolbar(doc)
    if bar is not None:
        for n in _entries(bar):
            if n.getAttribute(MARK) == "true":
                bar.removeChild(n)
                changed = True
    props = _root_child(doc, "ActionProperties")
    if props is not None:
        for a in props.getElementsByTagName("Action"):
            if a.getAttribute("name") == ACTION and a.getAttribute(LABEL_MARK) == "true":
                for attr in ("text", "icon", LABEL_MARK):
                    if a.hasAttribute(attr):
                        a.removeAttribute(attr)
                changed = True
    if changed:
        _save(path, doc)
