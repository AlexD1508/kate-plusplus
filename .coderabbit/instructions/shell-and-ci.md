---
id: kpp-shell-ci
name: Installer, tests and CI
paths:
  - "install.sh"
  - "tests/**"
  - "tools/**/*.sh"
  - ".github/workflows/**"
---

- `install.sh` is run as `curl … | bash`: it must work without a TTY, never need root, and only clone into the user's data directory.
- Shell scripts use `set -euo pipefail` and quote every variable.
- Tests must never touch the real user session: throw-away `$HOME`, `KPP_TEST=1`, and offscreen Kate (`QT_QPA_PLATFORM=offscreen` inside `dbus-run-session`).
