# YC Status Monitor

Track your Y Combinator application status 24/7. Get instant Telegram notifications when anything changes.

**Detects status changes like:** `In review` -> `Interview` -> `Accepted`

## Quick Start

### Windows
```
git clone https://github.com/serdarbba/yc-status-monitor.git
cd yc-status-monitor
install.bat
```

### Mac / Linux
```bash
git clone https://github.com/serdarbba/yc-status-monitor.git
cd yc-status-monitor
chmod +x install.sh
./install.sh
```

That's it! The installer handles everything and opens a web UI at `http://localhost:5959` where you:

1. **Log into YC** - A browser opens, you log in, close it
2. **Enter Telegram Bot Token** - Get from [@BotFather](https://t.me/BotFather)
3. **Enter Telegram Chat ID** - Get from [@userinfobot](https://t.me/userinfobot)

## Manual Install

```bash
pip install -r requirements.txt
playwright install chromium
python web_ui.py
```

## CLI Usage

```bash
# Single check
python yc_monitor.py --once

# Monitor every 15 minutes
python yc_monitor.py --interval 900

# Re-login if session expires
python yc_monitor.py --login

# First-time setup via terminal
python yc_monitor.py --setup
```

## How It Works

1. Uses Playwright with a real Chrome browser session to authenticate with YC
2. Fetches your application page (`apply.ycombinator.com/home`)
3. Extracts the status badge text (e.g. "In review", "Interview", "Accepted")
4. Hashes page content to detect any change
5. Sends Telegram notification when status changes

## Telegram Setup (2 minutes)

### Get Bot Token
1. Open Telegram
2. Search for `@BotFather`
3. Send `/newbot`
4. Follow prompts, copy the token

### Get Chat ID
1. Open Telegram
2. Search for `@userinfobot`
3. Send `/start`
4. Copy the number it gives you

### Important
After setup, send `/start` to your new bot in Telegram! Otherwise it can't message you.

## Requirements

- Python 3.8+
- Google Chrome installed
- Telegram account

## License

MIT
