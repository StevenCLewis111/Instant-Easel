"""
main.py: Instant Easel, the drawing app. One window, two tabs:
  Drawing:   the drawing studio, filling the whole page (brushes, canvas, layers, colour)
  Settings:  theme, general, display, shortcuts, backup & reset, about
"""
import os, sys, queue, shutil, json, time
import tkinter as tk
# every script lives in a folder under systems/ (sorted by tab): they're all found by name, from any folder
BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, BASE)
for _d, _dirs, _files in os.walk(os.path.join(BASE, "systems")):
    _dirs[:] = sorted(x for x in _dirs if not x.startswith((".", "__")))
    if any(f.endswith(".py") for f in _files) and _d not in sys.path: sys.path.insert(1, _d)
import paths
from PIL import Image, ImageTk
import theme as T
import features, draw_studio, prefs, settings_pages as SP, edit_pages as EP
import crash, skin, ui_art as UA

APP_NAME = "Instant Easel"
DESIGN = (1560, 920)
EDGE = 20                       # gap between the window's edge and the app's outer border, the same all the way round (design pixels)            # the size the app is designed at; any other window size zooms the whole UI by the same factor
ZMIN, ZMAX = 0.4, 3.0
# The windowed ("minimized window") size, the same rule as Retro TV: 1280x720 on a 16:9-family screen, 1024x768 on a 4:3-family
# screen, shrunk (keeping its shape) only if it would not fit inside the screen less 80 px. It never changes after that.
WINDOW_16_9, WINDOW_4_3 = (1280, 720), (1024, 768)
_ASPECT_43_FAMILY_MAX_RATIO = ((8.0 / 5.0) + (16.0 / 9.0)) / 2.0

def fixed_window_size(sw, sh):
    tw, th = WINDOW_4_3 if (sw / max(1, sh)) < _ASPECT_43_FAMILY_MAX_RATIO else WINDOW_16_9
    mw, mh = max(320, sw - 80), max(240, sh - 80)
    if tw > mw or th > mh:
        k = min(mw / tw, mh / th); tw, th = max(1, int(tw * k)), max(1, int(th * k))
    return tw, th

def target_zoom(w, h):
    """the whole UI is one picture at the DESIGN size: every window size shows that same layout, scaled to fit (never rearranged)"""
    return max(ZMIN, min(ZMAX, min(w / DESIGN[0], h / DESIGN[1])))

# ---------------------------------------------------------------- zoom: every size in the UI scales together with the window
# Each widget remembers its design-size text, padding and border values. When the window size settles, one zoom factor
# (window / DESIGN) is applied to all of them at once, so nothing drifts and the proportions never change.
_PIX_OPT = ("padx", "pady", "bd", "borderwidth", "highlightthickness", "wraplength", "insertwidth", "selectborderwidth")
_PIX_GEO = ("padx", "pady", "ipadx", "ipady")
_zctx = [None]                                                    # (kind, widget) while that widget's own options or geometry are being set
_orig_options = getattr(tk, "_zoom_orig", None) or tk.Misc._options                  # the real tkinter option converter

def _znum(v): return isinstance(v, (int, float)) and not isinstance(v, bool)
def _zpx(v, z): return v if (not _znum(v) or v <= 0) else max(1, int(round(v * z)))

def _zscale(kind, cnf, z):
    out = dict(cnf)
    for k in (_PIX_GEO if kind in ("pack", "grid") else _PIX_OPT):
        if k in out:
            v = out[k]
            out[k] = tuple(_zpx(i, z) for i in v) if isinstance(v, (tuple, list)) and all(_znum(i) for i in v) else _zpx(v, z)
    f = out.get("font") if kind == "opt" else None
    if isinstance(f, (tuple, list)) and len(f) >= 2 and _znum(f[1]):
        out["font"] = (f[0], (-1 if f[1] < 0 else 1) * max(5, int(round(abs(f[1]) * z)))) + tuple(f[2:])
    return out

def _zoom_options(self, cnf, kw=None):
    ctx = _zctx[0]
    if ctx and ctx[1] is self:
        cnf = tk._cnfmerge((cnf, kw)) if kw else tk._cnfmerge(cnf)
        if isinstance(cnf, dict):
            rec = self.__dict__.setdefault("_zd", {}).setdefault(ctx[0], {})
            for k in (_PIX_GEO if ctx[0] in ("pack", "grid") else _PIX_OPT + ("font",)):
                if k in cnf:
                    if _zscale(ctx[0], {k: cnf[k]}, 2.0)[k] != cnf[k]: rec[k] = cnf[k]      # a design size: remember it
                    else: rec.pop(k, None)                                                    # zero, text or a measured value: leave it alone
            return _orig_options(self, _zscale(ctx[0], cnf, T.Z))
    return _orig_options(self, cnf, kw)

def _zwrap(kind, fn):
    def run(self, *a, **k):
        prev = _zctx[0]; _zctx[0] = (kind, self)
        try: return fn(self, *a, **k)
        finally: _zctx[0] = prev
    run.__name__ = getattr(fn, "__name__", "run"); run.__doc__ = fn.__doc__
    return run

def _zgeo(kind, fn):
    inner = _zwrap(kind, fn)
    def run(self, *a, **k):
        try:
            if self.winfo_manager() != kind: self.__dict__.setdefault("_zd", {}).pop(kind, None)      # (re)placed from scratch: forget the old pads
        except tk.TclError: pass
        return inner(self, *a, **k)
    run.__name__ = getattr(fn, "__name__", "run"); run.__doc__ = fn.__doc__
    return run

if not getattr(tk, "_zoom_installed", False):
    tk._zoom_orig = _orig_options; tk.Misc._options = _zoom_options
    tk.BaseWidget.__init__ = _zwrap("opt", tk.BaseWidget.__init__)
    tk.Misc.configure = tk.Misc.config = _zwrap("opt", tk.Misc.configure)
    tk.Pack.pack_configure = tk.Pack.pack = _zgeo("pack", tk.Pack.pack_configure)
    tk.Grid.grid_configure = tk.Grid.grid = _zgeo("grid", tk.Grid.grid_configure)
    tk._zoom_installed = True

def _zreapply(w, z):
    for kind, rec in list(w.__dict__.get("_zd", {}).items()):
        if not rec: continue
        try:
            args = _orig_options(w, _zscale(kind, rec, z))
            if kind == "opt": w.tk.call((w._w, "configure") + args)
            elif w.winfo_manager() == kind: w.tk.call((kind, "configure", w._w) + args)             # never re-manage a hidden page
        except tk.TclError: pass

_zoom_gen = [0]

def _zoom_one(w, z):
    if getattr(w, "_zz", None) != z: _zreapply(w, z); w._zz = z

def zoom_to(root, z):
    """re-apply every remembered size at zoom z (1.0 = the design size). What you can see is done at once; hidden pages and
    panels catch up in the background a few milliseconds at a time (and any page is brought up to date before it's shown)"""
    T.Z = z; _zoom_gen[0] += 1; gen = _zoom_gen[0]; later = []
    def walk(w):
        _zoom_one(w, z)
        for c in w.winfo_children():
            try: seen = c.winfo_ismapped() or isinstance(c, tk.Toplevel)
            except tk.TclError: continue
            (walk if seen else later.append)(c)
    walk(root); T._notify(zoom_only=True); root.update_idletasks()
    stack = later[::-1]
    def catch_up():
        if gen != _zoom_gen[0]: return                                           # zoomed again meanwhile: that pass takes over
        t0 = time.perf_counter()
        while stack and time.perf_counter() - t0 < 0.006:
            w = stack.pop()
            try: _zoom_one(w, z); stack.extend(w.winfo_children())
            except tk.TclError: pass
        if stack: root.after(10, catch_up)
    root.after(40, catch_up)

