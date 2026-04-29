#!/usr/bin/env python
# coding: utf-8
"""
检索与重排序消融实验。

由于 eval_qa.jsonl 没有 gold support_doc_id，本脚本不计算严格 Recall@K/MRR。
它计算标准答案语义覆盖指标，并导出 Top-5 候选文档供人工标注。
"""

import csv
import hashlib
import json
import sys
import time
import argparse
from collections import defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.tools.rag_tool import RAGTool  # noqa: E402
from bm25_retriever import BM25  # noqa: E402
from faiss_retriever import FaissRetriever  # noqa: E402
from pdf_parse import load_knowledge_documents  # noqa: E402
from rerank_model import reRankLLM  # noqa: E402
from scoring_model import get_scoring_model  # noqa: E402


OUT_DIR = Path(__file__).resolve().parent
QA_PATH = ROOT / "data" / "eval_qa.jsonl"
REPORT_PATH = OUT_DIR / "retrieval_ablation_report.json"
SUMMARY_CSV = OUT_DIR / "retrieval_summary_metrics.csv"
AT_K_CSV = OUT_DIR / "retrieval_at_k_metrics.csv"
CANDIDATES_CSV = OUT_DIR / "retrieval_candidates_top5.csv"

METHODS = ["bm25_only", "faiss_only", "hybrid", "hybrid_rerank"]
K_VALUES = [1, 3, 5, 8, 10, 20]
MAX_K = max(K_VALUES)
SEMANTIC_THRESHOLD = 0.72
BATCH_SIZE = 32


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--stratified-limit", type=int, default=None)
    args = parser.parse_args()

    rows = load_local_qa_rows()
    if args.stratified_limit is not None:
        rows = stratified_sample(rows, args.stratified_limit)
    elif args.limit is not None:
        rows = rows[: args.limit]
    print(f"[Ablation] local QA rows: {len(rows)}")

    documents = load_knowledge_documents(
        kb_dir=str(ROOT / "data" / "kb_docs"),
        faq_path=str(ROOT / "data" / "faq_database.json"),
    )
    print(f"[Ablation] knowledge chunks: {len(documents)}")

    faiss = FaissRetriever(documents=documents)
    bm25 = BM25(documents)
    rerank = reRankLLM()
    if hasattr(rerank.reranker, "top_n"):
        rerank.reranker.top_n = MAX_K
    rag_helper = RAGTool(faiss, bm25, rerank, llm=None)

    retrieval_records: list[dict] = []
    doc_text_by_key: dict[str, str] = {}

    for index, row in enumerate(rows, start=1):
        print(f"[Ablation] retrieving {index}/{len(rows)} {row['id']}")
        method_docs, timings = retrieve_all_methods(row["question"], faiss, bm25, rerank, rag_helper)
        for method, docs in method_docs.items():
            for rank, doc in enumerate(docs[:MAX_K], start=1):
                key = doc_key(doc)
                doc_text_by_key[key] = doc.page_content
                retrieval_records.append(
                    {
                        "id": row["id"],
                        "question": row["question"],
                        "ground_truth": row["ground_truth"],
                        "method": method,
                        "rank": rank,
                        "doc_key": key,
                        "title": doc.metadata.get("title", ""),
                        "source_file": doc.metadata.get("source_file", ""),
                        "source_type": doc.metadata.get("source_type", ""),
                        "page": doc.metadata.get("page", ""),
                        "chunk_id": doc.metadata.get("chunk_id", ""),
                        "doc_id": doc.metadata.get("doc_id", ""),
                        "retrieval_time_sec": round(timings[method], 6),
                    }
                )

    scorer = get_scoring_model()
    gt_vectors = encode_texts(scorer, [row["ground_truth"] for row in rows])
    doc_keys = list(doc_text_by_key.keys())
    doc_vectors = encode_texts(scorer, [doc_text_by_key[key] for key in doc_keys])
    doc_index = {key: idx for idx, key in enumerate(doc_keys)}

    records_by_sample_method = defaultdict(list)
    for record in retrieval_records:
        records_by_sample_method[(record["id"], record["method"])].append(record)

    details = []
    at_k_rows = []
    summary_rows = []

    row_by_id = {row["id"]: row for row in rows}
    gt_index_by_id = {row["id"]: idx for idx, row in enumerate(rows)}

    for method in METHODS:
        reciprocal_ranks = []
        method_details = []
        for row in rows:
            sample_records = sorted(
                records_by_sample_method[(row["id"], method)],
                key=lambda item: item["rank"],
            )
            gt_vector = gt_vectors[gt_index_by_id[row["id"]]]
            similarities = []
            first_hit_rank = None
            for record in sample_records:
                score = float(np.dot(gt_vector, doc_vectors[doc_index[record["doc_key"]]]))
                score = max(0.0, min(1.0, score))
                record["semantic_similarity_to_ground_truth"] = round(score, 6)
                similarities.append(score)
                if first_hit_rank is None and score >= SEMANTIC_THRESHOLD:
                    first_hit_rank = record["rank"]

            reciprocal_ranks.append(1 / first_hit_rank if first_hit_rank else 0.0)
            method_details.append(
                {
                    "id": row["id"],
                    "method": method,
                    "first_semantic_hit_rank": first_hit_rank,
                    "semantic_mrr_item": round(1 / first_hit_rank, 6) if first_hit_rank else 0.0,
                    "best_similarity_at_20": round(max(similarities), 6) if similarities else 0.0,
                }
            )

            for k in K_VALUES:
                top_scores = similarities[:k]
                best_score = max(top_scores) if top_scores else 0.0
                at_k_rows.append(
                    {
                        "method": method,
                        "id": row["id"],
                        "k": k,
                        "semantic_hit": best_score >= SEMANTIC_THRESHOLD,
                        "best_similarity": round(best_score, 6),
                    }
                )

        details.extend(method_details)
        summary_rows.append(
            {
                "method": method,
                "sample_count": len(rows),
                "semantic_threshold": SEMANTIC_THRESHOLD,
                "semantic_mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 6),
            }
        )

    aggregated_at_k = aggregate_at_k(at_k_rows)
    write_summary(summary_rows, aggregated_at_k)
    write_at_k(aggregated_at_k)
    write_candidates(retrieval_records)

    report = {
        "experiment": "retrieval_ablation",
        "sample_count": len(rows),
        "methods": METHODS,
        "k_values": K_VALUES,
        "semantic_threshold": SEMANTIC_THRESHOLD,
        "metric_note": (
            "This report uses semantic coverage against ground_truth because eval_qa.jsonl "
            "does not contain gold support document labels. It is not strict Recall@K/MRR."
        ),
        "summary": summary_rows,
        "at_k": aggregated_at_k,
        "details": details,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"report": str(REPORT_PATH), "summary": summary_rows}, ensure_ascii=False, indent=2))


