"""
styles_fx.py: Instant Easel's art styles. Each style turns any image (an engine painting or your picture) into that look.
    from styles_fx import apply, STYLES
    out = apply(img, "Pop Art")
The four classic mediums (Oil Painting, Watercolor, Pastel, Pencil Sketch) use img2img's brush engine.
"""
import math, random
import numpy as np
from PIL import Image, ImageFilter, ImageOps, ImageDraw, ImageChops

STYLES = ["Painterly", "Realism", "Oil Painting", "Watercolor", "Pastel", "Pencil Sketch", "Black and White", "Cartoon", "Anime",
          "Comic Book", "Pop Art", "Street Art", "Pixel Art", "Abstract", "Impressionist", "Stained Glass", "Woodblock Print", "Neon", "Low Poly"]
MEDIUM = {"Oil Painting": "oil", "Watercolor": "watercolor", "Pastel": "pastel", "Pencil Sketch": "ink sketch"}
ALIASES = {"painterly": "Painterly", "oil": "Oil Painting", "watercolor": "Watercolor", "pastel": "Pastel", "ink sketch": "Pencil Sketch"}

def _lum(a): return a @ np.array([0.299, 0.587, 0.114], np.float32)

def _smooth(img, n=3, size=5):
    for _ in range(n): img = img.filter(ImageFilter.MedianFilter(size))
    return img

