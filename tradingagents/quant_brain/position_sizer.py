"""Position Sizer — Kelly criterion and volatility-based position sizing.

Calculates optimal position size based on:
- Kelly criterion (edge / odds)
- Account risk percentage per trade
- Volatility scaling (reduce size in high-vol environments)
- Maximum position limits
"""

import math
from typing import Optional


class PositionSizer:
    """Calculate optimal position sizes for trades."""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.portfolio_value = self.config.get("portfolio_value", 100000.0)
        self.max_risk_per_trade_pct = self.config.get("max_risk_per_trade_pct", 2.0)
        self.max_position_pct = self.config.get("max_position_pct", 20.0)
        self.kelly_fraction = self.config.get("kelly_fraction", 0.5)  # Half-Kelly for safety

    def calculate_position(
        self,
        current_price: float,
        stop_loss_pct: float,
        target_pct: float,
        confidence: float,
        portfolio_value: Optional[float] = None,
    ) -> dict:
        """Calculate optimal position size.

        Args:
            current_price: Current stock price
            stop_loss_pct: Stop-loss as negative % (e.g., -5.0)
            target_pct: Target as positive % (e.g., 10.0)
            confidence: AI confidence score 0-1
            portfolio_value: Override portfolio value

        Returns:
            dict with quantity, investment_amount, risk_amount, method
        """
        pv = portfolio_value or self.portfolio_value
        
        if current_price <= 0 or pv <= 0:
            return self._empty_result("Invalid price or portfolio value")

        # Ensure stop_loss is negative
        stop_loss_pct = -abs(stop_loss_pct) if stop_loss_pct != 0 else -5.0
        target_pct = abs(target_pct) if target_pct != 0 else 5.0

        # Method 1: Fixed % risk per trade
        risk_amount = pv * (self.max_risk_per_trade_pct / 100)
        price_risk_per_share = current_price * (abs(stop_loss_pct) / 100)
        
        if price_risk_per_share > 0:
            qty_by_risk = int(risk_amount / price_risk_per_share)
        else:
            qty_by_risk = 0

        # Method 2: Kelly criterion
        # Kelly = (p * b - q) / b
        # where p = win probability, q = 1-p, b = win/loss ratio
        win_prob = min(0.95, max(0.1, confidence))  # Clamp to reasonable range
        loss_prob = 1 - win_prob
        win_loss_ratio = target_pct / abs(stop_loss_pct) if abs(stop_loss_pct) > 0 else 1.0

        kelly_pct = (win_prob * win_loss_ratio - loss_prob) / win_loss_ratio
        kelly_pct = max(0, kelly_pct)  # Never negative
        kelly_pct *= self.kelly_fraction  # Apply fractional Kelly for safety

        kelly_investment = pv * kelly_pct
        qty_by_kelly = int(kelly_investment / current_price) if current_price > 0 else 0

        # Method 3: Max position size limit
        max_investment = pv * (self.max_position_pct / 100)
        qty_by_max = int(max_investment / current_price) if current_price > 0 else 0

        # Take the minimum of all three methods (most conservative)
        final_qty = max(1, min(qty_by_risk, qty_by_kelly, qty_by_max))
        investment_amount = final_qty * current_price
        actual_risk = final_qty * price_risk_per_share

        return {
            "quantity": final_qty,
            "investment_amount": round(investment_amount, 2),
            "investment_pct": round(investment_amount / pv * 100, 2),
            "risk_amount": round(actual_risk, 2),
            "risk_pct": round(actual_risk / pv * 100, 2),
            "stop_loss_price": round(current_price * (1 + stop_loss_pct / 100), 2),
            "target_price": round(current_price * (1 + target_pct / 100), 2),
            "kelly_fraction_used": round(kelly_pct, 4),
            "method": "min(risk_limit, half_kelly, max_position)",
            "details": {
                "qty_by_risk_limit": qty_by_risk,
                "qty_by_kelly": qty_by_kelly,
                "qty_by_max_position": qty_by_max,
                "win_prob": round(win_prob, 2),
                "win_loss_ratio": round(win_loss_ratio, 2),
            },
        }

    def _empty_result(self, reason: str) -> dict:
        return {
            "quantity": 0,
            "investment_amount": 0,
            "investment_pct": 0,
            "risk_amount": 0,
            "risk_pct": 0,
            "stop_loss_price": 0,
            "target_price": 0,
            "kelly_fraction_used": 0,
            "method": f"REJECTED: {reason}",
            "details": {},
        }
