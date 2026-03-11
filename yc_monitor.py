#!/usr/bin/env python3
"""
YC Status Monitor - Y Combinator Application Status Tracker
Checks your YC application status and notifies you via Telegram when it changes.

Uses Playwright for real browser session (handles YC login automatically).
"""

import os
import sys
import json
import time
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("[ERROR] Missing dependencies. Run: pip install -r requirements.txt")
    sys.exit(1)


# ─── Paths ────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
STATE_FILE = BASE_DIR / ".last_state"
SESSION_DIR = BASE_DIR / ".browser_session"

YC_HOME = "https://apply.ycombinator.com/home"


# ─── Config ───────────────────────────────────────────────────────
def load_config() -> dict:
    """Load config from file or environment variables."""
    config = {}
    config["telegram_token"] = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    config["telegram_chat_id"] = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not all(config.values()) and CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            file_cfg = json.load(f)
        config["telegram_token"] = config["telegram_token"] or file_cfg.get("telegram_token", "")
        config["telegram_chat_id"] = config["telegram_chat_id"] or file_cfg.get("telegram_chat_id", "")

    return config


def save_config(config: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print("[OK] Config saved.")


# ─── Setup Wizard ─────────────────────────────────────────────────
def setup_wizard() -> dict:
    print("=" * 55)
    print("  YC Status Monitor - First Time Setup")
    print("=" * 55)
    print()
    print("[1] Telegram Bot Token")
    print("    Open Telegram -> @BotFather -> /newbot -> copy token")
    print()
    telegram_token = input("    Paste Token: ").strip()
    print()
    print("[2] Telegram Chat ID")
    print("    Open Telegram -> @userinfobot -> /start -> copy ID")
    print()
    telegram_chat_id = input("    Paste Chat ID: ").strip()
    print()

    config = {
        "telegram_token": telegram_token,
        "telegram_chat_id": telegram_chat_id,
    }

    if not all(config.values()):
        print("[ERROR] All fields are required.")
        sys.exit(1)

    save_config(config)
    return config


# ─── Browser Login ────────────────────────────────────────────────
def browser_login():
    """Open browser for user to log into YC. Save session for later."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERROR] Playwright not installed. Run:")
        print("  pip install playwright && playwright install chromium")
        sys.exit(1)

    print("[LOGIN] Opening browser... Please log into Y Combinator.")
    print("        After you see 'My Applications' page, close the browser.")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            str(SESSION_DIR),
            headless=False,
            channel="chrome",
            viewport={"width": 1280, "height": 800},
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto(YC_HOME)

        # Wait for user to log in and reach the applications page
        try:
            page.wait_for_url("**/home**", timeout=300_000)  # 5 min
            # Check if logged in (look for the status badge or app name)
            page.wait_for_selector("text=My Applications", timeout=60_000)
            print("[OK] Login successful! Session saved.")
        except Exception:
            print("[OK] Browser closed. Session saved.")

        browser.close()


def has_valid_session() -> bool:
    """Check if we have a saved browser session."""
    return SESSION_DIR.exists() and any(SESSION_DIR.iterdir())


# ─── Fetch with Playwright ───────────────────────────────────────
def fetch_page_playwright(headless: bool = True) -> str:
    """Fetch YC page using saved Playwright session."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            str(SESSION_DIR),
            headless=headless,
            channel="chrome",
            viewport={"width": 1280, "height": 800},
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto(YC_HOME, wait_until="networkidle", timeout=30_000)

        # Check if we got redirected to login
        if "/session" in page.url or "/login" in page.url:
            browser.close()
            raise SessionExpiredError("YC session expired. Run: python yc_monitor.py --login")

        html = page.content()
        browser.close()
        return html


class SessionExpiredError(Exception):
    pass


# ─── Status Extraction ───────────────────────────────────────────
def extract_status(html: str) -> dict:
    """Extract status information from YC page."""
    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(separator=" ", strip=True)

    status_badge = ""

    # Method 1: Find the exact YC badge (blue pill span)
    for el in soup.find_all("span"):
        classes = " ".join(el.get("class", []))
        if "blue" in classes or "badge" in classes or "pill" in classes:
            text = el.get_text(strip=True)
            if text and len(text) < 50:
                status_badge = text
                break

    # Method 2: CSS selector patterns
    if not status_badge:
        for selector in [
            "[class*='badge']", "[class*='status']", "[class*='pill']",
            "[class*='tag']", "[class*='chip']",
        ]:
            el = soup.select_one(selector)
            if el and el.get_text(strip=True):
                text = el.get_text(strip=True)
                if len(text) < 50:
                    status_badge = text
                    break

    # Method 3: Known status phrases
    if not status_badge:
        known = [
            "In review", "Under review", "Submitted", "Interview",
            "Accepted", "Rejected", "Waitlisted", "Pending",
            "Invited to interview", "Congratulations", "Unfortunately",
        ]
        for s in known:
            if s.lower() in page_text.lower():
                status_badge = s
                break

    title = soup.title.string.strip() if soup.title and soup.title.string else "Unknown"

    return {
        "title": title,
        "status_badge": status_badge,
        "content_hash": hashlib.sha256(page_text.encode()).hexdigest()[:16],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── State ────────────────────────────────────────────────────────
def get_last_state() -> dict | None:
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return None


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ─── SF Time ──────────────────────────────────────────────────────
def get_sf_time_line() -> str:
    """One-line SF time footer for Telegram messages."""
    now_utc = datetime.now(timezone.utc)
    sf_time = now_utc + timedelta(hours=-7)  # PDT
    h = sf_time.hour
    day = sf_time.strftime("%A")
    time_str = sf_time.strftime("%I:%M %p")

    if day in ("Saturday", "Sunday"):
        office = "Weekend"
    elif 9 <= h < 18:
        office = "Office hours"
    else:
        office = "Outside office hours"

    return f"SF Time: {time_str} ({day}, {office})"


# ─── Telegram ─────────────────────────────────────────────────────
def send_telegram(token: str, chat_id: str, message: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    print("[SENT] Telegram notification sent!")


# ─── Check ────────────────────────────────────────────────────────
def check_once(config: dict) -> bool:
    """Single check. Returns True if status changed."""
    print(f"[CHECK] Checking YC status... ({datetime.now().strftime('%H:%M:%S')})")

    try:
        html = fetch_page_playwright(headless=True)
        current = extract_status(html)
    except SessionExpiredError as e:
        print(f"[ERROR] {e}")
        send_telegram(
            config["telegram_token"], config["telegram_chat_id"],
            "!! YC Monitor: Session expired. Please run:\npython yc_monitor.py --login"
        )
        return False
    except Exception as e:
        print(f"[WARN] Error fetching page: {e}")
        return False

    badge = current["status_badge"] or "unknown"
    print(f"[INFO] Status: {badge} | Hash: {current['content_hash']}")

    previous = get_last_state()

    if previous is None:
        save_state(current)
        msg = (
            f"YC Status Monitor Started\n\n"
            f"Current Status: {badge}\n\n"
            f"{get_sf_time_line()}"
        )
        send_telegram(config["telegram_token"], config["telegram_chat_id"], msg)
        print("[OK] First run - baseline saved.")
        return False

    if current["content_hash"] != previous["content_hash"]:
        save_state(current)
        old_badge = previous.get("status_badge", "unknown") or "unknown"
        new_badge = badge

        msg = f"YC STATUS CHANGED!\n\n{old_badge}  ->  {new_badge}\n\n"

        if new_badge.lower() in ("accepted", "congratulations", "invited to interview", "interview"):
            msg += "THIS COULD BE GREAT NEWS!\n\n"

        msg += (
            f"Check: {YC_HOME}\n\n"
            f"{get_sf_time_line()}"
        )
        send_telegram(config["telegram_token"], config["telegram_chat_id"], msg)
        print("[ALERT] STATUS CHANGED! Notification sent.")
        return True
    else:
        print(f"[OK] No change. Status: {badge}")
        return False


# ─── Main ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="YC Status Monitor")
    parser.add_argument("--setup", action="store_true", help="Run setup wizard")
    parser.add_argument("--login", action="store_true", help="Open browser to log into YC")
    parser.add_argument("--interval", type=int, default=0,
                        help="Check interval in seconds (0 = single check)")
    parser.add_argument("--once", action="store_true", help="Run single check and exit")
    args = parser.parse_args()

    # Setup
    config = load_config()
    if args.setup or not all(config.values()):
        config = setup_wizard()

    if not all(config.values()):
        print("[ERROR] Missing config. Run: python yc_monitor.py --setup")
        sys.exit(1)

    # Login
    if args.login or not has_valid_session():
        browser_login()
        if args.login:
            return

    # Check
    if args.once or args.interval == 0:
        check_once(config)
    else:
        print(f"[LOOP] Monitoring every {args.interval}s. Ctrl+C to stop.")
        try:
            while True:
                check_once(config)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
