"""
main.py: the Painterly Image Engine's home screen.
  Image Generator: type what you want, it paints it (and tells you what it understood).
  Training Mode:   teach it (images to learn from, words, styles), and paint by hand.
"""
import os, sys, threading, queue, shutil, random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, BASE)
from PIL import Image, ImageTk
import app as classic                 # library folder, styles, the classic tools window
import learn, language, landscape, bench, paint_window

def home_dir(): return os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
bench.TARGET = os.path.join(BASE, "styles", "summit.jpg")
SETTINGS = [("time", ["sunset", "night"]), ("clouds", ["few", "normal", "many"]), ("tint", ["none", "golden", "fiery", "pink", "cool"]),
            ("figures", ["0", "1", "2"]), ("pose", ["seated", "standing"]), ("height", ["0.2", "0.5", "0.9"]), ("peaks", ["3", "4", "5", "6"]),
            ("mountains", ["True", "False"]), ("rocks", ["True", "False"]), ("grass", ["True", "False"]), ("canyon", ["True", "False"]),
            ("sun_x", ["0.25", "0.5", "0.75"])]

def _typed(key, s):
    d = landscape.DEFAULTS.get(key)
    if isinstance(d, bool): return s == "True"
    if isinstance(d, int): return int(s)
    if isinstance(d, float): return float(s)
    return s

class Home(tk.Tk):
    def __init__(self):
        super().__init__(); self.title("Painterly Image Engine"); self.geometry("760x520"); self.configure(bg="#1d1d22")
        self.q = queue.Queue(); self.after(100, self._poll)
        tk.Label(self, text="Painterly Image Engine", font=("Georgia", 26, "bold"), fg="#efe6d4", bg="#1d1d22").pack(pady=(40, 6))
        tk.Label(self, text="Paint from words, or teach it something new.", font=("Georgia", 13, "italic"), fg="#b8b0a0", bg="#1d1d22").pack(pady=(0, 30))
        row = tk.Frame(self, bg="#1d1d22"); row.pack()
        for title, sub, cmd, col in (("Image Generator", "Type what you want to see", lambda: GeneratorWindow(self), "#b3562a"),
                                     ("Training Mode", "Teach it images, words and styles", lambda: TrainingWindow(self), "#3d4f80")):
            b = tk.Button(row, text=f"{title}\n\n{sub}", font=("Georgia", 15, "bold"), fg="white", bg=col, activebackground=col,
                          width=20, height=6, relief="flat", command=cmd, wraplength=240); b.pack(side="left", padx=16)
        tk.Button(self, text="Classic tools…", command=lambda: classic.App(self), relief="flat", fg="#b8b0a0", bg="#1d1d22",
                  activebackground="#1d1d22").pack(pady=24)

    def _poll(self):
        try:
            while True: self.q.get_nowait()()
        except queue.Empty: pass
        self.after(100, self._poll)

