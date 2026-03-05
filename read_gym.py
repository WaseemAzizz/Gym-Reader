import easyocr
import csv
import os
import time
import random
from datetime import datetime
from playwright.sync_api import sync_playwright

# --- SETTINGS ---
PROFILE_TO_SCRAPE = "westernrecuserstats"
TARGETS = ["3rd floor", "4th floor"]
SCREENSHOT_PATH = "latest_post.png"
CSV_PATH = "gym_stats.csv"
SESSION_PATH = "instagram_session.json"

def save_session():
    """
    Opens a browser for you to log in manually.
    Saves the session so future runs skip login entirely.
    Run this once by calling: python read_gym.py --save-session
    """
    print("Opening browser — please log into Instagram manually.")
    print("The session will be saved automatically once you're logged in.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto("https://www.instagram.com/accounts/login/")

        # Wait for the user to log in manually, then press Enter in terminal
        input("\n>>> Log into Instagram in the browser, then press Enter here to save the session...")

        context.storage_state(path=SESSION_PATH)
        print(f"Session saved to {SESSION_PATH}. Future runs will skip login.")
        browser.close()

def get_last_post_url():
    """Read the last scraped post URL from the CSV to avoid duplicates."""
    if not os.path.isfile(CSV_PATH):
        return None
    with open(CSV_PATH, mode='r', encoding='utf-8') as file:
        rows = list(csv.reader(file))
        # Find last row that has a post URL (4th column)
        for row in reversed(rows):
            if len(row) >= 4 and row[3].startswith("https://"):
                return row[3]
    return None

def scrape_and_save():
    """Main scrape run — uses saved session, no login needed."""
    if not os.path.exists(SESSION_PATH):
        print("No session found. Run with --save-session first:")
        print("  python read_gym.py --save-session")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n=== Gym Tracker Run: {timestamp} ===")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            storage_state=SESSION_PATH,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        try:
            print(f"Navigating to profile: {PROFILE_TO_SCRAPE}...")
            page.goto(f"https://www.instagram.com/{PROFILE_TO_SCRAPE}/", wait_until="domcontentloaded", timeout=60000)
            time.sleep(random.uniform(2, 4))

            # Wait for posts grid to load, then click the first one
            page.wait_for_selector("a[href*='/p/']", timeout=15000)
            time.sleep(2)
            first_post = page.locator("a[href*='/p/']").first
            first_post.click(timeout=15000)
            time.sleep(random.uniform(2, 3))

            # Get the current post URL to check for duplicates
            post_url = page.url
            print(f"Latest post URL: {post_url}")

            last_url = get_last_post_url()
            if last_url == post_url:
                print("No new post since last run. Skipping to avoid duplicates.")
                browser.close()
                return

            # Screenshot the post image
            post_image = page.locator("article img").first
            post_image.screenshot(path=SCREENSHOT_PATH)
            print(f"Screenshot saved to {SCREENSHOT_PATH}")

        except Exception as e:
            print(f"Scraping failed: {e}")
            browser.close()
            return

        browser.close()

    # OCR
    print("Running OCR...")
    reader = easyocr.Reader(['en'])
    results = reader.readtext(SCREENSHOT_PATH)

    found = {}
    for (_, text, _) in results:
        for area in TARGETS:
            if area.lower() in text.lower():
                try:
                    count = text.split(':')[-1].strip()
                    found[area] = count
                    print(f"Found: {area} -> {count}")
                except:
                    continue

    # Write to CSV
    file_exists = os.path.isfile(CSV_PATH)
    with open(CSV_PATH, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['Timestamp', 'Location', 'Occupancy', 'Post URL'])
        for area in TARGETS:
            occupancy = found.get(area, "N/A")
            writer.writerow([timestamp, area, occupancy, post_url])
            print(f"Saved: [{timestamp}] {area} - {occupancy}")

    print("Done.")

if __name__ == "__main__":
    import sys
    if "--save-session" in sys.argv:
        save_session()
    else:
        now = datetime.now()
        if not (9 <= now.hour < 23):
            print(f"Outside gym hours (9AM-11PM). Skipping run at {now.strftime('%H:%M')}.")
        else:
            scrape_and_save()