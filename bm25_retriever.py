#!/usr/bin/env python
# coding: utf-8
"""
BM25 检索器。
使用项目内实现返回显式分数，避免外部封装隐藏排序和分数细节。
"""

from __future__ import annotations

import math
from collections import Counter
from typing import List, Tuple

import jieba
from langchain_core.documents import Document

from pdf_parse import load_knowledge_documents


class BM25:
    """
    中文 BM25 检索器。
    """

    def __init__(self, documents: list[Document], k1: float = 1.5, b: float = 0.75):
        if not documents:
            raise ValueError("BM25 文档不能为空")

        self.documents: list[Document] = []
        self.tokenized_docs: list[list[str]] = []
        self.term_freqs: list[Counter[str]] = []
        self.doc_freq: Counter[str] = Counter()
        self.doc_lengths: list[int] = []
        self.k1 = k1
        self.b = b

        for idx, doc in enumerate(documents):
            text = doc.page_content.strip()
            if len(text) < 5:
                raise ValueError(f"BM25 收到过短文档块: index={idx}")

            metadata = dict(doc.metadata)
            metadata["id"] = idx
            normalized_doc = Document(page_content=text, metadata=metadata)
            tokens = self._tokenize(text)
            if not tokens:
                raise ValueError(f"BM25 分词结果为空: index={idx}")

            self.documents.append(normalized_doc)
            self.tokenized_docs.append(tokens)
            term_freq = Counter(tokens)
            self.term_freqs.append(term_freq)
            self.doc_lengths.append(len(tokens))
            self.doc_freq.update(term_freq.keys())

        self.avg_doc_len = sum(self.doc_lengths) / len(self.doc_lengths)
        self.idf = {
            term: math.log(1 + (len(self.documents) - df + 0.5) / (df + 0.5))
            for term, df in self.doc_freq.items()
        }

    def GetBM25TopK(self, query: str, topk: int) -> List[Document]:
        """返回 BM25 Top-K 文档。"""
        return [doc for doc, _score in self.GetBM25TopKWithScores(query, topk)]

    def GetBM25TopKWithScores(self, query: str, topk: int) -> List[Tuple[Document, float]]:
        """返回 BM25 Top-K 文档和分数。"""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            raise ValueError("BM25 查询分词结果为空")

        scored: list[tuple[Document, float]] = []
        for idx, doc in enumerate(self.documents):
            score = self._score(query_tokens, idx)
            if score <= 0:
                continue
            score += self._phrase_boost(query, doc.page_content)
            scored.append((doc, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:topk]

    def _score(self, query_tokens: list[str], doc_index: int) -> float:
        score = 0.0
        term_freq = self.term_freqs[doc_index]
        doc_len = self.doc_lengths[doc_index]

        for token in query_tokens:
            tf = term_freq.get(token, 0)
            if tf == 0:
                continue
            idf = self.idf.get(token, 0.0)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_len)
            score += idf * numerator / denominator

        return score

    def _phrase_boost(self, query: str, text: str) -> float:
        normalized_query = self._normalize(query)
        normalized_text = self._normalize(text)
        boost = 0.0

        if normalized_query and normalized_query in normalized_text:
            boost += 8.0

        key_phrases = [
            "学生证补办",
            "学分制收费",
            "成绩复核",
            "自助打印",
            "学籍异动",
            "毕业论文",
            "通识核心课",
            "休学",
            "复学",
            "退学",
        ]
        for phrase in key_phrases:
            if phrase in normalized_query and phrase in normalized_text:
                boost += 4.0

        return boost

    def _tokenize(self, text: str) -> list[str]:
        normalized = self._normalize(text)
        tokens = []
        for token in jieba.cut_for_search(normalized):
            token = token.strip()
            if not token:
                continue
            if token in {"的", "了", "和", "及", "与", "在", "是", "吗", "呢"}:
                continue
            tokens.append(token)
        return tokens

    def _normalize(self, text: str) -> str:
        return (
            text.strip()
            .lower()
            .replace("哪里", "哪")
            .replace("在哪儿", "在哪")
            .replace("如何", "怎么")
            .replace("办理地点", "地点")
            .replace("办事地点", "地点")
            .replace("收费标准", "收费")
            .replace("多少钱", "收费")
            .replace("费用", "收费")
        )


if __name__ == "__main__":
    documents = load_knowledge_documents("./data/kb_docs", faq_path="./data/faq_database.json")
    print(len(documents))

    bm25 = BM25(documents)
    res = bm25.GetBM25TopKWithScores("学生证补办地点在哪？", 6)
    for doc, score in res:
        print(score, doc.metadata, doc.page_content[:120])
