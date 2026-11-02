"""Validate or explicitly run the versioned Agent routing evaluation suite."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from agent.evaluation import (  # noqa: E402
    CORE_SCENARIOS,
    dump_json,
    load_eval_cases,
    score_eval_results,
    validate_eval_suite,
)
from agent.router import ENABLED_DOMAINS, route_domains  # noqa: E402
from core.config import get_settings  # noqa: E402


DEFAULT_DATASET = ROOT / "tests" / "evaluation" / "agent-routing-cases.jsonl"
DEFAULT_REPORT = ROOT / ".runtime" / "agent-routing-evaluation.json"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--live", action="store_true", help="调用已配置的真实外部模型")
    parser.add_argument(
        "--confirm-external-model-cost",
        action="store_true",
        help="确认本次评估会产生最多150次外部模型请求及相应费用",
    )
    parser.add_argument("--scenario", choices=CORE_SCENARIOS)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = load_eval_cases(args.dataset)
    manifest = validate_eval_suite(cases)
    print(dump_json({"dataset": str(args.dataset), **manifest}))
    if not args.live:
        print("数据集结构验证通过；未调用外部模型。")
        return 0
    if not args.confirm_external_model_cost:
        raise SystemExit("真实评估必须同时传入 --confirm-external-model-cost")

    settings = get_settings()
    if not settings.siliconflow_api_key or not settings.siliconflow_model:
        raise SystemExit("请先配置 SILICONFLOW_API_KEY 和 SILICONFLOW_MODEL")

    selected = [case for case in cases if not args.scenario or case.scenario == args.scenario]
    if args.limit is not None:
        if args.limit <= 0:
            raise SystemExit("--limit 必须大于 0")
        selected = selected[: args.limit]

    results: dict[str, dict] = {}
    for index, case in enumerate(selected, 1):
        try:
            actual = list(route_domains(case.message, ENABLED_DOMAINS))
            results[case.id] = {"actual_domains": actual}
        except Exception as exc:  # each failure belongs in the evidence report
            results[case.id] = {
                "actual_domains": None,
                "error": type(exc).__name__,
            }
        print(f"[{index}/{len(selected)}] {case.id}")

    score = score_eval_results(selected, results)
    full_run = len(selected) == len(cases)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": settings.siliconflow_model,
        "base_url": settings.siliconflow_base_url,
        "dataset": str(args.dataset),
        "full_run": full_run,
        "score": score,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(dump_json(score))
    print(f"报告：{args.output}")
    if full_run and not all(score["gates"].values()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
