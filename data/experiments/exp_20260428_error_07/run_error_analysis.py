#!/usr/bin/env python
# coding: utf-8
"""
统一错误分析实验。
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


OUT_DIR = Path(__file__).resolve().parent
REPORT_PATH = OUT_DIR / "error_analysis_report.json"
CASES_CSV = OUT_DIR / "error_cases.csv"
TYPE_SUMMARY_CSV = OUT_DIR / "error_type_summary.csv"
SOURCE_SUMMARY_CSV = OUT_DIR / "error_source_summary.csv"

E2E_REPORT = ROOT / "data" / "experiments" / "exp_20260428_e2e_01" / "eval_report_full.json"
ROUTE_REPORT = ROOT / "data" / "experiments" / "exp_20260428_route_02" / "route_report.json"
OOD_REPORT = ROOT / "data" / "experiments" / "exp_20260428_ood_05" / "ood_report.json"
COMPLEX_REPORT = ROOT / "data" / "experiments" / "exp_20260428_complex_04" / "complex_reasoning_report.json"
EFFICIENCY_REPORT = ROOT / "data" / "experiments" / "exp_20260428_efficiency_06" / "efficiency_report.json"


def main() -> None:
    cases = []
    cases.extend(collect_e2e_errors())
    cases.extend(collect_route_errors())
    cases.extend(collect_ood_errors())
    cases.extend(collect_complex_errors())
    cases.extend(collect_efficiency_errors())

    type_summary = Counter(case["error_type"] for case in cases)
    source_summary = Counter(case["source_experiment"] for case in cases)

    report = {
        "experiment": "error_analysis",
        "total_error_cases": len(cases),
        "error_type_summary": dict(type_summary),
        "error_source_summary": dict(source_summary),
        "cases": cases,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_cases(cases)
    write_counter(TYPE_SUMMARY_CSV, "error_type", type_summary)
    write_counter(SOURCE_SUMMARY_CSV, "source_experiment", source_summary)

    print(json.dumps({
        "total_error_cases": len(cases),
        "error_type_summary": dict(type_summary),
        "error_source_summary": dict(source_summary),
        "report": str(REPORT_PATH),
    }, ensure_ascii=False, indent=2))


def collect_e2e_errors() -> list[dict]:
    report = load_json(E2E_REPORT)
    cases = []
    for item in report["qa"]["details"]:
        if item.get("error"):
            cases.append(make_case(
                source="e2e_qa",
                item=item,
                error_type="执行异常",
                reason=item.get("error", ""),
            ))
        if not item.get("route_ok"):
            cases.append(make_case(
                source="e2e_qa",
                item=item,
                error_type="QA 路由错误",
                reason=f"expected_route={item.get('expected_route')}, actual_route={item.get('actual_route')}",
            ))
        if not item.get("answer_ok"):
            cases.append(make_case(
                source="e2e_qa",
                item=item,
                error_type="答案未通过",
                reason=f"semantic_similarity={item.get('semantic_similarity')}",
            ))
        if not item.get("citation_ok"):
            cases.append(make_case(
                source="e2e_qa",
                item=item,
                error_type="引用缺失",
                reason="答案未提供引用或引用列表为空",
            ))
    return cases


def collect_route_errors() -> list[dict]:
    report = load_json(ROUTE_REPORT)
    cases = []
    for item in report["details"]:
        if item.get("ok"):
            continue
        if item.get("error"):
            error_type = "路由执行异常"
            reason = item.get("error", "")
        else:
            intent_wrong = item.get("expected_intent") != item.get("actual_intent")
            route_wrong = item.get("expected_route") != item.get("actual_route")
            if intent_wrong and route_wrong:
                error_type = "意图和路径均错误"
            elif intent_wrong:
                error_type = "意图错误"
            else:
                error_type = "路径错误"
            reason = (
                f"expected_intent={item.get('expected_intent')}, actual_intent={item.get('actual_intent')}; "
                f"expected_route={item.get('expected_route')}, actual_route={item.get('actual_route')}"
            )
        cases.append(make_case("route", item, error_type, reason))
    return cases


def collect_ood_errors() -> list[dict]:
    report = load_json(OOD_REPORT)
    cases = []
    for item in report["details"]:
        if item.get("behavior_ok") and not item.get("error"):
            continue
        if item.get("error"):
            error_type = "OOD 执行异常"
            reason = item.get("error", "")
        elif item.get("actual_route") == "retrieve_local":
            error_type = "OOD 误入本地检索"
            reason = "越界问题被路由到 retrieve_local"
        elif item.get("actual_route") not in {"refuse", "retrieve_web"}:
            error_type = "OOD 行为不匹配"
            reason = f"actual_route={item.get('actual_route')}"
        else:
            error_type = "OOD 行为不匹配"
            reason = f"expected_behavior={item.get('expected_behavior')}, actual_route={item.get('actual_route')}"
        cases.append(make_case("ood", item, error_type, reason))
    return cases


def collect_complex_errors() -> list[dict]:
    report = load_json(COMPLEX_REPORT)
    cases = []
    for item in report["details"]:
        if item.get("error"):
            cases.append(make_case("complex_reasoning", item, "复杂推理执行异常", item.get("error", "")))
        if not item.get("answer_ok"):
            cases.append(make_case(
                "complex_reasoning",
                item,
                "复杂问答未通过",
                f"method={item.get('method')}, semantic_similarity={item.get('semantic_similarity')}",
            ))
        if item.get("method") != "direct_rag" and item.get("route_ok") is False:
            cases.append(make_case(
                "complex_reasoning",
                item,
                "复杂问答路由错误",
                f"method={item.get('method')}, expected_route={item.get('expected_route')}, actual_route={item.get('actual_route')}",
            ))
    return cases


def collect_efficiency_errors() -> list[dict]:
    report = load_json(EFFICIENCY_REPORT)
    cases = []
    for item in report["details"]:
        if item.get("error"):
            cases.append(make_case("efficiency", item, "效率实验执行异常", item.get("error", "")))
    return cases


def make_case(source: str, item: dict, error_type: str, reason: str) -> dict:
    return {
        "source_experiment": source,
        "id": item.get("id"),
        "question": item.get("question"),
        "method": item.get("method", ""),
        "expected_intent": item.get("expected_intent", ""),
        "actual_intent": item.get("actual_intent", ""),
        "expected_route": item.get("expected_route", ""),
        "actual_route": item.get("actual_route", ""),
        "error_type": error_type,
        "reason": reason,
        "error": item.get("error", ""),
    }


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_cases(cases: list[dict]) -> None:
    fieldnames = [
        "source_experiment",
        "id",
        "question",
        "method",
        "expected_intent",
        "actual_intent",
        "expected_route",
        "actual_route",
        "error_type",
        "reason",
        "error",
    ]
    with CASES_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cases)


def write_counter(path: Path, key_name: str, counter: Counter) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([key_name, "count"])
        for key, value in counter.most_common():
            writer.writerow([key, value])


if __name__ == "__main__":
    main()
