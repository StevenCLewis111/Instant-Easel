"""
img2img.py: Instant Easel's image-to-image. Repaints any picture (any shape) as a painting, guided by optional words.
    from img2img import render
    out, notes = render(Image.open("photo.jpg"), prompt="golden hour, watercolor", strength=0.7, medium="oil", palette="keep")
strength 0..1: low keeps close to the picture, high turns it fully into a painting.
medium: oil | watercolor | pastel | ink sketch      palette: keep | warm | night | learned (pass a learned profile)
"""
import math, random
import numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageOps
import painter2 as P
import language

MEDIUMS = ("oil", "watercolor", "pastel", "ink sketch")
PALETTES = ("keep", "warm", "night", "learned")
TINTS = {"golden": (1.10, 1.02, 0.86), "fiery": (1.16, 0.94, 0.80), "pink": (1.08, 0.94, 1.04), "cool": (0.90, 0.95, 1.12)}

def _fit(img, long_side=None):
    if long_side is None:
        try: import prefs; long_side = prefs.size("i2i_size")                    # Settings > Performance
        except Exception: long_side = 1600
    img = ImageOps.exif_transpose(img).convert("RGB"); w, h = img.size; s = long_side / max(w, h)
    return img.resize((max(8, int(w * s)), max(8, int(h * s))), Image.LANCZOS)

def _orientation(a):
    """stroke direction along edges (smoothed structure tensor), so strokes follow the forms in the picture"""
    from scipy.ndimage import gaussian_filter, sobel
    g = a.mean(2); gx, gy = sobel(g, 1), sobel(g, 0)
    jxx, jyy, jxy = gaussian_filter(gx * gx, 6), gaussian_filter(gy * gy, 6), gaussian_filter(gx * gy, 6)
    return 0.5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2

def _night(a):
    lum = a @ np.array([0.3, 0.59, 0.11], np.float32)
    return np.clip(lum[..., None] * 0.55 * np.array([0.7, 0.82, 1.28], np.float32) + a * 0.08, 0, 255)

def _palette_match(a, ref_roles):
    """shift the picture's colours toward a learned palette (keeps its own light and dark)"""
    cols = np.stack([np.asarray(c, np.float32) for c in ref_roles.values()])
    lum_a = a @ np.array([0.3, 0.59, 0.11], np.float32); lum_c = cols @ np.array([0.3, 0.59, 0.11], np.float32)
    order = np.argsort(lum_c); cols, lum_c = cols[order], lum_c[order]
    idx = np.clip(np.searchsorted(lum_c, lum_a), 1, len(cols) - 1); lo, hi = cols[idx - 1], cols[idx]
    t = np.clip((lum_a - lum_c[idx - 1]) / (lum_c[idx] - lum_c[idx - 1] + 1e-6), 0, 1)[..., None]
    target = lo * (1 - t) + hi * t; target *= (lum_a / (target @ np.array([0.3, 0.59, 0.11], np.float32) + 1e-6))[..., None]
    return np.clip(target, 0, 255)

