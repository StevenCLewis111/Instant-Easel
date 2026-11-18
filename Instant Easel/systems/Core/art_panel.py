"""
art_panel.py: the painted pieces of the Draw studio's Layers / Color panel (images/UI/Color Wheel Menu, Sliders, Scroll Bars, Side Panel Bars), built at any size.

Everything is made from the cut pieces: bars are stretched in the middle only (their rounded ends keep their shape), swatches are the
painted swatch recoloured to any colour (its gloss and frame kept), the slider is the dark track + cyan fill + knob, and the colour
ring is the painted ring. Pictures are cached by size, so a zoom or a redraw only makes what's new.
"""
import colorsys, math, os, sys
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageEnhance
import theme as T, ui_art as UA, skin

_ph = {}; _pil = {}

def ok(): return UA.load("panel/layer_add") is not None and UA.load("panel/wheel_ring") is not None
def src(name): return UA.load("panel/" + name)

def photo(key, make):
    """a cached PhotoImage (make() builds the PIL picture the first time)"""
    if key not in _ph:
        if len(_ph) > 900: _ph.clear()
        _ph[key] = ImageTk.PhotoImage(make())
    return _ph[key]

def fit(name, W, H):
    """a piece scaled to fit W x H, centred on a see-through box of exactly that size"""
    key = ("fit", name, W, H)
    if key not in _pil:
        im = src(name).copy(); im.thumbnail((W, H), Image.LANCZOS); box = Image.new("RGBA", (W, H))
        box.alpha_composite(im, ((W - im.width) // 2, (H - im.height) // 2)); _pil[key] = box
    return _pil[key]

def bar(name, W, H, cap_l=0.42, cap_r=None):
    """a bar at W x H: scaled to height H, its ends (cap_l / cap_r x the height) kept, the middle stretched"""
    key = ("bar", name, W, H, cap_l, cap_r)
    if key not in _pil:
        im = src(name); b = im.resize((max(1, round(im.width * H / im.height)), H), Image.LANCZOS)
        cl = max(2, round(H * cap_l)); cr = max(2, round(H * (cap_r if cap_r is not None else cap_l)))
        if W <= cl + cr + 2 or b.width <= cl + cr + 2: out = b.resize((W, H), Image.LANCZOS)
        else:
            out = Image.new("RGBA", (W, H)); out.paste(b.crop((0, 0, cl, H)), (0, 0))
            out.paste(b.crop((cl, 0, b.width - cr, H)).resize((W - cl - cr, H), Image.LANCZOS), (cl, 0))
            out.paste(b.crop((b.width - cr, 0, b.width, H)), (W - cr, 0))
        _pil[key] = out
    return _pil[key]

def vbar(name, W, H, cap=0.6):
    """a tall bar at W x H: scaled to width W, its top and bottom ends (cap x the width) kept, the middle stretched"""
    key = ("vbar", name, W, H, cap)
    if key not in _pil:
        im = src(name); b = im.resize((W, max(1, round(im.height * W / im.width))), Image.LANCZOS); c = max(2, round(W * cap))
        if H <= 2 * c + 2 or b.height <= 2 * c + 2: out = b.resize((W, H), Image.LANCZOS)
        else:
            out = Image.new("RGBA", (W, H)); out.paste(b.crop((0, 0, W, c)), (0, 0))
            out.paste(b.crop((0, c, W, b.height - c)).resize((W, H - 2 * c), Image.LANCZOS), (0, c)); out.paste(b.crop((0, b.height - c, W, b.height)), (0, H - c))
        _pil[key] = out
    return _pil[key]

def text(im, s, x, y, px, fill=(245, 245, 250), anchor="mm", edge=True):
    """write s on im (white with a dark edge, the panel's look)"""
    d = ImageDraw.Draw(im); f = skin._pil_font(max(6, px))
    d.text((x, y), s, font=f, anchor=anchor, fill=fill, stroke_width=max(1, round(px / 9)) if edge else 0, stroke_fill=(5, 10, 35))
    return im

def shade(im, k):
    """brighter (k > 1) or darker copy, see-through kept"""
    a = im.getchannel("A"); rgb = ImageEnhance.Brightness(im.convert("RGB")).enhance(k).convert("RGBA"); rgb.putalpha(a); return rgb

# ---------------------------------------------------------------- swatches: the painted swatch in any colour
_sw = {}
def _swatch_parts():
    """the painted swatch split once into: the colour area (with its light and shade) and the rest (frame, edge)"""
    if "parts" not in _sw:
        im = src("swatch"); a = np.asarray(im).astype(np.float32) / 255; rgb = a[..., :3]
        hsv = np.asarray(im.convert("RGB").convert("HSV")).astype(np.float32) / 255
        red = (rgb[..., 0] > 0.45) & (rgb[..., 1] < 0.55) & (rgb[..., 2] < 0.55) & (a[..., 3] > 0.5)
        from scipy import ndimage as ndi
        area = ndi.binary_fill_holes(ndi.binary_closing(red, iterations=2))           # the colour area, its gloss included
        light = hsv[..., 2] / max(1e-3, np.median(hsv[..., 2][red]))                   # how much lighter / darker each pixel is
        gloss = np.clip((1 - hsv[..., 1]) * area * (hsv[..., 2] > 0.8), 0, 1)          # the white shine
        _sw["parts"] = (np.asarray(im).copy(), area, light, gloss)
    return _sw["parts"]

def swatch(rgb, W, H):
    key = ("sw", tuple(rgb), W, H)
    if key not in _pil:
        base, area, light, gloss = _swatch_parts(); c = np.array(rgb, np.float32)
        col = np.clip(c[None, None, :] * light[..., None], 0, 255); col = col * (1 - gloss[..., None]) + 255 * gloss[..., None] * 0.9 + col * gloss[..., None] * 0.1
        out = base.copy(); out[..., :3] = np.where(area[..., None], col, out[..., :3]).astype(np.uint8)
        _pil[key] = Image.fromarray(out).resize((W, H), Image.LANCZOS)
    return _pil[key]

# ---------------------------------------------------------------- the colour ring: geometry and hue read from the painted ring
_ring = {}
def ring_info():
    """(outer radius, inner radius) as a share of the ring picture's half-size, and a hue for every degree round it"""
    if "info" not in _ring:
        im = src("wheel_ring"); a = np.asarray(im); al = a[..., 3] > 128; h, w = al.shape; cy, cx = h / 2, w / 2
        ys, xs = np.nonzero(al); R = max(xs.max() - cx, cx - xs.min(), ys.max() - cy, cy - ys.min())
        r = 0
        while r < R and not al[int(cy), int(cx + r)]: r += 1                               # the hole's edge (the inner black line)
        # the colour band: from the hole's edge to the outside, sample its middle all the way round
        hues = []
        rgb = a[..., :3].astype(np.float32) / 255
        for deg in range(360):
            t = math.radians(deg); best = None
            for f in np.linspace(0.25, 0.75, 9):
                rr = r + (R - r) * f; x, y = int(cx + rr * math.cos(t)), int(cy + rr * math.sin(t))
                hh, ss, vv = colorsys.rgb_to_hsv(*rgb[y, x])
                if best is None or ss * vv > best[1]: best = (hh, ss * vv)
            hues.append(best[0])
        _ring["info"] = (1.0, r / R, hues)
    return _ring["info"]

def hue_at(deg):
    return ring_info()[2][int(round(deg)) % 360]

def deg_for(hue):
    """the angle round the painted ring whose colour is closest to this hue"""
    hues = ring_info()[2]; d = [min(abs(h - hue), 1 - abs(h - hue)) for h in hues]; return int(np.argmin(d))

def wheel(S, hue):
    """the painted ring at S x S with the saturation / brightness square for this hue inside it (framed in black)"""
    key = ("wheel", S, round(hue, 3))
    if key not in _pil:
        out = Image.new("RGBA", (S, S)); out.alpha_composite(src("wheel_ring").resize((S, S), Image.LANCZOS))
        _, rin, _ = ring_info(); half = int(S / 2 * rin * 0.66); c = S // 2; n = 2 * half
        yy, xx = np.mgrid[0:n, 0:n]; sx = xx / max(1, n - 1); sy = 1 - yy / max(1, n - 1)
        hcol = np.array(colorsys.hsv_to_rgb(hue, 1, 1)); sq = (sy[..., None] * ((1 - sx[..., None]) + sx[..., None] * hcol)) * 255
        sqi = Image.fromarray(np.dstack([sq.astype(np.uint8), np.full((n, n), 255, np.uint8)]))
        frame = max(2, S // 70); d = ImageDraw.Draw(out)
        d.rounded_rectangle([c - half - frame, c - half - frame, c + half + frame - 1, c + half + frame - 1], radius=frame * 2, fill=(0, 0, 0, 255))
        out.alpha_composite(sqi, (c - half, c - half)); _pil[key] = out
    return _pil[key]

def square_half(S): return int(S / 2 * ring_info()[1] * 0.66)

# ---------------------------------------------------------------- the painted slider (same use as T.PlainSlider)
def slider_image(W, H, v, K=None):
    """the painted slider at W x H: dark track, cyan fill up to the knob, the round knob (K across) at value v (0..1)"""
    K = K or H; v = round(v, 3); key = ("sl", W, H, v, K)
    if key not in _pil:
        out = Image.new("RGBA", (W, H)); th = max(6, int(K * 0.46)); ty = (H - th) // 2
        out.alpha_composite(bar("slider_track", W, th, 0.5), (0, ty)); fw = int(K / 2 + v * (W - K)) + K // 3
        if fw > th: out.alpha_composite(bar("slider_fill", min(W, fw), th + 2, 0.55), (0, ty - 1))
        out.alpha_composite(fit("slider_knob", K, K), (int(v * (W - K)), (H - K) // 2))
        if len(_pil) > 1500: _pil.clear()
        _pil[key] = out
    return _pil[key]

def scrollbar_image(a, total, pos, size, hot, active, vertical=True):
    """the painted scroll bar: arrow button at each end, the dark track between, the glossy thumb (pos, size along the track)"""
    key = ("sb", a, total, int(pos), int(size), hot, active, vertical)
    if key in _pil: return _pil[key]
    out = Image.new("RGBA", (a, total)); up, dn = src("scroll_up"), src("scroll_down"); bh = max(4, round(up.height * a / up.width))
    tw = max(4, round(a * 0.6)); tx = (a - tw) // 2; t0, t1 = max(0, bh - 3), max(bh, total - bh + 3)
    if t1 - t0 > 6: out.alpha_composite(vbar("scroll_track", tw, t1 - t0, 0.5), (tx, t0))
    if size > 4:
        th_w = max(3, round(tw * 0.74)); th = vbar("scroll_thumb", th_w, max(6, int(size)), 0.5)
        out.alpha_composite(shade(th, 1.18) if active else th, ((a - th_w) // 2, int(a + pos)))
    for end, im in ((0, up), (1, dn)):
        b = im.resize((a, bh), Image.LANCZOS); b = shade(b, 1.2) if hot == end else b
        out.alpha_composite(b, (0, 0 if end == 0 else total - bh))
    if not vertical: out = out.rotate(90, expand=True)
    if len(_pil) > 1500: _pil.clear()
    _pil[key] = out; return out

class ArtSlider(tk.Label):
    """dark track, cyan fill up to the knob, white knob. .value (0..1), ._draw(), command(value) while dragging"""
    def __init__(self, master, value=1.0, command=None, width=120, height=24):
        super().__init__(master, bd=0, highlightthickness=0, padx=0, pady=0, cursor="hand2", bg=master["bg"])
        self.value = value; self.command = command; self.dw, self.dh = width, height
        self.bind("<Button-1>", self._drag); self.bind("<B1-Motion>", self._drag); T.on_change(self._draw, zoom=True); self._draw()
    def size(self, w=None, h=None):
        if w: self.dw = w
        if h: self.dh = h
        self._draw()
    def _px(self): return max(30, int(round(self.dw * T.Z))), max(10, int(round(self.dh * T.Z)))
    def _drag(self, e):
        W, H = self._px(); k = H; self.value = min(1, max(0, (e.x - k / 2) / max(1, W - k))); self._draw()
        if self.command: self.command(self.value)
    def _draw(self):
        W, H = self._px(); v = round(self.value, 3)
        try: self.configure(image=photo(("slider", W, H, v), lambda: slider_image(W, H, v)), bg=self.master["bg"])
        except tk.TclError: pass

class ValueBox(tk.Label):
    """the green value box with a typing field inside it (the field's text variable is .var, the field is .entry)"""
    def __init__(self, master, var, width=60, height=26, chars=5):
        super().__init__(master, bd=0, highlightthickness=0, padx=0, pady=0, bg=master["bg"])
        self.var = var; self.dw, self.dh = width, height
        self.entry = tk.Entry(self, textvariable=var, width=chars, bd=0, relief="flat", highlightthickness=0, justify="center",
                              fg="white", insertbackground="white", bg="#06101f", font=T.f(9))
        self.entry.place(relx=0.5, rely=0.5, anchor="center"); T.on_change(self._draw, zoom=True); self._draw()
    def _draw(self):
        W, H = max(20, int(round(self.dw * T.Z))), max(12, int(round(self.dh * T.Z)))
        try:
            self.configure(image=photo(("box", W, H), lambda: bar("box_value", W, H, 0.35)), width=W, height=H, bg=self.master["bg"])
            self.entry.configure(bg=self._inside(W, H))
        except tk.TclError: pass
    def _inside(self, W, H):
        im = bar("box_value", W, H, 0.35); r, g, b, a = im.getpixel((W // 2, H // 2)); return "#%02x%02x%02x" % (r, g, b)
