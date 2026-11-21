"""
studio_ai.py: the AI cut-out tools (Photoshop-style), run on this PC by ai_cutout.py.

  Select Subject        Select menu / Options > Cut Out: the picture's main subject, hair and fur included
  Object Selection      (tile) drag a box round a thing, or click it: just that thing. Shift adds, Alt takes away
  Quick Selection       (tile) paint over a thing: the selection snaps to its edges; more strokes add, Alt-strokes take away
  Remove Background     the subject kept, the rest hidden with a layer mask (nothing is lost: paint on the mask to fix it)
  Refine Edge           Options > Cut Out: Edge radius, Smooth, Contrast, Shift edge, Refine hair & fur; Decontaminate colors
                        (no background colour left round the edges of what you cut out). AI selections are refined as they're
                        made; the Refine edge button does it again (to any selection) with the sliders as they are now.

The models download once, the first time one is needed (you're asked first). Without them (offline, or you said no), the
colour-based tools in studio_cutout.py do the job instead. The slow work runs in the background: the studio stays usable.
"""
import threading, queue, hashlib
import numpy as np
import tkinter as tk
import theme as T
import prefs
import ai_cutout as AI

QUICK_TOOL = "quick_sel"


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
        what = {"subject": "Select Subject and Remove Background", "sam": "Object Selection and Quick Selection"}[kind]
        ans = T.popup(self, "A ONE-TIME DOWNLOAD", f"{what} use an AI model that runs on this PC (nothing is sent anywhere).\n\n"
                      f"It's {mb:.0f} MB, downloaded once. Download it now?", buttons=(("Download", "normal"), ("Not now", "normal")))
        if ans != "Download":
            self.__dict__.setdefault("_ai_said_no", set()).add(kind)
            T.banner(self.app, "OK — the colour-based tools will do it instead (Window > Cut Out)")
            if fallback: fallback()
            return
        state = {"last": -1}
        def prog(d, t):
            pc = int(d * 100 / max(1, t))
            if pc != state["last"] and pc % 2 == 0:
                state["last"] = pc; self._aiq.put(lambda pc=pc: T.banner(self.app, f"DOWNLOADING THE CUT-OUT AI — {pc}%", "success", seconds=30))
        self._ai_bg(lambda: AI.ensure(kind, prog), lambda r: (T.banner(self.app, "CUT-OUT AI READY", "success"), then()))

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

    # ------------------------------------------------------------------ Refine Edge (any selection)
    def refine_selection(self):
        k = self._sel_full()
        if k is None: T.banner(self.app, "NOTHING SELECTED — select something first"); return
        rgb = self._ai_rgb()
        def done(m): self._sel_commit(); self._sel_from_full(m); T.banner(self.app, "EDGE REFINED", "success")
        self._ai_bg(lambda: self._refined(rgb, k), done, "REFINING THE EDGE…")
