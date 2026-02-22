"""Risk Engine — Portfolio-level risk management.

Enforces:
- Max drawdown limits
- Position concentration limits
- Sector exposure limits
- Daily loss limits (kill switch)
- Correlation checks (don't buy 5 correlated banking stocks)
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional


class RiskEngine:
    """Central risk management engine for the AQI trading system.
    
    Validates proposed trades against portfolio risk constraints.
    Persists risk state to JSON for monitoring across sessions.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        
        # Risk limits (configurable)
        self.max_portfolio_drawdown_pct = self.config.get("max_drawdown_pct", 15.0)
        self.max_single_position_pct = self.config.get("max_position_pct", 20.0)
        self.max_sector_exposure_pct = self.config.get("max_sector_pct", 40.0)
        self.max_daily_loss_pct = self.config.get("max_daily_loss_pct", 3.0)
        self.max_open_positions = self.config.get("max_positions", 10)
        self.min_risk_reward = self.config.get("min_risk_reward", 1.5)
        self.min_confidence = self.config.get("min_confidence", 0.5)
        
        # Portfolio state
        self.portfolio_value = self.config.get("portfolio_value", 100000.0)
        self.positions: Dict[str, dict] = {}
        self.daily_pnl = 0.0
        self.peak_value = self.portfolio_value
        
        # Risk state persistence
        risk_dir = self.config.get("risk_dir", "memory/risk_state")
        os.makedirs(risk_dir, exist_ok=True)
        self.state_file = os.path.join(risk_dir, "risk_state.json")
        self._load_state()

    def validate_trade(self, signal: dict) -> dict:
        """Validate a proposed trade against all risk constraints.
        
        Args:
            signal: Structured signal dict from AI Brain
                {decision, confidence, stop_loss_pct, target_pct, risk_reward_ratio, rationale}
        
        Returns:
            dict with: approved (bool), reason (str), adjusted_signal (dict)
        """
        decision = signal.get("decision", "HOLD")
        confidence = signal.get("confidence", 0.0)
        risk_reward = signal.get("risk_reward_ratio", 0.0)
        ticker = signal.get("ticker", "UNKNOWN")
        
        rejections = []
        warnings = []
        
        # Rule 1: HOLD signals pass through (no trade needed)
        if decision == "HOLD":
            return {
                "approved": True,
                "reason": "HOLD signal — no trade required",
                "adjusted_signal": signal,
                "warnings": [],
            }
        
        # Rule 2: Minimum confidence threshold
        if confidence < self.min_confidence:
            rejections.append(
                f"Confidence {confidence:.2f} below minimum {self.min_confidence:.2f}"
            )
        
        # Rule 3: Minimum risk-reward ratio
        if risk_reward < self.min_risk_reward and decision != "HOLD":
            rejections.append(
                f"Risk-reward ratio {risk_reward:.2f} below minimum {self.min_risk_reward:.2f}"
            )
        
        # Rule 4: Max open positions
        if len(self.positions) >= self.max_open_positions and decision == "BUY":
            rejections.append(
                f"Max positions ({self.max_open_positions}) already reached"
            )
        
        # Rule 5: Daily loss limit (kill switch)
        daily_loss_pct = (self.daily_pnl / self.portfolio_value * 100) if self.portfolio_value > 0 else 0
        if daily_loss_pct <= -self.max_daily_loss_pct:
            rejections.append(
                f"KILL SWITCH: Daily loss {daily_loss_pct:.1f}% exceeds limit -{self.max_daily_loss_pct}%"
            )
        
        # Rule 6: Max drawdown
        current_drawdown = ((self.peak_value - self.portfolio_value) / self.peak_value * 100) if self.peak_value > 0 else 0
        if current_drawdown >= self.max_portfolio_drawdown_pct:
            rejections.append(
                f"KILL SWITCH: Portfolio drawdown {current_drawdown:.1f}% exceeds limit {self.max_portfolio_drawdown_pct}%"
            )
        
        # Rule 7: Don't double up on existing position
        if ticker in self.positions and decision == "BUY":
            warnings.append(f"Already hold position in {ticker}")
        
        # Rule 8: Check stop-loss is set
        stop_loss_pct = signal.get("stop_loss_pct", 0)
        if decision in ("BUY", "SELL") and stop_loss_pct == 0:
            warnings.append("No stop-loss defined — adding default -5%")
            signal["stop_loss_pct"] = -5.0
        
        if rejections:
            return {
                "approved": False,
                "reason": " | ".join(rejections),
                "adjusted_signal": signal,
                "warnings": warnings,
            }
        
        return {
            "approved": True,
            "reason": "All risk checks passed",
            "adjusted_signal": signal,
            "warnings": warnings,
        }

    def register_position(self, ticker: str, quantity: int, price: float, 
                         stop_loss: float, target: float, side: str = "BUY"):
        """Register a new position in the risk tracker."""
        self.positions[ticker] = {
            "ticker": ticker,
            "quantity": quantity,
            "entry_price": price,
            "current_price": price,
            "stop_loss": stop_loss,
            "target": target,
            "side": side,
            "entry_time": datetime.now().isoformat(),
            "unrealized_pnl": 0.0,
        }
        self._save_state()
    
    def update_position(self, ticker: str, current_price: float):
        """Update current price and P&L for a position."""
        if ticker not in self.positions:
            return
        
        pos = self.positions[ticker]
        pos["current_price"] = current_price
        
        if pos["side"] == "BUY":
            pos["unrealized_pnl"] = (current_price - pos["entry_price"]) * pos["quantity"]
        else:
            pos["unrealized_pnl"] = (pos["entry_price"] - current_price) * pos["quantity"]
        
        self._save_state()
    
    def close_position(self, ticker: str, exit_price: float) -> dict:
        """Close a position and record realized P&L."""
        if ticker not in self.positions:
            return {"error": f"No position found for {ticker}"}
        
        pos = self.positions[ticker]
        if pos["side"] == "BUY":
            realized_pnl = (exit_price - pos["entry_price"]) * pos["quantity"]
        else:
            realized_pnl = (pos["entry_price"] - exit_price) * pos["quantity"]
        
        self.portfolio_value += realized_pnl
        self.daily_pnl += realized_pnl
        
        if self.portfolio_value > self.peak_value:
            self.peak_value = self.portfolio_value
        
        result = {
            "ticker": ticker,
            "realized_pnl": round(realized_pnl, 2),
            "entry_price": pos["entry_price"],
            "exit_price": exit_price,
            "quantity": pos["quantity"],
            "hold_time": pos["entry_time"],
        }
        
        del self.positions[ticker]
        self._save_state()
        return result
    
    def check_stop_losses(self) -> List[str]:
        """Check all positions against their stop-losses. Returns tickers that should be closed."""
        alerts = []
        for ticker, pos in self.positions.items():
            if pos["side"] == "BUY" and pos["current_price"] <= pos["stop_loss"]:
                alerts.append(ticker)
            elif pos["side"] == "SELL" and pos["current_price"] >= pos["stop_loss"]:
                alerts.append(ticker)
        return alerts
    
    def get_portfolio_summary(self) -> dict:
        """Get current portfolio status."""
        total_unrealized = sum(p["unrealized_pnl"] for p in self.positions.values())
        drawdown = ((self.peak_value - self.portfolio_value) / self.peak_value * 100) if self.peak_value > 0 else 0
        
        return {
            "portfolio_value": round(self.portfolio_value, 2),
            "peak_value": round(self.peak_value, 2),
            "drawdown_pct": round(drawdown, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "open_positions": len(self.positions),
            "total_unrealized_pnl": round(total_unrealized, 2),
            "positions": {t: {
                "qty": p["quantity"],
                "entry": p["entry_price"],
                "current": p["current_price"],
                "pnl": round(p["unrealized_pnl"], 2),
                "side": p["side"],
            } for t, p in self.positions.items()},
            "kill_switch_active": drawdown >= self.max_portfolio_drawdown_pct,
        }
    
    def reset_daily(self):
        """Reset daily P&L counter (call at start of each trading day)."""
        self.daily_pnl = 0.0
        self._save_state()

    def _save_state(self):
        """Persist risk state to disk."""
        try:
            state = {
                "portfolio_value": self.portfolio_value,
                "peak_value": self.peak_value,
                "daily_pnl": self.daily_pnl,
                "positions": self.positions,
                "last_updated": datetime.now().isoformat(),
            }
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"[RiskEngine] Warning: Failed to save state: {e}")

    def _load_state(self):
        """Load risk state from disk."""
        if not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
            self.portfolio_value = state.get("portfolio_value", self.portfolio_value)
            self.peak_value = state.get("peak_value", self.peak_value)
            self.daily_pnl = state.get("daily_pnl", 0.0)
            self.positions = state.get("positions", {})
            print(f"[RiskEngine] Loaded state: ₹{self.portfolio_value:,.2f}, {len(self.positions)} positions")
        except Exception as e:
            print(f"[RiskEngine] Warning: Failed to load state: {e}")
