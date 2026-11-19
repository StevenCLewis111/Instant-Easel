"""
studio_extras.py: the Draw studio's select / crop / text tools (mixed into DrawStudio).

  Select (M) and Select oval: drag a box or oval; marching ants show it. Drag inside it to move what's in it (lifted off the layer
      and floating until you click outside, change tool or press Enter). Delete clears it, Ctrl+C copies, Ctrl+X cuts, Ctrl+V pastes
      (floating, ready to move), Ctrl+A selects everything, Esc drops the selection.
  Crop (C): drag the box to keep (outside goes dark); drag inside it to move it, drag a corner to resize it. Enter or a double-click
      crops every layer to it; Esc cancels. Ctrl+Z undoes a crop.
  Text (T): click where the text goes: a box with a blinking cursor appears and the TEXT panel (under Layers) takes your typing.
      Font, size, bold, italic, underline, alignment and colour change it live on the canvas. Drag inside the box to move it, the
      right-edge handle to set how wide it wraps, the corner handle to make the letters bigger or smaller. It is painted onto the
      layer when you click somewhere else, press Place, or change tool (Esc throws it away).
"""
import os, math, sys, tkinter as tk
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFont
import theme as T, paths

SEL_TOOLS = ("sel_rect", "sel_oval")
HANDLE = 7                                                                   # handle size on screen (pixels)

