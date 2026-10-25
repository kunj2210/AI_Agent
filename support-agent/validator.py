"""
validator.py — Pydantic models and JSON parsing for LLM output.

Validates that the LLM response matches the exact schema defined in
prompts/system_prompt.txt, and provides a safe fallback when it doesn't.
"""

import json
import re
from typing import Literal, Union, Any
from pydantic import BaseModel, Field, field_validator


# ── Pydantic schema ────────────────────────────────────────────────────────────

class PolicyExcerpt(BaseModel):
    source: str
    excerpt: str


class SupportResponse(BaseModel):
    """Mirrors the exact JSON output format defined in the assignment specification."""

    issue_category: Literal[
        "billing", "delivery", "technical_support",
        "refund", "refunds", "account_access", "other"
    ]
    intent:                     str
    summary:                    str
    priority:                   Literal["low", "medium", "high", "critical", "urgent"]
    sentiment:                  Literal["neutral", "calm", "frustrated", "angry"]
    relevant_policy:            Union[list[PolicyExcerpt], list[dict[str, Any]], str]
    recommended_resolution:     str
    escalation_required:        bool
    escalation_reason:          Union[str, None] = None
    missing_information:        list[str] = Field(default_factory=list)
    policy_conflict_detected:   bool = False
    injection_attempt_detected: bool = False
    customer_reply:             str

    @field_validator("relevant_policy", mode="before")
    @classmethod
    def normalize_relevant_policy(cls, v: Any) -> Any:
        if isinstance(v, str):
            return [{"source": "knowledge_base", "excerpt": v}] if v and v.lower() != "none" else []
        if isinstance(v, list):
            res = []
            for item in v:
                if isinstance(item, dict):
                    res.append(PolicyExcerpt(
                        source=item.get("source", "knowledge_base"),
                        excerpt=item.get("excerpt", str(item))
                    ))
                elif isinstance(item, str):
                    res.append(PolicyExcerpt(source="knowledge_base", excerpt=item))
            return res
        return []

    @field_validator("sentiment", mode="before")
    @classmethod
    def normalize_sentiment(cls, v: str) -> str:
        if v == "calm":
            return "neutral"
        return v

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, v: str) -> str:
        if v == "urgent":
            return "critical"
        return v


# ── Parsing helpers ────────────────────────────────────────────────────────────

def _strip_code_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers."""
    fenced = re.match(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    return text.strip()


def _extract_json_object(text: str) -> str:
    """Pull out the first {...} block from the text."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in LLM output.")
    return match.group(0)


# ── Public API ─────────────────────────────────────────────────────────────────

def parse_and_validate(raw_text: str) -> SupportResponse:
    """
    Parse raw_text from the LLM into a validated SupportResponse.
    """
    try:
        clean    = _strip_code_fences(raw_text)
        json_str = _extract_json_object(clean)
        data     = json.loads(json_str)
        return SupportResponse(**data)

    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from LLM: {exc}") from exc

    except Exception as exc:
        raise ValueError(f"Schema validation failed — {exc}") from exc


def fallback_response(reason: str) -> SupportResponse:
    """
    Return a safe, human-escalation response when the LLM output cannot be
    parsed or validated after all retries are exhausted.
    """
    return SupportResponse(
        issue_category="other",
        intent="Unknown — could not parse LLM response",
        summary=f"Automated processing escalated: {reason}",
        priority="high",
        sentiment="neutral",
        relevant_policy=[],
        recommended_resolution="Parsing failed after max retries. Route to a human agent immediately.",
        escalation_required=True,
        escalation_reason=f"LLM output could not be validated: {reason}",
        missing_information=[],
        policy_conflict_detected=False,
        injection_attempt_detected=False,
        customer_reply=(
            "I'm sorry, I wasn't able to process your request automatically. "
            "A human agent will follow up with you shortly. "
            "Thank you for your patience!"
        ),
    )
