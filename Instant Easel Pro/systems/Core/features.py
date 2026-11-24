"""
features.py: the single list of everything Instant Easel Pro does or will do, organized the way the menus are.
The app's menus and ROADMAP.md are both generated from this, so they can never disagree.
status: "built" | "partial" | "planned"     order: recommended build order (1 = next)     blank=True: an empty bordered page for now
"""
MENUS = [
 ("AI Images", "Make new images", [
   dict(name="Text to Image", status="built", order=3, desc="Type what you want, pick a style; the picture model paints it.",
        options=["The core text model can write a fuller description first, tuned to the picture model (sentences for Z-Image / FLUX.2, tags for SD)",
                 "Style: built-in (Realistic photo, Cinematic, Portrait, Black & white, Vintage, Cartoon, Anime, Comic book, Storybook, Watercolor, Oil, Digital painting, Pencil, Line art, 3D, Pixel art, Fantasy, Neon, Minimal) or your own models", "Sizes: square, portrait, tall, phone, landscape, wide, cinema", "How many (painted in one run), quality, upscale 2x / 4x",
                 "Leave out and follow my words (Stable Diffusion; Z-Image and FLUX.2 follow the words as written)", "Seed; a rough live preview while it paints",
                 "Results: upscale, vary, edit, fix a part, use as a start / reference / character", "Words, seed and settings saved inside each PNG"],
        notes="Download the image engine and a picture model once (here or Settings > AI Models). Every picture goes into your Images folder."),
   dict(name="Image to Image", status="built", order=4, desc="Repaint a picture, guided by words and a style.",
        options=["Start from a picture (opens your Images folder; phone photos stand the right way up)", "Change: vary a little, some, a lot, almost new",
                 "Works at the picture's own shape", "Style, seed, how many, upscale"]),
   dict(name="Prompt to Edit", status="built", order=10, desc="Describe one change; only that changes.",
        options=["'make it night', 'remove the man on the left', 'turn the car red', 'add snow'", "The rest of the picture stays as it was",
                 "Style as an edit: 'make it look like a watercolour'", "Uses FLUX.2 Klein 4B (Settings > AI Models > Image edits)"]),
   dict(name="Multi-Image Fusion", status="built", order=13, desc="Combine 2 to 4 pictures into one.",
        options=["Up to 4 pictures; say which picture each thing comes from", "Any size and style", "Uses FLUX.2 Klein 4B"],
        notes="Simple combinations work best with the 4B model."),
   dict(name="Consistent Character", status="built", order=15, desc="The same character in every scene.",
        options=["Characters: name, 1-4 pictures, a few words about them", "New, add a picture, delete; make one from any result", "Any scene, size and style",
                 "Uses FLUX.2 Klein 4B with their pictures; words only without it"]),
   dict(name="Depth to Image", status="built", order=16, desc="Keep a picture's layout and shapes; paint something new into them.",
        options=["Keep its outlines (edge guide)", "A depth map you have (depth guide)", "Its layout (FLUX.2 Klein)", "How closely: loosely, normal, exactly"],
        notes="The guides work with Stable Diffusion 1.5 and download once (0.7 GB each)."),
   dict(name="Sketch to Image", status="built", order=11, desc="Turn a sketch, line drawing or child's drawing into art.",
        options=["Use my latest drawing or choose any sketch", "Follow my lines exactly (scribble guide), keep my lines, balanced, free",
                 "Style: built-in (Realistic photo, Cinematic, Portrait, Black & white, Vintage, Cartoon, Anime, Comic book, Storybook, Watercolor, Oil, Digital painting, Pencil, Line art, 3D, Pixel art, Fantasy, Neon, Minimal) or your own models", "Optional words for what it is"]),
   dict(name="Pose to Image", status="built", order=14, desc="People in exact poses.",
        options=["Stick figure: drag the joints; right-drag moves it; the mouse wheel sizes it; mirror", "Poses: standing, arms up, waving, hands on hips, walking, running, sitting, jumping, kneeling",
                 "Follow the pose: loosely, normal, exactly", "Uses the pose guide with Stable Diffusion 1.5"]),
   dict(name="Inpainting", status="built", order=6, desc="Change or remove part of a picture; extend it past its edges.",
        options=["Brush over the area (left-drag), rub out (right-drag), brush size, clear", "Remove: leave the words empty", "Replace: say what goes there",
                 "Detail: just the brushed part at full size (sharper) or the whole picture", "Extend left / right / top / bottom / all (outpainting)",
                 "Soft edges; the rest stays exactly as it was; the result stays in the pad to keep fixing"]),
   dict(name="Image Prompting", status="built", order=12, desc="Carry the style and feel (or subject) of reference pictures into a new picture.",
        options=["1-4 reference pictures", "Take: style and feel, subject, or both", "Uses FLUX.2 Klein 4B"]),
 ]),
 ("AI Videos", "Make short videos with Wan 2.2", [
   dict(name="Text to Video", status="built", order=20, desc="Type a scene and what moves; Wan 2.2 5B makes it. Fast or Slow (for smaller cards).",
        options=["Same prompt language as Text to Image", "Animated sky: clouds drift, the sun sets or the moon rises, light changes",
                 "Moving layers: far mountains, near mountains, ground and figures move at different speeds (depth)",
                 "Camera moves: slow push in, pan, rise", "Uses the shared Video settings (length, frame rate, aspect, style)"],
        notes="The engine paints scenes in layers, so it can animate its own scenes. New motion (people walking, creatures flying) needs animated subject painters or an optional AI video add-on."),
   dict(name="Image to Video", status="built", order=21, desc="Bring any picture to life: it's the first frame, your words say what moves.",
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
 ("AI Chat", "Talk with it", [
   dict(name="Chats", status="built", order=0, desc="Conversations with memory: your rules, each chat's memory, a running summary, notes, a library and the web.",
        options=["Your rules (every chat) and each chat's memory, always loaded", "Older messages compressed into a summary, still searchable",
                 "'remember: ...' keeps a note", "Library of your documents", "Web search: off, when needed, always", "Save answers to your chats folder"]),
 ]),
 ("AI Coding", "Code with it", [
   dict(name="Projects", status="built", order=0, desc="Coding projects with layered memory, so a small model can handle a big project over many sessions.",
        options=["Your rules (every project), per user", "Project memory: what it does, rules, never-do, what to look for, commands",
                 "Running summary + every message searchable", "Notes it keeps; memory updates you approve", "Project library: your code and docs, indexed",
                 "Web search when it needs current information", "Save code to your code folder"]),
   dict(name="Code Editor", status="planned", order=33, desc="Edit the project's files with the AI beside you.", options=[]),
   dict(name="Run", status="planned", order=34, desc="Run the code and feed errors back to the AI. (Checking that code compiles, and fixing it first, is already in Projects.)", options=[]),
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
   dict(name="AI Tools", status="planned", order=7, desc="Bigger changes.",
        options=["Remove background (built-in cut-out; better with optional AI add-on)", "Expand image (paint beyond the edges)",
                 "Upscale 2x/4x", "Creative upscale (adds painted detail)", "Fix faces (needs optional AI add-on)", "Prompt to edit (same as Create)"],
        notes="Remove background, expand and upscale can be built into the engine. Fix faces needs a face-restoration AI model run offline as an add-on."),
   dict(name="History", status="built", order=0, desc="Undo, redo, every step by name, compare, reset, save as new / overwrite.",
        options=["Undo / Redo buttons on every Editing screen; Ctrl+Z / Ctrl+Y", "Every step listed by name (e.g. 'Exposure +20', 'Filter: sepia', 'Crop'); click to jump back",
                 "One slider drag = one step", "Compare before and after side by side", "Reset all (undoable)", "Save (on the bar above)"]),
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
   dict(name="Image Learning", status="partial", order=5, desc="Your image models (a category of things, or a look), each with its own things, pictures and captions, step by step.", options=[]),
   dict(name="Video Learning", status="planned", order=22, desc="Teach it movement from short clips (needs a 16 GB+ graphics card to train).", options=[]),
   dict(name="Chat Learning", status="built", order=0, desc="Teach it how to answer: examples, a check set, training, testing; a library for facts.", options=[]),
   dict(name="Coding Learning", status="built", order=0, desc="Teach it to code your way from permitted, clean code and your examples.", options=[]),
   dict(name="Image Scraper", status="built", order=0, hidden=True, parent="Image Learning", desc="Find pictures on Google Images to learn from.", options=[]),
   dict(name="Pictures", status="built", order=0, hidden=True, parent="Image Learning", desc="The active image model's pictures and their review.", options=[]),
   dict(name="Things to learn", status="built", order=0, hidden=True, parent="Image Learning", desc="Each thing an image model learns: its name, group, what it looks like; Look it up; captions.", options=[]),
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
   dict(name="AI Models", status="built", order=1, desc="This PC's check, and each AI's model: the best that fits first, never one too big.",
        options=["Your PC: processor, cores / threads, memory, graphics card, power", "Core text model and each tab's model", "AI Images: Z-Image Turbo / FLUX.2 Klein / SD 1.5 / XL / your file",
                 "Image edits: FLUX.2 Klein 4B", "AI Videos: Wan 2.2 5B (Fast on 16 GB+ cards, Slow on 6 GB+ with 24 GB PC memory)"]),
   dict(name="AI Images", status="built", order=1, desc="How the image generator works: defaults, preview, speed, add-ons.",
        options=["Default style and size", "Live preview", "Speed boost", "Sharper Stable Diffusion (second pass)", "Upscale every picture",
                 "Fuller descriptions", "Stop a stuck run after N minutes", "Add-ons: upscalers and guides (download / remove)"]),
   dict(name="AI Storage", status="built", order=0, desc="Give the AI its own drive; each AI gets its own portion.",
        options=["Choose the AI drive (everything moves there)", "Each AI's portion with used / budget", "Adding stops politely when a portion is full"]),
   dict(name="Download Everything", status="built", order=0, desc="One download of every engine, model (every size, even ones for a bigger PC), add-on, the video model and the code checkers.", options=[]),
   dict(name="Style Add-ons", status="built", order=0, desc="Ready-made style add-ons, each switched on or off, and your own from a link, for any picture model.", options=[]),
   dict(name="Updates", status="built", order=0, desc="Check GitHub for a newer version; opt-in check at startup.", options=["Version", "Check now", "Check when the app opens (off by default)"]),
   dict(name="Code Languages", status="built", order=0, desc="Switch AI Coding's languages on or off; each one's profile, library and checker.", options=[]),
   dict(name="Drawing AI", status="built", order=0, desc="Download the Drawing tab's AI models (any or all), remove them, or add your own.", options=[]),
   dict(name="Pen & Tablet", status="built", order=0, desc="A drawing tablet's pen pressure: on / off, how it feels, its eraser end; a tester.", options=[]),
   dict(name="Shortcuts", status="built", order=0, desc="Every keyboard shortcut.", options=["Anywhere", "Text to Image", "Image to Image", "Draw studio", "Editing"]),
   dict(name="Backup & Reset", status="built", order=0, desc="Export / import settings, theme, words and learned style; reset all settings.", options=["Export backup", "Import backup", "Reset all settings"]),
   dict(name="Theme", status="built", order=0, desc="Look of the app.", options=["Border color", "Background color", "Panel opacity", "Build a theme from one color (Matching, Complementary, Split, Triadic)", "Reset"]),
   dict(name="About", status="built", order=0, desc="Logo, version, credits and open-source notes.", options=["Easel logo", "Version", "Credits", "Open-source notes and licenses"]),
 ]),
]

TAB_ORDER = ["AI Images", "AI Videos", "AI Chat", "AI Coding", "AI Training", "Drawing", "Editing", "Settings"]   # the tabs, left to right
MENUS = sorted(MENUS, key=lambda m: TAB_ORDER.index(m[0]) if m[0] in TAB_ORDER else len(TAB_ORDER))
def visible_menus(pc=None):
    """the menus this PC can use: a tab (or page) whose AI needs more than the PC has (AI Videos on a small graphics card) isn't shown.
    See catalog.hidden_tabs; the PC check is hardware.py"""
    try:
        import catalog; tabs, pages = catalog.hidden_tabs(pc)
    except Exception: return MENUS
    return [(m, d, [f for f in fs if f["name"] not in pages]) for m, d, fs in MENUS if m not in tabs]

OLD_TAB_NAMES = {"Images": "AI Images", "Videos": "AI Videos", "Chat": "AI Chat", "Code": "AI Coding", "Training": "AI Training", "Draw": "Drawing"}

MODELS_DESIGN = """
## How the models fit together (design)

**One core text model** (Qwen3.5 4B or 9B, switchable in Settings > AI Models) understands you in every AI tab. It runs on this PC
through llama.cpp, which reaches Intel Arc, AMD and NVIDIA cards through Vulkan.

**Each tab can add its own model** on top of the core, for what that tab makes:
- AI Chat: the core model.
- AI Coding: the core model, or a coding model (Qwen2.5 Coder 7B).
- AI Images: an image model (Stable Diffusion 1.5 for a 6 GB card). Your words go through the core model first.
- AI Videos: Wan 2.2 5B; Fast on a 16 GB+ card, Slow (model in PC memory) on smaller ones.

**Training** has a side button per area (Image, Video, Chat, Coding), each with the steps that suit it.
- Image Learning has one more layer: your own image models (Cartoon, Fashion, Nature...). Each is trained on its own pictures, as a
  small add-on (LoRA) on top of the image model.
- Chat and Coding learn from examples and a library now. Fine-tuning the model itself needs a 12 GB+ graphics card.
"""

def roadmap_md():
    icon = {"built": "✅ built", "partial": "🟡 partial", "planned": "⬜ planned"}
    out = ["# Instant Easel Pro: roadmap and feature tracker", "", "Generated from `features.py` (the same list the app's menus use).", "",
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
