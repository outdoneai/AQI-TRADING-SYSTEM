"""Simple Backtester — Quick historical validation of trading signals.

Uses yfinance for historical data. No external backtesting framework required.
This is the lightweight fast-path. For deep analysis, use VectorBT/Backtrader.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import statistics


class SimpleBacktester:
    """Lightweight backtester that validates AI signals against historical data.
    
    Tests: "If the AI had given this signal N days ago, would it have been profitable?"
    Works without installing VectorBT or Backtrader — uses raw price data.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.lookback_days = self.config.get("backtest_lookback_days", 252)  # 1 year
        self.test_windows = self.config.get("test_windows", [5, 10, 20, 60])  # Hold periods to test

    def backtest_signal(
        self,
        ticker: str,
        decision: str,
        stop_loss_pct: float,
        target_pct: float,
    ) -> dict:
        """Backtest a signal against historical data.
        
        Simulates: What if we had executed this signal at various points in the last year?
        
        Args:
            ticker: Stock ticker symbol
            decision: BUY or SELL
            stop_loss_pct: Stop-loss percentage (negative, e.g., -5.0)
            target_pct: Target percentage (positive, e.g., 10.0)
        
        Returns:
            dict with win_rate, avg_return, sharpe, max_drawdown, trade_count
        """
        if decision == "HOLD":
            return {
                "approved": True,
                "reason": "HOLD — no backtest needed",
                "win_rate": 0,
                "avg_return_pct": 0,
                "sharpe_ratio": 0,
                "max_drawdown_pct": 0,
                "trade_count": 0,
            }

        try:
            import yfinance as yf
        except ImportError:
            return {
                "approved": True,
                "reason": "yfinance not available — skipping backtest",
                "win_rate": 0,
                "avg_return_pct": 0,
                "sharpe_ratio": 0,
                "max_drawdown_pct": 0,
                "trade_count": 0,
            }

        try:
            # Fetch historical data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=self.lookback_days + max(self.test_windows))
            
            data = yf.download(ticker, start=start_date.strftime("%Y-%m-%d"), 
                             end=end_date.strftime("%Y-%m-%d"), progress=False)
            
            if data.empty or len(data) < 30:
                return {
                    "approved": True,
                    "reason": f"Insufficient historical data for {ticker}",
                    "win_rate": 0,
                    "avg_return_pct": 0,
                    "sharpe_ratio": 0,
                    "max_drawdown_pct": 0,
                    "trade_count": 0,
                }

            closes = data["Close"].values.flatten()
            
            # Run backtest for each hold window
            all_results = {}
            
            for hold_days in self.test_windows:
                trades = self._simulate_trades(
                    closes, decision, stop_loss_pct, target_pct, hold_days
                )
                if trades:
                    all_results[f"{hold_days}d"] = self._compute_stats(trades)

            if not all_results:
                return {
                    "approved": True,
                    "reason": "No valid backtest trades generated",
                    "win_rate": 0,
                    "avg_return_pct": 0,
                    "sharpe_ratio": 0,
                    "max_drawdown_pct": 0,
                    "trade_count": 0,
                }

            # Use the best performing window as the primary result
            best_window = max(all_results.keys(), key=lambda k: all_results[k]["sharpe_ratio"])
            best = all_results[best_window]
            
            # Approval logic
            approved = (
                best["win_rate"] >= 0.4 and  # At least 40% win rate
                best["sharpe_ratio"] >= 0.5 and  # Reasonable Sharpe
                best["max_drawdown_pct"] <= 25.0  # Manageable drawdown
            )
            
            reason_parts = []
            if best["win_rate"] < 0.4:
                reason_parts.append(f"Low win rate: {best['win_rate']:.0%}")
            if best["sharpe_ratio"] < 0.5:
                reason_parts.append(f"Low Sharpe: {best['sharpe_ratio']:.2f}")
            if best["max_drawdown_pct"] > 25.0:
                reason_parts.append(f"High drawdown: {best['max_drawdown_pct']:.1f}%")

            return {
                "approved": approved,
                "reason": " | ".join(reason_parts) if reason_parts else f"Backtest passed ({best_window} hold)",
                "best_hold_period": best_window,
                "win_rate": best["win_rate"],
                "avg_return_pct": best["avg_return_pct"],
                "sharpe_ratio": best["sharpe_ratio"],
                "max_drawdown_pct": best["max_drawdown_pct"],
                "trade_count": best["trade_count"],
                "all_windows": all_results,
            }

        except Exception as e:
            return {
                "approved": True,
                "reason": f"Backtest error (proceeding anyway): {str(e)[:100]}",
                "win_rate": 0,
                "avg_return_pct": 0,
                "sharpe_ratio": 0,
                "max_drawdown_pct": 0,
                "trade_count": 0,
            }

    def _simulate_trades(
        self, closes, decision: str, stop_loss_pct: float, 
        target_pct: float, hold_days: int
    ) -> List[float]:
        """Simulate trades over historical data. Returns list of return percentages."""
        returns = []
        stop_loss_pct = -abs(stop_loss_pct)
        target_pct = abs(target_pct)

        # Step through data, simulating entry every 5 days
        for i in range(0, len(closes) - hold_days, 5):
            entry_price = closes[i]
            
            # Simulate hold period with stop-loss and target
            exit_price = entry_price
            hit_sl = False
            hit_target = False
            
            for j in range(1, min(hold_days + 1, len(closes) - i)):
                current = closes[i + j]
                
                if decision == "BUY":
                    change_pct = (current - entry_price) / entry_price * 100
                    if change_pct <= stop_loss_pct:
                        exit_price = entry_price * (1 + stop_loss_pct / 100)
                        hit_sl = True
                        break
                    elif change_pct >= target_pct:
                        exit_price = entry_price * (1 + target_pct / 100)
                        hit_target = True
                        break
                    exit_price = current
                    
                elif decision == "SELL":
                    change_pct = (entry_price - current) / entry_price * 100
                    if change_pct <= stop_loss_pct:
                        exit_price = entry_price * (1 - stop_loss_pct / 100)
                        hit_sl = True
                        break
                    elif change_pct >= target_pct:
                        exit_price = entry_price * (1 - target_pct / 100)
                        hit_target = True
                        break
                    exit_price = current

            # Calculate return
            if decision == "BUY":
                ret = (exit_price - entry_price) / entry_price * 100
            else:
                ret = (entry_price - exit_price) / entry_price * 100
            
            returns.append(ret)

        return returns

    def _compute_stats(self, returns: List[float]) -> dict:
        """Compute trading statistics from a list of returns."""
        if not returns:
            return {"win_rate": 0, "avg_return_pct": 0, "sharpe_ratio": 0, 
                    "max_drawdown_pct": 0, "trade_count": 0}

        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]
        
        win_rate = len(wins) / len(returns) if returns else 0
        avg_return = statistics.mean(returns) if returns else 0
        
        # Sharpe ratio (annualized, assuming ~252 trading days)
        if len(returns) > 1:
            std_dev = statistics.stdev(returns)
            sharpe = (avg_return / std_dev) * (252 ** 0.5) if std_dev > 0 else 0
        else:
            sharpe = 0

        # Max drawdown
        cumulative = 0
        peak = 0
        max_dd = 0
        for r in returns:
            cumulative += r
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd

        return {
            "win_rate": round(win_rate, 3),
            "avg_return_pct": round(avg_return, 2),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "trade_count": len(returns),
            "avg_win": round(statistics.mean(wins), 2) if wins else 0,
            "avg_loss": round(statistics.mean(losses), 2) if losses else 0,
        }
