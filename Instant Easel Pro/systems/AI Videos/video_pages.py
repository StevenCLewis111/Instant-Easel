"""
video_pages.py: the AI Videos tab. Text to Video (type a scene) and Image to Video (bring a picture to life), with Wan 2.2 5B.

Speed: Auto picks from what's free on the graphics card; Fast keeps the model on the card; Slow keeps it in PC memory so smaller
cards (and PCs with no AI card at all) still make videos, just more slowly. The finished video plays here on a loop and is saved in
your Videos folder; Save as GIF / WebP makes a copy that plays anywhere; Carry on from the last frame starts the next clip there.
"""
import os, sys, glob, threading, tkinter as tk
import theme as T, prefs, jobs, skin


def _frame(parent):
    f = tk.Frame(parent, bg=parent["bg"]); T.on_change(lambda: f.configure(bg=f.master["bg"])); return f


class Problem(Exception): pass


RESOLUTION = {"Low": 0.75, "Medium": 1.0, "High": 1.25}


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
    TITLE = "Text to Video"; START_PICTURE = False; PIC_LABEL = "START PICTURE"
    INTRO = "Describe a short scene and what moves in it. Wan 2.2 makes it, 24 frames a second."
    WORDS = "WHAT HAPPENS: the subject, what it does, how the camera moves"

    LENGTH_DEFAULT = "2 seconds"
    @property
    def LENGTHS(self): return self.V.LENGTHS

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
            self.slot = PicSlot(left, self.PIC_LABEL, w=200, h=120); self.slot.pack(anchor="w")
            if self._mem.get("picture") and os.path.exists(self._mem["picture"]): self.after_idle(lambda: self.slot.set(self._mem["picture"]))
        self.build_inputs(left)
        from image_pages import ListChoice
        pick = _frame(left); pick.pack(fill="x", pady=(6, 2))
        self.model = tk.StringVar(value=self._mem.get("model", ""))
        self.model_choice = ListChoice(pick, "video model", self._model_names(), self.model); self.model_choice.pack(side="left", padx=(0, 10))
        self.style = tk.StringVar(value=self._mem.get("style", "None"))
        self.style_choice = ListChoice(pick, "template", self._styles(), self.style); self.style_choice.pack(side="left")
        self.model.trace_add("write", lambda *a: (self._fit_pick(), self.refresh(), self._speed_words()))
        T.Text(left, self.WORDS, font=T.f(10)).pack(anchor="w", pady=(6, 2))
        self.prompt = T.Field(left, height=3); self.prompt.pack(fill="x")
        if self._mem.get("words"): self.prompt.insert("1.0", self._mem["words"])
        opts = _frame(left); opts.pack(anchor="w", pady=(8, 0))
        def var(name, default):
            v = tk.StringVar(value=self._mem.get(name, default)); return v
        self.length = var("length", self.LENGTH_DEFAULT); self.size = var("size", "Wide 832×480"); self.resolution = var("resolution", "Medium")
        self.quality = var("quality", "Normal"); self.speed = var("speed", prefs.get("speed_video") or "Auto"); self.seed = var("seed", "random")
        if self.length.get() not in self.LENGTHS: self.length.set(self.LENGTH_DEFAULT)
        cells = [T.Choice(opts, "length", list(self.LENGTHS), self.length), ListChoice(opts, "size", list(V.SIZES), self.size),
                 T.Choice(opts, "resolution", list(RESOLUTION), self.resolution), T.Choice(opts, "quality", list(V.QUALITY), self.quality),
                 T.Choice(opts, "speed", V.SPEEDS, self.speed)]
        sd = _frame(opts); T.Text(sd, "SEED", font=T.f(9)).pack(side="left", padx=(0, 4))
        T.Button(sd, "Random", lambda: self.seed.set("random"), width=7).pack(side="left", padx=(0, 4)); T.Entry(sd, self.seed, width=9).pack(side="left")
        cells.append(sd)
        self.improve = tk.BooleanVar(value=self._mem.get("improve", True))
        imp = _frame(opts); T.Text(imp, "FULLER DESCRIPTION", font=T.f(9)).pack(side="left", padx=(0, 6)); T.Toggle(imp, self.improve).pack(side="left")
        cells.append(imp)
        for i, c in enumerate(cells): c.grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 12), pady=3)
        self.speed_note = T.Text(left, "", muted=True, font=T.f(8)); self.speed_note.configure(wraplength=520, justify="left")
        if not self.START_PICTURE: self.speed_note.pack(anchor="w", pady=(4, 0))   # (no room under a start picture)
        self.speed.trace_add("write", lambda *a: (prefs.set("speed_video", self.speed.get()), self._speed_words()))
        for v in (self.length, self.size, self.quality): v.trace_add("write", lambda *a: self._speed_words())
        b = _frame(left); b.pack(anchor="w", pady=(8, 4), before=opts)              # Make it / Stop under the words (as Paint it), the settings below
        self.go_btn = skin.button(T.Button(b, "Make it", self.go, width=14)); self.go_btn.pack(side="left")
        jobs.guard(self.go_btn, self.page_key, app, "your video")
        T.Button(b, "Stop", self.stop, kind="danger", width=8).pack(side="left", padx=8)
        T.Button(b, "Open my Videos folder", lambda: prefs.open_folder(V.videos_folder())).pack(side="left")
        self.msg = T.Text(left, "", muted=True, font=T.f(9)); self.msg.configure(wraplength=520, justify="left"); self.msg.pack(anchor="w", before=opts)
        self.used = T.Text(left, "", muted=True, font=T.f(8)); self.used.configure(wraplength=520, justify="left"); self.used.pack(anchor="w", before=opts)
        # right: the player and what to do with the video
        self.player = Player(right); self.player.pack(anchor="n")
        acts = _frame(right); acts.pack(pady=(8, 0))
        self.acts = [T.Button(acts, "Play with sound", self._play, width=15), T.Button(acts, "Save as GIF", lambda: self._save_as("gif"), width=12),
                     T.Button(acts, "Save as WebP", lambda: self._save_as("webp"), width=13), T.Button(acts, "Carry on from here", self._carry_on, width=18)]
        for i, w in enumerate(self.acts): w.grid(row=i // 2, column=i % 2, padx=4, pady=2, sticky="ew")
        self.info = T.Text(right, "", muted=True, font=T.f(8)); self.info.pack(pady=(4, 0))
        self.refresh(); self._speed_words()

    # ---- what's offered
    def _styles(self):
        out = ["None"]
        try:
            import styles, style_addons as SA
            out += [s for s in styles.BUILT_IN if s != "None"]
            out += [s for s, e in SA.entries().items() if SA.base_of(e) == self.model_key() and s not in out]
        except Exception: pass
        return out

    def _speed_words(self):
        V = self.V; w, h = V.SIZES.get(self.size.get(), (832, 480)); frames = V.LENGTHS.get(self.length.get(), 49)
        mode, why = V.plan_speed(self.speed.get(), w, h, frames, self.model_key())
        words = {"Fast": "FAST: the model stays on the graphics card.",
                 "Slow": "SLOW: the model waits in PC memory, so smaller cards make videos too, just more slowly."}
        lead = "AUTO → " if self.speed.get() == "Auto" else ""
        self.speed_note.configure(text=lead + words.get(mode, "") + " Shorter, smaller or Draft is quicker.")

    def refresh(self):
        self._fit_pick(); k = self.model_key(); miss = self.V.ltx_missing() if k == "ltx2" else self.V.missing()
        if miss:
            size = "about 23 GB" if k == "ltx2" else "about 9 GB"
            self.status.configure(text=("NEEDS " + self.V.MODELS[k]["label"].upper() if len(miss) > 1 else "NEEDS " + miss[0].upper()) + f" — {size}")
            if not self.get_btn.winfo_manager(): self.get_btn.pack(side="left")
        else:
            self.status.configure(text="READY — " + self.V.MODELS[k]["label"].upper())
            if self.get_btn.winfo_manager(): self.get_btn.pack_forget()

    # ---- the video model picker: the downloaded ones, weak to strong
    def _label(self, k): return f"{self.V.MODELS[k]['label']} · {self.V.MODELS[k]['power']}"

    def _model_names(self):
        have = self.V.downloaded_models(); keys = have or ["wan22"]
        return [self._label(k) for k in keys]

    def model_key(self):
        v = self.model.get() if hasattr(self, "model") else ""
        for k in self.V.MODELS:
            if v.startswith(self.V.MODELS[k]["label"]): return k
        return "wan22"

    def _fit_pick(self):
        if not hasattr(self, "model_choice"): return
        names = self._model_names(); self.model_choice.choices = names
        if self.model.get() not in names: self.model.set(names[-1])          # (the strongest one that's here)
        st = self._styles(); self.style_choice.choices = st
        if self.style.get() not in st: self.style.set("None")

    def build_inputs(self, left): pass

    def download(self):
        q = self.app.q
        def work():
            try:
                rep = lambda t, f: q.put(lambda t=t, f=f: self.player.progress(f, t))
                (self.V.install_ltx(report=rep) if self.model_key() == "ltx2" else self.V.download(report=rep))
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
                 speed=self.speed.get(), seed=self.seed.get(), improve=self.improve.get(), model=self.model.get(), resolution=self.resolution.get())
        if self.START_PICTURE: m["picture"] = getattr(self.slot, "path", "") or ""
        prefs.set(f"video_page:{self.TITLE}", m)

    def go(self):
        if jobs.busy(self.page_key): return
        text = self.prompt.get("1.0", "end").strip()
        try:
            if (self.V.ltx_missing() if self.model_key() == "ltx2" else self.V.missing()):
                raise Problem("THE VIDEO MODEL ISN'T HERE YET — press Download (at the top) first")
            image = self.start_picture()
            if not text and not image: raise Problem("SAY WHAT HAPPENS FIRST")
            seed = self.seed.get().strip()
            if seed != "random" and not seed.isdigit(): raise Problem("THE SEED IS A WHOLE NUMBER, OR RANDOM")
        except Problem as e: return T.banner(self.app, str(e))
        self._remember(text); self.stop_event.clear(); q = self.app.q
        style = self.style.get(); improve = self.improve.get() and bool(text)
        args = dict(seconds=self.length.get(), size=self.size.get(), quality=self.quality.get(), speed=self.speed.get(), image=image,
                    seed=None if seed == "random" else int(seed), stop=self.stop_event, meta=dict(section=self.TITLE, style=style),
                    model=self.model_key(), resolution=RESOLUTION.get(self.resolution.get(), 1.0))
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
                bits = SA.lora_for(style, self.model_key())
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
        self.info.configure(text=f"{r['seconds']} s · {r['frames']} frames · made the {r['speed'].lower()} way · seed {r['seed']} · saved as {os.path.basename(r['video'])}"
                                 + (" · has sound: Play with sound" if r.get("sound") else ""))
        T.banner(self.app, f"VIDEO SAVED — {os.path.basename(r['video'])} in your Videos folder", "success")

    def _play(self):
        """open the video in the PC's own player (that's where the sound plays)"""
        if not self._need_video(): return
        try:
            if sys.platform == "win32": os.startfile(self.video)
            else: import subprocess; subprocess.Popen(["xdg-open" if sys.platform != "darwin" else "open", self.video])
        except Exception as e: T.banner(self.app, f"COULDN'T OPEN IT — {e}", "error")

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


