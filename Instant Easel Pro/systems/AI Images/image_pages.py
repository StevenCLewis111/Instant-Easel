"""
image_pages.py: the AI Images tab - ten sections built on one page (ImagePage), set up differently.

    Text to Image        words -> a picture (the core text model can write a fuller description first, tuned to the picture model)
    Image to Image       a picture + words -> repainted (a little ... almost new); "vary" for close variations
    Prompt to Edit       a picture + an instruction ("make it night", "remove the man", "the shirt red") -> just that changes (FLUX.2 Klein)
    Multi-Image Fusion   2-4 pictures + words ("the dog from picture 1 on the sofa from picture 2") -> one picture (FLUX.2 Klein)
    Consistent Character a saved character (1-4 pictures + a description) -> new scenes with the same face, hair and clothes (FLUX.2 Klein)
    Depth to Image       keep a picture's layout: its outlines (edge guide), a depth map (depth guide) or its layout (FLUX.2 Klein)
    Sketch to Image      a drawing -> a finished picture; follow the lines exactly (scribble guide) or keep / loosen them
    Pose to Image        pose a stick figure (presets, drag the joints) -> a person in that pose (pose guide)
    Inpainting           brush over part of a picture -> repaint just that (or remove it); sharper detail mode; extend the picture
    Image Prompting      1-4 reference pictures -> a new picture with their style and feel, their subject, or both (FLUX.2 Klein)

Every section: a STYLE (built-in: Realistic photo, Cartoon, Anime, Black & white... or your own image models from AI Training),
a SEED (same seed + words = same picture), how many, quality, and an optional upscale. A rough live preview shows while it paints.
Results: click a picture for Upscale, Vary, Edit with words, Fix part, Use as start, Use as reference, Make a character, Use this seed.
Each picture's words, seed and settings are saved inside the PNG. Every job goes in the app's one line of AI jobs (jobs.py).
"""
import os, re, json, shutil, threading, tkinter as tk
from tkinter import filedialog
import theme as T, prefs, skin, jobs, paths

QUALITY = {"Fast": 12, "Normal": 20, "Best": 30}
REMOVE_WORDS = "the surrounding background continuing naturally, seamless, nothing there"
BRUSH = {"Small": 8, "Medium": 18, "Large": 36}
UPSCALE = ["Off", "2x", "4x"]
GUIDE_STRENGTH = {"Loosely": 0.6, "Normal": 0.85, "Exactly": 1.0}
PIC_TYPES = [("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")]

class Problem(Exception):
    """something the person needs to do first (shown as a banner)"""

def _frame(parent):
    f = tk.Frame(parent, bg=parent["bg"]); T.on_change(lambda: f.configure(bg=f.master["bg"])); return f

def open_picture(p):
    from PIL import Image, ImageOps
    with Image.open(p) as im: return ImageOps.exif_transpose(im).convert("RGB")      # phone photos stand the right way up

class ListChoice(T.Choice):
    """a setting button that opens the whole list (for long lists: styles, sizes) instead of stepping through it"""
    def next(self, e=None, side=False):
        """side=True: the list opens in the space to the right of the button, its top level with the button's top"""
        m = tk.Menu(self, tearoff=0, font=T.f(10), bg=T.PALETTE["field"], fg="white", activebackground=T.PALETTE["button"])
        for c in self.choices:
            m.add_radiobutton(label=c, variable=self.var, value=c)
        side = side or getattr(self, "open_right", False)
        x, y = (self.winfo_rootx() + self.winfo_width() + 6, self.winfo_rooty()) if side else (self.winfo_rootx(), self.winfo_rooty() + self.winfo_height())
        try: m.tk_popup(x, y)
        finally: m.grab_release()

class _Pane:
    """a scrolling column (no border of its own): widgets go in .inner, lined up on the left; its scroll bar is .sb"""
    def __init__(self, master):
        self.cv = tk.Canvas(master, bd=0, highlightthickness=0, width=10, height=10)
        self.sb = T.Scrollbar(master, "vertical", command=self.cv.yview); self.cv.configure(yscrollcommand=self.sb.set)
        self.inner = tk.Frame(self.cv, bd=0, highlightthickness=0); self.win = self.cv.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.fit(), add="+"); self.cv.bind("<Configure>", lambda e: self.fit(), add="+")
        T.wheel_area(self.cv, lambda n: self.sb.can_scroll() and self.cv.yview_scroll(n, "units"))
    def fit(self):
        try:
            m = max(6, int(round(10 * T.Z)))                                         # a gap all round: nothing touches the border
            W, H = self.cv.winfo_width(), self.cv.winfo_height(); ih = self.inner.winfo_reqheight() + 2 * m
            self.cv.coords(self.win, m, m)
            self.cv.configure(scrollregion=(0, 0, max(W, self.inner.winfo_reqwidth() + 2 * m), max(ih, H)))
            if ih <= H: self.cv.yview_moveto(0)
        except tk.TclError: pass

class OptionPanel(tk.Frame):
    """the settings box beside the viewer:
        [ setting buttons, one under another | scroll bar | that setting's choices | scroll bar ]   (both lined up on the left)
    with a border line either side of the middle scroll bar and left of the right one. Clicking a setting lists its choices on the
    right; clicking a choice picks it. Each side scrolls on its own when it has more than fits."""
    def __init__(self, master):
        super().__init__(master, bd=0, highlightthickness=1); self.cap = None; self.current = None; self._job = None
        self.left, self.right = _Pane(self), _Pane(self)
        tp = max(4, int(round(8 * T.Z)))
        self.ltitle = T.Text(self, "Options", font=T.f(10, "underline")); self.ltitle.grid(row=0, column=0, pady=(tp, 0))   # titles: centred, underlined
        self.rtitle = T.Text(self, "", font=T.f(10, "underline")); self.rtitle.grid(row=0, column=4, pady=(tp, 0))
        for c, w in ((1, T.Line(self)), (3, T.Line(self)), (5, T.Line(self))): w.grid(row=0, column=c, rowspan=2, sticky="ns")
        g = T.ScrollBox.GAP                                                          # the same gap round each scroll bar as everywhere else
        for c, w in ((0, self.left.cv), (4, self.right.cv)): w.grid(row=1, column=c, sticky="nsew")
        for c, w in ((2, self.left.sb), (6, self.right.sb)): w.grid(row=0, rowspan=2, column=c, sticky="ns", padx=g, pady=g)
        self.columnconfigure(0, weight=1, uniform="op"); self.columnconfigure(4, weight=1, uniform="op"); self.rowconfigure(1, weight=1)
        self.inner = self.left.inner
        self.left.inner.bind("<Configure>", lambda e: self._soon(), add="+"); self.right.inner.bind("<Configure>", lambda e: self._soon(), add="+")
        self._style(); T.on_change(self._style)
        self.show(None)
    def _style(self):
        bg = self.master["bg"]
        try:
            self.configure(bg=bg, highlightbackground=T.PALETTE["border"], highlightcolor=T.PALETTE["border"])
            for pn in (self.left, self.right): pn.cv.configure(bg=bg); pn.inner.configure(bg=bg)
            for t in (self.ltitle, self.rtitle): t._style()                          # the titles take the box's colour
        except tk.TclError: pass
    def attach(self, choice):
        """this setting button lists its choices on the right instead of stepping through them"""
        choice.open_right = True
        if self.current is None: self.after_idle(lambda c=choice: self.current is None and self.show(c))   # the first setting's choices show to begin with
        opener = lambda e=None, c=choice: self.show(c)
        choice.bind("<Button-1>", opener); choice.bind("<Return>", opener)
        choice.var.trace_add("write", lambda *a, c=choice: self.current is c and self.after_idle(lambda: self.show(c)))
    def show(self, choice):
        self.current = choice; box = self.right.inner
        for w in box.winfo_children(): w.destroy()
        self.rtitle.configure(text=(choice.label or "Choices").title() if choice is not None else "Choices")
        if choice is None:
            T.Text(box, "Click a setting\non the left to see\nits choices here", muted=True, font=T.f(9)).pack(anchor="w"); return
        now = choice.var.get()
        for c in choice.choices:
            b = T.Button(box, ("● " if c == now else "") + str(c), lambda c=c: choice.var.set(c))
            b.pack(pady=2, anchor="w")
        self.right.cv.yview_moveto(0)
    def set_height(self, h):
        h = None if h is None else max(10, int(h))
        if h is None or self.cap is None or abs(h - self.cap) > 2: self.cap = h; self._soon()
    def _soon(self):
        if self._job is None: self._job = self.after(15, self._fit)
    def _fit(self):
        self._job = None
        try:
            ih = self.left.inner.winfo_reqheight() + 2 * max(6, int(round(10 * T.Z)))   # (the titles sit above, outside the scrolling part)
            want = ih if self.cap is None else min(ih, self.cap)
            for pn in (self.left, self.right):
                if int(float(pn.cv.cget("height"))) != want: pn.cv.configure(height=want)
            self.left.fit(); self.right.fit()
        except tk.TclError: pass

def _hide_when_empty(label):
    """a message line that takes no room while it has nothing to say (shows again, in its place, when it does)"""
    raw = label.configure
    def configure(cnf=None, **kw):
        out = raw(cnf, **kw)
        if "text" in kw or (isinstance(cnf, dict) and "text" in cnf):
            try:
                if str(label.cget("text")).strip():
                    if not label.winfo_manager():
                        sib = [w for w in label.master.pack_slaves()]
                        label.pack(anchor="w", **({"before": sib[0]} if (label is getattr(label, "_first", None) and sib) else {}))
                elif label.winfo_manager(): label.pack_forget()
            except tk.TclError: pass
        return out
    label.configure = label.config = configure
    if not str(label.cget("text")).strip(): label.pack_forget()

class _HeadTitle(T.Text):
    """a box's heading: gold, underlined, centred over it"""
    def __init__(self, master, text): super().__init__(master, text, font=T.f(10, "underline"))
    def _style(self):
        super()._style()
        try: self.configure(fg=T.PALETTE["title"])
        except tk.TclError: pass

def head_row(master):
    """a label row of fixed height (it can hold a painted button) — used on both sides so the boxes under them start level"""
    r = _frame(master); r.pack(side="top", fill="x", pady=(4, 2)); r.pack_propagate(False)
    fit = lambda: r.winfo_exists() and r.configure(height=max(18, int(round(40 * T.Z))))   # room for a painted button plus a gap under it
    fit(); T.on_change(fit, zoom=True); return r

def open_right(choice):
    """make any setting button open its whole list to its right (top lined up with the button) instead of stepping through"""
    choice.open_right = True
    opener = lambda e=None, c=choice: ListChoice.next(c, side=True)
    choice.bind("<Button-1>", opener); choice.bind("<Return>", opener)

