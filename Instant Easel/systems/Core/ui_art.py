"""
ui_art.py: Instant Easel's painted UI pictures (images/UI/<area>/..., see AREAS), found by name, sized and cached.

Every lookup returns None when a picture isn't there, so the caller keeps drawing its own (nothing ever goes blank).
To swap a picture, replace its PNG; to use a different one, change the name in the tables below.

    import ui_art as UA
    UA.toolbar("undo", h=38)       -> PIL RGBA picture 38 px tall (or None)
    UA.tile("Round", w=120)        -> the brush library tile for the catalog's "Round" (or None)
    UA.tile_title("Round")         -> the name painted on that tile ("Round Brush"), or "" if it has none
    UA.preview("Drip", "Special Brushes") -> the painted preview strip (or None)
    UA.stamp("Heart", 28)          -> a square stamp picture (or None)
"""
import os, re, threading
from PIL import Image

import paths
ROOT = paths.IMAGES                                                   # every picture is under images/ (see AREAS for where each kind lives)

# the code asks for pictures by short names ("toolbar/undo", "panel/swatch", "custom/Pens/Pen" ...); this says which images/ folder
# each kind is kept in. Pictures not used yet live under images/unused/, grouped by what they'd be for.
AREAS = {"skin": "UI/Tabs and Menus", "toolbar": "UI/Draw Toolbar", "buttons": "UI/Draw Toolbar/File Buttons", "custom": "UI/Brush Library",
         "panel": "UI/Color Wheel Menu", "previews": "unused/Brushes/Guide Swatches", "brushes": "unused/Brushes/Brush Library Tiles",
         "brushes_b": "unused/Brushes/Game Menu Tiles", "library": "unused/Brushes/Library Tiles", "variants": "unused/Brushes/Variant Tiles 1",
         "variants_b": "unused/Brushes/Variant Tiles 2", "stamps": "unused/Stamps/Stamps", "art": "unused/Icons/Artist Pieces",
         "tools": "unused/Icons/Toolkit Icons", "options": "unused/Buttons/Option Buttons"}
def _area(kind, name):
    """the folder for one picture: a few panel / toolbar pieces have their own UI area"""
    if kind == "panel":
        if name.startswith("slider_"): return "UI/Sliders"
        if name.startswith("scroll_"): return "UI/Scroll Bars"
        if name in ("side_bar", "arrow_left", "arrow_right"): return "UI/Side Panel Bars"
        if name.startswith("ball_"): return "UI/Status Dots"
    if kind == "toolbar" and name in ("win_max", "win_restore"): return "UI/Window Buttons"
    return AREAS.get(kind, kind)

# ---- toolbar: the Draw studio's top row. File buttons have their words painted on; the rest are square icons
TOOLBAR = {
    "new": "buttons/new", "open": "buttons/open", "picture": "buttons/last", "save": "buttons/save", "send": "buttons/send",
    "undo": "toolbar/undo", "redo": "toolbar/redo", "reset": "toolbar/reset", "apply": "toolbar/apply", "before_after": "toolbar/before_after", "compare": "toolbar/compare", "zoom in": "toolbar/zoom_in", "zoom out": "toolbar/zoom_out",
    "brush": "toolbar/brush", "eraser": "toolbar/eraser", "eyedropper": "toolbar/color", "paint bucket": "toolbar/bucket", "text": "toolbar/text",
    "restore": "toolbar/win_restore", "maximize": "toolbar/win_max",       # the studio-size button: single square at normal size, double square expanded
    "fit": "toolbar/fit", "line": "toolbar/shape_line", "rect": "toolbar/shape_rect", "oval": "toolbar/shape_oval",
    "select rect": "toolbar/select_rect", "select oval": "toolbar/select_oval", "crop": "toolbar/crop",          # selection and crop tools
    "mirror": "toolbar/mirror", "toggle_on": "toolbar/toggle_on", "toggle_off": "toolbar/toggle_off",   # mirror icon and its on/off switch
}

