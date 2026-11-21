"""
studio_ai.py: the AI cut-out tools (Photoshop-style), run on this PC by ai_cutout.py.

  Select Subject        Select menu / Options > Cut Out: the picture's main subject, hair and fur included
  Object Selection      (tile) drag a box round a thing, or click it: just that thing. Shift adds, Alt takes away
  Quick Selection       (tile) paint over a thing: the selection snaps to its edges; more strokes add, Alt-strokes take away
  Remove Background     the subject kept, the rest hidden with a layer mask (nothing is lost: paint on the mask to fix it)
  Magic Remove          (tool) paint over a person, a wire, a spot, anything: it's filled in from what's round it (LaMa), like
                        Photoshop's Remove tool; Remove selected does the same to whatever is selected (Content-Aware Fill)
  Blur Background       the subject stays sharp, the rest of the layer is blurred (Options > Magic: how much)
  Magic Expand          a bigger canvas on every side (Options > Magic: by how much), the new edges filled in to carry the
                        picture on (Photoshop's Generative Expand, without the cloud)
  Upscale 2x / 4x       the whole picture bigger with real detail (Real-ESRGAN), every layer
  Smooth Skin           skin evened out on this layer (or what's selected), pores and edges kept
  Refine Edge           Options > Cut Out: Edge radius, Smooth, Contrast, Shift edge, Refine hair & fur; Decontaminate colors
                        (no background colour left round the edges of what you cut out). AI selections are refined as they're
                        made; the Refine edge button does it again (to any selection) with the sliders as they are now.

The models download once, the first time one is needed (you're asked first). Without them (offline, or you said no), the
colour-based tools in studio_cutout.py do the job instead. The slow work runs in the background: the studio stays usable.
"""
import threading, queue, hashlib, math
import numpy as np
import tkinter as tk
import theme as T
import prefs
import ai_cutout as AI

QUICK_TOOL = "quick_sel"
REMOVE_TOOL = "magic_remove"


