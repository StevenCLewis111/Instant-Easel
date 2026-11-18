"""
paint_window.py: the app's drawing canvas. Paint by hand with every brush in brushes.py.
Opens as its own window from the main app ("Open drawing canvas"), or on its own: python paint_window.py
"""
import os, sys, tkinter as tk
from tkinter import ttk, filedialog, colorchooser
import numpy as np
from PIL import Image, ImageTk
sys.path.insert(0, getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))))
import brushes

GROUPS = [
    ("Traditional brushes", ["round", "flat", "bright", "filbert", "fan", "angular", "dagger", "liner (rigger)", "script", "mop", "spotter", "palette knife"]),
    ("Dry media", ["pencil", "charcoal", "pastel / chalk", "crayon", "ink pen", "calligraphy", "marker"]),
    ("Wet media", ["watercolor", "oil", "gouache", "acrylic", "airbrush", "dry brush", "sponge", "splatter"]),
    ("Special engines", ["bristle", "spray", "particle", "sketch", "hatching", "curve", "grid", "shape", "smudge / blender", "blur (filter)", "deform (push)", "clone", "glaze", "glow (dodge)", "eraser"]),
    ("Subject brushes", ["grass blades", "foliage", "stipple"]),
]
WHOLE_STROKE = {"shape", "sketch", "curve", "particle", "hatching", "grid", "grass blades"}   # drawn when the stroke ends

