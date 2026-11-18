# What four open-source projects teach Instant Easel (Nov 15)

| Project | What it is | License | How we can use it |
|---|---|---|---|
| **LocalAI** (mudler/LocalAI) | Runs AI models on your own PC, offline, behind one standard API: image generation, vision, depth, faces, object detection, upscaling, speech, text-to-motion, video | **MIT** | **As an optional add-on we talk to over its API.** No code copied; Instant Easel keeps working without it. |
| **Pixelle-Video** (ATH-MaaS/Pixelle-Video) | Topic in, narrated video out: script, AI images, voice, music, composition | **Apache 2.0** | Ideas, and code reusable **with attribution and its NOTICE file** |
| **OpenMontage** (OpenMontageInc/OpenMontage) | Agent-driven video production system with many pipelines | **AGPL-3.0** | **Ideas only.** Copying code would force Instant Easel to be AGPL. |
| **guizang-ppt-skill** (op7418/guizang-ppt-skill) | Single-file HTML slide decks and social covers | **AGPL-3.0** | **Ideas only** |

## LocalAI: the optional AI add-on
- **One local server, one standard API** (the same format as OpenAI's). Image generation is a POST to `http://localhost:8080/v1/images/generations` with `prompt`, `size`, `negative_prompt` and `step`. It runs Stable Diffusion and FLUX models on CPU or GPU (NVIDIA, AMD, Intel, Apple, Vulkan).
- **Its backends line up with our hardest roadmap items:**
  - **real AI text-to-image:** Stable Diffusion and FLUX (`stablediffusion-ggml`, `diffusers`)
  - **Depth to Image:** Depth Anything 3 (`depth-anything.cpp`)
  - **Fix faces:** face detection and recognition (`face-detect.cpp`)
  - **Remove background and Inpainting:** object detection and segmentation (`rf-detr.cpp`, `locate-anything.cpp`)
  - **AI Tools:** upscaling
  - **Story Sequence and video:** text-to-speech narration, including voice cloning
  - **Pose to Image and video:** text-to-motion, animated skeletons (`kimodo.cpp`)
  - **Text to Video and Image to Video:** video generation
- **Hardware notes:** big image models want a GPU with 8 GB+ of video memory, and LocalAI has options to split models between GPU, CPU and disk. CPU-only works but is slow.
- **How Instant Easel would use it:** Settings → **AI Add-ons**:
  1. Enter the LocalAI address and **test the connection**.
  2. It lists which capabilities are installed.
  3. Each one becomes available in the app; for example, **"LocalAI: FLUX"** appears in the Model list.
  4. Our own styles, Edit, captions and layout then work on what it makes.

  If LocalAI isn't running, everything falls back to the built-in engine.

## Pixelle-Video: the shape of Story Sequence
- **The storyboard model:** a video is a list of **frames**, each with a **narration line**, an **image prompt**, **audio**, and a **duration taken from the narration's length**. The settings: number of frames, words per narration, frame rate, voice, speed, and a **frame template**. → *our Story Sequence data model*
- **Frame templates per size** (book, film, full-bleed, ultrawide, dark tech) lay out the image, subtitles and title on each frame. → *Story Sequence templates: Book page, Film, Full-bleed, Minimal*
- **Pipeline:** script → image planning → frame-by-frame processing → video composition, with ffmpeg doing the joining. **The settings people actually change:** portrait or landscape size, voice, background music, and visual template.
- **Windows all-in-one package:** everything bundled, double-click to start. → *the same goal as our `.exe`*

## OpenMontage: production quality ideas (ideas only)
- **Stages with approval gates:** script → scene plan → assets → edit → compose. **The storyboard is an approval gate:** a contact sheet of every scene appears *before* the final render. → *Story Sequence shows a storyboard sheet to approve before rendering*
- **Platform output profiles:** YouTube 1920×1080, YouTube Shorts / Reels / TikTok 1080×1920, Instagram feed 1080×1080, cinematic 21:9 2560×1080. → *Video Settings presets*
- **Quality checks after rendering:** sample frames to catch black or broken frames, check audio for silence or clipping, and a **"slideshow risk" check** that flags videos that are just still images with weak motion. → *a Video self-check, like our image test suite*
- **Free, offline narration with Piper TTS.** → *a narration option that needs no add-on*
- **Style playbooks** that control typography, palette, motion and audio together. → *Video Style could carry caption fonts and motion, not just image look*
- **A decision log:** every choice recorded with the alternatives considered. → *Models' version history could record why each training changed*

## guizang-ppt-skill: covers and themes (ideas only)
- **Social cover formats from one idea:** 21:9 wide cover, 1:1 share card, 3:4 vertical cover, and video thumbnails. → *aspect presets for covers and thumbnails, plus "make all sizes" from one image*
- **A full theme from one brand color, using color science.** → *Theme tab: "build a theme from one color"*
- **Layout validators** that catch bad text placement and unsafe image crops. → *the same idea as our caption placement rules; extend to covers*

## Language and vision models for understanding (checked Nov 15)
Compared for *our* jobs (understand requests, see and sort training images, prompt to edit, check results):
- **Gemma 4** (Google, April 2026, **Apache 2.0**): multimodal at every size (E2B, E4B, 26B MoE with 4B active, 31B), with structured JSON output. **E4B (~4–6 GB) is the recommended single "understanding" model.** The 26B MoE gives more quality on a bigger GPU.
- **Qwen3** (Apache 2.0): strong text understanding at small sizes, but text-only; seeing images would need a separate vision model.
- **DeepSeek-V4** (MIT): Pro 1.6T and Flash 284B total parameters; the experimental vision version is 305B. Server-class, not for a home PC.
- **Llama 4 Scout** (Llama community license): multimodal, with a 10M-token context, but needs a high-memory GPU. The huge context isn't needed for short requests.
- **Context window doesn't matter here:** requests are short and images are labeled one at a time.
- **Role:** these models *understand*; they don't paint. Painting stays with the engine (or an image model like FLUX via LocalAI).
