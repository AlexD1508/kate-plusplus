# AUR package

The files here are what gets pushed to `ssh://aur@aur.archlinux.org/kate-plusplus.git`.

## Releasing a new version

```bash
# 1. tag and publish the GitHub release (vX.Y.Z), then:
cd packaging/aur
sed -i 's/^pkgver=.*/pkgver=X.Y.Z/; s/^pkgrel=.*/pkgrel=1/' PKGBUILD
updpkgsums                         # from pacman-contrib: refreshes sha256sums
makepkg -f && makepkg --printsrcinfo > .SRCINFO
# 2. copy PKGBUILD, .SRCINFO and kate-plusplus.install into the AUR clone, commit, push
```

`updpkgsums` comes from `pacman-contrib`; without it, run `sha256sum` on the
release tarball and paste the value into `sha256sums`.
