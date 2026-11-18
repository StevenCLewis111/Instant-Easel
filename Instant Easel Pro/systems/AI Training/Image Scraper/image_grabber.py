import base64
import colorsys
import hashlib
import json
import os
import queue
import random
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from io import BytesIO
from tkinter import messagebox, scrolledtext
from urllib.parse import quote_plus

import requests
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.firefox.options import Options

# ==== SETTINGS ====
IMAGES_PER_WORD = 20  # values change here
MAX_WORDS = 20  # values change here
CLICK_WAIT = 1.2  # values change here
PAGE_WAIT = 3.0  # values change here
DOWNLOAD_TIMEOUT = 15  # values change here
CAPTCHA_MAX_WAIT = 300  # values change here
MAX_SCROLLS = 12  # values change here
OUTPUT_FOLDER_NAME = "images"  # values change here
START_HIDDEN = True  # values change here
MANIFEST_NAME = "_saved.json"  # values change here
PROFILE_FOLDER_NAME = "firefox_profile"  # Firefox keeps its cookies here, so a solved CAPTCHA carries over (between runs too)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0"

# ==== THEME ====
THEME_FONT = "Courier New"  # values change here
THEME_OUTER = "#0a0e17"  # values change here
THEME_PANEL = "#151b2b"  # values change here
THEME_FIELD = "#0d1220"  # values change here
THEME_BORDER = "#22ff66"  # values change here
THEME_TITLE = "#ffd700"  # values change here
THEME_TEXT = "#ffffff"  # values change here
THEME_BLUE = "#264f94"  # values change here
THEME_GREEN = "#28a745"  # values change here
THEME_RED = "#dc3545"  # values change here
THEME_DISABLED_BG = "#1a1f2e"  # values change here
THEME_DISABLED_FG = "#5a6278"  # values change here
THEME_FILE_NAME = "image_grabber_theme.json"  # values change here
THEME_MIN_OPACITY = 0.3  # values change here

# ==== JAVASCRIPT ====
JS_THUMBS = """
return Array.from(document.images).filter(function(i){
  var r = i.getBoundingClientRect();
  return i.naturalWidth >= 80 && r.width >= 80 && r.height >= 80 &&
    (i.src.indexOf('data:image') === 0 || i.src.indexOf('encrypted-tbn') !== -1);
});
"""

JS_TAB_FETCH = """
var done = arguments[arguments.length - 1];
fetch(location.href, {credentials: 'include'}).then(function(r){
  if (!r.ok) throw new Error('HTTP ' + r.status);
  var t = r.headers.get('content-type') || '';
  if (t.indexOf('image') !== 0) throw new Error('not an image (' + t + ')');
  return r.blob();
}).then(function(b){
  var fr = new FileReader();
  fr.onload = function(){ done(fr.result); };
  fr.onerror = function(){ done('ERR:could not read the image'); };
  fr.readAsDataURL(b);
}).catch(function(e){ done('ERR:' + e.message); });
"""

JS_FULL = """
var out = [];
document.querySelectorAll('img').forEach(function(i){
  var s = i.src || '';
  if (s.indexOf('http') === 0 && s.indexOf('encrypted-tbn') === -1 &&
      s.indexOf('gstatic.com') === -1 && s.indexOf('google.com') === -1 &&
      i.naturalWidth >= 200) { out.push([s, i.naturalWidth]); }
});
out.sort(function(a, b){ return b[1] - a[1]; });
return out.map(function(x){ return x[0]; });
"""


# ==== HELPERS ====
def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


try:                                                               # inside Instant Easel: its logs/ and images/Image Scraper/ folders
    import paths as _paths
    LOG_FILE = _paths.log_file("image_grabber_log.txt"); OUTPUT_DIR = _paths.saved_images("Image Scraper", "x")[:-2]
    PROFILE_DIR = _paths.data(PROFILE_FOLDER_NAME)
except ImportError:                                                # on its own: everything beside it, as before
    LOG_FILE = os.path.join(app_dir(), "image_grabber_log.txt")
    OUTPUT_DIR = os.path.join(app_dir(), OUTPUT_FOLDER_NAME)
    PROFILE_DIR = os.path.join(app_dir(), PROFILE_FOLDER_NAME)


