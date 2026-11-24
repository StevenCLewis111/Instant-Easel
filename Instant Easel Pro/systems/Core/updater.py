"""
updater.py: updates in place, no more downloading the zip by hand.

Each build on GitHub stamps the commit it was made from into the app (build.json). The app compares that with the newest build on
the Releases page (the pro-latest / drawing-app-latest prerelease), downloads the new zip, and on restart a small helper waits for
the app to close, puts the new program files in (the .exe and its _internal folder), and opens it again.

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
PRO = True                                                                 # (this is Instant Easel Pro's copy)
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


def ready():
    """an update that's downloaded and waiting for a restart (dict), or None"""
    try:
        with open(os.path.join(folder(), "new", "_ready.json")) as f: return json.load(f)
    except Exception: return None


def restart_into_update(app=None):
    """hand over to the helper: it waits for this app to close, puts the new files in, and opens the app again"""
    if not FROZEN or sys.platform != "win32": raise RuntimeError("updating in place works in the Windows app (from the source, use git pull)")
    new = os.path.join(folder(), "new"); home = paths.HOME
    if not os.path.exists(os.path.join(new, EXE)): raise RuntimeError("download the update first")
    bat = os.path.join(folder(), "apply-update.bat"); log = os.path.join(folder(), "update.log")
    with open(bat, "w", encoding="utf-8") as f:
        f.write(f"""@echo off
rem Instant Easel's updater: waits for the app to close, puts the new program files in, opens it again.
:wait
tasklist /FI "PID eq {os.getpid()}" 2>nul | find "{os.getpid()}" >nul && (timeout /t 1 /nobreak >nul & goto wait)
robocopy "{new}\\_internal" "{home}\\_internal" /MIR /R:5 /W:1 /NFL /NDL /NJH /NJS /NP > "{log}"
copy /Y "{new}\\{EXE}" "{home}\\{EXE}" >> "{log}"
rmdir /S /Q "{new}"
start "" "{home}\\{EXE}"
del "%~f0"
""")
    flags = 0x00000008 | 0x00000200 | 0x08000000                              # (detached, its own group, no window)
    subprocess.Popen(["cmd", "/c", bat], creationflags=flags, close_fds=True, cwd=folder())
    if app is not None:
        try: app.after(200, getattr(app, "quit_app", app.destroy))          # (closes the way the window's X does: everything saved)
        except Exception: pass
