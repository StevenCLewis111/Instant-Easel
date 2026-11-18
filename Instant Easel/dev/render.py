import os, glob, json, sys
sys.path.insert(0, os.path.dirname(__file__))
from draw import canvas, caption, W, H
from PIL import Image
import scenes
OUT = os.path.join(os.path.dirname(__file__), "out"); os.makedirs(OUT, exist_ok=True)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
manifest, misses = [], []
for book, pre, anchor, sid, cap, fn in scenes.S:
    src = os.path.join(ROOT, f"Rough Draft 8 Book {book}")
    files = [f for f in sorted(glob.glob(os.path.join(src, "*.md"))) if os.path.basename(f).startswith(pre + " ") or os.path.basename(f).startswith(pre + " -")]
    f = files[0] if files else None
    if not f: misses.append((sid, "NO FILE")); continue
    if anchor and anchor not in open(f, encoding="utf-8").read(): misses.append((sid, anchor)); anchor = None
    im = fn(canvas()); im = caption(im, cap)
    path = os.path.join(OUT, sid + ".jpg"); im.save(path, quality=86)
    manifest.append(dict(book=book, file=os.path.basename(f), anchor=anchor, image=f"tools/art/out/{sid}.jpg", caption=cap))
json.dump(manifest, open(os.path.join(os.path.dirname(__file__), "illustrations.json"), "w"), indent=1)
print(len(manifest), "rendered; anchor misses:", misses)
# contact sheet
ims = [Image.open(os.path.join(ROOT, m["image"])).resize((180, 270)) for m in manifest]
cols = 16; rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGB", (cols * 182, rows * 272), (255, 255, 255))
for i, t in enumerate(ims): sheet.paste(t, ((i % cols) * 182, (i // cols) * 272))
sheet.save("/home/claude/contact.jpg", quality=80)
