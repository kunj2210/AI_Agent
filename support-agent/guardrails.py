"""
guardrails.py — Pre- and post-generation safety checks (no extra libraries).

Pre-check  : runs on raw user message before it reaches the LLM.
Post-check : enforces business rules on the validated response dict.
"""

import re

# ── Constants ──────────────────────────────────────────────────────────────────

# Phrases that suggest the user is trying prompt injection
_INJECTION_PATTERNS = re.compile(
    r"ignore\s+(all|previous)\s+instructions?"
    r"|system\s+prompt"
    r"|reveal\s+your\s+instructions?"
    r"|you\s+are\s+now"
    r"|act\s+as"
    r"|developer\s+mode"
    r"|override\s+rules?",
    re.IGNORECASE,
)

# Words that signal anger / frustration
_ANGRY_WORDS = re.compile(
    r"\b(worst|scam|furious|useless|fraud|cheater?|liar|horrible|disgusting|pathetic)\b",
    re.IGNORECASE,
)

# Promises the agent must never make to a customer
_PROMISE_PHRASES = re.compile(
    r"\bguarantee\b"
    r"|\b100\s*%\b"
    r"|definitely\s+refund"
    r"|I\s+promise"
    r"|will\s+be\s+refunded",
    re.IGNORECASE,
)

# Soft approval wording to neutralise when escalation is required
_APPROVAL_PHRASES = re.compile(
    r"(refund\s+(has\s+been\s+)?(approved|processed|confirmed|initiated))",
    re.IGNORECASE,
)

# Safe replacement for detected promise / approval phrases
_SAFE_PROMISE_REPLY = (
    "Thank you for reaching out. Your request has been noted and will be "
    "reviewed by our team. A specialist will follow up with you shortly. "
    "We appreciate your patience!"
)

_SAFE_APPROVAL_REPLACEMENT = "refund is pending review by a human agent"

# Detects multiple distinct day-windows in the same policy text
# e.g. "30 days" AND "7 days" appearing together → likely a conflict
_POLICY_CONFLICT = re.compile(r"(\d+)\s*days?", re.IGNORECASE)

# Priority ordering used when raising priority by one level
_PRIORITY_LEVELS = ["low", "medium", "high", "urgent"]


# ── Helper functions ───────────────────────────────────────────────────────────

def detect_injection(text: str) -> bool:
    """Return True if `text` contains a known prompt-injection pattern."""
    return bool(_INJECTION_PATTERNS.search(text))


def extract_refund_amount(text: str) -> float | None:
    """
    Look for a currency amount (₹ / Rs / INR) near refund-related words.
    Returns the amount as a float, or None if not found.
    """
    # Match patterns like ₹5000, Rs.500, INR 2,500 near refund/money-back
    pattern = re.compile(
        r"(?:refund|money\s+back|return|reimburse).{0,60}"   # anchor word first
        r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d{1,2})?)"         # then amount
        r"|"
        r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d{1,2})?)"         # or amount first
        r".{0,60}(?:refund|money\s+back|return|reimburse)",   # then anchor word
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if match:
        raw = match.group(1) or match.group(2)
        return float(raw.replace(",", ""))
    return None


def _is_mostly_caps(text: str) -> bool:
    """True if more than 60 % of the alpha characters in `text` are uppercase."""
    alpha = [c for c in text if c.isalpha()]
    if len(alpha) < 10:          # too short to judge
        return False
    return (sum(c.isupper() for c in alpha) / len(alpha)) > 0.60


def _raise_priority(current: str) -> str:
    """Raise `current` priority one level, capped at 'urgent'."""
    idx = _PRIORITY_LEVELS.index(current) if current in _PRIORITY_LEVELS else 0
    return _PRIORITY_LEVELS[min(idx + 1, len(_PRIORITY_LEVELS) - 1)]


# ── Public API ─────────────────────────────────────────────────────────────────