def google_cookie(cookie):
    """a cookie cleaned up so Firefox will take it on www.google.com, or None if it belongs to another site.
    Firefox refuses a cookie whose domain doesn't match the open page, an expiry that isn't a whole number, or a
    sameSite value it doesn't know; those refusals were the 'cookie copy failed' errors."""
    domain = (cookie.get("domain") or "").lower()
    if domain not in ("google.com", ".google.com", "www.google.com", ".www.google.com"):
        return None
    out = {"name": cookie["name"], "value": cookie["value"], "path": cookie.get("path") or "/",
           "secure": bool(cookie.get("secure", False)), "httpOnly": bool(cookie.get("httpOnly", False))}
    if domain in ("google.com", ".google.com"):
        out["domain"] = ".google.com"  # shared with every google.com page; host-only www cookies keep no domain
    if cookie.get("expiry") is not None:
        out["expiry"] = int(cookie["expiry"])
    same = cookie.get("sameSite")
    if same in ("Strict", "Lax") or (same == "None" and out["secure"]):
        out["sameSite"] = same
    return out


def safe_name(text):
    cleaned = "".join(c if c.isalnum() or c in " -_" else "_" for c in text).strip()
    return cleaned[:60] or "untitled"


def fetch_bytes(src, referer):
    if src.startswith("data:"):
        return base64.b64decode(src.split(",", 1)[1])
    resp = requests.get(
        src,
        headers={"User-Agent": USER_AGENT, "Referer": referer},
        timeout=DOWNLOAD_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.content


def save_png(data, path):
    img = Image.open(BytesIO(data))
    if img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGBA")
    img.save(path, "PNG")


# ==== ONE FIREFOX PER APP LAUNCH ====
# After a run the hidden Firefox is kept (not quit), and the next run picks it up: Google sees the same browser that already
# passed its "are you a human" check, so the puzzle comes up at most once per launch. close_browser() quits it when the app closes.
_KEPT = {"driver": None, "closed": False}
_KEPT_LOCK = threading.Lock()
_OPEN = set()  # every Firefox this launch started, including one a scan is using right now


def _alive(driver):
    try:
        driver.window_handles
        return True
    except Exception:
        return False


def take_browser():
    """-> the kept hidden Firefox (now owned by the caller), or None"""
    with _KEPT_LOCK:
        driver, _KEPT["driver"] = _KEPT["driver"], None
    if driver is not None and not _alive(driver):
        try:
            driver.quit()
        except Exception:
            pass
        return None
    return driver


def keep_browser(driver):
    """keep a hidden Firefox for the next run (if one is already kept, this one closes)"""
    with _KEPT_LOCK:
        if _KEPT["driver"] is None and not _KEPT["closed"]:
            _KEPT["driver"] = driver
            return
    _OPEN.discard(driver)
    try:
        driver.quit()
    except Exception:
        pass


def close_browser():
    """quit every Firefox this launch opened: the kept one and any a scan is still using (the app calls this as it closes)"""
    with _KEPT_LOCK:
        _KEPT["closed"] = True
        _KEPT["driver"] = None
        drivers = list(_OPEN)
        _OPEN.clear()
    for driver in drivers:
        try:
            driver.quit()
        except Exception:
            pass


import atexit  # noqa: E402
atexit.register(close_browser)  # also closes it if the app ends some other way


# ==== SEARCH WORKER ====
class Grabber:
    def __init__(self, words, log, stop_event):
        self.words = words
        self.log = log
        self.stop = stop_event
        self.driver = None
        self.hidden = START_HIDDEN

    def run(self):
        try:
            self.driver = take_browser()
            if self.driver is not None:
                self.log("Using the Firefox already open (hidden) from the last run...")
            else:
                self.log("Starting Firefox...")
                self.driver = self.start_driver(START_HIDDEN)
        except Exception as e:
            self.log("ERROR starting Firefox (is Firefox installed? internet on?): %r" % e)
            return
        try:
            for word in self.words:
                if self.stop.is_set():
                    self.log("Stopped.")
                    break
                try:
                    self.grab_word(word)
                except Exception as e:
                    self.log("ERROR on '%s': %r" % (word, e))
        finally:
            if self.driver is not None and self.hidden and _alive(self.driver):
                keep_browser(self.driver)  # stays open, hidden, for the next run; closed when the app closes
            elif self.driver is not None:
                _OPEN.discard(self.driver)
                try:
                    self.driver.quit()
                except Exception:
                    pass
            self.log("Done.")

    def start_driver(self, hidden):
        """Firefox using the app's own profile folder, so cookies (a solved CAPTCHA included) are kept between the
        visible and hidden browser and between runs"""
        def make(use_profile):
            options = Options()
            if hidden:
                options.add_argument("-headless")
            if use_profile:
                os.makedirs(PROFILE_DIR, exist_ok=True)
                options.add_argument("-profile")
                options.add_argument(PROFILE_DIR)
            driver = webdriver.Firefox(options=options)
            driver.set_page_load_timeout(max(DOWNLOAD_TIMEOUT, 30))
            driver.set_script_timeout(DOWNLOAD_TIMEOUT)
            self.hidden = hidden
            _OPEN.add(driver)
            return driver
        try:
            return make(True)
        except Exception as e:
            self.log("  saved Firefox profile unavailable (%r); using a fresh one" % e)
            return make(False)

    def captcha_present(self, driver):
        current = driver.current_url.lower()
        return "/sorry/" in current or "captcha" in current

    def wait_solved(self, driver):
        waited = 0
        while self.captcha_present(driver):
            if self.stop.is_set() or waited >= CAPTCHA_MAX_WAIT:
                raise RuntimeError("Google CAPTCHA not solved in time")
            time.sleep(3)
            waited += 3

    def handle_captcha(self, url):
        if not self.captcha_present(self.driver):
            return
        if not START_HIDDEN:
            self.log("Google is asking for a CAPTCHA. Solve it in the Firefox window.")
            self.wait_solved(self.driver)
            return

        self.log("Google is asking for a CAPTCHA. Opening Firefox - solve it there.")
        self.driver.quit()
        self.driver = self.start_driver(False)
        self.driver.get(url)
        self.wait_solved(self.driver)
        time.sleep(1.0)  # let Google finish setting its cookies
        cookies = self.driver.get_cookies()
        self.log("CAPTCHA solved. Hiding the browser again.")

        # the visible browser closes first: it saves its cookies to the shared profile, and only one Firefox can use it at once
        self.driver.quit()
        self.driver = None
        hidden = self.start_driver(True)
        hidden.get("https://www.google.com/")
        added, skipped, failed = 0, 0, []
        for cookie in cookies:  # covers cookies that only last for the session (Firefox doesn't save those)
            clean = google_cookie(cookie)
            if clean is None:
                skipped += 1
                continue
            try:
                hidden.add_cookie(clean)
                added += 1
            except Exception as e:
                failed.append("%s (%s)" % (clean["name"], str(e).splitlines()[0][:80] if str(e) else type(e).__name__))
        self.log("  cookies: %d copied, %d for other sites left out%s" % (added, skipped, (", failed: " + "; ".join(failed)) if failed else ""))
        hidden.get(url)
        time.sleep(PAGE_WAIT)
        if not self.captcha_present(hidden):
            self.driver = hidden
            return
        self.log("Hidden browser was blocked again. Showing Firefox for the rest of this run.")
        hidden.quit()
        self.driver = self.start_driver(False)
        self.driver.get(url)
        time.sleep(PAGE_WAIT)
        if self.captcha_present(self.driver):
            self.log("Google wants the CAPTCHA once more - solve it in the Firefox window.")
            self.wait_solved(self.driver)

    def close_extra_tabs(self, keep):
        """close any tab except the search results (a click on a result can open the source site in a new tab)"""
        for handle in list(self.driver.window_handles):
            if handle != keep:
                try:
                    self.driver.switch_to.window(handle)
                    self.driver.close()
                except Exception:
                    pass
        self.driver.switch_to.window(keep)

    def fetch_in_tab(self, src, results_tab):
        """open one new tab, download the image there, close the tab, back to the results"""
        if src.startswith("data:"):
            return base64.b64decode(src.split(",", 1)[1])
        self.driver.switch_to.new_window("tab")
        try:
            try:
                self.driver.get(src)
            except Exception:
                self.driver.execute_script("window.stop();")  # slow page: use what has loaded
            got = self.driver.execute_async_script(JS_TAB_FETCH)
            if not got or got.startswith("ERR:"):
                raise RuntimeError((got or "ERR:nothing came back")[4:])
            return base64.b64decode(got.split(",", 1)[1])
        finally:
            self.close_extra_tabs(results_tab)

    def download(self, src, results_tab):
        """in a new tab first; if the site won't hand it over that way, a direct download"""
        try:
            return self.fetch_in_tab(src, results_tab)
        except Exception as tab_err:
            try:
                return fetch_bytes(src, self.driver.current_url)
            except Exception as direct_err:
                raise RuntimeError("tab: %s / direct: %r" % (tab_err, direct_err))

    def grab_word(self, word):
        out_dir = os.path.join(OUTPUT_DIR, safe_name(word))
        os.makedirs(out_dir, exist_ok=True)
        url = "https://www.google.com/search?tbm=isch&q=" + quote_plus(word)
        self.log("Searching: %s" % word)
        self.driver.get(url)
        time.sleep(PAGE_WAIT)
        self.handle_captcha(url)
        results_tab = self.driver.current_window_handle
        self.close_extra_tabs(results_tab)

        saved = 0
        index = 0
        scrolls = 0
        used_full = set()
        used_thumb = set()

        while saved < IMAGES_PER_WORD and not self.stop.is_set():
            thumbs = self.driver.execute_script(JS_THUMBS)
            if index >= len(thumbs):
                if scrolls >= MAX_SCROLLS:
                    self.log("  Ran out of results for '%s' (%d saved)" % (word, saved))
                    break
                self.driver.execute_script("window.scrollBy(0, 1500);")
                scrolls += 1
                time.sleep(1.0)
                continue

            thumb = thumbs[index]
            index += 1
            try:
                thumb_src = thumb.get_attribute("src") or ""
                if thumb_src in used_thumb:
                    continue
                used_thumb.add(thumb_src)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", thumb
                )
                time.sleep(0.3)
                try:
                    ActionChains(self.driver).move_to_element(thumb).click().perform()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", thumb)
                time.sleep(CLICK_WAIT)
                self.close_extra_tabs(results_tab)  # the click opened a tab: close it, stay on the results

                candidates = self.driver.execute_script(JS_FULL)
                if candidates and candidates[0] in used_full:
                    time.sleep(1.0)
                    candidates = self.driver.execute_script(JS_FULL)
                candidates = [c for c in candidates if c not in used_full]

                data = None
                chosen = None
                for cand in candidates[:3]:
                    try:
                        data = self.download(cand, results_tab)
                        chosen = cand
                        break
                    except Exception as e:
                        self.log("  full-size download failed (%s), trying next" % e)
                if data is None:
                    data = self.download(thumb_src, results_tab)
                    self.log("  using thumbnail for result %d" % (saved + 1))
                else:
                    used_full.add(chosen)

                path = os.path.join(out_dir, "%s_%02d.png" % (safe_name(word), saved + 1))
                save_png(data, path)
                saved += 1
                self.log("  saved %d/%d" % (saved, IMAGES_PER_WORD))
            except Exception as e:
                self.log("  ERROR on result %d: %r" % (index, e))
            time.sleep(random.uniform(0.2, 0.6))

        self.log("Finished '%s': %d images" % (word, saved))