def load_local_qa_rows() -> list[dict]:
    rows = []
    with QA_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("expected_route") == "retrieve_local":
                rows.append(row)
    return rows


def stratified_sample(rows: list[dict], limit: int) -> list[dict]:
    if limit >= len(rows):
        return rows

    by_label = defaultdict(list)
    for row in rows:
        by_label[row.get("intent_label", "unknown")].append(row)

    labels = sorted(by_label)
    selected = []
    per_label = max(1, limit // len(labels))
    for label in labels:
        selected.extend(by_label[label][:per_label])

    remaining = limit - len(selected)
    if remaining > 0:
        selected_ids = {row["id"] for row in selected}
        for row in rows:
            if row["id"] in selected_ids:
                continue
            selected.append(row)
            if len(selected) >= limit:
                break

    return selected[:limit]


def retrieve_all_methods(query: str, faiss, bm25, rerank, rag_helper) -> tuple[dict[str, list], dict[str, float]]:
    method_docs = {}
    timings = {}

    started = time.perf_counter()
    method_docs["bm25_only"] = [doc for doc, _score in bm25.GetBM25TopKWithScores(query, MAX_K)]
    timings["bm25_only"] = time.perf_counter() - started

    started = time.perf_counter()
    method_docs["faiss_only"] = [doc for doc, _score in faiss.GetTopK(query, MAX_K)]
    timings["faiss_only"] = time.perf_counter() - started

    started = time.perf_counter()
    faiss_docs = faiss.GetTopK(query, MAX_K)
    bm25_docs = bm25.GetBM25TopKWithScores(query, MAX_K)
    merged_docs = rag_helper._merge_documents(faiss_docs, bm25_docs)
    hybrid_docs = rag_helper._pre_rank_candidates(query, merged_docs)[:MAX_K]
    method_docs["hybrid"] = hybrid_docs
    timings["hybrid"] = time.perf_counter() - started

    started = time.perf_counter()
    candidate_docs = rag_helper._pre_rank_candidates(query, merged_docs)[:MAX_K]
    reranked_docs = rerank.predict(query, candidate_docs)
    method_docs["hybrid_rerank"] = rag_helper._hybrid_final_rank(query, candidate_docs, reranked_docs)[:MAX_K]
    timings["hybrid_rerank"] = time.perf_counter() - started

    return method_docs, timings


def encode_texts(scorer, texts: list[str]) -> np.ndarray:
    vectors = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]
        vectors.append(scorer._encode_local(batch))
    return np.vstack(vectors)


