# Where everything lives (Instant Easel Pro)

Start the app with `python main.py` from this folder (or the built `InstantEaselPro.exe`).

| Folder | What's in it |
|---|---|
| `requirements.txt`, `requirements-ai.txt` | Add-ons to install (`requirements-ai.txt` is for the text model). |
| `main.py` | The app's window, its tabs and pages. Finds every script under `systems/` by itself. |
| `systems/` | The scripts, sorted by tab: `Core/` (shared by every tab), `Drawing/`, `AI Images/`, `AI Training/`, `Editing/`, `Settings/`. Each tab folder has a sub-folder per part of that tab where it helps (e.g. `AI Images/Engine`, `AI Training/Image Scraper`). |
| `systems/Core/paths.py` | The one place that knows where pictures, fonts, settings and logs are. Scripts ask it instead of building paths themselves. |
| `images/UI/` | Every picture the app shows, by the area it's used in: `Header`, `Splash`, `App Icon`, `Tabs and Menus`, `Status Dots`, `Draw Toolbar`, `Window Buttons`, `Brush Library`, `Color Wheel Menu`, `Sliders`, `Scroll Bars`, `Side Panel Bars`. |
| `images/UI/Brush Library/` | One picture per brush, `Section_Name/Brush_Name.png` (`_` is a space; the name is written on the tile from the file name). `_template.png` is the blank master: leave it unchanged. |
| `images/Styles/`, `images/Engine Examples/` | Reference paintings and example photos the painting engine uses. |
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
