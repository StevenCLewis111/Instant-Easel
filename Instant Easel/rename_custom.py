"""
rename_custom.py: give every picture in brand/icon/custom/ (and its folders) the "_ for a space" name the app looks for.
    "Soft Round.png" -> "Soft_Round.png",  "Special Brushes/" -> "Special_Brushes/"
Run it once from the app's folder (python rename_custom.py). Pictures already named that way are left alone; nothing is deleted.
"""
import os, sys

def main(root):
    base = os.path.join(root, "brand", "icon", "custom")
    if not os.path.isdir(base): print("no brand/icon/custom folder here:", base); return
    n = 0
    for d in sorted(os.listdir(base)):                                       # folders first
        src = os.path.join(base, d); dst = os.path.join(base, d.replace(" ", "_"))
        if os.path.isdir(src) and src != dst:
            if os.path.exists(dst):                                          # both spellings exist: move the files across
                for f in os.listdir(src):
                    if not os.path.exists(os.path.join(dst, f)): os.replace(os.path.join(src, f), os.path.join(dst, f))
                if not os.listdir(src): os.rmdir(src)
            else: os.replace(src, dst)
            n += 1; print("folder:", d, "->", os.path.basename(dst))
    for d, _, files in os.walk(base):
        for f in files:
            if " " in f:
                dst = os.path.join(d, f.replace(" ", "_"))
                if os.path.exists(dst): print("kept both (a file already has that name):", os.path.join(d, f)); continue
                os.replace(os.path.join(d, f), dst); n += 1; print("file:", f, "->", os.path.basename(dst))
    print(n, "renamed")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)))
