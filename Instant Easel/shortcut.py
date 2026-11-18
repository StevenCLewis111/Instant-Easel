"""
shortcut.py: makes a desktop shortcut to Instant Easel with its own icon (brand/icon/icon.ico). Windows only.
    python shortcut.py            (or Settings > General > Create desktop shortcut)
It points at InstantEasel.exe when the app is built, or at main.py (run without a console window) when it isn't.
"""
import os, sys, subprocess

def app_dir(): return os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
def bundle_dir(): return getattr(sys, "_MEIPASS", app_dir())

def make(name="Instant Easel"):
    """-> path of the new shortcut. Raises with a plain message if it can't."""
    if sys.platform != "win32": raise RuntimeError("desktop shortcuts are made on Windows only")
    icon = next((p for p in (os.path.join(d, "brand", sub, "icon.ico") for d in (bundle_dir(), app_dir()) for sub in ("icon", "")) if os.path.exists(p)),
                os.path.join(app_dir(), "brand", "icon", "icon.ico"))                  # brand/icon/icon.ico (older layout: brand/icon.ico)
    if getattr(sys, "frozen", False): target, args = sys.executable, ""
    else:
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        target, args = (pyw if os.path.exists(pyw) else sys.executable), f'"{os.path.join(app_dir(), "main.py")}"'
    ps = ("$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d '{n}.lnk'));"
          "$s.TargetPath='{t}'; $s.Arguments='{a}'; $s.WorkingDirectory='{w}'; $s.IconLocation='{i},0'; $s.Description='Instant Easel'; $s.Save();"
          "Write-Output (Join-Path $d '{n}.lnk')").format(n=name, t=target.replace("'", "''"), a=args.replace("'", "''"), w=app_dir().replace("'", "''"), i=icon.replace("'", "''"))
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, text=True, timeout=20, creationflags=0x08000000)
    if r.returncode != 0: raise RuntimeError((r.stderr or r.stdout or "PowerShell couldn't make the shortcut").strip().splitlines()[-1])
    return r.stdout.strip()

if __name__ == "__main__":
    print("made", make())
