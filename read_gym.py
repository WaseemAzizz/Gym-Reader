import easyocr
import csv
import os
import time
import random
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import pandas as pd
import numpy as np


# --- SETTINGS ---
PROFILE_TO_SCRAPE = "westernrecuserstats"
TARGETS = ["3rd floor", "4th floor"]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_PATH = os.path.join(BASE_DIR, "latest_post.png")
CSV_PATH = os.path.join(BASE_DIR, "gym_stats.csv")
SESSION_PATH = os.path.join(BASE_DIR, "instagram_session.json")
LOG_PATH = os.path.join(BASE_DIR, "gym_tracker.log")
GRAPH_PATH = os.path.join(BASE_DIR, "gym_graph.png")


# ─── LOGGING SETUP ────────────────────────────────────────────────────────────

def setup_logger():
    """
    Sets up a logger that writes to both the console and a rotating log file.
    Each log line includes timestamp, level, and message.
    """
    logger = logging.getLogger("GymTracker")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s  [%(levelname)-8s]  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler — keeps full history
    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler — INFO and above only
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

log = setup_logger()


# ─── SESSION SAVE ─────────────────────────────────────────────────────────────

def save_session():
    """
    Opens a browser for you to log in manually.
    Saves the session so future runs skip login entirely.
    Run once: python read_gym.py --save-session
    """
    log.info("Opening browser — please log into Instagram manually.")
    log.info("The session will be saved automatically once you're logged in.")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-position=100,100"]
        )
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto("https://www.instagram.com/accounts/login/")

        input("\n>>> Log into Instagram in the browser, then press Enter here to save the session...")

        context.storage_state(path=SESSION_PATH)
        log.info(f"Session saved to {SESSION_PATH}. Future runs will skip login.")
        browser.close()


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def get_last_post_url():
    """Read the last scraped post URL from the CSV to avoid duplicates."""
    if not os.path.isfile(CSV_PATH):
        log.debug("CSV does not exist yet — no previous URL to compare.")
        return None
    with open(CSV_PATH, mode='r', encoding='utf-8') as file:
        rows = list(csv.reader(file))
        for row in reversed(rows):
            if len(row) >= 4 and row[3].startswith("https://"):
                log.debug(f"Last recorded post URL: {row[3]}")
                return row[3]
    return None


# ─── GRAPH ────────────────────────────────────────────────────────────────────

