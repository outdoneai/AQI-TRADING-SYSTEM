"""OpenAlgo Bridge — Connects AI trading signals to real broker execution.

Uses OpenAlgo's REST API for broker-agnostic order management.
Supports all brokers that OpenAlgo supports (25+ Indian brokers).

Setup:
1. Install and run OpenAlgo: https://openalgo.in
2. Set OPENALGO_API_KEY and OPENALGO_HOST environment variables
3. Connect your broker in OpenAlgo dashboard
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional


class OpenAlgoBridge:
    """Bridge between the AQI trading system and OpenAlgo execution.
    
    Translates validated orders from the Quant Brain into
    OpenAlgo API calls for real broker execution.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.api_key = self.config.get("openalgo_api_key", os.environ.get("OPENALGO_API_KEY", ""))
        self.host = self.config.get("openalgo_host", os.environ.get("OPENALGO_HOST", "http://127.0.0.1:5000"))
        self.broker = self.config.get("broker", "shoonya")  # Default to free broker
        
        # Order log
        log_dir = self.config.get("log_dir", "memory/execution_logs")
        os.makedirs(log_dir, exist_ok=True)
        self.order_log = os.path.join(log_dir, "order_log.jsonl")
        
        self._session = None

    @property
    def is_configured(self) -> bool:
        """Check if OpenAlgo is configured and reachable."""
        return bool(self.api_key)

    def _get_session(self):
        """Get or create HTTP session."""
        if self._session is None:
            try:
                import requests
                self._session = requests.Session()
                self._session.headers.update({
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                })
            except ImportError:
                raise ImportError("requests library required. Install: pip install requests")
        return self._session

    def place_order(self, order: dict) -> dict:
        """Place an order via OpenAlgo API.
        
        Args:
            order: Validated order from SignalValidator
                {ticker, side, quantity, order_type, price, stop_loss, target}
        
        Returns:
            dict with: success, order_id, message
        """
        if not self.is_configured:
            return {
                "success": False,
                "order_id": None,
                "message": "OpenAlgo not configured. Set OPENALGO_API_KEY environment variable.",
            }

        try:
            session = self._get_session()
            
            # Map our order format to OpenAlgo API format
            # OpenAlgo uses exchange:symbol format (e.g., NSE:RELIANCE)
            ticker = order["ticker"].replace(".NS", "").replace(".BO", "")
            exchange = "NSE"  # Default to NSE
            
            payload = {
                "apikey": self.api_key,
                "strategy": "AQI_Beast",
                "symbol": ticker,
                "exchange": exchange,
                "action": order["side"].upper(),  # BUY or SELL
                "quantity": str(order["quantity"]),
                "pricetype": order.get("order_type", "LIMIT").upper(),
                "price": str(order.get("price", 0)),
                "product": "MIS",  # Intraday by default
            }
            
            response = session.post(
                f"{self.host}/api/v1/placeorder",
                json=payload,
                timeout=10,
            )
            
            result = response.json()
            
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "order": order,
                "payload": payload,
                "response": result,
                "status_code": response.status_code,
            }
            self._log_order(log_entry)
            
            if response.status_code == 200 and result.get("status") == "success":
                order_id = result.get("orderid", result.get("data", {}).get("orderid", "unknown"))
                return {
                    "success": True,
                    "order_id": order_id,
                    "message": f"Order placed: {order['side']} {order['quantity']}x {ticker}",
                }
            else:
                return {
                    "success": False,
                    "order_id": None,
                    "message": f"OpenAlgo error: {result.get('message', str(result))}",
                }

        except Exception as e:
            error_result = {
                "success": False,
                "order_id": None,
                "message": f"Order failed: {str(e)}",
            }
            self._log_order({"timestamp": datetime.now().isoformat(), "error": str(e), "order": order})
            return error_result

    def place_bracket_order(self, order: dict) -> dict:
        """Place a bracket order (entry + stop-loss + target) via OpenAlgo.
        
        This is the preferred method — it automatically sets SL and target.
        """
        if not self.is_configured:
            return {"success": False, "order_id": None, "message": "OpenAlgo not configured"}

        try:
            session = self._get_session()
            ticker = order["ticker"].replace(".NS", "").replace(".BO", "")
            
            payload = {
                "apikey": self.api_key,
                "strategy": "AQI_Beast",
                "symbol": ticker,
                "exchange": "NSE",
                "action": order["side"].upper(),
                "quantity": str(order["quantity"]),
                "pricetype": "LIMIT",
                "price": str(order.get("price", 0)),
                "product": "BO",  # Bracket Order
                "stoploss": str(abs(order.get("price", 0) - order.get("stop_loss", 0))),
                "target": str(abs(order.get("target", 0) - order.get("price", 0))),
            }
            
            response = session.post(
                f"{self.host}/api/v1/placeorder",
                json=payload,
                timeout=10,
            )
            
            result = response.json()
            self._log_order({"timestamp": datetime.now().isoformat(), "bracket_order": payload, "response": result})
            
            if response.status_code == 200 and result.get("status") == "success":
                return {
                    "success": True,
                    "order_id": result.get("orderid", "unknown"),
                    "message": f"Bracket order placed: {order['side']} {order['quantity']}x {ticker} | SL: {order.get('stop_loss')} | Target: {order.get('target')}",
                }
            else:
                return {"success": False, "order_id": None, "message": f"OpenAlgo error: {result}"}

        except Exception as e:
            return {"success": False, "order_id": None, "message": f"Bracket order failed: {str(e)}"}

    def get_positions(self) -> dict:
        """Get current open positions from broker via OpenAlgo."""
        if not self.is_configured:
            return {"success": False, "positions": []}

        try:
            session = self._get_session()
            response = session.post(
                f"{self.host}/api/v1/positionbook",
                json={"apikey": self.api_key},
                timeout=10,
            )
            result = response.json()
            return {"success": True, "positions": result.get("data", [])}
        except Exception as e:
            return {"success": False, "positions": [], "error": str(e)}

    def get_portfolio(self) -> dict:
        """Get portfolio holdings from broker via OpenAlgo."""
        if not self.is_configured:
            return {"success": False, "holdings": []}

        try:
            session = self._get_session()
            response = session.post(
                f"{self.host}/api/v1/holdings",
                json={"apikey": self.api_key},
                timeout=10,
            )
            result = response.json()
            return {"success": True, "holdings": result.get("data", [])}
        except Exception as e:
            return {"success": False, "holdings": [], "error": str(e)}

    def cancel_all_orders(self) -> dict:
        """Emergency: Cancel all pending orders (kill switch)."""
        if not self.is_configured:
            return {"success": False, "message": "Not configured"}

        try:
            session = self._get_session()
            response = session.post(
                f"{self.host}/api/v1/cancelallorder",
                json={"apikey": self.api_key, "strategy": "AQI_Beast"},
                timeout=10,
            )
            result = response.json()
            self._log_order({"timestamp": datetime.now().isoformat(), "action": "KILL_SWITCH", "response": result})
            return {"success": True, "message": "All orders cancelled"}
        except Exception as e:
            return {"success": False, "message": f"Cancel failed: {str(e)}"}

    def _log_order(self, entry: dict):
        """Append order to execution log."""
        try:
            with open(self.order_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception:
            pass
