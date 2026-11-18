import os, sys, subprocess
sys.path.insert(0, "/home/claude/books/tools/art"); os.chdir("/home/claude/books/tools/art")
import main as M
from PIL import Image
a = M.InstantEasel(); a.geometry("1560x920+0+0")
def shot(n): subprocess.run(["import", "-window", "root", f"/tmp/ui/sty-{n}.png"]); print("shot", n, flush=True)
def gallery():
    gw = M.StyleGallery(a); gw.geometry("+180+40"); a.after(2500, lambda: (shot("1-gallery"), gw.destroy(), gen()))
def gen():
    p = a.pages["Images"].pages["Text to Image"]; p.prompt.delete("1.0", "end"); p.prompt.insert("1.0", "an anime sunset over jagged peaks, two friends sitting"); p.generate()
    a.after(1000, lambda: wait(p, "gen_btn", lambda: a.after(600, lambda: (shot("2-anime"), i2i()))))
def wait(p, btn, then):
    if not getattr(p, btn).enabled or not p.results: a.after(1000, lambda: wait(p, btn, then)); return
    then()
def i2i():
    a.pages["Images"].select("Image to Image"); a.gen["style"].set("Pop Art"); p = a.pages["Images"].pages["Image to Image"]
    p.load(Image.open("examples/rocks-mountains/dfsdfsfdfs.jpg")); p.run(); a.after(800, lambda: wait(p, "go", lambda: a.after(600, lambda: (shot("3-popart"), a.destroy()))))
a.after(1200, gallery); a.mainloop(); print("STYLES UI TEST FINISHED")
