"""
video_pages.py: the AI Videos tab. Text to Video (type a scene) and Image to Video (bring a picture to life), with Wan 2.2 5B.

Speed: Auto picks from what's free on the graphics card; Fast keeps the model on the card; Slow keeps it in PC memory so smaller
cards (and PCs with no AI card at all) still make videos, just more slowly. The finished video plays here on a loop and is saved in
your Videos folder; Save as GIF / WebP makes a copy that plays anywhere; Carry on from the last frame starts the next clip there.
"""
import os, threading, tkinter as tk
import theme as T, prefs, jobs, skin


def _frame(parent):
    f = tk.Frame(parent, bg=parent["bg"]); T.on_change(lambda: f.configure(bg=f.master["bg"])); return f


class Problem(Exception): pass


class Player(tk.Frame):
    """plays the frames on a loop; click to pause"""
    def __init__(self, master, w=560, h=330):
        super().__init__(master, bg=master["bg"]); T.on_change(lambda: self.configure(bg=self.master["bg"]))
        self.W, self.H = w, h
        self.canvas = tk.Canvas(self, width=w, height=h, bg="#0b0f17", highlightthickness=1, highlightbackground=T.PALETTE["muted"])
        self.canvas.pack(); self.canvas.bind("<Button-1>", lambda e: self.toggle())
        self.frames = []; self.photos = []; self.i = 0; self.playing = False; self.fps = 24; self._job = None
        self.label = self.canvas.create_text(w // 2, h // 2, text="YOUR VIDEO PLAYS HERE", fill=T.PALETTE["muted"], font=T.f(11))
        self.bar = T.ProgressBar(self, width=w, height=20)

    def progress(self, frac, text):
        self.bar.set(frac if frac else None, text)
        if not self.bar.winfo_manager(): self.bar.pack(pady=(4, 0))

    def progress_done(self):
        if self.bar.winfo_manager(): self.bar.pack_forget()

    def show_still(self, path):
        from PIL import Image, ImageTk
        try:
            with Image.open(path) as im: im = im.convert("RGB"); im.load()
            self.load([im], 1)
        except Exception: pass

    def load(self, frames, fps):
        from PIL import ImageTk
        self.stop(); self.frames = frames; self.fps = fps; self.photos = []
        for f in frames:
            k = min(self.W / f.width, self.H / f.height); self.photos.append(ImageTk.PhotoImage(f.resize((max(1, int(f.width * k)), max(1, int(f.height * k))))))
        self.canvas.delete("all"); self.img = self.canvas.create_image(self.W // 2, self.H // 2, image=self.photos[0] if self.photos else None)
        self.i = 0
        if len(self.photos) > 1: self.play()

    def play(self):
        self.playing = True; self._tick()

    def stop(self):
        self.playing = False
        if self._job: self.after_cancel(self._job); self._job = None

    def toggle(self):
        if not self.photos or len(self.photos) < 2: return
        self.stop() if self.playing else self.play()

    def _tick(self):
        if not self.playing or not self.photos or not self.winfo_exists(): return
        self.canvas.itemconfigure(self.img, image=self.photos[self.i]); self.i = (self.i + 1) % len(self.photos)
        self._job = self.after(max(15, int(1000 / self.fps)), self._tick)


class VideoPage(tk.Frame):
    TITLE = "Text to Video"; START_PICTURE = False
    INTRO = "Describe a short scene and what moves in it. Wan 2.2 makes it, 24 frames a second."
    WORDS = "WHAT HAPPENS: the subject, what it does, how the camera moves"

    def __init__(self, master, app):
        super().__init__(master, bg=master["bg"]); self.app = app; T.on_change(lambda: self.configure(bg=self.master["bg"]))
        import video_engine as V; self.V = V
        self.page_key = "AI Videos/" + self.TITLE; self.job = None; self.stop_event = threading.Event(); self.video = None
        self._mem = prefs.get(f"video_page:{self.TITLE}") or {}
        T.Title(self, self.TITLE).pack(pady=(0, 2)); T.Text(self, self.INTRO, muted=True, font=T.f(9)).pack()
        st = _frame(self); st.pack(pady=(4, 2))
        self.status = T.Text(st, "", font=T.f(9)); self.status.pack(side="left", padx=(0, 10))
        self.get_btn = T.Button(st, "Download", self.download, width=12)
        split = _frame(self); split.pack(fill="both", expand=True, pady=(6, 0))
        split.columnconfigure(0, weight=1, uniform="half"); split.columnconfigure(1, weight=1, uniform="half")
        left = _frame(split); left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = _frame(split); right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        # left: the start picture, the words, the settings
        if self.START_PICTURE:
            from image_pages import PicSlot
            self.slot = PicSlot(left, "START PICTURE", w=260, h=180); self.slot.pack(anchor="w")
            if self._mem.get("picture") and os.path.exists(self._mem["picture"]): self.after_idle(lambda: self.slot.set(self._mem["picture"]))
        T.Text(left, self.WORDS, font=T.f(10)).pack(anchor="w", pady=(6, 2))
        self.prompt = T.Field(left, height=4); self.prompt.pack(fill="x")
        if self._mem.get("words"): self.prompt.insert("1.0", self._mem["words"])
        opts = _frame(left); opts.pack(anchor="w", pady=(8, 0))
        def var(name, default):
            v = tk.StringVar(value=self._mem.get(name, default)); return v
        self.style = var("style", "None"); self.length = var("length", "2 seconds"); self.size = var("size", "Wide 832×480")
        self.quality = var("quality", "Normal"); self.speed = var("speed", prefs.get("speed_video") or "Auto"); self.seed = var("seed", "random")
        cells = [T.Choice(opts, "style", self._styles(), self.style), T.Choice(opts, "length", list(V.LENGTHS), self.length),
                 T.Choice(opts, "size", list(V.SIZES), self.size), T.Choice(opts, "quality", list(V.QUALITY), self.quality),
                 T.Choice(opts, "speed", V.SPEEDS, self.speed)]
        sd = _frame(opts); T.Text(sd, "SEED", font=T.f(9)).pack(side="left", padx=(0, 4))
        T.Button(sd, "Random", lambda: self.seed.set("random"), width=7).pack(side="left", padx=(0, 4)); T.Entry(sd, self.seed, width=9).pack(side="left")
        cells.append(sd)
        self.improve = tk.BooleanVar(value=self._mem.get("improve", True))
        imp = _frame(opts); T.Text(imp, "FULLER DESCRIPTION", font=T.f(9)).pack(side="left", padx=(0, 6)); T.Toggle(imp, self.improve).pack(side="left")
        cells.append(imp)
        for i, c in enumerate(cells): c.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 18), pady=3)
        self.speed_note = T.Text(left, "", muted=True, font=T.f(8)); self.speed_note.configure(wraplength=520, justify="left"); self.speed_note.pack(anchor="w", pady=(4, 0))
        self.speed.trace_add("write", lambda *a: (prefs.set("speed_video", self.speed.get()), self._speed_words()))
        for v in (self.length, self.size, self.quality): v.trace_add("write", lambda *a: self._speed_words())
        b = _frame(left); b.pack(anchor="w", pady=(10, 0))
        self.go_btn = skin.button(T.Button(b, "Make it", self.go, width=14)); self.go_btn.pack(side="left")
        jobs.guard(self.go_btn, self.page_key, app, "your video")
        T.Button(b, "Stop", self.stop, kind="danger", width=8).pack(side="left", padx=8)
        T.Button(b, "Open my Videos folder", lambda: prefs.open_folder(V.videos_folder())).pack(side="left")
        self.msg = T.Text(left, "", muted=True, font=T.f(9)); self.msg.configure(wraplength=520, justify="left"); self.msg.pack(anchor="w", pady=(6, 0))
        self.used = T.Text(left, "", muted=True, font=T.f(8)); self.used.configure(wraplength=520, justify="left"); self.used.pack(anchor="w")
        # right: the player and what to do with the video
        self.player = Player(right); self.player.pack(anchor="n")
        acts = _frame(right); acts.pack(pady=(8, 0))
        self.acts = [T.Button(acts, "Save as GIF", lambda: self._save_as("gif"), width=12), T.Button(acts, "Save as WebP", lambda: self._save_as("webp"), width=13),
                     T.Button(acts, "Carry on from here", self._carry_on, width=18)]
        for w in self.acts: w.pack(side="left", padx=4)
        self.info = T.Text(right, "", muted=True, font=T.f(8)); self.info.pack(pady=(4, 0))
        self.refresh(); self._speed_words()

    # ---- what's offered
    def _styles(self):
        out = ["None"]
        try:
            import styles, style_addons as SA
            out += [s for s in styles.BUILT_IN if s != "None"]
            out += [s for s, e in SA.entries().items() if SA.base_of(e) == "wan22" and s not in out]
        except Exception: pass
        return out

    def _speed_words(self):
        V = self.V; w, h = V.SIZES.get(self.size.get(), (832, 480)); frames = V.LENGTHS.get(self.length.get(), 49)
        mode, why = V.plan_speed(self.speed.get(), w, h, frames)
        words = {"Fast": "FAST: the video model stays on the graphics card.",
                 "Slow": "SLOW: the model waits in PC memory and only the part working right now goes to the card, so smaller cards can make "
                         "videos too — just more slowly (several minutes a second of video on a 6 GB card)."}
        lead = f"AUTO → {mode.upper()}. " if self.speed.get() == "Auto" else ""
        self.speed_note.configure(text=lead + words.get(mode, "") + (f" ({why})" if why and self.speed.get() == "Auto" else "")
                                  + " Shorter, smaller and Draft are quicker; if it runs out of memory it's tried again the slower, safer way.")

    def refresh(self):
        miss = self.V.missing()
        if miss:
            self.status.configure(text=("NEEDS THE VIDEO MODEL" if len(miss) > 1 else "NEEDS " + miss[0].upper()) + " — about 9 GB")
            if not self.get_btn.winfo_manager(): self.get_btn.pack(side="left")
        else:
            self.status.configure(text="READY — WAN 2.2 5B")
            if self.get_btn.winfo_manager(): self.get_btn.pack_forget()

    def download(self):
        q = self.app.q
        def work():
            try:
                self.V.download(report=lambda t, f: q.put(lambda t=t, f=f: self.player.progress(f, t)))
                q.put(lambda: (self.player.progress_done(), self.refresh(), T.banner(self.app, "VIDEO MODEL READY", "success")))
            except Exception as e:
                q.put(lambda e=e: (self.player.progress_done(), self.refresh(), T.banner(self.app, f"DOWNLOAD DIDN'T FINISH — {e}", "error")))
        threading.Thread(target=work, daemon=True, name="video download").start()
        T.banner(self.app, "DOWNLOADING THE VIDEO MODEL — it carries on from where it stops", "success")

    # ---- making it
    def start_picture(self):
        if not self.START_PICTURE: return None
        if not getattr(self.slot, "path", None): raise Problem("CHOOSE A START PICTURE FIRST")
        return self.slot.path

    def receive(self, path):
        if self.START_PICTURE: self.slot.set(path)

    def _remember(self, text):
        m = dict(words=text, style=self.style.get(), length=self.length.get(), size=self.size.get(), quality=self.quality.get(),
                 speed=self.speed.get(), seed=self.seed.get(), improve=self.improve.get())
        if self.START_PICTURE: m["picture"] = getattr(self.slot, "path", "") or ""
        prefs.set(f"video_page:{self.TITLE}", m)

    def go(self):
        if jobs.busy(self.page_key): return
        text = self.prompt.get("1.0", "end").strip()
        try:
            if self.V.missing(): raise Problem("THE VIDEO MODEL ISN'T HERE YET — press Download (at the top) first")
            image = self.start_picture()
            if not text and not image: raise Problem("SAY WHAT HAPPENS FIRST")
            seed = self.seed.get().strip()
            if seed != "random" and not seed.isdigit(): raise Problem("THE SEED IS A WHOLE NUMBER, OR RANDOM")
        except Problem as e: return T.banner(self.app, str(e))
        self._remember(text); self.stop_event.clear(); q = self.app.q
        style = self.style.get(); improve = self.improve.get() and bool(text)
        args = dict(seconds=self.length.get(), size=self.size.get(), quality=self.quality.get(), speed=self.speed.get(), image=image,
                    seed=None if seed == "random" else int(seed), stop=self.stop_event, meta=dict(section=self.TITLE, style=style))
        def work(job):
            def progress(f, t): job.say(t); q.put(lambda f=f, t=t: (self.msg.configure(text=t.upper()), self.player.progress(f, t)))
            p = text or "the picture comes to life with gentle natural motion"
            if improve: progress(None, "Writing a fuller description…"); p = self._wording(text)
            words, lora = self._style_bits(style, p)
            q.put(lambda: self.used.configure(text=f"MAKING FROM: {words}"))
            progress(0, "Getting ready…")
            return self.V.make(words, lora=lora, on_progress=progress, **args)
        def failed(e): q.put(lambda e=e: (self.msg.configure(text=""), self.player.progress_done(), T.banner(self.app, f"COULDN'T MAKE THE VIDEO — {e}")))
        self.job = jobs.submit("AI Videos", f"{self.TITLE}: {(text or 'from a picture')[:40]}", work, kind="video", page=self.page_key, engine="image",
                               on_done=lambda r: q.put(lambda: self._show(r)), on_error=failed, on_cancel=self._stop_now)
        self.msg.configure(text="GETTING READY…" if self.job.place() <= 1 and not jobs.running() else jobs.where(self.job).upper())
        self.player.progress(None, "Waiting its turn…" if jobs.running() else "Getting ready…")

    def _style_bits(self, style, p):
        """the style's words added to the description, and its video add-on (made for Wan 2.2) when it has one switched on"""
        lora = None
        if style and style != "None":
            try:
                import styles, style_addons as SA
                sentence = styles.BUILT_IN.get(style, ("",))[0]
                if sentence: p = f"{p}. {sentence}"
                bits = SA.lora_for(style, "wan22")
                if bits: lora = bits
            except Exception: pass
        return p, lora

    def _wording(self, text):
        """the core text model's fuller description of the scene, with the motion and the camera (the request itself if it can't)"""
        try:
            import brain
            if not brain.installed(): return text
            ask = ("Rewrite this video request as a description for a video model in 2 to 4 plain sentences (50 to 100 words): the subject and "
                   "setting, then exactly what moves and how (speed, direction), then the camera (still, slow push in, pan...) and the light. "
                   "One continuous shot, a few seconds long. Keep every detail the person asked for. Reply with the description only.\n\n" + text)
            out = brain.ask("AI Videos", ask, max_tokens=220).strip().strip('"')
            try: brain.stop()
            except Exception: pass
            return out if 20 < len(out) < 1200 else text
        except Exception: return text

    def _stop_now(self): self.stop_event.set(); self.V.stop_now()

    def stop(self):
        if self.job is not None and self.job.state in ("waiting", "running"):
            jobs.cancel(self.job); self.msg.configure(text="STOPPED"); self.player.progress_done()

    def _show(self, r):
        self.player.progress_done(); self.msg.configure(text="")
        if not r or self.stop_event.is_set(): return
        self.video = r["video"]
        try: frames = self.V.frames_of(r["video"])
        except Exception: frames = []
        if frames: self.player.load(frames, r["fps"])
        self.info.configure(text=f"{r['seconds']} s · {r['frames']} frames · made the {r['speed'].lower()} way · seed {r['seed']} · saved as {os.path.basename(r['video'])}")
        T.banner(self.app, f"VIDEO SAVED — {os.path.basename(r['video'])} in your Videos folder", "success")

    def _need_video(self):
        if not self.video or not os.path.exists(self.video): T.banner(self.app, "MAKE A VIDEO FIRST"); return False
        return True

    def _save_as(self, kind):
        if not self._need_video(): return
        try: p = self.V.save_as(self.video, kind); T.banner(self.app, f"SAVED — {os.path.basename(p)}", "success")
        except Exception as e: T.banner(self.app, f"COULDN'T SAVE IT — {e}", "error")

    def _carry_on(self):
        """the last frame becomes Image to Video's start picture, so the next clip carries on from here"""
        if not self._need_video(): return
        try: p = self.V.last_frame(self.video)
        except Exception as e: return T.banner(self.app, f"COULDN'T READ THE LAST FRAME — {e}", "error")
        try:
            sec = self.app.pages["AI Videos"]; self.app.show("AI Videos"); sec.select("Image to Video"); page = sec.pages.get("Image to Video")
        except Exception: page = None
        if page is not None and hasattr(page, "receive"): page.receive(p)
        T.banner(self.app, "THE LAST FRAME IS THE START PICTURE — say what happens next", "success")


class TextVideoPage(VideoPage): pass


class ImageVideoPage(VideoPage):
    TITLE = "Image to Video"; START_PICTURE = True
    INTRO = "Bring a picture to life: it's the first frame, and your words say what moves."
    WORDS = "WHAT MOVES: 'her hair blows in the wind, she smiles', 'the waves roll in, slow push in'"


def page_classes(): return {"Text to Video": TextVideoPage, "Image to Video": ImageVideoPage}
