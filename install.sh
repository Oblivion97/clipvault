#!/usr/bin/env bash
# ClipVault Installer — compatible with Ubuntu, Fedora, Arch, openSUSE, and derivatives
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

say()  { echo -e "${CYAN}▶  $*${NC}"; }
ok()   { echo -e "${GREEN}✔  $*${NC}"; }
warn() { echo -e "${YELLOW}⚠  $*${NC}"; }
err()  { echo -e "${RED}✘  $*${NC}"; exit 1; }
hdr()  { echo -e "\n${BOLD}$*${NC}"; }

hdr "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
hdr "  📋  ClipVault Installer"
hdr "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/share/clipvault"
AUTOSTART_DIR="$HOME/.config/autostart"
APPS_DIR="$HOME/.local/share/applications"
IS_WAYLAND=false
[[ "${WAYLAND_DISPLAY:-}" != "" ]] && IS_WAYLAND=true

# ── Detect distro / package manager ──────────────────────────────────────────
detect_pm() {
    if   command -v apt-get &>/dev/null; then echo "apt"
    elif command -v dnf     &>/dev/null; then echo "dnf"
    elif command -v pacman  &>/dev/null; then echo "pacman"
    elif command -v zypper  &>/dev/null; then echo "zypper"
    elif command -v emerge  &>/dev/null; then echo "emerge"
    else echo "unknown"
    fi
}

PM=$(detect_pm)
say "Detected package manager: $PM"

# ── Install system packages ───────────────────────────────────────────────────
hdr "── Step 1: System packages"

install_pkgs() {
    case "$PM" in
        apt)
            sudo apt-get update -qq
            # Core GTK packages
            sudo apt-get install -y \
                python3-gi python3-gi-cairo \
                gir1.2-gtk-3.0 gir1.2-gdkpixbuf-2.0 \
                xdotool wl-clipboard \
                python3-pip libgirepository1.0-dev \
                2>&1 | grep -E '(newly installed|already newest|upgraded)' || true

            # pynput — try apt first (avoids externally-managed-environment)
            if apt-cache show python3-pynput &>/dev/null 2>&1; then
                sudo apt-get install -y python3-pynput 2>&1 | grep -E '(newly|already)' || true
            fi
            # Pillow
            if apt-cache show python3-pil &>/dev/null 2>&1; then
                sudo apt-get install -y python3-pil 2>&1 | grep -E '(newly|already)' || true
            fi
            # Wayland auto-paste tool
            if $IS_WAYLAND; then
                sudo apt-get install -y ydotool 2>&1 | grep -E '(newly|already)' || \
                    warn "ydotool not in repos — trying wtype as fallback"
                sudo apt-get install -y wtype 2>&1 | grep -E '(newly|already)' || true
            fi
            ;;

        dnf)
            sudo dnf install -y \
                python3-gobject python3-gobject-base \
                gtk3 python3-cairo \
                xdotool wl-clipboard python3-pip \
                gobject-introspection-devel gcc python3-devel \
                2>/dev/null || true
            if $IS_WAYLAND; then
                sudo dnf install -y ydotool 2>/dev/null || \
                sudo dnf install -y wtype   2>/dev/null || \
                    warn "No auto-paste tool found — you will press Ctrl+V manually"
            fi
            ;;

        pacman)
            sudo pacman -S --noconfirm --needed \
                python-gobject gtk3 python-cairo \
                xdotool wl-clipboard python-pip \
                2>/dev/null || true
            # pynput and pillow via pacman
            sudo pacman -S --noconfirm --needed \
                python-pynput python-pillow 2>/dev/null || true
            if $IS_WAYLAND; then
                sudo pacman -S --noconfirm --needed ydotool 2>/dev/null || \
                sudo pacman -S --noconfirm --needed wtype   2>/dev/null || \
                    warn "No auto-paste tool found — you will press Ctrl+V manually"
            fi
            ;;

        zypper)
            sudo zypper install -y --no-recommends \
                python3-gobject python3-gobject-cairo \
                typelib-1_0-Gtk-3_0 xdotool wl-clipboard python3-pip \
                2>/dev/null || true
            if $IS_WAYLAND; then
                sudo zypper install -y ydotool 2>/dev/null || \
                sudo zypper install -y wtype   2>/dev/null || \
                    warn "No auto-paste tool found — you will press Ctrl+V manually"
            fi
            ;;

        *)
            warn "Unknown package manager — please manually install:"
            warn "  python3-gi, xdotool, wl-clipboard, python3-pynput, python3-pil"
            ;;
    esac
}

install_pkgs
ok "System packages done"

# ── Python packages (pip fallback) ────────────────────────────────────────────
hdr "── Step 2: Python packages"

