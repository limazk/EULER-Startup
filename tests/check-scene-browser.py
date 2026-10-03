"""Check the real WebGL scene and its boundary with the demonstration."""
import os
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "tests" / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)
URL = os.environ.get("EULER_TEST_URL", "http://127.0.0.1:8766/")

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/usr/bin/chromium",
        headless=True,
        args=["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
    )
    for width, height in [(1440, 1000), (375, 900)]:
        page = browser.new_page(viewport={"width": width, "height": height})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(URL, wait_until="networkidle")
        expect(page.locator("#loader")).to_have_class("is-done")
        assert not page.locator("body").evaluate("e => e.classList.contains('reading')"), "WebGL fallback: scene not tested"
        # Sample a rendered frame, not just the canvas element's dimensions.
        assert page.evaluate("""() => new Promise(resolve => requestAnimationFrame(() => {
          const canvas = document.createElement('canvas');
          canvas.width = 64; canvas.height = 64;
          const ctx = canvas.getContext('2d');
          ctx.drawImage(document.getElementById('webgl'), 0, 0, 64, 64);
          const pixels = ctx.getImageData(0, 0, 64, 64).data;
          const colors = new Set();
          for (let i = 0; i < pixels.length; i += 4)
            colors.add(`${pixels[i]},${pixels[i+1]},${pixels[i+2]},${pixels[i+3]}`);
          resolve(colors.size > 20);
        }))"""), "Canvas is blank or uniform"
        page.screenshot(path=str(ARTIFACTS / f"scene-{width}.png"))
        page.get_by_role("link", name="Testar a EULER").click()
        expect(page.locator("body")).to_have_class(re.compile("euler-demo-active"))
        for selector in ["#webgl", "#labels", "#hotspots", ".float-panel"]:
            for element in page.locator(selector).all():
                expect(element).to_be_hidden()
        page.screenshot(path=str(ARTIFACTS / f"demo-section-{width}.png"))
        demo = page.locator("euler-demo")
        demo.get_by_role("button", name="Experimentar a EULER", exact=True).click()
        expect(page.locator("body")).to_have_class(re.compile("euler-demo-open"))
        expect(demo.locator("dialog")).to_be_visible()
        page.screenshot(path=str(ARTIFACTS / f"demo-modal-{width}.png"))
        page.keyboard.press("Escape")
        expect(demo.locator("dialog")).to_be_hidden()
        page.evaluate("window.scrollTo(0, 0)")
        expect(page.locator("#webgl")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not errors, errors
        print(f"PASS scene, demo isolation, modal and return at {width}px", flush=True)
        page.close()
    browser.close()
