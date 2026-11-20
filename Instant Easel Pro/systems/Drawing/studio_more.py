"""
studio_more.py: more of the Draw studio, in the Options and Color views.

Options (right side, below the layers and text):
  GUIDES  - a ruler, or 1 / 2 / 3-point perspective. Strokes snap along them; their dots can be dragged.
  FILL    - tolerance, fill from all layers or this one, gradients to clear or to the second colour, soft selection edges.
  CANVAS  - resize the picture (everything scales) or the canvas (more room, nothing scales).
  SAVING  - save PNG / WebP with a see-through background.
Color (below the sliders):
  MY COLORS - colours you keep (+ adds the current one, right-click removes), and the main colours of the picture.

Mixed into DrawStudio (draw_studio.py); it uses the studio's own state and helpers.
"""
import json, math
import tkinter as tk
import numpy as np
from PIL import Image
import theme as T, paths

GUIDES = ["Off", "Ruler", "1-point", "2-point", "3-point"]
HANDLE_R = 7                                                                 # guide dots (screen pixels)

class StudioMore:
    # ------------------------------------------------------------------ the Options sections
    def _more_options(self, parent, frame):
        """GUIDES, FILL, CANVAS and SAVING under the layers and text. frame(parent, **pack) makes a themed row"""
        def head(text):
            r = frame(parent, fill="x", pady=(10, 2)); T.Text(r, text, font=T.f(10, "underline")).pack()
        def choice(label, var, choices, tip=None):
            r = frame(parent, fill="x", pady=2); T.Text(r, label, font=T.f(8), width=10, anchor="w").pack(side="left")
            c = T.Choice(r, "", choices, var); c.pack(side="left", fill="x", expand=True)
            if tip: self._tip(c, tip)
        def toggle(label, var, tip=None, command=None):
            r = frame(parent, fill="x", pady=2); T.Text(r, label, font=T.f(9)).pack(side="left")
            t_ = T.Toggle(r, var, command=command); t_.pack(side="right")
            if tip: self._tip(t_, tip)
        # ---- guides
        head("GUIDES")
        self.guide = tk.StringVar(value="Off"); self.guide_snap = tk.BooleanVar(value=True); self.guide_move = tk.BooleanVar(value=False)
        choice("Guide:", self.guide, GUIDES, "A ruler, or perspective with 1, 2 or 3 vanishing points")
        toggle("Snap strokes to it", self.guide_snap, "Strokes run straight along the ruler, or toward a vanishing point (whichever way you start)")
        toggle("Move guides", self.guide_move, "Drag the guide's dots to place it (painting is paused while this is on)")
        for v in (self.guide, self.guide_snap): v.trace_add("write", lambda *a: self.refresh())
        self.guide_move.trace_add("write", lambda *a: self.refresh())
        # ---- fill and gradient (the paint bucket, magic wand and gradients)
        head("FILL")
        self.g_rows = getattr(self, "g_rows", {})
        def gslider(key, label, tip, top=100, unit="%"):
            row = self._slider_row(parent, label, self.gopts[key] / top, lambda v, k=key, t=top: self._set_g(k, v * t), f"{int(self.gopts[key])}{unit}")
            row.entry.bind("<Return>", lambda e, k=key, row=row: self._typed(row, lambda x, k=k: self._set_g(k, x, sync=True)))
            row.top, row.unit = top, unit; self._tip(row.slider, tip); self.g_rows[key] = row
        gslider("tolerance", "Tolerance:", "How different a colour can be and still get filled or selected (higher takes more)")
        choice("Fill from:", self.fill_sample, ["All layers", "This layer"], "Fill and Magic Wand look at the whole picture, or just the layer you're on")
        self.grad_to = tk.StringVar(value="Clear")
        choice("Gradient to:", self.grad_to, ["Clear", "2nd color"], "Gradients fade from your colour to see-through, or to your second colour")
        gslider("feather", "Feather:", "Softens the edges of selections (pixels), so what you cut, fill or paint inside them blends in", top=50, unit="px")
        # ---- canvas size
        head("CANVAS")
        w, h = getattr(self, "size_wh", (1600, 1100)); self.cw_var, self.ch_var = tk.StringVar(value=str(w)), tk.StringVar(value=str(h))   # (set again once the canvas exists)
        r = frame(parent, fill="x", pady=2); T.Text(r, "Size:", font=T.f(8)).pack(side="left")
        for var in (self.cw_var, self.ch_var):
            e = T.Entry(r, var, width=6); e.configure(font=T.f(9), justify="center"); e.pack(side="left", padx=3)
            if var is self.cw_var: T.Text(r, "x", font=T.f(8)).pack(side="left")
        r = frame(parent, fill="x", pady=(3, 2))
        self._tip(self._small_btn(r, "Resize picture", lambda: self._resize("picture")), "Everything scales to the new size").pack(side="left")
        self._tip(self._small_btn(r, "Resize canvas", lambda: self._resize("canvas")), "More (or less) room round the picture; nothing scales").pack(side="right")
        # ---- saving
        head("SAVING")
        self.save_clear = tk.BooleanVar(value=False)
        toggle("See-through background", self.save_clear, "PNG and WebP are saved without the white background (just what's on the layers)")

    def _small_btn(self, parent, text, cmd):
        b = T.Button(parent, text, cmd); b.configure(padx=7, pady=4, font=T.f(9)); return b

    def _set_g(self, key, val, sync=False):
        row = self.g_rows[key]; top = getattr(row, "top", 100); unit = getattr(row, "unit", "%")
        val = min(float(top), max(0.0, float(val))); self.gopts[key] = val
        self._sync_slider(row, val / top); row.var.set(f"{int(round(val))}{unit}")

    # ------------------------------------------------------------------ canvas size
    def _resize(self, how):
        try: W, H = int(float(self.cw_var.get())), int(float(self.ch_var.get()))
        except ValueError: T.banner(self.app, "NOT A NUMBER — type the width and height in pixels"); return
        if not (16 <= W <= 8000 and 16 <= H <= 8000): T.banner(self.app, "TOO BIG OR SMALL — from 16 to 8000 pixels each way"); return
        w, h = self.size_wh
        if (W, H) == (w, h): return
        self._whole_snapshot()
        if how == "picture":
            def fn(arr):
                one = lambda a2: np.asarray(Image.fromarray(np.ascontiguousarray(a2, np.float32), "F").resize((W, H), Image.LANCZOS if W < w else Image.BICUBIC), np.float32)
                return np.stack([one(arr[..., k]) for k in range(arr.shape[2])], -1) if arr.ndim == 3 else np.clip(one(arr), 0, None)
        else:
            ox, oy = (W - w) // 2, (H - h) // 2                                    # the picture stays in the middle
            def fn(arr):
                out = np.full((H, W) + arr.shape[2:], 255.0 if arr.ndim == 3 else 0.0, np.float32)
                sx0, sy0 = max(0, -ox), max(0, -oy); dx0, dy0 = max(0, ox), max(0, oy); cw, ch = min(w - sx0, W - dx0), min(h - sy0, H - dy0)
                if cw > 0 and ch > 0: out[dy0:dy0 + ch, dx0:dx0 + cw] = arr[sy0:sy0 + ch, sx0:sx0 + cw]
                return out
        self._resize_doc(fn, W, H)
        for L in self.layers: L.cv.alpha = np.clip(L.cv.alpha, 0, 1)
        self._recomp(); self._draw(); self.set_size(self.size); self.changed = True
        T.banner(self.app, f"RESIZED — {W} x {H} (Ctrl+Z undoes it)", "success")

    def _sync_canvas_size(self):
        if hasattr(self, "cw_var"): w, h = self.size_wh; self.cw_var.set(str(w)); self.ch_var.set(str(h))

    # ------------------------------------------------------------------ saving with a see-through background
    def flatten_clear(self):
        """the layers only (no background), as RGBA: blend modes are kept where there's paint beneath"""
        w, h = self.size_wh; col = np.zeros((h, w, 3), np.float32); al = np.zeros((h, w), np.float32); base_al = None
        import brushes
        for L in self.layers:
            if getattr(L, "clip", False):
                if not L.visible: continue
                a = L.cv.alpha * L.opacity * (base_al if base_al is not None else 0)
            else:
                base_al = L.cv.alpha * L.opacity if L.visible else np.zeros((h, w), np.float32)
                if not L.visible: continue
                a = L.cv.alpha * L.opacity
            top = L.cv.a if L.mode == "normal" else np.where(al[..., None] > 0.002, brushes.blend_rgb(col, L.cv.a, L.mode), L.cv.a)
            out = a + al * (1 - a); col = (top * a[..., None] + col * (al * (1 - a))[..., None]) / np.maximum(out, 1e-5)[..., None]; al = out
        return Image.fromarray(np.dstack([np.clip(col, 0, 255), np.clip(al, 0, 1)[..., None] * 255]).astype(np.uint8), "RGBA")

    # ------------------------------------------------------------------ guides: a ruler or perspective
    def _guide_state(self):
        g = getattr(self, "_guides", None); w, h = self.size_wh
        if g is None or g.get("size") != (w, h):
            g = self._guides = dict(size=(w, h), ruler=[(w * 0.3, h * 0.5), (w * 0.7, h * 0.5)],
                                    vps=[(w * 0.5, h * 0.42), (w * 0.08, h * 0.42), (w * 0.92, h * 0.42), (w * 0.5, h * 1.9)])
        return g

    def _guide_dots(self):
        """the draggable dots of the guide that's on: [(kind, index, (x, y))]"""
        g = self._guide_state(); m = self.guide.get() if hasattr(self, "guide") else "Off"
        if m == "Ruler": return [("ruler", i, q) for i, q in enumerate(g["ruler"])]
        if m == "1-point": return [("vp", 0, g["vps"][0])]
        if m == "2-point": return [("vp", 1, g["vps"][1]), ("vp", 2, g["vps"][2])]
        if m == "3-point": return [("vp", 1, g["vps"][1]), ("vp", 2, g["vps"][2]), ("vp", 3, g["vps"][3])]
        return []

    def _guides_draw(self):
        if not hasattr(self, "guide") or self.guide.get() == "Off": return
        g = self._guide_state(); m = self.guide.get(); w, h = self.size_wh; S_ = self._to_scr; col = T.PALETTE["border"]; far = (w + h) * 3
        if m == "Ruler":
            (ax, ay), (bx, by) = g["ruler"]; d = math.hypot(bx - ax, by - ay) or 1; ux, uy = (bx - ax) / d, (by - ay) / d
            self.cv.create_line(*S_(ax - ux * far, ay - uy * far), *S_(ax + ux * far, ay + uy * far), fill=col, width=2, tags="guide")
            self.cv.create_line(*S_(ax, ay), *S_(bx, by), fill="white", width=4, tags="guide")
        else:
            vps = [g["vps"][0]] if m == "1-point" else [g["vps"][1], g["vps"][2]] + ([g["vps"][3]] if m == "3-point" else [])
            if m != "1-point" or True:                                         # the horizon
                hy = vps[0][1] if m == "1-point" else (vps[0][1] + vps[1][1]) / 2
                self.cv.create_line(*S_(-far, hy), *S_(w + far, hy), fill=col, width=2, tags="guide")
            for (vx, vy) in vps:                                               # rays out of every vanishing point
                for k in range(24):
                    a = k * math.pi / 12; self.cv.create_line(*S_(vx, vy), *S_(vx + math.cos(a) * far, vy + math.sin(a) * far), fill=col, dash=(2, 6), tags="guide")
        for kind, i, (x, y) in self._guide_dots():
            X, Y = S_(x, y); r = HANDLE_R + (2 if self.guide_move.get() else 0)
            self.cv.create_oval(X - r, Y - r, X + r, Y + r, fill="white" if self.guide_move.get() else col, outline="black", width=2, tags="guide")

    def _guide_grab(self, e):
        """Move guides is on: grab the nearest dot under the mouse. True if one was taken"""
        best = None
        for kind, i, (x, y) in self._guide_dots():
            X, Y = self._to_scr(x, y); d = math.hypot(e.x - X, e.y - Y)
            if d <= HANDLE_R * 2.5 and (best is None or d < best[0]): best = (d, kind, i)
        self._guide_drag = best[1:] if best else None
        return best is not None

    def _guide_drag_to(self, p):
        if not getattr(self, "_guide_drag", None): return
        g = self._guide_state(); kind, i = self._guide_drag
        (g["ruler"] if kind == "ruler" else g["vps"])[i] = (p[0], p[1]); self.refresh()

    def _snap_begin(self, p):
        on = hasattr(self, "guide") and self.guide.get() != "Off" and self.guide_snap.get() and self.tool in ("brush", "eraser")
        self._snap = dict(start=(p[0], p[1]), dir=None) if on else None

    def _snap_pt(self, p):
        """a stroke point held on the guide: once the stroke has a direction, it runs straight that way"""
        sn = getattr(self, "_snap", None)
        if sn is None: return p
        sx, sy = sn["start"]
        if sn["dir"] is None:
            mx, my = p[0] - sx, p[1] - sy
            if math.hypot(mx, my) * (self.zoom or 1) < 10: return (sx, sy, p[2])    # wait until it's clear which way the stroke goes
            g = self._guide_state(); m = self.guide.get(); cands = []
            if m == "Ruler": (ax, ay), (bx, by) = g["ruler"]; cands.append((bx - ax, by - ay))
            else:
                vps = [g["vps"][0]] if m == "1-point" else [g["vps"][1], g["vps"][2]] + ([g["vps"][3]] if m == "3-point" else [])
                cands += [(vx - sx, vy - sy) for vx, vy in vps]
                if m in ("1-point", "2-point"): cands.append((0, 1))                    # upright lines
                if m == "1-point": cands.append((1, 0))                                 # and level ones
            best = None
            for cx, cy in cands:
                n = math.hypot(cx, cy) or 1; cx, cy = cx / n, cy / n; score = abs(cx * mx + cy * my) / math.hypot(mx, my)
                if best is None or score > best[0]: best = (score, cx, cy)
            sn["dir"] = (best[1], best[2])
        dx, dy = sn["dir"]; t = (p[0] - sx) * dx + (p[1] - sy) * dy
        return (sx + dx * t, sy + dy * t, p[2])

    # ------------------------------------------------------------------ MY COLORS (Color view)
    def _my_colors_file(self): return paths.json_file("draw_colors.json")

    def _load_my_colors(self):
        try: d = json.load(open(self._my_colors_file(), encoding="utf-8")); return [tuple(c) for c in d.get("colors", [])][:16]
        except Exception: return []

    def _save_my_colors(self):
        try:
            with open(self._my_colors_file(), "w", encoding="utf-8") as f: json.dump(dict(colors=[list(c) for c in self.my_colors]), f)
        except Exception: pass

    def add_my_color(self):
        c = tuple(self.color)
        if c in self.my_colors: self.my_colors.remove(c)
        self.my_colors.insert(0, c); self.my_colors = self.my_colors[:16]; self._save_my_colors(); self._paint_my_colors()

    def drop_my_color(self, i):
        if 0 <= i < len(self.my_colors): del self.my_colors[i]; self._save_my_colors(); self._paint_my_colors()

    def picture_colors(self):
        """the 8 main colours of the picture, into the PICTURE row"""
        im = Image.fromarray(self._comp); im.thumbnail((200, 200))
        q = im.quantize(8, method=Image.Quantize.MEDIANCUT); pal = q.getpalette()[:24]; counts = sorted(q.getcolors(), reverse=True)
        self.pic_colors = [tuple(pal[i * 3:i * 3 + 3]) for _, i in counts][:8]; self._paint_my_colors()
