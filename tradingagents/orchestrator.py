"""AQI Beast Orchestrator — Chains AI Brain → Quant Brain → Body.

This is the main entry point for the complete AQI trading system.
Can be triggered by OpenClaw, cron, or manual invocation.

Usage:
    from tradingagents.orchestrator import AQIOrchestrator
    
    bot = AQIOrchestrator(mode="paper")
    result = bot.run("RELIANCE.NS")
"""

import json
import os
from datetime import datetime, date
from typing import Dict, List, Optional

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.quant_brain.signal_validator import SignalValidator
from tradingagents.execution.paper_trader import PaperTrader
from tradingagents.execution.openalgo_bridge import OpenAlgoBridge


class AQIOrchestrator:
    """The Boss — orchestrates the full AI → Quant → Execution pipeline.
    
    Modes:
        - "paper": Paper trading (default, safe for testing)
        - "live": Real money via OpenAlgo (requires configuration)
        - "signal_only": Just generate signals, no execution
    """

    def __init__(
        self,
        mode: str = "paper",
        config: dict = None,
        selected_analysts: list = None,
    ):
        self.mode = mode
        self.config = config or {}
        self.selected_analysts = selected_analysts or ["market", "social", "news", "fundamentals"]
        
        # Initialize AI Brain (TradingAgents)
        self.ai_brain = TradingAgentsGraph(
            selected_analysts=self.selected_analysts,
            config=self.config,
        )
        
        # Initialize Quant Brain (SignalValidator chains backtest + risk + sizing)
        self.quant_brain = SignalValidator(self.config)
        
        # Initialize Body (execution layer)
        if mode == "live":
            self.body = OpenAlgoBridge(self.config)
        else:
            self.body = PaperTrader(self.config)
        
        # Results log
        log_dir = self.config.get("log_dir", "memory/orchestrator_logs")
        os.makedirs(log_dir, exist_ok=True)
        self.results_log = os.path.join(log_dir, "daily_results.jsonl")

    def run(
        self,
        ticker: str,
        trade_date: Optional[str] = None,
        current_price: Optional[float] = None,
        skip_backtest: bool = False,
    ) -> dict:
        """Run the full AQI pipeline for a single ticker.
        
        AI Brain analysis → Structured signal → Quant validation → Execution
        
        Args:
            ticker: Stock symbol (e.g., "RELIANCE.NS")
            trade_date: Date for analysis (default: today)
            current_price: Override current price (if None, uses latest from data)
            skip_backtest: Skip historical backtest validation
            
        Returns:
            dict with complete pipeline results
        """
        if trade_date is None:
            trade_date = date.today().strftime("%Y-%m-%d")

        result = {
            "ticker": ticker,
            "trade_date": trade_date,
            "mode": self.mode,
            "timestamp": datetime.now().isoformat(),
            "stages": {},
        }

        # ═══════════════════════════════════════════════════
        # STAGE 1: AI BRAIN — Generate trading signal
        # ═══════════════════════════════════════════════════
        print(f"\n{'='*60}")
        print(f"🤖 STAGE 1: AI Brain analyzing {ticker}...")
        print(f"{'='*60}")
        
        try:
            final_state, simple_signal = self.ai_brain.propagate(ticker, trade_date)
            
            # Get structured signal
            structured_signal = self.ai_brain.process_signal_structured(
                final_state["final_trade_decision"]
            )
            structured_signal["ticker"] = ticker
            
            result["stages"]["ai_brain"] = {
                "decision": structured_signal["decision"],
                "confidence": structured_signal["confidence"],
                "stop_loss_pct": structured_signal["stop_loss_pct"],
                "target_pct": structured_signal["target_pct"],
                "risk_reward_ratio": structured_signal["risk_reward_ratio"],
                "rationale": structured_signal["rationale"],
            }
            
            print(f"✅ AI Signal: {structured_signal['decision']} "
                  f"(confidence: {structured_signal['confidence']:.0%})")
            
        except Exception as e:
            result["stages"]["ai_brain"] = {"error": str(e)}
            result["final_status"] = "FAILED_AT_AI_BRAIN"
            self._log_result(result)
            print(f"❌ AI Brain failed: {e}")
            return result

        # If HOLD, no further processing needed
        if structured_signal["decision"] == "HOLD":
            result["final_status"] = "HOLD"
            result["order"] = None
            self._log_result(result)
            print(f"⏸️ HOLD — no trade executed")
            return result

        # Get current price if not provided
        if current_price is None:
            try:
                import yfinance as yf
                stock = yf.Ticker(ticker)
                current_price = stock.info.get("currentPrice") or stock.info.get("regularMarketPrice", 0)
            except Exception:
                current_price = 0

        if current_price <= 0:
            result["final_status"] = "FAILED_NO_PRICE"
            self._log_result(result)
            print(f"❌ Could not fetch current price for {ticker}")
            return result

        # ═══════════════════════════════════════════════════
        # STAGE 2: QUANT BRAIN — Validate, backtest, size
        # ═══════════════════════════════════════════════════
        print(f"\n{'='*60}")
        print(f"📊 STAGE 2: Quant Brain validating signal...")
        print(f"{'='*60}")
        
        validation = self.quant_brain.validate_and_size(
            signal=structured_signal,
            current_price=current_price,
            ticker=ticker,
            skip_backtest=skip_backtest,
        )
        
        result["stages"]["quant_brain"] = {
            "approved": validation["approved"],
            "reason": validation["reason"],
            "order": validation.get("order"),
            "warnings": validation.get("warnings", []),
        }
        
        if not validation["approved"]:
            result["final_status"] = f"REJECTED_BY_QUANT: {validation['reason']}"
            result["order"] = None
            self._log_result(result)
            print(f"🚫 REJECTED: {validation['reason']}")
            return result
        
        print(f"✅ Quant approved: {validation['order']['quantity']}x {ticker} "
              f"@ ₹{current_price:,.2f}")

        # ═══════════════════════════════════════════════════
        # STAGE 3: BODY — Execute (or paper trade)
        # ═══════════════════════════════════════════════════
        if self.mode == "signal_only":
            result["final_status"] = "SIGNAL_GENERATED"
            result["order"] = validation["order"]
            self._log_result(result)
            print(f"📋 Signal-only mode — order ready but not executed")
            return result

        print(f"\n{'='*60}")
        print(f"💪 STAGE 3: {'[PAPER]' if self.mode == 'paper' else '[LIVE]'} Executing...")
        print(f"{'='*60}")
        
        order = validation["order"]
        execution_result = self.body.place_order(order)
        
        result["stages"]["execution"] = execution_result
        
        if execution_result["success"]:
            # Register position in risk engine
            self.quant_brain.risk_engine.register_position(
                ticker=ticker,
                quantity=order["quantity"],
                price=current_price,
                stop_loss=order["stop_loss"],
                target=order["target"],
                side=order["side"],
            )
            result["final_status"] = "EXECUTED"
            result["order"] = order
            print(f"✅ {execution_result['message']}")
        else:
            result["final_status"] = f"EXECUTION_FAILED: {execution_result['message']}"
            result["order"] = None
            print(f"❌ {execution_result['message']}")

        self._log_result(result)
        return result

    def run_watchlist(
        self,
        tickers: List[str],
        trade_date: Optional[str] = None,
        skip_backtest: bool = False,
    ) -> List[dict]:
        """Run the pipeline for multiple tickers.
        
        Args:
            tickers: List of stock symbols
            trade_date: Date for analysis
            skip_backtest: Skip backtesting for speed
        
        Returns:
            List of result dicts, one per ticker
        """
        results = []
        for i, ticker in enumerate(tickers, 1):
            print(f"\n{'#'*60}")
            print(f"# [{i}/{len(tickers)}] Processing {ticker}")
            print(f"{'#'*60}")
            
            try:
                result = self.run(ticker, trade_date, skip_backtest=skip_backtest)
                results.append(result)
            except Exception as e:
                results.append({
                    "ticker": ticker,
                    "final_status": f"ERROR: {str(e)}",
                    "error": str(e),
                })
        
        # Print summary
        self._print_summary(results)
        return results

    def get_status(self) -> dict:
        """Get current system status — for OpenClaw monitoring."""
        portfolio = self.quant_brain.get_portfolio_summary()
        
        if hasattr(self.body, 'get_portfolio'):
            broker_portfolio = self.body.get_portfolio()
        else:
            broker_portfolio = {}
        
        return {
            "mode": self.mode,
            "timestamp": datetime.now().isoformat(),
            "risk_engine": portfolio,
            "broker": broker_portfolio,
            "kill_switch_active": portfolio.get("kill_switch_active", False),
        }

    def kill_switch(self):
        """Emergency: Cancel all orders and stop trading."""
        print("🚨 KILL SWITCH ACTIVATED")
        result = self.body.cancel_all_orders()
        print(f"   {result.get('message', 'Unknown')}")
        return result

    def _print_summary(self, results: List[dict]):
        """Print a summary table of all results."""
        print(f"\n{'='*60}")
        print(f"📊 DAILY SUMMARY — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*60}")
        print(f"{'Ticker':<15} {'Decision':<8} {'Status':<25}")
        print(f"{'-'*48}")
        for r in results:
            ticker = r.get("ticker", "?")
            decision = r.get("stages", {}).get("ai_brain", {}).get("decision", "?")
            status = r.get("final_status", "?")[:25]
            print(f"{ticker:<15} {decision:<8} {status:<25}")
        print(f"{'='*60}")

    def _log_result(self, result: dict):
        """Log result to JSONL file."""
        try:
            with open(self.results_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, default=str) + "\n")
        except Exception:
            pass