def zoom_ready(w):
    """bring one page (and everything in it) to the current zoom now, before it's shown"""
    z = T.Z; stack = [w]
    while stack:
        x = stack.pop()
        try: _zoom_one(x, z); stack.extend(x.winfo_children())
        except tk.TclError: pass

def _dot(master, color, size):
    """status dot: drawn at the current zoom, redrawn when it changes"""
    c = tk.Canvas(master, highlightthickness=0, bg=master["bg"])
    def draw():
        n = max(4, int(round(size * T.Z))); c.configure(width=n, height=n, bg=c.master["bg"]); c.delete("all"); c.create_oval(1, 1, n - 1, n - 1, fill=color, outline="")
    draw(); T.on_change(draw, zoom=True); return c
def _outlined(im, color):
    """a cut-out with an outline round its edge in the theme colour (painted over the outer few pixels, so the guy's own blue
    outline is covered and the girl gets one to match)"""
    from PIL import ImageFilter
    a = im.getchannel("A").point(lambda v: 255 if v > 110 else 0); t = max(2, round(im.height * 0.013))
    inner = a.filter(ImageFilter.MinFilter(2 * t + 1)); import numpy as _np
    band = _np.clip(_np.asarray(a, _np.int16) - _np.asarray(inner, _np.int16), 0, 255).astype(_np.uint8)
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5)); ring = Image.new("RGBA", im.size, (r, g, b, 255))
    ring.putalpha(Image.fromarray(_np.minimum(band, _np.asarray(im.getchannel("A")))).filter(ImageFilter.GaussianBlur(0.6)))
    out = im.copy(); out.alpha_composite(ring); return out

def icon_file(name):
    """the app's icons: images/UI/App Icon/"""
    return paths.ui("App Icon", name)
def home_dir(): return paths.HOME
PREFS = paths.json_file("instant_easel_theme.json")




def themed_frame(parent):
    f = tk.Frame(parent, bg=parent["bg"]); T.on_change(lambda: f.configure(bg=f.master["bg"])); return f

