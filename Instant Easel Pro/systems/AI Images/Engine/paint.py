"""Painterly re-rendering: color-match a scene to the author's paintings, then repaint it in brushstrokes."""
import os, sys, random, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import paths; HERE = paths.APP
REFS = {"summit": os.path.join(HERE, "images", "Styles", "summit.jpg"), "warm": os.path.join(HERE, "images", "Styles", "sunset-field.jpg"), "night": os.path.join(HERE, "images", "Styles", "night-city.jpg")}   # copies of the author's paintings

def _lab(a):   # RGB [0..1] -> l-alpha-beta (Reinhard)
    a = np.clip(a, 1e-4, 1)
    M = np.array([[0.3811, 0.5783, 0.0402], [0.1967, 0.7244, 0.0782], [0.0241, 0.1288, 0.8444]])
    lms = np.log10(a @ M.T)
    B = np.array([[1/np.sqrt(3), 0, 0], [0, 1/np.sqrt(6), 0], [0, 0, 1/np.sqrt(2)]]) @ np.array([[1, 1, 1], [1, 1, -2], [1, -1, 0]])
    return lms @ B.T
def _rgb(l):
    B = np.array([[1, 1, 1], [1, 1, -1], [1, -2, 0]]) @ np.array([[np.sqrt(3)/3, 0, 0], [0, np.sqrt(6)/6, 0], [0, 0, np.sqrt(2)/2]])
    lms = 10 ** (l @ B.T)
    M = np.array([[4.4679, -3.5873, 0.1193], [-1.2186, 2.3809, -0.1624], [0.0497, -0.2439, 1.2045]])
    return np.clip(lms @ M.T, 0, 1)

def ref_path(kind):
    return REFS.get(kind, kind)

def color_match(img, kind, strength=0.8):
    a = np.asarray(img, dtype=np.float64) / 255; r = np.asarray(Image.open(ref_path(kind)).convert("RGB").resize((400, 600)), dtype=np.float64) / 255
    la, lr = _lab(a.reshape(-1, 3)), _lab(r.reshape(-1, 3))
    out = la.copy()
    ratio = np.minimum(lr[:, 1:].std(0) / (la[:, 1:].std(0) + 1e-6), 1.3)
    out[:, 1:] = (la[:, 1:] - la[:, 1:].mean(0)) * ratio + lr[:, 1:].mean(0)
    out[:, 0] = la[:, 0] + (lr[:, 0].mean() - la[:, 0].mean()) * 0.35
    out = _rgb(out).reshape(a.shape)
    return Image.fromarray((255 * (a * (1 - strength) + out * strength)).astype(np.uint8))

