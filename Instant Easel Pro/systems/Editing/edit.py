"""
edit.py: Instant Easel Pro's Edit adjustments (Lightroom-style). Every value runs -100..100 (0 = no change) unless noted.
    from edit import apply, DEFAULTS
    out = apply(img, dict(DEFAULTS, exposure=20, shadows=30, saturation=15), filt="warm film")
Order (as photo editors do): exposure > white balance > tone (contrast, highlights, shadows, whites, blacks, brightness)
> colour (hue, vibrance, saturation) > detail (clarity, sharpness) > filter look > finishing (glow, vignette, grain).
"""
import numpy as np
from PIL import Image, ImageFilter, ImageOps

GROUPS = {
    "Light": ["exposure", "brightness", "contrast", "highlights", "shadows", "whites", "blacks"],
    "Color": ["temperature", "tint", "hue", "saturation", "vibrance"],
    "Effects": ["sharpness", "clarity", "vignette", "grain", "glow"],
}
DEFAULTS = {k: 0 for g in GROUPS.values() for k in g}
FILTERS = ["none", "grayscale", "sepia", "warm film", "cool film", "faded", "high contrast", "night"]

def _lum(a): return a @ np.array([0.299, 0.587, 0.114], np.float32)

def apply(img, p=None, filt="none", seed=3):
    p = dict(DEFAULTS, **(p or {})); a = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    # exposure: in stops (+100 = +2 stops)
    if p["exposure"]: a = a * (2.0 ** (p["exposure"] / 50.0))
    # white balance: temperature (blue <-> amber), tint (green <-> magenta)
    if p["temperature"]: t = p["temperature"] / 100.0; a = a * np.array([1 + 0.18 * t, 1 + 0.02 * t, 1 - 0.18 * t], np.float32)
    if p["tint"]: t = p["tint"] / 100.0; a = a * np.array([1 + 0.08 * t, 1 - 0.14 * t, 1 + 0.08 * t], np.float32)
    a = np.clip(a, 0, 1); L = _lum(a)[..., None]
    # tone: each control works on its own part of the light range
    if p["highlights"]: m = np.clip((L - 0.5) * 2, 0, 1) ** 1.5; a = a + m * (p["highlights"] / 100.0) * 0.35
    if p["shadows"]: m = np.clip(1 - L * 2, 0, 1) ** 1.5; a = a + m * (p["shadows"] / 100.0) * 0.35
    if p["whites"]: m = np.clip((L - 0.75) * 4, 0, 1); a = a + m * (p["whites"] / 100.0) * 0.25
    if p["blacks"]: m = np.clip(1 - L * 4, 0, 1); a = a + m * (p["blacks"] / 100.0) * 0.25
    if p["contrast"]: c = 1 + p["contrast"] / 100.0 * (0.9 if p["contrast"] > 0 else 0.7); a = (a - 0.5) * c + 0.5
    if p["brightness"]: b = p["brightness"] / 100.0; a = a + b * 0.25 * (1 - np.abs(a - 0.5) * 1.2)          # midtones most
    a = np.clip(a, 0, 1)
    # colour
    if p["hue"]:
        hsv = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).convert("HSV"), dtype=np.float32)
        hsv[..., 0] = (hsv[..., 0] + p["hue"] / 100.0 * 128) % 256
        a = np.asarray(Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB"), dtype=np.float32) / 255
    if p["vibrance"] or p["saturation"]:
        L = _lum(a)[..., None]; sat = (a.max(2, keepdims=True) - a.min(2, keepdims=True))
        k = 1 + p["saturation"] / 100.0
        if p["vibrance"]: k = k + (p["vibrance"] / 100.0) * (1 - np.clip(sat * 1.6, 0, 1))         # vibrance boosts dull colours most
        a = np.clip(L + (a - L) * k, 0, 1)
    out = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    # detail
    if p["clarity"]: out = out.filter(ImageFilter.UnsharpMask(radius=max(8, out.width // 120), percent=int(abs(p["clarity"]) * 1.2), threshold=2)) if p["clarity"] > 0 \
        else Image.blend(out, out.filter(ImageFilter.GaussianBlur(max(3, out.width // 300))), -p["clarity"] / 140)
    if p["sharpness"]: out = out.filter(ImageFilter.UnsharpMask(radius=1.6, percent=int(abs(p["sharpness"]) * 2.2), threshold=1)) if p["sharpness"] > 0 \
        else out.filter(ImageFilter.GaussianBlur(-p["sharpness"] / 40))
    out = look(out, filt)
    # finishing
    a = np.asarray(out, dtype=np.float32) / 255; h, w = a.shape[:2]
    if p["glow"] > 0:
        bright = np.clip((_lum(a) - 0.6) * 2.5, 0, 1)[..., None] * a; g = np.asarray(Image.fromarray((bright * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(w / 60)), dtype=np.float32) / 255
        a = 1 - (1 - a) * (1 - g * p["glow"] / 100.0)                                                    # screen-blend glow
    if p["vignette"]:
        yy, xx = np.mgrid[0:h, 0:w]; r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / 1.414
        m = np.clip((r - 0.35) / 0.65, 0, 1) ** 1.6; v = p["vignette"] / 100.0
        a = a * (1 - m[..., None] * v * 0.8) if v > 0 else a + (1 - a) * m[..., None] * (-v) * 0.7
    if p["grain"] > 0:
        rng = np.random.default_rng(seed); n = rng.normal(0, 1, (h, w, 1)).astype(np.float32); a = a + n * (p["grain"] / 100.0) * 0.08
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))

def look(img, name):
    """one-click filter looks"""
    if name in (None, "", "none"): return img
    a = np.asarray(img, dtype=np.float32) / 255; L = _lum(a)[..., None]
    if name == "grayscale": a = np.repeat(L, 3, 2)
    elif name == "sepia": a = np.clip(L * np.array([1.07, 0.89, 0.66], np.float32) + np.array([0.05, 0.03, 0.0], np.float32), 0, 1)
    elif name == "warm film": a = np.clip((a - 0.5) * 1.08 + 0.5, 0, 1) * np.array([1.08, 1.0, 0.86], np.float32) + 0.025
    elif name == "cool film": a = np.clip((a - 0.5) * 1.05 + 0.5, 0, 1) * np.array([0.9, 0.98, 1.1], np.float32)
    elif name == "faded": a = a * 0.82 + 0.1; a = L + (a - L) * 0.75
    elif name == "high contrast": a = np.clip((a - 0.5) * 1.45 + 0.5, 0, 1)
    elif name == "night": a = np.clip(L * 0.55 * np.array([0.7, 0.82, 1.28], np.float32) + a * 0.08, 0, 1)
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))

# ---------------- Transform (geometry): runs BEFORE the adjustments, as photo editors do ----------------
GEOM = dict(rot90=0, straighten=0.0, flip_h=False, flip_v=False, crop=None, scale=1.0)   # crop = (x0, y0, x1, y1) as 0..1 of the image

def _largest_inner(w, h, deg):
    """size of the biggest upright rectangle inside a w x h image rotated by deg (so no empty corners show)"""
    import math
    a = math.radians(abs(deg)) % math.pi
    if a > math.pi / 2: a = math.pi - a
    if a == 0: return w, h
    long_, short = max(w, h), min(w, h); sin, cos = math.sin(a), math.cos(a)
    if short <= 2 * sin * cos * long_ or abs(sin - cos) < 1e-10:
        x = 0.5 * short; wr, hr = (x / sin, x / cos) if w >= h else (x / cos, x / sin)
    else:
        c2 = cos * cos - sin * sin; wr, hr = (w * cos - h * sin) / c2, (h * cos - w * sin) / c2
    return int(wr), int(hr)

def transform(img, g=None):
    g = dict(GEOM, **(g or {})); out = img
    if g["rot90"] % 4: out = out.rotate(90 * (g["rot90"] % 4), expand=True)            # counter-clockwise quarter turns
    if g["flip_h"]: out = ImageOps.mirror(out)
    if g["flip_v"]: out = ImageOps.flip(out)
    if abs(g["straighten"]) > 0.01:
        w, h = out.size; r = out.rotate(-g["straighten"], resample=Image.BICUBIC, expand=True)
        iw, ih = _largest_inner(w, h, g["straighten"]); cx, cy = r.width / 2, r.height / 2
        out = r.crop((int(cx - iw / 2), int(cy - ih / 2), int(cx + iw / 2), int(cy + ih / 2)))
    if g["crop"]:
        x0, y0, x1, y1 = g["crop"]; w, h = out.size
        box = (int(min(x0, x1) * w), int(min(y0, y1) * h), int(max(x0, x1) * w), int(max(y0, y1) * h))
        if box[2] - box[0] > 4 and box[3] - box[1] > 4: out = out.crop(box)
    if abs(g["scale"] - 1.0) > 1e-3: out = out.resize((max(1, int(out.width * g["scale"])), max(1, int(out.height * g["scale"]))), Image.LANCZOS)
    return out

def crop_for_ratio(w, h, ratio, centre=(0.5, 0.5)):
    """the largest crop box (0..1 coords) of a given ratio like '16:9' that fits a w x h picture"""
    a, b = (float(x) for x in ratio.split(":")); r = a / b
    if w / h > r: cw, ch = h * r / w, 1.0
    else: cw, ch = 1.0, w / r / h
    cx = min(max(centre[0], cw / 2), 1 - cw / 2); cy = min(max(centre[1], ch / 2), 1 - ch / 2)
    return (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
