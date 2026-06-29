#!/usr/bin/env python3
"""
ClipVault — Windows-style Clipboard Manager for Linux
Win+V opens clipboard history. Click or Enter to paste.
"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
try:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3
    HAS_INDICATOR = True
except Exception:
    HAS_INDICATOR = False
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Pango

import os, sys, json, hashlib, base64, threading, time, subprocess, signal, re
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
VERSION = '1.6.0'
CONFIG_DIR    = os.path.expanduser('~/.config/clipvault')
HISTORY_FILE  = os.path.join(CONFIG_DIR, 'history.json')
SETTINGS_FILE = os.path.join(CONFIG_DIR, 'settings.json')

DEFAULTS = {
    'max_items':         200,
    'paste_delay_ms':    120,
    'deduplicate':       True,
    'ignore_passwords':  True,
    'store_images':      True,
    'clear_on_exit':     False,
    'pause_monitoring':  False,
    'autostart':         True,
    'show_image_thumbs': True,
    'max_preview_chars': 70,
    'image_thumb_w':     56,
    'image_thumb_h':     40,
    'hotkey':            '<super>+v',
}

class Settings:
    def __init__(self):
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self):
        try:
            with open(SETTINGS_FILE) as f:
                self._data.update(json.load(f))
        except Exception:
            pass

    def save(self):
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            print(f"[settings] {e}")

    def get(self, key):
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self._data[key] = value
        self.save()

# ── Helpers ───────────────────────────────────────────────────────────────────
def classify(text):
    t = text.strip()
    if re.match(r'^https?://\S+$', t):
        return 'link'
    if '\n' in t and any(t.startswith(p) for p in
                         ('def ', 'function ', 'class ', '#!', 'import ', '<', '{')):
        return 'code'
    return 'text'

def time_ago(iso):
    try:
        dt = datetime.fromisoformat(iso)
        s  = int((datetime.now() - dt).total_seconds())
        if s < 60:    return 'just now'
        if s < 3600:  return f'{s//60}m ago'
        if s < 86400: return f'{s//3600}h ago'
        return dt.strftime('%b %d')
    except:
        return ''

# ── Data model ────────────────────────────────────────────────────────────────
class ClipItem:
    def __init__(self, ctype, content, ts=None):
        self.ctype   = ctype
        self.content = content
        self.ts      = ts or datetime.now().isoformat()
        self.hash    = hashlib.md5(content.encode('utf-8', errors='ignore')).hexdigest()

    def preview(self, maxlen=70):
        if self.ctype == 'image':
            return '[Image]'
        t = self.content.strip().replace('\n', ' ').replace('\r', '')
        return t[:maxlen] + ('…' if len(t) > maxlen else '')

    def to_dict(self):
        return {'ctype': self.ctype, 'content': self.content, 'ts': self.ts}

    @staticmethod
    def from_dict(d):
        return ClipItem(d['ctype'], d['content'], d.get('ts'))


# ── CSS ───────────────────────────────────────────────────────────────────────
CSS = b"""
* {
    -gtk-icon-style: regular;
}
window.cv-win {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
}
.cv-header {
    background-color: #ffffff;
    padding: 16px 16px 12px 16px;
    border-bottom: 1px solid #e8e8e8;
}
.cv-title {
    color: #0d0d0d;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 1px;
}
.cv-count {
    color: #aaaaaa;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.5px;
}
.cv-search {
    background-color: #f7f7f7;
    border: 1px solid #e0e0e0;
    border-radius: 0;
    color: #0d0d0d;
    padding: 8px 12px;
    font-size: 13px;
    caret-color: #000000;
}
.cv-search:focus {
    border-color: #aaaaaa;
    background-color: #ffffff;
}
.cv-listbox {
    background-color: #ffffff;
}
.cv-listbox row {
    background-color: #ffffff;
    border-bottom: 1px solid #f0f0f0;
    transition: background-color 80ms ease;
}
.cv-listbox row:hover {
    background-color: #f9f9f9;
}
.cv-listbox row:selected,
.cv-listbox row:selected:focus {
    background-color: #f5f5f5;
    border-left: 3px solid #0d0d0d;
}
.cv-listbox row:selected .cv-preview,
.cv-listbox row:selected:focus .cv-preview {
    color: #0d0d0d;
    font-weight: 600;
}
.cv-listbox row:selected .cv-meta,
.cv-listbox row:selected:focus .cv-meta {
    color: #888888;
}
.cv-listbox row:selected .cv-badge,
.cv-listbox row:selected:focus .cv-badge {
    color: #666666;
    border-color: #cccccc;
}
.cv-listbox row:selected .cv-icon,
.cv-listbox row:selected:focus .cv-icon {
    color: #555555;
}
.cv-item-box {
    padding: 11px 14px;
}
.cv-icon {
    color: #cccccc;
    font-size: 14px;
}
.cv-preview {
    color: #1a1a1a;
    font-size: 13px;
    font-weight: 400;
}
.cv-meta {
    color: #aaaaaa;
    font-size: 11px;
    margin-top: 1px;
}
.cv-badge {
    color: #bbbbbb;
    font-size: 9px;
    font-family: monospace;
    font-weight: 700;
    letter-spacing: 1px;
    border: 1px solid #e0e0e0;
    padding: 1px 5px;
}
.cv-footer {
    background-color: #ffffff;
    padding: 8px 14px;
    border-top: 1px solid #e8e8e8;
}
.cv-hint {
    color: #cccccc;
    font-size: 11px;
    letter-spacing: 0.3px;
}
.cv-empty {
    color: #cccccc;
    font-size: 13px;
}
button.cv-clear {
    background-color: transparent;
    border: 1px solid #e0e0e0;
    border-radius: 0;
    color: #aaaaaa;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.8px;
    padding: 3px 10px;
}
button.cv-clear:hover {
    border-color: #cc3333;
    color: #cc3333;
    background-color: transparent;
}
.cv-thumb {
    border: 1px solid #e0e0e0;
}
button.cv-settings-btn {
    background-color: transparent;
    border: none;
    color: #cccccc;
    font-size: 14px;
    padding: 0 2px;
    min-width: 0;
    min-height: 0;
}
button.cv-settings-btn:hover {
    color: #555555;
    background-color: transparent;
}
window.cv-settings {
    background-color: #ffffff;
}
.cv-settings-header {
    background-color: #ffffff;
    padding: 16px 20px 12px 20px;
    border-bottom: 1px solid #e8e8e8;
}
.cv-settings-title {
    color: #0d0d0d;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 1px;
}
.cv-section-label {
    color: #aaaaaa;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    margin-top: 8px;
    margin-bottom: 2px;
}
.cv-setting-row {
    padding: 10px 20px;
    border-bottom: 1px solid #f4f4f4;
}
.cv-setting-name {
    color: #1a1a1a;
    font-size: 13px;
    font-weight: 500;
}
.cv-setting-desc {
    color: #aaaaaa;
    font-size: 11px;
    margin-top: 1px;
}
.cv-settings-footer {
    background-color: #ffffff;
    padding: 10px 20px;
    border-top: 1px solid #e8e8e8;
}
button.cv-save-btn {
    background-color: #0d0d0d;
    border: none;
    border-radius: 0;
    color: #ffffff;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.8px;
    padding: 6px 20px;
}
button.cv-save-btn:hover {
    background-color: #333333;
}
.cv-author-link {
    color: #0a66c2;
    font-size: 11px;
    padding: 0;
    border: none;
    background: transparent;
    box-shadow: none;
}
.cv-author-link:hover {
    color: #004182;
    background: transparent;
}
"""

# ── Icon helper ───────────────────────────────────────────────────────────────
_ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')

def _set_app_icon(window):
    for size in [256, 128, 64, 48, 32, 16]:
        path = os.path.join(_ICON_DIR, f'icon_{size}.png')
        if os.path.exists(path):
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file(path)
                window.set_icon(pb)
                return
            except Exception:
                pass
    fallback = os.path.join(_ICON_DIR, 'icon.png')
    if os.path.exists(fallback):
        try:
            window.set_icon(GdkPixbuf.Pixbuf.new_from_file(fallback))
        except Exception:
            pass

# ── Window ────────────────────────────────────────────────────────────────────
class ClipWindow(Gtk.Window):

    def __init__(self, app):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.app             = app
        self._pasting        = False   # guard: prevent double-paste
        self._ignore_fo      = False   # ignore focus-out briefly on open
        self._settings_open  = False

        self.set_title("ClipVault")
        self.set_default_size(480, 580)
        self.set_resizable(False)
        self.set_decorated(True)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        self.get_style_context().add_class('cv-win')
        _set_app_icon(self)

        self.connect('delete-event', lambda *_: self._dismiss() or True)
        self.connect('focus-out-event', self._on_window_focus_out)

        # Load CSS once
        p = Gtk.CssProvider()
        p.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), p,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self._build()

    # ── Build UI ──────────────────────────────────────────────────
    def _build(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(root)

        # Header
        hdr = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        hdr.get_style_context().add_class('cv-header')

        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        lbl = Gtk.Label(label="CLIPBOARD HISTORY")
        lbl.get_style_context().add_class('cv-title')
        lbl.set_halign(Gtk.Align.START)
        title_row.pack_start(lbl, True, True, 0)
        self.lbl_count = Gtk.Label()
        self.lbl_count.get_style_context().add_class('cv-count')
        title_row.pack_end(self.lbl_count, False, False, 0)
        gear = Gtk.Button(label="⚙")
        gear.get_style_context().add_class('cv-settings-btn')
        gear.connect('clicked', self._open_settings)
        title_row.pack_end(gear, False, False, 4)
        hdr.pack_start(title_row, False, False, 0)

        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("  Search…")
        self.search.get_style_context().add_class('cv-search')
        self.search.connect('changed', self._on_search_changed)
        # Enter in search box → paste selected item
        self.search.connect('activate', self._on_search_enter)
        # Escape / arrows in search box
        self.search.connect('key-press-event', self._on_search_key)
        hdr.pack_start(self.search, False, False, 0)
        root.pack_start(hdr, False, False, 0)

        # List
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.set_margin_top(4)
        scroll.set_margin_bottom(4)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.get_style_context().add_class('cv-listbox')
        self.listbox.set_activate_on_single_click(True)
        # Mouse click paste
        self.listbox.connect('row-activated', self._on_row_activated)
        # Keyboard on listbox: Enter, Delete, Escape, type-to-search
        self.listbox.connect('key-press-event', self._on_listbox_key)
        scroll.add(self.listbox)
        self._scroll = scroll
        root.pack_start(scroll, True, True, 0)

        # Footer
        foot = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        foot.get_style_context().add_class('cv-footer')
        hint = Gtk.Label(label="↑ ↓  NAVIGATE    ↵  PASTE    DEL  REMOVE    ESC  CLOSE")
        hint.get_style_context().add_class('cv-hint')
        hint.set_halign(Gtk.Align.START)
        foot.pack_start(hint, True, True, 0)
        btn = Gtk.Button(label="CLEAR ALL")
        btn.get_style_context().add_class('cv-clear')
        btn.connect('clicked', lambda _: (self.app.clear_all(),
                                          self._render(self.app.history)))
        foot.pack_end(btn, False, False, 0)
        root.pack_start(foot, False, False, 0)

    # ── Render ────────────────────────────────────────────────────
    def _render(self, items):
        for c in self.listbox.get_children():
            self.listbox.remove(c)

        if not items:
            row = Gtk.ListBoxRow()
            row.set_selectable(False)
            lbl = Gtk.Label(label="Nothing here yet — copy something!")
            lbl.get_style_context().add_class('cv-empty')
            lbl.set_margin_top(48); lbl.set_margin_bottom(48)
            row.add(lbl)
            self.listbox.add(row)
        else:
            icons = {'text': '¶', 'link': '⌁', 'code': '⌥', 'image': '▣'}
            for item in items:
                row = Gtk.ListBoxRow()
                row._clip = item

                box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                box.get_style_context().add_class('cv-item-box')

                if item.ctype == 'image':
                    thumb = self._make_thumbnail(item.content, width=56, height=40)
                    if thumb:
                        img_widget = Gtk.Image.new_from_pixbuf(thumb)
                        img_widget.set_valign(Gtk.Align.CENTER)
                        img_widget.get_style_context().add_class('cv-thumb')
                        box.pack_start(img_widget, False, False, 0)
                    else:
                        ico = Gtk.Label(label='▣')
                        ico.set_width_chars(2)
                        ico.set_valign(Gtk.Align.CENTER)
                        ico.get_style_context().add_class('cv-icon')
                        box.pack_start(ico, False, False, 0)
                else:
                    ico = Gtk.Label(label=icons.get(item.ctype, '¶'))
                    ico.set_width_chars(2)
                    ico.set_valign(Gtk.Align.CENTER)
                    ico.get_style_context().add_class('cv-icon')
                    box.pack_start(ico, False, False, 0)

                vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                vbox.set_hexpand(True)
                p_lbl = Gtk.Label(label=item.preview())
                p_lbl.set_halign(Gtk.Align.START)
                p_lbl.set_ellipsize(Pango.EllipsizeMode.END)
                p_lbl.set_max_width_chars(52)
                p_lbl.get_style_context().add_class('cv-preview')
                m_lbl = Gtk.Label(label=time_ago(item.ts))
                m_lbl.set_halign(Gtk.Align.START)
                m_lbl.get_style_context().add_class('cv-meta')
                vbox.pack_start(p_lbl, False, False, 0)
                vbox.pack_start(m_lbl, False, False, 0)
                box.pack_start(vbox, True, True, 0)

                badge = Gtk.Label(label=item.ctype.upper())
                badge.get_style_context().add_class('cv-badge')
                badge.set_valign(Gtk.Align.CENTER)
                box.pack_end(badge, False, False, 0)

                row.add(box)
                self.listbox.add(row)

        self.listbox.show_all()
        self.lbl_count.set_text(f"{len(self.app.history)} items")

        # Select first row
        rows = self._clip_rows()
        if rows:
            self.listbox.select_row(rows[0])

    def _make_thumbnail(self, b64_content, width=56, height=40):
        try:
            data = base64.b64decode(b64_content)
            loader = GdkPixbuf.PixbufLoader.new_with_type('png')
            loader.write(data)
            loader.close()
            pb = loader.get_pixbuf()
            src_w, src_h = pb.get_width(), pb.get_height()
            scale = min(width / src_w, height / src_h)
            tw = max(1, int(src_w * scale))
            th = max(1, int(src_h * scale))
            return pb.scale_simple(tw, th, GdkPixbuf.InterpType.BILINEAR)
        except Exception:
            return None

    def _clip_rows(self):
        return [r for r in self.listbox.get_children()
                if getattr(r, '_clip', None)]

    # ── Key handlers ──────────────────────────────────────────────

    def _on_listbox_key(self, _widget, ev):
        """Fires when listbox has focus. Arrow keys are handled by GTK natively."""
        k = ev.keyval
        if k in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._paste_selected()
            return True          # consume — stops row-activated from also firing
        if k == Gdk.KEY_Delete:
            self._delete_selected()
            return True
        if k == Gdk.KEY_Escape:
            self._dismiss()
            return True
        # Printable char while listbox focused → forward to search
        if ev.string and ev.string.isprintable() and not (
                ev.get_state() & (Gdk.ModifierType.CONTROL_MASK |
                                  Gdk.ModifierType.MOD1_MASK)):
            cur = self.search.get_text()
            self.search.set_text(cur + ev.string)
            self.search.set_position(-1)
            self.search.grab_focus()
            return True
        return False   # let GTK handle Up/Down natively

    def _on_search_key(self, _widget, ev):
        """Fires when search entry has focus."""
        k = ev.keyval
        if k == Gdk.KEY_Escape:
            self._dismiss()
            return True
        if k in (Gdk.KEY_Down, Gdk.KEY_Up):
            # Move selection and give focus back to listbox
            rows = self._clip_rows()
            if rows:
                sel = self.listbox.get_selected_row()
                idx = rows.index(sel) if sel in rows else -1
                d   = 1 if k == Gdk.KEY_Down else -1
                nxt = max(0, min(len(rows) - 1, idx + d))
                self.listbox.select_row(rows[nxt])
                self.listbox.grab_focus()
                rows[nxt].grab_focus()
                adj = self._scroll.get_vadjustment()
                alloc = rows[nxt].get_allocation()
                adj.clamp_page(alloc.y, alloc.y + alloc.height)
            return True
        if k == Gdk.KEY_Delete:
            self._delete_selected()
            return True
        return False

    def _on_search_enter(self, _entry):
        """Enter pressed inside search entry."""
        self._paste_selected()

    def _on_row_activated(self, _lb, row):
        """Mouse click on a row."""
        if hasattr(row, '_clip'):
            self._do_paste(row._clip)

    def _on_window_focus_out(self, _w, _ev):
        if self._ignore_fo:
            return
        GLib.timeout_add(150, self._maybe_dismiss)

    def _maybe_dismiss(self):
        if not self.has_toplevel_focus() and not self._settings_open:
            self._dismiss()
        return False

    def _open_settings(self, _btn=None):
        self._settings_open = True
        self._ignore_fo = True
        win = SettingsWindow(self.app)
        win.connect('destroy', self._on_settings_closed)
        win.show_all()

    def _on_settings_closed(self, _win):
        self._settings_open = False
        self._ignore_fo = False

    # ── Actions ───────────────────────────────────────────────────
    def _paste_selected(self):
        row = self.listbox.get_selected_row()
        if row and hasattr(row, '_clip'):
            self._do_paste(row._clip)

    def _delete_selected(self):
        row = self.listbox.get_selected_row()
        if not row or not hasattr(row, '_clip'):
            return
        # Remember adjacent row to re-select after deletion
        rows = self._clip_rows()
        idx  = rows.index(row)
        self.app.delete_item(row._clip)
        self._render(self.app.history)
        # Re-select nearest row
        new_rows = self._clip_rows()
        if new_rows:
            nxt = min(idx, len(new_rows) - 1)
            self.listbox.select_row(new_rows[nxt])

    def _do_paste(self, item):
        if self._pasting:
            return
        self._pasting = True
        self._dismiss()
        GLib.timeout_add(80, lambda: self._finish_paste(item))

    def _finish_paste(self, item):
        self.app.paste(item)
        GLib.timeout_add(150, self._reset_pasting)
        return False

    def _reset_pasting(self):
        self._pasting = False
        return False

    def _dismiss(self):
        self.hide()
        # Reset search without triggering a re-render (block signal)
        self.search.handler_block_by_func(self._on_search_changed)
        self.search.set_text('')
        self.search.handler_unblock_by_func(self._on_search_changed)

    def _on_search_changed(self, entry):
        q = entry.get_text().lower().strip()
        filtered = (
            [i for i in self.app.history
             if q in i.content.lower() or q in i.ctype]
            if q else list(self.app.history)
        )
        self._render(filtered)

    # ── Show ──────────────────────────────────────────────────────
    def show_popup(self):
        self._pasting = False
        self._render(self.app.history)
        self.show_all()
        self.present()
        # Block focus-out briefly so opening the window doesn't immediately close it
        self._ignore_fo = True
        GLib.timeout_add(300, self._unblock_fo)
        # Focus listbox so arrow keys work immediately
        self.listbox.grab_focus()

    def _unblock_fo(self):
        self._ignore_fo = False
        return False


# ── Settings Window ───────────────────────────────────────────────────────────
class SettingsWindow(Gtk.Window):

    def __init__(self, app):
        super().__init__(title="ClipVault Settings")
        self.app = app
        self.s   = app.settings
        self._widgets = {}

        self.set_default_size(440, 560)
        self.set_resizable(False)
        self.set_decorated(True)
        self.set_keep_above(True)
        self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        self.get_style_context().add_class('cv-settings')
        _set_app_icon(self)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(root)

        # Header
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        hdr.get_style_context().add_class('cv-settings-header')
        t = Gtk.Label(label=f"SETTINGS  —  v{VERSION}")
        t.get_style_context().add_class('cv-settings-title')
        t.set_halign(Gtk.Align.START)
        hdr.pack_start(t, True, True, 0)
        root.pack_start(hdr, False, False, 0)

        # Scrollable body
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scroll.add(body)
        root.pack_start(scroll, True, True, 0)

        def section(label):
            lbl = Gtk.Label(label=label)
            lbl.get_style_context().add_class('cv-section-label')
            lbl.set_halign(Gtk.Align.START)
            lbl.set_margin_start(20)
            lbl.set_margin_top(14)
            lbl.set_margin_bottom(2)
            body.pack_start(lbl, False, False, 0)

        def toggle_row(key, name, desc):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.get_style_context().add_class('cv-setting-row')
            info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            info.set_hexpand(True)
            n = Gtk.Label(label=name)
            n.get_style_context().add_class('cv-setting-name')
            n.set_halign(Gtk.Align.START)
            d = Gtk.Label(label=desc)
            d.get_style_context().add_class('cv-setting-desc')
            d.set_halign(Gtk.Align.START)
            info.pack_start(n, False, False, 0)
            info.pack_start(d, False, False, 0)
            sw = Gtk.Switch()
            sw.set_active(self.s.get(key))
            sw.set_valign(Gtk.Align.CENTER)
            row.pack_start(info, True, True, 0)
            row.pack_end(sw, False, False, 0)
            body.pack_start(row, False, False, 0)
            self._widgets[key] = sw

        def spin_row(key, name, desc, min_val, max_val, step=1):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.get_style_context().add_class('cv-setting-row')
            info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            info.set_hexpand(True)
            n = Gtk.Label(label=name)
            n.get_style_context().add_class('cv-setting-name')
            n.set_halign(Gtk.Align.START)
            d = Gtk.Label(label=desc)
            d.get_style_context().add_class('cv-setting-desc')
            d.set_halign(Gtk.Align.START)
            info.pack_start(n, False, False, 0)
            info.pack_start(d, False, False, 0)
            adj = Gtk.Adjustment(value=self.s.get(key),
                                 lower=min_val, upper=max_val,
                                 step_increment=step)
            sb = Gtk.SpinButton(adjustment=adj, climb_rate=1, digits=0)
            sb.set_valign(Gtk.Align.CENTER)
            sb.set_width_chars(5)
            row.pack_start(info, True, True, 0)
            row.pack_end(sb, False, False, 0)
            body.pack_start(row, False, False, 0)
            self._widgets[key] = sb

        def shortcut_row(key, name, desc):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.get_style_context().add_class('cv-setting-row')
            info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            info.set_hexpand(True)
            n = Gtk.Label(label=name)
            n.get_style_context().add_class('cv-setting-name')
            n.set_halign(Gtk.Align.START)
            d = Gtk.Label(label=desc)
            d.get_style_context().add_class('cv-setting-desc')
            d.set_halign(Gtk.Align.START)
            info.pack_start(n, False, False, 0)
            info.pack_start(d, False, False, 0)

            entry = Gtk.Entry()
            entry.set_text(self.s.get(key) or '<super>+v')
            entry.set_width_chars(18)
            entry.set_valign(Gtk.Align.CENTER)
            entry.get_style_context().add_class('cv-search')

            rec_btn = Gtk.Button(label="Record")
            rec_btn.set_valign(Gtk.Align.CENTER)
            rec_btn.get_style_context().add_class('cv-clear')

            recording = [False]
            pressed   = [set()]

            def _key_press(widget, event):
                if not recording[0]:
                    return False
                keyname = Gdk.keyval_name(event.keyval)
                mods = []
                state = event.state
                if state & Gdk.ModifierType.SUPER_MASK:   mods.append('<super>')
                if state & Gdk.ModifierType.CONTROL_MASK: mods.append('<ctrl>')
                if state & Gdk.ModifierType.MOD1_MASK:    mods.append('<alt>')
                if state & Gdk.ModifierType.SHIFT_MASK:   mods.append('<shift>')
                ignore = {'Super_L','Super_R','Control_L','Control_R',
                          'Alt_L','Alt_R','Shift_L','Shift_R','ISO_Level3_Shift'}
                if keyname not in ignore and mods:
                    combo = '+'.join(mods) + '+' + keyname.lower()
                    entry.set_text(combo)
                    recording[0] = False
                    rec_btn.set_label("Record")
                return True

            def _toggle_record(_btn):
                recording[0] = not recording[0]
                if recording[0]:
                    rec_btn.set_label("Press keys…")
                    entry.grab_focus()
                else:
                    rec_btn.set_label("Record")

            entry.connect('key-press-event', _key_press)
            rec_btn.connect('clicked', _toggle_record)

            ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            ctrl.pack_start(entry, False, False, 0)
            ctrl.pack_start(rec_btn, False, False, 0)

            row.pack_start(info, True, True, 0)
            row.pack_end(ctrl, False, False, 0)
            body.pack_start(row, False, False, 0)
            self._widgets[key] = entry

        # ── General
        section("GENERAL")
        shortcut_row('hotkey',        "Keyboard shortcut",   "Click Record then press your key combination")
        spin_row('max_items',         "History limit",       "Maximum number of items to keep",              10, 1000, 10)
        toggle_row('deduplicate',     "Remove duplicates",   "Keep only the most recent copy of each item")
        toggle_row('autostart',       "Start on login",      "Launch ClipVault automatically at startup")
        toggle_row('clear_on_exit',   "Clear on exit",       "Wipe history when the app closes")

        # ── Clipboard
        section("CLIPBOARD")
        toggle_row('store_images',    "Capture images",      "Record images copied to clipboard")
        toggle_row('ignore_passwords',"Ignore passwords",    "Skip clipboard content from password managers")
        toggle_row('pause_monitoring',"Pause monitoring",    "Stop recording new clipboard items")

        # ── Display
        section("DISPLAY")
        toggle_row('show_image_thumbs', "Image thumbnails",  "Show preview thumbnails for image items")
        spin_row('max_preview_chars', "Preview length",      "Max characters shown in item preview",          20, 200, 10)

        # ── Performance
        section("PERFORMANCE")
        spin_row('paste_delay_ms',    "Paste delay (ms)",    "Delay before simulating Ctrl+V after paste",    50, 500, 10)

        # Community section
        section("COMMUNITY")

        def link_row(label, desc, url, url_label):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.get_style_context().add_class('cv-setting-row')
            info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            info.set_hexpand(True)
            n = Gtk.Label(label=label)
            n.get_style_context().add_class('cv-setting-name')
            n.set_halign(Gtk.Align.START)
            d = Gtk.Label(label=desc)
            d.get_style_context().add_class('cv-setting-desc')
            d.set_halign(Gtk.Align.START)
            info.pack_start(n, False, False, 0)
            info.pack_start(d, False, False, 0)
            btn = Gtk.LinkButton.new_with_label(url, url_label)
            btn.get_style_context().add_class('cv-author-link')
            btn.set_valign(Gtk.Align.CENTER)
            row.pack_start(info, True, True, 0)
            row.pack_end(btn, False, False, 0)
            body.pack_start(row, False, False, 0)

        link_row("Report a bug",       "Found something broken? Let us know",
                 "https://github.com/Oblivion97/clipvault/issues/new", "Open issue →")
        link_row("Request a feature",  "Have an idea? Start a discussion",
                 "https://github.com/Oblivion97/clipvault/discussions", "Discuss →")
        link_row("Contribute code",    "Fork, branch, and submit a pull request",
                 "https://github.com/Oblivion97/clipvault", "View on GitHub →")
        link_row("Star the project",   "Show support and help others discover it",
                 "https://github.com/Oblivion97/clipvault", "GitHub →")

        # About section
        section("ABOUT")
        about_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        about_row.get_style_context().add_class('cv-setting-row')
        made_lbl = Gtk.Label(label="Made by ")
        made_lbl.get_style_context().add_class('cv-setting-desc')
        link = Gtk.LinkButton.new_with_label(
            "https://www.linkedin.com/in/hmmahmudulhasan/",
            "H M Mahmudul Hasan")
        link.get_style_context().add_class('cv-author-link')
        link.set_halign(Gtk.Align.START)
        about_row.pack_start(made_lbl, False, False, 0)
        about_row.pack_start(link, False, False, 0)
        body.pack_start(about_row, False, False, 0)

        # Footer
        foot = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        foot.get_style_context().add_class('cv-settings-footer')
        save_btn = Gtk.Button(label="SAVE")
        save_btn.get_style_context().add_class('cv-save-btn')
        save_btn.connect('clicked', self._on_save)
        foot.pack_end(save_btn, False, False, 0)
        root.pack_start(foot, False, False, 0)

    def _on_save(self, _btn):
        for key, widget in self._widgets.items():
            if isinstance(widget, Gtk.Switch):
                self.s.set(key, widget.get_active())
            elif isinstance(widget, Gtk.SpinButton):
                self.s.set(key, int(widget.get_value()))
            elif isinstance(widget, Gtk.Entry):
                self.s.set(key, widget.get_text().strip())
        self.app._apply_settings()
        self.destroy()


# ── Core app ──────────────────────────────────────────────────────────────────
class ClipVault:

    def __init__(self):
        self.history     = []
        self._last_hash  = None
        self._win        = None
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self.settings    = Settings()
        self._load()
        self._cb         = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self._is_wayland = bool(os.environ.get('WAYLAND_DISPLAY'))

        self._start_hotkey_thread()
        signal.signal(signal.SIGUSR1, lambda *_: GLib.idle_add(self._show))
        signal.signal(signal.SIGUSR2, lambda *_: GLib.idle_add(self._read_wl_clipboard))

        if self._is_wayland:
            self._start_wl_watch()
        else:
            GLib.timeout_add(500, self._poll_clipboard)

        self._build_tray()

        mode = 'Wayland' if self._is_wayland else 'X11'
        print(f"ClipVault running (PID {os.getpid()}) [{mode}]")
        print("Trigger: Win+V  or  pkill -USR1 -f clipvault.py")

    def _build_tray(self):
        icon_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'assets', 'icon_48.png')

        if HAS_INDICATOR:
            self._indicator = AppIndicator3.Indicator.new(
                'clipvault',
                icon_path if os.path.exists(icon_path) else 'edit-paste',
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
            self._indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            self._indicator.set_menu(self._tray_menu())
        else:
            self._status_icon = Gtk.StatusIcon()
            if os.path.exists(icon_path):
                self._status_icon.set_from_file(icon_path)
            else:
                self._status_icon.set_from_icon_name('edit-paste')
            self._status_icon.set_tooltip_text('ClipVault')
            self._status_icon.connect('activate', lambda *_: GLib.idle_add(self._show))
            self._status_icon.connect('popup-menu', self._on_tray_popup)

    def _tray_menu(self):
        menu = Gtk.Menu()

        item_open = Gtk.MenuItem(label='Open Clipboard History')
        item_open.connect('activate', lambda *_: GLib.idle_add(self._show))
        menu.append(item_open)

        menu.append(Gtk.SeparatorMenuItem())

        self._tray_pause_item = Gtk.CheckMenuItem(label='Pause Monitoring')
        self._tray_pause_item.set_active(self.settings.get('pause_monitoring'))
        self._tray_pause_item.connect('toggled', self._on_tray_pause)
        menu.append(self._tray_pause_item)

        item_clear = Gtk.MenuItem(label='Clear History')
        item_clear.connect('activate', lambda *_: (self.clear_all(),
                           self._win and self._win._render(self.history)))
        menu.append(item_clear)

        menu.append(Gtk.SeparatorMenuItem())

        item_settings = Gtk.MenuItem(label='Settings')
        item_settings.connect('activate', lambda *_: SettingsWindow(self).show_all())
        menu.append(item_settings)

        menu.append(Gtk.SeparatorMenuItem())

        item_quit = Gtk.MenuItem(label='Quit')
        item_quit.connect('activate', lambda *_: Gtk.main_quit())
        menu.append(item_quit)

        menu.show_all()
        return menu

    def _on_tray_pause(self, item):
        self.settings.set('pause_monitoring', item.get_active())

    def _on_tray_popup(self, icon, button, time):
        menu = self._tray_menu()
        menu.popup(None, None, Gtk.StatusIcon.position_menu,
                   icon, button, time)

    def _apply_settings(self):
        if self._win:
            self._win._render(self.history)
        self._restart_hotkey()

    # ── Clipboard — Wayland ───────────────────────────────────────
    def _start_wl_watch(self):
        script = os.path.join(CONFIG_DIR, 'notify.sh')
        with open(script, 'w') as f:
            f.write('#!/bin/sh\npkill -USR2 -f clipvault.py\n')
        os.chmod(script, 0o755)
        def run():
            while True:
                try:
                    subprocess.run(['wl-paste', '--watch', script], check=True)
                except FileNotFoundError:
                    print("[wl-paste] not found — run: sudo apt install wl-clipboard")
                    break
                except Exception as e:
                    print(f"[wl-paste] {e} — restarting in 2s")
                    time.sleep(2)
        threading.Thread(target=run, daemon=True).start()

    def _read_wl_clipboard(self):
        # Check available MIME types first to decide order
        try:
            types_r = subprocess.run(['wl-paste', '--list-types'],
                                     capture_output=True, text=True, timeout=3)
            mime_types = types_r.stdout if types_r.returncode == 0 else ''
        except Exception:
            mime_types = ''

        # Image takes priority over file-path text
        if 'image/' in mime_types:
            try:
                r = subprocess.run(['wl-paste', '--type', 'image/png'],
                                   capture_output=True, timeout=3)
                if r.returncode == 0 and r.stdout:
                    b64 = base64.b64encode(r.stdout).decode()
                    h   = hashlib.md5(b64.encode()).hexdigest()
                    if h != self._last_hash:
                        self._last_hash = h
                        self._add('image', b64, h)
                    return False
            except Exception as e:
                print(f"[wl-paste image] {e}")

        # Text
        try:
            r = subprocess.run(['wl-paste', '--no-newline'],
                               capture_output=True, text=True, timeout=3)
            if r.returncode == 0 and r.stdout.strip():
                self._ingest_text(r.stdout)
        except Exception as e:
            print(f"[wl-paste text] {e}")
        return False

    # ── Clipboard — X11 ───────────────────────────────────────────
    def _poll_clipboard(self):
        self._cb.request_text(self._got_text)
        return True

    def _got_text(self, cb, text):
        if text and text.strip():
            self._ingest_text(text)
        else:
            cb.request_image(self._got_image)

    def _got_image(self, _cb, pixbuf):
        if pixbuf is None:
            return
        try:
            ok, buf = pixbuf.save_to_bufferv('png', [], [])
            if ok:
                b64 = base64.b64encode(bytes(buf)).decode()
                h   = hashlib.md5(b64.encode()).hexdigest()
                if h != self._last_hash:
                    self._last_hash = h
                    self._add('image', b64, h)
        except Exception as e:
            print(f"[image capture] {e}")

    def _ingest_text(self, text):
        if self.settings.get('pause_monitoring'):
            return
        path = text.strip()
        if self.settings.get('store_images') and self._try_ingest_image_file(path):
            return
        h = hashlib.md5(text.encode('utf-8', errors='ignore')).hexdigest()
        if h != self._last_hash:
            self._last_hash = h
            self._add(classify(text), text, h)
            print(f"[clip] {classify(text)}: {text[:60].strip()!r}")

    def _try_ingest_image_file(self, path):
        IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
        ext = os.path.splitext(path)[1].lower()
        if ext not in IMAGE_EXTS or not os.path.isfile(path):
            return False
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file(path)
            ok, buf = pb.save_to_bufferv('png', [], [])
            if not ok:
                return False
            b64 = base64.b64encode(bytes(buf)).decode()
            h = hashlib.md5(b64.encode()).hexdigest()
            if h != self._last_hash:
                self._last_hash = h
                self._add('image', b64, h)
                print(f"[clip] image file: {path!r}")
            return True
        except Exception as e:
            print(f"[clip] image file load failed: {e}")
            return False

    def _add(self, ctype, content, h):
        self.history = [i for i in self.history if i.hash != h]
        item = ClipItem(ctype, content)
        item.hash = h
        self.history.insert(0, item)
        self.history = self.history[:self.settings.get('max_items')]
        self._save()

    # ── Paste ─────────────────────────────────────────────────────
    def paste(self, item):
        """Set clipboard to item then simulate Ctrl+V."""
        if item.ctype == 'image':
            try:
                loader = GdkPixbuf.PixbufLoader.new_with_type('png')
                loader.write(base64.b64decode(item.content))
                loader.close()
                self._cb.set_image(loader.get_pixbuf())
                self._cb.store()
            except Exception as e:
                print(f"[paste image] {e}")
                return
        else:
            # On Wayland use wl-copy for reliable clipboard ownership
            if self._is_wayland:
                try:
                    subprocess.Popen(['wl-copy', item.content])
                except Exception:
                    self._cb.set_text(item.content, -1)
                    self._cb.store()
            else:
                self._cb.set_text(item.content, -1)
                self._cb.store()

        # Move to top of history
        self.history = [item] + [i for i in self.history if i.hash != item.hash]
        self._save()

        # Simulate Ctrl+V after short delay
        threading.Thread(target=self._keystroke_paste, daemon=True).start()
        return False

    def _keystroke_paste(self):
        time.sleep(self.settings.get('paste_delay_ms') / 1000)
        if self._is_wayland:
            for cmd in (
                ['ydotool', 'key', 'ctrl+v'],
                ['wtype', '-M', 'ctrl', '-k', 'v'],
            ):
                try:
                    r = subprocess.run(cmd, capture_output=True, timeout=3)
                    if r.returncode == 0:
                        return
                except Exception:
                    pass
            print("[paste] Item is in clipboard — press Ctrl+V to paste")
        else:
            try:
                subprocess.run(['xdotool', 'key', '--clearmodifiers', 'ctrl+v'],
                               check=True, capture_output=True)
            except Exception as e:
                print(f"[paste] {e} — press Ctrl+V manually")

    # ── Hotkey ────────────────────────────────────────────────────
    def _start_hotkey_thread(self):
        self._hotkey_stop = threading.Event()
        def run():
            try:
                from pynput import keyboard as kb
                hotkey = self.settings.get('hotkey') or '<super>+v'
                with kb.GlobalHotKeys({hotkey: lambda: GLib.idle_add(self._show)}):
                    self._hotkey_stop.wait()
            except Exception as e:
                print(f"[hotkey/pynput] {e} — set shortcut manually in DE settings")
        self._hotkey_thread = threading.Thread(target=run, daemon=True)
        self._hotkey_thread.start()

    def _restart_hotkey(self):
        self._hotkey_stop.set()
        time.sleep(0.1)
        self._start_hotkey_thread()

    def _show(self):
        if self._win is None:
            self._win = ClipWindow(self)
        self._win.show_popup()
        return False

    def delete_item(self, item):
        self.history = [i for i in self.history if i.hash != item.hash]
        self._save()

    def clear_all(self):
        self.history.clear()
        self._last_hash = None
        self._save()

    # ── Persistence ───────────────────────────────────────────────
    def _load(self):
        if not os.path.exists(HISTORY_FILE):
            return
        try:
            with open(HISTORY_FILE) as f:
                raw = json.load(f)
            self.history = [ClipItem.from_dict(d) for d in raw]
            if self.history:
                self._last_hash = self.history[0].hash
            print(f"Loaded {len(self.history)} saved items.")
        except Exception as e:
            print(f"[load] {e}")

    def _save(self):
        try:
            limit = self.settings.get('max_items')
            to_save = [i.to_dict() for i in self.history[:limit]
                       if not (i.ctype == 'image' and len(i.content) > 2_000_000)]
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[save] {e}")

    def run(self):
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        Gtk.main()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    lock = os.path.join(CONFIG_DIR, '.lock')
    os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        import fcntl
        lf = open(lock, 'w')
        fcntl.lockf(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        # Already running — show the window via SIGUSR1
        subprocess.run(['pkill', '-USR1', '-f', 'clipvault.py'])
        sys.exit(0)
    ClipVault().run()
