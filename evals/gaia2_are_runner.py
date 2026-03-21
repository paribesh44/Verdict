from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import httpx


def load_tasks(path: Path) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            tasks.append(json.loads(line))
    return tasks


def _extract_trace_id_from_sse(body: str) -> str | None:
    """Parse SSE body and return traceId from the first event that has it."""
    for line in body.split("\n"):
        if line.startswith("data:"):
            payload = line[5:].strip()
            if not payload:
                continue
            try:
                data = json.loads(payload)
                event = data.get("event") or data.get("envelope") or data
                trace_id = event.get("traceId")
                if trace_id:
                    return trace_id
            except json.JSONDecodeError:
                continue
    return None


def evaluate_task(
    task: Dict[str, Any],
    orchestrator_url: str,
    audit_url: str | None,
) -> Dict[str, Any]:
    payload = {"query": task["query"], "actorId": "are-runner", "intent": "research"}
    with httpx.Client(timeout=45.0) as client:
        response = client.post(f"{orchestrator_url}/v1/research/stream", json=payload)
        response.raise_for_status()
        body = response.text

    success = "TEXT_MESSAGE_CONTENT" in body and "dataModelUpdate" in body
    trace_id = _extract_trace_id_from_sse(body)
    result: Dict[str, Any] = {
        "task_id": task.get("task_id", task.get("query", "")[:50]),
        "success": success,
        "expected": task.get("expected", ""),
        "trace_id": trace_id,
    }

    if audit_url and trace_id:
        ground_truth = task.get("expected") or None
        try:
            with httpx.Client(timeout=30.0) as audit_client:
                audit_resp = audit_client.post(
                    audit_url,
                    json={"traceId": trace_id, "groundTruth": ground_truth},
                )
                audit_resp.raise_for_status()
                audit = audit_resp.json()
                result["faithfulness"] = audit.get("faithfulness", 0.0)
                result["answer_correctness"] = audit.get("answerCorrectness", 0.0)
        except Exception as e:
            result["audit_error"] = str(e)
            result["faithfulness"] = 0.0
            result["answer_correctness"] = 0.0

    return result


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(results)
    passed = len([r for r in results if r.get("success")])
    faithfulness_scores = [r.get("faithfulness") for r in results if r.get("faithfulness") is not None]
    correctness_scores = [r.get("answer_correctness") for r in results if r.get("answer_correctness") is not None]
    avg_faithfulness = sum(faithfulness_scores) / len(faithfulness_scores) if faithfulness_scores else 0.0
    avg_correctness = sum(correctness_scores) / len(correctness_scores) if correctness_scores else 0.0
    f1 = 2 * avg_faithfulness * avg_correctness / (avg_faithfulness + avg_correctness) if (avg_faithfulness + avg_correctness) > 0 else 0.0
    return {
        "total": total,
        "passed": passed,
        "accuracy": (passed / total) if total else 0.0,
        "avg_faithfulness": round(avg_faithfulness, 4),
        "avg_answer_correctness": round(avg_correctness, 4),
        "f1_extraction": round(f1, 4),
    }


def write_report(results: List[Dict[str, Any]], summary: Dict[str, Any], out_path: Path) -> None:
    lines = [
        "# GAIA 2.0 ARE Evaluation Report",
        "",
        "## Summary",
        "",
        f"- **Total tasks**: {summary['total']}",
        f"- **Passed (heuristic)**: {summary['passed']}",
        f"- **Accuracy**: {summary['accuracy']:.2%}",
        f"- **Avg. Faithfulness**: {summary.get('avg_faithfulness', 0):.4f}",
        f"- **Avg. Answer Correctness**: {summary.get('avg_answer_correctness', 0):.4f}",
        f"- **F1 (extraction pipeline)**: {summary.get('f1_extraction', 0):.4f}",
        "",
        "## Per-task breakdown",
        "",
        "| Task ID | Success | Faithfulness | Answer Correctness |",
        "|---------|---------|--------------|-------------------|",
    ]
    for r in results:
        task_id = str(r.get("task_id", ""))[:40]
        succ = "✓" if r.get("success") else "✗"
        fa = r.get("faithfulness", "")
        ac = r.get("answer_correctness", "")
        if isinstance(fa, (int, float)):
            fa = f"{fa:.4f}"
        if isinstance(ac, (int, float)):
            ac = f"{ac:.4f}"
        lines.append(f"| {task_id} | {succ} | {fa} | {ac} |")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="GAIA 2.0 ARE runner adapter")
    parser.add_argument("--tasks", type=Path, required=True, help="Path to GAIA/ARE JSONL tasks")
    parser.add_argument(
        "--orchestrator-url",
        default="http://localhost:8001",
        help="Orchestrator base URL",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Call audit endpoint and include scores in report",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(__file__).parent / "latest_report.md",
        help="Output path for latest_report.md",
    )
    args = parser.parse_args()

    audit_url = f"{args.orchestrator_url}/v1/eval/audit" if args.audit else None
    tasks = load_tasks(args.tasks)
    results = [
        evaluate_task(task, args.orchestrator_url, audit_url)
        for task in tasks
    ]
    summary = summarize(results)
    write_report(results, summary, args.report)
    print(json.dumps({"summary": summary, "results": results}, indent=2))
    print(f"Report written to {args.report}")


if __name__ == "__main__":
    main()
