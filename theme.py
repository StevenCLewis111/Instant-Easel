"""
theme.py: the app's look. Navy panels framed in green, yellow underlined monospace titles, blue buttons with a green focus
outline, red close/danger buttons, toggle switches, rainbow hue sliders and key-hint footers. Colours come from PALETTE and can
be changed live from the Theme tab (border/text hue, background hue, panel opacity).
"""
import colorsys, tkinter as tk

PALETTE = dict(bg="#11151f", panel="#1a2033", panel2="#141a2a", border="#22e05a", title="#f5c400", text="#e8e8ec",
               muted="#9aa0b4", button="#28498c", button_hi="#335bb0", danger="#d9374b", danger_hi="#ef4b5f",
               toggle_on="#28a745", toggle_off="#2b3a5c", field="#0d1220", tab="#2b4a8b", tab_active="#1a2033")
FAMILY = "Courier New"                                   # replaced by Courier Prime (bundled, heavier bold) once init_fonts() runs
SCALE = 1.0                                              # Settings > Display > Text size
Z = 1.0                                                  # window zoom (set by the app; 1.0 = design size)
def f(size, *extra): return (FAMILY, max(6, int(round(size * SCALE))), "bold", *extra)  # every font in the app is bold
MONO = f(11); MONO_S = f(10); TITLE = f(16, "underline"); BIG = f(22)

def init_fonts(root):
    """load the bundled Courier Prime (SIL Open Font License) for this app only, then use it everywhere"""
    global FAMILY, MONO, MONO_S, TITLE, BIG
    import os, sys, tkinter.font as tkf
    here = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for name in ("CourierPrime-Bold.ttf", "CourierPrime-Regular.ttf"):
        path = os.path.join(here, "fonts", name)
        if sys.platform == "win32" and os.path.exists(path):
            try:
                import ctypes; ctypes.windll.gdi32.AddFontResourceExW(path, 0x10, 0)   # FR_PRIVATE: only this app sees it
            except Exception: pass
    if "Courier Prime" in tkf.families(root): FAMILY = "Courier Prime"
    MONO = f(11); MONO_S = f(10); TITLE = f(16, "underline"); BIG = f(22)
    return FAMILY
_listeners = []

# ---------------------------------------------------------------- smooth changes
# defer(): run a layout job once things stop changing (many resize events in a row = one run). flush(): run every waiting job now,
# so a page switch / zoom finishes its layout before anything is painted. frozen(): no painting at all while a change is made
# (Windows), then one clean repaint of the finished result: no half-built frames, no jumping.
_deferred = {}
def defer(widget, name, ms, fn):
    key = (id(widget), name); old = _deferred.pop(key, None)
    if old:
        try: widget.after_cancel(old[0])
        except Exception: pass
    def run():
        if _deferred.get(key, (None,))[0] == job_id[0]: _deferred.pop(key, None)
        try: fn()
        except tk.TclError: pass
    job_id = [None]; job_id[0] = widget.after(ms, run); _deferred[key] = (job_id[0], widget, run)

def flush(root=None, rounds=4):
    """run all waiting layout jobs now (repeating while they cause new ones), with the geometry brought up to date in between"""
    for _ in range(rounds):
        if root is not None:
            try: root.update_idletasks()
            except tk.TclError: return
        if not _deferred: return
        jobs = list(_deferred.items()); _deferred.clear()
        for key, (jid, w, run) in jobs:
            try: w.after_cancel(jid)
            except Exception: pass
            try: run()
            except Exception: pass

class frozen:
    """with T.frozen(root): ...   the change is made in one go and every waiting layout job runs before anything is painted, so
    the first frame shown is the finished one. (Earlier versions also switched Windows painting off; that hid the whole window
    for a moment, so it's gone.)"""
    def __init__(self, root): self.root = root
    def __enter__(self): return self
    def __exit__(self, *exc):
        try: flush(self.root)
        except Exception: pass
        return False

_zoom_listeners = []
def on_change(fn, zoom=False):
    """fn runs when the theme colours change; with zoom=True also when the zoom changes (it draws itself at a size that depends on Z)"""
    _listeners.append(fn)
    if zoom: _zoom_listeners.append(fn)

