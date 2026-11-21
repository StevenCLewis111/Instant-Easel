"""
brushes.py: the app's brush engine.
Every brush = a TIP (shape, softness, bristles, a stamp picture...) laid down along the stroke as dabs, with spacing, pressure,
jitter, scatter, texture and a blend mode. Special brushes (smudge, blur, sharpen, clone, neon, drips, vines, hatching, sketch,
particles...) do more than lay down a dab.

How a stroke builds up (the way SketchBook / Krita do it):
  * Flow is how much each dab adds. Dabs build up inside the stroke, but never past 100%.
  * Opacity is the most the whole stroke can cover: a 50% stroke is 50% see-through everywhere, however often the dabs overlap.
    (begin_stroke() / end_stroke() bracket one stroke painted in pieces as the mouse moves.)
  * Pressure (a pen, or the mouse's speed) changes size and/or opacity by each brush's own amounts (size_press, opac_press).
  * Dabs are evenly spaced along the whole stroke, even when it arrives in pieces.

    canvas = Canvas(1200, 800, paper=(244, 238, 226))
    canvas.stroke(points, "oil", color=(200, 90, 40), size=40, opacity=1.0)
"""
import math, random, colorsys
import numpy as np
from PIL import Image
import brush_art as ART

def _grain(h, w, seed=3, scale=1.0):
    rng = np.random.default_rng(seed); g = rng.random((h, w)).astype(np.float32)
    small = rng.random((max(2, h // 6), max(2, w // 6))).astype(np.float32)
    g = 0.6 * g + 0.4 * np.asarray(Image.fromarray(small).resize((w, h), Image.BICUBIC))
    return g

# ---------------- tips: return an alpha mask (0..1) of size s x s for one dab ----------------
def tip_round(s, hard=0.8, roundness=1.0, angle=0.0, **k):
    if s <= 3 and roundness >= 0.99: return np.ones((s, s), np.float32)  # tiny tips: a solid dot (fixes thin lines)
    y, x = np.mgrid[-1:1:s * 1j, -1:1:s * 1j]
    if roundness < 0.99:
        ca, sa = math.cos(angle), math.sin(angle); x, y = x * ca + y * sa, (-x * sa + y * ca) / max(0.05, roundness)
    r = np.sqrt(x * x + y * y) * (s / (s + 1.0))
    return (np.clip((1 - r) / max(1e-3, 1 - hard), 0, 1) * (r <= 1)).astype(np.float32)

def tip_soft(s, roundness=1.0, angle=0.0, hard=0.0, **k):
    """an airbrush tip: a soft glow. Hardness makes a solid middle that much of the radius, with the soft edge outside it"""
    y, x = np.mgrid[-1:1:s * 1j, -1:1:s * 1j]
    if roundness < 0.99:
        ca, sa = math.cos(angle), math.sin(angle); x, y = x * ca + y * sa, (-x * sa + y * ca) / max(0.05, roundness)
    r = np.sqrt(x * x + y * y); hard = min(0.95, max(0.0, hard)); u = np.clip((r - hard) / (1 - hard), 0, None)
    return np.clip(np.exp(-u * u * 4.5) - 0.01, 0, 1).astype(np.float32)

def tip_ellipse(s, aspect=0.35, angle=0.0, hard=0.85, **k):
    y, x = np.mgrid[-1:1:s * 1j, -1:1:s * 1j]; ca, sa = math.cos(angle), math.sin(angle)
    u, v = x * ca + y * sa, (-x * sa + y * ca) / aspect; r = np.sqrt(u * u + v * v)
    return (np.clip((1 - r) / max(1e-3, 1 - hard), 0, 1) * (r <= 1)).astype(np.float32)

def tip_rect(s, aspect=0.25, angle=0.0, hard=None, **k):
    """a flat tip. hard (Hardness): how much of it is solid; the rest fades to its edges (None: crisp, a one-pixel soft edge)"""
    y, x = np.mgrid[-1:1:s * 1j, -1:1:s * 1j]; ca, sa = math.cos(angle), math.sin(angle)
    u, v = x * ca + y * sa, -x * sa + y * ca
    soft = 2.0 / max(s, 2)                                               # a one-pixel soft edge (no jaggies)
    if hard is not None and hard < 0.97:
        su, sv = max(soft, (1 - hard) * 0.95), max(soft, (1 - hard) * aspect)
        return (np.clip((0.95 - np.abs(u)) / su, 0, 1) * np.clip((aspect - np.abs(v)) / sv, 0, 1)).astype(np.float32)
    return (np.clip((0.95 - np.abs(u)) / soft + 0.5, 0, 1) * np.clip((aspect - np.abs(v)) / soft + 0.5, 0, 1)).astype(np.float32)

def tip_bristles(s, n=14, aspect=0.3, angle=0.0, seed=0, **k):
    rng = random.Random(seed); m = np.zeros((s, s), np.float32); ca, sa = math.cos(angle), math.sin(angle); y, x = np.ogrid[:s, :s]
    for i in range(n):
        off = (i / max(1, n - 1) - 0.5) * 1.8; r = rng.uniform(0.04, 0.09) * s
        cx = s / 2 + off * s / 2 * ca * 0.9; cy = s / 2 + off * s / 2 * sa * 0.9
        m = np.maximum(m, ((x - cx) ** 2 + (y - cy) ** 2 <= r * r) * rng.uniform(0.55, 1.0))
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
    return (base * holes * rng.uniform(0.5, 1.0, (s, s))).astype(np.float32)

def tip_shape(s, kind="star", angle=0.0, **k): return ART.shape_mask(kind, s, angle)

HARD_TIPS = (tip_round, tip_ellipse, tip_rect, tip_soft)                  # tips Hardness and Round change (made from a formula;
                                                                         # pictured tips - bristles, sponge, fan, shapes, stamps - aren't)
_tips = {}
def _tip(fn, s, ta):
    """tips are made once per size / angle and kept (making them for every dab was the slowest part of painting)"""
    key = (fn, s) + tuple(sorted((k_, round(v, 2) if isinstance(v, float) else v) for k_, v in ta.items()))
    m = _tips.get(key)
    if m is None:
        if len(_tips) > 6000: _tips.clear()
        ang = ta.get("angle", 0.0)
        if s > 48 and isinstance(ang, float) and abs(ang) > 1e-3 and fn is not tip_shape:     # big tips: turn the straight one (much faster than redrawing it)
            base = _tip(fn, s, dict(ta, angle=0.0))
            m = np.asarray(Image.fromarray(base, "F").rotate(-math.degrees(ang), resample=Image.BILINEAR), np.float32)
        else: m = fn(s, **ta).astype(np.float32) if s > 3 else None
        if m is None or m.max() < 0.35: m = np.ones((s, s), np.float32) if fn is not tip_sponge else np.full((s, s), 0.7, np.float32)   # a 1-3 pixel brush: a solid dot, never nothing
        _tips[key] = m
    return m

_tipcs = {}
def _tipc(fn, s, ta):
    """the tip cut down to where it actually has paint (a flat brush turned diagonally is mostly empty corners), with where
    that piece sits in the full square: (piece, x offset, y offset, full size). Big brushes paint much faster this way"""
    key = (fn, s, tuple(sorted((k_, round(v, 2) if isinstance(v, float) else v) for k_, v in ta.items())))
    r = _tipcs.get(key)
    if r is None:
        m = _tip(fn, s, ta); ys = np.flatnonzero(m.max(1) > 0.003); xs = np.flatnonzero(m.max(0) > 0.003)
        if len(ys) and (len(ys) < s or len(xs) < s): r = (np.ascontiguousarray(m[ys[0]:ys[-1] + 1, xs[0]:xs[-1] + 1]), int(xs[0]), int(ys[0]), s)
        else: r = (m, 0, 0, s)
        if len(_tipcs) > 6000: _tipcs.clear()
        _tipcs[key] = r
    return r

# ---------------- brushes: name -> settings ----------------
B = {}
def brush(name, tip, spacing=0.15, size_scale=1.0, jitter_size=0.0, jitter_angle=0.0, scatter=0.0, color_jitter=0.0, grain=0.0,
          mode="normal", flow=1.0, taper=False, angle_follow=False, special=None, size_press=1.0, opac_press=0.0, opacity_jitter=0.0,
          hue_jitter=0.0, tex=None, tex_mode="mask", tex_strength=0.85, stamp=None, shape=None, **tipargs):
    """size_press / opac_press: how much pressure (pen, or mouse speed) changes size / opacity (0 = not at all, 1 = fully).
    tex: a texture or pattern laid in canvas space; tex_mode "mask" (holes in the paint), "color" (light and dark in your colour) or
    "pattern" (only the pattern's motif). stamp: a picture from images/UI/Stamps. shape: a decorative shape (star, heart...)."""
    B[name] = dict(tip=tip, spacing=spacing, size_scale=size_scale, jitter_size=jitter_size, jitter_angle=jitter_angle, scatter=scatter,
                   color_jitter=color_jitter, grain=grain, mode=mode, flow=flow, taper=taper, angle_follow=angle_follow,
                   special=special, size_press=size_press, opac_press=opac_press, opacity_jitter=opacity_jitter, hue_jitter=hue_jitter,
                   tex=tex, tex_mode=tex_mode, tex_strength=tex_strength, stamp=stamp, shape=shape, tipargs=tipargs)

# traditional brushes (spacing in brush widths: 0.1 = a dab every tenth of the width, smooth; flat tips need less)
brush("round", tip_round, hard=0.85, spacing=0.1, size_press=0.6)
brush("flat", tip_rect, aspect=0.22, angle_follow=True, spacing=0.05, size_press=0.3, opac_press=0.3)
brush("bright", tip_rect, aspect=0.35, angle_follow=True, spacing=0.05, grain=0.15, size_press=0.3)
brush("filbert", tip_ellipse, aspect=0.38, angle_follow=True, spacing=0.06, size_press=0.5)
brush("fan", tip_fan, angle_follow=True, spacing=0.05, color_jitter=0.08, flow=0.5, size_press=0.2, opac_press=0.5)
brush("angular", tip_rect, aspect=0.2, angle=0.6, spacing=0.05, size_press=0.4)
brush("dagger", tip_ellipse, aspect=0.18, angle=0.5, hard=0.9, taper=True, spacing=0.05)
brush("liner (rigger)", tip_round, hard=0.9, taper=True, spacing=0.05)
brush("script", tip_round, hard=0.95, taper=True, spacing=0.04)
brush("mop", tip_soft, spacing=0.1, flow=0.35, size_press=0.2, opac_press=0.8)
brush("spotter", tip_round, hard=0.95, spacing=0.08)
brush("palette knife", tip_rect, aspect=0.08, angle_follow=True, spacing=0.03, special="knife", size_press=0.0)
# dry media: pressure mostly changes how dark, like the real thing
brush("pencil", tip_round, hard=0.6, grain=0.75, spacing=0.1, flow=0.6, size_press=0.25, opac_press=0.8)
brush("charcoal", tip_ellipse, aspect=0.5, angle_follow=True, grain=0.85, spacing=0.08, flow=0.7, jitter_angle=0.3, size_press=0.3, opac_press=0.7)
brush("pastel / chalk", tip_ellipse, aspect=0.6, grain=0.7, spacing=0.08, flow=0.8, scatter=0.05, size_press=0.3, opac_press=0.6)
brush("crayon", tip_round, hard=0.7, grain=0.9, spacing=0.06, flow=0.9, size_press=0.2, opac_press=0.6)
brush("ink pen", tip_round, hard=1.0, taper=True, spacing=0.03)
brush("technical pen", tip_round, hard=1.0, spacing=0.03, size_press=0.0)
brush("fountain pen", tip_ellipse, aspect=0.45, angle=0.6, hard=0.95, spacing=0.03, taper=True, size_press=0.7)
brush("calligraphy", tip_rect, aspect=0.12, angle=0.78, spacing=0.03, size_press=0.5)
brush("marker", tip_rect, aspect=0.6, angle_follow=True, spacing=0.06, mode="multiply", flow=0.5, size_press=0.0, opac_press=0.2)
brush("ink", tip_round, hard=0.95, spacing=0.04, size_press=0.8)
# wet media
brush("watercolor", tip_soft, spacing=0.06, flow=0.32, mode="multiply", special="wet_edge", grain=0.2, size_press=0.3, opac_press=0.6)
brush("oil", tip_bristles, n=16, aspect=0.3, angle_follow=True, spacing=0.05, color_jitter=0.05, special="impasto", size_press=0.4)
brush("gouache", tip_ellipse, aspect=0.55, angle_follow=True, hard=0.95, spacing=0.06, grain=0.1, size_press=0.4)
brush("acrylic", tip_round, hard=0.9, spacing=0.06, color_jitter=0.03, size_press=0.5)
brush("airbrush", tip_soft, spacing=0.08, flow=0.12, size_press=0.0, opac_press=1.0)
brush("dry brush", tip_bristles, n=10, aspect=0.4, angle_follow=True, spacing=0.06, grain=0.8, size_press=0.3, opac_press=0.4)
brush("sponge", tip_sponge, spacing=0.4, jitter_angle=3.14, flow=0.8, size_press=0.2)
brush("splatter", tip_round, hard=0.9, spacing=0.35, scatter=1.6, jitter_size=0.9, size_scale=0.28, size_press=0.3)
# Krita-style engines
brush("bristle", tip_bristles, n=22, aspect=0.45, angle_follow=True, spacing=0.04, color_jitter=0.08, size_press=0.4)
brush("spray", tip_round, hard=0.9, spacing=0.2, scatter=1.0, jitter_size=0.8, flow=0.8, special="spray", size_press=0.0, opac_press=0.6)
MOVING_ONLY = ("particle", "sketch", "hatching", "curve", "grid", "shape", "grass", "swirl", "flourish", "vine")   # drawn along the path: nothing from a bare click
brush("particle", tip_round, special="particle")
brush("sketch", tip_round, special="sketch")
brush("hatching", tip_round, special="hatching")
brush("curve", tip_round, special="curve")
brush("grid", tip_round, special="grid")
brush("shape", tip_round, special="shape")
brush("smudge / blender", tip_soft, spacing=0.05, special="smudge")
brush("blur (filter)", tip_soft, spacing=0.2, special="blur")
brush("sharpen", tip_soft, spacing=0.25, special="sharpen")
brush("deform (push)", tip_soft, spacing=0.1, special="deform")
brush("clone", tip_soft, spacing=0.1, special="clone")
brush("glaze", tip_soft, spacing=0.1, flow=0.2, mode="multiply")
brush("glow (dodge)", tip_soft, spacing=0.1, flow=0.25, mode="screen")
brush("eraser", tip_round, hard=0.8, mode="erase", spacing=0.08, size_press=0.5)
# subject brushes
brush("grass blades", tip_round, special="grass")
brush("foliage", tip_ellipse, aspect=0.5, spacing=0.5, scatter=1.2, jitter_size=0.6, jitter_angle=3.14, color_jitter=0.15, size_press=0.4)
brush("stipple", tip_round, hard=1.0, spacing=0.12, scatter=0.9, jitter_size=0.5, size_scale=0.12, size_press=0.3)
# special brushes
brush("neon", tip_soft, spacing=0.06, special="neon", size_press=0.4)
brush("drip", tip_round, hard=0.9, spacing=0.08, special="drip", size_press=0.5)
brush("pattern brush", tip_shape, shape="diamond", kind="diamond", spacing=1.3, angle_follow=True, size_scale=0.8, size_press=0.4)
# decorative brushes: little shapes scattered (or in a row) along the stroke
brush("stars", tip_shape, kind="star", spacing=1.4, size_scale=0.7, jitter_size=0.25, jitter_angle=0.4, size_press=0.4)
brush("sparkles", tip_shape, kind="sparkle", spacing=0.9, scatter=0.9, jitter_size=0.6, jitter_angle=0.5, size_scale=0.6, hue_jitter=0.05)
brush("hearts", tip_shape, kind="heart", spacing=1.4, size_scale=0.7, jitter_angle=0.3, jitter_size=0.15, size_press=0.4)
brush("confetti", tip_shape, kind="confetti", spacing=0.6, scatter=1.2, jitter_size=0.4, jitter_angle=3.14, size_scale=0.35, hue_jitter=1.0)
brush("petals", tip_shape, kind="petal", spacing=0.8, scatter=1.0, jitter_size=0.4, jitter_angle=3.14, size_scale=0.5, color_jitter=0.12)
brush("snowflakes", tip_shape, kind="snow", spacing=1.0, scatter=1.1, jitter_size=0.6, jitter_angle=3.14, size_scale=0.55)
brush("bubbles", tip_shape, kind="bubble", spacing=1.0, scatter=0.9, jitter_size=0.6, size_scale=0.6, flow=0.85)
brush("dots brush", tip_shape, kind="dot", spacing=1.5, size_scale=0.5, size_press=0.5)
brush("ribbons", tip_rect, aspect=0.16, angle_follow=True, spacing=0.04, special="ribbon", size_press=0.2)
brush("swirls", tip_round, special="swirl")
brush("flourish", tip_round, special="flourish")
brush("vines", tip_round, special="vine")
# texture brushes: a soft dab with a texture worked through it (canvas-aligned, so overlapping strokes line up)
for _n, _t in (("grain", "grain"), ("noise texture", "noise"), ("sand", "sand"), ("spray texture", "spraytex"), ("fabric texture", "fabric"),
               ("paper texture", "paper"), ("grunge texture", "grunge"), ("concrete", "concrete"), ("rust", "rust"), ("mosaic", "mosaic"),
               ("crackle", "crackle")):
    brush(_n, tip_round, hard=0.45, spacing=0.12, flow=0.8, tex=_t, tex_mode="mask", tex_strength=0.9, size_press=0.3, opac_press=0.5)
brush("bokeh", tip_shape, kind="bokeh", spacing=0.9, scatter=1.4, jitter_size=0.8, size_scale=0.7, hue_jitter=0.06, opacity_jitter=0.6, flow=0.7)
# textures: paint the material in your colour (its light and dark)
for _t in ("canvas", "fabric", "wood", "brick", "metal", "stone", "paper", "grunge", "noise", "clouds", "water", "tiles"):
    brush(_t + " texture fill", tip_round, hard=0.7, spacing=0.1, tex=_t, tex_mode="color", size_press=0.0)
# patterns: the motif in your colour, the rest left as it is
for _p in ("dots", "stripes", "checks", "plaid", "hearts", "stars", "flowers", "circles", "diamonds", "chevron", "waves"):
    brush(_p + " pattern", tip_round, hard=0.75, spacing=0.1, tex=_p, tex_mode="pattern", size_press=0.0)
# stamps: one per click, spaced out when you drag
for _s in ART.stamp_names():
    brush("stamp " + _s.lower(), tip_round, stamp=_s, spacing=1.15, size_press=0.0)

BLEND_MODES = ["normal", "multiply", "screen", "overlay", "soft light", "hard light", "darken", "lighten", "color dodge", "color burn",
               "add", "subtract", "difference"]
def blend_rgb(base, top, mode):
    """what `top` colour over `base` colour gives in a blend mode (both 0..255); the result is then mixed in by coverage"""
    if mode in ("normal", None): return np.broadcast_to(top, np.broadcast(base, top).shape)
    B, Tp = np.asarray(base, np.float32) / 255, np.asarray(top, np.float32) / 255
    if mode == "multiply": r = B * Tp
    elif mode == "screen": r = 1 - (1 - B) * (1 - Tp)
    elif mode == "overlay": r = np.where(B < 0.5, 2 * B * Tp, 1 - 2 * (1 - B) * (1 - Tp))
    elif mode == "hard light": r = np.where(Tp < 0.5, 2 * B * Tp, 1 - 2 * (1 - B) * (1 - Tp))
    elif mode == "soft light": r = np.where(Tp < 0.5, B - (1 - 2 * Tp) * B * (1 - B), B + (2 * Tp - 1) * (np.where(B < 0.25, ((16 * B - 12) * B + 4) * B, np.sqrt(B)) - B))
    elif mode == "darken": r = np.minimum(B, Tp)
    elif mode == "lighten": r = np.maximum(B, Tp)
    elif mode == "color dodge": r = np.where(B <= 0.001, 0.0, np.where(Tp >= 0.999, 1.0, np.minimum(1.0, B / np.maximum(1 - Tp, 1e-3))))   # (W3C: black stays black)
    elif mode == "color burn": r = np.where(B >= 0.999, 1.0, np.where(Tp <= 0.001, 0.0, 1 - np.minimum(1.0, (1 - B) / np.maximum(Tp, 1e-3))))   # (white stays white)
    elif mode == "add": r = np.minimum(1.0, B + Tp)
    elif mode == "subtract": r = np.maximum(0.0, B - Tp)
    elif mode == "difference": r = np.abs(B - Tp)
    else: r = np.broadcast_to(Tp, np.broadcast(B, Tp).shape)
    return r * 255

def add_sticker(file, name):
    """a sticker (a cut-out you saved) as a stamp: placed in its own colours, one per click, a row when you drag"""
    n = "sticker " + name.lower()
    if n not in B: brush(n, tip_round, stamp="sticker:" + file, spacing=1.15, size_press=0.0)
    return n

def _hsv_shift(col, dh):
    h, s, v = colorsys.rgb_to_hsv(*(np.asarray(col, np.float32) / 255)); r, g, b = colorsys.hsv_to_rgb((h + dh) % 1, s, v)
    return np.array([r, g, b], np.float32) * 255

class Canvas:
    stamp_own_colors = True                                              # stamps: their own colours, or tinted with yours (Adjustments)
    texture_own_colors = True                                            # textures (wood, brick...): their natural colours, or yours

    def __init__(self, w, h, paper=(245, 240, 230), seed=1, transparent=False):
        """transparent=True makes a see-through layer: colour in self.a plus coverage in self.alpha (0..1)"""
        self.w, self.h = w, h; self.a = np.zeros((h, w, 3), np.float32) + np.array(paper, np.float32)
        self.paper = np.array(paper, np.float32); self.grain = _grain(h, w, seed); self.rng = random.Random(seed)
        self.alpha = np.zeros((h, w), np.float32) if transparent else None
        self._wash = None; self._op = 1.0; self.touched = None             # touched: the box dabs changed since it was last cleared

    def image(self): return Image.fromarray(np.clip(np.nan_to_num(self.a), 0, 255).astype(np.uint8))

    # ---------------- one stroke: dabs gather in a stroke buffer, laid on the layer at the stroke's opacity
    def begin_stroke(self, base_a=None, base_alpha=None):
        """start a stroke painted in pieces. base_*: the layer as it was before the stroke (copies are made if not given)"""
        self._wash = dict(base_a=self.a.copy() if base_a is None else base_a,
                          base_al=(None if self.alpha is None else (self.alpha.copy() if base_alpha is None else base_alpha)),
                          S=np.zeros((self.h, self.w), np.float32), C=None, const=None, mode="normal")    # C: made only if the colour varies

    def end_stroke(self): self._wash = None

    def _dab(self, x, y, mask, color, alpha, mode, grain, tex=None, off=None):
        s0, s1 = mask.shape
        fl = math.floor                                                   # (floor, not round: Python rounds halves to even, which skipped pixels on thin lines)
        if off is None: x0, y0 = int(fl(x - s1 / 2 + 0.5)), int(fl(y - s0 / 2 + 0.5))
        else: x0, y0 = int(fl(x - off[2] / 2 + 0.5)) + off[0], int(fl(y - off[2] / 2 + 0.5)) + off[1]       # a cut-down tip: where its piece sits
        x1, y1 = x0 + s1, y0 + s0
        cx0, cy0, cx1, cy1 = max(0, x0), max(0, y0), min(self.w, x1), min(self.h, y1)
        if cx0 >= cx1 or cy0 >= cy1: return
        self._touch(cx0, cy0, cx1, cy1)
        m = mask[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0] * alpha
        if grain: m = m * np.clip((self.grain[cy0:cy1, cx0:cx1] - grain * 0.55) / (1 - grain * 0.55), 0, 1)
        col = color
        if isinstance(color, np.ndarray) and color.ndim == 3: col = color[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]   # a picture (stamp)
        if tex is not None:                                               # texture / pattern, in canvas space
            arr, how, k, tname = tex; th, tw = arr.shape; t = arr[np.arange(cy0, cy1)[:, None] % th, np.arange(cx0, cx1)[None, :] % tw]
            if how == "color":
                own = ART.TEX_COLORS.get(tname) if self.texture_own_colors else None
                c = np.asarray(own if own is not None else col, np.float32); tx = np.clip(c * (0.45 + 0.8 * t[..., None]) + 18 * (t[..., None] - 0.5), 0, 255)
                col = c + (tx - c) * k                                        # Texture (strength): 0 = plain colour, 100% = the full texture
            elif how == "pattern": m = m * (1 - k + k * t)                    # 0 = a plain stroke, 100% = only the motif
            else: m = m * (1 - k + k * t)
        if self._wash is not None and (mode in BLEND_MODES or mode == "erase"): self._wash_dab(cy0, cy1, cx0, cx1, m, col, mode)
        else: self._blend(cy0, cy1, cx0, cx1, m * self._op, col, mode)

    def _touch(self, x0, y0, x1, y1):
        t = self.touched; self.touched = (x0, y0, x1, y1) if t is None else (min(t[0], x0), min(t[1], y0), max(t[2], x1), max(t[3], y1))

    def _wash_dab(self, y0, y1, x0, x1, m, color, mode):
        """add a dab to the stroke buffer (never past full), then lay the buffer on the layer at the stroke's opacity"""
        W = self._wash; sl = (slice(y0, y1), slice(x0, x1)); S = W["S"][sl]; W["mode"] = mode
        S2 = S + m * (1 - S); W["S"][sl] = S2
        flat = not (isinstance(color, np.ndarray) and color.ndim == 3)
        if flat and W["C"] is None:                                       # one colour so far: no per-pixel colour needed (much faster)
            c3 = tuple(float(v) for v in np.asarray(color, np.float32).reshape(3))
            if W["const"] is None: W["const"] = c3
            if W["const"] == c3 or np.allclose(W["const"], c3, atol=0.5):
                self._blend(y0, y1, x0, x1, S2 * self._op, W["const"], mode, base=(W["base_a"][sl], None if W["base_al"] is None else W["base_al"][sl])); return
        if W["C"] is None:                                               # the colour starts varying: from now on, colour per pixel
            W["C"] = np.empty((self.h, self.w, 3), np.float32); W["C"][:] = np.asarray(W["const"] if W["const"] is not None else (0, 0, 0), np.float32)
        C = W["C"][sl]; c = np.broadcast_to(np.asarray(color, np.float32), C.shape); keep = (S * (1 - m))[..., None]
        W["C"][sl] = np.where(S2[..., None] > 1e-5, (C * keep + c * m[..., None]) / np.maximum(S2, 1e-5)[..., None], c)
        self._blend(y0, y1, x0, x1, S2 * self._op, W["C"][sl], mode, base=(W["base_a"][sl], None if W["base_al"] is None else W["base_al"][sl]))

    def _blend(self, y0, y1, x0, x1, m, color, mode, base=None):
        """lay colour through mask m onto the region (or onto base, the region as it was, when given); on a transparent layer,
        coverage builds up (or is erased)"""
        if base is None: reg = self.a[y0:y1, x0:x1]; ra = None if self.alpha is None else self.alpha[y0:y1, x0:x1][..., None]
        else: reg = base[0]; ra = None if base[1] is None else base[1][..., None]
        m3 = m[..., None]; c = np.asarray(color, np.float32)
        if ra is not None:
            if mode == "erase": self.alpha[y0:y1, x0:x1] = (ra * (1 - m3))[..., 0]; self.a[y0:y1, x0:x1] = reg; return
            if mode != "normal":                                              # the standard (W3C / Photoshop) way: the mode mixes with what's
                new = (1 - ra) * c + ra * blend_rgb(reg, c, mode)             # on the layer; where the layer is empty, the paint's own colour
            else: new = c
            keep = ra * (1 - m3); out_a = keep + m3
            self.a[y0:y1, x0:x1] = (reg * keep + new * m3) / np.maximum(out_a, 1e-4); self.alpha[y0:y1, x0:x1] = out_a[..., 0]; return
        if mode == "erase": new = np.broadcast_to(self.paper, reg.shape)
        else: new = blend_rgb(reg, c, mode)
        self.a[y0:y1, x0:x1] = reg * (1 - m3) + new * m3

    # ---------------- the stroke
    def _resample(self, pts, step, state):
        """dabs every `step` pixels along the path; with state, the spacing carries on from the last piece"""
        out = []; nxt = state.get("next", 0.0) if state is not None else 0.0; first = state is None or "next" not in state
        if len(pts) == 1 or all(abs(p[0] - pts[0][0]) + abs(p[1] - pts[0][1]) < 1e-6 for p in pts):
            if first: out.append((pts[0][0], pts[0][1], pts[0][2], state.get("ang", 0.0) if state else 0.0))
            if state is not None: state["next"] = step
            return out
        travelled = 0.0
        for (x0, y0, p0), (x1, y1, p1) in zip(pts, pts[1:]):
            d = math.hypot(x1 - x0, y1 - y0)
            if d < 1e-9: continue
            ang = math.atan2(y1 - y0, x1 - x0)
            while nxt <= travelled + d:
                t = (nxt - travelled) / d; out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, p0 + (p1 - p0) * t, ang)); nxt += step
            travelled += d
        if state is not None: state["next"] = nxt - travelled
        return out

    def stroke(self, pts, name, color=(30, 30, 30), size=24, opacity=1.0, state=None):
        """pts: list of (x, y) or (x, y, pressure). state: a dict kept for one stroke painted in pieces as the mouse moves (live
        painting): direction is smoothed across the pieces, spacing carries on, and a tapering brush only thins at the start"""
        b = B[name]; pts = [(p[0], p[1], p[2] if len(p) > 2 else 1.0) for p in pts]
        sp = b["special"]
        if sp in MOVING_ONLY:
            return getattr(self, "_" + sp)(pts, color, size, opacity)
        own = self._wash is None and sp not in ("smudge", "blur", "sharpen", "deform", "clone")
        if own: self.begin_stroke()
        self._op = opacity
        try: self._stroke(b, pts, color, size, opacity, state)
        finally:
            if own: self.end_stroke()
            self._op = 1.0

    def _stroke(self, b, pts, color, size, opacity, state):
        sp = b["special"]; step = max(1.0, size * b["size_scale"] * b["spacing"])
        out = self._resample(pts, step, state)
        if not out: return
        N = len(out); travel = None
        if state is not None:                                                # turn smoothly: each dab leans only part way to the new direction
            vx, vy = state.get("dir", (None, None)); dist = state.get("dist", 0.0); sm = []; lx, ly = state.get("last", (out[0][0], out[0][1]))
            for (x, y, p, ang) in out:
                cx, cy = math.cos(ang), math.sin(ang); dist += math.hypot(x - lx, y - ly); lx, ly = x, y
                if dist < size * 0.5: vx, vy = 1.0, 0.0                          # a click or the first bit of a stroke: always the same way round
                elif vx is None: vx, vy = cx, cy
                else:
                    if cx * vx + cy * vy < 0 and b["tip"] in (tip_rect, tip_ellipse, tip_fan, tip_bristles): cx, cy = -cx, -cy   # a flat tip looks the same turned half way round
                    k = min(1.0, step / max(size * 1.2, 1.0)); vx, vy = vx + (cx - vx) * k, vy + (cy - vy) * k
                    n_ = math.hypot(vx, vy) or 1.0; vx, vy = vx / n_, vy / n_
                sm.append((x, y, p, math.atan2(vy, vx), dist))
            state["dir"] = (vx, vy); state["dist"] = dist; state["last"] = (lx, ly); state["ang"] = sm[-1][3]
            out = [q[:4] for q in sm]; travel = [q[4] for q in sm]
        src = None
        if sp == "clone":                                                    # copy from the layer as it was when the stroke began
            src = (self._wash["base_a"], self._wash["base_al"]) if self._wash is not None else (self.a.copy(), None if self.alpha is None else self.alpha.copy())
        prev = state.get("prev") if state is not None else None             # the last dab (smudge drags from there), across pieces
        tex = None
        if b["tex"]: tex = ((ART.pattern(b["tex"]) if b["tex_mode"] == "pattern" else ART.texture(b["tex"])), b["tex_mode"], b["tex_strength"], b["tex"])
        base_col = np.asarray(color, np.float32)
        for i, (x, y, p, ang) in enumerate(out):
            if b["taper"]:
                if travel is not None: tp = min(1.0, 0.25 + 0.75 * travel[i] / max(size * 1.5, 1.0))       # thin only as it starts
                else: t = i / max(1, N - 1); tp = math.sin(math.pi * t) ** 0.6
            else: tp = 1.0
            szf = (1 - b["size_press"] * (1 - p)) * tp; opf = 1 - b["opac_press"] * (1 - p)
            if b["opacity_jitter"]: opf *= 1 - self.rng.uniform(0, b["opacity_jitter"])
            s = max(1, int(round(size * b["size_scale"] * szf * ((1 - 0.95 * self.rng.uniform(0, min(1.0, b["jitter_size"]))) if b["jitter_size"] else 1))))   # Size Jitter: down to 5% at 100%, never bigger
            ta = dict(b["tipargs"])
            if b["angle_follow"]: ta["angle"] = ang + math.pi / 2 + ta.get("angle", 0)
            if b["jitter_angle"]: ta["angle"] = ta.get("angle", 0) + self.rng.uniform(-b["jitter_angle"], b["jitter_angle"])
            if "angle" in ta: ta["angle"] = round(ta["angle"] / 0.03) * 0.03          # (so tips can be reused)
            if b["tip"] in (tip_bristles, tip_sponge): ta["seed"] = 7
            dx = dy = 0
            if b["scatter"]: dx, dy = self.rng.gauss(0, b["scatter"] * size * 0.4), self.rng.gauss(0, b["scatter"] * size * 0.4)
            col = base_col
            if b["color_jitter"]: col = np.clip(col * (1 + self.rng.uniform(-b["color_jitter"], b["color_jitter"])), 0, 255)
            if b["hue_jitter"]: col = _hsv_shift(col if b["hue_jitter"] < 0.99 else np.array([235, 70, 90], np.float32), self.rng.uniform(-b["hue_jitter"], b["hue_jitter"]) if b["hue_jitter"] < 0.99 else self.rng.random())
            if b["stamp"]:                                                # a stamp picture: its own colours, or yours with its shading
                st = ART.stamp(b["stamp"], max(2, s), ta.get("angle", 0.0))
                if st is None: continue
                mask, rgb = st
                if not self.stamp_own_colors and not b["stamp"].startswith("sticker:"):     # (stickers keep their colours)
                    lum = rgb.mean(-1); ref = float(np.percentile(lum[mask > 0.5], 60)) if (mask > 0.5).any() else 128.0
                    rgb = np.clip(col[None, None, :] * np.clip(lum / max(ref, 1), 0.6, 1.25)[..., None], 0, 255)
                self._dab(x + dx, y + dy, mask, rgb, b["flow"] * opf, b["mode"], 0); continue
            mask = _tip(b["tip"], s, ta)
            if sp == "smudge":                                           # drag the paint under the brush along (like a finger through wet paint)
                if prev is not None: self._smear(x, y, prev[0], prev[1], mask, min(1.0, 0.9 * opacity * opf))   # Opacity is the strength
                prev = (x, y); continue
            if sp in ("blur", "sharpen"): self._filter_dab(x, y, s, opacity * opf, sp); continue
            if sp == "deform":                                           # push paint in the stroke direction
                if i:
                    px, py = out[i - 1][0], out[i - 1][1]; x0, y0 = int(px - s / 2), int(py - s / 2)
                    if 0 <= x0 and 0 <= y0 and x0 + s < self.w and y0 + s < self.h:
                        reg = self.a[y0:y0 + s, x0:x0 + s].copy(); tx, ty = int(x - s / 2), int(y - s / 2)
                        if 0 <= tx and 0 <= ty and tx + s < self.w and ty + s < self.h:
                            mm = mask[..., None] * 0.5 * opacity; self.a[ty:ty + s, tx:tx + s] = self.a[ty:ty + s, tx:tx + s] * (1 - mm) + reg * mm
                continue
            if sp == "clone":                                            # paint with a copy of another part of the layer (Alt-click picks it)
                off = b.get("clone_off")
                if off is None: continue
                P = self._patch(src[0], x + off[0], y + off[1], s, 0.0); PA = self._patch(src[1], x + off[0], y + off[1], s, 0.0) if src[1] is not None else 1.0
                self._dab(x, y, mask * PA, P, b["flow"] * opf, "normal", 0); continue
            if sp == "spray":
                for _ in range(10):
                    rr = s * 0.7; ox, oy = self.rng.gauss(0, rr * 0.5), self.rng.gauss(0, rr * 0.5); ds = max(2, int(self.rng.uniform(1, 4)))   # (s: pressure / jitter change the spray's spread)
                    self._dab(x + dx + ox, y + dy + oy, _tip(tip_round, ds, {"hard": 1}), col, b["flow"] * opf, "normal", 0)
                continue
            if sp == "neon":                                             # a wide soft glow, then a bright core
                g = _tip(tip_soft, max(3, int(s * 2.4)), {}); self._blend_direct(x + dx, y + dy, g, col, 0.06 * opacity * b["flow"])
                core = _tip(tip_round, max(2, int(s * 0.38)), {"hard": 0.7}); self._dab(x + dx, y + dy, core, np.clip(col * 0.35 + 255 * 0.65, 0, 255), opf * b["flow"], "normal", 0)
                continue
            pc = _tipc(b["tip"], s, ta); self._dab(x + dx, y + dy, pc[0], col, b["flow"] * opf, b["mode"], b["grain"], tex, off=pc[1:])
            if sp == "knife":                                            # palette knife: hard edge streaked with the paint beneath
                self._dab(x + dx + 2, y + dy + 2, mask * 0.4, np.clip(col * 1.25, 0, 255), 0.5, "normal", 0.5)
            if sp == "ribbon":                                           # a shine along the middle of the ribbon
                hi = _tip(tip_rect, s, dict(ta, aspect=0.05)); self._dab(x + dx - math.sin(ang) * s * 0.03, y + dy + math.cos(ang) * s * 0.03, hi, np.clip(col * 0.4 + 255 * 0.6, 0, 255), 0.55, "normal", 0)
            if sp == "drip" and self.rng.random() < min(0.35, 2.2 * step / max(size, 1)):   # now and then a run of paint drips down
                self._drip(x, y, s, col, opacity)
        if state is not None: state["prev"] = prev
        if sp == "wet_edge": self._edge_darken(out, size, color, opacity)             # watercolour pools darker at the stroke edge
        if sp == "impasto":                                              # thick paint catches light on one side
            for (x, y, p, ang) in out[::3]:
                self._dab(x - size * 0.12, y - size * 0.12, _tip(tip_ellipse, max(3, int(size * 0.5)), dict(aspect=0.2, angle=round((ang + math.pi / 2) / 0.03) * 0.03)), (255, 250, 240), 0.18, "normal", 0.3)

    def _patch(self, arr, cx, cy, s, fill):
        """the s x s piece of arr centred at (cx, cy), placed the way a dab is (fill where it runs off the picture)"""
        x0, y0 = int(math.floor(cx - s / 2 + 0.5)), int(math.floor(cy - s / 2 + 0.5)); h, w = arr.shape[:2]
        out = np.full((s, s) + arr.shape[2:], fill, np.float32); a0, b0, a1, b1 = max(0, x0), max(0, y0), min(w, x0 + s), min(h, y0 + s)
        if a0 < a1 and b0 < b1: out[b0 - y0:b1 - y0, a0 - x0:a1 - x0] = arr[b0:b1, a0:a1]
        return out

    def _smear(self, x, y, px, py, mask, k):
        """smudge: the paint at the last dab (px, py) is pushed to (x, y), see-through areas too (paint is dragged into them
        and they're dragged into paint). k: the strength"""
        s = mask.shape[0]; x0, y0 = int(math.floor(x - s / 2 + 0.5)), int(math.floor(y - s / 2 + 0.5))
        a0, b0, a1, b1 = max(0, x0), max(0, y0), min(self.w, x0 + s), min(self.h, y0 + s)
        if a0 >= a1 or b0 >= b1: return
        self._touch(a0, b0, a1, b1); sl = (slice(b0, b1), slice(a0, a1)); ms = (slice(b0 - y0, b1 - y0), slice(a0 - x0, a1 - x0))
        P = self._patch(self.a, px, py, s, 255.0)[ms]; m = (mask[ms] * k)[..., None]
        if self.alpha is None: self.a[sl] = self.a[sl] * (1 - m) + P * m; return
        PA = self._patch(self.alpha, px, py, s, 0.0)[ms][..., None]; TA = self.alpha[sl][..., None]
        na = TA * (1 - m) + PA * m                                         # mixed as premultiplied colour, so see-through moves too
        self.a[sl] = np.where(na > 1e-4, (self.a[sl] * TA * (1 - m) + P * PA * m) / np.maximum(na, 1e-4), self.a[sl]); self.alpha[sl] = na[..., 0]

    def _blend_direct(self, x, y, mask, color, alpha, mode="normal"):
        """a dab straight onto the layer, outside the stroke buffer (smudge, clone, glows)"""
        w = self._wash; self._wash = None; op = self._op; self._op = 1.0
        try: self._dab(x, y, mask, color, alpha, mode, 0)
        finally: self._wash = w; self._op = op

    def _filter_dab(self, x, y, s, amount, how):
        """blur or sharpen what's under a soft round brush"""
        from scipy.ndimage import uniform_filter
        r = max(2, s // 2); x0, y0, x1, y1 = max(0, int(x - r)), max(0, int(y - r)), min(self.w, int(x + r)), min(self.h, int(y + r))
        if x1 <= x0 + 2 or y1 <= y0 + 2: return
        self._touch(x0, y0, x1, y1)
        reg = self.a[y0:y1, x0:x1]; k = max(3, int(s / 10) | 1); bl = np.stack([uniform_filter(reg[..., c], k) for c in range(3)], -1)
        yy, xx = np.mgrid[y0:y1, x0:x1]; mm = np.clip(1 - np.hypot(xx - x, yy - y) / r, 0, 1)[..., None] ** 1.5 * amount
        new = bl if how == "blur" else np.clip(reg + (reg - bl) * 1.6, 0, 255)
        self.a[y0:y1, x0:x1] = reg * (1 - mm) + new * mm

    def _drip(self, x, y, s, col, opacity):
        L = s * self.rng.uniform(1.0, 4.0); w0 = max(2, int(s * self.rng.uniform(0.18, 0.32))); yy = y
        while yy < y + L:
            f = 1 - (yy - y) / L; ww = max(2, int(w0 * (0.55 + 0.45 * f))); self._dab(x, yy, _tip(tip_round, ww, {"hard": 0.9}), col, 1.0, "normal", 0); yy += max(1, ww * 0.3)
        self._dab(x, y + L, _tip(tip_round, max(3, int(w0 * 1.3)), {"hard": 0.9}), col, 1.0, "normal", 0)    # the drop at the end

    def _edge_darken(self, out, size, color, opacity):
        from scipy.ndimage import gaussian_filter, binary_erosion
        xs = [q[0] for q in out]; ys = [q[1] for q in out]; m = int(size) + 12
        X0, Y0, X1, Y1 = max(0, int(min(xs)) - m), max(0, int(min(ys)) - m), min(self.w, int(max(xs)) + m), min(self.h, int(max(ys)) + m)
        if X1 <= X0 or Y1 <= Y0: return
        self._touch(X0, Y0, X1, Y1)
        fp = np.zeros((Y1 - Y0, X1 - X0), np.float32)                     # only around the stroke, not the whole picture
        for x, y, p, ang in out:
            r = size * 0.45; x0, x1 = int(max(X0, x - r)), int(min(X1, x + r)); y0, y1 = int(max(Y0, y - r)), int(min(Y1, y + r))
            if x1 > x0 and y1 > y0:
                yy, xx = np.mgrid[y0:y1, x0:x1]; fp[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0] = np.maximum(fp[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0], ((xx - x) ** 2 + (yy - y) ** 2 <= r * r))
        edge = np.clip(gaussian_filter(fp, 3) - gaussian_filter(binary_erosion(fp > 0.5, iterations=5).astype(np.float32), 3), 0, 1) * 0.2 * opacity
        reg = self.a[Y0:Y1, X0:X1]; self.a[Y0:Y1, X0:X1] = reg * (1 - edge[..., None]) + reg * (np.asarray(color, np.float32) / 255) * edge[..., None]

    # ---------------- whole-stroke brushes (drawn from the finished path)
    def _particle(self, pts, color, size, opacity):
        for x, y, p in pts[::2]:
            for k in range(6):
                a = self.rng.uniform(0, 2 * math.pi); vx, vy = math.cos(a) * 2, math.sin(a) * 2; px, py = x, y
                for t in range(int(size * 0.45)):
                    vx += self.rng.gauss(0, 0.4); vy += self.rng.gauss(0, 0.4); px += vx; py += vy
                    self._dab(px, py, _tip(tip_round, 2, {"hard": 1}), color, 0.5 * opacity, "normal", 0)

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
        m = np.asarray(layer, np.float32) / 255 * opacity; self._blend(0, self.h, 0, self.w, m, color, "normal"); self._touch(0, 0, self.w, self.h)

    def _grass(self, pts, color, size, opacity):
        for x, y, p in pts[::2]:
            for k in range(5):
                ang = self.rng.gauss(0, 0.3); L = size * self.rng.uniform(0.6, 1.4); prev = (x, y); w0 = max(1, size * 0.08)
                for t in np.linspace(0.1, 1, 8):
                    px, py = x + math.sin(ang + 0.4 * t * t) * L * t, y - math.cos(ang) * L * t
                    self._line(prev[0], prev[1], px, py, np.clip(np.asarray(color) * self.rng.uniform(0.75, 1.25), 0, 255), opacity, max(1, int(w0 * (1 - t) + 1))); prev = (px, py)

    def _along(self, pts, step):
        """points every `step` pixels along the path, with the direction there"""
        out = []; nxt = 0.0; tr = 0.0
        for (x0, y0, _), (x1, y1, _) in zip(pts, pts[1:]):
            d = math.hypot(x1 - x0, y1 - y0)
            if d < 1e-9: continue
            while nxt <= tr + d: t = (nxt - tr) / d; out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, math.atan2(y1 - y0, x1 - x0))); nxt += step
            tr += d
        return out or [(pts[0][0], pts[0][1], 0.0)]

    def _swirl(self, pts, color, size, opacity):
        """little spirals along the stroke, turning alternate ways"""
        w = max(1, int(size * 0.08))
        for i, (x, y, a) in enumerate(self._along(pts, max(6, size * 1.4))):
            sgn = 1 if i % 2 == 0 else -1; prev = None; R = size * 0.55
            for t in np.linspace(0, 1, 40):
                r = R * t; th = a + sgn * t * 3.2 * math.pi; q = (x + math.cos(th) * r, y + math.sin(th) * r)
                if prev: self._line(prev[0], prev[1], q[0], q[1], color, opacity, w)
                prev = q

    def _flourish(self, pts, color, size, opacity):
        """a calligraphic line that loops as it goes, thick on the down-strokes"""
        path = self._along(pts, 2.0); R = size * 0.45; prev = None
        for i, (x, y, a) in enumerate(path):
            th = i * 2.0 / max(R, 1) * 1.3; nx, ny = -math.sin(a), math.cos(a)
            q = (x + math.cos(a) * math.sin(th) * R * 0.9 + nx * math.cos(th) * R, y + math.sin(a) * math.sin(th) * R * 0.9 + ny * math.cos(th) * R)
            w = max(1, int(size * (0.05 + 0.09 * abs(math.sin(th)))))
            if prev: self._line(prev[0], prev[1], q[0], q[1], color, opacity, w)
            prev = q

    def _vine(self, pts, color, size, opacity):
        """a curling stem with leaves on alternate sides"""
        col = np.asarray(color, np.float32); stem = np.clip(col * 0.7, 0, 255); path = self._along(pts, 2.0); prev = None
        for i, (x, y, a) in enumerate(path):
            off = math.sin(i * 2.0 / max(size, 1) * 2.2) * size * 0.15; q = (x - math.sin(a) * off, y + math.cos(a) * off)
            if prev: self._line(prev[0], prev[1], q[0], q[1], stem, opacity, max(1, int(size * 0.07)))
            prev = q
        for i, (x, y, a) in enumerate(self._along(pts, max(6, size * 0.75))):
            sgn = 1 if i % 2 == 0 else -1; la = a + sgn * 0.9; s = max(4, int(size * self.rng.uniform(0.45, 0.65)))
            cx, cy = x + math.cos(la) * s * 0.45, y + math.sin(la) * s * 0.45
            leaf = np.clip(col * self.rng.uniform(0.85, 1.15), 0, 255)
            self._dab(cx, cy, ART.shape_mask("leaf", s, la), leaf, opacity, "normal", 0)

    def _line(self, x0, y0, x1, y1, color, alpha, width):
        d = math.hypot(x1 - x0, y1 - y0); n = max(1, int(d / max(1, width * 0.35))); m = _tip(tip_round, max(2, width + 1), {"hard": 1})
        for i in range(n + 1):
            t = i / n; self._dab(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, m, color, alpha, "normal", 0)

