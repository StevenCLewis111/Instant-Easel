"""
brushes.py: the app's brush engine.
Every brush = a TIP (shape, softness, bristles) dragged along the stroke with spacing, pressure, jitter, paper grain and a
blend mode, following the brush model from the textbook. Special brushes (smudge, blur, deform, clone, hatching, sketch,
particle, grid...) work on what is already painted, like the Krita engines they're named after.

    canvas = Canvas(1200, 800, paper=(244, 238, 226))
    canvas.stroke(points, "oil filbert", color=(200, 90, 40), size=40, opacity=1.0)
"""
import math, random
import numpy as np
from PIL import Image

def _grain(h, w, seed=3, scale=1.0):
    rng = np.random.default_rng(seed); g = rng.random((h, w)).astype(np.float32)
    small = rng.random((max(2, h // 6), max(2, w // 6))).astype(np.float32)
    g = 0.6 * g + 0.4 * np.asarray(Image.fromarray(small).resize((w, h), Image.BICUBIC))
    return g

# ---------------- tips: return an alpha mask (0..1) of size s x s for one dab ----------------
def tip_round(s, hard=0.8, **k):
    if s <= 3: return np.ones((s, s), np.float32)                      # tiny tips: a solid dot (fixes thin lines)
    y, x = np.mgrid[-1:1:s * 1j, -1:1:s * 1j]; r = np.sqrt(x * x + y * y) * (s / (s + 1.0))
    return np.clip((1 - r) / max(1e-3, 1 - hard), 0, 1) * (r <= 1)

def tip_soft(s, **k):
    y, x = np.mgrid[-1:1:s * 1j, -1:1:s * 1j]; return np.clip(np.exp(-(x * x + y * y) * 4.5) - 0.01, 0, 1)

def tip_ellipse(s, aspect=0.35, angle=0.0, hard=0.85, **k):
    y, x = np.mgrid[-1:1:s * 1j, -1:1:s * 1j]; ca, sa = math.cos(angle), math.sin(angle)
    u, v = x * ca + y * sa, (-x * sa + y * ca) / aspect; r = np.sqrt(u * u + v * v)
    return np.clip((1 - r) / (1 - hard), 0, 1) * (r <= 1)

def tip_rect(s, aspect=0.25, angle=0.0, **k):
    y, x = np.mgrid[-1:1:s * 1j, -1:1:s * 1j]; ca, sa = math.cos(angle), math.sin(angle)
    u, v = x * ca + y * sa, -x * sa + y * ca
    return ((np.abs(u) <= 0.95) & (np.abs(v) <= aspect)).astype(np.float32)

def tip_bristles(s, n=14, aspect=0.3, angle=0.0, seed=0, **k):
    rng = random.Random(seed); m = np.zeros((s, s), np.float32); ca, sa = math.cos(angle), math.sin(angle)
    for i in range(n):
        off = (i / max(1, n - 1) - 0.5) * 1.8; r = rng.uniform(0.04, 0.09) * s
        cx = s / 2 + off * s / 2 * ca * 0.9 - 0 * sa; cy = s / 2 + off * s / 2 * sa * 0.9
        y, x = np.ogrid[:s, :s]; m = np.maximum(m, ((x - cx) ** 2 + (y - cy) ** 2 <= r * r) * rng.uniform(0.55, 1.0))
    return m

def tip_fan(s, angle=0.0, **k):
    m = np.zeros((s, s), np.float32); y, x = np.ogrid[:s, :s]
    for i in range(11):
        a = angle - math.pi / 2 + (i / 10 - 0.5) * 1.6
        for t in np.linspace(0.15, 0.95, 9):
            cx = s / 2 + math.cos(a) * t * s / 2; cy = s / 2 + math.sin(a) * t * s / 2; r = max(1, s * 0.025)
            m = np.maximum(m, ((x - cx) ** 2 + (y - cy) ** 2 <= r * r).astype(np.float32))
    return m

def tip_sponge(s, seed=0, **k):
    rng = np.random.default_rng(seed); base = tip_round(s, hard=0.4)
    holes = rng.random((s, s)) > 0.55
    return base * holes * rng.uniform(0.5, 1.0, (s, s))

# ---------------- brushes: name -> settings ----------------
B = {}
def brush(name, tip, spacing=0.15, size_scale=1.0, jitter_size=0.0, jitter_angle=0.0, scatter=0.0, color_jitter=0.0, grain=0.0,
          mode="normal", flow=1.0, taper=False, angle_follow=False, special=None, **tipargs):
    B[name] = dict(tip=tip, spacing=spacing, size_scale=size_scale, jitter_size=jitter_size, jitter_angle=jitter_angle, scatter=scatter,
                   color_jitter=color_jitter, grain=grain, mode=mode, flow=flow, taper=taper, angle_follow=angle_follow,
                   special=special, tipargs=tipargs)

# traditional brush shapes
brush("round", tip_round, hard=0.85)
brush("flat", tip_rect, aspect=0.22, angle_follow=True, spacing=0.06)
brush("bright", tip_rect, aspect=0.35, angle_follow=True, spacing=0.06, grain=0.15)
brush("filbert", tip_ellipse, aspect=0.38, angle_follow=True, spacing=0.07)
brush("fan", tip_fan, angle_follow=True, spacing=0.06, color_jitter=0.08, flow=0.5)
brush("angular", tip_rect, aspect=0.2, angle=0.6, spacing=0.06)
brush("dagger", tip_ellipse, aspect=0.18, angle=0.5, hard=0.9, taper=True, spacing=0.06)
brush("liner (rigger)", tip_round, hard=0.9, taper=True, spacing=0.05)
brush("script", tip_round, hard=0.95, taper=True, spacing=0.04)
brush("mop", tip_soft, spacing=0.1, flow=0.35)
brush("spotter", tip_round, hard=0.95, spacing=0.08)
brush("palette knife", tip_rect, aspect=0.08, angle_follow=True, spacing=0.03, special="knife")
# dry media
brush("pencil", tip_round, hard=0.6, grain=0.75, spacing=0.1, flow=0.6)
brush("charcoal", tip_ellipse, aspect=0.5, angle_follow=True, grain=0.85, spacing=0.08, flow=0.7, jitter_angle=0.3)
brush("pastel / chalk", tip_ellipse, aspect=0.6, grain=0.7, spacing=0.08, flow=0.8, scatter=0.05)
brush("crayon", tip_round, hard=0.7, grain=0.9, spacing=0.06, flow=0.9)
brush("ink pen", tip_round, hard=1.0, taper=True, spacing=0.03)
brush("calligraphy", tip_rect, aspect=0.12, angle=0.78, spacing=0.03)
brush("marker", tip_rect, aspect=0.6, angle_follow=True, spacing=0.08, mode="multiply", flow=0.1)
# wet media
brush("watercolor", tip_soft, spacing=0.06, flow=0.32, mode="multiply", special="wet_edge", grain=0.2)
brush("oil", tip_bristles, n=16, aspect=0.3, angle_follow=True, spacing=0.05, color_jitter=0.05, special="impasto")
brush("gouache", tip_ellipse, aspect=0.55, angle_follow=True, hard=0.95, spacing=0.06, grain=0.1)
brush("acrylic", tip_round, hard=0.9, spacing=0.06, color_jitter=0.03)
brush("airbrush", tip_soft, spacing=0.08, flow=0.12)
brush("dry brush", tip_bristles, n=10, aspect=0.4, angle_follow=True, spacing=0.06, grain=0.8)
brush("sponge", tip_sponge, spacing=0.4, jitter_angle=3.14, flow=0.8)
brush("splatter", tip_round, hard=0.9, spacing=0.35, scatter=1.6, jitter_size=0.9, size_scale=0.28)
# Krita-style engines
brush("bristle", tip_bristles, n=22, aspect=0.45, angle_follow=True, spacing=0.04, color_jitter=0.08)
brush("spray", tip_round, hard=0.9, spacing=0.2, scatter=1.0, jitter_size=0.8, flow=0.8, special="spray")
brush("particle", tip_round, special="particle")
brush("sketch", tip_round, special="sketch")
brush("hatching", tip_round, special="hatching")
brush("curve", tip_round, special="curve")
brush("grid", tip_round, special="grid")
brush("shape", tip_round, special="shape")
brush("smudge / blender", tip_soft, spacing=0.05, special="smudge")
brush("blur (filter)", tip_soft, spacing=0.2, special="blur")
brush("deform (push)", tip_soft, spacing=0.1, special="deform")
brush("clone", tip_soft, spacing=0.1, special="clone")
brush("glaze", tip_soft, spacing=0.1, flow=0.2, mode="multiply")
brush("glow (dodge)", tip_soft, spacing=0.1, flow=0.25, mode="screen")
brush("eraser", tip_round, hard=0.8, mode="erase")
# subject brushes
brush("grass blades", tip_round, special="grass")
brush("foliage", tip_ellipse, aspect=0.5, spacing=0.5, scatter=1.2, jitter_size=0.6, jitter_angle=3.14, color_jitter=0.15)
brush("stipple", tip_round, hard=1.0, spacing=0.12, scatter=0.9, jitter_size=0.5, size_scale=0.12)

class Canvas:
    def __init__(self, w, h, paper=(245, 240, 230), seed=1, transparent=False):
        """transparent=True makes a see-through layer: colour in self.a plus coverage in self.alpha (0..1)"""
        self.w, self.h = w, h; self.a = np.zeros((h, w, 3), np.float32) + np.array(paper, np.float32)
        self.paper = np.array(paper, np.float32); self.grain = _grain(h, w, seed); self.rng = random.Random(seed)
        self.alpha = np.zeros((h, w), np.float32) if transparent else None

    def image(self): return Image.fromarray(np.clip(np.nan_to_num(self.a), 0, 255).astype(np.uint8))

    def _dab(self, x, y, mask, color, alpha, mode, grain):
        s = mask.shape[0]; x0, y0 = int(x - s / 2), int(y - s / 2); x1, y1 = x0 + s, y0 + s
        cx0, cy0, cx1, cy1 = max(0, x0), max(0, y0), min(self.w, x1), min(self.h, y1)
        if cx0 >= cx1 or cy0 >= cy1: return
        m = mask[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0] * alpha
        if grain: m = m * np.clip((self.grain[cy0:cy1, cx0:cx1] - grain * 0.55) / (1 - grain * 0.55), 0, 1)
        self._blend(cy0, cy1, cx0, cx1, m, color, mode)

    def _blend(self, y0, y1, x0, x1, m, color, mode):
        """lay colour through mask m onto the region; on a transparent layer, coverage builds up (or is erased)"""
        reg = self.a[y0:y1, x0:x1]; m3 = m[..., None]; c = np.asarray(color, np.float32)
        if self.alpha is not None:
            ra = self.alpha[y0:y1, x0:x1][..., None]
            if mode == "erase": self.alpha[y0:y1, x0:x1] = (ra * (1 - m3))[..., 0]; return
            base = np.where(ra > 0.002, reg, 255.0)                          # empty layer acts as white for multiply/screen
            if mode == "multiply": new = base * (c / 255)
            elif mode == "screen": new = 255 - (255 - base) * (255 - c) / 255
            else: new = np.broadcast_to(c, reg.shape)
            out_a = ra * (1 - m3) + m3
            self.a[y0:y1, x0:x1] = (reg * ra * (1 - m3) + new * m3) / np.maximum(out_a, 1e-4); self.alpha[y0:y1, x0:x1] = out_a[..., 0]; return
        if mode == "multiply": new = reg * (c / 255)
        elif mode == "screen": new = 255 - (255 - reg) * (255 - c) / 255
        elif mode == "erase": new = np.broadcast_to(self.paper, reg.shape)
        else: new = np.broadcast_to(c, reg.shape)
        self.a[y0:y1, x0:x1] = reg * (1 - m3) + new * m3

    def stroke(self, pts, name, color=(30, 30, 30), size=24, opacity=1.0):
        """pts: list of (x, y) or (x, y, pressure)"""
        b = B[name]; pts = [(p[0], p[1], p[2] if len(p) > 2 else 1.0) for p in pts]
        sp = b["special"]
        if sp in ("particle", "sketch", "hatching", "curve", "grid", "shape", "grass"): return getattr(self, "_" + sp)(pts, color, size, opacity)
        # resample along the path at the brush's spacing
        out = []; step = max(1.0, size * b["spacing"])
        for (x0, y0, p0), (x1, y1, p1) in zip(pts, pts[1:]):
            d = math.hypot(x1 - x0, y1 - y0); n = max(1, int(d / step))
            for i in range(n): t = i / n; out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, p0 + (p1 - p0) * t, math.atan2(y1 - y0, x1 - x0)))
        if not out: out = [(pts[0][0], pts[0][1], pts[0][2], 0.0)]
        N = len(out); src = None
        if sp == "clone": src = self.a.copy()
        for i, (x, y, p, ang) in enumerate(out):
            t = i / max(1, N - 1); pr = p * (math.sin(math.pi * t) ** 0.6 if b["taper"] else 1.0)
            s = max(2, int(size * b["size_scale"] * pr * (1 + self.rng.uniform(-b["jitter_size"], b["jitter_size"]) if b["jitter_size"] else 1)))
            ta = dict(b["tipargs"])
            if b["angle_follow"]: ta["angle"] = ang + math.pi / 2 + ta.get("angle", 0)
            if b["jitter_angle"]: ta["angle"] = ta.get("angle", 0) + self.rng.uniform(-b["jitter_angle"], b["jitter_angle"])
            if b["tip"] in (tip_bristles, tip_sponge): ta["seed"] = 7
            mask = b["tip"](s, **ta).astype(np.float32)
            dx = dy = 0
            if b["scatter"]: dx, dy = self.rng.gauss(0, b["scatter"] * size * 0.4), self.rng.gauss(0, b["scatter"] * size * 0.4)
            col = np.asarray(color, np.float32)
            if b["color_jitter"]: col = np.clip(col * (1 + self.rng.uniform(-b["color_jitter"], b["color_jitter"])), 0, 255)
            if sp == "smudge":                                           # drag the colour under the brush along
                if i: self._dab(x, y, mask, self.a[int(np.clip(out[i - 1][1], 0, self.h - 1)), int(np.clip(out[i - 1][0], 0, self.w - 1))], 0.6 * opacity, "normal", 0)
                continue
            if sp == "blur":
                x0, y0 = int(x - s), int(y - s); x1, y1 = int(x + s), int(y + s); x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(self.w, x1), min(self.h, y1)
                if x1 > x0 + 2 and y1 > y0 + 2:
                    from scipy.ndimage import uniform_filter
                    reg = self.a[y0:y1, x0:x1]; bl = np.stack([uniform_filter(reg[..., c], 5) for c in range(3)], -1)
                    mm = tip_soft(max(y1 - y0, x1 - x0))[:y1 - y0, :x1 - x0][..., None] * opacity; self.a[y0:y1, x0:x1] = reg * (1 - mm) + bl * mm
                continue
            if sp == "deform":                                           # push paint in the stroke direction
                if i:
                    px, py = out[i - 1][0], out[i - 1][1]; x0, y0 = int(px - s / 2), int(py - s / 2)
                    if 0 <= x0 and 0 <= y0 and x0 + s < self.w and y0 + s < self.h:
                        reg = self.a[y0:y0 + s, x0:x0 + s].copy(); tx, ty = int(x - s / 2), int(y - s / 2)
                        if 0 <= tx and 0 <= ty and tx + s < self.w and ty + s < self.h:
                            mm = mask[..., None] * 0.5 * opacity; self.a[ty:ty + s, tx:tx + s] = self.a[ty:ty + s, tx:tx + s] * (1 - mm) + reg * mm
                continue
            if sp == "clone":                                            # stamp from an offset source
                sx, sy = int(x - 140), int(y)
                if 0 <= sx - s // 2 and sx + s // 2 < self.w:
                    reg = src[max(0, sy - s // 2):max(0, sy - s // 2) + s, sx - s // 2:sx - s // 2 + s]
                    if reg.shape[:2] == mask.shape: self._dab(x, y, mask, reg.mean((0, 1)), opacity, "normal", 0)
                continue
            if sp == "spray":
                for _ in range(10):
                    rr = size * 0.7; ox, oy = self.rng.gauss(0, rr * 0.5), self.rng.gauss(0, rr * 0.5); ds = max(2, int(self.rng.uniform(1, 4)))
                    self._dab(x + ox, y + oy, tip_round(ds, hard=1), col, b["flow"] * opacity, "normal", 0)
                continue
            self._dab(x + dx, y + dy, mask, col, b["flow"] * opacity, b["mode"], b["grain"])
            if sp == "knife":                                            # palette knife: hard edge streaked with the paint beneath
                self._dab(x + dx + 2, y + dy + 2, mask * 0.4, np.clip(col * 1.25, 0, 255), 0.5 * opacity, "normal", 0.5)
        if sp == "wet_edge":                                             # watercolour pools darker at the stroke edge
            self._edge_darken(out, size, color, opacity)
        if sp == "impasto":                                              # thick paint catches light on one side
            for (x, y, p, ang) in out[::3]:
                self._dab(x - size * 0.12, y - size * 0.12, tip_ellipse(max(3, int(size * 0.5)), aspect=0.2, angle=ang + math.pi / 2), (255, 250, 240), 0.18 * opacity, "normal", 0.3)

    def _edge_darken(self, out, size, color, opacity):
        from scipy.ndimage import gaussian_filter, binary_erosion
        fp = np.zeros((self.h, self.w), np.float32)
        for x, y, p, ang in out:
            r = size * 0.45; x0, x1 = int(max(0, x - r)), int(min(self.w, x + r)); y0, y1 = int(max(0, y - r)), int(min(self.h, y + r))
            if x1 > x0 and y1 > y0:
                yy, xx = np.mgrid[y0:y1, x0:x1]; fp[y0:y1, x0:x1] = np.maximum(fp[y0:y1, x0:x1], ((xx - x) ** 2 + (yy - y) ** 2 <= r * r))
        edge = np.clip(gaussian_filter(fp, 3) - gaussian_filter(binary_erosion(fp > 0.5, iterations=5).astype(np.float32), 3), 0, 1) * 0.2 * opacity
        self.a = self.a * (1 - edge[..., None]) + self.a * (np.asarray(color, np.float32) / 255) * edge[..., None]

    def _particle(self, pts, color, size, opacity):
        for x, y, p in pts[::2]:
            for k in range(6):
                a = self.rng.uniform(0, 2 * math.pi); vx, vy = math.cos(a) * 2, math.sin(a) * 2; px, py = x, y
                for t in range(int(size * 0.45)):
                    vx += self.rng.gauss(0, 0.4); vy += self.rng.gauss(0, 0.4); px += vx; py += vy
                    self._dab(px, py, tip_round(2, hard=1), color, 0.5 * opacity, "normal", 0)

    def _sketch(self, pts, color, size, opacity):
        hist = []
        for x, y, p in pts:
            for hx, hy in hist[-60:]:
                d = math.hypot(x - hx, y - hy)
                if d < size * 1.2 and self.rng.random() < 0.3: self._line(x, y, hx, hy, color, 0.15 * opacity, 1)
            hist.append((x, y)); self._line(x, y, *(hist[-2] if len(hist) > 1 else (x, y)), color, opacity, 2)

    def _hatching(self, pts, color, size, opacity):
        for x, y, p in pts[::3]:
            for k in range(-2, 3):
                ox = k * size * 0.22; self._line(x + ox - size * 0.3, y + size * 0.3, x + ox + size * 0.3, y - size * 0.3, color, 0.7 * opacity, 1)

    def _curve(self, pts, color, size, opacity):
        for (x0, y0, _), (x1, y1, _) in zip(pts[::4], pts[4::4]):
            mx, my = (x0 + x1) / 2 + self.rng.gauss(0, size), (y0 + y1) / 2 + self.rng.gauss(0, size); prev = (x0, y0)
            for t in np.linspace(0, 1, 12):
                bx = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t * t * x1; by = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * my + t * t * y1
                self._line(prev[0], prev[1], bx, by, color, 0.6 * opacity, 1); prev = (bx, by)

    def _grid(self, pts, color, size, opacity):
        cell = max(6, int(size * 0.5)); done = set()
        for x, y, p in pts:
            gx, gy = int(x // cell), int(y // cell)
            if (gx, gy) in done: continue
            done.add((gx, gy)); m = np.ones((cell - 2, cell - 2), np.float32)
            self._dab(gx * cell + cell / 2, gy * cell + cell / 2, m, np.clip(np.asarray(color) * self.rng.uniform(0.85, 1.15), 0, 255), opacity, "normal", 0)

    def _shape(self, pts, color, size, opacity):
        from PIL import ImageDraw
        layer = Image.new("L", (self.w, self.h), 0); ImageDraw.Draw(layer).polygon([(x, y) for x, y, p in pts], fill=255)
        m = np.asarray(layer, np.float32) / 255 * opacity; self._blend(0, self.h, 0, self.w, m, color, "normal")

    def _grass(self, pts, color, size, opacity):
        for x, y, p in pts[::2]:
            for k in range(5):
                ang = self.rng.gauss(0, 0.3); L = size * self.rng.uniform(0.6, 1.4); prev = (x, y); w0 = max(1, size * 0.08)
                for t in np.linspace(0.1, 1, 8):
                    px, py = x + math.sin(ang + 0.4 * t * t) * L * t, y - math.cos(ang) * L * t
                    self._line(prev[0], prev[1], px, py, np.clip(np.asarray(color) * self.rng.uniform(0.75, 1.25), 0, 255), opacity, max(1, int(w0 * (1 - t) + 1))); prev = (px, py)

    def _line(self, x0, y0, x1, y1, color, alpha, width):
        d = math.hypot(x1 - x0, y1 - y0); n = max(1, int(d)); m = tip_round(max(2, width + 1), hard=1)
        for i in range(n + 1):
            t = i / n; self._dab(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, m, color, alpha, "normal", 0)

def sampler(path, cols=4):
    """one swatch per brush: a wavy test stroke with the brush's name"""
    from PIL import ImageDraw, ImageFont
    import os
    names = list(B); rows = (len(names) + cols - 1) // cols; cw, ch = 420, 150
    cv = Canvas(cols * cw, rows * ch, paper=(244, 238, 226))
    # a dark band behind half of each cell so blend modes / smudge / glow have something to act on
    for i, n in enumerate(names):
        cx, cy = (i % cols) * cw, (i // cols) * ch
        cv.a[cy + 40:cy + 140, cx + 210:cx + 410] = np.array([70, 90, 140], np.float32)
        pts = [(cx + 30 + t * 360, cy + 90 + math.sin(t * 6.3) * 28, 0.4 + 0.6 * math.sin(math.pi * t)) for t in np.linspace(0, 1, 40)]
        col = (196, 92, 44) if n not in ("glow (dodge)",) else (255, 210, 120)
        cv.stroke(pts, n, color=col, size=34 if n not in ("ink pen", "pencil", "script", "liner (rigger)") else 14, opacity=1.0)
    img = cv.image(); d = ImageDraw.Draw(img)
    fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "EBGaramond-SemiBold.ttf"); f = ImageFont.truetype(fp, 24)
    for i, n in enumerate(names): d.text(((i % cols) * cw + 12, (i // cols) * ch + 6), n, font=f, fill=(40, 30, 30))
    img.save(path); return len(names)

if __name__ == "__main__":
    import sys; print(sampler(sys.argv[1] if len(sys.argv) > 1 else "brush_sampler.png"), "brushes")
