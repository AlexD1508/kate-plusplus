---
id: kpp-python
name: Python (CLI and engine)
paths:
  - "lib/**/*.py"
  - "bin/kate-plusplus"
  - "tools/**/*.py"
---

- Must run on Python 3.9: keep `from __future__ import annotations` in modules with `X | Y` annotations, and avoid `match`, `str.removeprefix`-style 3.9-only APIs in runtime paths, and 3.10+ stdlib features.
- Subprocesses: pass argument lists, never `shell=True` or string-built commands with config values. `core.run` already handles missing tools.
- User-facing output goes through `core.step/info/warn/fail` so `--quiet` and colours keep working.
- Values from `~/.config/kate-plusplus/config.ini` are untrusted: validate them (colours via `theme.norm`, numbers clamped) and fall back with a `warn`, never a traceback.
