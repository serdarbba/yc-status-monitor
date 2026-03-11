#!/bin/bash
echo ""
echo "================================================"
echo " YC Status Monitor - Quick Installer"
echo "================================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed."
    echo "Install: https://www.python.org/downloads/"
    exit 1
fi

echo "[1/3] Installing Python dependencies..."
pip3 install -r requirements.txt --quiet
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install dependencies."
    exit 1
fi
echo "[OK] Dependencies installed."

echo ""
echo "[2/3] Installing browser engine..."
playwright install chromium
echo "[OK] Browser ready."

echo ""
echo "[3/3] Launching setup wizard..."
echo ""
echo "------------------------------------------------"
echo " Your browser will open at http://localhost:5959"
echo " Follow the 3-step setup:"
echo "   1. Log into your YC account"
echo "   2. Enter Telegram Bot Token"
echo "   3. Enter Telegram Chat ID"
echo "------------------------------------------------"
echo ""
python3 web_ui.py