def generate_graph():
    """
    Produces a two-panel graph:
      Top   — Raw occupancy for the past 14 days (line chart)
      Bottom — Average occupancy by hour for the current day-of-week
               with the 3 quietest hours highlighted as 'best times'
    """
    log.info("Generating graph...")

    if not os.path.isfile(CSV_PATH):
        log.warning("CSV not found — skipping graph generation.")
        return

    df = pd.read_csv(CSV_PATH)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df['Occupancy'] = pd.to_numeric(df['Occupancy'], errors='coerce')
    df = df.dropna(subset=['Occupancy'])

    if df.empty:
        log.warning("No valid occupancy data — skipping graph generation.")
        return

    # ── Panel 1: 14-day raw history ──────────────────────────────────────────
    totals = (
        df.groupby('Timestamp')['Occupancy']
        .sum()
        .reset_index()
        .rename(columns={'Occupancy': 'Total'})
        .sort_values('Timestamp')
    )

    cutoff_14d = pd.Timestamp.now() - pd.Timedelta(days=14)
    totals_14d = totals[totals['Timestamp'] >= cutoff_14d].copy()

    # ── Panel 2: average by hour for today's day-of-week ────────────────────
    today_dow = datetime.now().weekday()           # 0=Mon … 6=Sun
    dow_name  = datetime.now().strftime("%A")

    df_dow = df[df['Timestamp'].dt.dayofweek == today_dow].copy()
    df_dow['Hour'] = df_dow['Timestamp'].dt.hour

    # Sum floors per timestamp first, then average per hour
    ts_totals = df_dow.groupby('Timestamp')['Occupancy'].sum().reset_index()
    ts_totals['Hour'] = ts_totals['Timestamp'].dt.hour
    hourly_avg = ts_totals.groupby('Hour')['Occupancy'].mean().reset_index()
    hourly_avg.columns = ['Hour', 'AvgOccupancy']

    # Gym open hours only (7 AM – 11 PM)
    hourly_avg = hourly_avg[(hourly_avg['Hour'] >= 7) & (hourly_avg['Hour'] <= 22)]

    # ── Layout ───────────────────────────────────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 11),
        gridspec_kw={'height_ratios': [3, 2], 'hspace': 0.45}
    )
    fig.patch.set_facecolor('#1e1e2e')
    for ax in (ax1, ax2):
        ax.set_facecolor('#1e1e2e')
        for spine in ax.spines.values():
            spine.set_edgecolor('#444444')
        ax.tick_params(colors='#aaaaaa')
        ax.grid(True, color='#333344', linestyle='--', alpha=0.5)

    # ── Panel 1 ──────────────────────────────────────────────────────────────
    if not totals_14d.empty:
        ax1.plot(
            totals_14d['Timestamp'], totals_14d['Total'],
            marker='o', color='#a78bfa', linewidth=2, markersize=5
        )
        # Label every point
        for _, row in totals_14d.iterrows():
            ax1.annotate(
                str(int(row['Total'])),
                (row['Timestamp'], row['Total']),
                textcoords="offset points", xytext=(0, 8),
                ha='center', color='#c4b5fd', fontsize=8
            )
        # Shade weekend bands
        date_range = pd.date_range(
            start=totals_14d['Timestamp'].min().normalize(),
            end=totals_14d['Timestamp'].max().normalize() + pd.Timedelta(days=1),
            freq='D'
        )
        for d in date_range:
            if d.weekday() >= 5:  # Sat / Sun
                ax1.axvspan(d, d + pd.Timedelta(days=1),
                            color='#312e81', alpha=0.25, zorder=0)

        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %d %H:%M'))
        ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax1.xaxis.set_tick_params(rotation=35)
    else:
        ax1.text(0.5, 0.5, 'Not enough data yet (need 14 days)',
                 transform=ax1.transAxes, ha='center', va='center',
                 color='#aaaaaa', fontsize=12)

    ax1.set_title(
        'Western Rec Centre — Total Occupancy (3rd + 4th Floor) · Last 14 Days',
        color='white', fontsize=13, pad=12
    )
    ax1.set_xlabel('Date / Time', color='#aaaaaa', fontsize=10)
    ax1.set_ylabel('Number of People', color='#aaaaaa', fontsize=10)

    weekend_patch = mpatches.Patch(color='#312e81', alpha=0.5, label='Weekend')
    ax1.legend(handles=[weekend_patch], facecolor='#2a2a3e', labelcolor='#aaaaaa',
               fontsize=9, loc='upper left')

    # ── Panel 2 ──────────────────────────────────────────────────────────────
    if not hourly_avg.empty:
        # Identify 3 quietest hours
        quietest = set(hourly_avg.nsmallest(3, 'AvgOccupancy')['Hour'].tolist())

        bar_colors = [
            '#22c55e' if h in quietest else '#a78bfa'
            for h in hourly_avg['Hour']
        ]
        bars = ax2.bar(
            hourly_avg['Hour'], hourly_avg['AvgOccupancy'],
            color=bar_colors, width=0.7, zorder=2
        )

        # Value labels on bars
        for bar, (_, row) in zip(bars, hourly_avg.iterrows()):
            ax2.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1.5,
                f"{row['AvgOccupancy']:.0f}",
                ha='center', va='bottom', color='#c4b5fd', fontsize=8
            )

        # Annotate best hours
        for h in quietest:
            row = hourly_avg[hourly_avg['Hour'] == h].iloc[0]
            ax2.annotate(
                '★ Best',
                xy=(row['Hour'], row['AvgOccupancy']),
                xytext=(0, 22), textcoords='offset points',
                ha='center', color='#22c55e', fontsize=8, fontweight='bold'
            )

        ax2.set_xticks(hourly_avg['Hour'])
        ax2.set_xticklabels(
            [f"{h}:00" for h in hourly_avg['Hour']],
            rotation=35, color='#aaaaaa', fontsize=8
        )

        quiet_patch  = mpatches.Patch(color='#22c55e', label='★ Best 3 times to go')
        normal_patch = mpatches.Patch(color='#a78bfa', label='Other hours')
        ax2.legend(handles=[quiet_patch, normal_patch],
                   facecolor='#2a2a3e', labelcolor='#aaaaaa', fontsize=9)

        n_days = df_dow['Timestamp'].dt.date.nunique()
        ax2.set_title(
            f'Average Occupancy by Hour — {dow_name}s  (based on {n_days} day(s) of data)',
            color='white', fontsize=12, pad=10
        )
    else:
        ax2.text(
            0.5, 0.5,
            f'No {dow_name} data yet — check back after a full week of tracking.',
            transform=ax2.transAxes, ha='center', va='center',
            color='#aaaaaa', fontsize=11
        )
        ax2.set_title(
            f'Best Times to Go — {dow_name}s (no data yet)',
            color='white', fontsize=12, pad=10
        )

    ax2.set_xlabel('Hour of Day', color='#aaaaaa', fontsize=10)
    ax2.set_ylabel('Avg People', color='#aaaaaa', fontsize=10)

    # ── Save ─────────────────────────────────────────────────────────────────
    plt.savefig(GRAPH_PATH, dpi=150, bbox_inches='tight')
    plt.close()
    log.info(f"Graph saved to {GRAPH_PATH}")

    # Log the top 3 best times for today as a convenience
    if not hourly_avg.empty:
        best = hourly_avg.nsmallest(3, 'AvgOccupancy')
        times_str = ", ".join(f"{int(h)}:00 (~{avg:.0f} people)"
                              for h, avg in zip(best['Hour'], best['AvgOccupancy']))
        log.info(f"Best times for {dow_name}: {times_str}")


