"""
features.py: the tabs and pages of Instant Easel (the drawing app), in the order they appear.
status: "built" | "partial" | "planned"
"""
MENUS = [
 ("Drawing", "Draw and paint by hand (the whole page is the drawing studio)", [
   dict(name="Draw", status="built", order=0, desc="A full drawing studio: paint by hand on a blank page or on any picture.",
        options=["Toolbar: New, Open, Save, Undo, Redo, Zoom -/+/Fit, Brush, Eraser, Eyedropper, Fill, Line, Rectangle, Ellipse, Text, Mirror",
                 "Brush library: every brush in brushes.py, grouped; each tile is a picture in images/UI/Brush Library",
                 "Layers: add, duplicate, delete, merge down, move up/down, show/hide, layer opacity, blend modes",
                 "Color: hue ring + saturation/brightness square, hex code, swatches, palettes, history, eyedropper",
                 "Canvas: zoom with the wheel, pan with the right mouse button; the view keeps its place when the window changes"]),
 ]),
 ("Settings", "The app itself", [
   dict(name="Theme", status="built", order=0, desc="Border colour, background colour, panel opacity, one-colour themes.", options=[]),
   dict(name="General", status="built", order=0, desc="Saving pictures, quitting, desktop shortcut.", options=[]),
   dict(name="Display", status="built", order=0, desc="Window mode, text size, splash.", options=[]),
   dict(name="Shortcuts", status="built", order=0, desc="Every keyboard shortcut.", options=[]),
   dict(name="Backup & Reset", status="built", order=0, desc="Move your settings and theme to another PC; reset everything.", options=[]),
   dict(name="About", status="built", order=0, desc="Version and credits.", options=[]),
 ]),
]

TAB_ORDER = ["Drawing", "Settings"]   # the tabs, left to right
OLD_TAB_NAMES = {"Draw": "Drawing"}
