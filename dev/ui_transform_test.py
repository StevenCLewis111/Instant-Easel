import os, sys, subprocess
sys.path.insert(0, "/home/claude/books/Instant Easel"); os.chdir("/home/claude/books/Instant Easel")
import main as M, edit as E
from PIL import Image
a = M.InstantEasel(); a.geometry("1560x920+0+0")
def shot(n): subprocess.run(["import", "-window", "root", f"/tmp/ui/tr-{n}.png"]); print("shot", n, flush=True)
def go():
    a.tabs.select("Editing"); sec = a.pages["Editing"]; sec.select("Transform"); P = sec.pages["Transform"]
    P.set_image(Image.open("examples/rocks-mountains/dfsdfsfdfs.jpg")); P.st.value = 0.5 + 6 / 90; P.st._draw(); P._straighten(P.st.value)
    P.ratio.set("16:9"); a.after(900, lambda: (shot("1-ratio"), drag(P)))
def drag(P):
    ev = lambda x, y: type("E", (), {"x": x, "y": y})()
    ox, oy = P._off; P._press(ev(ox + P._tw * 0.15, oy + P._th * 0.2)); P._drag(ev(ox + P._tw * 0.75, oy + P._th * 0.6))
    a.after(900, lambda: (shot("2-dragged"), light()))
def light():
    sec = a.pages["Editing"]; sec.select("Light"); sec.pages["Light"].refresh()
    ed = a.edit; out = E.apply(E.transform(ed["original"], ed["geom"]), ed["params"], ed["filt"]); print("full-size output:", out.size, "ratio", round(out.width / out.height, 3), "(16:9 = 1.778)", flush=True)
    a.after(900, lambda: (shot("3-light-cropped"), a.destroy()))
a.after(1200, go); a.mainloop(); print("TRANSFORM TEST FINISHED")
