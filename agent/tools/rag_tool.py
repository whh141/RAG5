#!/usr/bin/env python
# coding: utf-8
"""
RAG 工具。
主链路：混合召回 -> 去重 -> 重排 -> 事实抽取 -> 答案生成 -> 引用校验。
"""

import json
import re
from typing import Any, Dict, List, Tuple

from langchain_core.documents import Document


class RAGTool:
    """
    本地校园知识库 RAG。
    """

    def __init__(self, faiss_retriever, bm25_retriever, rerank_model, llm):
        self.faiss_retriever = faiss_retriever
        self.bm25_retriever = bm25_retriever
        self.rerank = rerank_model
        self.llm = llm

    def answer(
        self,
        query: str,
        intent: str,
        vector_top_k: int = 20,
        bm25_top_k: int = 20,
        rerank_top_k: int = 8,
    ) -> Dict[str, Any]:
        faiss_docs = self.faiss_retriever.GetTopK(query, vector_top_k)
        bm25_docs = self.bm25_retriever.GetBM25TopKWithScores(query, bm25_top_k)

        merged_docs = self._merge_documents(faiss_docs, bm25_docs)
        if not merged_docs:
            raise ValueError("本地检索未召回任何文档")

        candidate_docs = self._pre_rank_candidates(query, merged_docs)[: max(rerank_top_k * 3, rerank_top_k)]
        reranked_only = self.rerank.predict(query, candidate_docs)
        if not reranked_only:
            raise ValueError("重排序未返回文档")
        reranked_docs = self._hybrid_final_rank(query, candidate_docs, reranked_only)[:rerank_top_k]

        evidence_items = self._extract_evidence(query, intent, reranked_docs)
        if not evidence_items:
            raise ValueError("未能从本地文档中抽取可用证据")

        reasoning_steps: list[dict[str, Any]] = []
        if intent == "complex_reasoning":
            reasoning_steps = self._generate_reasoning_chain(query, evidence_items)
            answer = self._generate_answer_from_reasoning(query, evidence_items, reasoning_steps)
        else:
            answer = self._generate_answer(query, evidence_items)
        citations = self._verify_citations(answer, evidence_items)
        confidence = self._calculate_confidence(faiss_docs, len(evidence_items), len(reranked_docs))

        return {
            "answer": answer,
            "documents": reranked_docs,
            "evidence_items": evidence_items,
            "reasoning_steps": reasoning_steps,
            "citations": citations,
            "confidence": confidence,
            "retrieved_count": len(merged_docs),
            "reranked_count": len(reranked_docs),
            "source": "local_rag",
        }

    def _merge_documents(
        self,
        faiss_docs: List[Tuple[Document, float]],
        bm25_docs: List[Tuple[Document, float]],
    ) -> List[Document]:
        merged: list[Document] = []
        by_key: dict[str, Document] = {}

        for doc, score in faiss_docs:
            doc.metadata = dict(doc.metadata)
            doc.metadata["vector_score"] = float(score)
            key = self._document_key(doc)
            by_key[key] = doc

        for doc, score in bm25_docs:
            doc.metadata = dict(doc.metadata)
            doc.metadata["bm25_score"] = float(score)
            key = self._document_key(doc)
            if key in by_key:
                by_key[key].metadata["bm25_score"] = float(score)
            else:
                by_key[key] = doc

        return list(by_key.values())

    def _pre_rank_candidates(self, query: str, documents: List[Document]) -> List[Document]:
        max_bm25 = max((float(doc.metadata.get("bm25_score", 0.0)) for doc in documents), default=1.0)
        scored = []
        for doc in documents:
            score = (
                self._lexical_score(doc, max_bm25) * 0.65
                + self._vector_score(doc) * 0.20
                + self._slot_score(query, doc) * 0.15
            )
            scored.append((doc, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return [doc for doc, _score in scored]

    def _hybrid_final_rank(
        self,
        query: str,
        candidate_docs: List[Document],
        reranked_docs: List[Document],
    ) -> List[Document]:
        max_bm25 = max((float(doc.metadata.get("bm25_score", 0.0)) for doc in candidate_docs), default=1.0)
        rerank_position = {
            self._document_key(doc): idx
            for idx, doc in enumerate(reranked_docs, start=1)
        }

        scored = []
        for doc in candidate_docs:
            key = self._document_key(doc)
            rerank_score = 1 / rerank_position[key] if key in rerank_position else 0.0
            final_score = (
                self._lexical_score(doc, max_bm25) * 0.55
                + self._slot_score(query, doc) * 0.20
                + self._vector_score(doc) * 0.10
                + rerank_score * 0.15
            )
            doc.metadata["hybrid_score"] = final_score
            scored.append((doc, final_score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return [doc for doc, _score in scored]

    def _lexical_score(self, doc: Document, max_bm25: float) -> float:
        bm25_score = float(doc.metadata.get("bm25_score", 0.0))
        if max_bm25 <= 0:
            return 0.0
        return max(0.0, min(1.0, bm25_score / max_bm25))

    def _vector_score(self, doc: Document) -> float:
        vector_score = doc.metadata.get("vector_score")
        if vector_score is None:
            return 0.0
        return max(0.0, min(1.0, 1 - float(vector_score) / 1200))

    def _slot_score(self, query: str, doc: Document) -> float:
        query_text = query.strip().lower()
        doc_text = doc.page_content.strip().lower()
        score = 0.0

        slot_groups = [
            ({"地点", "在哪", "哪里", "窗口"}, {"地点", "在哪", "哪里", "窗口", "大厅", "办公室", "校区"}),
            ({"材料", "带什么", "上传"}, {"材料", "身份证", "照片", "申请书", "证明", "上传"}),
            ({"收费", "费用", "多少钱"}, {"收费", "费用", "元", "工本费", "校园卡"}),
            ({"时间", "什么时候", "几点"}, {"时间", "什么时候", "周一", "周五", "上午", "下午"}),
            ({"流程", "怎么办理", "怎么申请"}, {"流程", "申请", "办理", "步骤", "提交"}),
        ]

        for query_terms, doc_terms in slot_groups:
            if any(term in query_text for term in query_terms):
                matched = sum(1 for term in doc_terms if term in doc_text)
                score = max(score, min(1.0, matched / 3))

        return score

    def _extract_evidence(
        self,
        query: str,
        intent: str,
        documents: List[Document],
    ) -> List[Dict[str, Any]]:
        source_blocks = []
        for index, doc in enumerate(documents, start=1):
            source_blocks.append(
                {
                    "source_id": index,
                    "title": doc.metadata.get("title", ""),
                    "source_file": doc.metadata.get("source_file", ""),
                    "page": doc.metadata.get("page"),
                    "chunk_id": doc.metadata.get("chunk_id"),
                    "content": doc.page_content,
                }
            )

        prompt = f"""你是校园 RAG 系统的证据抽取器。请只从给定文档中抽取能回答问题的核心事实。

用户问题：{query}
问题类型：{intent}

文档片段 JSON：
{json.dumps(source_blocks, ensure_ascii=False)}

要求：
- 只输出 JSON object，不要 Markdown，不要解释。
- JSON object 必须包含 evidence_items 字段，值为数组。
- evidence_items 中每个元素必须包含 source_id 和 fact。
- fact 必须是文档中支持的明确事实，不得推测。
- 如果文档不足以回答问题，输出 {{"evidence_items": []}}。
- 最多输出 8 条事实。

输出示例：
{{
  "evidence_items": [
    {{"source_id": 1, "fact": "学生证补办地点为中心校区明德楼B座1楼师生服务大厅B01窗口。"}}
  ]
}}
"""
        result_text = self._infer_json_one(prompt)
        evidence_obj = self._parse_json(result_text, expected_type=dict, stage="证据抽取")
        evidence_raw = evidence_obj.get("evidence_items")
        if not isinstance(evidence_raw, list):
            raise ValueError("证据抽取 JSON 缺少 evidence_items 数组")

        evidence_items: list[dict[str, Any]] = []
        docs_by_source_id = {idx: doc for idx, doc in enumerate(documents, start=1)}
        for item in evidence_raw:
            if not isinstance(item, dict):
                raise ValueError(f"证据项不是对象: {item}")
            source_id = int(item.get("source_id", 0))
            fact = str(item.get("fact", "")).strip()
            if source_id not in docs_by_source_id:
                raise ValueError(f"证据 source_id 不存在: {source_id}")
            if not fact:
                raise ValueError("证据 fact 不能为空")

            doc = docs_by_source_id[source_id]
            evidence_items.append(
                {
                    "evidence_id": len(evidence_items) + 1,
                    "fact": fact,
                    "source_id": source_id,
                    "title": doc.metadata.get("title", ""),
                    "source_file": doc.metadata.get("source_file", ""),
                    "source_type": doc.metadata.get("source_type", ""),
                    "page": doc.metadata.get("page"),
                    "chunk_id": doc.metadata.get("chunk_id"),
                    "doc_id": doc.metadata.get("doc_id", ""),
                }
            )

        return evidence_items

    def _generate_answer(self, query: str, evidence_items: List[Dict[str, Any]]) -> str:
        prompt = f"""你是校园知识问答助手。请严格基于证据回答用户问题。

用户问题：{query}

证据 JSON：
{json.dumps(evidence_items, ensure_ascii=False)}

要求：
- 只能使用证据 JSON 中的事实。
- 每个关键结论后必须使用 [证据编号] 标注引用，例如 [1]。
- 不得输出证据之外的信息。
- 如果证据不足，不要编造，直接说明“证据不足，无法基于当前知识库回答该问题”。
- 回答中文，简洁、可执行。

直接输出答案："""
        answer = self._infer_one(prompt).strip()
        if not answer:
            raise ValueError("答案生成为空")
        return answer

    def _generate_reasoning_chain(
        self,
        query: str,
        evidence_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        prompt = f"""你是校园问答系统的复杂推理助手。请先基于证据生成结构化推理链，再交给后续模块生成最终答案。

用户问题：{query}

证据 JSON：
{json.dumps(evidence_items, ensure_ascii=False)}

要求：
- 只输出 JSON object，不要 Markdown，不要解释。
- JSON object 必须包含 reasoning_steps 字段，值为非空数组。
- reasoning_steps 中每个元素必须包含 step、summary、evidence_ids。
- step 必须从 1 开始递增。
- summary 必须是一步简洁的中文推理说明，不要重复问题原文。
- evidence_ids 必须是非空整数数组，且编号必须来自证据中的 evidence_id。
- 所有推理都必须由证据支撑，不得添加证据之外的结论。
- 最多输出 4 步。

输出示例：
{{
  "reasoning_steps": [
    {{
      "step": 1,
      "summary": "先确认成绩复核的适用条件和办理要求",
      "evidence_ids": [1, 2]
    }},
    {{
      "step": 2,
      "summary": "再确认缓考申请的适用条件和办理要求",
      "evidence_ids": [2, 3]
    }},
    {{
      "step": 3,
      "summary": "最后比较两者在条件和流程上的差异",
      "evidence_ids": [1, 2, 3]
    }}
  ]
}}"""
        result_text = self._infer_json_one(prompt)
        chain_obj = self._parse_json(result_text, expected_type=dict, stage="推理链生成")
        steps_raw = chain_obj.get("reasoning_steps")
        if not isinstance(steps_raw, list) or not steps_raw:
            raise ValueError("推理链生成缺少非空 reasoning_steps 数组")

        valid_ids = {item["evidence_id"] for item in evidence_items}
        reasoning_steps: list[dict[str, Any]] = []
        expected_step = 1
        for item in steps_raw:
            if not isinstance(item, dict):
                raise ValueError(f"推理步骤不是对象: {item}")

            step = int(item.get("step", 0))
            summary = str(item.get("summary", "")).strip()
            evidence_ids = item.get("evidence_ids")
            if step != expected_step:
                raise ValueError(f"推理步骤编号不连续: expected={expected_step}, got={step}")
            if not summary:
                raise ValueError(f"推理步骤 {step} 缺少 summary")
            if not isinstance(evidence_ids, list) or not evidence_ids:
                raise ValueError(f"推理步骤 {step} 缺少非空 evidence_ids")

            deduped_ids: list[int] = []
            for evidence_id in evidence_ids:
                if not isinstance(evidence_id, int):
                    raise ValueError(f"推理步骤 {step} 存在非整数 evidence_id")
                if evidence_id not in valid_ids:
                    raise ValueError(f"推理步骤 {step} 引用了不存在的证据编号: {evidence_id}")
                if evidence_id not in deduped_ids:
                    deduped_ids.append(evidence_id)

            reasoning_steps.append(
                {
                    "step": step,
                    "summary": summary,
                    "evidence_ids": deduped_ids,
                }
            )
            expected_step += 1

        return reasoning_steps

    def _generate_answer_from_reasoning(
        self,
        query: str,
        evidence_items: List[Dict[str, Any]],
        reasoning_steps: List[Dict[str, Any]],
    ) -> str:
        prompt = f"""你是校园知识问答助手。请基于证据和结构化推理链回答复杂推理问题。

用户问题：{query}

结构化推理链 JSON：
{json.dumps(reasoning_steps, ensure_ascii=False)}

证据 JSON：
{json.dumps(evidence_items, ensure_ascii=False)}

要求：
- 只能使用推理链和证据中的信息。
- 最终答案不要照抄推理链步骤编号，但要体现清晰的比较或归纳逻辑。
- 每个关键结论后必须使用 [证据编号] 标注引用，例如 [1][2]。
- 不得输出证据之外的信息。
- 如果证据仍然不足，直接说明“证据不足，无法基于当前知识库完成复杂推理回答”。
- 回答中文，简洁、清晰、可执行。

直接输出答案："""
        answer = self._infer_one(prompt).strip()
        if not answer:
            raise ValueError("复杂推理答案生成为空")
        return answer

    def _verify_citations(
        self,
        answer: str,
        evidence_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        citation_ids = {int(match) for match in re.findall(r"\[(\d+)\]", answer)}
        valid_ids = {item["evidence_id"] for item in evidence_items}

        if not citation_ids:
            raise ValueError("答案没有引用证据编号")

        invalid_ids = citation_ids - valid_ids
        if invalid_ids:
            raise ValueError(f"答案引用了不存在的证据编号: {sorted(invalid_ids)}")

        citations = []
        for item in evidence_items:
            if item["evidence_id"] not in citation_ids:
                continue
            citations.append(
                {
                    "evidence_id": item["evidence_id"],
                    "title": item["title"],
                    "source_file": item["source_file"],
                    "source_type": item["source_type"],
                    "page": item["page"],
                    "chunk_id": item["chunk_id"],
                    "fact": item["fact"],
                }
            )

        return citations

    def _calculate_confidence(
        self,
        faiss_docs: List[Tuple[Document, float]],
        evidence_count: int,
        reranked_count: int,
    ) -> float:
        if not faiss_docs:
            return 0.0
        best_score = min(float(score) for _doc, score in faiss_docs)
        score_confidence = max(0.0, min(1.0, 1 - best_score / 1200))
        evidence_confidence = min(1.0, evidence_count / 4)
        rerank_confidence = min(1.0, reranked_count / 8)
        return round(score_confidence * 0.45 + evidence_confidence * 0.4 + rerank_confidence * 0.15, 2)

    def _infer_one(self, prompt: str) -> str:
        outputs = self.llm.infer([prompt])
        if len(outputs) != 1:
            raise RuntimeError(f"LLM 返回数量异常: {len(outputs)}")
        return outputs[0]

    def _infer_json_one(self, prompt: str) -> str:
        if not hasattr(self.llm, "infer_json"):
            raise RuntimeError("当前 LLM 后端不支持 JSON mode，无法执行结构化证据抽取")
        outputs = self.llm.infer_json([prompt])
        if len(outputs) != 1:
            raise RuntimeError(f"LLM JSON 返回数量异常: {len(outputs)}")
        return outputs[0]

    def _parse_json(self, text: str, expected_type: type, stage: str):
        stripped = text.strip()
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{stage} 未输出严格 JSON: {stripped[:160]}") from exc
        if not isinstance(parsed, expected_type):
            raise ValueError(f"{stage} JSON 类型错误: expected={expected_type.__name__}")
        return parsed

    def _document_key(self, doc: Document) -> str:
        return str(doc.metadata.get("doc_id") or doc.page_content)
