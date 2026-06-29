# Changelog

All notable changes to ClipVault are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.2.0] — 2026-06-29

### Added
- Settings page with persistent config (`~/.config/clipvault/settings.json`)
- Settings: history limit, paste delay, deduplication, autostart, image capture, pause monitoring, preview length, and more
- Community section in settings — links to report bugs, request features, and contribute
- Author section in settings with LinkedIn link
- Image preview thumbnails in clipboard list
- Auto-detect image files copied from file manager (loads actual image data)
- Scroll-follows-selection — list now scrolls to keep selected item visible on arrow key navigation
- App icon in all standard sizes (16 / 32 / 48 / 64 / 128 / 256 px)
- Icon registered to system icon theme — shows in taskbar, app switcher, and autostart area
- Settings window opens independently alongside the main window (no longer closes history)

### Changed
- UI redesigned to light theme — white background, sharp black/white contrast
- Selected item now highlighted with a left border accent instead of solid black fill
- Item icons replaced with minimal typographic symbols (no emoji)
- Title and footer labels updated to all-caps spaced style
- Paste speed improved — total delay reduced from ~550 ms to ~200 ms
- Clipboard monitoring now checks MIME types before ingesting to correctly classify images vs text
- `install.sh` now installs icons and assets alongside the app

### Fixed
- Arrow key navigation no longer leaves selected item off-screen
- Image files copied from file manager now correctly stored as images with thumbnails
- Settings window opening no longer triggers focus-out dismiss on the main window

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
