"""
updater.py: updates in place, no more downloading the zip by hand.

Each build on GitHub stamps the commit it was made from into the app (build.json). The app compares that with the newest build on
the Releases page (the pro-latest / drawing-app-latest prerelease), downloads the new zip, and on restart a small helper waits for
the app to close, puts the new program files in (the .exe and its _internal folder), and opens it again. The helper is the new
copy itself, run from update/new with --finish-update: it logs every step to update/update.log.

Only the program's own files change: your settings, logs, pictures, models and everything else beside the .exe are left alone.

    import updater as U
    U.current()                      -> dict(sha, built) of this build ({} when running from the source)
    U.check()                        -> dict(sha, built, url, size, title) of a newer build, or None
    U.download(new, report)          the zip, unpacked into update/new (beside the app)
    U.restart_into_update(app)       the helper takes over; the app closes and comes back updated
"""
import os, sys, json, time, shutil, zipfile, subprocess, urllib.request
import paths

REPO = "StevenCLewis111/Instant-Easel"
FROZEN = bool(getattr(sys, "frozen", False))
PRO = False                                                                # (this is Instant Easel's copy; Pro has its own)
TAG = "pro-latest" if PRO else "drawing-app-latest"
ASSET = "InstantEaselPro-windows.zip" if PRO else "InstantEasel-windows.zip"
EXE = "InstantEaselPro.exe" if PRO else "InstantEasel.exe"


def current():
    """this build's stamp: dict(sha, built), or {} (running from the source: updates come with git pull)"""
    try:
        with open(os.path.join(paths.APP, "build.json"), encoding="utf-8") as f: return json.load(f)
    except Exception: return {}


def _get_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "InstantEasel-updater"})
    with urllib.request.urlopen(req, timeout=15) as r: return json.load(r)


def latest():
    """the newest build on GitHub: dict(sha, built, url, size, title)"""
    rel = _get_json(f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}")
    asset = next((a for a in rel.get("assets", []) if a.get("name") == ASSET), None)
    if not asset: raise RuntimeError("the newest build has no download yet (it may still be building)")
    return dict(sha=rel.get("target_commitish", ""), built=(rel.get("published_at") or "")[:16].replace("T", " "),
                url=asset["browser_download_url"], size=asset.get("size", 0), title=rel.get("name", ""))


def check():
    """a newer build than this one, or None"""
    lat = latest(); me = current()
    if not me.get("sha"): return None if not FROZEN else lat                # (an older build with no stamp: anything on GitHub is newer)
    return None if lat["sha"][:7] == me["sha"][:7] else lat


def folder():
    d = os.path.join(paths.HOME, "update"); os.makedirs(d, exist_ok=True); return d


