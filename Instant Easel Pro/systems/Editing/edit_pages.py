"""
edit_pages.py: the Editing tab (Light, Color, Effects, Filters, Transform, History), Lightroom-style, working on the SAME picture as
the Drawing tab: no copy, nothing to open twice. Switch between the two tabs and you see one picture.

  Hub (app.edit_hub)  the edit in progress (the slider values, the filter, crop / rotate / resize) and its named steps (History).
                      It reads the Drawing studio's layers, so a preview is the picture exactly as Drawing shows it, layers and all.
                      Apply to: "Whole picture" adjusts every layer and the paper (each layer stays its own); "This layer" just the layer Drawing
                      is on (like an adjustment in Photoshop). Crop, rotate, straighten, flip and resize always change the whole picture.
  enter() / leave()   main.py's show() calls them as you come into / go out of the Editing tab: leaving puts the edit into the
                      picture for real (one step on Drawing's Undo list), so Drawing then shows it. Coming back starts a fresh edit.
  pages               the side menu's pages; each shows the live preview (worked out small, on a background thread, so the
                      sliders never stutter) beside its own controls.

The adjustments themselves are edit.py's (apply / look / transform).
"""
import os, copy, threading, hashlib
import tkinter as tk
from tkinter import filedialog
import numpy as np
from PIL import Image, ImageTk, ImageDraw
import theme as T
import prefs
import skin
import edit as E
import ui_art as UA

PREVIEW = 1100                                   # the longest side the preview is worked out at (the picture itself is untouched)


def _frame(parent):
    f = tk.Frame(parent, bg=parent["bg"]); T.on_change(lambda: f.configure(bg=f.master["bg"])); return f


def _tf_f(a, g):
    """one channel (a float array) through the crop / rotate / flip / straighten / resize"""
    return np.asarray(E.transform(Image.fromarray(np.ascontiguousarray(a, np.float32), "F"), g), np.float32)


def _tf_arr(a, g):
    return np.stack([_tf_f(a[..., k], g) for k in range(a.shape[2])], -1) if a.ndim == 3 else np.clip(_tf_f(a, g), 0, None)


def _rgb(a): return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


