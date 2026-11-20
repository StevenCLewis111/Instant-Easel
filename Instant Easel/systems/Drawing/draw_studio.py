"""
draw_studio.py: Instant Easel's drawing studio (Editing > Draw), laid out like a full drawing app in Instant Easel's theme.
  Top:    Undo, Redo, Zoom -/+/Fit, Brush, Eraser, Eyedropper, Fill, Line, Rectangle, Ellipse, Text, Mirror; New, Open, Save
  Left:   brush library (all 45 brushes with live stroke previews) and brush properties (size, opacity, preview)
  Centre: the layered canvas (zoom with the wheel, pan with the right mouse button)
  Right:  layers (add, duplicate, delete, merge down, move, show/hide, opacity, blend mode) and colour (hue ring + square, hex, history)
Shortcuts: B brush, E eraser, I eyedropper, G fill, L line, T text, [ ] size, Ctrl+Z undo, Ctrl+Y redo
"""
import os, sys, math, json, shutil, threading, colorsys, types, tkinter as tk
from tkinter import filedialog, simpledialog
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFont
import theme as T, brushes, brush_art, prefs, brush_catalog as BC, ui_art as UA, art_panel as AP, skin
from paint_window import GROUPS, WHOLE_STROKE
from studio_extras import StudioExtras, SEL_TOOLS
from studio_more import StudioMore
from studio_groups import StudioGroups, Group

import paths; HERE = paths.APP                                    # (fonts/)
MODES = list(brushes.BLEND_MODES)                                              # layer blend modes (the same list brushes use)
TOOLS = [("Brush", "brush", "b"), ("Eraser", "eraser", "e"), ("Pick", "pick", "i"), ("Fill", "fill", "g"),
         ("Line", "line", "l"), ("Rect", "rect", None), ("Oval", "oval", None), ("Text", "text", "t"),
         ("Select", "sel_rect", "m"), ("Select oval", "sel_oval", None), ("Crop", "crop", "c"), ("Move", "move", "h"), ("Lasso", "sel_lasso", "f")]

TOOL_ICONS = {"brush": "brush", "eraser": "eraser", "pick": "eyedropper", "fill": "paint bucket", "line": "line", "rect": "rect", "oval": "oval", "text": "text",
              "sel_rect": "select rect", "sel_oval": "select oval", "crop": "crop", "move": "fit"}
BASIC_COLORS = [(230, 30, 40), (250, 130, 20), (250, 220, 30), (40, 200, 60), (30, 210, 230), (40, 90, 230), (150, 60, 220), (240, 60, 200)]
PALETTES = {"Warm": [(120, 30, 20), (200, 70, 30), (240, 140, 50), (250, 200, 90)], "Cool": [(20, 40, 90), (40, 100, 180), (80, 170, 220), (170, 230, 240)],
            "Pastel": [(250, 190, 200), (250, 230, 170), (190, 230, 200), (190, 200, 250)], "Earth": [(70, 50, 30), (130, 90, 50), (150, 140, 80), (200, 180, 140)]}

LEFT_W, RIGHT_W = 276, 282                                                   # side panel widths (design pixels): the canvas gets everything else

def slim(btn): btn.configure(padx=5, pady=3, font=T.f(9)); return btn            # narrow buttons for the side panels

OPT_KEYS = ("spacing", "flow", "hardness", "roundness", "angle", "rotation", "size_jitter", "scatter", "press_size", "press_opacity", "texture")
POLY_TOOLS = ("polygon", "polyline", "curve_tool")                            # click the corners, double-click (or Enter) to finish
GRAD_TOOLS = ("gradient", "gradient_radial")

TB_SIZES = [(44, 14, 6), (40, 13, 6), (36, 12, 6), (32, 12, 6), (29, 11, 6), (26, 11, 6), (23, 10, 5), (20, 9, 4)]                               # toolbar sizes, biggest first: icon, text, padding (design pixels)

def icon_btn(btn): btn.configure(padx=4, pady=4); return btn                    # icon-only buttons: just enough room round the picture

def small(btn): btn.configure(padx=7, pady=4, font=T.f(10)); return btn

STUDIOS = []                                                                   # open drawing studios (Settings > Shortcuts rebinds their keys)

# keys you can change (Settings > Shortcuts): action -> (what it does, default key as Tk names it)
KEY_ACTIONS = [("brush", "Brush", "b"), ("eraser", "Eraser", "e"), ("pick", "Eyedropper", "i"), ("fill", "Fill", "g"), ("line", "Line", "l"),
               ("text", "Text", "t"), ("sel_rect", "Select", "m"), ("sel_lasso", "Lasso", "f"), ("crop", "Crop", "c"), ("move", "Move the picture", "h"),
               ("smaller", "Smaller brush", "bracketleft"), ("bigger", "Bigger brush", "bracketright"), ("swap", "Swap colours", "x"),
               ("bw", "Black / white", "d"), ("turn_left", "Turn view left", "4"), ("turn_right", "Turn view right", "6"),
               ("straighten", "Straighten view", "5"), ("mirror_view", "Mirror view", "n")]
def key_map():
    """the keys in use: your changes (Settings > Shortcuts) over the defaults"""
    m = {a: k for a, _, k in KEY_ACTIONS}
    try: m.update({a: k for a, k in json.load(open(paths.json_file("draw_keys.json"), encoding="utf-8")).items() if a in m})
    except Exception: pass
    return m
def key_label(k):
    return {"bracketleft": "[", "bracketright": "]", "space": "Space", "comma": ",", "period": ".", "slash": "/", "minus": "-", "equal": "=",
            "semicolon": ";", "apostrophe": "'", "backslash": "\\", "grave": "`", "": "—"}.get(k, k.upper() if len(k) == 1 else k)

class Layer:
    """a layer: img is its picture; maskcv (if it has a mask) hides parts of it (where the mask has paint). cv is what painting goes
    onto: the mask while mask_edit is on, otherwise the picture"""
    def __init__(self, w, h, name):
        self.img = brushes.Canvas(w, h, paper=(255, 255, 255), transparent=True); self.name = name; self.maskcv = None; self.mask_edit = False
        self.visible = True; self.opacity = 1.0; self.mode = "normal"; self.clip = False      # clip: only shows where the layer below has paint
    @property
    def cv(self): return self.maskcv if self.mask_edit and self.maskcv is not None else self.img
    def shown(self, sl=(slice(None), slice(None))):
        """how much of the layer shows (its coverage, less what the mask hides)"""
        a = self.img.alpha[sl]
        return a if self.maskcv is None else a * (1 - self.maskcv.alpha[sl])
    def add_mask(self):
        if self.maskcv is None: self.maskcv = brushes.Canvas(self.img.w, self.img.h, paper=(0, 0, 0), transparent=True)
    def baked(self):
        """(colour, coverage) with the mask applied, for merging / saving"""
        return self.img.a, self.shown()

def blend_layer(bg, layer, sl=(slice(None), slice(None)), clip=None):
    """layer over bg; sl limits it to a region (bg is then that region only). clip: the coverage of the layer it's clipped to"""
    a = layer.shown(sl) * layer.opacity
    if clip is not None: a = a * clip
    a = a[..., None]; L = layer.img.a[sl]
    c = L if layer.mode == "normal" else brushes.blend_rgb(bg, L, layer.mode)
    return bg * (1 - a) + c * a

