# AI Training: how each area learns

AI Training has a menu per learning area: **Image**, **Video**, **Chat** and **Coding** (plus **Models**).
Each area walks through the same seven steps, with options that suit that area:

**1 Goal → 2 Collect → 3 Clean → 4 Label/Format → 5 Settings → 6 Train → 7 Test**

Dots: **green** works now · **blue** started (saved or partly working) · **grey** just a button for now.
"Use best-practice settings" puts an area back to the recommended settings.
Settings are kept in `.json/learning_settings.json`; the code is `systems/AI Training/Learning Areas/learning_areas.py`.

## Image Learning
- **Image models:** the bar at the top picks which of your image models you're training (Cartoon, Fashion, Nature...), or makes, renames or deletes one. Each has its own pictures, so they never mix.
- **Collect:** search Google Images (each picture is labelled with the word you searched), or add your own. 15–50 varied pictures per word is the sweet spot.
- **Clean:** every new picture goes through a review where you untick bad ones. Duplicates and tiny pictures are skipped.
- **Label:** the search word is the label. Each image model gets its own made-up trigger word.
- **Train / Test:** training each image model's add-on (a LoRA) on top of Stable Diffusion 1.5 comes with the image engine, which is the next thing being built.

## Video Learning
- Use short real clips (3–5 s), not only still pictures, because still pictures teach it not to move. 10–30 clips is a good start.
- Captions should describe the motion. Memory use grows with frames × size × clips, so start small.
- Training a video model needs a graphics card with 16 GB+ (or a rented one online), so most of this area is grey for now. Clips you add are kept in the video library.

## Chat Learning and Coding Learning
- These teach the core text model (Settings > AI Models).
- **Facts go in the library; how to answer goes in examples.** Both are used every time it answers, starting now.
- **Collect:** teach examples (a question and the perfect answer), or import a `.jsonl` / `.csv` file. Add documents or code to the library.
- **Clean:** duplicates count once. Coding keeps only permissively licensed code (MIT, Apache, BSD), skips duplicate files, and skips Python that doesn't compile.
- **Format:** answer length. For coding, also the main language and whether to explain the code.
- **Train:** baking examples into the model itself needs a 12 GB+ graphics card, so the training settings are saved for then.
- **Test:** ask it questions that are not in your examples.
