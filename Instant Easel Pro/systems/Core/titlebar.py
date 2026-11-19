"""
titlebar.py: the app's own title bar, in the blue of its buttons, with the painted window buttons (images/UI/Window Buttons:
title_min, title_max, title_restore, title_close).

Windows can't repaint the - [] X buttons on its own title bar, so in "Painted" mode (Settings > Display > Title bar) the main
window has no Windows frame (Tk's overrideredirect) and this bar is the top row of the window instead:

    [icon] Instant Easel Pro ............................................ [-] [] [X]

    drag the bar          moves the window (Windows' own move, so it snaps like any window)
    double-click the bar  windowed <-> maximized
    -                     windowed: to the taskbar.  maximized: back to the window (as Retro TV)
    [] / two squares      windowed: maximize.        maximized: full screen (Esc or F11 comes back)
    X                     closes the app

Without the Windows frame the window still gets its taskbar button, Alt+Tab and taskbar click to minimize / restore
(WS_EX_APPWINDOW + the minimize box and system menu styles are put back on it).

"Windows" mode keeps the standard title bar; on Windows 11 it (and every pop-up window's title bar in both modes) is
coloured the same blue.
"""
import os, sys, tkinter as tk
from PIL import Image, ImageTk, ImageEnhance
import theme as T, prefs, paths

BAR_H = 32                                             # design height of the bar (pixels at the windowed size)
BUTTONS = ("title_min", "title_max", "title_close")    # left to right; title_max shows title_restore while maximized

def enabled():
    """the painted title bar is used: Windows (the frame can't be painted there) and Settings > Display > Title bar = Painted.
    INSTANT_EASEL_PAINTED_BAR=1 shows it on other systems too (for testing)"""
    if prefs.get("title_bar") == "Windows": return False
    return sys.platform == "win32" or os.environ.get("INSTANT_EASEL_PAINTED_BAR") == "1"

def _blue_rgb():
    """the middle of the painted button (images/UI/Color Wheel Menu/bar_blank.png)"""
    try:
        im = Image.open(paths.ui("Color Wheel Menu", "bar_blank.png")).convert("RGB"); return im.getpixel((im.width // 2, im.height // 2))
    except Exception: return (0, 24, 89)

def colour_windows_bar(win):
    """Windows 11: the window's own title bar in the buttons' blue, with white words (ignored on older Windows)"""
    if sys.platform != "win32": return
    try:
        import ctypes
        hwnd = int(win.wm_frame(), 16); r, g, b = _blue_rgb()
        for attr, val in ((35, r | (g << 8) | (b << 16)), (36, 0x00FFFFFF), (34, r | (g << 8) | (b << 16))):   # caption, text, border colour
            v = ctypes.c_int(val); ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), attr, ctypes.byref(v), 4)
    except Exception: pass

def colour_popups(root):
    """every pop-up window (dialogs, pickers) gets the blue title bar as it opens"""
    if sys.platform != "win32": return
    root.bind_class("Toplevel", "<Map>", lambda e: e.widget.winfo_toplevel() is e.widget and colour_windows_bar(e.widget), add="+")