class InstantEasel(tk.Tk):
    def __init__(self, splash=False):
        if sys.platform == "win32":                                   # sharp at 125%/150% display scaling, and nothing drifts (Windows won't bitmap-stretch the app)
            try: import ctypes; ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                try: ctypes.windll.user32.SetProcessDPIAware()
                except Exception: pass
            try: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("InstantEasel.App")   # the taskbar shows Instant Easel's icon, not Python's
            except Exception: pass
        super().__init__(); self.withdraw()                           # never seen half-built: shown once everything is laid out (show_window)
        self._hide()
        try: import ui_art; ui_art.preload_in_background()            # the brush and toolbar pictures load on another thread while the window is built
        except Exception: pass
        self.tk.call("tk", "scaling", 96 / 72)    # one fixed scale: text and pictures keep the same size relative to each other
        sys.excepthook = prefs.log_error; self.report_callback_exception = self._on_error
        T.SCALE = prefs.size("text_size"); T.init_fonts(self); self.title(APP_NAME)
        self._mode = "fixed"; self._guard_until = 0.0; self._was_iconic = False; self._sub_hwnd = None; self._wndproc_ptr = None; self._orig_wndproc = None
        self.protocol("WM_DELETE_WINDOW", self.quit_app); self.bind("<F11>", lambda e: self.set_fullscreen(self._mode != "fullscreen"))
        self.bind("<Escape>", lambda e: self._mode == "fullscreen" and self._to_maximized())           # Esc: full screen -> maximized (title bar back)
        self.bind("<Map>", self._on_map, add="+"); self.bind("<Unmap>", self._on_unmap, add="+"); self.bind("<Configure>", self._on_root_configure, add="+")
        try:
            # every size, so the title bar, taskbar, Alt+Tab and pop-up windows each pick a crisp one (True: every window of the app uses it)
            self._icons = [ImageTk.PhotoImage(Image.open(icon_file(f"icon-{n}.png"))) for n in (256, 128, 64, 48, 32, 16)]
            self.iconphoto(True, *self._icons)
            if sys.platform == "win32": self.iconbitmap(default=icon_file("icon.ico"))       # the multi-size Windows icon file
        except Exception: pass
        self._load_theme()                                                       # (before the splash: it's drawn in the theme's colours)
        self._splash = Splash(self) if splash else None
        self.q = queue.Queue(); T.banner_host(self); self.after(100, self._poll); self.after(500, self._beat); self.after(60000, self._autosave); self._load_theme(); self._start_zoom()
        self.configure(bg=T.PALETTE["bg"]); T.on_change(lambda: self.configure(bg=T.PALETTE["bg"]))
        # zoom layout: the app is designed at DESIGN size; the window can be any size and everything (text, buttons, spacing) scales with it
        self.view_cv = tk.Canvas(self, highlightthickness=0, bg=T.PALETTE["bg"], bd=0)
        self.view_cv.grid(row=0, column=0, sticky="nsew"); self.rowconfigure(0, weight=1); self.columnconfigure(0, weight=1)
        self.content = tk.Frame(self.view_cv, bg=T.PALETTE["bg"]); self.content.pack_propagate(False)
        self._cwin = self.view_cv.create_window((0, 0), window=self.content, anchor="center"); self._zoom_job = None  # DESIGN x zoom, centred by _layout_view
        T.on_change(lambda: (self.view_cv.configure(bg=T.PALETTE["bg"]), self.content.configure(bg=T.PALETTE["bg"])))
        self.view_cv.bind("<Configure>", self._on_window_size)
        self.frame = T.Panel(self.content, pad=16); self.frame.pack(fill="both", expand=True, padx=EDGE, pady=EDGE); self.frame.configure(pady=0)   # the same gap on all four sides   # the title sits right under the top border
        names = [m for m, _, _ in features.MENUS]
        top = tk.Frame(self.frame, bg=self.frame["bg"]); top.pack(fill="x", pady=(0, 10)); self.top = top    # guy | logo over tabs | girl
        T.on_change(lambda: top.configure(bg=self.frame["bg"]))
        top.columnconfigure(0, weight=1); top.columnconfigure(2, weight=1)
        self.logo_lbl = None
        try:
            import numpy as _np
            lg = Image.open(paths.ui("Header", "title-logo.png")); _al = _np.asarray(lg)[..., 3] > 40
            _ys, _xs = _np.nonzero(_al); self.logo_src = lg.crop((int(_xs.min()), int(_ys.min()), int(_xs.max()) + 1, int(_ys.max()) + 1))   # painted area only
            self.logo = ImageTk.PhotoImage(self.logo_src.resize((517, 150), Image.LANCZOS))     # resized to the tab row's width once it's laid out
            self.logo_lbl = tk.Label(top, image=self.logo, bg=top["bg"], bd=0, padx=0, pady=0, highlightthickness=0)
            self.logo_lbl.grid(row=0, column=1, pady=(7, 12))                                  # the brush tip sits 7 px under the top border
            T.on_change(lambda: self.logo_lbl.configure(bg=self.frame["bg"]))
        except Exception:
            T.Title(top, APP_NAME.upper(), big=True).grid(row=0, column=1, pady=(0, 10))
        self.tabs = skin.tabs(T.Tabs(top, names, self.show)); self.tabs.grid(row=1, column=1)      # painted tabs (brand/icon/skin)
        self.mascot_src, self.mascot_lbl = {}, {}
        for f, col, sticky in (("mascot-guy.png", 0, "sw"), ("mascot-girl.png", 2, "se")):          # both look in at the logo
            try:
                im = Image.open(paths.ui("Header", f)).convert("RGBA"); import numpy as _np
                box = im.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()            # painted area only: no see-through margin at the sides or
                if box: im = im.crop(box)                                                          # the bottom, so the feet really touch the line
                self.mascot_src[col] = im
                lbl = tk.Label(self.frame, bg=top["bg"], bd=0, padx=0, pady=0, highlightthickness=0)   # placed (see _size_mascots): standing on the border below
                self.mascot_lbl[col] = lbl
                T.on_change(lambda l=lbl: l.configure(bg=self.frame["bg"]))
            except Exception: pass
        self.after_idle(self._size_mascots); T.on_change(lambda: self.mascot_src and self.after_idle(self._size_mascots))   # outline follows the theme colour
        self.frame.bind("<Configure>", lambda e: T.defer(self, "header", 80, self._paint_header), add="+")   # the header picture follows the window size
        self.after_idle(lambda: self.body.bind("<Configure>", lambda e: T.defer(self, "mascots", 60, self._size_mascots), add="+"))   # the line under the header moved: stand on it again

        built = {"Draw": draw_studio.DrawStudio, "Theme": ThemePage, "About": AboutPage, "General": SP.GeneralPage, "Display": SP.DisplayPage,
                 "Pen & Tablet": SP.PenPage, "Shortcuts": SP.ShortcutsPage, "Backup & Reset": SP.BackupPage, **EP.page_classes()}
        self.body = T.Panel(self.frame, pad=0, inner=True); self.body.pack(fill="both", expand=True, pady=(0, 14))
        self.pages = {}
        for i, (m, _, tools) in enumerate(features.MENUS):
            if self._splash: self._splash.step(i / (len(features.MENUS) + 1), f"LOADING {m.upper()}…")
            self.pages[m] = Section(self.body, self, m, tools, built)
        st = prefs.get("start_tab"); st = prefs.get("last_tab") if st == "Last used" else st
        st = features.OLD_TAB_NAMES.get(st, st)                                                 # settings saved with the old tab names still work
        self.show(st if st in self.pages else "Drawing"); self.tabs.active = st if st in self.pages else "Drawing"; self.tabs._style()

    def _size_mascots(self):
        """the logo a little wider than its own shape, centred over the tabs; the guy and girl stand on the line under the header"""
        self.update_idletasks()
        if getattr(self, "logo_src", None) is not None and self.tabs.winfo_width() > 50:
            kids = list(self.tabs.btns.values())                                               # the tab buttons only (not the header picture behind them)
            if kids[-1].winfo_width() < 20: return self.after(50, self._size_mascots)           # tabs not laid out yet: measure again shortly
            lh0 = int(round(150 * T.Z)); tw = int(self.logo_src.width * lh0 / self.logo_src.height * 1.3)   # its own shape, stretched a little side to side
            lh = int(round(150 * T.Z))
            if abs(self.logo.width() - tw) > 1 or self.logo.height() != lh:
                lc = self.__dict__.setdefault("_logo_cache", {})                               # sizes seen before (switching modes back and forth) are kept
                if (tw, lh) not in lc: lc[(tw, lh)] = self.logo_src.resize((tw, lh), Image.LANCZOS)
                self._logo_pil = lc[(tw, lh)]
                self.logo = ImageTk.PhotoImage(self._logo_pil); self.logo_lbl.configure(image=self.logo)
                self.update_idletasks()
        for lbl in self.mascot_lbl.values(): lbl.configure(image="", width=0, height=0)   # the old-size pictures would hold the header tall
        self.update_idletasks()                                                 # (after a big window turns small); measure it without them
        body_y = self.body.winfo_y() if hasattr(self, "body") else self.top.winfo_y() + self.top.winfo_height()
        h = body_y - self.top.winfo_y() - 4                                    # from 4 px under the top border down to the green line under the header
        if h < 40: return self.after(50, self._size_mascots)
        self._mph = {}
        mid = max(self.tabs.winfo_reqwidth(), self.top.grid_bbox(1, 0, 1, 1)[2])            # the middle column: the logo or the tab row, whichever is wider
        # locked to the windowed layout: a wider window (full screen, maximized) adds width that the header picture fills, but the guy
        # and girl keep the places they have in the window, scaled up, rather than sliding out to the new edges
        fw, fh = fixed_window_size(self.winfo_screenwidth(), self.winfo_screenheight())
        extra = max(0, int(self.view_cv.winfo_width() - T.Z * fw / target_zoom(fw, fh)))
        lock_w = self.top.winfo_width() - extra; x0 = self.top.winfo_x() + extra // 2
        room = (lock_w - mid) // 2 - int(round(18 * T.Z)) - 2                              # the space beside the logo and tab row
        for col, src in self.mascot_src.items():
            k = h / src.height
            if room > 40 and src.width * k > room: k = room / src.width                     # too wide for its space: smaller, never cut off
            self._mdz = getattr(self, "_mdz", {})
            if abs(self.view_cv.winfo_width() - fw) <= 4 and abs(self.view_cv.winfo_height() - fh) <= 4: self._mdz[col] = src.height * k / T.Z   # the windowed size (design pixels)...
            elif col in self._mdz: k = min(h, self._mdz[col] * T.Z) / src.height           # ...kept, scaled, at every other window size
            mc = self.__dict__.setdefault("_mascot_cache", {}); mk = (col, max(1, int(src.width * k)), max(1, int(src.height * k)))
            if mk not in mc: mc[mk] = src.resize(mk[1:], Image.LANCZOS)
            im = mc[mk]
            over = int(self.frame.cget("highlightthickness")) - (body_y - im.height)   # rows that would reach the top border or above it
            if over > 0: im = im.crop((0, over, im.width, im.height))            # cut those off, so nothing shows on or above the top line
            self._mph[col] = ImageTk.PhotoImage(im); self.mascot_lbl[col].configure(image=self._mph[col], width=0, height=0)   # 0 = the picture's own size
            self._mpil = getattr(self, "_mpil", {}); self._mpil[col] = im
            x = x0 if col == 0 else x0 + lock_w - im.width                          # outer edge where the page's border is in the windowed layout
            self.mascot_lbl[col].place(x=x, y=body_y - im.height, bordermode="outside")      # flat bottom standing on the line
        self.update_idletasks()
        if any(self.mascot_lbl[c].winfo_width() + 1 < self._mpil[c].width for c in self._mpil) and getattr(self, "_fit_tries", 0) < 2:
            self._fit_tries = getattr(self, "_fit_tries", 0) + 1; return self.after(30, self._size_mascots)    # the layout moved: measure once more
        self._fit_tries = 0
        self._paint_header()
        if not getattr(self, "_settling", False) and not getattr(self, "_in_transition", False):   # once more when the window has settled (a mode change has already waited)
            self._settling = True
            self.after(150, lambda: (self._size_mascots(), setattr(self, "_settling", False)))

    # ---------------- the header's picture (images/UI/Header/header-background.png): the waterfall, trees and stream behind the guy,
    # the girl, the logo and the tabs. Tk can't draw see-through widgets on a picture, so a backdrop fills the header and every piece
    # on it carries the matching slice of the picture behind it.
    HEADER_CROP, HEADER_DIM = 0.70, 0.85                                       # which band of the picture (from its top), and how bright
    def _header_band(self, W, H):
        key = (W, H, T.PALETTE["panel"])
        if getattr(self, "_hband_key", None) == key: return self._hband
        bc = self.__dict__.setdefault("_hband_cache", {})                         # the header for sizes seen before (switching modes back and forth)
        if key in bc: self._hband, self._hband_key, self._hcache = bc[key]; return self._hband
        src = getattr(self, "_hsrc", None)
        if src is None:
            try: src = self._hsrc = Image.open(paths.ui("Header", "header-background.png")).convert("RGBA")
            except Exception: self._hsrc = False; return None
        if src is False: return None
        from PIL import ImageEnhance
        s = src.resize((W, max(H, round(src.height * W / src.width))), Image.LANCZOS)
        top = min(round(s.height * self.HEADER_CROP), s.height - H); band = s.crop((0, top, W, top + H))
        rgb = ImageEnhance.Brightness(band.convert("RGB")).enhance(self.HEADER_DIM).convert("RGBA"); rgb.putalpha(band.getchannel("A"))
        out = Image.new("RGBA", (W, H), T.PALETTE["panel"]); out.alpha_composite(rgb)
        self._hband, self._hband_key = out, key; self._hcache = {}
        if len(bc) > 4: bc.clear()
        bc[key] = (out, key, self._hcache); return out

    def _hbox(self, w):
        """where a widget sits on the header picture"""
        fx, fy = self.frame.winfo_rootx() + self._hl, self.frame.winfo_rooty() + self._hl
        return w.winfo_rootx() - fx, w.winfo_rooty() - fy, w.winfo_width(), w.winfo_height()

    def _on_picture(self, w, im):
        """a PhotoImage of im (RGBA) sitting on its slice of the header picture"""
        band = getattr(self, "_hband", None)
        if band is None: return ImageTk.PhotoImage(im)
        x, y, ww, wh = self._hbox(w); W, H = im.size                         # the picture's own size (never the widget's old one)
        x, y = x + (ww - W) // 2, y + (wh - H) // 2                              # where Tk will centre it in the widget
        key = (id(im), x, y, W, H, id(band))
        if key in self._hcache: return self._hcache[key]
        piece = band.crop((x, y, x + W, y + H)); piece.alpha_composite(im)
        if len(self._hcache) > 200: self._hcache.clear()
        self._hcache[key] = ph = ImageTk.PhotoImage(piece); return ph

    def _tab_under(self, w, ph):
        im = ImageTk.getimage(ph); im.load(); w._on = self._on_picture(w, im); return w._on       # the button keeps its own picture alive

    def _paint_header(self):
        if not getattr(self, "logo_lbl", None): return
        self.update_idletasks()
        self._hl = int(self.frame.cget("highlightthickness")); W = self.frame.winfo_width() - 2 * self._hl
        H = self.body.winfo_y() - self._hl if hasattr(self, "body") else self.top.winfo_y() + self.top.winfo_height()
        if W < 50 or H < 30: return
        band = self._header_band(W, H)
        if band is None: return
        for name, master in (("_bd_frame", self.frame), ("_bd_top", self.top), ("_bd_tabs", self.tabs)):
            lbl = getattr(self, name, None)
            if lbl is None:
                lbl = tk.Label(master, bd=0, highlightthickness=0, padx=0, pady=0, bg=T.PALETTE["panel"]); setattr(self, name, lbl)
                if master is self.frame: lbl.place(x=self._hl, y=self._hl, width=W, height=H, bordermode="outside")   # from the frame's edge, inside its green border
                else: lbl.place(x=0, y=0, relwidth=1, relheight=1)
                lbl.lower()
            if master is self.frame: lbl.place_configure(x=self._hl, y=self._hl, width=W, height=H, bordermode="outside")
            x, y, ww, wh = self._hbox(master) if master is not self.frame else (0, 0, W, H)
            ph = ImageTk.PhotoImage(band.crop((x, y, x + max(1, ww), y + max(1, wh)))); lbl.configure(image=ph); lbl._ph = ph
        lp = getattr(self, "_logo_pil", None)
        if lp is not None and lp.size == (self.logo.width(), self.logo.height()): self._logo_on = self._on_picture(self.logo_lbl, lp); self.logo_lbl.configure(image=self._logo_on)
        for col, im in getattr(self, "_mpil", {}).items():
            ph = self._on_picture(self.mascot_lbl[col], im); self.mascot_lbl[col].configure(image=ph); self.mascot_lbl[col]._on = ph
        for b in self.tabs.btns.values():
            if getattr(b, "_skin", None) is not None:
                b.tk.call(b._w, "configure", "-bd", 0, "-highlightthickness", 0)          # no border round the picture (it would show a plain colour)
                b._under = self._tab_under; b._skin["ph"] = None; skin.draw(b)
        for w in [self.logo_lbl] + list(self.mascot_lbl.values()): w.tk.call(w._w, "configure", "-bd", 0, "-highlightthickness", 0)

    def goto(self, tab, page=None):
        """open a tab (and one of its pages), with the tab row showing it"""
        self.show(tab); self.tabs.active = tab; self.tabs._style()
        if page: self.pages[tab].select(page)

    def show(self, name, remember=True):
        if getattr(self, "_shown_tab", None) == name and self.pages[name].winfo_manager(): return
        T.tab_changed(self)                                                      # messages don't follow you to another tab
        hub = getattr(self, "edit_hub", None)                                    # Editing works on the Drawing picture: leaving it puts the edit in
        if hub is not None and getattr(self, "_shown_tab", None) == "Editing" and name != "Editing": hub.leave()
        with T.frozen(self):                                                     # the old tab stays on screen until the new one is complete
            zoom_ready(self.pages[name]); self.pages[name].pack(fill="both", expand=True)
            for n, p in self.pages.items():
                if n != name: p.pack_forget()
            self._shown_tab = name
        if hub is not None and name == "Editing": hub.enter()
        if remember: prefs.set("last_tab", name)

    # ---------------- start-up: hidden until ready, every page laid out once, then shown in one go
    def _hide(self):
        try: self.attributes("-alpha", 0.0)
        except tk.TclError: pass

    def _unhide(self, steps=5):
        """a short fade in (instant where the system has no window transparency)"""
        def fade(i=1):
            try: self.attributes("-alpha", min(1.0, i / steps))
            except tk.TclError: return
            if i < steps: self.after(16, fade, i + 1)
        fade()

    def _settle(self, timeout=1.5, quick=False):
        """wait until the window has its final size (a maximize can arrive in steps), then zoom once.
        quick: a mode change: done as soon as the size has changed and held for two looks (or held from the start for a few)"""
        end = time.monotonic() + timeout; last = None; same = 0; first = None
        while time.monotonic() < end:
            self.update()
            size = (self.view_cv.winfo_width(), self.view_cv.winfo_height())
            if first is None: first = size
            same = same + 1 if size == last else 0; last = size
            if quick and size[0] > 50 and ((size != first and same >= 2) or same >= 6): break
            if not quick and same >= 3 and size[0] > 50: break
            time.sleep(0.01 if quick else 0.015)
        if self._zoom_job: self.after_cancel(self._zoom_job); self._zoom_job = None
        self._rezoom(now=True)

    def _load_cutout_ai(self):
        """the drawing studio's cut-out AI (built into the app), loaded while the splash shows: ready on the first click"""
        try:
            import ai_cutout
            if not (ai_cutout.runtime_ok() and (ai_cutout.have("subject") or ai_cutout.have("sam"))): return
            if self._splash: self._splash.step(0.97, "LOADING THE CUT-OUT AI…")
            ai_cutout.preload()
        except Exception: prefs.log_note("loading the cut-out AI at start-up")

    def warm_up(self):
        """visit every tab and every page once while the window is still invisible, so each one is laid out at the real size and its
        pictures are made: the first visit later is as quick and still as every other one"""
        t0 = time.perf_counter(); start = getattr(self, "_shown_tab", None)
        keep = {n: getattr(sec, "current", None) for n, sec in self.pages.items()}
        names = list(self.pages)
        for i, n in enumerate(names):
            if self._splash: self._splash.step(0.8 + 0.2 * i / len(names), "GETTING READY…")
            sec = self.pages[n]; self.show(n, remember=False)
            for sub in list(sec.pages):
                sec.select(sub); T.flush(self)
            if keep[n]: sec.select(keep[n])
        if start: self.show(start, remember=False)
        T.flush(self); self._warm_ms = int((time.perf_counter() - t0) * 1000)

    # ---------------- window: fixed layout, scroll bars, full screen, safeguards
    # ---------------- Editing history: undo / redo / jump to any step



    # ---------------- window modes, the same as Retro TV:
    #   fixed window   the exact windowed size (fixed_window_size), centred, not drag-resizable; title bar has  -  []  X
    #   []  maximize   native maximize: title bar stays, fills the work area (taskbar still showing)
    #   [][] restore   (only while maximized) goes to borderless full screen
    #   -   minimize   from the fixed window: to the taskbar. While maximized: back to the fixed window instead
    #   taskbar restore always comes back as the fixed window, centred
    #   Esc            full screen -> maximized (the windowed full-screen size).   F11: full screen on / off (off = maximized).   X: quit
    # The UI is the same in every mode: one layout at the DESIGN size, zoomed to fit the window.

    def _fixed_geo(self):
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight(); w, h = fixed_window_size(sw, sh)
        return w, h, f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2)}"   # centred the same way Retro TV places its window

    def _start_zoom(self):
        """zoom for the size the window is about to open at, set before any widget is built (_rezoom corrects it if it opens differently)"""
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight(); mode = prefs.get("window_mode")
        if mode == "Full screen": w, h = sw, sh
        elif mode == "Maximized": w, h = sw, sh - 40
        else: w, h, _ = self._fixed_geo()
        T.Z = target_zoom(w, h)

    def _on_window_size(self, e):
        """keep the UI centred; once the size settles it is zoomed so everything keeps the same proportions. Painting is held from the
        first size change until the new zoom is finished, so a maximize / restore shows the old layout, then the new one: no steps between"""
        if self._zoom_job: self.after_cancel(self._zoom_job)
        self._layout_view()
        if getattr(self, "_in_transition", False): self._zoom_job = None; return  # a mode change zooms once, when the size has settled
        self._zoom_job = self.after_idle(self._rezoom)                        # as soon as the size has arrived (several size events = one zoom)

    def _rezoom(self, now=False):
        self._zoom_job = None; w, h = self.view_cv.winfo_width(), self.view_cv.winfo_height()
        if w < 50 or h < 50: return
        z = target_zoom(w, h)
        with T.frozen(self):
            if abs(z - T.Z) >= 0.005: zoom_to(self, z); self._size_mascots()
            self._layout_view()

    def _layout_view(self):
        """the UI fills the whole window: the zoom sets the size of everything, and whatever room the window's shape adds goes to the
        parts that stretch (the canvas, the picture and video areas); side menus and panels keep their size. The outer border is
        always the same distance (EDGE) from every edge of the window"""
        cw, ch = self.view_cv.winfo_width(), self.view_cv.winfo_height(); w, h = cw, ch
        self.view_cv.coords(self._cwin, cw / 2, ch / 2); self.view_cv.itemconfigure(self._cwin, width=w, height=h)

    # ---- the three modes
    def _guard(self, ms=500): self._guard_until = time.monotonic() + ms / 1000      # ignore the window's own echo of a change we just made

    def _transition(self, change):
        """a window mode change without the "window drops, then the UI catches up" look: the window goes see-through, changes size,
        the UI is re-laid out and zoomed for the new size while nobody can see it, then it fades back in finished"""
        if not getattr(self, "_ready", False) or getattr(self, "_in_transition", False): return change()   # (start-up has its own hiding)
        self._in_transition = True
        try:
            self._hide(); self.update_idletasks()
            change(); self._settle(0.5, quick=True)                               # (it zooms once for the new size at the end)
            if self._zoom_job: self.after_cancel(self._zoom_job); self._zoom_job = None
        finally:
            self._in_transition = False; self._unhide(steps=4)

    def _to_fixed(self): self._transition(self._do_fixed)
    def _to_maximized(self): self._transition(self._do_maximized)
    def _to_fullscreen(self): self._transition(self._do_fullscreen)

    def _do_fixed(self):
        """the windowed size: exact, centred, nothing remembered or adjusted"""
        self._guard(); self._mode = "fixed"
        if self.attributes("-fullscreen"): self.attributes("-fullscreen", False)
        try:
            if self.state() in ("zoomed", "iconic"): self.state("normal")
        except tk.TclError: pass
        try: self.attributes("-zoomed", False)                                            # (Linux)
        except tk.TclError: pass
        _, _, geo = self._fixed_geo(); self.geometry(geo); self.update_idletasks()
        self._win_prep(); self.geometry(geo)                                              # again after the frame style changed, so the inside is exact

    def _do_maximized(self):
        self._guard(); self._mode = "maximized"
        if self.attributes("-fullscreen"): self.attributes("-fullscreen", False)
        try: self.state("zoomed")
        except tk.TclError: self.attributes("-zoomed", True)
        self.update_idletasks(); self._after_maximize()

    def _after_maximize(self):
        """keep the title bar (- [][] X), no drag-resize edge, and make sure it really covers the work area"""
        self._mode = "maximized"; self._win_prep()
        hwnd = self._hwnd()
        if hwnd:
            try:
                import ctypes; u = ctypes.windll.user32
                class R(ctypes.Structure): _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]
                wa, out = R(), R()
                if u.SystemParametersInfoW(0x0030, 0, ctypes.byref(wa), 0) and u.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(out)):
                    ww, wh = wa.r - wa.l, wa.b - wa.t
                    if not (out.r - out.l >= ww - 8 and out.b - out.t >= wh - 8):        # a maximize that changed the button but not the size
                        u.SetWindowPos(ctypes.c_void_p(hwnd), None, wa.l, wa.t, ww, wh, 0x0004 | 0x0020 | 0x0040)
            except Exception: pass

    def _do_fullscreen(self):
        self._guard(); self._mode = "fullscreen"
        self.attributes("-fullscreen", True)
        self.update_idletasks(); self._win_prep()

    def set_fullscreen(self, on):
        self._to_fullscreen() if on else self._to_maximized()                    # leaving full screen lands on maximized, like Esc

    def apply_window_mode(self):
        """the start-up mode from Settings > Display (default: the fixed window)"""
        mode = prefs.get("window_mode")
        if mode == "Full screen": self._to_fullscreen()
        elif mode == "Maximized": self._to_fixed(); self._to_maximized()
        else: self._to_fixed()

    def reset_window(self): self._to_fixed()
    def restore_window(self): self._to_fixed()                                           # always the fixed size, centred (as Retro TV)

    def show_window(self):
        first = not getattr(self, "_ready", False)
        if first: self._hide()
        if first and prefs.get("window_mode") != "Windowed":                     # while still hidden: lay out once at the windowed size, so the
            self.deiconify(); self._to_fixed(); self._settle(0.8); self._size_mascots()   # header's guy and girl get their windowed size and
        self.deiconify(); self.apply_window_mode(); self.after(50, self._win_prep)       # place to keep (scaled) when maximized or full screen
        if first:
            self._settle(); self.warm_up(); self._ready = True
            self._load_cutout_ai()
            if self._splash: self._splash.close(); self._splash = None
            self._unhide()

    # ---- watching the title-bar buttons and the taskbar
    def _on_unmap(self, e):
        if e.widget is not self: return
        try:
            if self.state() == "iconic" and self._mode != "fullscreen": self._was_iconic = True
        except tk.TclError: pass

    def _on_map(self, e):
        if e.widget is not self: return
        self._win_prep()
        if self._was_iconic:                                                              # back from the taskbar: the fixed window, centred
            self._was_iconic = False
            if self._mode != "fullscreen": self.after_idle(self._to_fixed)

    def _on_root_configure(self, e):
        """catches mode changes that skip the title-bar buttons (Win+Up / Win+Down, double-click on the title, other systems)"""
        if e.widget is not self or time.monotonic() < self._guard_until: return
        try: st = self.state()
        except tk.TclError: return
        if st == "iconic" or self.attributes("-fullscreen"): return
        if st == "normal" and sys.platform != "win32":
            try: st = "zoomed" if self.attributes("-zoomed") else st                           # (Linux reports maximize this way)
            except tk.TclError: pass
        if self._mode == "fixed" and st == "zoomed": self._mode = "maximized"; self.after_idle(self._after_maximize)
        elif self._mode == "maximized" and st == "normal": self.after_idle(self._to_fullscreen)     # [][] while maximized = full screen

    # ---- Windows: the frame style and the - / [][] buttons
    def _hwnd(self):
        if sys.platform != "win32": return 0
        try: return int(self.wm_frame(), 16) if self.winfo_ismapped() else 0
        except Exception: return 0

    def _win_prep(self):
        """Windows only. Title bar keeps - [] X, the drag-resize edge is removed (the fixed window can't be stretched), and the
        - and [][] buttons are routed the Retro TV way. Tk rebuilds its frame window when full screen is switched, so this re-runs."""
        hwnd = self._hwnd()
        if not hwnd: return
        try:
            import ctypes; u = ctypes.windll.user32; h = ctypes.c_void_p(hwnd)
            style = u.GetWindowLongW(h, -16)
            if not (style & 0x00C00000): return                                              # no caption: full screen, leave it alone
            new = (style | 0x00010000 | 0x00020000 | 0x00080000) & ~0x00040000               # + maximize, minimize, system menu; - thick frame
            if new != style:
                u.SetWindowLongW(h, -16, new); u.SetWindowPos(h, None, 0, 0, 0, 0, 0x0004 | 0x0002 | 0x0001 | 0x0020)
                if self._mode == "fixed": self._guard(); self.geometry(self._fixed_geo()[2])       # the thinner frame changed the inside: make it exact again
            if self._sub_hwnd != hwnd: self._subclass(hwnd)
            self._set_win_icon(hwnd)
        except Exception as ex: prefs.log_error(type(ex), ex, ex.__traceback__)

    def _set_win_icon(self, hwnd):
        """Windows: give the window our icon straight from icon.ico (big for the taskbar and Alt+Tab, small for the title bar), on the
        window and its class, so the taskbar can't fall back to Tk's feather or a blank one. Re-run whenever Tk rebuilds the window."""
        try:
            import ctypes; u = ctypes.windll.user32
            u.LoadImageW.restype = ctypes.c_void_p; u.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
            u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]
            u.SetClassLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            ico = icon_file("icon.ico")
            if not os.path.exists(ico): return
            if getattr(self, "_hicons", None) is None:
                big = u.LoadImageW(None, ico, 1, u.GetSystemMetrics(11), u.GetSystemMetrics(12), 0x10)     # IMAGE_ICON, SM_CXICON, LR_LOADFROMFILE
                small = u.LoadImageW(None, ico, 1, u.GetSystemMetrics(49), u.GetSystemMetrics(50), 0x10)  # SM_CXSMICON
                self._hicons = (big, small)
            big, small = self._hicons
            for h in {hwnd, u.GetParent(ctypes.c_void_p(hwnd)) or hwnd}:
                h = ctypes.c_void_p(h)
                if big: u.SendMessageW(h, 0x0080, 1, big); u.SetClassLongPtrW(h, -14, big)                # WM_SETICON ICON_BIG, GCLP_HICON
                if small: u.SendMessageW(h, 0x0080, 0, small); u.SetClassLongPtrW(h, -34, small)          # ICON_SMALL, GCLP_HICONSM
        except Exception as ex: prefs.log_error(type(ex), ex, ex.__traceback__)

    def _subclass(self, hwnd):
        import ctypes
        u = ctypes.windll.user32
        u.SetWindowLongPtrW.restype = ctypes.c_void_p; u.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        u.CallWindowProcW.restype = ctypes.c_ssize_t; u.CallWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
        u.IsIconic.argtypes = [ctypes.c_void_p]
        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t)
        orig = {}
        def proc(hw, msg, wp, lp):
            try:
                if msg == 0x0112:                                                             # WM_SYSCOMMAND
                    cmd = int(wp) & 0xFFF0
                    if cmd == 0xF020 and self._mode == "maximized":                           # - while maximized: to the fixed window, not the taskbar
                        self.q.put(self._to_fixed); return 0
                    if cmd == 0xF120 and self._mode == "maximized" and not u.IsIconic(hw):    # [][] while maximized: full screen
                        self.q.put(self._to_fullscreen); return 0
                    if cmd == 0xF030 and self._mode == "fixed":                               # []: maximize, done our way (hidden while it re-lays out)
                        self.q.put(self._to_maximized); return 0
            except Exception: pass
            return u.CallWindowProcW(orig["p"], hw, msg, wp, lp)
        ptr = WNDPROC(proc)
        prev = u.SetWindowLongPtrW(ctypes.c_void_p(hwnd), -4, ctypes.cast(ptr, ctypes.c_void_p))
        if prev:
            orig["p"] = prev; self._wndproc_ptr = ptr; self._sub_hwnd = hwnd                 # keep the pointer alive for the window's life

    def quit_app(self):
        if getattr(self, "_asking", False): return                                            # a quit prompt is already up (e.g. Close pressed again on the taskbar)
        if prefs.get("confirm_exit"):
            self._asking = True
            try: answer = T.popup(self, "QUIT INSTANT EASEL?", "Anything you haven't saved will be lost.", (("Quit", "danger"), ("Cancel", "normal")))
            finally: self._asking = False
            if answer != "Quit": return
        crash.clean_exit()                                                                    # a normal quit: nothing to recover next time
        self.destroy()

    def _on_error(self, exc, val, tb):
        """every error is logged; a pop-up only for the first of a kind each minute, and never more than one open (a repeating error
        used to stack pop-ups until the app looked frozen)"""
        prefs.log_error(exc, val, tb)
        try: T.banner(self, f"SOMETHING WENT WRONG — {val or exc.__name__}. The app carried on; details are in logs/instant_easel_errors.log")
        except Exception: pass

    # ---------------- crash recovery
    def _beat(self):
        """tell the freeze watchdog the window is still responding"""
        crash.beat(); self.after(500, self._beat)

    def _autosave(self):
        """every minute: the drawing goes to the recovery folder (only when it's changed)"""
        try:
            folder = crash.recovery_dir(); ds = self.pages["Drawing"].pages.get("Draw")
            if ds is not None: ds.autosave(folder)
        except Exception: prefs.log_error(*sys.exc_info())
        finally: self.after(60000, self._autosave)

    def after_start(self, info):
        """once the window is up: tell crash.py all is well, then deal with how the last session ended"""
        crash.running()
        if info.get("safe_mode"):
            T.banner(self, "STARTED IN SAFE MODE — it failed to start twice, so the window, start page and splash settings were reset")
        if not info.get("crashed"): return
        folder = crash.recovery_dir(); has_draw = draw_studio.DrawStudio.has_recovery(folder)
        if not has_draw: return
        what = "your drawing"
        if T.popup(self, "INSTANT EASEL CLOSED UNEXPECTEDLY", f"It saved {what} a minute or less before it closed.\nRestore it?",
                   (("Restore", "normal"), ("Discard", "danger"))) != "Restore":
            shutil.rmtree(folder, ignore_errors=True); return
        try:
            if has_draw:
                ds = self.pages["Drawing"].pages["Draw"]; self.goto("Drawing"); self.update_idletasks(); ds.restore(folder)
            T.banner(self, f"RESTORED — {what}", "success")
        except Exception:
            prefs.log_error(*sys.exc_info()); T.banner(self, "COULDN'T RESTORE — the saved work couldn't be loaded (details in logs/instant_easel_errors.log)")

    def _poll(self):
        """run work handed over by background threads. One failing item can't stop the rest (it's logged), and at most
        ~25 ms is spent per pass, so a flood of updates can't freeze the window"""
        t0 = time.perf_counter()
        try:
            while time.perf_counter() - t0 < 0.025:
                try: fn = self.q.get_nowait()
                except queue.Empty: break
                try: fn()
                except Exception: self._on_error(*sys.exc_info())
        finally:
            self.after(30, self._poll)                                                   # quick, so the - and [][] buttons answer at once

    def _load_theme(self):
        try:
            p = json.load(open(PREFS)); T.set_border_hue(p.get("border", 0.38)); T.set_background_hue(p.get("bg", 0.62), 1.0)
        except Exception: pass

