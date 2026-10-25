"""
agent.py — Orchestrates the full resolution pipeline.

Flow per message:
  guardrail pre-check → retrieval → build prompt → LLM call
  → parse/validate (with retry) → guardrail post-check → return dict
"""

import os
import re
import yaml

from retriever  import get_retriever
from llm        import call_llm
from validator  import SupportResponse, parse_and_validate, fallback_response
from guardrails import pre_check, post_check

# ── Paths ──────────────────────────────────────────────────────────────────────
_BASE        = os.path.dirname(__file__)
_KB_FOLDER   = os.path.join(_BASE, "knowledge_base")
_PROMPT_FILE       = os.path.join(_BASE, "prompts", "system_prompt.txt")
_RETRY_PROMPT_FILE = os.path.join(_BASE, "prompts", "retry_prompt.txt")
_JSON_CFG        = os.path.join(_BASE, "config.json")
_AGENT_CFG         = os.path.join(_BASE, "config", "agent_config.yaml")
_BIZ_CFG           = os.path.join(_BASE, "config", "business_rules.yaml")


# ── Config helpers ─────────────────────────────────────────────────────────────

def load_config() -> dict:
    """
    Read config fresh on every call so admin edits apply immediately
    without restarting the server. Prefers config.json if available.
    """
    if os.path.exists(_JSON_CFG):
        with open(_JSON_CFG, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    with open(_AGENT_CFG, "r", encoding="utf-8") as f:
        agent = yaml.safe_load(f) or {}
    with open(_BIZ_CFG, "r", encoding="utf-8") as f:
        biz = yaml.safe_load(f) or {}
    return {**agent, **biz}


def _load_prompt_template() -> str:
    with open(_PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()


# ── Prompt builder ─────────────────────────────────────────────────────────────

def build_system_prompt(config: dict, retrieved_chunks: list[dict]) -> str:
    """
    Fill all {placeholders} in prompts/system_prompt.txt.
    If retrieval returned nothing, inject a note telling the model to escalate.
    """
    template = _load_prompt_template()

    if retrieved_chunks:
        policy_lines = [
            f"[Source: {c['source']}]\n{c['text']}" for c in retrieved_chunks
        ]
        retrieved_policies = "\n\n---\n\n".join(policy_lines)
    else:
        retrieved_policies = (
            "No relevant policy found in the knowledge base. "
            "Recommend escalation to a human agent."
        )

    def _bullets(items) -> str:
        return "\n".join(f"- {item}" for item in items)

    return template.format(
        role                = config.get("role", "AI Support Agent").strip(),
        tone                = config.get("tone", "professional_and_friendly"),
        supported_topics    = ", ".join(config.get("supported_topics", [])),
        escalation_rules    = _bullets(config.get("escalation_rules", [])),
        response_boundaries = _bullets(config.get("response_boundaries", [])),
        retrieved_policies  = retrieved_policies,
    )


# ── Main pipeline ──────────────────────────────────────────────────────────────

def handle_message(user_message: str, history: list[dict]) -> dict:
    """
    Run the full support resolution pipeline for one customer message.

    Args:
        user_message: The latest message from the customer.
        history:      Conversation so far as
                      [{"role": "user"|"assistant", "content": str}, ...]

    Returns:
        The validated, guardrail-enforced SupportResponse as a plain dict.
    """
    config = load_config()

    # ── Step 1: Pre-check (guardrails) ────────────────────────────────────────
    # Collect flags (injection, refund_amount, angry) from the raw message.
    # pre_check never hard-blocks — the LLM + post_check handle enforcement.
    flags = pre_check(user_message)

    # ── Step 2: Retrieve relevant policy chunks ───────────────────────────────
    # Combine the last user turn with the current message for richer context.
    last_user_msg = next(
        (m["content"] for m in reversed(history) if m["role"] == "user"), ""
    )
    query  = f"{last_user_msg} {user_message}".strip()
    top_k  = config.get("top_k_results", 3)
    # get_retriever() returns the cached index and auto-rebuilds if files changed
    chunks = get_retriever(_KB_FOLDER).retrieve(query, top_k=top_k)

    # ── Step 3: Build the system prompt ───────────────────────────────────────
    system_prompt = build_system_prompt(config, chunks)

    # ── Step 4: Trim history to the last 6 messages ───────────────────────────
    messages = history[-6:] + [{"role": "user", "content": user_message}]

    # ── Steps 5a–5c: LLM call with retry on validation failure ────────────────
    max_retries: int = config.get("max_retries", 2)
    last_error:  str = ""
    response:    SupportResponse | None = None

    for attempt in range(max_retries + 1):      # attempt 0, 1, …, max_retries
        raw = call_llm(system_prompt, messages)

        try:
            response = parse_and_validate(raw)
            break   # success

        except ValueError as exc:
            last_error = str(exc)

            if attempt < max_retries:
                # Feed the error back using the retry prompt template
                with open(_RETRY_PROMPT_FILE, "r", encoding="utf-8") as f:
                    retry_tpl = f.read()
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": retry_tpl.format(error=last_error),
                })
            # If this was the last attempt, response stays None → fallback below

    if response is None:
        return fallback_response(last_error).model_dump()

    # ── Step 6: Post-check (guardrails) ───────────────────────────────────────
    # Pass the response as a mutable dict alongside the pre-check flags and
    # the live business rules so post_check can enforce all limits.
    biz_rules      = {k: v for k, v in config.items()}   # full merged config
    response_dict  = response.model_dump()
    response_dict  = post_check(response_dict, flags, biz_rules)

    # ── Step 7: Return to Streamlit ───────────────────────────────────────────
    return response_dict