# ─── SCRAPE ───────────────────────────────────────────────────────────────────

def scrape_and_save():
    """Main scrape run — uses saved session, no login needed."""
    log.info("=" * 60)
    log.info(f"Gym Tracker run starting")

    if not os.path.exists(SESSION_PATH):
        log.error("No session file found at: " + SESSION_PATH)
        log.error("Run with --save-session first:  python read_gym.py --save-session")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
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
            log.info(f"Navigating to Instagram profile: @{PROFILE_TO_SCRAPE}")
            page.goto(
                f"https://www.instagram.com/{PROFILE_TO_SCRAPE}/",
                wait_until="domcontentloaded",
                timeout=60000
            )
            time.sleep(random.uniform(2, 4))

            log.debug("Waiting for post grid to load...")
            page.wait_for_selector("a[href*='/p/']", timeout=15000)
            time.sleep(2)

            first_post = page.locator("a[href*='/p/']").first
            first_post.click(timeout=15000)
            time.sleep(random.uniform(2, 3))

            post_url = page.url
            log.info(f"Latest post URL: {post_url}")

            last_url = get_last_post_url()
            if last_url == post_url:
                log.info("SKIP — post unchanged since last run (no new Instagram post yet).")
                browser.close()
                return

            log.info("New post detected — taking screenshot...")
            post_image = page.locator("article img").first
            post_image.screenshot(path=SCREENSHOT_PATH)
            log.info(f"Screenshot saved to {SCREENSHOT_PATH}")

        except Exception as e:
            log.error(f"Scraping failed: {type(e).__name__}: {e}")
            browser.close()
            return

        browser.close()

    # ── OCR ──────────────────────────────────────────────────────────────────
    log.info("Running OCR on screenshot...")
    reader = easyocr.Reader(['en'])
    results = reader.readtext(SCREENSHOT_PATH)

    raw_texts = [text for (_, text, _) in results]
    log.debug(f"OCR raw output: {raw_texts}")

    found = {}
    for (_, text, _) in results:
        for area in TARGETS:
            if area.lower() in text.lower():
                try:
                    count = text.split(':')[-1].strip()
                    found[area] = count
                    log.info(f"OCR found → {area}: {count}")
                except Exception as e:
                    log.warning(f"OCR parse error for '{text}': {e}")

    missing = [t for t in TARGETS if t not in found]
    if missing:
        log.warning(f"OCR could not extract data for: {missing}  — will record as N/A")

    # ── CSV write ─────────────────────────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    file_exists = os.path.isfile(CSV_PATH)

    with open(CSV_PATH, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['Timestamp', 'Location', 'Occupancy', 'Post URL'])
            log.info("CSV created with headers.")
        for area in TARGETS:
            occupancy = found.get(area, "N/A")
            writer.writerow([timestamp, area, occupancy, post_url])
            log.info(f"CSV row written: [{timestamp}] {area} → {occupancy}")

    log.info("Scrape complete.")


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if "--save-session" in sys.argv:
        save_session()

    elif "--graph-only" in sys.argv:
        # Useful for regenerating the graph without scraping
        log.info("Graph-only mode.")
        generate_graph()

    else:
        now = datetime.now()
        log.info(f"Scheduler triggered at {now.strftime('%Y-%m-%d %H:%M:%S')}")

        if not (7 <= now.hour < 23):
            log.info(
                f"SKIP — outside gym hours (7AM–11PM). "
                f"Current time: {now.strftime('%H:%M')}. No scrape needed."
            )
        else:
            scrape_and_save()
            generate_graph()

    log.info("Run finished.")
    log.info("-" * 60)