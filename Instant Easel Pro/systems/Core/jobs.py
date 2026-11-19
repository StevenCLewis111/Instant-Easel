"""
jobs.py: one line for every AI job in the app, so tabs never fight over the graphics card.

Pressing Paint it / Send / Ask in any AI tab puts a job in the line; one job runs at a time and the rest wait their turn, so you can
set several tabs going and walk away. While a page's job is waiting or running, its button is greyed out; pressing it anyway shows
a BUSY banner saying where the job is in the line. The pill at the bottom right of the window (1 RUNNING · 2 WAITING) opens the list,
where any job can be cancelled.

Pipelining: when the next job in line needs a different model than the one loaded, a waiting job that uses the loaded model goes
first (each job can be passed at most twice), so the app doesn't swap models back and forth.
While a job runs, PC memory is watched: if it gets close to full, a banner warns before anything fails.

    job = jobs.submit("AI Images", "Paint: a red shoe", work, kind="image", page=page_key, engine="image")
        work(job) runs on the jobs thread; job.say("Painting 2 of 4") shows progress; job.cancelled() -> stop soon
        on_done(result) / on_error(exception) are called on the jobs thread (hand them to the window with app.q.put)
    jobs.busy(page_key) -> the job that page has waiting / running (or None)
    jobs.guard(button, page_key, app)  grey the button while busy; pressing it then says BUSY
"""
import threading, time, itertools, tkinter as tk
import hardware

_lock = threading.Condition(); _waiting = []; _running = [None]; _ids = itertools.count(1); _loaded = [None]
MAX_PASSED = 2

class Job:
    def __init__(self, tab, title, fn, kind, page, engine, on_done, on_error, on_cancel):
        self.id = next(_ids); self.tab, self.title, self.fn, self.kind, self.page, self.engine = tab, title, fn, kind, page, engine
        self.on_done, self.on_error, self.on_cancel = on_done, on_error, on_cancel
        self.state = "waiting"; self.detail = "Waiting its turn"; self.passed = 0; self.created = time.time(); self.started = None
        self._cancel = threading.Event(); self.warned = False
    def say(self, text): self.detail = text
    def cancelled(self): return self._cancel.is_set()
    def place(self):
        """0 = running now; 1, 2, ... = place in the line"""
        with _lock:
            if _running[0] is self: return 0
            return _waiting.index(self) + 1 if self in _waiting else -1

def submit(tab, title, fn, kind="text", page=None, engine=None, on_done=None, on_error=None, on_cancel=None):
    _start_worker()
    j = Job(tab, title, fn, kind, page or tab, engine or kind, on_done, on_error, on_cancel)
    with _lock: _waiting.append(j); _lock.notify_all()
    return j

def busy(page):
    with _lock:
        if _running[0] is not None and _running[0].page == page: return _running[0]
        return next((j for j in _waiting if j.page == page), None)

def running():
    with _lock: return _running[0]

def snapshot():
    with _lock: return ([_running[0]] if _running[0] else []) + list(_waiting)

def cancel(job):
    with _lock:
        if job in _waiting: _waiting.remove(job); job.state = "cancelled"; return
    job._cancel.set(); job.detail = "Stopping…"
    if job.on_cancel:
        try: job.on_cancel()
        except Exception: pass

def where(job):
    """'running now' / 'waiting: 2nd in line'"""
    p = job.place()
    if p == 0: return "running now"
    if p < 0: return job.state
    return f"waiting: {_nth(p)} in line"

def _nth(n): return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"

# ---------------------------------------------------------------- the worker
_worker = [None]
def _start_worker():
    if _worker[0] is None or not _worker[0].is_alive():
        _worker[0] = threading.Thread(target=_loop, name="AI jobs", daemon=True); _worker[0].start()
        threading.Thread(target=_watch_memory, name="AI memory watch", daemon=True).start()

def _next():
    """the oldest job, unless a younger one can use the model that's already loaded (pipelining; nobody is passed more than twice)"""
    first = _waiting[0]
    if _loaded[0] and first.engine != _loaded[0] and first.passed < MAX_PASSED:
        for j in _waiting[1:]:
            if j.engine == _loaded[0]:
                for k in _waiting[:_waiting.index(j)]: k.passed += 1
                return j
    return first

def _loop():
    while True:
        with _lock:
            while not _waiting: _lock.wait()
            j = _next(); _waiting.remove(j); _running[0] = j; j.state = "running"; j.started = time.time(); j.detail = "Starting…"
        try:
            result = j.fn(j); j.state = "cancelled" if j.cancelled() else "done"
            if j.on_done: j.on_done(result)
        except Exception as e:
            j.state = "failed"
            try:
                import prefs; prefs.log_error(type(e), e, e.__traceback__)
            except Exception: pass
            if j.on_error:
                try: j.on_error(e)
                except Exception: pass
        finally:
            _loaded[0] = j.engine
            with _lock: _running[0] = None

def set_loaded(engine): _loaded[0] = engine                                      # an engine was stopped / started outside a job

