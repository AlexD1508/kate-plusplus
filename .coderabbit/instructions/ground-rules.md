---
id: kpp-ground-rules
name: Kate++ ground rules
---

Kate++ configures Kate for the user; it never patches Kate itself. Review every change against these rules:

1. **Never lose user data.** Kate sessions, stashed unsaved tabs and snapshots under `~/.local/share/kate*` belong to the user. Nothing may delete or overwrite them without a snapshot first (`make_backup`).
2. **Edits to other programs' files must be surgical and reversible.** `katerc`, session files, `mimeapps.list`, kxmlgui shortcut files, Hyprland and Caelestia configs must be changed key-by-key (`core.merge_rc`), as a marked block (`core.set_block`), or by merging XML elements. They must be written atomically (`core.atomic_write`), and `kate-plusplus uninstall` must restore exactly what was there before. Flag any new write that uninstall does not undo.
3. **Shortcuts are merged, never replaced.** Do not use KDE shortcut *schemes* (`[Shortcut Schemes] Current Scheme`): a scheme replaces every shortcut and once left Kate without Backspace, Delete or arrow keys. Overrides go through `lib/kpp/shortcuts.py` into `kxmlgui5/<component>/<file>` with a version lower than the built-in one.
4. **Works everywhere.** Python 3.9+ standard library only. No hard dependency on Caelestia, KDE Plasma, Hyprland or systemd; every integration must degrade gracefully when its tool is missing. Native and Flatpak Kate must both work (`core.Kate` paths, never hard-coded `~/.config`).
5. **Readable themes.** The theme engine's contrast floors (text ≥ 10:1, tokens ≥ 6:1, comments ≥ 4.6:1) must hold for any user accent or background.
6. **Tests stay sandboxed.** Tests use a throw-away `$HOME` and `KPP_TEST=1` so they never touch the developer's real session, systemd or compositor.
