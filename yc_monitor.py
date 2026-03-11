#!/usr/bin/env python3
"""
YC Status Monitor - Y Combinator Application Status Tracker
Checks your YC application status and notifies you via Telegram when it changes.
"""

import os
import sys
import json
import time
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timezone

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("❌ Missing dependencies. Run: pip install -r requirements.txt")
    sys.exit(1)


# ─── Config ───────────────────────────────────────────────────────
CONFIG_FILE = Path(__file__).parent / "config.json"
STATE_FILE = Path(__file__).parent / ".last_state"


def load_config() -> dict:
    """Load config from file or environment variables."""
    config = {}

    # 1) Try environment variables first (for GitHub Actions / CI)
    config["yc_url"] = os.environ.get("YC_APPLICATION_URL", "")
    config["telegram_token"] = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    config["telegram_chat_id"] = os.environ.get("TELEGRAM_CHAT_ID", "")

    # 2) Fall back to config.json
    if not all(config.values()) and CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            file_cfg = json.load(f)
        config["yc_url"] = config["yc_url"] or file_cfg.get("yc_url", "")
        config["telegram_token"] = config["telegram_token"] or file_cfg.get("telegram_token", "")
        config["telegram_chat_id"] = config["telegram_chat_id"] or file_cfg.get("telegram_chat_id", "")

    return config


def save_config(config: dict):
    """Save config to file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print(f"✅ Config saved to {CONFIG_FILE}")


# ─── Setup Wizard ─────────────────────────────────────────────────
def setup_wizard() -> dict:
    """Interactive setup — asks user for credentials on first run."""
    print("=" * 55)
    print("  🚀 YC Status Monitor - First Time Setup")
    print("=" * 55)
    print()

    # YC URL
    print("1️⃣  Y Combinator Application URL")
    print("   Go to https://apply.ycombinator.com and copy your")
    print("   application page URL from the browser address bar.")
    print()
    yc_url = input("   Paste URL: ").strip()

    print()

    # Telegram Bot Token
    print("2️⃣  Telegram Bot Token")
    print("   Open Telegram → search @BotFather → /newbot")
    print("   Copy the token it gives you.")
    print()
    telegram_token = input("   Paste Token: ").strip()

    print()

    # Telegram Chat ID
    print("3️⃣  Telegram Chat ID")
    print("   Open Telegram → search @userinfobot → /start")
    print("   It will show your Chat ID (a number).")
    print()
    telegram_chat_id = input("   Paste Chat ID: ").strip()

    print()

    config = {
        "yc_url": yc_url,
        "telegram_token": telegram_token,
        "telegram_chat_id": telegram_chat_id,
    }

    # Validate
    if not all(config.values()):
        print("❌ All fields are required. Please try again.")
        sys.exit(1)

    save_config(config)
    print()
    return config


# ─── Core Logic ───────────────────────────────────────────────────
def fetch_page(url: str) -> str:
    """Fetch YC application page content."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


def extract_status(html: str) -> dict:
    """Extract status information from YC page."""
    soup = BeautifulSoup(html, "html.parser")

    # Get page text for hashing
    page_text = soup.get_text(separator=" ", strip=True)

    # Try to find status-related elements
    status_keywords = [
        "submitted", "under review", "interview", "accepted",
        "rejected", "waitlisted", "pending", "invited",
        "congratulations", "unfortunately",
    ]

    found_statuses = []
    for kw in status_keywords:
        if kw.lower() in page_text.lower():
            found_statuses.append(kw)

    # Title
    title = soup.title.string if soup.title else "Unknown"

    return {
        "title": title.strip(),
        "statuses": found_statuses,
        "content_hash": hashlib.sha256(page_text.encode()).hexdigest()[:16],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_last_state() -> dict | None:
    """Load previous state."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return None


def save_state(state: dict):
    """Save current state."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def send_telegram(token: str, chat_id: str, message: str):
    """Send Telegram notification."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    print(f"📨 Telegram notification sent!")


# ─── Main ─────────────────────────────────────────────────────────
def check_once(config: dict) -> bool:
    """Single check. Returns True if status changed."""
    print(f"🔍 Checking YC status... ({datetime.now().strftime('%H:%M:%S')})")

    try:
        html = fetch_page(config["yc_url"])
        current = extract_status(html)
    except Exception as e:
        print(f"⚠️  Error fetching page: {e}")
        return False

    previous = get_last_state()

    if previous is None:
        # First run
        save_state(current)
        msg = (
            "🟢 <b>YC Status Monitor Started</b>\n\n"
            f"📄 Page: {current['title']}\n"
            f"📊 Status keywords: {', '.join(current['statuses']) or 'none detected'}\n"
            f"🔑 Content hash: {current['content_hash']}\n"
            f"⏰ {current['timestamp']}"
        )
        send_telegram(config["telegram_token"], config["telegram_chat_id"], msg)
        print("✅ First run — baseline saved. Monitoring started.")
        return False

    if current["content_hash"] != previous["content_hash"]:
        # STATUS CHANGED!
        save_state(current)

        new_kw = set(current["statuses"]) - set(previous.get("statuses", []))
        removed_kw = set(previous.get("statuses", [])) - set(current["statuses"])

        msg = (
            "🚨 <b>YC APPLICATION STATUS CHANGED!</b> 🚨\n\n"
            f"📄 Page: {current['title']}\n"
        )
        if new_kw:
            msg += f"🆕 New keywords: {', '.join(new_kw)}\n"
        if removed_kw:
            msg += f"❌ Removed keywords: {', '.join(removed_kw)}\n"
        msg += (
            f"\n📊 Current: {', '.join(current['statuses']) or 'none'}\n"
            f"🔑 Hash: {previous['content_hash']} → {current['content_hash']}\n"
            f"⏰ {current['timestamp']}\n\n"
            f"👉 Check now: {config['yc_url']}"
        )
        send_telegram(config["telegram_token"], config["telegram_chat_id"], msg)
        print("🚨 STATUS CHANGED! Notification sent.")
        return True
    else:
        print(f"✅ No change. Hash: {current['content_hash']}")
        return False


def main():
    parser = argparse.ArgumentParser(description="YC Status Monitor")
    parser.add_argument("--setup", action="store_true", help="Run setup wizard")
    parser.add_argument("--interval", type=int, default=0,
                        help="Check interval in seconds (0 = single check)")
    parser.add_argument("--once", action="store_true", help="Run single check and exit")
    args = parser.parse_args()

    # Load or setup config
    config = load_config()

    if args.setup or not all(config.values()):
        config = setup_wizard()

    if not all(config.values()):
        print("❌ Missing config. Run: python yc_monitor.py --setup")
        sys.exit(1)

    if args.once or args.interval == 0:
        check_once(config)
    else:
        print(f"🔄 Monitoring every {args.interval} seconds. Press Ctrl+C to stop.")
        print()
        try:
            while True:
                check_once(config)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n👋 Monitor stopped.")


if __name__ == "__main__":
    main()
