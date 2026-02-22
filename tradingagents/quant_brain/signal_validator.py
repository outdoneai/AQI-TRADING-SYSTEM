"""Signal Validator — The gatekeeper between AI Brain and Body.

Chains: AI Signal → Backtest → Risk Check → Position Size → Final Order
If any step rejects, the trade doesn't execute.
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional

from tradingagents.quant_brain.risk_engine import RiskEngine
from tradingagents.quant_brain.backtester import SimpleBacktester
from tradingagents.quant_brain.position_sizer import PositionSizer


class SignalValidator:
    """End-to-end signal validation pipeline.
    
    Takes a structured signal from the AI Brain and produces
    a fully validated, sized order ready for execution.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.risk_engine = RiskEngine(config)
        self.backtester = SimpleBacktester(config)
        self.position_sizer = PositionSizer(config)
        
        # Logging
        log_dir = self.config.get("log_dir", "memory/quant_logs")
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = os.path.join(log_dir, "signal_validation_log.jsonl")

    def validate_and_size(
        self,
        signal: dict,
        current_price: float,
        ticker: str,
        skip_backtest: bool = False,
    ) -> dict:
        """Full validation pipeline: Backtest → Risk → Size → Order.
        
        Args:
            signal: Structured signal from AI Brain
                {decision, confidence, stop_loss_pct, target_pct, risk_reward_ratio, rationale}
            current_price: Current market price of the stock
            ticker: Stock ticker symbol
            skip_backtest: Skip backtesting (for speed during paper trading)
        
        Returns:
            dict with: approved, order (if approved), rejection_reason, validation_details
        """
        signal["ticker"] = ticker
        result = {
            "ticker": ticker,
            "decision": signal.get("decision", "HOLD"),
            "current_price": current_price,
            "timestamp": datetime.now().isoformat(),
            "steps": {},
        }

        # Step 1: Quick rejection for HOLD
        if signal.get("decision") == "HOLD":
            result["approved"] = True
            result["order"] = None
            result["reason"] = "HOLD signal — no order generated"
            self._log(result)
            return result

        # Step 2: Backtest validation
        if not skip_backtest:
            backtest_result = self.backtester.backtest_signal(
                ticker=ticker,
                decision=signal["decision"],
                stop_loss_pct=signal.get("stop_loss_pct", -5.0),
                target_pct=signal.get("target_pct", 5.0),
            )
            result["steps"]["backtest"] = backtest_result
            
            if not backtest_result.get("approved", True):
                result["approved"] = False
                result["order"] = None
                result["reason"] = f"BACKTEST REJECTED: {backtest_result.get('reason', 'Unknown')}"
                self._log(result)
                return result
        else:
            result["steps"]["backtest"] = {"skipped": True}

        # Step 3: Risk validation
        risk_result = self.risk_engine.validate_trade(signal)
        result["steps"]["risk"] = risk_result
        
        if not risk_result["approved"]:
            result["approved"] = False
            result["order"] = None
            result["reason"] = f"RISK REJECTED: {risk_result['reason']}"
            self._log(result)
            return result

        # Step 4: Position sizing
        position = self.position_sizer.calculate_position(
            current_price=current_price,
            stop_loss_pct=signal.get("stop_loss_pct", -5.0),
            target_pct=signal.get("target_pct", 5.0),
            confidence=signal.get("confidence", 0.5),
            portfolio_value=self.risk_engine.portfolio_value,
        )
        result["steps"]["position_sizing"] = position

        if position["quantity"] <= 0:
            result["approved"] = False
            result["order"] = None
            result["reason"] = f"SIZING REJECTED: {position.get('method', 'Zero quantity')}"
            self._log(result)
            return result

        # Step 5: Generate order
        order = {
            "ticker": ticker,
            "side": signal["decision"],
            "quantity": position["quantity"],
            "order_type": "LIMIT",
            "price": current_price,
            "stop_loss": position["stop_loss_price"],
            "target": position["target_price"],
            "investment_amount": position["investment_amount"],
            "risk_amount": position["risk_amount"],
            "confidence": signal.get("confidence", 0.5),
            "rationale": signal.get("rationale", "N/A"),
        }

        result["approved"] = True
        result["order"] = order
        result["reason"] = "ALL CHECKS PASSED"
        result["warnings"] = risk_result.get("warnings", [])

        self._log(result)
        return result

    def get_portfolio_summary(self) -> dict:
        """Get current portfolio status from risk engine."""
        return self.risk_engine.get_portfolio_summary()

    def reset_daily(self):
        """Reset daily counters."""
        self.risk_engine.reset_daily()

    def _log(self, result: dict):
        """Append validation result to log file."""
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, default=str) + "\n")
        except Exception:
            pass