def hue_hex(h, s=0.85, v=0.9):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v); return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))

def set_border_hue(h):
    PALETTE["border"] = hue_hex(h, 0.85, 0.9); PALETTE["title"] = hue_hex((h + 0.5) % 1 if False else 0.135, 1.0, 0.96); _notify()

def set_background_hue(h, opacity=1.0):
    base = colorsys.hsv_to_rgb(h % 1.0, 0.45, 0.16 + 0.06 * opacity)
    PALETTE["panel"] = "#%02x%02x%02x" % tuple(int(c * 255) for c in base)
    p2 = colorsys.hsv_to_rgb(h % 1.0, 0.45, 0.12 + 0.05 * opacity); PALETTE["panel2"] = "#%02x%02x%02x" % tuple(int(c * 255) for c in p2)
    f = colorsys.hsv_to_rgb(h % 1.0, 0.5, 0.09); PALETTE["field"] = "#%02x%02x%02x" % tuple(int(c * 255) for c in f); _notify()

def _lighter(hexcol, t):
    """hexcol mixed toward white by t (0..1)"""
    r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(int(c + (255 - c) * t) for c in (r, g, b))

def _notify(zoom_only=False):
    """tell the widgets: everything after a colour change, only the size-drawn ones after a zoom change"""
    group = _zoom_listeners if zoom_only else _listeners
    for fn in list(group):
        try: fn()
        except tk.TclError:
            for g in (_listeners, _zoom_listeners):
                if fn in g: g.remove(fn)

class Panel(tk.Frame):
    """navy panel framed in the border colour"""
    def __init__(self, master, pad=14, inner=False, **kw):
        super().__init__(master, bg=PALETTE["panel2" if inner else "panel"], highlightthickness=1 if inner else 2, bd=0, padx=pad, pady=pad, **kw)
        self.inner = inner; self._style(); on_change(self._style)
    def _style(self): self.configure(bg=PALETTE["panel2" if self.inner else "panel"], highlightbackground=PALETTE["border"], highlightcolor=PALETTE["border"])

class Title(tk.Label):
    def __init__(self, master, text, big=False, **kw):
        super().__init__(master, text=text, font=BIG if big else TITLE, **kw); self._style(); on_change(self._style)
    def _style(self): self.configure(bg=self.master["bg"], fg=PALETTE["title"])

class Text(tk.Label):
    def __init__(self, master, text="", muted=False, font=None, **kw):
        super().__init__(master, text=text, font=font or MONO_S, justify="left", **kw); self.muted = muted; self._style(); on_change(self._style)
    def _style(self): self.configure(bg=self.master["bg"], fg=PALETTE["muted" if self.muted else "text"])

class Button(tk.Label):
    """blue rounded-look button; green outline on hover/focus; Enter or Space activates it"""
    def __init__(self, master, text, command=None, kind="normal", width=None, **kw):
        super().__init__(master, text=text, font=MONO, padx=14, pady=6, cursor="hand2", takefocus=1, highlightthickness=2, width=width or 0, **kw)
        self.kind = kind; self.command = command; self.enabled = True; self.hover = False
        self.bind("<Button-1>", lambda e: self.invoke()); self.bind("<Enter>", lambda e: self._set_hover(True)); self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<FocusIn>", lambda e: self._style()); self.bind("<FocusOut>", lambda e: self._style())
        self.bind("<Return>", lambda e: self.invoke()); self.bind("<space>", lambda e: self.invoke())
        self._style(); on_change(self._style)
    def _set_hover(self, h): self.hover = h; self._style()
    def _style(self):
        key = "danger" if self.kind == "danger" else "button"; hi = key + "_hi"
        bg = PALETTE[hi] if (self.hover and self.enabled) else PALETTE[key]
        focused = self.focus_get() is self if self.winfo_exists() else False
        ring = PALETTE["border"] if (self.hover or focused) and self.enabled else self.master["bg"]
        self.configure(bg=bg if self.enabled else "#2a2f3c", fg="white" if self.enabled else "#6c7080", highlightbackground=ring, highlightcolor=ring)
    def invoke(self):
        if self.enabled and self.command: self.command()
    def state(self, s):
        self.enabled = "disabled" not in str(s) or "!disabled" in str(s); self._style()

