"""
image_pages.py: the AI Images tab's working pages. They share one page (PaintPage), set up differently:

    Text to Image    type what you want -> (the core text model turns it into a clear picture description) -> the image engine paints it
    Image to Image   pick a picture (the box opens in your Images folder) -> words for what to change -> it repaints it
    Sketch to Image  a drawing (your latest one, or any sketch) -> a finished picture in the style you pick; keep your lines or let it go free
    Inpainting       brush over part of a picture -> say what goes there (or nothing, to remove it) -> only that part is repainted

Every page has: LEAVE OUT (what you don't want), FOLLOW MY WORDS (loosely / normal / closely), a SEED (the same seed and words paint
the same picture again, so you can change one thing at a time; every result shows its seed). The words, seed and settings are also
saved inside each PNG. Each page remembers its last settings.

Every picture is saved into your Images folder the moment it's made, so any tab can pick it up from there.
Paint it puts the picture in the app's line of AI jobs (jobs.py): it waits its turn if another tab is using the AI, and the button is
greyed out until it's done.
"""
import os, threading, tkinter as tk
from tkinter import filedialog
import theme as T, prefs, skin, jobs

QUALITY = {"Fast (12 steps)": 12, "Normal (20 steps)": 20, "Best (30 steps)": 30}
CHANGE = {"A little": 0.35, "Some": 0.55, "A lot": 0.75}
KEEP = {"Keep my lines": 0.55, "Balanced": 0.7, "Free": 0.85}                  # Sketch to Image: how far it may move away from the drawing
REPLACE = {"Blend in": 0.75, "Repaint": 0.9, "Fully new": 1.0}                 # Inpainting: how new the brushed part may be
STYLES = {"Painting": "detailed colorful digital painting", "Watercolor": "soft watercolor painting, paper texture",
          "Oil": "oil painting, rich visible brush strokes", "Cartoon": "clean cartoon illustration, bold outlines, bright flat colors",
          "Storybook": "children's storybook illustration, warm and friendly", "Photo": "realistic photo, natural light, sharp detail",
          "Pencil": "colored pencil drawing, soft shading"}
REMOVE_WORDS = "the surrounding background continuing naturally, seamless, nothing there"
BRUSH = {"Small": 8, "Medium": 18, "Large": 36}                                  # brush radius on screen (pixels)

def _frame(parent):
    f = tk.Frame(parent, bg=parent["bg"]); T.on_change(lambda: f.configure(bg=f.master["bg"])); return f

