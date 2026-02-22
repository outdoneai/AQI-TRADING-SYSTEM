"""AQI Beast — Daily Runner for OpenClaw / Cron triggers.

This is the script that runs every trading day at 9:00 AM IST.
Can be triggered by: OpenClaw, cron, systemd timer, or manually.

Usage:
    python -m tradingagents.daily_runner
    
    # Or with custom watchlist:
    python -m tradingagents.daily_runner --tickers RELIANCE.NS INFY.NS TCS.NS
"""

import os
import sys
import json
import argparse
from datetime import datetime, date
from pathlib import Path

# Load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# Default NSE watchlist — top liquid stocks
DEFAULT_WATCHLIST = [
    "RELIANCE.NS",
    "TCS.NS",
    "HDFCBANK.NS",
    "INFY.NS",
    "ICICIBANK.NS",
    "HINDUNILVR.NS",
    "SBIN.NS",
    "BHARTIARTL.NS",
    "KOTAKBANK.NS",
    "LT.NS",
]

# Default config
DEFAULT_CONFIG = {
    "llm_provider": os.environ.get("LLM_PROVIDER", "google"),
    "deep_think_llm": os.environ.get("DEEP_THINK_LLM", "gemini-2.0-flash"),
    "quick_think_llm": os.environ.get("QUICK_THINK_LLM", "gemini-2.0-flash"),
    "portfolio_value": float(os.environ.get("PORTFOLIO_VALUE", "100000")),
    "max_drawdown_pct": float(os.environ.get("MAX_DRAWDOWN_PCT", "15")),
    "max_position_pct": float(os.environ.get("MAX_POSITION_PCT", "20")),
    "max_daily_loss_pct": float(os.environ.get("MAX_DAILY_LOSS_PCT", "3")),
    "min_confidence": float(os.environ.get("MIN_CONFIDENCE", "0.5")),
    "min_risk_reward": float(os.environ.get("MIN_RISK_REWARD", "1.5")),
    "project_dir": str(Path(__file__).parent.parent),
}


def run_daily(tickers=None, mode="paper", skip_backtest=False):
    """Run the daily AQI Beast pipeline."""
    from tradingagents.orchestrator import AQIOrchestrator

    tickers = tickers or DEFAULT_WATCHLIST
    
    print(f"\n{'#'*60}")
    print(f"#  AQI BEAST — Daily Run")
    print(f"#  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
    print(f"#  Mode: {mode.upper()}")
    print(f"#  Watchlist: {len(tickers)} stocks")
    print(f"{'#'*60}\n")

    bot = AQIOrchestrator(mode=mode, config=DEFAULT_CONFIG)
    
    # Reset daily P&L counter
    bot.quant_brain.reset_daily()
    
    # Run on full watchlist
    results = bot.run_watchlist(
        tickers=tickers,
        skip_backtest=skip_backtest,
    )

    # Save daily summary
    summary_dir = Path("memory/daily_summaries")
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_file = summary_dir / f"summary_{date.today()}.json"
    
    summary = {
        "date": str(date.today()),
        "mode": mode,
        "tickers_analyzed": len(tickers),
        "results": [
            {
                "ticker": r.get("ticker"),
                "decision": r.get("stages", {}).get("ai_brain", {}).get("decision", "ERROR"),
                "confidence": r.get("stages", {}).get("ai_brain", {}).get("confidence", 0),
                "status": r.get("final_status", "UNKNOWN"),
            }
            for r in results
        ],
        "portfolio": bot.get_status(),
        "timestamp": datetime.now().isoformat(),
    }
    
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    
    print(f"\nDaily summary saved to: {summary_file}")
    
    # Print final portfolio status
    status = bot.get_status()
    print(f"\nPortfolio Status:")
    print(f"  Value: {status['risk_engine'].get('portfolio_value', 'N/A')}")
    print(f"  Open Positions: {status['risk_engine'].get('open_positions', 0)}")
    print(f"  Kill Switch: {'ACTIVE' if status['risk_engine'].get('kill_switch_active') else 'OFF'}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="AQI Beast — Daily Trading Runner")
    parser.add_argument("--tickers", nargs="+", default=None,
                       help="Stock tickers to analyze (default: top 10 NSE)")
    parser.add_argument("--mode", choices=["paper", "live", "signal_only"], default="paper",
                       help="Trading mode (default: paper)")
    parser.add_argument("--skip-backtest", action="store_true",
                       help="Skip historical backtest for faster execution")
    args = parser.parse_args()
    
    run_daily(
        tickers=args.tickers,
        mode=args.mode,
        skip_backtest=args.skip_backtest,
    )


if __name__ == "__main__":
    main()
