---
id: aur-consistency
name: AUR package is consistent
mode: error
paths:
  - "packaging/aur/**"
---

Fail if `pkgver`, `pkgrel`, the source URL or `sha256sums` in `packaging/aur/PKGBUILD` disagree with `packaging/aur/.SRCINFO`, or if `sha256sums` is `SKIP`.