class PaintWindow(tk.Toplevel):
    def __init__(self, master=None, w=1400, h=950, image=None):
        super().__init__(master); self.title("Drawing canvas"); self.geometry("1500x900")
        self.cw, self.ch = w, h; self.color = (196, 92, 44); self.paper = (244, 238, 226)
        self.canvas = brushes.Canvas(w, h, paper=self.paper); self.undo_stack = []; self.points = []
        if image is not None: self.load_image(image)
        side = ttk.Frame(self, padding=8); side.pack(side="left", fill="y")
        ttk.Label(side, text="Brush", font=("Georgia", 12, "bold")).pack(anchor="w")
        lf = ttk.Frame(side); lf.pack(fill="both", expand=False)
        self.lb = tk.Listbox(lf, height=24, width=26, exportselection=False); sb = ttk.Scrollbar(lf, command=self.lb.yview); self.lb.configure(yscrollcommand=sb.set)
        self.names = []
        for g, items in GROUPS:
            self.lb.insert("end", f"— {g} —"); self.lb.itemconfig("end", fg="#888"); self.names.append(None)
            for n in items:
                if n in brushes.B: self.lb.insert("end", "   " + n); self.names.append(n)
        self.lb.pack(side="left", fill="y"); sb.pack(side="right", fill="y"); self.lb.selection_set(1); self.brush = self.names[1]
        self.lb.bind("<<ListboxSelect>>", self.pick_brush)
        ttk.Label(side, text="Size").pack(anchor="w", pady=(8, 0)); self.size = tk.IntVar(value=30)
        ttk.Scale(side, from_=2, to=200, variable=self.size, orient="horizontal").pack(fill="x")
        ttk.Label(side, text="Opacity").pack(anchor="w"); self.opacity = tk.DoubleVar(value=1.0)
        ttk.Scale(side, from_=0.05, to=1.0, variable=self.opacity, orient="horizontal").pack(fill="x")
        self.swatch = tk.Label(side, text="  Colour  ", bg="#%02x%02x%02x" % self.color, fg="white", relief="groove"); self.swatch.pack(fill="x", pady=6)
        self.swatch.bind("<Button-1>", lambda e: self.pick_color())
        for txt, cmd in (("Undo  (Ctrl+Z)", self.undo), ("New canvas", self.new), ("Paper colour…", self.pick_paper),
                         ("Open image to paint on…", self.open_image), ("Save…", self.save)):
            ttk.Button(side, text=txt, command=cmd).pack(fill="x", pady=2)
        self.info = tk.StringVar(value="Pick a brush and paint by dragging."); ttk.Label(side, textvariable=self.info, wraplength=200, foreground="#555").pack(anchor="w", pady=8)
        self.view = tk.Canvas(self, bg="#202024", highlightthickness=0); self.view.pack(side="left", fill="both", expand=True)
        self.view.bind("<ButtonPress-1>", self.down); self.view.bind("<B1-Motion>", self.drag); self.view.bind("<ButtonRelease-1>", self.up)
        self.view.bind("<Configure>", lambda e: self.refresh()); self.bind("<Control-z>", lambda e: self.undo())
        self.scale = 1.0; self.refresh()

    # ---------- display ----------
    def refresh(self):
        vw, vh = max(50, self.view.winfo_width()), max(50, self.view.winfo_height())
        self.scale = min(vw / self.cw, vh / self.ch, 1.0)
        img = self.canvas.image().resize((int(self.cw * self.scale), int(self.ch * self.scale)), Image.BILINEAR)
        self.photo = ImageTk.PhotoImage(img); self.view.delete("all"); self.view.create_image(0, 0, image=self.photo, anchor="nw")

    def to_canvas(self, e): return (e.x / self.scale, e.y / self.scale, 1.0)

    # ---------- painting ----------
    def down(self, e):
        self.undo_stack.append(self.canvas.a.copy()); self.undo_stack = self.undo_stack[-25:]
        self.points = [self.to_canvas(e)]
        if self.brush not in WHOLE_STROKE: self.canvas.stroke(self.points * 2, self.brush, self.color, self.size.get(), self.opacity.get()); self.refresh()

    def drag(self, e):
        p = self.to_canvas(e)
        if self.points and abs(p[0] - self.points[-1][0]) + abs(p[1] - self.points[-1][1]) < 2: return
        self.points.append(p)
        if self.brush in WHOLE_STROKE:
            self.view.create_line(self.points[-2][0] * self.scale, self.points[-2][1] * self.scale, p[0] * self.scale, p[1] * self.scale, fill="#888")
        else:
            self.canvas.stroke(self.points[-2:], self.brush, self.color, self.size.get(), self.opacity.get()); self.refresh()

    def up(self, e):
        if self.brush in WHOLE_STROKE and len(self.points) > 1:
            self.canvas.stroke(self.points, self.brush, self.color, self.size.get(), self.opacity.get())
        self.points = []; self.refresh()

    # ---------- controls ----------
    def pick_brush(self, e=None):
        sel = self.lb.curselection()
        if sel and self.names[sel[0]]: self.brush = self.names[sel[0]]; self.info.set(f"Brush: {self.brush}")

    def pick_color(self):
        c = colorchooser.askcolor(color="#%02x%02x%02x" % self.color, parent=self)
        if c and c[0]: self.color = tuple(int(v) for v in c[0]); self.swatch.configure(bg=c[1])

    def pick_paper(self):
        c = colorchooser.askcolor(color="#%02x%02x%02x" % self.paper, parent=self)
        if c and c[0]: self.paper = tuple(int(v) for v in c[0]); self.new()

    def undo(self):
        if self.undo_stack: self.canvas.a = self.undo_stack.pop(); self.refresh()

    def new(self):
        self.undo_stack.append(self.canvas.a.copy()); self.canvas = brushes.Canvas(self.cw, self.ch, paper=self.paper); self.refresh()

    def load_image(self, img):
        img = img.convert("RGB"); self.cw, self.ch = img.size
        self.canvas = brushes.Canvas(self.cw, self.ch, paper=self.paper); self.canvas.a = np.asarray(img, dtype=np.float32).copy()

    def open_image(self):
        import prefs; p = filedialog.askopenfilename(parent=self, initialdir=prefs.save_folder(), filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.avif *.gif *.tif *.tiff"), ("All files", "*.*")])
        if p: self.undo_stack.append(self.canvas.a.copy()); self.load_image(Image.open(p)); self.refresh()

    def save(self):
        p = filedialog.asksaveasfilename(parent=self, defaultextension=".png", filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")])
        if p: self.canvas.image().save(p, quality=95); self.info.set("Saved: " + os.path.basename(p))

if __name__ == "__main__":
    root = tk.Tk(); root.withdraw(); w = PaintWindow(root); w.protocol("WM_DELETE_WINDOW", root.destroy); root.mainloop()