def aggregate_at_k(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["method"], row["k"])].append(row)

    result = []
    for method in METHODS:
        for k in K_VALUES:
            items = grouped[(method, k)]
            result.append(
                {
                    "method": method,
                    "k": k,
                    "semantic_coverage_at_k": round(
                        sum(1 for item in items if item["semantic_hit"]) / len(items),
                        6,
                    ),
                    "avg_best_similarity_at_k": round(
                        sum(item["best_similarity"] for item in items) / len(items),
                        6,
                    ),
                }
            )
    return result


def write_summary(summary_rows: list[dict], at_k_rows: list[dict]) -> None:
    at_k_lookup = {(row["method"], row["k"]): row for row in at_k_rows}
    with SUMMARY_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "method",
                "sample_count",
                "semantic_threshold",
                "semantic_mrr",
                "semantic_coverage_at_1",
                "semantic_coverage_at_3",
                "semantic_coverage_at_5",
                "semantic_coverage_at_8",
                "semantic_coverage_at_10",
                "semantic_coverage_at_20",
            ],
        )
        writer.writeheader()
        for row in summary_rows:
            item = dict(row)
            for k in K_VALUES:
                item[f"semantic_coverage_at_{k}"] = at_k_lookup[(row["method"], k)][
                    "semantic_coverage_at_k"
                ]
            writer.writerow(item)


def write_at_k(rows: list[dict]) -> None:
    with AT_K_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["method", "k", "semantic_coverage_at_k", "avg_best_similarity_at_k"],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_candidates(records: list[dict]) -> None:
    with CANDIDATES_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "question",
                "ground_truth",
                "method",
                "rank",
                "semantic_similarity_to_ground_truth",
                "doc_key",
                "title",
                "source_file",
                "source_type",
                "page",
                "chunk_id",
                "doc_id",
                "retrieval_time_sec",
                "human_support_label",
                "human_note",
            ],
        )
        writer.writeheader()
        for record in records:
            if record["rank"] > 5:
                continue
            row = dict(record)
            row["human_support_label"] = ""
            row["human_note"] = ""
            writer.writerow(row)


def doc_key(doc) -> str:
    metadata = doc.metadata or {}
    raw = "|".join(
        str(metadata.get(field, ""))
        for field in ("doc_id", "source_file", "page", "chunk_id", "id")
    )
    if raw.strip("|"):
        return raw
    return hashlib.md5(doc.page_content.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