# ---- brush library: only the matching Brush Library tiles (frame + name pill, all the same 2:1 shape), and only where the painted
# name is the brush's own name. Everything else keeps its drawn preview.
TILES = {
    "Round": "brushes/round_brush", "Flat": "brushes/flat_brush", "Filbert": "brushes/filbert_brush", "Watercolor": "brushes/watercolor_brush",
    "Airbrush": "brushes/airbrush", "Oil Paint": "brushes/oil_paint", "Ink Brush": "brushes/ink_brush", "Marker": "brushes/marker",
    "Charcoal": "brushes/charcoal", "Pastel": "brushes/pastel", "Crayon": "brushes/crayon", "Splatter": "brushes/splatter_brush",
    "Stipple": "brushes/stipple_brush", "Pattern Brush": "brushes/pattern_brush", "Smudge": "brushes/smudge", "Blend": "brushes/blend",
    "Fill": "brushes/fill", "Gradient": "brushes/gradient",
}
TILE_SIZE = (3, 2)                                                     # every tile is shown at exactly this shape (width : height)
_TITLED = ("brushes/", "custom/")

# ---- the pictures you edit: images/UI/Brush Library/<Section_Title>/<Name>.png, one for EVERY item in the Draw studio's brush list, named
# exactly as the list names it (e.g. custom/Special Brushes/Drip.png, custom/Stamps & Icons/Heart.png). The app loads every tile and
# stamp from there. Tiles still left as the blank template (custom/_template.png) are shown with the brush's name written on the pill;
# paint over one and save it under the same name and your picture is shown instead (from the next start). Put the name on the pill
# yourself: the app doesn't add a label under custom tiles. If a file is missing, the old picture (tables above) is used instead.
CUSTOM = "custom"

