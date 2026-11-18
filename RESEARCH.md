# How other people train image generators, and what it means for our engine (Nov 15)

## Two kinds of training
1. **Big base models** (Stable Diffusion, Midjourney, DALL·E, FLUX) are trained on *hundreds of millions to billions* of image-and-caption pairs, on data-center hardware. Individuals don't do this.
2. **Personal fine-tuning (LoRA)** is what individuals do. You start from a base model and teach it **one style, character or object** from a small set of your own images. It needs an NVIDIA graphics card with **8 GB+ of video memory** and tools like **kohya_ss** or **ComfyUI**. The result is a small add-on file you load into the base model and switch on with a unique trigger word.

## What happens to the training images
- **They aren't stored as files inside the model.** Training adjusts millions of numbers (weights) to capture patterns.
- **But models *can* memorize and reproduce images,** mostly ones that appeared **many times** in the training set. Carlini et al. (2023) extracted about **100 near-copies** of training images out of about **350,000 attempts** on Stable Diffusion, mostly images duplicated **100 or more times**. Almost **a third** of Stable Diffusion v1's two billion images turned out to be near-duplicates.
- **Removing a memorized image afterward is hard.** Research shows memorized images are spread through the whole model, so pruning specific parts doesn't reliably remove them.

## Do you have to keep the images forever?
**No, not to *use* the model.** It runs from its weights alone. Common practice is still to **keep the dataset**, because you'll need it to:
- **retrain or improve** the model (new base models come out, settings change)
- **reproduce** results, or prove what it was trained on
- **remove** something later, which means retraining without it, since you can't delete it from the weights
- **audit** for problem images such as watermarks or duplicates

## Best practices (common across guides)
- **"The dataset is 95%, the settings are 5%."** Image quality and choice decide the result.
- **Size:**
  - a character or object: **15–30** varied images
  - **a style: 15–100**, more than a character, because a style spans brushwork, palette and composition across *different subjects*
- **For a style, vary the *subjects* and keep the *style* constant.** If many images share a subject (one guide uses elephants), the model learns that subject as part of the "style."
- **Quality:** clean, high-resolution images with no watermarks, logos or heavy compression; cropped to consistent sizes; deduplicated.
- **Captions describe the content, not the style.** The style is what's left over for the model to learn.
- **Variety over repetition:** 30 different images seen once beats 10 images seen five times. Repeats don't add variety.
- **Save checkpoints** during training and **test on new prompts**, not the training ones, then pick the best checkpoint, not just the last.

## What doesn't work
- **Too few or too similar images,** which leads to **overfitting**: it copies the training images, poses and backgrounds get stuck, and it ignores new prompts.
- **Too much training or too many repeats** (overfitting again). **Too little** gives **underfitting**: a weak, vague resemblance.
- **Watermarked or low-quality images:** the model learns the watermark and the artifacts.
- **Judging quality only on the training images,** which hides overfitting.

## How our engine compares
Our engine **doesn't train a neural network.** It **measures** each subject (palette, texture, stroke direction, light-and-dark structure) and paints with code. So:
- **Memorization:** the measurements (`profile.json`) can't reproduce an image. **One exception:** the *texture bank* stores small crops of library images, and those *are* copies of pieces. → *now optional (off by default in learning)*
- **Keeping images:** after learning, the engine runs from `profile.json` alone. Keep the library anyway, to relearn whenever the engine improves (the same reasoning as everyone else).

## Applied to our engine now
1. **Deduplication:** identical images in the library are counted once (by file fingerprint), so a repeated picture can't dominate a subject. *(the duplication lesson)*
2. **Profile versions,** like checkpoints: every learn saves a dated copy in `my-library/history/`, so you can roll back if new images make it worse.
3. **Held-out testing:** `evaluate.py` scores against example images; the subject profiles are learned from the library. Keep some examples out of the library so the tests stay honest. *(the "test on new prompts" lesson)*
4. **More variety beats more repeats:** per-subject learning takes the **median** across images, so one odd image can't swing a subject.

## If you later want true text-to-image (local, offline, free once set up)
A PC with an **NVIDIA card (8–12 GB+ video memory)**, **ComfyUI** or **Forge**, a base model (**SDXL** or **FLUX**), and a **style LoRA trained on 30–100 of your own paintings** with **kohya_ss**. Following the practices above, that's how artists get "my own generator in my own style." This engine can then do the finishing: palette-matching, captions and book layout.
