#!/usr/bin/env bash
# Build superdrag_<version>_<arch>.deb from the PyInstaller folder in dist.
#   usage: packaging/linux/build-deb.sh 1.1.0
set -euo pipefail
VERSION="${1:-1.1.0}"
ARCH="$(dpkg --print-architecture)"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PKG="$ROOT/build/deb/superdrag_${VERSION}_${ARCH}"
rm -rf "${PKG:?}"
mkdir -p "$PKG/DEBIAN" "$PKG/opt" "$PKG/usr/bin" "$PKG/usr/share/applications" \
         "$PKG/usr/share/doc/superdrag"

SRC_DIR="$ROOT/dist/superdrag"
BIN_NAME="superdrag"
if [ ! -d "$SRC_DIR" ] && [ -d "$ROOT/dist/dragshift" ]; then
  SRC_DIR="$ROOT/dist/dragshift"
  BIN_NAME="dragshift"
elif [ ! -d "$SRC_DIR" ] && [ -d "$ROOT/dist/SuperDrag" ]; then
  SRC_DIR="$ROOT/dist/SuperDrag"
  BIN_NAME="SuperDrag"
fi

cp -a "$SRC_DIR" "$PKG/opt/superdrag"
ln -s /opt/superdrag/"$BIN_NAME" "$PKG/usr/bin/superdrag"
ln -s /opt/superdrag/"$BIN_NAME" "$PKG/usr/bin/dragshift" 2>/dev/null || true
install -m644 "$ROOT/packaging/linux/dragshift.desktop" "$PKG/usr/share/applications/"
if [ -f "$ROOT/packaging/linux/superdrag.desktop" ]; then
  install -m644 "$ROOT/packaging/linux/superdrag.desktop" "$PKG/usr/share/applications/"
fi
for s in 16 24 32 48 64 128 256 512; do
  d="$PKG/usr/share/icons/hicolor/${s}x${s}/apps"; mkdir -p "$d"
  ICON_SRC="$ROOT/dragshift/assets/superdrag.png"
  if [ ! -f "$ICON_SRC" ]; then ICON_SRC="$ROOT/dragshift/assets/dragshift.png"; fi
  python3 -c "from PIL import Image; Image.open('$ICON_SRC').resize(($s,$s), Image.LANCZOS).save('$d/superdrag.png')"
  cp "$d/superdrag.png" "$d/dragshift.png"
done
install -m644 "$ROOT/LICENSE" "$PKG/usr/share/doc/superdrag/copyright"
SIZE=$(du -sk "$PKG" | cut -f1)
cat > "$PKG/DEBIAN/control" <<CTRL
Package: superdrag
Version: $VERSION
Section: graphics
Priority: optional
Architecture: $ARCH
Installed-Size: $SIZE
Depends: libc6 (>= 2.36), libx11-6, libxext6, libxrender1, libxkbcommon0, libxkbcommon-x11-0, libxcb1, libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0, libxcb-xfixes0, libxcb-xinerama0, libxcb-xkb1, libfontconfig1, libfreetype6, libdbus-1-3, libegl1, libgl1, libglib2.0-0
Recommends: xdg-utils
Maintainer: Manish <https://github.com/officialgodgoku/SuperDrag>
Homepage: https://github.com/officialgodgoku/SuperDrag
Description: Convert and edit files with a Shift+drag radial menu
 Start dragging a file in your file manager (Thunar, Nautilus, Nemo...),
 press Shift and drop it on a slice of the liquid-glass menu: convert
 images, PDFs, Word and text files, compress, resize, crop, annotate,
 redact and more. Works on X11 desktops including XFCE, with or without
 a compositor. Right-click > Open With > SuperDrag works everywhere.
CTRL
cat > "$PKG/DEBIAN/postinst" <<'POST'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t /usr/share/icons/hicolor || true
exit 0
POST
cp "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/postrm"
chmod 755 "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/postrm"
mkdir -p "$ROOT/dist"
dpkg-deb --build --root-owner-group "$PKG" "$ROOT/dist/SuperDrag-linux-${ARCH}.deb"
cp "$ROOT/dist/SuperDrag-linux-${ARCH}.deb" "$ROOT/dist/DragShift-linux-${ARCH}.deb"
ls -la "$ROOT/dist/"*.deb
