"""
brush_art.py: the pictures the brush engine paints with, made once and kept: seamless textures and patterns (canvas-space, so
strokes join up), the little shapes the decorative brushes scatter, and the stamp pictures (images/UI/Stamps/<Name>.png).

    texture("wood")  -> 256 x 256 float array, 0..1, tiles seamlessly
    pattern("dots")  -> 64 x 64 float array, 0..1 (1 = the motif)
    shape_mask("star", 40, angle) -> 40 x 40 float mask
    stamp("Heart", 80, angle) -> (mask, rgb) or None
"""
import math, os
import numpy as np
from PIL import Image, ImageDraw

N = 256                                                                  # texture tile size (pixels)
_cache = {}

def _keep(key, make):
    v = _cache.get(key)
    if v is None:
        v = _cache[key] = make()
        if len(_cache) > 3000: _cache.clear(); _cache[key] = v
    return v

# ---------------------------------------------------------------- seamless noise helpers
def _blur(a, s):
    from scipy.ndimage import gaussian_filter
    return gaussian_filter(a, s, mode="wrap")

def _norm(a):
    lo, hi = float(a.min()), float(a.max()); return ((a - lo) / max(hi - lo, 1e-6)).astype(np.float32)

def _noise(seed, sigma, n=N):
    return _norm(_blur(np.random.default_rng(seed).random((n, n)).astype(np.float32), sigma))

def _fbm(seed, octaves=5, base=24.0, n=N):
    out = np.zeros((n, n), np.float32); amp = 1.0; tot = 0.0; s = base
    for o in range(octaves): out += _noise(seed + o, max(0.6, s), n) * amp; tot += amp; amp *= 0.55; s /= 2
    return _norm(out / tot)

def _voronoi(seed, cells, n=N):
    """distance to the nearest and second-nearest cell centre (seamless), and which cell"""
    rng = np.random.default_rng(seed); pts = rng.random((cells, 2)) * n
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32); d1 = np.full((n, n), 1e9, np.float32); d2 = d1.copy(); idx = np.zeros((n, n), np.int32)
    for i, (px, py) in enumerate(pts):
        dx = np.abs(xx - px); dx = np.minimum(dx, n - dx); dy = np.abs(yy - py); dy = np.minimum(dy, n - dy); d = np.sqrt(dx * dx + dy * dy)
        closer = d < d1; d2 = np.where(closer, d1, np.minimum(d2, d)); idx = np.where(closer, i, idx); d1 = np.where(closer, d, d1)
    return d1, d2, idx