# ---- painted preview strips (from the brushes guides) for everything above that has no painted tile. "Section:Name" keys;
# all strips are the same size (3.2 : 1), shown the same way as the drawn previews, with the name under them.
PREVIEWS = {
    # Brushes
    'Brushes:Soft Round': 'previews/brushes/soft_round',
    'Brushes:Hard Round': 'previews/brushes/hard_round',
    'Brushes:Square': 'previews/brushes/square',
    'Brushes:Pencil': 'previews/brushes/pencil',
    'Brushes:Spray': 'previews/brushes/spray',
    'Brushes:Ink': 'previews/brushes/ink',
    # Pens
    'Pens:Pen': 'previews/pens/pen',
    'Pens:Calligraphy': 'previews/pens/calligraphy',
    'Pens:G Pen': 'previews/pens/g_pen',
    'Pens:Fountain Pen': 'previews/pens/fountain_pen',
    'Pens:Technical Pen': 'previews/pens/technical_pen',
    'Pens:Fineliner': 'previews/pens/fineliner',
    # Special Brushes
    'Special Brushes:Drip': 'previews/special_brushes/drip',
    'Special Brushes:Leaf': 'previews/special_brushes/leaf',
    'Special Brushes:Star': 'previews/special_brushes/star',
    'Special Brushes:Heart': 'previews/special_brushes/heart',
    'Special Brushes:Bubble': 'previews/special_brushes/bubble',
    'Special Brushes:Sparkle': 'previews/special_brushes/sparkle',
    # Blending
    'Blending:Blur': 'previews/blending/blur',
    'Blending:Soften': 'previews/blending/soften',
    'Blending:Mix': 'previews/blending/mix',
    # Blurring
    'Blurring:Blur': 'previews/blurring/blur',
    'Blurring:Gaussian Blur': 'previews/blurring/gaussian_blur',
    'Blurring:Motion Blur': 'previews/blurring/motion_blur',
    'Blurring:Radial Blur': 'previews/blurring/radial_blur',
    'Blurring:Zoom Blur': 'previews/blurring/zoom_blur',
    # Sharpen
    'Sharpen:Sharpen': 'previews/sharpen/sharpen',
    'Sharpen:Unsharp Mask': 'previews/sharpen/unsharp_mask',
    'Sharpen:High Pass': 'previews/sharpen/high_pass',
    'Sharpen:Edge Enhance': 'previews/sharpen/edge_enhance',
    'Sharpen:Detail': 'previews/sharpen/detail',
    # Special Effects
    'Special Effects:Dodge': 'previews/special_effects/dodge',
    'Special Effects:Burn': 'previews/special_effects/burn',
    'Special Effects:Saturation': 'previews/special_effects/saturation',
    'Special Effects:Hue Shift': 'previews/special_effects/hue_shift',
    'Special Effects:Noise': 'previews/special_effects/noise',
    # Effect Brushes
    'Effect Brushes:Glow': 'previews/effect_brushes/glow',
    'Effect Brushes:Neon': 'previews/effect_brushes/neon',
    'Effect Brushes:Outline': 'previews/effect_brushes/outline',
    'Effect Brushes:Shadow': 'previews/effect_brushes/shadow',
    'Effect Brushes:Inner Shadow': 'previews/effect_brushes/inner_shadow',
    'Effect Brushes:Outer Glow': 'previews/effect_brushes/outer_glow',
    'Effect Brushes:Pixelate': 'previews/effect_brushes/pixelate',
    'Effect Brushes:Inner Glow': 'previews/effect_brushes/inner_glow',
    'Effect Brushes:Emboss': 'previews/effect_brushes/emboss',
    'Effect Brushes:Solarize': 'previews/effect_brushes/solarize',
    'Effect Brushes:Posterize': 'previews/effect_brushes/posterize',
    'Effect Brushes:Halftone': 'previews/effect_brushes/halftone',
    'Effect Brushes:RGB Split': 'previews/effect_brushes/rgb_split',
    'Effect Brushes:Chromatic': 'previews/effect_brushes/chromatic',
    # Decorative Brushes
    'Decorative Brushes:Stars': 'previews/decorative_brushes/stars',
    'Decorative Brushes:Sparkles': 'previews/decorative_brushes/sparkles',
    'Decorative Brushes:Hearts': 'previews/decorative_brushes/hearts',
    'Decorative Brushes:Confetti': 'previews/decorative_brushes/confetti',
    'Decorative Brushes:Petals': 'previews/decorative_brushes/petals',
    'Decorative Brushes:Snowflakes': 'previews/decorative_brushes/snowflakes',
    'Decorative Brushes:Bubbles': 'previews/decorative_brushes/bubbles',
    'Decorative Brushes:Ribbons': 'previews/decorative_brushes/ribbons',
    'Decorative Brushes:Swirls': 'previews/decorative_brushes/swirls',
    'Decorative Brushes:Flourish': 'previews/decorative_brushes/flourish',
    'Decorative Brushes:Vines': 'previews/decorative_brushes/vines',
    'Decorative Brushes:Dots': 'previews/decorative_brushes/dots',
    # Texture Brushes
    'Texture Brushes:Grain': 'previews/texture_brushes/grain',
    'Texture Brushes:Sand': 'previews/texture_brushes/sand',
    'Texture Brushes:Spray Texture': 'previews/texture_brushes/spray_texture',
    'Texture Brushes:Fabric Texture': 'previews/texture_brushes/fabric_texture',
    'Texture Brushes:Paper Texture': 'previews/texture_brushes/paper_texture',
    'Texture Brushes:Grunge Texture': 'previews/texture_brushes/grunge_texture',
    'Texture Brushes:Concrete': 'previews/texture_brushes/concrete',
    'Texture Brushes:Rust': 'previews/texture_brushes/rust',
    'Texture Brushes:Mosaic': 'previews/texture_brushes/mosaic',
    'Texture Brushes:Crackle': 'previews/texture_brushes/crackle',
    'Texture Brushes:Bokeh': 'previews/texture_brushes/bokeh',
    'Texture Brushes:Noise Texture': 'previews/texture_brushes/noise_texture',
    # Textures
    'Textures:Canvas': 'previews/textures/canvas',
    'Textures:Fabric': 'previews/textures/fabric',
    'Textures:Brick': 'previews/textures/brick',
    'Textures:Metal': 'previews/textures/metal',
    'Textures:Paper': 'previews/textures/paper',
    'Textures:Clouds': 'previews/textures/clouds',
    'Textures:Wood': 'previews/textures/wood',
    'Textures:Stone': 'previews/textures/stone',
    'Textures:Grunge': 'previews/textures/grunge',
    'Textures:Noise': 'previews/textures/noise',
    'Textures:Water': 'previews/textures/water',
    'Textures:Tiles': 'previews/textures/tiles',
    # Patterns
    'Patterns:Dots': 'previews/patterns/dots',
    'Patterns:Stripes': 'previews/patterns/stripes',
    'Patterns:Checks': 'previews/patterns/checks',
    'Patterns:Plaid': 'previews/patterns/plaid',
    'Patterns:Hearts': 'previews/patterns/hearts',
    'Patterns:Stars': 'previews/patterns/stars',
    'Patterns:Flowers': 'previews/patterns/flowers',
    'Patterns:Circles': 'previews/patterns/circles',
    'Patterns:Diamonds': 'previews/patterns/diamonds',
    'Patterns:Chevron': 'previews/patterns/chevron',
    'Patterns:Waves': 'previews/patterns/waves',
    # Paint Tools
    'Paint Tools:Radial Gradient': 'previews/paint_tools/gradient_fill',
    'Paint Tools:Pattern Fill': 'previews/paint_tools/pattern_fill',
}

