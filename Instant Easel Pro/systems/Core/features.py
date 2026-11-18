"""
features.py: the single list of everything Instant Easel does or will do, organized the way the menus are.
The app's menus and ROADMAP.md are both generated from this, so they can never disagree.
status: "built" | "partial" | "planned"     order: recommended build order (1 = next)     blank=True: an empty bordered page for now
"""
MENUS = [
 ("AI Images", "Make new images", [
   dict(name="Text to Image", status="partial", order=3, desc="Type what you want; the image model paints it.",
        options=["Your words go through the core text model first, which turns them into a clear picture description",
                 "Pick which of your image models (Cartoon, Fashion, Nature...) to switch on", "Size, how many, seed", "Save / download"],
        notes="Download the image engine once (on this page or Settings > AI Models). Every picture goes into your Images folder."),
   dict(name="Image to Image", status="partial", order=4, desc="Repaint any picture, guided by words.",
        options=["Start from a picture (opens your Images folder)", "How much to change it", "Your image models"], notes="Uses the same image engine as Text to Image."),
   dict(name="Prompt to Edit", status="planned", order=10, desc="Edit an image by describing the change.",
        options=["'make it night', 'warmer', 'more clouds', 'remove the rocks', 'brighter'", "For its own paintings: re-paint with changed settings",
                 "For any picture: maps words to Edit adjustments", "Shows what it changed; one-click undo"]),
   dict(name="Multi-Image Fusion", status="planned", order=13, desc="Combine several images into one.",
        options=["Add 2-6 images", "Layout: blend, collage, sky from one + land from another", "Harmonize palettes so it looks like one painting", "Repaint the result in a medium"]),
   dict(name="Consistent Character", status="planned", order=15, desc="Characters that look the same in every creation.",
        options=["Character sheet: name, build, height, hair, clothing color, pose set", "Save, edit, delete characters", "Use by name in prompts ('Kael sitting on a hill')"],
        notes="Characters are drawn by the engine's figure painter, so they stay in its silhouette style."),
   dict(name="Depth to Image", status="planned", order=16, desc="Reuse the structure and composition of an image.",
        options=["Estimate near/far layers from an image", "Paint a new scene that follows those layers", "Strength of structure"],
        notes="True depth estimation needs a small offline AI model (optional add-on). Without it, depth is estimated from brightness, blur and position."),
   dict(name="Sketch to Image", status="planned", order=11, desc="Turn a sketch, line drawing or child's drawing into art.",
        options=["Upload a sketch or draw one on the canvas", "Fills enclosed shapes with color, then paints them in a medium", "Keep lines on/off", "Color hints by word"]),
   dict(name="Pose to Image", status="planned", order=14, desc="People in specific poses.",
        options=["Drag a stick-figure skeleton (head, arms, legs)", "Pose presets: standing, sitting, walking, pointing, embracing",
                 "The figure painter draws the pose in the scene"]),
   dict(name="Inpainting", status="planned", order=6, desc="Edit part of an image or remove unwanted things.",
        options=["Brush a mask over the area", "Remove: fill from the surroundings", "Replace: paint the area to match words", "Mask feathering"]),
   dict(name="Image Prompting", status="planned", order=12, desc="Carry the style and subject feel of a reference image into a creation.",
        options=["Add 1-3 reference images", "Style strength (palette, texture, brushwork)", "Uses the same learning as Train"]),
 ]),
 ("AI Videos", "Make moving pictures (future)", [
   dict(name="Text to Video", status="planned", order=20, desc="Type a scene; it paints it and brings it to life.",
        options=["Same prompt language as Text to Image", "Animated sky: clouds drift, the sun sets or the moon rises, light changes",
                 "Moving layers: far mountains, near mountains, ground and figures move at different speeds (depth)",
                 "Camera moves: slow push in, pan, rise", "Uses the shared Video settings (length, frame rate, aspect, style)"],
        notes="The engine paints scenes in layers, so it can animate its own scenes. New motion (people walking, creatures flying) needs animated subject painters or an optional AI video add-on."),
   dict(name="Image to Video", status="planned", order=21, desc="Bring any picture to life.",
        options=["Gentle camera moves: zoom, pan, tilt", "Moving sky or water (brush the area that moves)", "Parallax depth from estimated near/far layers", "Motion strength"]),
   dict(name="Motion Effects", status="planned", order=22, desc="Classic motion tricks.",
        options=["Pan and zoom (Ken Burns)", "Parallax layers", "Cinemagraph: one area moves, the rest stays still", "Light flicker, glow pulse, falling snow or rain, drifting stars"]),
   dict(name="Story Sequence", status="planned", order=23, desc="Several images or prompts become one video, like a book trailer.",
        options=["Storyboard of frames: each has a narration line, an image prompt (or image), and a duration that follows the narration",
                 "Number of frames; words per narration line", "Frame templates: Book page, Film, Full-bleed, Minimal (subtitles and titles laid out per size)",
                 "Narration voice: offline Piper TTS, or LocalAI speech; speed", "Transitions: cut, crossfade, fade through black, slide", "Background music",
                 "Storyboard sheet to approve BEFORE rendering", "Book trailer preset (uses the book's chapter list and illustrations)"],
        notes="Shaped by Pixelle-Video's storyboard model (Apache 2.0) and OpenMontage's approval gates (ideas only)."),
   dict(name="Video Style", status="planned", order=24, desc="Any of the 19 art styles on every frame.",
        options=["Pick from the style gallery", "Steady style (no flicker between frames)", "Style strength"]),
   dict(name="Loops & GIFs", status="planned", order=25, desc="Short shareable clips.",
        options=["Seamless loop", "Animated GIF (size and colors)", "Boomerang (forward then back)", "Clip length 2-10 s"]),
   dict(name="Video Edit", status="planned", order=26, desc="Basic editing of a clip.",
        options=["Trim start/end", "Speed and reverse", "Fade in/out", "Captions over time", "Add or replace music"]),
   dict(name="Video Settings", status="planned", order=27, desc="Shared panel for every Video tool (like Image settings).",
        options=["Length: 3, 5, 10, 15 s", "Frame rate: 12, 24, 30 fps", "Aspect: 16:9, 9:16, 1:1, 2:3, 21:9",
                 "Platform presets: YouTube 1920x1080, Shorts/Reels/TikTok 1080x1920, Instagram 1080x1080, Cinematic 2560x1080",
                 "Motion strength; camera move", "Art style; model", "Export: MP4, GIF, WebM",
                 "Self-check after rendering: black or broken frames, silent or clipping audio, 'slideshow risk' (too little motion)"],
        notes="MP4/WebM export needs a small video encoder bundled with the app (ffmpeg); GIF needs nothing extra."),
 ]),
 ("AI Chat", "Talk with it (future)", [
   dict(name="New Chat", status="planned", order=30, desc="Placeholder.", options=[], blank=True),
   dict(name="Chat History", status="planned", order=31, desc="Placeholder.", options=[], blank=True),
   dict(name="Chat Settings", status="planned", order=32, desc="Placeholder.", options=[], blank=True),
 ]),
 ("AI Coding", "Code tools (future)", [
   dict(name="Code Editor", status="planned", order=33, desc="Placeholder.", options=[], blank=True),
   dict(name="Run", status="planned", order=34, desc="Placeholder.", options=[], blank=True),
   dict(name="Snippets", status="planned", order=35, desc="Placeholder.", options=[], blank=True),
 ]),
 ("Editing", "Change an image (any picture, or one it made)", [
   dict(name="Light", status="built", order=1, desc="Lightroom-style light adjustments.",
        options=["Exposure", "Brightness", "Contrast", "Highlights", "Shadows", "Whites", "Blacks"]),
   dict(name="Color", status="built", order=1, desc="Color adjustments.",
        options=["Temperature (warm/cool)", "Tint (green/magenta)", "Hue", "Saturation", "Vibrance"]),
   dict(name="Effects", status="built", order=1, desc="Finishing effects.",
        options=["Sharpness", "Clarity", "Vignette", "Grain", "Soft glow"]),
   dict(name="Filters", status="built", order=1, desc="One-click looks.",
        options=["Grayscale", "Sepia", "Warm film", "Cool film", "Faded", "High contrast", "Your saved looks"]),
   dict(name="Transform", status="built", order=2, desc="Shape and orientation.",
        options=["Crop: drag a box on the picture; ratio presets Free, 1:1, 2:3, 3:2, 4:5, 16:9, 9:16 (box keeps the shape); rule-of-thirds guides", "Rotate 90° left/right",
                 "Straighten -45° to +45° with automatic crop of the empty corners", "Flip horizontal/vertical", "Resize 25%-200%", "Runs before Light/Color/Effects; Save applies everything at full size"]),
   dict(name="AI Tools", status="planned", order=7, desc="Bigger changes.",
        options=["Remove background (built-in cut-out; better with optional AI add-on)", "Expand image (paint beyond the edges)",
                 "Upscale 2x/4x", "Creative upscale (adds painted detail)", "Fix faces (needs optional AI add-on)", "Prompt to edit (same as Create)"],
        notes="Remove background, expand and upscale can be built into the engine. Fix faces needs a face-restoration AI model run offline as an add-on."),
   dict(name="History", status="built", order=0, desc="Undo, redo, every step by name, compare, reset, save as new / overwrite.",
        options=["Undo / Redo buttons on every Editing screen; Ctrl+Z / Ctrl+Y", "Every step listed by name (e.g. 'Exposure +20', 'Filter: sepia', 'Crop'); click to jump back",
                 "One slider drag = one step", "Compare original and current side by side", "Reset to original (undoable)", "Save as new; Overwrite original (with confirmation)"]),
 ]),
 ("Drawing", "Draw and paint by hand (the whole page is the drawing studio)", [
   dict(name="Draw", status="built", order=0, desc="A full drawing studio: paint by hand on a blank page, the last created image, or any picture.",
        options=["Toolbar: Undo, Redo, Zoom -/+/Fit, Brush, Eraser, Eyedropper, Fill, Line, Rectangle, Ellipse, Text, Mirror symmetry",
                 "Brush library: all 45 brushes as live stroke previews, grouped; brush properties: size (1-300), opacity, preview stroke",
                 "Brush library sections (brush_catalog.py): Brushes, Pens, Blending, Blurring, Sharpen, Special Effects, Stamps & Icons, Layers & FX Brushes, "
                 "Texture Brushes, More brushes; tools not built yet show a drawn preview marked SOON",
                 "Next: Blending (smudge, blend, soften, mix), Blurring (gaussian, motion, radial, zoom), Sharpen (unsharp mask, high pass, edge enhance, detail), "
                 "Special Effects (dodge, burn, saturation, hue shift, noise, pixelate), Stamps (25 icons), FX (glow, outline, shadow, inner shadow, outer glow, neon), Textures (canvas, fabric, brick, metal, paper, clouds)",
                 "Layers: add, duplicate, delete, merge down, move up/down, show/hide, layer opacity, blend modes (normal, multiply, screen, overlay)",
                 "Color: hue ring + saturation/brightness square, hex code, color history, eyedropper",
                 "Canvas: zoom with the wheel, pan with the right mouse button; only the visible part is redrawn",
                 "New, Open, Use last created, Save, Send to Editing", "Shortcuts: B E I G L T, [ ] size, Ctrl+Z / Ctrl+Y",
                 "Next: selection and move, brush presets you can save, pressure from a pen tablet, layer thumbnails"])]),
 ("AI Training", "Teach it", [
   dict(name="Image Learning", status="partial", order=5, desc="Your image models (Cartoon, Fashion, Nature...), each with its own pictures, step by step.", options=[]),
   dict(name="Video Learning", status="planned", order=22, desc="Teach it movement from short clips (needs a 16 GB+ graphics card to train).", options=[]),
   dict(name="Chat Learning", status="built", order=0, desc="Teach it how to answer: examples, a check set, training, testing; a library for facts.", options=[]),
   dict(name="Coding Learning", status="built", order=0, desc="Teach it to code your way from permitted, clean code and your examples.", options=[]),
   dict(name="Image Scraper", status="built", order=0, hidden=True, parent="Image Learning", desc="Find pictures on Google Images to learn from.", options=[]),
   dict(name="Pictures", status="built", order=0, hidden=True, parent="Image Learning", desc="The active image model's pictures and their review.", options=[]),
 ]),
 ("Settings", "The app itself", [
   dict(name="General", status="built", order=0, desc="Save folder, file format and quality, auto-save, file names, start tab, confirm on quit.",
        options=["Save folder (change / open)", "File format PNG / JPEG / WebP and quality", "Auto-save every result into a dated folder", "File name pattern", "Open on start", "Confirm before quitting"]),
   dict(name="Performance", status="built", order=0, desc="Speed vs quality.", options=["Editing preview size", "Image to Image working size", "Draw undo steps"]),
   dict(name="Display", status="built", order=0, desc="Fixed layout with scroll bars, window modes, text size, hints, splash.",
        options=["Fixed layout: panels never move or squeeze; scroll bars when the window is smaller", "Window mode: Windowed / Maximized / Full screen (F11, Esc)",
                 "Remember size and position (only if still on a connected screen); minimum size; reset window", "Sharp, consistent sizing at Windows display scaling",
                 "Text size Small / Normal / Large", "Show hints", "Startup splash"]),
   dict(name="Privacy & Data", status="built", order=0, desc="What stays on your PC; storage used; clear learned data; reset words.",
        options=["Works offline statement", "Keep training copies (default off)", "Storage used by category", "Open data folder", "Clear learned data", "Reset taught words", "Local error log"]),
   dict(name="AI Models", status="partial", order=1, desc="The core text model (Qwen3.5 4B or 9B, switchable) and each AI tab's own model.",
        options=["Core text model: Qwen3.5 4B or 9B, download, start, stop, switch any time", "AI Chat: the core model", "AI Coding: the core model or Qwen2.5 Coder 7B",
                 "AI Images: Stable Diffusion 1.5 / XL / your own file (engine being built next)", "AI Videos: needs a 16 GB+ graphics card"]),
   dict(name="Updates", status="built", order=0, desc="Check GitHub for a newer version; opt-in check at startup.", options=["Version", "Check now", "Check when the app opens (off by default)"]),
   dict(name="Shortcuts", status="built", order=0, desc="Every keyboard shortcut.", options=["Anywhere", "Text to Image", "Image to Image", "Draw studio", "Editing"]),
   dict(name="Backup & Reset", status="built", order=0, desc="Export / import settings, theme, words and learned style; reset all settings.", options=["Export backup", "Import backup", "Reset all settings"]),
   dict(name="Theme", status="built", order=0, desc="Look of the app.", options=["Border color", "Background color", "Panel opacity", "Build a theme from one color (Matching, Complementary, Split, Triadic)", "Reset"]),
   dict(name="About", status="built", order=0, desc="Logo, version, credits and open-source notes.", options=["Easel logo", "Version", "Credits", "Open-source notes and licenses"]),
 ]),
]

