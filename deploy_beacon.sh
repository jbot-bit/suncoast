#!/bin/bash

# Vouch Beacon - Quick Deploy Script
# Run this to deploy the complete Vouch Beacon system

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║         VOUCH BEACON - DEPLOYMENT SCRIPT                ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    echo "Creating from template..."
    cp .env.beacon.example .env
    echo "✅ Created .env file"
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env and fill in your values:"
    echo "   - BOT_TOKEN"
    echo "   - BOT_USERNAME"
    echo "   - WEBHOOK_URL"
    echo "   - ADMIN_ID"
    echo "   - DATABASE_URL"
    echo "   - JWT_SECRET"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo "✅ Found .env file"
echo ""

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -q -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Run tests
echo "🧪 Running system tests..."
python test_beacon.py
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Tests failed! Please fix issues before deploying."
    exit 1
fi
echo ""

# Start the system
echo "🚀 Starting Vouch Beacon..."
echo ""
echo "The system will start on http://0.0.0.0:5000"
echo "Press Ctrl+C to stop"
echo ""
echo "Next steps after startup:"
echo "1. Set webhook: curl -X POST 'https://api.telegram.org/bot<TOKEN>/setWebhook?url=<URL>/webhook'"
echo "2. Add bot to group as admin"
echo "3. Test the flows:"
echo "   - Welcome Mat: New user joins"
echo "   - Guardian: Send banned word"
echo "   - Vouch: Send 'vouch @username'"
echo ""
echo "───────────────────────────────────────────────────────────"
echo ""

python main_beacon.py