class Hub:
    def __init__(self, app):
        self.app = app; app.edit_hub = self
        self.params = dict(E.DEFAULTS); self.filt = "none"; self.geom = dict(E.GEOM); self.listeners = []
        self.scope = tk.StringVar(master=app, value="Whole picture"); self.scope.trace_add("write", lambda *a: self.notify(record=False))
        self._key = None; self._px = None; self._building = None; self.hist = []; self.hpos = 0; self._hist_job = None; self.inside = False
        self.hist_start("Start")
        app.bind("<Control-z>", lambda e: self._key_undo(), add="+"); app.bind("<Control-y>", lambda e: self._key_undo(True), add="+")

    # ---------------------------------------------------------------- the Drawing picture
    def studio(self):
        try: return self.app.pages["Drawing"].pages["Draw"]
        except Exception: return None

    def _doc_key(self, S):
        c = S._comp; return (S.size_wh, tuple(id(L) for L in S.layers), S.layers.index(S.cur) if S.cur in S.layers else -1,
                             hashlib.md5(np.ascontiguousarray(c[::9, ::9]).tobytes()).hexdigest())

    def _proxies(self, wait=False):
        """each layer (and the background) made small, once, for quick previews; again only if the picture has changed"""
        S = self.studio()
        if S is None: return None
        key = self._doc_key(S)
        if self._px is not None and key == self._key: return self._px
        if wait: return self._build(S, key)
        if self._building != key:                                                  # made on another thread: the tab opens at once
            self._building = key
            def work():
                try: self._build(S, key)
                except Exception as ex: prefs.log_note("the Editing preview (making it small)", repr(ex))
                self.app.q.put(lambda: (setattr(self, "_building", None), self.notify(record=False)))
            threading.Thread(target=work, daemon=True, name="EditProxies").start()
        return None

    def _build(self, S, key):
        try: side = prefs.size("edit_preview")
        except Exception: side = PREVIEW
        w, h = S.size_wh; s = min(1.0, side / max(w, h)); pw, ph = max(1, int(w * s)), max(1, int(h * s))
        k = max(1, int(1 / s / 1.5))                                               # skip pixels first (quick), then a smooth resize
        small = lambda a: np.asarray(Image.fromarray(np.ascontiguousarray(a[::k, ::k], np.float32), "F").resize((pw, ph), Image.BILINEAR), np.float32)
        rgb = lambda a: _rgb(a[::k, ::k]).resize((pw, ph), Image.BILINEAR)
        layers = [(L, rgb(L.img.a), small(L.img.alpha), None if L.maskcv is None else small(L.maskcv.alpha)) for L in S.layers]
        px = dict(size=(pw, ph), full=(w, h), bg=np.asarray(rgb(S.bg), np.float32), layers=layers, groups=dict(S.groups))
        self._px, self._key = px, key; return px

    def targets(self):
        S = self.studio()
        if S is None: return set()
        return set(range(len(S.layers))) if self.scope.get() == "Whole picture" else {S.layers.index(S.cur)}

    def scope_names(self):
        S = self.studio(); n = S.cur.name if S is not None else "this layer"
        return ["Whole picture", f"This layer ({n})"[:34]]

    def whole(self): return self.scope.get() == "Whole picture"
    def _adjusting(self): return any(self.params.values()) or self.filt not in (None, "", "none")
    def pending(self): return self._adjusting() or self.geom != E.GEOM

    def has_picture(self): return self.studio() is not None

    def render(self, orig=False, geom=None, adjust=True, px=None):
        """the picture as it would be with this edit, at preview size (PIL RGB). orig: as it is now. Safe on a background thread:
        it builds its own small layers and runs Drawing's own layer blending on them (blend modes, groups, clipping, masks)"""
        import draw_studio as DS
        px = px or self._proxies(wait=True)
        if px is None: return None
        g = dict(E.GEOM) if orig else dict(geom if geom is not None else self.geom); adj = adjust and not orig
        tg = self.targets(); same = g == E.GEOM
        bg = px["bg"] if same else _tf_arr(px["bg"], g); h, w = bg.shape[:2]; tmp = []
        if adj and self.whole() and self._adjusting(): bg = np.asarray(E.apply(_rgb(bg), self.params, self.filt), np.float32)   # the paper too
        for i, (L, rgb, al, mk) in enumerate(px["layers"]):
            im = rgb if same else E.transform(rgb, g)
            if adj and i in tg and self._adjusting(): im = E.apply(im, self.params, self.filt)
            N = DS.Layer(w, h, L.name); N.img.a = np.asarray(im, np.float32); N.img.alpha = al if same else _tf_arr(al, g)
            if mk is not None: N.add_mask(); N.maskcv.alpha = mk if same else _tf_arr(mk, g)
            N.visible, N.opacity, N.mode, N.clip = L.visible, L.opacity, L.mode, L.clip
            if hasattr(L, "group"): N.group = L.group
            tmp.append(N)
        doc = object.__new__(DS.DrawStudio); doc.layers = tmp; doc.groups = px["groups"]          # (Drawing's blending, on these)
        out = DS.DrawStudio._composite(doc, bg.copy(), (slice(None), slice(None)))
        return _rgb(out)

    def output_size(self):
        S = self.studio()
        if S is None: return (0, 0)
        w, h = S.size_wh; return E.transform(Image.new("L", (w, h)), self.geom).size

    # ---------------------------------------------------------------- coming in, going out, applying
    def enter(self):
        """the Editing tab is shown: the Drawing picture as it is now"""
        self.inside = True
        try: self.app.focus_set()                                                 # (Drawing's canvas keeps its own Ctrl+Z: not while in here)
        except Exception: pass
        if self._proxies() is not None: self.notify(record=False)

    def leave(self):
        """the Editing tab is left: the edit goes into the picture (if there is one), so Drawing shows it"""
        self.inside = False
        if self.pending(): self.apply()

    def apply(self):
        """put the edit into the picture at full size: one step on Drawing's Undo list (Ctrl+Z there takes it all back)"""
        S = self.studio()
        if S is None or not self.pending(): return False
        try:
            S._whole_snapshot(); g = dict(self.geom); tg = self.targets()
            if getattr(S, "sel", None) is not None: S._sel_commit(); S.sel = None
            if g != E.GEOM:                                                       # crop / rotate / resize: every layer, mask, the background
                W, H = self.output_size(); S._resize_doc(lambda arr: _tf_arr(arr, g), W, H)
                for L in S.layers: L.img.alpha = np.clip(L.img.alpha, 0, 1)
            if self._adjusting():
                if self.whole(): S.bg = np.asarray(E.apply(_rgb(S.bg), self.params, self.filt), np.float32)
                for i in sorted(tg):
                    L = S.layers[i]; L.img.a = np.asarray(E.apply(_rgb(L.img.a), self.params, self.filt), np.float32)
            S._recomp(); S._draw(); S._layers_ui(); S.changed = True
            if hasattr(S, "set_size_level"): S.set_size_level(S.size_lvl)
        except Exception as ex:
            prefs.log_note("applying an edit to the picture", repr(ex)); T.banner(self.app, "COULDN'T APPLY THE EDIT — the details are in the log"); return False
        self.params = dict(E.DEFAULTS); self.filt = "none"; self.geom = dict(E.GEOM); self._px = None
        self.hist_start("Applied to the picture"); self.notify(record=False)
        T.banner(self.app, "EDIT APPLIED TO THE PICTURE — Ctrl+Z in Drawing takes it back", "success")
        return True

    def notify(self, record=True):
        for fn in list(self.listeners):
            try: fn()
            except Exception: pass
        if record: self.hist_touch()

    # ---------------------------------------------------------------- the edit's own steps (History; Ctrl+Z / Ctrl+Y in Editing)
    def _snap(self): return copy.deepcopy(dict(params=self.params, filt=self.filt, geom=self.geom))

    def hist_start(self, label):
        self.hist = [(label, self._snap())]; self.hpos = 0; self._hist_job = None; self._hist_changed()

    def hist_touch(self):
        """a change happened: recorded once things settle (one slider drag = one step)"""
        if self._hist_job: self.app.after_cancel(self._hist_job)
        self._hist_job = self.app.after(600, lambda: self.hist_commit())

    def hist_commit(self, label=None):
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
        if not (0 <= i < len(self.hist)): return
        if self._hist_job: self.app.after_cancel(self._hist_job); self._hist_job = None
        self.hpos = i; s = copy.deepcopy(self.hist[i][1]); self.params, self.filt, self.geom = s["params"], s["filt"], s["geom"]
        self.notify(record=False); self._hist_changed()

    def hist_undo(self):
        if self._hist_job: self.hist_commit()                                      # finish a change in progress first
        self.hist_jump(self.hpos - 1)

    def hist_redo(self): self.hist_jump(self.hpos + 1)

    def _hist_changed(self):
        try: h = self.app.pages["Editing"].pages.get("History")
        except Exception: h = None
        if h is not None and hasattr(h, "show_list"): h.show_list()

    def _key_undo(self, redo=False):
        if getattr(getattr(self.app, "tabs", None), "active", "") != "Editing": return
        (self.hist_redo if redo else self.hist_undo)()

    def reset(self):
        self.params = dict(E.DEFAULTS); self.filt = "none"; self.geom = dict(E.GEOM); self.notify(record=False); self.hist_commit("Reset")


