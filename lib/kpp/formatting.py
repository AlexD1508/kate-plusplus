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
    file; older Kate always reads <config>/kate/formatting/settings.json. None for a relative
    configPath, which Kate resolves against whatever directory it was started from."""
    custom = (core.read_rc_value(kate.katerc, "[kateformatplugin]", "configPath")
              if _kate_at_least(kate, CONFIG_PATH_MIN_KATE) else None)
    if custom and not Path(custom).expanduser().is_absolute():
        return None   # Kate reads it relative to its own working directory: unknowable here
    path = Path(custom).expanduser() if custom else kate.config / "kate" / "formatting" / "settings.json"
    return _canonical(path)


def _canonical(path) -> Path:
    """One identity per file: absolute, '..' and symlinks resolved, so aliases share a record."""
    return Path(path).expanduser().resolve()


def shortcut_supported(kate) -> bool:
    return _kate_at_least(kate, SHORTCUT_MIN_KATE)


def _parse(text):
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except (TypeError, ValueError):
        return None


def _without_key(data):
    return {k: v for k, v in data.items() if k != "formatOnSave"}


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
    if path is None:
        core.warn("Kate's Format plugin uses a relative configPath, so its file depends on where "
                  "Kate is started; leaving format-on-save as it is (use an absolute path)")
        return
    try:
        text = path.read_text(encoding="utf-8") if path.exists() else None
    except OSError:
        text = None
    data = {} if not path.exists() else _parse(text)
    if data is None:
        core.warn(f"{path} isn't valid JSON; leaving format-on-save as it is")
        return
    records = _records(state)
    if str(path) not in records:
        # recorded once per file, and saved before the file changes, so a later failure in
        # the same apply can never make a retry record Kate++'s own value as the original
        records[str(path)] = {"existed": path.exists(), "had_key": "formatOnSave" in data,
                              "value": data.get("formatOnSave"), "text": text}
        core.save_state(state)
    data["formatOnSave"] = enabled
    core.atomic_write(path, json.dumps(data, indent=4) + "\n")   # keeps an existing file's mode


def restore(kate, state) -> list:
    """Put every settings file Kate++ changed back the way it was. A file nobody else has
    edited since gets its original bytes back; otherwise only formatOnSave is reverted, so
    later edits stay. Records of restored files are dropped; the paths that could not be
    restored (unreadable, invalid JSON, not writable) are returned and keep their records."""
    records = _records(state)
    left = []
    for raw_path, before in list(records.items()):
        path = Path(raw_path)
        try:
            if path.exists():
                _restore_one(path, before)
        except (OSError, ValueError) as e:
            core.warn(f"couldn't restore {path} ({e})")
            left.append(raw_path)
            continue
        del records[raw_path]
    return left


def _restore_one(path, before):
    data = _parse(path.read_text(encoding="utf-8"))
    if data is None:
        raise ValueError("not a JSON object")
    original = before.get("text")
    if before["existed"] and original is not None:
        orig_data = _parse(original)
        if orig_data is not None and _without_key(orig_data) == _without_key(data):
            core.atomic_write(path, original)   # untouched since: the exact original bytes
            return
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
