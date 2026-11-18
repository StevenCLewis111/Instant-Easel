# Setting up the text model on your PC

The text model reads what you type in the app. It's a free, open model (Qwen3, Apache 2.0) that runs on your own PC: nothing is
sent anywhere. It's several GB, so it isn't stored on GitHub; the app downloads it once into `my-models/text/`.

You only do steps 1-5 once.

## 1. Get the latest code
In your copy of the repo, pull the newest version:
- **GitHub Desktop:** open the repo, press **Fetch origin**, then **Pull origin**.
- **Command line:** open a terminal in the repo folder and run `git pull`.

## 2. Make sure Python 3.12 is installed
Open a terminal (Start menu, type `cmd`, Enter) and run `python --version`. If it doesn't say 3.10 or newer, install Python 3.12
from https://www.python.org/downloads/ and tick **"Add python.exe to PATH"** on the first screen of the installer.

## 3. Open a terminal in the Instant Easel Pro folder
In File Explorer, open the `Instant Easel Pro` folder, click the address bar, type `cmd` and press Enter. A terminal opens there.

## 4. Install the add-ons
Run these one at a time (each takes a few minutes the first time):

```
python -m pip install -r requirements.txt
```

**Only if you have an NVIDIA graphics card** (it lets the model use the card; much faster, and training needs it):
```
python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
```

Then, for everyone:
```
python -m pip install -r requirements-ai.txt
```

Intel Arc and AMD graphics cards aren't supported by this kind of model yet: the model runs on your processor instead (it works,
just slower, and training is very slow).

## 5. Start the app and download the model
```
python main.py
```
Go to **Settings > Text Model**.
- The second line under MODEL says which graphics card it found (or that it's using the processor).
- **Model size** `auto` picks for you: the 4B model with an NVIDIA card of 8 GB or more, otherwise the 1.7B.
- Press **Download the model** and wait until it says *downloaded* (4-8 GB; the percentage counts up).

The .exe in `EXE Build` doesn't include the text model (it would be several GB). To use the text model, start the app with
`python main.py` as above.

## Using it

**Type anything.** In **AI Images > Text to Image**, type a request in your own words and press Generate. Under *What I understood*,
items marked **(AI)** came from the text model. The first time, it takes a little while to load.

**Teach it.** **AI Training > Words > Teach a new word or phrase**: what you teach goes into the AI Images tab's memory straight
away (the model uses it as an example at once).

**Train a tab.** **Settings > Text Model > Train** next to a tab bakes everything that tab was taught into its own small add-on.
The base model and the other tabs don't change. Training runs in the background; the status line shows how far it is.

**Send learning to another tab.** Settings > Text Model > *Send learning to another tab*: pick From and To, press **Send**.
Nothing moves between tabs any other way.

**Forget a tab.** **Forget** next to a tab deletes only that tab's memory.

## Learning from scraped pictures
1. **AI Training > Image Scraper:** type keywords (one per line), press **Start**.
2. When it's done, press **Review & learn**. Every scraped picture opens in Learn from Images' review.
3. Check each one: change *shows* if its label is wrong, and switch off **use it** for any picture you don't want.
4. Press **Add to library**. The pictures you kept go into the learning library; the scraped files are deleted, kept or not.
5. Press **Learn** in Learn from Images. With **Keep training copies** off, each picture is deleted once it's been learned.

## Where things are
- `my-models/text/base/`: the downloaded model (never uploaded to GitHub).
- `my-models/text/tabs/<Tab>/`: each tab's memory (`examples.jsonl`) and its trained add-on (`adapter/`).
- `systems/Core/brain.py`: the code that runs it.
