#!/usr/bin/env python
# coding: utf-8
"""
复杂推理能力实验。
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.config.model_config import ModelConfig  # noqa: E402
from agent.graph import build_agent_graph  # noqa: E402
from agent.nodes.finalizer import finalize_answer_node  # noqa: E402
from agent.nodes.intent_classifier import intent_classify_node  # noqa: E402
from agent.nodes.planner import planning_node  # noqa: E402
from agent.nodes.question_decomposer import question_decompose_node, route_after_decompose  # noqa: E402
from agent.nodes.synthesizer import synthesize_answer_node  # noqa: E402
from agent.nodes.tool_executor import composite_execution_node, set_tools, tool_execution_node  # noqa: E402
from agent.state import AgentState  # noqa: E402
from agent.tools import RAGTool, TavilyTool  # noqa: E402
from bm25_retriever import BM25  # noqa: E402
from config import LLM_BACKEND  # noqa: E402
from eval_all import _extract_answer_body, _initial_state  # noqa: E402
from faiss_retriever import FaissRetriever  # noqa: E402
from llm_model import get_llm_model  # noqa: E402
from pdf_parse import load_knowledge_documents  # noqa: E402
from rerank_model import reRankLLM  # noqa: E402
from scoring_model import get_scoring_model  # noqa: E402


OUT_DIR = Path(__file__).resolve().parent
QA_PATH = ROOT / "data" / "eval_qa.jsonl"
REPORT_PATH = OUT_DIR / "complex_reasoning_report.json"
SUMMARY_CSV = OUT_DIR / "complex_summary_metrics.csv"
DETAILS_CSV = OUT_DIR / "complex_case_details.csv"

METHODS = ["direct_rag", "agent_no_reflection", "full_agent"]
SIMILARITY_THRESHOLD = 0.72


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=15)
    args = parser.parse_args()

    rows = load_complex_rows(args.limit)
    print(f"[Complex] samples: {len(rows)}")

    runtime = initialize_runtime()
    scorer = get_scoring_model()

    details = []
    for row_index, row in enumerate(rows, start=1):
        print(f"[Complex] sample {row_index}/{len(rows)} {row['id']}")
        for method in METHODS:
            print(f"[Complex] method={method}")
            details.append(evaluate_one(row, method, runtime, scorer))

    summary = summarize(details)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "experiment": "complex_reasoning",
                "sample_count": len(rows),
                "methods": METHODS,
                "similarity_threshold": SIMILARITY_THRESHOLD,
                "summary": summary,
                "details": details,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_summary(summary)
    write_details(details)

    print(json.dumps({"report": str(REPORT_PATH), "summary": summary}, ensure_ascii=False, indent=2))


def initialize_runtime() -> dict[str, Any]:
    documents = load_knowledge_documents(
        kb_dir=str(ROOT / "data" / "kb_docs"),
        faq_path=str(ROOT / "data" / "faq_database.json"),
    )
    faiss_retriever = FaissRetriever(documents=documents)
    bm25_retriever = BM25(documents)
    llm = get_llm_model(model_path=str(ROOT / "pre_train_model" / "Qwen-7B-Chat"), backend=LLM_BACKEND)
    rerank = reRankLLM()
    rag_tool = RAGTool(
        faiss_retriever=faiss_retriever,
        bm25_retriever=bm25_retriever,
        rerank_model=rerank,
        llm=llm,
    )
    tavily_tool = TavilyTool(max_results=5) if ModelConfig.TAVILY_API_KEY else None
    set_tools(rag_tool, tavily_tool)
    return {
        "rag_tool": rag_tool,
        "graph": build_agent_graph(),
    }


def load_complex_rows(limit: int | None) -> list[dict]:
    rows = []
    with QA_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("intent_label") == "complex_reasoning" and row.get("expected_route") == "retrieve_local":
                rows.append(row)
                if limit is not None and len(rows) >= limit:
                    break
    return rows


def evaluate_one(row: dict, method: str, runtime: dict[str, Any], scorer) -> dict:
    try:
        if method == "direct_rag":
            result = run_direct_rag(row, runtime["rag_tool"])
        elif method == "agent_no_reflection":
            result = run_agent_without_reflection(row)
        elif method == "full_agent":
            result = runtime["graph"].invoke(_initial_state(row["question"]))
        else:
            raise ValueError(f"unknown method: {method}")

        answer_body = _extract_answer_body(result)
        similarity = float(scorer.calc_semantic_similarity(answer_body, row["ground_truth"]))
        citations = result.get("citations", []) or []
        reasoning_steps = result.get("reasoning_steps", []) or []
        trace = result.get("trace", []) or []
        return {
            "id": row["id"],
            "question": row["question"],
            "ground_truth": row["ground_truth"],
            "method": method,
            "expected_route": row.get("expected_route"),
            "actual_route": result.get("route"),
            "answer": result.get("final_answer") or result.get("draft_answer") or "",
            "answer_body": answer_body,
            "semantic_similarity": round(similarity, 6),
            "answer_ok": similarity >= SIMILARITY_THRESHOLD,
            "citation_count": len(citations),
            "citation_ok": len(citations) > 0,
            "reasoning_step_count": len(reasoning_steps),
            "reasoning_chain_ok": len(reasoning_steps) > 0,
            "reflection_count": int(result.get("reflection_count", 0) or 0),
            "route_ok": result.get("route") == row.get("expected_route") if result.get("route") else None,
            "sub_question_count": len(result.get("sub_questions", []) or []),
            "trace_stage_count": len(trace),
            "error": None,
        }
    except Exception as exc:
        return {
            "id": row["id"],
            "question": row["question"],
            "ground_truth": row["ground_truth"],
            "method": method,
            "expected_route": row.get("expected_route"),
            "actual_route": None,
            "answer": "",
            "answer_body": "",
            "semantic_similarity": None,
            "answer_ok": False,
            "citation_count": 0,
            "citation_ok": False,
            "reasoning_step_count": 0,
            "reasoning_chain_ok": False,
            "reflection_count": 0,
            "route_ok": False if method != "direct_rag" else None,
            "sub_question_count": 0,
            "trace_stage_count": 0,
            "error": str(exc),
        }


def run_direct_rag(row: dict, rag_tool) -> AgentState:
    rag_result = rag_tool.answer(query=row["question"], intent="complex_reasoning")
    state = _initial_state(row["question"])
    state["intent"] = "complex_reasoning"
    state["route"] = "retrieve_local"
    state["query_rewrite"] = row["question"]
    state["rag_result"] = rag_result
    state["evidence_items"] = rag_result.get("evidence_items", [])
    state["citations"] = rag_result.get("citations", [])
    state["draft_answer"] = rag_result.get("answer", "")
    state["final_answer"] = rag_result.get("answer", "")
    state["reasoning_steps"] = rag_result.get("reasoning_steps", []) or []
    state["answer_source"] = "local_rag"
    state["confidence"] = rag_result.get("confidence", 0.0)
    state["trace"] = [
        {
            "stage": "direct_rag",
            "retrieved_count": rag_result.get("retrieved_count"),
            "reranked_count": rag_result.get("reranked_count"),
            "evidence_count": len(state["evidence_items"]),
            "reasoning_step_count": len(state["reasoning_steps"]),
        }
    ]
    return state


def run_agent_without_reflection(row: dict) -> AgentState:
    state = _initial_state(row["question"])
    state = question_decompose_node(state)
    next_node = route_after_decompose(state)
    if next_node == "composite_execution":
        state = composite_execution_node(state)
    else:
        state = intent_classify_node(state)
        state = planning_node(state)
        state = tool_execution_node(state)
    state = synthesize_answer_node(state)
    state = finalize_answer_node(state)
    return state


def summarize(details: list[dict]) -> list[dict]:
    summary = []
    for method in METHODS:
        items = [item for item in details if item["method"] == method]
        successful = [item for item in items if item["error"] is None and item["semantic_similarity"] is not None]
        route_items = [item for item in items if item["route_ok"] is not None]
        summary.append(
            {
                "method": method,
                "sample_count": len(items),
                "failed": sum(1 for item in items if item["error"]),
                "answer_pass_rate": ratio(sum(1 for item in items if item["answer_ok"]), len(items)),
                "avg_semantic_similarity": round(
                    sum(item["semantic_similarity"] for item in successful) / len(successful),
                    6,
                )
                if successful
                else 0.0,
                "citation_rate": ratio(sum(1 for item in items if item["citation_ok"]), len(items)),
                "reasoning_chain_rate": ratio(
                    sum(1 for item in items if item["reasoning_chain_ok"]), len(items)
                ),
                "route_accuracy": ratio(sum(1 for item in route_items if item["route_ok"]), len(route_items))
                if route_items
                else "",
                "avg_reflection_count": round(
                    sum(item["reflection_count"] for item in items) / len(items),
                    6,
                )
                if items
                else 0.0,
            }
        )
    return summary


def write_summary(summary: list[dict]) -> None:
    with SUMMARY_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)


def write_details(details: list[dict]) -> None:
    fieldnames = [
        "id",
        "question",
        "method",
        "expected_route",
        "actual_route",
        "semantic_similarity",
        "answer_ok",
        "citation_count",
        "citation_ok",
        "reasoning_step_count",
        "reasoning_chain_ok",
        "reflection_count",
        "route_ok",
        "sub_question_count",
        "trace_stage_count",
        "error",
    ]
    with DETAILS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in details:
            writer.writerow({field: item.get(field) for field in fieldnames})


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


if __name__ == "__main__":
    main()
