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
 ("Editing", "Change an image (any picture, or one it made)", [
   dict(name="Light", status="built", order=1, desc="Lightroom-style light adjustments.",
        options=["Exposure", "Brightness", "Contrast", "Highlights", "Shadows", "Whites", "Blacks"]),
   dict(name="Color", status="built", order=1, desc="Color adjustments.",
        options=["Temperature (warm/cool)", "Tint (green/magenta)", "Hue", "Saturation", "Vibrance"]),
   dict(name="Curves", status="built", order=1, desc="Photoshop-style Curves: bend the light and each colour.",
        options=["RGB / Red / Green / Blue", "Click to add a point, drag it, drag it off (or right-click) to remove", "Presets: brighten, darken, more contrast, fade"]),
   dict(name="Levels", status="built", order=1, desc="Photoshop-style Levels: black point, midtones, white point.",
        options=["Input black / midtones / white over the picture's histogram", "Output black / white", "Auto"]),
   dict(name="Effects", status="built", order=1, desc="Finishing effects.",
        options=["Sharpness", "Clarity", "Vignette", "Grain", "Soft glow"]),
   dict(name="Filters", status="built", order=1, desc="One-click looks.",
        options=["Grayscale", "Sepia", "Warm film", "Cool film", "Faded", "High contrast", "Your saved looks"]),
   dict(name="Transform", status="built", order=2, desc="Shape and orientation.",
        options=["Crop: drag a box on the picture; ratio presets Free, 1:1, 2:3, 3:2, 4:5, 16:9, 9:16 (box keeps the shape); rule-of-thirds guides", "Rotate 90° left/right",
                 "Straighten -45° to +45° with automatic crop of the empty corners", "Flip horizontal/vertical", "Resize 25%-200%", "Runs before Light/Color/Effects; Save applies everything at full size"]),
   dict(name="History", status="built", order=0, desc="Undo, redo, every step by name, compare, reset, save as new / overwrite.",
        options=["Undo / Redo buttons on every Editing screen; Ctrl+Z / Ctrl+Y", "Every step listed by name (e.g. 'Exposure +20', 'Filter: sepia', 'Crop'); click to jump back",
                 "One slider drag = one step", "Compare before and after side by side", "Reset all (undoable)", "Save (on the bar above)"]),
 ]),
 ("Settings", "The app itself", [
   dict(name="Theme", status="built", order=0, desc="Border colour, background colour, panel opacity, one-colour themes.", options=[]),
   dict(name="General", status="built", order=0, desc="Saving pictures, quitting, desktop shortcut.", options=[]),
   dict(name="Display", status="built", order=0, desc="Window mode, text size, splash.", options=[]),
   dict(name="Pen & Tablet", status="built", order=0, desc="A drawing tablet's pen pressure: on / off, how it feels, its eraser end; a tester.", options=[]),
   dict(name="Shortcuts", status="built", order=0, desc="Every keyboard shortcut.", options=[]),
   dict(name="Backup & Reset", status="built", order=0, desc="Move your settings and theme to another PC; reset everything.", options=[]),
   dict(name="About", status="built", order=0, desc="Version and credits.", options=[]),
 ]),
]

TAB_ORDER = ["Drawing", "Editing", "Settings"]   # the tabs, left to right
OLD_TAB_NAMES = {"Draw": "Drawing"}