class MaskPad(tk.Canvas):
    """the picture with a brush: left-drag paints over what to change (red), right-drag rubs it out. .mask is full size, white = change"""
    def __init__(self, master, w=560, h=330):
        super().__init__(master, width=w, height=h, highlightthickness=1, cursor="crosshair", bd=0)
        self.pic = self.mask = None; self.brush = tk.StringVar(value="Medium"); self._last = None; self._style(); T.on_change(self._style)
        for ev, v in (("<Button-1>", 255), ("<B1-Motion>", 255), ("<Button-3>", 0), ("<B3-Motion>", 0)): self.bind(ev, lambda e, v=v: self._dab(e, v))
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "_last", None)); self.bind("<ButtonRelease-3>", lambda e: setattr(self, "_last", None))
        self.bind("<Configure>", lambda e: self.pic is not None and self._fit())
        self.after_idle(self._empty)
    def _style(self): self.configure(bg=T.PALETTE["field"], highlightbackground=T.PALETTE["border"])
    def _empty(self):
        self.delete("all"); self.create_text(self.winfo_width() / 2, self.winfo_height() / 2, fill=T.PALETTE["muted"], font=T.f(10),
                                             text="CHOOSE A PICTURE, THEN BRUSH OVER WHAT TO CHANGE")
    def set_picture(self, im):
        from PIL import Image
        self.pic = im.convert("RGB"); self.mask = Image.new("L", im.size, 0); self._fit()
    def _fit(self):
        from PIL import Image
        W, H = max(50, self.winfo_width() - 4), max(50, self.winfo_height() - 4)
        self.k = min(W / self.pic.width, H / self.pic.height); dw, dh = max(1, int(self.pic.width * self.k)), max(1, int(self.pic.height * self.k))
        self.ox, self.oy = (self.winfo_width() - dw) // 2, (self.winfo_height() - dh) // 2
        self.view = self.pic.resize((dw, dh), Image.LANCZOS); self.dmask = self.mask.resize((dw, dh)); self._redraw()
    def _redraw(self):
        from PIL import Image, ImageTk
        red = Image.blend(self.view, Image.new("RGB", self.view.size, (255, 40, 80)), 0.55)
        self._ph = ImageTk.PhotoImage(Image.composite(red, self.view, self.dmask))
        self.delete("all"); self.create_image(self.ox, self.oy, image=self._ph, anchor="nw")
    def _dab(self, e, v):
        if self.pic is None: return
        from PIL import ImageDraw
        r = BRUSH[self.brush.get()] * T.Z; x, y = e.x - self.ox, e.y - self.oy; last = self._last or (x, y); self._last = (x, y)
        for img, k in ((self.dmask, 1.0), (self.mask, 1 / self.k)):
            d = ImageDraw.Draw(img); a, b, c, dd = last[0] * k, last[1] * k, x * k, y * k; rr = r * k
            d.line((a, b, c, dd), fill=v, width=max(1, int(2 * rr))); d.ellipse((c - rr, dd - rr, c + rr, dd + rr), fill=v)
        self._redraw()
    def clear(self):
        if self.pic is None: return
        self.mask.paste(0, (0, 0, *self.mask.size)); self.dmask.paste(0, (0, 0, *self.dmask.size)); self._redraw()
    def has_mask(self): return self.mask is not None and self.mask.getbbox() is not None

