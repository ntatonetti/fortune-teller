"""Drives one full reading in Chrome with a fake camera and saves screenshots.

Usage: [ADULT=1] .venv/bin/python scripts/smoke.py [outdir]   (server must be running on :8000)
ADULT=1 forces adult mode and a mid-fortune glitch. HEAD=1 runs in foam-head mode
and also screenshots the alignment screen. SECRET=1 pays with a whispered secret and
asks a question (a fake microphone stands in for speech recognition). WALKAWAY=1 has
the guest walk off at the payment step (WALKAWAY=speak: during the fortune) and checks that she shuts down. A steady fake face
stands in for the camera so the fake video's flicker can't trigger walk-away.
"""

import sys
import time
from pathlib import Path

import os

from playwright.sync_api import sync_playwright

# Browsers live inside the project venv, not the global cache.
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(Path(__file__).resolve().parent.parent / ".venv" / "ms-playwright"))

out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/oracle-smoke")
out.mkdir(parents=True, exist_ok=True)
errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(
        args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required"],
    )
    page = browser.new_page(viewport={"width": 1600, "height": 900})
    # A silent stand-in for Chrome's speech recognition; words arrive via window.oracleHear.
    page.add_init_script(
        "window.webkitSpeechRecognition = class { start() {} stop() {} abort() {} };"
    )
    page.on("console", lambda m: m.type in ("error",) and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://localhost:8000/")
    page.wait_for_timeout(1500)
    if os.getenv("HEAD"):
        page.select_option("#displaySelect", "head")
    page.screenshot(path=out / "0-setup.png")
    page.click("#beginBtn")
    page.wait_for_timeout(3000)
    page.evaluate("window.oracleFakeFace(null)")  # nobody yet
    page.keyboard.press("d")
    if os.getenv("ADULT"):
        page.keyboard.press("a")  # force adult mode
        page.keyboard.press("g")  # and a mid-fortune glitch
    page.screenshot(path=out / "1-asleep.png")

    def state():
        return page.evaluate("window.oracleState()")

    page.evaluate("window.oracleFakeFace({x: 0.5, y: 0.45, w: 0.2, h: 0.26})")  # a guest walks up
    page.wait_for_timeout(1200)
    page.screenshot(path=out / "2-waking.png")
    t0 = time.time()
    while "invite" not in state() and time.time() - t0 < 20:
        page.wait_for_timeout(200)
    page.screenshot(path=out / "3-invite.png")
    print("reached:", state())
    page.keyboard.press("d")

    def hear(text):
        t1 = time.time()
        while not page.evaluate("window.oracleListening()") and time.time() - t1 < 30:
            page.wait_for_timeout(200)
        page.evaluate(f"window.oracleHear({text!r})")

    if os.getenv("WALKAWAY"):
        if os.getenv("WALKAWAY") == "speak":  # pay, then leave in the middle of the fortune
            page.keyboard.press("Space")
            t1 = time.time()
            while state() != "speak" and time.time() - t1 < 60:
                page.wait_for_timeout(200)
            print("reached:", state())
        page.evaluate("window.oracleFakeFace(null)")  # ...and walks off
        t1 = time.time()
        while state() not in ("farewell", "sleep") and time.time() - t1 < 20:
            page.wait_for_timeout(200)
        print(f"walked away -> {state()} after {time.time() - t1:.1f}s")
        page.screenshot(path=out / "4-walked-away.png")
        while state() != "sleep" and time.time() - t1 < 30:
            page.wait_for_timeout(200)
        print("then:", state())
        browser.close()
        print("errors:", errors or "none")
        sys.exit(0)

    if os.getenv("SECRET"):
        hear("I secretly ate the last cupcake")
        t1 = time.time()
        while state() != "ask" and time.time() - t1 < 30:
            page.wait_for_timeout(200)
        print("reached:", state())
        hear("Will I find the buried treasure tonight")
    else:
        page.keyboard.press("Space")
    page.wait_for_timeout(2500)
    page.screenshot(path=out / "4-consult.png")
    while "speak" not in state() and time.time() - t0 < 40:
        page.wait_for_timeout(200)
    page.wait_for_timeout(2500)
    page.screenshot(path=out / "5-speaking.png")
    print("reached:", state())
    while "sleep" not in state() and time.time() - t0 < 120:
        page.wait_for_timeout(300)
    print("back to:", state(), f"after {time.time() - t0:.0f}s")
    if os.getenv("HEAD"):
        page.keyboard.press("c")
        page.keyboard.press("p")
        page.mouse.move(800, 300)
        page.wait_for_timeout(600)
        page.screenshot(path=out / "6-align.png")
        # drag the face's top-left corner and check the warp follows
        handle = page.locator(".handle[data-surface=face][data-index='0']")
        box = handle.bounding_box()
        page.mouse.move(box["x"] + 9, box["y"] + 9)
        page.mouse.down()
        page.mouse.move(box["x"] - 40, box["y"] + 30, steps=5)
        page.mouse.up()
        page.wait_for_timeout(300)
        page.screenshot(path=out / "7-align-warped.png")
        saved = page.evaluate("JSON.parse(localStorage.getItem('oracle-headmap')).face[0]")
        print("face corner after drag:", [round(v) for v in saved])
        page.keyboard.press("Escape")
    browser.close()

print("errors:", errors or "none")
print("screenshots in", out)
