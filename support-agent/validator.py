"""
validator.py — Pydantic models and JSON parsing for LLM output.

Validates that the LLM response matches the exact schema defined in
prompts/system_prompt.txt, and provides a safe fallback when it doesn't.
"""

import json
import re
from typing import Literal
from pydantic import BaseModel, ValidationError


# ── Pydantic schema ────────────────────────────────────────────────────────────

class SupportResponse(BaseModel):
    """Mirrors the JSON output format defined in prompts/system_prompt.txt."""

    issue_category: Literal[
        "billing", "delivery", "technical_support",
        "refunds", "account_access", "other"
    ]
    intent:                 str
    urgency:                Literal["low", "medium", "high", "urgent"]
    sentiment:              Literal["calm", "frustrated", "angry"]
    summary:                str
    priority:               Literal["low", "medium", "high", "urgent"]
    relevant_policy:        str           # quoted text + source, or "none"
    recommended_resolution: str
    escalation_required:    bool
    escalation_reason:      str           # empty string when not escalating
    missing_information:    list[str]     # empty list when nothing is missing
    customer_reply:         str


# ── Parsing helpers ────────────────────────────────────────────────────────────

def _strip_code_fences(text: str) -> str:
    """
    Remove ```json ... ``` or ``` ... ``` wrappers that the LLM sometimes adds,
    even though the prompt tells it not to.
    """
    # Match an optional language tag after the opening fence
    fenced = re.match(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    return text.strip()


def _extract_json_object(text: str) -> str:
    """
    Pull out the first {...} block from the text.
    Handles cases where the model adds a sentence before or after the JSON.
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in LLM output.")
    return match.group(0)


# ── Public API ─────────────────────────────────────────────────────────────────

def parse_and_validate(raw_text: str) -> SupportResponse:
    """
    Parse `raw_text` from the LLM into a validated SupportResponse.

    Steps:
      1. Strip markdown code fences.
      2. Extract the first {...} JSON object.
      3. json.loads → dict.
      4. Pydantic validation.

    Raises:
        ValueError: with a clear message when parsing or validation fails.
    """
    try:
        clean    = _strip_code_fences(raw_text)
        json_str = _extract_json_object(clean)
        data     = json.loads(json_str)
        return SupportResponse(**data)

    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from LLM: {exc}") from exc

    except ValidationError as exc:
        # Summarise which fields failed so the retry message is useful
        errors = "; ".join(
            f"{'.'.join(str(l) for l in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        )
        raise ValueError(f"Schema validation failed — {errors}") from exc


def fallback_response(reason: str) -> SupportResponse:
    """
    Return a safe, human-escalation response when the LLM output cannot be
    parsed or validated after all retries are exhausted.

    Args:
        reason: Internal error description (logged, not shown to customer).
    """
    return SupportResponse(
        issue_category="other",
        intent="Unknown — could not parse LLM response",
        urgency="high",
        sentiment="calm",
        summary=f"Automated parsing failed: {reason}",
        priority="high",
        relevant_policy="none",
        recommended_resolution=(
            "Parsing failed after max retries. Route to a human agent immediately."
        ),
        escalation_required=True,
        escalation_reason=f"LLM output could not be validated: {reason}",
        missing_information=[],
        customer_reply=(
            "I'm sorry, I wasn't able to process your request automatically. "
            "A human agent will follow up with you shortly. "
            "Thank you for your patience!"
        ),
    )
