import os, sys, subprocess
sys.path.insert(0, "/home/claude/books/Instant Easel"); os.chdir("/home/claude/books/Instant Easel")
import main as M, prefs
from PIL import Image
prefs.set("confirm_exit", False)
a = M.InstantEasel(); a.geometry("1560x920+0+0"); a.deiconify()
def shot(n): subprocess.run(["import", "-window", "root", f"/tmp/ui/hist-{n}.png"]); print("shot", n, flush=True)
def labels(): return [l for l, _ in a.hist]
steps = []
def go():
    a.tabs.select("Editing"); sec = a.pages["Editing"]; sec.select("Light"); L = sec.pages["Light"]
    L.set_image(Image.open("/tmp/hist-test.jpg"), path="/tmp/hist-test.jpg")
    for v in (0.55, 0.58, 0.6): L.change("exposure", v)                 # one drag = several moves
    a.after(900, lambda: edit2(sec))
def edit2(sec):
    sec.select("Color"); sec.pages["Color"].change("saturation", 0.7); a.after(900, lambda: edit3(sec))
def edit3(sec):
    sec.select("Filters"); sec.pages["Filters"].pick("sepia"); a.after(900, lambda: edit4(sec))
def edit4(sec):
    sec.select("Transform"); T = sec.pages["Transform"]; T.geom(rot90=1); a.after(900, lambda: check(sec))
def check(sec):
    print("steps:", labels(), flush=True)
    a.hist_undo(); a.hist_undo(); print("after 2 undos -> at:", labels()[a.hpos], "| filter:", a.edit["filt"], "| rot90:", a.edit["geom"]["rot90"], flush=True)
    a.hist_redo(); print("after redo -> at:", labels()[a.hpos], "| filter:", a.edit["filt"], flush=True)
    a.hist_jump(0); print("jump to step 0 -> exposure:", a.edit["params"]["exposure"], "| saturation:", a.edit["params"]["saturation"], flush=True)
    a.hist_jump(len(a.hist) - 2); sec.select("Light"); a.tabs.active = "Editing"
    a.event_generate("<Control-z>"); print("Ctrl+Z -> at:", labels()[a.hpos], flush=True)
    sec.pages["Light"].reset(); print("reset recorded as:", labels()[-1], "| exposure now:", a.edit["params"]["exposure"], flush=True)
    a.hist_undo(); print("undo the reset -> exposure:", a.edit["params"]["exposure"], flush=True)
    sec.select("History"); H = sec.pages["History"]; H.show_list(); a.after(800, lambda: (shot("1-list"), compare(H)))
def compare(H):
    H.toggle_compare(); a.after(900, lambda: (shot("2-compare"), over(H)))
def over(H):
    before = os.path.getsize("/tmp/hist-test.jpg"); M.T.popup = lambda *x, **k: "Overwrite"
    H.overwrite(); print("overwrite changed the file:", os.path.getsize("/tmp/hist-test.jpg") != before, "| size now", Image.open("/tmp/hist-test.jpg").size, flush=True)
    a.destroy()
a.after(1200, go); a.mainloop(); print("HISTORY TEST FINISHED")
