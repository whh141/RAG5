#!/usr/bin/env python
# coding: utf-8
"""
自主路由实验脚本。

只评估 data/route_labels.jsonl，不运行 QA 和 OOD 评测，避免不同实验互相混杂。
"""

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_all import evaluate_routes  # noqa: E402


OUT_DIR = Path(__file__).resolve().parent
ROUTE_PATH = ROOT / "data" / "route_labels.jsonl"
REPORT_PATH = OUT_DIR / "route_report.json"
SUMMARY_CSV = OUT_DIR / "route_summary_metrics.csv"
CONFUSION_CSV = OUT_DIR / "route_confusion_matrix.csv"
ERROR_CSV = OUT_DIR / "route_error_cases.csv"

INTENTS = ["simple_fact", "complex_reasoning", "time_sensitive", "ood"]


def main() -> None:
    report = evaluate_routes(str(ROUTE_PATH), None)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    details = report["details"]
    total = len(details)
    intent_correct = sum(
        1 for item in details if item.get("expected_intent") == item.get("actual_intent")
    )
    route_correct = sum(
        1 for item in details if item.get("expected_route") == item.get("actual_route")
    )
    success_count = total - report.get("failed", 0)

    write_summary(report, total, intent_correct, route_correct, success_count)
    write_confusion_matrix(details)
    write_error_cases(details)

    print(
        json.dumps(
            {
                "total": total,
                "route_accuracy": report["accuracy"],
                "intent_accuracy": ratio(intent_correct, total),
                "path_accuracy": ratio(route_correct, total),
                "failure_rate": report["failure_rate"],
                "report": str(REPORT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def write_summary(report: dict, total: int, intent_correct: int, route_correct: int, success_count: int) -> None:
    rows = [
        ("route_total", total, "路由评测样本数"),
        ("route_accuracy", report["accuracy"], "意图和路径同时正确的比例"),
        ("intent_accuracy", ratio(intent_correct, total), "仅意图分类正确的比例"),
        ("path_accuracy", ratio(route_correct, total), "仅执行路径选择正确的比例"),
        ("route_failure_rate", report["failure_rate"], "路由节点执行失败比例"),
        ("route_success_rate", ratio(success_count, total), "路由节点成功执行比例"),
    ]
    with SUMMARY_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value", "description"])
        writer.writerows(rows)


def write_confusion_matrix(details: list[dict]) -> None:
    matrix = {expected: {actual: 0 for actual in INTENTS + ["unknown"]} for expected in INTENTS}
    for item in details:
        expected = item.get("expected_intent") or "unknown"
        actual = item.get("actual_intent") or "unknown"
        if expected not in matrix:
            matrix[expected] = {intent: 0 for intent in INTENTS + ["unknown"]}
        if actual not in matrix[expected]:
            matrix[expected][actual] = 0
        matrix[expected][actual] += 1

    columns = INTENTS + ["unknown"]
    with CONFUSION_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["expected_intent", *columns])
        for expected in INTENTS:
            writer.writerow([expected, *[matrix[expected].get(column, 0) for column in columns]])


def write_error_cases(details: list[dict]) -> None:
    with ERROR_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "question",
                "expected_intent",
                "actual_intent",
                "expected_route",
                "actual_route",
                "error_type",
                "error",
            ],
        )
        writer.writeheader()
        for item in details:
            if item.get("ok"):
                continue
            writer.writerow(
                {
                    "id": item.get("id"),
                    "question": item.get("question"),
                    "expected_intent": item.get("expected_intent"),
                    "actual_intent": item.get("actual_intent"),
                    "expected_route": item.get("expected_route"),
                    "actual_route": item.get("actual_route"),
                    "error_type": classify_error(item),
                    "error": item.get("error"),
                }
            )


def classify_error(item: dict) -> str:
    if item.get("error"):
        return "执行异常"
    intent_wrong = item.get("expected_intent") != item.get("actual_intent")
    route_wrong = item.get("expected_route") != item.get("actual_route")
    if intent_wrong and route_wrong:
        return "意图和路径均错误"
    if intent_wrong:
        return "意图错误"
    if route_wrong:
        return "路径错误"
    return "未知"


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


if __name__ == "__main__":
    main()