TAB_ORDER = ["AI Images", "AI Videos", "AI Chat", "AI Coding", "AI Training", "Drawing", "Editing", "Settings"]   # the tabs, left to right
MENUS = sorted(MENUS, key=lambda m: TAB_ORDER.index(m[0]) if m[0] in TAB_ORDER else len(TAB_ORDER))
OLD_TAB_NAMES = {"Images": "AI Images", "Videos": "AI Videos", "Chat": "AI Chat", "Code": "AI Coding", "Training": "AI Training", "Draw": "Drawing"}

MODELS_DESIGN = """
## How the models fit together (design)

**One core text model** (Qwen3.5 4B or 9B, switchable in Settings > AI Models) understands you in every AI tab. It runs on this PC
through llama.cpp, which reaches Intel Arc, AMD and NVIDIA cards through Vulkan.

**Each tab can add its own model** on top of the core, for what that tab makes:
- AI Chat: the core model.
- AI Coding: the core model, or a coding model (Qwen2.5 Coder 7B).
- AI Images: an image model (Stable Diffusion 1.5 for a 6 GB card). Your words go through the core model first.
- AI Videos: a video model (needs a 16 GB+ card).

**Training** has a side button per area (Image, Video, Chat, Coding), each with the steps that suit it.
- Image Learning has one more layer: your own image models (Cartoon, Fashion, Nature...). Each is trained on its own pictures, as a
  small add-on (LoRA) on top of the image model.
- Chat and Coding learn from examples and a library now. Fine-tuning the model itself needs a 12 GB+ graphics card.
"""

def roadmap_md():
    icon = {"built": "✅ built", "partial": "🟡 partial", "planned": "⬜ planned"}
    out = ["# Instant Easel: roadmap and feature tracker", "", "Generated from `features.py` (the same list the app's menus use).", "",
           "## Build order", "", "| # | Feature | Menu | Status |", "|---|---|---|---|"]
    todo = sorted([(f["order"], m, f) for m, _, fs in MENUS for f in fs if f["status"] != "built"], key=lambda x: x[0])
    for o, m, f in todo: out.append(f"| {o} | {f['name']} | {m} | {icon[f['status']]} |")
    for m, desc, fs in MENUS:
        out += ["", f"## {m}: {desc}"]
        for f in fs:
            out += ["", f"### {f['name']}  ({icon[f['status']]})", f"{f['desc']}", ""] + [f"- {o}" for o in f["options"]]
            if f.get("notes"): out += ["", f"*Note:* {f['notes']}"]
    return "\n".join(out) + "\n" + MODELS_DESIGN

if __name__ == "__main__":
    import os; import paths; open(os.path.join(paths.APP, "docs", "ROADMAP.md"), "w").write(roadmap_md()); print("ROADMAP.md written")