# ---------------------------------------------------------------- textures (0 = dark, 1 = light)
def _tex(name):
    n = N; yy, xx = np.mgrid[0:n, 0:n].astype(np.float32); t = 2 * math.pi / n
    if name in ("grain",): return _norm(0.7 * _noise(1, 0.6) + 0.3 * _noise(2, 3))
    if name in ("noise",): return _noise(3, 0.8)
    if name == "sand":
        g = _noise(4, 0.5); specks = (np.random.default_rng(5).random((n, n)) > 0.985).astype(np.float32)
        return _norm(np.clip(g * 1.6 - 0.3, 0, 1) * 0.8 + _blur(specks, 0.6) * 2)
    if name in ("spraytex", "spray"):
        d = (np.random.default_rng(6).random((n, n)) > 0.93).astype(np.float32); return _norm(_blur(d, 0.7))
    if name in ("fabric",):
        warp = 0.5 + 0.5 * np.sin(xx * t * 48); weft = 0.5 + 0.5 * np.sin(yy * t * 48)
        over = (np.floor(xx / (n / 48)) + np.floor(yy / (n / 48))) % 2
        return _norm(np.where(over > 0, warp, weft) * 0.8 + _noise(7, 1) * 0.2)
    if name in ("canvas",):
        a = 0.5 + 0.5 * np.sin((xx + yy) * t * 32); b = 0.5 + 0.5 * np.sin((xx - yy) * t * 32)
        return _norm(0.45 * a + 0.45 * b + 0.25 * _noise(8, 0.8))
    if name in ("paper",): return _norm(0.55 * _noise(9, 1.0) + 0.45 * _fbm(10, 4, 12))
    if name in ("grunge",):
        f = _fbm(11, 5, 30); s = _noise(12, 1.2); return _norm(np.clip((f - 0.35) * 2.2, 0, 1) * 0.75 + s * 0.25)
    if name in ("concrete",):
        f = _fbm(13, 5, 10); pits = (np.random.default_rng(14).random((n, n)) > 0.992).astype(np.float32)
        return _norm(f * 0.8 + _noise(15, 0.7) * 0.25 - _blur(pits, 1.2) * 3)
    if name in ("rust",):
        f = _fbm(16, 5, 20); b = _fbm(17, 3, 40); return _norm(np.clip(f * 1.4 - 0.2, 0, 1) * 0.6 + b * 0.25 + _noise(18, 0.6) * 0.15)
    if name in ("mosaic", "tiles_m"):
        d1, d2, idx = _voronoi(19, 70); shade = np.random.default_rng(20).uniform(0.45, 1.0, 70)[idx]
        return np.where(d2 - d1 < 2.2, 0.08, shade).astype(np.float32)
    if name in ("crackle",):
        d1, d2, idx = _voronoi(21, 55); crack = np.clip((d2 - d1) / 3.0, 0, 1); return _norm(crack * 0.85 + _noise(22, 1.2) * 0.15)
    if name in ("wood",):
        w = np.sin((yy * t * 10) + _fbm(23, 4, 30) * 9 + np.sin(xx * t * 2) * 1.5); grain = _noise(24, 0.6)
        return _norm((0.5 + 0.5 * w) ** 1.6 * 0.8 + grain * 0.2)
    if name in ("brick",):
        bh, bw = n / 8, n / 4; row = np.floor(yy / bh); xo = (xx + (row % 2) * bw / 2) % bw; yo = yy % bh
        mortar = (xo < 3) | (yo < 3); face = 0.65 + 0.35 * np.random.default_rng(25).random((8, 9))[row.astype(int) % 8, np.floor((xx + (row % 2) * bw / 2) / bw).astype(int) % 9]
        return _norm(np.where(mortar, 0.15, face * (0.85 + 0.15 * _noise(26, 1))))
    if name in ("metal",):
        streak = _norm(_blur(np.random.default_rng(27).random((n, n)).astype(np.float32), (0.4, 18))); sheen = 0.5 + 0.5 * np.cos(yy * t * 1)
        return _norm(streak * 0.55 + sheen * 0.45)
    if name in ("stone",):
        d1, d2, idx = _voronoi(28, 26); body = np.random.default_rng(29).uniform(0.5, 0.95, 26)[idx]
        edge = np.clip((d2 - d1) / 6, 0, 1); return _norm(body * (0.35 + 0.65 * edge) * (0.8 + 0.2 * _fbm(30, 4, 8)))
    if name in ("clouds",): return _fbm(31, 6, 40)
    if name in ("water",):
        f = _fbm(32, 4, 30); r = np.sin(yy * t * 12 + f * 6) * np.sin(xx * t * 4 + f * 3); return _norm(0.6 + 0.4 * r)
    if name in ("tiles",):
        s = n / 8; xo, yo = xx % s, yy % s; grout = (xo < 3) | (yo < 3)
        bevel = np.clip(np.minimum(np.minimum(xo, s - xo), np.minimum(yo, s - yo)) / 6, 0, 1)
        return np.where(grout, 0.2, 0.55 + 0.45 * bevel).astype(np.float32)
    if name in ("bokeh",): return _noise(33, 2)
    return _noise(99, 1)

def texture(name): return _keep(("tex", name), lambda: _tex(name))

# the natural colour of each material (Adjustments > Textures: Their own colors)
TEX_COLORS = {"canvas": (226, 212, 182), "fabric": (110, 92, 160), "wood": (150, 96, 52), "brick": (168, 74, 52), "metal": (158, 164, 174),
              "stone": (140, 134, 122), "paper": (236, 226, 204), "grunge": (96, 86, 72), "noise": (128, 128, 128), "clouds": (178, 206, 240),
              "water": (46, 120, 196), "tiles": (206, 216, 226)}

