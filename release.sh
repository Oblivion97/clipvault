#!/usr/bin/env bash
# ClipVault Release Builder
# Usage: ./release.sh <version>
# Example: ./release.sh 1.3.0

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GREEN}✔  $*${NC}"; }
info() { echo -e "${CYAN}▶  $*${NC}"; }
warn() { echo -e "${YELLOW}⚠  $*${NC}"; }
err()  { echo -e "${RED}✘  $*${NC}"; exit 1; }
hdr()  { echo -e "\n${BOLD}$*${NC}"; }

# ── Validate input ────────────────────────────────────────────────────────────
VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
    err "Usage: ./release.sh <version>  (e.g. ./release.sh 1.3.0)"
fi
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    err "Version must be in format X.Y.Z (e.g. 1.3.0)"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="$SCRIPT_DIR/dist/v$VERSION"
DEB_STAGING="$SCRIPT_DIR/packaging/deb/clipvault_${VERSION}"

hdr "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
hdr "  ClipVault Release Builder  v$VERSION"
hdr "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

mkdir -p "$DIST_DIR"

# ── Step 1: Bump version in source files ──────────────────────────────────────
hdr "── Step 1: Bumping version to $VERSION"

# clipvault.py
sed -i "s/^VERSION *= *'[^']*'/VERSION = '$VERSION'/" "$SCRIPT_DIR/clipvault.py"
ok "clipvault.py"


# AUR PKGBUILD
sed -i "s/^pkgver=.*/pkgver=$VERSION/" "$SCRIPT_DIR/packaging/aur/PKGBUILD"
sed -i "s/YOUR_USERNAME/Oblivion97/g" "$SCRIPT_DIR/packaging/aur/PKGBUILD"
ok "PKGBUILD"

# README install URL
sed -i "s/clipvault-[0-9]*\.[0-9]*\.[0-9]*\.zip/clipvault-${VERSION}.zip/g" \
    "$SCRIPT_DIR/README.md"
ok "README.md"

# ── Step 2: Build .deb ────────────────────────────────────────────────────────
hdr "── Step 2: Building .deb"

rm -rf "$DEB_STAGING"
mkdir -p "$DEB_STAGING/DEBIAN"
mkdir -p "$DEB_STAGING/usr/share/clipvault/assets"
mkdir -p "$DEB_STAGING/usr/bin"
mkdir -p "$DEB_STAGING/usr/share/applications"
mkdir -p "$DEB_STAGING/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$DEB_STAGING/etc/xdg/autostart"

# DEBIAN/control
cat > "$DEB_STAGING/DEBIAN/control" << EOF
Package: clipvault
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, gir1.2-gdkpixbuf-2.0, wl-clipboard | xdotool, python3-pynput
Maintainer: H M Mahmudul Hasan <mahmudul.uiu041@gmail.com>
Homepage: https://github.com/Oblivion97/clipvault
Description: Windows-style clipboard history for Linux
 ClipVault brings the Windows 11 clipboard history experience to Linux.
 Press Win+V to open a searchable popup of everything you have copied —
 text, links, code snippets and images — then click or press Enter to paste.
 .
 Features:
  - Win+V opens clipboard history from anywhere
  - Stores up to 200 items, persists across reboots
  - Image capture with live preview thumbnails
  - Instant search and filter
  - Settings page with privacy and behaviour options
  - Wayland and X11 support
  - Auto-starts silently at login
EOF

# DEBIAN scripts
cat > "$DEB_STAGING/DEBIAN/postinst" << 'EOF'
#!/bin/bash
set -e
if ! python3 -c "import pynput" 2>/dev/null; then
    pip3 install --quiet pynput 2>/dev/null || true
fi
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
fi
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi
echo "ClipVault installed. Press Win+V to open clipboard history."
EOF

cat > "$DEB_STAGING/DEBIAN/prerm" << 'EOF'
#!/bin/bash
set -e
pkill -f clipvault.py 2>/dev/null || true
EOF

