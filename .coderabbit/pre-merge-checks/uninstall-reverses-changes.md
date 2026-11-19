---
id: uninstall-reverses-changes
name: Uninstall reverses every change
mode: error
paths:
  - "lib/**"
  - "config/**"
  - "shortcuts/**"
  - "systemd/**"
  - "hyprland/**"
  - "desktop/**"
---

Fail if this PR makes Kate++ write a new file, setting, shortcut or association in the user's home directory and `do_uninstall` in `lib/kpp/cli.py` does not remove it or restore the previous value. Pass if the PR adds no new writes, or if every new write has a matching removal or restore.
