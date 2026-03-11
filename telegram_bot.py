#!/usr/bin/env python3
"""
YC Status Monitor - Telegram Bot
Interactive bot with commands: /check, /status, /time, /help
Settings are configured via the web UI (localhost:5959).
"""

import json
import time
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

from yc_monitor import (
    load_config, check_once, get_last_state,
    has_valid_session, YC_HOME,
)

BASE_DIR = Path(__file__).parent
BOT_STATE_FILE = BASE_DIR / ".bot_state"

# San Francisco timezone (UTC-7 PDT / UTC-8 PST)
SF_OFFSET = timedelta(hours=-7)  # PDT (March-November)


def get_sf_time() -> str:
    """Get current San Francisco time with office hours info."""
    now_utc = datetime.now(timezone.utc)
    sf_time = now_utc + SF_OFFSET
    hour = sf_time.hour
    day = sf_time.strftime("%A")

    time_str = sf_time.strftime("%I:%M %p")
    date_str = sf_time.strftime("%b %d, %Y")

    if day in ("Saturday", "Sunday"):
        office = "Weekend - Office closed"
    elif 9 <= hour < 18:
        office = "Office hours (9 AM - 6 PM)"
    elif hour < 9:
        mins_to_open = (9 - hour) * 60 - sf_time.minute
        office = f"Before office hours (opens in {mins_to_open} min)"
    else:
        office = "After office hours"

    return f"{time_str} ({date_str})\n{day} - {office}"


def load_bot_state() -> dict:
    """Load bot notification settings."""
    defaults = {
        "notify_mode": "change_only",  # change_only | interval
        "interval_minutes": 60,
        "auto_check_enabled": False,
    }
    if BOT_STATE_FILE.exists():
        with open(BOT_STATE_FILE, "r") as f:
            saved = json.load(f)
        defaults.update(saved)
    return defaults


def save_bot_state(state: dict):
    with open(BOT_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def send_message(token: str, chat_id: str, text: str):
    """Send a Telegram message."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Failed to send message: {e}")


def handle_check(config: dict):
    """Handle /check command - run immediate status check."""
    token = config["telegram_token"]
    chat_id = config["telegram_chat_id"]

    try:
        changed = check_once(config)
        # check_once already sends Telegram on first run or on change
        # Only send extra message if no change and not first run
        state = get_last_state()
        if not changed and state:
            badge = state.get("status_badge", "unknown") or "unknown"
            send_message(token, chat_id,
                f"No changes detected.\n\n"
                f"Current Status: <b>{badge}</b>\n\n"
                f"{get_sf_time()}"
            )
    except Exception as e:
        send_message(token, chat_id, f"Error checking status: {e}")


def handle_status(config: dict):
    """Handle /status command - show current state."""
    token = config["telegram_token"]
    chat_id = config["telegram_chat_id"]
    state = get_last_state()
    bot_state = load_bot_state()

    if state:
        badge = state.get("status_badge", "unknown") or "unknown"
    else:
        badge = "No data yet"

    mode = bot_state["notify_mode"]
    if mode == "change_only":
        mode_text = "Only on status change"
    else:
        interval = bot_state["interval_minutes"]
        if interval < 60:
            mode_text = f"Every {interval} minutes"
        else:
            mode_text = f"Every {interval // 60} hour(s)"

    session_ok = "Active" if has_valid_session() else "Expired"

    msg = (
        f"<b>YC Status Monitor</b>\n\n"
        f"Status: <b>{badge}</b>\n\n"
        f"Session: {session_ok}\n"
        f"Notifications: {mode_text}\n\n"
        f"{get_sf_time()}"
    )
    send_message(token, chat_id, msg)


def handle_time(config: dict):
    """Handle /time command - show SF time."""
    token = config["telegram_token"]
    chat_id = config["telegram_chat_id"]

    msg = (
        f"<b>San Francisco (YC HQ)</b>\n\n"
        f"{get_sf_time()}\n\n"
        f"YC typically responds during business hours:\n"
        f"Mon-Fri, 9 AM - 6 PM PT"
    )
    send_message(token, chat_id, msg)


def handle_help(config: dict):
    """Handle /help command."""
    token = config["telegram_token"]
    chat_id = config["telegram_chat_id"]

    msg = (
        "<b>YC Status Monitor - Commands</b>\n\n"
        "/check - Check YC status right now\n"
        "/status - Show current status & settings\n"
        "/time - SF time & YC office hours\n"
        "/help - Show this help\n\n"
        "Change notification settings from the web UI:\n"
        "http://localhost:5959"
    )
    send_message(token, chat_id, msg)


def poll_updates(config: dict):
    """Long-poll Telegram for new messages/commands."""
    token = config["telegram_token"]
    chat_id = config["telegram_chat_id"]
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    offset = 0

    print("[BOT] Telegram bot started. Listening for commands...")

    while True:
        try:
            resp = requests.get(url, params={
                "offset": offset,
                "timeout": 30,
            }, timeout=35)
            data = resp.json()

            if not data.get("ok"):
                time.sleep(5)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1

                if "message" not in update:
                    continue

                msg = update["message"]
                text = msg.get("text", "").strip()
                sender_id = str(msg.get("chat", {}).get("id", ""))

                # Only respond to the configured chat
                if sender_id != chat_id:
                    continue

                if text == "/check":
                    handle_check(config)
                elif text == "/status":
                    handle_status(config)
                elif text == "/time":
                    handle_time(config)
                elif text in ("/help", "/start"):
                    handle_help(config)

        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            print(f"[ERROR] Bot polling error: {e}")
            time.sleep(5)


def auto_check_loop(config: dict):
    """Background loop that checks based on configured interval."""
    while True:
        bot_state = load_bot_state()

        if bot_state.get("auto_check_enabled") and bot_state.get("notify_mode") == "interval":
            interval = bot_state.get("interval_minutes", 60)
            time.sleep(interval * 60)

            # Re-check if still enabled
            bot_state = load_bot_state()
            if bot_state.get("auto_check_enabled") and bot_state.get("notify_mode") == "interval":
                print(f"[AUTO] Scheduled check (every {interval} min)")
                try:
                    changed = check_once(config)
                    if not changed:
                        state = get_last_state()
                        badge = state.get("status_badge", "unknown") if state else "unknown"
                        send_message(
                            config["telegram_token"],
                            config["telegram_chat_id"],
                            f"Scheduled Check - No changes\n\n"
                            f"Status: <b>{badge}</b>\n\n"
                            f"{get_sf_time()}"
                        )
                except Exception as e:
                    print(f"[ERROR] Auto-check failed: {e}")
        else:
            time.sleep(30)


def main():
    config = load_config()
    if not config.get("telegram_token") or not config.get("telegram_chat_id"):
        print("[ERROR] Config not found. Run: python yc_monitor.py --setup")
        return

    # Set bot commands
    try:
        url = f"https://api.telegram.org/bot{config['telegram_token']}/setMyCommands"
        commands = [
            {"command": "check", "description": "Check YC status now"},
            {"command": "status", "description": "Current status & settings"},
            {"command": "time", "description": "SF time & YC office hours"},
            {"command": "help", "description": "Show all commands"},
        ]
        requests.post(url, json={"commands": commands}, timeout=10)
        print("[OK] Bot commands registered.")
    except Exception:
        pass

    # Start auto-check thread
    auto_thread = threading.Thread(target=auto_check_loop, args=(config,), daemon=True)
    auto_thread.start()

    # Start polling (blocks)
    poll_updates(config)


if __name__ == "__main__":
    main()