# ---- stamps (the guide's Stamps & Icons, same order as the catalog)
STAMPS = {
    'Star': 'stamps/star',
    'Gold Star': 'stamps/gold_star',
    'Heart': 'stamps/heart',
    'Blue Heart': 'stamps/blue_heart',
    'Check': 'stamps/check',
    'Cross': 'stamps/cross',
    'Plus': 'stamps/plus',
    'Minus': 'stamps/minus',
    'Warning': 'stamps/warning',
    'Info': 'stamps/info',
    'Gear': 'stamps/gear',
    'House': 'stamps/house',
    'Folder': 'stamps/folder',
    'Document': 'stamps/document',
    'Trash': 'stamps/trash',
    'Palette': 'stamps/palette',
    'Eyedropper': 'stamps/eyedropper',
    'Magnifier': 'stamps/magnifier',
    'Hand': 'stamps/hand',
    'Pointer': 'stamps/pointer',
    'Pencil': 'stamps/pencil',
    'Yellow Pencil': 'stamps/yellow_pencil',
    'Eraser': 'stamps/eraser',
    'Paint Bucket': 'stamps/paint_bucket',
    'Text': 'stamps/text',
}

# The drawing app ships only images/UI: every brush tile comes from images/UI/Brush Library, so the full app's back-up tables (which
# point at its images/unused pictures) are empty here.
TILES, PREVIEWS, STAMPS = {}, {}, {}

_src = {}; _sized = {}; _lock = threading.RLock()
MAX_SIDE = {"toolbar": 128, "buttons": 128}            # pictures are shrunk once on load to what the app can ever show (fast to resize later)
MAX_OTHER = 360

def path(rel):
    kind, _, rest = rel.partition("/")
    return os.path.join(ROOT, *_area(kind, rest.split("/")[0]).split("/"), *rest.split("/")) + ".png"

def _shrink(rel, im):
    """big source pictures are shrunk once (good quality), so every later resize is small and quick"""
    folder = rel.split("/")[0]
    if folder in MAX_SIDE:
        lim = MAX_SIDE[folder]
        if im.height > lim: im = im.resize((max(1, round(im.width * lim / im.height)), lim), Image.LANCZOS, reducing_gap=2.0)
    elif max(im.size) > MAX_OTHER:
        k = MAX_OTHER / max(im.size); im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS, reducing_gap=2.0)
    return im