# ---------------------------------------------------------------- Image Generator
class GeneratorWindow(tk.Toplevel):
    def __init__(self, home):
        super().__init__(home); self.home = home; self.title("Image Generator"); self.geometry("1200x820"); self.result = None; self.opts = None
        left = ttk.Frame(self, padding=12); left.pack(side="left", fill="y")
        ttk.Label(left, text="What should I paint?", font=("Georgia", 14, "bold")).pack(anchor="w")
        self.prompt = tk.Text(left, width=40, height=6, wrap="word", font=("Georgia", 12)); self.prompt.pack(fill="x", pady=4)
        self.prompt.insert("1.0", "two people sitting on a hill at sunset, tall mountains, lots of clouds")
        ttk.Label(left, text='Tips: try "night", "no rocks", "sun on the left", "a man standing", "stormy", "golden hour",\n'
                             'a caption in quotes like "The journey never ends".', foreground="#666", wraplength=360).pack(anchor="w")
        self.use_lib = tk.BooleanVar(value=False); ttk.Checkbutton(left, text="Use my learned style (Training Mode)", variable=self.use_lib).pack(anchor="w", pady=(8, 0))
        r = ttk.Frame(left); r.pack(fill="x", pady=8)
        self.gen_btn = ttk.Button(r, text="Generate", command=self.generate); self.gen_btn.pack(side="left", fill="x", expand=True, ipady=6)
        ttk.Button(r, text="New variation", command=lambda: self.generate(new_seed=True)).pack(side="left", padx=(6, 0), ipady=6)
        self.prog = ttk.Progressbar(left, mode="indeterminate"); self.prog.pack(fill="x")
        ttk.Label(left, text="What I understood:", font=("Georgia", 11, "bold")).pack(anchor="w", pady=(12, 0))
        self.und = tk.StringVar(value="—"); ttk.Label(left, textvariable=self.und, wraplength=360, foreground="#2b5b2b").pack(anchor="w")
        ttk.Label(left, text="Words I don't know yet:", font=("Georgia", 11, "bold")).pack(anchor="w", pady=(10, 0))
        self.unk = tk.StringVar(value="—"); ttk.Label(left, textvariable=self.unk, wraplength=360, foreground="#8a3b1c").pack(anchor="w")
        ttk.Button(left, text="Teach me these words…", command=self.teach_unknown).pack(anchor="w", pady=4)
        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Button(left, text="Save…", command=self.save).pack(fill="x")
        ttk.Button(left, text="Paint over it by hand", command=lambda: self.result and paint_window.PaintWindow(self, image=self.result)).pack(fill="x", pady=4)
        self.status = tk.StringVar(value="Type a request and press Generate."); ttk.Label(left, textvariable=self.status, wraplength=360, foreground="#555").pack(anchor="w", pady=6)
        self.view = ttk.Label(self); self.view.pack(side="left", expand=True)
        self.seed = random.randint(1, 9999); self.unknown = []

    def generate(self, new_seed=False):
        text = self.prompt.get("1.0", "end").strip()
        if not text: return
        if new_seed: self.seed = random.randint(1, 9999)
        opts, understood, unknown = language.understand(text, home_dir())
        opts["seed"] = self.seed; self.opts = opts; self.unknown = unknown
        self.und.set(", ".join(understood) or "nothing specific (I'll paint my default landscape)")
        self.unk.set(", ".join(unknown) or "none")
        prof = learn.load(classic.library_dir()) if self.use_lib.get() else None
        self.gen_btn.state(["disabled"]); self.prog.start(12); self.status.set("Painting… (about 20 seconds)")
        def work():
            try:
                out = landscape.render(opts, style=prof); self.result = out
                self.home.q.put(lambda: (self._show(out), self.status.set("Done. Save it, try a new variation, or change the words.")))
            except Exception as e:
                self.home.q.put(lambda: messagebox.showerror("Painting failed", str(e), parent=self))
            finally:
                self.home.q.put(lambda: (self.prog.stop(), self.gen_btn.state(["!disabled"])))
        threading.Thread(target=work, daemon=True).start()

    def _show(self, im):
        t = im.copy(); t.thumbnail((760, 780)); self.photo = ImageTk.PhotoImage(t); self.view.configure(image=self.photo)

    def teach_unknown(self):
        TeachDialog(self, self.unknown[0] if self.unknown else "")

    def save(self):
        if self.result is None: return
        p = filedialog.asksaveasfilename(parent=self, defaultextension=".png", filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")])
        if p: self.result.save(p, quality=95); self.status.set("Saved: " + os.path.basename(p))

# ---------------------------------------------------------------- teach a word
class TeachDialog(tk.Toplevel):
    def __init__(self, parent, word="", on_done=None):
        super().__init__(parent); self.title("Teach a word"); self.resizable(False, False); self.on_done = on_done
        ttk.Label(self, text="Word or phrase:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self.word = tk.StringVar(value=word); ttk.Entry(self, textvariable=self.word, width=28).grid(row=0, column=1, padx=8)
        ttk.Label(self, text="It means… (leave blank = no change)", foreground="#666").grid(row=1, column=0, columnspan=2, sticky="w", padx=8)
        self.vars = {}
        for i, (k, choices) in enumerate(SETTINGS):
            ttk.Label(self, text=k.replace("_", " ")).grid(row=i + 2, column=0, sticky="w", padx=8, pady=2)
            v = tk.StringVar(value=""); ttk.Combobox(self, textvariable=v, values=[""] + choices, state="readonly", width=12).grid(row=i + 2, column=1, sticky="w", padx=8)
            self.vars[k] = v
        ttk.Button(self, text="Teach it", command=self.save).grid(row=len(SETTINGS) + 2, column=0, columnspan=2, pady=10)

    def save(self):
        w = self.word.get().strip().lower()
        meaning = {k: _typed(k, v.get()) for k, v in self.vars.items() if v.get()}
        if not w: return
        language.teach(w, meaning, home_dir()); self.destroy()
        if self.on_done: self.on_done()

# ---------------------------------------------------------------- Training Mode
class TrainingWindow(tk.Toplevel):
    def __init__(self, home):
        super().__init__(home); self.home = home; self.title("Training Mode"); self.geometry("980x700")
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=8, pady=8)
        # --- learn from images
        t1 = ttk.Frame(nb, padding=14); nb.add(t1, text="Learn from images")
        ttk.Label(t1, text="Show it pictures of skies, mountains, rock, grass, people or whole scenes.\nIt guesses what each shows; you confirm; then press Learn.",
                  wraplength=900).pack(anchor="w")
        r = ttk.Frame(t1); r.pack(anchor="w", pady=10)
        ttk.Button(r, text="Add images to learn from…", command=self.add_images).pack(side="left")
        ttk.Button(r, text="Learn from library", command=self.learn).pack(side="left", padx=8)
        self.libinfo = tk.StringVar(); ttk.Label(t1, textvariable=self.libinfo, wraplength=900, foreground="#335").pack(anchor="w")
        self.prog = ttk.Progressbar(t1, mode="indeterminate", length=300); self.prog.pack(anchor="w", pady=6)
        # --- teach words
        t2 = ttk.Frame(nb, padding=14); nb.add(t2, text="Teach it words")
        ttk.Label(t2, text="Tell it what your words mean. It already knows about 200 painting words and phrases.", wraplength=900).pack(anchor="w")
        ttk.Button(t2, text="Teach a new word or phrase…", command=lambda: TeachDialog(self, on_done=self.refresh_words)).pack(anchor="w", pady=8)
        ttk.Label(t2, text="Words you've taught it:", font=("Georgia", 11, "bold")).pack(anchor="w")
        self.words = tk.Text(t2, height=18, width=100); self.words.pack(fill="both", expand=True)
        r2 = ttk.Frame(t2); r2.pack(anchor="w", pady=6)
        self.test = tk.StringVar(value="a golden hour sky over jagged peaks"); ttk.Entry(r2, textvariable=self.test, width=60).pack(side="left")
        ttk.Button(r2, text="Test understanding", command=self.test_words).pack(side="left", padx=6)
        self.testres = tk.StringVar(); ttk.Label(t2, textvariable=self.testres, wraplength=900, foreground="#2b5b2b").pack(anchor="w")
        # --- styles & hand painting
        t3 = ttk.Frame(nb, padding=14); nb.add(t3, text="Styles & painting")
        ttk.Button(t3, text="Add a painting as a style…", command=self.add_style).pack(anchor="w")
        ttk.Button(t3, text="Open the drawing canvas (45 brushes)", command=lambda: paint_window.PaintWindow(self)).pack(anchor="w", pady=8)
        ttk.Button(t3, text="Classic tools (repaint any image, book scenes)…", command=lambda: classic.App(self.home)).pack(anchor="w")
        self.refresh(); self.refresh_words()

    def refresh(self):
        lib = classic.library_dir(); prof = learn.load(lib)
        counts = {}
        for root, _, fs in os.walk(lib):
            sub = os.path.basename(root)
            if sub in learn.LABELS: counts[sub] = len([f for f in fs if f.lower().endswith(learn.EXT)])
        have = ", ".join(f"{k} {v}" for k, v in counts.items() if v) or "no images yet"
        learned = ", ".join(f"{k} ({v['images']})" for k, v in (prof or {}).get("subjects", {}).items()) or "nothing yet"
        self.libinfo.set(f"Library: {have}.   Learned: {learned}.")

    def add_images(self):
        ps = filedialog.askopenfilenames(parent=self, title="Choose images for it to learn from",
                                         filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.avif *.gif *.tif *.tiff"), ("All files", "*.*")])
        if not ps: return
        win = tk.Toplevel(self); win.title("What does each image show?"); win.geometry("640x520")
        ttk.Label(win, text="Check my guesses, fix any that are wrong, then press Add.", wraplength=600).pack(anchor="w", padx=10, pady=8)
        frame = ttk.Frame(win); frame.pack(fill="both", expand=True, padx=10)
        cv = tk.Canvas(frame, highlightthickness=0); sb = ttk.Scrollbar(frame, orient="vertical", command=cv.yview); inner = ttk.Frame(cv)
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all"))); cv.create_window((0, 0), window=inner, anchor="nw"); cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y"); rows = []
        for p in ps:
            try: g, conf, _ = learn.guess_label(p)
            except Exception: g, conf = "scene", "unsure"
            r = ttk.Frame(inner); r.pack(fill="x", pady=2)
            th = Image.open(p).convert("RGB"); th.thumbnail((64, 64)); ph = ImageTk.PhotoImage(th); lb = ttk.Label(r, image=ph); lb.image = ph; lb.pack(side="left")
            ttk.Label(r, text=os.path.basename(p)[:34], width=36).pack(side="left", padx=6)
            v = tk.StringVar(value=g); ttk.Combobox(r, textvariable=v, values=learn.LABELS, width=11, state="readonly").pack(side="left")
            ttk.Label(r, text=f"(guess: {conf})", foreground="#888").pack(side="left", padx=6); rows.append((p, v))
        def commit():
            for p, v in rows:
                d = os.path.join(classic.library_dir(), v.get()); os.makedirs(d, exist_ok=True); shutil.copy(p, d)
            win.destroy(); self.refresh()
        ttk.Button(win, text="Add to library", command=commit).pack(pady=8)

    def learn(self):
        self.prog.start(12)
        def work():
            try:
                learn.learn_labelled(classic.library_dir())
                sc = os.path.join(classic.library_dir(), "scene")
                if os.path.isdir(sc) and os.listdir(sc): learn.learn(sc)
            finally:
                self.home.q.put(lambda: (self.prog.stop(), self.refresh()))
        threading.Thread(target=work, daemon=True).start()

    def refresh_words(self):
        self.words.delete("1.0", "end"); tw = language.taught_words(home_dir())
        self.words.insert("1.0", "\n".join(f"{w}  →  {m}" for w, m in tw.items()) or "(none yet)")

    def test_words(self):
        o, u, k = language.understand(self.test.get(), home_dir())
        self.testres.set(f"Understood: {', '.join(u) or 'nothing'}   |   Settings: {o}   |   Unknown: {', '.join(k) or 'none'}")

    def add_style(self):
        p = filedialog.askopenfilename(parent=self, title="Choose a painting to use as a style", filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")])
        if p: shutil.copy(p, classic.user_styles_dir()); messagebox.showinfo("Style added", "Saved to my-styles. Use it from the classic tools.", parent=self)

if __name__ == "__main__":
    Home().mainloop()