class Toggle(tk.Canvas):
    """pill switch: green on, navy off"""
    def __init__(self, master, variable, command=None, **kw):
        super().__init__(master, width=int(50 * Z), height=int(24 * Z), highlightthickness=0, cursor="hand2", **kw)
        self.var = variable; self.command = command; self.bind("<Button-1>", self.flip); self._style(); on_change(self._style, zoom=True)
        variable.trace_add("write", lambda *a: self._style())
    def flip(self, e=None):
        self.var.set(not self.var.get())
        if self.command: self.command()
    def _style(self):
        on = bool(self.var.get()); k = Z; self.configure(bg=self.master["bg"], width=int(50 * k), height=int(24 * k)); self.delete("all")
        col = PALETTE["toggle_on"] if on else PALETTE["toggle_off"]
        self.create_oval(2 * k, 2 * k, 22 * k, 22 * k, fill=col, outline=col); self.create_oval(28 * k, 2 * k, 48 * k, 22 * k, fill=col, outline=col); self.create_rectangle(12 * k, 2 * k, 38 * k, 22 * k, fill=col, outline=col)
        x = (37 if on else 13) * k; self.create_oval(x - 8 * k, 4 * k, x + 8 * k, 20 * k, fill="white", outline="white")

class HueSlider(tk.Canvas):
    """rainbow bar with a white knob (0..1)"""
    def __init__(self, master, value=0.35, command=None, width=520, **kw):
        super().__init__(master, width=int(width * Z), height=int(26 * Z), highlightthickness=0, cursor="hand2", **kw)
        self.dw = width; self.w = int(width * Z); self.value = value; self.command = command
        self.bind("<Button-1>", self._drag); self.bind("<B1-Motion>", self._drag); self._draw(); on_change(self._draw, zoom=True)
    KNOB = 9                                                     # knob radius (design pixels)
    def _ends(self):
        """the track runs between these x positions, inset by the knob's radius so the knob never goes past the edge"""
        p = (self.KNOB + 2) * Z; return p, max(p + 1, self.w - p)
    def _drag(self, e):
        a, b = self._ends(); self.value = min(1, max(0, (e.x - a) / (b - a))); self._draw()
        if self.command: self.command(self.value)
    def _draw(self):
        z = Z; self.w = int(self.dw * z); self.configure(bg=self.master["bg"], width=self.w, height=int(26 * z)); self.delete("all")
        a, b = self._ends(); step = max(2, int(2 * z))
        for x in range(int(a), int(b) + 1, step): self.create_line(x, 9 * z, x, 19 * z, fill=hue_hex((x - a) / (b - a), 0.85, 0.92), width=step)
        k = a + self.value * (b - a); r = self.KNOB * z; self.create_oval(k - r, 4 * z, k + r, 22 * z, fill="white", outline="#ddd")

_art_mod = [None]
def _art():
    """art_panel, when its pictures are there (None otherwise: the drawn look is used)"""
    if _art_mod[0] is None:
        try:
            import art_panel as ap; _art_mod[0] = ap if (ap.src("slider_knob") is not None and ap.src("scroll_up") is not None) else False
        except Exception: _art_mod[0] = False
    return _art_mod[0] or None