def add_variation(img, seed):
    """soft low-frequency color drift so flat areas get cloud-like brushwork"""
    rng = np.random.default_rng(seed); h, w = img.height, img.width
    n = rng.normal(0, 1, (h // 60 + 2, w // 60 + 2, 3)); n = Image.fromarray(np.uint8(np.clip(128 + 40 * n, 0, 255))).resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(20))
    a = np.asarray(img, dtype=np.int16) + (np.asarray(n, dtype=np.int16) - 128) // 3
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

def palette(kind, n=6):
    r = np.asarray(Image.open(ref_path(kind)).convert("RGB").resize((200, 300)), dtype=np.float32)[:170].reshape(-1, 3)
    lum = r.mean(1); order = np.argsort(lum); qs = np.linspace(0.15, 0.97, n)
    return [r[order[int(q * (len(order) - 1))]] for q in qs]

def clouds(img, kind, seed):
    rng = np.random.default_rng(seed); h, w = img.height, img.width
    f = np.zeros((h, w), np.float32)
    for o, amp in ((8, 1.0), (16, 0.5), (32, 0.25), (64, 0.12)):
        n = rng.normal(0, 1, (int(h / w * o) + 2, o + 2)).astype(np.float32)
        f += amp * np.asarray(Image.fromarray(n).resize((w, h), Image.BICUBIC))
    f = (f - f.min()) / (f.max() - f.min()); f = np.clip((f - 0.42) * 3.2, 0, 1)      # soft cloud bodies
    pal = palette(kind); idx = np.clip((f * (len(pal) - 1)).astype(int), 0, len(pal) - 1)
    col = np.stack(pal)[idx]
    a = np.asarray(img, dtype=np.float32); lum = a.mean(2)
    yfade = np.clip(1.2 - np.linspace(0, 1, h)[:, None] * 1.6, 0, 1)                    # strongest high in the sky
    mask = (np.clip((lum - 22) / 40, 0, 1) * yfade * f * 0.75)[..., None]
    return Image.fromarray(np.clip(a * (1 - mask) + col * mask, 0, 255).astype(np.uint8))

def sky_transplant(img, kind, seed):
    """replace flat background sky with real brushwork from the author's painting (cropped/flipped per scene, tinted to the scene)"""
    rng = np.random.default_rng(seed); h, w = img.height, img.width
    a = np.asarray(img, dtype=np.float32); lum = a.mean(2)
    # flat, non-silhouette areas = sky. Local variation is tiny there.
    from scipy import ndimage
    gy, gx = np.gradient(ndimage.gaussian_filter(lum, 1.5)); edge = np.hypot(gx, gy) > 0.8     # hard edges = barriers
    edge = ndimage.binary_dilation(edge, iterations=3)
    lab, n = ndimage.label(~edge & (lum > 10))
    top_ids = set(np.unique(lab[:6, :])) - {0}                                                 # open regions touching the top
    sky_b = np.isin(lab, list(top_ids))
    sky_b = sky_b | (edge & ndimage.binary_dilation(sky_b, iterations=7))   # fill the thin band around figures and ridges
    sky = sky_b.astype(np.float32)
    ys = np.linspace(0, 1, h)[:, None]; sky *= np.clip(1.15 - ys * 0.9, 0, 1)
    sky = np.asarray(Image.fromarray((sky * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(10)), dtype=np.float32) / 255
    ref = Image.open(ref_path(kind)).convert("RGB"); rw, rh = ref.size
    top = ref.crop((0, 0, rw, int(rh * (0.62 if kind != "night" else 0.5))))      # the sky part of the painting
    sc = rng.uniform(1.0, 1.5); cw, ch = int(top.width / sc), int(top.height / sc)
    x0 = int(rng.uniform(0, top.width - cw)); y0 = int(rng.uniform(0, top.height - ch))
    tex = top.crop((x0, y0, x0 + cw, y0 + ch))
    if rng.random() < 0.5: tex = tex.transpose(Image.FLIP_LEFT_RIGHT)
    tex = np.asarray(tex.resize((w, h), Image.BICUBIC), dtype=np.float32)
    # tint the borrowed sky toward the scene's own sky color and brightness
    m = sky > 0.5
    if m.sum() > 100:
        scene_mean = a[m].mean(0); tex_mean = tex[m].mean(0)
        tex = np.clip(tex * (0.55 + 0.45 * scene_mean / (tex_mean + 1)), 0, 255)
    out = a * (1 - sky[..., None]) + tex * sky[..., None]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

def _texture(path, box, w, h, rng, xbox=(0, 1)):
    ref = Image.open(path).convert("RGB"); rw, rh = ref.size
    band = ref.crop((int(rw * xbox[0]), int(rh * box[0]), int(rw * xbox[1]), int(rh * box[1])))
    if rng.random() < 0.5: band = band.transpose(Image.FLIP_LEFT_RIGHT)
    return np.asarray(band.resize((w, h), Image.BICUBIC), dtype=np.float32)

def land_texture(img, seed):
    """paint the ground and mid-ground shapes with real brushwork; leave near-black silhouettes crisp"""
    from scipy import ndimage
    rng = np.random.default_rng(seed + 7); h, w = img.height, img.width
    a = np.asarray(img, dtype=np.float32); lum = a.mean(2)
    gy, gx = np.gradient(ndimage.gaussian_filter(lum, 1.5)); edge = ndimage.binary_dilation(np.hypot(gx, gy) > 0.8, iterations=2)
    lab, n = ndimage.label(~edge)
    sky_ids = set(np.unique(lab[:6, :])) - {0}; bottom_ids = set(np.unique(lab[-6:, :])) - {0}
    ground = _texture(REFS["warm"], (0.76, 0.98), w, h, rng, (0.0, 0.40))   # grass to the LEFT of the cover's figure and shadow
    rock = _texture(REFS["summit"], (0.46, 0.62), w, h, rng)                 # mountainsides ABOVE the summit couple
    out = a.copy(); sizes = ndimage.sum(np.ones_like(lum), lab, index=np.arange(n + 1))
    for i in range(1, n + 1):
        if i in sky_ids or sizes[i] < 4000: continue
        m = lab == i; mean = a[m].mean(0); L = mean.mean()
        tex = ground if i in bottom_ids else rock
        if L < 16: continue                # silhouettes (figures, buildings): leave untouched
        strength = 0.6 if i in bottom_ids else 0.75
        tt = tex[m]; tt = tt * (mean / (tt.mean(0) + 1))   # tint to the region's own color
        tt = (tt - tt.mean(0)) * 0.7 + mean                    # keep its brightness, soften the texture's contrast
        out[m] = a[m] * (1 - strength) + np.clip(tt, 0, 255) * strength
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

def round_shapes(img, k=9):
    """soften hard corners left by stacked code shapes (a mode-like median at reduced size, then back)"""
    from scipy import ndimage
    small = np.asarray(img.resize((img.width // 2, img.height // 2), Image.LANCZOS), dtype=np.uint8)
    sm = np.stack([ndimage.median_filter(small[..., c], size=k) for c in range(3)], -1)
    return Image.fromarray(sm).resize(img.size, Image.LANCZOS)

def remove_figures(img):
    """fill small dark silhouettes with the surrounding colors (normalized convolution); they're restored crisp after painting"""
    from scipy import ndimage
    a = np.asarray(img, dtype=np.float32); lum = a.mean(2); h, w = lum.shape
    dark = lum < 30
    lab, n = ndimage.label(dark); sizes = ndimage.sum(np.ones_like(lum), lab, index=np.arange(n + 1))
    touches_bottom = set(np.unique(lab[-4:, :]))
    small = np.isin(lab, [i for i in range(1, n + 1) if sizes[i] < 0.02 * h * w and i not in touches_bottom])
    small = ndimage.binary_dilation(small, iterations=4)
    if not small.any(): return img
    keep = (~small).astype(np.float32); out = a.copy()
    for c in range(3):
        num = ndimage.gaussian_filter(a[..., c] * keep, 25); den = ndimage.gaussian_filter(keep, 25) + 1e-6
        out[..., c] = np.where(small, num / den, a[..., c])
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

def paint(img, kind="night", seed=1, interior=False, work=(900, 1350), radii=(22, 11, 6, 3), T=12):
    rnd = random.Random(seed)
    img = round_shapes(img.convert("RGB"))
    clean = remove_figures(img)          # brushes never see the figures, so they can't smear them
    if interior:   # rooms, doors, chambers, close planets: brushwork and palette only, no borrowed sky
        src = color_match(add_variation(clean, seed), kind, 0.45).resize(work, Image.LANCZOS)
    else:
        src = color_match(land_texture(sky_transplant(clean, kind, seed), seed), kind, 0.6).resize(work, Image.LANCZOS)
    W, H = work; canvas = src.filter(ImageFilter.GaussianBlur(10)); d = ImageDraw.Draw(canvas)
    for r in radii:
        ref = np.asarray(src.filter(ImageFilter.GaussianBlur(r * 0.6)), dtype=np.float32)
        gray = ref.mean(2); gy, gx = np.gradient(gray)
        cur = np.asarray(canvas, dtype=np.float32); diff = np.sqrt(((cur - ref) ** 2).sum(2))
        cells = [(x, y) for y in range(0, H, r) for x in range(0, W, r)]; rnd.shuffle(cells)
        for x0, y0 in cells:
            blk = diff[y0:y0 + r, x0:x0 + r]
            if blk.size == 0 or blk.mean() < T: continue
            iy, ix = np.unravel_index(blk.argmax(), blk.shape); x, y = x0 + ix, y0 + iy
            col = tuple(int(np.clip(c + rnd.uniform(-6, 6), 0, 255)) for c in ref[y, x]); pts = [(x, y)]
            dx, dy = 0.0, 0.0
            for _ in range(rnd.randint(2, 7)):
                gxv, gyv = gx[int(y), int(x)], gy[int(y), int(x)]
                if math.hypot(gxv, gyv) < 0.5: gxv, gyv = 1.0, 0.25          # flat areas: gentle horizontal strokes
                ndx, ndy = -gyv, gxv; L = math.hypot(ndx, ndy); ndx, ndy = ndx / L, ndy / L
                if dx * ndx + dy * ndy < 0: ndx, ndy = -ndx, -ndy
                dx, dy = ndx, ndy; x, y = x + r * dx, y + r * dy
                if not (0 <= x < W and 0 <= y < H): break
                if np.abs(ref[int(y), int(x)] - np.array(col)).sum() > 36: break
                pts.append((x, y))
            if len(pts) > 1:
                d.line(pts, fill=col, width=max(2, int(r * 1.5)), joint="curve")
                for k in range(3):   # bristles
                    off = rnd.uniform(-r * 0.6, r * 0.6); bc = tuple(int(np.clip(c + rnd.uniform(-14, 14), 0, 255)) for c in col)
                    d.line([(px + off * 0.3, py + off) for px, py in pts], fill=bc, width=max(1, int(r * 0.35)), joint="curve")
            else: d.ellipse([x - r * 0.8, y - r * 0.8, x + r * 0.8, y + r * 0.8], fill=col)
    out = canvas.resize((1800, 2700), Image.BICUBIC).filter(ImageFilter.UnsharpMask(2, 60, 2))
    from scipy import ndimage
    o = np.asarray(img.resize((1800, 2700)), dtype=np.float32); ol = o.mean(2)
    gy, gx = np.gradient(ndimage.gaussian_filter(ol, 1.5)); edge = ndimage.binary_dilation(np.hypot(gx, gy) > 0.8, iterations=3)
    lab, _ = ndimage.label(~edge & (ol > 10)); sky = np.isin(lab, list(set(np.unique(lab[:6, :])) - {0}))
    sil = (ol < 30) & ~ndimage.binary_dilation(sky, iterations=2)
    sil = ndimage.binary_opening(sil, iterations=1)
    m = np.asarray(Image.fromarray((sil * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), dtype=np.float32)[..., None] / 255
    pa = np.asarray(out, dtype=np.float32); dark = o * 0.85 + pa * 0.15          # keep a whisper of paint in the shadows
    out = Image.fromarray(np.clip(pa * (1 - m) + dark * m, 0, 255).astype(np.uint8))
    # canvas grain
    g = np.random.default_rng(seed).normal(0, 6, (2700, 1800, 1)); a = np.asarray(out, dtype=np.float32) + g
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
