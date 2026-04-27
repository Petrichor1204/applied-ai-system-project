"""Simple guardrails and input/response validators for PawPal+.

This module contains lightweight, deterministic checks used to:
- detect medical red flags in user text and return a safe, non-LLM response
- sanitize LLM/user text for downstream logging or display
"""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger("pawpal.guardrails")

# A compact set of patterns that indicate urgent medical issues requiring a
# human (veterinarian) rather than an automated suggestion.
_MEDICAL_PATTERNS = [
    r"not (?:eating|eaten)",
    r"not eating for \d+",
    r"blood",
    r"bleeding",
    r"seizure",
    r"difficulty breathing",
    r"trouble breathing",
    r"unable to move",
    r"collapse",
    r"unconscious",
    r"lifeless",
    r"vomit",
    r"diarrhea",
    r"poison",
    r"toxic",
]


def _text_matches_medical(text: str) -> Optional[str]:
    txt = (text or "").lower()
    for pat in _MEDICAL_PATTERNS:
        if re.search(pat, txt):
            return pat
    return None


def check_for_medical_redflags(text: str) -> Optional[str]:
    """Return a human-facing guardrail message if a medical red-flag is found.

    If a red flag is detected, callers should short-circuit LLM calls and
    present this high-confidence directive to consult a veterinarian.
    """
    if not text:
        return None
    match = _text_matches_medical(text)
    if not match:
        return None
    logger.warning("Medical red-flag detected (%s) in input: %r", match, text[:200])
    return (
        "I detected a potential medical emergency in the information you provided. "
        "This looks urgent — please consult a veterinarian or emergency clinic right away. "
        "I cannot provide medical diagnosis."
    )


def sanitize_text(text: str, max_len: int = 1000) -> str:
    """Basic sanitizer for storing or displaying model/user text.

    - Trims length
    - Collapses excessive whitespace
    - Removes control characters
    """
    if text is None:
        return ""
    s = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_len:
        s = s[: max_len - 3] + "..."
    return s