class PlainSlider(tk.Canvas):
    """navy track with a white knob (0..1)"""
    def __init__(self, master, value=1.0, command=None, width=520, **kw):
        super().__init__(master, width=int(width * Z), height=int(26 * Z), highlightthickness=0, cursor="hand2", **kw)
        self.dw = width; self.w = int(width * Z); self.value = value; self.command = command
        self.bind("<Button-1>", self._drag); self.bind("<B1-Motion>", self._drag); self._draw(); on_change(self._draw, zoom=True)
    KNOB = 8                                                     # knob radius (design pixels)
    def _ends(self):
        """the track runs between these x positions, inset by the knob's radius so the knob never goes past the edge"""
        p = (self.KNOB + 2) * Z; return p, max(p + 1, self.w - p)
    def _drag(self, e):
        a, b = self._ends(); self.value = min(1, max(0, (e.x - a) / (b - a))); self._draw()
        if self.command: self.command(self.value)
    def _draw(self):
        z = Z; self.w = int(self.dw * z); self.configure(bg=self.master["bg"], width=self.w, height=int(26 * z)); self.delete("all")
        ap = _art()
        if ap is not None:                                                       # the painted slider (brand/icon/panel)
            H = int(26 * z); K = int(2 * (self.KNOB + 2) * z); v = round(self.value, 3)
            self._ph = ap.photo(("psl", self.w, H, v, K), lambda: ap.slider_image(self.w, H, v, K)); self.create_image(0, 0, image=self._ph, anchor="nw"); return
        a, b = self._ends(); self.create_line(a, 13 * z, b, 13 * z, fill=PALETTE["button"], width=max(4, int(4 * z)), capstyle="round")
        k = a + self.value * (b - a); r = self.KNOB * z; self.create_oval(k - r, 5 * z, k + r, 21 * z, fill="white", outline="#ddd")

# ---- mouse wheel: scrolls the scrolling box the pointer is in: anywhere inside its border, on its divider, its gaps,
# and the whole scroll bar from arrow to arrow. Found by where the pointer is on screen, so it doesn't depend on which
# little widget Windows hands the wheel event to.
_wheel_tops = set(); _wheel_areas = []