# ---------------------------------------------------------------- patterns (1 = the motif, in your colour)
P = 64                                                                   # pattern repeat (pixels)
def _pat(name):
    S = 4; n = P * S; im = Image.new("L", (n, n), 0); d = ImageDraw.Draw(im)
    def each(f):                                                        # draw a motif and its wrap-around copies, so it tiles
        for ox in (-n, 0, n):
            for oy in (-n, 0, n): f(ox, oy)
    if name == "dots":
        each(lambda ox, oy: [d.ellipse((ox + x - 9 * S, oy + y - 9 * S, ox + x + 9 * S, oy + y + 9 * S), fill=255) for x, y in ((n / 4, n / 4), (3 * n / 4, 3 * n / 4))])
    elif name == "stripes":
        for k in range(-4, 8): d.polygon([(k * n / 4, 0), (k * n / 4 + n / 8, 0), (k * n / 4 + n / 8 - n, n), (k * n / 4 - n, n)], fill=255)
    elif name == "checks":
        d.rectangle((0, 0, n / 2 - 1, n / 2 - 1), fill=255); d.rectangle((n / 2, n / 2, n - 1, n - 1), fill=255)
    elif name == "plaid":
        a = np.zeros((n, n), np.float32); b = np.arange(n)
        for c0, w, v in ((0, n / 5, 0.55), (n / 2, n / 12, 0.9), (0.72 * n, n / 30, 1.0)):
            band = ((b - c0) % n < w).astype(np.float32) * v; a = np.maximum(a, np.maximum(band[None, :], band[:, None]) * 0.7)
            a = np.maximum(a, band[None, :] * band[:, None])
        return np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((P, P), Image.LANCZOS), np.float32) / 255
    elif name in ("hearts", "stars", "flowers"):
        r = 12 * S
        def motif(ox, oy, x, y):
            if name == "hearts":
                d.ellipse((ox + x - r, oy + y - r * 0.8, ox + x, oy + y + r * 0.2), fill=255); d.ellipse((ox + x, oy + y - r * 0.8, ox + x + r, oy + y + r * 0.2), fill=255)
                d.polygon([(ox + x - r * 0.97, oy + y - r * 0.2), (ox + x + r * 0.97, oy + y - r * 0.2), (ox + x, oy + y + r)], fill=255)
            elif name == "stars":
                d.polygon([(ox + x + math.cos(-math.pi / 2 + i * math.pi / 5) * (r if i % 2 == 0 else r * 0.42), oy + y + math.sin(-math.pi / 2 + i * math.pi / 5) * (r if i % 2 == 0 else r * 0.42)) for i in range(10)], fill=255)
            else:
                for k in range(5):
                    a2 = k * 2 * math.pi / 5; cx, cy = ox + x + math.cos(a2) * r * 0.55, oy + y + math.sin(a2) * r * 0.55; d.ellipse((cx - r * 0.45, cy - r * 0.45, cx + r * 0.45, cy + r * 0.45), fill=255)
                d.ellipse((ox + x - r * 0.3, oy + y - r * 0.3, ox + x + r * 0.3, oy + y + r * 0.3), fill=0)
        each(lambda ox, oy: [motif(ox, oy, x, y) for x, y in ((n / 4, n / 4), (3 * n / 4, 3 * n / 4))])
    elif name == "circles":
        each(lambda ox, oy: [d.ellipse((ox + x - 13 * S, oy + y - 13 * S, ox + x + 13 * S, oy + y + 13 * S), outline=255, width=4 * S) for x, y in ((n / 4, n / 4), (3 * n / 4, 3 * n / 4))])
    elif name == "diamonds":
        each(lambda ox, oy: d.polygon([(ox + n / 2, oy + 4 * S), (ox + n - 4 * S, oy + n / 2), (ox + n / 2, oy + n - 4 * S), (ox + 4 * S, oy + n / 2)], fill=255))
    elif name == "chevron":
        for k in range(-1, 3):
            y0 = k * n / 2; w = n / 6
            d.polygon([(0, y0), (n / 2, y0 + n / 4), (n, y0), (n, y0 + w), (n / 2, y0 + n / 4 + w), (0, y0 + w)], fill=255)
    elif name == "waves":
        for k in range(-1, 3):
            pts = [(x, k * n / 2 + n / 4 + math.sin(x / n * 2 * math.pi) * n / 8) for x in np.linspace(0, n, 64)]
            d.line(pts, fill=255, width=int(n / 10))
    else: d.ellipse((n / 4, n / 4, 3 * n / 4, 3 * n / 4), fill=255)
    return np.asarray(im.resize((P, P), Image.LANCZOS), np.float32) / 255

def pattern(name): return _keep(("pat", name), lambda: _pat(name))

