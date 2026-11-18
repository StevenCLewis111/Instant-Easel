# Build audit: Painterly Image Engine (Nov 15)

## How it was checked
- **Packaged-app simulation:** only the files the `.exe` bundles (code, `styles/`, `fonts/`) were copied to an empty folder and every feature was run there. All passed: the old engine, the new landscape engine, label guessing, labeled learning and all 45 brushes.
- **Code review:** imports, file paths, packaging spec, error handling, threading and test coverage.
- **Test suite** (`evaluate.py`): every subject scored against its examples, with a dated scoreboard.

## Fixed in this audit
| Issue | Risk | Fix |
|---|---|---|
| Background threads updated the window directly (7 places) | **High**: random freezes or crashes on Windows | Updates now go through a thread-safe queue, polled on the main thread |
| Dev scripts with this machine's paths sat beside the app code | Low (not used by the app), but confusing | Moved to `dev/` |
| `test_scene.py` saved to a hard-coded folder | Low | Uses a `CMP` environment folder |

## Gaps closed (Nov 15, second pass)
| Gap | Status |
|---|---|
| No drawing canvas | **Built:** `paint_window.py`, with all 45 brushes grouped, size, opacity, color, paper, undo (25 steps), open image to paint on, save. Also **"Paint over this result by hand"**, which sends any engine painting into the canvas. |
| New engine limited to one test scene | **Built:** `landscape.py`, a scene builder: sunset or night, sun position, peaks, height, figures (0–2), rocks, grass, canyon, caption. The app opens it as a dialog. The test scene now runs *through* the builder with a fixed layout, so the scoreboard stays comparable (verified: 0.440 before and after). |
| Window never tested | **Tested** on a virtual screen (Tkinter + Xvfb installed here). The real app was opened and driven: main window, scene builder, drawing canvas with 8 brushes, paint-over. Screenshots in `planning/` notes. |
| Slow engine | Measured at **about 19 seconds** per full landscape (not 60). A low-quality preview saved only ~10%, so no preview switch was added. |

## Bugs found by the window test (fixed)
| Bug | Effect on Windows | Fix |
|---|---|---|
| The "after" picture panel was named `self.after`, **overwriting Tkinter's built-in `after` timer** | The thread-safe queue stopped after its first tick: **paintings finished but never appeared**, and the app looked stuck on "Painting…" | Panel renamed `after_lbl` |
| The control column was taller than an 800-pixel screen | Status line and progress bar hidden | The column scrolls (mouse wheel works), and it's widened to fit |

## Still open
1. **Two engines side by side** (`paint.py` for "Paint it" and the book's 93 illustrations, `painter2.py` for landscapes). → *move the book scenes onto the scene builder subject by subject, then retire `paint.py`*
2. **Pen-tablet pressure:** Tkinter doesn't report stylus pressure, so the canvas paints at full pressure. The brushes support pressure (the sampler shows it), but a tablet needs a different window toolkit (for example Qt) to read it.
3. **Learning is statistical,** not a neural network (see `RESEARCH.md`).

## Test status (latest scoreboard)
| Subject | Average vs all examples | Closest match | Trend |
|---|---|---|---|
| Scene vs the author's painting | 0.44 | — | — |
| Sky | 0.64 | 0.44 | — |
| Mountains | 0.77 | 0.56 | — |
| **Rock** | **1.11** | **0.33** | **much better (was 1.97)** |
| Grass | 1.25 | 0.36 | — |
| People | 1.20 | 0.47 | — |
