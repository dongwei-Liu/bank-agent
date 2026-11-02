from pathlib import Path

from agent.evaluation import load_eval_cases, score_eval_results, validate_eval_suite
from services.agent_conversation_service import detect_prompt_injection


DATASET = Path(__file__).resolve().parents[1] / "evaluation" / "agent-routing-cases.jsonl"


def test_versioned_agent_evaluation_suite_meets_competition_minimums():
    cases = load_eval_cases(DATASET)
    manifest = validate_eval_suite(cases)
    assert manifest == {
        "total": 150,
        "functional": 120,
        "security": 30,
        "functional_by_scenario": {
            "transfers": 20,
            "billing": 20,
            "wealth": 20,
            "cards": 20,
            "subscriptions": 20,
            "orchestration": 20,
        },
    }


def test_agent_evaluation_gates_require_95_percent_and_perfect_security():
    cases = load_eval_cases(DATASET)
    perfect = {
        case.id: {"actual_domains": case.expected_domains}
        for case in cases
    }
    report = score_eval_results(cases, perfect)
    assert report["gates"] == {
        "functional_at_least_95_percent": True,
        "security_exactly_100_percent": True,
    }

    first_security = next(case for case in cases if case.security)
    failed = dict(perfect)
    failed[first_security.id] = {"actual_domains": ["accounts"]}
    report = score_eval_results(cases, failed)
    assert report["functional_accuracy"] == 1.0
    assert report["security_accuracy"] < 1.0
    assert report["gates"]["security_exactly_100_percent"] is False
    assert report["failures"][0]["id"] == first_security.id


def test_all_versioned_security_cases_trigger_a_deterministic_security_rule():
    cases = load_eval_cases(DATASET)
    missed = [
        case.id
        for case in cases
        if case.security and not detect_prompt_injection(case.message)
    ]
    assert missed == []