# ==== GUI ====
class App:
    def __init__(self, root):
        self.root = root
        self.msgs = queue.Queue()
        self.stop_event = threading.Event()
        self.thread = None

        root.title("Image Grabber")
        root.geometry("640x620")
        root.configure(bg=THEME_OUTER)

        panel = tk.Frame(
            root,
            bg=THEME_PANEL,
            highlightbackground=THEME_BORDER,
            highlightcolor=THEME_BORDER,
            highlightthickness=2,
        )
        panel.pack(fill="both", expand=True, padx=14, pady=14)

        tk.Label(
            panel,
            text="IMAGE GRABBER",
            bg=THEME_PANEL,
            fg=THEME_TITLE,
            font=(THEME_FONT, 20, "bold underline"),
        ).pack(pady=(12, 8))

        tk.Label(
            panel,
            text="Keywords (one per line, max %d):" % MAX_WORDS,
            bg=THEME_PANEL,
            fg=THEME_TEXT,
            font=(THEME_FONT, 11, "bold"),
        ).pack(anchor="w", padx=16)
        self.words_box = scrolledtext.ScrolledText(
            panel,
            height=10,
            bg=THEME_FIELD,
            fg=THEME_TEXT,
            insertbackground=THEME_TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=THEME_BORDER,
            highlightcolor=THEME_BORDER,
            font=(THEME_FONT, 11),
        )
        self.words_box.pack(fill="x", padx=16, pady=(4, 0))

        btns = tk.Frame(panel, bg=THEME_PANEL)
        btns.pack(pady=12)
        self.start_btn = tk.Button(
            btns,
            text="Start",
            width=12,
            command=self.start,
            bg=THEME_GREEN,
            fg=THEME_TEXT,
            activebackground=THEME_GREEN,
            activeforeground=THEME_TEXT,
            disabledforeground=THEME_DISABLED_FG,
            relief="flat",
            cursor="hand2",
            font=(THEME_FONT, 11, "bold"),
        )
        self.start_btn.pack(side="left", padx=8)
        self.stop_btn = tk.Button(
            btns,
            text="Stop",
            width=12,
            command=self.stop,
            state="disabled",
            bg=THEME_DISABLED_BG,
            fg=THEME_TEXT,
            activebackground=THEME_RED,
            activeforeground=THEME_TEXT,
            disabledforeground=THEME_DISABLED_FG,
            relief="flat",
            cursor="hand2",
            font=(THEME_FONT, 11, "bold"),
        )
        self.stop_btn.pack(side="left", padx=8)

        self.log_box = scrolledtext.ScrolledText(
            panel,
            height=16,
            state="disabled",
            bg=THEME_FIELD,
            fg=THEME_TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=THEME_BORDER,
            highlightcolor=THEME_BORDER,
            font=(THEME_FONT, 10),
        )
        self.log_box.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        root.protocol("WM_DELETE_WINDOW", self.close)
        self.poll()

    def close(self):
        """closing the window also stops a search in progress"""
        self.stop_event.set()
        close_browser()
        self.root.destroy()

    def set_running(self, running):
        if running:
            self.start_btn.config(state="disabled", bg=THEME_DISABLED_BG)
            self.stop_btn.config(state="normal", bg=THEME_RED)
        else:
            self.start_btn.config(state="normal", bg=THEME_GREEN)
            self.stop_btn.config(state="disabled", bg=THEME_DISABLED_BG)

    def log(self, text):
        line = "[%s] %s" % (datetime.now().strftime("%H:%M:%S"), text)
        self.msgs.put(line)
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def poll(self):
        if not self.root.winfo_exists():  # window closed (when opened from Instant Easel)
            return
        while not self.msgs.empty():
            line = self.msgs.get()
            self.log_box.config(state="normal")
            self.log_box.insert("end", line + "\n")
            self.log_box.see("end")
            self.log_box.config(state="disabled")
        if self.thread is not None and not self.thread.is_alive():
            self.thread = None
            self.set_running(False)
        self.root.after(200, self.poll)

    def start(self):
        raw = self.words_box.get("1.0", "end").splitlines()
        words = []
        for w in raw:
            w = w.strip()
            if w and w not in words:
                words.append(w)
        if not words:
            messagebox.showwarning("Image Grabber", "Enter at least one keyword.")
            return
        if len(words) > MAX_WORDS:
            messagebox.showwarning("Image Grabber", "Max %d keywords at a time (you entered %d)." % (MAX_WORDS, len(words)))
            return
        try:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
        except Exception as e:
            self.log("ERROR creating folder %s: %r" % (OUTPUT_DIR, e))
            return

        self.stop_event.clear()
        self.set_running(True)
        grabber = Grabber(words, self.log, self.stop_event)
        self.thread = threading.Thread(target=grabber.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.log("Stopping after current image...")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
