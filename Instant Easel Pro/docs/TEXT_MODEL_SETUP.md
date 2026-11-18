# Setting up the core text model

The core text model is the English model every AI tab uses. You pick it in **Settings > AI Models**:

| Model | Size | On your Intel Arc A380 (6 GB) |
|---|---|---|
| **Qwen3.5 4B** (default) | about 3 GB | Fits fully on the graphics card: quick. |
| **Qwen3.5 9B** | about 5.7 GB | Smarter, but part of it runs on the processor: slower. Needs 16 GB+ of PC memory. |

You can switch between them any time. Both stay downloaded, so you can compare how each runs.

## Steps

1. **Update your graphics driver** (Intel Arc: Intel's driver page, or the Intel Driver & Support Assistant). The engine reaches the card through Vulkan, which comes with the driver.
2. Open the app and go to **Settings > AI Models**.
3. Press **Download it**. The first time, this downloads the engine (llama.cpp, about 30–60 MB) and the model you picked. The status line shows progress.
4. Press **Start it now** (or just use an AI tab; it starts by itself the first time).
5. To try the other model, switch **Core model** to Qwen3.5 9B and press **Download it** again.

Nothing else needs installing: no Python add-ons and no separate programs.

## If something goes wrong

- **It runs, but slowly:** the status says whether it's on the graphics card or the processor. If it says processor, update the graphics driver and press **Start it now** again.
- **It won't start:** the details are in `logs/text_engine.log`. Send that file to me.
- **Download stopped part-way:** press **Download it** again; it carries on where it stopped.

## Teaching it

**AI Training > Chat Learning** and **Coding Learning**:

- **Teach examples:** a question, plus the answer you want.
- **Add documents or code to its library:** it looks things up there before answering.
- **Test it:** ask it questions.

Training the model itself (fine-tuning) needs a graphics card with 12 GB or more, so those options are greyed out for now. Examples and the library work today.
