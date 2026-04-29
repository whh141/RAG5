#!/usr/bin/env python
# coding: utf-8
"""
系统效率实验。

构建带计时 wrapper 的 LangGraph，只用于实验观测，不修改业务主图。
"""

import argparse
import csv
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langgraph.graph import END, StateGraph  # noqa: E402

from agent.config.model_config import ModelConfig  # noqa: E402
from agent.nodes import (  # noqa: E402
    composite_execution_node,
    intent_classify_node,
    planning_node,
    question_decompose_node,
    reflection_node,
    route_after_decompose,
    should_continue,
    synthesize_answer_node,
    tool_execution_node,
)
from agent.nodes.finalizer import finalize_answer_node  # noqa: E402
from agent.nodes.tool_executor import set_tools  # noqa: E402
from agent.state import AgentState  # noqa: E402
from agent.tools import RAGTool, TavilyTool  # noqa: E402
from bm25_retriever import BM25  # noqa: E402
from config import LLM_BACKEND  # noqa: E402
from eval_all import _initial_state  # noqa: E402
from faiss_retriever import FaissRetriever  # noqa: E402
from llm_model import get_llm_model  # noqa: E402
from pdf_parse import load_knowledge_documents  # noqa: E402
from rerank_model import reRankLLM  # noqa: E402


OUT_DIR = Path(__file__).resolve().parent
REPORT_PATH = OUT_DIR / "efficiency_report.json"
DETAILS_CSV = OUT_DIR / "efficiency_case_details.csv"
SUMMARY_CSV = OUT_DIR / "efficiency_summary_metrics.csv"
STAGE_CSV = OUT_DIR / "stage_time_summary.csv"

