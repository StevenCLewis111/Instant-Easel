# Instant Easel Pro: roadmap and feature tracker

Generated from `features.py` (the same list the app's menus use).

## Build order

| # | Feature | Menu | Status |
|---|---|---|---|
| 1 | AI Models | Settings | 🟡 partial |
| 3 | Text to Image | AI Images | 🟡 partial |
| 4 | Image to Image | AI Images | 🟡 partial |
| 5 | Image Learning | AI Training | 🟡 partial |
| 6 | Inpainting | AI Images | 🟡 partial |
| 7 | AI Tools | Editing | ⬜ planned |
| 10 | Prompt to Edit | AI Images | ⬜ planned |
| 11 | Sketch to Image | AI Images | 🟡 partial |
| 12 | Image Prompting | AI Images | ⬜ planned |
| 13 | Multi-Image Fusion | AI Images | ⬜ planned |
| 14 | Pose to Image | AI Images | ⬜ planned |
| 15 | Consistent Character | AI Images | ⬜ planned |
| 16 | Depth to Image | AI Images | ⬜ planned |
| 20 | Text to Video | AI Videos | ⬜ planned |
| 21 | Image to Video | AI Videos | ⬜ planned |
| 22 | Motion Effects | AI Videos | ⬜ planned |
| 22 | Video Learning | AI Training | ⬜ planned |
| 23 | Story Sequence | AI Videos | ⬜ planned |
| 24 | Video Style | AI Videos | ⬜ planned |
| 25 | Loops & GIFs | AI Videos | ⬜ planned |
| 26 | Video Edit | AI Videos | ⬜ planned |
| 27 | Video Settings | AI Videos | ⬜ planned |
| 33 | Code Editor | AI Coding | ⬜ planned |
| 34 | Run | AI Coding | ⬜ planned |

## AI Images: Make new images

### Text to Image  (🟡 partial)
Type what you want; the image model paints it.

- Your words go through the core text model first, which turns them into a clear picture description
- Pick which of your image models (Cartoon, Fashion, Nature...) to switch on
- Size, how many, quality
- Leave out (what you don't want in it)
- Follow my words: loosely, normal, closely
- Seed: random or a number; every result shows its seed with Use this seed, to change one thing at a time
- The words, seed and settings saved inside each PNG
- Remembers the last settings

*Note:* Download the image engine once (on this page or Settings > AI Models). Every picture goes into your Images folder.

### Image to Image  (🟡 partial)
Repaint any picture, guided by words.

- Start from a picture (opens your Images folder)
- How much to change it
- Works at the picture's own shape
- Leave out, follow my words, seed (as Text to Image)
- Your image models

*Note:* Uses the same image engine as Text to Image.

### Prompt to Edit  (⬜ planned)
Edit an image by describing the change.

- 'make it night', 'warmer', 'more clouds', 'remove the rocks', 'brighter'
- For its own paintings: re-paint with changed settings
- For any picture: maps words to Edit adjustments
- Shows what it changed; one-click undo

### Multi-Image Fusion  (⬜ planned)
Combine several images into one.

- Add 2-6 images
- Layout: blend, collage, sky from one + land from another
- Harmonize palettes so it looks like one painting
- Repaint the result in a medium

### Consistent Character  (⬜ planned)
Characters that look the same in every creation.

- Character sheet: name, build, height, hair, clothing color, pose set
- Save, edit, delete characters
- Use by name in prompts ('Kael sitting on a hill')

*Note:* Characters are drawn by the engine's figure painter, so they stay in its silhouette style.

### Depth to Image  (⬜ planned)
Reuse the structure and composition of an image.

- Estimate near/far layers from an image
- Paint a new scene that follows those layers
- Strength of structure

*Note:* True depth estimation needs a small offline AI model (optional add-on). Without it, depth is estimated from brightness, blur and position.

### Sketch to Image  (🟡 partial)
Turn a sketch, line drawing or child's drawing into art.

- Use my latest drawing (from the Drawing tab) or choose any sketch
- Style: painting, watercolor, oil, cartoon, storybook, photo, pencil
- Drawing: keep my lines, balanced, free
- Optional words for what it is ('a red dragon on a hill')
- Leave out, follow my words, seed

*Note:* Uses the same image engine as Text to Image.

### Pose to Image  (⬜ planned)
People in specific poses.

- Drag a stick-figure skeleton (head, arms, legs)
- Pose presets: standing, sitting, walking, pointing, embracing
- The figure painter draws the pose in the scene

### Inpainting  (🟡 partial)
Edit part of an image or remove unwanted things.

- Brush over the area (left-drag), rub out (right-drag), brush size, clear
- Remove: leave the words empty and it fills from the surroundings
- Replace: say what goes there
- New part: blend in, repaint, fully new
- Soft edges; the rest of the picture stays exactly as it was, at full size

*Note:* Uses the same image engine as Text to Image.

### Image Prompting  (⬜ planned)
Carry the style and subject feel of a reference image into a creation.

- Add 1-3 reference images
- Style strength (palette, texture, brushwork)
- Uses the same learning as Train

## AI Videos: Make moving pictures (future)

### Text to Video  (⬜ planned)
Type a scene; it paints it and brings it to life.

- Same prompt language as Text to Image
- Animated sky: clouds drift, the sun sets or the moon rises, light changes
- Moving layers: far mountains, near mountains, ground and figures move at different speeds (depth)
- Camera moves: slow push in, pan, rise
- Uses the shared Video settings (length, frame rate, aspect, style)

*Note:* The engine paints scenes in layers, so it can animate its own scenes. New motion (people walking, creatures flying) needs animated subject painters or an optional AI video add-on.

### Image to Video  (⬜ planned)
Bring any picture to life.

- Gentle camera moves: zoom, pan, tilt
- Moving sky or water (brush the area that moves)
- Parallax depth from estimated near/far layers
- Motion strength

### Motion Effects  (⬜ planned)
Classic motion tricks.

- Pan and zoom (Ken Burns)
- Parallax layers
- Cinemagraph: one area moves, the rest stays still
- Light flicker, glow pulse, falling snow or rain, drifting stars

### Story Sequence  (⬜ planned)
Several images or prompts become one video, like a book trailer.

- Storyboard of frames: each has a narration line, an image prompt (or image), and a duration that follows the narration
- Number of frames; words per narration line
- Frame templates: Book page, Film, Full-bleed, Minimal (subtitles and titles laid out per size)
- Narration voice: offline Piper TTS, or LocalAI speech; speed
- Transitions: cut, crossfade, fade through black, slide
- Background music
- Storyboard sheet to approve BEFORE rendering
- Book trailer preset (uses the book's chapter list and illustrations)

*Note:* Shaped by Pixelle-Video's storyboard model (Apache 2.0) and OpenMontage's approval gates (ideas only).

### Video Style  (⬜ planned)
Any of the 19 art styles on every frame.

- Pick from the style gallery
- Steady style (no flicker between frames)
- Style strength

### Loops & GIFs  (⬜ planned)
Short shareable clips.

- Seamless loop
- Animated GIF (size and colors)
- Boomerang (forward then back)
- Clip length 2-10 s

### Video Edit  (⬜ planned)
Basic editing of a clip.

- Trim start/end
- Speed and reverse
- Fade in/out
- Captions over time
- Add or replace music

### Video Settings  (⬜ planned)
Shared panel for every Video tool (like Image settings).

- Length: 3, 5, 10, 15 s
- Frame rate: 12, 24, 30 fps
- Aspect: 16:9, 9:16, 1:1, 2:3, 21:9
- Platform presets: YouTube 1920x1080, Shorts/Reels/TikTok 1080x1920, Instagram 1080x1080, Cinematic 2560x1080
- Motion strength; camera move
- Art style; model
- Export: MP4, GIF, WebM
- Self-check after rendering: black or broken frames, silent or clipping audio, 'slideshow risk' (too little motion)

*Note:* MP4/WebM export needs a small video encoder bundled with the app (ffmpeg); GIF needs nothing extra.

## AI Chat: Talk with it

### Chats  (✅ built)
Conversations with memory: your rules, each chat's memory, a running summary, notes, a library and the web.

- Your rules (every chat) and each chat's memory, always loaded
- Older messages compressed into a summary, still searchable
- 'remember: ...' keeps a note
- Library of your documents
- Web search: off, when needed, always
- Save answers to your chats folder

## AI Coding: Code with it

### Projects  (✅ built)
Coding projects with layered memory, so a small model can handle a big project over many sessions.

- Your rules (every project), per user
- Project memory: what it does, rules, never-do, what to look for, commands
- Running summary + every message searchable
- Notes it keeps; memory updates you approve
- Project library: your code and docs, indexed
- Web search when it needs current information
- Save code to your code folder

### Code Editor  (⬜ planned)
Edit the project's files with the AI beside you.


### Run  (⬜ planned)
Run the code and feed errors back to the AI.


## AI Training: Teach it

### Image Learning  (🟡 partial)
Your image models (Cartoon, Fashion, Nature...), each with its own pictures, step by step.


### Video Learning  (⬜ planned)
Teach it movement from short clips (needs a 16 GB+ graphics card to train).


### Chat Learning  (✅ built)
Teach it how to answer: examples, a check set, training, testing; a library for facts.


### Coding Learning  (✅ built)
Teach it to code your way from permitted, clean code and your examples.


### Image Scraper  (✅ built)
Find pictures on Google Images to learn from.


### Pictures  (✅ built)
The active image model's pictures and their review.


## Drawing: Draw and paint by hand (the whole page is the drawing studio)

### Draw  (✅ built)
A full drawing studio: paint by hand on a blank page, the last created image, or any picture.

- Toolbar: Undo, Redo, Zoom -/+/Fit, Brush, Eraser, Eyedropper, Fill, Line, Rectangle, Ellipse, Text, Mirror symmetry
- Brush library: all 45 brushes as live stroke previews, grouped; brush properties: size (1-300), opacity, preview stroke
- Brush library sections (brush_catalog.py): Brushes, Pens, Blending, Blurring, Sharpen, Special Effects, Stamps & Icons, Layers & FX Brushes, Texture Brushes, More brushes; tools not built yet show a drawn preview marked SOON
- Next: Blending (smudge, blend, soften, mix), Blurring (gaussian, motion, radial, zoom), Sharpen (unsharp mask, high pass, edge enhance, detail), Special Effects (dodge, burn, saturation, hue shift, noise, pixelate), Stamps (25 icons), FX (glow, outline, shadow, inner shadow, outer glow, neon), Textures (canvas, fabric, brick, metal, paper, clouds)
- Layers: add, duplicate, delete, merge down, move up/down, show/hide, layer opacity, blend modes (normal, multiply, screen, overlay)
- Color: hue ring + saturation/brightness square, hex code, color history, eyedropper
- Canvas: zoom with the wheel, pan with the right mouse button; only the visible part is redrawn
- New, Open, Use last created, Save, Send to Editing
- Shortcuts: B E I G L T, [ ] size, Ctrl+Z / Ctrl+Y
- Next: selection and move, brush presets you can save, pressure from a pen tablet, layer thumbnails

## Editing: Change an image (any picture, or one it made)

### Light  (✅ built)
Lightroom-style light adjustments.

- Exposure
- Brightness
- Contrast
- Highlights
- Shadows
- Whites
- Blacks

### Color  (✅ built)
Color adjustments.

- Temperature (warm/cool)
- Tint (green/magenta)
- Hue
- Saturation
- Vibrance

### Effects  (✅ built)
Finishing effects.

- Sharpness
- Clarity
- Vignette
- Grain
- Soft glow

### Filters  (✅ built)
One-click looks.

- Grayscale
- Sepia
- Warm film
- Cool film
- Faded
- High contrast
- Your saved looks

### Transform  (✅ built)
Shape and orientation.

- Crop: drag a box on the picture; ratio presets Free, 1:1, 2:3, 3:2, 4:5, 16:9, 9:16 (box keeps the shape); rule-of-thirds guides
- Rotate 90° left/right
- Straighten -45° to +45° with automatic crop of the empty corners
- Flip horizontal/vertical
- Resize 25%-200%
- Runs before Light/Color/Effects; Save applies everything at full size

### AI Tools  (⬜ planned)
Bigger changes.

- Remove background (built-in cut-out; better with optional AI add-on)
- Expand image (paint beyond the edges)
- Upscale 2x/4x
- Creative upscale (adds painted detail)
- Fix faces (needs optional AI add-on)
- Prompt to edit (same as Create)

*Note:* Remove background, expand and upscale can be built into the engine. Fix faces needs a face-restoration AI model run offline as an add-on.

### History  (✅ built)
Undo, redo, every step by name, compare, reset, save as new / overwrite.

- Undo / Redo buttons on every Editing screen; Ctrl+Z / Ctrl+Y
- Every step listed by name (e.g. 'Exposure +20', 'Filter: sepia', 'Crop'); click to jump back
- One slider drag = one step
- Compare original and current side by side
- Reset to original (undoable)
- Save as new; Overwrite original (with confirmation)

## Settings: The app itself

### General  (✅ built)
Save folder, file format and quality, auto-save, file names, start tab, confirm on quit.

- Save folder (change / open)
- File format PNG / JPEG / WebP and quality
- Auto-save every result into a dated folder
- File name pattern
- Open on start
- Confirm before quitting

### Performance  (✅ built)
Speed vs quality.

- Editing preview size
- Image to Image working size
- Draw undo steps

### Display  (✅ built)
Fixed layout with scroll bars, window modes, text size, hints, splash.

- Fixed layout: panels never move or squeeze; scroll bars when the window is smaller
- Window mode: Windowed / Maximized / Full screen (F11, Esc)
- Remember size and position (only if still on a connected screen); minimum size; reset window
- Sharp, consistent sizing at Windows display scaling
- Text size Small / Normal / Large
- Show hints
- Startup splash

### Privacy & Data  (✅ built)
What stays on your PC; storage used; clear learned data; reset words.

- Works offline statement
- Keep training copies (default off)
- Storage used by category
- Open data folder
- Clear learned data
- Reset taught words
- Local error log

### AI Models  (🟡 partial)
The core text model (Qwen3.5 4B or 9B, switchable) and each AI tab's own model.

- Core text model: Qwen3.5 4B or 9B, download, start, stop, switch any time
- AI Chat: the core model
- AI Coding: the core model or Qwen2.5 Coder 7B
- AI Images: Stable Diffusion 1.5 / XL / your own file (engine being built next)
- AI Videos: needs a 16 GB+ graphics card

### AI Storage  (✅ built)
Give the AI its own drive; each AI gets its own portion.

- Choose the AI drive (everything moves there)
- Each AI's portion with used / budget
- Adding stops politely when a portion is full

### Updates  (✅ built)
Check GitHub for a newer version; opt-in check at startup.

- Version
- Check now
- Check when the app opens (off by default)

### Shortcuts  (✅ built)
Every keyboard shortcut.

- Anywhere
- Text to Image
- Image to Image
- Draw studio
- Editing

### Backup & Reset  (✅ built)
Export / import settings, theme, words and learned style; reset all settings.

- Export backup
- Import backup
- Reset all settings

### Theme  (✅ built)
Look of the app.

- Border color
- Background color
- Panel opacity
- Build a theme from one color (Matching, Complementary, Split, Triadic)
- Reset

### About  (✅ built)
Logo, version, credits and open-source notes.

- Easel logo
- Version
- Credits
- Open-source notes and licenses

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