def pre_check(user_message: str) -> dict:
    """
    Analyse the raw user message before it reaches the LLM.

    Returns a flags dict:
      {
        "injection":      bool,
        "refund_amount":  float | None,
        "angry":          bool,
        "blocked":        False,   # pre-check never hard-blocks; LLM + post-check handle it
      }
    """
    angry = bool(_ANGRY_WORDS.search(user_message)) or _is_mostly_caps(user_message)
    return {
        "injection":     detect_injection(user_message),
        "refund_amount": extract_refund_amount(user_message),
        "angry":         angry,
        "blocked":       False,   # always let the message reach the LLM
    }


def post_check(response: dict, flags: dict, business_rules: dict) -> dict:
    """
    Enforce business rules on the validated response dict after the LLM call.

    Mutates and returns the response dict.

    Rules applied (in order):
      0. Policy conflict in relevant_policy → force escalation.
      1. Injection detected  → force escalation; neutralise any approval wording.
      2. Refund > limit      → force escalation with a specific reason.
      3. Angry customer      → raise priority one level.
      4. Promise phrases     → replace customer_reply with a safe message + escalate.
      5. Approval while escalating → soften to "pending review by a human agent".
    """
    max_refund = business_rules.get("max_auto_refund_amount", 5000)

    # ── Rule 0: Return policy conflict (30-day vs 7-day window) ───────────────
    # If the quoted policy text mentions both conflicting return windows:
    policy_text = response.get("relevant_policy", "").lower()
    has_conflict = (
        ("return" in policy_text or "refund" in policy_text)
        and ("30 days" in policy_text or "30 day" in policy_text)
        and ("7 days" in policy_text or "7 day" in policy_text)
    )
    if has_conflict and not response.get("escalation_required"):
        response["escalation_required"] = True
        response["escalation_reason"] = (
            "Policy conflict detected: 30-day general refund window contradicts "
            "7-day sale return window. Cannot resolve without human review."
        )


    # ── Rule 1: Injection ──────────────────────────────────────────────────────
    if flags.get("injection"):
        response["escalation_required"] = True
        if not response.get("escalation_reason"):
            response["escalation_reason"] = "Possible prompt injection attempt detected."
        # Never allow approval wording to reach the customer after an injection attempt
        response["customer_reply"] = (
            "I'm sorry, but I'm unable to process that request. "
            "A member of our support team will be in touch with you shortly."
        )

    # ── Rule 2: Refund amount exceeds auto-approval limit ─────────────────────
    refund_amount = flags.get("refund_amount")
    if refund_amount is not None and refund_amount > max_refund:
        response["escalation_required"] = True
        response["escalation_reason"] = (
            f"Refund amount (₹{refund_amount:,.0f}) exceeds the auto-approval "
            f"limit of ₹{max_refund:,.0f}. Requires human review."
        )
        # Priority must be at least "high"
        if response.get("priority") in ("low", "medium"):
            response["priority"] = "high"

    # ── Rule 3: Angry customer → raise priority one level ─────────────────────
    if flags.get("angry") and "priority" in response:
        response["priority"] = _raise_priority(response["priority"])

    # ── Rule 4: Promise / guarantee phrases in customer_reply ─────────────────
    if _PROMISE_PHRASES.search(response.get("customer_reply", "")):
        response["customer_reply"]      = _SAFE_PROMISE_REPLY
        response["escalation_required"] = True
        if not response.get("escalation_reason"):
            response["escalation_reason"] = (
                "Customer reply contained an unsupported promise; replaced with safe message."
            )

    # ── Rule 5: Approval wording while escalation is required ─────────────────
    if response.get("escalation_required"):
        for field in ("recommended_resolution", "customer_reply"):
            if field in response:
                response[field] = _APPROVAL_PHRASES.sub(
                    _SAFE_APPROVAL_REPLACEMENT, response[field]
                )

    return response
