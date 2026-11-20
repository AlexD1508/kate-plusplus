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
CREATED = "kate-plusplus-created"      # on an <ActionProperties> section Kate++ had to create
OWNED = {"text": "Prettify", "icon": "tools-wizard"}   # attributes Kate++ sets on the action


def _owner(attr):
    return f"kate-plusplus-{attr}"     # present while the attribute is Kate++'s own value


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


def finalize(kate):
    """Last uninstall step (after the shortcut entries are gone): remove a section this module
    had to create, once it is empty again."""
    path = _file(kate)
    if not path.exists():
        return
    try:
        doc = minidom.parse(str(path))
    except Exception:  # noqa: BLE001 - unreadable: leave it alone
        return
    props = _root_child(doc, "ActionProperties")
    if props is not None and props.getAttribute(CREATED) == "true" and _empty(props, {CREATED}):
        props.parentNode.removeChild(props)
        _save(path, doc)


def _empty(el, own_attrs) -> bool:
    """No elements, comments or text inside, and no attributes but `own_attrs`."""
    if any(n.nodeType != n.TEXT_NODE or n.data.strip() for n in el.childNodes):
        return False
    return set(el.attributes.keys()) <= set(own_attrs)


def _pretty(doc):
    return "\n".join(line for line in doc.toprettyxml(indent=" ").splitlines() if line.strip())


def _save(path, doc):
    # through a symlink (e.g. a dotfiles repo) to its target, keeping the link and the mode
    core.atomic_write(path.resolve(), _pretty(doc) + "\n")


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
        props.setAttribute(CREATED, "true")
        doc.documentElement.appendChild(props)
    action = next((a for a in props.getElementsByTagName("Action") if a.getAttribute("name") == ACTION), None)
    if action is None:
        # normally Kate++'s shortcut entry is already here; if you removed it, the entry is
        # re-created with the shortcut module's own marker, so a single owner removes it again
        action = doc.createElement("Action")
        action.setAttribute("name", ACTION)
        action.setAttribute(MARK, "true")
        props.appendChild(action)
    for attr, value in OWNED.items():          # the name also shows in Edit → "Prettify"
        if action.hasAttribute(_owner(attr)):
            if action.getAttribute(attr) != value:   # changed by you since: yours from now on
                action.removeAttribute(_owner(attr))
        elif not action.hasAttribute(attr):
            action.setAttribute(attr, value)
            action.setAttribute(_owner(attr), "true")
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
            if a.getAttribute("name") != ACTION:
                continue
            for attr, value in OWNED.items():
                if a.hasAttribute(_owner(attr)):
                    if a.getAttribute(attr) == value:   # still Kate++'s: take it out again
                        a.removeAttribute(attr)
                    a.removeAttribute(_owner(attr))
                    changed = True
    if changed:
        _save(path, doc)