def render(image, prompt="", strength=0.7, medium="oil", palette="keep", profile=None, seed=7):
    """-> (painted PIL image, list of notes about what was applied)"""
    notes = []; opts, understood, unknown = language.understand(prompt or "")
    medium = opts.get("medium", medium)
    import styles_fx as SF
    medium = {v: k for k, v in SF.MEDIUM.items()}.get(medium, medium)                    # "oil" -> "Oil Painting"
    if medium in SF.MEDIUM: medium = SF.MEDIUM[medium]                                     # classic mediums use the brush engine below
    notes.append(f"style: {medium if medium not in MEDIUMS else {v: k for k, v in SF.MEDIUM.items()}[medium]}")
    img = _fit(image); a = np.asarray(img, dtype=np.float32); h, w = a.shape[:2]; s = float(np.clip(strength, 0.05, 1.0))
    # ---- palette
    if palette == "warm" or (palette == "keep" and opts.get("time") == "sunset" and "tint" not in opts):
        roles = P.sky_roles("styles/sunset-field.jpg") if False else None
        warm = a * np.array([1.08, 0.98, 0.84], np.float32) + np.array([14, 4, -6], np.float32); a = a * (1 - 0.6 * s) + warm * 0.6 * s; notes.append("warm sunset palette")
    if palette == "night" or opts.get("time") == "night":
        a = a * (1 - 0.85) + _night(a) * 0.85; notes.append("re-lit as night")
    if palette == "learned" and profile:
        roles = {}
        for sec in ("sky", "mountains", "ground"): roles.update({f"{sec}_{k}": v for k, v in profile.get(sec, {}).items()})
        for sub in profile.get("subjects", {}).values():
            for i, c in enumerate(sub.get("palette", [])): roles[f"p{len(roles)}_{i}"] = c
        if roles: a = a * (1 - 0.7 * s) + _palette_match(a, roles) * 0.7 * s; notes.append("learned palette")
    if opts.get("tint") in TINTS: a = np.clip(a * np.array(TINTS[opts["tint"]], np.float32), 0, 255); notes.append(f"{opts['tint']} mood")
    base = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    rnd = random.Random(seed); scale = max(w, h) / 1600
    # ---- medium
    if medium not in MEDIUMS:                                                            # any other art style
        painted = SF.apply(base, medium, seed=seed)
    elif medium == "ink sketch":
        g = ImageOps.grayscale(base); edges = g.filter(ImageFilter.FIND_EDGES).point(lambda v: 255 - min(255, v * 3))
        paper = Image.new("RGB", (w, h), (246, 240, 228)); ink = np.asarray(edges, dtype=np.float32) / 255
        tone = np.asarray(g, dtype=np.float32) / 255; out = np.asarray(paper, dtype=np.float32) * np.minimum(ink, 0.35 + 0.65 * tone)[..., None]
        canvas = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)); d = ImageDraw.Draw(canvas)
        ang = _orientation(a)
        for _ in range(int(14000 * s * (w * h) / 1.4e6)):                      # hatching only in the darker areas, short strokes
            x, y = rnd.uniform(0, w - 1), rnd.uniform(0, h - 1); t = tone[int(y), int(x)]
            if t < 0.55 and rnd.random() < (0.55 - t) * 1.8:
                L = 7 * scale; an = 0.8 if t > 0.3 else rnd.choice((0.8, -0.8))       # cross-hatch in the darkest parts
                d.line([(x - math.cos(an) * L, y - math.sin(an) * L), (x + math.cos(an) * L, y + math.sin(an) * L)], fill=(40, 34, 30), width=max(1, int(scale)))
        painted = canvas
    else:
        field = np.asarray(base.filter(ImageFilter.GaussianBlur(1.5 * scale)), dtype=np.float32); ang = _orientation(field)
        canvas = base.filter(ImageFilter.GaussianBlur(6 * scale * s + 1)) if medium != "watercolor" else Image.new("RGB", (w, h), (247, 243, 234))
        n = (w * h) / 1.4e6
        if medium == "oil":
            P.strokes_soft(canvas, field, ang, int(7000 * n * (0.4 + s)), (40 * scale, 110 * scale), (10 * scale, 20 * scale), seed, jitter=8, alpha=200)
            P.strokes_soft(canvas, field, ang, int(12000 * n * (0.4 + s)), (16 * scale, 44 * scale), (4 * scale, 9 * scale), seed + 1, jitter=10, alpha=215)
        elif medium == "pastel":
            P.strokes(canvas, field, ang, int(16000 * n * (0.4 + s)), (14 * scale, 40 * scale), (3 * scale, 7 * scale), seed, jitter=16)
            grain = np.random.default_rng(seed).random((h, w, 1)).astype(np.float32)
            c = np.asarray(canvas, dtype=np.float32); c = c * (0.86 + 0.14 * grain) + 18 * (grain > 0.92); canvas = Image.fromarray(np.clip(c, 0, 255).astype(np.uint8))
        elif medium == "watercolor":
            wash = base.filter(ImageFilter.GaussianBlur(5 * scale)); q = wash.quantize(colors=24).convert("RGB")
            edges = np.asarray(q.filter(ImageFilter.FIND_EDGES).convert("L"), dtype=np.float32)[..., None] / 255
            paper = np.asarray(canvas, dtype=np.float32); pig = np.asarray(q, dtype=np.float32)
            lift = 0.25 + 0.25 * (1 - s)                                         # transparent: the white paper glows through the washes
            out = paper - (255 - pig) * (1 - lift)
            out = out * (1 - np.clip(edges * 1.4, 0, 0.22))                      # softly darker pooled edges
            grain = np.random.default_rng(seed).random((h, w, 1)).astype(np.float32); out = out * (0.94 + 0.06 * grain)
            canvas = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
        painted = canvas
    # ---- strength: how much of the original survives
    keep = 1 - s
    out = Image.blend(painted, base, keep * 0.85) if medium != "ink sketch" else Image.blend(painted, ImageOps.grayscale(base).convert("RGB"), keep * 0.5)
    if opts.get("caption"):                                                      # caption, placed by the same rules
        oldW, oldH = P.W, P.H; P.W, P.H = out.size
        try: out = P.place_caption(out, opts["caption"], size=max(26, int(out.size[1] * 0.04)))
        finally: P.W, P.H = oldW, oldH
        notes.append("caption placed")
    ignored = [u for u in understood if not u.startswith("caption") and any(k in u for k in ("people", "mountain", "rock", "grass", "cloud", "peak", "canyon"))]
    if ignored: notes.append("scene words don't change an existing picture: " + ", ".join(ignored))
    return out, notes + ([f"unknown words: {', '.join(unknown)}"] if unknown else [])