class LongVideoPage(VideoPage):
    """several 5-second clips, each starting from the last frame of the one before, joined into one video"""
    TITLE = "Long Video"; START_PICTURE = True; PIC_LABEL = "START PICTURE (optional)"
    INTRO = "Longer videos, made 5 seconds at a time: each part starts where the last one ended. One line per part (the last line carries on)."
    WORDS = "WHAT HAPPENS, ONE LINE PER 5-SECOND PART"
    LENGTH_DEFAULT = "10 seconds"
    @property
    def LENGTHS(self): return {"10 seconds": 2, "15 seconds": 3, "20 seconds": 4, "30 seconds": 6}

    def start_picture(self): return getattr(self.slot, "path", None) or None

    def go(self):
        if jobs.busy(self.page_key): return
        lines = [l.strip() for l in self.prompt.get("1.0", "end").splitlines() if l.strip()]
        k = self.model_key()
        try:
            if (self.V.ltx_missing() if k == "ltx2" else self.V.missing()): raise Problem("THE VIDEO MODEL ISN'T HERE YET — press Download (at the top) first")
            if not lines: raise Problem("SAY WHAT HAPPENS FIRST — one line for each 5-second part")
            seed = self.seed.get().strip()
            if seed != "random" and not seed.isdigit(): raise Problem("THE SEED IS A WHOLE NUMBER, OR RANDOM")
        except Problem as e: return T.banner(self.app, str(e))
        self._remember("\n".join(lines)); self.stop_event.clear(); q = self.app.q; V = self.V
        n = self.LENGTHS[self.length.get()]; style = self.style.get(); start = self.start_picture()
        seed = None if seed == "random" else int(seed); res = RESOLUTION.get(self.resolution.get(), 1.0)
        def work(job):
            import tempfile, shutil as sh, random
            clips = []; img = start; work_dir = tempfile.mkdtemp(prefix="ie-long-"); s0 = seed if seed is not None else random.randint(0, 2 ** 31 - 2 - n)
            try:
                for i in range(n):
                    if self.stop_event.is_set(): return None
                    words, lora = self._style_bits(style, lines[min(i, len(lines) - 1)])
                    def progress(f, t, i=i):
                        frac = (i + (f or 0)) / n; t = f"Part {i + 1} of {n}: {t}"
                        job.say(t); q.put(lambda frac=frac, t=t: (self.msg.configure(text=t.upper()), self.player.progress(frac, t)))
                    r = V.make(words, seconds="5 seconds", size=self.size.get(), quality=self.quality.get(), speed=self.speed.get(), image=img,
                               seed=s0 + i, lora=lora, on_progress=progress, stop=self.stop_event, model=k, resolution=res, save=False,
                               meta=dict(section=self.TITLE, part=i + 1))
                    clip = os.path.join(work_dir, f"part{i:02d}" + os.path.splitext(r["video"])[1]); sh.move(r["video"], clip); clips.append(clip)
                    img = V.last_frame(clip, os.path.join(work_dir, f"last{i:02d}.png"))
                progress(0.99, "Joining the parts…")
                name = "-".join(lines[0].lower().split())[:40] or "long-video"
                if k == "ltx2":                                                  # (with sound: joined by ffmpeg, the sound kept)
                    import audio_engine as A, datetime
                    dest = os.path.join(V.videos_folder(), f"{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}-{name}.mp4"); A.join(clips, dest)
                else:
                    jpgs = []
                    for j, c in enumerate(clips): jpgs += V.jpeg_frames(c)[(1 if j else 0):]   # (each part's first frame is the last one's last)
                    tmp = os.path.join(work_dir, "joined.avi"); V.write_avi(jpgs, tmp); dest = V._save(tmp, name, meta=dict(section=self.TITLE, parts=lines, seed=s0, model=k))
                frames = len(V.frames_of(dest, limit=None)) if k == "ltx2" else len(jpgs)
                return dict(video=dest, frames=frames, fps=V.FPS, seconds=round(frames / V.FPS, 1), speed=r["speed"], seed=s0, folder=V.videos_folder(), sound=k == "ltx2")
            finally: sh.rmtree(work_dir, ignore_errors=True)
        def failed(e): q.put(lambda e=e: (self.msg.configure(text=""), self.player.progress_done(), T.banner(self.app, f"COULDN'T MAKE THE VIDEO — {e}")))
        self.job = jobs.submit("AI Videos", f"{self.TITLE}: {lines[0][:40]}", work, kind="video", page=self.page_key, engine="image",
                               on_done=lambda r: q.put(lambda: self._show(r)), on_error=failed, on_cancel=self._stop_now)
        self.player.progress(None, "Waiting its turn…" if jobs.running() else "Getting ready…")


