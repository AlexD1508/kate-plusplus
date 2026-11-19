---
id: kpp-packaging
name: AUR packaging
paths:
  - "packaging/**"
---

- `pkgver`, the source URL tag and `sha256sums` must describe the same released tag, and `.SRCINFO` must match `PKGBUILD` (it is generated with `makepkg --printsrcinfo`).
- The package installs runtime files only (no README media) under `/usr/share/kate-plusplus`, plus the `/usr/bin` wrapper, icon and license.