has_mod() { python3 -c "import $1" &>/dev/null; }

pip_install() {
    local pkg="$1"
    # Try pip with --break-system-packages (Ubuntu 23.04+, Debian 12+)
    pip3 install --user --quiet "$pkg" --break-system-packages 2>/dev/null && return
    # Older pip without that flag
    pip3 install --user --quiet "$pkg" 2>/dev/null && return
    warn "Could not install $pkg via pip — some features may be missing"
}

if ! has_mod pynput; then
    say "Installing pynput via pip…"
    pip_install pynput
fi
has_mod pynput && ok "pynput ready" || warn "pynput missing — Win+V hotkey won't work on X11"

if ! has_mod PIL; then
    say "Installing Pillow via pip…"
    pip_install Pillow
fi
has_mod PIL && ok "Pillow ready" || warn "Pillow missing — image capture disabled"

# ── Wayland: enable ydotool daemon ────────────────────────────────────────────
if $IS_WAYLAND; then
    hdr "── Step 3: Wayland auto-paste setup"
    if command -v ydotool &>/dev/null; then
        # Try systemd service first
        if systemctl list-unit-files ydotool.service &>/dev/null 2>&1; then
            sudo systemctl enable --now ydotool 2>/dev/null && \
                ok "ydotool daemon enabled via systemd" || \
                warn "Could not enable ydotool systemd service"
        fi
        # Also start it now in case systemd didn't work
        if ! pgrep -x ydotoold &>/dev/null; then
            nohup ydotoold > /dev/null 2>&1 &
            sleep 0.5
            pgrep -x ydotoold &>/dev/null && ok "ydotoold daemon started" || \
                warn "ydotoold daemon not running — run 'sudo ydotoold &' to enable auto-paste"
        else
            ok "ydotoold daemon already running"
        fi
    elif command -v wtype &>/dev/null; then
        ok "wtype found — will use for auto-paste"
    else
        warn "No auto-paste tool available."
        warn "Install one of: ydotool  or  wtype"
        warn "Without it: items copy to clipboard, press Ctrl+V yourself."
    fi
fi

# ── Copy app files ────────────────────────────────────────────────────────────
hdr "── Step 4: Installing app files"
mkdir -p "$INSTALL_DIR"
cp "$SCRIPT_DIR/clipvault.py" "$INSTALL_DIR/clipvault.py"
chmod +x "$INSTALL_DIR/clipvault.py"

# Copy assets (icons)
if [ -d "$SCRIPT_DIR/assets" ]; then
    cp -r "$SCRIPT_DIR/assets" "$INSTALL_DIR/assets"
fi

# Install icons to system theme
for size in 16 32 48 64 128 256; do
    icon_src="$SCRIPT_DIR/assets/icon_${size}.png"
    if [ -f "$icon_src" ]; then
        icon_dir="$HOME/.local/share/icons/hicolor/${size}x${size}/apps"
        mkdir -p "$icon_dir"
        cp "$icon_src" "$icon_dir/clipvault.png"
    fi
done
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
ok "App installed to $INSTALL_DIR"

# ── Desktop entry ─────────────────────────────────────────────────────────────
mkdir -p "$APPS_DIR"
cat > "$APPS_DIR/clipvault.desktop" << EOF
[Desktop Entry]
Name=ClipVault
Comment=Windows-style clipboard history (Win+V)
Exec=python3 $INSTALL_DIR/clipvault.py
Icon=clipvault
Terminal=false
Type=Application
Categories=Utility;GTK;
Keywords=clipboard;copy;paste;history;
StartupNotify=false
EOF
update-desktop-database "$APPS_DIR" 2>/dev/null || true
ok "Desktop entry created"

# ── Autostart ─────────────────────────────────────────────────────────────────
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_DIR/clipvault.desktop" << EOF
[Desktop Entry]
Name=ClipVault
Comment=Clipboard history daemon
Exec=python3 $INSTALL_DIR/clipvault.py
Icon=clipvault
Terminal=false
Type=Application
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=3
EOF
ok "Autostart entry created (runs on every login)"

# ── Register Win+V keyboard shortcut ──────────────────────────────────────────
hdr "── Step 5: Win+V keyboard shortcut"

SHORTCUT_CMD="pkill -USR1 -f clipvault.py"

