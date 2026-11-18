import os, sys, subprocess, time
sys.path.insert(0, "/home/claude/books/tools/art"); os.chdir("/home/claude/books/tools/art")
import main as M, edit as E
from PIL import Image
a = M.InstantEasel(); a.geometry("1560x920+0+0")
def shot(n): subprocess.run(["import", "-window", "root", f"/tmp/ui/edit-{n}.png"]); print("shot", n, flush=True)
def go():
    a.tabs.select("Editing"); sec = a.pages["Editing"]; sec.select("Light"); L = sec.pages["Light"]
    L.set_image(Image.open("examples/rocks-mountains/dfsdfsfdfs.jpg"))
    for k, v in (("exposure", 0.56), ("shadows", 0.7), ("highlights", 0.38), ("contrast", 0.6)): L.change(k, v)
    a.after(900, lambda: (shot("1-light"), color()))
def color():
    sec = a.pages["Editing"]; sec.select("Color"); C = sec.pages["Color"]
    for k, v in (("temperature", 0.72), ("vibrance", 0.7)): C.change(k, v)
    C.refresh(); a.after(900, lambda: (shot("2-color"), effects()))
def effects():
    sec = a.pages["Editing"]; sec.select("Effects"); F = sec.pages["Effects"]
    for k, v in (("vignette", 0.8), ("clarity", 0.65), ("glow", 0.7)): F.change(k, v)
    F.refresh(); a.after(900, lambda: (shot("3-effects"), filters()))
def filters():
    sec = a.pages["Editing"]; sec.select("Filters"); Fi = sec.pages["Filters"]; Fi.pick("warm film"); Fi.refresh()
    t0 = time.time(); full = E.apply(a.edit["original"], a.edit["params"], a.edit["filt"]); print(f"full-size apply: {full.size} in {time.time()-t0:.2f}s", flush=True)
    a.after(1200, lambda: (shot("4-filters"), a.destroy()))
a.after(1200, go); a.mainloop(); print("EDIT UI TEST FINISHED")
