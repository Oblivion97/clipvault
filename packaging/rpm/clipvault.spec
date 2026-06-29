Name:           clipvault
Version:        1.2.0
Release:        1%{?dist}
Summary:        Windows-style clipboard history for Linux — Win+V to paste
License:        MIT
URL:            https://github.com/Oblivion97/clipvault
Source0:        clipvault-%{version}.zip
BuildArch:      noarch

Requires:       python3 >= 3.8
Requires:       python3-gobject
Requires:       gtk3
Requires:       wl-clipboard
Requires:       xdotool

%description
ClipVault brings the Windows 11 clipboard history experience to Linux.
Press Win+V to open a searchable popup of everything you have copied —
text, links, code snippets and images — then click or press Enter to paste.

Features:
- Win+V opens clipboard history from anywhere
- Stores up to 200 items, persists across reboots
- Image capture with live preview thumbnails
- Instant search and filter
- Settings page with privacy and behaviour options
- Wayland and X11 support
- Auto-starts silently at login

%prep
%setup -q

%install
# App files
install -Dm644 clipvault.py %{buildroot}/usr/share/clipvault/clipvault.py

# Assets
mkdir -p %{buildroot}/usr/share/clipvault/assets
cp -r assets/. %{buildroot}/usr/share/clipvault/assets/

# Launcher
install -Dm755 /dev/stdin %{buildroot}/usr/bin/clipvault << 'EOF'
#!/bin/bash
exec python3 /usr/share/clipvault/clipvault.py "$@"
EOF

# Desktop entry
install -Dm644 /dev/stdin %{buildroot}/usr/share/applications/clipvault.desktop << 'EOF'
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

# Autostart
install -Dm644 /dev/stdin %{buildroot}/etc/xdg/autostart/clipvault.desktop << 'EOF'
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

# Icons
install -Dm644 assets/icon_256.png \
    %{buildroot}/usr/share/icons/hicolor/256x256/apps/clipvault.png
install -Dm644 assets/icon_128.png \
    %{buildroot}/usr/share/icons/hicolor/128x128/apps/clipvault.png
install -Dm644 assets/icon_64.png \
    %{buildroot}/usr/share/icons/hicolor/64x64/apps/clipvault.png
install -Dm644 assets/icon_48.png \
    %{buildroot}/usr/share/icons/hicolor/48x48/apps/clipvault.png
install -Dm644 assets/icon_32.png \
    %{buildroot}/usr/share/icons/hicolor/32x32/apps/clipvault.png
install -Dm644 assets/icon_16.png \
    %{buildroot}/usr/share/icons/hicolor/16x16/apps/clipvault.png

%post
python3 -c "import pynput" 2>/dev/null || pip3 install --quiet pynput 2>/dev/null || true
gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true
echo "ClipVault installed. Press Win+V to open clipboard history."

%preun
pkill -f clipvault.py 2>/dev/null || true

%postun
if [ $1 -eq 0 ]; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
fi

%files
/usr/share/clipvault/
/usr/bin/clipvault
/usr/share/applications/clipvault.desktop
/etc/xdg/autostart/clipvault.desktop
/usr/share/icons/hicolor/256x256/apps/clipvault.png
/usr/share/icons/hicolor/128x128/apps/clipvault.png
/usr/share/icons/hicolor/64x64/apps/clipvault.png
/usr/share/icons/hicolor/48x48/apps/clipvault.png
/usr/share/icons/hicolor/32x32/apps/clipvault.png
/usr/share/icons/hicolor/16x16/apps/clipvault.png

%changelog
* Sun Jun 29 2026 H M Mahmudul Hasan <mahmudul.uiu041@gmail.com> - 1.2.0-1
- Settings page, image thumbnails, tray icon, app icon, light theme UI
* Tue Jun 24 2025 H M Mahmudul Hasan <mahmudul.uiu041@gmail.com> - 1.0.0-1
- Initial release
