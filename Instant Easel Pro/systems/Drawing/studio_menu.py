"""
studio_menu.py: the drawing studio's menu bar (File, Edit, Image, Layer, Select, View, Window, Help) along its top.
The bar and its drop-downs have the studio's own background and border; the names are white and turn gold under the mouse.
Window shows or hides each section of the side panels (remembered), so the panels hold only what you use.
Every section starts with a divider line (DrawStudio._rule), so a section is that line and what comes after it up to the next one.
"""
import tkinter as tk
import numpy as np
import theme as T
import prefs

MENU_TEXT = T.MENU_WORDS     # white words; gold under the mouse
NO_HIDE = ("BRUSH OPTIONS",)   # always there
# off until you turn them on (Window), so a new picture starts with a tidy studio; the rest start on
DEFAULT_OFF = [("Color", "STICKERS"), ("Color", "MY COLORS"), ("Options", "TEXT"), ("Options", "NAVIGATOR"),
               ("Options", "CUT OUT"), ("Options", "GUIDES"), ("Options", "SAVING"), ("Options", "TIMELAPSE"), ("Adjustments", "MY BRUSHES")]
# a tool whose settings live in a section turns it on while you use it (and off again after, unless you turned it on yourself)
_SEL = [("Options", "CUT OUT"), ("Options", "FILL")]
TOOL_SECTIONS = {"text": [("Options", "TEXT")], "fill": [("Options", "FILL")], "pattern_fill": [("Options", "FILL")],
                 "gradient": [("Options", "FILL")], "gradient_radial": [("Options", "FILL")], "magic_eraser": [("Options", "FILL")],
                 "wand": _SEL, "smart": _SEL, "quick_sel": _SEL, "sel_rect": _SEL, "sel_oval": _SEL, "sel_lasso": _SEL, "crop": [("Options", "CANVAS")]}


