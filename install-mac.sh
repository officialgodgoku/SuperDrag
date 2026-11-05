#!/bin/bash
# SuperDrag installer for macOS.
#   curl -fsSL https://raw.githubusercontent.com/officialgodgoku/SuperDrag/main/install-mac.sh | bash
# Downloads the right build for this Mac from the latest GitHub release, installs it to
# /Applications and opens it. Files fetched by curl aren't marked "downloaded from the
# internet", so macOS doesn't show the "could not verify" warning. Read it first if you like —
# it's short.
set -euo pipefail

REPO="officialgodgoku/SuperDrag"
case "$(uname -m)" in
  arm64) ASSET="SuperDrag-mac-apple-silicon.dmg" ;;
  *)     ASSET="SuperDrag-mac-intel.dmg" ;;
esac
URL="https://github.com/$REPO/releases/latest/download/$ASSET"
TMP="$(mktemp -d)"
trap 'hdiutil detach "$TMP/mnt" -quiet 2>/dev/null || true; rm -rf "$TMP"' EXIT

echo "→ Downloading $ASSET"
curl -fL --progress-bar "$URL" -o "$TMP/SuperDrag.dmg"

echo "→ Installing to /Applications"
hdiutil attach "$TMP/SuperDrag.dmg" -mountpoint "$TMP/mnt" -nobrowse -quiet
osascript -e 'quit app "SuperDrag"' 2>/dev/null || true
pkill -x SuperDrag 2>/dev/null || true

SRC_APP="$TMP/mnt/SuperDrag.app"
DEST="/Applications/SuperDrag.app"
if [ -w /Applications ]; then
  rm -rf "$DEST"; ditto "$SRC_APP" "$DEST"
else
  sudo rm -rf "$DEST"; sudo ditto "$SRC_APP" "$DEST"
fi
xattr -dr com.apple.quarantine "$DEST" 2>/dev/null || true

echo "→ Opening SuperDrag (look for it in the menu bar)"
open "$DEST"
echo "✓ Done. Drag any file in Finder and press Shift."