def hub(app):
    return getattr(app, "edit_hub", None) or Hub(app)


# ==================================================================== the pages
class EditBase(tk.Frame):
    """top bar (open / apply / undo / redo / before-after / reset / save, and Apply to) + the page's own controls + the live preview"""
    def __init__(self, master, app, title):
        super().__init__(master, bg=master["bg"]); self.app = app; T.on_change(lambda: self.configure(bg=self.master["bg"]))
        self.hub = hub(app); self.hub.listeners.append(self.refresh); self._job = None; self.show_orig = False; self._busy = False; self._again = False
        bar = _frame(self); bar.pack(fill="x", pady=(0, 8))
        buttons = [("Open image", self.open, "normal")]
        if "AI Images" in getattr(app, "pages", {}) or "AI Images" in [m for m, *_ in __import__("features").MENUS]: buttons.append(("Edit last created", self.last, "normal"))
        buttons += [("↶ Undo", self.hub.hist_undo, "normal"), ("↷ Redo", self.hub.hist_redo, "normal"), ("Before / after", self.toggle, "normal"),
                    ("Reset all", self.hub.reset, "danger"), ("Apply", self.apply_now, "normal"), ("Save", self.save, "normal")]
        for text, cmd, kind in buttons:
            art = {"↶ Undo": "undo", "↷ Redo": "redo", "Reset all": "reset", "Apply": "apply", "Before / after": "before_after"}.get(text)          # your painted buttons
            tips = {"undo": "Undo (Ctrl+Z)", "redo": "Redo (Ctrl+Y)", "reset": "Reset all", "apply": "Apply", "before_after": "Before / after"}
            if art and UA.toolbar(art) is not None: self._art_button(bar, art, tips[art], cmd).pack(side="left", padx=(0, 8)); continue
            b = T.Button(bar, text, cmd, kind=kind)
            (skin.file_button(b) if text in ("Open image", "Save") else b).pack(side="left", padx=(0, 8))
        sc = _frame(bar); sc.pack(side="right")
        self._scope_box = _frame(sc); self._scope_box.pack(side="left"); self._scope_names = None; self._scope_choice()
        body = _frame(self); body.pack(fill="both", expand=True)
        self.controls = _frame(body); self.controls.pack(side="left", fill="y", padx=(0, 14))
        T.Title(self.controls, title).pack(anchor="w", pady=(0, 8))
        self.view = tk.Label(body, bg=T.PALETTE["field"], text="DRAW SOMETHING, OR OPEN A PICTURE", fg=T.PALETTE["muted"], font=T.f(11), width=1, height=1)
        self.view.pack(side="left", fill="both", expand=True); self.view.bind("<Configure>", lambda e: self.refresh()); T.on_change(lambda: self.view.configure(bg=T.PALETTE["field"]))

    def _art_button(self, parent, name, tip, cmd, h=40):
        """your painted Undo / Redo pictures (images/UI/Draw Toolbar), as in the Drawing toolbar: the picture is the whole button,
        a ring in the theme's border colour while the mouse is on it, the button's name in a little box after a moment"""
        w = tk.Label(parent, bd=0, highlightthickness=0, cursor="hand2", bg=parent["bg"]); w._ph = {}; st = {"on": False, "job": None, "tip": None}
        def style():
            try:
                if not w.winfo_exists(): return
            except tk.TclError: return
            px = max(16, int(round(h * T.Z))); im = skin.ringed(UA.toolbar(name, h=px), st["on"], key=("edit", name, px))
            k = (im.size, st["on"], T.PALETTE["border"])
            if k not in w._ph: w._ph[k] = ImageTk.PhotoImage(im)
            w.configure(image=w._ph[k], bg=w.master["bg"])
        def hide(e=None):
            if st["job"]: w.after_cancel(st["job"]); st["job"] = None
            if st["tip"] is not None: st["tip"].destroy(); st["tip"] = None
        def enter(e):
            st["on"] = True; style(); st["job"] = w.after(450, lambda: (st.__setitem__("job", None), st.__setitem__("tip", st["tip"] or T.tip_window(w, tip))))
        def leave(e): st["on"] = False; style(); hide()
        w.bind("<Enter>", enter); w.bind("<Leave>", leave); w.bind("<Button-1>", lambda e: (hide(), cmd()))
        style(); T.on_change(style, zoom=True); return w

    def _scope_choice(self):
        """Whole picture / This layer (named), rebuilt when the layer's name changes"""
        names = self.hub.scope_names()
        if names == self._scope_names: return
        self._scope_names = names
        for w in self._scope_box.winfo_children(): w.destroy()
        v = tk.StringVar(master=self, value=names[0] if self.hub.scope.get() == "Whole picture" else names[1])
        def pick(*a): self.hub.scope.set("Whole picture" if v.get() == names[0] else "This layer")
        v.trace_add("write", pick); self._scope_var = v; T.Choice(self._scope_box, "apply to", names, v).pack(side="left")

    # ---- the buttons
    def open(self):
        S = self.hub.studio()
        if S is None: return
        if self.hub.pending() and T.popup(self.app, "OPEN ANOTHER PICTURE?", "The edit you're making to this one will be put into it first.",
                                         (("Open", "normal"), ("Cancel", "normal"))) != "Open": return
        self.hub.apply(); S.open(); self.hub._px = None; self.hub.hist_start("Opened"); self.hub.notify(record=False)

    def last(self):
        c = self.app.pages["AI Images"].pages; im = None
        for n in ("Image to Image", "Text to Image"):
            r = getattr(c.get(n), "result", None)
            if r is not None: im = r; break
        if im is None: return T.banner(self.app, "NOTHING YET — create an image first")
        S = self.hub.studio(); self.hub.apply(); S.load_image(im); self.hub._px = None; self.hub.hist_start("Opened the last created image"); self.hub.notify(record=False)

    def toggle(self): self.show_orig = not self.show_orig; self.refresh()
    def apply_now(self):
        if not self.hub.pending(): T.banner(self.app, "NOTHING TO APPLY — move a slider, pick a filter or crop first"); return
        self.hub.apply()
    def save(self):
        S = self.hub.studio()
        if S is None: return
        self.hub.apply(); S.save()

    # ---- the preview (throttled, on a background thread: the sliders never stutter)
    def refresh(self):
        if self._job is None: self._job = self.after(30, self._draw)

    def _draw(self):
        self._job = None
        if not self.winfo_ismapped(): return
        self._scope_choice()
        if self._busy: self._again = True; return                                  # one render at a time; the newest settings next
        px = self.hub._proxies()
        if px is None: return
        w, h = max(200, self.view.winfo_width() - 8), max(200, self.view.winfo_height() - 8); orig = self.show_orig; self._busy = True
        def work():
            try: im = self.hub.render(orig=orig, px=px); t = im.copy(); t.thumbnail((w, h)); res = (t, None)
            except Exception as ex: res = (None, ex)
            self.app.q.put(lambda: self._rendered(*res))
        threading.Thread(target=work, daemon=True, name="EditPreview").start()

    def _rendered(self, t, err):
        self._busy = False
        if err is not None: prefs.log_note("the Editing preview", repr(err))
        elif t is not None and self.winfo_exists():
            self.ph = ImageTk.PhotoImage(t); self.view.configure(image=self.ph, text=""); self.after_hook()
        if self._again: self._again = False; self.refresh()

    def after_hook(self): pass