class Page(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=master["bg"]); self.app = app; T.on_change(lambda: self.configure(bg=self.master["bg"]))

# ---------------------------------------------------------------- menu sections: side menu of tools with status dots
DOT = {"built": "#28c840", "partial": "#f5c400", "planned": "#5b6275"}
DOT_FILL = {"built": "green", "partial": "blue", "planned": "grey"}          # the painted dots: done, started, just a button

def status_dot(master, status, size):
    """a status dot: the painted ring (skin/dot_ring.png) filled in, or the drawn dot if that picture is missing"""
    return skin.dot(master, DOT_FILL[status], size) if UA.load("skin/dot_ring") is not None else _dot(master, DOT[status], size)

class Section(tk.Frame):
    """one top tab: a side menu of its tools and the selected tool's page (which tools are finished is kept in docs/ROADMAP.md, not shown).
    Everything is laid out by pack, so nothing is measured or re-placed: the side column is [title] / [buttons, spread evenly to the bottom],
    then a divider, then the page."""
    GAP = 44                                                                                    # space between the Training buttons (design pixels)
    def __init__(self, master, app, menu, tools, built):
        super().__init__(master, bg=master["bg"]); self.app = app; self.menu_name = menu; T.on_change(lambda: self.configure(bg=self.master["bg"]))
        side = self.side = themed_frame(self); side.pack(side="left", fill="y")
        T.Line(self, vertical=True).pack(side="left", fill="y")                                  # divider right of the side menu, border to border
        self.content = themed_frame(self); self.content.pack(side="left", fill="both", expand=True)
        self.pages, self.buttons, self.rows = {}, {}, []
        T.Title(side, menu).pack(pady=(12, 0))                                                   # the tab's name, gold and underlined, level with the page's own title
        mf = self.menu = themed_frame(side)                                                      # the buttons, centred up and down between the title and that divider
        mf.pack(fill="y", expand=True, padx=30, pady=12)                                        # spread out evenly down to the bottom; the same gap both sides
        for f in tools:                                                                          # (30px each side of the buttons; the status dot sits in the right-hand space)
            row = themed_frame(mf); row.pack(fill="x", pady=0, expand=True); self.rows.append(row)
            b = skin.button(T.Button(row, f["name"], lambda n=f["name"]: self.select(n), width=20)); b.pack(side="left", fill="x"); self.buttons[f["name"]] = b
            self.pages[f["name"]] = built[f["name"]](self.content, app) if f["name"] in built else (BlankPage(self.content, app) if f.get("blank") else PlannedPage(self.content, app, f))
        self.create_row = None
        if menu == "AI Training":                                                                   # "+ Create a model" joins the block while the Models page is showing
            self.create_row = themed_frame(mf); skin.button(T.Button(self.create_row, "+ Create a model", self._create, width=20)).pack(side="left", fill="x")
        self._gaps(); self.select(tools[0]["name"])
        self.whole = len(tools) == 1 and getattr(self.pages[tools[0]["name"]], "WHOLE", False)
        if self.whole:                                                                           # one page that is the whole tab (Draw): no side menu
            for w in (side, self.winfo_children()[1]): w.pack_forget()

    def _gaps(self):
        """every tab: the buttons spread evenly from the title down to the divider (equal gaps, resized with the window)"""
        for r in self.rows + ([self.create_row] if self.create_row is not None and self.create_row.winfo_manager() else []):
            r.pack_configure(pady=0, expand=True)

    def show_create(self, on):
        if self.create_row is None: return
        self.create_row.pack(fill="x", expand=True) if on else self.create_row.pack_forget(); self._gaps()

    def _create(self):
        p = self.pages.get("Models")
        if p is not None: p.create()

    def select(self, name):
        page = self.pages[name]
        if not page.winfo_manager(): T.tab_changed(self.app)                                                     # another section: its messages go
        with T.frozen(self.app):                                                                                   # no half-drawn page in between
            zoom_ready(page)                                                                                       # a page marked FULL fills the whole area (so its dividers reach the borders)
            if not page.winfo_manager():
                page.pack(fill="both", expand=True, **({} if getattr(page, "FULL", False) else dict(padx=12, pady=12)))   # the same gap both sides
            for p in self.pages.values():
                if p is not page: p.pack_forget()
            self.current = name
        for n, b in self.buttons.items(): b.configure(relief="flat"); b.kind = "normal"; skin.select(b, n == name)





