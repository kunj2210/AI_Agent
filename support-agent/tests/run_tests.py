"""
run_tests.py — End-to-end test runner for the ShopEasy support agent.

Loads tests/test_cases.json, calls agent.handle_message for each case,
validates the output against the Pydantic schema, and checks expected fields.
Prints PASS / FAIL with reasons and a final summary.

Usage (from the support-agent/ root):
    python tests/run_tests.py
"""

import io
import json
import os
import sys
import time

# Force UTF-8 output so emoji don't crash on Windows cp1252 terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Make sure the project root is on sys.path so we can import local modules ──
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import agent                              # noqa: E402  (import after sys.path fix)
from validator import SupportResponse     # noqa: E402

# ── Constants ──────────────────────────────────────────────────────────────────
CASES_FILE   = os.path.join(os.path.dirname(__file__), "test_cases.json")
SLEEP_SECS   = 1          # pause between calls to respect free-tier rate limits
PRIORITY_ORD = ["low", "medium", "high", "urgent"]   # ascending order


# ── Assertion helpers ──────────────────────────────────────────────────────────

def _check(failures: list, label: str, actual, expected) -> None:
    """Append a failure message if actual != expected."""
    if actual != expected:
        failures.append(f"{label}: expected {expected!r}, got {actual!r}")


def _check_priority_min(failures: list, actual_priority: str, min_priority: str) -> None:
    """Fail if actual_priority is below min_priority in the ordering."""
    try:
        actual_idx = PRIORITY_ORD.index(actual_priority)
        min_idx    = PRIORITY_ORD.index(min_priority)
    except ValueError:
        failures.append(f"priority: unknown value '{actual_priority}' or '{min_priority}'")
        return
    if actual_idx < min_idx:
        failures.append(
            f"priority: expected at least {min_priority!r}, got {actual_priority!r}"
        )


def _check_missing_info_contains(failures: list, missing_list: list, keyword: str) -> None:
    """Fail if no item in missing_list contains keyword (case-insensitive)."""
    keyword_lower = keyword.lower()
    found = any(keyword_lower in item.lower() for item in missing_list)
    if not found:
        failures.append(
            f"missing_information: expected an item containing {keyword!r}, "
            f"got {missing_list!r}"
        )


def _check_reply_must_not_contain(failures: list, reply: str, forbidden: str) -> None:
    """Fail if `reply` contains `forbidden` (case-insensitive)."""
    if forbidden.lower() in reply.lower():
        failures.append(
            f"customer_reply: must not contain {forbidden!r} but it does.\n"
            f"  Reply: {reply[:120]!r}"
        )


# ── Schema validation ──────────────────────────────────────────────────────────

def _validate_schema(response: dict) -> list:
    """
    Validate the response dict against the Pydantic SupportResponse model.
    Returns a list of failure messages (empty = valid).
    """
    try:
        SupportResponse(**response)
        return []
    except Exception as exc:
        return [f"Pydantic schema validation failed: {exc}"]


# ── Main runner ────────────────────────────────────────────────────────────────

def run_tests() -> None:
    with open(CASES_FILE, "r", encoding="utf-8") as f:
        cases = json.load(f)

    passed = 0
    total  = len(cases)

    print(f"\n{'='*60}")
    print(f"  ShopEasy Agent — Test Suite ({total} cases)")
    print(f"{'='*60}\n")

    for case in cases:
        case_id     = case["id"]
        description = case["description"]
        user_input  = case["input"]
        expected    = case.get("expected", {})

        print(f"[{case_id}/{total}] {description}")
        print(f"  Input : {user_input!r}")

        # ── Call the agent (fresh history per test case) ───────────────────────
        try:
            response = agent.handle_message(user_input, history=[])
        except Exception as exc:
            print(f"  [FAIL] agent raised an exception: {exc}\n")
            continue

        failures: list[str] = []

        # ── Schema check ───────────────────────────────────────────────────────
        failures.extend(_validate_schema(response))

        # ── Field-level checks ─────────────────────────────────────────────────
        if "issue_category" in expected:
            _check(failures, "issue_category",
                   response.get("issue_category"), expected["issue_category"])

        if "escalation_required" in expected:
            _check(failures, "escalation_required",
                   response.get("escalation_required"), expected["escalation_required"])

        if "priority_min" in expected:
            _check_priority_min(failures,
                                response.get("priority", "low"),
                                expected["priority_min"])

        if "missing_info_contains" in expected:
            _check_missing_info_contains(failures,
                                         response.get("missing_information", []),
                                         expected["missing_info_contains"])

        if "reply_must_not_contain" in expected:
            _check_reply_must_not_contain(failures,
                                          response.get("customer_reply", ""),
                                          expected["reply_must_not_contain"])

        # ── Result ─────────────────────────────────────────────────────────────
        if not failures:
            passed += 1
            print("  [PASS]")
        else:
            print("  [FAIL]")
            for reason in failures:
                print(f"     - {reason}")

        # Print a few key fields for visibility
        print(f"  category={response.get('issue_category')}  "
              f"priority={response.get('priority')}  "
              f"escalate={response.get('escalation_required')}")
        print()

        # Respect free-tier rate limits
        time.sleep(SLEEP_SECS)

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"{'='*60}")
    print(f"  Result: {passed}/{total} passed")
    print(f"{'='*60}\n")

    # Exit with a non-zero code if any test failed (useful in CI pipelines)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    run_tests()