class AddSoundPage(tk.Frame):
    """the audio model: a voice saying your words, and sound effects that match what happens, mixed into a video"""
    TITLE = "Add Sound"
    def __init__(self, master, app):
        super().__init__(master, bg=master["bg"]); self.app = app; T.on_change(lambda: self.configure(bg=self.master["bg"]))
        import audio_engine as A, video_engine as V; self.A, self.V = A, V
        from image_pages import ListChoice
        self.page_key = "AI Videos/Add Sound"; self.job = None; self.stop_event = threading.Event(); self.video = None; self.result = None
        self._mem = prefs.get("video_page:Add Sound") or {}
        T.Title(self, self.TITLE).pack(pady=(0, 2))
        T.Text(self, "Give a video a voice, sound effects that match what happens in it, or both. Uses the audio model (Settings > AI Models > Audio).",
               muted=True, font=T.f(9)).pack()
        split = _frame(self); split.pack(fill="both", expand=True, pady=(6, 0))
        split.columnconfigure(0, weight=1, uniform="half"); split.columnconfigure(1, weight=1, uniform="half")
        left = _frame(split); left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = _frame(split); right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        r = _frame(left); r.pack(anchor="w")
        T.Button(r, "Latest video", self.latest, width=13).pack(side="left"); T.Button(r, "Choose a video…", self.choose, width=16).pack(side="left", padx=6)
        self.vname = T.Text(r, "no video chosen", muted=True, font=T.f(8)); self.vname.pack(side="left", padx=6)
        v = lambda k, d: tk.StringVar(value=self._mem.get(k, d))
        # the voice
        T.Line(left, vertical=False).pack(fill="x", pady=(10, 0))
        h = _frame(left); h.pack(fill="x", pady=(4, 2)); self.use_voice = tk.BooleanVar(value=self._mem.get("use_voice", True))
        T.Toggle(h, self.use_voice).pack(side="left"); T.Text(h, "VOICE: WHAT IT SAYS", font=T.f(10)).pack(side="left", padx=6)
        self.words = T.Field(left, height=3); self.words.pack(fill="x")
        if self._mem.get("words"): self.words.insert("1.0", self._mem["words"])
        o = _frame(left); o.pack(anchor="w", pady=(4, 0))
        self.voice = v("voice", "American woman: Heart"); self.speed = v("speed", "Normal"); self.vpower = v("vpower", "")
        ListChoice(o, "voice", list(A.VOICES), self.voice).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=2)
        T.Choice(o, "speed", ["Slow", "Normal", "Quick"], self.speed).grid(row=0, column=1, sticky="w", pady=2)
        self.vchoice = T.Choice(o, "voice model", ["Weak (small)", "Strong (full)"], self.vpower); self.vchoice.grid(row=1, column=0, sticky="w", pady=2)
        self.vget = T.Button(o, "Download", lambda: self.download("voices"), width=10); self.vget.grid(row=1, column=1, sticky="w", pady=2)
        # the sound effects
        T.Line(left, vertical=False).pack(fill="x", pady=(10, 0))
        h = _frame(left); h.pack(fill="x", pady=(4, 2)); self.use_fx = tk.BooleanVar(value=self._mem.get("use_fx", True))
        T.Toggle(h, self.use_fx).pack(side="left"); T.Text(h, "SOUND EFFECTS: WHAT YOU HEAR (optional)", font=T.f(10)).pack(side="left", padx=6)
        self.fx_words = T.Entry(left, tk.StringVar(value=self._mem.get("fx_words", "")), width=60); self.fx_words.pack(fill="x")
        o2 = _frame(left); o2.pack(anchor="w", pady=(4, 0)); self.fpower = v("fpower", "")
        self.fchoice = T.Choice(o2, "effects model", ["Weak (small)", "Strong (large)"], self.fpower); self.fchoice.grid(row=0, column=0, sticky="w", padx=(0, 10), pady=2)
        self.fget = T.Button(o2, "Download", lambda: self.download("effects"), width=10); self.fget.grid(row=0, column=1, sticky="w", pady=2)
        # the mix
        T.Line(left, vertical=False).pack(fill="x", pady=(10, 0))
        o3 = _frame(left); o3.pack(anchor="w", pady=(6, 0)); self.vvol = v("vvol", "Normal"); self.fvol = v("fvol", "Normal")
        T.Choice(o3, "voice volume", list(VOLUME), self.vvol).pack(side="left", padx=(0, 10)); T.Choice(o3, "effects volume", list(VOLUME), self.fvol).pack(side="left")
        b = _frame(left); b.pack(anchor="w", pady=(10, 0))
        self.go_btn = skin.button(T.Button(b, "Add the sound", self.go, width=16)); self.go_btn.pack(side="left")
        jobs.guard(self.go_btn, self.page_key, app, "the sound")
        T.Button(b, "Stop", self.stop, kind="danger", width=8).pack(side="left", padx=8)
        T.Button(b, "Open my Videos folder", lambda: prefs.open_folder(V.videos_folder())).pack(side="left")
        self.msg = T.Text(left, "", muted=True, font=T.f(9)); self.msg.configure(wraplength=520, justify="left"); self.msg.pack(anchor="w", pady=(6, 0))
        self.player = Player(right); self.player.pack(anchor="n")
        acts = _frame(right); acts.pack(pady=(8, 0))
        T.Button(acts, "Play with sound", self._play, width=16).pack(side="left", padx=4)
        self.info = T.Text(right, "", muted=True, font=T.f(8)); self.info.pack(pady=(4, 0))
        self.bind("<Map>", lambda e: e.widget is self and self.refresh(), add="+"); self.refresh()

    def refresh(self):
        A = self.A
        for kind, var, ch, btn, names in (("voices", self.vpower, self.vchoice, self.vget, ["Weak (small)", "Strong (full)"]),
                                          ("effects", self.fpower, self.fchoice, self.fget, ["Weak (small)", "Strong (large)"])):
            have = A.downloaded(kind); ch.choices = [names[0 if p == "weak" else 1] for p in have] or names
            if var.get() not in ch.choices: var.set(ch.choices[-1])
            want = "strong" if var.get().startswith("Strong") else "weak"
            btn.configure(text="Download" if not A.have(kind, want) else "Ready")
        if self._mem.get("video") and os.path.exists(self._mem["video"]) and not self.video: self._set_video(self._mem["video"])

    def _power(self, var): return "strong" if var.get().startswith("Strong") else "weak"

    def download(self, kind):
        A = self.A; power = self._power(self.vpower if kind == "voices" else self.fpower); q = self.app.q
        if A.have(kind, power): return T.banner(self.app, "IT'S HERE ALREADY", "success")
        def work():
            try:
                A.install(kind, power, report=lambda t, f: q.put(lambda t=t, f=f: self.player.progress(f, t)))
                q.put(lambda: (self.player.progress_done(), self.refresh(), T.banner(self.app, "READY — " + ("the voice model" if kind == "voices" else "the sound effects model"), "success")))
            except Exception as e: q.put(lambda e=e: (self.player.progress_done(), T.banner(self.app, f"DOWNLOAD DIDN'T FINISH — {e}", "error")))
        threading.Thread(target=work, daemon=True, name="audio download").start()
        T.banner(self.app, "DOWNLOADING " + ("THE VOICE MODEL (small)" if kind == "voices" else "THE SOUND EFFECTS MODEL — PyTorch and MMAudio, a few GB"), "success")

    def latest(self):
        fs = sorted([f for f in glob.glob(os.path.join(self.V.videos_folder(), "*")) if f.lower().endswith((".avi", ".mp4", ".webm"))], key=os.path.getmtime)
        if not fs: return T.banner(self.app, "NO VIDEOS YET — make one in Text to Video")
        self._set_video(fs[-1])

    def choose(self):
        from tkinter import filedialog
        p = filedialog.askopenfilename(parent=self.app, initialdir=self.V.videos_folder(), title="Choose a video",
                                       filetypes=[("Videos", "*.avi *.mp4 *.webm *.mov *.mkv"), ("All files", "*.*")])
        if p: self._set_video(p)

    def receive(self, path): self._set_video(path)

    def _set_video(self, p):
        self.video = p; self.vname.configure(text=os.path.basename(p))
        try:
            fr = self.V.frames_of(p, limit=200)
            if fr: self.player.load(fr, self.V.FPS)
        except Exception: pass

    def go(self):
        if jobs.busy(self.page_key): return
        A = self.A; words = self.words.get("1.0", "end").strip(); fxw = self.fx_words.get().strip() if hasattr(self.fx_words, "get") else ""
        voice_on = self.use_voice.get() and bool(words); fx_on = self.use_fx.get()
        vp, fp = self._power(self.vpower), self._power(self.fpower)
        try:
            if not self.video or not os.path.exists(self.video): raise Problem("CHOOSE A VIDEO FIRST — Latest video or Choose a video")
            if not voice_on and not fx_on: raise Problem("TURN ON THE VOICE (and type what it says) OR THE SOUND EFFECTS")
            if voice_on and not A.have("voices", vp): raise Problem("DOWNLOAD THE VOICE MODEL FIRST (the Download button beside it)")
            if fx_on and not A.have("effects"): raise Problem("DOWNLOAD THE SOUND EFFECTS MODEL FIRST (the Download button beside it)")
        except Problem as e: return T.banner(self.app, str(e))
        prefs.set("video_page:Add Sound", dict(video=self.video, words=words, use_voice=self.use_voice.get(), use_fx=fx_on, fx_words=fxw, voice=self.voice.get(),
                                               speed=self.speed.get(), vpower=self.vpower.get(), fpower=self.fpower.get(), vvol=self.vvol.get(), fvol=self.fvol.get()))
        self.stop_event.clear(); q = self.app.q; video = self.video
        voice = A.VOICES.get(self.voice.get(), "af_heart"); speed = {"Slow": 0.85, "Normal": 1.0, "Quick": 1.15}[self.speed.get()]
        vv, fv = VOLUME[self.vvol.get()], VOLUME[self.fvol.get()]
        def work(job):
            def say(t): job.say(t); q.put(lambda t=t: (self.msg.configure(text=t.upper()), self.player.progress(None, t)))
            tracks = []
            if voice_on: say("Speaking the words…"); tracks.append((A.speak(words, voice, speed, power=vp)[0], vv))
            if fx_on:
                say("Making the sound effects (on the processor this takes a few minutes)…")
                tracks.append((A.effects(video, fxw, power=fp, on_progress=lambda f, t: say(t), stop=self.stop_event), fv))
            if self.stop_event.is_set(): return None
            say("Mixing it into the video…")
            out = os.path.splitext(video)[0] + "-with-sound.mp4"; n = 2
            while os.path.exists(out): out = os.path.splitext(video)[0] + f"-with-sound-{n}.mp4"; n += 1
            return A.mix(video, tracks, out)
        def done(out):
            def show():
                self.player.progress_done(); self.msg.configure(text="")
                if not out: return
                self.result = out; self.info.configure(text=f"saved as {os.path.basename(out)} · Play with sound to hear it")
                T.banner(self.app, f"SOUND ADDED — {os.path.basename(out)} in your Videos folder", "success")
            q.put(show)
        def failed(e): q.put(lambda e=e: (self.msg.configure(text=""), self.player.progress_done(), T.banner(self.app, f"COULDN'T ADD THE SOUND — {e}")))
        self.job = jobs.submit("AI Videos", "Add Sound: " + os.path.basename(video)[:40], work, kind="audio", page=self.page_key, engine="audio",
                               on_done=done, on_error=failed, on_cancel=lambda: (self.stop_event.set(), A.stop_now()))
        self.player.progress(None, "Waiting its turn…" if jobs.running() else "Getting ready…")

    def stop(self):
        if self.job is not None and self.job.state in ("waiting", "running"): jobs.cancel(self.job); self.msg.configure(text="STOPPED"); self.player.progress_done()

    def _play(self):
        p = self.result or self.video
        if not p: return T.banner(self.app, "CHOOSE A VIDEO FIRST")
        try:
            if sys.platform == "win32": os.startfile(p)
            else: import subprocess; subprocess.Popen(["xdg-open" if sys.platform != "darwin" else "open", p])
        except Exception as e: T.banner(self.app, f"COULDN'T OPEN IT — {e}", "error")


VOLUME = {"Quiet": 0.5, "Normal": 1.0, "Loud": 1.6}


def page_classes(): return {"Text to Video": TextVideoPage, "Image to Video": ImageVideoPage, "Long Video": LongVideoPage, "Add Sound": AddSoundPage}
