"""
skin.py: painted button and status-dot pictures for Tk widgets (images/UI/Tabs and Menus, Status Dots).

    import skin
    skin.button(widget, "Text to Image", chars=20)   # a T.Button or a tab label wears skin/button.png, same size it had before
    skin.tabs(tabs)                                   # every tab of a T.Tabs row
    skin.dot(master, "green" | "blue" | "grey", 12)   # skin/dot_ring.png filled with the painted ball (a Label)
    skin.file_button(T.Button(row, "Open my Images folder", cmd))   # New / Open / Save buttons wear the painted file-button pictures

The button picture is stretched in the middle only (its rounded ends keep their shape), drawn at the widget's own size for the current
zoom, with the text painted on in white with a dark edge so it reads on every colour of the rainbow. Hover is a little brighter, a tab
that isn't the open one a little darker, a disabled button grey. If the picture files are missing, widgets keep their normal look.
"""
import os, sys
import tkinter as tk, tkinter.font as tkfont
from PIL import Image, ImageTk, ImageDraw, ImageEnhance, ImageFont
import theme as T, ui_art as UA

import paths; HERE = paths.APP                                   # (fonts/)
CAP = 0.36                                        # each rounded end is this share of the picture's height (kept, never stretched)
_src = {}; _ph = {}; _pil_fonts = {}; _tk_fonts = {}

def available(): return UA.load("skin/button") is not None

PIECES = {"rainbow": ("skin/button", CAP), "bar": ("panel/bar_blank", 0.3)}     # the two button looks: rainbow tabs / menus, the HISTORY-style bar

def _base(h, piece="rainbow"):
    """the button picture at height h, made once per height from a smaller working copy"""
    key = (piece, h)
    if key not in _src:
        im = UA.load(PIECES[piece][0]); wk = ("work", piece)
        if wk not in _src: _src[wk] = im.resize((round(im.width * 160 / im.height), 160), Image.LANCZOS)
        w = _src[wk]; _src[key] = w.resize((max(1, round(w.width * h / w.height)), h), Image.LANCZOS)
    return _src[key]

def _stretch(W, H, piece="rainbow"):
    """the button at exactly W x H: both ends as they are, only the middle stretched"""
    b = _base(H, piece); cap = max(2, round(H * PIECES[piece][1]))
    if W <= 2 * cap + 2: return b.resize((W, H), Image.LANCZOS)
    out = Image.new("RGBA", (W, H)); out.paste(b.crop((0, 0, cap, H)), (0, 0))
    out.paste(b.crop((cap, 0, b.width - cap, H)).resize((W - 2 * cap, H), Image.LANCZOS), (cap, 0))
    out.paste(b.crop((b.width - cap, 0, b.width, H)), (W - cap, 0)); return out

def margin(): return max(2, round(3 * T.Z))                       # room round every painted button for its highlight ring

