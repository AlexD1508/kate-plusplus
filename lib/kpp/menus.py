"""Notepad++-style "Language" menu on Kate's menu bar.

With Kate's language list available (languages.py) it is an A–Z menu: A, B, C, … submenus of
one action per language, and "All Languages" (Kate's own grouped list) at the bottom.
Without it, Kate's grouped list itself sits on the menu bar, named "Language".

Kate already has the full, grouped list of languages (the Tools → Highlighting submenu,
action `tools_highlighting`). Kate++ places that same action directly on the menu bar and
names it "Language". This lives in Kate's own per-user menu file
(~/.local/share/kxmlgui5/katepart/katepart5ui.rc), which Kate writes in full the first time
it starts and rebuilds after Kate updates, so Kate++ (re)adds the entry on `apply` and from
its background job.
"""
from __future__ import annotations

import xml.dom.minidom as minidom

from . import core, languages as langs

ACTION = "tools_highlighting"
MARK = "kate-plusplus"            # on elements Kate++ created
ORIG = "kate-plusplus-orig-text"  # on a user's element Kate++ relabelled: its previous text
LABEL = "&Language"              # Kate's grouped list when it is the whole menu
ALL_LABEL = "All Languages"       # … and when it is the last entry of the A–Z menu
MENU = "kpp_language"             # the A–Z menu element


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


def _ours(bar):
    """Kate++'s menu-bar elements: the A–Z menu and/or the plain grouped-list entry."""
    return [n for n in bar.childNodes if n.nodeType == n.ELEMENT_NODE and n.getAttribute(MARK) == "true"
            and ((n.tagName == "Menu" and n.getAttribute("name") == MENU)
                 or (n.tagName == "Action" and n.getAttribute("name") == ACTION))]


def _users_own(bar):
    return [n for n in _top_entries(bar) if n.getAttribute(MARK) != "true"]


def status(kate) -> str:
    """present | missing | pending (Kate hasn't written its full menu file yet)."""
    path = _file(kate)
    if not path.exists():
        return "pending"
    bar = _menubar(minidom.parse(str(path)))
    if bar is None:
        return "pending"
    return "present" if _ours(bar) or _users_own(bar) else "missing"


def _el(doc, tag, name=None, text=None):
    el = doc.createElement(tag)
    if name:
        el.setAttribute("name", name)
    if text is not None:
        t = doc.createElement("text")
        t.appendChild(doc.createTextNode(text))
        el.appendChild(t)
    return el


def _az_menu(doc, languages):
    menu = _el(doc, "Menu", MENU, "&Language")
    menu.setAttribute(MARK, "true")
    for letter, names in langs.groups(languages):
        if len(names) == 1:                     # like Notepad++: a lone language sits directly
            menu.appendChild(_el(doc, "Action", langs.action_name(names[0])))
            continue
        sub = _el(doc, "Menu", f"{MENU}_{'num' if letter == '#' else letter}", letter)
        for n in names:
            sub.appendChild(_el(doc, "Action", langs.action_name(n)))
        menu.appendChild(sub)
    menu.appendChild(doc.createElement("Separator"))
    menu.appendChild(_el(doc, "Action", ACTION))  # Kate's grouped list: every language
    return menu


def ensure(kate, languages=()) -> str:
    """Put Kate++'s Language menu on the menu bar (A–Z when `languages` is given), replacing
    an older Kate++ entry. A grouped-list entry of the user's own is left alone."""
    path = _file(kate)
    if not path.exists():
        return "pending"
    original = path.read_text(encoding="utf-8")
    doc = minidom.parseString(original)
    bar = _menubar(doc)
    if bar is None:
        return "pending"
    if _users_own(bar):
        return "present"
    for n in _ours(bar):
        bar.removeChild(n)
    if languages:
        entry = _az_menu(doc, languages)
    else:
        entry = _el(doc, "Action", ACTION)
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
    label.setAttribute("text", ALL_LABEL if languages else LABEL)
    if _pretty(doc) != _pretty(minidom.parseString(original)):   # unchanged: don't touch the file
        _save(path, doc)
    return "present"


def _pretty(doc):
    return "\n".join(l for l in doc.toprettyxml(indent=" ").splitlines() if l.strip())


def remove(kate):
    """Undo only what Kate++ did: its menu-bar entries and its label."""
    path = _file(kate)
    if not path.exists():
        return
    doc = minidom.parse(str(path))
    changed = False
    bar = _menubar(doc)
    if bar is not None:
        for n in _ours(bar):
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
