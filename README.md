# 🚀 YC Status Monitor

Track your Y Combinator application status 24/7. Get instant Telegram notifications when anything changes.

## Quick Start (Local)

```bash
git clone https://github.com/serdarbba/yc-status-monitor.git
cd yc-status-monitor
pip install -r requirements.txt
python yc_monitor.py
```

First run will ask you for:
1. **YC Application URL** — from https://apply.ycombinator.com
2. **Telegram Bot Token** — create via [@BotFather](https://t.me/BotFather)
3. **Telegram Chat ID** — get from [@userinfobot](https://t.me/userinfobot)

### Run Continuously
```bash
python yc_monitor.py --interval 900   # Check every 15 minutes
```

## ☁️ GitHub Actions (24/7 — Free)

No need to keep your computer on. GitHub runs it for you.

1. **Fork this repo**
2. Go to **Settings → Secrets → Actions**
3. Add 3 secrets:

| Name | Value |
|------|-------|
| `YC_APPLICATION_URL` | Your YC application page URL |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your chat ID from @userinfobot |

4. Go to **Actions** tab → Enable workflows
5. Done! ✅ Checks every 15 minutes automatically.

## How It Works

- Fetches your YC application page
- Hashes the content to detect any change
- Looks for status keywords (submitted, interview, accepted, etc.)
- Sends Telegram alert when something changes

## License

MIT
