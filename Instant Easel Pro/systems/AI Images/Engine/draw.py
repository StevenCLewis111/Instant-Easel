"""Silhouette illustration kit for the trilogy (matches the cover style)."""
import math, random
from PIL import Image, ImageDraw, ImageFilter, ImageFont
W, H = 1800, 2700
import os as _os
import paths as _paths; _FD = _paths.FONTS
if not _os.path.isdir(_FD): _FD = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "fonts")
FONT = _os.path.join(_FD, "EBGaramond-Italic.ttf")
INK = (6, 8, 14)


def chaikin(pts, n=3, closed=True):
    """corner-cutting: turns a jagged polygon into a smooth organic outline"""
    for _ in range(n):
        new = []; L = len(pts); rng_ = range(L) if closed else range(L - 1)
        for i in rng_:
            (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % L]
            new += [(0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1), (0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1)]
        if not closed: new = [pts[0]] + new + [pts[-1]]
        pts = new
    return pts

def canvas(top=(7,11,22), bottom=(42,49,80)):
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bottom[i]-top[i]) * t) for i in range(3)))
    return im

def stars(im, n=500, seed=1, ymax=0.7):
    r = random.Random(seed); d = ImageDraw.Draw(im)
    for _ in range(n):
        x, y = r.randrange(W), r.randrange(int(H*ymax)); s = r.choice([1,1,1,2,2,3]); b = r.randrange(140,255)
        d.ellipse([x, y, x+s, y+s], fill=(b, b, min(255, b+15)))

def glow(im, x, y, r, color=(120,170,255), strength=0.9):
    g = Image.new("RGB", (W, H), (0,0,0)); d = ImageDraw.Draw(g)
    for i in range(12, 0, -1):
        rr = r*i/12; c = tuple(int(v*strength*(1-i/13)) for v in color)
        d.ellipse([x-rr, y-rr, x+rr, y+rr], fill=c)
    g = g.filter(ImageFilter.GaussianBlur(r/5))
    return Image.fromarray(__import__("numpy").clip(__import__("numpy").asarray(im, dtype="int16")+__import__("numpy").asarray(g, dtype="int16"),0,255).astype("uint8"))

def disc(im, x, y, r, fill, outline=None):
    ImageDraw.Draw(im).ellipse([x-r, y-r, x+r, y+r], fill=fill, outline=outline)

def moon(im, x, y, r, seed=3, col=(205,208,215)):
    disc(im, x, y, r, col); rr = random.Random(seed); d = ImageDraw.Draw(im)
    for _ in range(14):
        a, dd, cr = rr.random()*6.28, rr.random()*r*0.75, rr.randrange(int(r*0.05)+2, int(r*0.16)+3)
        cx, cy = x+math.cos(a)*dd, y+math.sin(a)*dd
        d.ellipse([cx-cr, cy-cr, cx+cr, cy+cr], fill=tuple(c-28 for c in col))

