"""
studio_cutout.py: tools for cutting things out of a picture.

  Smart Select (tile)   drag a box round something: the thing itself is selected, not its background (colour models of what's
                        in the middle of the box and what's round its edge, tidied up). Shift adds to the selection, Alt takes away.
  Magic Eraser (tile)   click a colour area: it's erased from the layer (Tolerance and Fill from, in Options > Fill).
  Magic Wand            Shift-click adds to the selection, Alt-click takes away; Options > Cut Out > Contiguous: joined-up only, or
                        that colour everywhere.
  Options > CUT OUT     Remove background (the area round the edges, from the layer you're on), Cut / Copy to a new layer, Invert,
                        Grow, Shrink.

Mixed into DrawStudio (draw_studio.py). Selections are made as masks (kind "mask") so they work with everything else.
"""
import numpy as np
import tkinter as tk
import theme as T

ALT = 0x20008                                                                  # Alt held (Windows 0x20000, Linux Mod1 0x8)

def _kmeans(px, k=6, iters=8, seed=0):
    """a few typical colours of a set of pixels"""
    px = px.reshape(-1, 3).astype(np.float32)
    if len(px) == 0: return np.zeros((1, 3), np.float32)
    rng = np.random.default_rng(seed)
    if len(px) > 4000: px = px[rng.choice(len(px), 4000, replace=False)]
    c = px[rng.choice(len(px), min(k, len(px)), replace=False)].copy()
    for _ in range(iters):
        lab = ((px[:, None, :] - c[None]) ** 2).sum(-1).argmin(1)
        for j in range(len(c)):
            m = lab == j
            if m.any(): c[j] = px[m].mean(0)
    return c

def _nearest(img, centers):
    """distance from every pixel to the nearest of the colours"""
    d = None
    for c in centers:
        e = ((img - c) ** 2).sum(-1)
        d = e if d is None else np.minimum(d, e)
    return np.sqrt(d)

