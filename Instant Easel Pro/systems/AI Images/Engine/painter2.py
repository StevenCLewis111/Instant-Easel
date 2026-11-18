"""painter2: paints scenes the way the author's paintings are made (sky, clouds, mountains, ground, silhouettes, shadows)."""
import math, random, numpy as np
from PIL import Image, ImageDraw, ImageFilter
W, H = 1800, 2700
CLOUD_AMOUNT = 1.0     # 0.35 = few clouds, 1 = normal, 1.35 = lots
SUN_COLOR = (255, 236, 190)   # the night scene swaps this for a pale moon
QUALITY = 1.0          # 1.0 = full brushwork; preview mode lowers it so a layout appears quickly

def noise2(h, w, cells, seed, stretch=(1.0, 1.0)):
    """smooth fractal noise, optionally stretched (clouds are wider than tall)"""
    rng = np.random.default_rng(seed); out = np.zeros((h, w), np.float32); amp = 1.0
    for o in range(5):
        cy, cx = max(2, int(cells * (2 ** o) / stretch[0])), max(2, int(cells * (2 ** o) / stretch[1]))
        n = rng.normal(0, 1, (cy, cx)).astype(np.float32)
        out += amp * np.asarray(Image.fromarray(n).resize((w, h), Image.BICUBIC)); amp *= 0.5
    return (out - out.min()) / (out.max() - out.min())

def lerp(a, b, t): return a + (b - a) * t

def palette_from(target, box, n=7):
    """colors of a region of the author's painting, dark to light (the engine 'learns' its palette here)"""
    im = Image.open(target).convert("RGB"); w, h = im.size
    r = np.asarray(im.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h))).resize((120, 120)), dtype=np.float32).reshape(-1, 3)
    lum = r @ np.array([0.3, 0.59, 0.11]); o = np.argsort(lum)
    return [r[o[int(q * (len(o) - 1))]] for q in np.linspace(0.04, 0.98, n)]

def ramp(pal, t):
    """map 0..1 to a color along the palette"""
    t = np.clip(t, 0, 1) * (len(pal) - 1); i = np.clip(t.astype(int), 0, len(pal) - 2); f = (t - i)[..., None]
    P = np.stack(pal); return P[i] * (1 - f) + P[i + 1] * f

def strokes(canvas, colorfield, angle, n, length, width, seed, mask=None, jitter=10):
    """lay down n brushstrokes; colour from colorfield, direction from angle field (radians)"""
    n = int(n * QUALITY); rnd = random.Random(seed); d = ImageDraw.Draw(canvas); h, w = colorfield.shape[:2]
    for _ in range(n):
        x, y = rnd.uniform(0, w - 1), rnd.uniform(0, h - 1)
        if mask is not None and not mask[int(y), int(x)]: continue
        c = colorfield[int(y), int(x)]; col = tuple(int(np.clip(v + rnd.uniform(-jitter, jitter), 0, 255)) for v in c)
        a = angle[int(y), int(x)] + rnd.uniform(-0.25, 0.25); L = rnd.uniform(*length); wd = int(rnd.uniform(*width))
        pts = []
        for k in range(4):                     # slight curve
            t = (k / 3 - 0.5) * L; bend = math.sin(k) * L * 0.06
            pts.append((x + math.cos(a) * t - math.sin(a) * bend, y + math.sin(a) * t + math.cos(a) * bend))
        d.line(pts, fill=col, width=wd, joint="curve")

def kmeans_colors(target, box, k=8, seed=0):
    im = Image.open(target).convert("RGB"); w, h = im.size
    X = np.asarray(im.crop((int(box[0]*w), int(box[1]*h), int(box[2]*w), int(box[3]*h))).resize((100, 100)), dtype=np.float32).reshape(-1, 3)
    rng = np.random.default_rng(seed); C = X[rng.choice(len(X), k, replace=False)]
    for _ in range(20):
        lab = ((X[:, None] - C[None]) ** 2).sum(2).argmin(1)
        C = np.stack([X[lab == i].mean(0) if (lab == i).any() else C[i] for i in range(k)])
    return C

