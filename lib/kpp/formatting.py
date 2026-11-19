"""Kate's Format plugin: format-on-save switch and formatter overview.

The plugin's user settings live in <Kate config>/kate/formatting/settings.json, or (Kate
26.08+) in the file named by katerc `[kateformatplugin] configPath` when that is set, resolved
the way Kate does, and are merged over its built-in defaults, which turn formatOnSave ON. Kate++ only
manages the one `formatOnSave` key, records the file and its previous value before changing
it, and restores exactly that on uninstall.

The Format plugin reads per-user shortcuts (kxmlgui5/formatplugin/ui.rc) from Kate 24.08 on;
older Kate builds its menu from inline XML, so the Prettify shortcut needs Kate 24.08+.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import core

# (command, what it formats, install hint); Kate's defaults: jq for JSON, ruff for Python,
# yamlfmt for YAML, prettier for JS/TS/CSS/HTML, clang-format for C/C++, … (no Markdown)
FORMATTERS = [
    ("prettier", "JS, TS, CSS, HTML", "npm i -g prettier"),
    ("ruff", "Python", "pip install ruff"),
    ("jq", "JSON", "install jq"),
    ("clang-format", "C, C++", "install clang"),
    ("shfmt", "Shell", "install shfmt"),
    ("yamlfmt", "YAML", "go install github.com/google/yamlfmt/cmd/yamlfmt@latest"),
    ("rustfmt", "Rust", "rustup component add rustfmt"),
    ("gofmt", "Go", "comes with Go"),
    ("xmllint", "XML", "install libxml2"),
]
POPULAR = ("prettier", "ruff", "jq", "clang-format", "shfmt")


SHORTCUT_MIN_KATE = (24, 8)


CONFIG_PATH_MIN_KATE = (26, 8)   # first release whose Format plugin reads configPath


def _kate_at_least(kate, version) -> bool:
    try:
        return tuple(int(x) for x in kate.version.split(".")[:2]) >= version
    except ValueError:
        return True   # unknown version: assume a current Kate


def settings_path(kate):
    """Mirror Kate: from 26.08 a non-empty [kateformatplugin] configPath wins over the default
    file; older Kate always reads <config>/kate/formatting/settings.json."""
    custom = (core.read_rc_value(kate.katerc, "[kateformatplugin]", "configPath")
              if _kate_at_least(kate, CONFIG_PATH_MIN_KATE) else None)
    path = Path(custom).expanduser() if custom else kate.config / "kate" / "formatting" / "settings.json"
    return _canonical(path)


def _canonical(path) -> Path:
    """One identity per file: absolute, '..' and symlinks resolved, so aliases share a record."""
    return Path(path).expanduser().resolve()


def shortcut_supported(kate) -> bool:
    return _kate_at_least(kate, SHORTCUT_MIN_KATE)


def _read(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _records(state):
    """Restore records, one per settings file Kate++ has changed: {path: record}."""
    rec = state.setdefault("format_before", {})
    if "path" in rec:   # single-record layout from an earlier development build
        rec = {rec["path"]: {k: v for k, v in rec.items() if k != "path"}}
    merged = {}
    for raw, record in rec.items():   # normalise keys; the first baseline of a file wins
        merged.setdefault(str(_canonical(raw)), record)
    state["format_before"] = merged
    return merged


def set_format_on_save(kate, state, enabled: bool):
    path = settings_path(kate)
    data = _read(path) if path.exists() else {}
    if data is None:
        core.warn(f"{path} isn't valid JSON; leaving format-on-save as it is")
        return
    records = _records(state)
    if str(path) not in records:
        # recorded once per file, and saved before the file changes, so a later failure in
        # the same apply can never make a retry record Kate++'s own value as the original
        records[str(path)] = {"existed": path.exists(), "had_key": "formatOnSave" in data,
                              "value": data.get("formatOnSave")}
        core.save_state(state)
    data["formatOnSave"] = enabled
    core.atomic_write(path, json.dumps(data, indent=4) + "\n")   # keeps an existing file's mode


def restore(kate, state):
    """Put every settings file Kate++ changed back the way it was."""
    for raw_path, before in _records(state).items():
        path = Path(raw_path)
        if not path.exists():
            continue
        data = _read(path)
        if data is None:
            continue
        if before["had_key"]:
            data["formatOnSave"] = before["value"]
        else:
            data.pop("formatOnSave", None)
        if not before["existed"] and not data:
            path.unlink()
        else:
            core.atomic_write(path, json.dumps(data, indent=4) + "\n")


def installed():
    return [(cmd, what) for cmd, what, _ in FORMATTERS if core.have(cmd)]
