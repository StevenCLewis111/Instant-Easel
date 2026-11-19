"""
main.py: Instant Easel Pro. One menu window, five tabs:
  Generate: type what you want, it paints it (and says what it understood)
  Train:    images to learn from (it guesses what each shows; you confirm)
  Words:    teach it what your words mean
  Paint:    drawing canvas, styles, classic tools
  Theme:    border colour, background colour, panel opacity
"""
import os, sys, threading, queue, shutil, random, json, time
import tkinter as tk
from tkinter import filedialog
# every script lives in a folder under systems/ (sorted by tab): they're all found by name, from any folder
BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, BASE)
for _d, _dirs, _files in os.walk(os.path.join(BASE, "systems")):
    _dirs[:] = sorted(x for x in _dirs if not x.startswith((".", "__")))
    if any(f.endswith(".py") for f in _files) and _d not in sys.path: sys.path.insert(1, _d)
import paths
from PIL import Image, ImageTk
import theme as T
import paint_window, features, edit as E, draw_studio, prefs, settings_pages as SP
import crash, skin, ui_art as UA, learning_areas as LA, image_pages as IP, workspace_page as WP

APP_NAME = "Instant Easel Pro"
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
SETTINGS = [("time", ["sunset", "night"]), ("clouds", ["few", "normal", "many"]), ("tint", ["none", "golden", "fiery", "pink", "cool"]),
            ("figures", ["0", "1", "2"]), ("pose", ["seated", "standing"]), ("height", ["0.2", "0.5", "0.9"]), ("peaks", ["3", "4", "5", "6"]),
            ("mountains", ["True", "False"]), ("rocks", ["True", "False"]), ("grass", ["True", "False"]), ("canyon", ["True", "False"]),
            ("sun_x", ["0.25", "0.5", "0.75"])]
PREFS = paths.json_file("instant_easel_theme.json")


COL_WRAP = 344                                                               # text width inside a fixed 360 column (design pixels)


def themed_frame(parent):
    f = tk.Frame(parent, bg=parent["bg"]); T.on_change(lambda: f.configure(bg=f.master["bg"])); return f