class BlankPage(tk.Frame):
    """an empty page for a tool that's still to come: just open space inside its own border"""
    def __init__(self, master, app):
        super().__init__(master, bg=master["bg"], highlightthickness=1, bd=0); self._style(); T.on_change(self._style)
    def _style(self): self.configure(bg=self.master["bg"], highlightbackground=T.PALETTE["border"], highlightcolor=T.PALETTE["border"])

class PlannedPage(tk.Frame):
    """placeholder for a tool that's on the roadmap: what it will do and its options"""
    def __init__(self, master, app, f):
        super().__init__(master, bg=master["bg"]); T.on_change(lambda: self.configure(bg=self.master["bg"]))
        T.Title(self, f["name"]).pack(pady=(4, 4))
        T.Text(self, f["desc"], font=T.f(11)).pack(pady=(0, 6))
        T.Text(self, f"STATUS: {f['status'].upper()}" + (f"   ·   BUILD ORDER #{f['order']}" if f["order"] else ""), muted=True).pack(pady=(0, 14))
        box = T.Panel(self, pad=14, inner=True); box.pack(fill="x", padx=30)
        T.Text(box, "PLANNED OPTIONS", font=T.f(11)).pack(anchor="w", pady=(0, 6))
        for o in f["options"]:
            l = T.Text(box, "•  " + o, font=T.f(10)); l.configure(wraplength=640); l.pack(anchor="w", pady=1)
        if f.get("notes"):
            n = T.Text(self, "NOTE: " + f["notes"], muted=True); n.configure(wraplength=700); n.pack(pady=12)

















