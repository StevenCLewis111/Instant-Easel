"""
brush_catalog.py: every brush, pen and drawing tool in Instant Easel Pro's Draw studio, grouped the way the Brushes, Pens & Tools guide shows.

Each tool lists the names it may have in the brush engine (brushes.B). When the engine has one of them, the tile shows a live stroke
from the real brush and works; when it doesn't yet, the tile shows a drawn preview of what it will do and is marked SOON.
Brushes the engine has that this list doesn't mention are shown in a last "More brushes" section, so nothing goes missing.

    import brush_catalog as BC
    for title, layout, items in BC.sections(brushes.B): ...     # layout "tiles" or "icons"; item["engine"] is None while it's planned
    BC.preview(item)  -> 96 x 30 PIL picture for a planned tool       BC.icon(name, 28) -> stamp picture
"""
import math, re
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

PAPER = (244, 238, 226); TW, TH = 96, 30                       # tile size (pixels)

def _b(name, *engines, look=None, **kw):
    """one tool: its display name, the engine names it may have, and how its preview is drawn until it exists"""
    return dict(name=name, engines=list(engines) or [name], look=look or {}, kind=kw.get("kind", "brush"), tool=kw.get("tool"))

SECTIONS = [
    ("Brushes", "tiles", [
        _b("Round", "round", "round brush", look=dict(color=(30, 45, 110), width=7)),
        _b("Flat", "flat", "flat brush", look=dict(color=(15, 20, 40), width=10, cap="square", tex="bristle")),
        _b("Square", "square", "bright", "square brush", look=dict(color=(15, 15, 20), width=9, cap="square")),
        _b("Filbert", "filbert", "filbert brush", look=dict(color=(20, 30, 60), width=10, tex="bristle", taper=True)),
        _b("Fan", "fan", "fan brush", look=dict(color=(40, 50, 80), width=10, tex="fan")),
        _b("Angular", "angular", "angle", "angled brush", look=dict(color=(25, 30, 50), width=9, tex="nib")),
        _b("Bristle", "bristle", "bristle brush", look=dict(color=(60, 55, 60), width=10, tex="bristle")),
        _b("Airbrush", "airbrush", "air brush", look=dict(color=(25, 35, 70), width=9, soft=6)),
        _b("Dry Media", "dry media", "dry brush", look=dict(color=(40, 40, 50), width=9, tex="speckle")),
        _b("Wet Media", "wet media", "gouache", "acrylic", look=dict(color=(25, 40, 90), width=9, soft=1.5, tex="wet")),
        _b("Watercolor", "watercolor", "watercolour", "wash", look=dict(color=(30, 140, 230), width=9, soft=1.5, alpha=0.75, tex="wet")),
        _b("Oil Paint", "oil paint", "oil", "oil brush", look=dict(color=(240, 60, 20), width=9, tex="bristle", grad=(255, 170, 30))),
        _b("Ink", "ink", "sumi", look=dict(color=(5, 5, 8), width=8)),
        _b("Ink Brush", "ink brush", "dagger", "brush pen", look=dict(color=(20, 120, 170), width=8, taper=True)),
        _b("Marker", "marker", "felt marker", look=dict(color=(25, 50, 190), width=7, cap="square", alpha=0.9)),
        _b("Charcoal", "charcoal", look=dict(color=(20, 20, 20), width=8, tex="speckle")),
        _b("Pastel", "pastel", "pastel / chalk", "chalk", look=dict(color=(110, 50, 170), width=8, tex="grain")),
        _b("Crayon", "crayon", "wax crayon", look=dict(color=(30, 190, 220), width=8, tex="grain")),
        _b("Pencil", "pencil", "graphite", look=dict(color=(70, 70, 75), width=2)),
        _b("Spray", "spray", "spray paint", "spray can", look=dict(color=(20, 20, 20), width=10, tex="dots")),
    ]),
    ("Pens", "tiles", [
        _b("Pen", "pen", "ink pen", "ballpoint", look=dict(color=(15, 15, 20), width=1.6)),
        _b("Calligraphy", "calligraphy", "calligraphy pen", look=dict(color=(15, 15, 20), width=3, tex="nib")),
        _b("G Pen", "g pen", "script", "comic pen", look=dict(color=(15, 15, 20), width=2.4, taper=True)),
        _b("Fountain Pen", "fountain pen", "fountain", look=dict(color=(15, 15, 30), width=2.2, taper=True)),
        _b("Technical Pen", "technical pen", "tech pen", "ink pen", look=dict(color=(15, 15, 20), width=1.4)),
        _b("Fineliner", "fineliner", "liner (rigger)", "fine liner", look=dict(color=(15, 15, 20), width=1.1)),
    ]),
    ("Special Brushes", "tiles", [
        _b("Splatter", "splatter", "splat", look=dict(scatter="splat", color=(30, 70, 200))),
        _b("Drip", "drip", "drips", look=dict(fx="drip")),
        _b("Leaf", "leaf", "foliage", "leaves", look=dict(scatter="leaf", color=(90, 190, 60))),
        _b("Stipple", "stipple", "dotting", look=dict(color=(30, 30, 40), width=10, tex="dots")),
        _b("Pattern Brush", "pattern brush", "pattern", look=dict(scatter="star", color=(20, 20, 30), even=True)),
    ]),
    ("Blending", "tiles", [
        _b("Smudge", "smudge", "smudge / blender", "finger", kind="tool", look=dict(color=(40, 55, 100), width=8, soft=1.5, tex="smear")),
        _b("Soften", "soften", "soft blend", kind="tool", look=dict(color=(40, 55, 100), width=7, soft=7, alpha=0.7)),
        _b("Mix", "mix", "deform (push)", "mixer", kind="tool", look=dict(color=(40, 55, 100), width=6, soft=2, tex="swirl")),
    ]),
    ("Blurring", "tiles", [
        _b("Blur", "blur", "blur (filter)", kind="tool", look=dict(fx="dots", radius=2.5)),
        _b("Gaussian Blur", "gaussian blur", "gaussian", kind="tool", look=dict(fx="dots", radius=4)),
        _b("Motion Blur", "motion blur", "motion", kind="tool", look=dict(fx="motion")),
        _b("Radial Blur", "radial blur", "spin blur", kind="tool", look=dict(fx="radial")),
        _b("Zoom Blur", "zoom blur", kind="tool", look=dict(fx="zoom")),
    ]),
    ("Sharpen", "tiles", [
        _b("Sharpen", "sharpen", kind="tool", look=dict(color=(25, 35, 70), width=8, tex="crisp")),
        _b("Unsharp Mask", "unsharp mask", "unsharp", kind="tool", look=dict(color=(225, 150, 140), width=6, tex="outline")),
        _b("High Pass", "high pass", "highpass", kind="tool", look=dict(color=(60, 60, 70), width=5, tex="outline")),
        _b("Edge Enhance", "edge enhance", "edges", kind="tool", look=dict(color=(20, 20, 25), width=6, tex="outline")),
        _b("Detail", "detail", kind="tool", look=dict(color=(30, 30, 40), width=4, taper=True)),
    ]),
    ("Special Effects", "tiles", [
        _b("Dodge", "dodge", "glow (dodge)", "lighten", kind="tool", look=dict(fx="dodge")),
        _b("Burn", "burn", "glaze", "darken", kind="tool", look=dict(fx="burn")),
        _b("Saturation", "saturation", "saturate", kind="tool", look=dict(fx="rainbow")),
        _b("Hue Shift", "hue shift", "hue", kind="tool", look=dict(fx="hue")),
        _b("Noise", "noise", kind="tool", look=dict(fx="noise")),
    ]),
    ("Effect Brushes", "tiles", [
        _b("Neon", "neon", "neon brush", look=dict(fx="neon", color=(255, 40, 200))),
        _b("Outline", "outline", "outline brush", look=dict(fx="ring", color=(235, 240, 255))),
        _b("Shadow", "shadow", "drop shadow", look=dict(fx="shadow")),
        _b("Inner Shadow", "inner shadow", look=dict(fx="inner")),
        _b("Outer Glow", "outer glow", look=dict(fx="neon", color=(170, 90, 255))),
        _b("Inner Glow", "inner glow", look=dict(fx="inner", glow=True)),
        _b("Emboss", "emboss", kind="tool", look=dict(fx="emboss")),
        _b("Solarize", "solarize", kind="tool", look=dict(fx="solarize")),
        _b("Posterize", "posterize", kind="tool", look=dict(fx="posterize")),
        _b("Pixelate", "pixelate", "grid", "pixel", kind="tool", look=dict(fx="pixelate")),
        _b("Halftone", "halftone", kind="tool", look=dict(fx="halftone")),
        _b("RGB Split", "rgb split", "channel split", kind="tool", look=dict(fx="rgbsplit")),
        _b("Chromatic", "chromatic", "chromatic aberration", kind="tool", look=dict(fx="chromatic")),
    ]),
    ("Decorative Brushes", "tiles", [
        _b("Stars", "stars", "star trail", look=dict(scatter="star", color=(250, 200, 30), even=True)),
        _b("Sparkles", "sparkles", look=dict(scatter="sparkle", color=(255, 120, 200))),
        _b("Hearts", "hearts", look=dict(scatter="heart", color=(240, 50, 120), even=True)),
        _b("Confetti", "confetti", look=dict(scatter="confetti")),
        _b("Petals", "petals", look=dict(scatter="petal", color=(250, 140, 190))),
        _b("Snowflakes", "snowflakes", "snow", look=dict(scatter="snow", color=(200, 225, 255), dark=True)),
        _b("Bubbles", "bubbles", look=dict(scatter="bubble", color=(70, 170, 240), even=True)),
        _b("Ribbons", "ribbons", "ribbon", look=dict(color=(220, 60, 200), width=6, tex="ribbon")),
        _b("Swirls", "swirls", "swirl", look=dict(fx="swirls")),
        _b("Flourish", "flourish", look=dict(fx="flourish")),
        _b("Vines", "vines", "vine", look=dict(scatter="leaf", color=(70, 170, 60), stem=True)),
        _b("Dots", "dots brush", look=dict(scatter="dot", color=(250, 210, 40), even=True)),
    ]),
    ("Texture Brushes", "tiles", [_b(n, n.lower(), n.lower() + " brush", look=dict(fx="texture", tex=t)) for n, t in (
        ("Grain", "grain"), ("Noise Texture", "noise"), ("Sand", "sand"), ("Spray Texture", "spraytex"), ("Fabric Texture", "fabric"),
        ("Paper Texture", "paper"), ("Grunge Texture", "grunge"), ("Concrete", "concrete"), ("Rust", "rust"), ("Mosaic", "mosaic"),
        ("Crackle", "crackle"), ("Bokeh", "bokeh"))]),
    ("Textures", "tiles", [_b(n, n.lower() + " texture", n.lower() + " fill", kind="fill", look=dict(fx="texture", tex=n.lower())) for n in (
        "Canvas", "Fabric", "Wood", "Brick", "Metal", "Stone", "Paper", "Grunge", "Noise", "Clouds", "Water", "Tiles")]),
    ("Patterns", "tiles", [_b(n, n.lower() + " pattern", kind="fill", look=dict(fx="pattern", pat=n.lower())) for n in (
        "Dots", "Stripes", "Checks", "Plaid", "Hearts", "Stars", "Flowers", "Circles", "Diamonds", "Chevron", "Waves")]),
    ("Stamps & Icons", "icons", [_b(n, "stamp " + n.lower(), kind="stamp") for n in (
        "Star", "Gold Star", "Heart", "Blue Heart", "Check", "Cross", "Plus", "Minus", "Warning", "Info",
        "Gear", "House", "Folder", "Document", "Trash", "Palette", "Eyedropper", "Magnifier", "Hand", "Pointer",
        "Pencil", "Yellow Pencil", "Eraser", "Paint Bucket", "Text")]),
    ("Paint Tools", "tiles", [
        _b("Gradient", "tool:gradient", kind="tool", look=dict(fx="rainbow")),
        _b("Gradient Fill", "tool:gradient fill", kind="tool", look=dict(fx="gradfill")),
        _b("Pattern Fill", "tool:pattern fill", kind="tool", look=dict(fx="pattern", pat="checks", col=(150, 80, 40))),
        _b("Color Fill", "tool:color fill", kind="tool", tool="fill", look=dict(fx="blocks")),
        _b("Magic Wand", "tool:magic wand", kind="tool", look=dict(fx="icon", icon="Magic Wand")),
        _b("Eyedropper", "tool:eyedropper", kind="tool", tool="pick", look=dict(fx="icon", icon="Eyedropper")),
        _b("Crop", "tool:crop", kind="tool", look=dict(fx="icon", icon="Crop")),
        _b("Move", "tool:move", kind="tool", look=dict(fx="icon", icon="Move")),
        _b("Rotate", "tool:rotate", kind="tool", look=dict(fx="icon", icon="Rotate")),
        _b("Flip", "tool:flip", kind="tool", look=dict(fx="icon", icon="Flip")),
    ]),
    ("Misc Tools", "tiles", [
        _b("Ruler", "tool:ruler", kind="tool", look=dict(fx="shape", shape="ruler")),
        _b("Ellipse", "tool:ellipse", kind="tool", tool="oval", look=dict(fx="shape", shape="ellipse")),
        _b("Rectangle", "tool:rectangle", kind="tool", tool="rect", look=dict(fx="shape", shape="rect")),
        _b("Polygon", "tool:polygon", kind="tool", look=dict(fx="shape", shape="polygon")),
        _b("Line", "tool:line", kind="tool", tool="line", look=dict(fx="shape", shape="line")),
        _b("Curve", "tool:curve", kind="tool", look=dict(fx="shape", shape="curve")),
        _b("Freehand", "tool:freehand", kind="tool", tool="brush", look=dict(fx="shape", shape="freehand")),
        _b("Polyline", "tool:polyline", kind="tool", look=dict(fx="shape", shape="polyline")),
        _b("Text", "tool:text", kind="tool", tool="text", look=dict(fx="shape", shape="text")),
        _b("Erase", "tool:erase", kind="tool", tool="eraser", look=dict(fx="icon", icon="Eraser")),
        _b("Dither", "tool:dither", kind="tool", look=dict(fx="dither")),
    ]),
]

