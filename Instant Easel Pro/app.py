"""
Painterly Image Engine: a standalone Windows desktop app (works offline; nothing is sent anywhere).
Open an image, choose one of your painting styles, and repaint it. Or render one of the book's scenes.
"""
import os, sys, threading, shutil, random, queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

def base_dir():   # where bundled files live (works both as a script and as a PyInstaller .exe)
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
def user_styles_dir():   # styles the user adds live next to the .exe so they persist
    d = os.path.join(os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)), "my-styles")
    os.makedirs(d, exist_ok=True); return d

def library_dir():   # the learning library lives next to the .exe so it grows over time
    d = os.path.join(os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)), "my-library")
    os.makedirs(d, exist_ok=True); return d

sys.path.insert(0, base_dir())
from PIL import Image, ImageTk
import draw, paint, learn
import theme as T                                   # messages use the app's banners
paint.HERE = base_dir()
paint.REFS = {"warm": os.path.join(base_dir(), "styles", "sunset-field.jpg"),
              "night": os.path.join(base_dir(), "styles", "night-city.jpg"),
              "summit": os.path.join(base_dir(), "styles", "summit.jpg")}
draw.FONT = os.path.join(base_dir(), "fonts", "EBGaramond-Italic.ttf")

class App(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Painterly Image Engine"); self.geometry("1100x760"); self.minsize(900, 620)
        self.q = queue.Queue(); self.after(100, self._poll)        # worker threads hand UI updates to the main thread
        self.src = None; self.result = None
        holder = ttk.Frame(self); holder.pack(side="left", fill="y")                  # the controls column scrolls on small screens
        lc = tk.Canvas(holder, width=300, highlightthickness=0); lsb = ttk.Scrollbar(holder, orient="vertical", command=lc.yview)
        left = ttk.Frame(lc, padding=12); left.bind("<Configure>", lambda e: lc.configure(scrollregion=lc.bbox("all")))
        lc.create_window((0, 0), window=left, anchor="nw"); lc.configure(yscrollcommand=lsb.set)
        lc.pack(side="left", fill="y"); lsb.pack(side="left", fill="y")
        lc.bind_all("<MouseWheel>", lambda e: lc.yview_scroll(int(-e.delta / 120), "units"))
        ttk.Label(left, text="Painterly Image Engine", font=("Georgia", 15, "bold")).pack(anchor="w", pady=(0, 10))
        ttk.Button(left, text="Open image…", command=self.open_image).pack(fill="x")
        ttk.Label(left, text="…or render a book scene:").pack(anchor="w", pady=(12, 2))
        import scenes; self.scenes = {s[3]: s for s in scenes.S}
        self.scene_var = tk.StringVar(); cb = ttk.Combobox(left, textvariable=self.scene_var, values=list(self.scenes), width=28, state="readonly")
        cb.pack(fill="x"); cb.bind("<<ComboboxSelected>>", self.load_scene)
        ttk.Button(left, text="Paint landscape (new engine)…", command=self.new_engine).pack(fill="x", pady=(8, 0))
        ttk.Button(left, text="Open drawing canvas", command=lambda: __import__("paint_window").PaintWindow(self)).pack(fill="x", pady=(4, 0))
        ttk.Button(left, text="Paint over this result by hand", command=self.paint_over).pack(fill="x", pady=(4, 0))
        ttk.Separator(left).pack(fill="x", pady=12)
        ttk.Label(left, text="Style (your paintings):").pack(anchor="w")
        self.style_var = tk.StringVar(); self.style_box = ttk.Combobox(left, textvariable=self.style_var, width=28, state="readonly"); self.style_box.pack(fill="x")
        ttk.Button(left, text="Add a painting as a style…", command=self.add_style).pack(fill="x", pady=(4, 0))
        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Label(left, text="Learning library:", font=("Georgia", 11, "bold")).pack(anchor="w")
        ttk.Button(left, text="Add images to learn from…", command=self.add_library).pack(fill="x", pady=(2, 0))
        ttk.Button(left, text="Learn from library", command=self.learn_library).pack(fill="x", pady=(4, 0))
        self.libinfo = tk.StringVar(); ttk.Label(left, textvariable=self.libinfo, wraplength=230, foreground="#555").pack(anchor="w")
        self.swatch = tk.Canvas(left, width=230, height=18, highlightthickness=0); self.swatch.pack(anchor="w", pady=(2, 0))
        self.interior = tk.BooleanVar(); ttk.Checkbutton(left, text="Interior / close-up (no borrowed sky)", variable=self.interior).pack(anchor="w", pady=(10, 0))
        ttk.Label(left, text="Brushwork seed:").pack(anchor="w", pady=(10, 0))
        self.seed = tk.IntVar(value=7); ttk.Spinbox(left, from_=0, to=9999, textvariable=self.seed, width=8).pack(anchor="w")
        ttk.Button(left, text="New random seed", command=lambda: self.seed.set(random.randint(0, 9999))).pack(anchor="w", pady=(2, 0))
        ttk.Label(left, text="Caption (optional):").pack(anchor="w", pady=(10, 0))
        self.caption = tk.StringVar(); ttk.Entry(left, textvariable=self.caption, width=30).pack(fill="x")
        ttk.Separator(left).pack(fill="x", pady=12)
        self.paint_btn = ttk.Button(left, text="Paint it", command=self.run); self.paint_btn.pack(fill="x", ipady=6)
        ttk.Button(left, text="Save result…", command=self.save).pack(fill="x", pady=(6, 0))
        self.status = tk.StringVar(value="Open an image or pick a scene."); ttk.Label(left, textvariable=self.status, wraplength=230, foreground="#555").pack(anchor="w", pady=(12, 0))
        self.prog = ttk.Progressbar(left, mode="indeterminate"); self.prog.pack(fill="x", pady=(6, 0))
        right = ttk.Frame(self, padding=12); right.pack(side="left", fill="both", expand=True)
        self.before = ttk.Label(right); self.before.pack(side="left", expand=True)
        self.after_lbl = ttk.Label(right); self.after_lbl.pack(side="left", expand=True)
        self.refresh_styles(); self.refresh_library()

    def _poll(self):
        """run UI updates queued by background threads (Tkinter is only safe on its own thread)"""
        try:
            while True: self.q.get_nowait()()
        except queue.Empty: pass
        self.after(100, self._poll)

    def refresh_library(self):
        imgs = [f for root, _, fs in os.walk(library_dir()) for f in fs if f.lower().endswith(learn.EXT) and "patches" not in root]
        self.profile = learn.load(library_dir())
        state = ("learned: " + ", ".join(f"{k} {v['images']}" for k, v in self.profile.get("subjects", {}).items())) if self.profile and self.profile.get("subjects") else ("learned" if self.profile else "not learned yet")
        self.libinfo.set(f"{len(imgs)} images in the library ({state}).")
        self.swatch.delete("all")
        if self.profile:
            cols = [c for sec in ("sky", "mountains", "ground") for c in self.profile.get(sec, {}).values()] + [c for s in self.profile.get("subjects", {}).values() for c in s.get("palette", [])]
            for i, c in enumerate(cols[:15]):
                self.swatch.create_rectangle(i * 15, 0, i * 15 + 14, 18, fill="#%02x%02x%02x" % tuple(int(x) for x in c[:3]), outline="")

    def add_library(self):
        """pick images; the app guesses what each one shows; you confirm or correct; each goes to its subject"""
        ps = filedialog.askopenfilenames(title="Choose images for the engine to learn from", filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.avif *.gif *.tif *.tiff"), ("All files", "*.*")])
        if not ps: return
        win = tk.Toplevel(self); win.title("What does each image show?"); win.geometry("640x520")
        ttk.Label(win, text="The engine guessed what each image shows. Check the guesses, change any that are wrong, then press Add.", wraplength=600).pack(anchor="w", padx=10, pady=8)
        frame = ttk.Frame(win); frame.pack(fill="both", expand=True, padx=10)
        canvas = tk.Canvas(frame, highlightthickness=0); sb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview); inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=inner, anchor="nw"); canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        rows = []
        for p in ps:
            try: g, conf, _ = learn.guess_label(p)
            except Exception: g, conf = "scene", "unsure"
            r = ttk.Frame(inner); r.pack(fill="x", pady=2)
            th = Image.open(p).convert("RGB"); th.thumbnail((64, 64)); ph = ImageTk.PhotoImage(th); lb = ttk.Label(r, image=ph); lb.image = ph; lb.pack(side="left")
            ttk.Label(r, text=os.path.basename(p)[:34], width=36).pack(side="left", padx=6)
            v = tk.StringVar(value=g); ttk.Combobox(r, textvariable=v, values=learn.LABELS, width=11, state="readonly").pack(side="left")
            ttk.Label(r, text="(guess: " + conf + ")", foreground="#888").pack(side="left", padx=6)
            rows.append((p, v))
        def commit():
            for p, v in rows:
                d = os.path.join(library_dir(), v.get()); os.makedirs(d, exist_ok=True); shutil.copy(p, d)
            win.destroy(); self.refresh_library(); self.status.set(f"Added {len(rows)} images, sorted by subject. Press 'Learn from library'.")
        ttk.Button(win, text="Add to library", command=commit).pack(pady=8)

    def learn_library(self):
        self.prog.start(12); self.status.set("Learning from the library… (a few seconds per image)")
        def work():
            try:
                prof = learn.learn_labelled(library_dir(), keep_images=False)
                scenes = os.path.join(library_dir(), "scene")
                if os.path.isdir(scenes) and os.listdir(scenes): learn.learn(scenes)
                subs = ", ".join(f"{k} ({v['images']})" for k, v in prof.get("subjects", {}).items())
                msg = f"Learned: {subs or 'nothing yet'}. Choose the style 'My library (learned)'."
            except SystemExit as e: msg = str(e)
            except Exception as e: msg = f"Learning failed: {e}"
            self.q.put(lambda: (self.prog.stop(), self.refresh_library(), self.refresh_styles(), self.status.set(msg)))
        threading.Thread(target=work, daemon=True).start()

    def refresh_styles(self):
        names = ["warm (sunset field)", "night (night city)"]
        if learn.load(library_dir()): names.insert(0, "My library (learned)")
        self.custom = {}
        for d in (os.path.join(base_dir(), "styles"), user_styles_dir()):
            for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
                if f.lower().endswith((".jpg", ".jpeg", ".png")) and f not in ("sunset-field.jpg", "night-city.jpg", "summit.jpg"):
                    self.custom[f] = os.path.join(d, f); names.append(f)
        self.style_box["values"] = names
        if not self.style_var.get(): self.style_var.set(names[0])

    def style_kind(self):
        v = self.style_var.get()
        if v.startswith("My library"):
            prof = learn.load(library_dir())
            if prof and self.src is not None: return learn.closest(prof, library_dir(), self.src) or "warm"   # nearest-mood library image; warm once images are deleted
            return "warm"
        if v.startswith("warm"): return "warm"
        if v.startswith("night"): return "night"
        return self.custom.get(v, "warm")

    def show(self, im, label):
        t = im.copy(); t.thumbnail((400, 600)); ph = ImageTk.PhotoImage(t); label.configure(image=ph); label.image = ph

    def fit(self, im):
        w, h = im.size; tw = min(w, int(h * 2 / 3)); th = int(tw * 3 / 2)
        return im.crop(((w - tw) // 2, (h - th) // 2, (w - tw) // 2 + tw, (h - th) // 2 + th)).resize((draw.W, draw.H), Image.LANCZOS)

    def open_image(self):
        p = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.avif *.gif *.tif *.tiff"), ("All files", "*.*")])
        if p: self.src = self.fit(Image.open(p).convert("RGB")); self.show(self.src, self.before); self.status.set("Image loaded. Choose a style and press Paint it.")

    def load_scene(self, _=None):
        s = self.scenes[self.scene_var.get()]
        self.src = s[5](draw.canvas()); self.caption.set(s[4]); self.show(self.src, self.before); self.status.set(f"Scene {s[3]} loaded.")

    def add_style(self):
        p = filedialog.askopenfilename(title="Choose a painting to use as a style", filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.avif *.gif *.tif *.tiff"), ("All files", "*.*")])
        if p: shutil.copy(p, user_styles_dir()); self.refresh_styles(); self.style_var.set(os.path.basename(p)); self.status.set("Style added. It is saved in the my-styles folder next to the app.")

    def run(self):
        if self.src is None: return T.banner(self, "NOTHING TO PAINT YET — open an image or pick a scene first")
        self.paint_btn.state(["disabled"]); self.prog.start(12); self.status.set("Painting… (about 10–20 seconds)")
        def work():
            try:
                out = paint.paint(self.src, self.style_kind(), seed=int(self.seed.get()), interior=self.interior.get())
                if self.caption.get().strip(): out = draw.caption(out, self.caption.get().strip())
                self.result = out; self.q.put(lambda: (self.show(out, self.after_lbl), self.status.set("Done. Save it, or change the seed and paint again.")))
            except Exception as e:
                T.banner(self, f"PAINTING FAILED — {e}")
            finally:
                self.q.put(lambda: (self.prog.stop(), self.paint_btn.state(["!disabled"])))
        threading.Thread(target=work, daemon=True).start()

    def paint_over(self):
        img = self.result or self.src
        if img is None: return T.banner(self, "NOTHING YET — paint something (or open an image) first")
        __import__("paint_window").PaintWindow(self, image=img)

    def new_engine(self):
        """scene builder: choose the landscape, then the new engine paints it"""
        import landscape
        win = tk.Toplevel(self); win.title("Paint a landscape"); win.resizable(False, False)
        v = {k: tk.StringVar(value=str(d)) for k, d in landscape.DEFAULTS.items()}
        rows = [("Light", "time", ["sunset", "night"]), ("Sun position (0 = left, 1 = right)", "sun_x", None), ("Number of peaks", "peaks", ["3", "4", "5", "6"]),
                ("Mountain height (0.2 – 1.0)", "height", None), ("Figures sitting on the rise", "figures", ["0", "1", "2"]),
                ("Rocks", "rocks", ["True", "False"]), ("Grass", "grass", ["True", "False"]), ("Canyon in front of the range", "canyon", ["True", "False"]),
                ("Caption (optional)", "caption", None)]
        for i, (lab, key, choices) in enumerate(rows):
            ttk.Label(win, text=lab).grid(row=i, column=0, sticky="w", padx=8, pady=3)
            (ttk.Combobox(win, textvariable=v[key], values=choices, state="readonly", width=22) if choices else ttk.Entry(win, textvariable=v[key], width=25)).grid(row=i, column=1, padx=8)
        def go():
            o = {}
            for k, d in landscape.DEFAULTS.items():
                s = v[k].get()
                o[k] = (s == "True") if isinstance(d, bool) else type(d)(s) if not isinstance(d, str) else s
            o["seed"] = int(self.seed.get()); win.destroy(); self._run_landscape(o)
        ttk.Button(win, text="Paint it", command=go).grid(row=len(rows), column=0, columnspan=2, pady=10)

    def _run_landscape(self, opts):
        import bench, landscape
        bench.TARGET = os.path.join(base_dir(), "styles", "summit.jpg")
        prof = learn.load(library_dir()) if self.style_var.get().startswith("My library") else None
        self.paint_btn.state(["disabled"]); self.prog.start(12); self.status.set("Painting the landscape… (about 20 seconds)")
        def work():
            try:
                out = landscape.render(opts, style=prof)
                self.result = out; self.q.put(lambda: (self.show(out, self.after_lbl), self.status.set("Done. Save it, paint over it by hand, or change the seed.")))
            except Exception as e:
                T.banner(self, f"PAINTING FAILED — {e}")
            finally:
                self.q.put(lambda: (self.prog.stop(), self.paint_btn.state(["!disabled"])))
        threading.Thread(target=work, daemon=True).start()

    def save(self):
        if self.result is None: return T.banner(self, "NOTHING TO SAVE YET — paint something first")
        p = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")])
        if p: self.result.save(p, quality=92); self.status.set(f"Saved: {os.path.basename(p)}"); T.banner(self, f"SAVED — {os.path.basename(p)}", "success")

if __name__ == "__main__":
    root = tk.Tk(); root.withdraw(); T.banner_host(root); w = App(root); w.protocol("WM_DELETE_WINDOW", root.destroy); root.mainloop()