_rings = {}
def ringed(im, on, key=None):
    """the picture with a see-through margin round it; when on, a highlight ring in the theme's border colour that follows the
    button's own shape (rounded where it's rounded) instead of a square box"""
    m = margin(); col = T.PALETTE["border"]; k = (key if key is not None else id(im), im.size, on, col if on else None, m)
    if k in _rings: return _rings[k]
    from PIL import ImageFilter
    out = Image.new("RGBA", (im.width + 2 * m, im.height + 2 * m)); out.alpha_composite(im, (m, m))
    if on:
        a = out.getchannel("A").point(lambda v: 255 if v > 90 else 0)
        outer = a.filter(ImageFilter.MaxFilter(2 * m - 1 if m > 1 else 3)); inner = a.filter(ImageFilter.MaxFilter(max(1, 2 * (m // 3) + 1)))
        import numpy as np
        band = Image.fromarray(np.clip(np.asarray(outer, dtype=np.int16) - np.asarray(inner, dtype=np.int16), 0, 255).astype(np.uint8))
        r, g, b = (int(col[i:i + 2], 16) for i in (1, 3, 5)); ring = Image.new("RGBA", out.size, (r, g, b, 255)); ring.putalpha(band.filter(ImageFilter.GaussianBlur(0.5)))
        under = Image.new("RGBA", out.size); under.alpha_composite(ring); under.alpha_composite(out); out = under
    if len(_rings) > 800: _rings.clear()
    _rings[k] = out; return out

def _pil_font(px):
    if px not in _pil_fonts:
        f = None
        for n in (os.path.join(HERE, "fonts", "CourierPrime-Bold.ttf"), "courbd.ttf", "DejaVuSansMono-Bold.ttf", "arialbd.ttf"):
            try: f = ImageFont.truetype(n, px); break
            except Exception: pass
        _pil_fonts[px] = f or ImageFont.load_default()
    return _pil_fonts[px]

def _tk_font(design):
    """the widget's font at the current zoom (the same rule the zoom uses), for measuring"""
    fam, size = design[0], design[1]; s = max(5, int(round(abs(size) * T.Z))); key = (fam, s)
    if key not in _tk_fonts: _tk_fonts[key] = tkfont.Font(family=fam, size=s, weight="bold")
    return _tk_fonts[key], s

def picture(text, W, H, pt, state="normal", ring=False, piece="rainbow"):
    """the finished button picture (cached): the button, its text, and its ring when it's chosen / under the mouse"""
    key = (text, W, H, pt, state, ring, piece, T.PALETTE["border"] if ring else None, margin())
    if key in _ph: return _ph[key]
    im = _stretch(W, H, piece)
    if state in ("hover", "dim", "disabled"):
        rgb, a = im.convert("RGB"), im.getchannel("A")
        if state == "hover": rgb = ImageEnhance.Brightness(rgb).enhance(1.15)
        elif state == "dim": rgb = ImageEnhance.Brightness(rgb).enhance(0.72)
        else: rgb = ImageEnhance.Brightness(ImageEnhance.Color(rgb).enhance(0.0)).enhance(0.55)
        im = rgb.convert("RGBA"); im.putalpha(a)
    if text:
        d = ImageDraw.Draw(im); px = max(6, round(pt * 4 / 3)); room = W - 2 * round(H * PIECES[piece][1] * 0.55)
        while px > 6 and d.textlength(text, font=_pil_font(px)) > room: px -= 1
        d.text((W / 2, H / 2), text, font=_pil_font(px), anchor="mm", fill=(245, 245, 250) if state != "disabled" else (170, 170, 180),
               stroke_width=max(1, round(H / 15)), stroke_fill=(8, 12, 40))
    im = ringed(im, ring, key=("btn",) + key)
    if len(_ph) > 4000: _ph.clear()
    _ph[key] = ImageTk.PhotoImage(im); return _ph[key]

def select(w, on):
    """mark a button as the chosen one (its ring stays on)"""
    w._sel = bool(on)
    if getattr(w, "_skin", None) is not None: w._style()
    else: w.configure(highlightbackground=T.PALETTE["border"] if on else w.master["bg"])

def _take_over(w, text, chars, taller=0):
    """remember the widget's design pads / font and stop the zoom resetting its pads (the picture includes them now)"""
    rec = w.__dict__.setdefault("_zd", {}).setdefault("opt", {})
    pads = (rec.pop("padx", None), rec.pop("pady", None))
    if pads == (None, None) and getattr(w, "_pads", None): pads = tuple(w._pads)       # painted-words labels keep their design pads here
    if pads[0] is None: pads = (int(w.cget("padx")), pads[1])
    if pads[1] is None: pads = (pads[0], int(w.cget("pady")))
    pads = (pads[0], pads[1] + taller)
    w._skin = dict(text=text, chars=chars, pads=pads, font=rec.get("font") or T.MONO, state="normal", ring=False, piece="rainbow")
    rec.pop("highlightthickness", None)                                         # the ring is part of the picture now (no square box)
    w.tk.call(w._w, "configure", "-padx", 0, "-pady", 0, "-width", 0, "-text", "", "-compound", "center", "-highlightthickness", 0)

def draw(w, state=None, ring=None):
    """(re)draw a skinned widget at the current zoom"""
    sk = getattr(w, "_skin", None)
    if sk is None: return
    if state: sk["state"] = state
    if ring is not None: sk["ring"] = ring
    if sk.get("file"):                                                          # a painted New / Open / Save button
        ph = file_picture(sk["file"], sk["text"], max(12, round(sk["fh"] * T.Z)), sk["state"], sk["ring"])
        if sk.get("ph") is not ph:
            try: w.configure(image=ph); sk["ph"] = ph
            except tk.TclError: pass
        return
    f, pt = _tk_font(sk["font"])
    cw = f.measure("0") * sk["chars"] if sk["chars"] else f.measure(sk["text"])
    px, py = (max(0, round(p * T.Z)) for p in sk["pads"])
    W, H = cw + 2 * px, f.metrics("linespace") + 2 * py
    ph = picture(sk["text"], W, H, pt, sk["state"], sk["ring"], sk["piece"])
    if sk.get("ph") is ph: return                                              # already showing it: no relayout
    under = getattr(w, "_under", None)                                         # sits on a picture (the header): the button with that picture behind it
    try: w.configure(image=under(w, ph) if under else ph); sk["ph"] = ph
    except tk.TclError: pass

def button(w, text=None, chars=None, taller=2, piece="rainbow"):
    """a T.Button wears the picture (piece "rainbow" or "bar"). It keeps its size; the hover / focus / chosen ring is drawn round
    the button's own shape"""
    if not available() or getattr(w, "_skin", None) is not None: return w
    text = text if text is not None else w.cget("text"); chars = chars if chars is not None else (int(w.cget("width")) or None)
    _take_over(w, text, chars, taller); w._skin["piece"] = piece; w._sel = getattr(w, "_sel", False)
    def style():
        try:
            if not w.winfo_exists(): return
            if w.cget("bg") != w.master["bg"]: w.configure(bg=w.master["bg"], activebackground=w.master["bg"])
        except tk.TclError: return
        on = getattr(w, "enabled", True); hv = on and getattr(w, "hover", False)
        draw(w, "disabled" if not on else ("hover" if hv else "normal"), ring=on and (hv or w._sel or w.focus_get() is w))
    w._style = style; style(); T.on_change(style, zoom=True); return w

def tabs(row):
    """every tab of a T.Tabs row: the open tab bright with its ring (round the tab's own shape), the others a little darker;
    under the mouse a tab brightens and gets the ring too (as the Draw page's buttons do)"""
    if not available(): return row
    for n, b in row.btns.items():
        _take_over(b, n, None); b._hover = False
        b.bind("<Enter>", lambda e, b=b: (setattr(b, "_hover", True), restyle()), add="+")
        b.bind("<Leave>", lambda e, b=b: (setattr(b, "_hover", False), restyle()), add="+")
    orig = row._style
    def restyle():
        orig()
        for n, b in row.btns.items():
            if b.cget("bg") != row.master["bg"]: b.configure(bg=row.master["bg"])
            if int(b.cget("highlightthickness")): b.tk.call(b._w, "configure", "-highlightthickness", 0)
            draw(b, "hover" if b._hover else ("normal" if n == row.active else "dim"), ring=n == row.active or b._hover)   # ring under the mouse, and kept on the open tab
    row._style = restyle; restyle(); T.on_change(restyle, zoom=True); return row

# ---------------------------------------------------------------- New / Open / Save: the painted file buttons (images/UI/Draw Toolbar/File Buttons)
# Every New / Open / Save button wears its picture exactly as drawn. When the button's job has more words ("Open my Images folder",
# "Save to Training"), they show in a small note while the pointer is over it.
FILE_ART = {"new": "buttons/new", "open": "buttons/open", "save": "buttons/save"}
_file_ph = {}

def _file_parts(which):
    """the picture split into: frame + icon (left), a clean strip of background (middle), the right end of the frame"""
    key = ("fparts", which)
    if key not in _src:
        import numpy as np
        im = UA.load(FILE_ART[which]); a = np.asarray(im).astype(int); H, W = a.shape[:2]; band = a[int(H * .3):int(H * .7)]
        dark = np.where(((band[..., :3].max(-1) < 60) & (band[..., 3] > 200)).sum(0) > 3)[0]
        icon_end = int(max([c for c in dark if c < W // 2] or [W * 0.45]))              # the icon's dark outline ends here
        white = np.where((((band[..., :3].min(-1) > 225) & (band[..., 3] > 200)).sum(0) > 2))[0]
        word_end = int(white.max()) if len(white) else int(W * 0.87)
        cap = max(8, round(W * 0.075)); s0 = min(word_end + 6, W - cap - 8); s1 = max(s0 + 4, W - cap)
        _src[key] = (im.crop((0, 0, icon_end + round(H * 0.05), H)), im.crop((s0, 0, s1, H)), im.crop((W - cap, 0, W, H)))
    return _src[key]

def _word_font(px):
    k = ("word", px)
    if k not in _pil_fonts:
        f = None
        for n in ("arialbd.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  os.path.join(HERE, "fonts", "CourierPrime-Bold.ttf")):
            try: f = ImageFont.truetype(n, px); break
            except Exception: pass
        _pil_fonts[k] = f or ImageFont.load_default()
    return _pil_fonts[k]

def _file_base(which, text):
    """the button at the picture's own height: the painted one, or the frame + icon with these words"""
    key = ("fbase", which, text)
    if key in _src: return _src[key]
    im = UA.load(FILE_ART[which])
    if False:                                                                   # (the stretched version with other words looked cut up: always the picture as drawn)
        left, strip, cap = _file_parts(which); H = im.height; font = _word_font(round(H * 0.40))
        d = ImageDraw.Draw(Image.new("RGBA", (1, 1))); tw = int(d.textlength(text, font=font)); mid = tw + round(H * 0.16)
        out = Image.new("RGBA", (left.width + mid + cap.width, H)); out.paste(left, (0, 0))
        x, flip = left.width, False
        while x < left.width + mid:                                                     # the background strip, mirrored side by side
            out.paste(strip.transpose(Image.FLIP_LEFT_RIGHT) if flip else strip, (x, 0)); x += strip.width; flip = not flip
        out.paste(cap, (left.width + mid, 0))
        ImageDraw.Draw(out).text((left.width + mid / 2, H / 2), text, font=font, anchor="mm", fill=(250, 250, 255),
                                 stroke_width=max(2, round(H * 0.035)), stroke_fill=(16, 28, 90))
        im = out
    _src[key] = im; return im

def _hover_note(w, text):
    """a small note with the button's full name while the pointer rests on it"""
    tip = {}
    def show(e=None):
        if tip.get("w") is not None: return
        try:
            t = tk.Toplevel(w); t.overrideredirect(True); t.attributes("-topmost", True)
            tk.Label(t, text=text, bg=T.PALETTE["panel2"], fg="white", font=T.f(9), padx=6, pady=2, bd=1, relief="solid").pack()
            t.geometry(f"+{w.winfo_rootx()}+{w.winfo_rooty() + w.winfo_height() + 2}"); tip["w"] = t
        except tk.TclError: pass
    def hide(e=None):
        t = tip.pop("w", None)
        if t is not None:
            try: t.destroy()
            except tk.TclError: pass
    w.bind("<Enter>", lambda e: w.after(350, lambda: getattr(w, "hover", False) and show()), add="+")
    w.bind("<Leave>", hide, add="+"); w.bind("<ButtonPress-1>", hide, add="+"); w.bind("<Destroy>", hide, add="+")

def file_picture(which, text, H, state="normal", ring=False):
    key = (which, text, H, state, ring, T.PALETTE["border"] if ring else None, margin())
    if key in _file_ph: return _file_ph[key]
    b = _file_base(which, text); im = b.resize((max(1, round(b.width * H / b.height)), H), Image.LANCZOS)
    if state in ("hover", "disabled"):
        rgb, a = im.convert("RGB"), im.getchannel("A")
        rgb = ImageEnhance.Brightness(rgb).enhance(1.15) if state == "hover" else ImageEnhance.Brightness(ImageEnhance.Color(rgb).enhance(0.0)).enhance(0.55)
        im = rgb.convert("RGBA"); im.putalpha(a)
    im = ringed(im, ring, key=("file",) + key)
    if len(_file_ph) > 300: _file_ph.clear()
    _file_ph[key] = ImageTk.PhotoImage(im); return _file_ph[key]

def file_kind(text):
    """"new" / "open" / "save" for a button whose words start with one of them, else None"""
    w = (text or "").strip().lower().split(" ")[0].rstrip("….")
    return w if w in FILE_ART else None

def file_button(w, which=None, height=34):
    """a T.Button wears the painted New / Open / Save picture (height in design pixels). Hover brightens it, the ring shows on
    hover / focus, greyed while it can't be used. If the picture is missing the button keeps its normal look"""
    text = w.cget("text"); which = which or file_kind(text)
    if not which or UA.load(FILE_ART[which]) is None or getattr(w, "_skin", None) is not None: return w
    _take_over(w, text, None); w._skin["file"] = which; w._skin["fh"] = height
    if text.replace("…", "").strip().lower() != which: _hover_note(w, text.replace("…", "").strip())
    def style():
        try:
            if not w.winfo_exists(): return
            if w.cget("bg") != w.master["bg"]: w.configure(bg=w.master["bg"], activebackground=w.master["bg"])
        except tk.TclError: return
        on = getattr(w, "enabled", True); hv = on and getattr(w, "hover", False)
        draw(w, "disabled" if not on else ("hover" if hv else "normal"), ring=on and (hv or w.focus_get() is w))
    w._style = style; style(); T.on_change(style, zoom=True); return w

# ---------------------------------------------------------------- status dots
FILLS = {"green": ((70, 230, 110), (20, 140, 50)), "blue": ((90, 170, 255), (20, 60, 170)), "grey": ((150, 150, 160), (60, 60, 70))}

def _hole(ring, big):
    """radius of the see-through hole in the middle of the ring (measured once)"""
    if "hole" not in _src:
        import numpy as np
        a = np.asarray(ring.resize((big, big), Image.LANCZOS))[..., 3]; c = big // 2; r = 0
        while r < c and a[c, c + r] < 128: r += 1
        _src["hole"] = r
    return _src["hole"]

def dot_picture(fill, px):
    key = ("dot", fill, px)
    if key in _ph: return _ph[key]
    ring = UA.load("skin/dot_ring"); big = 96
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ball = UA.load(f"panel/ball_{fill}")                                    # the painted green / blue / grey ball in the ring's hole
    if ball is not None:
        R = _hole(ring, big) + 3; b2 = ball.resize((2 * R, 2 * R), Image.LANCZOS); im.alpha_composite(b2, (big // 2 - R, big // 2 - R))
    elif fill in FILLS:                                                       # (no ball picture: a drawn one)
        hi, lo = FILLS[fill]; R = _hole(ring, big) + 2; c = big / 2; d = ImageDraw.Draw(im); n = 20
        for i in range(n):
            t = i / (n - 1); r = R * (1 - 0.75 * t); ox = oy = -R * 0.25 * t
            col = tuple(int(lo[k] + (hi[k] - lo[k]) * t) for k in range(3))
            d.ellipse([c + ox - r, c + oy - r, c + ox + r, c + oy + r], fill=col + (255,))
    im.alpha_composite(ring.resize((big, big), Image.LANCZOS))
    _ph[key] = ImageTk.PhotoImage(im.resize((px, px), Image.LANCZOS)); return _ph[key]

def dot(master, fill, size):
    """a status dot: the ring filled green or red, or left empty. Sized with the zoom"""
    lb = tk.Label(master, bd=0, highlightthickness=0, padx=0, pady=0, bg=master["bg"])
    def draw_dot():
        try: lb.configure(image=dot_picture(fill, max(6, int(round(size * T.Z)))), bg=lb.master["bg"])
        except tk.TclError: pass
    draw_dot(); T.on_change(draw_dot, zoom=True); return lb