class AdjustPage(EditBase):
    GROUP = "Light"
    def __init__(self, master, app):
        super().__init__(master, app, self.GROUP); self.labels = {}; self.sliders = {}
        for k in E.GROUPS[self.GROUP]:
            r = _frame(self.controls); r.pack(fill="x", pady=(6, 0))
            T.Text(r, k.upper()).pack(side="left"); self.labels[k] = T.Text(r, "0", muted=True); self.labels[k].pack(side="right")
            s = T.PlainSlider(self.controls, value=0.5, width=300, command=lambda v, k=k: self.change(k, v)); s.pack(anchor="w")
            s.bind("<Double-Button-1>", lambda e, k=k: self.change(k, 0.5, reset=True)); self.sliders[k] = s
        T.Text(self.controls, "Double-click a slider to reset it.", muted=True).pack(anchor="w", pady=10)

    def change(self, k, v, reset=False):
        val = int(round((v - 0.5) * 200)); self.hub.params[k] = val
        if reset: self.sliders[k].value = 0.5; self.sliders[k]._draw()
        self.labels[k].configure(text=f"{val:+d}" if val else "0"); self.hub.notify()

    def after_hook(self):
        for k, s in self.sliders.items():
            v = self.hub.params[k]; want = v / 200 + 0.5
            if abs(s.value - want) > 1e-6: s.value = want; s._draw()
            self.labels[k].configure(text=f"{v:+d}" if v else "0")


