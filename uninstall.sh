#!/usr/bin/env bash
# ClipVault Uninstaller — cleanly removes everything

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

say()  { echo -e "${CYAN}▶  $*${NC}"; }
ok()   { echo -e "${GREEN}✔  $*${NC}"; }
warn() { echo -e "${YELLOW}⚠  $*${NC}"; }

echo -e "\n${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  🗑  ClipVault Uninstaller${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

# ── Stop running instance ─────────────────────────────────────────────────────
say "Stopping ClipVault…"
if pgrep -f clipvault.py > /dev/null; then
    pkill -f clipvault.py 2>/dev/null || true
    sleep 0.5
    ok "Process stopped"
else
    ok "Not running"
fi

# ── Remove app files ──────────────────────────────────────────────────────────
say "Removing app files…"
rm -rf "$HOME/.local/share/clipvault"
ok "App files removed"

# ── Remove history and config ─────────────────────────────────────────────────
say "Removing config and history…"
rm -rf "$HOME/.config/clipvault"
ok "Config and history removed"

# ── Remove desktop entries ────────────────────────────────────────────────────
say "Removing desktop entries…"
rm -f "$HOME/.config/autostart/clipvault.desktop"
rm -f "$HOME/.local/share/applications/clipvault.desktop"
ok "Desktop entries removed"

# ── Remove Win+V keyboard shortcut ───────────────────────────────────────────
say "Removing Win+V keyboard shortcut…"

remove_gnome_shortcut() {
    local BINDING="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/clipvault/"
    local EXISTING
    EXISTING=$(gsettings get org.gnome.settings-daemon.plugins.media-keys \
                   custom-keybindings 2>/dev/null || echo "[]")

    if echo "$EXISTING" | grep -q "clipvault"; then
        # Build new list without the clipvault entry
        NEW_LIST=$(echo "$EXISTING" | sed "s|'$BINDING'||g" | \
                   sed "s|, ,|,|g" | sed "s|\[, |[|g" | sed "s|, ]|]|g" | \
                   sed "s|\[,|[|g")
        gsettings set org.gnome.settings-daemon.plugins.media-keys \
            custom-keybindings "$NEW_LIST" 2>/dev/null || true
        # Clear the binding schema
        gsettings reset-recursively \
            "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$BINDING" \
            2>/dev/null || true
        ok "GNOME Win+V shortcut removed"
    else
        ok "No GNOME shortcut found (already clean)"
    fi
}

remove_kde_shortcut() {
    if command -v kwriteconfig5 &>/dev/null; then
        kwriteconfig5 --file kglobalshortcutsrc \
            --group "clipvault.desktop" \
            --key "_launch" "none,none,ClipVault" 2>/dev/null || true
        ok "KDE shortcut removed"
    fi
}

DE="${XDG_CURRENT_DESKTOP:-}"
SESSION="${DESKTOP_SESSION:-}"

if [[ "$DE" == *"KDE"* ]] || [[ "$SESSION" == *"plasma"* ]]; then
    remove_kde_shortcut
elif command -v gsettings &>/dev/null; then
    remove_gnome_shortcut
else
    warn "Could not auto-remove shortcut — remove manually from DE keyboard settings"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${GREEN}  ✔  ClipVault fully uninstalled${NC}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  All files, history, shortcuts and autostart entries removed."
echo ""
