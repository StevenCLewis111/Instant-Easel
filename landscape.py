"""
landscape.py: the new engine's scene builder. Describe a landscape with options; it is painted with painter2.
    from landscape import render, DEFAULTS
    img = render(dict(DEFAULTS, figures=1, time="night"), preview=True)
"""
import numpy as np
import painter2 as P
from painter2 import W, H, Image
import bench

DEFAULTS = dict(time="sunset", sun_x=0.41, peaks=4, height=0.5, rocks=True, grass=True, figures=2,
                caption="", seed=3, canyon=True, mountains=True, clouds="normal", tint="none", pose="seated")
TINTS = {"golden": (1.10, 1.02, 0.86), "fiery": (1.16, 0.94, 0.80), "pink": (1.08, 0.94, 1.04), "cool": (0.90, 0.95, 1.12),
         "night": (0.62, 0.72, 1.05), "none": (1, 1, 1)}

def _peaks(n, height, seed):
    rng = np.random.default_rng(seed); xs = np.linspace(0.06, 0.96, n) + rng.uniform(-0.04, 0.04, n)
    main = int(rng.integers(0, n)) if n > 2 else 0; out = []
    for i, x in enumerate(xs):
        top = 0.58 - height * (0.12 if i == main else rng.uniform(0.02, 0.07)); out.append((float(x), float(top), float(rng.uniform(0.3, 0.46))))
    return out

SIZES = {"2:3": (1800, 2700), "3:2": (2700, 1800), "1:1": (2200, 2200), "16:9": (2880, 1620), "9:16": (1620, 2880)}

def render(opts=None, style=None, preview=False, aspect="2:3"):
    global W, H
    import draw as D
    W, H = SIZES.get(aspect, SIZES["2:3"]); P.W, P.H = W, H; D.W, D.H = W, H          # paint at the chosen shape
    try:
        return _render(opts, style, preview)
    finally:
        W, H = SIZES["2:3"]; P.W, P.H = W, H; D.W, D.H = W, H

