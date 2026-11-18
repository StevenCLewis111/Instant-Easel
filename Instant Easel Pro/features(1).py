"""
features.py: the single list of everything Instant Easel does or will do, organized the way the menus are.
The app's menus and ROADMAP.md are both generated from this, so they can never disagree.
status: "built" | "partial" | "planned"     order: recommended build order (1 = next)     blank=True: an empty bordered page for now
"""
MENUS = [
 ("Images", "Make new images", [
   dict(name="Text to Image", status="partial", order=3, desc="Type what you want; it paints it.",
        options=["Prompt box with 'what I understood' and unknown words (built)",
                 "SHARED IMAGE SETTINGS PANEL, right side of Images, used by every Create tool (built):",
                 "   Model: Core (default) / My learned style (built); trained models appear here once Training > Models exists",
                 "   Art style: 19 styles in a thumbnail gallery (built): Painterly, Realism, Oil Painting, Watercolor, Pastel, Pencil Sketch, Black and White, Cartoon, Anime, Comic Book, Pop Art, Street Art, Pixel Art, Abstract, Impressionist, Stained Glass, Woodblock Print, Neon, Low Poly; style words in the prompt pick them too",
                 "   Aspect ratio: 2:3, 3:2, 1:1, 16:9, 9:16, original, painted at that shape (built)",
                 "   Next: cover and thumbnail presets: 21:9 wide cover, 4:5 and 3:4 vertical, 1:1 share card, 1280x720 thumbnail, 6x9 in book cover; 'make all sizes' from one image",
                 "   How many: 1, 4 (2x2) or 9 (3x3), click one to choose it (built)",
                 "   Starting image: upload / clear; guides colors in Text to Image, is the picture in Image to Image (built)",
                 "   Download all (built); Save per image (built)", "New variation (built)", "Next: your saved styles in Art style; trained models in Model"]),
   dict(name="Image to Image", status="built", order=0, desc="Repaint any picture, guided by words.",
        options=["Strength", "Art style, model, aspect, how many: from the shared Image settings panel", "Palette: keep, warm, night", "Mood words, night re-lighting, captions"]),
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
 ("Videos", "Make moving pictures (future)", [
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
 ("Chat", "Talk with it (future)", [
   dict(name="New Chat", status="planned", order=30, desc="Placeholder.", options=[], blank=True),
   dict(name="Chat History", status="planned", order=31, desc="Placeholder.", options=[], blank=True),
   dict(name="Chat Settings", status="planned", order=32, desc="Placeholder.", options=[], blank=True),
 ]),
 ("Code", "Code tools (future)", [
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
 ("Draw", "Draw and paint by hand (the whole page is the drawing studio)", [
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
 ("Training", "Teach it", [
   dict(name="Models", status="built", order=0, desc="Trained models on a shared Core: create, select, rename, train, versions, delete.",
        options=["Create: name, focus (Landscapes, Faces, Cartoons, Animals, Night scenes, Architecture, Custom), description; start empty or from another model",
                 "Select: the model Images paints with (also in Image settings > Model)", "Train: opens Learn from Images aimed at that model",
                 "Rename; Delete (with confirmation; the Core and other models are untouched)", "Versions: every training session saves one; roll back any time",
                 "Each model: its own images (deleted after learning), learned style, and words",
                 "Shared Core: painting knowledge, brushes, styles, words taught to all models, and every label correction (improves every model's guesses)"],
        notes="A model learns how things look (color, texture, brushwork, light). New kinds of subjects need a painter in the Core, which then serves every model."),
   dict(name="Learn from Images", status="built", order=0, desc="Images it learns from (guess + confirm), per subject. Images are deleted after learning.",
        options=["Add images", "Confirm labels", "Learn", "Cumulative: new learning blends into old, weighted by image count", "Fingerprints stop the same picture being learned twice",
                 "After learning, the app's copies are deleted (switch 'Keep copies' to keep them); your originals are never touched", "Dated profile versions in history/ (numbers only)"]),
   dict(name="Words", status="built", order=0, desc="Teach its vocabulary.", options=["Teach a word", "Words you've taught", "Test understanding"]),
 ]),
 ("Settings", "The app itself", [
   dict(name="General", status="built", order=0, desc="Save folder, file format and quality, auto-save, file names, start tab, confirm on quit.",
        options=["Save folder (change / open)", "File format PNG / JPEG / WebP and quality", "Auto-save every result into a dated folder", "File name pattern", "Open on start", "Confirm before quitting"]),
   dict(name="Generation Defaults", status="built", order=0, desc="What the Image settings start with; fixed or random seed.", options=["Model, art style, aspect, how many", "Seed: random or fixed", "Apply now"]),
   dict(name="Performance", status="built", order=0, desc="Speed vs quality.", options=["Editing preview size", "Image to Image working size", "Draw undo steps"]),
   dict(name="Display", status="built", order=0, desc="Fixed layout with scroll bars, window modes, text size, hints, splash.",
        options=["Fixed layout: panels never move or squeeze; scroll bars when the window is smaller", "Window mode: Windowed / Maximized / Full screen (F11, Esc)",
                 "Remember size and position (only if still on a connected screen); minimum size; reset window", "Sharp, consistent sizing at Windows display scaling",
                 "Text size Small / Normal / Large", "Show hints", "Startup splash"]),
   dict(name="Privacy & Data", status="built", order=0, desc="What stays on your PC; storage used; clear learned data; reset words.",
        options=["Works offline statement", "Keep training copies (default off)", "Storage used by category", "Open data folder", "Clear learned data", "Reset taught words", "Local error log"]),
   dict(name="AI Models", status="partial", order=5, desc="Built-in model runner (no separate programs): hardware, catalog, model files.",
        options=["Your PC: processor, memory, graphics card", "Use the graphics card (Vulkan)", "Models folder", "Catalog: Gemma 4 E4B, SDXL-class, FLUX.1 [schnell] with size and license; found / not installed",
                 "Add a model file", "Next: the built-in runner that loads and uses the models; downloads"],
        notes="Author's direction: native first; model files loaded by the app itself, no separate programs."),
   dict(name="Updates", status="built", order=0, desc="Check GitHub for a newer version; opt-in check at startup.", options=["Version", "Check now", "Check when the app opens (off by default)"]),
   dict(name="Shortcuts", status="built", order=0, desc="Every keyboard shortcut.", options=["Anywhere", "Text to Image", "Image to Image", "Draw studio", "Editing"]),
   dict(name="Backup & Reset", status="built", order=0, desc="Export / import settings, theme, words and learned style; reset all settings.", options=["Export backup", "Import backup", "Reset all settings"]),
   dict(name="Theme", status="built", order=0, desc="Look of the app.", options=["Border color", "Background color", "Panel opacity", "Build a theme from one color (Matching, Complementary, Split, Triadic)", "Reset"]),
   dict(name="About", status="built", order=0, desc="Logo, version, credits and open-source notes.", options=["Easel logo", "Version", "Credits", "Open-source notes and licenses"]),
   dict(name="Classic Tools", status="built", order=0, desc="Older tools: repaint book scenes, styles.", options=["Book scenes", "Styles"]),
 ]),
]

MODELS_DESIGN = """
## How models work (design)

**The Core** is shared by every model, and improved by every model:
- **Language:** the painting vocabulary, and every word taught in any model.
- **Painting knowledge:** composition, light and depth rules (`KNOWLEDGE.md`), the brushes and the subject painters (sky, mountains, rock, grass, figures…).
- **Learning methods:** how images are measured (palette, texture, brushwork, light and dark), the label guesser and its corrections, and the test suite.
- **When any model is trained,** anything general it teaches (new words, corrected guesses, better learning settings) goes into the Core, so every model benefits.

**A Model** is trained its own way to become its own thing:
- **Identity:** a name, a focus (faces, cartoons, animals, landscapes, night scenes…), a description and a cover image.
- **Its own training images,** labeled by subject.
- **Its own learned style:** palettes, textures, brushwork and light-and-dark structure, learned only from its images.
- **Its own words,** on top of the Core's (for example, "chibi" means something only in the cartoons model).
- **Its own defaults:** medium, palette, aspect ratio.
- **Versions** (like checkpoints): every training saves a version you can roll back to, with its test scores.

**In Training > Models:** create, select (the active model), rename or edit, delete (with confirmation), see its images, versions and scores.
**In Create:** pick which model paints.

**Honest limit:** a model learns *how things look* (color, texture, light, brushwork) from its images. Drawing a new *kind* of subject (animal bodies, cartoon faces) also needs a painter for that subject in the Core, and once it's added, every model can use it.
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
    import os; open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ROADMAP.md"), "w").write(roadmap_md()); print("ROADMAP.md written")
