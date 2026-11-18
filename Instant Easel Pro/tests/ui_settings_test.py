"""(older test from an earlier version of the app: it points at a folder and screens that no longer exist, kept for reference)"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _testlog; _testlog.start(__file__)
import os, sys, subprocess, json, glob, zipfile
sys.path.insert(0, "/home/claude/books/Instant Easel"); os.chdir("/home/claude/books/Instant Easel")
import main as M, prefs
from PIL import Image
def shot(n): subprocess.run(["import", "-window", "root", f"/tmp/ui/set2-{n}.png"]); print("shot", n, flush=True)
a = M.InstantEasel(); a.geometry("1560x920+0+0"); a.deiconify()
pages = ["General", "Generation Defaults", "Performance", "Display", "Privacy & Data", "AI Models", "Updates", "Shortcuts", "Backup & Reset", "Theme"]
def tour(i=0):
    if i == len(pages): return a.after(300, layout)
    a.tabs.select("Settings"); a.pages["Settings"].select(pages[i]); a.after(700, lambda: (shot(f"p{i:02d}-" + pages[i].replace(" ", "").replace("&", "")), tour(i + 1)))
def pos(): x, y = a.tabs.winfo_rootx(), a.tabs.winfo_rooty(); return (x - a.winfo_rootx(), y - a.winfo_rooty())
def layout():
    a.tabs.select("Images"); base = pos(); print("tabs at (window-relative):", base, flush=True)
    a.geometry("1000x650+0+0"); a.after(900, lambda: small(base))
def small(base):
    print("1000x650 -> tabs at", pos(), "| scroll bars:", bool(a.hbar.winfo_ismapped()), bool(a.vbar.winfo_ismapped()), flush=True); shot("small-window")
    a.geometry("1600x900+0+0"); a.after(900, lambda: big(base))
def big(base):
    print("1600x900 -> tabs at", pos(), "| scroll bars:", bool(a.hbar.winfo_ismapped()), bool(a.vbar.winfo_ismapped()), flush=True)
    a.set_fullscreen(True); a.after(900, lambda: (print("full screen:", bool(a.attributes('-fullscreen')), "| tabs at", pos(), flush=True), shot("fullscreen"), a.set_fullscreen(False), a.after(700, theme1)))
def theme1():
    a.tabs.select("Settings"); th = a.pages["Settings"].pages["Theme"]; a.pages["Settings"].select("Theme"); th.one.value = 0.08; th.one._draw(); th.harmony.set("Complementary"); th.one_color()
    a.after(900, lambda: (shot("one-color-theme"), th.reset(), autosave()))
def autosave():
    prefs.set("save_folder", "/tmp/ie-saves"); prefs.set("auto_save", True); prefs.set("save_format", "JPEG")
    a.tabs.select("Images"); a.pages["Images"].select("Image to Image"); p = a.pages["Images"].pages["Image to Image"]; p.load(Image.open("examples/rocks-mountains/d.jpg")); p.run()
    a.after(800, lambda: wait(p))
def wait(p):
    if not p.go.enabled or not p.results: return a.after(500, lambda: wait(p))
    files = glob.glob("/tmp/ie-saves/*/*"); print("auto-saved files:", [os.path.basename(f) for f in files], flush=True)
    bk = a.pages["Settings"].pages["Backup & Reset"]
    import settings_pages as SP
    SP.filedialog.asksaveasfilename = lambda **k: "/tmp/ie-backup.zip"; SP.filedialog.askopenfilename = lambda **k: "/tmp/ie-backup.zip"
    bk.export(); print("backup contains:", zipfile.ZipFile("/tmp/ie-backup.zip").namelist(), flush=True); bk.restore(); print("restore:", bk.msg.cget("text"), flush=True)
    prefs.set("auto_save", False); prefs.set("save_format", "PNG"); a.destroy()
a.after(1200, tour); a.mainloop(); print("SETTINGS TEST FINISHED")