class StudioMenu:
    # ------------------------------------------------------------------ the bar
    def _menubar(self):
        bar = self._mbar = tk.Frame(self, bg=self["bg"]); bar.pack(fill="x", pady=(0, 2))
        line = self._mline = T.Line(self, vertical=False); line.pack(fill="x", pady=(0, 6))
        self._mlabels = []; self._mopen = None
        for i, name in enumerate(("File", "Edit", "Image", "Layer", "Select", "View", "Window", "Help")):
            lb = tk.Label(bar, text=name, bg=self["bg"], fg=MENU_TEXT, cursor="hand2", bd=0)
            lb.pack(side="left", expand=True); self._mlabels.append(lb)                # (an equal share of the width each: spread across the bar)
            lb.bind("<Enter>", lambda e, i=i, l=lb: (l.configure(fg=T.PALETTE["title"]), self.after(90, lambda: self._menu_hover(i)))
                    if self.winfo_containing(*self.winfo_pointerxy()) is l else None)   # hover opens its menu (really under the mouse: closing one sends a stray Enter)
            lb.bind("<Leave>", lambda e, i=i, l=lb: l.configure(fg=MENU_TEXT) if (self._mopen is None or self._mopen[0] != i) else None)   # (white again, unless its menu is open)
            lb.bind("<Button-1>", lambda e, i=i: (self._menu_close() if self._mopen and self._mopen[0] == i else self._menu_open(i), "break")[1])
        def style():
            bar.configure(bg=self["bg"])
            for lb in self._mlabels: lb.configure(bg=self["bg"], font=T.f(10), padx=int(10 * T.Z), pady=int(3 * T.Z))
        style(); T.on_change(style, zoom=True)
        self.after_idle(self._sections_init)

    # ------------------------------------------------------------------ what's in each menu
    def _menu_defs(self, name):
        """the items: (label, shortcut, action), ("check", label, is_on, action), "-" (a line), ("head", text)"""
        sel = lambda: getattr(self, "sel", None) is not None
        if name == "File":
            return [("New picture", "", lambda: self.new(*self.size_wh)), ("Open…", "Ctrl+O", self.open), ("Place image…", "Ctrl+Shift+O", self.place_image),
                    ("Save…", "Ctrl+S", self.save), "-", ("Import stickers…", "", self.import_stickers)]
        if name == "Edit":
            return [("Undo", "Ctrl+Z", self.undo), ("Redo", "Ctrl+Y", self.redo), "-",
                    ("Cut", "Ctrl+X", lambda: sel() and (self._sel_copy(), self._sel_delete())), ("Copy", "Ctrl+C", lambda: sel() and self._sel_copy()),
                    ("Paste", "Ctrl+V", self.paste_any), ("Paste from another program", "Ctrl+Shift+V", self.paste_picture),
                    ("Delete selected", "Del", lambda: sel() and self._sel_delete()), "-",
                    ("Free Transform", "Ctrl+T", self._xf_start), "-", ("Keyboard shortcuts…", "", self._open_shortcuts)]
        if name == "Image":
            k = lambda a: self._key_label_of(a)
            return [("Canvas size…", "", lambda: self._goto_section("Options", "CANVAS")), ("Crop", k("crop"), lambda: self.set_tool("crop")), "-",
                    ("Turn view left", k("turn_left"), lambda: self._key_action("turn_left")), ("Turn view right", k("turn_right"), lambda: self._key_action("turn_right")),
                    ("Straighten view", k("straighten"), lambda: self._key_action("straighten")), ("Mirror view", k("mirror_view"), lambda: self._key_action("mirror_view")), "-",
                    ("Zoom in", "Wheel", lambda: self.zoom_by(1.25)), ("Zoom out", "Wheel", lambda: self.zoom_by(1 / 1.25)), ("Fit to window", "", self.fit), "-",
                    ("Light, color & filters… (Editing)", "", lambda: self.app.goto("Editing", "Light"))]
        if name == "Layer":
            return [("New layer", "", self.add_layer), ("Duplicate layer", "", self.dup_layer), ("Delete layer", "", self.del_layer), "-",
                    ("Merge down", "", self.merge_down), ("Move up", "", lambda: self.move_layer(1)), ("Move down", "", lambda: self.move_layer(-1)), "-",
                    ("Group layers", "", self.group_layers), ("Ungroup", "", self.ungroup), "-",
                    ("check", "Lock transparency", self.lock_alpha.get, lambda: self.lock_alpha.set(not self.lock_alpha.get()))]
        if name == "Select":
            return [("Subject", "", self.select_subject), ("Select all", "Ctrl+A", self._sel_all), ("Deselect", "Ctrl+D", lambda: sel() and (self._sel_commit(), setattr(self, "sel", None), self._x_overlay())),
                    ("Invert", "Ctrl+Shift+I", self.sel_invert), ("Refine edge", "", self.refine_selection), ("Grow / shrink…", "", lambda: self._goto_section("Options", "CUT OUT")), "-",
                    ("Remove background", "Ctrl+I", self.remove_background), ("Cut to layer", "", lambda: self.sel_to_layer(True)),
                    ("Copy to layer", "", lambda: self.sel_to_layer(False)), ("Make sticker", "", self.make_sticker)]
        if name == "View":
            return [("check", "Brushes panel", lambda: bool(self.L.winfo_manager()), lambda: self.toggle_panel(self.L)),
                    ("check", "Color / Options panel", lambda: bool(self._R.winfo_manager()), lambda: self.toggle_panel(self._R)),
                    ("check", "Studio fills the page", lambda: self._big, self.toggle_big), ("Canvas only", "Tab", self.canvas_only), "-",
                    ("Guides…", "", lambda: self._goto_section("Options", "GUIDES")), ("Navigator…", "", lambda: self._goto_section("Options", "NAVIGATOR"))]
        if name == "Window":
            out = []
            for view in ("Color", "Options", "Adjustments"):
                names = [n for v, n in self._sections if v == view]
                if not names: continue
                out.append(("head", {"Color": "COLOR SIDE", "Options": "OPTIONS SIDE", "Adjustments": "ADJUSTMENTS"}[view]))
                for n in names: out.append(("check", n.title(), lambda v=view, n=n: (v, n) not in getattr(self, "_hidden_secs", ()), lambda v=view, n=n: self._toggle_section(v, n)))
            return out + ["-", ("Show everything", "", self._show_all_sections)]
        if name == "Help":
            return [("Keyboard shortcuts…", "", self._open_shortcuts)]
        return []

    def _key_label_of(self, action):
        import draw_studio as DS
        try: return DS.key_label(DS.key_map().get(action, ""))
        except Exception: return ""

    def _open_shortcuts(self):
        try: self.app.show("Settings"); self.app.pages["Settings"].select("Shortcuts")
        except Exception: prefs.log_note("opening Settings > Shortcuts from the Help menu")

    # ------------------------------------------------------------------ the drop-down
    def _menu_open(self, i):
        self._menu_close()
        lb = self._mlabels[i]; items = self._menu_defs(lb["text"]); z = T.Z; bg = self["bg"]
        top = tk.Toplevel(self); top.withdraw(); top.overrideredirect(True)
        top.configure(bg=bg, highlightthickness=max(2, int(2 * z)), highlightbackground=T.PALETTE["border"], highlightcolor=T.PALETTE["border"])
        try: top.attributes("-topmost", True)
        except Exception: pass
        f = T.f(9); fs = T.f(8)
        for it in items:
            if it == "-": tk.Frame(top, bg=T.PALETTE["border"], height=max(1, int(z))).pack(fill="x", padx=int(6 * z), pady=int(3 * z)); continue
            if it[0] == "head":
                tk.Label(top, text=it[1], bg=bg, fg=T.PALETTE["muted"], font=T.f(7), anchor="w", padx=int(10 * z)).pack(fill="x", pady=(int(4 * z), 0)); continue
            if it[0] == "check": text, short, act, mark = it[1], "", it[3], ("✓" if it[2]() else "")
            else: text, short, act, mark = it[0], it[1], it[2], ""
            row = tk.Frame(top, bg=bg, cursor="hand2"); row.pack(fill="x")
            parts = [tk.Label(row, text=mark, width=2, bg=bg, fg=MENU_TEXT, font=f),
                     tk.Label(row, text=text, bg=bg, fg=MENU_TEXT, font=f, anchor="w", padx=int(2 * z), pady=int(2 * z))]
            parts[0].pack(side="left", padx=(int(4 * z), 0)); parts[1].pack(side="left")
            if short: parts.append(tk.Label(row, text=short, bg=bg, fg=MENU_TEXT, font=fs, padx=int(10 * z))); parts[2].pack(side="right", padx=(int(24 * z), 0))
            def hot(on, parts=parts):
                for p in parts: p.configure(fg=T.PALETTE["title"] if on else MENU_TEXT)
            for w in [row] + parts:
                w.bind("<Enter>", lambda e, h=hot: h(True)); w.bind("<Leave>", lambda e, h=hot: h(False))
                w.bind("<ButtonRelease-1>", lambda e, a=act: self._menu_run(a))
                w.bind("<Button-1>", lambda e: "break")
        top.update_idletasks()
        top.geometry(f"+{lb.winfo_rootx()}+{lb.winfo_rooty() + lb.winfo_height()}"); top.deiconify()
        lb.configure(fg=T.PALETTE["title"]); self._mopen = (i, top)
        self._mout = 0; self.after(80, self._menu_watch)                              # it closes once the mouse is off the name and the menu

    def _menu_hover(self, i):
        """the mouse rested on a menu name: open it (if it's still there)"""
        lb = self._mlabels[i]
        if self.winfo_containing(*self.winfo_pointerxy()) is lb and not (self._mopen and self._mopen[0] == i): self._menu_open(i)

    @staticmethod
    def _inside(w, x, y, grow=0):
        try: return w.winfo_rootx() - grow <= x < w.winfo_rootx() + w.winfo_width() + grow and w.winfo_rooty() - grow <= y < w.winfo_rooty() + w.winfo_height() + grow
        except tk.TclError: return False

    def _menu_watch(self):
        """while a menu is open: another name under the mouse opens that one; off the name and its menu for a moment, it closes"""
        if not self._mopen: return
        i, top = self._mopen; x, y = self.winfo_pointerxy(); lb = self._mlabels[i]
        j = next((k for k, l in enumerate(self._mlabels) if self._inside(l, x, y)), None)
        if j is not None and j != i: self._menu_open(j); return
        bridge = lb.winfo_rootx() <= x < lb.winfo_rootx() + max(lb.winfo_width(), 1) and lb.winfo_rooty() <= y <= top.winfo_rooty() + 2   # the gap between them
        if self._inside(lb, x, y) or self._inside(top, x, y, 2) or bridge: self._mout = 0
        else:
            self._mout += 1
            if self._mout >= 3: self._menu_close(); return                      # (about a quarter of a second off it: gone)
        self.after(80, self._menu_watch)

    def _menu_hit(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        return self._mlabels.index(w) if w in self._mlabels else None

    def _menu_click(self, e):
        top = self._mopen[1] if self._mopen else None
        if top is None: return
        inside = top.winfo_rootx() <= e.x_root < top.winfo_rootx() + top.winfo_width() and top.winfo_rooty() <= e.y_root < top.winfo_rooty() + top.winfo_height()
        if inside: return
        i = self._menu_hit(e)
        if i is not None and i != self._mopen[0]: self._menu_open(i)
        else: self._menu_close()

    def _menu_motion(self, e):
        i = self._menu_hit(e)                                                       # sliding along the bar opens the next menu
        if i is not None and self._mopen and i != self._mopen[0]: self._menu_open(i)

    def _menu_close(self):
        if not self._mopen: return
        i, top = self._mopen; self._mopen = None
        try: top.destroy()
        except tk.TclError: pass
        self._mlabels[i].configure(fg=MENU_TEXT)

    def _menu_run(self, act):
        self._menu_close()
        def go():
            try: act()
            except Exception as ex: prefs.log_note("a menu item", repr(ex))
        self.after_idle(go)

    # ------------------------------------------------------------------ putting other pictures in
    def place_image(self, path=None, im=None, name=None):
        """File > Place image: a picture onto a new layer of its own (named after it), shrunk to fit if it's bigger than the canvas,
        in the middle, with Free Transform on so you can move, resize and turn it (Enter keeps it), like Photoshop's Place"""
        from PIL import Image, ImageOps
        import os
        if im is None:
            from tkinter import filedialog
            path = path or filedialog.askopenfilename(parent=self, title="Place image", initialdir=prefs.save_folder(),
                                                      filetypes=[("Pictures", "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff *.avif"), ("All files", "*.*")])
            if not path: return
            try: im = Image.open(path); im.load()
            except Exception: prefs.log_note("placing a picture", path); T.banner(self.app, "COULDN'T OPEN THAT PICTURE"); return
            name = name or os.path.splitext(os.path.basename(path))[0]
        try: im = ImageOps.exif_transpose(im)
        except Exception: pass
        im = im.convert("RGBA"); w, h = self.size_wh; s = min(1.0, 0.9 * w / im.width, 0.9 * h / im.height)
        if s < 1: im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
        if getattr(self, "_xf", None): self._xf_end(True)
        if getattr(self, "sel", None) is not None: self._sel_commit(); self.sel = None
        self.add_layer(); L = self.cur; L.name = (name or "Picture")[:40]
        arr = np.asarray(im, np.float32); ih, iw = arr.shape[:2]; x0, y0 = (w - iw) // 2, (h - ih) // 2
        L.img.a[y0:y0 + ih, x0:x0 + iw] = arr[..., :3]; L.img.alpha[y0:y0 + ih, x0:x0 + iw] = arr[..., 3] / 255.0
        self._recomp(); self._layers_ui(); self._draw(); self.changed = True
        self.after_idle(self._xf_start)
        T.banner(self.app, "PLACED ON ITS OWN LAYER — drag to move it, corners to resize, outside to turn; Enter keeps it", "success")

    def paste_picture(self):
        """a picture copied in another program (a browser, a screenshot...) onto a new layer, like Place image"""
        try:
            from PIL import ImageGrab
            got = ImageGrab.grabclipboard()
        except Exception: got = None
        if isinstance(got, list):                                                    # copied picture files: the first one that opens
            for p in got:
                try: return self.place_image(path=p)
                except Exception: continue
            got = None
        if got is None: T.banner(self.app, "NO PICTURE TO PASTE — copy a picture in another program first"); return
        self.place_image(im=got, name="Pasted")

    def paste_any(self):
        """Ctrl+V: what you copied here (Copy / Cut), or else a picture copied in another program"""
        if getattr(self, "_clip", None) is not None: self._sel_paste()
        else: self.paste_picture()

    # ------------------------------------------------------------------ canvas only (Tab)
    def canvas_only(self):
        """Tab: everything but the picture goes (menu, toolbar, both side panels, the page around the studio); Tab or Esc brings it back"""
        if not getattr(self, "_conly", None):
            was_big = self._big
            if not was_big: self.toggle_big()
            panels = [p for p in (self.L, self._R) if p.winfo_manager()]
            for p in panels: self.toggle_panel(p)
            order = self.pack_slaves()                                              # (to put them back in the same order)
            bars = [(w, w.pack_info()) for w in (self._mbar, self._mline, self._bar) if w.winfo_manager()]
            for w, _ in bars: w.pack_forget()
            self._conly = (was_big, panels, bars, order)
        else:
            was_big, panels, bars, order = self._conly; self._conly = None
            for w, info in bars:
                info = {k: v for k, v in info.items() if k not in ("in", "before", "after")}
                nxt = next((x for x in order[order.index(w) + 1:] if x.winfo_manager() == "pack"), None)
                w.pack(before=nxt, **info) if nxt is not None else w.pack(**info)
            for p in panels:
                if not p.winfo_manager(): self.toggle_panel(p)
            if not was_big and self._big: self.toggle_big()
        self.cv.focus_set()

    # ------------------------------------------------------------------ sections: show / hide (Window), jump to one
    def _sections_init(self):
        """find every section of the side panels: a divider line and what follows it up to the next line, in the same place.
        (Palettes and History are each one group: the group goes.) Also the menu's keys: Ctrl+O, Ctrl+S, Tab"""
        cv = self.cv
        cv.bind("<Control-o>", lambda e: (self.open(), "break")[1]); cv.bind("<Control-s>", lambda e: (self.save(), "break")[1])
        cv.bind("<Control-O>", lambda e: (self.place_image(), "break")[1]); cv.bind("<Control-V>", lambda e: (self.paste_picture(), "break")[1])
        cv.bind("<Tab>", lambda e: (self.canvas_only(), "break")[1])
        cv.bind("<Escape>", lambda e: (self.canvas_only(), "break")[1] if getattr(self, "_conly", None) else None, add="+")
        bt = cv.bindtags(); cv.bind_class("ConlyEsc", "<Escape>", lambda e: (self.canvas_only(), "break")[1] if getattr(self, "_conly", None) else None)
        cv.bindtags(("ConlyEsc",) + tuple(bt))                                       # (before the studio-size Esc)
        canv = {"Color": getattr(self, "_col_canvas", None), "Options": getattr(self, "_opt_canvas", None), "Adjustments": getattr(self, "_adj_canvas", None)}
        def view_of(w):
            p = str(w)
            for v, c in canv.items():
                if c is not None and p.startswith(str(c) + "."): return v
            return None
        def title_in(ws):
            for w in ws:
                stack = [w]
                while stack:
                    x = stack.pop(0)
                    if isinstance(x, tk.Label):
                        try: t = str(x.cget("text")).strip()
                        except tk.TclError: t = ""
                        if t and t.upper() == t and any(c.isalpha() for c in t): return t
                    stack.extend(x.winfo_children())
            return None
        self._secs = {}; self._sections = []; self._sec_slaves = {}; seen = set()
        for r in getattr(self, "_rules", []):
            par = r.master
            if par in seen: continue
            seen.add(par)
            if getattr(par, "_sec_name", None):                                     # a whole group (Palettes, History)
                box = par.master; self._sec_slaves.setdefault(box, box.pack_slaves()); v = view_of(par)
                if v and (v, par._sec_name) not in self._secs: self._secs[(v, par._sec_name)] = (box, [par]); self._sections.append((v, par._sec_name))
                continue
            slaves = par.pack_slaves(); self._sec_slaves[par] = slaves; runs = []; cur = None
            for w in slaves:
                if getattr(w, "_is_rule", False): cur = [w]; runs.append(cur)
                elif cur is not None: cur.append(w)
            for run in runs:
                v = view_of(run[0]); name = title_in(run[1:])
                if v is None or name is None or name in NO_HIDE or (v, name) in self._secs: continue
                self._secs[(v, name)] = (par, run); self._sections.append((v, name))
        self._hidden_secs = set(); self._sec_info = {}; self._auto_on = set()
        saved = prefs.get("draw_hidden_sections")                                   # (nothing saved yet: the defaults)
        for k in (DEFAULT_OFF if saved is None else saved):
            if tuple(k) in self._secs: self._hide_section(tuple(k))
        self._refit_views(); self._auto_sections()

    def _hide_section(self, key):
        par, run = self._secs[key]
        self._sec_info[key] = [(w, w.pack_info()) for w in run if w.winfo_manager()]
        for w, _ in self._sec_info[key]: w.pack_forget()
        self._hidden_secs.add(key)

    def _show_section(self, key):
        """back in its place: in front of the first thing after it (as the panel was built) that's still showing"""
        par, run = self._secs[key]; order = self._sec_slaves.get(par, []); info = self._sec_info.pop(key, [])
        nxt = None
        if run[-1] in order:
            for w in order[order.index(run[-1]) + 1:]:
                if w.winfo_exists() and w.winfo_manager() == "pack": nxt = w; break
        for w, inf in info:
            inf = {a: b for a, b in inf.items() if a not in ("in", "before", "after")}
            try: w.pack(before=nxt, **inf) if nxt is not None else w.pack(**inf)
            except tk.TclError: pass
        self._hidden_secs.discard(key)

    def _save_hidden(self):
        """(a section a tool turned on for now still counts as off)"""
        prefs.set("draw_hidden_sections", [list(k) for k in sorted(self._hidden_secs | getattr(self, "_auto_on", set()))])

    def _toggle_section(self, view, name):
        key = (view, name); self._auto_on.discard(key)                              # you've chosen: it stays as you set it
        if key in self._hidden_secs: self._show_section(key)
        else: self._hide_section(key)
        self._save_hidden(); self._refit_views()

    def _auto_sections(self):
        """the tool in use turns on the sections its settings are in; the ones it turned on go off again when you leave it"""
        if not hasattr(self, "_secs"): return
        want = set(TOOL_SECTIONS.get(getattr(self, "tool", ""), []))
        if getattr(self, "sel", None) is not None: want |= set(_SEL)                # something selected: the Cut Out tools
        changed = False
        for k in list(self._auto_on):
            if k not in want and k in self._secs: self._hide_section(k); self._auto_on.discard(k); changed = True
        for k in want:
            if k in self._hidden_secs and k in self._secs: self._show_section(k); self._auto_on.add(k); changed = True
        if changed: self._refit_views()

    def _section_on(self, key):
        """turn a section on for good (e.g. Stickers, once you've made or imported one)"""
        if not hasattr(self, "_secs") or key not in self._secs: return
        self._auto_on.discard(key)
        if key in self._hidden_secs: self._show_section(key); self._save_hidden(); self._refit_views()

    def _show_all_sections(self):
        for k in list(self._hidden_secs): self._show_section(k)
        self._save_hidden(); self._refit_views()

    def _refit_views(self):
        for fn in ("_cfit", "_ofit", "_afit"):
            f = getattr(self, fn, None)
            if callable(f):
                try: f(None)
                except Exception: pass

    def _goto_section(self, view, name):
        """open that side and scroll so the section is at the top (showing it first if Window had it hidden)"""
        key = (view, name); self._auto_on.discard(key)
        if key in getattr(self, "_hidden_secs", ()): self._show_section(key); self._save_hidden()
        if view == "Adjustments": self._left_view("Adjustments")
        else: self._right_view(view)
        self.update_idletasks(); self._refit_views()
        cv = {"Color": getattr(self, "_col_canvas", None), "Options": getattr(self, "_opt_canvas", None), "Adjustments": getattr(self, "_adj_canvas", None)}[view]
        if cv is None or key not in self._secs: return
        rule = self._secs[key][1][0]; self.update_idletasks()
        inner = cv.nametowidget(cv.itemcget(cv.find_all()[0], "window")) if cv.find_all() else None
        if inner is None: return
        y = rule.winfo_rooty() - inner.winfo_rooty(); h = max(1, inner.winfo_height())
        cv.yview_moveto(max(0.0, y / h))
