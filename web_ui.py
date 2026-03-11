#!/usr/bin/env python3
"""
YC Status Monitor - Web UI
Simple local web interface for setup, monitoring, and settings.
"""

import json
import subprocess
import sys
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
import webbrowser

from yc_monitor import load_config, save_config, check_once, CONFIG_FILE, has_valid_session, browser_login

PORT = 5959
BOT_STATE_FILE = Path(__file__).parent / ".bot_state"

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>YC Status Monitor</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0a0a0a;
    color: #e5e5e5;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .container {
    max-width: 480px;
    width: 100%;
    padding: 20px;
  }
  .card {
    background: #171717;
    border: 1px solid #262626;
    border-radius: 16px;
    padding: 32px;
  }
  .logo {
    text-align: center;
    margin-bottom: 24px;
  }
  .logo h1 {
    font-size: 24px;
    font-weight: 700;
    color: #fb923c;
  }
  .logo p {
    color: #737373;
    font-size: 14px;
    margin-top: 4px;
  }
  .field {
    margin-bottom: 20px;
  }
  .field label {
    display: block;
    font-size: 13px;
    font-weight: 600;
    color: #a3a3a3;
    margin-bottom: 6px;
  }
  .field .hint {
    font-size: 12px;
    color: #525252;
    margin-bottom: 6px;
  }
  .field input, .field select {
    width: 100%;
    padding: 10px 14px;
    background: #0a0a0a;
    border: 1px solid #333;
    border-radius: 8px;
    color: #e5e5e5;
    font-size: 14px;
    outline: none;
    transition: border-color 0.2s;
  }
  .field input:focus, .field select:focus {
    border-color: #fb923c;
  }
  .field input::placeholder {
    color: #404040;
  }
  .btn {
    width: 100%;
    padding: 12px;
    background: #fb923c;
    color: #0a0a0a;
    border: none;
    border-radius: 10px;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
    transition: background 0.2s;
    margin-top: 8px;
  }
  .btn:hover { background: #f97316; }
  .btn:disabled { background: #404040; cursor: not-allowed; }
  .btn-secondary {
    background: transparent;
    border: 1px solid #333;
    color: #a3a3a3;
    margin-top: 10px;
  }
  .btn-secondary:hover { border-color: #fb923c; color: #fb923c; }
  .btn-green {
    background: #22c55e;
    color: #000;
  }
  .btn-green:hover { background: #16a34a; }
  .status-box {
    background: #0a0a0a;
    border: 1px solid #262626;
    border-radius: 10px;
    padding: 16px;
    margin-top: 20px;
    font-size: 13px;
    line-height: 1.8;
    display: none;
  }
  .status-box.visible { display: block; }
  .status-box .label { color: #737373; }
  .status-box .value { color: #fb923c; font-weight: 600; }
  .dot {
    display: inline-block; width: 8px; height: 8px;
    border-radius: 50%; margin-right: 6px; vertical-align: middle;
  }
  .dot.green { background: #22c55e; }
  .dot.red { background: #ef4444; }
  .dot.yellow { background: #eab308; }
  .toast {
    position: fixed;
    bottom: 30px;
    left: 50%;
    transform: translateX(-50%);
    background: #22c55e;
    color: #000;
    padding: 10px 24px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    display: none;
  }
  .steps {
    display: flex;
    justify-content: center;
    gap: 8px;
    margin-bottom: 20px;
  }
  .step {
    width: 32px; height: 4px;
    background: #333;
    border-radius: 2px;
    transition: background 0.3s;
  }
  .step.active { background: #fb923c; }
  .divider {
    border-top: 1px solid #262626;
    margin: 16px 0;
  }
  .settings-section {
    margin-top: 16px;
  }
  .settings-section h3 {
    font-size: 14px;
    color: #a3a3a3;
    margin-bottom: 12px;
  }
  .radio-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;
  }
  .radio-option {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    background: #0a0a0a;
    border: 1px solid #333;
    border-radius: 8px;
    cursor: pointer;
    transition: border-color 0.2s;
  }
  .radio-option:hover { border-color: #525252; }
  .radio-option.selected { border-color: #fb923c; }
  .radio-option input[type="radio"] { accent-color: #fb923c; }
  .radio-option label {
    font-size: 13px;
    color: #e5e5e5;
    cursor: pointer;
  }
  .sf-time {
    background: #0f1a2e;
    border: 1px solid #1e3a5f;
    border-radius: 10px;
    padding: 12px 16px;
    margin-top: 16px;
    font-size: 13px;
    text-align: center;
  }
  .sf-time .sf-label { color: #60a5fa; font-weight: 600; font-size: 12px; }
  .sf-time .sf-clock { color: #93c5fd; font-size: 18px; font-weight: 700; margin: 4px 0; }
  .sf-time .sf-office { color: #64748b; font-size: 12px; }
  .bot-status {
    background: #0a1a0a;
    border: 1px solid #1a3a1a;
    border-radius: 10px;
    padding: 12px 16px;
    margin-top: 12px;
    font-size: 13px;
    text-align: center;
  }
  .bot-status .bot-label { color: #4ade80; font-weight: 600; }
</style>
</head>
<body>

<div class="container">
  <div class="card">
    <div class="logo">
      <h1>YC Status Monitor</h1>
      <p>Get notified when your YC status changes</p>
    </div>

    <div class="steps">
      <div class="step active" id="s1"></div>
      <div class="step" id="s2"></div>
      <div class="step" id="s3"></div>
    </div>

    <form id="setupForm">
      <!-- Step 1: YC Login -->
      <div class="step-content" id="step1">
        <div class="field">
          <label>Step 1: Log into Y Combinator</label>
          <div class="hint">A browser will open. Log into your YC account, then come back here.</div>
        </div>
        <button type="button" class="btn" onclick="doLogin()">Open YC Login</button>
        <p id="loginStatus" style="text-align:center;margin-top:10px;color:#737373;font-size:13px;"></p>
      </div>

      <!-- Step 2 -->
      <div class="step-content" id="step2" style="display:none">
        <div class="field">
          <label>Telegram Bot Token</label>
          <div class="hint">Open Telegram -> @BotFather -> /newbot -> copy token</div>
          <input type="text" name="telegram_token" id="telegram_token" placeholder="123456:ABC-DEF..." required>
        </div>
        <button type="button" class="btn" onclick="nextStep(3)">Continue</button>
        <button type="button" class="btn btn-secondary" onclick="nextStep(1)">Back</button>
      </div>

      <!-- Step 3 -->
      <div class="step-content" id="step3" style="display:none">
        <div class="field">
          <label>Telegram Chat ID</label>
          <div class="hint">Open Telegram -> @userinfobot -> /start -> copy ID</div>
          <input type="text" name="telegram_chat_id" id="telegram_chat_id" placeholder="123456789" required>
        </div>
        <button type="submit" class="btn">Start Monitoring</button>
        <button type="button" class="btn btn-secondary" onclick="nextStep(2)">Back</button>
      </div>
    </form>

    <div class="status-box" id="statusBox">
      <div><span class="label">Status: </span><span id="statusDot" class="dot green"></span><span id="statusText" class="value">Monitoring</span></div>
      <div><span class="label">Last Check: </span><span id="lastCheck" class="value">-</span></div>
      <div><span class="label">Content Hash: </span><span id="contentHash" class="value">-</span></div>
      <div><span class="label">Badge: </span><span id="keywords" class="value">-</span></div>
      <button type="button" class="btn" onclick="checkNow()" id="checkBtn">Check Now</button>

      <div class="divider"></div>

      <!-- Settings Section -->
      <div class="settings-section">
        <h3>Notification Settings</h3>
        <div class="radio-group" id="notifyOptions">
          <div class="radio-option selected" onclick="selectOption(this, 'change_only')">
            <input type="radio" name="notify" value="change_only" checked>
            <label>Only when status changes</label>
          </div>
          <div class="radio-option" onclick="selectOption(this, 'interval_15')">
            <input type="radio" name="notify" value="interval_15">
            <label>Every 15 minutes + on change</label>
          </div>
          <div class="radio-option" onclick="selectOption(this, 'interval_60')">
            <input type="radio" name="notify" value="interval_60">
            <label>Every 1 hour + on change</label>
          </div>
          <div class="radio-option" onclick="selectOption(this, 'interval_180')">
            <input type="radio" name="notify" value="interval_180">
            <label>Every 3 hours + on change</label>
          </div>
        </div>
        <button type="button" class="btn btn-secondary" onclick="saveSettings()" id="saveSettingsBtn">Save Settings</button>
      </div>

      <!-- SF Time -->
      <div class="sf-time" id="sfTimeBox">
        <div class="sf-label">SAN FRANCISCO (YC HQ)</div>
        <div class="sf-clock" id="sfClock">--:-- --</div>
        <div class="sf-office" id="sfOffice">Loading...</div>
      </div>

      <!-- Bot Status -->
      <div class="bot-status" id="botStatus">
        <span class="bot-label">Telegram Bot: </span>
        <span id="botStatusText">Not running</span>
        <br>
        <button type="button" class="btn btn-green" onclick="startBot()" id="startBotBtn" style="margin-top:8px;">Start Telegram Bot</button>
      </div>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
  let currentStep = 1;

  function nextStep(n) {
    document.querySelectorAll('.step-content').forEach(el => el.style.display = 'none');
    document.querySelectorAll('.step').forEach(el => el.classList.remove('active'));
    document.getElementById('step' + n).style.display = 'block';
    for (let i = 1; i <= n; i++) document.getElementById('s' + i).classList.add('active');
    currentStep = n;
  }

  function showToast(msg, color) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.style.background = color || '#22c55e';
    t.style.display = 'block';
    setTimeout(() => t.style.display = 'none', 3000);
  }

  function selectOption(el, value) {
    document.querySelectorAll('.radio-option').forEach(o => o.classList.remove('selected'));
    el.classList.add('selected');
    el.querySelector('input').checked = true;
  }

  function doLogin() {
    var btn = event.target;
    btn.disabled = true;
    btn.textContent = 'Opening browser...';
    document.getElementById('loginStatus').textContent = 'Browser is opening. Log into YC, then close the browser.';
    fetch('/api/login', { method: 'POST' })
      .then(r => r.json())
      .then(res => {
        btn.disabled = false;
        btn.textContent = 'Open YC Login';
        if (res.ok) {
          document.getElementById('loginStatus').textContent = 'Login successful!';
          document.getElementById('loginStatus').style.color = '#22c55e';
          nextStep(2);
        } else {
          document.getElementById('loginStatus').textContent = 'Error: ' + (res.error || 'unknown');
          document.getElementById('loginStatus').style.color = '#ef4444';
        }
      });
  }

  // Load existing config
  fetch('/api/config').then(r => r.json()).then(cfg => {
    if (cfg.has_config && cfg.has_session) {
      document.getElementById('telegram_token').value = cfg.telegram_token || '';
      document.getElementById('telegram_chat_id').value = cfg.telegram_chat_id || '';
      showMonitoring();
      if (cfg.last_state) {
        var s = cfg.last_state;
        document.getElementById('lastCheck').textContent = s.timestamp ? new Date(s.timestamp).toLocaleTimeString() : '-';
        document.getElementById('contentHash').textContent = s.content_hash || '-';
        document.getElementById('keywords').textContent = s.status_badge || 'none';
        document.getElementById('statusDot').className = 'dot green';
        document.getElementById('statusText').textContent = s.status_badge || 'Monitoring';
      }
      // Load settings
      if (cfg.bot_state) {
        var bs = cfg.bot_state;
        var val = bs.notify_mode === 'change_only' ? 'change_only' : 'interval_' + bs.interval_minutes;
        var radio = document.querySelector('input[value="' + val + '"]');
        if (radio) {
          document.querySelectorAll('.radio-option').forEach(o => o.classList.remove('selected'));
          radio.checked = true;
          radio.closest('.radio-option').classList.add('selected');
        }
      }
      // Bot status
      if (cfg.bot_running) {
        document.getElementById('botStatusText').textContent = 'Running';
        document.getElementById('botStatusText').style.color = '#4ade80';
        document.getElementById('startBotBtn').textContent = 'Bot is running';
        document.getElementById('startBotBtn').disabled = true;
      }
    } else if (cfg.has_session) {
      nextStep(2);
    }
  });

  document.getElementById('setupForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const data = {
      telegram_token: document.getElementById('telegram_token').value,
      telegram_chat_id: document.getElementById('telegram_chat_id').value,
    };
    fetch('/api/save', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data)
    }).then(r => r.json()).then(res => {
      if (res.ok) {
        showToast('Config saved!');
        showMonitoring();
        checkNow();
      } else {
        showToast('Error: ' + res.error, '#ef4444');
      }
    });
  });

  function showMonitoring() {
    document.getElementById('setupForm').style.display = 'none';
    document.querySelector('.steps').style.display = 'none';
    document.getElementById('statusBox').classList.add('visible');
  }

  function checkNow() {
    const btn = document.getElementById('checkBtn');
    btn.disabled = true;
    btn.textContent = 'Checking...';
    fetch('/api/check', { method: 'POST' })
      .then(r => r.json())
      .then(res => {
        btn.disabled = false;
        btn.textContent = 'Check Now';
        if (res.ok) {
          document.getElementById('lastCheck').textContent = new Date().toLocaleTimeString();
          document.getElementById('contentHash').textContent = res.hash || '-';
          document.getElementById('keywords').textContent = res.badge || res.statuses || 'none';
          if (res.changed) {
            document.getElementById('statusDot').className = 'dot yellow';
            document.getElementById('statusText').textContent = res.badge ? res.badge + ' (CHANGED!)' : 'CHANGED!';
            showToast('Status changed!', '#eab308');
          } else {
            document.getElementById('statusDot').className = 'dot green';
            document.getElementById('statusText').textContent = res.badge || 'No change';
          }
        } else {
          document.getElementById('statusDot').className = 'dot red';
          document.getElementById('statusText').textContent = 'Error';
          showToast('Error: ' + res.error, '#ef4444');
        }
      });
  }

  function saveSettings() {
    const selected = document.querySelector('input[name="notify"]:checked').value;
    let data = {};
    if (selected === 'change_only') {
      data = { notify_mode: 'change_only', auto_check_enabled: false };
    } else {
      const mins = parseInt(selected.split('_')[1]);
      data = { notify_mode: 'interval', interval_minutes: mins, auto_check_enabled: true };
    }
    fetch('/api/settings', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data)
    }).then(r => r.json()).then(res => {
      if (res.ok) showToast('Settings saved!');
      else showToast('Error saving settings', '#ef4444');
    });
  }

  function startBot() {
    const btn = document.getElementById('startBotBtn');
    btn.disabled = true;
    btn.textContent = 'Starting...';
    fetch('/api/start_bot', { method: 'POST' })
      .then(r => r.json())
      .then(res => {
        if (res.ok) {
          document.getElementById('botStatusText').textContent = 'Running';
          document.getElementById('botStatusText').style.color = '#4ade80';
          btn.textContent = 'Bot is running';
          showToast('Telegram bot started!');
        } else {
          btn.disabled = false;
          btn.textContent = 'Start Telegram Bot';
          showToast('Error: ' + (res.error || 'unknown'), '#ef4444');
        }
      });
  }

  // SF Time clock
  function updateSFTime() {
    const now = new Date();
    // SF is UTC-7 (PDT)
    const sfOffset = -7 * 60;
    const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
    const sf = new Date(utc + (sfOffset * 60000));

    const h = sf.getHours();
    const m = sf.getMinutes();
    const ampm = h >= 12 ? 'PM' : 'AM';
    const h12 = h % 12 || 12;
    const mStr = m < 10 ? '0' + m : m;
    document.getElementById('sfClock').textContent = h12 + ':' + mStr + ' ' + ampm;

    const day = sf.getDay();
    if (day === 0 || day === 6) {
      document.getElementById('sfOffice').textContent = 'Weekend - Office closed';
    } else if (h >= 9 && h < 18) {
      document.getElementById('sfOffice').textContent = 'Office hours (9 AM - 6 PM PT)';
      document.getElementById('sfOffice').style.color = '#4ade80';
    } else {
      document.getElementById('sfOffice').textContent = 'Outside office hours';
      document.getElementById('sfOffice').style.color = '#64748b';
    }
  }
  updateSFTime();
  setInterval(updateSFTime, 30000);
</script>

</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    bot_process = None

    def log_message(self, format, *args):
        pass  # Suppress logs

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _html(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def do_GET(self):
        if self.path == "/api/config":
            cfg = load_config()
            has_config = bool(cfg.get("telegram_token") and cfg.get("telegram_chat_id"))
            # Mask tokens for security
            if cfg.get("telegram_token"):
                t = cfg["telegram_token"]
                cfg["telegram_token"] = t[:8] + "..." + t[-4:] if len(t) > 12 else t
            cfg["has_config"] = has_config
            cfg["has_session"] = has_valid_session()
            # Include last state
            state_file = Path(__file__).parent / ".last_state"
            if state_file.exists():
                with open(state_file) as f:
                    cfg["last_state"] = json.load(f)
            # Include bot settings
            if BOT_STATE_FILE.exists():
                with open(BOT_STATE_FILE) as f:
                    cfg["bot_state"] = json.load(f)
            # Bot running status
            cfg["bot_running"] = Handler.bot_process is not None and Handler.bot_process.poll() is None
            self._json(cfg)
        else:
            self._html(HTML_PAGE)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        if self.path == "/api/login":
            try:
                browser_login()
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)

        elif self.path == "/api/save":
            try:
                data = json.loads(body)
                save_config(data)
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 400)

        elif self.path == "/api/check":
            try:
                cfg = load_config()
                changed = check_once(cfg)
                state_file = Path(__file__).parent / ".last_state"
                state = {}
                if state_file.exists():
                    with open(state_file) as f:
                        state = json.load(f)
                self._json({
                    "ok": True,
                    "changed": changed,
                    "hash": state.get("content_hash", ""),
                    "badge": state.get("status_badge", ""),
                    "statuses": ", ".join(state.get("statuses", [])),
                })
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)

        elif self.path == "/api/settings":
            try:
                data = json.loads(body)
                with open(BOT_STATE_FILE, "w") as f:
                    json.dump(data, f, indent=2)
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 400)

        elif self.path == "/api/start_bot":
            try:
                if Handler.bot_process is not None and Handler.bot_process.poll() is None:
                    self._json({"ok": True, "message": "Already running"})
                    return
                Handler.bot_process = subprocess.Popen(
                    [sys.executable, str(Path(__file__).parent / "telegram_bot.py")],
                    cwd=str(Path(__file__).parent),
                )
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)

        else:
            self._json({"error": "not found"}, 404)


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"YC Status Monitor UI -> http://localhost:{PORT}")
    webbrowser.open(f"http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        if Handler.bot_process and Handler.bot_process.poll() is None:
            Handler.bot_process.terminate()
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