class PaintPage(tk.Frame):
    TITLE = "Text to Image"; SOURCE = None; MASK = False
    INTRO = "Type what you want. The core text model turns it into a clear picture description, then the image engine paints it."
    WORDS = "WHAT YOU WANT"
    def __init__(self, master, app):
        super().__init__(master, bg=master["bg"]); self.app = app; T.on_change(lambda: self.configure(bg=self.master["bg"]))
        import imaging, image_models as IM; self.imaging = imaging; self.IM = IM
        self.job = None; self.stop_event = threading.Event(); self.start_image = None; self._ph = []; self.page_key = "AI Images/" + self.TITLE
        mem = prefs.get(f"image_page:{self.TITLE}") or {}; self._mem = mem
        def var(key, default):
            v = tk.StringVar(value=mem.get(key, default)); return v
        T.Title(self, self.TITLE).pack(pady=(0, 4)); T.Text(self, self.INTRO, muted=True).pack()
        st = _frame(self); st.pack(pady=(6, 2))
        self.status = T.Text(st, "", font=T.f(10)); self.status.pack(side="left", padx=(0, 10))
        self.get_btn = T.Button(st, "Download the image engine", self.download); self.get_btn.pack(side="left")
        if self.SOURCE:
            r = _frame(self); r.pack(pady=(4, 0))
            T.Button(r, "Choose a picture", self.choose, width=18).pack(side="left", padx=6)
            if self.SOURCE == "sketch": T.Button(r, "Use my latest drawing", self.use_latest, width=22).pack(side="left", padx=6)
            if self.MASK:                                                       # the brush pad on the left, the controls in a column on the right
                split = _frame(self); split.pack(fill="both", expand=True, pady=(6, 0)); left = _frame(split); left.pack(side="left", anchor="n", padx=(0, 14))
                host = _frame(split); host.pack(side="left", fill="both", expand=True, anchor="n")
                self.pad = MaskPad(left); self.pad.pack()
                T.Choice(r, "brush", list(BRUSH), self.pad.brush).pack(side="left", padx=6)
                T.Button(r, "Clear the brushing", lambda: self.pad.clear(), width=18).pack(side="left", padx=6)
                T.Text(left, "Left-drag: brush over what to change.   Right-drag: rub out.", muted=True, font=T.f(8)).pack()
            else:
                self.pick_lbl = tk.Label(r, text="no picture yet", bg=T.PALETTE["field"], fg=T.PALETTE["muted"], width=22, height=5); self.pick_lbl.pack(side="left", padx=6)
        if not self.MASK: host = self
        side = "top" if self.MASK else "left"; pad_c = dict(pady=3) if self.MASK else dict(padx=4)    # settings stacked in the column, or in a row
        T.Text(host, self.WORDS, font=T.f(10)).pack(anchor="w", pady=(6, 2))
        self.prompt = T.Field(host, height=3); self.prompt.pack(fill="x")
        if mem.get("words"): self.prompt.insert("1.0", mem["words"])
        lo = _frame(host); lo.pack(fill="x", pady=(6, 0))
        T.Text(lo, "LEAVE OUT", font=T.f(10)).pack(side="left", padx=(0, 8))
        self.leave_out = var("leave_out", self.imaging.NEGATIVE); T.Entry(lo, self.leave_out, width=70).pack(side="left", fill="x", expand=True)
        opts = _frame(host); opts.pack(pady=(8, 0))
        if not self.SOURCE:
            self.size = var("size", list(self.imaging.SIZES)[0])
            if self.size.get() not in self.imaging.SIZES: self.size.set(self.size.get().split()[0] if self.size.get().split()[0] in self.imaging.SIZES else "Square")
            T.Choice(opts, "size", list(self.imaging.SIZES), self.size).pack(side="left", padx=4)
        self.count = var("count", "1")
        if not self.MASK: T.Choice(opts, "how many", ["1", "2", "4"], self.count).pack(side="left", padx=4)     # Inpainting: one at a time, into the pad
        else: self.count.set("1")
        self.quality = var("quality", "Normal (20 steps)"); T.Choice(opts, "quality", list(QUALITY), self.quality).pack(side=side, **pad_c)
        self.follow = var("follow", "Normal"); T.Choice(opts, "follow my words", list(self.imaging.GUIDANCE), self.follow).pack(side=side, **pad_c)
        self.amount_map = REPLACE if self.MASK else KEEP if self.SOURCE == "sketch" else CHANGE if self.SOURCE else None
        if self.amount_map:
            label = "new part" if self.MASK else "drawing" if self.SOURCE == "sketch" else "change"
            self.amount = var("amount", list(self.amount_map)[1]); T.Choice(opts, label, list(self.amount_map), self.amount).pack(side=side, **pad_c)
        opts2 = _frame(host); opts2.pack(pady=(6, 0))
        if self.SOURCE == "sketch":
            self.style = var("style", "Painting"); T.Choice(opts2, "style", list(STYLES), self.style).pack(side="left", padx=4)
        self.model = tk.StringVar(value=self.IM.active() or "None"); self.model_choice = T.Choice(opts2, "image model", ["None"] + self.IM.names(), self.model)
        self.model_choice.pack(side=side, **pad_c)
        sr = _frame(opts2); sr.pack(side=side, **pad_c)
        T.Text(sr, "SEED", font=T.f(10)).pack(side="left", padx=(14 if not self.MASK else 0, 6))
        self.seed = var("seed", "random"); T.Entry(sr, self.seed, width=12).pack(side="left")
        T.Button(sr, "Random", lambda: self.seed.set("random"), width=8).pack(side="left", padx=4)
        self.improve = tk.BooleanVar(value=mem.get("improve", True))
        if not self.SOURCE:
            r2 = _frame(self); r2.pack(pady=(6, 0))
            T.Text(r2, "Let the core text model improve my words", font=T.f(9)).pack(side="left", padx=(0, 6)); T.Toggle(r2, self.improve).pack(side="left")
        b = _frame(host); b.pack(pady=8)
        self.go_btn = skin.button(T.Button(b, "Paint it", self.go, width=14)); self.go_btn.pack(side="left", padx=6)
        jobs.guard(self.go_btn, self.page_key, app, "your picture")
        T.Button(b, "Stop", self.stop, kind="danger", width=8).pack(side="left", padx=6)
        if not self.MASK: T.Button(b, "Open my Images folder", lambda: prefs.open_folder(prefs.save_folder()), width=22).pack(side="left", padx=6)
        self.msg = T.Text(host, "", muted=True); self.msg.pack()
        self.used = T.Text(host, "", muted=True, font=T.f(8)); self.used.configure(wraplength=380 if self.MASK else 900); self.used.pack()
        self.results = _frame(self); self.results.pack(fill="both", expand=True, pady=(6, 0))
        if not self.MASK: T.Text(self, "Every picture is saved into your Images folder straight away, so every tab can pick it up from there.", muted=True, font=T.f(8)).pack(side="bottom")
        self.bind("<Map>", lambda e: self.refresh(), add="+"); self.refresh(); self._tick()

    def refresh(self):
        self.model_choice.choices = ["None"] + self.IM.names()
        if self.model.get() not in self.model_choice.choices: self.model.set("None")

    def _tick(self):
        if not self.winfo_exists(): return
        st = self.imaging.status(); pct = f" {st['progress'] * 100:.0f}%" if st["state"] in ("downloading", "painting") and st.get("progress") else ""
        text = f"{(st['detail'] or st['state'] or '').upper()}{pct}"
        if st["state"] == "ready" and not self.SOURCE:
            w, h = self.imaging.pixels(self.size.get()); text += f"   {w} x {h}"
        self.status.configure(text=text)
        if self.job is not None and self.job.state == "waiting": self.msg.configure(text=jobs.where(self.job).upper())
        show = st["state"] in ("not-installed", "error")
        if show and not self.get_btn.winfo_manager(): self.get_btn.pack(side="left")
        elif not show and self.get_btn.winfo_manager(): self.get_btn.pack_forget()
        self.after(700, self._tick)

    def download(self):
        q = self.app.q
        self.imaging.download(on_done=lambda ok, m: q.put(lambda: T.banner(self.app, ("DOWNLOADED — " if ok else "DOWNLOAD FAILED — ") + m, "success" if ok else "error")))

    # ---- the starting picture
    def choose(self):
        p = filedialog.askopenfilename(parent=self.app, initialdir=prefs.save_folder(), title="Choose a picture",
                                       filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")])
        if p: self.load_picture(p)

    def use_latest(self):
        p = prefs.latest_picture()
        if not p: return T.banner(self.app, "NO PICTURES IN YOUR IMAGES FOLDER YET — draw one in the Drawing tab and save it")
        self.load_picture(p)

    def load_picture(self, p):
        from PIL import Image, ImageTk
        try: self.start_image = Image.open(p).convert("RGB")
        except Exception as e: return T.banner(self.app, f"CAN'T OPEN THAT PICTURE — {e}")
        if self.MASK: return self.pad.set_picture(self.start_image)
        th = self.start_image.copy(); th.thumbnail((180, 120)); self._pick_ph = ImageTk.PhotoImage(th)
        self.pick_lbl.configure(image=self._pick_ph, width=th.width, height=th.height, text="")

    def _wording(self, text):
        """the core text model's clearer version of the request (the request itself if the text model isn't set up)"""
        if not self.improve.get() or self.SOURCE: return text
        try:
            import brain
            if not brain.installed(): return text
            ans = brain.ask("AI Images", "Rewrite this request as one short, vivid picture description for an image model: the subject first, "
                            "then style, lighting and details, comma-separated, under 50 words. Reply with the description only.\n\n" + text,
                            max_tokens=120, use_library=False)
            return ans.strip().strip('"') or text
        except Exception: return text

    def _remember(self, text):
        keep = dict(words=text, leave_out=self.leave_out.get(), count=self.count.get(), quality=self.quality.get(), follow=self.follow.get(),
                    seed=self.seed.get(), improve=bool(self.improve.get()))
        if not self.SOURCE: keep["size"] = self.size.get()
        if self.amount_map: keep["amount"] = self.amount.get()
        if self.SOURCE == "sketch": keep["style"] = self.style.get()
        prefs.set(f"image_page:{self.TITLE}", keep)

    def go(self):
        if jobs.busy(self.page_key): return
        text = self.prompt.get("1.0", "end").strip()
        if not text and not self.SOURCE: return T.banner(self.app, "TYPE WHAT YOU WANT FIRST")
        if not text and self.SOURCE == "picture" and not self.MASK: return T.banner(self.app, "SAY WHAT TO CHANGE FIRST")
        if self.SOURCE and self.start_image is None:
            return T.banner(self.app, "CHOOSE A PICTURE FIRST — the box opens in your Images folder" if self.SOURCE != "sketch" else "CHOOSE A DRAWING FIRST (or use your latest one)")
        if self.MASK and not self.pad.has_mask(): return T.banner(self.app, "BRUSH OVER THE PART TO CHANGE FIRST")
        if not self.imaging.ready(): return T.banner(self.app, "THE IMAGE ENGINE ISN'T DOWNLOADED YET — press Download the image engine")
        sd = self.seed.get().strip().lower()
        if sd not in ("", "random") and not sd.isdigit(): return T.banner(self.app, "THE SEED IS A WHOLE NUMBER (or 'random')")
        self._remember(text)
        self.stop_event.clear(); q = self.app.q; n = int(self.count.get()); model = "" if self.model.get() == "None" else self.model.get()
        negative = self.leave_out.get().strip()
        kw = dict(n=n, steps=QUALITY[self.quality.get()], cfg=self.imaging.GUIDANCE[self.follow.get()], seed=int(sd) if sd.isdigit() else None,
                  negative=negative, image_model=model, stop=self.stop_event, hint=text or self.TITLE)
        words = text
        if not self.SOURCE: kw["size"] = self.size.get()
        else: kw.update(init_image=self.start_image, size=self.imaging.fit_size(self.start_image), strength=self.amount_map[self.amount.get()])
        if self.SOURCE == "sketch": words = f"{text}, {STYLES[self.style.get()]}" if text else STYLES[self.style.get()]
        if self.MASK:
            from PIL import Image, ImageFilter
            orig = self.start_image; edge = max(3, int(max(orig.size) * 0.012))
            grown = self.pad.mask.filter(ImageFilter.MaxFilter(edge * 2 + 1))                       # a little past the brushing, so it blends in
            soft = grown.filter(ImageFilter.GaussianBlur(edge))                                     # feathered edge for putting it back
            kw.update(mask=grown, finish=lambda pic: Image.composite(pic.convert("RGB").resize(orig.size, Image.LANCZOS), orig, soft))
            if not text: words = REMOVE_WORDS; kw["negative"] = (negative + ", " if negative else "") + "person, object, text, logo"
        if model and self.imaging.kind() == "zimage":
            T.banner(self.app, f"{model.upper()} IS MADE FOR STABLE DIFFUSION 1.5 — Z-Image Turbo paints without it (choose Stable Diffusion 1.5 in Settings > AI Models to use it)", "busy")
        def work(job):
            def progress(f, t): job.say(t); q.put(lambda t=t: self.msg.configure(text=t.upper()))
            if not self.SOURCE and self.improve.get(): progress(0, "Improving your words with the text model…")
            wording = self._wording(words)
            q.put(lambda: self.used.configure(text=f"PAINTING FROM: {wording}"))
            progress(0, "Painting…"); return self.imaging.paint(wording, on_progress=progress, **kw)
        def failed(e): q.put(lambda e=e: (self.msg.configure(text=""), T.banner(self.app, f"COULDN'T PAINT — {e}")))
        self.job = jobs.submit("AI Images", f"{self.TITLE}: {(text or words)[:40]}", work, kind="image", page=self.page_key, engine="image",
                               on_done=lambda saved: q.put(lambda: self._show(saved)), on_error=failed, on_cancel=self._stop_now)
        self.msg.configure(text="GETTING READY…" if self.job.place() <= 1 and not jobs.running() else jobs.where(self.job).upper())

    def _stop_now(self): self.stop_event.set(); self.imaging.stop_now()
    def stop(self):
        if self.job is not None and self.job.state in ("waiting", "running"):
            jobs.cancel(self.job); self.msg.configure(text="STOPPED")

    def _show(self, saved):
        from PIL import Image, ImageTk
        if self.MASK and saved:                                                  # the result goes into the pad: keep brushing and fixing it
            self.load_picture(saved[-1]); self.msg.configure(text="DONE — BRUSH AGAIN TO KEEP FIXING IT")
            return T.banner(self.app, "PAINTED — saved to your Images folder; it's in the brush pad to keep fixing", "success")
        for w in self.results.winfo_children(): w.destroy()
        self._ph = []; self.update_idletasks()
        th = min(210, max(110, self.results.winfo_height() - 34))                  # as big as the space left under the buttons allows
        for p in saved:
            try: im = Image.open(p); im.thumbnail((th, th)); ph = ImageTk.PhotoImage(im)
            except Exception: continue
            seed = prefs.picture_info(p).get("seed", "")
            cell = _frame(self.results); cell.pack(side="left", padx=6, anchor="n")
            self._ph.append(ph); lb = tk.Label(cell, image=ph, bg=self["bg"], cursor="hand2"); lb.pack()
            lb.bind("<Button-1>", lambda e, p=p: prefs.open_folder(os.path.dirname(p)))
            if seed:
                row = _frame(cell); row.pack(pady=(3, 0))
                T.Text(row, f"SEED {seed}", font=T.f(8), muted=True).pack(side="left", padx=(0, 6))
                T.Button(row, "Use this seed", lambda s=seed: (self.seed.set(s), T.banner(self.app, f"SEED {s} SET — change the words a little and paint again", "success")),
                         width=12).pack(side="left")
        note = self.imaging.last.get("note") or ""
        self.msg.configure(text=(f"DONE — {len(saved)} SAVED TO YOUR IMAGES FOLDER" + (f" ({note.upper()})" if note else "")) if saved else "STOPPED")
        if saved: T.banner(self.app, f"PAINTED — {len(saved)} saved to your Images folder" + (f" ({note})" if note else ""), "success")

class FromPicturePage(PaintPage):
    TITLE = "Image to Image"; SOURCE = "picture"; WORDS = "WHAT TO CHANGE"
    INTRO = "Choose a picture (the box opens in your Images folder), say what to change, and it repaints it."

class SketchPage(PaintPage):
    TITLE = "Sketch to Image"; SOURCE = "sketch"; WORDS = "WHAT IT IS (optional): 'a red dragon on a hill'"
    INTRO = "Turn a drawing into a finished picture: your latest drawing from the Drawing tab, or any sketch. Keep your lines or let it go free."

class InpaintPage(PaintPage):
    TITLE = "Inpainting"; SOURCE = "picture"; MASK = True; WORDS = "WHAT GOES THERE (leave empty to remove it)"
    INTRO = "Brush over part of a picture and say what goes there. Leave the words empty to remove it. The rest of the picture stays exactly as it was."

def page_classes(): return {"Text to Image": PaintPage, "Image to Image": FromPicturePage, "Sketch to Image": SketchPage, "Inpainting": InpaintPage}
