"""Kate plugins (Function list, Folder browser, Preview, Snippets, Format, …).

Kate reads which plugins are on from the *session* file ([Kate Plugins] in
~/.local/share/kate/sessions/*.katesession and anonymous.katesession), not from katerc:
KatePluginManager::loadConfig() is given the session config. So Kate++ switches its plugins
on in every session file.

Each plugin is switched on once per session file: its previous value is recorded first
(plugins_before), and the plugin counts as done only after the write succeeded (plugins_done),
so a failed write is retried. If you turn a plugin off in Kate afterwards, Kate++ leaves it
off. Uninstall puts back the recorded value, but only where the plugin is still on (a later
change of yours stays).
"""
from __future__ import annotations

from pathlib import Path

from . import core

GROUP = "[Kate Plugins]"


def wanted(repo: Path):
    """The plugins config/kate.ini switches on."""
    return [k for g, k, v in core.read_settings_ini(repo / "config/kate.ini")
            if g == GROUP and v.strip().lower() == "true"]


def _mode(path: Path):
    return path.stat().st_mode & 0o777 if path.exists() else 0o600


def pending(repo: Path, state: dict, files) -> list:
    """Session files with plugins Kate++ hasn't switched on yet."""
    done = state.get("plugins_done", {})
    plugins = wanted(repo)
    return [Path(f) for f in files if any(k not in done.get(str(f), []) for k in plugins)]


def enable(repo: Path, state: dict, files) -> int:
    """Switch the wanted plugins on in each session file (once per file and plugin).
    Returns how many session files changed."""
    records = state.setdefault("plugins_before", {})
    done = state.setdefault("plugins_done", {})
    plugins = wanted(repo)
    changed = 0
    for f in pending(repo, state, files):
        rec = records.setdefault(str(f), {})
        todo = [k for k in plugins if k not in done.get(str(f), [])]
        if any(k not in rec for k in todo):
            for k in todo:
                rec.setdefault(k, core.read_rc_value(f, GROUP, k))   # the first baseline wins
            core.save_state(state)   # recorded before the file changes
        core.merge_rc(f, [(GROUP, k, "true") for k in todo], _mode(f))
        done[str(f)] = sorted(set(done.get(str(f), [])) | set(todo))   # only after the write
        core.save_state(state)
        changed += 1
    return changed


def restore(state: dict):
    """Put back each plugin Kate++ switched on, unless it was changed since."""
    for f, rec in state.get("plugins_before", {}).items():
        path = Path(f)
        if not path.exists():
            continue
        changes = [(GROUP, k, "@delete" if old is None else old) for k, old in rec.items()
                   if old != "true" and core.read_rc_value(path, GROUP, k) == "true"]
        if changes:
            core.merge_rc(path, changes, _mode(path))