def sampler(path, cols=4):
    """one swatch per brush: a wavy test stroke with the brush's name"""
    from PIL import ImageDraw, ImageFont
    names = list(B); rows = (len(names) + cols - 1) // cols; cw, ch = 420, 150
    cv = Canvas(cols * cw, rows * ch, paper=(244, 238, 226))
    for i, n in enumerate(names):                                        # a dark band behind half of each cell for blend modes / smudge / glow
        cx, cy = (i % cols) * cw, (i // cols) * ch
        cv.a[cy + 40:cy + 140, cx + 210:cx + 410] = np.array([70, 90, 140], np.float32)
        pts = [(cx + 30 + t * 360, cy + 90 + math.sin(t * 6.3) * 28, 0.4 + 0.6 * math.sin(math.pi * t)) for t in np.linspace(0, 1, 40)]
        col = (196, 92, 44) if n not in ("glow (dodge)",) else (255, 210, 120)
        cv.stroke(pts, n, color=col, size=34 if n not in ("ink pen", "pencil", "script", "liner (rigger)") else 14, opacity=1.0)
    img = cv.image(); d = ImageDraw.Draw(img)
    try: f = ImageFont.truetype(__import__("paths").font("EBGaramond-SemiBold.ttf"), 24)
    except Exception: f = ImageFont.load_default()
    for i, n in enumerate(names): d.text(((i % cols) * cw + 12, (i // cols) * ch + 6), n, font=f, fill=(40, 30, 30))
    img.save(path); return len(names)

if __name__ == "__main__":
    import sys; print(sampler(sys.argv[1] if len(sys.argv) > 1 else "brush_sampler.png"), "brushes")
