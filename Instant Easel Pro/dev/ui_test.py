import os, sys, time, subprocess, threading
sys.path.insert(0, "/home/claude/books/tools/art"); os.chdir("/home/claude/books/tools/art")
import app as A, paint_window as PW, landscape
def shot(name): subprocess.run(["import", "-window", "root", f"/tmp/ui/{name}.png"]); print("screenshot", name, flush=True)
a = A.App(); a.geometry("1280x800+0+0")
steps = []
def step(delay, fn): steps.append((delay, fn))
step(1500, lambda: shot("1-main-window"))
def build(): a._run_landscape(dict(landscape.DEFAULTS, figures=2, caption="Come back sometimes. Appreciate the view.", seed=3))
step(500, build)
def wait_done():
    if str(a.paint_btn["state"]) == "disabled" or a.result is None: a.after(1000, wait_done); return
    shot("2-landscape-painted")
    w = PW.PaintWindow(a, w=1000, h=650); w.geometry("1280x800+0+0"); a.after(1200, lambda: draw_on(w))
def draw_on(w):
    import math
    for i, n in enumerate(["oil", "watercolor", "charcoal", "ink pen", "marker", "spray", "grass blades", "glow (dodge)"]):
        w.brush = n; y = 70 + i * 72
        pts = [(60 + t * 820, y + math.sin(t * 6) * 18, 1.0) for t in [k / 30 for k in range(31)]]
        w.undo_stack.append(w.canvas.a.copy()); w.canvas.stroke(pts, n, color=(196, 92, 44) if n != "glow (dodge)" else (255, 210, 120), size=34 if n not in ("ink pen",) else 10)
    w.refresh(); a.after(1200, lambda: (shot("3-drawing-canvas"), over(w)))
def over(w):
    w.destroy(); a.paint_over(); a.after(1500, lambda: paint_over_strokes())
def paint_over_strokes():
    win = [c for c in a.winfo_children() if isinstance(c, PW.PaintWindow)][-1]; win.geometry("1280x800+0+0")
    win.brush = "glow (dodge)"; win.canvas.stroke([(900, 1400), (1100, 1300), (1300, 1350)], "glow (dodge)", color=(255, 200, 120), size=220, opacity=0.8)
    win.brush = "oil"; win.canvas.stroke([(200, 2300), (600, 2200), (900, 2350)], "oil", color=(90, 40, 30), size=90)
    win.refresh(); a.after(1200, lambda: (shot("4-paint-over-result"), a.destroy()))
step(1000, wait_done)
t = 0
for d, fn in steps: t += d; a.after(t, fn)
a.mainloop(); print("UI TEST FINISHED", flush=True)