cat > "$DEB_STAGING/DEBIAN/postrm" << 'EOF'
#!/bin/bash
set -e
if [ "$1" = "purge" ]; then
    rm -rf /etc/xdg/autostart/clipvault.desktop
    if command -v gtk-update-icon-cache &>/dev/null; then
        gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
    fi
fi
EOF

# Launcher
cat > "$DEB_STAGING/usr/bin/clipvault" << 'EOF'
#!/bin/bash
exec python3 /usr/share/clipvault/clipvault.py "$@"
EOF

# Desktop entries
cat > "$DEB_STAGING/usr/share/applications/clipvault.desktop" << 'EOF'
[Desktop Entry]
Name=ClipVault
GenericName=Clipboard Manager
Comment=Windows-style clipboard history — press Win+V
Exec=clipvault
Icon=clipvault
Terminal=false
Type=Application
Categories=Utility;GTK;
Keywords=clipboard;copy;paste;history;
StartupNotify=false
EOF

cat > "$DEB_STAGING/etc/xdg/autostart/clipvault.desktop" << 'EOF'
[Desktop Entry]
Name=ClipVault
Comment=Clipboard history daemon
Exec=clipvault
Icon=clipvault
Terminal=false
Type=Application
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=3
EOF

# Copy files
cp "$SCRIPT_DIR/clipvault.py"              "$DEB_STAGING/usr/share/clipvault/clipvault.py"
cp -r "$SCRIPT_DIR/assets/."               "$DEB_STAGING/usr/share/clipvault/assets/"
cp "$SCRIPT_DIR/assets/icon_256.png"       "$DEB_STAGING/usr/share/icons/hicolor/256x256/apps/clipvault.png"

# Permissions
chmod 755 "$DEB_STAGING/DEBIAN/postinst" "$DEB_STAGING/DEBIAN/prerm" "$DEB_STAGING/DEBIAN/postrm"
chmod 755 "$DEB_STAGING/usr/bin/clipvault"
chmod 644 "$DEB_STAGING/usr/share/clipvault/clipvault.py"
chmod 644 "$DEB_STAGING/usr/share/applications/clipvault.desktop"
chmod 644 "$DEB_STAGING/etc/xdg/autostart/clipvault.desktop"

DEB_OUT="$DIST_DIR/clipvault_${VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$DEB_STAGING" "$DEB_OUT"
ok ".deb → $DEB_OUT"

# ── Step 3: Build .zip (for manual install via install.sh) ────────────────────
hdr "── Step 3: Building .zip"

ZIP_STAGING="$SCRIPT_DIR/packaging/zip_staging/clipvault-$VERSION"
rm -rf "$ZIP_STAGING"
mkdir -p "$ZIP_STAGING"

cp "$SCRIPT_DIR/clipvault.py"   "$ZIP_STAGING/"
cp "$SCRIPT_DIR/install.sh"     "$ZIP_STAGING/"
cp "$SCRIPT_DIR/uninstall.sh"   "$ZIP_STAGING/"
cp "$SCRIPT_DIR/README.md"      "$ZIP_STAGING/"
cp "$SCRIPT_DIR/LICENSE"        "$ZIP_STAGING/"
cp "$SCRIPT_DIR/CHANGELOG.md"   "$ZIP_STAGING/"
cp -r "$SCRIPT_DIR/assets"      "$ZIP_STAGING/"

ZIP_OUT="$DIST_DIR/clipvault-${VERSION}.zip"
(cd "$SCRIPT_DIR/packaging/zip_staging" && zip -r "$ZIP_OUT" "clipvault-$VERSION" -x "*.pyc" -x "*__pycache__*")
rm -rf "$SCRIPT_DIR/packaging/zip_staging"
ok ".zip → $ZIP_OUT"

# ── Step 4: Update AUR sha256 ─────────────────────────────────────────────────
hdr "── Step 4: Updating AUR PKGBUILD sha256"
SHA256=$(sha256sum "$ZIP_OUT" | awk '{print $1}')
sed -i "s/sha256sums=('SKIP')/sha256sums=('$SHA256')/" "$SCRIPT_DIR/packaging/aur/PKGBUILD" || true
ok "sha256: $SHA256"