def _key(s): return re.sub(r"[^a-z0-9]", "", str(s).lower())

def sections(engine_names):
    """the catalog matched to the brush engine: each item gets item["engine"] (its real name in the engine, or None while planned).
    Engine brushes the catalog doesn't mention come last, under "More brushes"."""
    names = list(engine_names); by_key = {_key(n): n for n in names}; used = set(); out = []
    for title, layout, items in SECTIONS:
        sec = []
        for it in items:
            it = dict(it); it["engine"] = None
            for e in it["engines"]:
                n = by_key.get(_key(e))
                if n is not None and (n not in used or it["kind"] != "brush"): it["engine"] = n; used.add(n); break
            if it["engine"] is None and it.get("tool"): it["studio_tool"] = it["tool"]          # already a Draw tool (fill, pick, line...)
            sec.append(it)
        out.append((title, layout, sec))
    extra = [dict(name=n[:1].upper() + n[1:], engines=[n], engine=n, look={}, kind="brush", tool=None) for n in names if n not in used and _key(n) != "eraser"]
    if extra: out.append(("More brushes", "tiles", extra))
    return out

# ---------------------------------------------------------------- previews for tools that aren't built yet
S = 4                                                                                     # drawn 4x bigger, then shrunk: smooth edges

def _path(n=48, amp=6.0):
    return [((8 + 80 * t) * S, (15 + amp * math.sin(t * 2 * math.pi * 0.9 + 0.4)) * S) for t in np.linspace(0, 1, n)]

