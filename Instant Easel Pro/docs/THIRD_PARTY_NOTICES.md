# Third-party software and models

Instant Easel Pro uses these parts made by other people; thank you to their authors. Everything below runs on your own PC.

**Can it be shared?** Every part is marked:
- ✅ **Shareable**: an open licence that allows sharing, including commercially (keep its licence and credit with it).
- ⚠️ **Shareable with limits**: sharing is allowed, but its licence carries use rules (for example no harmful uses), and
  anything shared must pass those rules on.
- ⛔ **Not for commercial use**: personal, research and evaluation use only. Don't sell it, or anything made into a product with it.
- ❓ **Unknown**: its page doesn't state a licence. Treat it as not shareable until you've checked.

**Nothing here ships with the app** except the libraries in the first table. Every model, engine and tool is downloaded onto
your AI drive when you ask (Settings > Download Everything, Drawing AI, AI Models, Templates, or the tool's own Download
button), and each can be swapped for a file of your own. Sharing the app doesn't share any of them.

## Included in the app
| Part | What it does here | Licence | Share? |
|---|---|---|---|
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) (Microsoft) | runs the Drawing tab's AI models | MIT | ✅ |
| [NumPy](https://numpy.org), [SciPy](https://scipy.org) | the painting engine's maths | BSD-3-Clause | ✅ |
| [Pillow](https://python-pillow.org) | opening and saving pictures and videos' frames | MIT-CMU (HPND) | ✅ |
| [Requests](https://github.com/psf/requests) | downloads, the image scraper | Apache-2.0 | ✅ |
| [ONNX](https://github.com/onnx/onnx) | turns the upscaler's download into the model it runs | Apache-2.0 | ✅ |

## Drawing tab AI (Settings > Drawing AI, or when its tool is first used)
Most are fetched from the [rembg](https://github.com/danielgatis/rembg) project's release files (MIT); each is checked against a SHA-256 hash.

| Model | Used by | Licence | Share? |
|---|---|---|---|
| ISNet / DIS, `isnet-general-use` (Qin et al., [xuebinqin/DIS](https://github.com/xuebinqin/DIS)) | Select Subject, Remove Background, Object Selection's outlines | Apache-2.0 | ✅ |
| Segment Anything, ViT-B, quantized (Meta AI, [facebookresearch/segment-anything](https://github.com/facebookresearch/segment-anything)) | Object Selection, Quick Selection | Apache-2.0 | ✅ |
| LaMa, big-lama (Suvorov et al., Samsung AI, [advimman/lama](https://github.com/advimman/lama)); ONNX export by Carve ([Carve/LaMa-ONNX](https://huggingface.co/Carve/LaMa-ONNX)) | Magic Remove, Remove selected, Expand | Apache-2.0 | ✅ |
| Real-ESRGAN, realesr-general-x4v3 (Xintao Wang et al., [xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN)); turned into ONNX by the build | Upscale 2x / 4x | BSD-3-Clause | ✅ |

## Engines (downloaded when first needed, or by Download Everything)
| Engine | Used by | Licence | Share? |
|---|---|---|---|
| [llama.cpp](https://github.com/ggml-org/llama.cpp) (ggml authors) | every text AI: AI Chat, AI Coding, the fuller descriptions | MIT | ✅ |
| [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) (leejet) | AI Images and AI Videos | MIT | ✅ |

## Text models
| Model | Used by | Licence | Share? |
|---|---|---|---|
| [Qwen3.5](https://huggingface.co/Qwen/Qwen3.5-9B) 2B, 4B, 9B, 27B (Alibaba Qwen team); GGUF files by bartowski | the core text model | Apache-2.0 | ✅ |
| [Qwen2.5 Coder](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct) 7B and 14B (Alibaba Qwen team); GGUF by bartowski | AI Coding | Apache-2.0 | ✅ |
| [Qwen2.5 Coder 3B](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct) (Alibaba Qwen team); GGUF by bartowski | AI Coding (small PCs) | **Qwen Research License**: non-commercial (research / evaluation) only | ⛔ |

## Picture models
| Model | Used by | Licence | Share? |
|---|---|---|---|
| [Z-Image Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) (Tongyi-MAI, Alibaba); GGUF by leejet; decoder repackaged by Comfy-Org | AI Images | Apache-2.0 | ✅ |
| [Qwen3 4B Instruct 2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) and [Qwen3 4B](https://huggingface.co/Qwen/Qwen3-4B) (Alibaba Qwen team); GGUF by unsloth | the text readers for Z-Image and FLUX.2 Klein | Apache-2.0 | ✅ |
| [FLUX.2 Klein 4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) (Black Forest Labs); GGUF by leejet / unsloth; decoder from FLUX.2 repackaged by Comfy-Org | Prompt to Edit, references, painting | Apache-2.0 (the 4B only: the 9B and FLUX.2 dev are non-commercial and aren't used) | ✅ |
| [Stable Diffusion 1.5](https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive) (Runway / CompVis / Stability AI) | AI Images, the guides, your own image models | CreativeML OpenRAIL-M | ⚠️ |
| [Stable Diffusion XL base 1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0) (Stability AI) | AI Images | CreativeML Open RAIL++-M | ⚠️ |
| [ControlNet 1.1](https://github.com/lllyasviel/ControlNet-v1-1-nightly) pose, outline (canny), depth, scribble (Lvmin Zhang); fp16 files by comfyanonymous | Pose / Depth / Sketch to Image | CreativeML OpenRAIL-M | ⚠️ |
| [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) x4plus and x4plus anime 6B (Xintao Wang et al.) | upscaling after painting | BSD-3-Clause | ✅ |

## Video model
| Model | Used by | Licence | Share? |
|---|---|---|---|
| [Wan 2.2 TI2V 5B](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B) (Wan team, Alibaba); GGUF and decoder by QuantStack (decoder also from Comfy-Org) | AI Videos | Apache-2.0 | ✅ |
| umt5-xxl text encoder (Google, as shipped with Wan); GGUF by [city96](https://huggingface.co/city96/umt5-xxl-encoder-gguf) | AI Videos' text reader | Apache-2.0 | ✅ |
| [LTX-2.3](https://huggingface.co/Lightricks/LTX-2.3) 22B distilled (Lightricks); GGUF and decoders by [unsloth](https://huggingface.co/unsloth/LTX-2.3-GGUF) | AI Videos: video with sound (the strong video model) | **LTX-2 Community License**: free, commercial use included, for anyone under $10M a year in revenue; above that a paid licence | ⚠️ |
| [Gemma 3 12B](https://huggingface.co/google/gemma-3-12b-it) (Google); GGUF by [unsloth](https://huggingface.co/unsloth/gemma-3-12b-it-qat-GGUF) | LTX-2.3's text reader | Gemma Terms of Use (sharing allowed; Google's prohibited-use policy passes on) | ⚠️ |

## Audio model (AI Videos > Add Sound; runs in its own Python, downloaded onto your AI drive)
| Part | Used by | Licence | Share? |
|---|---|---|---|
| Python (from the official [nuget.org package](https://www.nuget.org/packages/python) on Windows) | runs the audio model, apart from the app | PSF License | ✅ |
| [Kokoro 82M](https://huggingface.co/hexgrad/Kokoro-82M) (hexgrad), model files by [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) | voices | Apache-2.0 (kokoro-onnx: MIT) | ✅ |
| [phonemizer](https://github.com/bootphon/phonemizer) and [eSpeak NG](https://github.com/espeak-ng/espeak-ng) (via espeakng-loader) | turn the words into sounds for Kokoro | GPL-3.0 | ✅ (GPL: pass on its source offer) |
| [MMAudio](https://github.com/hkchengrex/MMAudio) (Ho Kei Cheng et al., UIUC, Sony AI) | sound effects matched to the video | code MIT; **model weights CC-BY-NC-4.0: non-commercial only** | ⛔ |
| [PyTorch](https://pytorch.org), torchvision, torchaudio (Meta / Linux Foundation) | runs MMAudio | BSD-3-Clause | ✅ |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) with its [FFmpeg](https://ffmpeg.org) | mixing the sound into the video, joining clips | BSD-2-Clause; the FFmpeg program it brings is GPL | ✅ (GPL: pass on its source offer) |
| [soundfile](https://github.com/bastibe/python-soundfile) / libsndfile | writing the voice | BSD-3-Clause / LGPL-2.1 | ✅ |

## Templates (Settings > Templates)
Made by other people for Z-Image Turbo. Each is its own work with its own licence.

| Template | Made by | Licence | Share? |
|---|---|---|---|
| Anime ([ANIME-REDMOND-ZIMAGE](https://huggingface.co/artificialguybr/ANIME-REDMOND-ZIMAGE)) | artificialguybr | Apache-2.0 | ✅ |
| Line art / colouring page ([COLORINGBOOK-REDMOND-ZIMAGE](https://huggingface.co/artificialguybr/COLORINGBOOK-REDMOND-ZIMAGE)) | artificialguybr | Apache-2.0 | ✅ |
| Vintage photo ([Technically-Color-Z-Image-Turbo](https://huggingface.co/renderartist/Technically-Color-Z-Image-Turbo)) | renderartist | Apache-2.0 | ✅ |
| Pixel art ([elusarca pixel art](https://huggingface.co/reverentelusarca/elusarca-pixel-art-style-lora-zimage-turbo)) | reverentelusarca | see its page | ❓ |
| Pencil sketch ([Z-Image-Turbo-pencil-sketch](https://huggingface.co/Ttio2/Z-Image-Turbo-pencil-sketch)) | Ttio2 | see its page | ❓ |
| Black & white ([darkroom-noir-zimage](https://huggingface.co/frankbarbs/darkroom-noir-zimage)) | frankbarbs | see its page | ❓ |
| Minimal / flat ([zimage-flat-color-v2-1](https://huggingface.co/oshi-pog/zimage-flat-color-v2-1)) | motimalu | see its page | ❓ |
| Oil painting, Digital painting ([Z-Image-LoRAs](https://huggingface.co/Zuellni/Z-Image-LoRAs)) | Zuellni | see its page | ❓ |
| Realistic photo ([Z-Image-Turbo-Realism-LoRA](https://huggingface.co/suayptalha/Z-Image-Turbo-Realism-LoRA)) | suayptalha | see its page | ❓ |
| **Templates you add yourself** | whoever made them | whatever its page says | ❓ check each |

## Code checkers (Download Everything, Windows; kept in the AI drive's Code Tools folder)
| Tool | Checks | Licence | Share? |
|---|---|---|---|
| [Node.js](https://nodejs.org) | JavaScript | MIT | ✅ |
| [TypeScript](https://www.typescriptlang.org) (Microsoft) | TypeScript | Apache-2.0 | ✅ |
| GCC (Free Software Foundation), [WinLibs](https://winlibs.com) build with MinGW-w64 | C and C++ | GPL-3.0 with the GCC Runtime Library Exception; MinGW-w64 parts: permissive (ZPL / MIT / public domain) | ✅ (GPL: pass on its source offer) |
| [Eclipse Temurin JDK 21](https://adoptium.net) (Adoptium) | Java | GPL-2.0 with the Classpath Exception | ✅ (GPL: pass on its source offer) |
| [Go](https://go.dev) (Google) | Go | BSD-3-Clause | ✅ |

## What you make with them
The licences above are about the models and tools themselves. Pictures, videos and code you make with them are generally yours,
but the OpenRAIL models, LTX-2 and Gemma (⚠️), and the Qwen Research License and MMAudio's weights (⛔) also set rules on how their output may be used, so read
those if you'll ever publish or sell what they made.

## Methods (written for this app, after the published papers)
- Guided filter, He, Sun & Tang (2010): Refine Edge's hair and fur.
- Fast multi-level foreground estimation ("blur fusion"), Germer et al. (2020): Decontaminate Colors.
