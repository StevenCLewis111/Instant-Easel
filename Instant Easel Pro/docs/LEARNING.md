# AI Training: how each area learns

AI Training has a menu per learning area: **Image**, **Video**, **Chat** and **Coding** (plus **Models**).
Each area walks through the same seven steps, with options that suit that area:

**1 Goal → 2 Collect → 3 Clean → 4 Label/Format → 5 Settings → 6 Train → 7 Test**

Dots: **green** works now · **blue** started (saved or partly working) · **grey** just a button for now.
"Use best-practice settings" puts an area back to the recommended settings.
Settings are kept in `.json/learning_settings.json`; the code is `systems/AI Training/Learning Areas/learning_areas.py`.

## Image Learning
- **Collect:** search Google Images (each picture is labelled with the word you searched), or add your own. 15–50 varied pictures per word is the sweet spot.
- **Clean:** review before learning and untick bad pictures. Pictures already learned are skipped, and so are tiny ones (under 256 px).
- **Label:** the search word is the label. "Teach words" teaches what your words mean.
- **Train / Test:** Learn now; every training saves a version you can roll back to (Models).
- It learns how things look: colours, textures, brushwork and light.

## Video Learning
- Use short real clips (3–5 s), not only still pictures, because still pictures teach it not to move. 10–30 clips is a good start.
- Captions should describe the motion. Memory use grows with frames × size × clips, so start small.
- Training a video model needs a graphics card with 16 GB+ (or a rented one online), so most of this area is grey for now. Clips you add are kept in the video library.

## Chat Learning and Coding Learning
- **Facts go in the library; how to answer is what training changes.** Training doesn't store facts reliably.
- **Collect:** teach examples (a question and the perfect answer), or import a `.jsonl` / `.csv` file. Aim for 100+; 500+ is better.
- **Clean:** duplicates are removed. Coding also keeps only permissively licensed code (MIT, Apache, BSD), skips duplicate files, and skips Python that doesn't compile.
- **Settings:** 1–3 passes, a learning speed (Careful / Normal / Fast), and an add-on size (8 / 16 / 32).
  "Hold back 10% to check it" keeps some examples out of training. Training stops early once the check gets worse, because that means it has started memorising.
- **Train:** each area trains its own small add-on. Other areas and the base model don't change.
- **Test:** ask it questions that are not in your examples.