class InstantEasel(tk.Tk):
    def __init__(self, splash=False):
        if sys.platform == "win32":                                   # sharp at 125%/150% display scaling, and nothing drifts (Windows won't bitmap-stretch the app)
            try: import ctypes; ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                try: ctypes.windll.user32.SetProcessDPIAware()
                except Exception: pass
            try: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("InstantEaselPro.App")   # the taskbar shows Instant Easel Pro's icon, not Python's
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
        self.bind("<Control-z>", lambda e: self._key_undo()); self.bind("<Control-y>", lambda e: self._key_undo(redo=True))
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
        self.menus = features.visible_menus()                                    # tabs this PC can't use (AI Videos on a small card) are left out
        names = [m for m, _, _ in self.menus]
        top = tk.Frame(self.frame, bg=self.frame["bg"]); top.pack(fill="x", pady=(0, 10)); self.top = top    # guy | logo over tabs | girl
        T.on_change(lambda: top.configure(bg=self.frame["bg"]))
        top.columnconfigure(0, weight=1); top.columnconfigure(2, weight=1)
        self.logo_lbl = None
        try:
            import numpy as _np
            lg = Image.open(paths.ui("Header", "title-logo.png")); _al = _np.asarray(lg)[..., 3] > 40
            _ys, _xs = _np.nonzero(_al); self.logo_src = lg.crop((int(_xs.min()), int(_ys.min()), int(_xs.max()) + 1, int(_ys.max()) + 1))   # painted area only
            badge = T.paint_words("PRO", max(12, int(self.logo_src.height * 0.26)), (255, 214, 0))                   # this is Instant Easel Pro
            big = Image.new("RGBA", (self.logo_src.width + badge.width // 3, self.logo_src.height + badge.height // 4)); big.alpha_composite(self.logo_src.convert("RGBA"))
            big.alpha_composite(badge, (big.width - badge.width, big.height - badge.height)); self.logo_src = big
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

        built = {"Image Scraper": ScraperPage, **LA.page_classes(), **IP.page_classes(), **WP.page_classes(), "Theme": ThemePage, "Draw": draw_studio.DrawStudio,
                 "Light": LightPage, "Color": ColorPage, "Effects": EffectsPage, "Filters": FiltersPage, "Transform": TransformPage, "History": HistoryPage, "About": AboutPage,
                 "General": SP.GeneralPage, "Performance": SP.PerformancePage, "Display": SP.DisplayPage, "Privacy & Data": SP.PrivacyPage,
                 "AI Models": SP.AIModelsPage, "AI Images": SP.AIImagesPage, "AI Storage": SP.AIStoragePage, "Updates": SP.UpdatesPage, "Shortcuts": SP.ShortcutsPage, "Backup & Reset": SP.BackupPage}
        self.edit = dict(original=None, proxy=None, params=dict(E.DEFAULTS), filt="none", geom=dict(E.GEOM), listeners=[])   # shared by the Edit tools
        self.body = T.Panel(self.frame, pad=0, inner=True); self.body.pack(fill="both", expand=True, pady=(0, 14))
        self.pages = {}
        for i, (m, _, tools) in enumerate(self.menus):
            if self._splash: self._splash.step(i / (len(self.menus) + 1), f"LOADING {m.upper()}…")
            self.pages[m] = Section(self.body, self, m, tools, built)
        st = prefs.get("start_tab"); st = prefs.get("last_tab") if st == "Last used" else st
        st = features.OLD_TAB_NAMES.get(st, st)                                                 # settings saved with the old tab names still work
        self.show(st if st in self.pages else "AI Images"); self.tabs.active = st if st in self.pages else "AI Images"; self.tabs._style()
        if prefs.get("check_updates_on_start"): self.after(4000, lambda: self.pages["Settings"].pages["Updates"].check())
        import jobs; self.jobs_pill = jobs.Pill(self)                                          # the AI jobs line: '1 RUNNING · 2 WAITING', click for the list
        self.after(5000, self._rescan_pc)

    def _rescan_pc(self):
        """check the PC again in the background (a new graphics card or more memory shows up next time the app opens)"""
        import hardware, catalog
        def changed(old, new):
            if catalog.hidden_tabs(old) != catalog.hidden_tabs(new) or [o["key"] for o in catalog.options("AI Images", old)] != [o["key"] for o in catalog.options("AI Images", new)]:
                self.q.put(lambda: T.banner(self, f"YOUR PC CHANGED — {hardware.describe(new)}. Close and reopen the app to update what it offers", "success"))
        hardware.rescan_async(on_done=changed)

    def _size_mascots(self):
        """the logo spans exactly the tab row (Images' left edge to Settings' right edge); the guy and girl's flat bottoms sit on the tab row's bottom"""
        self.update_idletasks()
        if getattr(self, "logo_src", None) is not None and self.tabs.winfo_width() > 50:
            kids = list(self.tabs.btns.values())                                               # the tab buttons only (not the header picture behind them)
            if kids[-1].winfo_width() < 20: return self.after(50, self._size_mascots)           # tabs not laid out yet: measure again shortly
            trim = kids[-1].winfo_width() / 2                                                  # half a Settings tab, taken off each end
            left = kids[0].winfo_x() + kids[0].winfo_width() / 2 + trim                        # middle of the Images tab, then in by the trim
            right = kids[-1].winfo_x() + kids[-1].winfo_width() / 2 - trim                     # middle of the Settings tab, then in by the trim
            tw = int(round(right - left)); lh0 = int(round(150 * T.Z))
            tw = min(int(tw * 1.0), int(self.logo_src.width * lh0 / self.logo_src.height * 1.3))    # stretched side to side, up to the tab row's span
            shift = int(round((left + right) / 2 - self.tabs.winfo_width() / 2))               # the two tabs differ in width: nudge so both edges land on their middles
            self.logo_lbl.grid_configure(padx=f"{max(0, 2 * shift)} {max(0, -2 * shift)}")      # measured pixels, passed as text so zoom leaves them alone
            lh = int(round(150 * T.Z))
            if abs(self.logo.width() - tw) > 1 or self.logo.height() != lh:
                self._logo_pil = self.logo_src.resize((tw, lh), Image.LANCZOS)
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
            im = src.resize((max(1, int(src.width * k)), max(1, int(src.height * k))), Image.LANCZOS)
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
        if not getattr(self, "_settling", False):                                # once more when the window has settled (sizes read mid-resize are stale)
            self._settling = True
            self.after(150, lambda: (self._size_mascots(), setattr(self, "_settling", False)))

    # ---------------- the header's picture (images/UI/Header/header-background.png): the waterfall, trees and stream behind the guy,
    # the girl, the logo and the tabs. Tk can't draw see-through widgets on a picture, so a backdrop fills the header and every piece
    # on it carries the matching slice of the picture behind it.
    HEADER_CROP, HEADER_DIM = 0.70, 0.85                                       # which band of the picture (from its top), and how bright
    def _header_band(self, W, H):
        key = (W, H, T.PALETTE["panel"])
        if getattr(self, "_hband_key", None) == key: return self._hband
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
        self._hband, self._hband_key = out, key; self._hcache = {}; return out

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
        with T.frozen(self):                                                     # the old tab stays on screen until the new one is complete
            zoom_ready(self.pages[name]); self.pages[name].pack(fill="both", expand=True)
            for n, p in self.pages.items():
                if n != name: p.pack_forget()
            self._shown_tab = name
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

    def _settle(self, timeout=1.5):
        """wait until the window has its final size (a maximize can arrive in steps), then zoom once"""
        end = time.monotonic() + timeout; last = None; same = 0
        while time.monotonic() < end:
            self.update()
            size = (self.view_cv.winfo_width(), self.view_cv.winfo_height())
            same = same + 1 if size == last else 0; last = size
            if same >= 3 and size[0] > 50: break
            time.sleep(0.015)
        if self._zoom_job: self.after_cancel(self._zoom_job); self._zoom_job = None
        self._rezoom(now=True)

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
    def _snap(self):
        import copy; ed = self.edit; return copy.deepcopy(dict(params=ed["params"], filt=ed["filt"], geom=ed["geom"]))
    def hist_start(self, label):
        self.hist = [(label, self._snap())]; self.hpos = 0; self._hist_job = None; self._hist_changed()
    def hist_touch(self):
        """a change happened: record it once things settle (one slider drag = one step)"""
        if not hasattr(self, "hist") or self.edit["original"] is None: return
        if self._hist_job: self.after_cancel(self._hist_job)
        self._hist_job = self.after(600, lambda: self.hist_commit())
    def hist_commit(self, label=None):
        if not hasattr(self, "hist"): return
        self._hist_job = None; snap = self._snap(); prev = self.hist[self.hpos][1]
        if snap == prev and label is None: return
        label = label or self._describe(prev, snap)
        self.hist = self.hist[:self.hpos + 1] + [(label, snap)]; self.hist = self.hist[-200:]; self.hpos = len(self.hist) - 1; self._hist_changed()
    def _describe(self, a, b):
        """name a step by what changed: 'Exposure +20', 'Filter: sepia', 'Crop', 'Rotate 90°'..."""
        parts = [f"{k.capitalize()} {v:+d}" if v else f"{k.capitalize()} reset" for k, v in b["params"].items() if v != a["params"].get(k)]
        if b["filt"] != a["filt"]: parts.append(f"Filter: {b['filt']}")
        g0, g1 = a["geom"], b["geom"]
        if g1["rot90"] != g0["rot90"]: parts.append("Rotate 90°")
        if g1["flip_h"] != g0["flip_h"]: parts.append("Flip ↔")
        if g1["flip_v"] != g0["flip_v"]: parts.append("Flip ↕")
        if g1["straighten"] != g0["straighten"]: parts.append(f"Straighten {g1['straighten']:+.1f}°")
        if g1["crop"] != g0["crop"]: parts.append("Crop" if g1["crop"] else "Clear crop")
        if g1["scale"] != g0["scale"]: parts.append(f"Resize {int(g1['scale'] * 100)}%")
        return ", ".join(parts[:3]) + ("…" if len(parts) > 3 else "") or "Change"
    def hist_jump(self, i):
        if not hasattr(self, "hist") or not (0 <= i < len(self.hist)): return
        if self._hist_job: self.after_cancel(self._hist_job); self._hist_job = None
        import copy; self.hpos = i; s = copy.deepcopy(self.hist[i][1]); self.edit.update(params=s["params"], filt=s["filt"], geom=s["geom"])
        for fn in self.edit["listeners"]: fn()
        self._hist_changed()
    def hist_undo(self):
        if hasattr(self, "hist"):
            if self._hist_job: self.hist_commit()                                    # finish a change in progress first
            self.hist_jump(self.hpos - 1)
    def hist_redo(self):
        if hasattr(self, "hist"): self.hist_jump(self.hpos + 1)

    def _hist_changed(self):
        h = self.pages.get("Editing") and self.pages["Editing"].pages.get("History") if hasattr(self, "pages") else None
        if h: h.show_list()
    def _key_undo(self, redo=False):
        """Ctrl+Z / Ctrl+Y in Editing (the Draw studio has its own undo)"""
        if getattr(self.tabs, "active", "") != "Editing": return
        sec = self.pages["Editing"]
        (self.hist_redo if redo else self.hist_undo)()


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

    def _to_fixed(self):
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

    def _to_maximized(self):
        self._guard(); self._mode = "maximized"
        if self.attributes("-fullscreen"): self.attributes("-fullscreen", False)
        try: self.state("zoomed")
        except tk.TclError: self.attributes("-zoomed", True)
        self.after_idle(self._after_maximize)

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

    def _to_fullscreen(self):
        self._guard(); self._mode = "fullscreen"
        self.attributes("-fullscreen", True)
        self.after_idle(self._win_prep)

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
                    if cmd == 0xF030 and self._mode == "fixed":                               # []: maximize (Windows does it, we tidy up after)
                        self._mode = "maximized"; self._guard_until = time.monotonic() + 0.5; self.q.put(self._after_maximize)
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
            try: answer = T.popup(self, "QUIT INSTANT EASEL PRO?", "Anything you haven't saved will be lost.", (("Quit", "danger"), ("Cancel", "normal")))
            finally: self._asking = False
            if answer != "Quit": return
        crash.clean_exit()                                                                    # a normal quit: nothing to recover next time
        for mod, fn in (("jobs", "cancel_all"), ("imaging", "stop_now"), ("brain", "stop")):         # no engine left running in the background
            m = sys.modules.get(mod)
            if m is not None and hasattr(m, fn):
                try: getattr(m, fn)()
                except Exception: pass
        ig = sys.modules.get("image_grabber")                                                 # the scraper's hidden Firefox (kept open between
        if ig is not None:                                                                     # scans so Google's check comes up once) closes too
            try: ig.close_browser()
            except Exception: pass
        self.destroy()

    def bring_to_front(self):
        """someone opened the app again: show this copy instead"""
        try:
            if self.state() == "iconic": self.deiconify()
            self.lift(); self.attributes("-topmost", True); self.after(300, lambda: self.attributes("-topmost", False)); self.focus_force()
        except tk.TclError: pass

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
        """every minute: the drawing and the Editing settings go to the recovery folder (only when they've changed)"""
        try:
            folder = crash.recovery_dir(); ds = self.pages["Drawing"].pages.get("Draw")
            if ds is not None: ds.autosave(folder)
            ed = self.edit
            if ed.get("original") is not None and ed.get("path"):
                state = dict(path=ed["path"], params=ed["params"], filt=ed["filt"], geom={k: (list(v) if isinstance(v, tuple) else v) for k, v in ed["geom"].items()})
                with open(os.path.join(folder, "editing.json.tmp"), "w") as f: json.dump(state, f)
                os.replace(os.path.join(folder, "editing.json.tmp"), os.path.join(folder, "editing.json"))
        except Exception: prefs.log_error(*sys.exc_info())
        finally: self.after(60000, self._autosave)

    def after_start(self, info):
        """once the window is up: tell crash.py all is well, then deal with how the last session ended"""
        crash.running()
        if info.get("safe_mode"):
            T.banner(self, "STARTED IN SAFE MODE — it failed to start twice, so the window, start page and splash settings were reset")
        if not info.get("crashed"): return
        folder = crash.recovery_dir(); has_draw = draw_studio.DrawStudio.has_recovery(folder); ed_file = os.path.join(folder, "editing.json")
        if not has_draw and not os.path.exists(ed_file): return
        what = " and ".join(x for x in (("your drawing" if has_draw else ""), ("your editing" if os.path.exists(ed_file) else "")) if x)
        if T.popup(self, "INSTANT EASEL PRO CLOSED UNEXPECTEDLY", f"It saved {what} a minute or less before it closed.\nRestore it?",
                   (("Restore", "normal"), ("Discard", "danger"))) != "Restore":
            shutil.rmtree(folder, ignore_errors=True); return
        try:
            if os.path.exists(ed_file):
                with open(ed_file) as f: st = json.load(f)
                if os.path.exists(st["path"]):
                    light = self.pages["Editing"].pages.get("Light"); light.set_image(Image.open(st["path"]), path=st["path"])
                    g = st["geom"]; g["crop"] = tuple(g["crop"]) if g.get("crop") else None
                    self.edit.update(params=st["params"], filt=st["filt"], geom=g); light.notify(record=False); self.hist_commit("Restored after a crash")
                    self.show("Editing"); self.tabs.active = "Editing"; self.tabs._style(); self.pages["Editing"].select("Light")
            if has_draw:
                ds = self.pages["Drawing"].pages["Draw"]; self.goto("Drawing"); self.update_idletasks(); ds.restore(folder)
            T.banner(self, f"RESTORED — {what}", "success")
        except Exception:
            prefs.log_error(*sys.exc_info()); T.banner(self, "COULDN'T RESTORE — the saved work couldn't be loaded (details in instant_easel_errors.log)")

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
            p = json.load(open(PREFS)); T.set_border_hue(p.get("border", 0.38)); T.set_background_hue(p.get("bg", 0.62), p.get("opacity", 1.0))
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
LA.DOT = status_dot                                                                              # the learning areas use the same dots

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
        self.parents = {f["name"]: f.get("parent") for f in tools if f.get("hidden")}         # pages opened from inside another page (no button of their own)
        T.Title(side, menu).pack(pady=(12, 0))                                                   # the tab's name, gold and underlined, level with the page's own title
        mf = self.menu = themed_frame(side)                                                      # the buttons, centred up and down between the title and that divider
        mf.pack(fill="y", expand=True, padx=30, pady=12)                                        # spread out evenly down to the bottom; the same gap both sides
        for f in tools:                                                                          # (30px each side of the buttons; the status dot sits in the right-hand space)
            if f.get("hidden"):
                self.pages[f["name"]] = built[f["name"]](self.content, app) if f["name"] in built else PlannedPage(self.content, app, f); continue
            row = themed_frame(mf); row.pack(fill="x", pady=0, expand=True); self.rows.append(row)
            b = skin.button(T.Button(row, f["name"], lambda n=f["name"]: self.select(n), width=20)); b.pack(side="left", fill="x"); self.buttons[f["name"]] = b
            self.pages[f["name"]] = built[f["name"]](self.content, app) if f["name"] in built else (BlankPage(self.content, app) if f.get("blank") else PlannedPage(self.content, app, f))
        self.create_row = None
        if menu == "AI Training":                                                                   # "+ Create a model" joins the block while the Models page is showing
            self.create_row = themed_frame(mf); skin.button(T.Button(self.create_row, "+ Create a model", self._create, width=20)).pack(side="left", fill="x")
        self._gaps(); self.select(tools[0]["name"])
        tools = [f for f in tools if not f.get("hidden")]
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
        with T.frozen(self.app):                                                                                   # no half-drawn page in between
            zoom_ready(page)                                                                                       # a page marked FULL fills the whole area (so its dividers reach the borders)
            if not page.winfo_manager():
                page.pack(fill="both", expand=True, **({} if getattr(page, "FULL", False) else dict(padx=12, pady=12)))   # the same gap both sides
            for p in self.pages.values():
                if p is not page: p.pack_forget()
            self.current = name
        lit = self.parents.get(name) or name                                                    # an inner page lights up the button it was opened from
        for n, b in self.buttons.items(): b.configure(relief="flat"); b.kind = "normal"; skin.select(b, n == lit)





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


# ---------------------------------------------------------------- Edit: shared image, settings and preview
class EditBase(Page):
    """top bar (open / last created / reset / save) + the tool's controls + a live preview; state shared across Edit tools"""
    def __init__(self, master, app, title):
        super().__init__(master, app); self.app.edit["listeners"].append(self.refresh); self._job = None; self.show_orig = False
        self._busy = False; self._again = False
        bar = themed_frame(self); bar.pack(fill="x", pady=(0, 8))
        for text, cmd, kind in (("Open image", self.open, "normal"), ("Edit last created", self.last, "normal"), ("↶ Undo", self.app.hist_undo, "normal"),
                                ("↷ Redo", self.app.hist_redo, "normal"), ("Before / after", self.toggle, "normal"), ("Reset all", self.reset, "danger"), ("Save", self.save, "normal")):
            T.Button(bar, text, cmd, kind=kind).pack(side="left", padx=(0, 8))
        body = themed_frame(self); body.pack(fill="both", expand=True)
        self.controls = themed_frame(body); self.controls.pack(side="left", fill="y", padx=(0, 14))
        T.Title(self.controls, title).pack(anchor="w", pady=(0, 8))
        self.view = tk.Label(body, bg=T.PALETTE["field"], text="OPEN AN IMAGE, OR EDIT THE LAST CREATED ONE", fg=T.PALETTE["muted"], font=T.f(11), width=1, height=1)
        self.view.pack(side="left", fill="both", expand=True); self.view.bind("<Configure>", lambda e: self.refresh()); T.on_change(lambda: self.view.configure(bg=T.PALETTE["field"]))

    # ---- shared state
    def set_image(self, im, path=None):
        im = im.convert("RGB"); p = im.copy(); p.thumbnail((prefs.size("edit_preview"),) * 2)
        self.app.edit.update(original=im, proxy=p, path=path, params=dict(E.DEFAULTS), filt="none", geom=dict(E.GEOM))
        self.app.hist_start("Opened " + (os.path.basename(path) if path else "image")); self.notify(record=False)
    def notify(self, record=True):
        for fn in self.app.edit["listeners"]: fn()
        if record: self.app.hist_touch()
    def open(self):
        p = filedialog.askopenfilename(parent=self.app, initialdir=prefs.save_folder(), filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.avif *.gif *.tif *.tiff"), ("All files", "*.*")])
        if p: self.set_image(Image.open(p), path=p)
    def last(self):
        c = self.app.pages["AI Images"].pages; im = None
        for n in ("Image to Image", "Text to Image"):
            r = getattr(c.get(n), "result", None)
            if r is not None: im = r; break
        if im is None: return T.banner(self.app, "NOTHING YET — create an image first")
        self.set_image(im)
    def toggle(self): self.show_orig = not self.show_orig; self.refresh()
    def reset(self): self.app.edit.update(params=dict(E.DEFAULTS), filt="none", geom=dict(E.GEOM)); self.notify(record=False); self.app.hist_commit("Reset to original")
    def save(self):
        if self.app.edit["original"] is None: return
        p = filedialog.asksaveasfilename(parent=self.app, initialdir=prefs.save_folder(), initialfile=prefs.next_name(), defaultextension=prefs.ext(), filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("WebP", "*.webp")])
        if p:
            ed = self.app.edit; prefs.save_image(E.apply(E.transform(ed["original"], ed["geom"]), ed["params"], ed["filt"]), p)
            T.banner(self.app, f"SAVED — {os.path.basename(p)} (full size)", "success")

    # ---- preview (debounced so sliders stay smooth)
    def refresh(self):
        """redraw the preview soon. Throttled (keeps updating while a slider is dragged), not debounced (which waited until you stopped)"""
        if self._job is None: self._job = self.after(30, self._draw)
    def _draw(self):
        """the adjustments are worked out on a background thread so sliders never stutter; only the newest settings are shown"""
        self._job = None; px = self.app.edit["proxy"]
        if px is None or not self.winfo_ismapped(): return
        if self._busy: self._again = True; return                                # one render at a time; the latest settings go next
        ed = self.app.edit; geom, params, filt, orig = dict(ed["geom"]), dict(ed["params"]), ed["filt"], self.show_orig
        w, h = max(200, self.view.winfo_width() - 8), max(200, self.view.winfo_height() - 8); self._busy = True
        def work():
            try:
                im = px if orig else E.apply(E.transform(px, geom), params, filt); t = im.copy(); t.thumbnail((w, h)); res = (t, None)
            except Exception as ex: res = (None, ex)
            self.app.q.put(lambda: self._rendered(*res))
        threading.Thread(target=work, daemon=True, name="EditPreview").start()
    def _rendered(self, t, err):
        self._busy = False
        if err is not None: prefs.log_error(type(err), err, err.__traceback__)
        elif t is not None and self.winfo_exists():
            self.ph = ImageTk.PhotoImage(t); self.view.configure(image=self.ph, text=""); self.after_hook()
        if self._again: self._again = False; self.refresh()
    def after_hook(self): pass

class AdjustPage(EditBase):
    GROUP = "Light"
    def __init__(self, master, app):
        super().__init__(master, app, self.GROUP); self.labels = {}; self.sliders = {}
        for k in E.GROUPS[self.GROUP]:
            r = themed_frame(self.controls); r.pack(fill="x", pady=(6, 0))
            T.Text(r, k.upper()).pack(side="left"); self.labels[k] = T.Text(r, "0", muted=True); self.labels[k].pack(side="right")
            s = T.PlainSlider(self.controls, value=0.5, width=300, command=lambda v, k=k: self.change(k, v)); s.pack(anchor="w")
            s.bind("<Double-Button-1>", lambda e, k=k: self.change(k, 0.5, reset=True)); self.sliders[k] = s
        T.Text(self.controls, "Double-click a slider to reset it.", muted=True).pack(anchor="w", pady=10)
    def change(self, k, v, reset=False):
        val = int(round((v - 0.5) * 200)); self.app.edit["params"][k] = val
        if reset: self.sliders[k].value = 0.5; self.sliders[k]._draw()
        self.labels[k].configure(text=f"{val:+d}" if val else "0"); self.notify()
    def after_hook(self):
        for k, s in self.sliders.items():
            v = self.app.edit["params"][k]; want = v / 200 + 0.5
            if abs(s.value - want) > 1e-6: s.value = want; s._draw(); self.labels[k].configure(text=f"{v:+d}" if v else "0")

class LightPage(AdjustPage): GROUP = "Light"
class ColorPage(AdjustPage): GROUP = "Color"
class EffectsPage(AdjustPage): GROUP = "Effects"

class FiltersPage(EditBase):
    def __init__(self, master, app):
        super().__init__(master, app, "Filters"); self.tiles = {}
        grid = themed_frame(self.controls); grid.pack(anchor="w")
        for i, f in enumerate(E.FILTERS):
            cell = themed_frame(grid); cell.grid(row=i // 2, column=i % 2, padx=6, pady=6)
            lb = tk.Label(cell, bg=T.PALETTE["field"], width=16, height=5, text=f.upper(), fg=T.PALETTE["muted"], font=T.f(8), highlightthickness=3, cursor="hand2")
            lb.pack(); lb.bind("<Button-1>", lambda e, f=f: self.pick(f)); T.Text(cell, f.upper(), font=T.f(8)).pack(); self.tiles[f] = lb
    def pick(self, f): self.app.edit["filt"] = f; self.notify()
    def after_hook(self):
        px = self.app.edit["proxy"]; small = px.copy(); small.thumbnail((130, 90)); self._thumbs = []
        for f, lb in self.tiles.items():
            ph = ImageTk.PhotoImage(E.look(small, f)); self._thumbs.append(ph)
            lb.configure(image=ph, text="", width=small.width, height=small.height,
                         highlightbackground=T.PALETTE["border"] if f == self.app.edit["filt"] else T.PALETTE["panel2"])

class HistoryPage(EditBase):
    """every step by name (click to jump), undo/redo, side-by-side compare, reset, save as new / overwrite original"""
    def __init__(self, master, app):
        super().__init__(master, app, "History"); self.compare = False
        c = self.controls
        r = themed_frame(c); r.pack(anchor="w", pady=(0, 6))
        T.Button(r, "Compare side by side", self.toggle_compare).pack(side="left")
        r = themed_frame(c); r.pack(anchor="w", pady=(0, 8))
        T.Button(r, "Save as new", self.save).pack(side="left"); T.Button(r, "Overwrite original", self.overwrite, kind="danger").pack(side="left", padx=6)
        T.Text(c, "STEPS  (click one to go back to it)", font=T.f(10)).pack(anchor="w", pady=(6, 2))
        box = T.ScrollBox(c, bg="panel2"); box.pack(fill="both", expand=True)            # list, divider and scroll bar, boxed in
        self.lcv = tk.Canvas(box.body, width=262, height=420, bg=T.PALETTE["panel2"], highlightthickness=0); box.attach(self.lcv)
        self.lcv.pack(side="left", fill="both", expand=True)
        self.list = tk.Frame(self.lcv, bg=T.PALETTE["panel2"]); self.lcv.create_window((0, 0), window=self.list, anchor="nw")
        self.list.bind("<Configure>", lambda e: T.fit_scrollregion(self.lcv)); T.on_change(lambda: (self.lcv.configure(bg=T.PALETTE["panel2"]), self.list.configure(bg=T.PALETTE["panel2"])))
        self.show_list()
    def show_list(self):
        for w in self.list.winfo_children(): w.destroy()
        hist = getattr(self.app, "hist", None)
        if not hist: T.Text(self.list, "No steps yet. Open an image and edit it.", muted=True).pack(anchor="w", padx=6, pady=6); return
        for i, (label, _) in enumerate(hist):
            cur = i == self.app.hpos; future = i > self.app.hpos
            b = tk.Label(self.list, text=f"{i:>3}  {label}", anchor="w", width=34, font=T.f(9), cursor="hand2", padx=6, pady=3,
                         bg=T.PALETTE["button"] if cur else T.PALETTE["panel2"], fg=T.PALETTE["muted"] if future else "white",
                         highlightthickness=2, highlightbackground=T.PALETTE["border"] if cur else T.PALETTE["panel2"])
            b.pack(fill="x", pady=1); b.bind("<Button-1>", lambda e, i=i: self.app.hist_jump(i))
        self.lcv.update_idletasks(); self.lcv.yview_moveto(1.0 if self.app.hpos == len(hist) - 1 else max(0, self.app.hpos / max(1, len(hist))))
    def toggle_compare(self): self.compare = not self.compare; self.refresh()
    def _draw(self):
        if not self.compare: return super()._draw()
        self._job = None; ed = self.app.edit; px = ed["proxy"]
        if px is None or not self.winfo_ismapped(): return
        cur = E.apply(E.transform(px, ed["geom"]), ed["params"], ed["filt"]); w, h = max(200, self.view.winfo_width() - 8), max(200, self.view.winfo_height() - 8)
        a, b = px.copy(), cur.copy(); a.thumbnail((w // 2 - 6, h - 30)); b.thumbnail((w // 2 - 6, h - 30))
        sheet = Image.new("RGB", (w, h), tuple(int(T.PALETTE["field"][i:i + 2], 16) for i in (1, 3, 5)))
        sheet.paste(a, ((w // 2 - a.width) // 2, 28)); sheet.paste(b, (w // 2 + (w // 2 - b.width) // 2, 28))
        from PIL import ImageDraw; d = ImageDraw.Draw(sheet); d.text((w // 4 - 30, 6), "ORIGINAL", fill=(200, 200, 210)); d.text((3 * w // 4 - 24, 6), "CURRENT", fill=(200, 200, 210))
        self.ph = ImageTk.PhotoImage(sheet); self.view.configure(image=self.ph, text="")
    def overwrite(self):
        ed = self.app.edit; p = ed.get("path")
        if ed["original"] is None: return
        if not p: return T.banner(self.app, "NO ORIGINAL FILE — this picture didn't come from a file; use Save as new")
        if T.popup(self.app, "OVERWRITE THE ORIGINAL?", f"{os.path.basename(p)} will be replaced with the edited version.\nThis can't be undone.",
                   (("Overwrite", "danger"), ("Cancel", "normal"))) == "Overwrite":
            prefs.save_image(E.apply(E.transform(ed["original"], ed["geom"]), ed["params"], ed["filt"]), p); T.banner(self.app, f"SAVED — {os.path.basename(p)}", "success")

class TransformPage(EditBase):
    """crop (drag a box, ratio presets), rotate, straighten, flip, resize; the preview shows the crop box over the whole picture"""
    RATIOS = ["Free", "1:1", "2:3", "3:2", "4:5", "16:9", "9:16"]; SCALES = ["100%", "200%", "75%", "50%", "25%"]
    def __init__(self, master, app):
        super().__init__(master, app, "Transform")
        body = self.view.master; self.view.pack_forget()
        self.cv = tk.Canvas(body, bg=T.PALETTE["field"], highlightthickness=0, cursor="crosshair"); self.cv.pack(side="left", fill="both", expand=True)
        self.cv.bind("<Configure>", lambda e: self.refresh()); self.cv.bind("<ButtonPress-1>", self._press); self.cv.bind("<B1-Motion>", self._drag)
        T.on_change(lambda: self.cv.configure(bg=T.PALETTE["field"]))
        c = self.controls
        T.Text(c, "ROTATE & FLIP").pack(anchor="w", pady=(4, 4))
        r = themed_frame(c); r.pack(anchor="w")
        T.Button(r, "⟲ 90°", lambda: self.geom(rot90=self.g["rot90"] + 1)).pack(side="left"); T.Button(r, "⟳ 90°", lambda: self.geom(rot90=self.g["rot90"] - 1)).pack(side="left", padx=6)
        r = themed_frame(c); r.pack(anchor="w", pady=6)
        T.Button(r, "Flip ↔", lambda: self.geom(flip_h=not self.g["flip_h"])).pack(side="left"); T.Button(r, "Flip ↕", lambda: self.geom(flip_v=not self.g["flip_v"])).pack(side="left", padx=6)
        rr = themed_frame(c); rr.pack(fill="x", pady=(10, 0)); T.Text(rr, "STRAIGHTEN").pack(side="left"); self.st_lbl = T.Text(rr, "0.0°", muted=True); self.st_lbl.pack(side="right")
        self.st = T.PlainSlider(c, value=0.5, width=300, command=self._straighten); self.st.pack(anchor="w")
        self.st.bind("<Double-Button-1>", lambda e: (setattr(self.st, "value", 0.5), self.st._draw(), self._straighten(0.5)))
        T.Text(c, "CROP  (drag on the picture)").pack(anchor="w", pady=(12, 4))
        self.ratio = tk.StringVar(value="Free"); T.Choice(c, "ratio", self.RATIOS, self.ratio).pack(anchor="w")
        self.ratio.trace_add("write", lambda *a: self._apply_ratio())
        T.Button(c, "Clear crop", lambda: self.geom(crop=None)).pack(anchor="w", pady=6)
        T.Text(c, "RESIZE").pack(anchor="w", pady=(8, 4))
        self.scale = tk.StringVar(value="100%"); T.Choice(c, "size", self.SCALES, self.scale).pack(anchor="w")
        self.scale.trace_add("write", lambda *a: self.geom(scale=int(self.scale.get()[:-1]) / 100))
        self.size_lbl = T.Text(c, "", muted=True); self.size_lbl.pack(anchor="w", pady=10)
        self._box = None

    @property
    def g(self): return self.app.edit["geom"]
    def geom(self, **kw): self.g.update(kw); self.notify()
    def _straighten(self, v):
        deg = round((v - 0.5) * 90, 1); self.st_lbl.configure(text=f"{deg:+.1f}°" if deg else "0.0°"); self.geom(straighten=deg)
    def _base(self):
        """the picture after rotate/flip/straighten (before crop and resize)"""
        return E.transform(self.app.edit["proxy"], dict(self.g, crop=None, scale=1.0))
    def _apply_ratio(self):
        if self.app.edit["proxy"] is None: return
        r = self.ratio.get(); b = self._base()
        self.geom(crop=None if r == "Free" else E.crop_for_ratio(b.width, b.height, r))
    def _draw(self):
        self._job = None; px = self.app.edit["proxy"]
        if px is None or not self.winfo_ismapped(): return
        ed = self.app.edit; base = self._base(); shown = base if self.show_orig else E.apply(base, ed["params"], ed["filt"])
        w, h = max(200, self.cv.winfo_width() - 16), max(200, self.cv.winfo_height() - 16); t = shown.copy(); t.thumbnail((w, h))
        self._k = t.width / base.width; self._off = ((self.cv.winfo_width() - t.width) / 2, (self.cv.winfo_height() - t.height) / 2); self._tw, self._th = t.width, t.height
        self.cv.delete("all"); self.ph = ImageTk.PhotoImage(t); self.cv.create_image(self._off[0], self._off[1], image=self.ph, anchor="nw")
        c = self.g["crop"]
        if c:
            x0, y0 = self._off[0] + min(c[0], c[2]) * t.width, self._off[1] + min(c[1], c[3]) * t.height
            x1, y1 = self._off[0] + max(c[0], c[2]) * t.width, self._off[1] + max(c[1], c[3]) * t.height
            for box in ((self._off[0], self._off[1], self._off[0] + t.width, y0), (self._off[0], y1, self._off[0] + t.width, self._off[1] + t.height),
                        (self._off[0], y0, x0, y1), (x1, y0, self._off[0] + t.width, y1)):
                self.cv.create_rectangle(*box, fill="black", stipple="gray50", width=0)                 # darken outside the crop
            self.cv.create_rectangle(x0, y0, x1, y1, outline=T.PALETTE["border"], width=2)
            for i in (1, 2):                                                                             # rule-of-thirds guides
                self.cv.create_line(x0 + (x1 - x0) * i / 3, y0, x0 + (x1 - x0) * i / 3, y1, fill="#ffffff", stipple="gray50")
                self.cv.create_line(x0, y0 + (y1 - y0) * i / 3, x1, y0 + (y1 - y0) * i / 3, fill="#ffffff", stipple="gray50")
        out = E.transform(ed["original"], ed["geom"]).size if ed["original"] is not None else (0, 0)
        self.size_lbl.configure(text=f"OUTPUT: {out[0]} x {out[1]} px")
    def _xy(self, e):
        return (min(1, max(0, (e.x - self._off[0]) / max(1, self._tw))), min(1, max(0, (e.y - self._off[1]) / max(1, self._th))))
    def _press(self, e):
        if self.app.edit["proxy"] is None: return
        self._start = self._xy(e)
    def _drag(self, e):
        if self.app.edit["proxy"] is None or not hasattr(self, "_start"): return
        (sx, sy), (x, y) = self._start, self._xy(e); r = self.ratio.get()
        if r != "Free":                                                                                  # keep the chosen shape
            a, b = (float(v) for v in r.split(":")); base_r = self._tw / max(1, self._th); want = (a / b) / base_r
            dx, dy = x - sx, y - sy; h_ = max(abs(dy), abs(dx) / want); dx, dy = (1 if dx >= 0 else -1) * h_ * want, (1 if dy >= 0 else -1) * h_
            x, y = min(1, max(0, sx + dx)), min(1, max(0, sy + dy))
        self.geom(crop=(sx, sy, x, y))

# ---------------------------------------------------------------- Generate


# ---------------------------------------------------------------- Image to Image

# ---------------------------------------------------------------- teach a word (themed dialog)

# ---------------------------------------------------------------- Train

# ---------------------------------------------------------------- Image Scraper
class ScraperPage(Page):
    """Training > Image Scraper: type keywords, it searches Google Images (Firefox, hidden) and saves each word's pictures to the
    images folder beside the app. The search engine is image_grabber.py (beside main.py); this page is its screen inside the app."""
    def __init__(self, master, app):
        super().__init__(master, app); self.thread = None; self.stop_event = threading.Event()
        T.Title(self, "Image scraper").pack(pady=(0, 6))
        self.intro = T.Text(self, "Keywords, one per line (up to 20). Pictures are saved to the images folder, one folder per keyword.", muted=True); self.intro.pack()
        self.words = T.Field(self, height=8, scroll=True); self.words.pack(fill="x", pady=(10, 0))
        r = themed_frame(self); r.pack(pady=12)
        self.start_btn = T.Button(r, "Start", self.start, width=12); self.start_btn.pack(side="left", padx=8)
        self.stop_btn = T.Button(r, "Stop", self.stop, width=12, kind="danger"); self.stop_btn.pack(side="left", padx=8); self.stop_btn.state("disabled")
        T.Button(r, "Open images folder", self.open_folder, width=20).pack(side="left", padx=8)
        T.Button(r, "Review & add", self.send_to_learning, width=16).pack(side="left", padx=8)
        T.Hints(self, [("TAB", "next button"), ("ENTER", "press")]).pack(side="bottom", pady=4)
        self.log_box = T.Field(self, height=10, scroll=True); self.log_box.pack(fill="both", expand=True)
        self.log_box.bind("<Key>", lambda e: None if (e.state & 4 and e.keysym.lower() in ("c", "a")) else "break")   # read-only (copy still works)

    def _grabber(self):
        try:
            import image_grabber; return image_grabber
        except Exception as e:
            T.banner(self.app, f"IMAGE SCRAPER UNAVAILABLE — {e}. It needs image_grabber.py beside main.py, plus Firefox, selenium and requests")

    def log(self, text):
        """called from the search thread: the line is added on the app's own thread"""
        if "ERROR" in str(text): self._had_error = True                       # (a "download failed, trying next" is normal: the next source is used)
        line = "[%s] %s" % (__import__("datetime").datetime.now().strftime("%H:%M:%S"), text)
        self.app.q.put(lambda: self._add_line(line))

    def _add_line(self, line):
        self.log_box.insert("end", line + "\n")
        try: self.log_box.see("end")
        except Exception: pass

    def running(self, on):
        self.start_btn.state("disabled" if on else "!disabled"); self.stop_btn.state("!disabled" if on else "disabled")

    def send_to_learning(self):
        """every picture the scraper saved -> the Pictures review for the active image model (you check them; the ones you keep go in, and the
        scraped files are deleted either way)"""
        g = self._grabber()
        if g is None: return
        exts = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
        ps = sorted(os.path.join(d, f) for d, _, fs in os.walk(g.OUTPUT_DIR) for f in fs if f.lower().endswith(exts))
        if not ps: return T.banner(self.app, "NOTHING TO REVIEW — the scraper hasn't saved any pictures yet")
        words = sorted({os.path.basename(os.path.dirname(p)) for p in ps})
        self.app.goto("AI Training", "Pictures"); tp = self.app.pages["AI Training"].pages["Pictures"]
        tp.review(ps[:300], remove_originals=True, source="Image Scraper (" + ", ".join(words[:6]) + ("…" if len(words) > 6 else "") + ")")

    def start(self):
        if self.thread is not None and self.thread.is_alive(): return
        g = self._grabber()
        if g is None: return
        words = []
        for w in self.words.get("1.0", "end").splitlines():
            w = w.strip()
            if w and w not in words: words.append(w)
        if not words: return T.banner(self.app, "NO KEYWORDS — type at least one keyword")
        if len(words) > g.MAX_WORDS: return T.banner(self.app, f"TOO MANY KEYWORDS — up to {g.MAX_WORDS} at a time (you typed {len(words)})")
        try: os.makedirs(g.OUTPUT_DIR, exist_ok=True)
        except Exception as e: return T.banner(self.app, f"CAN'T MAKE THE FOLDER — {g.OUTPUT_DIR}: {e}")
        self.stop_event.clear(); self.running(True); self._had_error = False
        try: g.IMAGES_PER_WORD = int(LA.get("Image Learning", "per_word"))                        # Image Learning > Collect > Pictures per word
        except (TypeError, ValueError): pass
        grabber = g.Grabber(words, self.log, self.stop_event)
        def work():
            try: grabber.run()
            finally:
                self.app.q.put(lambda: self.running(False))
                if self.stop_event.is_set(): T.banner(self.app, "IMAGE SCRAPER STOPPED — the pictures saved so far are in the images folder")
                elif self._had_error: T.banner(self.app, "IMAGE SCRAPER FINISHED WITH PROBLEMS — see its log for which pictures failed")
                else: T.banner(self.app, f"DOWNLOADED — pictures for {len(words)} keyword(s) are in the images folder", "success")
        self.thread = threading.Thread(target=work, daemon=True); self.thread.start()

    def stop(self):
        self.stop_event.set(); self.log("Stopping after the current image...")

    def open_folder(self):
        g = self._grabber()
        if g is None: return
        os.makedirs(g.OUTPUT_DIR, exist_ok=True)
        try:
            if sys.platform == "win32": os.startfile(g.OUTPUT_DIR)
            else: import subprocess; subprocess.Popen(["xdg-open" if sys.platform != "darwin" else "open", g.OUTPUT_DIR])
        except Exception as e: T.banner(self.app, f"CAN'T OPEN THE FOLDER — {e}")

# ---------------------------------------------------------------- Models

# ---------------------------------------------------------------- Words

# ---------------------------------------------------------------- Paint

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
                     "Painting engine, brushes, styles, editing, drawing studio and learning: written for Instant Easel Pro.",
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
        self.p = dict(border=p.get("border", 0.38), bg=p.get("bg", 0.62), opacity=p.get("opacity", 1.0))
        T.Title(self, "Theme").pack(pady=(0, 18)); self.sliders = {}
        for label, key, cls in (("PANEL OPACITY", "opacity", T.PlainSlider), ("BACKGROUND COLOR", "bg", T.HueSlider), ("BORDER COLOR", "border", T.HueSlider)):
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
        mb.showerror(APP_NAME, "Instant Easel Pro couldn't start.\n\n" + err_text + "\n\nThe details are in instant_easel_errors.log next to the app. "
                     "If it fails again, the next start uses safe mode (window, start page and splash settings reset).", parent=r)
        r.destroy()
    except Exception: pass

def run_app():
    import single
    holder = {}
    if not single.claim(on_show=lambda: holder.get("app") and holder["app"].q.put(holder["app"].bring_to_front)):
        return                                                           # already open: that copy comes to the front instead
    info = crash.start(home_dir(), prefs.log_error)                   # crash log, thread errors, freeze watchdog, last-session check
    if info["safe_mode"]:                                             # failed to start twice in a row: the settings most likely to blame go back to defaults
        for k in ("window_mode", "start_tab", "show_splash", "check_updates_on_start", "text_size"): prefs.set(k, prefs.DEFAULTS[k])
    try:
        app = InstantEasel(splash=bool(prefs.get("show_splash")) and not info["safe_mode"])   # built hidden (the splash shows the progress)
        holder["app"] = app
        app.restore_window()                                            # the fixed size, centred, before it is first shown
        app.show_window()                                               # laid out, zoomed and warmed up while invisible, then shown in one go
        app.after(2500, lambda: app.after_start(info))                  # up and running: a crash after this isn't a start-up failure
    except Exception as e:
        prefs.log_error(*sys.exc_info()); crash.start_failed(); _cant_start(f"{type(e).__name__}: {e}"); sys.exit(1)
    try: app.mainloop()
    except Exception: prefs.log_error(*sys.exc_info()); raise

if __name__ == "__main__":
    run_app()