def _edges(img, thresh=40, thick=1):
    g = ImageOps.grayscale(img).filter(ImageFilter.GaussianBlur(1.2)); e = np.asarray(g.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    m = Image.fromarray(((e > thresh) * 255).astype(np.uint8))
    for _ in range(thick): m = m.filter(ImageFilter.MaxFilter(3))
    return np.asarray(m, dtype=np.float32)[..., None] / 255

def _quant(img, n): return img.quantize(colors=n, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")

def _voronoi(img, n, seed=3):
    from scipy.spatial import cKDTree
    a = np.asarray(img, dtype=np.float32); h, w = a.shape[:2]; rng = np.random.default_rng(seed)
    pts = np.stack([rng.uniform(0, w, n), rng.uniform(0, h, n)], 1); yy, xx = np.mgrid[0:h, 0:w]
    d, idx = cKDTree(pts).query(np.stack([xx.ravel(), yy.ravel()], 1), k=2); idx1 = idx[:, 0].reshape(h, w)
    cols = np.zeros((n, 3), np.float32); cnt = np.bincount(idx1.ravel(), minlength=n).astype(np.float32)[:, None]
    for c in range(3): cols[:, c] = np.bincount(idx1.ravel(), weights=a[..., c].ravel(), minlength=n)
    cols /= np.maximum(cnt, 1); border = (d[:, 1] - d[:, 0]).reshape(h, w)
    return cols[idx1], border, idx1

def apply(img, style, seed=3):
    style = ALIASES.get(style, style); img = img.convert("RGB"); w, h = img.size; s = max(w, h) / 1600; rng = np.random.default_rng(seed)
    if style in (None, "", "Painterly"): return img
    if style in MEDIUM:
        import img2img; out = img2img.render(img, "", 0.8, MEDIUM[style], "keep", seed=seed)[0].resize((w, h))
        if style == "Watercolor":                            # watercolour stays clear and colourful, not grey
            b = np.asarray(out, dtype=np.float32); L = _lum(b)[..., None]; b = np.clip(L + (b - L) * 1.7 + 6, 0, 255); out = Image.fromarray(b.astype(np.uint8))
        return out
    a = np.asarray(img, dtype=np.float32)
    if style == "Realism":                                   # refined detail, natural colour, gentle depth
        out = img.filter(ImageFilter.UnsharpMask(radius=2 * s + 1, percent=90, threshold=2)).filter(ImageFilter.UnsharpMask(radius=12 * s + 2, percent=25, threshold=3))
        b = np.asarray(out, dtype=np.float32); L = _lum(b)[..., None]; b = L + (b - L) * 0.92; return Image.fromarray(np.clip(b, 0, 255).astype(np.uint8))
    if style == "Black and White":                           # red-filter monochrome: dramatic skies, rich tones, fine grain
        L = a[..., 0] * 0.55 + a[..., 1] * 0.35 + a[..., 2] * 0.10; L = (L / 255 - 0.5) * 1.25 + 0.5
        L = np.clip(L + rng.normal(0, 0.018, L.shape), 0, 1) * 255; return Image.fromarray(L.astype(np.uint8)).convert("RGB")
    if style == "Cartoon":                                   # flat colour areas + bold outlines
        flat = np.asarray(_quant(_smooth(img, 3, 7), 14), dtype=np.float32); L = _lum(flat)[..., None]; flat = np.clip(L + (flat - L) * 1.35, 0, 255)
        e = _edges(_smooth(img, 2, 5), 30, max(1, int(2 * s))); return Image.fromarray((flat * (1 - e) + 20 * e).astype(np.uint8))
    if style == "Anime":                                     # cel shading: 3 light bands per colour, vivid, clean thin lines
        sm = np.asarray(_smooth(img, 3, 5), dtype=np.float32); L = _lum(sm)[..., None] / 255
        band = np.where(L > 0.66, 1.12, np.where(L > 0.36, 0.86, 0.58)); hue = sm / (L * 255 + 1e-3)
        cel = np.clip(hue * band * 190, 0, 255); Lc = _lum(cel)[..., None]; cel = np.clip(Lc + (cel - Lc) * 1.3, 0, 255)
        deep = np.clip((0.16 - L) / 0.08, 0, 1)                                          # keep the deepest shadows (silhouettes) dark
        cel = cel * (1 - deep) + sm * 0.6 * deep
        e = _edges(Image.fromarray(sm.astype(np.uint8)), 45, 1); return Image.fromarray((cel * (1 - e * 0.85) + 40 * e * 0.85).astype(np.uint8))
    if style == "Comic Book":                                # ink outlines + halftone dots in the shadows
        flat = np.asarray(_quant(_smooth(img, 2, 5), 10), dtype=np.float32); L = _lum(flat) / 255
        yy, xx = np.mgrid[0:h, 0:w]; p = max(5, int(8 * s)); cx, cy = (xx % p) - p / 2, (yy % p) - p / 2
        dots = (np.sqrt(cx ** 2 + cy ** 2) < (1 - L) * p * 0.55)[..., None] & (L < 0.6)[..., None]
        out = np.where(dots, flat * 0.35, flat); e = _edges(img, 28, max(1, int(2 * s))); return Image.fromarray((out * (1 - e) + 10 * e).astype(np.uint8))
    if style == "Pop Art":                                   # bold flat pop palette + Ben-Day dots + black outlines
        L = _lum(np.asarray(_smooth(img, 2, 5), dtype=np.float32)) / 255; pal = np.array([[18, 18, 24], [228, 32, 52], [36, 92, 220], [255, 106, 180], [255, 220, 20], [250, 246, 236]], np.float32)
        idx = np.clip((L * 5.99).astype(int), 0, 5); out = pal[idx]
        yy, xx = np.mgrid[0:h, 0:w]; p = max(8, int(12 * s)); d = np.sqrt(((xx % p) - p / 2) ** 2 + ((yy + (xx // p % 2) * p / 2) % p - p / 2) ** 2)
        dots = (d < p * 0.28)[..., None] & ((idx == 3) | (idx == 4))[..., None]; out = np.where(dots, out * 0.82 + np.array([255, 255, 255]) * 0.18, out)
        e = _edges(img, 30, max(2, int(3 * s))); return Image.fromarray((out * (1 - e) + 12 * e).astype(np.uint8))
    if style == "Street Art":                                # graffiti: saturated poster colours, spray speckle, drips, on a wall
        flat = np.asarray(_quant(_smooth(img, 2, 5), 8), dtype=np.float32); L = _lum(flat)[..., None]; flat = np.clip(L + (flat - L) * 1.7, 0, 255)
        wall = 150 + 30 * rng.random((h, w, 1)).astype(np.float32) + 18 * np.asarray(Image.fromarray((rng.random((h // 8 + 1, w // 8 + 1)) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), dtype=np.float32)[..., None] / 255
        Lw = _lum(flat) / 255; paint = (Lw < 0.62)[..., None]                       # light areas stay bare wall
        halo = np.asarray(Image.fromarray((paint[..., 0] * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(9 * s)), dtype=np.float32)[..., None] / 255
        wallc = np.repeat(wall, 3, 2) * np.array([1.0, 0.97, 0.92]); sprayc = np.array([255, 70, 160], np.float32)
        out = np.where(paint, flat, wallc * (1 - halo * 0.55) + sprayc * halo * 0.55)       # spray-paint halo around the shapes
        speck = (rng.random((h, w, 1)) < 0.03) & paint; out = np.where(speck, out * 0.7, out)
        im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)); d = ImageDraw.Draw(im); dark = np.argwhere(Lw < 0.3)
        for _ in range(int(220 * s)):                         # paint drips under dark shapes
            if len(dark) == 0: break
            y, x = dark[rng.integers(len(dark))]; L_ = rng.uniform(30, 160) * s; ww = max(2, int(rng.uniform(2, 6) * s))
            col = tuple(int(c) for c in flat[y, x]); d.line([(x, y), (x, y + L_)], fill=col, width=ww); d.ellipse([x - ww, y + L_ - ww, x + ww, y + L_ + ww], fill=col)
        e = _edges(Image.fromarray(np.where(paint, flat, 255).astype(np.uint8)), 40, max(3, int(4 * s))); a2 = np.asarray(im, dtype=np.float32)
        return Image.fromarray((a2 * (1 - e) + 14 * e).astype(np.uint8))
    if style == "Pixel Art":                                 # chunky pixels, limited palette
        px = max(48, int(w / max(6, 10 * s))); small = img.resize((px, max(8, int(px * h / w))), Image.BOX); small = _quant(small, 24)
        return small.resize((w, h), Image.NEAREST)
    if style == "Abstract":                                  # big colour fields, bold shapes, a few gestural lines
        cols, border, idx = _voronoi(img.resize((w // 2, h // 2)), 70, seed); L = _lum(cols)[..., None]; cols = np.clip(L + (cols - L) * 1.8, 0, 255)
        im = Image.fromarray(cols.astype(np.uint8)).resize((w, h), Image.NEAREST); d = ImageDraw.Draw(im, "RGBA"); r = random.Random(seed)
        for _ in range(9):
            x, y, rad = r.uniform(0, w), r.uniform(0, h), r.uniform(40, 200) * s; c = tuple(int(v) for v in a[int(min(h - 1, y)), int(min(w - 1, x))]) + (150,)
            (d.ellipse if r.random() < 0.5 else d.rectangle)([x - rad, y - rad, x + rad, y + rad], fill=c)
        for _ in range(6): d.line([(r.uniform(0, w), r.uniform(0, h)), (r.uniform(0, w), r.uniform(0, h))], fill=(20, 20, 26, 220), width=int(max(3, 6 * s)))
        return im
    if style == "Impressionist":                             # short bright broken dabs
        import painter2 as P
        field = np.clip(a * 1.1 + 14, 0, 255); L = _lum(field)[..., None]; field = np.clip(L + (field - L) * 1.55, 0, 255)
        canvas = Image.fromarray(field.astype(np.uint8)).filter(ImageFilter.GaussianBlur(14 * s)); ang = np.full((h, w), 0.5, np.float32) + rng.normal(0, 0.7, (h, w)).astype(np.float32)
        n = (w * h) / 1.0e6
        P.strokes(canvas, field, ang, int(9000 * n), (14 * s, 30 * s), (7 * s, 13 * s), seed, jitter=34)
        P.strokes(canvas, field, ang, int(14000 * n), (8 * s, 16 * s), (4 * s, 8 * s), seed + 1, jitter=40); return canvas
    if style == "Stained Glass":                             # glowing panes, dark lead lines
        cols, border, _ = _voronoi(img, int(380 * (w * h) / 2.5e6) + 60, seed); L = _lum(cols)[..., None]; cols = np.clip(L + (cols - L) * 1.6, 0, 255) * 1.08
        lead = (border < 3 * s)[..., None]; return Image.fromarray(np.clip(np.where(lead, 22, cols), 0, 255).astype(np.uint8))
    if style == "Woodblock Print":                           # flat muted colours, navy outlines, paper and grain
        flat = np.asarray(_quant(_smooth(img, 3, 7), 8), dtype=np.float32); L = _lum(flat)[..., None]; flat = L + (flat - L) * 1.05
        flat = (flat - 128) * 1.2 + 128 + np.array([14, 10, 0], np.float32); grain = np.sin(np.arange(h)[:, None, None] * 0.35 + rng.normal(0, 0.8, (h, w, 1))) * 5
        paper = flat + grain + rng.normal(0, 3, (h, w, 1)); e = _edges(img, 32, max(2, int(2 * s)))
        return Image.fromarray(np.clip(paper * (1 - e) + np.array([30, 36, 62]) * e, 0, 255).astype(np.uint8))
    if style == "Neon":                                      # glowing edge lines on dark, synthwave colours
        e = _edges(_smooth(img, 1, 3), 22, max(1, int(s)))[..., 0]; yy = np.linspace(0, 1, h)[:, None]
        col = np.stack([255 * (1 - yy) + 30 * yy, 40 + 0 * yy, 200 * (1 - yy) + 255 * yy], -1) * np.ones((1, w, 1))
        line = e[..., None] * col; glow = np.asarray(Image.fromarray(np.clip(line, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6 * s)), dtype=np.float32)
        base = np.asarray(img, dtype=np.float32) * 0.12 + np.array([10, 4, 24]); return Image.fromarray(np.clip(base + glow * 1.8 + line, 0, 255).astype(np.uint8))
    if style == "Low Poly":                                  # faceted triangles
        from scipy.spatial import Delaunay
        n = int(900 * (w * h) / 2.5e6) + 150; g = np.asarray(ImageOps.grayscale(img).filter(ImageFilter.FIND_EDGES), dtype=np.float32)
        ys, xs = np.nonzero(g > 40); pick = rng.choice(len(xs), min(n, len(xs)), replace=False) if len(xs) else []
        pts = np.concatenate([np.stack([xs[pick], ys[pick]], 1) if len(xs) else np.zeros((0, 2)), rng.uniform(0, 1, (n // 2, 2)) * [w, h],
                              [[0, 0], [w - 1, 0], [0, h - 1], [w - 1, h - 1]]])
        tri = Delaunay(pts); im = Image.new("RGB", (w, h)); d = ImageDraw.Draw(im)
        for simp in tri.simplices:
            p = pts[simp]; c = a[int(np.clip(p[:, 1].mean(), 0, h - 1)), int(np.clip(p[:, 0].mean(), 0, w - 1))]
            d.polygon([tuple(q) for q in p], fill=tuple(int(v) for v in c))
        return im
    return img