def sky_roles(target):
    if isinstance(target, dict): return {k: np.asarray(v, np.float32) for k, v in target['sky'].items()}
    """learn the sky's colour roles from the painting: cool gaps, dark cloud bodies, rose, orange, gold rims"""
    C = kmeans_colors(target, (0, 0, 1, 0.5), k=12); lum = C @ np.array([.3, .59, .11]); cool = C[:, 2] - 0.6 * C[:, 0] - 0.4 * C[:, 1]
    light = lum >= np.percentile(lum, 35)
    gap = C[np.where(light, cool, -1e9).argmax()]            # the cool lavender showing between clouds (a LIGHT cool colour)
    body = C[lum.argmin()]; rim = C[lum.argmax()]
    warm = sorted([c for c in C if not (c is gap)], key=lambda c: c @ np.array([.3, .59, .11]))
    gap = gap * 0.55 + np.array([138, 136, 186], np.float32) * 0.45          # the painting's blue-lavender breaks
    return dict(gap=gap, body=body, rose=warm[len(warm)//2], orange=warm[-2], rim=rim)

def paint_sky(im, sun, target, seed=3, horizon=0.62):
    h, w = H, W; yy = np.linspace(0, 1, h)[:, None] * np.ones((1, w)); xx = np.ones((h, 1)) * np.linspace(0, 1, w)[None, :]
    R = sky_roles(target); sx, sy = sun[0] / w, sun[1] / h
    glow = np.clip(1 - np.sqrt(((xx - sx) * 1.1) ** 2 + ((yy - sy) * 2.2) ** 2) * 1.1, 0, 1) ** 1.5
    # clear sky between clouds: cool lavender high up, warming to gold at the horizon
    t = np.clip(yy / horizon, 0, 1)[..., None]
    sky = R["gap"] * (1 - t) + (R["orange"] * 0.5 + R["rim"] * 0.5) * t
    sky = sky * (1 - glow[..., None] * 0.7) + R["rim"] * glow[..., None] * 0.7
    # clouds: wide masses in perspective rows (big and loose high up, thin and flat near the horizon)
    rowf = np.sin((yy ** 0.55) * 26 + noise2(h, w, 2, seed + 9) * 4.0) * 0.07
    big = noise2(h, w, 6, seed, stretch=(1.0, 1.9)); mid = noise2(h, w, 13, seed + 1, stretch=(1.0, 1.6))
    billow = 1 - np.abs(noise2(h, w, 18, seed + 2, stretch=(1.0, 1.6)) * 2 - 1)          # lumpy, puffy edges
    c = big * 0.42 + mid * 0.33 + billow * 0.25 + rowf
    sharp = np.clip((c - 0.43) * 9.0, 0, 1) * np.clip(1.15 - (yy / horizon) ** 4, 0, 1)
    from scipy.ndimage import gaussian_filter
    cloud = gaussian_filter(sharp, 1.2)                                      # crisp clouds, just the stair-steps softened
    below = np.roll(sharp, -16, axis=0); above = np.roll(cloud, 22, axis=0)
    under = np.clip((sharp - below) * 4.0, 0, 1)                  # lower edge of a cloud: lit from the low sun
    top = np.clip((cloud - above) * 2.0, 0, 1)
    light = np.clip(0.25 + glow * 0.9 + (yy / horizon) * 0.4, 0, 1)[..., None]
    low = np.clip((yy / horizon) ** 1.3, 0, 1)[..., None]
    plum = R["body"] * 0.6 + np.array([58, 34, 58], np.float32) * 0.4                 # deeper plum bodies
    body = plum * (1 - low ** 0.8) + (R["rose"] * 0.2 + R["orange"] * 0.8) * low ** 0.8
    body = body * (1 - light * 0.35) + R["orange"] * light * 0.35
    rimc = R["orange"] * (1 - glow[..., None]) + R["rim"] * glow[..., None]
    col = body * (1 - under[..., None]) + rimc * under[..., None] * np.clip(0.95 + 0.5 * light, 0, 1.25)
    col = col * (1 - top[..., None] * 0.35) + R["body"] * top[..., None] * 0.35
    field = sky * (1 - cloud[..., None]) + col * cloud[..., None]
    lum = field.mean(2, keepdims=True); field = np.clip(lum + (field - lum) * 1.3, 0, 255)       # richer colour, like the painting
    # the setting sun: hot core, wide glow, faint rays
    sd = np.sqrt(((xx - sx) * w) ** 2 + ((yy - sy) * h) ** 2)
    core = np.clip(1 - sd / 70, 0, 1) ** 0.6; halo = np.clip(1 - sd / 520, 0, 1) ** 2.2
    rays = (0.5 + 0.5 * np.cos(np.arctan2(yy * h - sy * h, xx * w - sx * w) * 14)) * np.clip(1 - sd / 900, 0, 1) * (1 - cloud) * 0.18
    hot = np.array([255, 236, 190], np.float32)
    field = field * (1 - (halo * 0.55 + rays)[..., None]) + R["rim"] * (halo * 0.55 + rays)[..., None]
    field = field * (1 - core[..., None]) + hot * core[..., None]
    base = Image.fromarray(np.clip(field, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(4))
    im.paste(base.crop((0, 0, w, int(h * horizon) + 40)), (0, 0))
    ang = -0.18 + (noise2(h, w, 4, seed + 5) - 0.5) * 0.9 - cloud * 0.15
    mask = yy < horizon + 0.02
    mask = mask & (sd > 60)                                              # keep the sun's core clean
    strokes(im, field, ang, 22000, (50, 140), (12, 24), seed, mask, jitter=8)
    strokes(im, field, ang, 34000, (20, 60), (5, 12), seed + 1, mask, jitter=12)
    return im

# ---- stand-ins for this pass (flat), replaced in later passes ----
def flat_rest(im):
    d = ImageDraw.Draw(im)
    d.polygon([(0, H * 0.66), (W * 0.18, H * 0.58), (W * 0.33, H * 0.62), (W * 0.5, H * 0.47), (W * 0.66, H * 0.6), (W * 0.8, H * 0.55), (W, H * 0.62), (W, H), (0, H)], fill=(120, 80, 100))
    d.rectangle([0, H * 0.74, W, H], fill=(28, 20, 22)); d.rectangle([W * 0.22, H * 0.72, W * 0.78, H * 0.745], fill=(28, 20, 22))
    import draw; draw.person(im, W * 0.43, H * 0.725, 300, "sit", (12, 8, 10)); draw.person(im, W * 0.57, H * 0.725, 300, "sit", (12, 8, 10), -1)
    return im

def mountain_roles(target):
    if isinstance(target, dict): return {k: np.asarray(v, np.float32) for k, v in target['mountains'].items()}
    """learn the mountains' colours: deep shadow, violet, mauve, lit orange, peach highlight"""
    C = kmeans_colors(target, (0.08, 0.42, 0.92, 0.72), k=10, seed=1); lum = C @ np.array([.3, .59, .11])
    o = np.argsort(lum); warmth = C[:, 0] - C[:, 2]
    lit = C[np.where(lum > np.percentile(lum, 55), warmth, -1e9).argmax()]
    deep = C[o[1]] * 0.5 + C[o[2]] * 0.5
    if deep @ np.array([.3, .59, .11]) < 45: deep = deep * 0.4 + np.array([70, 48, 72], np.float32) * 0.6     # violet, not black
    deep = deep * 0.35 + np.array([68, 48, 82], np.float32) * 0.65                      # shadows are VIOLET in the painting
    lit = lit * 0.6 + np.array([236, 120, 52], np.float32) * 0.4                       # saturated sunlit orange
    shadow = C[o[2]] * 0.4 + np.array([112, 80, 118], np.float32) * 0.6
    return dict(deep=deep, shadow=shadow, mid=C[o[5]] * 0.7 + np.array([200, 100, 70], np.float32) * 0.3, lit=lit, hi=C[o[-1]])

def ridge_profile(xs, peaks, base, seed, rough=0.012, floor=None):
    """ridgeline through the peaks with fractal roughness; peaks = [(x_frac, top_frac, width_frac)]"""
    rng = np.random.default_rng(seed); y = np.full(len(xs), floor if floor else base, np.float32)
    y += np.asarray(Image.fromarray(rng.normal(0, 1, (1, 12)).astype(np.float32)).resize((len(xs), 1), Image.BICUBIC))[0] * H * 0.012
    for px, top, wd in peaks:
        d = np.abs(xs / W - px) / wd
        y = np.minimum(y, H * (top + (base / H - top) * np.clip(d, 0, 1) ** 1.42))     # pointed summits, concave flanks
    jag = np.cumsum(rng.normal(0, 1, len(xs))); jag = np.convolve(jag - np.convolve(jag, np.ones(401) / 401, "same"), np.ones(9) / 9, "same")
    y = y + jag / (np.abs(jag).max() + 1e-6) * H * rough
    return np.convolve(np.pad(y, 4, mode='edge'), np.ones(9) / 9, 'valid')        # light smoothing keeps summits sharp

def with_shoulders(peaks, seed):
    rng = np.random.default_rng(seed); out = list(peaks)
    for px, top, wd in peaks:
        side = rng.choice((-1, 1))                                                     # one broad shoulder per peak
        off = wd * rng.uniform(0.35, 0.5) * side; drop = (0.78 - top) * rng.uniform(0.35, 0.5)
        out.append((px + off, top + drop, wd * rng.uniform(0.8, 1.0)))
    return out

def paint_range(im, peaks, base, R, sun, seed, haze=0.0, sky_col=None, light_from=-1, floor=None):
    h, w = H, W; xs = np.arange(w, dtype=np.float32); peaks = with_shoulders(peaks, seed)
    ridge = ridge_profile(xs, peaks, base, seed, floor=floor, rough=0.008)
    yy = np.arange(h, dtype=np.float32)[:, None]; inside = yy >= ridge[None, :]
    # which peak owns each column, and the fall-line angle from that summit
    best = np.argmin(np.stack([np.abs(xs / w - p[0]) / p[2] for p in peaks]), 0)
    px = np.array([peaks[i][0] * w for i in best]); py = np.array([peaks[i][1] * h for i in best])
    dx = xs[None, :] - px[None, :]; dy = np.maximum(yy - py[None, :], 1)
    # face direction from the ridge's real slope, blurred more the further below the crest:
    # lit and shadow faces then meet along diagonal ridges and V-shaped valleys (no vertical seams)
    depth_px = np.maximum(yy - ridge[None, :], 0)
    levels = [0, 30, 70, 130, 220, 340, 500, 700]
    slopes = []
    for lv in levels:
        from scipy.ndimage import gaussian_filter1d
        rb = gaussian_filter1d(ridge.astype(np.float64), 6 + lv * 0.55, mode="nearest"); slopes.append(np.gradient(rb))
    slopes = np.stack(slopes)                                                     # [level, x]
    li = np.clip(np.searchsorted(levels, depth_px) - 1, 0, len(levels) - 1)
    slope = slopes[li, np.arange(w)[None, :]]
    side = np.tanh(-slope * 1.6) * (-light_from)                                 # +1 = facing the light
    ang = np.arctan2(dx, dy)                                           # fall lines radiate from each summit
    streak = noise2(64, 256, 8, seed + 3)                                # gullies: noise sampled along the fall-line angle
    si = np.clip(((ang / np.pi + 0.5) * 255).astype(int), 0, 255); di = np.clip((dy / h * 63 * 3).astype(int), 0, 63)
    gully = streak[di, si]
    facet = noise2(h // 3, w // 3, 40, seed + 8); facet = np.asarray(Image.fromarray(facet).resize((w, h), Image.NEAREST))
    facet = np.floor(facet * 6) / 6 - 0.5                               # angular rock planes (posterised, hard-edged)
    strata = np.sin((yy * 0.09 + dx * 0.035) + noise2(h // 4, w // 4, 6, seed + 9).repeat(4, 0).repeat(4, 1)[:h, :w] * 6) * 0.06
    shade = np.clip(0.42 + 0.45 * side + (gully - 0.5) * 0.3 + facet * 0.16 + strata, 0, 1)
    depth = np.clip((yy - ridge[None, :]) / (base - ridge.min() + 1), 0, 1)        # lower = darker, cooler
    shade = shade * (1 - depth * 0.65)
    pal = [R["deep"], R["shadow"], R["mid"], R["lit"], R["hi"]]
    field = ramp(pal, shade).astype(np.float32)
    sunnear = np.clip(1 - np.abs(xs - sun[0]) / (w * 0.35), 0, 1)[None, :]
    rimz = np.clip(1 - (yy - ridge[None, :]) / 10, 0, 1) * np.clip((side > 0) * 0.7 + sunnear * 0.9, 0, 1)   # backlit ridgelines glow                # bright crest lines on the lit side
    field = field * (1 - rimz[..., None] * 0.6) + R["hi"] * rimz[..., None] * 0.6
    if haze and sky_col is not None:
        if haze >= 0.35:   # FAR zone: only two shades (highlight / shadow), both shifted toward the sky; low contrast, bright, unsaturated
            lit2 = np.asarray(sky_col, np.float32) * 0.55 + R["hi"] * 0.45; sh2 = np.asarray(sky_col, np.float32) * 0.7 + R["shadow"] * 0.3
            two = (shade > 0.48)[..., None]; field = np.where(two, lit2, sh2)
        else:              # MIDDLE zone: contrast drops toward the haze
            field = field * (1 - haze) + np.asarray(sky_col, np.float32) * haze
    layer = Image.fromarray(np.clip(field, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
    m = Image.fromarray((inside * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
    im.paste(layer, (0, 0), m)
    rnd = random.Random(seed + 77); d = ImageDraw.Draw(im)
    for px_, top_, wd_ in peaks:
        sx0, sy0 = px_ * w, top_ * h
        if sy0 < ridge.min() - 5 or not (0 <= sx0 < w): continue
        for k in range(0):
            ang0 = rnd.uniform(-0.75, 0.75); x, y = sx0, ridge[int(np.clip(sx0, 0, w - 1))] + 4; pts = [(x, y)]
            for s in range(rnd.randint(5, 10)):
                ang0 += rnd.uniform(-0.25, 0.25); x += math.sin(ang0) * 45; y += math.cos(ang0) * 45
                if not (0 <= x < w) or y > base: break
                if y < ridge[int(x)] + 6: break                                      # never leave the mountain
                pts.append((x, y))
            if len(pts) < 3: continue
            litside = (np.sign(pts[-1][0] - sx0) * light_from) > 0
            col = tuple(int(c) for c in ((R["hi"] * 0.45 + R["lit"] * 0.55) if litside else (R["deep"] * 0.6 + R["shadow"] * 0.4)))
            if haze and sky_col is not None: col = tuple(int(c * (1 - haze) + s * haze) for c, s in zip(col, sky_col))
            d.line(pts, fill=col, width=rnd.randint(6, 11), joint="curve")
    sang = np.pi / 2 - ang                                               # strokes run down the slopes
    strokes(im, field, sang, 9000 if not haze else 4000, (24, 70), (5, 12), seed, inside, jitter=8)
    return ridge

def flat_rest_ground(im):
    d = ImageDraw.Draw(im); d.rectangle([0, H * 0.74, W, H], fill=(28, 20, 22)); d.rectangle([W * 0.22, H * 0.72, W * 0.78, H * 0.745], fill=(28, 20, 22))
    import draw; draw.person(im, W * 0.43, H * 0.725, 300, "sit", (12, 8, 10)); draw.person(im, W * 0.57, H * 0.725, 300, "sit", (12, 8, 10), -1)


def ground_roles(target):
    if isinstance(target, dict): return {k: np.asarray(v, np.float32) for k, v in target['ground'].items()}
    C = kmeans_colors(target, (0.0, 0.76, 1.0, 1.0), k=10, seed=2); lum = C @ np.array([.3, .59, .11]); o = np.argsort(lum)
    warmth = C[:, 0] - C[:, 2]; rocks = C[np.where((lum > np.percentile(lum, 50)), -np.abs(warmth), -1e9).argmax()]
    plain = kmeans_colors(target, (0.0, 0.70, 1.0, 0.77), k=6, seed=3); pl = plain @ np.array([.3, .59, .11])
    return dict(earth=C[o[0]], dark=C[o[2]], mid=C[o[5]], grass=C[np.where(lum > np.percentile(lum, 60), warmth, -1e9).argmax()],
                rock=rocks, plain_lo=plain[pl.argmin()], plain_hi=plain[pl.argmax()])

def paint_ground(im, G, sun, seed, plain_top, knoll_top, knoll_shoulder):
    rnd = random.Random(seed); h, w = H, W; d = ImageDraw.Draw(im)
    yy = np.arange(h, dtype=np.float32)[:, None] * np.ones((1, w)); xx = np.ones((h, 1)) * np.arange(w, dtype=np.float32)[None, :]
    # sunlit plain between the mountains and the foreground rise
    pt = (yy - plain_top) / (h - plain_top); plain = (yy >= plain_top)
    sunglow = np.clip(1 - np.abs(xx - sun[0]) / (w * 0.6), 0, 1)[..., None]
    hi = G["plain_hi"] * 0.7 + np.array([226, 128, 62], np.float32) * 0.3
    pf = (hi * (1 - np.clip(pt * 3, 0, 1))[..., None] + G["plain_lo"] * np.clip(pt * 3, 0, 1)[..., None])
    pf = pf * (1 - sunglow * 0.15) + np.array([240, 160, 80], np.float32) * sunglow * 0.15
    layer = Image.fromarray(np.clip(pf, 0, 255).astype(np.uint8)); im.paste(layer, (0, 0), Image.fromarray((plain * 255).astype(np.uint8)))
    strokes(im, pf, np.zeros((h, w)) + 0.05, 7000, (20, 60), (4, 9), seed, plain & (yy < knoll_shoulder + 60), jitter=14)
    # the foreground rise: a dome whose top is at knoll_top (centre) and meets the frame edges at knoll_shoulder
    cx = w * 0.5; ridge = knoll_top + (knoll_shoulder - knoll_top) * np.clip(np.abs(xx[0] - cx) / (w * 0.5), 0, 1) ** 1.6
    ridge = ridge + np.asarray(Image.fromarray(np.random.default_rng(seed).normal(0, 1, (1, 30)).astype(np.float32)).resize((w, 1), Image.BICUBIC))[0] * 10
    knoll = yy >= ridge[None, :]
    kt = np.clip((yy - ridge[None, :]) / (h - knoll_top), 0, 1)
    kf = G["mid"] * (1 - np.clip(kt * 4, 0, 1))[..., None] + G["earth"] * np.clip(kt * 4, 0, 1)[..., None]
    im.paste(Image.fromarray(np.clip(kf, 0, 255).astype(np.uint8)), (0, 0), Image.fromarray((knoll * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5)))
    # grass: short upward strokes, glowing where the low sun catches the top edge
    rim = np.clip(1 - (yy - ridge[None, :]) / 380, 0, 1) ** 1.4                      # the low sun warms the upper rise
    warm = np.asarray(G["grass"], np.float32) * 0.5 + np.array([196, 92, 40], np.float32) * 0.5
    gcol = kf * (1 - rim[..., None] * 0.85) + warm * rim[..., None] * 0.85
    gang = -np.pi / 2 + (noise2(h, w, 6, seed + 4) - 0.5) * 0.9
    strokes(im, gcol, gang, 26000, (14, 46), (2, 5), seed + 1, knoll, jitter=22)
    strokes(im, gcol, gang, 9000, (24, 70), (2, 4), seed + 2, knoll & (rim > 0.05), jitter=26)
    return ridge

def paint_figures(im, figs, sun, rim_col, ground_ridge):
    """crisp silhouettes, a warm rim of backlight, and long cast shadows toward the viewer"""
    import draw
    h, w = H, W; sil = Image.new("L", (w, h), 0); sd = Image.new("RGB", (w, h), (0, 0, 0))
    sil = Image.new("L", (w, h), 0)
    for i, (fx, fh, pose, facing) in enumerate(figs):
        base = ground_ridge[int(fx)] + fh * 0.1                                   # sit IN the ground, not on top of it
        if pose.startswith("seated"):
            draw.seated_person(sil, fx, base, fh, hair=pose.split(":")[1] if ":" in pose else "short", facing=facing, seed=i)
        else:
            draw.person(sd, fx, base, fh, pose, (255, 255, 255), facing)
    sil = Image.fromarray(np.maximum(np.asarray(sil), np.asarray(sd.convert("L"))))
    # cast shadows: the silhouette stretched down the slope, away from the sun, softened
    shad = Image.new("L", (w, h), 0)
    for (fx, fh, pose, facing) in figs:
        base = ground_ridge[int(fx)] + 6; dxs = (fx - sun[0]) * 0.25
        poly = [(fx - fh * 0.18, base), (fx + fh * 0.18, base), (fx + fh * 0.5 + dxs, base + fh * 1.9), (fx - fh * 0.35 + dxs, base + fh * 1.9)]
        ImageDraw.Draw(shad).polygon(poly, fill=150)
    shad = shad.filter(ImageFilter.GaussianBlur(18))
    a = np.asarray(im, dtype=np.float32); m = np.asarray(shad, dtype=np.float32)[..., None] / 255
    a = a * (1 - m * 0.75) + np.array([18, 10, 14]) * m * 0.75
    # rim light: a thin warm edge on the sun side of each silhouette
    s = np.asarray(sil, dtype=np.float32) / 255
    sh = np.roll(np.roll(s, 4, axis=0), int(np.sign(w * 0.5 - sun[0]) * 3) or 3, axis=1)
    rim = np.clip(s - sh, 0, 1); rim = np.asarray(Image.fromarray((rim * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5)), dtype=np.float32)[..., None] / 255
    body = np.asarray(Image.fromarray((s * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)), dtype=np.float32)[..., None] / 255
    a = a * (1 - body) + np.array([20, 12, 14]) * body
    a = a * (1 - rim * 0.8) + np.asarray(rim_col, np.float32) * rim * 0.8
    out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    # grass tufts growing in front of each lap, so the figures sit in the hillside
    rnd = random.Random(5); dd = ImageDraw.Draw(out)
    for (fx, fh, pose, facing) in figs:
        base = ground_ridge[int(fx)] + fh * 0.1
        for k in range(70):
            gx = fx + rnd.uniform(-fh * 0.55, fh * 0.55); gy = base + rnd.uniform(-fh * 0.02, fh * 0.08); L = rnd.uniform(fh * 0.06, fh * 0.2)
            lean = rnd.uniform(-0.35, 0.35); col = tuple(int(c) for c in (np.array([150, 70, 34]) * rnd.uniform(0.5, 1.15)).clip(0, 255))
            dd.line([(gx, gy), (gx + math.sin(lean) * L, gy - math.cos(lean) * L)], fill=col, width=rnd.randint(2, 4))
    return out


def place_caption(im, text, avoid=(), font_path=None, size=58):
    """Caption placement (the same rules as the cover lettering):
    no black bar; find the darkest, calmest band in the lower third that clears the figures;
    a soft dark glow behind the letters so they read on anything; safe margins; balanced line breaks."""
    from PIL import ImageFont
    import os
    font_path = font_path or __import__("paths").font("EBGaramond-Italic.ttf")
    f = ImageFont.truetype(font_path, size); d = ImageDraw.Draw(im); margin = int(W * 0.09)
    words = text.split(); maxw = W - 2 * margin
    best_lines = [text]
    for n in range(1, 5):                                   # balanced breaks: fewest lines, most even lengths
        per = math.ceil(len(words) / n); lines = [" ".join(words[i:i + per]) for i in range(0, len(words), per)]
        if all(d.textlength(l, font=f) <= maxw for l in lines): best_lines = lines; break
    lh = int(size * 1.25); block = lh * len(best_lines)
    a = np.asarray(im.convert("L"), dtype=np.float32); gy, gx = np.gradient(a)
    busy = np.hypot(gx, gy); best, by = 1e18, None
    for y in range(int(H * 0.84), int(H * 0.95) - block, 12):          # lower area, inside the bottom safe margin
        band = slice(y - 20, y + block + 20)
        if any(not (y + block < ay0 or y > ay1) for ay0, ay1 in avoid): continue
        cost = a[band, margin:W - margin].mean() * 1.0 + busy[band, margin:W - margin].mean() * 6
        if cost < best: best, by = cost, y
    by = by or int(H * 0.88)
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
    for i, l in enumerate(best_lines):
        x = (W - d.textlength(l, font=f)) / 2; gd.text((x, by + i * lh), l, font=f, fill=(10, 6, 10, 235))
    glow = glow.filter(ImageFilter.GaussianBlur(14)); out = im.convert("RGBA"); out.alpha_composite(glow); out.alpha_composite(glow)
    od = ImageDraw.Draw(out)
    for i, l in enumerate(best_lines):
        x = (W - od.textlength(l, font=f)) / 2; od.text((x, by + i * lh), l, font=f, fill=(247, 238, 218))
    return out.convert("RGB")

# ---------------- clouds v2: billow clusters lit as 3-D domes (lessons from the sky examples) ----------------
def cloud_layout(sun, seed, horizon):
    """designed composition: big masses framing the top and sides, smaller rows toward the horizon, an open window at the sun"""
    rnd = random.Random(seed); masses = []
    rows = [(0.02, 1.5, 6), (0.12, 1.35, 7), (0.22, 1.15, 8), (0.32, 0.95, 9), (0.41, 0.75, 10), (0.49, 0.55, 12), (0.555, 0.4, 14)]
    for fy, scale, n in rows:
        y = H * fy * horizon / 0.62
        for k in range(max(0, int(round(n * CLOUD_AMOUNT)))):
            x = rnd.uniform(-0.1, 1.1) * W
            if abs(x - sun[0]) < W * 0.13 * (1.2 - fy) and fy > 0.3: continue         # keep a window around the sun
            if fy < 0.2 and abs(x - W * 0.5) < W * 0.12 and rnd.random() < 0.4: continue  # a little lighter at top centre
            masses.append((x, y, scale * rnd.uniform(0.7, 1.2)))
    return masses

def billows(cx, base_y, scale, rnd):
    """one cumulus mass: a flat-ish base with rounded puffs heaped on top, biggest in the middle"""
    R0 = 170 * scale; out = []
    width = R0 * rnd.uniform(2.6, 4.4)
    for i in range(int(10 + 14 * scale)):
        t = rnd.uniform(-1, 1); x = cx + t * width / 2
        r = R0 * rnd.uniform(0.35, 0.75) * (1 - 0.55 * abs(t))
        y = base_y - r * rnd.uniform(0.2, 0.9) - (1 - abs(t)) * R0 * rnd.uniform(0.0, 0.7)
        out.append((x, y, r))
    for i in range(int(6 + 8 * scale)):                                   # small puffs along the top edge
        x0, y0, r0 = rnd.choice(out); a = rnd.uniform(-2.6, -0.5)
        out.append((x0 + math.cos(a) * r0 * 0.8, y0 + math.sin(a) * r0 * 0.8, r0 * rnd.uniform(0.3, 0.5)))
    return out

WIND = -0.22   # one wind direction for every cloud (radians; rising to the right)

def paint_sky2(im, sun, target, seed=3, horizon=0.62):
    h, w = H, W; sc = 2; hh, ww = h // sc, w // sc
    yy = (np.arange(hh)[:, None] * sc).astype(np.float32); xx = (np.arange(ww)[None, :] * sc).astype(np.float32)
    S = sky_roles(target); sx, sy = sun
    # clear sky: cool high, warm and glowing toward the sun and horizon
    t = np.clip(yy / (h * horizon), 0, 1)
    sd = np.sqrt((xx - sx) ** 2 + ((yy - sy) * 1.6) ** 2); glow = np.clip(1 - sd / (w * 0.75), 0, 1) ** 1.8
    gapc = S["gap"] * 0.3 + np.array([112, 126, 182], np.float32) * 0.7          # cool blue-grey lavender between clouds
    sky = (gapc * (1 - t[..., None]) + (S["orange"] * 0.5 + S["rim"] * 0.5) * t[..., None])
    sky = sky * (1 - glow[..., None] * 0.6) + S["rim"] * glow[..., None] * 0.6
    sky = np.broadcast_to(sky, (hh, ww, 3)).copy()
    # height field of all billows (each puff a dome), then light it like a 3-D surface
    rnd = random.Random(seed); hf = np.zeros((hh, ww), np.float32); depth = np.zeros((hh, ww), np.float32)
    for mx, my, s in cloud_layout(sun, seed, horizon):
        for bx, by, r in billows(mx, my, s, rnd):
            x0, x1 = int(max(0, (bx - 2 * r) / sc)), int(min(ww, (bx + 2 * r) / sc + 1)); y0, y1 = int(max(0, (by - 1.2 * r) / sc)), int(min(hh, (by + 1.2 * r) / sc + 1))
            if x0 >= x1 or y0 >= y1: continue
            dx = xx[:, x0:x1] - bx; dy = yy[y0:y1] - by
            ca, sa = math.cos(WIND), math.sin(WIND); u = (dx * ca + dy * sa) / 1.35; v = (-dx * sa + dy * ca) / 0.92
            dome = np.sqrt(np.clip(r * r - u ** 2 - v ** 2, 0, None))
            hf[y0:y1, x0:x1] = np.maximum(hf[y0:y1, x0:x1], dome); depth[y0:y1, x0:x1] = np.where(dome > 0, np.maximum(depth[y0:y1, x0:x1], my), depth[y0:y1, x0:x1])
    for k in range(9):                                                     # long low streaks near the horizon
        by = h * horizon * rnd.uniform(0.62, 0.95); bx = rnd.uniform(-0.1, 0.9) * w; L = w * rnd.uniform(0.25, 0.6)
        x0, x1 = int(max(0, bx / sc)), int(min(ww, (bx + L) / sc)); y0, y1 = int(max(0, (by - 30) / sc)), int(min(hh, (by + 30) / sc))
        if x0 >= x1 or y0 >= y1: continue
        u = (xx[:, x0:x1] - bx) / L; thick = 22 * np.sin(np.clip(u, 0, 1) * np.pi) ** 0.6 * (0.6 + 0.4 * np.sin(u * 31 + k))
        dome = np.clip(thick - np.abs(yy[y0:y1] - by), 0, None) * 0.9
        hf[y0:y1, x0:x1] = np.maximum(hf[y0:y1, x0:x1], dome); depth[y0:y1, x0:x1] = np.where(dome > 0, by, depth[y0:y1, x0:x1])
    from scipy.ndimage import gaussian_filter
    hfs = gaussian_filter(hf, 1.5); gy, gx = np.gradient(hfs, sc)
    N = np.dstack([-gx, -gy, np.ones_like(hfs)]); N /= np.linalg.norm(N, axis=2, keepdims=True)
    L = np.dstack([sx - xx + 0 * yy, (sy - yy) + 0 * xx, np.full((hh, ww), w * 0.35)]); L /= np.linalg.norm(L, axis=2, keepdims=True)
    lam = np.clip((N * L).sum(2), 0, 1)
    mask = np.clip(hf / 6, 0, 1)
    edge = np.clip(mask - np.clip(hf / 30, 0, 1), 0, 1)                    # thin outer band of each cloud
    far = np.clip(depth / (h * horizon), 0, 1)                             # lower rows: lighter, warmer, hazier
    shadow = S["body"] * 0.55 + np.array([78, 44, 78], np.float32) * 0.45  # deep plum shadow side
    lit = S["orange"] * 0.4 + np.array([250, 122, 36], np.float32) * 0.6; rim = S["rim"] * 0.3 + np.array([255, 200, 90], np.float32) * 0.7   # hot, vivid
    lam = np.clip((lam - 0.25) * 1.6, 0, 1) ** 0.9                         # crisper light/shadow split
    col = shadow * (1 - lam[..., None]) + (S["rose"] * 0.4 + lit * 0.6) * lam[..., None]
    col = col * (1 - (edge * lam)[..., None] * 0.9) + rim * (edge * lam)[..., None] * 0.9       # glowing rims facing the sun
    col = col * (1 - far[..., None] * 0.35) + (S["rose"] * 0.5 + S["rim"] * 0.5) * far[..., None] * 0.35
    field = sky * (1 - mask[..., None]) + col * mask[..., None]
    lum = field.mean(2, keepdims=True); field = np.clip(lum + (field - lum) * 1.25, 0, 255)
    core = np.clip(1 - sd / 40, 0, 1) ** 0.6; halo = np.clip(1 - sd / 300, 0, 1) ** 2
    field = field * (1 - halo[..., None] * 0.6) + np.array([255, 230, 180]) * halo[..., None] * 0.6
    field = field * (1 - core[..., None]) + np.array(SUN_COLOR, np.float32) * core[..., None]
    big = np.asarray(Image.fromarray(field.astype(np.uint8)).resize((w, h), Image.BICUBIC), dtype=np.float32)
    im.paste(Image.fromarray(big.astype(np.uint8)).crop((0, 0, w, int(h * horizon) + 40)), (0, 0))
    # brushstrokes curve around each billow (tangent to the dome), loose and horizontal in clear sky
    Nb = np.asarray(Image.fromarray(((np.arctan2(N[..., 1], N[..., 0]) + np.pi) / (2 * np.pi) * 255).astype(np.uint8)).resize((w, h)), dtype=np.float32) / 255 * 2 * np.pi - np.pi
    mb = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).resize((w, h)), dtype=np.float32) / 255
    tang = Nb + np.pi / 2; tang = np.where(np.cos(tang - WIND) < 0, tang + np.pi, tang)       # tangent pointed along the wind
    dev = np.clip(np.angle(np.exp(1j * (tang - WIND))), -1.05, 1.05)                        # strokes may wrap around each lump
    ang = np.where(mb > 0.5, WIND + dev * 0.8, WIND * 0.6)
    # smooth the direction field so neighbouring strokes flow together (no crosshatching)
    from scipy.ndimage import gaussian_filter as _gf
    c2, s2 = _gf(np.cos(2 * ang), 22), _gf(np.sin(2 * ang), 22); ang = 0.5 * np.arctan2(s2, c2)
    yb = np.arange(h)[:, None] * np.ones((1, w)); keep = (yb < h * (horizon + 0.02)) & (np.sqrt((np.arange(w)[None, :] - sx) ** 2 + (yb - sy) ** 2) > 45)
    strokes_soft(im, big, ang, 14000, (80, 200), (16, 30), seed, keep, jitter=7, alpha=165)     # broad soft brush
    strokes_soft(im, big, ang, 12000, (34, 90), (7, 15), seed + 1, keep, jitter=9, alpha=185)
    sky_part = im.crop((0, 0, w, int(h * (horizon + 0.02)))).filter(ImageFilter.GaussianBlur(1.1))   # wet blending
    im.paste(sky_part, (0, 0))
    return im


def strokes_soft(canvas, colorfield, angle, n, length, width, seed, mask=None, jitter=10, alpha=170, batches=4):
    """round-ended, slightly translucent strokes laid in batches so neighbours blend like wet paint"""
    n = int(n * QUALITY); rnd = random.Random(seed); h, w = colorfield.shape[:2]; per = max(1, n // batches)
    for b in range(batches):
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
        for _ in range(per):
            x, y = rnd.uniform(0, w - 1), rnd.uniform(0, h - 1)
            if mask is not None and not mask[int(y), int(x)]: continue
            c = colorfield[int(y), int(x)]; col = tuple(int(np.clip(v + rnd.uniform(-jitter, jitter), 0, 255)) for v in c) + (alpha,)
            a = angle[int(y), int(x)] + rnd.uniform(-0.15, 0.15); L = rnd.uniform(*length); wd = int(rnd.uniform(*width))
            pts = []
            for k in range(5):
                tt = (k / 4 - 0.5) * L; bend = math.sin(k * 0.9) * L * 0.05
                pts.append((x + math.cos(a) * tt - math.sin(a) * bend, y + math.sin(a) * tt + math.cos(a) * bend))
            d.line(pts, fill=col, width=wd, joint="curve")
            for (px, py), s in ((pts[0], 0.5), (pts[-1], 0.5)):              # rounded ends
                r = wd * s; d.ellipse([px - r, py - r, px + r, py + r], fill=col)
        canvas.paste(Image.alpha_composite(canvas.convert("RGBA"), layer).convert("RGB"))

# ---------------- rocks v2: faceted blocks with three planes, cracks, mottling, cast shadows ----------------
def paint_rock(im, cx, cy, size, sun, G, rnd):
    """a flat, dark slab: wider than tall, tilted, cool lit top plane with a thin warm edge, violet underside"""
    d = ImageDraw.Draw(im, "RGBA"); tilt = rnd.uniform(-0.25, 0.25); wr, hr = size * rnd.uniform(1.4, 2.0), size * rnd.uniform(0.45, 0.7)
    n = rnd.randint(6, 9); pts = []
    for i in range(n):
        a = -math.pi + 2 * math.pi * i / n + rnd.uniform(-0.3, 0.3); rr = rnd.uniform(0.75, 1.05)
        x, y = math.cos(a) * wr * rr, math.sin(a) * hr * rr * (0.7 if math.sin(a) > 0 else 1.0)
        pts.append((cx + x * math.cos(tilt) - y * math.sin(tilt), cy + x * math.sin(tilt) + y * math.cos(tilt)))
    lx = 1 if sun[0] > cx else -1
    sh = Image.new("L", im.size, 0); ImageDraw.Draw(sh).ellipse([cx - wr * 1.1 - lx * wr * 0.25, cy, cx + wr * 1.1 - lx * wr * 0.25, cy + hr * 1.3], fill=180)
    sh = sh.filter(ImageFilter.GaussianBlur(hr * 0.35)); arr = np.asarray(im, dtype=np.float32); m = np.asarray(sh, dtype=np.float32)[..., None] / 255
    arr = arr * (1 - m * 0.5) + np.array([34, 20, 40]) * m * 0.5; im.paste(Image.fromarray(arr.astype(np.uint8))); d = ImageDraw.Draw(im, "RGBA")
    stone = np.asarray(G["rock"], np.float32) * 0.45 + np.array([70, 62, 80], np.float32) * 0.55          # dark grey-violet
    d.polygon(pts, fill=tuple(int(c) for c in stone * rnd.uniform(0.6, 0.8)))                                 # body
    cyc = sum(p[1] for p in pts) / len(pts)
    top = sorted([p for p in pts if p[1] <= cyc], key=lambda p: p[0])
    if len(top) >= 2:                                                                                        # cool lit top plane
        inner = [(x, y + hr * 0.35) for x, y in reversed(top)]
        d.polygon(top + inner, fill=tuple(int(min(255, c)) for c in stone * 1.15 + np.array([12, 10, 20])))
        d.line(top, fill=(232, 150, 92, 220), width=max(2, int(size * 0.045)))                              # thin warm sunlit edge
    low = sorted([p for p in pts if p[1] > cyc], key=lambda p: p[0])
    if len(low) >= 2: d.line(low, fill=(28, 18, 32, 200), width=max(3, int(size * 0.12)))                    # dark underside
    for _ in range(rnd.randint(1, 2) if size > 45 else 0):                                                    # a crack or two
        x, y = cx + rnd.uniform(-wr * 0.5, wr * 0.5), cyc - hr * 0.2; path = [(x, y)]
        for k in range(rnd.randint(2, 4)): x += rnd.uniform(-wr * 0.15, wr * 0.15); y += rnd.uniform(hr * 0.1, hr * 0.3); path.append((x, y))
        d.line(path, fill=(20, 14, 22, 220), width=max(2, int(size * 0.03)))
    return im

def scatter_rocks(im, ridge, sun, G, seed, top_y):
    """few big boulders, many small stones (power law); bigger toward the viewer; drawn back to front"""
    rnd = random.Random(seed); rocks = []
    for _ in range(26):
        if rnd.random() < 0.6: x = rnd.gauss(W * 0.5, W * 0.2); y = rnd.uniform(top_y + 20, top_y + (H - top_y) * 0.45)   # clustered near the summit
        else: x = rnd.uniform(W * 0.02, W * 0.98); y = rnd.uniform(top_y + 40, H * 0.97)
        x = min(max(x, 10), W - 10)
        if y < ridge[int(x)] + 30: continue
        near = (y - top_y) / (H - top_y); size = min(120, 26 * (1 / max(rnd.random(), 0.08)) ** 0.5) * (0.6 + 1.0 * near)
        rocks.append((y, x, size))
    for y, x, s in sorted(rocks): paint_rock(im, x, y, s, sun, G, rnd)
    # grass grows back over the rocks' bases so they sit IN the ground
    yy = np.arange(H)[:, None] * np.ones((1, W)); knoll = yy > ridge[None, :] + 10
    gf = np.zeros((H, W, 3), np.float32) + np.asarray(G["grass"], np.float32) * 0.7
    strokes(im, gf, np.full((H, W), -np.pi / 2), 2500, (16, 44), (2, 4), seed + 9, knoll, jitter=30)
    return im

# ---------------- grass v2: clumps of tapered, curved blades, painted in layers (dark base, mid, bright tips) ----------------
def blade(d, x, y, L, w, ang, bend, col):
    """one tapered, curved blade: thick at the base, a fine point at the tip"""
    pts_l, pts_r = [], []
    for k in range(6):
        t = k / 5; a = ang + bend * t * t; px = x + math.sin(a) * L * t; py = y - math.cos(a) * L * t
        ww = w * (1 - t) ** 0.8; nx, ny = math.cos(a), math.sin(a)
        pts_l.append((px - nx * ww, py - ny * ww)); pts_r.append((px + nx * ww, py + ny * ww))
    d.polygon(pts_l + pts_r[::-1], fill=col)

def paint_grass2(im, ridge, sun, G, seed, top_y):
    rnd = random.Random(seed); h, w = H, W
    yy = np.arange(h, dtype=np.float32)[:, None] * np.ones((1, w)); xx = np.ones((h, 1)) * np.arange(w, dtype=np.float32)[None, :]
    knoll = yy > ridge[None, :] + 4
    # 1) big light and shade patches across the hillside (mounds lit, hollows dark)
    patch = noise2(h // 4, w // 4, 5, seed + 3); patch = np.asarray(Image.fromarray(patch).resize((w, h), Image.BICUBIC))
    near = np.clip((yy - top_y) / (h - top_y), 0, 1)
    rim = np.clip(1 - (yy - ridge[None, :]) / 420, 0, 1) ** 1.3            # the low sun warms the upper rise
    dark = np.asarray(G["earth"], np.float32) * 0.6 + np.array([34, 18, 22], np.float32) * 0.4
    mid = np.asarray(G["dark"], np.float32) * 0.5 + np.array([92, 44, 30], np.float32) * 0.5
    lit = np.asarray(G["grass"], np.float32) * 0.4 + np.array([212, 104, 44], np.float32) * 0.6
    light = np.clip((patch - 0.45) * 2.2 + rim * 0.8 - near * 0.35, 0, 1)[..., None]
    base = dark * (1 - light) + mid * light
    a = np.asarray(im, dtype=np.float32); km = knoll[..., None]
    a = np.where(km, base, a); im.paste(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)))
    d = ImageDraw.Draw(im)
    # 2) clumps, back to front: each a fan of blades painted dark -> mid -> a few bright tips
    clumps = []
    for _ in range(int(2600 * QUALITY)):
        x = rnd.uniform(0, w - 1); y = rnd.uniform(top_y, h + 40)
        if y < ridge[int(x)] + 6: continue
        clumps.append((y, x))
    for y, x in sorted(clumps):
        nr = np.clip((y - top_y) / (h - top_y), 0, 1); size = (18 + 120 * nr ** 1.4) * rnd.uniform(0.6, 1.4)
        lv = float(light[min(int(y), h - 1), int(x), 0]); ws = 1.2 + 4.5 * nr
        nb = rnd.randint(5, 9)
        for layer, (cbase, frac, lenf) in enumerate(((dark * 0.9, 1.0, 0.7), (mid * (0.8 + 0.4 * lv), 0.8, 0.95), (lit * (0.7 + 0.5 * lv), 0.35 + 0.5 * lv, 1.05))):
            for _ in range(int(nb * frac)):
                ang = rnd.gauss(0, 0.32); bend = rnd.uniform(-0.5, 0.5); L = size * lenf * rnd.uniform(0.6, 1.25)
                col = tuple(int(c) for c in np.clip(cbase * rnd.uniform(0.85, 1.15), 0, 255))
                blade(d, x + rnd.uniform(-size * 0.25, size * 0.25), y, L, ws * rnd.uniform(0.7, 1.3), ang, bend, col)
        if rnd.random() < 0.03 and nr > 0.15:                               # an occasional tall seed stalk
            L = size * rnd.uniform(1.6, 2.4); ang = rnd.gauss(0, 0.2)
            d.line([(x, y), (x + math.sin(ang) * L, y - math.cos(ang) * L)], fill=tuple(int(c) for c in lit * 0.9), width=max(1, int(ws * 0.5)))
            tx, ty = x + math.sin(ang) * L, y - math.cos(ang) * L
            d.ellipse([tx - ws * 1.5, ty - ws * 4, tx + ws * 1.5, ty + ws * 1.5], fill=tuple(int(c) for c in lit))
    return im

# ---------------- rock surface: fractured plates, each a lit facet; dark cracks with lit lips; strata; grain ----------------
def rock_surface(w, h, seed, light=(-0.6, -0.8), base=(120, 100, 96), scale=1.0, strata=0.35):
    """returns an RGB float array (h, w, 3) of fractured rock lit from `light` (screen x,y direction toward the light)"""
    from scipy.ndimage import gaussian_filter, maximum_filter, minimum_filter
    rng = np.random.default_rng(seed); sc = 3; hh, ww = h // sc + 1, w // sc + 1
    n = int(ww * hh / (900 * scale * scale)) + 8
    pts = np.stack([rng.uniform(0, ww, n), rng.uniform(0, hh, n)], 1)
    yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
    d1 = np.full((hh, ww), 1e9, np.float32); d2 = np.full((hh, ww), 1e9, np.float32); lab = np.zeros((hh, ww), np.int32)
    for i, (px, py) in enumerate(pts):                                  # Voronoi plates (nearest + second-nearest distance)
        dd = (xx - px) ** 2 + ((yy - py) * 1.6) ** 2                     # squashed: plates read as layered rock
        closer = dd < d1; d2 = np.where(closer, d1, np.minimum(d2, dd)); d1 = np.where(closer, dd, d1); lab = np.where(closer, i, lab)
    crack = np.clip(1 - (np.sqrt(d2) - np.sqrt(d1)) / 1.6, 0, 1)        # thin dark lines where plates meet
    # each plate is a tilted facet: its own normal, lit by the light direction
    nx = rng.normal(0, 0.55, n); ny = rng.normal(-0.25, 0.55, n)        # plates tend to face slightly up
    L = np.array(light, np.float32); L /= np.linalg.norm(L)
    facet = np.clip(0.55 + (nx[lab] * -L[0] + ny[lab] * -L[1]) * 0.5, 0.08, 1.0)
    tone = rng.uniform(0.85, 1.15, n)[lab]                              # each plate a slightly different stone
    strat = 1 + strata * 0.25 * np.sin(yy * 0.9 + gaussian_filter(rng.normal(0, 4, (hh, ww)), 6))
    grain = 1 + 0.12 * (rng.random((hh, ww)) - 0.5) + 0.1 * gaussian_filter(rng.normal(0, 1, (hh, ww)), 2)
    roll = np.clip(1 - np.sqrt(d1) / 18, 0, 1) * 0.35                   # light rolls across each plate (not flat colour)
    gy_, gx_ = np.gradient(gaussian_filter(np.sqrt(d1), 1.5)); roll2 = np.clip((gx_ * -L[0] + gy_ * -L[1]) * 0.6, -0.3, 0.3)
    fine = 1 + 0.22 * gaussian_filter(rng.normal(0, 1, (hh, ww)), 0.7)        # stronger granular texture
    val = facet * tone * strat * grain * fine * (0.85 + roll) + roll2
    lip = np.clip(np.roll(crack, 2, 0) - crack, 0, 1) * 0.6             # thin lit lip just below each crack
    col = np.asarray(base, np.float32)[None, None, :] * val[..., None]
    col = col * (1 - crack[..., None] * 0.85) + np.array([16, 12, 16], np.float32) * crack[..., None] * 0.85
    col = col + lip[..., None] * np.array([60, 50, 44], np.float32)
    big = np.asarray(Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), dtype=np.float32)
    return big
