import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scenes, draw, paint
from PIL import Image
FINAL = {"b1-00-1", "b1-01-1"}                     # author's own paintings: never touched
ids = sys.argv[1:]; done = []
for book, pre, anchor, sid, cap, fn in scenes.S:
    if sid in FINAL or (ids and sid not in ids): continue
    base = fn(draw.canvas())
    top = np.asarray(base.resize((60, 90)), dtype=np.float32)[:45].mean()
    kind = "warm" if top > 70 else "night"
    p = draw.caption(paint.paint(base, kind, seed=hash(sid) % 1000), cap)
    p.save(f"out/{sid}.jpg", quality=90); p.resize((1200, 1800), Image.LANCZOS).save(f"png/{sid}.png", optimize=True)
    done.append(f"{sid}:{kind}")
print(len(done), "repainted")
