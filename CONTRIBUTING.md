# Contributing to Kate++

Thanks for wanting to help! Kate++ is small on purpose: it *configures* Kate and
never patches it. Good contributions keep it that way.

## Ways to help

- **Report a bug**: use the [bug form](https://github.com/AlexD1508/kate-plusplus/issues/new?template=bug_report.yml)
  and paste the output of `kate-plusplus doctor`.
- **Suggest a feature**, especially Notepad++ habits you miss in Kate.
- **Share a theme**: post your `[theme]` settings and a screenshot in the
  [theme showcase](https://github.com/AlexD1508/kate-plusplus/issues/new?template=theme_showcase.yml).
- **Test on your distro**: tell us what worked.

## Project layout

| Path | What |
|---|---|
| `bin/kate-plusplus` | entry point |
| `lib/kpp/cli.py` | commands: install/apply, theme, backup, restore, doctor, … |
| `lib/kpp/core.py` | detection, config, safe edits of other programs' files |
| `lib/kpp/theme.py` | the harmonised theme engine (OKLCH, contrast checks) |
| `config/kate.ini` | the Kate settings Kate++ manages |
| `config/config.ini` | template for the user's `~/.config/kate-plusplus/config.ini` |
| `shortcuts/` | the Notepad++ shortcut scheme (per KDE component) |
| `kate-scripts/` | the Notepad++ Tools (Kate JavaScript commands) |
| `hyprland/`, `desktop/`, `systemd/` | overlay, launcher entry, timers |
| `tools/make-gallery.py` | regenerates the README theme images |
| `packaging/aur/` | AUR PKGBUILD |

## Ground rules

1. **Never lose user data.** Anything that edits a file Kate++ doesn't own must
   be key-by-key or marked-block based, atomic, and reversible by `uninstall`.
2. **Readable first.** Theme changes must keep the contrast floors in
   `theme.py` (text ≥ 10:1, tokens ≥ 6:1, comments ≥ 4.6:1).
3. **Works everywhere.** Python 3.9+ standard library only; no hard dependency
   on Caelestia, Plasma, Hyprland or systemd.

## Before opening a pull request

```bash
python3 -m py_compile lib/kpp/*.py
node tests/kate-scripts.test.js kate-scripts/kate-plusplus.js
bash tests/sandbox-install.sh          # full install/uninstall in a throw-away $HOME
```

`KPP_TEST=1` makes the CLI skip `systemctl` and `hyprctl`, so tests never touch
your real session.