register_gnome_shortcut() {
    local BINDING="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/clipvault/"
    local EXISTING
    EXISTING=$(gsettings get org.gnome.settings-daemon.plugins.media-keys \
                   custom-keybindings 2>/dev/null || echo "@as []")

    if echo "$EXISTING" | grep -q "clipvault"; then
        ok "Win+V shortcut already registered"; return
    fi

    if [[ "$EXISTING" == "@as []" ]] || [[ "$EXISTING" == "[]" ]]; then
        NEW_LIST="['$BINDING']"
    else
        NEW_LIST="${EXISTING%]}, '$BINDING']"
    fi

    gsettings set org.gnome.settings-daemon.plugins.media-keys \
        custom-keybindings "$NEW_LIST" 2>/dev/null || { warn "gsettings failed"; return; }

    gsettings set \
        "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$BINDING" \
        name    "ClipVault"       2>/dev/null || true
    gsettings set \
        "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$BINDING" \
        command "$SHORTCUT_CMD"   2>/dev/null || true
    gsettings set \
        "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$BINDING" \
        binding "<Super>v"        2>/dev/null || true
    ok "Win+V shortcut registered via gsettings"
}

register_kde_shortcut() {
    # KDE: write a khotkeys config or use kwriteconfig5
    if command -v kwriteconfig5 &>/dev/null; then
        kwriteconfig5 --file kglobalshortcutsrc \
            --group "clipvault.desktop" \
            --key "_launch" "Meta+V,none,ClipVault" 2>/dev/null && \
            ok "Win+V shortcut registered for KDE" || \
            warn "KDE shortcut registration failed — add manually in System Settings → Shortcuts"
    else
        warn "Add shortcut manually: System Settings → Shortcuts → Custom Shortcuts"
        warn "  Command: $SHORTCUT_CMD   Key: Meta+V"
    fi
}

# Detect desktop environment
DE="${XDG_CURRENT_DESKTOP:-}"
SESSION="${DESKTOP_SESSION:-}"

if [[ "$DE" == *"GNOME"* ]] || [[ "$DE" == *"pop"* ]] || \
   [[ "$SESSION" == *"gnome"* ]] || [[ "$SESSION" == *"pop"* ]]; then
    if command -v gsettings &>/dev/null; then
        register_gnome_shortcut
    else
        warn "gsettings not found — add Win+V shortcut manually"
    fi
elif [[ "$DE" == *"KDE"* ]] || [[ "$SESSION" == *"plasma"* ]]; then
    register_kde_shortcut
elif [[ "$DE" == *"XFCE"* ]]; then
    warn "XFCE detected — add shortcut manually:"
    warn "  Settings → Keyboard → Application Shortcuts"
    warn "  Command: $SHORTCUT_CMD   Key: Super+V"
elif [[ "$DE" == *"MATE"* ]]; then
    if command -v gsettings &>/dev/null; then
        register_gnome_shortcut   # MATE uses same gsettings schema
    fi
elif [[ "$DE" == *"Cinnamon"* ]]; then
    if command -v gsettings &>/dev/null; then
        register_gnome_shortcut   # Cinnamon is GNOME-derived
    fi
elif [[ "$DE" == *"COSMIC"* ]]; then
    warn "COSMIC DE detected — pynput handles Win+V internally."
    warn "If Win+V conflicts, change it in: ClipVault → Settings → Keyboard shortcut"
    warn "Or add via COSMIC Settings → Keyboard → Custom Shortcuts:"
    warn "  Command: $SHORTCUT_CMD   Key: Super+V"
elif command -v gsettings &>/dev/null; then
    # Unknown DE but gsettings exists — try anyway
    register_gnome_shortcut
else
    warn "Could not auto-register Win+V for desktop: ${DE:-unknown}"
    warn "Add manually: Command '$SHORTCUT_CMD'  Key: Super+V"
fi

# ── Kill old instance and start fresh ────────────────────────────────────────
hdr "── Step 6: Starting ClipVault"
pkill -f clipvault.py 2>/dev/null || true
sleep 0.5
nohup python3 "$INSTALL_DIR/clipvault.py" \
    > "$INSTALL_DIR/clipvault.log" 2>&1 &
sleep 1

if pgrep -f clipvault.py > /dev/null; then
    ok "ClipVault is running!"
else
    warn "ClipVault failed to start. Check log:"
    warn "  cat $INSTALL_DIR/clipvault.log"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${GREEN}  ✔  ClipVault installed!${NC}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  Press ${BOLD}Win+V${NC} to open clipboard history"
echo -e "  Logs: $INSTALL_DIR/clipvault.log"
echo ""
if $IS_WAYLAND && ! command -v ydotool &>/dev/null && ! command -v wtype &>/dev/null; then
    echo -e "  ${YELLOW}⚠  No auto-paste tool found. Install one:${NC}"
    echo -e "     Ubuntu/Debian:  ${CYAN}sudo apt install ydotool${NC}"
    echo -e "     Fedora:         ${CYAN}sudo dnf install ydotool${NC}"
    echo -e "     Arch:           ${CYAN}sudo pacman -S ydotool${NC}"
    echo ""
fi