# ---------------------------------------------------------------- About
VERSION = "0.9 (Nov 15, 2026)"
class AboutPage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)
        self.wrap = tk.Frame(self, bg=self["bg"]); self.wrap.pack(fill="both", expand=True); T.on_change(lambda: self.wrap.configure(bg=self["bg"]))
        w = self.wrap
        try:
            lg = Image.open(paths.ui("Splash", "logo-easel.png")); lg.thumbnail((430, 290)); self.ph = ImageTk.PhotoImage(lg)
            self.lbl = tk.Label(w, image=self.ph, bg=self["bg"]); self.lbl.pack(pady=(4, 6)); T.on_change(lambda: self.lbl.configure(bg=self["bg"]))
        except Exception: T.Title(w, APP_NAME, big=True).pack()
        T.Text(w, f"VERSION {VERSION}", font=T.f(11)).pack()
        T.Text(w, "Type it, see it painted. Teach it your style. Free, offline, your own.", muted=True).pack(pady=(2, 10))
        box = T.Panel(w, pad=12, inner=True); box.pack(padx=40)
        for line in ("Made by Steven Lewis, built with Claude.",
                     "Painting engine, brushes, styles, editing, drawing studio and learning: written for Instant Easel.",
                     "Learned from open source: LocalAI (MIT) and Pixelle-Video (Apache 2.0); ideas only from OpenMontage and guizang-ppt-skill (AGPL).",
                     "Fonts: Courier Prime and EB Garamond (SIL Open Font License).",
                     "Images you teach it are measured, then deleted. Only what it learned is kept."):
            l = T.Text(box, "•  " + line, font=T.f(10)); l.configure(wraplength=760); l.pack(anchor="w", pady=1)
        self.bind("<Map>", lambda e: self.after_idle(self._centre))

    def _centre(self):
        """centre on the whole panel, not just the space beside the side menu: pad the right by the side menu's width"""
        section = self.master.master; side = section.winfo_children()[0]
        self.wrap.pack_configure(padx=f"0 {side.winfo_width() + max(1, int(round(T.Z))) + 24}")      # side menu + its divider (+ the page margins, 12 each side); measured pixels: text, so zoom leaves it alone