def load(rel):
    """the picture (cached, shrunk to the most the app shows), or None if the file is missing or unreadable"""
    if not rel: return None
    with _lock:
        if rel not in _src:
            if rel.startswith(CUSTOM + "/") and rel != f"{CUSTOM}/_template" and _is_blank(rel):
                _src[rel] = load(f"{CUSTOM}/_template")                   # a blank template: share the one copy, no decoding
            else:
                try: im = Image.open(path(rel)); im.load(); _src[rel] = _shrink(rel, im.convert("RGBA"))
                except Exception: _src[rel] = None
        return _src[rel]

def sized(rel, w=None, h=None):
    """the picture at width w or height h (keeping its shape), cached per size"""
    im = load(rel)
    if im is None: return None
    if w is None and h is None: return im
    if w is None: w = max(1, round(im.width * h / im.height))
    if h is None: h = max(1, round(im.height * w / im.width))
    key = (rel, w, h)
    if key not in _sized: _sized[key] = im.resize((w, h), Image.LANCZOS)
    return _sized[key]

def preload(rels=None):
    """decode pictures ahead of time (used in a background thread at start-up)"""
    if rels is None:
        rels = list(TOOLBAR.values())
        cdir = os.path.join(ROOT, *AREAS[CUSTOM].split("/"))
        for d, _, fs in os.walk(cdir):
            for f in fs:
                if f.endswith(".png"): rels.append(CUSTOM + "/" + os.path.relpath(os.path.join(d, f[:-4]), cdir).replace(os.sep, "/"))
        rels += list(PREVIEWS.values())
    for r in rels:
        try: load(r)
        except Exception: pass

def preload_in_background():
    t = threading.Thread(target=preload, name="ui_art preload", daemon=True); t.start(); return t

def _key(s): return re.sub(r"[^a-z0-9]", "", str(s).lower())

def toolbar(name, h=None):
    return sized(TOOLBAR.get(name), h=h) if name in TOOLBAR else None

def _slug(s): return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")

_blank = None; _blank_n = -1; _blankmemo = {}
def _is_blank(rel):
    """True while a custom tile is still exactly the template (checked by size first, so it's quick)"""
    global _blank, _blank_n
    if rel in _blankmemo: return _blankmemo[rel]
    if _blank is None:
        try: _blank = open(path(f"{CUSTOM}/_template"), "rb").read()
        except Exception: _blank = b""
        _blank_n = len(_blank)
    try: res = bool(_blank) and os.path.getsize(path(rel)) == _blank_n and open(path(rel), "rb").read() == _blank
    except Exception: res = False
    _blankmemo[rel] = res; return res

def file_name(s): return str(s).replace(" ", "_")                           # names on disk: "_" for every space ("Soft Round" -> Soft_Round.png)
def from_file(s): return str(s).replace("_", " ")                          # and back: the title written on the tile

def custom_rel(name, section):
    """custom/<Section_Name>/<Brush_Name>.png (the older spelling with spaces still works) if that file is there"""
    if not section: return None
    for sec, nm in ((file_name(section), file_name(name)), (section, name)):
        rel = f"{CUSTOM}/{sec}/{nm}"
        if os.path.exists(path(rel)): return rel
    return None

def tile_rel(name, section=None):
    """custom/<section>/<name>.png first (every brush has one); if it's missing, the old table above"""
    rel = custom_rel(name, section)
    if rel: return rel
    rel = TILES.get(f"{section}:{name}") if section else None
    return rel or TILES.get(name)

_named = {}; _pillbox = {}; _fonts = {}
def _font(size):
    if size not in _fonts:
        from PIL import ImageFont
        f = None
        for n in ("arialbd.ttf", "DejaVuSans-Bold.ttf"):
            try: f = ImageFont.truetype(n, size); break
            except Exception: pass
        _fonts[size] = f or ImageFont.load_default()
    return _fonts[size]

