import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scenes, draw, paint
from PIL import Image
FINAL = {"b1-00-1", "b1-01-1"}
INTERIOR = set(open("interior_ids.txt").read().split())
log = open("/home/claude/repaint.log", "a")
for book, pre, anchor, sid, cap, fn in scenes.S:
    if sid in FINAL or sid not in INTERIOR or os.path.exists(f"/home/claude/repaint_done3/{sid}"): continue
    base = fn(draw.canvas()); top = np.asarray(base.resize((60, 90)), dtype=np.float32)[:45].mean()
    kind = "warm" if top > 70 else "night"
    mc = np.asarray(base.resize((60, 90)), dtype=np.float32).reshape(-1, 3).mean(0)
    if sid in INTERIOR and mc[0] > mc[2] + 4: kind = "warm"          # warm-lit rooms keep their warmth
    p = draw.caption(paint.paint(base, kind, seed=sum(map(ord, sid)), interior=True), cap)
    p.save(f"out/{sid}.jpg", quality=90); p.resize((1200, 1800), Image.LANCZOS).save(f"png/{sid}.png", optimize=True)
    open(f"/home/claude/repaint_done3/{sid}", "w").write(kind); log.write(f"{sid} {kind}\n"); log.flush()
log.write("ALL DONE\n")
