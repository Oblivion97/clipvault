# Changelog

All notable changes to ClipVault are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0] — 2025-06-24

### Added
- Initial release
- Win+V (Super+V) hotkey opens clipboard history popup
- Stores up to 200 items: text, links, code snippets, images
- Smart content classification (text / link / code / image)
- Full-text search across clipboard history
- Keyboard navigation (↑↓ arrows, Enter to paste, Del to remove)
- Single-click paste
- Persistent history across reboots
- Autostart on login
- Wayland support via `wl-paste --watch` clipboard monitoring
- Auto-paste via `ydotool` or `wtype` on Wayland
- Auto-paste via `xdotool` on X11
- Cross-distro installer (apt / dnf / pacman / zypper)
- Auto-registers Win+V shortcut on GNOME, KDE, Cinnamon, MATE
- Black/white solid UI (no transparency issues)
- Duplicate detection
- Clear all history
- Single instance lock