STAGES = [
    "question_decompose",
    "intent_classify",
    "planning",
    "tool_execution",
    "composite_execution",
    "synthesize",
    "reflection",
    "finalize",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-type", type=int, default=3)
    args = parser.parse_args()

    samples = load_samples(args.per_type)
    print(f"[Efficiency] samples: {len(samples)}")

    initialize_tools()
    graph = build_timed_agent_graph()

    details = []
    for index, sample in enumerate(samples, start=1):
        print(f"[Efficiency] {index}/{len(samples)} {sample['id']} {sample['sample_type']}")
        details.append(run_one(graph, sample))

    summary = summarize_by_type(details)
    stage_summary = summarize_stages(details)

    REPORT_PATH.write_text(
        json.dumps(
            {
                "experiment": "efficiency",
                "sample_count": len(samples),
                "summary": summary,
                "stage_summary": stage_summary,
                "details": details,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_details(details)
    write_summary(summary)
    write_stage_summary(stage_summary)
    print(json.dumps({"report": str(REPORT_PATH), "summary": summary}, ensure_ascii=False, indent=2))


def initialize_tools() -> None:
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


def build_timed_agent_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("question_decompose", timed_node("question_decompose", question_decompose_node))
    workflow.add_node("intent_classify", timed_node("intent_classify", intent_classify_node))
    workflow.add_node("planning", timed_node("planning", planning_node))
    workflow.add_node("tool_execution", timed_node("tool_execution", tool_execution_node))
    workflow.add_node("composite_execution", timed_node("composite_execution", composite_execution_node))
    workflow.add_node("synthesize", timed_node("synthesize", synthesize_answer_node))
    workflow.add_node("reflection", timed_node("reflection", reflection_node))
    workflow.add_node("finalize", timed_node("finalize", finalize_answer_node))

    workflow.set_entry_point("question_decompose")
    workflow.add_conditional_edges(
        "question_decompose",
        route_after_decompose,
        {
            "intent_classify": "intent_classify",
            "composite_execution": "composite_execution",
        },
    )
    workflow.add_edge("intent_classify", "planning")
    workflow.add_edge("planning", "tool_execution")
    workflow.add_edge("tool_execution", "synthesize")
    workflow.add_edge("composite_execution", "synthesize")
    workflow.add_edge("synthesize", "reflection")
    workflow.add_conditional_edges(
        "reflection",
        should_continue,
        {
            "finalize": "finalize",
            "retry": "planning",
        },
    )
    workflow.add_edge("finalize", END)
    return workflow.compile()


def timed_node(stage: str, fn: Callable[[AgentState], AgentState]):
    def wrapper(state: AgentState) -> AgentState:
        started = time.perf_counter()
        try:
            return fn(state)
        finally:
            elapsed = time.perf_counter() - started
            metadata = state.setdefault("metadata", {})
            timings = metadata.setdefault("timings", [])
            timings.append({"stage": stage, "elapsed_sec": elapsed})

    return wrapper


def run_one(graph, sample: dict) -> dict:
    started = time.perf_counter()
    state = _initial_state(sample["question"])
    error = None
    result = None
    try:
        result = graph.invoke(state)
    except Exception as exc:
        error = str(exc)
        result = state

    total_time = time.perf_counter() - started
    timings = result.get("metadata", {}).get("timings", []) if isinstance(result, dict) else []
    stage_totals = {stage: 0.0 for stage in STAGES}
    for item in timings:
        stage = item.get("stage")
        if stage in stage_totals:
            stage_totals[stage] += float(item.get("elapsed_sec", 0.0))

    row = {
        "id": sample["id"],
        "sample_type": sample["sample_type"],
        "question": sample["question"],
        "expected_route": sample.get("expected_route"),
        "actual_intent": result.get("intent") if isinstance(result, dict) else "",
        "actual_route": result.get("route") if isinstance(result, dict) else "",
        "answer_source": result.get("answer_source") if isinstance(result, dict) else "",
        "reflection_count": int(result.get("reflection_count", 0) or 0) if isinstance(result, dict) else 0,
        "total_time_sec": round(total_time, 6),
        "error": error,
    }
    for stage in STAGES:
        row[f"{stage}_time_sec"] = round(stage_totals[stage], 6)
    return row


def load_samples(per_type: int) -> list[dict]:
    samples: list[dict] = []

    eval_rows = read_jsonl(ROOT / "data" / "eval_qa.jsonl")
    route_rows = read_jsonl(ROOT / "data" / "route_labels.jsonl")
    ood_rows = read_jsonl(ROOT / "data" / "ood_questions.jsonl")

    samples.extend(
        {
            "id": row["id"],
            "sample_type": "simple_fact",
            "question": row["question"],
            "expected_route": row.get("expected_route"),
        }
        for row in select_rows(eval_rows, per_type, lambda item: item.get("intent_label") == "simple_fact")
    )
    samples.extend(
        {
            "id": row["id"],
            "sample_type": "complex_reasoning",
            "question": row["question"],
            "expected_route": row.get("expected_route"),
        }
        for row in select_rows(eval_rows, per_type, lambda item: item.get("intent_label") == "complex_reasoning")
    )
    samples.extend(
        {
            "id": row["id"],
            "sample_type": "time_sensitive",
            "question": row["question"],
            "expected_route": row.get("expected_route"),
        }
        for row in select_rows(route_rows, per_type, lambda item: item.get("intent") == "time_sensitive")
    )
    samples.extend(
        {
            "id": row["id"],
            "sample_type": "ood",
            "question": row["question"],
            "expected_route": "refuse",
        }
        for row in ood_rows[:per_type]
    )
    return samples


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def select_rows(rows: list[dict], limit: int, predicate) -> list[dict]:
    return [row for row in rows if predicate(row)][:limit]


def summarize_by_type(details: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for item in details:
        grouped[item["sample_type"]].append(item)

    rows = []
    for sample_type, items in grouped.items():
        total_times = [item["total_time_sec"] for item in items]
        rows.append(
            {
                "sample_type": sample_type,
                "sample_count": len(items),
                "failed": sum(1 for item in items if item["error"]),
                "avg_total_time_sec": round(sum(total_times) / len(total_times), 6),
                "p50_total_time_sec": round(statistics.median(total_times), 6),
                "p95_total_time_sec": round(percentile(total_times, 0.95), 6),
                "avg_reflection_count": round(
                    sum(item["reflection_count"] for item in items) / len(items),
                    6,
                ),
            }
        )
    return rows


def summarize_stages(details: list[dict]) -> list[dict]:
    totals = {stage: 0.0 for stage in STAGES}
    total_stage_time = 0.0
    for item in details:
        for stage in STAGES:
            value = float(item.get(f"{stage}_time_sec", 0.0) or 0.0)
            totals[stage] += value
            total_stage_time += value

    rows = []
    sample_count = len(details)
    for stage in STAGES:
        rows.append(
            {
                "stage": stage,
                "total_time_sec": round(totals[stage], 6),
                "avg_time_sec": round(totals[stage] / sample_count, 6) if sample_count else 0.0,
                "time_share": round(totals[stage] / total_stage_time, 6) if total_stage_time else 0.0,
            }
        )
    return rows


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * q
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = index - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def write_details(details: list[dict]) -> None:
    fieldnames = [
        "id",
        "sample_type",
        "question",
        "expected_route",
        "actual_intent",
        "actual_route",
        "answer_source",
        "reflection_count",
        "total_time_sec",
        *[f"{stage}_time_sec" for stage in STAGES],
        "error",
    ]
    with DETAILS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(details)


def write_summary(summary: list[dict]) -> None:
    with SUMMARY_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)


def write_stage_summary(stage_summary: list[dict]) -> None:
    with STAGE_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(stage_summary[0].keys()))
        writer.writeheader()
        writer.writerows(stage_summary)


if __name__ == "__main__":
    main()