# ---------------------------------------------------------------- picture widgets
class PicSlot(tk.Frame):
    """one picture to start from: a thumbnail with Choose / Latest (and Clear). .image is the picture (PIL) or None"""
    def __init__(self, master, label="PICTURE", on_change=None, w=150, h=112, latest=True, clear=False):
        super().__init__(master, bg=master["bg"]); T.on_change(lambda: self.configure(bg=self.master["bg"]))
        self.image = self.path = None; self.on_change = on_change; self.w, self.h = int(w * T.Z), int(h * T.Z); self._ph = None
        T.Text(self, label, font=T.f(8), muted=True).pack()
        self.box = tk.Label(self, text="no picture", bg=T.PALETTE["field"], fg=T.PALETTE["muted"], font=T.f(8), cursor="hand2")
        self.box.pack(); self.box.bind("<Button-1>", lambda e: self.choose()); self._blank()
        r = _frame(self); r.pack(pady=(2, 0))
        T.Button(r, "Choose", self.choose, width=7).pack(side="left", padx=1)
        if latest: T.Button(r, "Latest", self.latest, width=6).pack(side="left", padx=1)
        if clear: T.Button(r, "Clear", lambda: self.set(None), width=5, kind="danger").pack(side="left", padx=1)
    def _blank(self):
        self.box.configure(image="", text="click to choose", width=max(10, self.w // 8), height=max(4, self.h // 18))
    def choose(self):
        p = filedialog.askopenfilename(parent=self.winfo_toplevel(), initialdir=prefs.save_folder(), title="Choose a picture", filetypes=PIC_TYPES)
        if p: self.set(p)
    def latest(self):
        p = prefs.latest_picture()
        if not p: return T.banner(self.winfo_toplevel(), "NO PICTURES IN YOUR IMAGES FOLDER YET")
        self.set(p)
    def set(self, p):
        from PIL import ImageTk
        if p is None:
            self.image = self.path = None; self._blank()
        else:
            try: self.image = open_picture(p) if isinstance(p, str) else p.convert("RGB"); self.path = p if isinstance(p, str) else None
            except Exception as e: return T.banner(self.winfo_toplevel(), f"CAN'T OPEN THAT PICTURE — {e}")
            th = self.image.copy(); th.thumbnail((self.w, self.h)); self._ph = ImageTk.PhotoImage(th)
            self.box.configure(image=self._ph, text="", width=th.width, height=th.height)
        if self.on_change: self.on_change()

class MaskPad(tk.Canvas):
    """the picture with a brush: left-drag paints over what to change (red), right-drag rubs it out. .mask is full size, white = change.
    extend(): makes the picture bigger on chosen sides; the new strip is masked so it gets painted in (outpainting)"""
    def __init__(self, master, w=470, h=310):
        super().__init__(master, width=int(w * T.Z), height=int(h * T.Z), highlightthickness=1, cursor="crosshair", bd=0)
        self.pic = self.mask = None; self.brush = tk.StringVar(value="Medium"); self._last = None; self._style(); T.on_change(self._style)
        for ev, v in (("<Button-1>", 255), ("<B1-Motion>", 255), ("<Button-3>", 0), ("<B3-Motion>", 0)): self.bind(ev, lambda e, v=v: self._dab(e, v))
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "_last", None)); self.bind("<ButtonRelease-3>", lambda e: setattr(self, "_last", None))
        self.bind("<Configure>", lambda e: self._fit() if self.pic is not None else self._empty())     # the hint stays centred
    def _style(self): self.configure(bg=T.PALETTE["field"], highlightbackground=T.PALETTE["border"])
    def _empty(self):
        self.delete("all"); self.create_text(self.winfo_width() / 2, self.winfo_height() / 2, fill=T.PALETTE["muted"], font=T.f(10),
                                             text="CHOOSE A PICTURE, THEN BRUSH OVER WHAT TO CHANGE")
    def set_picture(self, im, mask=None):
        from PIL import Image
        self.pic = im.convert("RGB"); self.mask = mask if mask is not None else Image.new("L", im.size, 0); self._fit()
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
    def extend(self, sides, amount=0.25):
        """grow the picture on `sides` ('left', 'right', 'top', 'bottom') by amount of its size; the new parts start as a blur of the
        nearby edge and are masked (with a small overlap) so the AI paints them in"""
        from PIL import Image, ImageFilter, ImageDraw
        if self.pic is None: return
        w, h = self.pic.size; dl = int(w * amount) if "left" in sides else 0; dr = int(w * amount) if "right" in sides else 0
        dt = int(h * amount) if "top" in sides else 0; db = int(h * amount) if "bottom" in sides else 0
        if not (dl or dr or dt or db): return
        W, H = w + dl + dr, h + dt + db
        bg = self.pic.resize((W, H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(max(W, H) // 30))   # the edges' colours, softly
        bg.paste(self.pic, (dl, dt)); m = Image.new("L", (W, H), 255); ov = max(8, min(w, h) // 32)
        ImageDraw.Draw(m).rectangle((dl + (ov if dl else 0), dt + (ov if dt else 0), dl + w - 1 - (ov if dr else 0), dt + h - 1 - (ov if db else 0)), fill=0)
        from PIL import ImageChops
        old = Image.new("L", (W, H), 0); old.paste(self.mask, (dl, dt)); self.set_picture(bg, ImageChops.lighter(m, old))   # keep any brushing too

# OpenPose's 18 points and the colours its guide expects
JOINTS = ["nose", "neck", "r_shoulder", "r_elbow", "r_wrist", "l_shoulder", "l_elbow", "l_wrist", "r_hip", "r_knee", "r_ankle",
          "l_hip", "l_knee", "l_ankle", "r_eye", "l_eye", "r_ear", "l_ear"]
LIMBS = [(1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9), (9, 10), (1, 11), (11, 12), (12, 13), (1, 0), (0, 14), (14, 16), (0, 15), (15, 17)]
COLORS = [(255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0), (0, 255, 0), (0, 255, 85), (0, 255, 170),
          (0, 255, 255), (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255), (255, 0, 170), (255, 0, 85)]
def _pose(*pts): return [tuple(p) for p in pts]
POSES = {   # (x, y) from 0 to 1 in a portrait frame: nose, neck, R shoulder/elbow/wrist, L shoulder/elbow/wrist, R hip/knee/ankle, L hip/knee/ankle, eyes, ears
 "Standing": _pose((.50, .14), (.50, .22), (.40, .23), (.37, .36), (.36, .48), (.60, .23), (.63, .36), (.64, .48), (.44, .50), (.44, .69), (.44, .88),
                   (.56, .50), (.56, .69), (.56, .88), (.48, .125), (.52, .125), (.46, .14), (.54, .14)),
 "Arms up": _pose((.50, .18), (.50, .26), (.40, .27), (.34, .16), (.32, .05), (.60, .27), (.66, .16), (.68, .05), (.44, .53), (.44, .71), (.44, .89),
                  (.56, .53), (.56, .71), (.56, .89), (.48, .165), (.52, .165), (.46, .18), (.54, .18)),
 "Waving": _pose((.50, .14), (.50, .22), (.40, .23), (.37, .36), (.36, .48), (.60, .23), (.70, .17), (.72, .06), (.44, .50), (.44, .69), (.44, .88),
                 (.56, .50), (.56, .69), (.56, .88), (.48, .125), (.52, .125), (.46, .14), (.54, .14)),
 "Hands on hips": _pose((.50, .14), (.50, .22), (.40, .23), (.31, .33), (.42, .47), (.60, .23), (.69, .33), (.58, .47), (.44, .50), (.44, .69), (.44, .88),
                        (.56, .50), (.56, .69), (.56, .88), (.48, .125), (.52, .125), (.46, .14), (.54, .14)),
 "Walking": _pose((.50, .14), (.50, .22), (.40, .23), (.43, .36), (.48, .47), (.60, .23), (.57, .36), (.52, .46), (.45, .50), (.38, .68), (.33, .87),
                  (.55, .50), (.58, .69), (.64, .86), (.48, .125), (.52, .125), (.46, .14), (.54, .14)),
 "Running": _pose((.54, .15), (.52, .23), (.43, .24), (.35, .33), (.40, .42), (.61, .24), (.68, .32), (.74, .26), (.46, .50), (.32, .62), (.24, .78),
                  (.57, .50), (.66, .66), (.62, .86), (.52, .135), (.56, .135), (.50, .15), (.58, .15)),
 "Sitting": _pose((.50, .20), (.50, .28), (.40, .29), (.37, .42), (.42, .53), (.60, .29), (.63, .42), (.58, .53), (.44, .56), (.30, .58), (.30, .82),
                  (.56, .56), (.42, .58), (.42, .82), (.48, .185), (.52, .185), (.46, .20), (.54, .20)),
 "Jumping": _pose((.50, .10), (.50, .18), (.40, .19), (.31, .10), (.26, .02), (.60, .19), (.69, .10), (.74, .02), (.44, .46), (.36, .60), (.40, .74),
                  (.56, .46), (.64, .60), (.60, .74), (.48, .085), (.52, .085), (.46, .10), (.54, .10)),
 "Kneeling": _pose((.50, .24), (.50, .32), (.40, .33), (.38, .46), (.42, .57), (.60, .33), (.62, .46), (.58, .57), (.44, .60), (.40, .80), (.24, .82),
                   (.56, .60), (.62, .76), (.62, .94), (.48, .225), (.52, .225), (.46, .24), (.54, .24)),
}

class PosePad(tk.Canvas):
    """a stick figure to pose: drag a joint (left button), drag the whole figure (right button), mouse wheel to size it.
    render(w, h) draws it the way the pose guide expects (OpenPose colours on black)"""
    def __init__(self, master, w=250, h=320):
        super().__init__(master, width=int(w * T.Z), height=int(h * T.Z), highlightthickness=1, bd=0, bg="black", cursor="hand2")
        self.configure(highlightbackground=T.PALETTE["border"]); self.pts = list(POSES["Standing"]); self.drag = None; self._move = None
        self.bind("<Button-1>", self._grab); self.bind("<B1-Motion>", self._drag); self.bind("<ButtonRelease-1>", lambda e: setattr(self, "drag", None))
        self.bind("<Button-3>", lambda e: setattr(self, "_move", (e.x, e.y))); self.bind("<B3-Motion>", self._move_all)
        self.bind("<MouseWheel>", self._wheel); self.bind("<Button-4>", lambda e: self._scale(1.05)); self.bind("<Button-5>", lambda e: self._scale(0.95))
        self.bind("<Configure>", lambda e: self.draw())
    def set_pose(self, name): self.pts = list(POSES[name]); self.draw()
    def mirror(self): self.pts = [(1 - x, y) for x, y in self.pts]; s = self.pts; self.pts = [s[i] for i in (0, 1, 5, 6, 7, 2, 3, 4, 11, 12, 13, 8, 9, 10, 15, 14, 17, 16)]; self.draw()
    def _wh(self): return max(10, self.winfo_width()), max(10, self.winfo_height())
    def _grab(self, e):
        W, H = self._wh(); d = [((x * W - e.x) ** 2 + (y * H - e.y) ** 2, i) for i, (x, y) in enumerate(self.pts)]; best = min(d)
        self.drag = best[1] if best[0] < (22 * T.Z) ** 2 else None
    def _drag(self, e):
        if self.drag is None: return
        W, H = self._wh(); self.pts[self.drag] = (min(1, max(0, e.x / W)), min(1, max(0, e.y / H))); self.draw()
    def _move_all(self, e):
        if not self._move: return
        W, H = self._wh(); dx, dy = (e.x - self._move[0]) / W, (e.y - self._move[1]) / H; self._move = (e.x, e.y)
        self.pts = [(x + dx, y + dy) for x, y in self.pts]; self.draw()
    def _wheel(self, e): self._scale(1.05 if e.delta > 0 else 0.95)
    def _scale(self, k):
        cx = sum(x for x, _ in self.pts) / len(self.pts); cy = sum(y for _, y in self.pts) / len(self.pts)
        self.pts = [(cx + (x - cx) * k, cy + (y - cy) * k) for x, y in self.pts]; self.draw()
    def draw(self):
        self.delete("all"); W, H = self._wh(); lw = max(3, int(min(W, H) * 0.025))
        for i, (a, b) in enumerate(LIMBS):
            (x1, y1), (x2, y2) = self.pts[a], self.pts[b]; c = "#%02x%02x%02x" % COLORS[i]
            self.create_line(x1 * W, y1 * H, x2 * W, y2 * H, fill=c, width=lw, capstyle="round")
        r = max(4, lw)
        for i, (x, y) in enumerate(self.pts):
            c = "#%02x%02x%02x" % COLORS[i]; self.create_oval(x * W - r, y * H - r, x * W + r, y * H + r, fill=c, outline="white" if i == self.drag else c)
    def render(self, w, h):
        """the pose picture for the guide, at w x h: the figure kept at its shape, centred in the frame"""
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (w, h), "black"); d = ImageDraw.Draw(im); W, H = self._wh(); s = min(w / W, h / H); ox, oy = (w - W * s) / 2, (h - H * s) / 2
        P = [(ox + x * W * s, oy + y * H * s) for x, y in self.pts]; lw = max(4, int(min(w, h) * 0.018))
        for i, (a, b) in enumerate(LIMBS): d.line((*P[a], *P[b]), fill=COLORS[i], width=lw)
        for i, (x, y) in enumerate(P): d.ellipse((x - lw, y - lw, x + lw, y + lw), fill=COLORS[i])
        return im

# ---------------------------------------------------------------- characters (Consistent Character)
def chars_root():
    d = paths.ai("my-library", "Characters"); os.makedirs(d, exist_ok=True); return d
def char_names(): return sorted(n for n in os.listdir(chars_root()) if os.path.isfile(os.path.join(chars_root(), n, "character.json")))
def char_info(name):
    try:
        with open(os.path.join(chars_root(), name, "character.json"), encoding="utf-8") as f: return json.load(f)
    except Exception: return {}
def char_save(name, info):
    d = os.path.join(chars_root(), name); os.makedirs(d, exist_ok=True); tmp = os.path.join(d, "character.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f: json.dump(info, f, indent=1)
    os.replace(tmp, os.path.join(d, "character.json"))
def char_pictures(name):
    d = os.path.join(chars_root(), name); return sorted(os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")))[:4] if os.path.isdir(d) else []
def char_add_picture(name, src):
    pics = char_pictures(name)
    if len(pics) >= 4: os.remove(pics[0])                                      # four at most: the oldest makes room
    im = open_picture(src) if isinstance(src, str) else src.convert("RGB"); im.thumbnail((1024, 1024))
    n = 1
    while os.path.exists(os.path.join(chars_root(), name, f"look-{n}.png")): n += 1
    im.save(os.path.join(chars_root(), name, f"look-{n}.png"))

# ---------------------------------------------------------------- the picture viewer (Text to Image's right half)
class Viewer(tk.Frame):
    """the picture shown large, a progress bar on top of it while it paints, the other pictures of the run underneath, and its buttons"""
    def __init__(self, master, page):
        super().__init__(master, bg=master["bg"]); T.on_change(lambda: self.configure(bg=self.master["bg"])); self.page = page
        self.paths = []; self.current = None; self._img = None; self._ph = None; self._tph = []; self.busy = False
        self.cv = tk.Canvas(self, bd=0, highlightthickness=1, cursor="hand2")                   # packed last: the picture takes what the buttons leave
        self.cv.bind("<Configure>", lambda e: self._draw()); self.cv.bind("<Double-Button-1>", lambda e: self.current and _open_file(self.current))
        self.cv.bind("<Button-3>", lambda e: self.current and self.page._actions(e, self.current, prefs.picture_info(self.current).get("seed", "")))
        self.bar = T.ProgressBar(self.cv, width=360, height=22)
        head = head_row(self)                                                    # same height as WHAT YOU WANT's row: the two boxes' tops line up
        _HeadTitle(head, "YOUR PICTURE").place(relx=0.5, rely=1.0, anchor="s")    # centred over the box (Open / Save sit at the right)
        self._head_btns = []
        for text, fn in (("Save a copy…", lambda p: self.page.save_copy(p)), ("Open", _open_file)):   # Save at the top right, Open to its left
            b = skin.file_button(T.Button(head, text, lambda fn=fn: self.current and fn(self.current)), height=30)
            b.pack(side="right", anchor="n", padx=(6, 0)); self._head_btns.append(b)   # top of the row: a gap between them and the box below
        self.barea = T.ScrollArea(self); self.barea.pack(side="bottom", fill="x", pady=(6, 0)); self.btns = self.barea.inner; self._buttons()
        self.bind("<Configure>", lambda e: e.widget is self and self.winfo_viewable() and self.barea.set_height(self.winfo_height() * 0.4), add="+")
        self.strip = _frame(self); self.strip.pack(side="bottom", pady=(2, 0))
        self.info = T.Text(self, "", muted=True, font=T.f(8)); self.info.pack(side="bottom", pady=(3, 0))
        self.cv.pack(side="top", fill="both", expand=True); self._style(); T.on_change(self._style)
    def _style(self): self.cv.configure(bg=T.PALETTE["field"], highlightbackground=T.PALETTE["border"]); self._draw()
    def _buttons(self):
        rows = [[("Show in folder", lambda p: prefs.open_folder(os.path.dirname(p))), ("Delete", self._delete)],
                [("Upscale 2x", lambda p: self.page.upscale_pic(p, 2)), ("Upscale 4x", lambda p: self.page.upscale_pic(p, 4)),
                 ("Vary a little", lambda p: self.page.vary(p, 0.3)), ("Vary a lot", lambda p: self.page.vary(p, 0.6))],
                [("Edit with words", lambda p: send_to(self.page.app, "Prompt to Edit", p)), ("Fix a part", lambda p: send_to(self.page.app, "Inpainting", p)),
                 ("Use as start", lambda p: send_to(self.page.app, "Image to Image", p)), ("More ▸", None)]]
        self._bl = []; r = self.btns
        for row in rows:
            for text, fn in row:
                if fn is None:
                    b = T.Button(r, text, lambda: None); b.command = lambda b=b: self._more(b)
                else: b = T.Button(r, text, lambda fn=fn: self.current and fn(self.current), kind="danger" if text == "Delete" else "normal")
                if skin.file_kind(text): skin.file_button(b, height=36)                 # painted New / Open / Save button
                self._bl.append(b)
        order = self._bl[2:] + self._bl[:2]                                         # 4 across: the edits first, Show in folder / Delete last
        for c in range(4): r.columnconfigure(c, weight=1)                         # spare width shared out between the columns
        for i, b in enumerate(order): b.grid(row=i // 4, column=i % 4, padx=1, pady=2)
    def _more(self, b):
        if not self.current: return
        class E: x_root = b.winfo_rootx(); y_root = b.winfo_rooty() + b.winfo_height()
        self.page._actions(E, self.current, prefs.picture_info(self.current).get("seed", ""))
    def _delete(self, p):
        if self.page.delete_pic(p):
            self.paths = [x for x in self.paths if x != p]; self.show_results(self.paths) if self.paths else self.clear()
    def clear(self):
        self.paths = []; self.current = None; self._img = None; self._strip(); self.info.configure(text=""); self._draw()
    def show_image(self, im, rough=False):
        self._img = im.copy(); self._rough = rough; self._draw()
    def show_results(self, paths):
        self.paths = list(paths); self._strip(); self.pick(self.paths[0])
    def pick(self, p):
        from PIL import Image
        try:
            with Image.open(p) as im: self._img = im.convert("RGB"); self._img.load()
        except Exception: return
        self.current = p; self._rough = False; i = prefs.picture_info(p)
        self.info.configure(text=f"{os.path.basename(p)}   ·   {self._img.width} x {self._img.height}" + (f"   ·   SEED {i['seed']}" if i.get("seed") else "")
                            + "   ·   double-click to open, right-click for more")
        self._draw(); self._strip()
    def _strip(self):
        from PIL import Image, ImageTk
        for w in self.strip.winfo_children(): w.destroy()
        self._tph = []
        if len(self.paths) < 2: return
        for p in self.paths:
            try: im = Image.open(p); im.thumbnail((int(64 * T.Z), int(64 * T.Z))); ph = ImageTk.PhotoImage(im)
            except Exception: continue
            self._tph.append(ph); lb = tk.Label(self.strip, image=ph, bd=2, relief="solid" if p == self.current else "flat", bg=T.PALETTE["border"] if p == self.current else self["bg"], cursor="hand2")
            lb.pack(side="left", padx=3); lb.bind("<Button-1>", lambda e, p=p: self.pick(p))
    def _draw(self):
        from PIL import ImageTk
        self.cv.delete("pic", "hint"); W, H = max(10, self.cv.winfo_width()), max(10, self.cv.winfo_height())
        if self._img is None: self._placeholders(W, H)
        else:
            im = self._img.copy(); im.thumbnail((W - 8, H - 8)); self._ph = ImageTk.PhotoImage(im)
            self.cv.create_image(W / 2, H / 2, image=self._ph, tags="pic")
            if getattr(self, "_rough", False): self.cv.create_text(W / 2, H - 14, text="ROUGH PREVIEW — STILL PAINTING", fill="white", font=T.f(8), tags="hint")
        if self.busy: self.cv.coords("barwin", W / 2, 18); self.cv.tag_raise("barwin")
    def _placeholders(self, W, H):
        """grey boxes in the shape of the chosen size, one for each picture that will be made: IMAGE WILL APPEAR HERE"""
        pg = self.page
        try: w, h = pg.imaging.pixels(pg.size.get(), pg.model_key()); n = int(pg.count.get())
        except Exception: w, h, n = 1, 1, 1
        if n == 1: cols, rows = 1, 1
        elif n == 2: cols, rows = (1, 2) if w > h * 1.2 else (2, 1)                # wide pictures stack, the rest sit side by side
        else: cols, rows = 2, 2
        gap = int(10 * T.Z); pad = int(10 * T.Z)
        k = min((W - 2 * pad - gap * (cols - 1)) / (cols * w), (H - 2 * pad - gap * (rows - 1)) / (rows * h)); cw, ch = w * k, h * k
        x0 = (W - (cols * cw + gap * (cols - 1))) / 2; y0 = (H - (rows * ch + gap * (rows - 1))) / 2
        for i in range(n):
            x, y = x0 + (i % cols) * (cw + gap), y0 + (i // cols) * (ch + gap)
            self.cv.create_rectangle(x, y, x + cw, y + ch, fill="#3a3f4b", outline="#5a6070", tags="hint")
            self.cv.create_text(x + cw / 2, y + ch / 2, text="IMAGE WILL\nAPPEAR HERE" if cw < 200 * T.Z else "IMAGE WILL APPEAR HERE",
                                fill="#c9ccd6", font=T.f(10 if cw > 150 * T.Z else 8), justify="center", tags="hint")
    def progress(self, frac, text):
        """the progress bar on top of the picture"""
        self.bar.set(frac if frac else (None if frac is None else 0.0), text)
        if not self.busy:
            self.busy = True; self.cv.create_window(self.cv.winfo_width() / 2, 18, window=self.bar, tags="barwin")
    def progress_done(self):
        self.busy = False; self.cv.delete("barwin"); self._rough = False; self._draw()

# ---------------------------------------------------------------- the page
class ImagePage(tk.Frame):
    TITLE = "Text to Image"; INTRO = "Type what you want and pick a style. The core text model can write a fuller description first."
    WORDS = "WHAT YOU WANT"; WORDS_NEEDED = True
    SPLIT = False                     # a picture area on the left, the settings on the right
    MODEL = "paint"                   # "paint": the picture model chosen in Settings; "klein": FLUX.2 Klein; "guide": SD 1.5 + a guide
    SIZE = True; COUNT = True; IMPROVE = False; UPSCALE_AFTER = True; SHOW_FOLLOW = True
    AMOUNT = None; AMOUNT_LABEL = "change"; AMOUNT_DEFAULT = None
    VIEWER = False                    # the picture shown large on the right, with its buttons underneath (Text to Image)
    def __init__(self, master, app):
        super().__init__(master, bg=master["bg"]); self.app = app; T.on_change(lambda: self.configure(bg=self.master["bg"]))
        import imaging, styles; self.imaging = imaging; self.styles = styles
        self.job = None; self.stop_event = threading.Event(); self._ph = []; self._prev_ph = None; self.page_key = "AI Images/" + self.TITLE
        self._mem = prefs.get(f"image_page:{self.TITLE}") or {}; self.viewer = None
        T.Title(self, self.TITLE).pack(pady=(0, 2)); T.Text(self, self.INTRO, muted=True, font=T.f(9)).pack()
        st = _frame(self); st.pack(pady=(4, 2))
        self.status = T.Text(st, "", font=T.f(9)); self.status.pack(side="left", padx=(0, 10))
        self.dl_bar = T.ProgressBar(st, width=300)                               # a real bar while something downloads
        self.get_btn = T.Button(self if self.VIEWER else st, "Download", self.download, width=12)
        if self.SPLIT or self.VIEWER:
            split = _frame(self); split.pack(fill="both", expand=True, pady=(4, 0)); self._split = split
            if self.VIEWER:                                                          # two equal halves, whatever the window size
                split.columnconfigure(0, weight=1, uniform="half"); split.columnconfigure(1, weight=1, uniform="half"); split.rowconfigure(0, weight=1)
                self.left = _frame(split); self.left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
                self.viewer = Viewer(split, self); self.viewer.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
                host = self.left
            else:
                self.left = _frame(split); self.left.pack(side="left", anchor="n", padx=(0, 14))
                host = _frame(split); host.pack(side="left", fill="both", expand=True, anchor="n")
        else: self.left = None; host = self
        self.host = host
        if self.SPLIT: self.build_left(self.left)
        else: self.build_top(host)
        if self.VIEWER:
            self._words_label = head_row(host); _HeadTitle(self._words_label, self.WORDS).place(relx=0.5, rely=1.0, anchor="s")
        else: self._words_label = T.Text(host, self.WORDS, font=T.f(10)); self._words_label.pack(anchor="w", pady=(4, 2))
        self.prompt = T.Field(host, height=3, **({"width": 10} if self.VIEWER else {}))   # (beside the viewer it fills whatever height is left)
        self.prompt.pack(fill="both" if self.VIEWER else "x", expand=bool(self.VIEWER))
        if self._mem.get("words"): self.prompt.insert("1.0", self._mem["words"])
        self.lo_row = _frame(host); self.lo_row.pack(fill="x", pady=(4, 0))
        T.Text(self.lo_row, "LEAVE OUT", font=T.f(9)).pack(side="left", padx=(0, 8))
        self.leave_out = self.var("leave_out", imaging.NEGATIVE); T.Entry(self.lo_row, self.leave_out, width=10 if self.VIEWER else 60).pack(side="left", fill="x", expand=True)
        self.lo_note = T.Text(host, "", muted=True, font=T.f(8)); self.lo_note.configure(wraplength=480 if self.VIEWER else 1000)
        # the settings, laid out in a tidy grid (2 across beside the viewer, 3 across otherwise)
        if self.VIEWER:                                                              # beside the viewer: in a bordered area that scrolls if it must
            self.optarea = OptionPanel(host); self.optarea.pack(pady=(8, 0), fill="x"); self.optbox = self.optarea.inner
        else: self.optbox = _frame(host); self.optbox.pack(pady=(8, 0), anchor="w" if self.SPLIT else "center")
        ob = self.optbox
        self._opts = []
        def add(w, span=1): self._opts.append((w, span)); return w
        self.style = self.var("style", prefs.get("image_default_style") or "None")
        self.style_choice = add(ListChoice(ob, "style", styles.names(), self.style))
        if self.SIZE:
            self.size = self.var("size", prefs.get("image_default_size") or imaging.SIZES[0])
            if self.size.get() not in imaging.SIZES: self.size.set(imaging.SIZES[0])
            add(ListChoice(ob, "size", imaging.SIZES, self.size))
        self.count = self.var("count", "1")
        if self.COUNT: add(T.Choice(ob, "how many", ["1", "2", "4"], self.count))
        else: self.count.set("1")
        self.quality = self.var("quality", "Normal")
        if self.quality.get().split()[0] in QUALITY: self.quality.set(self.quality.get().split()[0])
        if self.quality.get() not in QUALITY: self.quality.set("Normal")
        self.quality_choice = add(T.Choice(ob, "quality", list(QUALITY), self.quality))
        self.follow = self.var("follow", "Normal")
        self.follow_choice = T.Choice(ob, "follow my words", list(imaging.GUIDANCE), self.follow)
        if self.SHOW_FOLLOW: add(self.follow_choice)
        if self.AMOUNT:
            self.amount = self.var("amount", self.AMOUNT_DEFAULT or list(self.AMOUNT)[1])
            if self.amount.get() not in self.AMOUNT: self.amount.set(self.AMOUNT_DEFAULT or list(self.AMOUNT)[1])
            add(T.Choice(ob, self.AMOUNT_LABEL, list(self.AMOUNT), self.amount))
            self.amount.trace_add("write", lambda *a: self._model_changed())        # Sketch: following the lines exactly switches to SD 1.5
        self.upscale = self.var("upscale", prefs.get("image_auto_upscale") or "Off")
        if self.UPSCALE_AFTER: add(T.Choice(ob, "upscale", UPSCALE, self.upscale))
        self.build_extra(ob)                                                         # a section's own settings (each packs into ob; moved into the grid below)
        for w in ob.winfo_children():
            if w not in [x for x, _ in self._opts] and w is not self.follow_choice: w.pack_forget(); add(w)
        seed = _frame(ob); T.Text(seed, "SEED", font=T.f(9)).pack(side="left", padx=(0, 4))
        self.seed = self.var("seed", "random")
        T.Button(seed, "Random", lambda: self.seed.set("random"), width=7).pack(side="left", padx=(0, 4))
        T.Entry(seed, self.seed, width=9).pack(side="left"); add(seed); self._seed_row = seed
        self.improve = tk.BooleanVar(value=self._mem.get("improve", prefs.get("image_improve_words") if prefs.get("image_improve_words") is not None else True))
        if self.IMPROVE:
            imp = _frame(ob); T.Text(imp, "FULLER DESCRIPTION", font=T.f(9)).pack(side="left", padx=(0, 6)); T.Toggle(imp, self.improve).pack(side="left"); add(imp); self._imp_row = imp
        self._layout_opts()
        b = _frame(host)
        if self.VIEWER:                                                              # beside the viewer: above the settings box, Paint it centred in the left half, Stop in the right
            self.gobar = b; b.columnconfigure(0, weight=1, uniform="go"); b.columnconfigure(1, weight=1, uniform="go")
        else: b.pack(pady=8, anchor="center")
        self.go_btn = skin.button(T.Button(b, "Paint it", self.go, width=14))
        jobs.guard(self.go_btn, self.page_key, app, "your picture")
        stop = T.Button(b, "Stop", self.stop, kind="danger", width=14); self.stop_btn = stop
        if self.VIEWER: self.go_btn.grid(row=0, column=0); stop.grid(row=0, column=1)
        else:
            self.go_btn.pack(side="left", padx=(0, 6)); stop.configure(width=8); stop.pack(side="left", padx=6)
            skin.file_button(T.Button(b, "Open my Images folder", lambda: prefs.open_folder(prefs.save_folder()))).pack(side="left", padx=6)
        mh = host
        if self.VIEWER: self.notes = mh = _frame(host); self.notes.pack(fill="x")    # the two message lines: take no room while they're empty
        self.msg = T.Text(mh, "", muted=True, font=T.f(9)); self.msg.pack(anchor="w" if self.VIEWER else "center")
        if self.VIEWER: self.msg.configure(wraplength=int(480 * T.Z))
        self.used = T.Text(mh, "", muted=True, font=T.f(8)); self.used.configure(wraplength=480 if (self.SPLIT or self.VIEWER) else 1000)
        self.used.pack(anchor="w" if self.VIEWER else "center")
        if self.VIEWER:
            self.msg._first = self.msg
            for lab in (self.msg, self.used): _hide_when_empty(lab)
        if self.VIEWER:                                                              # everything under the words box is placed first, from the bottom up,
            for w in (self.optarea, self.gobar, self.notes, self.lo_row):           # so the words box only gets the height that's left and nothing is cut off;
                                                                                         # the settings box last, so its bottom lines up with the picture buttons' box
                w.pack_configure(side="bottom", before=self._words_label)
            self.lo_row.pack_configure(pady=(6, 0)); self.optarea.pack_configure(fill="x", pady=0)
            self.gobar.pack_configure(fill="x", pady=(10, 10))                       # Paint it / Stop: the same gap above (to LEAVE OUT) as below (to the box)
            host.bind("<Configure>", lambda e: e.widget is host and self.after(20, self._fit_left), add="+")
            self.bind("<Configure>", lambda e: e.widget is self and self.get_btn.winfo_manager() and self.after(30, self._place_dl), add="+")
        self.run_bar = T.ProgressBar(self if not self.SPLIT else host, width=520)   # (sections without the viewer: a bar above the results while it paints)
        self.results = _frame(self if not self.SPLIT else host)
        if not self.VIEWER: self.results.pack(fill="both", expand=True, pady=(4, 0))
        self.style.trace_add("write", lambda *a: self._model_changed()); self.bind("<Map>", lambda e: e.widget is self and self.refresh(), add="+")
        if self.viewer is not None:                                                  # the picture box shows the shape and number of pictures to come
            for v in (self.size, self.count): v.trace_add("write", lambda *a: self.viewer.clear())
        self._model_changed(); self._tick()

    def _layout_opts(self):
        """put the visible settings into the grid, in order"""
        hidden = getattr(self, "_hidden_opts", set())
        for w, _ in self._opts: w.grid_forget()
        if self.VIEWER:
            # one column, lined up on the left, scrolling down: the settings in order, then the seed row and the fuller-description toggle
            tail = [w for w in (getattr(self, "_seed_row", None), getattr(self, "_imp_row", None)) if w is not None]
            i = 0
            for w in [w for w, _ in self._opts if w not in hidden and w not in tail] + tail:
                if isinstance(w, T.Choice) and not getattr(w, "open_right", False): self.optarea.attach(w)
                w.grid(row=i, column=0, pady=3, sticky="w"); i += 1
            if self.optarea.current in hidden: self.optarea.show(None)
            return
        cols = 3; i = 0
        for w, span in self._opts:
            if w in hidden: continue
            w.grid(row=i // cols, column=i % cols, sticky="w", padx=4, pady=3); i += 1

    def _place_dl(self):
        """Download at the left, halfway between the page's top border and the WHAT YOU WANT words below it"""
        try:
            lab = self._words_label.winfo_children()[0] if self._words_label.winfo_children() else self._words_label
            band = lab.winfo_rooty() - self.winfo_rooty()                            # down to the WHAT YOU WANT words below it
            if band <= 0: band = self._split.winfo_y() + int(40 * T.Z)
            self.get_btn.place(x=0, y=max(0, (band - self.get_btn.winfo_reqheight()) // 2))
        except (tk.TclError, AttributeError): self.get_btn.place(x=0, y=0)

    def _fit_left(self):
        """the settings area gets what the column has left after the words box's 3 lines; past that it scrolls"""
        try:
            H = self.host.winfo_height()
            if H < 50 or not self.host.winfo_viewable(): return
            others = self.host.winfo_reqheight() - self.prompt.winfo_reqheight() - self.optarea.winfo_reqheight()
            border = self.optarea.winfo_reqheight() - int(float(self.optarea.left.cv.cget("height")))
            room = H - others - self.prompt.winfo_reqheight() - border             # all but the words box's 3 lines
            self.optarea.set_height(max(int(40 * T.Z), min(room, int(H * 0.5))))   # at most half the column: the words box keeps a fair share
        except tk.TclError: pass

    # ---- building blocks for the sections
    def var(self, key, default): return tk.StringVar(value=self._mem.get(key, default))
    def build_top(self, host): pass
    def build_left(self, left): pass
    def build_extra(self, row): pass
    def model_key(self):
        """the picture model this request will use"""
        if self.MODEL == "klein": return "klein"
        if self.MODEL == "guide": return "sd15"
        return self.imaging.choice()
    def needs(self):
        """[(download key, what it is)] this section still needs"""
        out = []; im = self.imaging; key = self.model_key()
        if not im.engine_exe(): out.append(("engine", "the image engine"))
        if not im.have(key) and not (self.MODEL == "paint" and im.ready()):
            out.append((key if key in ("zimage", "klein", "sd15") else "sd15", im.MODELS.get(key, {}).get("label", "Stable Diffusion 1.5")))
        return out
    def request(self, words):
        """the engine settings for this section's request (raise Problem('...') if something is missing)"""
        return dict(size=self.size.get() if self.SIZE else "Square 1:1")

    def refresh(self):
        self.style_choice.choices = self.styles.names()
        if self.style.get() not in self.style_choice.choices: self.style.set("None")
    def _model_changed(self):
        """LEAVE OUT and FOLLOW MY WORDS only matter for Stable Diffusion (Z-Image and FLUX.2 ignore them): hidden for the others"""
        try: dit = self.imaging.spec(self.model_key())["dit"]
        except Exception: dit = False
        self._hidden_opts = {self.follow_choice} if dit else set()
        if self.SHOW_FOLLOW: self._layout_opts()
        if dit:
            if self.lo_row.winfo_manager(): self.lo_row.pack_forget()
            self.lo_note.configure(text=f"{self.imaging.model_label(self.model_key()) or 'This model'} follows your words as written: say what you want rather than what to leave out.")
            if not self.lo_note.winfo_manager():
                if self.VIEWER: self.lo_note.pack(side="bottom", anchor="w", after=self.notes, pady=(6, 0))   # where LEAVE OUT was
                else: self.lo_note.pack(after=self.prompt, anchor="w")
        else:
            if self.lo_note.winfo_manager(): self.lo_note.pack_forget()
            if not self.lo_row.winfo_manager():
                if self.VIEWER: self.lo_row.pack(side="bottom", after=self.notes, fill="x", pady=(6, 0))
                else: self.lo_row.pack(after=self.prompt, fill="x", pady=(4, 0))

    def _tick(self):
        if not self.winfo_exists(): return
        st = self.imaging.status(); need = self.needs()
        downloading = st["state"] == "downloading"
        if downloading:
            self.dl_bar.set(st.get("progress") or None, st["detail"].replace("Downloading ", "").split("…")[0][:40])
            if not self.dl_bar.winfo_manager(): self.dl_bar.pack(side="left", padx=(0, 10), after=self.status)
        elif self.dl_bar.winfo_manager(): self.dl_bar.pack_forget()
        if downloading: text = "DOWNLOADING " + st["detail"].split("…")[-1].strip().upper()
        elif st["state"] == "error": text = st["detail"].upper()
        elif need: text = "NEEDS: " + " AND ".join(n[1].upper() for n in need) + " — press Download"
        else:
            key = self.model_key(); text = f"READY: {self.imaging.model_label(key).upper()}"
            if self.MODEL == "paint" and self.imaging.kind(key) != key and key in ("zimage", "klein"):
                text += f"  (standing in until {self.imaging.MODELS[key]['label']} is downloaded)"
            if self.SIZE: w, h = self.imaging.pixels(self.size.get(), key); text += f"   {w} x {h}"
        self.status.configure(text=text)
        if self.job is not None and self.job.state == "waiting": self.msg.configure(text=jobs.where(self.job).upper())
        show = bool(need) and st["state"] != "downloading"
        if show and not self.get_btn.winfo_manager():
            if self.VIEWER: self._place_dl()                                         # top left, centred up and down in the band above the boxes
            else: self.get_btn.pack(side="left")
        elif not show and self.get_btn.winfo_manager(): (self.get_btn.place_forget if self.VIEWER else self.get_btn.pack_forget)()
        self.after(800, self._tick)

    def download(self):
        need = self.needs()
        if not need: return
        key = need[1][0] if need[0][0] == "engine" and len(need) > 1 else need[0][0]           # the engine comes with any model download
        q = self.app.q; size = self.imaging.download_size(key) / 1e9
        self.imaging.download(on_done=lambda ok, m: q.put(lambda: T.banner(self.app, ("DOWNLOADED — " if ok else "DOWNLOAD FAILED — ") + m, "success" if ok else "error")), key=key)
        T.banner(self.app, f"DOWNLOADING — {dict(need)[key] if key in dict(need) else key}" + (f" (about {size:.1f} GB)" if size > 0.05 else "") + "; progress is shown above", "success")

    # ---- painting
    def _seed(self):
        sd = self.seed.get().strip().lower()
        if sd not in ("", "random") and not sd.isdigit(): raise Problem("THE SEED IS A WHOLE NUMBER (or 'random')")
        return int(sd) if sd.isdigit() else None

    def _wording(self, text, key):
        """the core text model's fuller description, written the way this picture model likes (research: Z-Image and FLUX.2 want
        plain sentences that say what must be there; Stable Diffusion wants short comma tags). The request itself if it can't"""
        try:
            import brain
            if not brain.installed(): return text
            if self.imaging.spec(key)["dit"]:
                ask = ("Rewrite this picture request as a vivid description for an image model in 2 to 4 plain sentences (60 to 110 words): "
                       "the subject first, then the setting, composition, lighting and colours. Say what must be in it, not what must not. "
                       "Keep every detail the person asked for and invent nothing that changes their meaning. Reply with the description only.\n\n" + text)
            else:
                ask = ("Rewrite this request as one short picture description for Stable Diffusion: the subject first, then style, lighting and details, "
                       "as comma-separated tags, under 45 words. Reply with the tags only.\n\n" + text)
            ans = brain.ask("AI Images", ask, max_tokens=200, use_library=False)
            return ans.strip().strip('"') or text
        except Exception: return text

    def _remember(self, text):
        keep = dict(words=text, leave_out=self.leave_out.get(), count=self.count.get(), quality=self.quality.get(), follow=self.follow.get(),
                    seed=self.seed.get(), improve=bool(self.improve.get()), style=self.style.get(), upscale=self.upscale.get())
        if self.SIZE: keep["size"] = self.size.get()
        if self.AMOUNT: keep["amount"] = self.amount.get()
        keep.update(self.remember_extra()); prefs.set(f"image_page:{self.TITLE}", keep)
    def remember_extra(self): return {}

    def go(self):
        if jobs.busy(self.page_key): return
        text = self.prompt.get("1.0", "end").strip()
        try:
            if self.WORDS_NEEDED and not text and self.style.get() == "None": raise Problem(f"TYPE {self.WORDS.split(':')[0].split('(')[0].strip()} FIRST")
            need = self.needs()
            if need: raise Problem(f"THIS NEEDS {need[-1][1].upper()} — press Download (at the top) first")
            seed = self._seed(); kw = self.request(text)
        except Problem as e: return T.banner(self.app, str(e))
        self._remember(text)
        key = kw.pop("model", None) or self.model_key()
        sty = self.styles.resolve(self.style.get(), kw.pop("words", text), key, editing=kw.pop("editing", False),
                                  use_refs=kw.pop("style_refs", True), allow_switch=kw.pop("allow_switch", self.MODEL != "guide"))
        refs = (list(kw.pop("refs", []) or []) + sty["refs"])[:4]; key = sty["model"]      # your own style model may bring FLUX.2 Klein + its pictures
        negative = ", ".join(x for x in (self.leave_out.get().strip(), sty["negative"], kw.pop("negative_extra", "")) if x)
        self.stop_event.clear(); q = self.app.q
        args = dict(n=int(self.count.get()), steps=QUALITY[self.quality.get()], cfg=self.imaging.GUIDANCE[self.follow.get()], seed=seed, negative=negative,
                    stop=self.stop_event, hint=text or self.TITLE, model=key, refs=refs or None, lora=sty["lora"] or ("", None),
                    upscale=None if self.upscale.get() == "Off" else self.upscale.get() + (" art" if self.style.get() in ("Anime", "Cartoon", "Comic book", "Pixel art", "Line art / colouring page") else ""),
                    meta_extra=dict(style=self.style.get(), section=self.TITLE))
        args.update(kw); improve = self.IMPROVE and self.improve.get() and text; prompt = sty["prompt"]
        if sty["note"]: T.banner(self.app, sty["note"].upper(), "busy")
        def work(job):
            def progress(f, t): job.say(t); q.put(lambda f=f, t=t: (self.msg.configure(text=t.upper()), self._progress(f, t)))
            q.put(lambda: self._progress(None, "Starting…"))
            p = prompt
            if improve:
                job.say("Writing a fuller description…"); q.put(lambda: self._progress(None, "Writing a fuller description with the text model…")); fuller = self._wording(text, key)
                p = self.styles.resolve(self.style.get(), fuller, key, allow_switch=bool(refs))["prompt"] if fuller != text else prompt
            if args.get("upscale"):
                need = "upscale_art" if "art" in args["upscale"] else "upscale_photo"
                if not self.imaging.addon(need) and not self.imaging.addon("upscale_photo") and not self.imaging.addon("upscale_art"):
                    progress(0, "Getting the upscaler (once, about 70 MB)…"); self.imaging.ensure_addon(need)
            q.put(lambda: self.used.configure(text=f"PAINTING FROM: {p}"))
            progress(0, "Painting…")
            return self.imaging.paint(p, on_progress=progress, preview=lambda path: q.put(lambda: self._preview(path)), **args)
        def failed(e): q.put(lambda e=e: (self.msg.configure(text=""), self._progress_done(), T.banner(self.app, f"COULDN'T PAINT — {e}")))
        self.job = jobs.submit("AI Images", f"{self.TITLE}: {(text or self.style.get())[:40]}", work, kind="image", page=self.page_key, engine="image",
                               on_done=lambda saved: q.put(lambda: self._show(saved)), on_error=failed, on_cancel=self._stop_now)
        self.msg.configure(text="GETTING READY…" if self.job.place() <= 1 and not jobs.running() else jobs.where(self.job).upper())
        if self.viewer is not None: self.viewer.clear()                              # placeholders until the new pictures arrive
        self._progress(None, "Waiting its turn…" if jobs.running() else "Getting ready…")

    def _stop_now(self): self.stop_event.set(); self.imaging.stop_now()
    def stop(self):
        if self.job is not None and self.job.state in ("waiting", "running"): jobs.cancel(self.job); self.msg.configure(text="STOPPED"); self._progress_done()

    def _progress(self, frac, text):
        """the bar while it paints: over the picture (Text to Image) or above the results"""
        if self.viewer is not None: return self.viewer.progress(frac, text)
        self.run_bar.set(frac if frac else None if frac is None else 0.0, text)
        if not self.run_bar.winfo_manager(): self.run_bar.pack(before=self.results, pady=(2, 0))
    def _progress_done(self):
        if self.viewer is not None: return self.viewer.progress_done()
        if self.run_bar.winfo_manager(): self.run_bar.pack_forget()

    def _preview(self, path):
        """the rough picture of the run so far"""
        from PIL import Image, ImageTk
        try:
            with Image.open(path) as im: im = im.convert("RGB"); im.load()
        except Exception: return
        if self.viewer is not None: return self.viewer.show_image(im, rough=True)
        if self._prev_ph is None:
            for w in self.results.winfo_children(): w.destroy()
            T.Text(self.results, "PREVIEW (rough, while it paints)", font=T.f(8), muted=True).pack()
            self._prev_lbl = tk.Label(self.results, bg=self["bg"]); self._prev_lbl.pack()
        th = max(120, min(260, self.results.winfo_height() - 30)); im.thumbnail((th, th))
        self._prev_ph = ImageTk.PhotoImage(im); self._prev_lbl.configure(image=self._prev_ph)

    def _show(self, saved):
        from PIL import Image, ImageTk
        self._prev_ph = None; self._progress_done()
        if not saved: self.msg.configure(text="STOPPED"); return
        note = self.imaging.last.get("note") or ""
        self.msg.configure(text=f"DONE — {len(saved)} SAVED TO YOUR IMAGES FOLDER" + (f" ({note.upper()})" if note else ""))
        T.banner(self.app, f"PAINTED — {len(saved)} saved to your Images folder" + (f" ({note})" if note else ""), "success")
        if self.viewer is not None: return self.viewer.show_results(saved)
        for w in self.results.winfo_children(): w.destroy()
        self._ph = []; self.update_idletasks()
        th = min(220, max(110, self.results.winfo_height() - 40))
        row = _frame(self.results); row.pack()
        for p in saved:
            try: im = Image.open(p); im.thumbnail((th, th)); ph = ImageTk.PhotoImage(im)
            except Exception: continue
            seed = prefs.picture_info(p).get("seed", "")
            cell = _frame(row); cell.pack(side="left", padx=6, anchor="n")
            self._ph.append(ph); lb = tk.Label(cell, image=ph, bg=self["bg"], cursor="hand2"); lb.pack()
            lb.bind("<Button-1>", lambda e, p=p, s=seed: self._actions(e, p, s)); lb.bind("<Button-3>", lambda e, p=p, s=seed: self._actions(e, p, s))
            T.Text(cell, f"SEED {seed} · click for more" if seed else "click for more", font=T.f(8), muted=True).pack(pady=(2, 0))

    def save_copy(self, p):
        """a copy of the picture wherever you like, in the format you pick (it's already in your Images folder)"""
        dest = filedialog.asksaveasfilename(parent=self.app, initialfile=os.path.basename(p), defaultextension=".png", title="Save a copy",
                                            filetypes=[("PNG (keeps the picture's details)", "*.png"), ("JPEG", "*.jpg"), ("WebP", "*.webp")])
        if not dest: return
        try:
            from PIL import Image
            if dest.lower().endswith(".png"): shutil.copyfile(p, dest)
            else:
                with Image.open(p) as im: im.convert("RGB").save(dest, quality=95)
            T.banner(self.app, f"SAVED — {os.path.basename(dest)}", "success")
        except Exception as e: T.banner(self.app, f"COULDN'T SAVE IT — {e}")

    def delete_pic(self, p):
        if T.popup(self.app, "DELETE THIS PICTURE?", f"{os.path.basename(p)} is removed from your Images folder.", (("Delete", "danger"), ("Cancel", "normal"))) != "Delete": return False
        try: os.remove(p); T.banner(self.app, "DELETED", "success"); return True
        except Exception as e: T.banner(self.app, f"COULDN'T DELETE IT — {e}"); return False

    # ---- what to do with a result
    def _actions(self, e, p, seed):
        m = tk.Menu(self, tearoff=0, font=T.f(10), bg=T.PALETTE["field"], fg="white", activebackground=T.PALETTE["button"])
        m.add_command(label="Open the picture", command=lambda: prefs.open_folder(p) if os.path.isdir(p) else _open_file(p))
        m.add_command(label="Show in the Images folder", command=lambda: prefs.open_folder(os.path.dirname(p)))
        m.add_separator()
        m.add_command(label="Upscale 2x (bigger, sharper)", command=lambda: self.upscale_pic(p, 2))
        m.add_command(label="Upscale 4x", command=lambda: self.upscale_pic(p, 4))
        m.add_command(label="Vary a little", command=lambda: self.vary(p, 0.3))
        m.add_command(label="Vary a lot", command=lambda: self.vary(p, 0.6))
        m.add_separator()
        for title, label in (("Prompt to Edit", "Edit with words"), ("Inpainting", "Fix or remove a part"), ("Image to Image", "Use as a start picture"),
                             ("Image Prompting", "Use as a style reference"), ("Multi-Image Fusion", "Add to Multi-Image Fusion"),
                             ("Consistent Character", "Make a character from it"), ("Depth to Image", "Reuse its layout")):
            m.add_command(label=label, command=lambda t=title: send_to(self.app, t, p))
        if seed:
            m.add_separator(); m.add_command(label=f"Use this seed ({seed})", command=lambda: (self.seed.set(seed), T.banner(self.app, f"SEED {seed} SET — change the words a little and paint again", "success")))
        try: m.tk_popup(e.x_root, e.y_root)
        finally: m.grab_release()

    def upscale_pic(self, p, factor):
        q = self.app.q; art = prefs.picture_info(p).get("style") in ("Anime", "Cartoon", "Comic book", "Pixel art", "Line art / colouring page")
        def work(job):
            need = "upscale_art" if art else "upscale_photo"
            if not self.imaging.addon(need): job.say("Getting the upscaler (once)…"); self.imaging.ensure_addon(need)
            job.say(f"Upscaling {factor}x…"); return [self.imaging.upscale(p, factor, art, stop=self.stop_event)]
        self.stop_event.clear()
        self.job = jobs.submit("AI Images", f"Upscale {factor}x", work, kind="image", page=self.page_key, engine="image",
                               on_done=lambda s: q.put(lambda: self._show([x for x in s if x])), on_error=lambda e: q.put(lambda e=e: (self._progress_done(), T.banner(self.app, f"COULDN'T UPSCALE — {e}"))),
                               on_cancel=self._stop_now)
        self.msg.configure(text=f"UPSCALING {factor}X — " + jobs.where(self.job).upper()); self._progress(None, f"Upscaling {factor}x…")

    def vary(self, p, amount):
        info = prefs.picture_info(p); words = info.get("words") or self.prompt.get("1.0", "end").strip() or "the same picture"
        q = self.app.q
        try: pic = open_picture(p)
        except Exception as e: return T.banner(self.app, f"CAN'T OPEN THAT PICTURE — {e}")
        key = self.imaging.choice()
        args = dict(n=int(self.count.get()), init_image=pic, strength=amount, size=self.imaging.fit_size(pic, key=key), stop=self.stop_event, hint="variation",
                    negative=info.get("leave_out", self.imaging.NEGATIVE), meta_extra=dict(varied_from=os.path.basename(p)))
        self.stop_event.clear()
        self.job = jobs.submit("AI Images", "Vary a picture", lambda job: self.imaging.paint(words, on_progress=lambda f, t: job.say(t), **args), kind="image",
                               page=self.page_key, engine="image", on_done=lambda s: q.put(lambda: self._show(s)),
                               on_error=lambda e: q.put(lambda e=e: (self._progress_done(), T.banner(self.app, f"COULDN'T VARY IT — {e}"))), on_cancel=self._stop_now)
        self.msg.configure(text="VARYING — " + jobs.where(self.job).upper()); self._progress(None, "Varying…")

    def receive(self, path):
        """a picture sent from another section's results"""
        T.banner(self.app, "THIS SECTION DOESN'T TAKE A PICTURE")

def _open_file(p):
    import subprocess, sys
    try:
        if sys.platform == "win32": os.startfile(p)
        elif sys.platform == "darwin": subprocess.Popen(["open", p])
        else: subprocess.Popen(["xdg-open", p])
    except Exception: pass

def send_to(app, title, path):
    """open another AI Images section with this picture in it"""
    try:
        app.goto("AI Images", title); app.pages["AI Images"].pages[title].receive(path)
    except Exception as e: T.banner(app, f"COULDN'T OPEN {title.upper()} — {e}")

# ---------------------------------------------------------------- the sections
class TextPage(ImagePage):
    TITLE = "Text to Image"; IMPROVE = True; VIEWER = True
    INTRO = "Type what you want and pick a style (Realistic photo, Cartoon, Anime, Black & white... or your own models from AI Training)."
    def request(self, words): return dict(size=self.size.get())

class OnePicture(ImagePage):
    """a section that starts from one picture"""
    SPLIT = True; SIZE = False; PIC_LABEL = "START PICTURE"
    def build_left(self, left):
        self.slot = PicSlot(left, self.PIC_LABEL, w=260, h=230); self.slot.pack()
        if self._mem.get("picture") and os.path.exists(self._mem["picture"]): self.after_idle(lambda: self.slot.set(self._mem["picture"]))
    def remember_extra(self): return dict(picture=self.slot.path or "")
    def receive(self, path): self.slot.set(path)
    def picture(self):
        if self.slot.image is None: raise Problem("CHOOSE A PICTURE FIRST — the box opens in your Images folder")
        return self.slot.image

class PicturePage(OnePicture):
    TITLE = "Image to Image"; WORDS = "WHAT TO CHANGE (optional with a style)"; WORDS_NEEDED = True
    INTRO = "Repaint a picture: say what to change and how much. 'Vary a little' makes close variations of it."
    AMOUNT = {"Vary a little": 0.3, "Some": 0.5, "A lot": 0.7, "Almost new": 0.85}; AMOUNT_DEFAULT = "Some"
    def request(self, words):
        pic = self.picture(); key = self.model_key()
        return dict(init_image=pic, size=self.imaging.fit_size(pic, key=key), strength=self.AMOUNT[self.amount.get()], words=words or "the same picture", allow_switch=False)

class EditPage(OnePicture):
    TITLE = "Prompt to Edit"; MODEL = "klein"; SHOW_FOLLOW = False
    WORDS = "WHAT TO CHANGE: 'make it night', 'remove the man on the left', 'turn the car red', 'add snow'"
    INTRO = "Describe one change and only that changes; the rest stays as it was. Uses FLUX.2 Klein (Settings > AI Models > Image edits)."
    PIC_LABEL = "PICTURE TO EDIT"
    def request(self, words):
        pic = self.picture()
        return dict(refs=[pic], size=self.imaging.fit_size(pic, key="klein"), editing=True, style_refs=False,
                    words=(words + ". Keep everything else exactly the same.") if words else "")

class FusionPage(ImagePage):
    TITLE = "Multi-Image Fusion"; MODEL = "klein"; SPLIT = True; SHOW_FOLLOW = False
    WORDS = "HOW TO COMBINE THEM: 'the dog from picture 1 sitting on the sofa from picture 2'"
    INTRO = "Combine 2 to 4 pictures into one. Say which picture each thing comes from. Simple combinations work best. Uses FLUX.2 Klein."
    def build_left(self, left):
        g = _frame(left); g.pack(); self.slots = []
        for i in range(4):
            s = PicSlot(g, f"PICTURE {i + 1}", w=130, h=100, latest=False, clear=True); s.grid(row=i // 2, column=i % 2, padx=4, pady=3); self.slots.append(s)
    def receive(self, path):
        for s in self.slots:
            if s.image is None: return s.set(path)
        self.slots[-1].set(path)
    def request(self, words):
        pics = [s.image for s in self.slots if s.image is not None]
        if len(pics) < 2: raise Problem("CHOOSE AT LEAST 2 PICTURES TO COMBINE")
        return dict(refs=pics, size=self.size.get(), style_refs=False,
                    words=f"{words}. Combine the {len(pics)} reference pictures (picture 1 is the first) into one natural, seamless picture.")

class CharacterPage(ImagePage):
    TITLE = "Consistent Character"; MODEL = "klein"; SPLIT = True; SHOW_FOLLOW = False
    WORDS = "THE NEW SCENE: 'at the beach eating ice cream', 'reading in a cosy library'"
    INTRO = "Save a character once (1 to 4 pictures of them + a few words), then put them in any scene with the same face, hair and clothes."
    def build_left(self, left):
        r = _frame(left); r.pack()
        names = char_names() or ["—"]; self.char = tk.StringVar(value=self._mem.get("character") if self._mem.get("character") in names else names[0])
        self.char_choice = ListChoice(r, "character", names, self.char); self.char_choice.pack(side="left")
        r2 = _frame(left); r2.pack(pady=3)
        for text, cmd, kind in (("+ New", self.new_char, "normal"), ("Add a picture", self.add_pic, "normal"), ("Delete", self.del_char, "danger")):
            T.Button(r2, text, cmd, kind=kind, width=11).pack(side="left", padx=2)
        T.Text(left, "WHAT THEY LOOK LIKE (keeps them the same)", font=T.f(8), muted=True).pack(pady=(4, 0))
        self.desc = T.Field(left, height=3, width=34); self.desc.pack()
        self.desc.bind("<FocusOut>", lambda e: self._save_desc())
        self.thumbs = _frame(left); self.thumbs.pack(pady=4); self._tph = []
        self.char.trace_add("write", lambda *a: self._show_char()); self.after_idle(self._show_char)
    def _show_char(self):
        from PIL import Image, ImageTk
        n = self.char.get(); self.desc.delete("1.0", "end")
        if n in char_names(): self.desc.insert("1.0", char_info(n).get("description", ""))
        for w in self.thumbs.winfo_children(): w.destroy()
        self._tph = []
        for p in char_pictures(n) if n in char_names() else []:
            try: im = Image.open(p); im.thumbnail((int(70 * T.Z), int(70 * T.Z))); ph = ImageTk.PhotoImage(im)
            except Exception: continue
            self._tph.append(ph); tk.Label(self.thumbs, image=ph, bg=self["bg"]).pack(side="left", padx=2)
        if not self._tph: T.Text(self.thumbs, "no pictures yet — Add a picture (a clear one of their face and clothes)", muted=True, font=T.f(8)).pack()
    def _save_desc(self):
        n = self.char.get()
        if n in char_names(): i = char_info(n); i["description"] = self.desc.get("1.0", "end").strip(); char_save(n, i)
    def _names_changed(self, pick):
        names = char_names() or ["—"]; self.char_choice.choices = names; self.char.set(pick if pick in names else names[0])
    def new_char(self, from_picture=None):
        from tkinter import simpledialog
        name = simpledialog.askstring("New character", "Their name (e.g. Captain Mia)", parent=self.app)
        name = re.sub(r'[<>:"/\\|?*]+', "", (name or "")).strip()[:40]
        if not name: return
        if name in char_names(): return T.banner(self.app, f"THERE'S ALREADY A CHARACTER CALLED {name.upper()}")
        char_save(name, dict(name=name, description=""))
        if from_picture: char_add_picture(name, from_picture)
        self._names_changed(name); T.banner(self.app, f"MADE — {name}. " + ("Describe them below" if from_picture else "Add a picture of them next"), "success")
    def add_pic(self):
        n = self.char.get()
        if n not in char_names(): return T.banner(self.app, "MAKE A CHARACTER FIRST — press + New")
        p = filedialog.askopenfilename(parent=self.app, initialdir=prefs.save_folder(), title="A picture of them", filetypes=PIC_TYPES)
        if p: char_add_picture(n, p); self._show_char()
    def del_char(self):
        n = self.char.get()
        if n not in char_names(): return
        if T.popup(self.app, f"DELETE {n.upper()}?", "Their saved pictures and description are deleted (pictures you made with them stay).",
                   (("Delete", "danger"), ("Cancel", "normal"))) == "Delete":
            shutil.rmtree(os.path.join(chars_root(), n), ignore_errors=True); self._names_changed(None)
    def receive(self, path): self.new_char(from_picture=path)
    def remember_extra(self): self._save_desc(); return dict(character=self.char.get())
    def model_key(self): return "klein" if self.imaging.have("klein") or not self.imaging.ready() else self.imaging.choice()
    def needs(self):
        out = super().needs()
        return [n for n in out if n[0] != "klein"] if self.imaging.ready() and not self.imaging.have("klein") else out
    def request(self, words):
        n = self.char.get()
        if n not in char_names(): raise Problem("MAKE A CHARACTER FIRST — press + New, add a picture and a few words about them")
        self._save_desc(); desc = char_info(n).get("description", ""); pics = [open_picture(p) for p in char_pictures(n)]
        if self.imaging.have("klein") and pics:
            return dict(refs=pics, size=self.size.get(), style_refs=False, model="klein",
                        words=f"{words}. The person is exactly the character in the reference pictures: same face, hair, body and clothes." + (f" ({desc})" if desc else ""))
        if not desc: raise Problem("DESCRIBE THE CHARACTER (or download FLUX.2 Klein so their pictures keep them the same)")
        T.banner(self.app, "WORDS ONLY — download FLUX.2 Klein (Settings > AI Models > Image edits) so the pictures keep them the same", "busy")
        return dict(size=self.size.get(), words=f"{desc}, {words}")

class DepthPage(OnePicture):
    TITLE = "Depth to Image"; WORDS = "WHAT TO MAKE OF IT: 'a cosy log cabin at sunset', 'the same room as a spaceship'"
    INTRO = "Keep a picture's layout and shapes, and paint something new into them: its outlines, a depth map you have, or its layout (FLUX.2 Klein)."
    PIC_LABEL = "PICTURE WITH THE LAYOUT"
    METHODS = {"Its outlines": "outline", "A depth map I have": "depth", "Its layout (FLUX.2 Klein)": "klein"}
    def build_extra(self, row):
        self.method = self.var("method", "Its outlines"); T.Choice(row, "keep", list(self.METHODS), self.method).pack(side="left", padx=3)
        self.guide = self.var("guide_strength", "Normal"); T.Choice(row, "keep it", list(GUIDE_STRENGTH), self.guide).pack(side="left", padx=3)
        self.method.trace_add("write", lambda *a: self._model_changed())
    def remember_extra(self): return dict(OnePicture.remember_extra(self), method=self.method.get(), guide_strength=self.guide.get())
    def model_key(self): return "klein" if self.METHODS.get(getattr(self, "method", tk.StringVar(value="")).get()) == "klein" else "sd15"
    def needs(self):
        out = super().needs(); g = self.METHODS.get(self.method.get())
        if g in ("outline", "depth") and not self.imaging.addon(g): out.append((g, self.imaging.ADDON_FILES[g]["label"] + " (0.7 GB)"))
        return out
    def request(self, words):
        pic = self.picture(); g = self.METHODS[self.method.get()]
        if g == "klein":
            return dict(refs=[pic], size=self.imaging.fit_size(pic, key="klein"), model="klein", style_refs=False,
                        words=f"{words}. Keep the exact layout, shapes and composition of the reference picture.")
        return dict(model="sd15", size=self.imaging.fit_size(pic, long_side=768, key="sd15"), allow_switch=False, style_refs=False,
                    control=dict(image=pic, guide=g, strength=GUIDE_STRENGTH[self.guide.get()], edges=(g == "outline")))

class SketchPage(OnePicture):
    TITLE = "Sketch to Image"; WORDS = "WHAT IT IS (optional): 'a red dragon on a hill'"; WORDS_NEEDED = False
    INTRO = "Turn a drawing into a finished picture: your latest drawing, or any sketch. Follow your lines exactly, keep them, or let it go free."
    PIC_LABEL = "YOUR DRAWING"
    AMOUNT = {"Follow my lines exactly": "guide", "Keep my lines": 0.55, "Balanced": 0.7, "Free": 0.85}; AMOUNT_LABEL = "drawing"; AMOUNT_DEFAULT = "Keep my lines"
    def build_left(self, left):
        super().build_left(left); T.Button(left, "Use my latest drawing", lambda: self.slot.latest(), width=22).pack(pady=4)
    def model_key(self): return "sd15" if getattr(self, "amount", None) is not None and self.AMOUNT.get(self.amount.get()) == "guide" else self.imaging.choice()
    def needs(self):
        out = super().needs()
        if self.AMOUNT.get(self.amount.get()) == "guide" and not self.imaging.addon("scribble"): out.append(("scribble", "the scribble guide (0.7 GB)"))
        return out
    def request(self, words):
        from PIL import ImageOps
        pic = self.picture(); a = self.AMOUNT[self.amount.get()]; words = words or "a finished, detailed picture of this drawing"
        if a == "guide":                                                     # the guide wants white lines on black
            lines = ImageOps.invert(ImageOps.autocontrast(pic.convert("L"))).point(lambda v: 255 if v > 60 else 0).convert("RGB")
            return dict(model="sd15", size=self.imaging.fit_size(pic, long_side=768, key="sd15"), allow_switch=False, style_refs=False, words=words,
                        control=dict(image=lines, guide="scribble", strength=0.9))
        key = self.model_key(); return dict(init_image=pic, size=self.imaging.fit_size(pic, key=key), strength=a, words=words, allow_switch=False)

class PosePage(ImagePage):
    TITLE = "Pose to Image"; MODEL = "guide"; SPLIT = True; WORDS = "WHO AND WHERE: 'a knight in shining armour in a castle courtyard'"
    INTRO = "Pose the stick figure (pick a pose, drag the joints; right-drag moves it, the mouse wheel sizes it), then say who it is. Uses the pose guide."
    def build_left(self, left):
        self.pad = PosePad(left); self.pad.pack()
        r = _frame(left); r.pack(pady=3)
        self.pose_name = tk.StringVar(value=self._mem.get("pose", "Standing")); ListChoice(r, "pose", list(POSES), self.pose_name).pack(side="left", padx=2)
        T.Button(r, "Mirror", self.pad.mirror, width=7).pack(side="left", padx=2)
        self.pose_name.trace_add("write", lambda *a: self.pad.set_pose(self.pose_name.get()))
        if self._mem.get("pose_points") and len(self._mem["pose_points"]) == 18: self.pad.pts = [tuple(p) for p in self._mem["pose_points"]]
    def build_extra(self, row):
        self.guide = self.var("guide_strength", "Normal"); T.Choice(row, "follow the pose", list(GUIDE_STRENGTH), self.guide).pack(side="left", padx=3)
    def remember_extra(self): return dict(pose=self.pose_name.get(), pose_points=self.pad.pts, guide_strength=self.guide.get())
    def needs(self):
        out = super().needs()
        if not self.imaging.addon("pose"): out.append(("pose", "the pose guide (0.7 GB)"))
        return out
    def request(self, words):
        w, h = self.imaging.pixels(self.size.get(), "sd15")
        return dict(model="sd15", size=self.size.get(), allow_switch=False, style_refs=False, words=f"{words}, full body",
                    control=dict(image=self.pad.render(w, h), guide="pose", strength=GUIDE_STRENGTH[self.guide.get()]))

class InpaintPage(ImagePage):
    TITLE = "Inpainting"; SPLIT = True; SIZE = False; COUNT = False; WORDS = "WHAT GOES THERE (leave empty to remove it)"; WORDS_NEEDED = False
    INTRO = "Brush over part of a picture and say what goes there (or nothing, to remove it). Extend the picture to paint past its edges."
    AMOUNT = {"Blend in": 0.75, "Repaint": 0.9, "Fully new": 1.0}; AMOUNT_LABEL = "new part"; AMOUNT_DEFAULT = "Repaint"
    def build_left(self, left):
        self.pad = MaskPad(left); self.pad.pack()
        r = _frame(left); r.pack(pady=(4, 0))
        T.Button(r, "Choose a picture", self.choose, width=16).pack(side="left", padx=2)
        T.Choice(r, "brush", list(BRUSH), self.pad.brush).pack(side="left", padx=2)
        T.Button(r, "Clear brushing", lambda: self.pad.clear(), width=14).pack(side="left", padx=2)
        r2 = _frame(left); r2.pack(pady=(3, 0)); T.Text(r2, "EXTEND:", font=T.f(8)).pack(side="left", padx=(0, 4))
        for side in ("left", "right", "top", "bottom"):
            T.Button(r2, side.capitalize(), lambda s=side: self._extend([s]), width=7).pack(side="left", padx=1)
        T.Button(r2, "All", lambda: self._extend(["left", "right", "top", "bottom"]), width=5).pack(side="left", padx=1)
        T.Text(left, "Left-drag: brush over what to change.   Right-drag: rub out.", muted=True, font=T.f(8)).pack()
        self.orig = None
    def build_extra(self, row):
        self.detail = self.var("detail", "Brushed part only (sharper)")
        T.Choice(row, "detail", ["Brushed part only (sharper)", "Whole picture"], self.detail).pack(side="left", padx=3)
    def remember_extra(self): return dict(detail=self.detail.get())
    def choose(self):
        p = filedialog.askopenfilename(parent=self.app, initialdir=prefs.save_folder(), title="Choose a picture", filetypes=PIC_TYPES)
        if p: self.receive(p)
    def receive(self, path):
        try: self.orig = open_picture(path)
        except Exception as e: return T.banner(self.app, f"CAN'T OPEN THAT PICTURE — {e}")
        self.pad.set_picture(self.orig)
    def _extend(self, sides):
        if self.pad.pic is None: return T.banner(self.app, "CHOOSE A PICTURE FIRST")
        self.pad.extend(sides); self.orig = self.pad.pic.copy()
        T.banner(self.app, "EXTENDED — the new strip is marked; say what's there (or leave it empty to continue the picture) and paint", "success")
    def request(self, words):
        from PIL import Image, ImageFilter
        if self.pad.pic is None: raise Problem("CHOOSE A PICTURE FIRST")
        if not self.pad.has_mask(): raise Problem("BRUSH OVER THE PART TO CHANGE FIRST (or press an Extend button)")
        orig = self.pad.pic; key = self.model_key(); edge = max(3, int(max(orig.size) * 0.012))
        grown = self.pad.mask.filter(ImageFilter.MaxFilter(edge * 2 + 1)); soft = grown.filter(ImageFilter.GaussianBlur(edge))  # past the brushing; feathered
        extra = dict(allow_switch=False) if words else dict(words=REMOVE_WORDS, negative_extra="person, object, text, logo", allow_switch=False, style_refs=False)
        bbox = grown.getbbox()
        if self.detail.get().startswith("Brushed") and bbox and (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) < 0.45 * orig.width * orig.height:
            # research: paint just the brushed area at full size, with some surroundings for context, then put it back - far more detail
            pad = int(max(bbox[2] - bbox[0], bbox[3] - bbox[1]) * 0.35) + 32
            box = (max(0, bbox[0] - pad), max(0, bbox[1] - pad), min(orig.width, bbox[2] + pad), min(orig.height, bbox[3] + pad))
            crop, cmask, csoft = orig.crop(box), grown.crop(box), soft.crop(box)
            def finish(pic, crop=crop, csoft=csoft, box=box):
                part = Image.composite(pic.convert("RGB").resize(crop.size, Image.LANCZOS), crop, csoft); full = orig.copy(); full.paste(part, box[:2]); return full
            return dict(init_image=crop, mask=cmask, size=self.imaging.fit_size(crop, key=key), strength=self.AMOUNT[self.amount.get()], finish=finish, **extra)
        return dict(init_image=orig, mask=grown, size=self.imaging.fit_size(orig, key=key), strength=self.AMOUNT[self.amount.get()],
                    finish=lambda pic: Image.composite(pic.convert("RGB").resize(orig.size, Image.LANCZOS), orig, soft), **extra)
    def _show(self, saved):
        self._progress_done()
        if saved:                                                                # the result goes back into the pad: keep fixing it
            self.receive(saved[-1]); self.msg.configure(text="DONE — BRUSH AGAIN TO KEEP FIXING IT")
            return T.banner(self.app, "PAINTED — saved to your Images folder; it's in the brush pad to keep fixing", "success")
        super()._show(saved)

class PromptRefPage(ImagePage):
    TITLE = "Image Prompting"; MODEL = "klein"; SPLIT = True; SHOW_FOLLOW = False; WORDS = "WHAT TO PAINT (optional): 'a lighthouse on a cliff'"; WORDS_NEEDED = False
    INTRO = "Carry the style and feel (or the subject) of 1 to 4 reference pictures into a new picture. Uses FLUX.2 Klein."
    TAKE = {"Style and feel": "in the same visual style, colours, lighting and mood as the reference pictures",
            "Subject": "featuring the same subject as the reference pictures, in a new scene",
            "Both": "with the same subject and the same visual style as the reference pictures"}
    def build_left(self, left):
        g = _frame(left); g.pack(); self.slots = []
        for i in range(4):
            s = PicSlot(g, f"REFERENCE {i + 1}", w=130, h=100, latest=False, clear=True); s.grid(row=i // 2, column=i % 2, padx=4, pady=3); self.slots.append(s)
    def build_extra(self, row):
        self.take = self.var("take", "Style and feel"); T.Choice(row, "take", list(self.TAKE), self.take).pack(side="left", padx=3)
    def remember_extra(self): return dict(take=self.take.get())
    def receive(self, path):
        for s in self.slots:
            if s.image is None: return s.set(path)
        self.slots[-1].set(path)
    def request(self, words):
        pics = [s.image for s in self.slots if s.image is not None]
        if not pics: raise Problem("CHOOSE AT LEAST ONE REFERENCE PICTURE")
        what = words or "A new picture"
        return dict(refs=pics, size=self.size.get(), style_refs=False, words=f"{what}, {self.TAKE[self.take.get()]}.")

def page_classes():
    return {"Text to Image": TextPage, "Image to Image": PicturePage, "Prompt to Edit": EditPage, "Multi-Image Fusion": FusionPage,
            "Consistent Character": CharacterPage, "Depth to Image": DepthPage, "Sketch to Image": SketchPage, "Pose to Image": PosePage,
            "Inpainting": InpaintPage, "Image Prompting": PromptRefPage}
