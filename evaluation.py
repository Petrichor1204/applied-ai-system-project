"""Lightweight evaluation and logging utilities for PawPal+ reliability metrics.

This module appends JSON-lines to `logs/reliability.jsonl` and exposes a
small helper to compute basic metrics (average confidence, fallback rate).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from statistics import mean
from typing import Dict, Any

logger = logging.getLogger("pawpal.evaluation")

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
_LOG_FILE = LOG_DIR / "reliability.jsonl"


def record_call(call_type: str, response: str, confidence: float, fallback: bool = False, extra: Dict[str, Any] | None = None) -> None:
    payload = {
        "ts": __import__("time").time(),
        "call_type": call_type,
        "confidence": float(confidence),
        "fallback": bool(fallback),
        "response_len": len(response or ""),
        "response": (response or "")[:1000],
        "extra": extra or {},
    }
    try:
        with _LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.exception("Failed to write reliability log: %s", exc)


def get_metrics(last_n: int = 200) -> Dict[str, Any]:
    """Compute simple metrics from the most recent `last_n` records.

    Returns a dict with `count`, `avg_confidence`, and `fallback_rate`.
    """
    if not _LOG_FILE.exists():
        return {"count": 0, "avg_confidence": None, "fallback_rate": None}
    vals = []
    fallbacks = 0
    count = 0
    try:
        with _LOG_FILE.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                vals.append(rec.get("confidence", 0.0))
                if rec.get("fallback"):
                    fallbacks += 1
                count += 1
                if count >= last_n:
                    break
    except Exception as exc:
        logger.exception("Failed reading reliability log: %s", exc)
    return {
        "count": count,
        "avg_confidence": float(mean(vals)) if vals else None,
        "fallback_rate": (fallbacks / count) if count else None,
    }
