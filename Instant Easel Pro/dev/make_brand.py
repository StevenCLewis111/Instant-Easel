"""Our own logo banner and app icon for Instant Easel (blocky pixel lettering, glow lines, light flares)."""
import os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__))
# 5x7 pixel font (our own), only the letters the name needs
F = {
 "F": ["11111","10000","10000","11110","10000","10000","10000"], "R": ["11110","10001","10001","11110","10100","10010","10001"],
 "E": ["11111","10000","10000","11110","10000","10000","11111"], "T": ["11111","00100","00100","00100","00100","00100","00100"],
 "X": ["10001","10001","01010","00100","01010","10001","10001"], "O": ["01110","10001","10001","10001","10001","10001","01110"],
 "I": ["11111","00100","00100","00100","00100","00100","11111"], "M": ["10001","11011","10101","10101","10001","10001","10001"],
 "A": ["01110","10001","10001","11111","10001","10001","10001"], "G": ["01110","10001","10000","10111","10001","10001","01111"],
 "N": ["10001","11001","10101","10011","10001","10001","10001"], " ": ["00000"] * 7,
 "S": ["01111","10000","10000","01110","00001","00001","11110"], "L": ["10000","10000","10000","10000","10000","10000","11111"]}

def pixel_text(text, cell, gap=1):
    w = sum((5 + gap) * cell for _ in text); img = Image.new("L", (w, 7 * cell), 0); d = ImageDraw.Draw(img); x = 0
    for ch in text:
        for r, row in enumerate(F[ch]):
            for c, bit in enumerate(row):
                if bit == "1": d.rectangle([x + c * cell, r * cell, x + (c + 1) * cell - 2, (r + 1) * cell - 2], fill=255)
        x += (5 + gap) * cell
    return img

def flare(size, color=(255, 170, 60)):
    f = Image.new("RGBA", (size, size), (0, 0, 0, 0)); a = np.zeros((size, size), np.float32); c = size / 2
    y, x = np.mgrid[0:size, 0:size]
    a += np.clip(1 - np.abs(x - c) / (size * 0.012 + 1), 0, 1) * np.clip(1 - np.abs(y - c) / c, 0, 1) ** 2
    a += np.clip(1 - np.abs(y - c) / (size * 0.012 + 1), 0, 1) * np.clip(1 - np.abs(x - c) / c, 0, 1) ** 2 * 0.7
    a += np.clip(1 - np.hypot(x - c, y - c) / (size * 0.12), 0, 1) ** 2
    a = np.clip(a, 0, 1); rgba = np.dstack([np.full_like(a, color[0]), np.full_like(a, color[1]), np.full_like(a, color[2]), a * 255]).astype(np.uint8)
    core = Image.fromarray(rgba); d = ImageDraw.Draw(core); d.ellipse([c - size * 0.04, c - size * 0.04, c + size * 0.04, c + size * 0.04], fill=(255, 250, 230, 255))
    return core

def logo(path, width=1400):
    lines = ["INSTANT EASEL"]; cell = 13
    t1 = pixel_text(lines[0], cell)
    W = width; H = 300; img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0)); bd = ImageDraw.Draw(band)
    bd.rounded_rectangle([40, 40, W - 40, H - 40], radius=26, fill=(12, 20, 40, 235))                          # navy band
    img = Image.alpha_composite(img, band)
    for y, col in ((52, (90, 220, 255)), (H - 54, (90, 220, 255)), (60, (255, 160, 50)), (H - 62, (255, 160, 50))):  # glow lines
        g = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(g).line([(70, y), (W - 70, y)], fill=col + (255,), width=3)
        img = Image.alpha_composite(img, Image.alpha_composite(g.filter(ImageFilter.GaussianBlur(5)), g))
    for t, y in ((t1, (H - t1.height) // 2),):                                                                     # white pixel letters with a soft glow
        x = (W - t.width) // 2; glow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); m = Image.new("L", (W, H), 0); m.paste(t, (x, y))
        glow.putalpha(m.filter(ImageFilter.GaussianBlur(7))); glow = Image.composite(Image.new("RGBA", (W, H), (120, 200, 255, 255)), glow, m.filter(ImageFilter.GaussianBlur(7)))
        img = Image.alpha_composite(img, glow); white = Image.new("RGBA", (W, H), (248, 248, 255, 255)); img.paste(white, (0, 0), m)
    for cx, cy, s in ((W * 0.5, 52, 150), (W * 0.5, H - 54, 120), (52, H / 2, 90), (W - 52, H / 2, 90)):        # light flares
        f = flare(s, (255, 175, 70) if s > 100 else (190, 230, 255)); img.alpha_composite(f, (int(cx - s / 2), int(cy - s / 2)))
    img.save(path); return img

def icon(path, size=512):
    s = size; img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    bg = Image.new("RGB", (s, s)); bd = ImageDraw.Draw(bg)
    for y in range(s): bd.line([(0, y), (s, y)], fill=(int(16 + 18 * y / s), int(30 + 36 * y / s), int(84 + 64 * y / s)))
    mask = Image.new("L", (s, s), 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.18), fill=255)
    img.paste(bg, (0, 0), mask); d = ImageDraw.Draw(img)
    d.rounded_rectangle([6, 6, s - 7, s - 7], radius=int(s * 0.17), outline=(34, 230, 90), width=int(s * 0.022))   # green frame
    wood, dark = (196, 140, 72), (120, 80, 40)
    # easel: two front legs, a back leg, a crossbar and a ledge
    d.line([(s * 0.5, s * 0.16), (s * 0.27, s * 0.88)], fill=wood, width=int(s * 0.035)); d.line([(s * 0.5, s * 0.16), (s * 0.73, s * 0.88)], fill=wood, width=int(s * 0.035))
    d.line([(s * 0.5, s * 0.16), (s * 0.5, s * 0.86)], fill=dark, width=int(s * 0.025))
    d.rectangle([s * 0.22, s * 0.68, s * 0.78, s * 0.72], fill=wood)
    # the canvas: a sunset painting
    x0, y0, x1, y1 = int(s * 0.25), int(s * 0.24), int(s * 0.75), int(s * 0.68)
    for y in range(y0, y1):
        t_ = (y - y0) / (y1 - y0); d.line([(x0, y), (x1, y)], fill=(int(80 + 170 * t_), int(60 + 90 * t_), int(130 - 50 * t_)))
    d.ellipse([s * 0.45, s * 0.46, s * 0.57, s * 0.58], fill=(255, 228, 150))
    d.polygon([(x0, y1), (s * 0.38, s * 0.47), (s * 0.52, y1)], fill=(44, 32, 62)); d.polygon([(s * 0.44, y1), (s * 0.63, s * 0.43), (x1, y1)], fill=(64, 42, 80))
    d.rectangle([x0, y0, x1, y1], outline=(245, 240, 228), width=int(s * 0.018))
    # the spark: "instant"
    f = flare(int(s * 0.42), (255, 205, 90)); img.alpha_composite(f, (int(s * 0.62), int(s * 0.04)))
    img.save(path)
    img.save(os.path.splitext(path)[0] + ".ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return img

if __name__ == "__main__":
    logo(os.path.join(HERE, "old", "logo-pixel.png")); icon(os.path.join(HERE, "old", "icon-pixel.png"))   # the original pixel brand (kept for reference); print("brand written")
