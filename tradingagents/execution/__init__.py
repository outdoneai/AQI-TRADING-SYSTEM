"""Execution Layer — OpenAlgo bridge for order execution.

Connects to OpenAlgo for broker-agnostic order execution.
Supports: Shoonya (₹0 brokerage), Angel One, Zerodha, Dhan, etc.
"""

from tradingagents.execution.openalgo_bridge import OpenAlgoBridge
from tradingagents.execution.paper_trader import PaperTrader

__all__ = ["OpenAlgoBridge", "PaperTrader"]
