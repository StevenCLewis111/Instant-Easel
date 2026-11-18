import os, sys, subprocess
sys.path.insert(0, "/home/claude/books/tools/art"); os.chdir("/home/claude/books/tools/art")
import main as M
from PIL import Image
a = M.InstantEasel(); a.geometry("1280x860+0+0")
def go():
    a.tabs.select("Image to Image"); p = a.pages["Image to Image"]
    p.load(Image.open("examples/rocks-mountains/d.jpg")); p.prompt.set('golden hour, "The next mountain"'); p.medium.set("oil"); p.run(); a.after(800, wait)
def wait():
    p = a.pages["Image to Image"]
    if not p.go.enabled or p.result is None: a.after(500, wait); return
    a.after(600, lambda: (subprocess.run(["import", "-window", "root", "/tmp/ui/ie-img2img.png"]), print("notes:", p.notes.cget("text")), a.destroy()))
a.after(1200, go); a.mainloop(); print("IMG2IMG UI TEST FINISHED")
