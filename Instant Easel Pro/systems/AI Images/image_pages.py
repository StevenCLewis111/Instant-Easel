"""
image_pages.py: the AI Images tab's working pages.

    Text to Image   type what you want -> (the core text model turns it into a clear picture description) -> the image engine paints it
    Image to Image  pick a picture (the box opens in your Images folder) -> words for what to change -> it repaints it

Every picture is saved into your Images folder the moment it's made, so any tab can pick it up from there.
"""
import os, threading, tkinter as tk
from tkinter import filedialog
import theme as T, prefs, skin

QUALITY = {"Fast (12 steps)": 12, "Normal (20 steps)": 20, "Best (30 steps)": 30}
CHANGE = {"A little": 0.35, "Some": 0.55, "A lot": 0.75}

def _frame(parent):
    f = tk.Frame(parent, bg=parent["bg"]); T.on_change(lambda: f.configure(bg=f.master["bg"])); return f

class PaintPage(tk.Frame):
    TITLE = "Text to Image"; FROM_PICTURE = False
    INTRO = "Type what you want. The core text model turns it into a clear picture description, then the image engine paints it."
    def __init__(self, master, app):
        super().__init__(master, bg=master["bg"]); self.app = app; T.on_change(lambda: self.configure(bg=self.master["bg"]))
        import imaging, image_models as IM; self.imaging = imaging; self.IM = IM
        self.thread = None; self.stop_event = threading.Event(); self.start_image = None; self._ph = []
        T.Title(self, self.TITLE).pack(pady=(0, 4)); T.Text(self, self.INTRO, muted=True).pack()
        st = _frame(self); st.pack(pady=(8, 4))
        self.status = T.Text(st, "", font=T.f(10)); self.status.pack(side="left", padx=(0, 10))
        self.get_btn = T.Button(st, "Download the image engine", self.download); self.get_btn.pack(side="left")
        if self.FROM_PICTURE:
            r = _frame(self); r.pack(pady=(6, 0))
            T.Button(r, "Choose a picture", self.choose, width=18).pack(side="left", padx=6)
            self.pick_lbl = tk.Label(r, text="no picture yet", bg=T.PALETTE["field"], fg=T.PALETTE["muted"], width=22, height=5); self.pick_lbl.pack(side="left", padx=6)
        T.Text(self, "WHAT YOU WANT" if not self.FROM_PICTURE else "WHAT TO CHANGE", font=T.f(10)).pack(anchor="w", pady=(8, 2))
        self.prompt = T.Field(self, height=3); self.prompt.pack(fill="x")
        opts = _frame(self); opts.pack(pady=(8, 0))
        self.size = tk.StringVar(value=list(self.imaging.SIZES)[0]); T.Choice(opts, "size", list(self.imaging.SIZES), self.size).pack(side="left", padx=4)
        self.count = tk.StringVar(value="1"); T.Choice(opts, "how many", ["1", "2", "4"], self.count).pack(side="left", padx=4)
        self.quality = tk.StringVar(value="Normal (20 steps)"); T.Choice(opts, "quality", list(QUALITY), self.quality).pack(side="left", padx=4)
        if self.FROM_PICTURE:
            self.change = tk.StringVar(value="Some"); T.Choice(opts, "change", list(CHANGE), self.change).pack(side="left", padx=4)
        self.model = tk.StringVar(value=self.IM.active() or "None"); self.model_choice = T.Choice(opts, "image model", ["None"] + self.IM.names(), self.model)
        self.model_choice.pack(side="left", padx=4)
        r2 = _frame(self); r2.pack(pady=(8, 0)); self.improve = tk.BooleanVar(value=True)
        T.Text(r2, "Let the core text model improve my words", font=T.f(9)).pack(side="left", padx=(0, 6)); T.Toggle(r2, self.improve).pack(side="left")
        b = _frame(self); b.pack(pady=10)
        self.go_btn = skin.button(T.Button(b, "Paint it", self.go, width=14)); self.go_btn.pack(side="left", padx=6)
        T.Button(b, "Stop", self.stop, kind="danger", width=8).pack(side="left", padx=6)
        T.Button(b, "Open my Images folder", lambda: prefs.open_folder(prefs.save_folder()), width=22).pack(side="left", padx=6)
        self.msg = T.Text(self, "", muted=True); self.msg.pack()
        self.used = T.Text(self, "", muted=True, font=T.f(8)); self.used.configure(wraplength=900); self.used.pack()
        self.results = _frame(self); self.results.pack(fill="both", expand=True, pady=(8, 0))
        T.Text(self, "Every picture is saved into your Images folder straight away, so every tab can pick it up from there.", muted=True, font=T.f(8)).pack(side="bottom")
        self.bind("<Map>", lambda e: self.refresh(), add="+"); self.refresh(); self._tick()

    def refresh(self):
        self.model_choice.choices = ["None"] + self.IM.names()
        if self.model.get() not in self.model_choice.choices: self.model.set("None")

    def _tick(self):
        if not self.winfo_exists(): return
        st = self.imaging.status(); pct = f" {st['progress'] * 100:.0f}%" if st["state"] in ("downloading", "painting") and st.get("progress") else ""
        self.status.configure(text=f"{(st['detail'] or st['state'] or '').upper()}{pct}")
        show = st["state"] in ("not-installed", "error")
        if show and not self.get_btn.winfo_manager(): self.get_btn.pack(side="left")
        elif not show and self.get_btn.winfo_manager(): self.get_btn.pack_forget()
        self.after(700, self._tick)

    def download(self):
        q = self.app.q
        self.imaging.download(on_done=lambda ok, m: q.put(lambda: T.banner(self.app, ("DOWNLOADED — " if ok else "DOWNLOAD FAILED — ") + m, "success" if ok else "error")))

    def choose(self):
        from PIL import Image, ImageTk
        p = filedialog.askopenfilename(parent=self.app, initialdir=prefs.save_folder(), title="Choose a picture",
                                       filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")])
        if not p: return
        try: self.start_image = Image.open(p).convert("RGB")
        except Exception as e: return T.banner(self.app, f"CAN'T OPEN THAT PICTURE — {e}")
        th = self.start_image.copy(); th.thumbnail((180, 120)); self._pick_ph = ImageTk.PhotoImage(th)
        self.pick_lbl.configure(image=self._pick_ph, width=th.width, height=th.height, text="")

    def _wording(self, text):
        """the core text model's clearer version of the request (the request itself if the text model isn't set up)"""
        if not self.improve.get(): return text
        try:
            import brain
            if not brain.installed(): return text
            ans = brain.ask("AI Images", "Rewrite this request as one short, vivid picture description for an image model: the subject first, "
                            "then style, lighting and details, comma-separated, under 50 words. Reply with the description only.\n\n" + text,
                            max_tokens=120, use_library=False)
            return ans.strip().strip('"') or text
        except Exception: return text

    def go(self):
        if self.thread is not None and self.thread.is_alive(): return
        text = self.prompt.get("1.0", "end").strip()
        if not text: return T.banner(self.app, "TYPE WHAT YOU WANT FIRST")
        if self.FROM_PICTURE and self.start_image is None: return T.banner(self.app, "CHOOSE A PICTURE FIRST — the box opens in your Images folder")
        if not self.imaging.ready(): return T.banner(self.app, "THE IMAGE ENGINE ISN'T DOWNLOADED YET — press Download the image engine")
        self.stop_event.clear(); q = self.app.q; n = int(self.count.get()); model = "" if self.model.get() == "None" else self.model.get()
        kw = dict(n=n, size=self.size.get(), steps=QUALITY[self.quality.get()], image_model=model, stop=self.stop_event)
        if self.FROM_PICTURE: kw.update(init_image=self.start_image, strength=CHANGE[self.change.get()])
        self.msg.configure(text="GETTING READY…")
        def work():
            try:
                wording = self._wording(text) if not self.FROM_PICTURE else text
                q.put(lambda: self.used.configure(text=f"PAINTING FROM: {wording}"))
                saved = self.imaging.paint(wording, on_progress=lambda f, t: q.put(lambda t=t: self.msg.configure(text=t.upper())), **kw)
                q.put(lambda: self._show(saved))
            except Exception as e:
                prefs.log_error(type(e), e, e.__traceback__); q.put(lambda e=e: (self.msg.configure(text=""), T.banner(self.app, f"COULDN'T PAINT — {e}")))
        self.thread = threading.Thread(target=work, name="paint", daemon=True); self.thread.start()

    def stop(self): self.stop_event.set(); self.imaging.stop_now()

    def _show(self, saved):
        from PIL import Image, ImageTk
        for w in self.results.winfo_children(): w.destroy()
        self._ph = []
        for p in saved:
            try: im = Image.open(p); im.thumbnail((300, 300)); ph = ImageTk.PhotoImage(im)
            except Exception: continue
            self._ph.append(ph); lb = tk.Label(self.results, image=ph, bg=self["bg"], cursor="hand2"); lb.pack(side="left", padx=6)
            lb.bind("<Button-1>", lambda e, p=p: prefs.open_folder(os.path.dirname(p)))
        self.msg.configure(text=f"DONE — {len(saved)} SAVED TO YOUR IMAGES FOLDER" if saved else "STOPPED")
        if saved: T.banner(self.app, f"PAINTED — {len(saved)} saved to your Images folder", "success")

class FromPicturePage(PaintPage):
    TITLE = "Image to Image"; FROM_PICTURE = True
    INTRO = "Choose a picture (the box opens in your Images folder), say what to change, and it repaints it."

def page_classes(): return {"Text to Image": PaintPage, "Image to Image": FromPicturePage}
