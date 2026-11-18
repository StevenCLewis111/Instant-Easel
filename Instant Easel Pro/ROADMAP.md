# Instant Easel: roadmap and feature tracker

Generated from `features.py` (the same list the app's menus use).

## Build order

| # | Feature | Menu | Status |
|---|---|---|---|
| 3 | Text to Image | Images | 🟡 partial |
| 5 | AI Models | Settings | 🟡 partial |
| 6 | Inpainting | Images | ⬜ planned |
| 7 | AI Tools | Editing | ⬜ planned |
| 10 | Prompt to Edit | Images | ⬜ planned |
| 11 | Sketch to Image | Images | ⬜ planned |
| 12 | Image Prompting | Images | ⬜ planned |
| 13 | Multi-Image Fusion | Images | ⬜ planned |
| 14 | Pose to Image | Images | ⬜ planned |
| 15 | Consistent Character | Images | ⬜ planned |
| 16 | Depth to Image | Images | ⬜ planned |
| 20 | Text to Video | Videos | ⬜ planned |
| 21 | Image to Video | Videos | ⬜ planned |
| 22 | Motion Effects | Videos | ⬜ planned |
| 23 | Story Sequence | Videos | ⬜ planned |
| 24 | Video Style | Videos | ⬜ planned |
| 25 | Loops & GIFs | Videos | ⬜ planned |
| 26 | Video Edit | Videos | ⬜ planned |
| 27 | Video Settings | Videos | ⬜ planned |

## Images: Make new images

### Text to Image  (🟡 partial)
Type what you want; it paints it.

- Prompt box with 'what I understood' and unknown words (built)
- SHARED IMAGE SETTINGS PANEL, right side of Images, used by every Create tool (built):
-    Model: Core (default) / My learned style (built); trained models appear here once Training > Models exists
-    Art style: 19 styles in a thumbnail gallery (built): Painterly, Realism, Oil Painting, Watercolor, Pastel, Pencil Sketch, Black and White, Cartoon, Anime, Comic Book, Pop Art, Street Art, Pixel Art, Abstract, Impressionist, Stained Glass, Woodblock Print, Neon, Low Poly; style words in the prompt pick them too
-    Aspect ratio: 2:3, 3:2, 1:1, 16:9, 9:16, original, painted at that shape (built)
-    Next: cover and thumbnail presets: 21:9 wide cover, 4:5 and 3:4 vertical, 1:1 share card, 1280x720 thumbnail, 6x9 in book cover; 'make all sizes' from one image
-    How many: 1, 4 (2x2) or 9 (3x3), click one to choose it (built)
-    Starting image: upload / clear; guides colors in Text to Image, is the picture in Image to Image (built)
-    Download all (built); Save per image (built)
- New variation (built)
- Next: your saved styles in Art style; trained models in Model

### Image to Image  (✅ built)
Repaint any picture, guided by words.

- Strength
- Art style, model, aspect, how many: from the shared Image settings panel
- Palette: keep, warm, night
- Mood words, night re-lighting, captions

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

### Sketch to Image  (⬜ planned)
Turn a sketch, line drawing or child's drawing into art.

- Upload a sketch or draw one on the canvas
- Fills enclosed shapes with color, then paints them in a medium
- Keep lines on/off
- Color hints by word

### Pose to Image  (⬜ planned)
People in specific poses.

- Drag a stick-figure skeleton (head, arms, legs)
- Pose presets: standing, sitting, walking, pointing, embracing
- The figure painter draws the pose in the scene

### Inpainting  (⬜ planned)
Edit part of an image or remove unwanted things.

- Brush a mask over the area
- Remove: fill from the surroundings
- Replace: paint the area to match words
- Mask feathering

### Image Prompting  (⬜ planned)
Carry the style and subject feel of a reference image into a creation.

- Add 1-3 reference images
- Style strength (palette, texture, brushwork)
- Uses the same learning as Train

## Videos: Make moving pictures (future)

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

### Draw  (✅ built)
A full drawing studio: paint by hand on a blank page, the last created image, or any picture.

- Toolbar: Undo, Redo, Zoom -/+/Fit, Brush, Eraser, Eyedropper, Fill, Line, Rectangle, Ellipse, Text, Mirror symmetry
- Brush library: all 45 brushes as live stroke previews, grouped; brush properties: size (1-300), opacity, preview stroke
- Layers: add, duplicate, delete, merge down, move up/down, show/hide, layer opacity, blend modes (normal, multiply, screen, overlay)
- Color: hue ring + saturation/brightness square, hex code, color history, eyedropper
- Canvas: zoom with the wheel, pan with the right mouse button; only the visible part is redrawn
- New, Open, Use last created, Save, Send to Editing
- Shortcuts: B E I G L T, [ ] size, Ctrl+Z / Ctrl+Y
- Next: selection and move, brush presets you can save, pressure from a pen tablet, layer thumbnails

### History  (✅ built)
Undo, redo, every step by name, compare, reset, save as new / overwrite.

- Undo / Redo buttons on every Editing screen; Ctrl+Z / Ctrl+Y
- Every step listed by name (e.g. 'Exposure +20', 'Filter: sepia', 'Crop'); click to jump back
- One slider drag = one step
- Compare original and current side by side
- Reset to original (undoable)
- Save as new; Overwrite original (with confirmation)

## Training: Teach it

### Models  (✅ built)
Trained models on a shared Core: create, select, rename, train, versions, delete.

- Create: name, focus (Landscapes, Faces, Cartoons, Animals, Night scenes, Architecture, Custom), description; start empty or from another model
- Select: the model Images paints with (also in Image settings > Model)
- Train: opens Learn from Images aimed at that model
- Rename; Delete (with confirmation; the Core and other models are untouched)
- Versions: every training session saves one; roll back any time
- Each model: its own images (deleted after learning), learned style, and words
- Shared Core: painting knowledge, brushes, styles, words taught to all models, and every label correction (improves every model's guesses)

*Note:* A model learns how things look (color, texture, brushwork, light). New kinds of subjects need a painter in the Core, which then serves every model.

### Learn from Images  (✅ built)
Images it learns from (guess + confirm), per subject. Images are deleted after learning.

- Add images
- Confirm labels
- Learn
- Cumulative: new learning blends into old, weighted by image count
- Fingerprints stop the same picture being learned twice
- After learning, the app's copies are deleted (switch 'Keep copies' to keep them); your originals are never touched
- Dated profile versions in history/ (numbers only)

### Words  (✅ built)
Teach its vocabulary.

- Teach a word
- Words you've taught
- Test understanding

## Settings: The app itself

### General  (✅ built)
Save folder, file format and quality, auto-save, file names, start tab, confirm on quit.

- Save folder (change / open)
- File format PNG / JPEG / WebP and quality
- Auto-save every result into a dated folder
- File name pattern
- Open on start
- Confirm before quitting

### Generation Defaults  (✅ built)
What the Image settings start with; fixed or random seed.

- Model, art style, aspect, how many
- Seed: random or fixed
- Apply now

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
Built-in model runner (no separate programs): hardware, catalog, model files.

- Your PC: processor, memory, graphics card
- Use the graphics card (Vulkan)
- Models folder
- Catalog: Gemma 4 E4B, SDXL-class, FLUX.1 [schnell] with size and license; found / not installed
- Add a model file
- Next: the built-in runner that loads and uses the models; downloads

*Note:* Author's direction: native first; model files loaded by the app itself, no separate programs.

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

### Classic Tools  (✅ built)
Older tools: repaint book scenes, styles.

- Book scenes
- Styles

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