def planet(im, x, y, r, seed=8):
    import numpy as np
    im2 = glow(im, x, y, r*1.3, (60,120,230), 0.6)
    layer = Image.new("RGBA", (W, H), (0,0,0,0)); d = ImageDraw.Draw(layer); rr = random.Random(seed)
    d.ellipse([x-r, y-r, x+r, y+r], fill=(28,78,150,255))
    for _ in range(5):   # continents
        cx, cy, s = x + rr.uniform(-0.6,0.6)*r, y + rr.uniform(-0.6,0.6)*r, rr.uniform(0.15,0.35)*r
        d.ellipse([cx-s*1.4, cy-s, cx+s*1.4, cy+s], fill=(66,104,72,255))
    land = layer.filter(ImageFilter.GaussianBlur(r*0.03))
    cl = Image.new("RGBA", (W, H), (0,0,0,0)); dc = ImageDraw.Draw(cl)
    for _ in range(18):  # soft clouds
        cx, cy = x + rr.uniform(-0.8,0.8)*r, y + rr.uniform(-0.8,0.8)*r
        dc.ellipse([cx-r*0.35, cy-r*0.06, cx+r*0.35, cy+r*0.06], fill=(240,245,250,150))
    cl = cl.filter(ImageFilter.GaussianBlur(r*0.04))
    mask = Image.new("L", (W, H), 0); ImageDraw.Draw(mask).ellipse([x-r, y-r, x+r, y+r], fill=255)
    land.alpha_composite(cl); comp = Image.new("RGBA", (W, H), (0,0,0,0)); comp.paste(land, (0,0), mask)
    shade = Image.new("RGBA", (W, H), (0,0,0,0)); ds = ImageDraw.Draw(shade); ds.ellipse([x-r*0.7, y-r*1.05, x+r*1.5, y+r*1.0], fill=(0,0,0,0))
    out = im2.convert("RGBA"); out.alpha_composite(comp)
    term = Image.new("RGBA", (W, H), (0,0,0,0)); dt = ImageDraw.Draw(term); dt.ellipse([x-r*0.2, y-r*1.2, x+r*1.8, y+r*1.2], fill=(0,0,0,150))
    term = term.filter(ImageFilter.GaussianBlur(r*0.15)); tm = Image.new("RGBA", (W, H), (0,0,0,0)); tm.paste(term, (0,0), mask); out.alpha_composite(tm)
    return out.convert("RGB")

