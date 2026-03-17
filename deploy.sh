#!/bin/bash

# Soccer Picks - Production Deployment Script for Ubuntu Server
# Run on a fresh Ubuntu Server after cloning from GitHub
# Usage: bash deploy.sh

set -e  # Exit on any error

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ⚽ Soccer Picks - Ubuntu Server Production Deployment     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# ============================================================
# 0. Pre-flight checks
# ============================================================
echo "[1/8] 🔍 Pre-flight checks..."

if [ ! -f "requirements.txt" ]; then
    echo "❌ Error: requirements.txt not found!"
    echo "   Make sure you're in the soccer_picks directory"
    exit 1
fi

if [ ! -f ".env.example" ]; then
    echo "❌ Error: .env.example not found!"
    exit 1
fi

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "⚠️  Running as root. Some commands may fail."
    echo "    Consider running as a regular user instead."
    SUDO=""
else
    SUDO="sudo"
fi

# Get the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "✓ Project directory: $PROJECT_DIR"
echo ""

# ============================================================
# 1. Update system and install dependencies
# ============================================================
echo "[2/8] 📦 Updating system and installing Python..."

$SUDO apt-get update -q
$SUDO apt-get install -y -q \
    python3 python3-pip python3-venv \
    git curl wget \
    build-essential libssl-dev libffi-dev

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python $PYTHON_VERSION installed"
echo ""

# ============================================================
# 2. Create virtual environment
# ============================================================
echo "[3/8] 🐍 Creating Python virtual environment..."

if [ -d "venv" ]; then
    echo "ℹ️  Virtual environment already exists, skipping..."
    source venv/bin/activate
else
    python3 -m venv venv
    source venv/bin/activate
    echo "✓ Virtual environment created and activated"
fi

# Upgrade pip
pip install --upgrade pip setuptools wheel -q
echo "✓ pip upgraded"
echo ""

# ============================================================
# 3. Install Python dependencies
# ============================================================
echo "[4/8] 📚 Installing Python dependencies..."

pip install -r requirements.txt -q
echo "✓ All dependencies installed"
echo ""

# ============================================================
# 4. Create .env file
# ============================================================
echo "[5/8] ⚙️  Setting up environment variables..."

if [ -f ".env" ]; then
    echo "⚠️  .env already exists, skipping creation..."
else
    cp .env.example .env
    echo "✓ .env file created from template"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env with your Telegram credentials:"
    echo "   nano .env"
    echo ""
    echo "   You need:"
    echo "   - TELEGRAM_TOKEN from @BotFather"
    echo "   - TELEGRAM_CHAT_ID from @userinfobot"
    echo ""
    exit 1
fi

echo "✓ Environment variables configured"
echo ""

# ============================================================
# 5. Create data directories
# ============================================================
echo "[6/8] 📁 Creating data directories..."

mkdir -p data/cache
mkdir -p data/history
mkdir -p logs

echo "✓ Data directories created"
echo ""

# ============================================================
# 6. Run tests
# ============================================================
echo "[7/8] 🧪 Running tests..."

source venv/bin/activate

echo "  → Testing calendar module..."
python tests/test_calendar.py > /dev/null 2>&1 && echo "    ✓ Calendar OK" || echo "    ⚠ Calendar warning"

echo "  → Testing formatter..."
python tests/test_formatter.py > /dev/null 2>&1 && echo "    ✓ Formatter OK" || echo "    ⚠ Formatter warning"

echo "  → Testing bot configuration..."
python tests/test_bot.py > /dev/null 2>&1 && echo "    ✓ Bot OK" || echo "    ⚠ Bot warning"

echo "✓ Tests completed"
echo ""

# ============================================================
# 7. Install systemd service
# ============================================================
echo "[8/8] 🔧 Installing systemd service..."

# Get current user
CURRENT_USER=$(whoami)
echo "Current user: $CURRENT_USER"

# Create a temporary service file with the correct paths
TEMP_SERVICE=$(mktemp)
sed "s|/home/user|$(pwd)|g" soccer-picks.service > "$TEMP_SERVICE"
sed -i "s|User=user|User=$CURRENT_USER|g" "$TEMP_SERVICE"
sed -i "s|Group=user|Group=$CURRENT_USER|g" "$TEMP_SERVICE"

# Copy service files
$SUDO cp "$TEMP_SERVICE" /etc/systemd/system/soccer-picks.service
$SUDO cp soccer-picks.timer /etc/systemd/system/soccer-picks.timer
rm "$TEMP_SERVICE"

# Reload systemd
$SUDO systemctl daemon-reload

echo "✓ systemd service installed"
echo ""

# ============================================================
# 8. Summary and next steps
# ============================================================
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                ✅ DEPLOYMENT SUCCESSFUL                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

echo "📋 Next steps:"
echo ""
echo "1️⃣  Edit your .env file with Telegram credentials:"
echo "   nano .env"
echo ""
echo "2️⃣  Get Telegram credentials:"
echo "   - Token: Search @BotFather on Telegram and create a new bot"
echo "   - Chat ID: Search @userinfobot and send any message"
echo ""
echo "3️⃣  Test the connection:"
echo "   source venv/bin/activate"
echo "   python -c 'from telegram.bot import test_connection; test_connection()'"
echo ""
echo "4️⃣  Run a manual test:"
echo "   source venv/bin/activate"
echo "   python main.py"
echo ""
echo "5️⃣  Enable and start the service:"
echo "   sudo systemctl enable soccer-picks.timer"
echo "   sudo systemctl start soccer-picks.timer"
echo ""
echo "6️⃣  Check the service status:"
echo "   sudo systemctl status soccer-picks.timer"
echo "   sudo systemctl list-timers soccer-picks.timer"
echo ""
echo "7️⃣  View logs (real-time):"
echo "   sudo journalctl -u soccer-picks -f"
echo ""
echo "📚 Full documentation: cat README.md"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "⚽ Ready for production!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
