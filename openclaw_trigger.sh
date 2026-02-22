#!/bin/bash
# ============================================
# AQI Beast — OpenClaw Daily Trigger
# ============================================
# This script is called by OpenClaw on AWS at 9:00 AM IST (3:30 AM UTC)
# 
# Setup in OpenClaw:
#   1. SSH into your AWS instance
#   2. Place this script at: ~/AQI-TRADING-SYSTEM/openclaw_trigger.sh
#   3. Make executable: chmod +x openclaw_trigger.sh
#   4. Add to OpenClaw's tool config or cron:
#      crontab -e
#      30 3 * * 1-5 /home/ubuntu/AQI-TRADING-SYSTEM/openclaw_trigger.sh >> /home/ubuntu/AQI-TRADING-SYSTEM/memory/cron.log 2>&1
# ============================================

set -e

# Change to project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtualenv
source .venv/bin/activate

# Load environment variables
export $(grep -v '^#' .env | xargs)

echo "========================================="
echo "  AQI Beast — Starting Daily Run"
echo "  $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "========================================="

# Check if market day (skip weekends)
DAY=$(date +%u)
if [ "$DAY" -gt 5 ]; then
    echo "Weekend — skipping."
    exit 0
fi

# Run the daily pipeline in paper mode
# Change to --mode live when ready for real trading
python -m tradingagents.daily_runner --mode paper

echo ""
echo "========================================="
echo "  Daily run complete: $(date '+%H:%M:%S')"
echo "========================================="