class DrawStudio(StudioGroups, StudioMore, StudioExtras, tk.Frame):
    WHOLE = True                                                               # the Draw tab is this one page (no side menu)
    def __init__(self, master, app, size=(1600, 1100)):
        super().__init__(master, bg=master["bg"]); self.app = app; T.on_change(lambda: self.configure(bg=self.master["bg"])); STUDIOS.append(self); self._groups_init()
        self.color = (196, 92, 44); self.color2 = (255, 255, 255); self.history = []; self.tool = "brush"; self.brush = "round"; self.size = 24; self.opacity = 0.5   # brushes start half see-through
        self._x_init()                                                              # select / crop / text state (studio_extras)
        self.mirror = tk.BooleanVar(value=False); self.undo_stack, self.redo_stack = [], []; self.zoom = None; self.pan = [0, 0]
        self.mirror_y = tk.BooleanVar(value=False); self.use_pressure = tk.BooleanVar(value=False)                      # Brush Options switches
        self.color_mode = tk.StringVar(value="Normal"); self.blend_mode = tk.StringVar(value="Brush default"); self._hue = 0.0
        self.opts = {k: None for k in OPT_KEYS}; self._icons = {}
        self.view_rot = 0.0; self.view_flip = False                                 # turning / mirroring the VIEW (the picture itself doesn't change)
        self.lock_alpha = tk.BooleanVar(value=False); self.radial = tk.StringVar(value="Off"); self.stamp_colors = tk.StringVar(value="Their own colors"); self.fill_sample = tk.StringVar(value="All layers")
        self.gopts = dict(smooth=45.0, tolerance=24.0, feather=0.0); self.my_colors = self._load_my_colors(); self.pic_colors = []
        self.fill_sample = tk.StringVar(value="All layers"); self.grad_to = tk.StringVar(value="Clear"); self.texture_colors = tk.StringVar(value="Their own colors"); self._last_pattern = "checks"; self._poly = None
        self._big = False; self._hidden = []; self._tight = []; self._tipsets = {}     # "studio fills the page" mode                     # None = the brush's own setting
        self._job = None; self.points = []; self._prev = None
        self._tick_job = None; self._pending = []; self._last_pt = None; self._patches = []; self._edit = None; self._dirty = None
        self._pv_job = None; self._layer_job = None; self._ui_job = None; self._wheel_cache = (None, None); self._in_layers_ui = False
        self.changed = False                                         # anything drawn since the last autosave (crash recovery)
        self._toolbar(); body = tk.Frame(self, bg=self["bg"]); body.pack(fill="both", expand=True); T.on_change(lambda: body.configure(bg=self["bg"]))
        self._left(body); self._right(body)
        self.cv = self._cv_small = self._make_canvas(body); self.cv.pack(side="left", fill="both", expand=True, padx=6)

        self.bind("<Map>", lambda e: e.widget is self and self._start_tiles(), add="+")      # brush previews are made the first time Draw is opened
        self.new(*size)

    # ------------------------------------------------------------------ layout
    def _toolbar(self):
        """one row from edge to edge: equal gaps between all the buttons (the gaps grow and shrink with the window), and the buttons
        themselves at the biggest of three sizes that fits"""
        bar = self._bar = tk.Frame(self, bg=self["bg"]); bar.pack(fill="x", pady=(0, 6)); T.on_change(lambda: bar.configure(bg=self["bg"]))
        self._tb = []; self._tb_size = None
        def add(w, kind, icon=None):
            if self._tb:                                                           # a stretchy gap before every item but the first: all gaps equal
                g = tk.Frame(bar, width=2, height=1, bg=self["bg"]); g.pack(side="left", fill="x", expand=True); T.on_change(lambda g=g: g.configure(bg=self["bg"]))
            w.pack(side="left"); self._tb.append((w, kind, icon)); return w
        # left to right: file, undo / redo, view, cut-outs, painting tools, shapes, zoom, text (then mirror and the studio-size button)
        files = {"new": ("New", lambda: self.new(*self.size_wh), "danger", "New picture"), "open": ("Open", self.open, "normal", "Open a picture"),
                 "save": ("Save", self.save, "normal", "Save the picture")}
        icons = {"undo": ("Undo (Ctrl+Z)", self.undo), "redo": ("Redo (Ctrl+Y)", self.redo),                  "zoom out": ("Zoom out (or the mouse wheel, where the mouse is)", lambda: self.zoom_by(1 / 1.25)), "zoom in": ("Zoom in (or the mouse wheel, where the mouse is)", lambda: self.zoom_by(1.25))}
        names = {"brush": "Paint brush", "eraser": "Eraser", "pick": "Color picker (click the picture to take its color)", "fill": "Fill (paint bucket)",
                 "line": "Draw line", "rect": "Draw rectangle", "oval": "Draw circle", "text": "Text", "sel_rect": "Select area (rectangle)",
                 "sel_oval": "Select area (circle)", "crop": "Crop",
                 "move": "Move: drag the picture around (double-click it to fit it back)"}
        keys = {tool: key for _, tool, key in TOOLS}
        order = ["new", "open", "save", "undo", "redo", "brush", "eraser", "fill", "move", "crop", "sel_rect", "sel_oval",   # (colour picking: Pick on the Color side)
                 "line", "rect", "oval", "zoom out", "zoom in", "text"]
        self.tool_btns = {}
        for k in order:
            if k in files:
                text, cmd, kind, tip = files[k]; add(self._tip(T.Button(bar, text, cmd, kind=kind), tip), "file", k)
            elif k in icons:
                tip, cmd = icons[k]; add(self._tip(T.Button(bar, "", cmd), tip), "icon", k)
            else:
                tip = names[k] + (f"  ({keys[k].upper()})" if keys.get(k) else "")
                self.tool_btns[k] = add(self._tip(T.Button(bar, "", lambda t=k: self.set_tool(t)), tip), "icon", TOOL_ICONS.get(k))
        r = tk.Frame(bar, bg=self["bg"]); T.on_change(lambda: r.configure(bg=self["bg"]))
        self._mirror_lbl = self._tip(T.Text(r, ""), "Mirror: paint both sides at once (left-right)"); self._mirror_lbl.pack(side="left")
        if UA.toolbar("toggle_on") is not None and UA.toolbar("toggle_off") is not None:     # painted on/off switch
            self._mirror_sw = tk.Label(r, bg=self["bg"], cursor="hand2", bd=0, highlightthickness=0); self._mirror_sw.pack(side="left", padx=4)
            self._mirror_sw.bind("<Button-1>", lambda e: self.mirror.set(not self.mirror.get()))
            self.mirror.trace_add("write", lambda *a: self._mirror_switch()); T.on_change(lambda: self._mirror_sw.configure(bg=self["bg"]))
            self._tip(self._mirror_sw, "Mirror on / off")
        else: self._mirror_sw = None; T.Toggle(r, self.mirror).pack(side="left", padx=4)
        add(r, "mirror", "mirror")
        self._big_btn = add(self._tip(T.Button(bar, "", self.toggle_big), "Expand: the studio fills the whole page", key="big"), "icon", "maximize")
        self._fit_job = None; self._size_toolbar(TB_SIZES[-1]); bar.bind("<Configure>", lambda e: self._fit_toolbar())

    def _size_toolbar(self, size):
        """put the toolbar at one of TB_SIZES: (icon size, text size, padding), all in design pixels"""
        if size == self._tb_size: return
        self._tb_size = size; ic, fs, pad = size; px = max(10, int(round(ic * T.Z))); hpx = px + 2 * max(1, int(round(pad * T.Z))); self._art_h = hpx
        for w, kind, icon in self._tb:
            if w is self._big_btn: icon = "restore" if self._big else "maximize"     # normal size: single square, expanded: double square
            art = UA.toolbar(icon, h=hpx) if kind in ("file", "icon") else None
            if art is not None: self._art_button(w, art); continue                 # painted picture: it is the whole button
            if kind == "file": w.configure(font=T.f(fs), padx=pad + 2, pady=pad); self._with_icon(w, icon, px)
            elif kind == "icon": w.configure(padx=pad, pady=pad); self._with_icon(w, icon, px)
            else:
                art = UA.toolbar(icon, h=hpx)
                if art is not None:
                    k = ("mir", art.size)
                    if k not in self._icons: self._icons[k] = ImageTk.PhotoImage(art)
                    self._mirror_lbl.configure(image=self._icons[k], text="", compound="center")
                else: self._with_icon(self._mirror_lbl, icon, px)
                self._mirror_switch()
        self._icon_px = px

    def _fit_toolbar(self):
        """the bar changed width: choose the toolbar size once things settle (never in the middle of a resize)"""
        if self._bar.winfo_width() == getattr(self, "_fit_w", None): return              # same width as last time: nothing to do (stops resize loops)
        T.defer(self, "toolbar", 30, self._fit_now)

    def _fit_now(self, tries=0):
        """the biggest size whose buttons fit the bar's width, with at least a small gap between each"""
        self._fit_job = None; width = self._bar.winfo_width()
        if width < 50: return
        self._fit_w = width
        for size in TB_SIZES:
            self._size_toolbar(size); self._bar.update_idletasks()
            need = sum(w.winfo_reqwidth() for w, _, _ in self._tb) + self._apx(6) * (len(self._tb) - 1)     # biggest buttons that still leave a small gap
            if need <= width: break
        if self._bar.winfo_width() != width and tries < 2: self._fit_now(tries + 1)      # the width moved while measuring: once more
        self._fit_w = self._bar.winfo_width()

    @staticmethod
    def _raw_set(w, kind, vals):
        """set sizes as exact pixels (not through the zoom), so they can be put back exactly"""
        args = [x for k, v in vals.items() for x in ("-" + k, v)]
        if kind == "opt": w.tk.call(w._w, "configure", *args)
        else: w.tk.call("pack", "configure", w._w, *args)

    def _make_canvas(self, parent):
        """a drawing canvas with all its mouse and key handling (the normal one, and the whole-page one, work the same)"""
        cv = tk.Canvas(parent, bg="#2a2d36", highlightthickness=1, bd=0, cursor="crosshair")      # a border on all four sides, like the panels beside it
        edge = lambda: cv.configure(highlightbackground=T.PALETTE["border"], highlightcolor=T.PALETTE["border"]); edge(); T.on_change(edge)
        for ev, fn in (("<ButtonPress-1>", self.down), ("<B1-Motion>", self.drag), ("<ButtonRelease-1>", self.up),
                       ("<ButtonPress-3>", self._pan_start), ("<B3-Motion>", self._pan_move), ("<MouseWheel>", self._wheel),
                       ("<Button-4>", lambda e: self.zoom_by(1.15, (e.x, e.y))), ("<Button-5>", lambda e: self.zoom_by(1 / 1.15, (e.x, e.y))), ("<Configure>", lambda e: self._cv_resized())):
            cv.bind(ev, fn)
        cv.bind("<Enter>", lambda e: cv.focus_set())
        cv.bind("<Double-Button-1>", lambda e: self.fit() if self.tool == "move" else (self._poly_finish() if self.tool in POLY_TOOLS else None), add="+")   # Move: fit back; Polygon / Curve: finish
        cv.bind("<Motion>", lambda e: self._poly_preview(self.to_img(e)) if self.tool in POLY_TOOLS and self._poly else None, add="+")
        for ev in ("<Motion>", "<B1-Motion>", "<Enter>"): cv.bind(ev, lambda e: self._tip_move(e), add="+")   # the brush tip follows the mouse
        cv.bind("<Leave>", lambda e: self._tip_hide(e.widget), add="+"); cv.bind("<Unmap>", lambda e: self._tip_hide(e.widget), add="+")
        cv.bind("<Escape>", lambda e: self.x_key(e) or ((self.toggle_big(), "break")[1] if self._big else None))
        for k in ("<Delete>", "<BackSpace>", "<Return>", "<Control-a>", "<Control-c>", "<Control-x>", "<Control-v>"): cv.bind(k, lambda e: self.x_key(e))
        cv.bind("<Double-Button-1>", lambda e: (self.tool == "crop" and self._crop is not None and self._crop_hit(self.to_img(e)) == "in" and self._crop_apply()) or None)
        for key, fn in (("<Control-z>", lambda e: (self.undo(), "break")[1]), ("<Control-y>", lambda e: (self.redo(), "break")[1])):
            cv.bind(key, fn)
        self._key_cvs = getattr(self, "_key_cvs", []) + [cv]; self._bind_keys(cv)
        cv.bind("<Control-t>", lambda e: self.x_key(e)); cv.bind("<Control-d>", lambda e: self.x_key(e))
        cv.bind("<Shift-ButtonPress-3>", self._turn_start); cv.bind("<Shift-B3-Motion>", self._turn_move)
        return cv

    def _key_action(self, a):
        """what each changeable key does"""
        if a in ("brush", "eraser", "pick", "fill", "line", "text", "sel_rect", "sel_lasso", "crop", "move"): self.set_tool(a)
        elif a == "smaller": self.set_size(self.size / 1.2)
        elif a == "bigger": self.set_size(self.size * 1.2)
        elif a == "swap": self.swap_colors()
        elif a == "bw": self.default_colors()
        elif a == "turn_left": self.set_view(delta=-15)
        elif a == "turn_right": self.set_view(delta=15)
        elif a == "straighten": self.set_view(rot=0, flip=False)
        elif a == "mirror_view": self.set_view(flip=not self.view_flip)

    def _bind_keys(self, cv):
        for k in getattr(cv, "_my_keys", []):                                   # the old keys go first
            try: cv.unbind(k)
            except tk.TclError: pass
        cv._my_keys = []
        for a, k in key_map().items():
            if not k: continue
            seq = f"<Key-{k}>"
            try: cv.bind(seq, lambda e, a=a: self._key_action(a)); cv._my_keys.append(seq)
            except tk.TclError: pass

    def rebind_keys(self):
        for cv in getattr(self, "_key_cvs", []):
            try: self._bind_keys(cv)
            except tk.TclError: pass

    def _turn_start(self, e):
        W, H = self.cv.winfo_width(), self.cv.winfo_height(); self._turn0 = (math.atan2(e.y - H / 2, e.x - W / 2), math.degrees(self.view_rot))
    def _turn_move(self, e):
        """Shift + right-drag: turn the view freely round the middle of the window (snaps to straight when close)"""
        if getattr(self, "_turn0", None) is None: return
        W, H = self.cv.winfo_width(), self.cv.winfo_height(); a = math.degrees(math.atan2(e.y - H / 2, e.x - W / 2) - self._turn0[0]) + self._turn0[1]
        r = ((a + 180) % 360) - 180
        self.set_view(rot=0 if abs(r) < 3 else r)

    def toggle_big(self):
        """studio fills the page / back: painting held until the new layout (toolbar size, tiles, canvas) is finished"""
        top = self.winfo_toplevel()
        with T.frozen(top):
            self._toggle_big_now(); T.flush(top)

    def _toggle_big_now(self):
        """[][] : the whole Draw studio (toolbar, brushes, canvas, layers & colour) fills the page inside the green border, over the
        tabs, logo and the Editing menu.  [] (or Esc) : back to normal"""
        app = self.app; sec = self.master.master                                   # the Editing section: its side menu and divider sit left of the page
        line = sec.winfo_children()[1]
        if not self._big:
            # (what's hidden, and what it goes back in front of)
            self._hidden = [(w, w.pack_info(), nxt) for w, nxt in ((app.top, app.body), (sec.side, line), (line, sec.content)) if w.winfo_manager() == "pack"]
            for w, _, _ in self._hidden: w.pack_forget()
            # no margins, padding or inner border between the studio and the green border (raw values, put back exactly later)
            self._tight = [(app.frame, "opt", {"padx": app.frame.cget("padx")}), (app.body, "opt", {"highlightthickness": app.body.cget("highlightthickness")}),
                           (app.body, "pack", {k: app.body.pack_info()[k] for k in ("padx", "pady")}), (self, "pack", {k: self.pack_info()[k] for k in ("padx", "pady")})]
            for w, kind, vals in self._tight: self._raw_set(w, kind, {k: 0 for k in vals})
            self._big = True
        else:
            for w, kind, vals in self._tight: self._raw_set(w, kind, vals)
            for w, info, nxt in reversed(self._hidden):                            # back exactly where and how it was (raw pixels, so the zoom doesn't rescale them)
                opts = []
                for k, v in info.items():
                    if k != "in": opts += ["-" + k, v]
                w.tk.call("pack", "configure", w._w, "-before", nxt._w, *opts)
            import sys
            m = sys.modules.get("main") or sys.modules.get("__main__")             # if the window was resized meanwhile: back at the current size
            if hasattr(m, "_zreapply"):
                for w in [w for w, _, _ in self._hidden] + [w for w, _, _ in self._tight]: m._zreapply(w, T.Z)
            self._hidden = []; self._tight = []; self._big = False
        icon = "restore" if self._big else "maximize"; art = UA.toolbar(icon, h=getattr(self, "_art_h", 30))     # normal size: single square, expanded: double square
        if art is not None: self._art_button(self._big_btn, art)
        else: self._with_icon(self._big_btn, icon, getattr(self, "_icon_px", 18))
        self._tipsets["big"]("Back to normal size (Esc)" if self._big else "Expand: the studio fills the whole page")
        self.update_idletasks(); self.cv.focus_set()                          # the view keeps its place (see _cv_resized)

    def _fixed_width(self, panel, design_w):
        """a side panel at a fixed width (scaled with the window); its contents fit inside it, the canvas gets the rest"""
        panel.pack_propagate(False); size = lambda: panel.configure(width=max(1, int(round(design_w * T.Z))))
        size(); T.on_change(size, zoom=True)

    def _mirror_switch(self):
        """the painted mirror switch: the on or off picture, as tall as the toolbar buttons"""
        sw = getattr(self, "_mirror_sw", None)
        if sw is None or not sw.winfo_exists(): return
        im = UA.toolbar("toggle_on" if self.mirror.get() else "toggle_off", h=max(10, int(getattr(self, "_art_h", 30) * 0.8)))
        key = ("sw", im.size, bool(self.mirror.get()))
        if key not in self._icons: self._icons[key] = ImageTk.PhotoImage(im)
        sw.configure(image=self._icons[key])

    def _art_button(self, w, im):
        """a painted button picture as the whole button: no blue box behind it; the green ring still shows on hover, focus and the chosen tool"""
        key = ("art", id(w), im.size)
        if key not in self._icons: self._icons[key] = ImageTk.PhotoImage(im)
        w._art_im = im; w.configure(text="", compound="center", padx=0, pady=0)
        if getattr(w, "_is_art", False): w._style(); return
        w._is_art = True; w._selected = False; w.__dict__.get("_zd", {}).get("opt", {}).pop("highlightthickness", None)
        def style():
            if not w.winfo_exists(): return
            on = bool((w.hover and w.enabled) or w._selected or (w.focus_get() is w)); im2 = skin.ringed(w._art_im, on, key=("tb", id(w._art_im)))
            k = ("artr", id(w._art_im), on, T.PALETTE["border"] if on else None, im2.size)
            if k not in self._icons: self._icons[k] = ImageTk.PhotoImage(im2)
            w.tk.call(w._w, "configure", "-highlightthickness", 0); w.configure(bg=w.master["bg"], image=self._icons[k])
        w._style = style; style(); T.on_change(style)

    def _with_icon(self, w, name, size=16):
        """put one of the app's drawn icons on a button or label, left of its text"""
        if not name: return w
        key = (name, size)
        if key not in self._icons: self._icons[key] = ImageTk.PhotoImage(BC.icon(name, size))
        w.configure(image=self._icons[key], compound="left" if w.cget("text") else "center"); return w

    def _tip(self, w, text, key=None):
        """a small label naming a button, shown while the mouse rests on it"""
        st = {"job": None, "win": None, "text": text}
        if key: self._tipsets[key] = lambda t: st.__setitem__("text", t)
        def show():
            st["job"] = None
            if st["win"] is not None: return
            t = tk.Toplevel(w); t.overrideredirect(True); t.attributes("-topmost", True)
            tk.Label(t, text=st["text"], font=T.f(9), fg="white", bg=T.PALETTE["panel2"], padx=6, pady=2, highlightthickness=1, highlightbackground=T.PALETTE["border"]).pack()
            t.geometry(f"+{w.winfo_rootx()}+{w.winfo_rooty() + w.winfo_height() + 4}"); st["win"] = t
        def hide(e=None):
            if st["job"]: w.after_cancel(st["job"]); st["job"] = None
            if st["win"] is not None: st["win"].destroy(); st["win"] = None
        w.bind("<Enter>", lambda e: st.__setitem__("job", w.after(450, show)), add="+"); w.bind("<Leave>", hide, add="+"); w.bind("<Button-1>", hide, add="+")
        return w

    def _slider_row(self, parent, label, value, command, shown):
        """the guide's slider bar: name, slider, value box (type a number + Enter to set it exactly)"""
        r = tk.Frame(parent, bg=parent["bg"]); r.pack(fill="x", pady=1); T.on_change(lambda: r.configure(bg=r.master["bg"]))
        T.Text(r, label, font=T.f(8), width=9, anchor="w").pack(side="left")
        v = tk.StringVar(value=shown); e = T.Entry(r, v, width=5); e.configure(font=T.f(8), justify="center"); e.pack(side="right")
        s = T.PlainSlider(r, value=value, width=98, command=command); s.pack(side="right", padx=3)
        r.slider, r.var, r.entry = s, v, e; return r

    def _left(self, body):
        L = self._edged_panel(body, "left"); self.L = L; self._fixed_width(L, LEFT_W)
        sw = tk.Frame(L, bg=L["bg"]); sw.pack(fill="x", pady=(0, 4)); self.view_btns = {}
        for name in ("Brushes", "Adjustments"):
            b = skin.button(small(T.Button(sw, name, lambda n=name: self._left_view(n), width=10)), piece="bar"); b.pack(side="left", expand=True); self.view_btns[name] = b
        self.lib_view = tk.Frame(L, bg=L["bg"]); self.opt_view = tk.Frame(L, bg=L["bg"])
        T.on_change(lambda: (self.lib_view.configure(bg=L["bg"]), self.opt_view.configure(bg=L["bg"])))
        sw.pack_configure(pady=(0, 9))                                                # room for the line under Brushes / Adjustments
        lline = T.Line(L)                                                            # the line under the two buttons, edge to edge (like the right side)
        def lborder(e=None):
            try:
                e_ = int(float(L.cget("bd"))) + int(float(L.cget("highlightthickness")))
                px_, py_ = e_ + int(float(L.cget("padx"))), e_ + int(float(L.cget("pady"))); t_ = max(1, int(round(T.Z)))
                y = sw.winfo_rooty() + sw.winfo_height() - L.winfo_rooty() - py_ + 4
                lline.place(x=-px_ + e_, y=y, width=L.winfo_width() - 2 * e_, height=t_); lline.lift()
            except tk.TclError: pass
        for w_ in (sw, L): w_.bind("<Configure>", lambda e: L.after_idle(lborder), add="+")
        pinned = self._pinned = tk.Frame(L, bg=L["bg"]); pinned.pack(side="bottom", fill="x"); T.on_change(lambda: pinned.configure(bg=L["bg"]))
        self._art_by_engine = {}                                                     # brush -> its painted tile or preview strip (shown under its name)
        box = T.ScrollBox(self.lib_view, bg="panel2"); box.pack(fill="both", expand=True, pady=(0, 4))    # boxed list: wheel anywhere inside, slider sized to the list
        sc = tk.Canvas(box.body, width=10, height=330, bg=L["bg"], highlightthickness=0); box.attach(sc); self._sc = sc
        inner = tk.Frame(sc, bg=L["bg"]); sc.create_window((0, 0), window=inner, anchor="nw"); inner.bind("<Configure>", lambda e: T.fit_scrollregion(sc))
        sc.pack(side="left", fill="both", expand=True, padx=(4, 0))
        self.tiles = {}; self._tile_ph = {}; self._live_tiles = []; self._tile_src = {}; self._tile_names = []; self._icon_tiles = []; self._art_tiles = []
        def art_bg():                                                                # painted tiles sit straight on the panel
            for lb in self._art_tiles:
                sel = lb.cget("highlightbackground") == T.PALETTE["border"]; lb._off = L["bg"]
                lb.configure(bg=L["bg"], highlightbackground=T.PALETTE["border"] if sel else L["bg"])
        T.on_change(art_bg)
        self._tw = 80; self._ic = 30; self._lh = 12; self._tile_soon = {}; self._tile_cache = {}; self._name_cache = {}; self._fitted = False
        sc.bind("<Configure>", lambda e: T.defer(self, "tiles", 40, self._fit_tiles), add="+")              # once the size settles, not on every step
        self._pills = []
        def pill(text):                                                              # a section heading: the HISTORY-style bar, name in the middle
            h = tk.Label(inner, bd=0, highlightthickness=0, padx=0, pady=0, bg=L["bg"]); h.pack(pady=(8, 4))      # centred over its two tiles
            h._text = text.upper(); h._grid = None; self._pills.append(h); self._set_pill(h)
            T.on_change(lambda: h.configure(bg=h.master["bg"])); return h
        for title, layout, items in BC.sections(brushes.B):
            if layout == "icons": continue                                           # Stamps & Icons: not shown in the brush list
            ph_ = pill(title); grid = tk.Frame(inner, bg=L["bg"]); grid.pack(); ph_._grid = grid
            if layout == "icons":                                                    # stamps: a grid of small pictures
                for i, it in enumerate(items):
                    lb = tk.Label(grid, bg="#0d1220", cursor="hand2", highlightthickness=1, highlightbackground=L["bg"])
                    lb.grid(row=i // 5, column=i % 5, padx=2, pady=2); lb.bind("<Button-1>", lambda e, it=it, t=title: self._pick(it, t))
                    self._icon_tiles.append((lb, it["name"])); self._set_icon(lb, it["name"])
                T.Text(inner, "Stamps: coming soon", muted=True, font=T.f(7)).pack(anchor="w", padx=4)
                continue
            for i, it in enumerate(items):
                m_ = self._apx(7)                                                        # a gap from the box's lines on the left and right
                cell = tk.Frame(grid, bg=L["bg"]); cell.grid(row=i // 2, column=i % 2, padx=(m_, 3) if i % 2 == 0 else (3, m_), pady=3, sticky="n")
                art = UA.tile_image(it["name"], title); off = L["bg"] if art is not None else "#f4eee2"
                lb = tk.Label(cell, bg=off, highlightthickness=T.HL, highlightbackground=off, cursor="hand2"); lb.pack(); lb._off = off
                lb._engine = it["engine"]; lb.bind("<Button-1>", lambda e, it=it, t=title: self._pick(it, t))
                planned = it["engine"] is None and not it.get("studio_tool")
                nm = tk.Label(cell, text=it["name"], bg=L["bg"], fg=T.PALETTE["muted"] if planned else "white", font=T.f(7)); nm._full = it["name"]
                if art is None or not UA.says_its_name(it["name"], title): nm.pack()              # painted tiles that show their own name need no label
                self._tile_names.append(nm)
                key = f"{title}:{it['name']}"; self.tiles[key] = lb
                pic = art if art is not None else UA.preview(it["name"], title)
                if pic is not None and it["engine"] is not None: self._art_by_engine.setdefault(it["engine"], pic)
                if art is not None:                                                            # the painted tile: frame, name and picture
                    self._art_tiles.append(lb); self._set_tile(key, self._soon_tag(art) if planned else art)
                    if it["engine"] is not None and it["engine"] == getattr(self, "brush", None): lb.configure(highlightbackground=T.PALETTE["border"])
                elif UA.preview(it["name"], title) is not None:                                  # a painted preview strip from the guides
                    self._set_tile(key, UA.preview(it["name"], title).convert("RGB"), soon=planned)
                    if it["engine"] is not None and it["engine"] == getattr(self, "brush", None): lb.configure(highlightbackground=T.PALETTE["border"])
                elif it["engine"] is None: self._set_tile(key, BC.preview(it), soon=planned)       # drawn preview (marked SOON only if it isn't built)
                else: self._set_tile(key, Image.new("RGB", (96, 30), (244, 238, 226))); self._live_tiles.append((key, it["engine"]))
        self._tiles_started = False
        # ---- always in view: the brush, its preview, size and opacity
        self.brush_lbl = T.Text(pinned, "Round", font=T.f(10)); self.brush_lbl.pack(pady=(6, 0))
        self._pv = ImageTk.PhotoImage(Image.new("RGB", (200, 46), (244, 238, 226)))            # a picture from the start, so width/height are pixels (not 200 letters wide)
        self.preview = tk.Label(pinned, bg="#f4eee2", image=self._pv, width=200, height=46); self.preview.pack(pady=4); self._pw = 200
        pinned.bind("<Configure>", lambda e: self._fit_preview(pinned), add="+"); self._preview()
        self.size_row = self._slider_row(pinned, "Size:", self._s2v(24), lambda v: self.set_size(self._v2s(v), from_slider=True), "24")
        self.size_row.entry.bind("<Return>", lambda e: self._typed(self.size_row, lambda x: self.set_size(x)))
        self.op_row = self._slider_row(pinned, "Opacity:", 0.5, self.set_opacity, "50%")
        self.op_row.entry.bind("<Return>", lambda e: self._typed(self.op_row, lambda x: (self.set_opacity(x / 100), self._sync_slider(self.op_row, self.opacity))))
        self.size_s, self.op_s = self.size_row.slider, self.op_row.slider
        # ---- Options view
        # Adjustments scrolls like the right side: a rail on the panel's right (scroll bar, a border line left of it) beside the
        # size / opacity rows and the options, which sit in a scrolling canvas with a gap before the line
        g = T.ScrollBox.GAP; self._adj_rail = rail = tk.Frame(L, bg=L["bg"])
        asb = T.Scrollbar(rail, "vertical"); asb.pack(side="right", fill="y", padx=(int(float(L.cget("padx"))) - 1, 0), pady=g); T.Line(rail, vertical=True).pack(side="right", fill="y")
        acv = tk.Canvas(self.opt_view, bd=0, highlightthickness=0, bg=L["bg"], width=10); acv.pack(fill="both", expand=True, padx=(0, g))
        O = tk.Frame(acv, bg=L["bg"]); awin = acv.create_window(0, 0, window=O, anchor="nw")
        asb.command = acv.yview; acv.configure(yscrollcommand=asb.set)
        def afit(e=None):                                                            # as tall as the view (Reset stays at the bottom), taller when needed
            try:
                h_ = max(acv.winfo_height(), O.winfo_reqheight())
                acv.itemconfigure(awin, width=acv.winfo_width(), height=h_); acv.configure(scrollregion=(0, 0, acv.winfo_width(), h_))
            except tk.TclError: pass
        O.bind("<Configure>", afit, add="+"); acv.bind("<Configure>", afit, add="+")
        T.wheel_area(self.opt_view, lambda n: asb.can_scroll() and acv.yview_scroll(n, "units"))
        T.on_change(lambda: (rail.configure(bg=L["bg"]), acv.configure(bg=L["bg"]), O.configure(bg=L["bg"])))
        self._adj_canvas = acv
        hd = tk.Frame(O, bg=O["bg"]); hd.pack(fill="x", pady=(2, 4)); self._title(hd, "BRUSH OPTIONS").pack()
        ft = tk.Frame(O, bg=O["bg"]); ft.pack(side="bottom", fill="x", pady=(4, 0)); T.on_change(lambda: ft.configure(bg=O["bg"]))      # Reset: bottom right
        self._tip(small(T.Button(ft, "Reset", lambda: self._load_brush_opts(self.brush))), "Back to this brush's own settings").pack(side="right")
        OPTS = [("spacing", "Spacing:", 1, 200, "%", "How far apart the dabs are, in brush widths (low = smooth, high = dotted / spaced stamps)"),
                ("flow", "Flow:", 1, 100, "%", "How much paint each dab adds. Low builds up softly; the stroke never goes past your Opacity"),
                ("hardness", "Hardness:", 0, 100, "%", "Soft or crisp edge"),
                ("roundness", "Round:", 5, 100, "%", "100% is round; lower squashes the tip flat (turn it with Angle)"),
                ("angle", "Angle:", 0, 180, "°", "Turns the tip and keeps it that way (it stops following the stroke)"),
                ("rotation", "Rotate:", 0, 180, "°", "Turns each dab a random amount, up to this"),
                ("size_jitter", "Jitter:", 0, 100, "%", "Makes each dab a random amount bigger or smaller"),
                ("scatter", "Scatter:", 0, 300, "%", "Spreads the dabs out from the line you draw"),
                ("press_size", "Pr. Size:", 0, 100, "%", "How much pressure (a pen, or the mouse's speed) changes the size"),
                ("press_opacity", "Pr. Opac:", 0, 100, "%", "How much pressure (a pen, or the mouse's speed) changes how see-through it is"),
                ("texture", "Texture:", 0, 100, "%", "How strongly a texture brush's texture shows")]
        self.opt_rows = {}
        for key, label, lo, hi, unit, tip in OPTS:
            row = self._slider_row(O, label, 0.5, lambda v, k=key, lo=lo, hi=hi: self._set_opt(k, lo + v * (hi - lo)), "")
            row.entry.bind("<Return>", lambda e, k=key, row=row: self._typed(row, lambda x, k=k: self._set_opt(k, x, sync=True))); row.unit, row.range = unit, (lo, hi)
            self._tip(row.slider, tip); self.opt_rows[key] = row
        def head(text):                                                           # a small heading between the groups
            r = tk.Frame(O, bg=O["bg"]); r.pack(fill="x", pady=(8, 1)); T.on_change(lambda: r.configure(bg=O["bg"]))
            T.Text(r, text, muted=True, font=T.f(8)).pack()
        def choice(label, var, choices, tip=None):
            r = tk.Frame(O, bg=O["bg"]); r.pack(fill="x", pady=2); T.on_change(lambda: r.configure(bg=O["bg"]))
            T.Text(r, label, font=T.f(8), width=11, anchor="w").pack(side="left"); c = T.Choice(r, "", choices, var); c.pack(side="left", fill="x", expand=True)
            if tip: self._tip(c, tip)
        def toggle(label, var, tip=None):
            r = tk.Frame(O, bg=O["bg"]); r.pack(fill="x", pady=2); T.on_change(lambda: r.configure(bg=O["bg"]))
            T.Text(r, label, font=T.f(8)).pack(side="left"); t_ = T.Toggle(r, var, command=self.refresh); t_.pack(side="right")
            if tip: self._tip(t_, tip)
        self.g_rows = {}
        def gslider(key, label, tip):
            row = self._slider_row(O, label, self.gopts[key] / 100, lambda v, k=key: self._set_g(k, v * 100), f"{int(self.gopts[key])}%")
            row.entry.bind("<Return>", lambda e, k=key, row=row: self._typed(row, lambda x, k=k: self._set_g(k, x, sync=True))); self._tip(row.slider, tip); self.g_rows[key] = row
        head("MY BRUSHES")                                                         # your own brushes: a brush with your settings, kept
        self.preset_var = tk.StringVar(value="—"); r = tk.Frame(O, bg=O["bg"]); r.pack(fill="x", pady=2); T.on_change(lambda: r.configure(bg=O["bg"]))
        self._preset_choice = T.Choice(r, "", ["—"] + sorted(self._presets()), self.preset_var); self._preset_choice.pack(side="left", fill="x", expand=True)
        self._tip(self._preset_choice, "Your saved brushes: click for the next one (right-click for the one before)")
        self.preset_var.trace_add("write", lambda *a: self._use_preset(self.preset_var.get()))
        r = tk.Frame(O, bg=O["bg"]); r.pack(fill="x", pady=(2, 2)); T.on_change(lambda: r.configure(bg=O["bg"]))
        self._tip(small(T.Button(r, "Save brush", self._save_preset)), "Keep this brush with its size, opacity and every setting above, under a name").pack(side="left")
        self._tip(small(T.Button(r, "Delete", self._delete_preset, kind="danger")), "Forget the saved brush shown above").pack(side="right")
        head("STROKE")
        gslider("smooth", "Smooth:", "Steadies your hand: the line follows the mouse a little behind, so wobbles smooth out (0 = off)")
        toggle("Pressure (by speed)", self.use_pressure, "A mouse has no pressure: draw slowly for full strength, faster for lighter / thinner")
        toggle("Mirror X", self.mirror, "Paint is mirrored left / right")
        toggle("Mirror Y", self.mirror_y, "Paint is mirrored top / bottom")
        choice("Radial:", self.radial, ["Off", "3", "4", "5", "6", "8", "12", "16"], "Radial symmetry: your stroke repeats round the middle of the picture")
        head("COLOR")
        choice("Color Mode:", self.color_mode, ["Normal", "Color Jitter", "Rainbow"])
        choice("Blend Mode:", self.blend_mode, ["Brush default"] + [m.title() for m in brushes.BLEND_MODES])
        choice("Stamps:", self.stamp_colors, ["Their own colors", "My color"], "Stamps in their own colours, or in the colour you've picked")
        choice("Textures:", self.texture_colors, ["Their own colors", "My color"], "Wood, brick, stone, water... in their natural colours, or in your colour")
        self.texture_colors.trace_add("write", lambda *a: self._preview())
        self.mirror.trace_add("write", lambda *a: self.refresh()); self.mirror_y.trace_add("write", lambda *a: self.refresh()); self.radial.trace_add("write", lambda *a: self.refresh())
        self.stamp_colors.trace_add("write", lambda *a: self._preview())
        head("VIEW")                                                              # turn / mirror the view only (the picture doesn't change)
        self.turn_row = self._slider_row(O, "Turn:", 0.5, lambda v: self.set_view(rot=(v - 0.5) * 360), "0°")
        self.turn_row.entry.bind("<Return>", lambda e: self._typed(self.turn_row, lambda x: self.set_view(rot=x)))
        self._tip(self.turn_row.slider, "Turn the view to draw at a comfortable angle (keys 4 / 6, or Shift + right-drag; 5 straightens)")
        self.flip_view = tk.BooleanVar(value=False)
        r = tk.Frame(O, bg=O["bg"]); r.pack(fill="x", pady=2); T.on_change(lambda: r.configure(bg=O["bg"])); T.Text(r, "Mirror view (N)", font=T.f(8)).pack(side="left")
        self._tip(T.Toggle(r, self.flip_view, command=lambda: self.set_view(flip=self.flip_view.get())), "See the picture back to front: mistakes in proportion jump out").pack(side="right")
        r = tk.Frame(O, bg=O["bg"]); r.pack(fill="x", pady=(2, 4)); T.on_change(lambda: r.configure(bg=O["bg"]))
        self._tip(small(T.Button(r, "Straighten (5)", lambda: self.set_view(rot=0, flip=False))), "Back to upright, not mirrored").pack(side="right")
        def sync_view():
            d_ = math.degrees(self.view_rot); self._sync_slider(self.turn_row, d_ / 360 + 0.5); self.turn_row.var.set(f"{int(round(d_))}°")
            if self.flip_view.get() != self.view_flip: self.flip_view.set(self.view_flip)
        self._sync_view_ui = sync_view
        self._left_view("Brushes"); self._load_brush_opts(self.brush)

    def _right(self, body):
        if AP.ok(): return self._right_art(body)                                     # the painted panel (brand/icon/panel)
        R = T.Panel(body, pad=8, inner=True); R.pack(side="right", fill="y"); self._fixed_width(R, RIGHT_W)
        self._title(R, "LAYERS").pack()
        r = tk.Frame(R, bg=R["bg"]); r.pack(anchor="w", pady=4)
        for text, cmd, ic, tip in (("+", self.add_layer, None, "New layer"), ("Dup", self.dup_layer, None, "Duplicate layer"), ("Merge", self.merge_down, None, "Merge down"),
                                   ("", lambda: self.move_layer(1), "up", "Move layer up"), ("", lambda: self.move_layer(-1), "down", "Move layer down")):
            self._tip(self._with_icon(slim(T.Button(r, text, cmd)), ic, 13), tip).pack(side="left", padx=1)
        self._tip(slim(T.Button(r, "Del", self.del_layer, kind="danger")), "Delete layer").pack(side="left", padx=1)
        self.layer_box = tk.Frame(R, bg=R["bg"]); self.layer_box.pack(fill="x", pady=4)
        self.mode = tk.StringVar(value="normal"); T.Choice(R, "blend", MODES, self.mode).pack(fill="x", pady=2)
        self.mode.trace_add("write", lambda *a: self._set_layer(mode=self.mode.get()))
        self.lop_row = self._slider_row(R, "Opacity:", 1.0, lambda v: self._set_layer(opacity=v), "100%"); self.lop_s = self.lop_row.slider
        self.lop_row.entry.bind("<Return>", lambda e: self._typed(self.lop_row, lambda x: (self._sync_slider(self.lop_row, x / 100), self._set_layer(opacity=min(1, max(0, x / 100))))))
        self.lop_lbl = types.SimpleNamespace(configure=lambda text: self.lop_row.var.set(text))
        self._text_panel(R)
        # ---- colour: its parts spread evenly down the rest of the panel and centred; the spacing shrinks first when there's less room
        col = tk.Frame(R, bg=R["bg"]); col.pack(fill="both", expand=True, pady=(6, 0)); T.on_change(lambda: col.configure(bg=R["bg"]))
        def part():
            f = tk.Frame(col, bg=R["bg"]); f.pack(expand=True); T.on_change(lambda: f.configure(bg=R["bg"])); return f
        T.Text(part(), "COLOR", font=T.f(10)).pack()
        self.wheel = tk.Canvas(part(), width=self._wsize(), height=self._wsize(), bg=R["bg"], highlightthickness=0, cursor="hand2"); self.wheel.pack()
        T.on_change(lambda: self._draw_wheel(), zoom=True)
        self.wheel.bind("<Button-1>", self._wheel_pick); self.wheel.bind("<B1-Motion>", self._wheel_pick); self._wheel_target = None
        self.wheel.bind("<ButtonRelease-1>", lambda e: (setattr(self, "_wheel_target", None), self._remember()))
        r = part()
        self.swatch = tk.Label(r, width=6, height=2, bg="#c45c2c", relief="flat"); self.swatch.pack(side="left")
        self.hexv = tk.StringVar(value="#C45C2C"); e = T.Entry(r, self.hexv, width=9); e.pack(side="left", padx=6); e.bind("<Return>", lambda ev: self._hex_in())
        slim(T.Button(r, "Pick", lambda: self.set_tool("pick"))).pack(side="left")
        self._swatch_row(part(), BASIC_COLORS, 22)                                       # the basic colours, one click each
        p = part(); T.Text(p, "PALETTES", muted=True, font=T.f(8)).pack()
        for pair in ((PALETTES["Warm"], PALETTES["Cool"]), (PALETTES["Pastel"], PALETTES["Earth"])):
            r = tk.Frame(p, bg=R["bg"]); r.pack(pady=1)
            for pal in pair: self._swatch_row(r, pal, 15, side="left", padx=4)
        h = part(); T.Text(h, "HISTORY", muted=True, font=T.f(8)).pack()
        self.hist_row = tk.Frame(h, bg=R["bg"], height=1); self.hist_row.pack(pady=2)
        self.h, self.s, self.v = colorsys.rgb_to_hsv(*(c / 255 for c in self.color)); self._draw_wheel()

    # ------------------------------------------------------------------ the painted Layers / Color panel
    def _art(self, lb, render, hover=True):
        """a picture widget: render(lb) gives its PhotoImage; redrawn on zoom, a little brighter under the mouse"""
        lb._render = render; lb._hover = False; self._art_items.append(lb); self._art_paint(lb)
        if hover:
            lb.bind("<Enter>", lambda e: (setattr(lb, "_hover", True), self._art_paint(lb)), add="+")
            lb.bind("<Leave>", lambda e: (setattr(lb, "_hover", False), self._art_paint(lb)), add="+")
        return lb
    def _art_paint(self, lb):
        try:
            if lb.winfo_exists(): lb.configure(image=lb._render(lb), bg=lb.master["bg"])
        except tk.TclError: pass
    def _art_redraw(self):
        self._art_items = [lb for lb in self._art_items if lb.winfo_exists()]
        for lb in self._art_items: self._art_paint(lb)
    def _apx(self, v): return max(1, int(round(v * T.Z)))
    def _art_label(self, parent, cursor="hand2"):
        return tk.Label(parent, bd=0, highlightthickness=0, padx=0, pady=0, bg=parent["bg"], cursor=cursor)
    def _panel_button(self, parent, piece, command, tip, size=34):
        lb = self._art_label(parent)
        self._art(lb, lambda b: AP.photo(("btn", piece, self._apx(size), b._hover),
                                         lambda: (AP.shade(AP.fit(piece, self._apx(size), self._apx(size)), 1.18) if b._hover else AP.fit(piece, self._apx(size), self._apx(size)))))
        lb.bind("<Button-1>", lambda e: command()); self._tip(lb, tip); return lb

    def _right_art(self, body):
        """the Layers / Color panel made from the painted pieces: layer buttons, layer rows, blend bar, opacity slider and value box,
        COLOR header, the painted colour ring, colour swatch / hex / Pick, colour swatches, palettes and HISTORY"""
        R = self._edged_panel(body, "right"); self._fixed_width(R, RIGHT_W); self._artp = True; self._R = R
        self._art_items = []; T.on_change(self._art_redraw, zoom=True); self._lay_off = 0; self._show_hist = True
        IW = self._IW = RIGHT_W - 2 * 8 - 4 - 24                                               # design width inside the panel (less the Options scroll bar)
        def frame(parent=None, **pack):
            f = tk.Frame(parent if parent is not None else here[0], bg=R["bg"]); f.pack(**pack); T.on_change(lambda: f.configure(bg=R["bg"])); return f
        # ---- Color / Layers: two views, switched by the buttons at the top (as Brushes / Options on the left)
        sw = tk.Frame(R, bg=R["bg"]); sw.pack(fill="x", pady=(0, 4)); T.on_change(lambda: sw.configure(bg=R["bg"])); self.right_btns = {}
        for name in ("Color", "Options"):
            b = skin.button(small(T.Button(sw, name, lambda n=name: self._right_view(n), width=10)), piece="bar"); b.pack(side="left", expand=True); self.right_btns[name] = b
        self.col_view = tk.Frame(R, bg=R["bg"]); self.lay_view = tk.Frame(R, bg=R["bg"])
        T.on_change(lambda: (self.col_view.configure(bg=R["bg"]), self.lay_view.configure(bg=R["bg"])))
        # Options (layers + text) scrolls: its scroll bar on the right, a border line left of it, the contents in a scrolling canvas
        ov = self.lay_view; g = T.ScrollBox.GAP
        osb = T.Scrollbar(ov, "vertical"); osb.pack(side="right", fill="y", padx=(int(float(R.cget("padx"))) - 1, 0), pady=g); ovl = T.Line(ov, vertical=True); ovl.pack(side="right", fill="y")
        ocv = tk.Canvas(ov, bd=0, highlightthickness=0, bg=R["bg"], width=10); ocv.pack(side="left", fill="both", expand=True, padx=(0, g), pady=(g, 0))   # a gap before the lines
        # Color scrolls the same way (for when it gets more options): scroll bar on the right, a line left of it, a gap before the line
        cvo = self.col_view
        csb = T.Scrollbar(cvo, "vertical"); csb.pack(side="right", fill="y", padx=(int(float(R.cget("padx"))) - 1, 0), pady=g); cvl = T.Line(cvo, vertical=True); cvl.pack(side="right", fill="y")
        ccv = tk.Canvas(cvo, bd=0, highlightthickness=0, bg=R["bg"], width=10); ccv.pack(side="left", fill="both", expand=True, padx=(0, g))
        CVI = self._col_inner = tk.Frame(ccv, bg=R["bg"]); cwin = ccv.create_window(0, 0, window=CVI, anchor="nw")
        csb.command = ccv.yview; ccv.configure(yscrollcommand=csb.set)
        def cfit(e=None):                                                            # as tall as the view (so the parts can spread), taller when they need it
            try:
                h_ = max(ccv.winfo_height(), CVI.winfo_reqheight())
                ccv.itemconfigure(cwin, width=ccv.winfo_width(), height=h_); ccv.configure(scrollregion=(0, 0, ccv.winfo_width(), h_))
            except tk.TclError: pass
        CVI.bind("<Configure>", cfit, add="+"); ccv.bind("<Configure>", cfit, add="+"); self._cfit = cfit
        ccv.bind("<Map>", lambda e: self.after(60, cfit), add="+")            # (its height is set, so growing contents don't tell it: check when shown)
        T.wheel_area(cvo, lambda n: csb.can_scroll() and ccv.yview_scroll(n, "units"))
        T.on_change(lambda: (ccv.configure(bg=R["bg"]), CVI.configure(bg=R["bg"])))
        self._col_canvas = ccv
        # border lines that reach the panel's own border: one across the top (under Color / Options), one down to the bottom
        top_line, side_line = T.Line(R), T.Line(R, vertical=True)
        def oborders(e=None):
            try:
                view = ov if ov.winfo_ismapped() else (self.col_view if self.col_view.winfo_ismapped() else None)
                if view is None: top_line.place_forget(); side_line.place_forget(); return
                e_ = int(float(R.cget("bd"))) + int(float(R.cget("highlightthickness")))      # place() counts from inside the panel's edge and padding
                px_, py_ = e_ + int(float(R.cget("padx"))), e_ + int(float(R.cget("pady"))); t_ = max(1, int(round(T.Z)))
                y = view.winfo_rooty() - R.winfo_rooty() - py_
                top_line.place(x=-px_ + e_, y=y, width=R.winfo_width() - 2 * e_, height=t_); top_line.lift()   # under Color / Options on both views
                x = (ovl if view is ov else cvl).winfo_rootx() - R.winfo_rootx() - px_       # the line beside that view's scroll bar
                side_line.place(x=x, y=y, width=t_, height=R.winfo_height() - (y + py_) - e_)
                top_line.lift(); side_line.lift()
            except tk.TclError: pass
        for w_ in (ov, R): w_.bind("<Configure>", lambda e: ov.after_idle(oborders), add="+")
        for v_ in (ov, self.col_view):
            v_.bind("<Map>", lambda e: ov.after_idle(oborders), add="+"); v_.bind("<Unmap>", lambda e: ov.after_idle(oborders), add="+")
        self.col_view.bind("<Configure>", lambda e: ov.after_idle(oborders), add="+")
        LV = tk.Frame(ocv, bg=R["bg"]); owin = ocv.create_window(0, 0, window=LV, anchor="nw")
        osb.command = ocv.yview; ocv.configure(yscrollcommand=osb.set)
        def ofit(e=None):
            try:
                ocv.itemconfigure(owin, width=ocv.winfo_width()); ocv.configure(scrollregion=(0, 0, ocv.winfo_width(), max(LV.winfo_reqheight(), ocv.winfo_height())))
            except tk.TclError: pass
        LV.bind("<Configure>", ofit, add="+"); ocv.bind("<Configure>", ofit, add="+"); self._ofit = ofit
        ocv.bind("<Map>", lambda e: self.after(60, ofit), add="+")
        T.wheel_area(ov, lambda n: osb.can_scroll() and ocv.yview_scroll(n, "units"))
        T.on_change(lambda: (ocv.configure(bg=R["bg"]), LV.configure(bg=R["bg"])))
        self._opt_canvas = ocv
        here = [LV]
        # ---- layers
        lt = frame(fill="x", pady=(4, 3)); T.Text(lt, "LAYERS", font=T.f(10, "underline")).pack()      # the section's title (like TEXT below it)
        r = frame(fill="x", pady=(0, 3)); bs = (IW - 5 * 4) // 6
        for piece, cmd, tip in (("layer_add", self.add_layer, "New layer"), ("layer_dup", self.dup_layer, "Duplicate layer"),
                                ("layer_merge", self.merge_down, "Merge down"), ("layer_up", lambda: self.move_layer(1), "Move layer up"),
                                ("layer_down", lambda: self.move_layer(-1), "Move layer down"), ("layer_del", self.del_layer, "Delete layer")):
            self._panel_button(r, piece, cmd, tip, bs).pack(side="left", expand=True)
        # the layer list: its own box, half the panel tall, the painted scroll bar on its right (space kept even with one layer)
        lbox = self._lay_frame = tk.Frame(LV, bd=0, highlightthickness=1); lbox.pack(fill="x", pady=(2, 4)); lbox.pack_propagate(False)
        lbox.configure(height=self._apx(220))
        def lbox_style(): lbox.configure(bg=R["bg"], highlightbackground=T.PALETTE["border"], highlightcolor=T.PALETTE["border"])
        lbox_style(); T.on_change(lbox_style)
        self._lay_sb = T.Scrollbar(lbox, command=self._lay_cmd); self._lay_sb.pack(side="right", fill="y", padx=4, pady=4)
        T.Line(lbox, vertical=True).pack(side="right", fill="y")
        self.layer_box = tk.Frame(lbox, bg=R["bg"]); self.layer_box.pack(side="left", fill="both", expand=True, padx=3, pady=3)
        T.on_change(lambda: self.layer_box.configure(bg=R["bg"]))
        T.wheel_area(lbox, lambda n: self._lay_scroll(n))                                     # the wheel anywhere over the list scrolls it
        LV.bind("<Configure>", lambda e: T.defer(self, "layrows", 60, self._fit_layer_rows), add="+")   # the box: half the panel, as many rows as fit
        # ---- blend mode: click for the next one, right-click for the one before
        self.mode = tk.StringVar(value="normal"); bh = 30
        def blend_img(b):
            W, H = self._apx(IW), self._apx(bh); m = self.mode.get().upper(); hv = b._hover
            def make():
                im = AP.bar("bar_blend", W, H, 1.3, 0.6).copy(); im = AP.shade(im, 1.15) if hv else im
                return AP.text(im, f"BLEND: {m}", int(W * 0.55), H // 2, int(H * 0.36))
            return AP.photo(("blend", W, H, m, hv), make)
        self.blend_lbl = self._art(self._art_label(LV), blend_img); self.blend_lbl.pack(pady=(4, 2))
        def step(d): self.mode.set(MODES[(MODES.index(self.mode.get()) + d) % len(MODES)] if self.mode.get() in MODES else MODES[0])
        self.blend_lbl.bind("<Button-1>", lambda e: step(1)); self.blend_lbl.bind("<Button-3>", lambda e: step(-1))
        self._tip(self.blend_lbl, "Blend mode: click for the next, right-click for the one before")
        self.mode.trace_add("write", lambda *a: (self._art_paint(self.blend_lbl), self._set_layer(mode=self.mode.get())))
        # ---- layer opacity: slider + value box
        r = frame(fill="x", pady=(1, 3)); T.Text(r, "Opacity:", font=T.f(9)).pack(side="left")
        var = tk.StringVar(value="100%"); box = AP.ValueBox(r, var, 58, 26, chars=5); box.pack(side="right")
        sl = AP.ArtSlider(r, 1.0, lambda v: (self._set_layer(opacity=v), var.set(f"{int(v * 100)}%")), width=IW - 58 - 82, height=24); sl.pack(side="right", padx=4)
        self.lop_row = types.SimpleNamespace(slider=sl, var=var, entry=box.entry); self.lop_s = sl
        box.entry.bind("<Return>", lambda e: self._typed(self.lop_row, lambda x: (self._sync_slider(self.lop_row, x / 100), self._set_layer(opacity=min(1, max(0, x / 100))))))
        self.lop_lbl = types.SimpleNamespace(configure=lambda text: var.set(text))
        self.clip_var = tk.BooleanVar(value=False)
        ck = frame(fill="x", pady=(0, 3)); T.Text(ck, "Clip to layer below", font=T.f(9)).pack(side="left")
        self._tip(T.Toggle(ck, self.clip_var, command=self._set_clip), "This layer only shows where the layer under it has paint (shade or texture inside a shape)").pack(side="right")
        gb = frame(fill="x", pady=(0, 3))
        self._tip(small(T.Button(gb, "Group", self.group_layers)), "Put this layer and the one under it in a group (click a group's row to pick the whole group)").pack(side="left")
        self._tip(small(T.Button(gb, "Ungroup", self.ungroup)), "Take the layers out of their group").pack(side="right")
        self.mask_var = tk.BooleanVar(value=False)
        mk = frame(fill="x", pady=(0, 3)); T.Text(mk, "Paint on mask", font=T.f(9)).pack(side="left")
        self._tip(T.Toggle(mk, self.mask_var, command=self._mask_toggle), "Layer mask: painting now hides this layer (the eraser brings it back); nothing is lost. Turn off to paint the layer again").pack(side="right")
        mb = frame(fill="x", pady=(0, 3))
        self._tip(small(T.Button(mb, "Apply mask", self._mask_apply)), "Make what the mask hides really gone, and remove the mask").pack(side="left")
        self._tip(small(T.Button(mb, "Delete mask", self._mask_delete, kind="danger")), "Remove the mask: the whole layer shows again").pack(side="right")
        lk = frame(fill="x", pady=(0, 3)); T.Text(lk, "Lock transparency", font=T.f(9)).pack(side="left")
        self._tip(T.Toggle(lk, self.lock_alpha), "Paint only where this layer already has paint (great for shading inside a shape)").pack(side="right")
        self._text_panel(LV)                                                         # TEXT: words, font, size, style (the Text tool)
        self._navigator(LV, frame, self._apx(IW) - 4)                                 # NAVIGATOR, LAYER COLOR (studio_more)
        self._layer_color(LV, frame)
        self._more_options(LV, frame)                                                # GUIDES, FILL, CANVAS, SAVING (studio_more)
        self._timelapse(LV, frame)
        # ---- COLOR header
        def header(word, H, arrow=None):
            def render(b):
                W, h = self._apx(IW), self._apx(H); ar = arrow() if arrow else ""; hv = b._hover and bool(arrow)
                def make():
                    im = Image.new("RGBA", (W, h)); bh_ = AP.bar("bar_header", W - h // 2, int(h * 0.82), 0.4)
                    im.alpha_composite(AP.shade(bh_, 1.15) if hv else bh_, (h // 2, (h - int(h * 0.82)) // 2))
                    im.alpha_composite(AP.fit("palette_icon", h, h), (0, 0)); AP.text(im, word, int(h * 1.25), h // 2, int(h * 0.42), anchor="lm")
                    if ar:                                                        # a - (open) or + (closed) drawn in the border-line colour
                        from PIL import ImageDraw
                        d = ImageDraw.Draw(im); col = T.PALETTE["border"]; cx, cy = W - int(h * 0.62), h // 2
                        r_ = max(3, int(h * 0.22)); t_ = max(2, int(round(h * 0.09)))
                        d.rectangle((cx - r_, cy - t_ // 2, cx + r_, cy - t_ // 2 + t_ - 1), fill=col)
                        if ar == "+": d.rectangle((cx - t_ // 2, cy - r_, cx - t_ // 2 + t_ - 1, cy + r_), fill=col)
                    return im
                return AP.photo(("hdr", word, W, h, ar, hv, T.PALETTE["border"]), make)
            return render
        here[0] = CV = self._col_inner
        top_row = frame(fill="x")                                                    # current colour / hex / Pick (filled below)
        # ---- the colour ring: as big as the room left allows
        wf = frame(); self._wS = self._apx(150); wf.configure(width=self._wS, height=self._wS)
        self.wheel = tk.Canvas(wf, width=self._wS, height=self._wS, bg=R["bg"], highlightthickness=0, cursor="hand2"); self.wheel.place(relx=0.5, rely=0.5, anchor="center")
        T.on_change(lambda: self.wheel.configure(bg=R["bg"]))
        def fit_wheel():
            others = sum(g.winfo_reqheight() for g in self._col_groups if g is not wf and g is not getattr(self, "_col_extra", None)); gaps = self._apx(10) * len(self._col_groups)
            view = self._col_canvas.winfo_height() if getattr(self, "_col_canvas", None) is not None else CV.winfo_height()
            room = view - others - gaps; need = self._apx(118)                       # (the sliders sit below: scroll down to them)
            if self._pal_auto:                                                    # palettes give way to the ring when the panel is short
                pal_h = self._apx(46)
                if self._pal_open and room < need: return self._set_palettes(False)
                if not self._pal_open and room - pal_h >= need: return self._set_palettes(True)
            S = max(60, min(room, self._apx(IW)) - 2)
            if S != self._wS: self._wS = S; self.wheel.configure(width=S, height=S); wf.configure(width=S, height=S); self._draw_wheel()
        CV.bind("<Configure>", lambda e: T.defer(self, "wheel", 30, fit_wheel), add="+"); self._fit_wheel = fit_wheel
        self._col_canvas.bind("<Configure>", lambda e: T.defer(self, "wheel", 30, fit_wheel), add="+")      # the view's own height sets the ring's size
        self.wheel.bind("<Button-1>", self._wheel_pick); self.wheel.bind("<B1-Motion>", self._wheel_pick); self._wheel_target = None
        self.wheel.bind("<ButtonRelease-1>", lambda e: (setattr(self, "_wheel_target", None), self._remember()))
        # ---- current colour, hex, Pick
        r = top_row; sw_w, hx_w = 62, 86; pk_w = IW - sw_w - hx_w - 8
        def cur_img(b):                                                          # your colour, with the second colour as a small square in the corner
            W, H = self._apx(sw_w), self._apx(32)
            def make():
                im = AP.swatch(self.color, W, H).copy(); sw2 = AP.swatch(self.color2, max(6, int(W * 0.34)), max(6, int(H * 0.5)))
                im.alpha_composite(sw2.convert("RGBA"), (W - sw2.width - max(1, W // 30), H - sw2.height - max(1, H // 14))); return im
            return AP.photo(("cur", self.color, self.color2, W, H), make)
        self.swatch = self._art(self._art_label(r, cursor="hand2"), cur_img, hover=False); self.swatch.pack(side="left")
        self.swatch.bind("<Button-1>", lambda e: self.swap_colors())
        self._tip(self.swatch, "Your colour (the small square is your second colour). Click or press X to swap them, D for black / white")
        self.hexv = tk.StringVar(value="#C45C2C"); hb = AP.ValueBox(r, self.hexv, hx_w, 30, chars=8); hb.pack(side="left", padx=4)
        hb.entry.bind("<Return>", lambda ev: self._hex_in())
        def pick_img(b):
            W, H = self._apx(pk_w), self._apx(32); hv = b._hover
            def make():
                im = AP.bar("bar_button", W, H, 0.4).copy(); im = AP.shade(im, 1.15) if hv else im
                im.alpha_composite(AP.fit("dropper", int(H * 0.72), int(H * 0.72)), (int(H * 0.3), int(H * 0.14)))
                return AP.text(im, "Pick", int(W * 0.62), H // 2, int(H * 0.4))
            return AP.photo(("pick", W, H, hv), make)
        pk = self._art(self._art_label(r), pick_img); pk.pack(side="left"); pk.bind("<Button-1>", lambda e: self.set_tool("pick")); self._tip(pk, "Pick a colour from the picture, then back to your tool (I)")
        # ---- swatches: basic colours, then the palettes
        cw = (IW - 7 * 3) // 8
        def swatches(parent, colors, h):
            row = frame(parent, pady=1)
            for c in colors:
                lb = self._art(self._art_label(row), lambda b, c=c, h=h: AP.photo(("swb", c, self._apx(cw), self._apx(h), b._hover),
                               lambda: AP.shade(AP.swatch(c, self._apx(cw), self._apx(h)), 1.15) if b._hover else AP.swatch(c, self._apx(cw), self._apx(h))))
                lb.pack(side="left", padx=1); lb.bind("<Button-1>", lambda e, c=c: (self.set_color(c), self._remember()))
            return row
        basic = swatches(CV, BASIC_COLORS, 24)
        # palettes: the header opens / closes them. On their own they close when the panel is short (so the colour ring keeps its
        # room) and open again when there's space (big mode); clicking the header decides from then on
        self._pal_open, self._pal_auto = True, True
        pal_group = frame(fill="x")                                                   # the palettes header and its colours, one group
        ph_ = self._art(self._art_label(pal_group), header("PALETTES", 24, arrow=lambda: "-" if self._pal_open else "+")); ph_.pack(pady=(0, 1))
        self._pal_box = frame(pal_group, fill="x"); self._pal_hdr = ph_
        for pair in (("Warm", "Cool"), ("Pastel", "Earth")): swatches(self._pal_box, PALETTES[pair[0]] + PALETTES[pair[1]], 20)
        ph_.bind("<Button-1>", lambda e: (setattr(self, "_pal_auto", False), self._set_palettes(not self._pal_open)))
        self._tip(ph_, "Show / hide the palettes")
        # ---- history: the recent colours, shown / hidden with the HISTORY button
        hist_group = frame(fill="x")                                                  # the HISTORY button and the recent colours, one group
        self.hist_row = frame(hist_group, fill="x", pady=(2, 0))
        def hist_img(b):
            W, H = self._apx(IW), self._apx(34); hv = b._hover
            def make():                                                        # the blank bar stretched to size, the icon, the word
                im = AP.bar("bar_blank", W, H, 0.3).copy(); im = AP.shade(im, 1.15) if hv else im
                ic = int(H * 0.78); px = int(H * 0.56); gap = int(H * 0.22)               # icon right beside the word, the pair centred
                from PIL import ImageDraw as _D
                tw = _D.Draw(im).textlength("HISTORY", font=skin._pil_font(px)); x0 = int((W - (ic + gap + tw)) / 2)
                im.alpha_composite(AP.fit("history_icon", ic, ic), (x0, (H - ic) // 2))
                return AP.text(im, "HISTORY", x0 + ic + gap, H // 2, px, anchor="lm")
            return AP.photo(("hist2", W, H, hv), make)
        hb2 = self._art(self._art_label(hist_group), hist_img); hb2.bind("<Button-1>", lambda e: self._toggle_hist())
        self.hist_row.pack_forget(); hb2.pack(side="top"); self.hist_row.pack(side="top", fill="x", pady=(4, 0))   # the HISTORY button, its colours under it
        self._tip(hb2, "Show / hide the colours you used last")
        self.after_idle(lambda: self._remember(add=False))                          # the 8 white history slots show from the start
        # ---- colour sliders (scroll down to them): hue / saturation / value and red / green / blue, typed values, a random colour
        sl_group = frame(fill="x"); self._csl = {}; self._csl_busy = None
        hd_ = frame(sl_group, fill="x", pady=(0, 2)); T.Text(hd_, "COLOR SLIDERS", muted=True, font=T.f(8)).pack()
        for key, lab, top in (("h", "Hue:", 360), ("s", "Saturation:", 100), ("v", "Value:", 100), ("r", "Red:", 255), ("g", "Green:", 255), ("b", "Blue:", 255)):
            row = self._slider_row(sl_group, lab, 0.5, lambda v, k=key: self._csl_set(k, v), ""); row.top = top
            row.entry.bind("<Return>", lambda e, k=key, row=row: self._typed(row, lambda x, k=k, row=row: self._csl_set(k, x / row.top)))
            self._csl[key] = row
        rr_ = frame(sl_group, fill="x", pady=(3, 0))
        self._tip(small(T.Button(rr_, "Random", self._random_color)), "A random colour (nice and bright)").pack(side="right")
        self._tip(small(T.Button(rr_, "Opposite", lambda: (self.set_color(tuple(int(x * 255) for x in colorsys.hsv_to_rgb((self.h + 0.5) % 1, self.s, self.v))), self._remember()))),
                  "The colour opposite this one on the wheel (its complement)").pack(side="right", padx=4)
        self._sync_csl()
        # ---- MY COLORS: colours you keep (+ adds yours, right-click one to drop it) and the picture's own main colours
        hd_ = frame(sl_group, fill="x", pady=(10, 2)); T.Text(hd_, "MY COLORS", muted=True, font=T.f(8)).pack()
        self._my_lbls = []
        for row_i in range(2):
            row = frame(sl_group, pady=1)
            for k in range(8):
                i = row_i * 8 + k; lb = tk.Label(row, bd=0, highlightthickness=0, bg=R["bg"], cursor="hand2"); lb.pack(side="left", padx=1)
                lb.bind("<Button-1>", lambda e, i=i: (self.set_color(self.my_colors[i]), self._remember()) if i < len(self.my_colors) else self.add_my_color())
                lb.bind("<Button-3>", lambda e, i=i: self.drop_my_color(i)); self._my_lbls.append(lb)
        rr2 = frame(sl_group, fill="x", pady=(3, 0))
        self._tip(small(T.Button(rr2, "+ Keep color", self.add_my_color)), "Keep the current colour in My Colors (right-click a kept colour to drop it)").pack(side="left")
        self._tip(small(T.Button(rr2, "From picture", self.picture_colors)), "The 8 main colours in your picture, in the row below").pack(side="right")
        row = frame(sl_group, pady=(3, 1)); self._pic_lbls = []
        for k in range(8):
            lb = tk.Label(row, bd=0, highlightthickness=0, bg=R["bg"], cursor="hand2"); lb.pack(side="left", padx=1); self._pic_lbls.append(lb)
            lb.bind("<Button-1>", lambda e, k=k: (self.set_color(self.pic_colors[k]), self._remember()) if k < len(self.pic_colors) else None)
        self._my_cw = cw; self._paint_my_colors()
        self.h, self.s, self.v = colorsys.rgb_to_hsv(*(c / 255 for c in self.color)); self._draw_wheel()
        self._col_groups = [top_row, wf, basic, pal_group, hist_group, sl_group]; self._col_extra = sl_group
        for g in self._col_groups: g.pack_forget()
        # spaced out a little (up to a set gap, less on a short panel), the whole block kept toward the top: a tall panel
        # (full screen, studio expanded) adds room below the block, not big holes between its parts
        sp_top = tk.Frame(CV, height=0, bg=R["bg"]); sp_bot = tk.Frame(CV, height=0, bg=R["bg"])
        T.on_change(lambda: (sp_top.configure(bg=R["bg"]), sp_bot.configure(bg=R["bg"])))
        sp_top.pack(fill="x"); sp_top.pack_propagate(False)                            # kept toward the top: the spare room goes below
        for g in self._col_groups: g.pack()
        sp_bot.pack(fill="both", expand=True)
        def col_gaps():
            try:
                pills = getattr(self, "_pills", None)                                  # top row level with the first title bar in the brush list (BRUSHES)
                if pills and self._sc.winfo_ismapped() and CV.winfo_ismapped():
                    p0 = pills[0]
                    ptop = p0.winfo_rooty() - self._sc.winfo_rooty() + int(self._sc.canvasy(0)) + self._sc.winfo_rooty()
                    ctop = CV.winfo_rooty() + int(self._col_canvas.canvasy(0))
                    want = max(0, ptop - ctop)
                    if abs(int(sp_top.cget("height")) - want) > 1: sp_top.configure(height=want)
                free = CV.winfo_height() - sum(g.winfo_reqheight() for g in self._col_groups) - int(sp_top.cget("height"))
                gap = max(2, min(self._apx(16), free // (len(self._col_groups) + 1)))
                for i, g in enumerate(self._col_groups): g.pack_configure(pady=(0 if i == 0 else gap, 0))
            except tk.TclError: pass
        CV.bind("<Configure>", lambda e: T.defer(self, "colgaps", 40, col_gaps), add="+")
        self._sc.bind("<Configure>", lambda e: T.defer(self, "colgaps", 60, col_gaps), add="+"); self.col_view.bind("<Map>", lambda e: T.defer(self, "colgaps", 60, col_gaps), add="+")
        self._right_view({"Layers": "Options"}.get(prefs.get("draw_right_view"), prefs.get("draw_right_view")) if prefs.get("draw_right_view") in ("Color", "Layers", "Options") else "Color")

    @staticmethod
    def _title(parent, text):
        """a panel's main title: gold and underlined, like every page's title (a little smaller to fit the side panels)"""
        t = T.Title(parent, text); t.configure(font=T.f(12, "underline")); return t

    def _edged_panel(self, body, side):
        """a side panel whose inner edge (the one facing the canvas) is the painted strip with the arrow: no green line and no gap
        there; the green border stays on the other three sides. Without the strip picture it's the plain framed panel"""
        if AP.src("side_bar") is None:
            P = T.Panel(body, pad=8, inner=True); P.pack(side=side, fill="y"); return P
        O = tk.Frame(body, bg=T.PALETTE["border"]); O.pack(side=side, fill="y"); T.on_change(lambda: O.configure(bg=T.PALETTE["border"]))
        P = T.Panel(O, pad=8, inner=True); P.configure(highlightthickness=0)
        P._edge = dict(side=side, fill="y", pady=1, padx=(1, 0) if side == "left" else (0, 1)); P.pack(**P._edge)
        P._strip = self._side_strip(O, P, side); return P

    def _side_strip(self, O, panel, side):
        """the painted bar on the panel's canvas side; its arrow slides the panel away (more room for the canvas) and back"""
        SW = 14; cv = tk.Canvas(O, width=self._apx(SW), highlightthickness=0, bd=0, cursor="hand2", bg=O["bg"])
        cv.pack(side=side, fill="y"); cv._hover = False
        def draw():
            W, H = self._apx(SW), cv.winfo_height()
            if H < 20: return
            shown = bool(panel.winfo_manager()); hv = cv._hover
            ar = ("arrow_left" if shown else "arrow_right") if side == "left" else ("arrow_right" if shown else "arrow_left")
            def make():
                im = AP.vbar("side_bar", W, H, 0.7).copy(); a = AP.src(ar); ah = round(a.height * W / a.width)
                im.alpha_composite(a.resize((W, ah), Image.LANCZOS), (0, (H - ah) // 2)); return AP.shade(im, 1.15) if hv else im
            try:
                cv.configure(width=W, bg=cv.master["bg"]); cv.delete("all")
                cv._ph = AP.photo(("strip", W, H, ar, hv), make); cv.create_image(0, 0, image=cv._ph, anchor="nw")
            except tk.TclError: pass
        cv._draw = draw
        cv.bind("<Configure>", lambda e: T.defer(cv, "strip", 20, draw), add="+"); T.on_change(draw, zoom=True)
        cv.bind("<Enter>", lambda e: (setattr(cv, "_hover", True), draw())); cv.bind("<Leave>", lambda e: (setattr(cv, "_hover", False), draw()))
        cv.bind("<Button-1>", lambda e: self.toggle_panel(panel))
        self._tip(cv, "Hide / show the " + ("brushes" if side == "left" else "Layers and Color") + " panel"); return cv

    def toggle_panel(self, panel):
        """slide a side panel away (the canvas gets its room) or bring it back"""
        with T.frozen(self.winfo_toplevel()):
            if panel.winfo_manager(): panel.pack_forget()
            else: panel.pack(before=panel._strip, **panel._edge)
            panel._strip._draw()

    def toggle_side(self): self.toggle_panel(self._R)

    def _set_palettes(self, on):
        self._pal_open = on
        if on and not self._pal_box.winfo_manager(): self._pal_box.pack(fill="x", after=self._pal_hdr)
        if not on and self._pal_box.winfo_manager(): self._pal_box.pack_forget()
        self._art_paint(self._pal_hdr)

    def _toggle_hist(self):
        self._show_hist = not self._show_hist; self._remember(add=False)

    def _rows(self): return getattr(self, "_lay_rows", 4)                          # layer rows shown (as many as fit, see _fit_layer_rows)
    def _lay_scroll(self, d):
        self._lay_off = max(0, min(max(0, len(self._row_items()) + 1 - self._rows()), self._lay_off + d))   # (+1: the Background row)
        self._lay_free = True
        try: self._layers_ui()                                                     # scrolling moves freely (the chosen layer may scroll out of view)
        finally: self._lay_free = False

    def _layers_ui_art(self):
        """layer rows: green-framed = the layer you're painting on (or the group you picked); the ball shows / hides it; a group's row
        sits above its layers (its arrow folds them away); as many rows as fit (the wheel scrolls more)"""
        for w in self.layer_box.winfo_children(): w.destroy()
        items = self._row_items(); n = len(items)
        want = ("g", self.sel_group) if self.sel_group is not None else ("l", self.li)
        if want not in items:                                                     # its group is folded: the group's row stands for it
            g = self._group_of(self.cur); want = ("g", g) if g is not None else want
        pos = items.index(want) if want in items else 0
        k = self._rows(); total = n + 1                                                # every row, then the Background row
        if not getattr(self, "_lay_free", False):                                   # a layer was chosen / added: bring it into view
            if pos < self._lay_off: self._lay_off = pos
            if pos >= self._lay_off + k: self._lay_off = pos - k + 1
        self._lay_off = max(0, min(self._lay_off, max(0, total - k)))
        if getattr(self, "_lay_sb", None) is not None: self._lay_sb.set(self._lay_off / total, min(1.0, (self._lay_off + k) / total))
        IW, RH = self._IW - 34, 26                                                    # (room for the list's scroll bar)
        for kind, v in items[self._lay_off:self._lay_off + k]:
            if kind == "g":
                G = self.groups[v]; info = ("g", G.name, G.visible, int(G.opacity * 100), G.mode, self.sel_group == v, G.collapsed)
                def render(b, info=info):
                    W, H = self._apx(IW), self._apx(RH); _, name, vis, op, mode, sel, folded = info
                    def make():
                        from PIL import ImageDraw as _D
                        im = AP.bar("bar_navy_green" if sel else "bar_dark", W, H, 0.4).copy(); d = int(H * 0.6)
                        im.alpha_composite(AP.fit("ball_white" if vis else "ball_grey", d, d), (int(H * 0.32), (H - d) // 2))
                        x0, cy, r = int(H * 1.25), H / 2, H * 0.2                        # the fold arrow: pointing right when folded, down when open
                        pts = [(x0, cy - r), (x0 + r * 1.6, cy), (x0, cy + r)] if folded else [(x0, cy - r * 0.7), (x0 + r * 2, cy - r * 0.7), (x0 + r, cy + r * 0.9)]
                        _D.Draw(im).polygon(pts, fill=(245, 196, 0))
                        AP.text(im, name[:11], int(H * 2.1), H // 2, int(H * 0.44), anchor="lm", fill=(245, 196, 0))
                        return AP.text(im, f"{op}% {mode}", W - int(H * 0.4), H // 2, int(H * 0.36), fill=(70, 220, 255), anchor="rm")
                    return AP.photo(("grow", W, H) + info, make)
                lb = self._art(self._art_label(self.layer_box), render, hover=False); lb.pack(pady=1)
                lb.bind("<Button-1>", lambda e, g=v: self.toggle_group(g, "visible") if e.x < self._apx(RH) * 1.1 else
                        (self.toggle_group(g, "fold") if e.x < self._apx(RH) * 2.0 else self.select_group(g)))
            else:
                i = v; L = self.layers[i]; ing = self._group_of(L) is not None
                info = (L.name, L.visible, int(L.opacity * 100), L.mode, i == self.li and self.sel_group is None, ing, L.maskcv is not None)
                def render(b, info=info):
                    W, H = self._apx(IW), self._apx(RH); name, vis, op, mode, sel, ing, has_mask = info
                    def make():
                        im = AP.bar("bar_navy_green" if sel else "bar_navy", W, H, 0.4).copy(); d = int(H * 0.6); ind = int(H * 0.55) if ing else 0
                        if ing: im.paste((245, 196, 0, 255), (int(H * 0.12), int(H * 0.2), int(H * 0.12) + max(2, H // 10), int(H * 0.8)))   # in a group: a gold mark, set in
                        im.alpha_composite(AP.fit("ball_white" if vis else "ball_grey", d, d), (int(H * 0.32) + ind, (H - d) // 2))
                        AP.text(im, (name[:10] if ing else name[:12]), int(H * 1.2) + ind, H // 2, int(H * 0.44), anchor="lm")
                        return AP.text(im, f"{'M ' if has_mask else ''}{op}% {mode}", W - int(H * 0.4), H // 2, int(H * 0.36), fill=(70, 220, 255), anchor="rm")
                    return AP.photo(("row", W, H) + info, make)
                lb = self._art(self._art_label(self.layer_box), render, hover=False); lb.pack(pady=1)
                off = 0.55 if ing else 0
                lb.bind("<Button-1>", lambda e, i=i, off=off: self._toggle_vis(i) if e.x < self._apx(RH) * (1.1 + off) else self._select(i))
            lb.bind("<MouseWheel>", lambda e: self._lay_scroll(-1 if e.delta > 0 else 1), add="+")
        def bg_row(b):
            W, H = self._apx(IW), self._apx(RH)
            return AP.photo(("bgrow", W, H), lambda: AP.text(AP.bar("bar_dark", W, H, 0.4).copy(), "Background", int(H * 0.5), H // 2, int(H * 0.44), anchor="lm"))
        if self._lay_off + k > n: self._art(self._art_label(self.layer_box, cursor=""), bg_row, hover=False).pack(pady=1)   # scrolled to the bottom
        L = self.cur; self._in_layers_ui = True
        src = self.groups[self.sel_group] if getattr(self, "sel_group", None) is not None and self.sel_group in self.groups else L
        try:
            self.mode.set(src.mode)
            if hasattr(self, "clip_var") and self.clip_var.get() != getattr(L, "clip", False): self.clip_var.set(getattr(L, "clip", False))
            if hasattr(self, "mask_var") and self.mask_var.get() != L.mask_edit: self.mask_var.set(L.mask_edit)
        finally: self._in_layers_ui = False
        self.lop_s.value = src.opacity; self.lop_s._draw(); self.lop_lbl.configure(text=f"{int(src.opacity * 100)}%")

    def _draw_wheel_art(self):
        S = self._wS; c = S / 2; self.wheel.delete("all")
        self._wph = AP.photo(("wheel", S, round(self.h, 3)), lambda: AP.wheel(S, self.h)); self.wheel.create_image(0, 0, image=self._wph, anchor="nw")
        _, rin, _ = AP.ring_info(); rm = c * (1 + rin) / 2; a = math.radians(AP.deg_for(self.h)); m = max(4, S * 0.04)
        for x, y in ((c + rm * math.cos(a), c + rm * math.sin(a)),
                     (c - AP.square_half(S) + self.s * 2 * AP.square_half(S), c - AP.square_half(S) + (1 - self.v) * 2 * AP.square_half(S))):
            self.wheel.create_oval(x - m, y - m, x + m, y + m, outline="#050a1c", width=4); self.wheel.create_oval(x - m, y - m, x + m, y + m, outline="white", width=2)

    def _wheel_pick_art(self, e):
        S = self._wS; c = S / 2; half = AP.square_half(S); r = math.hypot(e.x - c, e.y - c)
        if self._wheel_target is None: self._wheel_target = "square" if (abs(e.x - c) <= half * 1.1 and abs(e.y - c) <= half * 1.1) else ("ring" if r > c * AP.ring_info()[1] * 0.8 else None)
        if self._wheel_target is None: return
        if self._wheel_target == "ring": self.h = AP.hue_at(math.degrees(math.atan2(e.y - c, e.x - c)) % 360)       # the colour painted under the pointer
        else: self.s = min(1, max(0, (e.x - (c - half)) / (2 * half))); self.v = min(1, max(0, 1 - (e.y - (c - half)) / (2 * half)))
        rgb = tuple(int(x * 255) for x in colorsys.hsv_to_rgb(self.h, self.s, self.v)); h, s, v = self.h, self.s, self.v
        self._quiet_wheel = True
        try: self.set_color(rgb)
        finally: self._quiet_wheel = False
        self.h, self.s, self.v = h, s, v; self._draw_wheel()

    # ------------------------------------------------------------------ document
    @property
    def cur(self): return self.layers[self.li]

    def new(self, w=1600, h=1100, background=None):
        self.size_wh = (w, h); self.bg = np.full((h, w, 3), 255.0, np.float32) if background is None else np.asarray(background.convert("RGB").resize((w, h)), dtype=np.float32)
        self.layers = [Layer(w, h, "Layer 1")]; self.li = 0; self.undo_stack, self.redo_stack = [], []; self.zoom = None; self.pan = [0, 0]
        self.groups = {}; self.sel_group = None
        self._comp = np.empty((h, w, 3), np.uint8); self._recomp(); self.changed = False
        self._layers_ui(); self.refresh()
        if hasattr(self, "size_s"): self.set_size(self.size)                         # the size slider's range follows the canvas size
        self._sync_canvas_size()

    def load_image(self, im):
        im = im.convert("RGB"); s = min(1.0, 2400 / max(im.size)); im = im.resize((int(im.width * s), int(im.height * s)))
        self.new(im.width, im.height, background=im)

    def open(self):
        p = filedialog.askopenfilename(parent=self, initialdir=prefs.save_folder(), filetypes=[("Images and layered drawings", "*.png *.jpg *.jpeg *.webp *.bmp *.avif *.gif *.tif *.tiff *.ora"),
                                                                                         ("Layered drawing (OpenRaster)", "*.ora"), ("All files", "*.*")])
        if not p: return
        try: self.open_ora(p) if p.lower().endswith(".ora") else self.load_image(Image.open(p))
        except Exception as ex: T.banner(self.app, f"COULDN'T OPEN IT — {ex}")


    def _recomp(self, rect=None):
        """update the finished picture (all visible layers over the background) in rect = (x0, y0, x1, y1), or everywhere.
        The screen, eyedropper, fill and save all read this, so nothing re-blends the whole picture on every mouse move."""
        w, h = self.size_wh
        x0, y0, x1, y1 = (0, 0, w, h) if rect is None else (max(0, int(rect[0])), max(0, int(rect[1])), min(w, int(math.ceil(rect[2]))), min(h, int(math.ceil(rect[3]))))
        if x1 <= x0 or y1 <= y0: return
        sl = (slice(y0, y1), slice(x0, x1)); part = self.bg[sl].copy()
        part = self._composite(part, sl)                                         # layers and groups (studio_groups)
        self._comp[sl] = np.clip(part, 0, 255).astype(np.uint8)

    def flatten(self):
        return Image.fromarray(self._comp.copy())

    def save(self):
        p = filedialog.asksaveasfilename(parent=self, initialdir=prefs.save_folder(), initialfile=prefs.next_name(), defaultextension=prefs.ext(),
                                         filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("WebP", "*.webp"), ("Layered drawing - keeps every layer (opens in Krita / GIMP)", "*.ora")])
        if not p: return
        if p.lower().endswith(".ora"): self.save_ora(p)
        elif self.save_clear.get() and p.lower().endswith((".png", ".webp")): self.flatten_clear().save(p)      # Options > Saving: see-through background
        else: prefs.save_image(self.flatten(), p)
        T.banner(self.app, f"SAVED — {os.path.basename(p)}", "success")

    ORA_OPS = {"normal": "svg:src-over", "multiply": "svg:multiply", "screen": "svg:screen", "overlay": "svg:overlay", "soft light": "svg:soft-light",
               "hard light": "svg:hard-light", "darken": "svg:darken", "lighten": "svg:lighten", "color dodge": "svg:color-dodge",
               "color burn": "svg:color-burn", "add": "svg:plus", "difference": "svg:difference", "subtract": "krita:subtract"}

    def save_ora(self, path):
        """every layer kept (name, visible, opacity, blend mode, clipping), the background as the bottom layer, plus the flat picture"""
        import zipfile, io
        from xml.sax.saxutils import quoteattr
        w, h = self.size_wh; png = lambda im: (lambda b: (im.save(b, "PNG", compress_level=3), b.getvalue())[1])(io.BytesIO())
        rows = []; files = []; open_g = None
        for i, L in reversed(list(enumerate(self.layers))):                       # stack.xml lists the top layer first
            g = self._group_of(L)
            if g != open_g:                                                       # a group: its layers inside a stack of their own
                if open_g is not None: rows.append("</stack>")
                if g is not None:
                    G = self.groups[g]
                    rows.append(f'<stack name={quoteattr(G.name)} opacity="{G.opacity:.3f}" visibility="{"visible" if G.visible else "hidden"}" '
                                f'composite-op="{self.ORA_OPS.get(G.mode, "svg:src-over")}" isolation="isolate" x-instant-mode={quoteattr(G.mode)} x-instant-folded="{1 if G.collapsed else 0}">')
                open_g = g
            px = Image.fromarray(np.rint(np.dstack([np.clip(L.img.a, 0, 255), np.clip(L.shown(), 0, 1)[..., None] * 255])).astype(np.uint8), "RGBA")   # (a mask is applied)
            src = f"data/layer{i}.png"; files.append((src, png(px)))
            rows.append(f'<layer name={quoteattr(L.name)} src="{src}" x="0" y="0" opacity="{L.opacity:.3f}" visibility="{"visible" if L.visible else "hidden"}" '
                        f'composite-op="{self.ORA_OPS.get(L.mode, "svg:src-over")}" x-instant-mode={quoteattr(L.mode)} x-instant-clip="{1 if getattr(L, "clip", False) else 0}"/>')
        if open_g is not None: rows.append("</stack>")
        files.append(("data/background.png", png(Image.fromarray(np.clip(self.bg, 0, 255).astype(np.uint8)))))
        rows.append('<layer name="Background" src="data/background.png" x="0" y="0" opacity="1.000" visibility="visible" composite-op="svg:src-over" x-instant-background="1"/>')
        xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<image version="0.0.3" w="{w}" h="{h}"><stack>{"".join(rows)}</stack></image>'
        flat = self.flatten(); th = flat.copy(); th.thumbnail((256, 256))
        tmp = path + ".tmp"
        with zipfile.ZipFile(tmp, "w") as z:
            z.writestr(zipfile.ZipInfo("mimetype"), "image/openraster", compress_type=zipfile.ZIP_STORED)   # first and uncompressed, as the format asks
            z.writestr("stack.xml", xml, compress_type=zipfile.ZIP_DEFLATED)
            for name, data in files: z.writestr(name, data, compress_type=zipfile.ZIP_STORED)
            z.writestr("mergedimage.png", png(flat)); z.writestr("Thumbnails/thumbnail.png", png(th))
        os.replace(tmp, path); self.changed = False

    def open_ora(self, path):
        import zipfile, io, xml.etree.ElementTree as ET
        with zipfile.ZipFile(path) as z:
            root = ET.fromstring(z.read("stack.xml")); w, h = int(root.get("w")), int(root.get("h"))
            items = []; gstacks = {}                                                 # bottom layer first; layers inside a <stack> are a group
            def walk(st, parent_stack=None):
                for el in st:
                    if el.tag == "layer": items.append((el, parent_stack))
                    elif el.tag == "stack": walk(el, el)
            top = root.find("stack"); walk(top if top is not None else root)
            items = items[::-1]; stacks = [s_ for _, s_ in items]; items = [el for el, _ in items]
            pics = [Image.open(io.BytesIO(z.read(el.get("src")))).convert("RGBA") for el in items]
        bg = None
        if items and stacks[0] is None and (items[0].get("x-instant-background") == "1" or (items[0].get("name", "").lower() == "background" and pics[0].getchannel("A").getextrema()[0] == 255)):
            bg = Image.new("RGB", (w, h), (255, 255, 255)); bg.paste(pics[0].convert("RGB"), (int(float(items[0].get("x", 0))), int(float(items[0].get("y", 0))))); items, pics, stacks = items[1:], pics[1:], stacks[1:]
        self.new(w, h, background=bg); self.layers = []; gids = {}
        ops = {v: k for k, v in self.ORA_OPS.items()}
        for el, im in zip(items, pics):
            L = Layer(w, h, el.get("name", "Layer")); full = Image.new("RGBA", (w, h), (0, 0, 0, 0)); full.paste(im, (int(float(el.get("x", 0))), int(float(el.get("y", 0)))))
            px = np.asarray(full, np.float32); L.img.a = px[..., :3].copy(); L.img.alpha = px[..., 3] / 255
            L.visible = el.get("visibility", "visible") != "hidden"; L.opacity = float(el.get("opacity", 1.0))
            L.mode = el.get("x-instant-mode") or ops.get(el.get("composite-op", "svg:src-over"), "normal"); L.clip = el.get("x-instant-clip") == "1"
            st = stacks[len(self.layers)]
            if st is not None:
                if id(st) not in gids:
                    self._gid += 1; gids[id(st)] = self._gid; G = Group(st.get("name", "Group")); G.opacity = float(st.get("opacity", 1.0))
                    G.visible = st.get("visibility", "visible") != "hidden"; G.mode = st.get("x-instant-mode") or ops.get(st.get("composite-op", "svg:src-over"), "normal")
                    G.collapsed = st.get("x-instant-folded") == "1"; self.groups[self._gid] = G
                L.group = gids[id(st)]
            self.layers.append(L)
        if not self.layers: self.layers = [Layer(w, h, "Layer 1")]
        self.li = len(self.layers) - 1; self._recomp(); self._layers_ui(); self.fit(); self.changed = False


    # ------------------------------------------------------------------ view
    def fit(self):
        """the whole page in view, centred. Stays 'fitted' (refits whenever the space changes) until you zoom or pan"""
        W, H = max(50, self.cv.winfo_width()), max(50, self.cv.winfo_height()); w, h = self.size_wh
        self.zoom = min((W - 20) / w, (H - 20) / h); self.pan = [0, 0]; self._view_fit = True; self._view_z = T.Z; self.refresh()

    def zoom_by(self, k, at=None):
        """zoom in / out. With `at` (a spot on the canvas, e.g. under the mouse) that spot of the picture stays under it,
        so you zoom into whatever part you point at; without it, the middle of the view stays put"""
        if self.zoom is None: self.fit()
        z0 = self.zoom; z1 = min(8.0, max(0.05, z0 * k))
        if at is not None and z1 != z0:
            P = self._from_scr(*at); self.zoom = z1; X, Y = self._to_scr(*P)          # the picture spot under the mouse stays under it
            self.pan = [self.pan[0] + at[0] - X, self.pan[1] + at[1] - Y]
        elif z1 != z0: self.pan = [self.pan[0] * z1 / z0, self.pan[1] * z1 / z0]   # (the middle of the view stays put)
        self.zoom = z1; self._view_fit = False; self.refresh()

    def _cv_resized(self):
        """the canvas changed size (window resized, minimized / maximized, a side panel opened / closed, big mode): the view keeps
        its place. A fitted page is fitted again; otherwise the same spot stays in the middle, and if the whole app was zoomed the
        picture is scaled with it, so it looks the same as before"""
        if getattr(self, "_view_fit", True) or self.zoom is None: self.fit(); return
        k = T.Z / getattr(self, "_view_z", T.Z)
        if abs(k - 1) > 1e-3: self.zoom *= k; self.pan = [self.pan[0] * k, self.pan[1] * k]
        self._view_z = T.Z; self.refresh()

    def _wheel(self, e): self.zoom_by(1.15 if e.delta > 0 else 1 / 1.15, (e.x, e.y))      # zooms in / out where the mouse is
    def _pan_start(self, e): self._pan0 = (e.x, e.y, *self.pan)
    def _pan_move(self, e): x0, y0, px, py = self._pan0; self.pan = [px + e.x - x0, py + e.y - y0]; self._view_fit = False; self.refresh()

    def _geom(self):
        W, H = self.cv.winfo_width(), self.cv.winfo_height(); w, h = self.size_wh; z = self.zoom
        return (W - w * z) / 2 + self.pan[0], (H - h * z) / 2 + self.pan[1], z

    def _patch(self, rect):
        self._nav_soon()
        """show just the part of the picture that changed (a small image laid over the view) instead of redrawing the whole view"""
        if self.zoom is None or not self.winfo_ismapped(): return
        if self._turned(): self.refresh(); return                                # a turned view: the next frame redraws it whole
        if len(self._patches) > 400: self.refresh(); return                     # a very long stroke: tidy up with one full redraw
        ox, oy, z = self._geom(); w, h = self.size_wh; W, H = self.cv.winfo_width(), self.cv.winfo_height()
        SX0, SY0 = max(0, math.floor(ox + max(0, rect[0]) * z)), max(0, math.floor(oy + max(0, rect[1]) * z))
        SX1, SY1 = min(W, math.ceil(ox + min(w, rect[2]) * z)), min(H, math.ceil(oy + min(h, rect[3]) * z))
        if SX1 - SX0 < 1 or SY1 - SY0 < 1: return
        fx0, fy0, fx1, fy1 = (SX0 - ox) / z, (SY0 - oy) / z, (SX1 - ox) / z, (SY1 - oy) / z              # the exact picture area under those screen pixels
        ix0, iy0 = max(0, int(fx0)), max(0, int(fy0)); ix1, iy1 = min(w, int(math.ceil(fx1)) + 1), min(h, int(math.ceil(fy1)) + 1)
        if ix1 <= ix0 or iy1 <= iy0: return
        # (a stroke off the paper's edge: rounding can put the area a hair outside the picture, so keep the box inside it)
        bw, bh = ix1 - ix0, iy1 - iy0; bx0, by0 = min(max(0.0, fx0 - ix0), bw - 0.01), min(max(0.0, fy0 - iy0), bh - 0.01)
        box = (bx0, by0, min(max(bx0 + 0.01, min(fx1, w) - ix0), bw), min(max(by0 + 0.01, min(fy1, h) - iy0), bh))
        im = Image.fromarray(self._comp[iy0:iy1, ix0:ix1]).resize((SX1 - SX0, SY1 - SY0), Image.NEAREST if z > 2 else Image.BILINEAR, box=box)
        ph = ImageTk.PhotoImage(im); self._patches.append(ph); self.cv.create_image(SX0, SY0, image=ph, anchor="nw", tags="patch")

    def _turned(self): return abs(getattr(self, "view_rot", 0.0)) > 1e-6 or getattr(self, "view_flip", False)

    def _to_scr(self, x, y):
        """a picture point -> where it is on the screen (the view may be turned / mirrored)"""
        if not self._turned(): ox, oy, z = self._geom(); return ox + x * z, oy + y * z
        W, H = self.cv.winfo_width(), self.cv.winfo_height(); w, h = self.size_wh; z = self.zoom
        u, v = (x - w / 2) * (-1 if self.view_flip else 1), y - h / 2; c, s_ = math.cos(self.view_rot), math.sin(self.view_rot)
        return W / 2 + self.pan[0] + z * (u * c - v * s_), H / 2 + self.pan[1] + z * (u * s_ + v * c)

    def _from_scr(self, X, Y):
        if not self._turned(): ox, oy, z = self._geom(); return (X - ox) / z, (Y - oy) / z
        W, H = self.cv.winfo_width(), self.cv.winfo_height(); w, h = self.size_wh; z = self.zoom
        a, b = (X - W / 2 - self.pan[0]) / z, (Y - H / 2 - self.pan[1]) / z; c, s_ = math.cos(self.view_rot), math.sin(self.view_rot)
        u, v = a * c + b * s_, -a * s_ + b * c
        return w / 2 + u * (-1 if self.view_flip else 1), h / 2 + v

    def to_img(self, e):
        x, y = self._from_scr(e.x, e.y); return (x, y, 1.0)

    def set_view(self, rot=None, flip=None, delta=None):
        """turn the view (degrees, round the middle of the window) and / or mirror it; the picture under the middle stays put"""
        if self.zoom is None: self.fit()
        W, H = self.cv.winfo_width(), self.cv.winfo_height(); mid = self._from_scr(W / 2, H / 2)
        if delta is not None: rot = math.degrees(self.view_rot) + delta
        if rot is not None: r = ((rot + 180) % 360) - 180; self.view_rot = 0.0 if abs(r) < 0.5 else math.radians(r)
        if flip is not None: self.view_flip = bool(flip)
        X, Y = self._to_scr(*mid); self.pan = [self.pan[0] + W / 2 - X, self.pan[1] + H / 2 - Y]
        if self.tool in ("crop", "text") and self._turned(): self.set_view(rot=0, flip=False)       # (crop / text work on an upright view)
        sync = getattr(self, "_sync_view_ui", None)
        if sync: sync()
        self._view_fit = False; self.refresh()

    def refresh(self):
        """redraw the view soon. Throttled, not debounced: while you pan or zoom it keeps redrawing (up to ~60 a second)
        instead of waiting for you to stop"""
        if self._job is None: self._job = self.after(16, self._draw)

    def _draw(self):
        if self._job is not None:
            try: self.after_cancel(self._job)
            except Exception: pass
        self._job = None
        if not self.winfo_ismapped(): return
        if self.zoom is None: self.fit(); return
        ox, oy, z = self._geom(); w, h = self.size_wh; W, H = self.cv.winfo_width(), self.cv.winfo_height()
        self._patches = []
        if self._turned():                                                       # turned / mirrored view: one transform of the whole picture
            c, s_ = math.cos(self.view_rot), math.sin(self.view_rot); fx = -1 if self.view_flip else 1; Cx, Cy = W / 2 + self.pan[0], H / 2 + self.pan[1]
            data = (fx * c / z, fx * s_ / z, w / 2 - fx * (Cx * c + Cy * s_) / z, -s_ / z, c / z, h / 2 + (Cx * s_ - Cy * c) / z)
            im = Image.fromarray(self._comp).transform((max(1, W), max(1, H)), Image.AFFINE, data, Image.NEAREST if z > 2 else Image.BILINEAR, fillcolor=(42, 45, 54))
            self.ph = ImageTk.PhotoImage(im); self.cv.delete("all"); self.cv.create_image(0, 0, image=self.ph, anchor="nw")
        else:
            x0, y0 = max(0, int(-ox / z)), max(0, int(-oy / z)); x1, y1 = min(w, int((W - ox) / z) + 1), min(h, int((H - oy) / z) + 1)   # only what's on screen
            if x1 <= x0 or y1 <= y0: self.cv.delete("all"); return
            im = Image.fromarray(self._comp[y0:y1, x0:x1]).resize((max(1, int((x1 - x0) * z)), max(1, int((y1 - y0) * z))), Image.NEAREST if z > 2 else Image.BILINEAR)
            self.ph = ImageTk.PhotoImage(im); self.cv.delete("all"); self.cv.create_image(ox + x0 * z, oy + y0 * z, image=self.ph, anchor="nw")
        S_ = self._to_scr
        if self.mirror.get(): self.cv.create_line(*S_(w / 2, 0), *S_(w / 2, h), fill=T.PALETTE["border"], dash=(4, 4))
        if self.mirror_y.get(): self.cv.create_line(*S_(0, h / 2), *S_(w, h / 2), fill=T.PALETTE["border"], dash=(4, 4))
        n = self._radial_n()
        if n > 1:                                                                 # the spokes of radial symmetry
            R = math.hypot(w, h) / 2
            for k in range(n): a = 2 * math.pi * k / n - math.pi / 2; self.cv.create_line(*S_(w / 2, h / 2), *S_(w / 2 + math.cos(a) * R, h / 2 + math.sin(a) * R), fill=T.PALETTE["border"], dash=(3, 5))
        self._guides_draw(); self._nav_soon()
        self._tip_redraw()
        if getattr(self, "_x_ready", False): self._x_overlay()                  # selection ants, crop box, text box

    # ------------------------------------------------------------------ tools
    def set_tool(self, t):
        if hasattr(self, "tool"): self._x_leaving(t)                             # finish a selection / crop / text first
        if t == "pick" and getattr(self, "tool", "pick") != "pick": self._before_pick = self.tool   # Pick hands back to this tool once a colour is taken
        self.tool = t
        if t in ("crop", "text") and self._turned(): self.set_view(rot=0, flip=False)     # crop / text work on an upright view
        for k, b in self.tool_btns.items():
            if getattr(b, "_is_art", False): b._selected = k == t; b._style()
            else: b.configure(highlightbackground=T.PALETTE["border"] if k == t else b.master["bg"])
        cur = self._no_cursor() if t in ("brush", "eraser") else {"pick": "tcross", "fill": "spraycan", "text": "xterm", "sel_rect": "tcross",
                                                                     "sel_oval": "tcross", "crop": "sizing", "move": "fleur", "wand": "tcross", "pattern_fill": "spraycan", "sel_lasso": "pencil"}.get(t, "crosshair")
        for cv in {self.cv, getattr(self, "_cv_small", self.cv), getattr(self, "_cv_big", self.cv)}:     # both canvases (normal and whole-page)
            try: cv.configure(cursor=cur)
            except tk.TclError: cv.configure(cursor="crosshair")
        self._tip_redraw()

    # ------------------------------------------------------------------ the brush tip under the mouse
    def _no_cursor(self):
        """no mouse pointer over the canvas (the brush's own mark shows instead). Windows doesn't know the name "none", so it gets a
        see-through cursor file (by its short path, which has no spaces)"""
        if getattr(self, "_nocur", None) is not None: return self._nocur
        cur = "none"
        if sys.platform.startswith("win"):
            f = os.path.join(paths.APP, "images", "UI", "Cursors", "blank.cur")
            if os.path.exists(f):
                try:
                    import ctypes; buf = ctypes.create_unicode_buffer(520)
                    if ctypes.windll.kernel32.GetShortPathNameW(f, buf, 520): f = buf.value
                except Exception: pass
                cur = "{@" + f.replace("\\", "/") + "}"
        try: self.cv.configure(cursor=cur)
        except tk.TclError: cur = "dotbox"
        self._nocur = cur; return cur

    def _tip_move(self, e):
        self._tip_at = (e.widget, e.x, e.y); self._tip_redraw()

    def _os_cursor(self, hide):
        """Windows: hide the real mouse pointer while it's over the canvas with the brush / eraser (the brush's own mark shows
        instead), and bring it back when it leaves. Done with Windows itself, so no cross can show whatever Tk does"""
        if not sys.platform.startswith("win") or bool(hide) == getattr(self, "_os_hidden", False): return
        try:
            import ctypes; show = ctypes.windll.user32.ShowCursor
            for _ in range(20):                                                       # Windows keeps a count: step it just past 0
                n = show(not hide)
                if (n < 0) if hide else (n >= 0): break
            self._os_hidden = bool(hide)
        except Exception: pass

    def _tip_hide(self, cv):
        self._tip_at = None; self._os_cursor(False)
        try: cv.delete("tip")
        except tk.TclError: pass

    def _tip_image(self):
        """what one touch of the brush leaves (its shape, softness, texture, colour and opacity) at the size you'd paint it,
        — no ring or cross, just the mark. Eraser: a see-through white dot its size"""
        z = self.zoom or 1.0; d = self.size * z
        if self.tool == "brush":
            try: opts = repr(sorted(self._live_brush().items(), key=lambda kv: kv[0]))
            except Exception: opts = ""
            key = ("brush", self.brush, self.size, tuple(self._stroke_color()), round(z, 2), opts)   # (not the opacity: the tip keeps one look)
        else: key = ("eraser", self.size, round(z, 2))
        if getattr(self, "_tip_key", None) == key: return self._tip_ph
        D = int(min(600, max(10, d * 1.25 + 8)))                                    # on screen, the most it will cover
        out = Image.new("RGBA", (D, D), (0, 0, 0, 0))
        if self.tool == "brush":
            try:
                rs = max(1, min(self.size, 260, max(12, int(self.size * z))))                 # drawn at about the size it shows on screen
                n = max(8, int(rs * 1.6) + 6); c = brushes.Canvas(n, n, paper=(0, 0, 0), transparent=True)
                brushes.B["__tip__"] = self._live_brush()
                try:
                    c.stroke([(n / 2, n / 2, 1.0), (n / 2 + 0.6, n / 2, 1.0)], "__tip__", color=self._stroke_color(), size=rs, opacity=1.0)
                    if np.nan_to_num(c.alpha).max() < 0.05:                     # tapering brushes leave nothing on one touch: a short line instead
                        L = rs * 0.35
                        c.stroke([(n / 2 + (t - 0.5) * 2 * L, n / 2 - (t - 0.5) * 0.6 * L, 0.4 + 0.6 * math.sin(math.pi * t)) for t in np.linspace(0, 1, 16)], "__tip__",
                                 color=self._stroke_color(), size=rs, opacity=1.0)
                finally: brushes.B.pop("__tip__", None)
                al = np.nan_to_num(c.alpha); top = float(al.max())
                if 0 < top < 0.6: al = al * min(4.0, 0.6 / top)                     # very soft brushes: strong enough to see
                rgb = Image.fromarray(np.clip(np.nan_to_num(c.a), 0, 255).astype(np.uint8))
                a = Image.fromarray(np.clip(al * 255 * 0.85, 0, 255).astype(np.uint8))
                dab = rgb.convert("RGBA"); dab.putalpha(a)
                k = z * self.size / rs                                                   # its pixels to screen pixels
                dab = dab.resize((max(1, round(n * k)), max(1, round(n * k))), Image.LANCZOS if k < 1 else Image.NEAREST if k > 3 else Image.BILINEAR)
                if dab.width > D: dab = dab.crop(((dab.width - D) // 2, (dab.height - D) // 2, (dab.width - D) // 2 + D, (dab.height - D) // 2 + D))
                out.alpha_composite(dab, ((D - dab.width) // 2, (D - dab.height) // 2))
            except Exception: pass
        r = max(2, d / 2); c0 = D / 2
        if out.getchannel("A").getextrema()[1] < 25:                                    # nothing to show (eraser, or a mark too faint): a see-through dot
            fill = (255, 255, 255, 110) if self.tool == "eraser" else tuple(self._stroke_color()) + (150,)
            ImageDraw.Draw(out).ellipse((c0 - r, c0 - r, c0 + r, c0 + r), fill=fill)
        self._tip_ph = ImageTk.PhotoImage(out); self._tip_key = key; return self._tip_ph

    def _tip_redraw(self):
        at = getattr(self, "_tip_at", None)
        for cv in {self.cv, getattr(self, "_cv_small", self.cv)}:
            try: cv.delete("tip")
            except tk.TclError: pass
        on = at is not None and self.tool in ("brush", "eraser") and at[0] is self.cv; self._os_cursor(on)
        if not on: return
        try: self.cv.create_image(at[1], at[2], image=self._tip_image(), tags="tip")
        except tk.TclError: pass

    def set_brush(self, n, label=None):
        self.brush = n; self.brush_lbl.configure(text=label or n); self.set_tool("brush")
        if hasattr(self, "opt_rows"): self._load_brush_opts(n)
        for k, lb in self.tiles.items(): lb.configure(highlightbackground=T.PALETTE["border"] if lb._engine == n else lb._off)
        self._preview()

    def _pick(self, it, section=None):
        """a tile was clicked: use it, or say it's still to come"""
        if it.get("engine"):
            pic = UA.tile_image(it["name"], section) or UA.preview(it["name"], section)       # the picture of the tile that was clicked
            if pic is not None: self._art_by_engine[it["engine"]] = pic
            if it["engine"].endswith(" pattern"): self._last_pattern = it["engine"][:-len(" pattern")]      # Pattern Fill uses it
            self.set_brush(it["engine"], it["name"])
        elif it.get("studio_tool"): self.set_tool(it["studio_tool"]); self.brush_lbl.configure(text=it["name"])
        else: T.banner(self.app, f"COMING SOON — {it['name']} isn't built yet")

    def _right_view(self, name):
        """the right panel: the Color view (ring, swatches, palettes, history) or the Options view (layers and text)"""
        for n, b in self.right_btns.items(): skin.select(b, n == name)
        for w in (self.col_view, self.lay_view): w.pack_forget()
        (self.col_view if name == "Color" else self.lay_view).pack(fill="both", expand=True); prefs.set("draw_right_view", name)

    def _fit_layer_rows(self):
        """the layer list's box is half the Layers view tall; it shows as many rows as fit, the rest scroll"""
        try: H = max(self._apx(70), self.lay_view.winfo_height() // 4)
        except tk.TclError: return
        if abs(self._lay_frame.winfo_height() - H) > 2: self._lay_frame.configure(height=H)
        n = max(2, (H - self._apx(10)) // max(1, self._apx(26) + 2))
        if n != getattr(self, "_lay_rows", 4): self._lay_rows = n; self._layers_ui()

    def _lay_cmd(self, *a):
        """the layer list's scroll bar"""
        total = len(self.layers) + 1
        if a[0] == "moveto": self._lay_off = int(round(float(a[1]) * total)); self._lay_scroll(0)
        elif a[0] == "scroll": self._lay_scroll(int(a[1]) * (self._rows() if a[2] == "pages" else 1))

    # ---------------- Brush Options
    def _left_view(self, name):
        for n, b in self.view_btns.items(): skin.select(b, n == name)
        for w in (self.opt_view, self.lib_view, self._pinned, self._adj_rail): w.pack_forget()
        if name == "Brushes": self._pinned.pack(side="bottom", fill="x"); self.lib_view.pack(fill="both", expand=True)
        else:                                                                         # the scroll rail first, so it runs the full height on the right
            self._adj_rail.pack(side="right", fill="y"); self._pinned.pack(side="top", fill="x", pady=(0, 8), padx=(0, T.ScrollBox.GAP)); self.opt_view.pack(fill="both", expand=True)

    def _typed(self, row, apply):
        try: apply(float(row.var.get().strip().rstrip("%°")))
        except ValueError: T.banner(self.app, "NOT A NUMBER — type a number, then press Enter")

    def _sync_slider(self, row, v01): row.slider.value = min(1, max(0, v01)); row.slider._draw()

    def _brush_defaults(self, n):
        b = brushes.B.get(n) or {}; ta = b.get("tipargs", {}); flat = b.get("tip") in (brushes.tip_ellipse, brushes.tip_rect)
        return dict(spacing=round(b.get("spacing", 0.15) * 100), flow=round(b.get("flow", 1.0) * 100), hardness=round(ta.get("hard", 0.85) * 100),
                    roundness=round((ta.get("aspect", 0.35) if flat else ta.get("roundness", 1.0)) * 100),
                    angle=round(math.degrees(ta.get("angle", 0.0))) % 181, rotation=min(180, round(math.degrees(b.get("jitter_angle", 0.0)))),
                    size_jitter=round(b.get("jitter_size", 0.0) * 100), scatter=round(b.get("scatter", 0.0) * 100),
                    press_size=round(b.get("size_press", 1.0) * 100), press_opacity=round(b.get("opac_press", 0.0) * 100),
                    texture=round(b.get("tex_strength", 0.85) * 100))

    def _load_brush_opts(self, n):
        """the sliders show this brush's own settings; nothing is overridden until you move one"""
        self.opts = {k: None for k in OPT_KEYS}
        for k, v in self._brush_defaults(n).items(): self._show_opt(k, v)

    def _show_opt(self, key, val):
        row = self.opt_rows[key]; lo, hi = row.range; self._sync_slider(row, (val - lo) / (hi - lo)); row.var.set(f"{int(round(val))}{row.unit}")

    def _set_opt(self, key, val, sync=False):
        lo, hi = self.opt_rows[key].range; val = min(hi, max(lo, val)); self.opts[key] = val; self._show_opt(key, val); self._preview()

    def _presets(self):
        try: return json.load(open(paths.json_file("draw_brushes.json"), encoding="utf-8"))
        except Exception: return {}

    def _save_preset(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("Save brush", "Name for this brush:", parent=self, initialvalue=self.brush_lbl.cget("text"))
        if not name or not name.strip(): return
        name = name.strip()[:40]; d = self._presets()
        d[name] = dict(brush=self.brush, label=self.brush_lbl.cget("text"), opts={k: v for k, v in self.opts.items() if v is not None},
                       size=self.size, opacity=self.opacity, blend=self.blend_mode.get())
        try:
            with open(paths.json_file("draw_brushes.json"), "w", encoding="utf-8") as f: json.dump(d, f, indent=1)
        except Exception as ex: T.banner(self.app, f"COULDN'T SAVE IT — {ex}"); return
        self._preset_choice.choices = ["—"] + sorted(d); self.preset_var.set(name); T.banner(self.app, f"SAVED — your brush '{name}' is under My Brushes", "success")

    def _delete_preset(self):
        name = self.preset_var.get(); d = self._presets()
        if name not in d: return
        del d[name]
        try:
            with open(paths.json_file("draw_brushes.json"), "w", encoding="utf-8") as f: json.dump(d, f, indent=1)
        except Exception: pass
        self._preset_choice.choices = ["—"] + sorted(d); self.preset_var.set("—")

    def _use_preset(self, name):
        pr = self._presets().get(name)
        if not pr or pr.get("brush") not in brushes.B: return
        self.set_brush(pr["brush"], pr.get("label") or name)
        for k, v in pr.get("opts", {}).items():
            if k in self.opt_rows: self._set_opt(k, v)
        self.set_size(pr.get("size", self.size)); self.set_opacity(pr.get("opacity", self.opacity)); self._sync_slider(self.op_row, self.opacity)
        if pr.get("blend"): self.blend_mode.set(pr["blend"])
        self.brush_lbl.configure(text=name)

    def _live_brush(self):
        """the brush with your Brush Options applied (a copy; the brush's own settings are never changed)"""
        b = dict(brushes.B[self.brush]); b["tipargs"] = dict(b["tipargs"]); o = self.opts
        if o["spacing"] is not None: b["spacing"] = max(0.01, o["spacing"] / 100)
        if o["flow"] is not None: b["flow"] = max(0.01, o["flow"] / 100)
        if o["roundness"] is not None:
            if b["tip"] in (brushes.tip_ellipse, brushes.tip_rect): b["tipargs"]["aspect"] = max(0.05, o["roundness"] / 100)
            else: b["tipargs"]["roundness"] = max(0.05, o["roundness"] / 100)
        if o["size_jitter"] is not None: b["jitter_size"] = o["size_jitter"] / 100
        if o["scatter"] is not None: b["scatter"] = o["scatter"] / 100
        if o["press_size"] is not None: b["size_press"] = o["press_size"] / 100
        if o["press_opacity"] is not None: b["opac_press"] = o["press_opacity"] / 100
        if o["texture"] is not None: b["tex_strength"] = o["texture"] / 100
        brushes.Canvas.stamp_own_colors = self.stamp_colors.get() != "My color"
        brushes.Canvas.texture_own_colors = self.texture_colors.get() != "My color"
        if o["hardness"] is not None: b["tipargs"]["hard"] = min(0.98, o["hardness"] / 100)
        if o["rotation"] is not None: b["jitter_angle"] = math.radians(o["rotation"])
        if o["angle"] is not None:                                                # an angle you set is kept exactly: the tip no longer turns with the stroke
            b["tipargs"]["angle"] = math.radians(o["angle"]); b["angle_follow"] = False
        if self.blend_mode.get() != "Brush default" and b["mode"] != "erase": b["mode"] = self.blend_mode.get().lower()
        if self.color_mode.get() == "Color Jitter": b["color_jitter"] = max(b["color_jitter"], 0.18)
        return b

    def _stroke_color(self):
        if self.color_mode.get() != "Rainbow": return self.color
        self._hue = (self._hue + 0.015) % 1; r, g, b = colorsys.hsv_to_rgb(self._hue, max(0.6, self.s), max(0.6, self.v)); return (int(r * 255), int(g * 255), int(b * 255))

    def _set_tile(self, key, im, soon=None):
        """a tile's picture, kept at full size and shown at the size that fits the box. Every cell is the same size: a painted tile fills
        it; a preview strip plus its name label below take exactly the same height"""
        self._tile_src[key] = im
        if soon is not None: self._tile_soon[key] = soon
        th = max(16, round(self._tw * UA.TILE_SIZE[1] / UA.TILE_SIZE[0]))
        if not self._fitted:                                                                  # pictures are made once the real size is known
            ph = self._tile_cache.get(("blank", self._tw, th))                               # meanwhile a shared empty picture (sizes in pixels)
            if ph is None: ph = self._tile_cache[("blank", self._tw, th)] = ImageTk.PhotoImage(Image.new("RGBA", (self._tw, th), (0, 0, 0, 0)))
            self.tiles[key].configure(image=ph, width=self._tw, height=th); return
        ck = (id(im), self._tw, th, self._lh, bool(self._tile_soon.get(key)))
        ph = self._tile_cache.get(ck)
        if ph is not None: self._tile_ph[key] = ph; self.tiles[key].configure(image=ph, width=ph.width(), height=ph.height()); return
        if im.mode == "RGBA": im = im.resize((self._tw, th), Image.LANCZOS)                      # painted tile: exactly the box
        else:
            h = max(10, th - self._lh); r = self._tw / h                                          # strip: the box less the name line
            if im.width / im.height > r: nw = max(1, round(im.height * r)); im = im.crop(((im.width - nw) // 2, 0, (im.width - nw) // 2 + nw, im.height))
            else: nh = max(1, round(im.width / r)); im = im.crop((0, (im.height - nh) // 2, im.width, (im.height - nh) // 2 + nh))
            im = im.convert("RGB").resize((self._tw, h), Image.LANCZOS)
            if self._tile_soon.get(key): im = self._soon(im)
            th = h
        ph = ImageTk.PhotoImage(im); self._tile_ph[key] = ph
        if len(self._tile_cache) > 5000: self._tile_cache.clear()
        self._tile_cache[ck] = ph; self.tiles[key].configure(image=ph, width=self._tw, height=th)

    def _set_icon(self, lb, name):
        size = max(12, self._ic - 8); key = ("icon", name, size)
        if key not in self._tile_ph: self._tile_ph[key] = ImageTk.PhotoImage(UA.stamp(name, size) or BC.icon(name, size))     # painted stamp, else drawn
        lb.configure(image=self._tile_ph[key], width=self._ic - 2, height=self._ic - 2)

    def _fit_tiles(self):
        """the brush box changed width: two tiles a row (and five stamps) that fit it exactly, nothing cut off at the right"""
        w = self._sc.winfo_width()
        if w < 60: return
        tw = max(40, (w - 2 * self._apx(7) - 6 - 8 - 4) // 2); ic = max(20, min(40, (w - 4) // 5 - 4)); lh = self._name_h()
        if (tw, ic, lh) == (self._tw, self._ic, self._lh) and self._fitted: return
        self._tw, self._ic, self._lh = tw, ic, lh; self._fitted = True
        self.after_idle(self._fit_pills)                                              # once the tiles have their new size: the titles match them
        for key, im in list(self._tile_src.items()): self._set_tile(key, im)
        if self._tile_names:                                                          # names on one line: shortened with … if too long
            import tkinter.font as tkfont
            f = tkfont.Font(font=self._tile_names[0].cget("font"))
            fk = (str(self._tile_names[0].cget("font")), tw)
            for nm in self._tile_names:
                ck = (fk, nm._full); t = self._name_cache.get(ck)
                if t is None:
                    t = nm._full
                    while len(t) > 3 and f.measure(t) > tw: t = t[:-2].rstrip() + "…"
                    self._name_cache[ck] = t
                if nm.cget("text") != t: nm.configure(text=t, wraplength=0)
        for lb, name in self._icon_tiles: self._set_icon(lb, name)

    @staticmethod
    def _soon_tag(im):
        """a painted tile for a tool that isn't built yet: the picture as it is, with a small SOON tag in the corner"""
        im = im.copy(); d = ImageDraw.Draw(im); h = max(14, im.height // 7); w = h * 3; font = UA._font(int(h * 0.75))
        x1, y1 = im.width - 6, im.height - 6; d.rounded_rectangle([x1 - w, y1 - h, x1, y1], radius=h // 3, fill=(20, 26, 42, 235), outline=(245, 196, 0, 255))
        d.text((x1 - w / 2, y1 - h / 2), "SOON", fill=(245, 196, 0, 255), font=font, anchor="mm"); return im

    def _fit_pills(self):
        self._sc.update_idletasks()
        for h in self._pills: self._set_pill(h)

    def _set_pill(self, h):
        """a section title bar exactly as wide as the two tiles under it (left edge of the left one to right edge of the right one),
        the name in its middle"""
        g = getattr(h, "_grid", None); W = 2 * self._tw + 8
        cells = g.winfo_children()[:2] if g is not None else []
        if len(cells) == 2:                                                             # the two tiles' real widths and the gap between them
            pads = [int(v) for v in str(cells[0].grid_info().get("padx", 0)).replace("(", " ").replace(")", " ").replace(",", " ").split()] or [0]
            inner = pads[-1] if len(pads) > 1 else pads[0]                                # the gap on the side facing the other tile
            tiles = [c.winfo_children()[0].winfo_reqwidth() for c in cells]
            if min(tiles) > 10: W = tiles[0] + tiles[1] + 2 * inner
        W = max(40, W); H = max(12, round(20 * T.Z))
        if not AP.ok(): h.configure(text=h._text, fg="white", bg=T.PALETTE["button"], font=T.f(9)); return
        ph = AP.photo(("pill", h._text, W, H), lambda: AP.text(AP.bar("bar_blank", W, H, 0.3).copy(), h._text, W // 2, H // 2, int(H * 0.5)))
        h.configure(image=ph, width=W, height=H)

    def _name_h(self):
        """height of one name line under a tile (changes with the zoom)"""
        return self._tile_names[0].winfo_reqheight() if self._tile_names else 12

    @staticmethod
    def _soon(im):
        """a planned tool's preview: slightly faded, with a small SOON tag sized to the picture"""
        im = Image.blend(im.convert("RGB"), Image.new("RGB", im.size, (244, 238, 226)), 0.25); d = ImageDraw.Draw(im)
        h = max(9, im.height // 3); w = h * 3; font = UA._font(max(7, int(h * 0.7)))
        d.rectangle([im.width - w, im.height - h, im.width - 1, im.height - 1], fill=(20, 26, 42))
        d.text((im.width - w / 2, im.height - h / 2), "SOON", fill=(245, 196, 0), font=font, anchor="mm"); return im

    def _size_max(self):
        """the biggest brush: the whole mark still fits inside the canvas (its shorter side)"""
        return max(16, min(getattr(self, "size_wh", (300, 300))))
    def _s2v(self, s): return math.log(max(1, s)) / math.log(self._size_max())
    def _v2s(self, v): return max(1, int(round(self._size_max() ** v)))
    def set_size(self, s, from_slider=False):
        self.size = int(max(1, min(self._size_max(), s))); self.size_row.var.set(str(self.size)); self._tip_redraw()   # 1 pixel to the whole canvas
        if not from_slider: self.size_s.value = self._s2v(self.size); self.size_s._draw()
        self._preview()
    def set_opacity(self, v): self.opacity = max(0.02, min(1.0, v)); self.op_row.var.set(f"{int(round(self.opacity * 100))}%"); self._preview(); self._tip_redraw()

    UNDO_MB = 400                                                               # undo memory cap, on top of Settings > Performance > Draw undo steps

    def _begin_edit(self):
        """before a change to the current layer: remember it, so the change can be undone"""
        L = self.cur; self._edit = (self.li, L.cv.a.copy(), L.cv.alpha.copy()); self._dirty = None; self._edit_mask = L.cv is not L.img

    def _commit_edit(self):
        """after the change: keep only the area that actually changed (not the whole layer) on the undo list"""
        if self._edit is None: return None
        i, a0, al0 = self._edit; self._edit = None
        if i >= len(self.layers): return None
        L = self.layers[i]; w, h = self.size_wh
        if self._dirty is not None:                                              # a stroke: look around it (wide margin for splatter), not the whole layer
            m = self.size * 3 + 32; d = self._dirty
            bx0, by0, bx1, by1 = max(0, int(d[0] - m)), max(0, int(d[1] - m)), min(w, int(d[2] + m) + 1), min(h, int(d[3] + m) + 1)
        else: bx0, by0, bx1, by1 = 0, 0, w, h
        self._dirty = None
        if bx1 <= bx0 or by1 <= by0: return None
        sl = (slice(by0, by1), slice(bx0, bx1))
        diff = (L.cv.alpha[sl] != al0[sl]) | np.any(L.cv.a[sl] != a0[sl], axis=2)
        rows, cols = np.flatnonzero(diff.any(1)), np.flatnonzero(diff.any(0))
        if not len(rows): return None
        y0, y1, x0, x1 = by0 + int(rows[0]), by0 + int(rows[-1]) + 1, bx0 + int(cols[0]), bx0 + int(cols[-1]) + 1
        self.undo_stack.append((i, y0, y1, x0, x1, a0[y0:y1, x0:x1].copy(), al0[y0:y1, x0:x1].copy(), getattr(self, "_edit_mask", False))); self.redo_stack.clear()
        self._tl_grab()                                                          # timelapse: a frame after every change (if recording)
        self._trim_undo(); self.changed = True
        return (x0, y0, x1, y1)

    def _trim_undo(self):
        steps = int(prefs.get("undo_steps")); self.undo_stack = self.undo_stack[-steps:]
        while len(self.undo_stack) > 1 and sum(u[5].nbytes + u[6].nbytes for u in self.undo_stack) > self.UNDO_MB * 1e6: self.undo_stack.pop(0)

    def _swap(self, src, dst):
        if not src: return
        if src[-1][0] == "whole": return self._swap_whole(src, dst)              # a crop
        i, y0, y1, x0, x1, a, al, *mk = src.pop(); mk = bool(mk and mk[0])
        if i >= len(self.layers): return
        L = self.layers[i]; sl = (slice(y0, y1), slice(x0, x1)); C = L.maskcv if mk and L.maskcv is not None else L.img
        dst.append((i, y0, y1, x0, x1, C.a[sl].copy(), C.alpha[sl].copy(), mk)); C.a[sl] = a; C.alpha[sl] = al
        self._recomp((x0, y0, x1, y1)); self.changed = True; self._draw()
    def undo(self): self._swap(self.undo_stack, self.redo_stack)
    def redo(self): self._swap(self.redo_stack, self.undo_stack)

    def _mirror_sets(self, pts):
        """the stroke, plus its mirror images (Mirror X: left-right, Mirror Y: top-bottom, both: all four)"""
        w, h = self.size_wh; out = [pts]
        if self.mirror.get(): out.append([(w - x, y, p) for x, y, p in pts])
        if self.mirror_y.get(): out.append([(x, h - y, p) for x, y, p in pts])
        if self.mirror.get() and self.mirror_y.get(): out.append([(w - x, h - y, p) for x, y, p in pts])
        n = self._radial_n()
        if n > 1:                                                                 # radial: every copy again, turned round the middle
            cx, cy = w / 2, h / 2; base = list(out)
            for k in range(1, n):
                a = 2 * math.pi * k / n; ca, sa = math.cos(a), math.sin(a)
                for P in base: out.append([(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca, p) for x, y, p in P])
        return out

    def _radial_n(self):
        v = self.radial.get() if hasattr(self, "radial") else "Off"; return int(v) if v.isdigit() else 1

    def _paint(self, pts):
        if self.tool == "eraser": name, color = "eraser", self.color
        else:
            brushes.B["__live__"] = self._live_brush(); name, color = "__live__", self._stroke_color()   # the brush with your options, for this stroke piece
        try:
            st = getattr(self, "_stroke_state", None) if self._live() else None
            for k, P in enumerate(self._mirror_sets(pts)):
                self.cur.cv.stroke(P, name, color=color, size=self.size, opacity=self.opacity, state=None if st is None else st.setdefault(k, {}))
            self._confine(pts)                                                     # a selection is on: paint only inside it
            if self.lock_alpha.get() and self._edit is not None and self.tool != "eraser":   # Lock transparency: coverage stays as it was
                x0, y0, x1, y1 = (int(max(0, v)) for v in (self.cur.cv.touched or self._bbox(pts))); sl = (slice(y0, int(y1) + 1), slice(x0, int(x1) + 1))
                self.cur.cv.alpha[sl] = self._edit[2][sl]
        finally: brushes.B.pop("__live__", None)

    def _sel_full(self):
        """the selection as a mask the size of the picture (None when nothing is selected or it's being moved)"""
        s = getattr(self, "sel", None)
        if s is None or s.get("float") is not None: return None
        key = (id(s), s["box"], s["kind"], self.gopts.get("feather", 0), self.size_wh)
        if getattr(self, "_selfull_key", None) != key:
            w, h = self.size_wh; m = np.zeros((h, w), np.float32); x0, y0, x1, y1 = s["box"]; m[y0:y1, x0:x1] = self._sel_mask(s["kind"], x1 - x0, y1 - y0)
            self._selfull, self._selfull_key = m, key
        return self._selfull

    def _confine(self, pts):
        k = self._sel_full()
        if k is None or self._edit is None: return
        x0, y0, x1, y1 = (int(max(0, v)) for v in (self.cur.cv.touched or self._bbox(pts))); sl = (slice(y0, int(y1) + 1), slice(x0, int(x1) + 1))
        C = self.cur.cv; kk = k[sl]; C.alpha[sl] = self._edit[2][sl] * (1 - kk) + C.alpha[sl] * kk
        C.a[sl] = self._edit[1][sl] * (1 - kk[..., None]) + C.a[sl] * kk[..., None]

    def _live(self):
        """painting as the mouse moves (all brushes except the whole-stroke ones, which paint on release)"""
        return self.tool == "eraser" or (self.tool == "brush" and self.brush not in WHOLE_STROKE)

    def _bbox(self, pts):
        m = self.size * 1.5 + 6; xs = [q[0] for q in pts]; ys = [q[1] for q in pts]; W, H = self.size_wh
        if self._radial_n() > 1: return [0, 0, W, H]                              # radial copies go all round
        box = [min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m]
        if self.mirror.get(): box[0], box[2] = min(box[0], W - box[2]), max(box[2], W - box[0])
        if self.mirror_y.get(): box[1], box[3] = min(box[1], H - box[3]), max(box[3], H - box[1])
        return box

    def _show_change(self, rect):
        d = self._dirty; self._dirty = list(rect) if d is None else [min(d[0], rect[0]), min(d[1], rect[1]), max(d[2], rect[2]), max(d[3], rect[3])]
        self._recomp(rect); self._patch(rect)

    def down(self, e):
        if getattr(self, "_lc_orig", None) is not None: self._lc_apply()             # a layer colour change being previewed is kept first
        if self.tool == "move": self._pan_start(e); return                         # Move: the press grabs the picture, dragging moves it
        if hasattr(self, "guide") and self.guide.get() != "Off" and self.guide_move.get(): self._guide_grab(e); return   # Move guides: drag their dots
        p = self.to_img(e); self.start = p; t = self.tool
        if t in ("brush", "eraser") and (getattr(e, "state", 0) & 0x1) and getattr(self, "_last_end", None) is not None:
            return self._straight(self._last_end, p)                             # Shift + click: a straight line from where the last stroke ended
        if t == "pick":
            x, y = int(p[0]), int(p[1]); w, h = self.size_wh
            if 0 <= x < w and 0 <= y < h:
                self.set_color(tuple(int(c) for c in self._comp[y, x])); self._remember()
                self.set_tool(getattr(self, "_before_pick", "brush") or "brush")           # back to the tool you had before pressing Pick
            return
        if t in POLY_TOOLS: self._poly_click(p); return
        if t in ("fill", "pattern_fill"):
            self._begin_edit(); self._fill(p, pattern=t == "pattern_fill"); r = self._commit_edit()
            if r: self._recomp(r); self._draw()
            return
        if t == "text" or t in SEL_TOOLS or t == "crop": return self.x_down(e, p)     # text box, selection, crop (studio_extras)
        self._begin_edit(); self.points = [p]; self._pending = []; self._last_pt = p
        if t in ("brush", "eraser"): self.cur.cv.begin_stroke(self._edit[1], self._edit[2])   # one stroke: never more than your Opacity
        self._stroke_state = {}; self._smooth_pt = p; self._smooth_pr = 1.0                 # one stroke: smoothed direction, position and pressure
        self._raw = [p]; self._snap_begin(p)                                     # the mouse's points, smoothed into curves as they come
        if self._live(): self._paint_show([p, p])

    def drag(self, e):
        if hasattr(self, "guide") and self.guide.get() != "Off" and self.guide_move.get(): self._guide_drag_to(self.to_img(e)); return
        if self.tool == "move":
            if getattr(self, "_pan0", None) is not None: self._pan_move(e)
            return
        if self.tool == "text" or self.tool in SEL_TOOLS or self.tool == "crop": return self.x_drag(e, self.to_img(e))
        if self._edit is None and self.tool not in ("line", "rect", "oval") + GRAD_TOOLS: return     # press happened somewhere else
        p = self.to_img(e); t = self.tool
        if t in ("pick", "fill", "text", "pattern_fill") or t in POLY_TOOLS: return
        if t in ("line", "rect", "oval") + GRAD_TOOLS:
            if getattr(e, "state", 0) & 0x1: p = self._constrain(self.start, p)
            self.cv.delete("shape"); self._preview_shape(self.start, p); return
        p = self._snap_pt(p)                                                     # held on the guide (ruler / perspective), if one is on
        if self.points and abs(p[0] - self.points[-1][0]) + abs(p[1] - self.points[-1][1]) < 1.5 / max(self.zoom, 0.01): return
        sp_ = getattr(self, "_smooth_pt", None)                                   # steady the hand: follow the mouse a little behind, not every jiggle
        f_ = 1 - 0.9 * self.gopts["smooth"] / 100                                 # Smooth 0 = right on the mouse, 100 = a long way behind
        if sp_ is not None: p = (sp_[0] + (p[0] - sp_[0]) * f_, sp_[1] + (p[1] - sp_[1]) * f_, p[2])
        self._smooth_pt = p
        if self.use_pressure.get() and self.points:                              # a mouse has no pressure: slower = harder, faster = lighter (eased in)
            q = self.points[-1]; speed = math.hypot(p[0] - q[0], p[1] - q[1]) * max(self.zoom or 1, 0.01)
            self._smooth_pr = getattr(self, "_smooth_pr", 1.0) * 0.85 + min(1.0, max(0.3, 1.2 - speed / 35)) * 0.15
            p = (p[0], p[1], self._smooth_pr)
        self.points.append(p)
        if self._live():
            self._pending.extend(self._curve_in(p))                              # painted on the next frame tick, together with any other moves since
            if self._tick_job is None: self._tick_job = self.after(8, self._tick)
        else: a, b = self.points[-2], self.points[-1]; self.cv.create_line(*self._to_scr(a[0], a[1]), *self._to_scr(b[0], b[1]), fill="#888", tags="shape")

    def _curve_in(self, p):
        """the mouse jumps between the points it reports (more so while the computer is busy): instead of straight corners,
        the stroke curves through them (each corner becomes a smooth bend between the middles of its two sides)"""
        R = self._raw; R.append(p)
        if len(R) > 3: del R[0]
        mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
        if len(R) == 2: return [mid(R[0], R[1])]
        m0, c, m1 = mid(R[-3], R[-2]), R[-2], mid(R[-2], R[-1])
        n = max(2, min(40, int(math.hypot(m1[0] - m0[0], m1[1] - m0[1]) / 3)))
        return [tuple((1 - t) ** 2 * m0[j] + 2 * (1 - t) * t * c[j] + t * t * m1[j] for j in range(3)) for t in (k / n for k in range(1, n + 1))]

    def _tick(self):
        """one frame: paint every mouse position since the last frame as one piece, then update only that part of the screen"""
        self._tick_job = None
        if not self._pending: return
        pts = [self._last_pt] + self._pending; self._pending = []; self._last_pt = pts[-1]
        self._paint_show(pts)

    def _paint_show(self, pts):
        """paint a piece, then update the screen for exactly the area the dabs touched (not a box the size of the brush round every point)"""
        cv = self.cur.cv; cv.touched = None; self._paint(pts); t = cv.touched; cv.touched = None
        if t is not None: self._show_change(t)

    def up(self, e):
        if hasattr(self, "guide") and self.guide.get() != "Off" and self.guide_move.get(): self._guide_drag = None; return
        if self.tool == "move": self._pan0 = None; return
        if self.tool == "text" or self.tool in SEL_TOOLS or self.tool == "crop": return self.x_up(e, self.to_img(e))
        if self._tick_job is not None: self.after_cancel(self._tick_job); self._tick_job = None
        if self._live() and len(getattr(self, "_raw", [])) >= 2:                   # the last bit, right to where you let go (smoothing lags behind)
            q = self._snap_pt(self.to_img(e)); last = self._raw[-1]; self._pending.append(last)
            if math.hypot(q[0] - last[0], q[1] - last[1]) > 0.5: self._pending.append((q[0], q[1], last[2]))
        self._tick()
        p = self.to_img(e); t = self.tool
        if t in ("line", "rect", "oval") + GRAD_TOOLS and getattr(e, "state", 0) & 0x1: p = self._constrain(self.start, p)
        if t in ("brush", "eraser") and self.points: self._last_end = (p[0], p[1], 1.0)     # (Shift + click carries on from here)
        if t in ("line", "rect", "oval"):
            if self._edit is None: self._begin_edit()
            self._paint(self._shape_pts(t, self.start, p))
        elif t == "brush" and self.brush in WHOLE_STROKE and len(self.points) > 1: self._paint(self.points); self._dirty = None   # whole-stroke brushes: check everywhere
        elif t in GRAD_TOOLS:
            if self._edit is None: self._begin_edit()
            self.cv.delete("shape"); self._gradient(self.start, p, radial=t == "gradient_radial")
        if t in ("line", "rect", "oval") + GRAD_TOOLS: self._dirty = None
        try: self.cur.cv.end_stroke()
        except Exception: pass
        self.points = []; self._pending = []; self._snap = None
        r = self._commit_edit()
        if r: self._recomp(r)                                                    # exactly what changed, even far-flung splatter
        self._draw()

    def _constrain(self, a, b):
        """Shift held: lines and gradients turn in 15-degree steps, rectangles become squares, ovals circles"""
        dx, dy = b[0] - a[0], b[1] - a[1]
        if self.tool in ("rect", "oval"): m = max(abs(dx), abs(dy)); return (a[0] + math.copysign(m, dx or 1), a[1] + math.copysign(m, dy or 1), b[2])
        L = math.hypot(dx, dy); ang = round(math.atan2(dy, dx) / (math.pi / 12)) * (math.pi / 12)
        return (a[0] + math.cos(ang) * L, a[1] + math.sin(ang) * L, b[2])

    def _straight(self, a, b):
        """paint a straight line from a to b with the current brush (one Undo step)"""
        self._begin_edit(); self.cur.cv.begin_stroke(self._edit[1], self._edit[2])
        try:
            n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 3))
            self._paint([(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n, 1.0) for i in range(n + 1)])
        finally: self.cur.cv.end_stroke()
        self._last_end = (b[0], b[1], 1.0); self._dirty = None; r = self._commit_edit()
        if r: self._recomp(r)
        self._draw()

    def _shape_pts(self, t, a, b):
        (x0, y0, _), (x1, y1, _) = a, b
        if t == "line": n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 6)); return [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n, 1.0) for i in range(n + 1)]
        if t == "rect":
            c = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]; out = []
            for (ax, ay), (bx, by) in zip(c, c[1:]):
                n = max(2, int(math.hypot(bx - ax, by - ay) / 6)); out += [(ax + (bx - ax) * i / n, ay + (by - ay) * i / n, 1.0) for i in range(n)]
            return out + [(x0, y0, 1.0)]
        cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, abs(x1 - x0) / 2, abs(y1 - y0) / 2; n = max(24, int((rx + ry) / 3))
        return [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n), 1.0) for i in range(n + 1)]

    def _preview_shape(self, a, b):
        """the outline while dragging a shape: drawn on top of the view (the picture itself isn't redrawn)"""
        ox, oy, z = self._geom(); (X0, Y0), (X1, Y1) = self._to_scr(a[0], a[1]), self._to_scr(b[0], b[1]); col = "#%02x%02x%02x" % self.color
        if self._turned() and self.tool in ("rect", "oval"):                     # a turned view: the outline as the picture sees it
            pts = self._shape_pts(self.tool, a, b)[::2]; self.cv.create_line(*[c_ for q in pts for c_ in self._to_scr(q[0], q[1])], fill=col, width=2, tags="shape"); return
        if self.tool in GRAD_TOOLS:                                              # the gradient's line (and its reach, for a radial one)
            self.cv.create_line(X0, Y0, X1, Y1, fill=col, width=2, arrow="last", tags="shape")
            if self.tool == "gradient_radial": r = math.hypot(X1 - X0, Y1 - Y0); self.cv.create_oval(X0 - r, Y0 - r, X0 + r, Y0 + r, outline=col, dash=(4, 4), tags="shape")
            return
        {"line": self.cv.create_line, "rect": self.cv.create_rectangle, "oval": self.cv.create_oval}[self.tool](X0, Y0, X1, Y1, outline=col, width=2, tags="shape") if self.tool != "line" \
            else self.cv.create_line(X0, Y0, X1, Y1, fill=col, width=2, tags="shape")

    def _fill(self, p, pattern=False):
        """the paint bucket: the area of about the same colour (Tolerance), from the whole picture or this layer (Fill from).
        pattern=True fills it with the last pattern you used, in your colour"""
        from scipy.ndimage import label, binary_dilation
        x, y = int(p[0]), int(p[1]); w, h = self.size_wh
        if not (0 <= x < w and 0 <= y < h): return
        if self.fill_sample.get() == "This layer":
            L = self.cur.cv; src = np.dstack([L.a * L.alpha[..., None], L.alpha[..., None] * 255]).astype(np.float32)
        else: src = self._comp.astype(np.float32)
        tol = 1 + self.gopts["tolerance"] / 100 * 255 * src.shape[2] * 0.45
        same = np.abs(src - src[y, x]).sum(2) < tol; lab, _ = label(same); m = lab == lab[y, x]
        m = binary_dilation(m, iterations=1).astype(np.float32) * self.opacity          # covers the anti-aliased edge
        k = self._sel_full()
        if k is not None: m = m * k                                                  # inside the selection only
        if pattern:
            pat = brush_art.pattern(self._last_pattern); m = m * pat[np.arange(h)[:, None] % pat.shape[0], np.arange(w)[None, :] % pat.shape[1]]
        self.cur.cv._blend(0, h, 0, w, m, self.color, "normal")

    def _gradient(self, a, b, radial=False):
        """your colour fading to clear: along the line you dragged (Gradient) or out from where you started (Gradient Fill)"""
        w, h = self.size_wh; dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
        if L2 < 4: return
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        t = np.sqrt((xx - a[0]) ** 2 + (yy - a[1]) ** 2) / math.sqrt(L2) if radial else ((xx - a[0]) * dx + (yy - a[1]) * dy) / L2
        m = np.clip(1 - t, 0, 1) * self.opacity; keep = None
        if self.sel is not None and self.sel.get("float") is None:                   # inside the selection only
            x0, y0, x1, y1 = self.sel["box"]; keep = np.zeros((h, w), np.float32); keep[y0:y1, x0:x1] = self._sel_mask(self.sel["kind"], x1 - x0, y1 - y0); m = m * keep
        if self.grad_to.get() == "2nd color":                                       # your second colour underneath, your colour fading over it
            under = np.full((h, w), self.opacity, np.float32) * (keep if keep is not None else 1); self.cur.cv._blend(0, h, 0, w, under, self.color2, "normal")
        self.cur.cv._blend(0, h, 0, w, m, self.color, "normal")

    def _poly_click(self, p):
        """Polygon / Polyline / Curve: each click adds a point; double-click or Enter draws it with your brush, Esc cancels"""
        if self._poly and math.hypot(p[0] - self._poly[-1][0], p[1] - self._poly[-1][1]) < 2 / max(self.zoom or 1, 0.01): return
        self._poly = (self._poly or []) + [p]; self._poly_preview()

    def _poly_path(self, pts, closed):
        P = [(q[0], q[1]) for q in pts]
        if closed and len(P) > 2: P = P + [P[0]]
        if self.tool == "curve_tool" and len(P) > 2:                                # a smooth curve through every point (Catmull-Rom)
            Q = [P[0]] + P + [P[-1]] if not closed else [P[-2]] + P + [P[1]]; out = []
            for i in range(1, len(Q) - 2):
                p0, p1, p2, p3 = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]; n = max(4, int(math.hypot(p2[0] - p1[0], p2[1] - p1[1]) / 3))
                for k in range(n):
                    t = k / n; t2, t3 = t * t, t * t * t
                    out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
            P = out + [P[-1]]
        res = []
        for (ax, ay), (bx, by) in zip(P, P[1:]):
            n = max(1, int(math.hypot(bx - ax, by - ay) / 3)); res += [(ax + (bx - ax) * i / n, ay + (by - ay) * i / n, 1.0) for i in range(n)]
        return res + [(P[-1][0], P[-1][1], 1.0)]

    def _poly_preview(self, cursor=None):
        self.cv.delete("poly")
        if not self._poly: return
        pts = self._poly + ([cursor] if cursor is not None else []); path = self._poly_path(pts, closed=self.tool == "polygon" and cursor is None)
        col = "#%02x%02x%02x" % self.color
        if len(path) > 1: self.cv.create_line(*[c for q in path for c in self._to_scr(q[0], q[1])], fill=col, width=2, tags="poly")
        for q in self._poly: X, Y = self._to_scr(q[0], q[1]); self.cv.create_rectangle(X - 3, Y - 3, X + 3, Y + 3, outline="white", fill=col, tags="poly")

    def _poly_finish(self, cancel=False):
        pts = self._poly; self._poly = None
        try: self.cv.delete("poly")
        except tk.TclError: pass
        if cancel or not pts or len(pts) < 2: return
        self._begin_edit(); brush_tool = self.tool; self.tool = "brush"
        try: self._paint(self._poly_path(pts, closed=brush_tool == "polygon"))
        finally: self.tool = brush_tool
        self._dirty = None; r = self._commit_edit()
        if r: self._recomp(r)
        self._draw()

    def _text(self, p, s):
        h, w = self.cur.cv.h, self.cur.cv.w; mask = Image.new("L", (w, h), 0); d = ImageDraw.Draw(mask)
        try: f = ImageFont.truetype(os.path.join(HERE, "fonts", "EBGaramond-SemiBold.ttf"), max(10, self.size * 2))
        except Exception: f = ImageFont.load_default()
        d.text((p[0], p[1]), s, font=f, fill=255); m = np.asarray(mask, np.float32) / 255 * self.opacity
        self.cur.cv._blend(0, h, 0, w, m, self.color, "normal")

    # ------------------------------------------------------------------ brushes
    def _start_tiles(self):
        if not self._tiles_started: self._tiles_started = True; self.after(80, self._fill_tiles, list(self._live_tiles))

    def _fill_tiles(self, todo):
        """real strokes from the brush engine for every brush that exists, one at a time so the window stays responsive"""
        if not todo or not self.winfo_exists(): return
        key, n = todo.pop(0); c = brushes.Canvas(150, 46, paper=(244, 238, 226))
        thin = any(w in n.lower() for w in ("pen", "pencil", "script", "liner", "detail"))
        try: c.stroke([(12 + t * 126, 23 + math.sin(t * 6.3) * 10, 0.5 + 0.5 * math.sin(math.pi * t)) for t in np.linspace(0, 1, 18)], n, color=(70, 52, 120), size=6 if thin else 14)
        except Exception: pass
        self._set_tile(key, c.image())
        if n == self.brush: self.tiles[key].configure(highlightbackground=T.PALETTE["border"])
        self.after(5, self._fill_tiles, todo)

    def _preview(self):
        """brush preview, at most ~25 times a second while a slider or the colour is being dragged"""
        if self._pv_job is None: self._pv_job = self.after(40, self._preview_now)

    def _fit_preview(self, pinned):
        pw = max(80, int((pinned.winfo_width() - 6) * 0.62))                     # the brush picture smaller: more room for the brush list
        if abs(pw - self._pw) > 2: self._pw = pw; self._preview()

    def _preview_now(self):
        self._pv_job = None
        if not hasattr(self, "preview"): return
        pic = getattr(self, "_art_by_engine", {}).get(self.brush)
        if pic is not None:                                                          # the brush's new picture (painted tile or strip)
            if pic.mode == "RGBA": im = pic.resize((self._pw, max(20, round(self._pw * UA.TILE_SIZE[1] / UA.TILE_SIZE[0]))), Image.LANCZOS)
            else:
                ph = max(20, round(self._pw * 46 / 200)); r = self._pw / ph
                if pic.width / pic.height > r: nw = round(pic.height * r); pic = pic.crop(((pic.width - nw) // 2, 0, (pic.width - nw) // 2 + nw, pic.height))
                else: nh = round(pic.width / r); pic = pic.crop((0, (pic.height - nh) // 2, pic.width, (pic.height - nh) // 2 + nh))
                im = pic.convert("RGB").resize((self._pw, ph), Image.LANCZOS)
            self._pv = ImageTk.PhotoImage(im); self.preview.configure(image=self._pv, width=im.width, height=im.height, bg=self.preview.master["bg"]); return
        self.preview.configure(bg="#f4eee2")
        c = brushes.Canvas(400, 92, paper=(244, 238, 226)); s = min(self.size, 60)
        try:
            brushes.B["__live__"] = self._live_brush()
            c.stroke([(20 + t * 360, 46 + math.sin(t * 6.3) * 20, 0.5 + 0.5 * math.sin(math.pi * t)) for t in np.linspace(0, 1, 30)], "__live__", color=self.color, size=s, opacity=self.opacity)
        except Exception: pass
        finally: brushes.B.pop("__live__", None)
        ph = max(20, round(self._pw * 46 / 200)); self._pv = ImageTk.PhotoImage(c.image().resize((self._pw, ph), Image.LANCZOS)); self.preview.configure(image=self._pv, width=self._pw, height=ph)

    # ------------------------------------------------------------------ crash recovery: the drawing is autosaved, and offered back after a crash
    _saving = threading.Lock()

    def autosave(self, folder):
        """save the drawing (every layer, the background, layer settings) if it changed; the writing happens in the background"""
        if not self.changed or not hasattr(self, "layers") or self._edit is not None: return False      # never mid-stroke
        if not self._saving.acquire(blocking=False): return False                                       # the last save is still writing
        try:
            bg = np.clip(self.bg, 0, 255).astype(np.uint8)
            layers = [(L.name, L.visible, float(L.opacity), L.mode, np.rint(np.dstack([np.clip(L.img.a, 0, 255), L.img.alpha[..., None] * 255])).astype(np.uint8)) for L in self.layers]
            masks = [(i, np.rint(np.clip(L.maskcv.alpha, 0, 1) * 255).astype(np.uint8)) for i, L in enumerate(self.layers) if L.maskcv is not None]
            meta = dict(size=list(self.size_wh), li=self.li, layers=[dict(name=n, visible=v, opacity=o, mode=m, clip=bool(getattr(L, "clip", False)), group=self._group_of(L)) for (n, v, o, m, _), L in zip(layers, self.layers)],
                        groups={str(g): dict(name=G.name, visible=G.visible, opacity=G.opacity, mode=G.mode, collapsed=G.collapsed) for g, G in self.groups.items()})
            self.changed = False
        except Exception: self._saving.release(); raise
        def write():
            try:
                d = os.path.join(folder, "draw"); tmp = d + ".tmp"; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
                Image.fromarray(bg).save(os.path.join(tmp, "background.png"), compress_level=1)
                for i, (*_, px) in enumerate(layers): Image.fromarray(px, "RGBA").save(os.path.join(tmp, f"layer{i}.png"), compress_level=1)
                for i, mk in masks: Image.fromarray(mk).save(os.path.join(tmp, f"mask{i}.png"), compress_level=1)
                with open(os.path.join(tmp, "drawing.json"), "w") as f: json.dump(meta, f)
                shutil.rmtree(d, ignore_errors=True); os.replace(tmp, d)                  # swapped in whole, so a crash mid-save can't leave half a drawing
            except Exception:
                self.changed = True; import sys; prefs.log_error(*sys.exc_info())
            finally: self._saving.release()
        threading.Thread(target=write, daemon=True, name="DrawAutosave").start(); return True

    @staticmethod
    def has_recovery(folder): return os.path.exists(os.path.join(folder, "draw", "drawing.json"))

    def restore(self, folder):
        """load the autosaved drawing back"""
        d = os.path.join(folder, "draw")
        with open(os.path.join(d, "drawing.json")) as f: meta = json.load(f)
        w, h = meta["size"]; self.new(w, h, background=Image.open(os.path.join(d, "background.png")))
        self.layers = []
        for i, m in enumerate(meta["layers"]):
            L = Layer(w, h, m["name"]); px = np.asarray(Image.open(os.path.join(d, f"layer{i}.png")).convert("RGBA"), dtype=np.float32)
            L.img.a = px[..., :3].copy(); L.img.alpha = px[..., 3] / 255; L.visible, L.opacity, L.mode = m["visible"], m["opacity"], m["mode"]; L.clip = bool(m.get("clip", False))
            if m.get("group") is not None: L.group = int(m["group"])
            mp = os.path.join(d, f"mask{i}.png")
            if os.path.exists(mp): L.add_mask(); L.maskcv.alpha = np.asarray(Image.open(mp).convert("L"), np.float32) / 255
            self.layers.append(L)
        for g, gm in meta.get("groups", {}).items():
            G = Group(gm.get("name", "Group")); G.visible, G.opacity, G.mode, G.collapsed = gm.get("visible", True), gm.get("opacity", 1.0), gm.get("mode", "normal"), gm.get("collapsed", False)
            self.groups[int(g)] = G; self._gid = max(self._gid, int(g))
        self._tidy_groups(); self.li = min(meta.get("li", 0), len(self.layers) - 1); self._recomp(); self._layers_ui(); self.changed = True; self.fit()

    def _mask_toggle(self):
        L = self.cur
        if self.mask_var.get(): L.add_mask(); L.mask_edit = True; T.banner(self.app, "PAINTING ON THE MASK — the brush hides, the eraser brings back", "success")
        else: L.mask_edit = False
        self._layers_ui(); self._tip_redraw()
    def _mask_apply(self):
        L = self.cur
        if L.maskcv is None: return
        self._whole_snapshot(); L.img.alpha = L.shown().copy(); L.maskcv = None; L.mask_edit = False; self.mask_var.set(False); self._recomp(); self._draw(); self._layers_ui()
    def _mask_delete(self):
        L = self.cur
        if L.maskcv is None: return
        self._whole_snapshot(); L.maskcv = None; L.mask_edit = False; self.mask_var.set(False); self._recomp(); self._draw(); self._layers_ui()

    def _set_clip(self):
        L = self.cur; L.clip = bool(self.clip_var.get()); self._recomp(); self._draw(); self.changed = True

    # ------------------------------------------------------------------ layers
    def _layers_ui(self):
        if getattr(self, "_artp", False): return self._layers_ui_art()
        for w in self.layer_box.winfo_children(): w.destroy()
        for i in range(len(self.layers) - 1, -1, -1):
            L = self.layers[i]; sel = i == self.li
            r = tk.Frame(self.layer_box, bg=T.PALETTE["button"] if sel else T.PALETTE["field"], highlightthickness=T.HL,
                         highlightbackground=T.PALETTE["border"] if sel else T.PALETTE["panel2"]); r.pack(fill="x", pady=1)
            eye = tk.Label(r, text="●" if L.visible else "○", fg="white", bg=r["bg"], font=T.f(12), cursor="hand2"); eye.pack(side="left", padx=4)
            eye.bind("<Button-1>", lambda e, i=i: self._toggle_vis(i))
            nm = tk.Label(r, text=f"{L.name}", fg="white", bg=r["bg"], font=T.f(9), anchor="w", width=12, cursor="hand2"); nm.pack(side="left")
            tk.Label(r, text=f"{int(L.opacity * 100)}% {L.mode[:4]}", fg=T.PALETTE["muted"], bg=r["bg"], font=T.f(8)).pack(side="right", padx=4)
            for wdg in (r, nm): wdg.bind("<Button-1>", lambda e, i=i: self._select(i))
        tk.Label(self.layer_box, text="  Background", fg=T.PALETTE["muted"], bg=T.PALETTE["field"], font=T.f(9), anchor="w").pack(fill="x", pady=1)
        L = self.cur; self._in_layers_ui = True
        src = self.groups[self.sel_group] if getattr(self, "sel_group", None) is not None and self.sel_group in self.groups else L
        try:
            self.mode.set(src.mode)
            if hasattr(self, "clip_var") and self.clip_var.get() != getattr(L, "clip", False): self.clip_var.set(getattr(L, "clip", False))
            if hasattr(self, "mask_var") and self.mask_var.get() != L.mask_edit: self.mask_var.set(L.mask_edit)
        finally: self._in_layers_ui = False
        self.lop_s.value = src.opacity; self.lop_s._draw(); self.lop_lbl.configure(text=f"{int(src.opacity * 100)}%")

    def _select(self, i): self.li = i; self.sel_group = None; self._layers_ui()
    def _picture_changed(self):
        """a layer setting or the layer stack changed: rebuild the finished picture, at most ~25 times a second"""
        self.changed = True
        if self._layer_job is None: self._layer_job = self.after(40, self._picture_now)
    def _picture_now(self):
        self._layer_job = None
        if hasattr(self, "_comp"): self._recomp(); self._draw()
    def _toggle_vis(self, i): self.layers[i].visible = not self.layers[i].visible; self._layers_ui(); self._picture_changed()
    def _set_layer(self, **kw):
        if not hasattr(self, "layers") or self._in_layers_ui: return
        target = self.groups[self.sel_group] if getattr(self, "sel_group", None) is not None else self.cur       # a picked group: its own blend / opacity
        for k, v in kw.items(): setattr(target, k, v)
        if "opacity" in kw: self.lop_lbl.configure(text=f"{int(target.opacity * 100)}%")
        if self._ui_job is None: self._ui_job = self.after(120, self._layers_ui_later)          # the list's "%" text, not on every slider move
        self._picture_changed()
    def _layers_ui_later(self): self._ui_job = None; self._layers_ui()
    def add_layer(self):
        w, h = self.size_wh; L = Layer(w, h, f"Layer {len(self.layers) + 1}"); L.group = self._group_of(self.cur)      # a new layer goes in with the one you're on
        self.layers.insert(self.li + 1, L); self.li += 1; self.sel_group = None; self._layers_ui()
    def dup_layer(self):
        w, h = self.size_wh; src = self.cur; L = Layer(w, h, src.name + " copy"); L.img.a, L.img.alpha = src.img.a.copy(), src.img.alpha.copy()
        if src.maskcv is not None: L.add_mask(); L.maskcv.alpha = src.maskcv.alpha.copy()
        L.opacity, L.mode = src.opacity, src.mode; L.group = self._group_of(src); self.layers.insert(self.li + 1, L); self.li += 1; self._layers_ui(); self._picture_changed()
    def del_layer(self):
        if getattr(self, "sel_group", None) is not None: return self.delete_group()      # a picked group goes with its layers
        if len(self.layers) == 1: self.cur.mask_edit = False; self.cur.maskcv = None; self._begin_edit(); self.cur.cv.alpha[:] = 0; self._commit_edit()
        else: self.layers.pop(self.li); self.li = max(0, self.li - 1)
        self.undo_stack = [u for u in self.undo_stack if u[0] < len(self.layers)]; self._layers_ui(); self._picture_changed()
    def merge_down(self):
        if getattr(self, "sel_group", None) is not None: return self.merge_group()       # a picked group: flattened into one layer
        if self.li == 0: return
        top, low = self.layers[self.li], self.layers[self.li - 1]
        a_t = (top.shown() * top.opacity)[..., None]; a_l = low.shown()[..., None]          # (masks are applied first)
        col = blend_layer(low.img.a.copy(), top) if top.mode != "normal" else top.img.a
        out_a = a_l + a_t * (1 - a_l)
        low.img.a = (low.img.a * a_l * (1 - a_t) + col * a_t) / np.maximum(out_a, 1e-4); low.img.alpha = out_a[..., 0]; low.maskcv = None; low.mask_edit = False
        self.layers.pop(self.li); self.li -= 1; self.undo_stack = [u for u in self.undo_stack if u[0] < len(self.layers)]; self._layers_ui(); self._picture_changed()
    def move_layer(self, d):
        j = self.li + d
        if getattr(self, "sel_group", None) is not None: return self.move_group(d)       # a picked group moves as one
        if 0 <= j < len(self.layers):
            self.layers[self.li], self.layers[j] = self.layers[j], self.layers[self.li]; self.li = j; self.undo_stack.clear()
            self._tidy_groups(); self._layers_ui(); self._picture_changed()

    # ------------------------------------------------------------------ colour
    def _swatch_row(self, parent, colors, size, side=None, **pack):
        row = tk.Frame(parent, bg=parent["bg"]); row.pack(side=side, anchor="w", **pack)
        for c in colors:
            b = tk.Frame(row, width=size, height=size, bg="#%02x%02x%02x" % c, cursor="hand2", highlightthickness=1, highlightbackground="#0d1220")
            b.pack(side="left", padx=1); b.bind("<Button-1>", lambda e, c=c: (self.set_color(c), self._remember()))
        return row

    def _paint_my_colors(self):
        """the MY COLORS slots (empty ones show as a faint +) and the picture's colours"""
        if not hasattr(self, "_my_lbls"): return
        W, H = self._apx(self._my_cw), self._apx(20); self._my_ph = []
        def pic(c):
            if c is None:
                im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); d.rectangle((0, 0, W - 1, H - 1), outline=T.PALETTE["border"])
                d.text((W / 2, H / 2), "+", fill=T.PALETTE["border"], anchor="mm"); return im
            return AP.swatch(c, W, H)
        blank = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for i, lb in enumerate(self._my_lbls):                                    # kept colours, then empty slots (a faint + adds yours)
            ph = ImageTk.PhotoImage(pic(self.my_colors[i] if i < len(self.my_colors) else None)); self._my_ph.append(ph); lb.configure(image=ph, width=W, height=H)
        for i, lb in enumerate(self._pic_lbls):                                   # the picture's colours (empty until From picture)
            ph = ImageTk.PhotoImage(pic(self.pic_colors[i]) if i < len(self.pic_colors) else blank); self._my_ph.append(ph); lb.configure(image=ph, width=W, height=H)
        if getattr(self, "_cfit", None): self.after(30, self._cfit)                  # the Color view's scroll room includes the new rows

    def swap_colors(self):
        c1, c2 = self.color, self.color2; self.color2 = c1; self.set_color(c2)
    def default_colors(self):
        self.color2 = (255, 255, 255); self.set_color((0, 0, 0))

    def _sync_csl(self):
        """the colour sliders show the current colour"""
        rows = getattr(self, "_csl", None)
        if not rows: return
        h, s_, v = colorsys.rgb_to_hsv(*(c / 255 for c in self.color)); vals = dict(h=h, s=s_, v=v, r=self.color[0] / 255, g=self.color[1] / 255, b=self.color[2] / 255)
        for k, row in rows.items():
            if k != self._csl_busy: self._sync_slider(row, vals[k])
            row.var.set(str(int(round(vals[k] * row.top))))

    def _csl_set(self, key, v):
        v = min(1.0, max(0.0, v)); c = list(self.color)
        if key in "rgb": c["rgb".index(key)] = int(round(v * 255))
        else:
            h, s_, vv = colorsys.rgb_to_hsv(*(x / 255 for x in self.color))
            if key == "h": h = v
            elif key == "s": s_ = v
            else: vv = v
            if key == "h" and s_ < 0.02: s_ = 0.6                                   # a grey has no hue: give it some colour to turn
            c = [int(round(x * 255)) for x in colorsys.hsv_to_rgb(h % 1.0, s_, vv)]
        self._csl_busy = key
        try: self.set_color(tuple(c))
        finally: self._csl_busy = None
        if key == "h": self.h = v; self._draw_wheel()

    def _random_color(self):
        import random as _r
        self.set_color(tuple(int(x * 255) for x in colorsys.hsv_to_rgb(_r.random(), _r.uniform(0.55, 1.0), _r.uniform(0.6, 1.0)))); self._remember()

    def set_color(self, rgb):
        self.color = tuple(int(c) for c in rgb[:3]); self.h, self.s, self.v = colorsys.rgb_to_hsv(*(c / 255 for c in self.color))
        hx = "#%02X%02X%02X" % self.color; self.hexv.set(hx)
        if getattr(self, "_artp", False): self._art_paint(self.swatch)
        else: self.swatch.configure(bg=hx)
        if not getattr(self, "_quiet_wheel", False): self._draw_wheel()           # dragging on the wheel redraws it once, after
        self._sync_csl(); self._preview()
    def _remember(self, add=True):
        if add:
            if self.color in self.history: self.history.remove(self.color)
            self.history.insert(0, self.color); self.history = self.history[:10]
        for w in self.hist_row.winfo_children(): w.destroy()
        if getattr(self, "_artp", False):                                      # painted swatches, up to 8, shown while HISTORY is on
            if not self._show_hist: return
            cw = (self._IW - 7 * 3) // 8                                         # always 8 slots: white until a colour fills it, newest first
            for c in self.history[:8] + [None] * (8 - len(self.history[:8])):
                cc = c or (255, 255, 255)
                lb = self._art(self._art_label(self.hist_row), lambda b, cc=cc: AP.photo(("swh", cc, self._apx(cw), self._apx(18)), lambda: AP.swatch(cc, self._apx(cw), self._apx(18))), hover=False)
                lb.pack(side="left", padx=1)
                if c is not None: lb.bind("<Button-1>", lambda e, c=c: self.set_color(c))
            return
        for c in self.history[:8] + [None] * (8 - len(self.history[:8])):
            b = tk.Label(self.hist_row, width=2, height=1, bg="#%02x%02x%02x" % (c or (255, 255, 255)), cursor="hand2" if c else ""); b.pack(side="left", padx=1)
            if c is not None: b.bind("<Button-1>", lambda e, c=c: self.set_color(c))
    def _hex_in(self):
        s = self.hexv.get().strip().lstrip("#")
        if len(s) == 6:
            try: self.set_color(tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))); self._remember()
            except ValueError: pass
    WHEEL = 156                                                                  # design size of the colour wheel; it scales with the window
    def _wsize(self): return self._wS if getattr(self, "_artp", False) else max(80, int(round(self.WHEEL * T.Z)))

    def _draw_wheel(self):
        if getattr(self, "_artp", False): return self._draw_wheel_art()
        S = self._wsize(); c = S / 2; k = S / 200; key = (round(self.h, 3), S)
        if int(self.wheel.cget("width")) != S: self.wheel.configure(width=S, height=S)
        if self._wheel_cache[0] == key: self._wph = self._wheel_cache[1]; self.wheel.delete("all"); self.wheel.configure(bg=self.wheel.master["bg"]); self.wheel.create_image(0, 0, image=self._wph, anchor="nw")
        else: self._build_wheel(S, c, key)
        a = self.h * 2 * np.pi; sq0, sq1 = c - 52 * k, c + 52 * k; m = 6 * k
        self.wheel.create_oval(c + 88 * k * math.cos(a) - m, c + 88 * k * math.sin(a) - m, c + 88 * k * math.cos(a) + m, c + 88 * k * math.sin(a) + m, outline="white", width=2)
        px, py = sq0 + self.s * (sq1 - sq0), sq0 + (1 - self.v) * (sq1 - sq0); self.wheel.create_oval(px - m, py - m, px + m, py + m, outline="white", width=2)
    def _build_wheel(self, S, c, key):
        k = S / 200; yy, xx = np.mgrid[0:S, 0:S]; r = np.hypot(xx - c, yy - c); ang = (np.arctan2(yy - c, xx - c) / (2 * np.pi)) % 1
        img = np.zeros((S, S, 4), np.uint8); ring = (r > 78 * k) & (r < 98 * k)
        hsv = np.stack([ang, np.ones_like(ang), np.ones_like(ang)], -1)
        rgb = np.zeros((S, S, 3)); i = (ang * 6).astype(int) % 6; f = ang * 6 - (ang * 6).astype(int); q, t_ = 1 - f, f
        for n, (R, G, B) in enumerate(((1, t_, 0), (q, 1, 0), (0, 1, t_), (0, q, 1), (t_, 0, 1), (1, 0, q))):
            sel = i == n
            for ch, val in enumerate((R, G, B)): rgb[..., ch] = np.where(sel, val if np.isscalar(val) else val, rgb[..., ch])
        img[ring, :3] = (rgb[ring] * 255).astype(np.uint8); img[ring, 3] = 255
        sq0, sq1 = c - 52 * k, c + 52 * k; sx = np.clip((xx - sq0) / (sq1 - sq0), 0, 1); sy = 1 - np.clip((yy - sq0) / (sq1 - sq0), 0, 1); inside = (xx >= sq0) & (xx <= sq1) & (yy >= sq0) & (yy <= sq1)
        hue = np.array(colorsys.hsv_to_rgb(self.h, 1, 1)); sqc = (sy[..., None] * ((1 - sx[..., None]) + sx[..., None] * hue)) * 255
        img[inside, :3] = sqc[inside].astype(np.uint8); img[inside, 3] = 255
        self._wph = ImageTk.PhotoImage(Image.fromarray(img, "RGBA")); self._wheel_cache = (key, self._wph)
        self.wheel.delete("all"); self.wheel.configure(bg=self.wheel.master["bg"]); self.wheel.create_image(0, 0, image=self._wph, anchor="nw")
    def _wheel_pick(self, e):
        if getattr(self, "_artp", False): return self._wheel_pick_art(e)
        S = self._wsize(); c = S / 2; k = S / 200; r = math.hypot(e.x - c, e.y - c); sq0 = c - 52 * k
        if self._wheel_target is None: self._wheel_target = "ring" if r > 70 * k else "square"
        if self._wheel_target == "ring": self.h = (math.atan2(e.y - c, e.x - c) / (2 * math.pi)) % 1
        else: self.s = min(1, max(0, (e.x - sq0) / (104 * k))); self.v = min(1, max(0, 1 - (e.y - sq0) / (104 * k)))
        rgb = tuple(int(x * 255) for x in colorsys.hsv_to_rgb(self.h, self.s, self.v)); h, s, v = self.h, self.s, self.v
        self._quiet_wheel = True
        try: self.set_color(rgb)
        finally: self._quiet_wheel = False
        self.h, self.s, self.v = h, s, v; self._draw_wheel()