# ---------------------------------------------------------------- Theme
class ThemePage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)
        try: p = json.load(open(PREFS))
        except Exception: p = {}
        self.p = dict(border=p.get("border", 0.38), bg=p.get("bg", 0.62), opacity=1.0)      # (panels are always solid now)
        T.Title(self, "Theme").pack(pady=(0, 18)); self.sliders = {}
        for label, key, cls in (("BACKGROUND COLOR", "bg", T.HueSlider), ("BORDER COLOR", "border", T.HueSlider)):
            T.Text(self, label).pack(pady=(10, 4)); s = cls(self, value=self.p[key], command=lambda v, k=key: self.change(k, v), width=700); s.pack(); self.sliders[key] = s
        T.Text(self, "BUILD A THEME FROM ONE COLOR", font=T.f(11)).pack(pady=(22, 4))
        T.Text(self, "Pick one color; the background and border are worked out from it with color harmony.", muted=True).pack()
        self.one = T.HueSlider(self, value=self.p["bg"], width=700); self.one.pack(pady=6)
        self.harmony = tk.StringVar(value="Complementary"); T.Choice(self, "harmony", ["Matching", "Complementary", "Split", "Triadic"], self.harmony).pack(pady=4)
        r = themed_frame(self); r.pack(pady=14)
        T.Button(r, "Apply one-color theme", self.one_color).pack(side="left", padx=6); T.Button(r, "Reset theme", self.reset, kind="danger").pack(side="left", padx=6)

    def change(self, key, v):
        """recolouring restyles every widget, so while a slider is dragged it's applied at most ~25 times a second"""
        self.p[key] = v
        if getattr(self, "_tjob", None) is None: self._tjob = self.after(40, self._apply_theme)
        if getattr(self, "_sjob", None) is not None: self.after_cancel(self._sjob)
        self._sjob = self.after(400, self._save_theme)                           # the file is written once, when you stop
    def _apply_theme(self):
        self._tjob = None; T.set_border_hue(self.p["border"]); T.set_background_hue(self.p["bg"], self.p["opacity"])
    def _save_theme(self):
        self._sjob = None
        try:
            with open(PREFS, "w") as f: json.dump(self.p, f)
        except Exception: pass

    def one_color(self):
        """background takes the chosen hue (dark); the border is its harmony partner on the color wheel"""
        h = self.one.value; off = {"Matching": 0.0, "Complementary": 0.5, "Split": 0.42, "Triadic": 0.333}[self.harmony.get()]
        self.p.update(bg=h, border=(h + off) % 1.0)
        for k in ("bg", "border"): self.sliders[k].value = self.p[k]; self.sliders[k]._draw()
        self.change("bg", self.p["bg"])

    def reset(self):
        self.p = dict(border=0.38, bg=0.62, opacity=1.0)
        for k, s in self.sliders.items(): s.value = self.p[k]; s._draw()
        self.change("border", 0.38)

