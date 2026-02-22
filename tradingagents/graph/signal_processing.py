# TradingAgents/graph/signal_processing.py

import json
import re
from langchain_openai import ChatOpenAI


class SignalProcessor:
    """Processes trading signals to extract structured, machine-readable decisions."""

    def __init__(self, quick_thinking_llm: ChatOpenAI):
        """Initialize with an LLM for processing."""
        self.quick_thinking_llm = quick_thinking_llm

    def process_signal(self, full_signal: str) -> str:
        """
        Process a full trading signal to extract the core decision.
        Returns a simple BUY/SELL/HOLD string for backward compatibility.
        """
        structured = self.process_signal_structured(full_signal)
        return structured.get("decision", "HOLD")

    def process_signal_structured(self, full_signal: str) -> dict:
        """
        Process a full trading signal to extract a structured JSON decision.

        Returns:
            dict with keys: decision, confidence, stop_loss, target, rationale
        """
        messages = [
            (
                "system",
                """You are a signal extraction engine. Analyze the trading report and extract a structured JSON decision.

You MUST output ONLY valid JSON with these exact keys:
{
  "decision": "BUY" or "SELL" or "HOLD",
  "confidence": 0.0 to 1.0 (how confident you are),
  "stop_loss_pct": -1.0 to -20.0 (suggested stop-loss as negative percentage from current price, e.g. -5.0 means 5% below),
  "target_pct": 1.0 to 50.0 (suggested target as positive percentage from current price, e.g. 10.0 means 10% above),
  "risk_reward_ratio": float (target_pct / abs(stop_loss_pct)),
  "rationale": "One sentence summary of WHY this decision"
}

Rules:
- confidence > 0.7 = strong conviction
- confidence 0.4-0.7 = moderate
- confidence < 0.4 = weak/uncertain
- If HOLD, stop_loss_pct and target_pct should be 0
- risk_reward_ratio should be > 2.0 for BUY/SELL signals to be worth taking
- Output ONLY the JSON, no markdown, no explanation""",
            ),
            ("human", full_signal),
        ]

        try:
            raw = self.quick_thinking_llm.invoke(messages).content.strip()

            # Clean markdown code blocks if present
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)

            result = json.loads(raw)

            # Validate and normalize
            decision = result.get("decision", "HOLD").upper().strip()
            if decision not in ("BUY", "SELL", "HOLD"):
                decision = "HOLD"

            confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))

            return {
                "decision": decision,
                "confidence": round(confidence, 2),
                "stop_loss_pct": round(float(result.get("stop_loss_pct", 0)), 1),
                "target_pct": round(float(result.get("target_pct", 0)), 1),
                "risk_reward_ratio": round(float(result.get("risk_reward_ratio", 0)), 2),
                "rationale": str(result.get("rationale", "No rationale provided")),
            }

        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            # Fallback: try to extract just the decision from raw text
            fallback_decision = "HOLD"
            raw_upper = full_signal.upper()
            if "BUY" in raw_upper and "SELL" not in raw_upper:
                fallback_decision = "BUY"
            elif "SELL" in raw_upper and "BUY" not in raw_upper:
                fallback_decision = "SELL"

            return {
                "decision": fallback_decision,
                "confidence": 0.3,
                "stop_loss_pct": -5.0,
                "target_pct": 5.0,
                "risk_reward_ratio": 1.0,
                "rationale": f"Fallback extraction (JSON parse failed: {str(e)[:50]})",
            }
