"""
shortcut.py: makes a desktop shortcut to Instant Easel Pro with its own icon (images/UI/App Icon/icon.ico). Windows only.
    python shortcut.py            (or Settings > General > Create desktop shortcut)
It points at InstantEaselPro.exe when the app is built, or at main.py (run without a console window) when it isn't.
"""
import os, sys, subprocess

import paths
def app_dir(): return paths.HOME
def bundle_dir(): return paths.APP

def make(name="Instant Easel Pro"):
    """-> path of the new shortcut. Raises with a plain message if it can't."""
    if sys.platform != "win32": raise RuntimeError("desktop shortcuts are made on Windows only")
    icon = paths.ui("App Icon", "icon.ico")                
    if getattr(sys, "frozen", False): target, args = sys.executable, ""
    else:
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        target, args = (pyw if os.path.exists(pyw) else sys.executable), f'"{os.path.join(app_dir(), "main.py")}"'
    ps = ("$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d '{n}.lnk'));"
          "$s.TargetPath='{t}'; $s.Arguments='{a}'; $s.WorkingDirectory='{w}'; $s.IconLocation='{i},0'; $s.Description='Instant Easel Pro'; $s.Save();"
          "Write-Output (Join-Path $d '{n}.lnk')").format(n=name, t=target.replace("'", "''"), a=args.replace("'", "''"), w=app_dir().replace("'", "''"), i=icon.replace("'", "''"))
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, text=True, timeout=20, creationflags=0x08000000)
    if r.returncode != 0: raise RuntimeError((r.stderr or r.stdout or "PowerShell couldn't make the shortcut").strip().splitlines()[-1])
    return r.stdout.strip()

if __name__ == "__main__":
    print("made", make())
