from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.agent_service import deepseek_json_extract, fetch_public_source, flatten_proposed_fields


DEFAULT_SAMPLES = Path(__file__).with_name("agent_real_samples.json")
DEFAULT_RESULTS = Path(__file__).with_name("results")


def load_local_agent_env() -> None:
    env_path = ROOT / "backend" / "data" / "agent.env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def normalized_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", text)


def values_for_path(proposal: dict[str, Any], path: str) -> list[Any]:
    if path.startswith("media."):
        return [(proposal.get("media") or {}).get(path.split(".", 1)[1])]
    if path == "contacts.email":
        return [item.get("email") for item in proposal.get("contacts") or []]
    if path == "contacts.phone":
        return [item.get("phone") for item in proposal.get("contacts") or []]
    return []


def value_matches(actual_values: list[Any], expected_values: list[Any]) -> bool:
    for actual in actual_values:
        if actual in (None, "", []):
            continue
        for expected in expected_values:
            if isinstance(expected, (int, float)):
                try:
                    actual_number = float(actual)
                except (TypeError, ValueError):
                    continue
                tolerance = max(1.0, abs(float(expected)) * 0.05)
                if abs(actual_number - float(expected)) <= tolerance:
                    return True
                continue
            actual_text = normalized_text(actual)
            expected_text = normalized_text(expected)
            if expected_text and (expected_text in actual_text or actual_text in expected_text):
                return True
    return False


def score_proposal(proposal: dict[str, Any], expected: dict[str, list[Any]]) -> dict[str, Any]:
    checks = []
    for path, expected_values in expected.items():
        actual_values = values_for_path(proposal, path)
        checks.append({
            "field": path,
            "expected": expected_values,
            "actual": actual_values,
            "matched": value_matches(actual_values, expected_values),
        })
    evidence = proposal.get("evidence") or {}
    proposed = flatten_proposed_fields(proposal.get("media") or {}, proposal.get("contacts") or [])
    unsupported = [path for path, value in proposed.items() if value not in (None, "", []) and path not in evidence]
    matched = sum(1 for item in checks if item["matched"])
    return {
        "matched": matched,
        "total": len(checks),
        "accuracy": round(matched / len(checks), 3) if checks else 0,
        "checks": checks,
        "unsupported_proposed_fields": unsupported,
    }


def run_sample(sample: dict[str, Any], fetch_only: bool) -> dict[str, Any]:
    started = datetime.now()
    result: dict[str, Any] = {
        "id": sample["id"],
        "source_label": sample["source_label"],
        "url": sample["url"],
        "status": "fetching",
    }
    try:
        content, final_url = fetch_public_source(sample["url"])
        result.update({"status": "fetched", "final_url": final_url, "source_chars": len(content)})
        if not fetch_only:
            # Use the final public URL as the model-visible label so fixture names do not leak the answer.
            proposal, usage = deepseek_json_extract(content, final_url)
            result.update({
                "status": "completed",
                "proposal": proposal,
                "usage": usage,
                "score": score_proposal(proposal, sample["expected"]),
            })
    except Exception as exc:  # Keep the remaining public samples running.
        result.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}"})
    result["elapsed_seconds"] = round((datetime.now() - started).total_seconds(), 2)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a non-writing real-source evaluation for Pangdun Agent.")
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLES)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--id", action="append", dest="sample_ids", help="Run only the selected sample id; repeatable.")
    parser.add_argument("--fetch-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    load_local_agent_env()
    samples = json.loads(args.samples.read_text(encoding="utf-8"))
    if args.sample_ids:
        selected_ids = set(args.sample_ids)
        samples = [sample for sample in samples if sample["id"] in selected_ids]
    if args.limit:
        samples = samples[: args.limit]
    results = []
    for index, sample in enumerate(samples, start=1):
        print(f"[{index}/{len(samples)}] {sample['id']} ...", flush=True)
        result = run_sample(sample, args.fetch_only)
        results.append(result)
        if result["status"] == "completed":
            score = result["score"]
            print(f"  completed: {score['matched']}/{score['total']} ({score['accuracy']:.0%})", flush=True)
        elif result["status"] == "fetched":
            print(f"  fetched: {result['source_chars']} chars", flush=True)
        else:
            print(f"  failed: {result['error']}", flush=True)
    completed = [item for item in results if item["status"] == "completed"]
    expected_by_id = {sample["id"]: sample["expected"] for sample in samples}
    total_checks = sum(len(expected_by_id[item["id"]]) for item in results)
    total_matched = sum(item["score"]["matched"] for item in completed)
    usage = {
        key: sum(int((item.get("usage") or {}).get(key) or 0) for item in completed)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        "fetch_only": args.fetch_only,
        "sample_count": len(samples),
        "completed_count": len(completed),
        "failed_count": sum(1 for item in results if item["status"] == "failed"),
        "matched_checks": total_matched,
        "total_checks": total_checks,
        "overall_accuracy": round(total_matched / total_checks, 3) if total_checks else None,
        "perfect_sample_count": sum(1 for item in completed if item["score"]["matched"] == item["score"]["total"]),
        "unsupported_proposed_field_count": sum(len(item["score"]["unsupported_proposed_fields"]) for item in completed),
        "usage": usage,
        "results": results,
    }
    output = args.output
    if output is None:
        DEFAULT_RESULTS.mkdir(parents=True, exist_ok=True)
        output = DEFAULT_RESULTS / f"agent-real-{datetime.now():%Y%m%d-%H%M%S}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report: {output}")
    if not args.fetch_only:
        print(f"overall: {total_matched}/{total_checks} ({(report['overall_accuracy'] or 0):.0%})")
    return 0 if report["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