# ---------------------------------------------------------------- fonts: the app's own, plus common ones the PC has
def _font_dirs():
    out = [os.path.join(paths.APP, "fonts")]
    if sys.platform.startswith("win"): out.append(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    elif sys.platform == "darwin": out += ["/Library/Fonts", "/System/Library/Fonts", "/System/Library/Fonts/Supplemental"]
    else: out += ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation", "/usr/share/fonts/truetype"]
    return out

FONT_FILES = [   # name: regular, bold, italic, bold italic
    ("Arial", "arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"),
    ("Times New Roman", "times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf"),
    ("Georgia", "georgia.ttf", "georgiab.ttf", "georgiai.ttf", "georgiaz.ttf"),
    ("Verdana", "verdana.ttf", "verdanab.ttf", "verdanai.ttf", "verdanaz.ttf"),
    ("Segoe UI", "segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf"),
    ("Comic Sans MS", "comic.ttf", "comicbd.ttf", "comici.ttf", "comicz.ttf"),
    ("Impact", "impact.ttf", None, None, None),
    ("Courier New", "cour.ttf", "courbd.ttf", "couri.ttf", "courbi.ttf"),
    ("Courier Prime", "CourierPrime-Regular.ttf", "CourierPrime-Bold.ttf", None, None),
    ("EB Garamond", "EBGaramond-Regular.ttf", "EBGaramond-SemiBold.ttf", "EBGaramond-Italic.ttf", None),
    ("DejaVu Sans", "DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique.ttf"),
    ("DejaVu Serif", "DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf", "DejaVuSerif-Italic.ttf", "DejaVuSerif-BoldItalic.ttf"),
]
_found = None
def fonts():
    """{name: [regular, bold, italic, bold italic] paths (None where missing)} for the fonts this PC has"""
    global _found
    if _found is None:
        _found = {}; dirs = _font_dirs()
        def find(fn):
            if not fn: return None
            for d in dirs:
                for cand in (fn, fn.lower()):
                    p = os.path.join(d, cand)
                    if os.path.exists(p): return p
            return None
        for name, *files in FONT_FILES:
            got = [find(f) for f in files]
            if got[0]: _found[name] = got
    return _found

_fcache = {}
def load_font(name, size, bold=False, italic=False):
    """(font, fake_bold, fake_italic): the real bold / italic file when the PC has one, else drawn heavier / slanted"""
    files = fonts().get(name) or next(iter(fonts().values()), None)
    want = (1 if bold else 0) + (2 if italic else 0)
    path = None; fb, fi = bold, italic
    if files:
        if files[want]: path, fb, fi = files[want], False, False
        elif bold and italic and files[1]: path, fb = files[1], False
        elif bold and italic and files[2]: path, fi = files[2], False
        else: path = files[0]
    key = (path, size)
    if key not in _fcache:
        try: _fcache[key] = ImageFont.truetype(path, size) if path else ImageFont.load_default()
        except Exception: _fcache[key] = ImageFont.load_default()
    return _fcache[key], fb, fi

def wrap_lines(text, font, width):
    """the text as lines, wrapped at width pixels (None: only at line breaks)"""
    out = []
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    for para in text.split("\n"):
        if width is None or not para: out.append(para); continue
        line = ""
        for word in para.split(" "):
            t = word if not line else line + " " + word
            if d.textlength(t, font=font) <= width or not line: line = t
            else: out.append(line); line = word
        out.append(line)
    return out

def render_text(text, name, size, bold, italic, underline, align, width):
    """the text as a coverage mask (L image) in picture pixels, and where each line ends (for the cursor)"""
    font, fb, fi = load_font(name, max(4, int(size)), bold, italic)
    lines = wrap_lines(text, font, width) or [""]
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    asc, desc = font.getmetrics() if hasattr(font, "getmetrics") else (size, size // 4)
    lh = int((asc + desc) * 1.15); stroke = max(1, int(size / 28)) if fb else 0
    widths = [d.textlength(l, font=font) for l in lines]
    W = int(max(width or 0, max(widths) if widths else 0, size * 0.6)) + 2 * stroke + int(size * 0.35 if fi else 0) + 4
    H = lh * len(lines) + 2 * stroke + 4
    m = Image.new("L", (W, H), 0); dr = ImageDraw.Draw(m); ends = []
    for i, (l, lw) in enumerate(zip(lines, widths)):
        box_w = width or max(widths)
        x = {"Left": 0, "Center": (box_w - lw) / 2, "Right": box_w - lw}.get(align, 0) + stroke + 2
        y = i * lh + stroke + 2
        dr.text((x, y), l, font=font, fill=255, stroke_width=stroke, stroke_fill=255)
        if underline and l:
            uy = y + asc + max(1, size // 14); dr.line((x, uy, x + lw, uy), fill=255, width=max(1, size // 16))
        ends.append((x + lw, y, lh))
    if fi:                                                                    # slant: the top moves right
        k = 0.22; m = m.transform((W, H), Image.AFFINE, (1, k, -k * H, 0, 1, 0), Image.BICUBIC)
        ends = [(ex + k * (H - (ey + lh * 0.5)), ey, lh) for ex, ey, lh in ends]
    return m, ends


class StudioExtras:
    """methods mixed into DrawStudio. It keeps: self.sel (selection), self._crop (crop box), self.txt (text being placed)"""

    # ------------------------------------------------------------------ shared plumbing
    def _x_init(self):
        if getattr(self, "_x_ready", False): return
        self._x_ready = True; self.sel = None; self._crop = None; self.txt = None; self._clip = None
        self._x_drag = None; self._ants = 0; self._blink = True; self._x_job = None
        self._x_tick()

    def _x_tick(self):
        """marching ants and the blinking text cursor"""
        try:
            if not self.winfo_exists(): return
        except tk.TclError: return
        self._ants = (self._ants + 2) % 12; self._blink = not self._blink
        if self.sel is not None or self.txt is not None: self._x_overlay()
        self._x_job = self.after(450, self._x_tick)

    def _x_scr(self, x, y):
        ox, oy, z = self._geom(); return ox + x * z, oy + y * z

    def _x_leaving(self, new_tool):
        """the tool is changing: finish what the old tool had going"""
        self._x_init()
        if self.tool in SEL_TOOLS and new_tool not in SEL_TOOLS: self._sel_commit(); self.sel = None
        if self.tool == "crop" and new_tool != "crop": self._crop = None
        if self.tool == "text" and new_tool != "text": self._txt_commit()
        self._x_overlay()

    def _x_overlay(self):
        """draw the ants / crop shade / text box on top of the picture (called after every redraw)"""
        cv = getattr(self, "cv", None)
        if cv is None: return
        try: cv.delete("xov")
        except tk.TclError: return
        if self.zoom is None: return
        if self.sel is not None: self._sel_draw(cv)
        if self._crop is not None and self.tool == "crop": self._crop_draw(cv)
        if self.txt is not None: self._txt_draw(cv)

    def x_key(self, e):
        """keys on the canvas for these tools; returns "break" when used"""
        self._x_init(); k = e.keysym; ctrl = bool(e.state & 0x4)
        if self.tool == "crop" and self._crop is not None:
            if k == "Return": self._crop_apply(); return "break"
            if k == "Escape": self._crop = None; self._x_overlay(); return "break"
        if self.tool in SEL_TOOLS or self.sel is not None:
            if ctrl and k.lower() == "a": self._sel_all(); return "break"
            if ctrl and k.lower() == "c": self._sel_copy(); return "break"
            if ctrl and k.lower() == "x": self._sel_copy(); self._sel_delete(); return "break"
            if ctrl and k.lower() == "v": self._sel_paste(); return "break"
            if k in ("Delete", "BackSpace") and self.sel is not None: self._sel_delete(); return "break"
            if k == "Return" and self.sel is not None: self._sel_commit(); self._x_overlay(); return "break"
            if k == "Escape" and self.sel is not None: self._sel_commit(); self.sel = None; self._x_overlay(); return "break"
        if self.tool == "text" and self.txt is not None and k == "Escape": self._txt_cancel(); return "break"
        return None

    def x_down(self, e, p):
        self._x_init()
        if self.tool in SEL_TOOLS: return self._sel_down(e, p)
        if self.tool == "crop": return self._crop_down(e, p)
        if self.tool == "text": return self._txt_down(e, p)

    def x_drag(self, e, p):
        if self._x_drag is None: return
        kind = self._x_drag[0]
        if kind.startswith("sel"): self._sel_drag(p)
        elif kind.startswith("crop"): self._crop_drag(p)
        elif kind.startswith("txt"): self._txt_drag(p)

    def x_up(self, e, p):
        if self._x_drag is None: return
        kind = self._x_drag[0]
        if kind == "sel_new":
            x0, y0 = self._x_drag[1]; x1, y1 = p[0], p[1]
            box = self._clip_box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            self.sel = None if box is None or box[2] - box[0] < 2 or box[3] - box[1] < 2 else dict(kind="oval" if self.tool == "sel_oval" else "rect", box=box, float=None)
        elif kind == "crop_new" and self._crop is not None and (self._crop[2] - self._crop[0] < 3 or self._crop[3] - self._crop[1] < 3): self._crop = None
        self._x_drag = None; self._x_overlay()

    def _clip_box(self, x0, y0, x1, y1):
        w, h = self.size_wh; x0, y0, x1, y1 = max(0, int(x0)), max(0, int(y0)), min(w, int(math.ceil(x1))), min(h, int(math.ceil(y1)))
        return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None

    # ------------------------------------------------------------------ selection
    def _sel_mask(self, kind, bw, bh):
        if kind == "rect": return np.ones((bh, bw), np.float32)
        yy, xx = np.mgrid[0:bh, 0:bw]; cx, cy = (bw - 1) / 2, (bh - 1) / 2
        d = ((xx - cx) / max(1, bw / 2)) ** 2 + ((yy - cy) / max(1, bh / 2)) ** 2
        return np.clip((1 - d) * max(bw, bh) / 2 + 0.5, 0, 1).astype(np.float32)      # soft 1-pixel edge

    def _sel_inside(self, p):
        if self.sel is None: return False
        x0, y0, x1, y1 = self._sel_box_now()
        return x0 <= p[0] <= x1 and y0 <= p[1] <= y1

    def _sel_box_now(self):
        s = self.sel; x0, y0, x1, y1 = s["box"]
        if s["float"] is not None: dx, dy = s["float"]["off"]; return (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        return s["box"]

    def _sel_down(self, e, p):
        if self.sel is not None and self._sel_inside(p):                         # move what's selected
            if self.sel["float"] is None: self._sel_lift()
            self._x_drag = ("sel_move", (p[0], p[1]), tuple(self.sel["float"]["off"])); return
        self._sel_commit(); self.sel = None
        self._x_drag = ("sel_new", (p[0], p[1])); self._x_overlay()

    def _sel_drag(self, p):
        kind = self._x_drag[0]
        if kind == "sel_new":
            x0, y0 = self._x_drag[1]; self.cv.delete("xov")
            X0, Y0 = self._x_scr(x0, y0); X1, Y1 = self._x_scr(p[0], p[1])
            f = self.cv.create_oval if self.tool == "sel_oval" else self.cv.create_rectangle
            f(X0, Y0, X1, Y1, outline="black", dash=(4, 4), tags="xov"); f(X0, Y0, X1, Y1, outline="white", dash=(4, 4), dashoffset=4, tags="xov")
        elif kind == "sel_move":
            sx, sy = self._x_drag[1]; ox, oy = self._x_drag[2]
            self._sel_place(int(round(ox + p[0] - sx)), int(round(oy + p[1] - sy)))

    def _sel_lift(self):
        """take what's selected off the layer: it floats until it's put down"""
        s = self.sel; x0, y0, x1, y1 = s["box"]; L = self.cur.cv; sl = (slice(y0, y1), slice(x0, x1))
        m = self._sel_mask(s["kind"], x1 - x0, y1 - y0)
        self._begin_edit()
        fa, fal = L.a[sl].copy(), L.alpha[sl] * m
        L.alpha[sl] = L.alpha[sl] * (1 - m)
        s["float"] = dict(a=fa, alpha=fal, off=[0, 0], base_a=L.a.copy(), base_al=L.alpha.copy(), shown=None)
        self._sel_place(0, 0)

    def _sel_place(self, dx, dy):
        """show the floating part at offset (dx, dy): the layer as it was after lifting, with the part on top"""
        f = self.sel["float"]; L = self.cur.cv; w, h = self.size_wh
        old = f["shown"]
        if old is not None:                                                     # put back what was under it last time
            ox0, oy0, ox1, oy1 = old; sl = (slice(oy0, oy1), slice(ox0, ox1)); L.a[sl] = f["base_a"][sl]; L.alpha[sl] = f["base_al"][sl]
        x0, y0, x1, y1 = self.sel["box"]; bw, bh = x1 - x0, y1 - y0
        X0, Y0 = x0 + dx, y0 + dy; cx0, cy0, cx1, cy1 = max(0, X0), max(0, Y0), min(w, X0 + bw), min(h, Y0 + bh)
        f["off"] = [dx, dy]; f["shown"] = (cx0, cy0, cx1, cy1) if cx1 > cx0 and cy1 > cy0 else None
        if f["shown"] is not None:
            sl = (slice(cy0, cy1), slice(cx0, cx1)); src = (slice(cy0 - Y0, cy1 - Y0), slice(cx0 - X0, cx1 - X0))
            ta, tal = f["a"][src], f["alpha"][src]; ba, bal = L.a[sl], L.alpha[sl]
            out_al = tal + bal * (1 - tal)
            L.a[sl] = np.where(out_al[..., None] > 0, (ta * tal[..., None] + ba * (bal * (1 - tal))[..., None]) / np.maximum(out_al, 1e-6)[..., None], ba)
            L.alpha[sl] = out_al
        r = [old, f["shown"]]; r = [q for q in r if q]
        if r: self._recomp((min(q[0] for q in r), min(q[1] for q in r), max(q[2] for q in r), max(q[3] for q in r)))
        self._draw()

    def _sel_commit(self):
        """put the floating part down where it is (one Undo step for the whole move)"""
        s = self.sel
        if s is None or s["float"] is None: return
        dx, dy = s["float"]["off"]; x0, y0, x1, y1 = s["box"]; s["float"] = None
        s["box"] = self._clip_box(x0 + dx, y0 + dy, x1 + dx, y1 + dy) or s["box"]
        self._dirty = None; r = self._commit_edit()
        if r: self._recomp(r)
        self._draw()

    def _sel_delete(self):
        s = self.sel
        if s is None: return
        if s["float"] is not None:                                              # a floating part: just drop it (its hole is already there)
            f = s["float"]; L = self.cur.cv; L.a[:] = f["base_a"]; L.alpha[:] = f["base_al"]; s["float"] = None
            self._dirty = None; r = self._commit_edit(); self._recomp(); self._draw(); return
        x0, y0, x1, y1 = s["box"]; sl = (slice(y0, y1), slice(x0, x1)); m = self._sel_mask(s["kind"], x1 - x0, y1 - y0)
        self._begin_edit(); L = self.cur.cv; L.alpha[sl] = L.alpha[sl] * (1 - m)
        self._dirty = None; r = self._commit_edit()
        if r: self._recomp(r)
        self._draw()

    def _sel_copy(self):
        s = self.sel
        if s is None: return
        if s["float"] is not None: f = s["float"]; self._clip = dict(a=f["a"].copy(), alpha=f["alpha"].copy(), box=self._sel_box_now(), kind=s["kind"]); return
        x0, y0, x1, y1 = s["box"]; sl = (slice(y0, y1), slice(x0, x1)); L = self.cur.cv
        self._clip = dict(a=L.a[sl].copy(), alpha=L.alpha[sl] * self._sel_mask(s["kind"], x1 - x0, y1 - y0), box=s["box"], kind=s["kind"])
        T.banner(self.app, "COPIED — Ctrl+V pastes it", "success")

    def _sel_paste(self):
        c = self._clip
        if c is None: return
        self._sel_commit()
        if self.tool not in SEL_TOOLS: self.set_tool("sel_rect")
        w, h = self.size_wh; ch, cw = c["alpha"].shape; x0 = min(max(0, c["box"][0]), max(0, w - cw)); y0 = min(max(0, c["box"][1]), max(0, h - ch))
        self._begin_edit(); L = self.cur.cv
        self.sel = dict(kind=c["kind"], box=(x0, y0, x0 + cw, y0 + ch),
                        float=dict(a=c["a"].copy(), alpha=c["alpha"].copy(), off=[0, 0], base_a=L.a.copy(), base_al=L.alpha.copy(), shown=None))
        self._sel_place(0, 0)

    def _sel_all(self):
        self._sel_commit(); w, h = self.size_wh
        if self.tool not in SEL_TOOLS: self.set_tool("sel_rect")
        self.sel = dict(kind="rect", box=(0, 0, w, h), float=None); self._x_overlay()

    def _sel_draw(self, cv):
        x0, y0, x1, y1 = self._sel_box_now(); X0, Y0 = self._x_scr(x0, y0); X1, Y1 = self._x_scr(x1, y1)
        f = cv.create_oval if self.sel["kind"] == "oval" else cv.create_rectangle
        f(X0, Y0, X1, Y1, outline="black", dash=(6, 6), dashoffset=self._ants, tags="xov")
        f(X0, Y0, X1, Y1, outline="white", dash=(6, 6), dashoffset=self._ants + 6, tags="xov")

    # ------------------------------------------------------------------ crop
    def _crop_hit(self, p):
        """which part of the crop box is under the point: a corner ("nw" ...), "in", or None"""
        if self._crop is None: return None
        x0, y0, x1, y1 = self._crop; r = HANDLE * 1.6 / max(self.zoom, 1e-3)
        for name, (cx, cy) in (("nw", (x0, y0)), ("ne", (x1, y0)), ("sw", (x0, y1)), ("se", (x1, y1))):
            if abs(p[0] - cx) <= r and abs(p[1] - cy) <= r: return name
        return "in" if x0 <= p[0] <= x1 and y0 <= p[1] <= y1 else None

    def _crop_down(self, e, p):
        hit = self._crop_hit(p)
        if hit: self._x_drag = ("crop_" + hit, (p[0], p[1]), self._crop); return
        self._crop = None; self._x_drag = ("crop_new", (p[0], p[1]))

    def _crop_drag(self, p):
        kind = self._x_drag[0]; sx, sy = self._x_drag[1]; w, h = self.size_wh
        if kind == "crop_new": b = (min(sx, p[0]), min(sy, p[1]), max(sx, p[0]), max(sy, p[1]))
        else:
            x0, y0, x1, y1 = self._x_drag[2]; dx, dy = p[0] - sx, p[1] - sy
            if kind == "crop_in":
                dx = min(max(dx, -x0), w - x1); dy = min(max(dy, -y0), h - y1); b = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
            else:
                if "w" in kind: x0 += dx
                if "e" in kind: x1 += dx
                if "n" in kind: y0 += dy
                if "s" in kind: y1 += dy
                b = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        self._crop = (max(0, b[0]), max(0, b[1]), min(w, b[2]), min(h, b[3])); self._x_overlay()

    def _crop_draw(self, cv):
        x0, y0, x1, y1 = self._crop; w, h = self.size_wh
        X0, Y0 = self._x_scr(x0, y0); X1, Y1 = self._x_scr(x1, y1); A0, B0 = self._x_scr(0, 0); A1, B1 = self._x_scr(w, h)
        for r in ((A0, B0, A1, Y0), (A0, Y1, A1, B1), (A0, Y0, X0, Y1), (X1, Y0, A1, Y1)):   # the part that goes: darkened
            cv.create_rectangle(*r, fill="black", stipple="gray50", outline="", tags="xov")
        cv.create_rectangle(X0, Y0, X1, Y1, outline="white", width=2, tags="xov")
        for cx, cy in ((X0, Y0), (X1, Y0), (X0, Y1), (X1, Y1)):
            cv.create_rectangle(cx - HANDLE, cy - HANDLE, cx + HANDLE, cy + HANDLE, fill="white", outline="black", tags="xov")
        cv.create_text((X0 + X1) / 2, Y1 + 14, text=f"{int(x1 - x0)} x {int(y1 - y0)}   Enter or double-click = crop   Esc = cancel",
                       fill="white", font=T.f(9), tags="xov")

    def _crop_apply(self):
        if self._crop is None: return
        b = self._clip_box(*self._crop); self._crop = None
        if b is None: return
        x0, y0, x1, y1 = b; w, h = self.size_wh
        if (x0, y0, x1, y1) == (0, 0, w, h): self._x_overlay(); return
        self._whole_snapshot()
        self._resize_doc(lambda arr: arr[y0:y1, x0:x1].copy(), x1 - x0, y1 - y0)
        T.banner(self.app, f"CROPPED — {x1 - x0} x {y1 - y0} (Ctrl+Z undoes it)", "success")

    def _whole_snapshot(self):
        """remember the whole picture (every layer and the background) on the Undo list, for a crop"""
        A = np.stack([self.bg] + [L.cv.a for L in self.layers]); AL = np.stack([L.cv.alpha for L in self.layers])
        self.undo_stack.append(("whole", 0, 0, 0, 0, A, AL)); self.redo_stack.clear(); self._trim_undo(); self.changed = True

    def _resize_doc(self, fn, w, h):
        import brushes
        self.bg = fn(self.bg)
        for L in self.layers:
            c = L.cv; c.a = fn(c.a); c.alpha = fn(c.alpha); c.w, c.h = w, h
            try: c.grain = fn(c.grain) if c.grain.shape[:2] != (h, w) else c.grain
            except Exception: pass
            if c.grain.shape[:2] != (h, w): c.grain = brushes._grain(h, w, 1)
        self.size_wh = (w, h); self._comp = np.empty((h, w, 3), np.uint8); self._recomp()
        self.sel = None; self._view_fit = True; self.fit(); self._layers_ui()

    def _swap_whole(self, src, dst):
        """undo / redo a crop: swap the whole picture with the one remembered"""
        _, _, _, _, _, A, AL = src.pop()
        cur_A = np.stack([self.bg] + [L.cv.a for L in self.layers]); cur_AL = np.stack([L.cv.alpha for L in self.layers])
        dst.append(("whole", 0, 0, 0, 0, cur_A, cur_AL))
        h, w = A.shape[1:3]; it = iter(range(len(A)))
        self.bg = A[0].copy()
        import brushes
        for i, L in enumerate(self.layers):
            if i + 1 < len(A): L.cv.a = A[i + 1].copy(); L.cv.alpha = AL[i].copy()
            else: L.cv.a = np.zeros((h, w, 3), np.float32) + 255; L.cv.alpha = np.zeros((h, w), np.float32)
            L.cv.w, L.cv.h = w, h; L.cv.grain = brushes._grain(h, w, 1)
        self.size_wh = (w, h); self._comp = np.empty((h, w, 3), np.uint8); self._recomp()
        self.sel = None; self._view_fit = True; self.fit(); self._layers_ui(); self.changed = True

    # ------------------------------------------------------------------ text
    def _text_panel(self, parent):
        """TEXT under the layers: the words, font, size, bold / italic / underline, alignment, and Place / Cancel"""
        bg = parent["bg"]
        def fr(**pack):
            f = tk.Frame(parent, bg=bg); f.pack(**pack); T.on_change(lambda: f.configure(bg=f.master["bg"])); return f
        hdr = fr(fill="x", pady=(6, 1)); T.Text(hdr, "TEXT", font=T.f(10, "underline")).pack()
        self.txt_box = T.Field(parent, height=2); self.txt_box.configure(font=T.f(10), padx=6, pady=4); self.txt_box.pack(fill="x", pady=(2, 4))
        self.txt_box.bind("<KeyRelease>", lambda e: self._txt_changed(), add="+")
        self.txt_box.bind("<<Paste>>", lambda e: self.after(10, self._txt_changed), add="+")
        names = list(fonts()) or ["Default"]
        self.txt_font = tk.StringVar(value="Arial" if "Arial" in names else names[0])
        self.txt_size = tk.StringVar(value="48"); self.txt_align = tk.StringVar(value="Left")
        self.txt_bold, self.txt_italic, self.txt_under = tk.BooleanVar(), tk.BooleanVar(), tk.BooleanVar()
        r = fr(fill="x", pady=1); T.Choice(r, "font", names, self.txt_font).pack(fill="x")
        r = fr(fill="x", pady=2); T.Text(r, "Size:", font=T.f(8)).pack(side="left")
        e = T.Entry(r, self.txt_size, width=5); e.configure(font=T.f(9), justify="center"); e.pack(side="left", padx=4)
        for sym, k in (("-", 1 / 1.15), ("+", 1.15)):
            T.Button(r, sym, lambda k=k: self._txt_scale(k), width=2).pack(side="left", padx=1)
        r = fr(fill="x", pady=1); T.Choice(r, "align", ["Left", "Center", "Right"], self.txt_align).pack(fill="x")
        r = fr(fill="x", pady=2)
        for label, var in (("B", self.txt_bold), ("I", self.txt_italic), ("U", self.txt_under)):
            c = tk.Frame(r, bg=bg); c.pack(side="left", expand=True); T.on_change(lambda c=c: c.configure(bg=c.master["bg"]))
            fnt = T.f(10, {"B": "bold", "I": "italic", "U": "underline"}[label])
            T.Text(c, label, font=fnt).pack(side="left", padx=(0, 3)); T.Toggle(c, var).pack(side="left")
        r = fr(fill="x", pady=(4, 2))
        T.Button(r, "Place", self._txt_commit, kind="success", width=7).pack(side="left", expand=True)
        T.Button(r, "Cancel", self._txt_cancel, kind="danger", width=7).pack(side="left", expand=True)
        for v in (self.txt_font, self.txt_align, self.txt_bold, self.txt_italic, self.txt_under): v.trace_add("write", lambda *a: self._txt_changed())
        self.txt_size.trace_add("write", lambda *a: self._txt_changed())

    def _txt_settings(self):
        try: size = max(4, min(1000, int(float(self.txt_size.get()))))
        except ValueError: size = 48
        return dict(name=self.txt_font.get(), size=size, bold=self.txt_bold.get(), italic=self.txt_italic.get(),
                    underline=self.txt_under.get(), align=self.txt_align.get())

    def _txt_scale(self, k):
        try: s = float(self.txt_size.get())
        except ValueError: s = 48
        self.txt_size.set(str(max(4, min(1000, int(round(s * k)))) if round(s * k) != s else int(s + (1 if k > 1 else -1))))

    def _txt_text(self):
        try: return self.txt_box.get("1.0", "end-1c")
        except (tk.TclError, AttributeError): return ""

    def _txt_down(self, e, p):
        t = self.txt
        if t is not None:
            hit = self._txt_hit(p)
            if hit: self._x_drag = ("txt_" + hit, (p[0], p[1]), (t["x"], t["y"], t["width"], self._txt_settings()["size"])); return
            self._txt_commit()
        if not hasattr(self, "txt_box"): return
        self.txt = dict(x=p[0], y=p[1], width=None, mask=None, ends=[], key=None)
        if self._right_view_name() != "Layers": self._right_view("Layers")
        self.txt_box.delete("1.0", "end"); self.txt_box.focus_set(); self._txt_changed()

    def _right_view_name(self):
        try: return "Layers" if self.lay_view.winfo_manager() else "Color"
        except (AttributeError, tk.TclError): return "Layers"

    def _txt_hit(self, p):
        t = self.txt
        if t is None or t["mask"] is None: return None
        x0, y0 = t["x"], t["y"]; x1, y1 = x0 + t["mask"].width, y0 + t["mask"].height; r = HANDLE * 1.6 / max(self.zoom, 1e-3)
        if abs(p[0] - x1) <= r and abs(p[1] - y1) <= r: return "size"
        if abs(p[0] - x1) <= r and y0 <= p[1] <= y1: return "wrap"
        return "move" if x0 <= p[0] <= x1 and y0 <= p[1] <= y1 else None

    def _txt_drag(self, p):
        kind = self._x_drag[0]; sx, sy = self._x_drag[1]; x, y, width, size = self._x_drag[2]; t = self.txt
        if t is None: return
        if kind == "txt_move": t["x"], t["y"] = x + p[0] - sx, y + p[1] - sy; self._x_overlay()
        elif kind == "txt_wrap":
            w0 = width if width is not None else (t["mask"].width if t["mask"] is not None else 100)
            t["width"] = max(size * 0.8, w0 + p[0] - sx); self._txt_changed()
        elif kind == "txt_size":
            h0 = t["mask"].height if t["mask"] is not None else size; k = max(0.1, (h0 + p[1] - sy) / max(1, h0))
            self.txt_size.set(str(max(4, min(1000, int(round(size * k))))))
            if width is not None: t["width"] = width * k

    def _txt_changed(self):
        t = self.txt
        if t is None: return
        s = self._txt_settings(); text = self._txt_text()
        key = (text, t["width"], tuple(s.items()))
        if key != t["key"]:
            t["mask"], t["ends"] = render_text(text, s["name"], s["size"], s["bold"], s["italic"], s["underline"], s["align"], t["width"])
            t["key"] = key; t["ph_key"] = None
        self._blink = True; self._x_overlay()

    def _txt_draw(self, cv):
        t = self.txt
        if t is None or t["mask"] is None: return
        z = self.zoom; m = t["mask"]; X0, Y0 = self._x_scr(t["x"], t["y"]); X1, Y1 = self._x_scr(t["x"] + m.width, t["y"] + m.height)
        col = tuple(self.color); pk = (t["key"], round(z, 3), col, round(self.opacity, 2))
        if t.get("ph_key") != pk and m.width > 0 and self._txt_text():
            W, H = max(1, int(m.width * z)), max(1, int(m.height * z))
            if W * H < 16e6:
                a = m.resize((W, H), Image.LANCZOS if z < 1 else Image.BILINEAR).point(lambda v: int(v * self.opacity))
                im = Image.new("RGBA", (W, H), col + (0,)); im.putalpha(a); t["ph"] = ImageTk.PhotoImage(im); t["ph_key"] = pk
        if self._txt_text() and t.get("ph") is not None: cv.create_image(X0, Y0, image=t["ph"], anchor="nw", tags="xov")
        cv.create_rectangle(X0 - 3, Y0 - 3, X1 + 3, Y1 + 3, outline="white", dash=(4, 3), tags="xov")
        cv.create_rectangle(X0 - 3, Y0 - 3, X1 + 3, Y1 + 3, outline="black", dash=(4, 3), dashoffset=4, tags="xov")
        my = (Y0 + Y1) / 2
        cv.create_rectangle(X1 + 3 - HANDLE / 2, my - HANDLE, X1 + 3 + HANDLE / 2, my + HANDLE, fill="white", outline="black", tags="xov")   # wrap width
        cv.create_rectangle(X1 + 3 - HANDLE, Y1 + 3 - HANDLE, X1 + 3 + HANDLE, Y1 + 3 + HANDLE, fill="white", outline="black", tags="xov")   # size
        if self._blink and t["ends"]:                                           # the blinking cursor after the last letter
            ex, ey, lh = t["ends"][-1]; cx, cy = self._x_scr(t["x"] + ex + 1, t["y"] + ey)
            cv.create_line(cx, cy, cx, cy + lh * z * 0.9, fill="#%02x%02x%02x" % col, width=max(2, int(z * self._txt_settings()["size"] / 20)), tags="xov")

    def _txt_commit(self):
        """paint the text onto the current layer (one Undo step) and close the box"""
        t = self.txt; self.txt = None
        text = self._txt_text().strip("\n")
        if t is not None and text.strip():
            if t["mask"] is None: self.txt = t; self._txt_changed(); self.txt = None
            m = np.asarray(t["mask"], np.float32) / 255 * self.opacity; w, h = self.size_wh
            X0, Y0 = int(round(t["x"])), int(round(t["y"])); mh, mw = m.shape
            cx0, cy0, cx1, cy1 = max(0, X0), max(0, Y0), min(w, X0 + mw), min(h, Y0 + mh)
            if cx1 > cx0 and cy1 > cy0:
                self._begin_edit()
                self.cur.cv._blend(cy0, cy1, cx0, cx1, m[cy0 - Y0:cy1 - Y0, cx0 - X0:cx1 - X0], tuple(self.color), "normal")
                self._dirty = (cx0, cy0, cx1, cy1); r = self._commit_edit()
                if r: self._recomp(r)
        try: self.txt_box.delete("1.0", "end")
        except (tk.TclError, AttributeError): pass
        self._draw()

    def _txt_cancel(self):
        self.txt = None
        try: self.txt_box.delete("1.0", "end")
        except (tk.TclError, AttributeError): pass
        self._x_overlay()
