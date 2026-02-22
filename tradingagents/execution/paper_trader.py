"""Paper Trader — Simulated execution for testing without real money.

Behaves identically to OpenAlgoBridge but executes in memory.
Tracks P&L, fills orders at current prices, applies slippage.
"""

import json
import os
from datetime import datetime
from typing import Dict, List


class PaperTrader:
    """Simulated broker for paper trading.
    
    Use this instead of OpenAlgoBridge during testing.
    Same interface, zero risk.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.initial_capital = self.config.get("paper_capital", 100000.0)
        self.capital = self.initial_capital
        self.slippage_pct = self.config.get("slippage_pct", 0.1)  # 0.1% slippage
        self.positions: Dict[str, dict] = {}
        self.trade_history: List[dict] = []
        self.order_counter = 0
        
        # Persistence
        log_dir = self.config.get("log_dir", "memory/paper_trading")
        os.makedirs(log_dir, exist_ok=True)
        self.state_file = os.path.join(log_dir, "paper_state.json")
        self.trade_log = os.path.join(log_dir, "paper_trades.jsonl")
        self._load_state()

    @property
    def is_configured(self) -> bool:
        return True  # Always configured — it's paper trading

    def place_order(self, order: dict) -> dict:
        """Simulate order execution."""
        self.order_counter += 1
        order_id = f"PAPER-{self.order_counter:06d}"
        
        ticker = order["ticker"]
        side = order["side"]
        quantity = order["quantity"]
        price = order["price"]
        
        # Apply slippage
        if side == "BUY":
            fill_price = price * (1 + self.slippage_pct / 100)
        else:
            fill_price = price * (1 - self.slippage_pct / 100)
        
        cost = fill_price * quantity
        
        if side == "BUY":
            if cost > self.capital:
                return {
                    "success": False,
                    "order_id": None,
                    "message": f"Insufficient capital: need ₹{cost:,.2f}, have ₹{self.capital:,.2f}",
                }
            self.capital -= cost
            self.positions[ticker] = {
                "ticker": ticker,
                "side": side,
                "quantity": quantity,
                "entry_price": fill_price,
                "stop_loss": order.get("stop_loss", 0),
                "target": order.get("target", 0),
                "entry_time": datetime.now().isoformat(),
            }
        elif side == "SELL":
            if ticker in self.positions:
                pos = self.positions[ticker]
                pnl = (fill_price - pos["entry_price"]) * pos["quantity"]
                self.capital += pos["quantity"] * fill_price
                self.trade_history.append({
                    "ticker": ticker,
                    "side": "SELL",
                    "entry_price": pos["entry_price"],
                    "exit_price": fill_price,
                    "quantity": pos["quantity"],
                    "pnl": round(pnl, 2),
                    "timestamp": datetime.now().isoformat(),
                })
                del self.positions[ticker]
            else:
                # Short selling (simplified)
                self.capital += cost
                self.positions[ticker] = {
                    "ticker": ticker,
                    "side": "SELL",
                    "quantity": quantity,
                    "entry_price": fill_price,
                    "stop_loss": order.get("stop_loss", 0),
                    "target": order.get("target", 0),
                    "entry_time": datetime.now().isoformat(),
                }
        
        self._save_state()
        self._log_trade(order, order_id, fill_price)
        
        return {
            "success": True,
            "order_id": order_id,
            "message": f"[PAPER] {side} {quantity}x {ticker} @ ₹{fill_price:,.2f} (slippage: {self.slippage_pct}%)",
        }

    def place_bracket_order(self, order: dict) -> dict:
        """Simulate bracket order (same as regular for paper trading)."""
        return self.place_order(order)

    def get_positions(self) -> dict:
        return {"success": True, "positions": list(self.positions.values())}

    def get_portfolio(self) -> dict:
        total_invested = sum(
            p["entry_price"] * p["quantity"] for p in self.positions.values()
        )
        total_pnl = sum(t["pnl"] for t in self.trade_history)
        
        return {
            "success": True,
            "holdings": list(self.positions.values()),
            "summary": {
                "initial_capital": self.initial_capital,
                "current_capital": round(self.capital, 2),
                "invested": round(total_invested, 2),
                "total_realized_pnl": round(total_pnl, 2),
                "total_trades": len(self.trade_history),
                "open_positions": len(self.positions),
                "return_pct": round((self.capital - self.initial_capital) / self.initial_capital * 100, 2),
            },
        }

    def cancel_all_orders(self) -> dict:
        return {"success": True, "message": "[PAPER] All orders cancelled"}

    def _save_state(self):
        try:
            state = {
                "capital": self.capital,
                "initial_capital": self.initial_capital,
                "positions": self.positions,
                "trade_count": len(self.trade_history),
                "order_counter": self.order_counter,
                "last_updated": datetime.now().isoformat(),
            }
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    def _load_state(self):
        if not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
            self.capital = state.get("capital", self.initial_capital)
            self.positions = state.get("positions", {})
            self.order_counter = state.get("order_counter", 0)
            print(f"[PaperTrader] Loaded: ₹{self.capital:,.2f}, {len(self.positions)} positions")
        except Exception:
            pass

    def _log_trade(self, order: dict, order_id: str, fill_price: float):
        try:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "order_id": order_id,
                "order": order,
                "fill_price": fill_price,
                "capital_after": round(self.capital, 2),
            }
            with open(self.trade_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception:
            pass