# ── Step 5: Build .rpm (Fedora / openSUSE) ───────────────────────────────────
hdr "── Step 5: Building .rpm"

if ! command -v rpmbuild &>/dev/null; then
    info "rpmbuild not found — installing rpm tools..."
    sudo apt-get install -y rpm 2>/dev/null || warn "Could not install rpm tools — skipping .rpm build"
fi

if command -v rpmbuild &>/dev/null; then
    RPM_BUILD="$SCRIPT_DIR/packaging/rpm/build"
    rm -rf "$RPM_BUILD"
    mkdir -p "$RPM_BUILD"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

    # Update version in spec
    SPEC_TMP="$RPM_BUILD/SPECS/clipvault.spec"
    cp "$SCRIPT_DIR/packaging/rpm/clipvault.spec" "$SPEC_TMP"
    sed -i "s/^Version:.*/Version:        $VERSION/" "$SPEC_TMP"
    sed -i "s/^Source0:.*/Source0:        clipvault-$VERSION.zip/" "$SPEC_TMP"

    # Put the zip in SOURCES
    cp "$ZIP_OUT" "$RPM_BUILD/SOURCES/clipvault-$VERSION.zip"

    rpmbuild -bb "$SPEC_TMP" \
        --define "_topdir $RPM_BUILD" \
        --define "_builddir $RPM_BUILD/BUILD" \
        --define "_rpmdir $RPM_BUILD/RPMS" 2>&1 | tail -5

    RPM_FILE=$(find "$RPM_BUILD/RPMS" -name "*.rpm" | head -1)
    if [[ -n "$RPM_FILE" ]]; then
        RPM_OUT="$DIST_DIR/clipvault-${VERSION}.noarch.rpm"
        cp "$RPM_FILE" "$RPM_OUT"
        ok ".rpm → $RPM_OUT"
    else
        warn ".rpm build failed — check spec file"
    fi
    rm -rf "$RPM_BUILD"
else
    warn "Skipping .rpm — rpmbuild not available"
fi

# ── Step 6: Sync website screenshot ──────────────────────────────────────────
hdr "── Step 6: Syncing website screenshot"
if [[ -f "$SCRIPT_DIR/assets/screenshot.png" ]]; then
    cp "$SCRIPT_DIR/assets/screenshot.png" "$SCRIPT_DIR/docs/screenshot.png"
    ok "docs/screenshot.png synced"
else
    warn "assets/screenshot.png not found — skipping screenshot sync"
fi

# ── Step 7: Git tag + GitHub release ─────────────────────────────────────────
hdr "── Step 7: Git commit, tag and GitHub release"

cd "$SCRIPT_DIR"
git add -A
git commit -m "Release v$VERSION" || true
git tag "v$VERSION" 2>/dev/null || warn "Tag v$VERSION already exists — skipping"
git push origin master --tags
ok "Pushed to GitHub"

# Upload all dist files as GitHub release assets
if command -v gh &>/dev/null; then
    info "Creating GitHub release v$VERSION..."
    ASSETS=()
    for f in "$DIST_DIR"/*.deb "$DIST_DIR"/*.zip "$DIST_DIR"/*.rpm; do
        [[ -f "$f" ]] && ASSETS+=("$f")
    done
    gh release create "v$VERSION" \
        --title "ClipVault v$VERSION" \
        --notes "See [CHANGELOG.md](https://github.com/Oblivion97/clipvault/blob/master/CHANGELOG.md) for what's new." \
        "${ASSETS[@]}"
    ok "GitHub release created with ${#ASSETS[@]} assets"
else
    warn "gh CLI not found — install it to auto-upload: sudo apt install gh"
    echo "  Manual upload: go to https://github.com/Oblivion97/clipvault/releases/new"
fi

hdr "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}${BOLD}Release v$VERSION complete!${NC}"
hdr "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