class StudioAI:
    # ------------------------------------------------------------------ background work, models
    def _ai_init(self):
        if hasattr(self, "_aiq"): return
        self._aiq = queue.Queue(); self._ai_busy = False; self._sam = AI.Sam(); self._subj_cache = (None, None); self._sam_wait = []
        self._sam_job = None
        for k, v in (("edge_radius", 8.0), ("edge_smooth", 0.0), ("edge_contrast", 0.0), ("edge_shift", 0.0)): self.gopts.setdefault(k, v)
        if not hasattr(self, "refine_hair"): self.refine_hair = tk.BooleanVar(value=True)
        if not hasattr(self, "decontam"): self.decontam = tk.BooleanVar(value=True)
        self.after(120, self._ai_poll)

    def _ai_poll(self):
        try:
            while True:
                fn = self._aiq.get_nowait()
                try: fn()
                except Exception as ex: prefs.log_note("an AI cut-out step", repr(ex))
        except queue.Empty: pass
        try: self.after(120, self._ai_poll)
        except tk.TclError: pass

    def _ai_bg(self, work, done, msg=None):
        """work() in the background; done(result) back on the studio's own thread. One job at a time"""
        self._ai_init()
        if self._ai_busy: T.banner(self.app, "STILL WORKING ON THE LAST ONE — one moment"); return
        self._ai_busy = True
        if msg: T.banner(self.app, msg, "success", seconds=60)
        try: self.config(cursor="watch")
        except tk.TclError: pass
        def run():
            try: r = work(); err = None
            except Exception as ex: r = None; err = ex; prefs.log_note("AI cut-out", repr(ex))
            def back():
                self._ai_busy = False
                if msg:
                    try: T._hide_banner(self.app.winfo_toplevel())                   # (the "working..." message goes)
                    except Exception: pass
                try: self.config(cursor="")
                except tk.TclError: pass
                if err is not None: T.banner(self.app, "THAT DIDN'T WORK — the details are in the log"); return
                done(r)
            self._aiq.put(back)
        threading.Thread(target=run, daemon=True).start()

    def _ai_ready(self, kind, then, fallback=None):
        """the models for kind ('subject' / 'sam') ready? then(); if they need downloading, ask first (once a session) and fetch
        them in the background; no / offline: fallback() (the colour tools), if there is one"""
        self._ai_init()
        if not AI.runtime_ok():
            prefs.log_note("AI cut-out", "onnxruntime missing", quiet_missing=True)
            if fallback: fallback()
            return
        if AI.have(kind): return then()
        if kind in getattr(self, "_ai_said_no", set()):
            if fallback: fallback()
            return
        mb = AI.download_size(kind) / 1e6
        what = {"subject": "Select Subject, Remove Background and Blur Background", "sam": "Object Selection and Quick Selection",
                "remove": "Magic Remove and Magic Expand", "upscale": "Upscale"}[kind]
        ans = T.popup(self, "A ONE-TIME DOWNLOAD", f"{what} use an AI model that runs on this PC (nothing is sent anywhere).\n\n"
                      f"It's {mb:.0f} MB, downloaded once. Download it now?", buttons=(("Download", "normal"), ("Not now", "normal")))
        if ans != "Download":
            self.__dict__.setdefault("_ai_said_no", set()).add(kind)
            T.banner(self.app, "OK — the colour-based tools will do it instead (Window > Cut Out)" if kind != "remove" else "OK — not now (the Clone brush can cover things by hand)")
            if fallback: fallback()
            return
        state = {"last": -1}
        def prog(d, t):
            pc = int(d * 100 / max(1, t))
            if pc != state["last"] and pc % 2 == 0:
                state["last"] = pc; self._aiq.put(lambda pc=pc: T.banner(self.app, f"DOWNLOADING THE AI — {pc}%", "success", seconds=30))
        self._ai_bg(lambda: AI.ensure(kind, prog), lambda r: (T.banner(self.app, "AI READY", "success"), then()))

    def _ai_rgb(self):
        """what the AI looks at: the picture as you see it (all layers)"""
        return np.asarray(self._comp[..., :3], np.float32)

    def _pic_key(self):
        c = self._comp; return (c.shape, hashlib.md5(np.ascontiguousarray(c[::7, ::7]).tobytes()).hexdigest())

    def _refined(self, rgb, m):
        g = self.gopts
        return AI.refine(rgb, m, radius=int(g["edge_radius"]), hair=self.refine_hair.get(), smooth=g["edge_smooth"],
                         contrast=g["edge_contrast"], shift=g["edge_shift"])

    # ------------------------------------------------------------------ Select Subject
    def select_subject(self, how="new"):
        def go():
            rgb = self._ai_rgb(); key = self._pic_key()
            def work():
                k, m = self._subj_cache
                if k != key: m = AI.subject(rgb); self._subj_cache = (key, m)
                return self._refined(rgb, m)
            def done(m):
                if m is None or m.max() < 0.5: T.banner(self.app, "NO CLEAR SUBJECT — try Object Selection round the thing you want"); return
                self._sel_commit(); self._combine(m, how); self._auto_sections() if hasattr(self, "_auto_sections") else None
                T.banner(self.app, "SUBJECT SELECTED — Options > Cut Out: refine the edge, cut it to a layer, or make a sticker", "success")
            self._ai_bg(work, done, "SELECTING THE SUBJECT…")
        self._ai_ready("subject", go, fallback=lambda: T.banner(self.app, "SELECT SUBJECT NEEDS THE AI — try Smart / Magic Wand selections"))

    # ------------------------------------------------------------------ Segment Anything: the picture, read once
    def _sam_prepare(self, then=None):
        """read the picture for Segment Anything (slow, in the background) unless it's already been read as it is now"""
        key = self._pic_key()
        if self._sam.key == key and self._sam.emb is not None:
            if then: then()
            return
        if then: self._sam_wait.append(then)
        if getattr(self, "_sam_reading", None) == key: return
        self._sam_reading = key; rgb = self._ai_rgb()
        def work(): self._sam.set_image(rgb, key); return True
        def done(_):
            self._sam_reading = None; waits, self._sam_wait = self._sam_wait, []
            for f in waits: f()
        if self._ai_busy: self._sam_reading = None; self.after(400, lambda: self._sam_prepare()); return
        self._ai_bg(work, done, "READING THE PICTURE FOR OBJECT SELECTION…" if then else None)

    def _sam_warm(self):
        """the Object / Quick Selection tool was picked: read the picture now, so the first click is quick"""
        self._ai_init()
        if AI.runtime_ok() and AI.have("sam") and not self._ai_busy: self._sam_prepare()

    # ------------------------------------------------------------------ Object Selection (box or click) and Quick Selection (strokes)
    def _object_select(self, box, how="new"):
        x0, y0, x1, y1 = box; click = (x1 - x0) < 6 and (y1 - y0) < 6
        def fallback():
            if click: T.banner(self.app, "DRAG A BOX ROUND IT — clicking needs the AI"); return
            self._smart_select(box, how)
        def go():
            def ask():
                rgb = self._ai_rgb()
                def work():
                    if click: m = AI.object_mask(rgb, self._sam, pos=[((x0 + x1) / 2, (y0 + y1) / 2)])
                    else: m = AI.object_mask(rgb, self._sam, box=(x0, y0, x1, y1))
                    return self._refined(rgb, m)
                def done(m):
                    if m is None or m.max() < 0.5: T.banner(self.app, "NOTHING FOUND THERE — try a box round the whole thing"); return
                    self._sel_commit(); self._combine(m, how)
                self._ai_bg(work, done, "SELECTING…")
            self._sam_prepare(ask)
        self._ai_ready("sam", go, fallback)

    def _quick_select(self, pts, how):
        if self.sel is not None and how == "new": how = "add"                      # (more strokes add, as in Photoshop)
        step = max(1, len(pts) // 8); pos = pts[::step][:10]
        def go():
            def ask():
                rgb = self._ai_rgb()
                def work(): return self._refined(rgb, AI.object_mask(rgb, self._sam, pos=pos, use_subject=False))
                def done(m):
                    if m is None or m.max() < 0.5: return
                    self._sel_commit(); self._combine(m, how)
                self._ai_bg(work, done)
            self._sam_prepare(ask)
        def fallback():                                                              # without the AI: the colour areas you painted over
            for p in pos[:6]: self._wand(p, "add" if how != "sub" else "sub")
        self._ai_ready("sam", go, fallback)

    # ------------------------------------------------------------------ Remove Background (AI, onto a layer mask)
    def remove_background(self):
        L = self.cur
        if L.img.alpha.max() < 0.05: T.banner(self.app, "THIS LAYER IS EMPTY — pick the layer with the picture on it"); return
        a = L.img.alpha[..., None]; rgb = L.img.a * a + 255.0 * (1 - a)
        def go():
            def work(): return self._refined(rgb, AI.subject(rgb))
            def done(m):
                if m is None or m.max() < 0.5: T.banner(self.app, "NO CLEAR SUBJECT ON THIS LAYER — use Object Selection, then Cut to layer"); return
                self._whole_snapshot()                                               # (Ctrl+Z puts it back)
                L.add_mask(); L.maskcv.alpha = np.maximum(L.maskcv.alpha, 1 - m).astype(np.float32)
                if self.decontam.get(): L.img.a = AI.foreground(L.img.a, m).astype(np.float32)   # no old-background fringe at the edges
                self._recomp(); self._layers_ui(); self._draw(); self.changed = True
                T.banner(self.app, "BACKGROUND HIDDEN WITH A MASK — paint on the mask to fix it; Delete mask brings it all back", "success")
            self._ai_bg(work, done, "REMOVING THE BACKGROUND…")
        self._ai_ready("subject", go, fallback=self._remove_background_colour)

    # ------------------------------------------------------------------ Magic Remove (paint over it: gone)
    def _mr_warm(self):
        """the Magic Remove tool was picked: load its model now (in the background), so the first stroke is quick"""
        self._ai_init()
        if AI.runtime_ok() and AI.have("remove") and "lama" not in AI._sessions and not getattr(self, "_mr_loading", False):
            self._mr_loading = True
            def load():
                try: AI._session("lama")
                except Exception as ex: prefs.log_note("loading Magic Remove", repr(ex))
                self._mr_loading = False
            threading.Thread(target=load, daemon=True, name="MagicRemoveLoad").start()

    def _mr_width(self): return max(2.0, float(self.size))                        # the stroke: the brush size (in picture pixels)

    def _mr_down(self, e, p):
        if self._ai_busy: T.banner(self.app, "STILL WORKING ON THE LAST ONE — one moment"); return
        self._mr_pts = [(p[0], p[1])]; self._mr_show()

    def _mr_drag(self, p):
        pts = getattr(self, "_mr_pts", None)
        if pts is None: return
        if math.hypot(p[0] - pts[-1][0], p[1] - pts[-1][1]) * (self.zoom or 1) >= 2: pts.append((p[0], p[1])); self._mr_show()

    def _mr_show(self):
        """the stroke shows in see-through red as you paint, at its real width"""
        self.cv.delete("xov"); pts = self._mr_pts; wd = max(3, int(self._mr_width() * (self.zoom or 1)))
        sc = [c for q in pts for c in self._x_scr(*q)]
        if len(sc) == 2: x, y = sc; r = wd / 2; self.cv.create_oval(x - r, y - r, x + r, y + r, fill="#ff3c5a", outline="", stipple="gray50", tags="xov")
        else: self.cv.create_line(*sc, fill="#ff3c5a", width=wd, capstyle="round", joinstyle="round", stipple="gray50", tags="xov")

    def _mr_up(self, e, p):
        pts = getattr(self, "_mr_pts", None); self._mr_pts = None
        if not pts: return
        from PIL import Image, ImageDraw
        w, h = self.size_wh; m = Image.new("L", (w, h), 0); d = ImageDraw.Draw(m); wd = self._mr_width()
        if len(pts) > 1: d.line(pts, fill=255, width=int(round(wd)), joint="curve")
        for x, y in (pts[0], pts[-1]) if len(pts) > 1 else pts: d.ellipse((x - wd / 2, y - wd / 2, x + wd / 2, y + wd / 2), fill=255)
        self.magic_remove(np.asarray(m) > 127, keep_overlay=True)

    def remove_selected(self):
        """Magic Remove on whatever is selected (Photoshop: Content-Aware Fill / Delete and Fill Selection)"""
        m = self._sel_full() if self.sel is not None else None
        if m is None: T.banner(self.app, "SELECT IT FIRST — or pick Magic Remove and paint over it"); return
        hole = m > 0.5; self._sel_commit(); self.sel = None; self._x_overlay(); self.magic_remove(hole)

    def magic_remove(self, hole, keep_overlay=False):
        """fill the hole from its surroundings, on the layer you're on (one Undo step). On an empty or see-through layer it
        works from the picture as you see it, and the fill goes onto that layer (like Photoshop's Sample All Layers)"""
        if not hole.any(): self.cv.delete("xov"); return
        L = self.cur
        if L.cv is not L.img: self.cv.delete("xov"); T.banner(self.app, "YOU'RE ON THE LAYER'S MASK — click the layer's picture first"); return
        ys, xs = np.where(hole)
        y0, y1, x0, x1 = max(0, ys.min() - 20), ys.max() + 21, max(0, xs.min() - 20), xs.max() + 21
        own = float(L.img.alpha[y0:y1, x0:x1].mean()) > 0.6                          # the layer has the picture on it here
        src = np.asarray(L.img.a, np.float32) if own else np.asarray(self._comp[..., :3], np.float32)
        def go():
            if not keep_overlay: self.cv.delete("xov")
            def work(): return AI.inpaint(src, hole)
            def done(res):
                self.cv.delete("xov")
                if res is None: return
                self._begin_edit()
                k = hole.astype(np.float32); soft = np.clip(res, 0, 255).astype(np.float32)
                L.img.a[...] = np.where(hole[..., None], soft, L.img.a) if own else soft * k[..., None] + L.img.a * (1 - k[..., None])
                if not own: L.img.alpha[...] = np.maximum(L.img.alpha, k)
                self._dirty = None; r = self._commit_edit(); self._recomp(r) if r else self._recomp(); self._draw(); self.changed = True
                T.banner(self.app, "REMOVED — Ctrl+Z puts it back; paint over anything left to tidy it", "success")
            self._ai_bg(work, done, "REMOVING…")
        def no():
            self.cv.delete("xov")
        self._ai_ready("remove", go, fallback=no)

    # ------------------------------------------------------------------ Magic Expand, Upscale, Smooth Skin
    def magic_expand(self):
        """the canvas grows by Options > Magic > Expand (% of each side, half on each edge); the layer you're on gets the new edges
        filled in from the picture (from the picture as you see it if this layer is see-through there). One Undo step"""
        w, h = self.size_wh; pc = float(self.gopts.get("expand", 20.0)) / 100
        dx, dy = int(round(w * pc / 2)), int(round(h * pc / 2))
        if max(w + 2 * dx, h + 2 * dy) > 8000: T.banner(self.app, "THAT WOULD BE OVER 8000 PIXELS — expand by less"); return
        L = self.cur
        if L.cv is not L.img: T.banner(self.app, "YOU'RE ON THE LAYER'S MASK — click the layer's picture first"); return
        own = float(L.img.alpha.mean()) > 0.95
        src = np.asarray(L.img.a if own else self._comp[..., :3], np.float32)
        def go():
            def work(): return AI.expand(src, dx, dy, dx, dy)
            def done(big):
                if big is None: return
                W, H = w + 2 * dx, h + 2 * dy; self._whole_snapshot()
                def fn(arr):                                                       # every layer, mask and the paper: the same picture, more room
                    out = np.full((H, W) + arr.shape[2:], 255.0 if arr.ndim == 3 else 0.0, np.float32)
                    out[dy:dy + h, dx:dx + w] = arr; return out
                self._resize_doc(fn, W, H)
                ring = np.ones((H, W), bool); ring[dy:dy + h, dx:dx + w] = False         # the new edges
                if own: L.img.a = big.astype(np.float32); L.img.alpha = np.ones((H, W), np.float32)
                else: L.img.a = np.where(ring[..., None], big, L.img.a).astype(np.float32); L.img.alpha = np.maximum(L.img.alpha, ring.astype(np.float32))
                self._recomp(); self._draw(); self.set_size_level(self.size_lvl); self.changed = True
                T.banner(self.app, f"EXPANDED TO {W} x {H} — Ctrl+Z undoes it", "success")
            self._ai_bg(work, done, "EXPANDING THE PICTURE… (this can take a minute)")
        self._ai_ready("remove", go, fallback=lambda: None)

    def upscale_picture(self, factor):
        """the whole picture factor (2 / 4) times bigger: each layer's colours with Real-ESRGAN (real detail), see-through-ness and
        masks smoothly. One Undo step"""
        w, h = self.size_wh; W, H = w * factor, h * factor
        if max(W, H) > 8000: T.banner(self.app, f"{W} x {H} IS TOO BIG — up to 8000 pixels each way (try 2x, or crop first)"); return
        layers = list(self.layers); jobs = [L.img.a for L in layers if L.img.alpha.max() > 0.01]; key = self._pic_key()
        def go():
            def work():
                done_, out = [0], {}
                for a in jobs:
                    out[id(a)] = AI.upscale(a, factor)
                    done_[0] += 1; self._aiq.put(lambda n=done_[0]: T.banner(self.app, f"UPSCALING… layer {n} of {len(jobs)}", "success", seconds=120))
                return out
            def done(out):
                if out is None: return
                if self._pic_key() != key: T.banner(self.app, "THE PICTURE CHANGED WHILE IT WAS WORKING — try again"); return
                self._whole_snapshot(); smooth = lambda a2: np.asarray(Image.fromarray(np.ascontiguousarray(a2, np.float32), "F").resize((W, H), Image.BICUBIC), np.float32)
                def fn(arr):
                    if id(arr) in out: return out[id(arr)].astype(np.float32)
                    return np.stack([smooth(arr[..., k]) for k in range(arr.shape[2])], -1) if arr.ndim == 3 else np.clip(smooth(arr), 0, 1)
                self._resize_doc(fn, W, H); self._recomp(); self._draw(); self.set_size_level(self.size_lvl); self.changed = True
                T.banner(self.app, f"UPSCALED {factor}x TO {W} x {H} — Ctrl+Z undoes it", "success")
            self._ai_bg(work, done, "UPSCALING…")
        from PIL import Image
        self._ai_ready("upscale", go, fallback=lambda: None)

    def smooth_skin(self):
        """skin evened out on this layer (only what's selected, if anything is). One Undo step"""
        L = self.cur
        if L.cv is not L.img: T.banner(self.app, "YOU'RE ON THE LAYER'S MASK — click the layer's picture first"); return
        if L.img.alpha.max() < 0.05: T.banner(self.app, "THIS LAYER IS EMPTY — pick the layer with the picture on it"); return
        area = self._sel_full() if self.sel is not None else None; rgb = np.asarray(L.img.a, np.float32); amt = float(self.gopts.get("skin", 70.0)) / 100
        def work(): return AI.smooth_skin(rgb, amt, area)
        def done(res):
            if res is None: return
            self._begin_edit(); L.img.a[...] = res.astype(np.float32); self._dirty = None
            r = self._commit_edit(); self._recomp(r) if r else self._recomp(); self._draw(); self.changed = True
            T.banner(self.app, "SKIN SMOOTHED — Ctrl+Z puts it back", "success")
        self._ai_bg(work, done, "SMOOTHING SKIN…")

    # ------------------------------------------------------------------ Options > MAGIC: every AI tool in one place
    def _magic_options(self, parent, frame):
        self._rule(parent); r = frame(parent, fill="x", pady=(4, 2)); T.Text(r, "MAGIC", font=T.f(10, "underline")).pack()
        self._ai_init()
        rows = [(("Object select", lambda: self.set_tool("smart"), "Object Selection: drag a box round a thing, or click it"),
                 ("Quick select", lambda: self.set_tool("quick_sel"), "Quick Selection: paint over a thing")),
                (("Select subject", self.select_subject, "Select subject"), ("Refine edge", self.refine_selection, "Refine edge")),
                (("Magic remove", lambda: self.set_tool(REMOVE_TOOL), "Magic Remove: paint over anything and it's filled in from what's round it"),
                 ("Remove selected", self.remove_selected, "Fill what's selected from what's round it")),
                (("Remove background", self.remove_background, "Remove background"),), (("Blur background", self.blur_background, "Blur background"),),
                (("Smooth skin", self.smooth_skin, "Smooth skin: on this layer, or what's selected"),),
                (("Magic expand", self.magic_expand, "Magic expand: a bigger canvas, its new edges filled in"),),
                (("Upscale 2x", lambda: self.upscale_picture(2), "The whole picture twice as big, with real detail"),
                 ("Upscale 4x", lambda: self.upscale_picture(4), "The whole picture four times as big, with real detail"))]
        for row in rows:
            f = frame(parent, fill="x", pady=(2, 1))
            for i, (text, cmd, tip) in enumerate(row):
                self._tip(self._small_btn(f, text, cmd), tip).pack(side="left" if i == 0 else "right", expand=len(row) == 1)
        self.gopts.setdefault("bg_blur", 12.0)
        row = self._slider_row(parent, "Blur:", (self.gopts["bg_blur"] - 2) / 38, lambda v: self._set_g("bg_blur", 2 + v * 38), f"{int(self.gopts['bg_blur'])}px")
        row.entry.bind("<Return>", lambda e: self._typed(row, lambda x: self._set_g("bg_blur", x, sync=True))); row.top, row.unit, row.lo = 38, "px", 2
        self._tip(row.slider, "How much Blur background blurs"); self.g_rows["bg_blur"] = row
        for key, label, lo, hi, d, tip in (("skin", "Skin:", 0, 100, 70.0, "How much Smooth skin smooths"), ("expand", "Expand:", 5, 100, 20.0, "How much bigger Magic expand makes the canvas (half on each side)")):
            self.gopts.setdefault(key, d); span = hi - lo
            row = self._slider_row(parent, label, (self.gopts[key] - lo) / span, lambda v, k=key, lo=lo, span=span: self._set_g(k, lo + v * span), f"{int(self.gopts[key])}%")
            row.entry.bind("<Return>", lambda e, k=key, row=row: self._typed(row, lambda x, k=k: self._set_g(k, x, sync=True))); row.top, row.unit, row.lo = span, "%", lo
            self._tip(row.slider, tip); self.g_rows[key] = row

    # ------------------------------------------------------------------ Blur Background
    def blur_background(self):
        """the subject stays sharp, the rest of this layer is blurred (Options > Magic > Blur: how much). One Undo step"""
        L = self.cur
        if L.img.alpha.max() < 0.05: T.banner(self.app, "THIS LAYER IS EMPTY — pick the layer with the picture on it"); return
        if L.cv is not L.img: T.banner(self.app, "YOU'RE ON THE LAYER'S MASK — click the layer's picture first"); return
        rgb = np.asarray(L.img.a, np.float32); amount = float(self.gopts.get("bg_blur", 12.0)); key = self._pic_key()
        def go():
            def work():
                k, m = self._subj_cache
                if k != key: m = AI.subject(rgb); self._subj_cache = (key, m)
                return AI.blur_background(rgb, self._refined(rgb, m), amount)
            def done(res):
                if res is None: return
                self._begin_edit(); L.img.a[...] = np.clip(res, 0, 255).astype(np.float32); self._dirty = None
                r = self._commit_edit(); self._recomp(r) if r else self._recomp(); self._draw(); self.changed = True
                T.banner(self.app, "BACKGROUND BLURRED — Ctrl+Z puts it back", "success")
            self._ai_bg(work, done, "BLURRING THE BACKGROUND…")
        self._ai_ready("subject", go, fallback=lambda: T.banner(self.app, "BLUR BACKGROUND NEEDS THE AI"))

    # ------------------------------------------------------------------ Refine Edge (any selection)
    def refine_selection(self):
        k = self._sel_full()
        if k is None: T.banner(self.app, "NOTHING SELECTED — select something first"); return
        rgb = self._ai_rgb()
        def done(m): self._sel_commit(); self._sel_from_full(m); T.banner(self.app, "EDGE REFINED", "success")
        self._ai_bg(lambda: self._refined(rgb, k), done, "REFINING THE EDGE…")
