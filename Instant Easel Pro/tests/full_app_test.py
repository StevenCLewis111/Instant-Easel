"""
full_app_test.py: opens the real app and works through every tab and page, the Editing tools, every drawing tool, layers, colour,
zoom / pan, theme sliders, window modes and zoom changes. Prints ok / FAIL for each step (also written to the main log).
Your settings and theme are put back exactly as they were afterwards.   Run:  python tests/full_app_test.py
"""
import os, sys, shutil; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _testlog; ROOT = _testlog.start(__file__)
_BACKUP = {}
for _f in ("instant_easel_settings.json", "instant_easel_theme.json"):
    _p = os.path.join(ROOT, ".json", _f)
    if os.path.exists(_p): _BACKUP[_p] = open(_p, "rb").read()
_LOG = os.path.join(ROOT, "logs", "instant_easel_errors.log"); _LOG0 = os.path.getsize(_LOG) if os.path.exists(_LOG) else 0
import sys, types, time
import main, prefs
T = main.T; E = types.SimpleNamespace; T.popup = lambda *a, **k: "OK"
from PIL import Image
import numpy as np
app = main.InstantEasel(); app.withdraw(); app.restore_window(); app.show_window()
steps = []
def step(name, fn):
    try: fn(); app.update(); steps.append(f"ok   {name}")
    except Exception as e: import traceback; steps.append(f"FAIL {name}: {e!r}\n{traceback.format_exc()[-600:]}")
def run():
    ed = app.pages["Editing"]
    img = Image.fromarray((np.random.rand(500, 700, 3) * 255).astype(np.uint8))
    step("open image in Editing", lambda: (app.show("Editing"), ed.select("Light"), ed.pages["Light"].set_image(img)))
    def sliders():
        lp = ed.pages["Light"]
        for v in np.linspace(0.5, 0.9, 25): lp.change("exposure", v); app.update(); time.sleep(0.005)
        t0 = time.time()
        while lp._busy and time.time() - t0 < 5: app.update(); time.sleep(0.01)
        assert lp.ph is not None
    step("drag Exposure 25 steps (background render)", sliders)
    for page in ("Color", "Effects", "Filters", "Transform", "History"): step(f"Editing > {page}", lambda p=page: (ed.select(p), app.update(), time.sleep(0.3), app.update()))
    step("undo / redo edits", lambda: (app.hist_undo(), app.hist_redo()))
    ds = app.pages["Drawing"].pages["Draw"]
    def draw_all():
        app.show("Drawing"); app.update(); ds.fit(); app.update(); cx, cy = ds.cv.winfo_width() // 2, ds.cv.winfo_height() // 2
        for tool in ("brush", "eraser", "line", "rect", "oval", "fill", "pick"):
            ds.set_tool(tool); ds.down(E(x=cx - 30, y=cy - 20))
            for i in range(10): ds.drag(E(x=cx - 30 + i * 6, y=cy - 20 + i * 4))
            ds.up(E(x=cx + 30, y=cy + 20)); app.update()
        ds.mirror.set(True); ds.set_tool("brush"); ds.down(E(x=cx, y=cy)); ds.drag(E(x=cx + 20, y=cy)); ds.up(E(x=cx + 20, y=cy)); ds.mirror.set(False)
        for _ in range(4): ds.undo()
        for _ in range(2): ds.redo()
        ds.add_layer(); ds.down(E(x=cx, y=cy)); ds.drag(E(x=cx + 25, y=cy + 5)); ds.up(E(x=cx + 25, y=cy + 5))
        ds.dup_layer(); ds._toggle_vis(ds.li); ds.lop_s.command(0.4); ds.mode.set("multiply"); ds.move_layer(-1); ds.merge_down(); ds.del_layer()
        for k in range(10): ds._wheel_pick(E(x=95 + k, y=95)); app.update()
        ds.set_size(80); ds.zoom_by(1.5); ds._pan_start(E(x=10, y=10)); ds._pan_move(E(x=40, y=30)); app.update(); time.sleep(0.2); app.update()
        assert ds.flatten().size == tuple(ds.size_wh)
    step("Draw: every tool, mirror, undo/redo, layers, colour, zoom, pan", draw_all)
    step("Theme sliders", lambda: [app.pages["Settings"].pages["Theme"].change("bg", v / 20) or app.update() for v in range(20)])
    import catalog; hidden, hidden_pages = catalog.hidden_tabs()                  # tabs this PC can't use aren't built (AI Videos on a small card)
    step("tabs this PC can't use are hidden" + (f" ({', '.join(sorted(hidden))})" if hidden else ""),
         lambda: (assert_(not (hidden & set(app.pages)), "a hidden tab was built"), assert_(not any(p in sec.pages for sec in app.pages.values() for p in hidden_pages), "a hidden page was built")))
    for tab in [t for t in ("AI Images", "AI Videos", "AI Chat", "AI Coding", "AI Training", "Settings") if t not in hidden]:
        sec = app.pages[tab]
        for name in sec.pages: step(f"{tab} > {name}", lambda s=sec, n=name: (app.show(tab), s.select(n), app.update()))
    step("window: maximized -> full screen -> fixed -> maximized", lambda: (app._to_maximized(), app.update(), app._to_fullscreen(), app.update(), app._to_fixed(), app.update(), app.apply_window_mode(), app.update()))
    step("zoom changes", lambda: [main.zoom_to(app, z) or app.update() for z in (1.2, 0.7, 0.78)])
    app.after(2500, done)
def assert_(ok, msg):
    if not ok: raise AssertionError(msg)
def done():
    print("\n".join(steps))
    new = open(_LOG, encoding="utf-8", errors="replace").read()[_LOG0:] if os.path.exists(_LOG) else ""
    errs = [l for l in new.splitlines() if l.startswith("=== 20") or l.startswith("Traceback")]   # app errors (not this test's own lines)
    print("ERRORS LOGGED:", "none" if not errs else f"{len(errs)} (see logs/instant_easel_errors.log)")
    for p, b in _BACKUP.items(): open(p, "wb").write(b)                     # your settings and theme, back as they were
    if any(l.startswith("FAIL") for l in steps) or errs: sys.excepthook(AssertionError, AssertionError("some steps failed"), None)
    app.destroy()
app.after(1500, run); app.mainloop()
