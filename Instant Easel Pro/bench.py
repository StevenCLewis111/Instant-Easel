"""Style bench: compare an attempt to the author's painting (palette, texture, stroke direction, value structure)."""
import sys, numpy as np
from PIL import Image, ImageDraw, ImageFont
import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__))
TARGET = _os.path.join(_HERE, "styles", "summit.jpg")                    # the author's summit painting (identical copy)
BASE = _os.path.join(_HERE, "..", "books", "book 1", "images", "illustrations-hires", "b1-03-1.png")   # the book's terrace scene, the test baseline
def feats(im):
    a = np.asarray(im.convert("RGB").resize((400, 600)), dtype=np.float32) / 255
    g = a.mean(2); gy, gx = np.gradient(g); mag = np.hypot(gx, gy); ang = np.arctan2(gy, gx) % np.pi
    f = {}
    f["palette"] = np.histogramdd(a.reshape(-1, 3), bins=(6, 6, 6), range=((0, 1),) * 3)[0].ravel(); f["palette"] /= f["palette"].sum()
    f["texture"] = np.histogram(np.clip(mag, 0, 0.12), bins=24)[0].astype(float); f["texture"] /= f["texture"].sum()
    w = mag > 0.01; f["strokes"] = np.histogram(ang[w], bins=18, range=(0, np.pi), weights=mag[w])[0]; f["strokes"] /= f["strokes"].sum() + 1e-9
    f["values"] = np.array([g[int(600 * i / 6):int(600 * (i + 1) / 6)].mean() for i in range(6)])     # light/dark by band, top to bottom
    return f
def score(im, target=None):
    t = feats(Image.open(target or TARGET)); s = feats(im); r = {}
    for k in ("palette", "texture", "strokes"): r[k] = 0.5 * np.sum((s[k] - t[k]) ** 2 / (s[k] + t[k] + 1e-9))
    r["values"] = float(np.abs(s["values"] - t["values"]).mean() * 4)
    r["total"] = sum(r.values()); return r
def compare(new, label, path):
    base = Image.open(BASE).convert("RGB"); tgt = Image.open(TARGET).convert("RGB")
    W, H = 420, 630; sheet = Image.new("RGB", (W * 3 + 40, H + 70), (24, 24, 28)); d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype("fonts/EBGaramond-SemiBold.ttf", 22)
    for i, (im, cap) in enumerate(((base, "BASELINE (current)"), (new, label), (tgt, "TARGET (your painting)"))):
        sheet.paste(im.resize((W, H)), (10 + i * (W + 10), 50)); d.text((10 + i * (W + 10), 14), cap, font=f, fill=(235, 225, 205))
    sheet.save(path, quality=88)
if __name__ == "__main__":
    for p in sys.argv[1:]:
        r = score(Image.open(p)); print(p, {k: round(v, 3) for k, v in r.items()})
