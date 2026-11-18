# Instant Easel

*Type it, see it painted. Teach it your style.* Offline, free, your own.

![Instant Easel](brand/logo.png)

(Formerly the Painterly Image Engine.)

Your own image tool, built for the trilogy and improving over time. It takes a **simple composition** (a sketch, a photo, or a scene drawn in code) and **repaints it in your style**: brushstrokes, your palettes, and real skies and textures borrowed from your own paintings.

It is not an AI that makes pictures from words. It transforms images you give it, and it runs on any ordinary computer, with no internet and no graphics card.

## Install (once)
1. Install [Python 3](https://www.python.org/downloads/).
2. In a terminal, from this folder (`Instant Easel/`):
   ```
   pip install -r requirements.txt
   ```

## Use it
```
# paint any image in your sunset style
python3 generate.py --input my_sketch.png --out painted.jpg --style warm

# use ANY painting as the style source (palette + sky)
python3 generate.py --input photo.jpg --out painted.jpg --style styles/night-city.jpg

# rooms, doorways, close-up planets: brushwork only, no borrowed sky
python3 generate.py --input room.png --out room_painted.jpg --style night --interior

# render one of the book's 93 scenes by name, with its caption
python3 generate.py --scene b2-16-1 --out roof.jpg
python3 generate.py --list            # all scene names and captions
```
Add `--caption "Your text"` for a book-style caption, and try different `--seed` numbers for different brushwork.

## The app
One menu window, with the Instant Easel logo and five tabs: **Images**, **Videos**, **Editing**, **Training**, **Settings**.

**Image to Image** repaints any picture (a photo, a sketch, one of its own paintings) at its own shape:
- **Words (optional):** "golden hour," "night" (re-lights it as moonlight), "stormy," "watercolor," or a caption in quotes.
- **Strength:** low stays close to the picture; high makes it fully a painting.
- **Medium:** oil, watercolor, pastel or ink sketch. **Palette:** keep the picture's colors, warm sunset, night, or your learned style.
- **Before and after** side by side, Save, and paint over by hand. About 1–2 seconds per picture.
- **Image Generator:** type what you want ("two people sitting on a hill at sunset, tall mountains, lots of clouds, no rocks") and press **Generate**.
  - It shows **what it understood** and **any words it doesn't know yet**, with a button to teach them.
  - **New variation** repaints the same request with different brushwork. **Use my learned style** paints with what Training Mode learned.
  - **Save**, or **paint over it by hand**.
- **Training Mode** has three tabs:
  - **Learn from images:** add pictures; it guesses sky, mountains, rock, grass, people or scene; you confirm; then **Learn**.
  - **Teach it words:** say what a word or phrase means (light, clouds, color mood, figures, pose, mountains, rocks, grass, canyon, sun position). Includes a test box to check its understanding.
  - **Styles & painting:** add a painting as a style, the drawing canvas (45 brushes), and the classic tools.

**What it understands:** about 340 painting words and phrases, including:
- **synonyms:** dusk = evening = sunset
- **numbers:** "a man," "two friends," "a couple"
- **negatives:** "no rocks," "without grass"
- **positions:** "sun on the left"
- **amounts:** "lots of clouds," "clear sky"
- **sizes:** "tall," "jagged," "rolling hills"
- **poses:** sitting or standing
- **color moods:** golden, crimson, lavender, melancholy
- **captions** in quotes

It also handles **word forms** (rocks, rocky, rock) and **misspellings** ("sunst" → sunset), and tells you when it corrected one. Words you teach are saved in `vocab.json` next to the app.

**What it paints today:** mountain landscapes at sunset or night (moon and stars), with clouds, a canyon, a grassy rise, rocks, and up to two sitting or standing figures. Subjects it can't paint yet, like dragons, oceans or forests, are reported as unknown rather than guessed at.

## The Windows app (InstantEasel.exe)
A double-click desktop program with its own window. It's fully offline: no website, no internet, nothing sent anywhere.
- **Open image**, pick a **style**, press **Paint it**, then **Save result**. Or pick a **book scene** from the list.
- **Add a painting as a style** from inside the app. Your styles are kept in a `my-styles` folder next to the .exe.

**Get the .exe, way 1 (on your PC):** install Python 3 from python.org (tick **"Add python.exe to PATH"**), download this repository (**Code → Download ZIP**), unzip it, open `Instant Easel`, and double-click **`build_windows.bat`**. Your app appears at `Instant Easel/dist/InstantEasel.exe`. Copy it anywhere and run it. Python isn't needed after that.

**Get the .exe, way 2 (GitHub builds it for you):** the build recipe is ready in `windows-build/build-paint-engine.yml`. To switch it on, it has to live in `.github/workflows/`. Give the access token the **Workflows: Read and write** permission and Claude can move it, or create that file yourself on the GitHub website. After that, every change to the engine builds a fresh `InstantEasel.exe`, downloadable from the repository's **Actions** tab.

## The learning library
In the app, use **Add images to learn from…** (pick as many as you like), then **Learn from library**. The engine studies every image and builds a **style profile**:
- **Colors:** sky (cool gaps, cloud bodies, rims), mountains (shadow, mid, sunlit) and ground.
- **Brushwork:** stroke direction and texture.
- **Light and dark:** from top to bottom.
- **A texture bank** of sky, rock and ground patches.

The color swatches under the button show what it learned. Choose the style **My library (learned)**: for each picture, it uses the library images closest in mood. Images are kept in `my-library` next to the app, so the library grows over time. From the command line: `python3 learn.py my-library`.


## Your styles (`styles/`)
| File | What it gives |
|---|---|
| `sunset-field.jpg` | the Book One cover: warm sunset palette, swirling clouds, painted grass |
| `night-city.jpg` | the prologue city: deep blue night, Milky Way |
| `summit.jpg` | the Chapter 1 summit: painted rock and mountainsides |

**Drop in any new painting and pass its path to `--style`.** Every painting you add gives the engine more to work with.

## How it works (`paint.py`)
1. **Round the shapes.** Hard corners from simple drawings are softened (`round_shapes`).
2. **Set the figures aside.** Small dark silhouettes are lifted out so brushstrokes never smear them (`remove_figures`).
3. **Borrow a real sky.** Open sky connected to the top of the picture is replaced with brushwork from your painting, cropped and tinted per image (`sky_transplant`).
4. **Paint the land.** Ground and mountainsides get painted grass and rock from figure-free parts of your paintings (`land_texture`).
5. **Match the palette** to your painting, keeping the image's own light and dark (`color_match`).
6. **Brushstrokes:** thousands of curved, bristled strokes, big to small, following the light (`paint`).
7. **Crisp silhouettes back on top,** sharp and dark, like the figures in your paintings.

The book scenes themselves are drawn in `draw.py` (shapes, organic figures, smooth ridgelines) and `scenes.py` (all 93 compositions).

## What it does well, and doesn't
- **Good:** landscapes, skies, coasts, mountains, night scenes, silhouetted figures, and simple compositions with clear shapes.
- **Weak:**
  - Lettering and small text get mangled, so add titles afterward.
  - Speckled or starry backgrounds aren't recognized as sky.
  - It can't invent detail. A simple shape stays a simple shape, just painted.
  - Faces aren't possible.

## Roadmap: making it better
**Near-term (I can keep building these here):**
- [ ] Better sky detection, so starry and speckled skies get transplanted too
- [ ] Clouds that follow the composition, flowing around peaks and figures
- [ ] Water reflections and light paths under suns and moons
- [ ] More figure poses (walking, carrying, reaching up, embracing) and better hands and hair silhouettes
- [ ] A protect-text option so titles survive painting
- [ ] Per-scene style choice (any `styles/` file) inside `scenes.py`
- [ ] Faster painting for batch runs

**The big step: real AI generation (on your own computer).** To get images made from words, like your two paintings, you'd run an open AI image model, such as Stable Diffusion through **ComfyUI** or **Automatic1111**, on a PC with an NVIDIA graphics card (8 GB+ of video memory). It's free to run once set up. You can even **train it on your own paintings** (a "LoRA") so it learns your style. This engine then becomes the finishing stage: palette-matching, consistent captions, and dropping images straight into the books.

## Look and brand
- **Theme** (`theme.py`):
  - navy panels framed in a colored border, yellow underlined monospace titles
  - tabs with the active one outlined; blue buttons with an outline on hover and focus; red close and danger buttons
  - toggle switches, rainbow hue sliders, key-hint footers
- **Theme tab:** border color, background color and panel opacity change the whole app live, and are saved in `instant_easel_theme.json`.
- **Brand** (`brand/`, the author's logos, Nov 15): `title-logo.png` (the paint-splash wordmark, used as the header title) and `logo-easel.png` (with the easel and palette, used on the splash screen and the About page). `icon.png` / `icon.ico`: the easel logo at large sizes, and the easel-and-palette close-up (`icon-closeup.png`) at 64 px and below. The earlier pixel logo and icon are kept in `brand/old/`. **Mascots** (the author's artwork): `mascot-guy.png` sits at the header's top left and `mascot-girl.png` at its top right, both looking in at the logo.
- **Name check (Nov 15):** no existing app called "Instant Easel" was found. Plain "Easel" is used by several products, including an AI image app called Easel AI, so always use the full name.

## What happens to the images you teach it
- **They're measured, then deleted.** When you press **Learn**, each image is measured (colors, textures, brushwork, light and dark), and the measurements blend into what it already knows. Then **the app's copies are deleted.** Only the numbers stay, in `my-library/profile.json`.
- **Your originals are never touched.** Adding an image makes a copy for the library, and only that copy is deleted.
- **Learning is cumulative.** New images blend with earlier ones, weighted by how many images each batch had, so teaching it more never erases what it learned before.
- **No double-counting.** Each learned picture's fingerprint (a short code, not the picture) is remembered, so the same image can't be learned twice.
- **Keep copies** (Training tab, off by default) keeps the library copies if you want to re-learn from them after an engine update.