class Splash:
    """startup splash: the easel logo on the dark panel, a green frame and a loading bar that follows the real start-up"""
    def __init__(self, root):
        self.root = root; s = self.win = tk.Toplevel(root); s.withdraw(); s.overrideredirect(True); s.configure(bg=T.PALETTE["border"])
        inner = tk.Frame(s, bg=T.PALETTE["panel"], padx=24, pady=18); inner.pack(padx=3, pady=3)
        try:
            lg = Image.open(paths.ui("Splash", "logo-easel.png")); lg.thumbnail((460, 310)); s.ph = ImageTk.PhotoImage(lg)
            tk.Label(inner, image=s.ph, bg=T.PALETTE["panel"]).pack()
        except Exception: tk.Label(inner, text=APP_NAME, font=T.f(22), fg=T.PALETTE["title"], bg=T.PALETTE["panel"]).pack()
        self.bar = tk.Canvas(inner, width=300, height=10, bg=T.PALETTE["field"], highlightthickness=0); self.bar.pack(pady=(12, 4))
        self.lbl = tk.Label(inner, text="LOADING…", font=T.f(10), fg=T.PALETTE["muted"], bg=T.PALETTE["panel"], width=24); self.lbl.pack()   # fixed width: the text changing can't resize it
        stack = [s]                                                                   # the app's zoom must never resize the splash
        while stack:
            w = stack.pop(); w.__dict__.pop("_zd", None); w._zz = "fixed"; stack.extend(w.winfo_children())
        s.update_idletasks(); W, H = s.winfo_reqwidth(), s.winfo_reqheight()
        self.geo = f"{W}x{H}+{max(0, (s.winfo_screenwidth() - W) // 2)}+{max(0, (s.winfo_screenheight() - H) // 2)}"
        s.geometry(self.geo); s.deiconify(); s.attributes("-topmost", True); s.update_idletasks()
        s.geometry(self.geo)                                                          # again once it's showing (Windows can ignore it before)
        self.t0 = time.monotonic(); self.step(0.02, "LOADING…")
    def step(self, frac, text=None):
        try:
            self.bar.delete("all"); self.bar.create_rectangle(0, 0, 300 * max(0.0, min(1.0, frac)), 10, fill=T.PALETTE["border"], width=0)
            if text: self.lbl.configure(text=text)
            if self.win.winfo_geometry() != self.geo: self.win.geometry(self.geo)      # always the same size, centred
            self.win.update()                                                            # drawn now (the app is busy building)
        except tk.TclError: pass
    def close(self):
        self.step(1.0, "READY")
        try: self.win.destroy()
        except tk.TclError: pass

def splash(root, ms=0):
    """(kept for older callers) show the splash, then the window"""
    sp = Splash(root); root._splash = sp; root.show_window(); return sp

def _cant_start(err_text):
    """the app couldn't build its window: say so plainly (there's no console to show the error) instead of vanishing"""
    try:
        import tkinter.messagebox as mb
        r = tk.Tk(); r.withdraw()
        try: r.iconbitmap(default=icon_file("icon.ico"))
        except Exception: pass
        mb.showerror(APP_NAME, "Instant Easel couldn't start.\n\n" + err_text + "\n\nThe details are in instant_easel_errors.log next to the app. "
                     "If it fails again, the next start uses safe mode (window, start page and splash settings reset).", parent=r)
        r.destroy()
    except Exception: pass

def run_app():
    info = crash.start(home_dir(), prefs.log_error)                   # crash log, thread errors, freeze watchdog, last-session check
    if info["safe_mode"]:                                             # failed to start twice in a row: the settings most likely to blame go back to defaults
        for k in ("window_mode", "start_tab", "show_splash", "check_updates_on_start", "text_size"): prefs.set(k, prefs.DEFAULTS[k])
    try:
        app = InstantEasel(splash=bool(prefs.get("show_splash")) and not info["safe_mode"])   # built hidden (the splash shows the progress)
        app.restore_window()                                            # the fixed size, centred, before it is first shown
        app.show_window()                                               # laid out, zoomed and warmed up while invisible, then shown in one go
        app.after(2500, lambda: app.after_start(info))                  # up and running: a crash after this isn't a start-up failure
    except Exception as e:
        prefs.log_error(*sys.exc_info()); crash.start_failed(); _cant_start(f"{type(e).__name__}: {e}"); sys.exit(1)
    try: app.mainloop()
    except Exception: prefs.log_error(*sys.exc_info()); raise

if __name__ == "__main__":
    run_app()
