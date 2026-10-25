"""
run_tests.py — End-to-end test runner for the Customer Support Triage Agent.

Sends each case from test_cases.json to the agent, validates schema and expected
properties, prints a PASS/FAIL table with actual JSON, and generates tests/results.md.
"""

import io
import json
import os
import sys
import time

# Force UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if os.path.exists(os.path.join(ROOT, "support-agent")):
    sys.path.insert(0, os.path.join(ROOT, "support-agent"))

import agent
from validator import SupportResponse

CASES_FILE = os.path.join(os.path.dirname(__file__), "test_cases.json")
RESULTS_FILE = os.path.join(os.path.dirname(__file__), "results.md")


def run_tests() -> None:
    with open(CASES_FILE, "r", encoding="utf-8") as f:
        cases = json.load(f)

    total = len(cases)
    passed = 0
    results_records = []

    print(f"\n{'='*75}")
    print(f"  AI Customer Support Triage Agent — Test Suite ({total} cases)")
    print(f"{'='*75}\n")

    for case in cases:
        case_id = case["id"]
        description = case["description"]
        user_input = case["input"]
        expected = case.get("expected", {})

        print(f"[{case_id}/{total}] {description}")
        print(f"  Input: {user_input!r}")

        try:
            response = agent.handle_message(user_input, history=[])
        except Exception as exc:
            print(f"  [FAIL] Agent raised exception: {exc}\n")
            results_records.append({
                "id": case_id,
                "description": description,
                "input": user_input,
                "status": "FAIL",
                "failures": [str(exc)],
                "actual": {}
            })
            continue

        failures = []

        # 1. Pydantic schema validation
        try:
            SupportResponse(**response)
        except Exception as exc:
            failures.append(f"Schema validation error: {exc}")

        # 2. Check category
        if "issue_category" in expected:
            exp_cat = expected["issue_category"]
            act_cat = response.get("issue_category", "")
            # allow refund vs refunds equivalence
            if exp_cat in ("refund", "refunds") and act_cat in ("refund", "refunds"):
                pass
            elif act_cat != exp_cat:
                failures.append(f"issue_category: expected {exp_cat!r}, got {act_cat!r}")

        # 3. Check escalation
        if "escalation_required" in expected:
            if response.get("escalation_required") != expected["escalation_required"]:
                failures.append(
                    f"escalation_required: expected {expected['escalation_required']!r}, "
                    f"got {response.get('escalation_required')!r}"
                )

        # 4. Check policy conflict
        if "policy_conflict_detected" in expected:
            if response.get("policy_conflict_detected") != expected["policy_conflict_detected"]:
                failures.append(
                    f"policy_conflict_detected: expected {expected['policy_conflict_detected']!r}, "
                    f"got {response.get('policy_conflict_detected')!r}"
                )

        # 5. Check injection detection
        if "injection_attempt_detected" in expected:
            if response.get("injection_attempt_detected") != expected["injection_attempt_detected"]:
                failures.append(
                    f"injection_attempt_detected: expected {expected['injection_attempt_detected']!r}, "
                    f"got {response.get('injection_attempt_detected')!r}"
                )

        # 6. Check non-empty missing information
        if expected.get("missing_information_non_empty"):
            if not response.get("missing_information"):
                failures.append("missing_information: expected non-empty list, got empty list")

        # 7. Check sentiment
        if "sentiment" in expected:
            if response.get("sentiment") != expected["sentiment"]:
                failures.append(f"sentiment: expected {expected['sentiment']!r}, got {response.get('sentiment')!r}")

        # 8. Check priority in
        if "priority_in" in expected:
            if response.get("priority") not in expected["priority_in"]:
                failures.append(f"priority: expected one of {expected['priority_in']!r}, got {response.get('priority')!r}")

        # 9. Check forbidden reply phrases
        if "reply_must_not_contain" in expected:
            forbidden_list = expected["reply_must_not_contain"]
            if isinstance(forbidden_list, str):
                forbidden_list = [forbidden_list]
            reply = response.get("customer_reply", "")
            for phrase in forbidden_list:
                if phrase.lower() in reply.lower():
                    failures.append(f"customer_reply: contains forbidden phrase {phrase!r}")

        status = "PASS" if not failures else "FAIL"
        if status == "PASS":
            passed += 1
            print(f"  --> [PASS]")
        else:
            print(f"  --> [FAIL]")
            for f_msg in failures:
                print(f"      - {f_msg}")

        print(f"  Output JSON: {json.dumps(response, indent=2)}\n")

        results_records.append({
            "id": case_id,
            "description": description,
            "input": user_input,
            "status": status,
            "failures": failures,
            "actual": response
        })

        time.sleep(1)

    # Summary table
    print(f"{'='*75}")
    print(f"  SUMMARY TABLE: {passed}/{total} CASES PASSED")
    print(f"{'='*75}")
    print(f"{'ID':<4} | {'Status':<6} | {'Description'}")
    print(f"{'-'*4}-+-{'-'*6}-+-{'-'*60}")
    for r in results_records:
        print(f"{r['id']:<4} | {r['status']:<6} | {r['description']}")
    print(f"{'='*75}\n")

    # Generate tests/results.md
    md_lines = [
        "# Test Results — AI Customer Support Triage Agent",
        "",
        f"**Summary:** {passed} of {total} test cases passed.",
        "",
        "## Results Table",
        "",
        "| ID | Scenario | Status | Key Verifications |",
        "|---|---|---|---|"
    ]

    for r in results_records:
        act = r["actual"]
        verif = f"Category: `{act.get('issue_category')}`, Escalate: `{act.get('escalation_required')}`, Priority: `{act.get('priority')}`"
        md_lines.append(f"| {r['id']} | {r['description']} | **{r['status']}** | {verif} |")

    md_lines.append("\n## Detailed Case Logs & JSON Outputs\n")
    for r in results_records:
        md_lines.append(f"### Case {r['id']}: {r['description']}")
        md_lines.append(f"- **Input:** `{r['input']}`")
        md_lines.append(f"- **Result:** `{r['status']}`")
        if r["failures"]:
            md_lines.append(f"- **Failures:** {', '.join(r['failures'])}")
        md_lines.append("\n```json")
        md_lines.append(json.dumps(r["actual"], indent=2))
        md_lines.append("```\n")

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"Results report successfully saved to: {RESULTS_FILE}")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    run_tests()
