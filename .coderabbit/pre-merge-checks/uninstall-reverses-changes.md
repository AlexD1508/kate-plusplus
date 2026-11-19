---
id: uninstall-reverses-changes
name: Uninstall reverses every change
mode: error
---

Fail if this PR makes Kate++ write anything new on disk (a file, a setting, a shortcut, a file association, a systemd unit, a compositor or shell config entry), from any file in the repository and wherever it lands (including `$XDG_CONFIG_HOME` / `$XDG_DATA_HOME` / `$XDG_STATE_HOME` when they point outside `$HOME`), and `kate-plusplus uninstall` (`do_uninstall` in `lib/kpp/cli.py`) does not reverse it exactly:

- something Kate++ **created** must be removed;
- something Kate++ **overwrote** must be restored to the **exact previous value**; deleting it is not enough, because the user's original value would be lost.

**User data is exempt and must be kept:** snapshots made by `make_backup` (in `~/.local/share/kate-plusplus/backups/`), Kate sessions and stashed unsaved tabs, and the user's `~/.config/kate-plusplus/config.ini`. Uninstall intentionally keeps these.

Pass if the PR adds no new writes, or if every new write has a matching removal or exact restore.