def _wheel_units(e):
    num = getattr(e, "num", None)
    if num == 4: return -1                                                       # (Linux wheel up / down)
    if num == 5: return 1
    d = int(getattr(e, "delta", 0) or 0); return (-1 if d > 0 else 1) * max(1, abs(d) // 120)

def _on_wheel(e):
    try: px, py = e.widget.winfo_pointerxy()
    except Exception: return
    best = None
    for w in list(_wheel_areas):
        try:
            if not w.winfo_exists(): _wheel_areas.remove(w); continue
            if not w.winfo_viewable(): continue
            x, y, ww, hh = w.winfo_rootx(), w.winfo_rooty(), w.winfo_width(), w.winfo_height()
        except Exception: continue
        if x <= px < x + ww and y <= py < y + hh and (best is None or ww * hh < best[0]):
            best = (ww * hh, w)                                                  # the innermost box the pointer is in
    if best:
        best[1]._wheel_scroll(_wheel_units(e)); return "break"

def fit_scrollregion(cv):
    """a canvas's scroll region = its contents, but never smaller than the canvas itself: a list that fits can't move,
    and the scroll bar shows a full bar until there is really something hidden"""
    try:
        bb = cv.bbox("all") or (0, 0, 0, 0)
        cv.configure(scrollregion=(0, 0, max(bb[2], cv.winfo_width()), max(bb[3], cv.winfo_height())))
    except tk.TclError: pass

def wheel_area(widget, scroll):
    """make the mouse wheel anywhere over widget's rectangle (borders included) call scroll(units): -n up, +n down"""
    widget._wheel_scroll = scroll
    if widget not in _wheel_areas: _wheel_areas.append(widget)
    top = widget.winfo_toplevel(); key = str(top)
    if key not in _wheel_tops:
        _wheel_tops.add(key)
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"): top.bind(ev, _on_wheel, add="+")
    return widget

class Scrollbar(tk.Canvas):
    """theme-matching scroll bar: an arrow button at each end and a theme-coloured highlight that fills the whole track when there is
    nothing to scroll, then shrinks to show empty track on the side(s) you can still scroll. A drop-in for tk.Scrollbar."""
    def __init__(self, master, orient="vertical", command=None, **kw):
        a = max(10, int(round(14 * Z))); vertical = orient == "vertical"
        super().__init__(master, highlightthickness=0, bd=0, width=a if vertical else 10, height=10 if vertical else a, **kw)
        self.vertical, self.command, self.lo, self.hi, self._off, self._hover, self._hot, self._rep = vertical, command, 0.0, 1.0, None, False, None, None
        self.bind("<Configure>", lambda e: self._draw()); self.bind("<Enter>", lambda e: self._hov(True)); self.bind("<Leave>", lambda e: (self._hov(False), self._warm(None)))
        self.bind("<Motion>", lambda e: self._warm(self._zone(e)))
        self.bind("<ButtonPress-1>", self._press); self.bind("<B1-Motion>", self._drag); self.bind("<ButtonRelease-1>", self._release)
        self._draw(); on_change(self._draw, zoom=True)
        wheel_area(self, lambda n: self.command and self.can_scroll() and self.command("scroll", n, "units"))     # the wheel works on the bar itself too
    def set(self, lo, hi): self.lo, self.hi = float(lo), float(hi); self._draw()
    def can_scroll(self):
        """only when the contents overflow the view (the slider is then shorter than the track)"""
        return (self.hi - self.lo) < 0.999
    def _a(self): return max(10, int(round(16 * Z)))                                   # thickness, and the size of the arrow buttons
    def _total(self): return max(1, self.winfo_height() if self.vertical else self.winfo_width())
    def _len(self): return max(1, self._total() - 2 * self._a())                       # the track between the arrows
    def _thumb(self):
        L = self._len(); frac = self.hi - self.lo; size = min(L, max(int(28 * Z), int(frac * L)))
        return ((L - size) * (self.lo / (1 - frac)) if frac < 0.9999 else 0), size
    def _arrow(self, end, a, total):
        o = 0 if end == 0 else total - a; hot = self._hot == end
        fill = PALETTE["button_hi"] if hot else PALETTE["button"]
        if self.vertical: self.create_rectangle(1, o, a - 1, o + a - 1, fill=fill, outline=PALETTE["border"] if hot else PALETTE["panel"])
        else: self.create_rectangle(o, 1, o + a - 1, a - 1, fill=fill, outline=PALETTE["border"] if hot else PALETTE["panel"])
        p = (0.32, 0.66) if end == 0 else (0.68, 0.34)
        pts = [(a / 2, o + a * p[0]), (a * 0.26, o + a * p[1]), (a * 0.74, o + a * p[1])] if self.vertical else [(o + a * p[0], a / 2), (o + a * p[1], a * 0.26), (o + a * p[1], a * 0.74)]
        self.create_polygon(pts, fill="white", outline="")
    def _draw(self):
        a = self._a(); ap = _art()
        if ap is not None:                                                       # the painted scroll bar (brand/icon/panel/scroll_*)
            self.configure(bg=self.master["bg"], **(dict(width=a) if self.vertical else dict(height=a))); self.delete("all")
            total = self._total(); pos, size = self._thumb(); active = self._hover or self._off is not None
            if total > 2 * a:
                self._ph = ap.photo(("psb", a, total, int(pos), int(size), self._hot, active, self.vertical),
                                    lambda: ap.scrollbar_image(a, total, pos, size, self._hot, active, self.vertical))
                self.create_image(0, 0, image=self._ph, anchor="nw")
            return
        self.configure(bg=PALETTE["field"], **(dict(width=a) if self.vertical else dict(height=a))); self.delete("all")
        total = self._total(); pos, size = self._thumb(); active = self._hover or self._off is not None; s0 = a + pos
        fill = _lighter(PALETTE["border"], 0.3) if active else PALETTE["border"]; edge = fill                   # solid, in the highlight colour
        if self.vertical: self.create_rectangle(3, s0, a - 3, s0 + size, fill=fill, outline=edge)
        else: self.create_rectangle(s0, 3, s0 + size, a - 3, fill=fill, outline=edge)
        self._arrow(0, a, total); self._arrow(1, a, total)
    def _at(self, e): return e.y if self.vertical else e.x
    def _zone(self, e):
        c = self._at(e); return 0 if c < self._a() else 1 if c > self._total() - self._a() else None
    def _warm(self, z):
        if z != self._hot: self._hot = z; self._draw()
    def _step(self, z):
        if self.command and self.can_scroll(): self.command("scroll", 1 if z else -1, "units")
    def _tick(self, z): self._step(z); self._rep = self.after(60, self._tick, z)
    def _press(self, e):
        if not self.can_scroll(): return                                         # everything fits: arrows, track and slider do nothing
        z = self._zone(e)
        if z is not None: self._step(z); self._rep = self.after(350, self._tick, z); return          # an arrow: step, and keep stepping while held
        pos, size = self._thumb(); c = self._at(e) - self._a()
        if pos <= c <= pos + size: self._off = c - pos; self._draw()
        elif self.command: self.command("scroll", 1 if c > pos else -1, "pages")
    def _drag(self, e):
        if self._off is None or not self.command: return
        room = self._len() - self._thumb()[1]
        if room > 0: self.command("moveto", min(1.0, max(0.0, (self._at(e) - self._a() - self._off) / room)) * (1 - (self.hi - self.lo)))
    def _release(self, e):
        if self._rep: self.after_cancel(self._rep); self._rep = None
        self._off = None; self._draw()
    def _hov(self, on): self._hover = on; self._draw()

class ScrollBox(tk.Frame):
    """a scrolling list in a box: border all round, a divider, then the scroll bar in its own gutter with the same gap on every side.
        box = ScrollBox(parent, bg="panel2"); box.pack(...)
        cv = tk.Canvas(box.body, ...); cv.pack(fill="both", expand=True); box.attach(cv)"""
    GAP = 12                                                     # space round the scroll bar (design pixels; zoom scales it)
    def __init__(self, master, bg=None, **kw):
        super().__init__(master, bd=0, highlightthickness=1, **kw); self.bg_key = bg
        self.body = tk.Frame(self, bd=0, highlightthickness=0); self.body.pack(side="left", fill="both", expand=True)
        Line(self, vertical=True).pack(side="left", fill="y")
        self.gutter = tk.Frame(self, bd=0, highlightthickness=0); self.gutter.pack(side="left", fill="y")
        self.sb = Scrollbar(self.gutter); self.sb.pack(fill="y", expand=True, padx=self.GAP, pady=self.GAP)
        self._style(); on_change(self._style)
    def attach(self, widget):
        """link a scrollable widget (canvas, text) to this box's scroll bar"""
        self.sb.command = widget.yview; widget.configure(yscrollcommand=self.sb.set)
        wheel_area(self, lambda n: self.sb.can_scroll() and widget.yview_scroll(n, "units"))   # the wheel anywhere in the box scrolls it
        if isinstance(widget, tk.Canvas): widget.bind("<Configure>", lambda e: fit_scrollregion(widget), add="+")
        return widget
    def _style(self):
        bg = PALETTE[self.bg_key] if self.bg_key else self.master["bg"]
        self.configure(bg=bg, highlightbackground=PALETTE["border"], highlightcolor=PALETTE["border"])
        self.body.configure(bg=bg); self.gutter.configure(bg=bg)

class Line(tk.Frame):
    """thin divider in the border colour (follows the Theme tab and the zoom)"""
    def __init__(self, master, vertical=True, **kw):
        super().__init__(master, **kw); self.vertical = vertical; self._style(); on_change(self._style, zoom=True)
    def _style(self):
        t = max(1, int(round(Z))); self.configure(bg=PALETTE["border"], **(dict(width=t) if self.vertical else dict(height=t)))

class Tabs(tk.Frame):
    """row of tabs; the active one is dark with a green outline"""
    def __init__(self, master, names, command):
        super().__init__(master); self.command = command; self.btns = {}; self.active = names[0]
        for n in names:
            b = tk.Label(self, text=n, font=MONO, padx=18, pady=8, cursor="hand2", highlightthickness=2)
            b.pack(side="left", padx=3); b.bind("<Button-1>", lambda e, n=n: self.select(n)); self.btns[n] = b
        self._style(); on_change(self._style)
    def select(self, n): self.active = n; self._style(); self.command(n)
    def _style(self):
        self.configure(bg=self.master["bg"])
        for n, b in self.btns.items():
            act = n == self.active
            b.configure(bg=PALETTE["tab_active"] if act else PALETTE["tab"], fg="white",
                        highlightbackground=PALETTE["border"] if act else self.master["bg"], highlightcolor=PALETTE["border"])

class Field(tk.Text):
    def __init__(self, master, height=4, **kw):
        super().__init__(master, height=height, wrap="word", font=f(12), relief="flat", padx=10, pady=8, highlightthickness=1, insertbackground="white", **kw)
        self._style(); on_change(self._style)
    def _style(self): self.configure(bg=PALETTE["field"], fg="white", highlightbackground=PALETTE["border"], highlightcolor=PALETTE["border"])

class Entry(tk.Entry):
    def __init__(self, master, textvariable=None, width=30, **kw):
        super().__init__(master, textvariable=textvariable, width=width, font=f(11), relief="flat", highlightthickness=1, insertbackground="white", **kw)
        self._style(); on_change(self._style)
    def _style(self): self.configure(bg=PALETTE["field"], fg="white", highlightbackground=PALETTE["border"], highlightcolor=PALETTE["border"])

class Choice(tk.Label):
    """click to cycle through choices, shown as a blue setting button: 'CLOUDS: MANY'"""
    def __init__(self, master, label, choices, variable):
        super().__init__(master, font=MONO_S, padx=12, pady=6, cursor="hand2", takefocus=1, highlightthickness=2)
        self.label = label; self.choices = choices; self.var = variable
        self.bind("<Button-1>", self.next); self.bind("<Return>", self.next); self.bind("<Button-3>", self.prev)
        variable.trace_add("write", lambda *a: self._style()); self._style(); on_change(self._style)
    def next(self, e=None):
        c = self.choices; v = self.var.get(); self.var.set(c[(c.index(v) + 1) % len(c)] if v in c else c[0])
    def prev(self, e=None):
        c = self.choices; v = self.var.get(); self.var.set(c[(c.index(v) - 1) % len(c)] if v in c else c[0])
    def _style(self):
        v = self.var.get() or "—"; self.configure(text=(f"{self.label.upper()}: " if self.label else "") + f"{str(v).upper()}  ▸", bg=PALETTE["button"], fg="white",
                                                 highlightbackground=self.master["bg"], highlightcolor=PALETTE["border"])

class Hints(tk.Frame):
    """footer of key hints: [ENTER] GENERATE   [TAB] NEXT ..."""
    def __init__(self, master, items):
        super().__init__(master); self.items = items; self._style(); on_change(self._style)
    def _style(self):
        for c in self.winfo_children(): c.destroy()
        self.configure(bg=self.master["bg"])
        try:
            import prefs
            if not prefs.get("show_hints"): return                        # Settings > Display > Show hints
        except Exception: pass
        for key, what in self.items:
            tk.Label(self, text=f" {key} ", font=f(9), bg="#05070c", fg="#cfd3dc", relief="ridge", bd=2).pack(side="left", padx=(0, 4))
            tk.Label(self, text=what.upper(), font=f(9), bg=self.master["bg"], fg=PALETTE["muted"]).pack(side="left", padx=(0, 16))

# ---------------------------------------------------------------- banners: one place for every message in the app
# Red for anything negative (errors, warnings, "nothing to save yet"...), green for anything positive (saved, updated, downloaded...).
# Always the same spot: bottom centre of the window, over whatever page is showing. It sizes itself side to side to fit the
# message, stays 15 seconds, then goes, and only comes back if the same thing happens again. Safe to call from any thread.
#     T.banner(widget, "CHECK YOUR DRIVE — D: isn't responding")            # red
#     T.banner(widget, "SAVED — sunset.png", "success")                      # green
import threading as _threading, queue as _queue
BANNER_SECONDS = 15
BANNER_COLORS = {"error": ("#8f1d1d", "#ef5350"), "success": ("#1b6b32", "#4ee07a")}     # fill, outline
BANNER_FONT = ("Arial", 16, "bold")                                                    # design size; scales with the window
_banner_q = _queue.Queue(); _banner_roots = set()

def banner(widget, text, kind="error", seconds=BANNER_SECONDS):
    """show a message banner. kind: "success" (green) or "error" / "warning" / anything else (red)"""
    if _threading.current_thread() is _threading.main_thread(): _show_banner(widget, text, kind, seconds)
    else: _banner_q.put((widget, text, kind, seconds))                         # from a background thread: the window's own loop shows it

def banner_host(root):
    """call once with the main window: messages sent from background threads are shown from here"""
    if str(root) in _banner_roots: return
    _banner_roots.add(str(root))
    def pump():
        while True:
            try: item = _banner_q.get_nowait()
            except _queue.Empty: break
            try: _show_banner(*item)
            except Exception: pass
        try: root.after(100, pump)
        except tk.TclError: pass
    root.after(100, pump)

def _show_banner(widget, text, kind, seconds):
    try: top = widget.winfo_toplevel()
    except Exception: return
    b = getattr(top, "_banner", None)
    if b is None or not b.winfo_exists():
        b = tk.Label(top, fg="white", bd=0, justify="center", cursor="hand2")
        b.bind("<Button-1>", lambda e: _hide_banner(top)); top._banner = b; top._banner_job = None    # a click also closes it
    fill, edge = BANNER_COLORS.get(kind, BANNER_COLORS["error"])
    room = max(200, top.winfo_width() - int(80 * Z))
    b.configure(text=" ".join(str(text).split()), bg=fill, highlightbackground=edge, highlightcolor=edge, wraplength=room,
                font=BANNER_FONT, padx=14, pady=6, highlightthickness=2)            # set every time, so it's always at the window's current size
    b.place(in_=top, relx=0.5, rely=1.0, y=-max(4, int(round(12 * Z))), anchor="s"); b.tkraise()
    if getattr(top, "_banner_job", None) is not None:
        try: top.after_cancel(top._banner_job)
        except tk.TclError: pass
    top._banner_job = top.after(int(seconds * 1000), lambda: _hide_banner(top))   # a new message replaces it and restarts the 15 seconds

def _hide_banner(top):
    b = getattr(top, "_banner", None); top._banner_job = None
    if b is not None and b.winfo_exists(): b.place_forget()

_SUCCESS_WORDS = ("SAVED", "APPLIED", "ADDED", "RESTORED", "DONE", "ROLLED BACK", "UPDATED", "UPLOADED", "DOWNLOADED", "EXPORTED", "IMPORTED",
                  "LEARNED", "FINISHED", "COPIED", "SENT", "CREATED", "RESET")

def popup(master, title, message, buttons=(("OK", "normal"),)):
    """themed modal for a question that needs an answer: yellow title, message, coloured buttons -> returns the label pressed.
    A plain message (only an OK button) is shown as a banner instead, so every message in the app looks and behaves the same.
    It opens centred on the program; if the program is minimized it opens centred on the screen instead and stands on its own, because on
    Windows a pop-up that belongs to a minimized window is hidden with it (the program then looks frozen while an invisible prompt waits)."""
    if len(buttons) == 1:                                                      # nothing to choose: a banner (green if it's good news)
        kind = "success" if any(w in str(title).upper() for w in _SUCCESS_WORDS) else "error"
        banner(master, f"{title} — {message}", kind); return buttons[0][0]
    win = tk.Toplevel(master); win.withdraw(); win.configure(bg=PALETTE["panel2"]); win.resizable(False, False); res = {"v": None}
    p = Panel(win, pad=22); p.pack(fill="both", expand=True)
    Title(p, title).pack(pady=(0, 10)); Text(p, message).pack(pady=(0, 16))
    row = tk.Frame(p, bg=p["bg"]); row.pack()
    for lab, kind in buttons:
        Button(row, lab, command=lambda l=lab: (res.__setitem__("v", l), win.destroy()), kind=kind).pack(side="left", padx=10)
    try: top = master.winfo_toplevel(); away = top.state() in ("iconic", "withdrawn") or not top.winfo_viewable()
    except tk.TclError: top, away = master, False
    win.update_idletasks(); w, h = win.winfo_reqwidth(), win.winfo_reqheight(); sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    if away: win.attributes("-topmost", True); cx, cy = sw // 2, sh // 2                      # stand-alone, on top, middle of the screen
    else: win.transient(top); cx, cy = top.winfo_rootx() + top.winfo_width() // 2, top.winfo_rooty() + top.winfo_height() // 2   # middle of the program
    win.geometry(f"+{max(0, min(cx - w // 2, sw - w))}+{max(0, min(cy - h // 2, sh - h))}")
    win.deiconify(); win.lift(); win.focus_force()
    try: win.wait_visibility(); win.grab_set()
    except tk.TclError: pass
    master.wait_window(win); return res["v"]
