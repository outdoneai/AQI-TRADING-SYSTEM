#!/bin/bash
# ============================================
# AQI Beast — AWS Setup Script
# ============================================
# Run this on a fresh Ubuntu AWS instance:
#   chmod +x setup_aws.sh && ./setup_aws.sh
# ============================================

set -e

echo "========================================="
echo "  AQI Beast — AWS Setup"
echo "========================================="

# 1. System dependencies
echo "[1/5] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv git

# 2. Clone repo (if not already cloned)
if [ ! -d "TRADING-AGENTS" ]; then
    echo "[2/5] Cloning repository..."
    git clone https://github.com/TauricResearch/TradingAgents.git TRADING-AGENTS
else
    echo "[2/5] Repo already exists, pulling latest..."
    cd TRADING-AGENTS && git pull && cd ..
fi

cd TRADING-AGENTS

# 3. Create virtual environment
echo "[3/5] Setting up Python environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e . -q

# 4. Setup environment
echo "[4/5] Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  Created .env from template — EDIT THIS FILE with your API keys!"
    echo "  nano .env"
else
    echo "  .env already exists"
fi

# 5. Create runtime directories
echo "[5/5] Creating runtime directories..."
mkdir -p memory/agent_memories
mkdir -p memory/risk_state
mkdir -p memory/quant_logs
mkdir -p memory/execution_logs
mkdir -p memory/paper_trading
mkdir -p memory/orchestrator_logs

echo ""
echo "========================================="
echo "  Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Edit .env with your API keys:   nano .env"
echo "  2. Activate virtualenv:            source .venv/bin/activate"
echo "  3. Run paper trading test:"
echo ""
echo '     python3 -c "'
echo '     from tradingagents.orchestrator import AQIOrchestrator'
echo '     bot = AQIOrchestrator(mode=\"paper\")'
echo '     result = bot.run(\"RELIANCE.NS\")'
echo '     print(result)'
echo '     "'
echo ""
echo "  4. For OpenClaw integration, add a daily cron:"
echo "     crontab -e"
echo "     30 3 * * 1-5 cd ~/TRADING-AGENTS && .venv/bin/python3 -m tradingagents.orchestrator"
echo ""
echo "========================================="
