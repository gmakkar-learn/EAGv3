"""
Run once to capture UI screenshots for README.md.
Usage:  python3 docs/take_screenshots.py
Requires: pip install playwright && playwright install chromium
Server must be running on http://localhost:8000
"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent / "screenshots"
OUT.mkdir(exist_ok=True)

URL = "http://localhost:8000/static/index.html"
VIEWPORT = {"width": 1280, "height": 900}

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport=VIEWPORT)
    page.goto(URL, wait_until="networkidle")

    # ── 01: Selector card ──────────────────────────────────────────────────
    card = page.locator(".card").first
    card.screenshot(path=str(OUT / "01-selector.png"))
    print("✓ 01-selector.png")

    # ── Click Build Portfolio and wait for results ─────────────────────────
    print("  Clicking Build Portfolio (may take 60–90s on first run)…")
    page.click("#buildBtn")

    # Wait for the results div to become visible (up to 3 minutes)
    page.wait_for_selector("#results", state="visible", timeout=180_000)
    # Give JS a moment to finish rendering
    time.sleep(1)

    # ── 02: Portfolio Metrics card ─────────────────────────────────────────
    metrics_card = page.locator(".card").nth(1)
    metrics_card.screenshot(path=str(OUT / "02-metrics.png"))
    print("✓ 02-metrics.png")

    # ── 03: Portfolio Holdings card ────────────────────────────────────────
    holdings_card = page.locator(".card").nth(2)
    holdings_card.screenshot(path=str(OUT / "03-holdings.png"))
    print("✓ 03-holdings.png")

    # ── 04: Verification card ──────────────────────────────────────────────
    verification_card = page.locator(".card").nth(3)
    verification_card.screenshot(path=str(OUT / "04-verification.png"))
    print("✓ 04-verification.png")

    # ── 05: Tooltip open on first metric tile ──────────────────────────────
    # Click the ℹ on Jensen's Alpha tile to show tooltip, then screenshot
    info_btn = page.locator(".info-btn").first
    info_btn.click()
    time.sleep(0.3)
    metrics_card.screenshot(path=str(OUT / "05-metric-tooltip.png"))
    info_btn.click()  # close
    print("✓ 05-metric-tooltip.png")

    # ── 06: Stock info tooltip ─────────────────────────────────────────────
    # Click the ℹ on first holdings row
    stock_info_btn = page.locator("td.ticker-cell .info-btn").first
    stock_info_btn.click()
    time.sleep(0.3)
    holdings_card.screenshot(path=str(OUT / "06-stock-tooltip.png"))
    stock_info_btn.click()  # close
    print("✓ 06-stock-tooltip.png")

    browser.close()

print(f"\nAll screenshots saved to {OUT}")