def mountains(im, base, amp, seed, col, jag=14):
    r = random.Random(seed); d = ImageDraw.Draw(im); pts = [(0, H)]; n = jag
    for i in range(n+1):
        x = W*i/n; y = base - r.random()*amp - (amp*0.6 if i in (n//2, n//2+1) else 0)
        pts.append((x, y))
    ridge = pts[1:]; fine = []
    for (x0, y0), (x1, y1) in zip(ridge, ridge[1:]):
        for k in range(4):
            tt = k / 4; fine.append((x0 + (x1 - x0) * tt, y0 + (y1 - y0) * tt + r.uniform(-amp * 0.04, amp * 0.04)))
    fine.append(ridge[-1]); d.polygon([(0, H)] + chaikin(fine, 3, closed=False) + [(W, H)], fill=col)

def peak(im, x, base, w, h, col=INK):
    pts = [(x-w/2, base), (x-w*0.28, base-h*0.45), (x-w*0.08, base-h*0.9), (x, base-h), (x+w*0.1, base-h*0.88), (x+w*0.3, base-h*0.42), (x+w/2, base)]
    ImageDraw.Draw(im).polygon(chaikin(pts, 3, closed=False), fill=col)

def ground(im, y, col=INK): ImageDraw.Draw(im).rectangle([0, y, W, H], fill=col)

def sea(im, y, col=(14,24,44), seed=5, glint=None):
    d = ImageDraw.Draw(im); d.rectangle([0, y, W, H], fill=col); r = random.Random(seed)
    for _ in range(120):
        yy = r.randrange(int(y)+10, H); xx = r.randrange(W); L = r.randrange(30, 140)
        c = glint or tuple(min(255, v+30) for v in col)
        d.line([(xx, yy), (xx+L, yy)], fill=c, width=2)

def person(im, x, base, h, pose="stand", col=INK, facing=1):
    d = ImageDraw.Draw(im); f = facing; u = h / 100.0
    def P(pts): return [(x + f * px * u, base - py * u) for px, py in pts]
    if pose == "sit_back":   # seated cross-legged, seen from behind: rounded back, sloping shoulders, wide lap
        body = [(-30, 0), (-28, 8), (-20, 13), (-17, 26), (-17, 42), (-19, 54), (-18, 60), (-12, 64), (-5, 66), (-4, 70), (4, 70), (5, 66), (12, 64),
                (18, 60), (19, 54), (17, 42), (17, 26), (20, 13), (28, 8), (30, 0)]       # broad sloping shoulders, a neck
        head = (0, 80, 10.0)
    elif pose == "sit":
        body = [(-9, 0), (-10, 22), (-12, 46), (-11, 60), (-7, 66), (-3, 68), (3, 68), (8, 66), (11, 60), (12, 46), (11, 30),
                (14, 24), (30, 22), (34, 16), (34, 0), (26, 0), (25, 12), (12, 12), (6, 0)]
        head = (0, 78, 8.5)
    elif pose == "kneel":
        body = [(-10, 0), (-11, 30), (-12, 52), (-10, 66), (-6, 72), (6, 72), (10, 66), (12, 52), (11, 34), (26, 30), (28, 0), (14, 0), (14, 18), (2, 18), (2, 0)]
        head = (0, 82, 8.5)
    elif pose == "arms":
        body = [(-7, 0), (-6, 24), (-4, 44), (-7, 46), (-9, 60), (-13, 72), (-24, 92), (-21, 95), (-10, 80), (-7, 86), (-3, 89), (3, 89), (7, 86), (10, 80),
                (21, 95), (24, 92), (13, 72), (9, 60), (7, 46), (4, 44), (6, 24), (7, 0), (2, 0), (1, 30), (-1, 30), (-2, 0)]
        head = (0, 96, 7.5)
    elif pose == "reach":
        body = [(-7, 0), (-6, 24), (-4, 44), (-8, 46), (-11, 62), (-11, 76), (-7, 86), (-3, 89), (3, 89), (8, 86), (14, 80), (36, 82), (37, 78), (14, 72),
                (11, 62), (7, 46), (4, 44), (6, 24), (7, 0), (2, 0), (1, 30), (-1, 30), (-2, 0)]
        head = (0, 96, 7.5)
    elif pose == "coat":
        body = [(-14, 0), (-12, 30), (-11, 56), (-12, 72), (-9, 82), (-4, 88), (4, 88), (9, 82), (12, 72), (11, 56), (12, 30), (14, 0)]
        head = (0, 96, 7.5)
    else:  # stand
        body = [(-7, 0), (-6, 22), (-5, 44), (-8, 46), (-11, 60), (-11, 76), (-7, 86), (-3, 89), (3, 89), (7, 86), (11, 76), (11, 60), (8, 46),
                (5, 44), (6, 22), (7, 0), (2, 0), (1, 30), (-1, 30), (-2, 0)]
        head = (0, 96, 7.5)
    d.polygon(chaikin(P(body), 3), fill=col)
    hx, hy, hr = head; cx, cy, r = x + f * hx * u, base - hy * u, hr * u
    d.ellipse([cx - r, cy - r * 1.12, cx + r, cy + r * 1.05], fill=col)

def crowd(im, x0, x1, base, h, n, seed=2, col=INK):
    r = random.Random(seed)
    for _ in range(n): person(im, r.uniform(x0, x1), base + r.uniform(-h*0.05, h*0.05), h*r.uniform(0.85, 1.1), col=col)

def lights_rising(im, n=260, seed=4, y0=0.95, y1=0.05, col=(255,228,170)):
    r = random.Random(seed)
    for _ in range(n):
        x = r.randrange(W); y = int(H*(y1 + (y0-y1)*r.random())); s = r.randrange(3, 9)
        im = glow(im, x, y, s*4, col, 0.55) if r.random() < 0.08 else im
        disc(im, x, y, s, col)
    return im

def ring(im, x, y, r, col=(150,190,255), width=26, lit=True):
    if lit: im = glow(im, x, y, r*1.25, col, 0.55)
    d = ImageDraw.Draw(im); d.ellipse([x-r, y-r, x+r, y+r], outline=(30,36,52), width=width)
    if lit: d.ellipse([x-r+width, y-r+width, x+r-width, y+r-width], outline=col, width=6)
    return im

def two_circles(im, x, y, r, col=(230,215,170), width=6):
    d = ImageDraw.Draw(im)
    d.ellipse([x-r*1.6, y-r, x+r*0.4, y+r], outline=col, width=width); d.ellipse([x-r*0.4, y-r, x+r*1.6, y+r], outline=col, width=width)
    d.line([(x-r*0.6, y), (x+r*0.6, y)], fill=col, width=width)

def door(im, x, base, w, h, glowc=(240,225,180), carved=True):
    im = glow(im, x, base-h*0.5, w*0.9, glowc, 0.5); d = ImageDraw.Draw(im)
    d.rectangle([x-w*0.75, base-h*1.15, x+w*0.75, base], fill=(20,22,30))
    d.rounded_rectangle([x-w/2, base-h, x+w/2, base], radius=int(w/2), fill=(200,190,160))
    if carved: two_circles(im, x, base-h-h*0.07, w*0.12, (230,215,170))
    return im

def dome_city(im, base, seed=7, col=INK, lights=0, dome_x=None):
    r = random.Random(seed); d = ImageDraw.Draw(im); x = 0
    while x < W:
        w = r.randrange(60, 170); h = r.randrange(140, 520)
        d.rectangle([x, base-h, x+w, base], fill=col)
        if r.random() < 0.3: d.polygon([(x, base-h), (x+w/2, base-h-r.randrange(40,140)), (x+w, base-h)], fill=col)
        for _ in range(lights if r.random() < 0.6 else 0):
            lx, ly = r.randrange(x+8, x+w-8), r.randrange(base-h+20, base-10)
            d.rectangle([lx, ly, lx+8, ly+12], fill=(255,214,140))
        x += w + r.randrange(0, 30)
    dx = dome_x or W*0.5
    d.pieslice([dx-330, base-640, dx+330, base+20], 180, 360, fill=col)
    d.rectangle([0, base, W, H], fill=col)

def ship(im, x, y, L, col=(26,30,42), lit=(150,200,255)):
    d = ImageDraw.Draw(im)
    d.polygon([(x-L/2, y), (x-L*0.25, y-L*0.09), (x+L*0.38, y-L*0.06), (x+L/2, y), (x+L*0.38, y+L*0.06), (x-L*0.25, y+L*0.09)], fill=col)
    for k in range(6): d.ellipse([x-L*0.2+k*L*0.09, y-4, x-L*0.2+k*L*0.09+8, y+4], fill=lit)
    return glow(im, x-L/2-20, y, L*0.15, (110,170,255), 0.7)

def well_merge(im):
    im = glow(im, W*0.3, H*0.35, 420, (90,110,200), 0.6); im = glow(im, W*0.7, H*0.42, 420, (140,90,200), 0.6)
    d = ImageDraw.Draw(im)
    for k in range(9):
        d.ellipse([W*0.3-80-k*40, H*0.35-80-k*40, W*0.3+80+k*40, H*0.35+80+k*40], outline=(60,70,120), width=2)
        d.ellipse([W*0.7-80-k*40, H*0.42-80-k*40, W*0.7+80+k*40, H*0.42+80+k*40], outline=(90,60,120), width=2)
    return im

def sphere(im, x, y, r, glowc=(170,200,255), opened=False):
    im = glow(im, x, y, r*1.6, glowc, 0.8 if opened else 0.35)
    disc(im, x, y, r, (12,14,24) if not opened else (235,240,255))
    if not opened: ImageDraw.Draw(im).arc([x-r*0.8, y-r*0.8, x+r*0.5, y+r*0.5], 200, 260, fill=(90,110,150), width=8)
    return im

def pyramid(im, x, base, w, col=INK):
    ImageDraw.Draw(im).polygon([(x-w/2, base), (x, base-w*0.62), (x+w/2, base)], fill=col)

def temple(im, x, base, w, col=INK, steps=7):
    d = ImageDraw.Draw(im)
    for i in range(steps):
        ww = w*(1-i/(steps+1.5)); hh = w*0.07
        d.rectangle([x-ww/2, base-hh*(i+1), x+ww/2, base-hh*i], fill=col)

def tower(im, x, base, w, h, col=INK, window=None):
    d = ImageDraw.Draw(im); d.rectangle([x-w/2, base-h, x+w/2, base], fill=col)
    d.polygon([(x-w/2, base-h), (x, base-h-w*0.6), (x+w/2, base-h)], fill=col)
    if window:
        im = glow(im, x, base-h+window, 90, (255,200,120), 0.9)
        ImageDraw.Draw(im).rectangle([x-14, base-h+window-20, x+14, base-h+window+20], fill=(255,214,150))
    return im

def rain(im, n=900, seed=9, col=(120,130,160)):
    r = random.Random(seed); d = ImageDraw.Draw(im)
    for _ in range(n):
        x, y = r.randrange(W), r.randrange(H); d.line([(x, y), (x-12, y+60)], fill=col, width=2)

def cradles(im, base, rows=4, col=(70,90,120)):
    d = ImageDraw.Draw(im)
    for row in range(rows):
        y = base - row*140; s = 1 - row*0.15
        for i in range(9):
            x = 120 + i*(W-240)/8; w = 150*s
            d.rounded_rectangle([x-w/2, y-40*s, x+w/2, y], radius=20, fill=col, outline=(130,160,200))

def caption(im, text, y=None):
    d = ImageDraw.Draw(im); f = ImageFont.truetype(FONT, 58)
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=f) > W*0.8: lines.append(cur); cur = w_
        else: cur = t
    lines.append(cur); yy = y or H - 140 - 70*len(lines)
    pad = Image.new("RGBA", (W, 70*len(lines)+80), (0,0,0,150)); im.paste(Image.new("RGB", pad.size, (0,0,0)), (0, yy-40), pad)
    d = ImageDraw.Draw(im)
    for i, ln in enumerate(lines):
        d.text(((W - d.textlength(ln, font=f))/2, yy + i*70), ln, font=f, fill=(238,228,205))
    return im

def seated_person(mask, x, base, h, hair="short", facing=1, seed=0):
    """Seated cross-legged, seen from behind (proportions from the reference silhouettes):
    widest at the crossed knees, tapering torso, sloped shoulders, a neck, arms hanging with a gap of light, varied hair.
    Draws white on a black mask; gaps are carved back out in black."""
    import random as _r
    rnd = _r.Random(seed); d = ImageDraw.Draw(mask); u = h / 100.0; f = facing
    P = lambda pts: [(x + f * px * u, base - py * u) for px, py in pts]
    lap = [(-37, 0), (-38, 7), (-33, 14), (-24, 18), (24, 18), (33, 14), (38, 7), (37, 0)]
    d.polygon(chaikin(P(lap), 3), fill=255)                                          # compact crossed legs
    torso = [(-24, 10), (-25, 28), (-26, 42), (-27, 52), (-25, 58), (-18, 62), (-8, 64), (8, 64), (18, 62), (25, 58), (27, 52), (26, 42), (25, 28), (24, 10)]
    d.polygon(chaikin(P(torso), 3), fill=255)                                        # broad, short, rounded shoulders
    for s in (-1, 1):                                                                 # arms hug the body
        arm = [(s * 24, 58), (s * 29, 52), (s * 31, 40), (s * 31, 26), (s * 32, 14), (s * 26, 12), (s * 25, 26), (s * 25, 40)]
        d.polygon(chaikin(P(arm), 2), fill=255)
    d.polygon(chaikin(P([(-6, 62), (-5.5, 67), (5.5, 67), (6, 62)]), 2), fill=255)  # short neck
    hx, hy, r = x, base - 77 * u, 12.5 * u
    d.ellipse([hx - r, hy - r * 1.12, hx + r, hy + r * 1.0], fill=255)                # a real-sized head
    if hair == "long":
        d.polygon(chaikin(P([(-11, 84), (-12, 72), (-10, 60), (-4, 58), (4, 58), (10, 60), (12, 72), (11, 84)]), 3), fill=255)
    elif hair == "curly":
        for k in range(11):
            a = -math.pi * 0.95 + k * math.pi * 0.9 / 10; rr = r * rnd.uniform(0.32, 0.45)
            cx_, cy_ = hx + math.cos(a) * r * 1.02, hy + math.sin(a) * r * 1.05; d.ellipse([cx_ - rr, cy_ - rr, cx_ + rr, cy_ + rr], fill=255)
    elif hair == "tied":
        d.ellipse([hx - r * 0.45, hy - r * 1.55, hx + r * 0.45, hy - r * 0.75], fill=255)
    return mask
