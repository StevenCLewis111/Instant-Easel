# Where everything lives (Instant Easel Pro)

Start the app with `python main.py` from this folder (or the built `InstantEaselPro.exe`).

| Folder | What's in it |
|---|---|
| `requirements.txt` | Add-ons to install when running from source. The AI models need nothing extra: the app downloads them (Settings > AI Models). |
| `main.py` | The app's window, its tabs and pages. Finds every script under `systems/` by itself. |
| `systems/` | The scripts, sorted by tab: `Core/` (shared by every tab), `Drawing/`, `AI Images/`, `AI Training/`, `Editing/`, `Settings/`. Each tab folder has a sub-folder per part of that tab where it helps (e.g. `AI Images/Engine`, `AI Training/Image Scraper`). |
| `systems/Core/paths.py` | The one place that knows where pictures, fonts, settings and logs are. Scripts ask it instead of building paths themselves. |
| `systems/Core/hardware.py`, `catalog.py`, `jobs.py` | The PC check (processor, cores / threads, memory, graphics card, battery / power plan), the model ladders (each AI offers the best model that fits this PC and the smaller ones, never a bigger one; tabs the PC can't use are hidden), and the one line of AI jobs every AI tab shares (one runs at a time; the pill at the bottom right lists them). |
| `images/UI/` | Every picture the app shows, by the area it's used in: `Header`, `Splash`, `App Icon`, `Tabs and Menus`, `Status Dots`, `Draw Toolbar`, `Window Buttons`, `Brush Library`, `Color Wheel Menu`, `Sliders`, `Scroll Bars`, `Side Panel Bars`. |
| `images/UI/Brush Library/` | One picture per brush, `Section_Name/Brush_Name.png` (`_` is a space; the name is written on the tile from the file name). `_template.png` is the blank master: leave it unchanged. |
| `images/Image Scraper/`, `images/AI Images/`, `images/Drawing/` | Pictures the app saves while you use it. |
| `images/Screenshots/` | Screenshots of the app. |
| `images/unused/` | Pictures not used yet, grouped by what they'd be for (`Brushes`, `Stamps`, `Icons`, `Buttons`, `Toolbar`, `Slider UI`, `Panel`, `Sprite Sheets`, `Web Icons`, `App Icon`). |
| `fonts/` | The app's fonts. |
| `.json/` | Your settings, theme and taught words (`instant_easel_settings.json`, `instant_easel_theme.json`, `vocab.json`). |
| `logs/` | The main log `instant_easel_errors.log` (errors **and** test results), the crash / freeze logs, the scraper log and `scoreboard.json`. |
| `tests/` | Tests. Each one writes its results into the main log. `full_app_test.py` checks every tab and page; `evaluate.py` scores the painting engine. The `ui_*_test.py` files are from an older version and are kept for reference. |
| `dev/` | Development tools (brand maker, render / repaint helpers). |
| `docs/` | Notes, roadmap, research. |
| `my-library/`, `my-models/` | What the app has learned, and your models. `my-models/text/` holds the text model (downloaded on your PC, never uploaded) and each tab's text memory. See `docs/TEXT_MODEL_SETUP.md`. |
| `build/`, `EXE Build/`, `PaintEngine.spec`, `build_windows.bat` | Building `InstantEaselPro.exe`: GitHub builds it on every push (`.github/workflows/build-windows.yml`, the new exe lands in `EXE Build/`), or run `build_windows.bat` on your own PC. |

Adding a script: put it in the tab folder it belongs to; nothing else to change (the app finds it by name). Moving a picture the app
uses: change its area in `AREAS` in `systems/Core/ui_art.py`.

## AI models and learning (made on your PC, never uploaded)

| Folder | What's in it |
|---|---|
| `my-models/runtime/llama.cpp/` | The engine that runs the text models (downloaded once). |
| `my-models/text/4b`, `9b`, `coder7b` | The core text models and a tab's own text model (`.gguf` files). |
| `my-models/text/tabs/<Tab>/` | What each AI tab was taught: `examples.jsonl` and its `library/`. |
| `my-models/image/` | Image model files you add (Stable Diffusion). |
| `my-library/Image models/<Name>/` | Each of your image models (Cartoon, Fashion...): `model.json` and its `pictures/<label>/`. |

`docs/old/` holds the notes from the first, from-scratch version (the hand-written painter), kept for reference.

## Your work (in the folder of the app you launched: the project folder, or EXE Build for the .exe)

| Folder | What goes in it |
|---|---|
| `images/` (pictures at the top level) | Every picture: drawings you save, AI Images results, edited photos. Every "open a picture" box starts here. |
| `videos/` | Videos (when AI Videos is built). |
| `code/` | Code from AI Coding (each code block as its own file). |
| `chats/` | Chats you save from AI Chat. |

`systems/AI Images/Image Engine/imaging.py` is the image engine; `systems/AI Images/image_pages.py` is its Text to Image and Image to Image pages.