def _stroke_mask(width, cap="round", taper=False, path=None):
    m = Image.new("L", (TW * S, TH * S), 0); d = ImageDraw.Draw(m); pts = path or _path()
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        t = i / (len(pts) - 1); w = width * S * ((0.25 + 0.75 * math.sin(math.pi * t)) if taper else 1)
        d.line([a, b], fill=255, width=max(1, int(w)))
        if cap == "round": r = w / 2; d.ellipse([b[0] - r, b[1] - r, b[0] + r, b[1] + r], fill=255)
    if cap == "round": r = width * S / 2 * (0.25 if taper else 1); x, y = pts[0]; d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    return m

def _over(base, color, mask, alpha=1.0):
    a = np.asarray(mask, np.float32)[..., None] / 255 * alpha; b = np.asarray(base, np.float32)
    col = np.broadcast_to(np.asarray(color, np.float32), b.shape) if not isinstance(color, np.ndarray) else color
    return Image.fromarray(np.clip(b * (1 - a) + col * a, 0, 255).astype(np.uint8))

def _finish(big): return big.resize((TW, TH), Image.LANCZOS)

def _shape_at(d, kind, x, y, r, col, rng, ang=0.0):
    """one little shape for the scatter brushes"""
    if kind == "star":
        pts = [(x + math.cos(ang - math.pi / 2 + i * math.pi / 5) * (r if i % 2 == 0 else r * 0.45), y + math.sin(ang - math.pi / 2 + i * math.pi / 5) * (r if i % 2 == 0 else r * 0.45)) for i in range(10)]
        d.polygon(pts, fill=col)
    elif kind == "heart":
        d.ellipse([x - r, y - r * 0.8, x, y + r * 0.2], fill=col); d.ellipse([x, y - r * 0.8, x + r, y + r * 0.2], fill=col); d.polygon([(x - r * 0.95, y - r * 0.15), (x + r * 0.95, y - r * 0.15), (x, y + r)], fill=col)
    elif kind in ("leaf", "petal"):
        ca, sa = math.cos(ang), math.sin(ang); pts = [(x + (u * ca - v * sa) * r, y + (u * sa + v * ca) * r) for u, v in
               [(math.cos(t) * 1.0, math.sin(t) * (0.45 if kind == "leaf" else 0.6)) for t in np.linspace(0, 2 * math.pi, 18)]]
        d.polygon(pts, fill=col)
        if kind == "leaf": d.line([(x - ca * r, y - sa * r), (x + ca * r, y + sa * r)], fill=tuple(int(c * 0.6) for c in col), width=max(1, int(r / 5)))
    elif kind == "bubble": d.ellipse([x - r, y - r, x + r, y + r], outline=col, width=max(1, int(r / 4))); d.ellipse([x - r * 0.45, y - r * 0.55, x - r * 0.15, y - r * 0.25], fill=(255, 255, 255))
    elif kind == "sparkle":
        for a2 in (0, math.pi / 2): d.polygon([(x + math.cos(a2) * r, y + math.sin(a2) * r), (x + math.cos(a2 + math.pi / 2) * r * 0.18, y + math.sin(a2 + math.pi / 2) * r * 0.18),
                                               (x - math.cos(a2) * r, y - math.sin(a2) * r), (x - math.cos(a2 + math.pi / 2) * r * 0.18, y - math.sin(a2 + math.pi / 2) * r * 0.18)], fill=col)
    elif kind == "snow":
        for k in range(3):
            a2 = ang + k * math.pi / 3; d.line([(x - math.cos(a2) * r, y - math.sin(a2) * r), (x + math.cos(a2) * r, y + math.sin(a2) * r)], fill=col, width=max(1, int(r / 4)))
    elif kind == "confetti":
        c2 = tuple(int(v) for v in rng.choice([(240, 60, 90), (60, 160, 240), (250, 210, 40), (80, 200, 100), (190, 90, 230)])); w2 = r * 0.5
        d.polygon([(x - r * math.cos(ang) - w2 * math.sin(ang), y - r * math.sin(ang) + w2 * math.cos(ang)), (x + r * math.cos(ang) - w2 * math.sin(ang), y + r * math.sin(ang) + w2 * math.cos(ang)),
                   (x + r * math.cos(ang) + w2 * math.sin(ang), y + r * math.sin(ang) - w2 * math.cos(ang)), (x - r * math.cos(ang) + w2 * math.sin(ang), y - r * math.sin(ang) - w2 * math.cos(ang))], fill=c2)
    else: d.ellipse([x - r, y - r, x + r, y + r], fill=col)                         # splat / dot

def _scatter(look):
    rng = np.random.default_rng(11); W, H = TW * S, TH * S
    im = Image.new("RGB", (W, H), (14, 18, 40) if look.get("dark") else PAPER); d = ImageDraw.Draw(im); kind = look["scatter"]; col = look.get("color", (40, 40, 60))
    if look.get("stem"): d.line(_path(), fill=(60, 120, 50), width=int(1.6 * S))
    if look.get("even"):                                                                 # an even row along the stroke (pattern / stars / hearts...)
        for i, (x, y) in enumerate(_path(7)): _shape_at(d, kind, x, y, 4.2 * S, col, rng)
    else:
        n = {"splat": 40, "confetti": 22, "sparkle": 9, "snow": 8}.get(kind, 10)
        for _ in range(n):
            x = rng.uniform(6, 90) * S; y = (15 + rng.normal(0, 5)) * S; r = (rng.uniform(0.6, 2.4) if kind == "splat" else rng.uniform(2.4, 4.4)) * S
            _shape_at(d, kind, x, y, r, col, rng, rng.uniform(0, 6.3))
    return _finish(im)

