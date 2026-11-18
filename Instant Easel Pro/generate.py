#!/usr/bin/env python3
"""
generate.py: the trilogy's painterly image engine as a standalone tool.

Paint any image in the author's style:
    python3 generate.py --input sketch.png --out painted.jpg --style warm
    python3 generate.py --input photo.jpg --out painted.jpg --style styles/my_painting.jpg --interior
Render a scene from the books by its slot name:
    python3 generate.py --scene b2-16-1 --out roof.jpg
List the scenes:
    python3 generate.py --list

--style   "warm" (sunset cover), "night" (prologue city), or a path to ANY painting to borrow its palette and sky
--interior  rooms, doors, close-up planets: brushwork and palette only, no borrowed sky
--caption   optional caption text (book style); --seed changes the brushwork
"""
import argparse, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from PIL import Image
import draw, paint

def main():
    ap = argparse.ArgumentParser(description="Painterly image engine")
    ap.add_argument("--input"); ap.add_argument("--scene"); ap.add_argument("--list", action="store_true")
    ap.add_argument("--out", default="painted.jpg"); ap.add_argument("--style", default="warm")
    ap.add_argument("--interior", action="store_true"); ap.add_argument("--caption"); ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    if a.list:
        import scenes
        for s in scenes.S: print(f"{s[3]:10s} {s[4]}")
        return
    if a.scene:
        import scenes
        hit = [s for s in scenes.S if s[3] == a.scene]
        if not hit: sys.exit(f"no scene named {a.scene}; try --list")
        base = hit[0][5](draw.canvas()); cap = a.caption if a.caption is not None else hit[0][4]
    elif a.input:
        base = Image.open(a.input).convert("RGB"); cap = a.caption
        w, h = base.size                               # fit to the book's 2:3 page, center-cropped
        tw = min(w, int(h * 2 / 3)); th = int(tw * 3 / 2)
        base = base.crop(((w - tw) // 2, (h - th) // 2, (w - tw) // 2 + tw, (h - th) // 2 + th)).resize((draw.W, draw.H), Image.LANCZOS)
    else:
        sys.exit("give --input IMAGE or --scene NAME (or --list)")
    out = paint.paint(base, a.style, seed=a.seed, interior=a.interior)
    if cap: out = draw.caption(out, cap)
    out.save(a.out, quality=90); print("wrote", a.out, out.size)

if __name__ == "__main__":
    main()