class StudioCutout:
    # ------------------------------------------------------------------ selections as whole-picture masks
    def _sel_from_full(self, full):
        """make the selection from a picture-sized mask (or none, if it's empty)"""
        ys = np.flatnonzero(full.max(1) > 0.01); xs = np.flatnonzero(full.max(0) > 0.01)
        if not len(ys): self.sel = None; self._x_overlay(); return False
        x0, y0, x1, y1 = int(xs[0]), int(ys[0]), int(xs[-1]) + 1, int(ys[-1]) + 1
        self.sel = dict(kind="mask", box=(x0, y0, x1, y1), mask=np.ascontiguousarray(full[y0:y1, x0:x1], np.float32), float=None); self._x_overlay(); return True

    def _combine(self, new_full, how):
        """new: replace the selection; add / subtract: with the one there is"""
        old = self._sel_full() if self.sel is not None else None
        if how == "add" and old is not None: new_full = np.maximum(old, new_full)
        elif how == "sub": new_full = np.clip((old if old is not None else np.zeros_like(new_full)) - new_full, 0, 1)
        return self._sel_from_full(new_full)

    def _how(self, e):
        st = getattr(e, "state", 0)
        return "add" if st & 0x1 else "sub" if st & ALT else "new"

    def _source(self):
        """what the colour tools look at: the whole picture, or the layer you're on (Options > Fill > Fill from)"""
        if self.fill_sample.get() == "This layer":
            L = self.cur.img; return np.dstack([L.a * L.alpha[..., None], L.alpha[..., None] * 255]).astype(np.float32)
        return self._comp.astype(np.float32)

    def _region(self, p, contiguous=True):
        """the area of about the colour at p (Tolerance), joined up or everywhere"""
        from scipy.ndimage import label, binary_dilation
        src = self._source(); x, y = int(p[0]), int(p[1]); w, h = self.size_wh
        if not (0 <= x < w and 0 <= y < h): return None
        tol = 1 + self.gopts["tolerance"] / 100 * 255 * src.shape[2] * 0.45
        same = np.abs(src - src[y, x]).sum(2) < tol
        if contiguous: lab, _ = label(same); same = lab == lab[y, x]
        return binary_dilation(same, iterations=1).astype(np.float32)

    # ------------------------------------------------------------------ Magic Wand with add / take away
    def _wand(self, p, how="new"):
        m = self._region(p, contiguous=self.wand_contig.get() if hasattr(self, "wand_contig") else True)
        if m is not None: self._combine(m, how)

    # ------------------------------------------------------------------ Smart Select
    def _smart_select(self, box, how="new"):
        """the thing inside the box, without its background"""
        from scipy import ndimage as ndi
        w, h = self.size_wh; x0, y0, x1, y1 = box; x0, y0, x1, y1 = max(0, int(x0)), max(0, int(y0)), min(w, int(x1)), min(h, int(y1))
        if x1 - x0 < 8 or y1 - y0 < 8: T.banner(self.app, "DRAG A BIGGER BOX — round the whole thing you want"); return
        img = self._source()[y0:y1, x0:x1, :3]; H, W = img.shape[:2]
        k = max(2, min(H, W) // 25)                                                  # what's round the box's edge is background
        edge = np.ones((H, W), bool); edge[k:-k, k:-k] = False
        yy, xx = np.mgrid[0:H, 0:W]; core = ((xx - W / 2) / (W * 0.25)) ** 2 + ((yy - H / 2) / (H * 0.25)) ** 2 < 1   # the middle: the thing
        fg = core.copy()
        for it in range(3):                                                         # colour models, refined from the last guess
            F = _kmeans(img[fg & ~edge] if (fg & ~edge).any() else img[core], 6, seed=it); B = _kmeans(img[edge | (~fg & ~core)], 8, seed=10 + it)
            dF, dB = _nearest(img, F), _nearest(img, B); fg = (dF < dB * 0.95) & ~edge
            fg = ndi.binary_opening(fg, iterations=1); fg = ndi.binary_closing(fg, iterations=2)
            lab, n = ndi.label(fg)
            if n:                                                                    # keep the parts that reach the middle (or the biggest)
                touch = np.unique(lab[core & fg]); touch = touch[touch > 0]
                if not len(touch): touch = [int(np.bincount(lab.ravel())[1:].argmax()) + 1]
                fg = np.isin(lab, touch)
            fg = ndi.binary_fill_holes(fg)
        if not fg.any(): T.banner(self.app, "COULDN'T FIND IT — try a box that fits closer, or the Magic Wand"); return
        soft = np.clip(ndi.gaussian_filter(fg.astype(np.float32), 0.8) * 1.4 - 0.2, 0, 1)   # a soft edge, no jaggies
        full = np.zeros((h, w), np.float32); full[y0:y1, x0:x1] = soft; self._combine(full, how)

    # ------------------------------------------------------------------ Magic Eraser
    def _magic_erase(self, p):
        from scipy import ndimage as ndi
        m = self._region(p, contiguous=self.wand_contig.get() if hasattr(self, "wand_contig") else True)
        if m is None: return
        m = np.clip(ndi.gaussian_filter(m, 0.7) * 1.2, 0, 1)
        k = self._sel_full()
        if k is not None: m = m * k                                                  # inside the selection only
        self._begin_edit(); C = self.cur.cv; C.alpha = C.alpha * (1 - m); self._dirty = None          # (all the way, not at the brush's opacity)
        r = self._commit_edit()
        if r: self._recomp(r)
        self._draw()

    # ------------------------------------------------------------------ Remove background
    def remove_background(self):
        """erase what's round the edges of the layer you're on (the background of a photo or a drawing), joined to the edges"""
        from scipy import ndimage as ndi
        L = self.cur.img; al = L.alpha
        if al.max() < 0.05: T.banner(self.app, "THIS LAYER IS EMPTY — pick the layer with the picture on it"); return
        h, w = al.shape; img = L.a; border = np.zeros((h, w), bool); b = max(2, min(h, w) // 100)
        border[:b] = border[-b:] = True; border[:, :b] = border[:, -b:] = True; border &= al > 0.5
        if border.sum() < 20: T.banner(self.app, "NO BACKGROUND TO TAKE AWAY — the edges are already see-through"); return
        B = _kmeans(img[border], 6, seed=3); d = _nearest(img, B)
        tol = 10 + self.gopts["tolerance"] / 100 * 120                               # Options > Fill > Tolerance: how different still counts
        like = (d < tol) & (al > 0.02)
        lab, n = ndi.label(like); edge_labels = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])); edge_labels = edge_labels[edge_labels > 0]
        bgm = np.isin(lab, edge_labels)
        if not bgm.any(): T.banner(self.app, "COULDN'T TELL THE BACKGROUND — raise Tolerance (Options > Fill) and try again"); return
        bgm = ndi.binary_opening(bgm, iterations=1)
        soft = np.clip(ndi.gaussian_filter(bgm.astype(np.float32), 0.9) * 1.3, 0, 1)
        self._begin_edit(); C = self.cur.cv
        if C is not L: T.banner(self.app, "TURN OFF PAINT ON MASK first"); self._edit = None; return
        C.alpha = C.alpha * (1 - soft); self._dirty = None; r = self._commit_edit()
        if r: self._recomp(r)
        self._draw(); T.banner(self.app, "BACKGROUND REMOVED — Ctrl+Z puts it back; Tolerance (Options > Fill) changes how much goes", "success")

    # ------------------------------------------------------------------ selection helpers
    def sel_invert(self):
        w, h = self.size_wh; k = self._sel_full(); self._sel_commit()
        self._sel_from_full(np.ones((h, w), np.float32) if k is None else 1 - k)

    def sel_grow(self, grow=True):
        from scipy import ndimage as ndi
        k = self._sel_full()
        if k is None: T.banner(self.app, "NOTHING SELECTED — select something first"); return
        n = max(1, int(self.gopts.get("grow", 4)))
        m = ndi.binary_dilation(k > 0.5, iterations=n) if grow else ndi.binary_erosion(k > 0.5, iterations=n)
        self._sel_from_full(m.astype(np.float32))

    def sel_to_layer(self, cut=True):
        """what's selected on this layer, onto a new layer above it (Cut also takes it off this one)"""
        from draw_studio import Layer
        self._sel_commit(); k = self._sel_full()
        if k is None: T.banner(self.app, "NOTHING SELECTED — select something first (Smart Select, Magic Wand, Lasso...)"); return
        src = self.cur; w, h = self.size_wh; L = Layer(w, h, f"{src.name} {'cut' if cut else 'copy'}")
        L.img.a = src.img.a.copy(); L.img.alpha = src.shown() * k; L.group = self._group_of(src)
        if cut:
            self._begin_edit(); src.img.alpha = src.img.alpha * (1 - k); self._dirty = None; self._commit_edit()
        self.layers.insert(self.li + 1, L); self.li += 1; self.sel_group = None; self.sel = None
        self._recomp(); self._layers_ui(); self._draw()
        nm = self.make_sticker(L.img.a, L.img.alpha, quiet=True)                   # everything cut out is kept as a sticker too
        T.banner(self.app, f"{'CUT' if cut else 'COPIED'} TO A NEW LAYER" + (f" — and kept as '{nm}' (Color view > Stickers)" if nm else ""), "success")

    def _cutout_options(self, parent, frame):
        self._rule(parent); r = frame(parent, fill="x", pady=(4, 2)); T.Text(r, "CUT OUT", font=T.f(10, "underline")).pack()
        rows = [(("Remove background", self.remove_background, "Erase the background round the edges of this layer (photos too). Ctrl+Z puts it back"),),
                (("Cut to layer", lambda: self.sel_to_layer(True), "What's selected moves onto a new layer of its own"),
                 ("Copy to layer", lambda: self.sel_to_layer(False), "What's selected is copied onto a new layer")),
                (("Make sticker", self.make_sticker, "What's selected on this layer (or all of it) becomes a sticker, kept in the Color view"),),
                (("Invert", self.sel_invert, "Select everything that isn't selected (Ctrl+Shift+I)"),),
                (("Grow", lambda: self.sel_grow(True), "Make the selection bigger all round"), ("Shrink", lambda: self.sel_grow(False), "Make the selection smaller all round"))]
        for row in rows:
            f = frame(parent, fill="x", pady=(2, 1))
            for i, (text, cmd, tip) in enumerate(row):
                self._tip(self._small_btn(f, text, cmd), tip).pack(side="left" if i == 0 else "right", expand=len(row) == 1)
        self.gopts.setdefault("grow", 4.0)
        row = self._slider_row(parent, "By:", self.gopts["grow"] / 50, lambda v: self._set_g("grow", v * 50), f"{int(self.gopts['grow'])}px")
        row.entry.bind("<Return>", lambda e: self._typed(row, lambda x: self._set_g("grow", x, sync=True))); row.top, row.unit = 50, "px"; self.g_rows["grow"] = row
        self._tip(row.slider, "How many pixels Grow and Shrink change the selection by")
        self.sticker_border = tk.BooleanVar(value=True)
        f = frame(parent, fill="x", pady=2); T.Text(f, "Sticker border", font=T.f(9)).pack(side="left")
        self._tip(T.Toggle(f, self.sticker_border), "New stickers get a white border round them, like a real sticker").pack(side="right")
        self.wand_contig = tk.BooleanVar(value=True)
        f = frame(parent, fill="x", pady=2); T.Text(f, "Wand: joined-up only", font=T.f(9)).pack(side="left")
        self._tip(T.Toggle(f, self.wand_contig), "Magic Wand and Magic Eraser take only the joined-up area (off: that colour everywhere)").pack(side="right")

    # ------------------------------------------------------------------ STICKERS: everything you cut out, kept to place again
    def _sticker_dir(self):
        import os, paths
        d = paths.data("stickers"); os.makedirs(d, exist_ok=True); return d

    def _sticker_files(self):
        import os
        d = self._sticker_dir()
        try: return sorted((f for f in os.listdir(d) if f.lower().endswith(".png")), key=lambda f: os.path.getmtime(os.path.join(d, f)))
        except OSError: return []

    def make_sticker(self, a=None, al=None, quiet=False):
        """save a cut-out as a sticker (a white border round it, like a real sticker if Options > Cut Out > Sticker border is on).
        With nothing given: what's selected on this layer, or everything on it"""
        import os, time, prefs
        from PIL import Image
        from scipy import ndimage as ndi
        if a is None:
            k = self._sel_full(); L = self.cur; a = L.img.a; al = L.shown() * (k if k is not None else 1)
        ys = np.flatnonzero(al.max(1) > 0.02); xs = np.flatnonzero(al.max(0) > 0.02)
        if not len(ys):
            if not quiet: T.banner(self.app, "NOTHING TO MAKE A STICKER OF — select something, or pick a layer with paint on it")
            return None
        y0, y1, x0, x1 = ys[0], ys[-1] + 1, xs[0], xs[-1] + 1; a, al = a[y0:y1, x0:x1], al[y0:y1, x0:x1]
        b = max(3, int(max(a.shape[:2]) * 0.03)) if getattr(self, "sticker_border", None) is None or self.sticker_border.get() else 0
        if b:                                                                     # a white border, the way stickers are cut
            H, W = al.shape; pad = b + 2; A = np.zeros((H + 2 * pad, W + 2 * pad), np.float32); A[pad:pad + H, pad:pad + W] = al
            C = np.full((H + 2 * pad, W + 2 * pad, 3), 255.0, np.float32); C[pad:pad + H, pad:pad + W] = a * al[..., None] + 255 * (1 - al[..., None])
            dist = ndi.distance_transform_edt(A < 0.5); ring = np.clip(b + 1 - dist, 0, 1)
            al = np.maximum(A, ring); a = C
        im = Image.fromarray(np.dstack([np.clip(a, 0, 255), np.clip(al, 0, 1)[..., None] * 255]).astype(np.uint8), "RGBA")
        if max(im.size) > 1200: im.thumbnail((1200, 1200), Image.LANCZOS)
        n = len(self._sticker_files()) + 1; name = f"Sticker {n}"
        while os.path.exists(os.path.join(self._sticker_dir(), name.replace(" ", "_") + ".png")): n += 1; name = f"Sticker {n}"
        try: im.save(os.path.join(self._sticker_dir(), name.replace(" ", "_") + ".png"))
        except Exception: prefs.log_note("saving a sticker"); T.banner(self.app, "COULDN'T SAVE THE STICKER"); return None
        self._fill_stickers()
        if not quiet: T.banner(self.app, f"STICKER MADE — '{name}' is under Stickers in the Color view", "success")
        return name

    def import_stickers(self, paths_in=None):
        """add sticker pictures: PNG files, or .zip files (only the PNGs inside are read). Each is checked as a real picture,
        shrunk to 1200px at most and saved in your stickers folder under its own name"""
        import os, io, re, zipfile, prefs
        from PIL import Image
        if paths_in is None:
            from tkinter import filedialog
            paths_in = filedialog.askopenfilenames(parent=self, title="Import stickers", filetypes=[("Stickers (PNG or ZIP)", "*.png *.zip"), ("All files", "*.*")])
        d = self._sticker_dir(); done = 0; bad = 0
        def add(stem, data):
            nonlocal done, bad
            try:
                im = Image.open(io.BytesIO(data)); im.load(); im = im.convert("RGBA")
                if max(im.size) > 1200: im.thumbnail((1200, 1200), Image.LANCZOS)
                stem = re.sub(r"[^A-Za-z0-9 _-]+", "", stem).strip().replace(" ", "_")[:60] or "Sticker"
                name, n = stem, 2
                while os.path.exists(os.path.join(d, name + ".png")): name = f"{stem}_{n}"; n += 1
                im.save(os.path.join(d, name + ".png")); done += 1
            except Exception: bad += 1
        for fp in paths_in or ():
            try:
                if fp.lower().endswith(".zip"):
                    with zipfile.ZipFile(fp) as z:
                        for info in z.infolist():
                            nm = info.filename
                            if info.is_dir() or not nm.lower().endswith(".png") or "__MACOSX" in nm or os.path.basename(nm).startswith("."): continue
                            if info.file_size > 40_000_000: bad += 1; continue
                            add(os.path.splitext(os.path.basename(nm))[0], z.read(info))
                else:
                    with open(fp, "rb") as f: add(os.path.splitext(os.path.basename(fp))[0], f.read())
            except Exception: prefs.log_note("importing stickers", fp); bad += 1
        if done or bad:
            self._fill_stickers()
            T.banner(self.app, f"{done} STICKER{'S' if done != 1 else ''} ADDED" + (f" — {bad} couldn't be read" if bad else ""), "success" if done else "error")
        return done

    def _fill_stickers(self):
        """STICKERS in the Color view (under the colour ring and history): one picture per sticker; click to place it, right-click
        to delete it"""
        import os, brushes
        from PIL import Image, ImageTk, ImageDraw
        box = getattr(self, "_sticker_box", None)
        if box is None: return
        for w in box.winfo_children(): w.destroy()
        files = self._sticker_files(); bg = box["bg"]; self._sticker_ph = []
        if not files:
            T.Text(box, "Cut something out (Options > Cut Out) and it's kept here as a sticker", muted=True, font=T.f(7), wraplength=self._apx(220)).grid(row=0, column=0, columnspan=4, pady=3)
            return
        S = self._apx(48)
        for i, f in enumerate(files):
            name = os.path.splitext(f)[0].replace("_", " "); eng = brushes.add_sticker(f, name)
            try: st = Image.open(os.path.join(self._sticker_dir(), f)).convert("RGBA")
            except Exception: continue
            sel = eng == getattr(self, "brush", None)
            tile = Image.new("RGBA", (S, S), (0, 0, 0, 0)); ImageDraw.Draw(tile).rounded_rectangle((0, 0, S - 1, S - 1), radius=S // 6, fill=(16, 24, 48, 255),
                                                                                                       outline=T.PALETTE["border"] if sel else (60, 90, 140), width=2 if sel else 1)
            st.thumbnail((S - 8, S - 8), Image.LANCZOS); tile.alpha_composite(st, ((S - st.width) // 2, (S - st.height) // 2))
            ph = ImageTk.PhotoImage(tile); self._sticker_ph.append(ph)
            lb = tk.Label(box, image=ph, bd=0, highlightthickness=0, bg=bg, cursor="hand2"); lb.grid(row=i // 4, column=i % 4, padx=2, pady=2)
            lb.bind("<Button-1>", lambda e, eng=eng, name=name, f=f: self._use_sticker(eng, name, f))
            lb.bind("<Button-3>", lambda e, f=f, name=name: self._delete_sticker(f, name))
            self._tip(lb, f"{name}: click to place it (drag for a row), right-click to delete it")
        if getattr(self, "_cfit", None): self.after(30, self._cfit)

    def _use_sticker(self, eng, name, f):
        import os
        from PIL import Image
        self.set_brush(eng, name); self._fill_stickers()
        try: w, h = Image.open(os.path.join(self._sticker_dir(), f)).size; self.set_size(min(max(w, h), self._size_max()))   # its own size to start with
        except Exception: pass

    def _delete_sticker(self, f, name):
        import os
        from tkinter import messagebox
        if not messagebox.askyesno("Delete sticker", f"Delete '{name}'?", parent=self): return
        try: os.remove(os.path.join(self._sticker_dir(), f))
        except OSError: pass
        self._fill_stickers()