# ---------------------------------------------------------------- decorative shapes (one mask per size / angle, cached)
def _shape(kind, s, ang):
    S = 3; n = max(4, s * S); im = Image.new("L", (n, n), 0); d = ImageDraw.Draw(im); x = y = n / 2; r = n * 0.46
    rot = lambda u, v: (x + u * math.cos(ang) - v * math.sin(ang), y + u * math.sin(ang) + v * math.cos(ang))
    if kind == "star":
        d.polygon([rot(math.cos(-math.pi / 2 + i * math.pi / 5) * (r if i % 2 == 0 else r * 0.42), math.sin(-math.pi / 2 + i * math.pi / 5) * (r if i % 2 == 0 else r * 0.42)) for i in range(10)], fill=255)
    elif kind == "heart":
        pts = [rot(r * 0.95 * 16 * math.sin(t) ** 3 / 16, -r * 0.95 * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) / 16) for t in np.linspace(0, 2 * math.pi, 60)]
        d.polygon(pts, fill=255)
    elif kind == "sparkle":
        pts = []
        for i in range(8): rr = r if i % 2 == 0 else r * 0.16; a2 = i * math.pi / 4; pts.append(rot(math.cos(a2) * rr, math.sin(a2) * rr))
        d.polygon(pts, fill=255)
    elif kind in ("petal", "leaf"):
        w = 0.42 if kind == "leaf" else 0.55; d.polygon([rot(math.cos(t) * r, math.sin(t) * r * w * (1 - 0.35 * math.cos(t))) for t in np.linspace(0, 2 * math.pi, 40)], fill=255)
        if kind == "leaf": d.line([rot(-r, 0), rot(r, 0)], fill=110, width=max(1, int(n / 22)))
    elif kind == "snow":
        for k in range(6):
            a2 = k * math.pi / 3; d.line([rot(0, 0), rot(math.cos(a2) * r, math.sin(a2) * r)], fill=255, width=max(1, int(n / 12)))
            for f in (0.55,):
                bx, by = math.cos(a2) * r * f, math.sin(a2) * r * f
                for s2 in (-1, 1):
                    a3 = a2 + s2 * 0.7; d.line([rot(bx, by), rot(bx + math.cos(a3) * r * 0.32, by + math.sin(a3) * r * 0.32)], fill=255, width=max(1, int(n / 16)))
    elif kind == "bubble":
        d.ellipse((x - r, y - r, x + r, y + r), fill=70, outline=255, width=max(1, int(n / 14)))
        d.ellipse((x - r * 0.55, y - r * 0.6, x - r * 0.15, y - r * 0.25), fill=255)
    elif kind == "confetti":
        d.polygon([rot(-r, -r * 0.4), rot(r, -r * 0.4), rot(r, r * 0.4), rot(-r, r * 0.4)], fill=255)
    elif kind == "diamond":
        d.polygon([rot(0, -r), rot(r * 0.6, 0), rot(0, r), rot(-r * 0.6, 0)], fill=255)
    elif kind == "bokeh":
        d.ellipse((x - r, y - r, x + r, y + r), fill=110, outline=230, width=max(1, int(n / 18)))
    else: d.ellipse((x - r, y - r, x + r, y + r), fill=255)               # dot
    return np.asarray(im.resize((s, s), Image.LANCZOS), np.float32) / 255

def shape_mask(kind, s, ang=0.0):
    a = round(ang / 0.06) * 0.06; return _keep(("shape", kind, s, a), lambda: _shape(kind, s, a))

# ---------------------------------------------------------------- stamps
def _stamp_dir():
    try:
        import paths; return paths.ui("Stamps")
    except Exception: return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "images", "UI", "Stamps")

def stamp_names():
    """every stamp picture there is, by name ("Christmas Tree")"""
    try: return sorted(os.path.splitext(f)[0].replace("_", " ") for f in os.listdir(_stamp_dir()) if f.lower().endswith(".png"))
    except OSError: return []

def sticker_dir():
    try:
        import paths; return paths.data("stickers")
    except Exception: return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "stickers")

def _stamp_src(name):
    if name.startswith("sticker:"): p = os.path.join(sticker_dir(), name[8:])              # your stickers (cut-outs), kept beside the app
    else: p = os.path.join(_stamp_dir(), name.replace(" ", "_") + ".png")
    try: return Image.open(p).convert("RGBA")
    except Exception:
        try: import prefs; prefs.log_note("loading a stamp picture", p)
        except Exception: pass
        return None

def stamp(name, s, ang=0.0):
    """the stamp at size s (its longest side), turned by ang: (alpha mask, RGB colours), or None if it's missing"""
    a = round(ang / 0.05) * 0.05
    def make():
        im = _keep(("stampsrc", name), lambda: _stamp_src(name) or False)
        if im is False: return False
        r = im.resize((max(2, s), max(2, s)), Image.LANCZOS)
        if a: r = r.rotate(-math.degrees(a), resample=Image.BICUBIC)
        arr = np.asarray(r, np.float32); return (arr[..., 3] / 255, arr[..., :3])
    v = _keep(("stamp", name, s, a), make)
    return None if v is False else v