def _render(opts=None, style=None, preview=False):
    o = dict(DEFAULTS, **(opts or {})); seed = int(o["seed"])
    P.QUALITY = 0.25 if preview else 1.0
    P.CLOUD_AMOUNT = {"few": 0.35, "normal": 1.0, "many": 1.35}.get(o["clouds"], 1.0)
    night = o["time"] == "night"; P.SUN_COLOR = (226, 232, 255) if night else (255, 236, 190)
    prof = style if isinstance(style, dict) else None
    base = (style if isinstance(style, str) else None) or bench.TARGET
    skybase = bench.TARGET.replace("summit.jpg", "night-city.jpg") if night and not isinstance(style, str) else base
    S = P.sky_roles(prof) if prof and "sky" in prof else P.sky_roles(skybase)
    R = P.mountain_roles(prof) if prof and "mountains" in prof else P.mountain_roles(base)
    G = P.ground_roles(prof) if prof and "ground" in prof else P.ground_roles(base)
    if night:                                                                         # re-light the land for night: dim, cool, low saturation
        def nightc(c):
            c = np.asarray(c, np.float32); lum = float(c @ np.array([0.3, 0.59, 0.11]))
            return np.clip(lum * 0.42 * np.array([0.72, 0.84, 1.3]) + c * 0.06, 0, 255)
        R = {k: nightc(v) for k, v in R.items()}; G = {k: nightc(v) for k, v in G.items()}
    subj = (prof or {}).get("subjects", {})
    if "rock" in subj: G["rock"] = np.asarray(subj["rock"]["palette"][len(subj["rock"]["palette"]) // 2], np.float32)
    if "grass" in subj: G["grass"] = np.asarray(subj["grass"]["palette"][-2], np.float32)
    skystyle = prof if prof and "sky" in prof else skybase
    main = o.get("main_peaks") or _peaks(int(o["peaks"]), float(o["height"]), seed + 12)        # an exact layout can be given
    far = o.get("far_peaks") or _peaks(int(o["peaks"]), float(o["height"]) * 0.6, seed + 11)
    xs = np.arange(W, dtype=np.float32)
    rm = P.ridge_profile(xs, P.with_shoulders(main, 12), H * 0.76, 12, floor=H * 0.71, rough=0.008)
    rf = P.ridge_profile(xs, P.with_shoulders(far, 11), H * 0.74, 11, floor=H * 0.68, rough=0.008)
    top = np.minimum(rm, rf); lo, hi = int(W * max(0.05, o["sun_x"] - 0.12)), int(W * min(0.95, o["sun_x"] + 0.12))
    if o.get("sun_range"): lo, hi = int(W * o["sun_range"][0]), int(W * o["sun_range"][1])
    nx = lo + int(np.argmax(top[lo:hi])); sun = (float(nx), float(top[nx] - 18))
    if not o["mountains"]: sun = (W * float(o["sun_x"]), H * 0.66)
    if night: sun = (W * float(o["sun_x"]), H * 0.16)                                  # the moon rides high
    im = Image.new("RGB", (W, H)); P.paint_sky2(im, sun, skystyle, seed)
    if night:                                                                         # night clouds: blue-grey bodies, silver moonlit edges
        a = np.asarray(im, dtype=np.float32); lum = a @ np.array([0.3, 0.59, 0.11], np.float32)
        warm = np.clip((a[..., 0] - a[..., 2] + 25) / 45, 0, 1)[..., None]                  # only the warm (cloud) parts change
        cool = lum[..., None] * np.array([0.52, 0.6, 0.86], np.float32) + np.array([8, 12, 30], np.float32)
        silver = np.clip((lum - 150) / 80, 0, 1)[..., None]
        cool = cool * (1 - silver) + np.array([200, 210, 235], np.float32) * silver
        im = Image.fromarray(np.clip(a * (1 - warm) + cool * warm, 0, 255).astype(np.uint8))
    if night:                                                                         # stars in the clear sky, a crisp moon
        from PIL import ImageDraw, ImageFilter
        rng = np.random.default_rng(seed); a = np.asarray(im, dtype=np.float32); d = ImageDraw.Draw(im)
        for _ in range(900):
            x, y = int(rng.uniform(0, W)), int(rng.uniform(0, H * 0.6))
            if a[y, x].mean() < 95:                                                  # only where the sky is dark (not on clouds)
                s = rng.choice([1, 1, 1, 2, 2, 3]); b = int(rng.uniform(170, 255)); d.ellipse([x, y, x + s, y + s], fill=(b, b, min(255, b + 20)))
        mx, my, mr = sun[0], sun[1], 70
        glow = Image.new("L", (W, H), 0); ImageDraw.Draw(glow).ellipse([mx - mr * 3, my - mr * 3, mx + mr * 3, my + mr * 3], fill=120)
        glow = np.asarray(glow.filter(ImageFilter.GaussianBlur(60)), dtype=np.float32)[..., None] / 255
        a = np.asarray(im, dtype=np.float32); a = a + glow * np.array([140, 160, 210]); im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        ImageDraw.Draw(im).ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=(232, 236, 248))
    if o["mountains"]:
        P.paint_range(im, far, H * 0.74, R, sun, 11, haze=0.5, sky_col=S["gap"], floor=H * 0.68)
        P.paint_range(im, main, H * 0.76, R, sun, 12, floor=H * 0.71)
    if o["canyon"] and o["mountains"]:
        yy = np.arange(H)[:, None]; xx = np.arange(W)[None, :]
        mist = (np.clip(1 - np.abs(xx - W * 0.5) / (W * 0.45), 0, 1) * np.clip(1 - np.abs(yy - H * 0.715) / (H * 0.03), 0, 1))[..., None]
        a = np.asarray(im, dtype=np.float32); a = a * (1 - mist * 0.5) + np.array([236, 150, 96]) * mist * 0.5; im = Image.fromarray(a.astype(np.uint8))
        R2 = {k: v * 0.55 for k, v in R.items()}
        P.paint_range(im, [(0.0, 0.645, 0.4), (0.22, 0.672, 0.3), (0.78, 0.668, 0.3), (1.0, 0.64, 0.4)], H * 0.80, R2, sun, 31, haze=0.12, sky_col=S["gap"], floor=H * 0.745)
    ridge = P.paint_ground(im, G, sun, 21 + seed, H * 0.79, H * 0.70, H * 0.82)
    if o["grass"]: P.paint_grass2(im, ridge, sun, G, 42 + seed, H * 0.70)
    if o["rocks"]: P.scatter_rocks(im, ridge, sun, G, 41 + seed, H * 0.70)
    k = H / 2700                                                                      # figures scale with the picture's height
    if o["pose"] == "standing": figs = [(W * 0.44, 470 * k, "stand", 1), (W * 0.56, 445 * k, "stand", -1)][:int(o["figures"])]
    else: figs = [(W * 0.43, 300 * k, "seated:short", 1), (W * 0.575, 285 * k, "seated:curly", -1)][:int(o["figures"])]
    if int(o["figures"]) == 1: figs = [(W * 0.5, (470 if o["pose"] == "standing" else 300) * k, "stand" if o["pose"] == "standing" else "seated:short", 1)]
    if figs: im = P.paint_figures(im, figs, sun, (200, 214, 240) if night else S["rim"], ridge)
    if night:                                                                         # moonlit ground (after the figures, so their grass tufts are re-lit too)
        a = np.asarray(im, dtype=np.float32); yy = np.arange(H)[:, None]; land = (yy > ridge[None, :] - 4)[..., None]
        lum = a @ np.array([0.3, 0.59, 0.11], np.float32); cool = lum[..., None] * 0.55 * np.array([0.7, 0.82, 1.25], np.float32) + a * 0.05
        im = Image.fromarray(np.clip(np.where(land, cool, a), 0, 255).astype(np.uint8))
    tint = TINTS.get(o["tint"], (1, 1, 1))                                               # night is handled by re-lighting above
    if tint != (1, 1, 1):
        a = np.asarray(im, dtype=np.float32) * np.array(tint, np.float32); im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if o["caption"]: im = P.place_caption(im, o["caption"], avoid=[(H * 0.60, H * 0.72)] if figs else [], size=64)
    P.QUALITY = 1.0; P.CLOUD_AMOUNT = 1.0; P.SUN_COLOR = (255, 236, 190)
    return im