class TitleBar(tk.Frame):
    """the bar itself (see the top of this file). app: the main window, which has _mode, _to_fixed, _to_maximized,
    _to_fullscreen, quit_app"""
    def __init__(self, app):
        super().__init__(app, bd=0, highlightthickness=0, height=self._h(), cursor="arrow"); self.app = app
        self.pack_propagate(False); self._src = {}; self._ph = {}; self._hover = None
        for n in BUTTONS + ("title_restore",):
            try: self._src[n] = Image.open(paths.ui("Window Buttons", n + ".png")).convert("RGBA")
            except Exception: pass
        self.bg = tk.Label(self, bd=0, highlightthickness=0); self.bg.place(x=0, y=0, relwidth=1, relheight=1)
        self.icon = tk.Label(self, bd=0, highlightthickness=0); self.icon.pack(side="left", padx=(8, 6))
        self.name = tk.Label(self, bd=0, highlightthickness=0); self.name.pack(side="left")
        self.btns = {}
        for n in reversed(BUTTONS):                                             # packed from the right: close, max, min
            b = tk.Label(self, bd=0, highlightthickness=0, cursor="hand2"); b.pack(side="right", padx=(0, 4 if n != "title_close" else 6)); self.btns[n] = b
            b.bind("<Enter>", lambda e, n=n: self._hov(n)); b.bind("<Leave>", lambda e: self._hov(None))
            b.bind("<ButtonRelease-1>", lambda e, n=n: self._press(n, e))
        for w in (self, self.bg, self.icon, self.name):
            w.bind("<ButtonPress-1>", self._drag_start); w.bind("<B1-Motion>", self._drag_move); w.bind("<Double-Button-1>", self._double)
        self.bind("<Configure>", lambda e: self._paint()); T.on_change(self._paint, zoom=True)

    # ---- size and pictures
    def _h(self): return BAR_H                                                # fixed (not zoomed): the window sizes stay exact
    def _paint(self):
        try:
            if not self.winfo_exists(): return
        except tk.TclError: return
        H = self._h()
        if int(self.cget("height")) != H: self.configure(height=H)
        W = max(1, self.winfo_width())
        key = ("bg", W, H)
        if key not in self._ph:
            try:                                                                    # the button's middle column (its gloss, top and bottom edge) across the bar
                src = Image.open(paths.ui("Color Wheel Menu", "bar_blank.png")).convert("RGBA")
                col = src.crop((src.width // 2, 0, src.width // 2 + 1, src.height)).resize((1, H), Image.LANCZOS).convert("RGB")
                self._ph = {k: v for k, v in self._ph.items() if k[0] != "bg"}; self._ph[key] = ImageTk.PhotoImage(col.resize((W, H)))
            except Exception: self._ph[key] = None
        r, g, b = _blue_rgb(); flat = "#%02x%02x%02x" % (r, g, b)
        for w in (self, self.icon, self.name, *self.btns.values()): w.configure(bg=flat)
        if self._ph[key] is not None: self.bg.configure(image=self._ph[key])
        try:
            ic = Image.open(paths.ui("App Icon", "icon-64.png")).convert("RGBA").resize((H - 8, H - 8), Image.LANCZOS)
            self._icon = ImageTk.PhotoImage(self._on_bar(ic, self.icon, H)); self.icon.configure(image=self._icon)
            words = T.paint_words(self.app.title(), max(10, int(H * 0.42)), (245, 245, 250))
            self._name = ImageTk.PhotoImage(self._on_bar(words, self.name, H)); self.name.configure(image=self._name)
        except Exception: pass
        self._buttons()
    def _on_bar(self, im, w, H):
        """im on the bar's own blue (so its see-through edges blend)"""
        bgk = [k for k in self._ph if k[0] == "bg" and self._ph[k] is not None]
        out = Image.new("RGBA", im.size, _blue_rgb() + (255,))
        if bgk:
            col = ImageTk.getimage(self._ph[bgk[0]]).convert("RGBA").crop((0, 0, 1, H)).resize((im.width, H))
            out = col.crop((0, (H - im.height) // 2, im.width, (H - im.height) // 2 + im.height))
        out.alpha_composite(im); return out
    def _buttons(self):
        H = self._h(); s = H - 6
        for n, b in self.btns.items():
            name = "title_restore" if (n == "title_max" and self.app._mode == "maximized") else n
            src = self._src.get(name)
            if src is None: b.configure(text={"title_min": "–", "title_max": "□", "title_close": "✕"}[n], fg="white"); continue
            k = (name, s, self._hover == n)
            if k not in self._ph:
                im = src.copy(); im.thumbnail((s, s), Image.LANCZOS)
                if self._hover == n:
                    a = im.getchannel("A"); im = ImageEnhance.Brightness(im.convert("RGB")).enhance(1.2).convert("RGBA"); im.putalpha(a)
                self._ph[k] = ImageTk.PhotoImage(self._on_bar(im, b, H))
            b.configure(image=self._ph[k])
    def refresh(self): self._buttons()
    def _hov(self, n): self._hover = n; self._buttons()

    # ---- what the buttons do (the same as the Windows buttons did)
    def _press(self, n, e):
        b = self.btns[n]
        if not (0 <= e.x < b.winfo_width() and 0 <= e.y < b.winfo_height()): return     # let go off the button: nothing
        a = self.app
        if n == "title_close": return a.quit_app()
        if n == "title_min": return a._to_fixed() if a._mode == "maximized" else minimize(a)
        if n == "title_max": return a._to_fullscreen() if a._mode == "maximized" else a._to_maximized()
    def _double(self, e):
        a = self.app; a._to_fixed() if a._mode == "maximized" else a._to_maximized()

    # ---- moving the window by the bar
    def _drag_start(self, e):
        self._grab = (e.x_root - self.app.winfo_x(), e.y_root - self.app.winfo_y())
        if self.app._mode != "fixed" or sys.platform != "win32": return
        try:                                                                        # Windows moves it itself (smooth, and it snaps)
            import ctypes; u = ctypes.windll.user32; hwnd = int(self.app.wm_frame(), 16)
            u.ReleaseCapture(); u.SendMessageW(ctypes.c_void_p(hwnd), 0x00A1, 2, 0); self._grab = None   # WM_NCLBUTTONDOWN, HTCAPTION
        except Exception: pass
    def _drag_move(self, e):
        if self.app._mode != "fixed" or getattr(self, "_grab", None) is None: return
        self.app.geometry(f"+{e.x_root - self._grab[0]}+{e.y_root - self._grab[1]}")

# ---------------------------------------------------------------- the window without the Windows frame
def frameless(app):
    """no Windows frame on the main window (call before it is first shown)"""
    app.overrideredirect(True)

def keep_on_taskbar(app):
    """a frameless window still gets its taskbar button, Alt+Tab, and taskbar click to minimize / restore"""
    if sys.platform != "win32" or getattr(app, "_tb_done", False): return
    try:
        import ctypes; u = ctypes.windll.user32; hwnd = ctypes.c_void_p(int(app.wm_frame(), 16))
        ex = u.GetWindowLongW(hwnd, -20); u.SetWindowLongW(hwnd, -20, (ex | 0x00040000) & ~0x00000080)   # WS_EX_APPWINDOW, not a tool window
        st = u.GetWindowLongW(hwnd, -16); u.SetWindowLongW(hwnd, -16, st | 0x00020000 | 0x00080000)       # minimize box, system menu
        app._tb_done = True; app.withdraw(); app.update_idletasks(); app.deiconify()                     # re-shown, so the taskbar picks it up
    except Exception as ex: prefs.log_error(type(ex), ex, ex.__traceback__)

def minimize(app):
    """to the taskbar"""
    app._was_iconic = True
    if sys.platform == "win32":
        try:
            import ctypes; ctypes.windll.user32.ShowWindow(ctypes.c_void_p(int(app.wm_frame(), 16)), 6); return   # SW_MINIMIZE
        except Exception: pass
    try: app.overrideredirect(False); app.iconify()                              # (other systems: the frame comes back while it's down)
    except tk.TclError: pass

def work_area(app):
    """the screen less the taskbar: (x, y, w, h)"""
    if sys.platform == "win32":
        try:
            import ctypes
            class R(ctypes.Structure): _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]
            wa = R()
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(wa), 0): return wa.l, wa.t, wa.r - wa.l, wa.b - wa.t
        except Exception: pass
    return 0, 0, app.winfo_screenwidth(), app.winfo_screenheight() - 40
