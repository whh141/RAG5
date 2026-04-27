#!/usr/bin/env python
# coding: utf-8
"""
统一评测入口。
评测重点：路由准确率、问答语义相似度、引用覆盖、OOD 拒答。
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable

from sklearn.metrics import auc, precision_recall_curve, roc_curve

from config import LLM_BACKEND
from faiss_retriever import FaissRetriever
from bm25_retriever import BM25
from rerank_model import reRankLLM
from llm_model import get_llm_model
from pdf_parse import load_knowledge_documents
from scoring_model import get_scoring_model

from agent.config.model_config import ModelConfig
from agent.graph import build_agent_graph
from agent.nodes.intent_classifier import intent_classify_node
from agent.nodes.tool_executor import set_tools
from agent.state import AgentState
from agent.tools import RAGTool, TavilyTool


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", default="data/eval_report.json")
    parser.add_argument("--qa-limit", type=int, default=None)
    parser.add_argument("--route-limit", type=int, default=None)
    parser.add_argument("--ood-limit", type=int, default=None)
    parser.add_argument("--similarity-threshold", type=float, default=0.72)
    parser.add_argument("--qa-dev-path", default=None)
    parser.add_argument("--auto-threshold", action="store_true")
    parser.add_argument("--threshold-grid-start", type=float, default=0.50)
    parser.add_argument("--threshold-grid-stop", type=float, default=0.95)
    parser.add_argument("--threshold-grid-step", type=float, default=0.01)
    args = parser.parse_args()

    _validate_runtime_requirements("data/eval_qa.jsonl", args.qa_limit)
    runtime = initialize_runtime()
    scorer = get_scoring_model()
    calibration_report = None

    if args.auto_threshold:
        if not args.qa_dev_path:
            raise ValueError("启用 --auto-threshold 时必须提供 --qa-dev-path")
        calibration_report = calibrate_similarity_threshold(
            runtime["graph"],
            scorer,
            args.qa_dev_path,
            args.threshold_grid_start,
            args.threshold_grid_stop,
            args.threshold_grid_step,
        )
        args.similarity_threshold = calibration_report["best_threshold"]

    route_report = evaluate_routes("data/route_labels.jsonl", args.route_limit)
    qa_report = evaluate_qa(
        runtime["graph"],
        scorer,
        "data/eval_qa.jsonl",
        args.qa_limit,
        args.similarity_threshold,
    )
    ood_report = evaluate_ood(runtime["graph"], "data/ood_questions.jsonl", args.ood_limit)

    report = {
        "route": route_report,
        "qa": qa_report,
        "ood": ood_report,
    }
    if calibration_report:
        report["qa_threshold_calibration"] = calibration_report

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(_summary(report), ensure_ascii=False, indent=2))
    print(f"评测报告已保存: {output_path}")


def initialize_runtime() -> Dict[str, Any]:
    base = "."
    documents = load_knowledge_documents(
        kb_dir=f"{base}/data/kb_docs",
        faq_path=f"{base}/data/faq_database.json",
    )

    faiss_retriever = FaissRetriever(documents=documents)
    bm25_retriever = BM25(documents)
    llm = get_llm_model(model_path=f"{base}/pre_train_model/Qwen-7B-Chat", backend=LLM_BACKEND)
    rerank = reRankLLM()

    rag_tool = RAGTool(
        faiss_retriever=faiss_retriever,
        bm25_retriever=bm25_retriever,
        rerank_model=rerank,
        llm=llm,
    )
    tavily_tool = TavilyTool(max_results=5) if ModelConfig.TAVILY_API_KEY else None
    set_tools(rag_tool, tavily_tool)

    return {"graph": build_agent_graph()}


def evaluate_routes(path: str, limit: int | None) -> Dict[str, Any]:
    rows = list(_read_jsonl(path, limit))
    results = []
    correct = 0
    failed = 0
    failure_reasons: dict[str, int] = {}

    for row in rows:
        try:
            state = _initial_state(row["question"])
            result = intent_classify_node(state)
            ok = result["intent"] == row["intent"] and result["route"] == row["expected_route"]
            correct += int(ok)
            results.append(
                {
                    "id": row.get("id"),
                    "question": row["question"],
                    "expected_intent": row["intent"],
                    "actual_intent": result["intent"],
                    "expected_route": row["expected_route"],
                    "actual_route": result["route"],
                    "ok": ok,
                    "error": None,
                }
            )
        except Exception as exc:
            failed += 1
            failure_type = _categorize_error(exc)
            failure_reasons[failure_type] = failure_reasons.get(failure_type, 0) + 1
            results.append(
                {
                    "id": row.get("id"),
                    "question": row["question"],
                    "expected_intent": row["intent"],
                    "actual_intent": None,
                    "expected_route": row["expected_route"],
                    "actual_route": None,
                    "ok": False,
                    "failure_type": failure_type,
                    "error": str(exc),
                }
            )

    return {
        "total": len(rows),
        "correct": correct,
        "failed": failed,
        "accuracy": _ratio(correct, len(rows)),
        "failure_rate": _ratio(failed, len(rows)),
        "failure_reasons": failure_reasons,
        "details": results,
    }


def evaluate_qa(graph, scorer, path: str, limit: int | None, similarity_threshold: float) -> Dict[str, Any]:
    rows = list(_read_jsonl(path, limit))
    results = []
    route_correct = 0
    citation_correct = 0
    answer_passed = 0
    failed = 0
    similarity_scores: list[float] = []
    failure_reasons: dict[str, int] = {}

    for row in rows:
        try:
            result = graph.invoke(_initial_state(row["question"]))
            answer = result["final_answer"]
            answer_body = _extract_answer_body(result)
            similarity = scorer.calc_semantic_similarity(answer_body, row["ground_truth"])
            similarity = float(similarity)
            has_citation = len(result.get("citations", [])) > 0 or result.get("route") == "refuse"
            route_ok = result.get("route") == row.get("expected_route")
            answer_ok = similarity >= similarity_threshold

            route_correct += int(route_ok)
            citation_correct += int(has_citation)
            answer_passed += int(answer_ok)
            similarity_scores.append(similarity)

            results.append(
                {
                    "id": row.get("id"),
                    "question": row["question"],
                    "expected_route": row.get("expected_route"),
                    "actual_route": result.get("route"),
                    "answer": answer,
                    "answer_body": answer_body,
                    "ground_truth": row["ground_truth"],
                    "semantic_similarity": similarity,
                    "answer_ok": answer_ok,
                    "citations": result.get("citations", []),
                    "route_ok": route_ok,
                    "citation_ok": has_citation,
                    "trace": result.get("trace", []),
                    "error": None,
                }
            )
        except Exception as exc:
            failed += 1
            failure_type = _categorize_error(exc)
            failure_reasons[failure_type] = failure_reasons.get(failure_type, 0) + 1
            results.append(
                {
                    "id": row.get("id"),
                    "question": row["question"],
                    "expected_route": row.get("expected_route"),
                    "actual_route": None,
                    "answer": None,
                    "answer_body": None,
                    "ground_truth": row["ground_truth"],
                    "semantic_similarity": None,
                    "answer_ok": False,
                    "citations": [],
                    "route_ok": False,
                    "citation_ok": False,
                    "trace": [],
                    "failure_type": failure_type,
                    "error": str(exc),
                }
            )

    return {
        "total": len(rows),
        "failed": failed,
        "route_accuracy": _ratio(route_correct, len(rows)),
        "citation_rate": _ratio(citation_correct, len(rows)),
        "citation_presence_rate": _ratio(citation_correct, len(rows)),
        "answer_pass_rate": _ratio(answer_passed, len(rows)),
        "failure_rate": _ratio(failed, len(rows)),
        "similarity_threshold": similarity_threshold,
        "successful_eval_count": len(similarity_scores),
        "avg_semantic_similarity": (
            sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0.0
        ),
        "avg_semantic_similarity_on_success": (
            sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0.0
        ),
        "failure_reasons": failure_reasons,
        "metric_definitions": {
            "citation_rate": "当前实现统计的是引用存在率，而非引用正确率。",
            "avg_semantic_similarity": "仅在成功执行并完成相似度计算的样本上统计。",
        },
        "details": results,
    }


def evaluate_ood(graph, path: str, limit: int | None) -> Dict[str, Any]:
    rows = list(_read_jsonl(path, limit))
    results = []
    refused = 0
    behavior_matched = 0
    failed = 0
    failure_reasons: dict[str, int] = {}

    for row in rows:
        try:
            result = graph.invoke(_initial_state(row["question"]))
            ok = result.get("route") == "refuse"
            expected_behavior = row.get("expected_behavior")
            behavior_ok = _match_ood_behavior(result.get("route"), expected_behavior)
            refused += int(ok)
            behavior_matched += int(behavior_ok)
            results.append(
                {
                    "id": row.get("id"),
                    "question": row["question"],
                    "expected_behavior": expected_behavior,
                    "actual_intent": result.get("intent"),
                    "actual_route": result.get("route"),
                    "answer": result.get("final_answer"),
                    "ok": ok,
                    "behavior_ok": behavior_ok,
                    "error": None,
                }
            )
        except Exception as exc:
            failed += 1
            failure_type = _categorize_error(exc)
            failure_reasons[failure_type] = failure_reasons.get(failure_type, 0) + 1
            results.append(
                {
                    "id": row.get("id"),
                    "question": row["question"],
                    "expected_behavior": row.get("expected_behavior"),
                    "actual_intent": None,
                    "actual_route": None,
                    "answer": None,
                    "ok": False,
                    "behavior_ok": False,
                    "failure_type": failure_type,
                    "error": str(exc),
                }
            )

    return {
        "total": len(rows),
        "failed": failed,
        "refuse_accuracy": _ratio(refused, len(rows)),
        "strict_refuse_accuracy": _ratio(refused, len(rows)),
        "behavior_match_rate": _ratio(behavior_matched, len(rows)),
        "failure_rate": _ratio(failed, len(rows)),
        "failure_reasons": failure_reasons,
        "metric_definitions": {
            "strict_refuse_accuracy": "仅当 route == refuse 时记为成功。",
            "behavior_match_rate": "若数据集提供 expected_behavior，则按样本期望行为做宽口径匹配。",
        },
        "details": results,
    }


def _initial_state(question: str) -> AgentState:
    return {
        "user_question": question,
        "conversation_history": [],
        "sub_questions": [],
        "is_composite": False,
        "intent": "",
        "route": "",
        "route_reason": "",
        "query_rewrite": "",
        "plan": [],
        "rag_result": {},
        "tavily_result": None,
        "evidence_items": [],
        "citations": [],
        "draft_answer": "",
        "reasoning_steps": [],
        "reflection_count": 0,
        "quality_score": 0.0,
        "reflection_notes": [],
        "improvement_actions": [],
        "final_answer": "",
        "answer_source": "",
        "confidence": 0.0,
        "need_human": False,
        "metadata": {},
        "trace": [],
        "sub_results": [],
    }


def _read_jsonl(path: str, limit: int | None) -> Iterable[dict]:
    count = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            yield json.loads(line)
            count += 1
            if limit is not None and count >= limit:
                break


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _summary(report: Dict[str, Any]) -> Dict[str, Any]:
    summary = {
        "route_accuracy": report["route"]["accuracy"],
        "route_failure_rate": report["route"]["failure_rate"],
        "qa_route_accuracy": report["qa"]["route_accuracy"],
        "qa_citation_rate": report["qa"]["citation_rate"],
        "qa_answer_pass_rate": report["qa"]["answer_pass_rate"],
        "qa_failure_rate": report["qa"]["failure_rate"],
        "qa_avg_semantic_similarity": round(report["qa"]["avg_semantic_similarity"], 4),
        "ood_refuse_accuracy": report["ood"]["refuse_accuracy"],
        "ood_failure_rate": report["ood"]["failure_rate"],
    }
    if "qa_threshold_calibration" in report:
        summary["qa_calibrated_threshold"] = report["qa_threshold_calibration"]["best_threshold"]
    return summary


def _extract_answer_body(result: Dict[str, Any]) -> str:
    draft_answer = str(result.get("draft_answer", "")).strip()
    if draft_answer:
        return draft_answer

    final_answer = str(result.get("final_answer", "")).strip()
    if not final_answer:
        return ""

    marker = "\n\n参考来源："
    if marker in final_answer:
        return final_answer.split(marker, 1)[0].strip()
    return final_answer


def _categorize_error(exc: Exception) -> str:
    message = str(exc).lower()
    if "tavily" in message or "api key" in message or "联网搜索工具未初始化" in str(exc):
        return "config"
    if "similarity" in message or "score" in message or "embedding" in message:
        return "metric"
    if "intent" in message or "route" in message or "路由" in str(exc):
        return "routing"
    if any(token in str(exc) for token in ("检索", "证据", "引用", "重排序", "召回", "推理链")):
        return "execution"
    return "runtime"


def _validate_runtime_requirements(qa_path: str, qa_limit: int | None) -> None:
    rows = list(_read_jsonl(qa_path, qa_limit))
    qa_requires_web = any(row.get("expected_route") == "retrieve_web" for row in rows)
    if qa_requires_web and not ModelConfig.TAVILY_API_KEY:
        raise ValueError(
            "QA 评测集中包含 time_sensitive / retrieve_web 样本，但当前未配置 TAVILY_API_KEY。"
        )


def _match_ood_behavior(route: str | None, expected_behavior: str | None) -> bool:
    route = route or ""
    expected_behavior = expected_behavior or ""
    if expected_behavior == "reject_or_web":
        return route in {"refuse", "retrieve_web"}
    return route == "refuse"


def calibrate_similarity_threshold(
    graph,
    scorer,
    path: str,
    grid_start: float,
    grid_stop: float,
    grid_step: float,
) -> Dict[str, Any]:
    rows = list(_read_jsonl(path, None))
    if len(rows) < 2:
        raise ValueError("阈值校准至少需要 2 条开发集样本")
    if grid_step <= 0:
        raise ValueError("threshold grid step 必须大于 0")
    if grid_start >= grid_stop:
        raise ValueError("threshold grid start 必须小于 stop")

    scores: list[float] = []
    labels: list[int] = []
    answers: list[str] = []
    ground_truths: list[str] = []

    for row in rows:
        result = graph.invoke(_initial_state(row["question"]))
        answer_body = _extract_answer_body(result)
        answers.append(answer_body)
        ground_truths.append(str(row["ground_truth"]))

    for idx, answer_body in enumerate(answers):
        positive_score = float(scorer.calc_semantic_similarity(answer_body, ground_truths[idx]))
        scores.append(positive_score)
        labels.append(1)

        negative_ground_truth = ground_truths[(idx + 1) % len(ground_truths)]
        negative_score = float(scorer.calc_semantic_similarity(answer_body, negative_ground_truth))
        scores.append(negative_score)
        labels.append(0)

    thresholds = []
    current = grid_start
    while current <= grid_stop + 1e-9:
        thresholds.append(round(current, 6))
        current += grid_step

    search_results = []
    best = None
    for threshold in thresholds:
        tp = fp = fn = tn = 0
        for score, label in zip(scores, labels):
            predicted = 1 if score >= threshold else 0
            if predicted == 1 and label == 1:
                tp += 1
            elif predicted == 1 and label == 0:
                fp += 1
            elif predicted == 0 and label == 1:
                fn += 1
            else:
                tn += 1

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        item = {
            "threshold": threshold,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
        }
        search_results.append(item)
        if best is None or item["f1"] > best["f1"] or (
            item["f1"] == best["f1"] and item["threshold"] > best["threshold"]
        ):
            best = item

    fpr, tpr, roc_thresholds = roc_curve(labels, scores)
    precision_curve, recall_curve, pr_thresholds = precision_recall_curve(labels, scores)

    return {
        "method": "contrastive_dev_pairs",
        "dev_path": path,
        "best_threshold": best["threshold"],
        "best_f1": best["f1"],
        "threshold_search": search_results,
        "roc_auc": round(float(auc(fpr, tpr)), 6),
        "pr_auc": round(float(auc(recall_curve, precision_curve)), 6),
        "roc_curve": {
            "fpr": [round(float(x), 6) for x in fpr],
            "tpr": [round(float(x), 6) for x in tpr],
            "thresholds": [round(float(x), 6) for x in roc_thresholds],
        },
        "pr_curve": {
            "precision": [round(float(x), 6) for x in precision_curve],
            "recall": [round(float(x), 6) for x in recall_curve],
            "thresholds": [round(float(x), 6) for x in pr_thresholds],
        },
    }


if __name__ == "__main__":
    main()
