#!/usr/bin/env python
# coding: utf-8
"""
OOD 越界拒答实验。
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_all import evaluate_ood, initialize_runtime  # noqa: E402


OUT_DIR = Path(__file__).resolve().parent
OOD_PATH = ROOT / "data" / "ood_questions.jsonl"
REPORT_PATH = OUT_DIR / "ood_report.json"
SUMMARY_CSV = OUT_DIR / "ood_summary_metrics.csv"
DETAILS_CSV = OUT_DIR / "ood_case_details.csv"
ERROR_CSV = OUT_DIR / "ood_error_cases.csv"


def main() -> None:
    runtime = initialize_runtime()
    report = evaluate_ood(runtime["graph"], str(OOD_PATH), None)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    write_summary(report)
    write_details(report["details"])
    write_errors(report["details"])

    route_counts = Counter(item.get("actual_route") or "unknown" for item in report["details"])
    print(
        json.dumps(
            {
                "total": report["total"],
                "refuse_accuracy": report["refuse_accuracy"],
                "behavior_match_rate": report["behavior_match_rate"],
                "failure_rate": report["failure_rate"],
                "route_counts": route_counts,
                "report": str(REPORT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def write_summary(report: dict) -> None:
    details = report["details"]
    route_counts = Counter(item.get("actual_route") or "unknown" for item in details)
    rows = [
        ("ood_total", report["total"], "OOD 评测样本数"),
        ("strict_refuse_accuracy", report["strict_refuse_accuracy"], "actual_route == refuse 的比例"),
        ("behavior_match_rate", report["behavior_match_rate"], "符合 expected_behavior 的比例"),
        ("ood_failure_rate", report["failure_rate"], "OOD 链路执行失败比例"),
        ("ood_success_rate", ratio(report["total"] - report["failed"], report["total"]), "OOD 链路成功执行比例"),
        ("route_refuse_count", route_counts.get("refuse", 0), "实际拒答样本数"),
        ("route_retrieve_web_count", route_counts.get("retrieve_web", 0), "实际进入时效检索样本数"),
        ("route_retrieve_local_count", route_counts.get("retrieve_local", 0), "实际误入本地检索样本数"),
        ("route_unknown_count", route_counts.get("unknown", 0), "无实际路由样本数"),
    ]
    with SUMMARY_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value", "description"])
        writer.writerows(rows)


def write_details(details: list[dict]) -> None:
    fieldnames = [
        "id",
        "question",
        "expected_behavior",
        "actual_intent",
        "actual_route",
        "ok",
        "behavior_ok",
        "answer",
        "error",
    ]
    with DETAILS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in details:
            writer.writerow({field: item.get(field) for field in fieldnames})


def write_errors(details: list[dict]) -> None:
    fieldnames = [
        "id",
        "question",
        "expected_behavior",
        "actual_intent",
        "actual_route",
        "error_type",
        "error",
    ]
    with ERROR_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in details:
            if item.get("behavior_ok") and not item.get("error"):
                continue
            writer.writerow(
                {
                    "id": item.get("id"),
                    "question": item.get("question"),
                    "expected_behavior": item.get("expected_behavior"),
                    "actual_intent": item.get("actual_intent"),
                    "actual_route": item.get("actual_route"),
                    "error_type": classify_error(item),
                    "error": item.get("error"),
                }
            )


def classify_error(item: dict) -> str:
    if item.get("error"):
        return "执行异常"
    route = item.get("actual_route")
    expected = item.get("expected_behavior")
    if route == "retrieve_local":
        return "OOD 误入本地检索"
    if expected == "reject_or_web" and route not in {"refuse", "retrieve_web"}:
        return "未按期望拒答或联网"
    if route is None:
        return "无实际路由"
    return "行为不匹配"


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


if __name__ == "__main__":
    main()