class LightPage(AdjustPage): GROUP = "Light"
class ColorPage(AdjustPage): GROUP = "Color"
class EffectsPage(AdjustPage): GROUP = "Effects"


class FiltersPage(EditBase):
    def __init__(self, master, app):
        super().__init__(master, app, "Filters"); self.tiles = {}; self._thumbs = []; self._tkey = None
        grid = _frame(self.controls); grid.pack(anchor="w")
        for i, f in enumerate(E.FILTERS):
            cell = _frame(grid); cell.grid(row=i // 2, column=i % 2, padx=6, pady=6)
            lb = tk.Label(cell, bg=T.PALETTE["field"], width=16, height=5, text=f.upper(), fg=T.PALETTE["muted"], font=T.f(8), highlightthickness=3, cursor="hand2")
            lb.pack(); lb.bind("<Button-1>", lambda e, f=f: self.pick(f)); T.Text(cell, f.upper(), font=T.f(8)).pack(); self.tiles[f] = lb

    def pick(self, f): self.hub.filt = f; self.hub.notify()

    def after_hook(self):
        key = (self.hub._key, tuple(sorted(self.hub.params.items())), str(self.hub.geom), self.hub.scope.get())
        if key != self._tkey:                                                      # the little previews: the picture with each look
            self._tkey = key; keep = self.hub.filt; self.hub.filt = "none"
            try: base = self.hub.render()
            finally: self.hub.filt = keep
            small = base.copy(); small.thumbnail((130, 90)); self._thumbs = []
            for f, lb in self.tiles.items():
                ph = ImageTk.PhotoImage(E.look(small, f)); self._thumbs.append(ph); lb.configure(image=ph, text="", width=small.width, height=small.height)
        for f, lb in self.tiles.items():
            lb.configure(highlightbackground=T.PALETTE["border"] if f == self.hub.filt else T.PALETTE["panel2"])


class HistoryPage(EditBase):
    """every step of this edit by name (click to jump), undo / redo, side-by-side compare, reset, save"""
    def __init__(self, master, app):
        super().__init__(master, app, "History"); self.compare = False
        c = self.controls
        r = _frame(c); r.pack(anchor="w", pady=(0, 6)); T.Button(r, "Compare side by side", self.toggle_compare).pack(side="left")
        r = _frame(c); r.pack(anchor="w", pady=(0, 8)); skin.file_button(T.Button(r, "Save as new", self.save)).pack(side="left")
        T.Text(c, "STEPS  (click one to go back to it)", font=T.f(10)).pack(anchor="w", pady=(6, 2))
        box = T.ScrollBox(c, bg="panel2"); box.pack(fill="y", expand=True, anchor="w")
        self.lcv = tk.Canvas(box.body, width=262, height=420, bg=T.PALETTE["panel2"], highlightthickness=0); box.attach(self.lcv)
        self.lcv.pack(side="left", fill="both", expand=True)
        self.list = tk.Frame(self.lcv, bg=T.PALETTE["panel2"]); self.lcv.create_window((0, 0), window=self.list, anchor="nw")
        self.list.bind("<Configure>", lambda e: T.fit_scrollregion(self.lcv)); T.on_change(lambda: (self.lcv.configure(bg=T.PALETTE["panel2"]), self.list.configure(bg=T.PALETTE["panel2"])))
        T.Text(c, "Your edit goes into the picture when you go back to Drawing (or press Apply); Drawing's Undo can take it back.", muted=True).pack(anchor="w", pady=8)
        self.show_list()

    def show_list(self):
        for w in self.list.winfo_children(): w.destroy()
        H = self.hub
        for i, (label, _) in enumerate(H.hist):
            cur = i == H.hpos; future = i > H.hpos
            b = tk.Label(self.list, text=f"{i:>3}  {label}", anchor="w", width=34, font=T.f(9), cursor="hand2", padx=6, pady=3,
                         bg=T.PALETTE["button"] if cur else T.PALETTE["panel2"], fg=T.PALETTE["muted"] if future else "white",
                         highlightthickness=2, highlightbackground=T.PALETTE["border"] if cur else T.PALETTE["panel2"])
            b.pack(fill="x", pady=1); b.bind("<Button-1>", lambda e, i=i: H.hist_jump(i))
        self.lcv.update_idletasks(); self.lcv.yview_moveto(1.0 if H.hpos == len(H.hist) - 1 else max(0, H.hpos / max(1, len(H.hist))))

    def toggle_compare(self): self.compare = not self.compare; self.refresh()

    def _draw(self):
        if not self.compare: return super()._draw()
        self._job = None
        if not self.winfo_ismapped() or self.hub._proxies() is None: return
        w, h = max(200, self.view.winfo_width() - 8), max(200, self.view.winfo_height() - 8)
        a, b = self.hub.render(orig=True), self.hub.render(); a.thumbnail((w // 2 - 6, h - 30)); b.thumbnail((w // 2 - 6, h - 30))
        sheet = Image.new("RGB", (w, h), tuple(int(T.PALETTE["field"][i:i + 2], 16) for i in (1, 3, 5)))
        sheet.paste(a, ((w // 2 - a.width) // 2, 28)); sheet.paste(b, (w // 2 + (w // 2 - b.width) // 2, 28))
        d = ImageDraw.Draw(sheet); d.text((w // 4 - 30, 6), "BEFORE", fill=(200, 200, 210)); d.text((3 * w // 4 - 24, 6), "AFTER", fill=(200, 200, 210))
        self.ph = ImageTk.PhotoImage(sheet); self.view.configure(image=self.ph, text="")


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
        r = _frame(c); r.pack(anchor="w")
        T.Button(r, "⟲ 90°", lambda: self.geom(rot90=self.g["rot90"] + 1)).pack(side="left"); T.Button(r, "⟳ 90°", lambda: self.geom(rot90=self.g["rot90"] - 1)).pack(side="left", padx=6)
        r = _frame(c); r.pack(anchor="w", pady=6)
        T.Button(r, "Flip ↔", lambda: self.geom(flip_h=not self.g["flip_h"])).pack(side="left"); T.Button(r, "Flip ↕", lambda: self.geom(flip_v=not self.g["flip_v"])).pack(side="left", padx=6)
        rr = _frame(c); rr.pack(fill="x", pady=(10, 0)); T.Text(rr, "STRAIGHTEN").pack(side="left"); self.st_lbl = T.Text(rr, "0.0°", muted=True); self.st_lbl.pack(side="right")
        self.st = T.PlainSlider(c, value=0.5, width=300, command=self._straighten); self.st.pack(anchor="w")
        self.st.bind("<Double-Button-1>", lambda e: (setattr(self.st, "value", 0.5), self.st._draw(), self._straighten(0.5)))
        T.Text(c, "CROP  (drag on the picture)").pack(anchor="w", pady=(12, 4))
        self.ratio = tk.StringVar(master=self, value="Free"); T.Choice(c, "ratio", self.RATIOS, self.ratio).pack(anchor="w")
        self.ratio.trace_add("write", lambda *a: self._apply_ratio())
        T.Button(c, "Clear crop", lambda: self.geom(crop=None)).pack(anchor="w", pady=6)
        T.Text(c, "RESIZE").pack(anchor="w", pady=(8, 4))
        self.scale = tk.StringVar(master=self, value="100%"); T.Choice(c, "size", self.SCALES, self.scale).pack(anchor="w")
        self.scale.trace_add("write", lambda *a: self.geom(scale=int(self.scale.get()[:-1]) / 100))
        T.Text(c, "These change the whole picture (every layer).", muted=True).pack(anchor="w", pady=(10, 0))
        self.size_lbl = T.Text(c, "", muted=True); self.size_lbl.pack(anchor="w", pady=6)

    @property
    def g(self): return self.hub.geom
    def geom(self, **kw): self.g.update(kw); self.hub.notify()

    def _straighten(self, v):
        deg = round((v - 0.5) * 90, 1); self.st_lbl.configure(text=f"{deg:+.1f}°" if deg else "0.0°"); self.geom(straighten=deg)

    def _apply_ratio(self):
        px = self.hub._proxies()
        if px is None: return
        r = self.ratio.get(); W, H = E.transform(Image.new("L", px["size"]), dict(self.g, crop=None, scale=1.0)).size
        self.geom(crop=None if r == "Free" else E.crop_for_ratio(W, H, r))

    def _draw(self):
        self._job = None
        if not self.winfo_ismapped() or self.hub._proxies() is None: return
        self._scope_choice()
        base = self.hub.render(orig=self.show_orig, geom=dict(self.g, crop=None, scale=1.0))     # rotated / straightened, not yet cropped
        w, h = max(200, self.cv.winfo_width() - 16), max(200, self.cv.winfo_height() - 16); t = base.copy(); t.thumbnail((w, h))
        self._off = ((self.cv.winfo_width() - t.width) / 2, (self.cv.winfo_height() - t.height) / 2); self._tw, self._th = t.width, t.height
        self.cv.delete("all"); self.ph = ImageTk.PhotoImage(t); self.cv.create_image(self._off[0], self._off[1], image=self.ph, anchor="nw")
        c = self.g["crop"]
        if c:
            x0, y0 = self._off[0] + min(c[0], c[2]) * t.width, self._off[1] + min(c[1], c[3]) * t.height
            x1, y1 = self._off[0] + max(c[0], c[2]) * t.width, self._off[1] + max(c[1], c[3]) * t.height
            for box in ((self._off[0], self._off[1], self._off[0] + t.width, y0), (self._off[0], y1, self._off[0] + t.width, self._off[1] + t.height),
                        (self._off[0], y0, x0, y1), (x1, y0, self._off[0] + t.width, y1)):
                self.cv.create_rectangle(*box, fill="black", stipple="gray50", width=0)          # darker outside the crop
            self.cv.create_rectangle(x0, y0, x1, y1, outline=T.PALETTE["border"], width=2)
            for i in (1, 2):                                                                       # rule-of-thirds guides
                self.cv.create_line(x0 + (x1 - x0) * i / 3, y0, x0 + (x1 - x0) * i / 3, y1, fill="#ffffff", stipple="gray50")
                self.cv.create_line(x0, y0 + (y1 - y0) * i / 3, x1, y0 + (y1 - y0) * i / 3, fill="#ffffff", stipple="gray50")
        W, H = self.hub.output_size(); self.size_lbl.configure(text=f"OUTPUT: {W} x {H} px")

    def _xy(self, e): return (min(1, max(0, (e.x - self._off[0]) / max(1, self._tw))), min(1, max(0, (e.y - self._off[1]) / max(1, self._th))))
    def _press(self, e):
        if self.hub._proxies() is None or not hasattr(self, "_off"): return
        self._start = self._xy(e)
    def _drag(self, e):
        if not hasattr(self, "_start"): return
        (sx, sy), (x, y) = self._start, self._xy(e); r = self.ratio.get()
        if r != "Free":                                                                            # keep the chosen shape
            a, b = (float(v) for v in r.split(":")); base_r = self._tw / max(1, self._th); want = (a / b) / base_r
            dx, dy = x - sx, y - sy; h_ = max(abs(dy), abs(dx) / want); dx, dy = (1 if dx >= 0 else -1) * h_ * want, (1 if dy >= 0 else -1) * h_
            x, y = min(1, max(0, sx + dx)), min(1, max(0, sy + dy))
        self.geom(crop=(sx, sy, x, y))


def page_classes():
    return {"Light": LightPage, "Color": ColorPage, "Effects": EffectsPage, "Filters": FiltersPage, "Transform": TransformPage, "History": HistoryPage}
