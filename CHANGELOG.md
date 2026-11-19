# Changelog

All notable changes to Kate++ are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Language menu** on the menu bar, like Notepad++: pick a language for any tab, including
  unsaved drafts. If a Kate update rebuilds its menus, the background job re-adds it within
  10 minutes (systemd); otherwise run `kate-plusplus apply`.
- **Matching window colours:** picking a theme now colours Kate's whole window (menus, tabs,
  sidebars, status bar) to match. `window-colors = match | system`; a scheme you pick in
  Kate after installing is never overwritten, and uninstall restores your previous one.
- <kbd>Ctrl</kbd>+<kbd>T</kbd> opens a new tab (Ctrl+N still works). Transpose Characters
  moves off Ctrl+T and stays available in the command bar.
- **Ten popular themes** Kate doesn't ship, built from their official palettes and lifted to
  WCAG AA contrast: Rosé Pine (Main, Moon, Dawn), Kanagawa (Wave, Dragon, Lotus),
  Everforest (Dark, Light), Night Owl and Synthwave '84.
- `source` in `config.ini` accepts **any theme by name**, including every theme that ships
  with Kate (`Catppuccin Mocha`, `Dracula`, `Nord`, …). Family names (`rose-pine`,
  `kanagawa`, `everforest`) follow your system's light/dark preference.

### Fixed
- The opt-in pop-up notepad no longer overwrites a `org.kde.kate.desktop` launcher override
  you made yourself (uninstall used to delete it afterwards).
- Uninstall now restores **exactly** the value each Kate setting had before Kate++, even
  when you skip restoring the full settings backup (previously those keys were deleted).
- Uninstall keeps shortcuts you added in Kate after installing Kate++ (shortcuts Kate++ itself
  set go back to their earlier values).

## [1.0.1] — 2026-11-19

### Fixed
- **Backspace, Delete, arrows and other keys stopped working** after install. 1.0.0 used a
  KDE shortcut *scheme*, which replaces every shortcut with the few it lists. Kate++ now
  merges its Notepad++ shortcuts into Kate's own shortcut files, so only those keys change
  and your own shortcut customisations are kept. Upgrading cleans up the old scheme.
- Kate++ no longer tries to hide the menu bar and toolbar (Kate 26 ignores that at startup;
  Notepad++ has both anyway).
- Theme: a token colour that would clash with your accent now moves to the most open hue
  instead of colliding with another token (types and strings could match on gold wallpapers).

### Changed
- The pop-up notepad hotkey is now **opt-in** (`kate-plusplus install --overlay`).
- Redesigned FAQ.

### Added
- Regression test that starts a real Kate and verifies its live shortcuts.

## [1.0.0] — 2026-11-19

First release.

### Added
- **Session memory**: Kate opens straight into your "Notepad" session; unsaved
  tabs and edits are stashed on close, no save prompts.
- **Notepad++ shortcut scheme**: duplicate line, replace, comment, delete line,
  case, macros; switchable back to Kate's defaults at any time.
- **Notepad++ Tools**: format/minify JSON, Base64 and URL encode/decode, insert
  date/time, remove empty/duplicate lines, trim trailing spaces.
- **Harmonised themes**: Kate++ Caelestia (follows the wallpaper), Kate++ Plasma
  (follows KDE colours), Kate++ Dark and Light; accent/background overrides and
  soft/balanced/vivid syntax colours, all contrast-checked.
- **Pop-up notepad** on Super+J for Caelestia + Hyprland.
- **Safety snapshots** every 10 minutes with `kate-plusplus restore`.
- Kate as default editor for text, Markdown, JSON, YAML, logs and config files.
- `kate-plusplus` CLI and menu: install, apply, config, theme, backup, restore,
  doctor, update, uninstall.
- Native and Flatpak Kate support; one-line installer; AUR package.

[1.0.1]: https://github.com/AlexD1508/kate-plusplus/releases/tag/v1.0.1
[1.0.0]: https://github.com/AlexD1508/kate-plusplus/releases/tag/v1.0.0
