# AQI Beast — Production Setup Guide

## Step 1: Reddit API Keys (FREE)

1. Go to https://www.reddit.com/prefs/apps
2. Click **"Create Another App"** at the bottom
3. Fill in:
   - **Name:** `AQI-Beast`
   - **Type:** Select `script`
   - **Redirect URI:** `http://localhost:8080`
4. Click **Create App**
5. Copy:
   - **Client ID** = string under the app name (e.g., `3KlR7mN_xQzP...`)
   - **Client Secret** = the `secret` field
6. Add to your `.env`:
   ```
   REDDIT_CLIENT_ID=your_client_id_here
   REDDIT_CLIENT_SECRET=your_client_secret_here
   ```

## Step 2: Finnhub API Key (FREE)

1. Go to https://finnhub.io/register
2. Sign up with name, email, password
3. After login, your API key is on the dashboard
4. Add to `.env`:
   ```
   FINNHUB_API_KEY=your_key_here
   ```
5. Free tier: 60 API calls/minute (plenty for daily runs)

## Step 3: OpenAlgo + Shoonya (Rs.0 Brokerage)

### 3a: Open Shoonya Account
1. Go to https://shoonya.finvasia.com
2. Open a FREE demat + trading account
3. Complete KYC (Aadhaar + PAN)
4. Wait for account activation (1-2 days)

### 3b: Install OpenAlgo
```bash
# On your AWS instance
git clone https://github.com/marketcalls/openalgo.git
cd openalgo
pip install -r requirements.txt
python app.py  # Starts on port 5000
```

### 3c: Connect Shoonya to OpenAlgo
1. Open http://your-aws-ip:5000 in browser
2. Go to Broker Settings
3. Select **Shoonya/Finvasia**
4. Enter your Shoonya credentials
5. Copy the OpenAlgo API key

### 3d: Add to `.env`:
```
OPENALGO_API_KEY=your_openalgo_api_key
OPENALGO_HOST=http://127.0.0.1:5000
```

## Step 4: AWS Deployment

```bash
# SSH into your AWS instance
ssh ubuntu@your-aws-ip

# Clone the repo
git clone https://github.com/outdoneai/AQI-TRADING-SYSTEM.git
cd AQI-TRADING-SYSTEM

# Run one-command setup
chmod +x setup_aws.sh
./setup_aws.sh

# Edit .env with all your API keys
nano .env

# Test paper trading
source .venv/bin/activate
python -m tradingagents.daily_runner --mode paper --tickers RELIANCE.NS
```

## Step 5: OpenClaw Daily Trigger

### Option A: Cron Job (simple)
```bash
crontab -e
# Add this line (runs at 9:00 AM IST = 3:30 AM UTC, Mon-Fri):
30 3 * * 1-5 /home/ubuntu/AQI-TRADING-SYSTEM/openclaw_trigger.sh >> /home/ubuntu/AQI-TRADING-SYSTEM/memory/cron.log 2>&1
```

### Option B: OpenClaw Integration
Add this tool to your OpenClaw config:
```json
{
  "name": "run_aqi_beast",
  "description": "Run the AQI Beast trading system on the daily watchlist",
  "command": "/home/ubuntu/AQI-TRADING-SYSTEM/openclaw_trigger.sh"
}
```

Then tell OpenClaw: "Run AQI Beast every trading day at 9 AM IST"

## Step 6: Go Live (when ready)

After paper trading for 1-2 weeks and verifying results:

```bash
# Change mode from paper to live
python -m tradingagents.daily_runner --mode live
```

Or update `openclaw_trigger.sh`:
```bash
python -m tradingagents.daily_runner --mode live
```