def download(new, report=None, stop=None):
    """the new build's zip, downloaded (carrying on where it stopped) and unpacked into update/new. -> that folder"""
    d = folder(); z = os.path.join(d, ASSET); part = z + ".part"
    have = os.path.getsize(part) if os.path.exists(part) else 0
    req = urllib.request.Request(new["url"], headers={"User-Agent": "InstantEasel-updater", **({"Range": f"bytes={have}-"} if have else {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        if have and r.status != 206: have = 0
        total = (int(r.headers.get("Content-Length") or 0) + have) or new.get("size", 0)
        with open(part, "ab" if have else "wb") as f:
            got = have; t = 0
            while True:
                if stop is not None and stop.is_set(): raise RuntimeError("stopped")
                b = r.read(1 << 20)
                if not b: break
                f.write(b); got += len(b)
                if report and time.time() - t > 0.3: t = time.time(); report(f"Downloading the update: {got / 1e6:.0f} of {total / 1e6:.0f} MB", got / total if total else None)
    if new.get("size") and os.path.getsize(part) != new["size"]: raise RuntimeError("the download didn't finish (it carries on next time)")
    os.replace(part, z)
    out = os.path.join(d, "new"); shutil.rmtree(out, ignore_errors=True)
    report and report("Unpacking the update…", None)
    with zipfile.ZipFile(z) as f: f.extractall(out)
    if not os.path.exists(os.path.join(out, EXE)): raise RuntimeError(f"the update has no {EXE} in it")
    with open(os.path.join(out, "_ready.json"), "w") as f: json.dump(new, f)
    os.remove(z)
    return out


def _when(stamp): return str((stamp or {}).get("built") or "")[:16]       # "2026-11-24 21:49": sorts by time


def ready():
    """an update that's downloaded and waiting for a restart (dict), or None. Only one NEWER than this copy: a download left over from
    before (say this copy was put in by hand since) is older or the same, and is cleared away instead of put back over the newer one"""
    try:
        with open(os.path.join(folder(), "new", "_ready.json")) as f: n = json.load(f)
    except Exception: return None
    me = current()
    if me.get("sha") and (n.get("sha", "")[:7] == me["sha"][:7] or (_when(n) and _when(me) and _when(n) <= _when(me))):
        tidy(); return None
    return n


def tidy():
    """clear what an update leaves behind: the unpacked copy, the zip, a half-download from before. The app's folder stays one build big"""
    d = os.path.join(paths.HOME, "update")
    if not os.path.isdir(d): return
    shutil.rmtree(os.path.join(d, "new"), ignore_errors=True)
    for f in os.listdir(d):
        p = os.path.join(d, f)
        try:
            if f.endswith(".zip") or (f.endswith(".part") and time.time() - os.path.getmtime(p) > 3 * 86400): os.remove(p)
            elif os.path.isdir(p): shutil.rmtree(p, ignore_errors=True)
        except OSError: pass


def _log(msg):
    try:
        with open(os.path.join(_home_of_update(), "update", "update.log"), "a", encoding="utf-8") as f: f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except Exception: pass


def _home_of_update():
    """the app's real folder, seen from the new copy that runs from <app>/update/new"""
    return os.path.dirname(os.path.dirname(paths.HOME)) if os.path.basename(paths.HOME).lower() == "new" else paths.HOME


def _launch(exe, *args, cwd=None):
    """start a program on its own: it carries on after this app closes"""
    base = 0x00000008 | 0x00000200                                           # detached, its own process group
    for flags in (base | 0x01000000, base):                                  # (+ break away from this app's job, where Windows allows it)
        try: return subprocess.Popen([exe, *args], creationflags=flags, close_fds=True, cwd=cwd or os.path.dirname(exe))
        except OSError: continue
    raise RuntimeError(f"couldn't start {os.path.basename(exe)}")


def restart_into_update(app=None):
    """the new copy (in update/new) takes over: it waits for this app to close, puts itself in, and opens the app again"""
    if not FROZEN or sys.platform != "win32": raise RuntimeError("updating in place works in the Windows app (from the source, use git pull)")
    new = os.path.join(folder(), "new"); exe = os.path.join(new, EXE)
    if not os.path.exists(exe): raise RuntimeError("download the update first")
    try: os.remove(os.path.join(folder(), "update.log"))
    except OSError: pass
    _log(f"restarting into the update: {exe} (this copy is {os.getpid()})")
    _launch(exe, "--finish-update", str(os.getpid()))
    import threading
    t = threading.Timer(8, lambda: os._exit(0)); t.daemon = True; t.start()  # (in case anything holds the app open once its window is gone)
    if app is not None:
        try: app.after(150, lambda: app.quit_app(ask=False) if hasattr(app, "quit_app") else app.destroy())
        except Exception: pass


def _wait_for(pid, seconds=30):
    """wait until the old copy has closed (then end it if it's stuck)"""
    import ctypes
    k = ctypes.windll.kernel32; h = k.OpenProcess(0x00100000 | 0x0001, False, int(pid))   # SYNCHRONIZE | PROCESS_TERMINATE
    if not h: return True                                                     # (already gone)
    try:
        if k.WaitForSingleObject(h, int(seconds * 1000)) == 0: return True
        _log(f"the old copy ({pid}) was still open after {seconds} s: ending it"); k.TerminateProcess(h, 0)
        return k.WaitForSingleObject(h, 10000) == 0
    finally: k.CloseHandle(h)


def finish(pid):
    """run by the NEW copy from update/new: put the new program in place of the old one, then open it"""
    home = _home_of_update(); new = paths.HOME; ok = False
    _log(f"finishing: copying {new} -> {home}")
    try:
        _wait_for(pid); time.sleep(0.5)
        for attempt in range(40):                                             # (a virus scanner or Windows itself can hold a file a moment)
            try:
                old_int = os.path.join(home, "_internal")
                if os.path.isdir(old_int): shutil.rmtree(old_int)
                shutil.copytree(os.path.join(new, "_internal"), old_int)
                shutil.copy2(os.path.join(new, EXE), os.path.join(home, EXE))
                ok = True; break
            except (PermissionError, OSError) as e:
                if attempt % 5 == 0: _log(f"waiting for a file to be free ({e.__class__.__name__}: {e})")
                time.sleep(0.5)
        _log("copied the new version in" if ok else "COULDN'T put the update in: a file stayed in use. The old version opens; try again from Settings > Updates")
    except Exception as e: _log(f"FAILED: {e!r}")
    try: _launch(os.path.join(home, EXE), "--cleanup-update", cwd=home); _log("opened the app")
    except Exception as e: _log(f"couldn't open the app again: {e!r}")


def handle_args():
    """at start-up: True when this run was only the update's helper (it then quits). --cleanup-update tidies the update folder away"""
    if "--finish-update" in sys.argv:
        i = sys.argv.index("--finish-update"); finish(sys.argv[i + 1] if len(sys.argv) > i + 1 else 0); return True
    if "--cleanup-update" in sys.argv:
        import threading
        def tidy():
            for _ in range(30):
                time.sleep(1)
                try: shutil.rmtree(os.path.join(folder(), "new")); tidy(); _log("tidied the update folder away"); return
                except FileNotFoundError: tidy(); return
                except OSError: pass
        threading.Thread(target=tidy, daemon=True, name="update tidy").start()
        return False
    if FROZEN and os.path.basename(paths.HOME).lower() != "new":
        try: ready()                                                         # (clears a leftover that isn't newer)
        except Exception: pass
    return _apply_waiting()


def _apply_waiting():
    """an update downloaded but not put in (the app was quit instead of restarted, or the restart didn't take): it goes in now,
    before the window opens. True when the new copy has taken over (this run then quits). Three tries at most per update."""
    if not FROZEN or sys.platform != "win32" or os.path.basename(paths.HOME).lower() == "new": return False
    n = ready()
    if not n or (n.get("sha") and n["sha"][:7] == (current().get("sha") or "")[:7]): return False
    exe = os.path.join(folder(), "new", EXE); tries = os.path.join(folder(), "new", "_tries")
    try: count = int(open(tries).read().strip() or 0)
    except Exception: count = 0
    if count >= 3 or not os.path.exists(exe): return False
    try:
        with open(tries, "w") as f: f.write(str(count + 1))
        _log(f"putting in the waiting update at start-up (try {count + 1})")
        _launch(exe, "--finish-update", str(os.getpid())); return True
    except Exception as e: _log(f"couldn't start the waiting update: {e!r}"); return False