def _stroke(look):
    rng = np.random.default_rng(len(str(look))); big = Image.new("RGB", (TW * S, TH * S), PAPER)
    m = _stroke_mask(look.get("width", 6), look.get("cap", "round"), look.get("taper", False))
    tex = look.get("tex")
    if tex == "dots":
        d = Image.new("L", m.size, 0); dd = ImageDraw.Draw(d)
        for x, y in _path(30):
            for _ in range(14):
                r = abs(rng.normal(0, 1)) * 4 * S; a = rng.uniform(0, 6.3); px, py = x + math.cos(a) * r, y + math.sin(a) * r * 0.8
                s = rng.uniform(0.3, 0.8) * S; dd.ellipse([px - s, py - s, px + s, py + s], fill=255)
        m = d
    arr = np.asarray(m, np.float32) / 255
    if tex in ("grain", "speckle"): arr = arr * (rng.random(arr.shape) > (0.35 if tex == "grain" else 0.5))
    if tex == "bristle": arr = arr * (0.55 + 0.45 * np.sin(np.arange(arr.shape[0])[:, None] * 0.9 + rng.random((1, arr.shape[1])) * 0.6) ** 2)
    if tex == "nib": arr = np.asarray(_stroke_mask(look["width"] * 1.6, taper=True), np.float32) / 255
    if tex == "fan": arr = arr * (np.sin(np.arange(arr.shape[0])[:, None] * 1.6) > 0.1)
    if tex == "ribbon":
        two = np.asarray(_stroke_mask(look["width"], path=[(x, y + math.sin(x / S / 4) * 4 * S) for x, y in _path()]), np.float32) / 255
        arr = np.clip(arr + two, 0, 1); look = dict(look, grad=(120, 60, 220))
    if tex == "smear": arr = np.asarray(Image.fromarray((arr * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(S * 3)), np.float32) / 255 * 1.2
    if tex == "swirl":
        two = np.asarray(_stroke_mask(look["width"] * 0.8, path=[(x, y + math.sin(x / S / 5) * 4 * S) for x, y in _path()]), np.float32) / 255
        arr = np.clip(arr * 0.55 + two * 0.65, 0, 1)                                   # two colours folding into each other
        look = dict(look, grad=(170, 60, 120))
    m = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))
    if look.get("soft"): m = m.filter(ImageFilter.GaussianBlur(look["soft"] * S))
    if tex == "wet": m = Image.fromarray(np.clip(np.asarray(m, np.float32) * (0.75 + 0.5 * rng.random((m.height, m.width)) ** 3), 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(S))
    color = look.get("color", (30, 30, 40))
    if look.get("grad"):                                                               # colour runs along the stroke (oil)
        t = np.linspace(0, 1, TW * S)[None, :, None]; color = np.asarray(color, np.float32) * (1 - t) + np.asarray(look["grad"], np.float32) * t
        color = np.broadcast_to(color, (TH * S, TW * S, 3))
    out = _over(big, color, m, look.get("alpha", 1.0))
    if tex in ("outline", "crisp"):
        edge = m.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
        out = _over(out, (10, 10, 15) if tex == "crisp" else (255, 255, 255), edge, 0.9 if tex == "crisp" else 0.8)
    return _finish(out)

def _fx(look):
    fx = look["fx"]; rng = np.random.default_rng(7); W, H = TW * S, TH * S; yy, xx = np.mgrid[0:H, 0:W]
    if fx == "dots":
        im = Image.new("RGB", (W, H), PAPER); d = ImageDraw.Draw(im)
        for cx in (W * 0.3, W * 0.7): d.ellipse([cx - 5 * S, H / 2 - 5 * S, cx + 5 * S, H / 2 + 5 * S], fill=(20, 40, 110))
        return _finish(im.filter(ImageFilter.GaussianBlur(look["radius"] * S)))
    if fx == "motion":
        m = _stroke_mask(5); m = m.filter(ImageFilter.BoxBlur(6 * S)); return _finish(_over(Image.new("RGB", (W, H), PAPER), (40, 50, 90), m, 1.0))
    if fx in ("radial", "zoom"):
        cx, cy = W / 2, H / 2; ang = np.arctan2(yy - cy, xx - cx); r = np.hypot((xx - cx) / W * 3, (yy - cy) / H)
        v = (0.5 + 0.5 * np.sin(ang * 14)) if fx == "zoom" else (0.5 + 0.5 * np.sin(ang * 3 + r * 18))
        a = np.clip(1 - r * 0.9, 0, 1) * v
        return _finish(Image.fromarray(np.clip(np.asarray(PAPER, np.float32) * (1 - a[..., None] * 0.7) + np.array([40, 50, 90]) * a[..., None] * 0.7, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(S * 1.5)))
    if fx in ("dodge", "burn"):
        bg = (110, 120, 140) if fx == "dodge" else (200, 205, 215); g = np.exp(-(((xx - W * 0.35) / (W * 0.22)) ** 2 + ((yy - H / 2) / (H * 0.35)) ** 2))
        col = 255 if fx == "dodge" else 0; a = np.asarray(bg, np.float32) * (1 - g[..., None]) + col * g[..., None]
        return _finish(Image.fromarray(a.astype(np.uint8)))
    if fx in ("rainbow", "hue"):
        h = xx / W + (np.sin(yy / H * 6.3) * 0.08 if fx == "hue" else 0)
        rgb = np.stack([np.clip(np.abs(((h * 6 + k) % 6) - 3) - 1, 0, 1) for k in (0, 4, 2)], -1) * 255
        return _finish(Image.fromarray(rgb.astype(np.uint8)))
    if fx == "noise":
        n = rng.random((TH, TW)) * 120 + 90; return Image.fromarray(np.repeat(n[..., None], 3, 2).astype(np.uint8))
    if fx == "pixelate":
        b = (rng.random((3, 10)) * 255).astype(np.uint8); return Image.fromarray(np.repeat(b[..., None], 3, 2)).resize((TW, TH), Image.NEAREST)
    if fx in ("neon", "ring", "shadow", "inner"):
        bg = Image.new("RGB", (W, H), (14, 18, 40)); m = _stroke_mask(7); col = look.get("color", (240, 240, 255))
        if fx == "neon":
            out = _over(bg, col, m.filter(ImageFilter.GaussianBlur(4 * S)), 1.0); out = _over(out, col, m, 1.0)
            return _finish(_over(out, (255, 255, 255), _stroke_mask(2.2), 0.9))
        if fx == "ring": return _finish(_over(bg, col, m.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(5)), 1.0))
        if fx == "shadow":
            sh = Image.new("L", m.size); sh.paste(m, (2 * S, 3 * S)); out = _over(bg, (0, 0, 0), sh.filter(ImageFilter.GaussianBlur(2 * S)), 0.9)
            return _finish(_over(out, (200, 210, 235), m, 1.0))                     # light stroke, dark shadow under it
        inner = np.clip(np.asarray(m, np.float32) - np.asarray(m.filter(ImageFilter.GaussianBlur(2 * S)), np.float32) * 0.8, 0, 255)
        out = _over(bg, (230, 235, 250), m.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(5)), 1.0)
        if look.get("glow"): out = _over(_over(bg, (30, 40, 80), m, 1.0), (110, 220, 255), Image.fromarray(inner.astype(np.uint8)), 1.0); return _finish(out)
        return _finish(_over(out, (40, 50, 90), Image.fromarray(inner.astype(np.uint8)), 0.9))
    if fx == "texture": return _texture(look["tex"])
    if fx == "pattern": return _pattern(look["pat"], look.get("col"))
    if fx == "icon":
        im = Image.new("RGB", (TW, TH), (20, 26, 42)); ic = icon(look["icon"], 26); im.paste(ic, ((TW - 26) // 2, 2), ic); return im      # dark, like the stamps: white icons show
    if fx == "shape": return _shape_tile(look["shape"])
    sample = _sample_scene()
    if fx == "emboss": return sample.convert("L").filter(ImageFilter.EMBOSS).convert("RGB")
    if fx == "solarize":
        from PIL import ImageOps; return ImageOps.solarize(sample, 110)
    if fx == "posterize":
        from PIL import ImageOps; return ImageOps.posterize(sample, 2)
    if fx == "halftone":
        im = Image.new("RGB", (W, H), (245, 245, 245)); d = ImageDraw.Draw(im); g = np.asarray(sample.convert("L").resize((24, 8)), np.float32) / 255
        for j in range(8):
            for i in range(24):
                r = (1 - g[j, i]) * 2.2 * S; cx, cy = (i + 0.5) * 4 * S, (j + 0.5) * 3.75 * S; d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(30, 40, 120))
        return _finish(im)
    if fx in ("rgbsplit", "chromatic"):
        a = np.asarray(sample, np.float32); o = 3 if fx == "rgbsplit" else 1
        out = np.stack([np.roll(a[..., 0], -o, 1), a[..., 1], np.roll(a[..., 2], o, 1)], -1)
        if fx == "chromatic": out = np.stack([np.roll(a[..., 0], -2, 1), np.roll(a[..., 1], 1, 0), np.roll(a[..., 2], 2, 1)], -1)
        return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    if fx == "drip":
        im = Image.new("RGB", (W, H), PAPER); d = ImageDraw.Draw(im); col = (40, 90, 200); d.rectangle([4 * S, 3 * S, 92 * S, 9 * S], fill=col)
        for x, L in zip(range(8, 92, 7), (14, 9, 18, 11, 16, 8, 13, 17, 10, 15, 12, 9)):
            d.rectangle([x * S, 8 * S, (x + 2.4) * S, (8 + L) * S], fill=col); d.ellipse([(x - 0.6) * S, (6 + L) * S, (x + 3) * S, (9.6 + L) * S], fill=col)
        return _finish(im)
    if fx in ("swirls", "flourish"):
        im = Image.new("RGB", (W, H), PAPER); d = ImageDraw.Draw(im); col = (60, 70, 90) if fx == "swirls" else (200, 160, 40)
        for cx in ((18, 48, 78) if fx == "swirls" else (24, 72)):
            pts = [(cx * S + math.cos(t) * t * 1.1 * S, 15 * S + math.sin(t) * t * 1.1 * S) for t in np.linspace(0, 11, 60)]
            d.line(pts, fill=col, width=int(1.6 * S))
        if fx == "flourish": d.line(_path(amp=3), fill=col, width=int(1.4 * S))
        return _finish(im)
    if fx == "gradfill":
        t = (xx + yy * 0.6) / (W + H * 0.6); a = np.stack([30 + 40 * t, 90 + 120 * t, 200 + 50 * t], -1)
        chk = ((xx // (6 * S) + yy // (6 * S)) % 2)[..., None]; return _finish(Image.fromarray(np.clip(a * (0.8 + 0.2 * chk), 0, 255).astype(np.uint8)))
    if fx == "blocks":
        im = Image.new("RGB", (W, H), PAPER); d = ImageDraw.Draw(im); d.rectangle([8 * S, 4 * S, 44 * S, 26 * S], fill=(40, 140, 240)); d.rectangle([52 * S, 4 * S, 88 * S, 26 * S], fill=(250, 110, 30))
        return _finish(im)
    if fx == "dither":
        g = (xx / W); th = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]])[(yy // S) % 4, (xx // S) % 4] / 16
        v = np.where(g > th, 235, 30); return _finish(Image.fromarray(np.repeat(v[..., None], 3, 2).astype(np.uint8)))
    return Image.new("RGB", (TW, TH), PAPER)

def _sample_scene():
    """a tiny sunset scene the effect previews are shown on"""
    H, W = TH, TW; yy, xx = np.mgrid[0:H, 0:W]; t = yy / H
    sky = np.stack([90 + 150 * t, 60 + 80 * t, 140 - 40 * t], -1); hill = yy > 18 + 6 * np.sin(xx / 14)
    sun = (xx - 62) ** 2 + (yy - 12) ** 2 < 30
    a = np.where(hill[..., None], np.array([50, 40, 70]), sky); a = np.where(sun[..., None], np.array([255, 220, 120]), a)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

def _pattern(name, col=None):
    W, H = TW * S, TH * S; yy, xx = np.mgrid[0:H, 0:W]; u, v = xx / S, yy / S
    def two(mask, a, b): return np.where(mask[..., None], np.asarray(a, np.float32), np.asarray(b, np.float32))
    red, white, blue = (225, 45, 55), (250, 248, 245), (40, 80, 200)
    if name == "dots": a = two(((u % 6 - 3) ** 2 + (v % 6 - 3) ** 2) < 3, white, red)
    elif name == "stripes": a = two(((u + v) % 8) < 4, blue, white)
    elif name == "checks": a = two(((u // 5 + v // 5) % 2) == 0, col or (20, 20, 25), white)
    elif name == "plaid":
        a = np.asarray((200, 40, 60), np.float32) * np.ones((H, W, 1)); a = np.where(((u % 10) < 2)[..., None], a * 0.5 + np.array([30, 30, 120]) * 0.5, a)
        a = np.where(((v % 10) < 2)[..., None], a * 0.5 + np.array([240, 200, 40]) * 0.5, a)
    elif name in ("hearts", "stars", "flowers"):
        im = Image.new("RGB", (W, H), {"hearts": (250, 225, 235), "stars": (30, 60, 170), "flowers": (250, 140, 40)}[name]); d = ImageDraw.Draw(im); rng = np.random.default_rng(1)
        for j in range(3):
            for i in range(10):
                x, y = (i * 10 + 5 + (j % 2) * 5) * S, (j * 10 + 5) * S
                if name == "flowers":
                    for k in range(5): a2 = k * 1.256; d.ellipse([x + math.cos(a2) * 2.2 * S - 1.8 * S, y + math.sin(a2) * 2.2 * S - 1.8 * S, x + math.cos(a2) * 2.2 * S + 1.8 * S, y + math.sin(a2) * 2.2 * S + 1.8 * S], fill=(255, 255, 255))
                    d.ellipse([x - 1.3 * S, y - 1.3 * S, x + 1.3 * S, y + 1.3 * S], fill=(250, 210, 40))
                else: _shape_at(d, name[:-1], x, y, 3.4 * S, (230, 40, 90) if name == "hearts" else (255, 255, 255), rng)
        return _finish(im)
    elif name == "circles": a = two(np.abs(np.hypot(u % 10 - 5, v % 10 - 5) - 3.2) < 0.9, white, blue)
    elif name == "diamonds": a = two((np.abs(u % 10 - 5) + np.abs(v % 10 - 5)) < 3.5, (240, 60, 160), white)
    elif name == "chevron": a = two(((v + np.abs(u % 10 - 5)) % 8) < 3.5, (40, 160, 230), (20, 50, 110))
    else: a = two(((v + 2.5 * np.sin(u / 2.5)) % 7) < 3, (50, 160, 230), (15, 40, 100))      # waves
    return _finish(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)))

def _shape_tile(shape):
    W, H = TW * S, TH * S; im = Image.new("RGB", (W, H), PAPER); d = ImageDraw.Draw(im); ink = (30, 40, 70); w = int(1.6 * S)
    if shape == "ruler":
        d.rectangle([6 * S, 9 * S, 90 * S, 21 * S], fill=(250, 210, 40), outline=(120, 90, 20), width=w)
        for i in range(8, 90, 4): d.line([(i * S, 9 * S), (i * S, (14 if i % 8 == 0 else 12) * S)], fill=(80, 60, 10), width=max(1, int(0.8 * S)))
    elif shape == "ellipse": d.ellipse([20 * S, 5 * S, 76 * S, 25 * S], outline=ink, width=w)
    elif shape == "rect": d.rectangle([24 * S, 5 * S, 72 * S, 25 * S], outline=ink, width=w)
    elif shape == "polygon": d.polygon([(48 * S + math.cos(a) * 18 * S, 15 * S + math.sin(a) * 10 * S) for a in np.linspace(0, 2 * math.pi, 7)[:-1]], outline=ink, width=w)
    elif shape == "line": d.line([(14 * S, 24 * S), (82 * S, 6 * S)], fill=ink, width=w)
    elif shape == "curve": d.line([((14 + 68 * t) * S, (24 - 36 * t * (1 - t) * 1.2) * S) for t in np.linspace(0, 1, 30)], fill=ink, width=w)
    elif shape == "freehand": d.line(_path(amp=5), fill=ink, width=w)
    elif shape == "polyline": d.line([(10 * S, 22 * S), (30 * S, 8 * S), (50 * S, 20 * S), (68 * S, 7 * S), (86 * S, 18 * S)], fill=ink, width=w, joint="curve")
    elif shape == "text": d.rectangle([40 * S, 4 * S, 56 * S, 8 * S], fill=ink); d.rectangle([46 * S, 4 * S, 50 * S, 26 * S], fill=ink)
    return _finish(im)

def _texture(name):
    rng = np.random.default_rng(3); H, W = TH, TW; yy, xx = np.mgrid[0:H, 0:W]
    if name == "canvas":
        v = 200 + 25 * ((xx % 3 == 0) | (yy % 3 == 0)) - 30 * rng.random((H, W)); c = np.stack([v, v * 0.98, v * 0.95], -1)
    elif name == "fabric":
        v = 60 + 40 * ((xx + yy) % 4 < 2) + 50 * rng.random((H, W)); c = np.stack([v, v, v * 1.05], -1)
    elif name == "brick":
        row = yy // 7; off = (row % 2) * 8; mortar = (yy % 7 == 0) | ((xx + off) % 16 == 0)
        c = np.where(mortar[..., None], np.array([200, 190, 175]), np.array([190, 75, 45]) + rng.normal(0, 10, (H, W, 1)))
    elif name == "metal":
        v = 120 + 70 * (xx / W) + 25 * np.sin(yy * 0.9 + rng.random((1, W)) * 3); c = np.stack([v * 0.92, v * 0.97, v * 1.05], -1)
    elif name == "paper":
        v = 222 + 18 * rng.random((H, W)); c = np.stack([v, v * 0.95, v * 0.84], -1)
    elif name == "wood":
        v = np.sin((yy + 3 * np.sin(xx / 9)) * 1.3) * 0.5 + 0.5; c = np.array([165, 105, 50]) * (0.75 + 0.3 * v[..., None]) + rng.normal(0, 4, (H, W, 1))
    elif name == "stone":
        n = _blobs(rng, 6, 16, H, W); c = np.stack([n, n * 0.97, n * 0.9], -1) * 150 + 60
    elif name in ("grunge", "concrete"):
        n = _blobs(rng, 5, 12, H, W) * 0.6 + rng.random((H, W)) * 0.4; base = 70 if name == "grunge" else 150
        c = np.stack([n] * 3, -1) * (90 if name == "grunge" else 60) + base
    elif name == "noise": v = rng.random((H, W)) * 150 + 60; c = np.stack([v] * 3, -1)
    elif name == "grain": v = 200 - (rng.random((H, W)) > 0.82) * 110; c = np.stack([v, v * 0.97, v * 0.92], -1)
    elif name == "sand": v = 205 + 30 * rng.random((H, W)); c = np.stack([v, v * 0.86, v * 0.6], -1)
    elif name == "spraytex": v = np.where(rng.random((H, W)) > 0.7, 40, 235); c = np.stack([v] * 3, -1)
    elif name == "water":
        v = 0.5 + 0.5 * np.sin(xx / 5 + np.sin(yy / 3) * 2); c = np.array([30, 110, 200]) * (0.8 + 0.3 * v[..., None])
    elif name == "tiles":
        grout = (yy % 10 == 0) | (xx % 10 == 0); c = np.where(grout[..., None], np.array([220, 225, 235]), np.array([40, 110, 210]) + rng.normal(0, 8, (H, W, 1)))
    elif name == "rust": n = _blobs(rng, 5, 14, H, W); c = np.stack([150 + 80 * n, 70 + 40 * n, 30 + 20 * n], -1) + rng.normal(0, 10, (H, W, 1))
    elif name == "mosaic":
        cells = rng.integers(0, 4, (H // 5 + 1, W // 5 + 1)); pal = np.array([[230, 120, 40], [250, 240, 230], [190, 60, 40], [80, 140, 200]])
        c = pal[cells[yy // 5, xx // 5]]; c = np.where(((yy % 5 == 0) | (xx % 5 == 0))[..., None], 60, c)
    elif name == "crackle":
        v = np.full((H, W), 215.0); im = Image.fromarray(v.astype(np.uint8)); d = ImageDraw.Draw(im)
        for _ in range(9):
            x, y = rng.uniform(0, W), rng.uniform(0, H)
            for _ in range(5): nx, ny = x + rng.normal(0, 8), y + rng.normal(0, 5); d.line([(x, y), (nx, ny)], fill=90); x, y = nx, ny
        v = np.asarray(im, np.float32); c = np.stack([v, v * 0.96, v * 0.88], -1)
    elif name == "bokeh":
        im = Image.new("RGB", (W, H), (25, 30, 60)); d = ImageDraw.Draw(im)
        for _ in range(14):
            x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(2, 6); col = tuple(int(v) for v in rng.choice([(250, 200, 120), (140, 180, 255), (255, 140, 200)]))
            d.ellipse([x - r, y - r, x + r, y + r], fill=col)
        return im.filter(ImageFilter.GaussianBlur(1.2))
    else:                                                                                 # clouds
        n = np.asarray(Image.fromarray((rng.random((5, 14)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32) / 255
        sky = np.array([90, 150, 225], np.float32); c = sky * (1 - n[..., None] ** 1.5) + 255 * n[..., None] ** 1.5
    return Image.fromarray(np.clip(c, 0, 255).astype(np.uint8))

def _blobs(rng, gh, gw, H, W):
    return np.asarray(Image.fromarray((rng.random((gh, gw)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32) / 255

def preview(item):
    """a 96 x 30 picture of what a planned tool will do"""
    look = item.get("look") or {}
    try: return _fx(look) if "fx" in look else _scatter(look) if "scatter" in look else _stroke(look)
    except Exception: return Image.new("RGB", (TW, TH), PAPER)

# ---------------------------------------------------------------- stamp icons (drawn, so they look the same on every PC)
def icon(name, size=28):
    Z = size * 4; im = Image.new("RGBA", (Z, Z), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = Z / 2; k = Z / 28
    def star(col):
        pts = [(c + math.cos(math.pi / 2 + i * math.pi / 5) * (12 if i % 2 == 0 else 5) * k, c - math.sin(math.pi / 2 + i * math.pi / 5) * (12 if i % 2 == 0 else 5) * k + k) for i in range(10)]
        d.polygon(pts, fill=col, outline=(30, 30, 40), width=int(k))
    def heart(col):
        d.ellipse([4 * k, 6 * k, 15 * k, 17 * k], fill=col); d.ellipse([13 * k, 6 * k, 24 * k, 17 * k], fill=col); d.polygon([(4.6 * k, 13 * k), (23.4 * k, 13 * k), (14 * k, 24 * k)], fill=col)
    n = name.lower()
    if n == "star": star((250, 250, 250))
    elif n == "gold star": star((255, 205, 40))
    elif n == "heart": heart((230, 40, 60))
    elif n == "blue heart": heart((70, 170, 240))
    elif n == "check": d.line([(5 * k, 15 * k), (11 * k, 21 * k), (23 * k, 7 * k)], fill=(40, 200, 80), width=int(4.5 * k), joint="curve")
    elif n == "cross": d.line([(6 * k, 6 * k), (22 * k, 22 * k)], fill=(230, 40, 50), width=int(4.5 * k)); d.line([(22 * k, 6 * k), (6 * k, 22 * k)], fill=(230, 40, 50), width=int(4.5 * k))
    elif n == "plus": d.rectangle([12 * k, 5 * k, 16 * k, 23 * k], fill=(60, 210, 90)); d.rectangle([5 * k, 12 * k, 23 * k, 16 * k], fill=(60, 210, 90))
    elif n == "minus": d.rectangle([5 * k, 12 * k, 23 * k, 16 * k], fill=(70, 160, 240))
    elif n == "warning":
        d.polygon([(c, 4 * k), (25 * k, 24 * k), (3 * k, 24 * k)], fill=(255, 205, 40), outline=(40, 30, 10), width=int(k))
        d.rectangle([13 * k, 10 * k, 15 * k, 18 * k], fill=(30, 25, 10)); d.ellipse([12.8 * k, 19.5 * k, 15.2 * k, 21.9 * k], fill=(30, 25, 10))
    elif n == "info":
        d.rounded_rectangle([4 * k, 4 * k, 24 * k, 24 * k], radius=4 * k, fill=(40, 90, 220)); d.ellipse([12.6 * k, 7 * k, 15.4 * k, 9.8 * k], fill="white"); d.rectangle([12.8 * k, 11.5 * k, 15.2 * k, 21 * k], fill="white")
    elif n == "gear":
        for i in range(8):
            a = i * math.pi / 4; d.line([(c + math.cos(a) * 6 * k, c + math.sin(a) * 6 * k), (c + math.cos(a) * 11 * k, c + math.sin(a) * 11 * k)], fill=(120, 150, 210), width=int(4 * k))
        d.ellipse([c - 8 * k, c - 8 * k, c + 8 * k, c + 8 * k], fill=(120, 150, 210)); d.ellipse([c - 3.5 * k, c - 3.5 * k, c + 3.5 * k, c + 3.5 * k], fill=(0, 0, 0, 0))
    elif n == "house":
        d.polygon([(c, 4 * k), (25 * k, 14 * k), (3 * k, 14 * k)], fill=(230, 90, 60)); d.rectangle([7 * k, 14 * k, 21 * k, 24 * k], fill=(245, 235, 215)); d.rectangle([12 * k, 17 * k, 16 * k, 24 * k], fill=(150, 90, 50))
    elif n == "folder": d.rectangle([3 * k, 8 * k, 12 * k, 11 * k], fill=(230, 170, 30)); d.rounded_rectangle([3 * k, 10 * k, 25 * k, 23 * k], radius=2 * k, fill=(250, 200, 50))
    elif n == "document":
        d.polygon([(7 * k, 3 * k), (18 * k, 3 * k), (22 * k, 7 * k), (22 * k, 25 * k), (7 * k, 25 * k)], fill=(245, 245, 250))
        for y in (10, 14, 18): d.line([(10 * k, y * k), (19 * k, y * k)], fill=(90, 110, 160), width=int(1.5 * k))
    elif n == "trash":
        d.rectangle([6 * k, 6 * k, 22 * k, 9 * k], fill=(120, 150, 210)); d.rectangle([11 * k, 4 * k, 17 * k, 6 * k], fill=(120, 150, 210)); d.polygon([(7 * k, 10 * k), (21 * k, 10 * k), (19 * k, 25 * k), (9 * k, 25 * k)], fill=(120, 150, 210))
    elif n == "palette":
        d.ellipse([3 * k, 5 * k, 25 * k, 23 * k], fill=(225, 175, 110)); d.ellipse([15 * k, 14 * k, 20 * k, 19 * k], fill=(0, 0, 0, 0))
        for (x, y), col in zip(((8, 10), (13, 8), (18, 10), (8, 16)), ((230, 50, 50), (50, 120, 230), (60, 190, 80), (250, 210, 40))): d.ellipse([x * k - 2 * k, y * k - 2 * k, x * k + 2 * k, y * k + 2 * k], fill=col)
    elif n == "eyedropper": d.line([(7 * k, 21 * k), (19 * k, 9 * k)], fill=(170, 200, 230), width=int(3 * k)); d.ellipse([17 * k, 4 * k, 24 * k, 11 * k], fill=(60, 70, 90)); d.line([(5 * k, 23 * k), (8 * k, 20 * k)], fill=(40, 120, 220), width=int(2 * k))
    elif n == "magnifier": d.ellipse([4 * k, 4 * k, 18 * k, 18 * k], outline=(80, 160, 240), width=int(3 * k)); d.line([(16 * k, 16 * k), (24 * k, 24 * k)], fill=(80, 160, 240), width=int(4 * k))
    elif n == "hand":
        d.rounded_rectangle([8 * k, 12 * k, 21 * k, 25 * k], radius=4 * k, fill=(250, 220, 190))
        for x, top in ((8.5, 6), (11.8, 4), (15.1, 4.5), (18.4, 7)): d.rounded_rectangle([x * k, top * k, (x + 2.8) * k, 15 * k], radius=1.4 * k, fill=(250, 220, 190))
        d.rounded_rectangle([4 * k, 13 * k, 9 * k, 16 * k], radius=1.4 * k, fill=(250, 220, 190))
    elif n == "pointer": d.polygon([(8 * k, 3 * k), (8 * k, 22 * k), (12.5 * k, 17.5 * k), (16 * k, 25 * k), (19 * k, 23.5 * k), (15.5 * k, 16 * k), (21 * k, 16 * k)], fill="white", outline=(20, 20, 30), width=int(k))
    elif n in ("pencil", "yellow pencil"):
        body = (90, 150, 230) if n == "pencil" else (250, 200, 40)
        d.line([(7 * k, 21 * k), (21 * k, 7 * k)], fill=body, width=int(5 * k)); d.polygon([(4 * k, 24 * k), (5.5 * k, 18.5 * k), (9.5 * k, 22.5 * k)], fill=(240, 205, 160)); d.line([(20 * k, 8 * k), (23 * k, 5 * k)], fill=(240, 120, 140), width=int(5 * k))
    elif n == "eraser": d.polygon([(4 * k, 17 * k), (15 * k, 6 * k), (24 * k, 15 * k), (13 * k, 26 * k)], fill=(240, 240, 245)); d.polygon([(4 * k, 17 * k), (9 * k, 12 * k), (18 * k, 21 * k), (13 * k, 26 * k)], fill=(170, 190, 220))
    elif n == "paint bucket":
        d.polygon([(7 * k, 9 * k), (21 * k, 9 * k), (19 * k, 25 * k), (9 * k, 25 * k)], fill=(70, 140, 230)); d.ellipse([7 * k, 7 * k, 21 * k, 11 * k], fill=(120, 190, 250)); d.arc([8 * k, 2 * k, 20 * k, 14 * k], 180, 360, fill=(200, 210, 230), width=int(1.6 * k))
    elif n == "text": d.rectangle([5 * k, 4 * k, 23 * k, 8 * k], fill="white"); d.rectangle([12 * k, 4 * k, 16 * k, 24 * k], fill="white")
    # ---- tools (also used on the Draw toolbar buttons)
    elif n == "magic wand":
        d.line([(5 * k, 23 * k), (17 * k, 11 * k)], fill=(200, 160, 90), width=int(3 * k)); star_at = (20 * k, 8 * k)
        pts = [(star_at[0] + math.cos(-math.pi / 2 + i * math.pi / 5) * (6 if i % 2 == 0 else 2.5) * k, star_at[1] + math.sin(-math.pi / 2 + i * math.pi / 5) * (6 if i % 2 == 0 else 2.5) * k) for i in range(10)]
        d.polygon(pts, fill=(255, 220, 60))
    elif n == "color picker": icon_draw_dropper(d, k, (60, 200, 90))
    elif n == "crop":
        d.line([(9 * k, 3 * k), (9 * k, 19 * k), (25 * k, 19 * k)], fill="white", width=int(2.6 * k)); d.line([(3 * k, 9 * k), (19 * k, 9 * k), (19 * k, 25 * k)], fill="white", width=int(2.6 * k))
    elif n in ("move", "fit"):
        col = (90, 180, 255) if n == "move" else "white"
        for a2 in range(4):
            ang = a2 * math.pi / 2; tx, ty = c + math.cos(ang) * 11 * k, c + math.sin(ang) * 11 * k
            if n == "move": d.line([(c, c), (tx, ty)], fill=col, width=int(2.4 * k))
            d.polygon([(tx + math.cos(ang) * 2 * k, ty + math.sin(ang) * 2 * k), (tx - math.cos(ang) * 3 * k + math.cos(ang + math.pi / 2) * 3.5 * k, ty - math.sin(ang) * 3 * k + math.sin(ang + math.pi / 2) * 3.5 * k),
                       (tx - math.cos(ang) * 3 * k - math.cos(ang + math.pi / 2) * 3.5 * k, ty - math.sin(ang) * 3 * k - math.sin(ang + math.pi / 2) * 3.5 * k)], fill=col)
        if n == "fit": d.rectangle([9 * k, 9 * k, 19 * k, 19 * k], outline="white", width=int(2 * k))
    elif n in ("rotate", "undo", "redo"):
        flip = n == "redo"; d.arc([5 * k, 5 * k, 23 * k, 23 * k], 200 if not flip else -20, 520 if n == "rotate" else (450 if not flip else 160), fill="white", width=int(2.8 * k))
        ax, ay = (5.5 * k, 11 * k) if not flip else (22.5 * k, 11 * k)
        d.polygon([(ax - 3.5 * k, ay - 1 * k), (ax + 3.5 * k, ay - 1 * k), (ax, ay + 4.5 * k)], fill="white")
    elif n in ("flip", "mirror"):
        d.polygon([(12 * k, 5 * k), (12 * k, 23 * k), (3 * k, 23 * k)], fill=(120, 170, 255)); d.polygon([(16 * k, 5 * k), (16 * k, 23 * k), (25 * k, 23 * k)], outline="white", width=int(1.6 * k))
        d.line([(14 * k, 3 * k), (14 * k, 25 * k)], fill=(255, 90, 160), width=int(1.4 * k))
    elif n in ("zoom in", "zoom out"):
        d.ellipse([4 * k, 4 * k, 18 * k, 18 * k], outline="white", width=int(2.6 * k)); d.line([(16 * k, 16 * k), (24 * k, 24 * k)], fill="white", width=int(3.6 * k))
        d.line([(7.5 * k, 11 * k), (14.5 * k, 11 * k)], fill="white", width=int(2.2 * k))
        if n == "zoom in": d.line([(11 * k, 7.5 * k), (11 * k, 14.5 * k)], fill="white", width=int(2.2 * k))
    elif n == "brush":
        d.line([(10 * k, 18 * k), (23 * k, 5 * k)], fill=(200, 150, 90), width=int(3 * k)); d.polygon([(3 * k, 25 * k), (6 * k, 16 * k), (12 * k, 20 * k)], fill=(255, 120, 60))
        d.line([(8 * k, 17 * k), (11 * k, 20 * k)], fill=(220, 220, 230), width=int(3 * k))
    elif n == "line": d.line([(5 * k, 23 * k), (23 * k, 5 * k)], fill="white", width=int(2.6 * k)); [d.ellipse([x - 2.4 * k, y - 2.4 * k, x + 2.4 * k, y + 2.4 * k], fill="white") for x, y in ((5 * k, 23 * k), (23 * k, 5 * k))]
    elif n == "rect": d.rectangle([4 * k, 7 * k, 24 * k, 21 * k], outline="white", width=int(2.6 * k))
    elif n == "oval": d.ellipse([3 * k, 7 * k, 25 * k, 21 * k], outline="white", width=int(2.6 * k))
    elif n == "new": d.polygon([(7 * k, 3 * k), (18 * k, 3 * k), (22 * k, 7 * k), (22 * k, 25 * k), (7 * k, 25 * k)], fill=(245, 245, 250)); d.line([(14.5 * k, 10 * k), (14.5 * k, 20 * k)], fill=(40, 170, 80), width=int(2.6 * k)); d.line([(9.5 * k, 15 * k), (19.5 * k, 15 * k)], fill=(40, 170, 80), width=int(2.6 * k))
    elif n == "open": d.rectangle([3 * k, 7 * k, 12 * k, 10 * k], fill=(230, 170, 30)); d.rounded_rectangle([3 * k, 9 * k, 25 * k, 23 * k], radius=2 * k, fill=(250, 200, 50))
    elif n == "picture":
        d.rounded_rectangle([3 * k, 5 * k, 25 * k, 23 * k], radius=2 * k, fill=(110, 170, 240)); d.polygon([(4 * k, 22 * k), (12 * k, 12 * k), (18 * k, 18 * k), (21 * k, 15 * k), (24 * k, 22 * k)], fill=(60, 150, 70))
        d.ellipse([17 * k, 7 * k, 22 * k, 12 * k], fill=(255, 230, 90))
    elif n == "save":
        d.rounded_rectangle([4 * k, 4 * k, 24 * k, 24 * k], radius=2 * k, fill=(70, 130, 230)); d.rectangle([8 * k, 4 * k, 20 * k, 11 * k], fill=(230, 235, 245)); d.rectangle([8 * k, 15 * k, 20 * k, 24 * k], fill=(30, 50, 100))
    elif n == "send":
        d.rounded_rectangle([3 * k, 9 * k, 19 * k, 25 * k], radius=2 * k, outline="white", width=int(2.2 * k)); d.line([(11 * k, 17 * k), (23 * k, 5 * k)], fill=(60, 220, 120), width=int(2.8 * k))
        d.polygon([(25 * k, 3 * k), (16 * k, 4.5 * k), (23.5 * k, 12 * k)], fill=(60, 220, 120))
    elif n == "restore":                                                          # the window-bar "restore" look: two overlapping squares
        d.rectangle([9 * k, 4 * k, 24 * k, 19 * k], outline="white", width=int(2.2 * k)); d.rectangle([4 * k, 9 * k, 19 * k, 24 * k], fill=(40, 73, 140), outline="white", width=int(2.2 * k))
    elif n == "maximize": d.rectangle([5 * k, 5 * k, 23 * k, 23 * k], outline="white", width=int(2.4 * k))
    elif n in ("up", "down"):
        pts = [(c, 5 * k), (23 * k, 16 * k), (17 * k, 16 * k), (17 * k, 24 * k), (11 * k, 24 * k), (11 * k, 16 * k), (5 * k, 16 * k)]
        if n == "down": pts = [(x, Z - y) for x, y in pts]
        d.polygon(pts, fill="white")
    return im.resize((size, size), Image.LANCZOS)

def icon_draw_dropper(d, k, tip):
    d.line([(7 * k, 21 * k), (19 * k, 9 * k)], fill=(200, 210, 230), width=int(3 * k)); d.ellipse([17 * k, 4 * k, 24 * k, 11 * k], fill=(60, 70, 90)); d.line([(5 * k, 23 * k), (8 * k, 20 * k)], fill=tip, width=int(2 * k))
