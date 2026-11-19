---
id: uninstall-reverses-changes
name: Uninstall reverses every change
mode: error
---

Fail if this PR makes Kate++ write anything new in the user's home directory (a file, a setting, a shortcut, a file association, a systemd unit, a compositor or shell config entry), from any file in the repository, and `kate-plusplus uninstall` (`do_uninstall` in `lib/kpp/cli.py`) does not reverse it exactly:

- something Kate++ **created** must be removed;
- something Kate++ **overwrote** must be restored to the **exact previous value**; deleting it is not enough, because the user's original value would be lost.

Pass if the PR adds no new writes, or if every new write has a matching removal or exact restore.
