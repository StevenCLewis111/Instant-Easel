# Third-party software and models

Instant Easel is free. It uses these open-source parts; thank you to their authors.

## Included in the app
| Part | What it does here | Licence |
|---|---|---|
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) (Microsoft) | runs the cut-out AI models on your PC | MIT |
| [NumPy](https://numpy.org), [SciPy](https://scipy.org) | the painting engine's maths | BSD-3-Clause |
| [Pillow](https://python-pillow.org) | opening and saving pictures | MIT-CMU (HPND) |

## Downloaded the first time a cut-out tool needs them (not included in the app)
They're fetched from the [rembg](https://github.com/danielgatis/rembg) project's release files (MIT), checked against a
SHA-256 hash, and kept in `my-models/cutout/` on your PC. They run on your PC only: no picture is ever sent anywhere.

| Model | Used by | Licence |
|---|---|---|
| ISNet / DIS, `isnet-general-use` (Qin et al., [xuebinqin/DIS](https://github.com/xuebinqin/DIS)) | Select Subject, Remove Background, Object Selection's outlines | Apache-2.0 |
| Segment Anything, ViT-B, quantized (Meta AI, [facebookresearch/segment-anything](https://github.com/facebookresearch/segment-anything)) | Object Selection, Quick Selection | Apache-2.0 |
| LaMa, big-lama (Suvorov et al., Samsung AI, [advimman/lama](https://github.com/advimman/lama)); ONNX export by Carve ([Carve/LaMa-ONNX](https://huggingface.co/Carve/LaMa-ONNX)) | Magic Remove, Remove selected | Apache-2.0 |
| Real-ESRGAN, realesr-general-x4v3 (Xintao Wang et al., [xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN)); turned into ONNX by the build | Upscale 2x / 4x | BSD-3-Clause |

## Methods (written for this app, after the published papers)
- Guided filter, He, Sun & Tang (2010): Refine Edge's hair and fur.
- Fast multi-level foreground estimation ("blur fusion"), Germer et al. (2020): Decontaminate Colors.
