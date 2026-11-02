"""Run every unique prompt from the demo Markdown through durable Agent conversations.

Raw replies can contain private banking facts, so the JSON output belongs in the
Git-ignored ``.runtime`` directory.  This probe never confirms Actions, submits
OTP codes, or starts the Banking Worker.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend"))

from core.config import get_settings  # noqa: E402


TERMINAL_RUN_STATES = {"SUCCEEDED", "FAILED", "CANCELLED"}


def extract_prompts(document: Path) -> list[dict[str, object]]:
    text = document.read_text(encoding="utf-8")
    section = "未分类"
    fenced = False
    recommended = False
    occurrences: list[dict[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            section = line[3:].strip()
            recommended = False
            continue
        if line.startswith("建议正式演示优先选择"):
            section = "十、推荐主线"
            recommended = True
            continue
        if line == "```":
            fenced = not fenced
            continue
        prompt: str | None = None
        if fenced and line:
            prompt = line
        elif line.startswith("|"):
            inline = re.findall(r"`([^`]+)`", line)
            if inline:
                prompt = inline[0]
        elif recommended and re.match(r"^\d+\.\s", line):
            inline = re.findall(r"`([^`]+)`", line)
            if inline:
                prompt = inline[0]
        if prompt:
            occurrences.append({"section": section, "prompt": prompt})

    unique: dict[str, dict[str, object]] = {}
    for item in occurrences:
        existing = unique.get(item["prompt"])
        if existing is None:
            unique[item["prompt"]] = {
                "prompt": item["prompt"],
                "sections": [item["section"]],
            }
        elif item["section"] not in existing["sections"]:
            existing["sections"].append(item["section"])
    return list(unique.values())


def request_json(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    token: str | None = None,
    idempotency_key: str | None = None,
    payload: dict | None = None,
) -> dict | list:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    response = client.request(method, path, headers=headers, json=payload)
    response.raise_for_status()
    if response.status_code == 204:
        return {}
    return response.json()


def run_prompt(
    client: httpx.Client,
    token: str,
    item: dict[str, object],
    prompt: str,
    timeout_seconds: float,
) -> dict[str, object]:
    started = time.monotonic()
    conversation = request_json(
        client,
        "POST",
        "/api/agent/conversations",
        token=token,
        payload={"title": f"演示逐条验收 {str(item['prompt'])[:24]}"},
    )
    conversation_id = str(conversation["id"])
    result: dict[str, object] = {
        "prompt": prompt,
        "source_prompt": item["prompt"],
        "sections": item["sections"],
        "conversation_id": conversation_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        queued = request_json(
            client,
            "POST",
            f"/api/agent/conversations/{conversation_id}/messages",
            token=token,
            idempotency_key=str(uuid4()),
            payload={"message": prompt},
        )
        run_id = str(queued["id"])
        result["run_id"] = run_id
        while True:
            run = request_json(client, "GET", f"/api/agent/runs/{run_id}", token=token)
            result["run"] = run
            if str(run["status"]) in TERMINAL_RUN_STATES:
                break
            if time.monotonic() - started >= timeout_seconds:
                result["probe_status"] = "TIMEOUT"
                break
            time.sleep(1.0)
        detail = request_json(
            client,
            "GET",
            f"/api/agent/conversations/{conversation_id}",
            token=token,
        )
        result["messages"] = detail.get("messages", [])
        result["events"] = detail.get("events", [])
        if "probe_status" not in result:
            result["probe_status"] = str(result["run"]["status"])
    except httpx.HTTPStatusError as exc:
        result["probe_status"] = "HTTP_ERROR"
        result["http_status"] = exc.response.status_code
        try:
            result["http_error"] = exc.response.json()
        except ValueError:
            result["http_error"] = exc.response.text[:2000]
    except Exception as exc:  # probe must preserve later prompts
        result["probe_status"] = "PROBE_ERROR"
        result["probe_error"] = f"{type(exc).__name__}: {exc}"
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--username", default="alice")
    parser.add_argument("--section", help="Only run prompts whose section contains this text")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    prompts = extract_prompts(args.document)
    if args.section:
        prompts = [
            item for item in prompts
            if any(args.section in str(section) for section in item["sections"])
        ]
    # Test birthday before attack prompts so a security write lock cannot hide
    # unrelated functionality.  All other sections keep document order.
    prompts.sort(key=lambda item: (
        0 if any("生日" in str(section) for section in item["sections"]) else
        2 if any("安全" in str(section) for section in item["sections"]) else 1
    ))

    existing: dict[str, object] = {
        "document": str(args.document),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "results": [],
    }
    if args.resume and args.output.exists():
        existing = json.loads(args.output.read_text(encoding="utf-8"))
    results = list(existing.get("results", []))
    completed = {str(row.get("source_prompt")) for row in results}

    settings = get_settings()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        base_url=args.base_url,
        timeout=httpx.Timeout(30.0),
        trust_env=False,
    ) as client:
        health = request_json(client, "GET", "/api/health")
        tokens = request_json(
            client,
            "POST",
            "/api/auth/login",
            payload={"username": args.username, "password": settings.demo_password},
        )
        token = str(tokens["access_token"])
        accounts = request_json(client, "GET", "/api/accounts", token=token)
        if not accounts:
            raise RuntimeError("The selected user has no account for placeholder replacement")
        account_no = str(accounts[0]["account_no"])
        tail = account_no[-4:]
        existing.update(
            health=health,
            username=args.username,
            prompt_count=len(prompts),
            placeholder_account_tail=tail,
        )
        for index, item in enumerate(prompts, start=1):
            source = str(item["prompt"])
            if source in completed:
                continue
            prompt = source.replace("<真实账户尾号>", tail)
            print(f"[{index}/{len(prompts)}] {prompt}", flush=True)
            result = run_prompt(client, token, item, prompt, args.timeout)
            results.append(result)
            existing["results"] = results
            args.output.write_text(
                json.dumps(existing, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            assistant = [
                row.get("content", "") for row in result.get("messages", [])
                if row.get("role") == "assistant"
            ]
            print(
                f"  status={result['probe_status']} reply={assistant[-1][:240] if assistant else '<none>'}",
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
