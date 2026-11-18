import os, sys, subprocess
sys.path.insert(0, "/home/claude/books/tools/art"); os.chdir("/home/claude/books/tools/art")
import main as M
def shot(n): subprocess.run(["import", "-window", "root", f"/tmp/ui/menu-{n}.png"]); print("shot", n, flush=True)
a = M.InstantEasel(); a.geometry("1280x860+0+0")
steps = [("Create", "Text to Image", "1-create"), ("Create", "Inpainting", "2-create-inpainting"), ("Edit", "Light", "3-edit-light"),
         ("Edit", "AI Tools", "4-edit-ai"), ("Train", "Models", "5-train-models"), ("Settings", "Theme", "6-settings")]
def run(i=0):
    if i == len(steps): a.destroy(); return
    tab, tool, name = steps[i]; a.tabs.select(tab); a.pages[tab].select(tool); a.after(700, lambda: (shot(name), run(i + 1)))
a.after(1200, run); a.mainloop(); print("MENU TEST FINISHED")