# ---------------------------------------------------------------- memory watch while a job runs
def _watch_memory():
    while True:
        time.sleep(3)
        j = _running[0]
        if j is None or j.warned: continue
        try:
            total = float(hardware.pc().get("ram_gb") or 0); fr = hardware.free_ram_gb()
            if total and fr < max(1.0, total * 0.05):
                j.warned = True
                note(f"PC MEMORY ALMOST FULL — {fr:.1f} GB free. Close other programs, or {j.tab} may stop with an error", "busy")
        except Exception: pass

def note(text, kind="busy"):
    """a banner from any thread (the window's own loop shows it)"""
    try:
        import theme as T, tkinter
        root = tkinter._default_root
        if root is not None: T.banner(root, text, kind)
    except Exception: pass

# ---------------------------------------------------------------- the window side
def guard(button, page, app, what="it"):
    """grey `button` while `page` has a job waiting or running; pressing it then shows a BUSY banner with its place in the line"""
    import theme as T
    def blocked():
        j = busy(page)
        if j: T.banner(app, f"BUSY — {what} is {where(j)}. It runs as soon as it's ready (the list is at the bottom right)", "busy")
    button.on_blocked = blocked
    def tick():
        try:
            if not button.winfo_exists(): return
            want = "disabled" if busy(page) else "!disabled"
            if (want == "disabled") == button.enabled: button.state(want)
            button.after(400, tick)
        except tk.TclError: pass
    tick()

class Pill(tk.Label):
    """bottom right of the main window: '● 1 RUNNING · 2 WAITING' while anything is in the line; click for the list"""
    def __init__(self, app):
        import theme as T
        super().__init__(app, fg="white", bd=0, cursor="hand2", font=T.f(9), padx=10, pady=3, highlightthickness=1)
        self.app = app; self.T = T; self.win = None
        self.bind("<Button-1>", lambda e: self.open()); self.after(500, self.tick)
    def tick(self):
        try:
            if not self.winfo_exists(): return
            items = snapshot(); run = [j for j in items if j.state == "running"]; wait = len(items) - len(run)
            if items:
                T = self.T; txt = "● " + ("1 RUNNING" if run else "STARTING") + (f" · {wait} WAITING" if wait else "")    # the details are in the list
                self.configure(text=txt, bg="#5a4a00", highlightbackground="#f5c400")
                body = getattr(self.app, "body", None)
                if body is not None and body.winfo_ismapped():
                    hl = int(body.cget("highlightthickness") or 0)          # inside the page panel's bottom-right corner, clear of its border
                    x = body.winfo_rootx() - self.app.winfo_rootx() + body.winfo_width() - hl - int(10 * T.Z)
                    y = body.winfo_rooty() - self.app.winfo_rooty() + body.winfo_height() - hl - int(8 * T.Z)
                    self.place(in_=self.app, x=x, y=y, anchor="se"); self.lift()
                    b = getattr(self.app, "_banner", None)
                    if b is not None and b.winfo_exists() and b.winfo_manager(): b.lift()   # a message banner stays on top of it
            elif self.winfo_manager(): self.place_forget()
            self.after(500, self.tick)
        except tk.TclError: pass
    def open(self):
        if self.win is not None and self.win.winfo_exists(): self.win.lift(); return
        self.win = JobsWindow(self.app)

class JobsWindow(tk.Toplevel):
    """the line: what's running, what's waiting, with Cancel on each"""
    def __init__(self, app):
        import theme as T
        super().__init__(app); self.T = T; self.title("AI jobs"); self.configure(bg=T.PALETTE["bg"]); self.transient(app)
        self.panel = T.Panel(self, pad=14); self.panel.pack(fill="both", expand=True, padx=8, pady=8)
        T.Title(self.panel, "AI JOBS").pack(pady=(0, 4))
        T.Text(self.panel, "One job runs at a time so they never fight over the graphics card. The rest wait their turn.", muted=True, font=T.f(9)).pack()
        self.rows = tk.Frame(self.panel, bg=self.panel["bg"]); self.rows.pack(fill="both", expand=True, pady=8)
        T.Button(self.panel, "Close", self.destroy, width=8).pack()
        self._sig = None; self.geometry("+%d+%d" % (app.winfo_rootx() + 120, app.winfo_rooty() + 120)); self.refresh()
    def refresh(self):
        if not self.winfo_exists(): return
        T = self.T; items = snapshot(); sig = [(j.id, j.state, j.detail) for j in items]
        if sig != self._sig:
            self._sig = sig
            for w in self.rows.winfo_children(): w.destroy()
            if not items: T.Text(self.rows, "NOTHING RUNNING OR WAITING", muted=True).pack(pady=10)
            for j in items:
                r = tk.Frame(self.rows, bg=self.rows["bg"]); r.pack(fill="x", pady=2)
                state = "RUNNING" if j.state == "running" else f"WAITING ({_nth(j.place())})"
                T.Text(r, f"{state:<14} {j.tab}: {j.title[:48]}", font=T.f(9), width=72, anchor="w").pack(side="left")
                T.Button(r, "Cancel", lambda j=j: cancel(j), kind="danger", width=7).pack(side="right", padx=4)
                if j.state == "running": T.Text(self.rows, "      " + j.detail, muted=True, font=T.f(8)).pack(anchor="w")
        self.after(600, self.refresh)