def _pill(im):
    """where the blue name pill is on a picture (found once per picture)"""
    k = id(im)
    if k not in _pillbox:
        import numpy as np
        from scipy import ndimage as ndi
        a = np.asarray(im); pill = (a[..., 2] > 170) & (a[..., 0] < 90) & (a[..., 1] < 120) & (a[..., 3] > 200)
        pill[int(a.shape[0] * 0.3):] = False                                   # the pill is along the top (blue paint lower down isn't it)
        lab, n = ndi.label(pill)
        if not n: _pillbox[k] = None
        else:
            sl = ndi.find_objects(lab)[int(np.argmax(ndi.sum(pill, lab, range(1, n + 1))))]
            _pillbox[k] = (sl[1].start, sl[0].start, sl[1].stop, sl[0].stop)
    return _pillbox[k]

_tbox = []
def _template_pill(im):
    """the pill's place on the template, scaled to this picture (every custom tile is made from the template)"""
    if not _tbox:
        t = load(f"{CUSTOM}/_template"); b = _pill(t) if t is not None else None; _tbox.append((b, t.size if t is not None else None))
    b, ts = _tbox[0]
    if b is None: return None
    kx, ky = im.width / ts[0], im.height / ts[1]; return (b[0] * kx, b[1] * ky, b[2] * kx, b[3] * ky)

def _with_name(im, name):
    """the tile with its name written on the blue pill (only on screen; the file isn't changed). Every custom tile gets this, so
    the name always comes from the file name"""
    from PIL import ImageDraw
    box = _pill(im) or _template_pill(im)                                      # the tile's own pill first (painted tiles differ a little)
    if box is None: return im
    x0, y0, x1, y1 = box; out = im.copy(); d = ImageDraw.Draw(out); size = int((y1 - y0) * 0.75)
    while size > 7 and d.textlength(name, font=_font(size)) > (x1 - x0) * 0.9: size -= 1
    d.text(((x0 + x1) / 2, (y0 + y1) / 2), name, fill="white", font=_font(size), anchor="mm", stroke_width=1, stroke_fill=(10, 30, 120)); return out

def tile_image(name, section=None):
    """the picture to show for a brush tile: its custom file (a blank one with the name written on), or None"""
    rel = tile_rel(name, section); im = load(rel)
    if im is None: return None
    if rel.startswith(CUSTOM + "/"):                                            # every custom tile writes its own name (from its file name)
        name = from_file(rel.rsplit("/", 1)[-1]); key = (rel, name)
        if key not in _named: _named[key] = _with_name(im, name)
        return _named[key]
    return im

def tile(name, w=None, section=None):
    im = tile_image(name, section)
    if im is None or w is None: return im
    return im.resize((w, max(1, round(im.height * w / im.width))), Image.LANCZOS)

def tile_title(name, section=None):
    """the words painted on the tile ("" when the tile has no real name on it)"""
    rel = tile_rel(name, section) or ""
    if rel.startswith(CUSTOM + "/"): return name
    if not rel.startswith(_TITLED): return ""
    return rel.split("/")[-1].replace("_", " ").title()

def says_its_name(name, section=None):
    """True when the tile's painted name already reads as the catalog name (then no extra label is needed under it)"""
    t = _key(tile_title(name, section)); n = _key(name)
    return bool(t) and (n in t or t in n)

def preview(name, section):
    """the painted preview strip for a catalog item (None if there isn't one)"""
    return load(PREVIEWS.get(f"{section}:{name}"))

def stamp(name, size, section="Stamps & Icons"):
    """a stamp picture centred in a size x size square: custom/<section>/<name>.png first, else the table above"""
    im = load(custom_rel(name, section) or STAMPS.get(name))
    if im is None: return None
    key = ("stamp", name, size)
    if key not in _sized:
        s = im.copy(); s.thumbnail((size, size), Image.LANCZOS); sq = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        sq.alpha_composite(s, ((size - s.width) // 2, (size - s.height) // 2)); _sized[key] = sq
    return _sized[key]

def missing():
    """names in the tables whose picture file isn't there (for a quick check)"""
    out = []
    for table in (TOOLBAR, TILES, PREVIEWS, STAMPS):
        out += [f"{k} -> {v}" for k, v in table.items() if not os.path.exists(path(v))]
    return out
