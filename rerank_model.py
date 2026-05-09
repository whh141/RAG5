#!/usr/bin/env python
# coding: utf-8
"""
Rerank 模型统一接口
支持本地模型 (transformers) 和 API 服务 (LangChain)
"""

import os
import torch
import torch.nn.functional as F
from typing import List, Optional

from langchain_core.documents import Document

# LangChain Rerankers
try:
    from langchain_community.document_compressors import CohereRerank, JinaRerank
except ImportError:
    CohereRerank = None
    JinaRerank = None

# transformers
try:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
except ImportError:
    AutoModelForSequenceClassification = None
    AutoTokenizer = None

from config import (
    RERANK_BACKEND,
    RERANK_API_PROVIDER,
    RERANK_MODEL_PATH,
    RERANK_API_KEY,
    RERANK_API_BASE,
    RERANK_MODEL_NAME,
    RERANK_TOP_N,
    LLM_DEVICE,
)

os.environ["TOKENIZERS_PARALLELISM"] = "false"


def get_rerank_model(
    model_path: Optional[str] = None,
    backend: Optional[str] = None,
    provider: Optional[str] = None,
):
    """
    获取 Rerank 模型
    
    根据配置返回相应的 Reranker:
    - backend="local": 本地 transformers 模型
    - backend="api" + provider="cohere": Cohere API (LangChain)
    - backend="api" + provider="jina": Jina AI API (自定义适配器)
    
    Args:
        model_path: 本地模型路径（可选，如果提供则强制使用本地模型）
        backend: 后端类型 "local" 或 "api"（可选，默认从配置读取）
        provider: API 服务商 "cohere", "jina"（可选，默认从配置读取）
    
    Returns:
        Reranker 实例
    """
    # 如果显式提供 model_path，强制使用本地模型
    if model_path:
        backend = "local"
    
    backend = (backend or RERANK_BACKEND).lower()
    provider = (provider or RERANK_API_PROVIDER).lower()
    
    if backend == "api":
        return _get_api_reranker(provider)
    else:
        return _get_local_reranker(model_path or RERANK_MODEL_PATH)


def _get_local_reranker(model_path: str):
    """获取本地 Reranker (使用 transformers)"""
    if AutoModelForSequenceClassification is None or AutoTokenizer is None:
        raise ImportError(
            "transformers 需要安装: pip install transformers torch"
        )
    
    print(f"  [Rerank] 加载本地模型: {model_path}")
    
    return _LocalBGEReranker(
        model_path=model_path,
        top_n=RERANK_TOP_N,
    )


def _get_api_reranker(provider: str):
    """获取 API Reranker"""
    print(f"  [Rerank] 使用 API: {provider}")
    print(f"  [Rerank] 模型: {RERANK_MODEL_NAME}")
    
    if provider == "cohere":
        if CohereRerank is None:
            raise ImportError(
                "CohereRerank 需要安装: pip install langchain-community cohere"
            )
        
        return CohereRerank(
            cohere_api_key=RERANK_API_KEY,
            model=RERANK_MODEL_NAME,
            top_n=RERANK_TOP_N,
        )
    
    elif provider == "jina":
        # Jina 使用自定义实现（不依赖 LangChain）
        return _JinaRerankAdapter(
            api_key=RERANK_API_KEY,
            api_base=RERANK_API_BASE or "https://api.jina.ai",
            model=RERANK_MODEL_NAME,
            top_n=RERANK_TOP_N,
        )
    
    else:
        raise ValueError(f"不支持的 API 服务商: {provider}")

class _LocalBGEReranker:
    """本地 BGE Rerank 模型 (使用 transformers)"""

    def __init__(self, model_path: str, top_n: int = 10, max_length: int = 512):
        self.model_path = model_path
        self.top_n = top_n
        self.max_length = max_length

        self.device = (
            "cuda"
            if LLM_DEVICE == "cuda" and torch.cuda.is_available()
            else "cpu"
        )

        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
        self.model.eval()
        self.model.to(self.device)

        if self.device == "cuda":
            self.model.half()

    def _extract_relevance_scores(self, logits: torch.Tensor) -> torch.Tensor:
        """
        把模型输出变成“每个文档一个相关性分数”。

        支持：
        - [N]            已经是一维分数
        - [N, 1]         单标签/回归式 rerank
        - [N, 2+]        分类式 rerank，取“相关”类别概率或 logit
        """
        if logits.ndim == 1:
            return logits

        if logits.ndim != 2:
            raise ValueError(f"不支持的 logits 维度: {tuple(logits.shape)}")

        num_labels = logits.shape[-1]

        if num_labels == 1:
            return logits.squeeze(-1)

        # 尽量从配置里找“相关/positive”标签
        positive_idx = None

        id2label = getattr(self.model.config, "id2label", None)
        if isinstance(id2label, dict):
            for idx, label in id2label.items():
                label_text = str(label).strip().lower()
                if label_text in {
                    "relevant", "relevance", "positive", "pos",
                    "yes", "true", "entailment", "similar"
                }:
                    positive_idx = int(idx)
                    break

        if positive_idx is None and num_labels == 2:
            # 对二分类 rerank，默认第二列是“更相关”是最常见约定
            positive_idx = 1

        if positive_idx is None:
            raise ValueError(
                f"无法从 logits shape={tuple(logits.shape)} 推断相关性列，"
                f"id2label={getattr(self.model.config, 'id2label', None)}"
            )

        # 用 softmax 后的相关类概率做排序分数，更稳定
        probs = F.softmax(logits, dim=-1)
        return probs[:, positive_idx]

    def compress_documents(
        self,
        documents: List[Document],
        query: str,
    ) -> List[Document]:
        if not documents:
            return []

        pairs = [(query, doc.page_content) for doc in documents]
        inputs = self.tokenizer(
            pairs,
            padding=True,
            truncation=True,
            return_tensors="pt",
            max_length=self.max_length,
        ).to(self.device)

        with torch.no_grad():
            logits = self.model(**inputs).logits

        scores = self._extract_relevance_scores(logits)

        if scores.ndim != 1:
            raise ValueError(f"relevance scores 必须是一维，当前 shape={tuple(scores.shape)}")

        if scores.shape[0] != len(documents):
            raise ValueError(
                f"分数数量与文档数量不一致: scores={scores.shape[0]}, docs={len(documents)}"
            )

        sorted_indices = torch.argsort(scores, descending=True).tolist()
        result = [documents[i] for i in sorted_indices[: self.top_n]]

        if self.device == "cuda":
            torch.cuda.empty_cache()

        return result

class _JinaRerankAdapter:
    """Jina AI Rerank 适配器"""
    
    def __init__(self, api_key: str, api_base: str, model: str, top_n: int = 10):
        self.api_key = api_key
        self.api_base = api_base.rstrip('/')
        self.model = model
        self.top_n = top_n
    
    def compress_documents(
        self,
        documents: List[Document],
        query: str,
    ) -> List[Document]:
        """
        压缩（重排序）文档
        
        Args:
            documents: 文档列表
            query: 查询文本
            
        Returns:
            重排序后的文档列表
        """
        import requests
        
        doc_texts = [doc.page_content for doc in documents]
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        
        payload = {
            "model": self.model,
            "query": query,
            "documents": doc_texts,
            "top_n": str(min(self.top_n, len(doc_texts))),  # Jina 需要字符串
            "return_documents": False,
        }
        
        response = requests.post(
            self.api_base,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        result = response.json()
        ranked_indices = [item["index"] for item in result.get("results", [])]
        if not ranked_indices:
            raise ValueError("Jina Rerank API 未返回排序结果")

        return [documents[idx] for idx in ranked_indices]


class reRankLLM:
    """
    向后兼容的 Rerank 类
    保持原有的 predict() 接口，内部使用 LangChain Reranker
    """
    
    def __init__(self, model_path: Optional[str] = None, max_length: int = 512):
        """
        Args:
            model_path: 模型路径（可选，如果提供则强制使用本地模型）
            max_length: 最大序列长度（保留参数以兼容旧代码，但不使用）
        """
        self.reranker = get_rerank_model(model_path=model_path)
        self.max_length = max_length  # 保留以兼容旧代码
    
    def predict(self, query: str, docs: List[Document]) -> List[Document]:
        """
        对文档进行重排序
        
        Args:
            query: 查询文本
            docs: 文档列表
            
        Returns:
            按相关性排序的文档列表
        """
        if not docs:
            return []
        
        return self.reranker.compress_documents(
            documents=docs,
            query=query,
        )


if __name__ == "__main__":
    # 测试
    print("测试 Rerank 模型...")
    
    from pdf_parse import load_knowledge_documents
#from pdf_parse import DataProcess
    from bm25_retriever import BM25
    
    # 准备测试数据
    documents = load_knowledge_documents("./data/kb_docs", faq_path="./data/faq_database.json")
    bm25 = BM25(documents)

    #dp = DataProcess(pdf_path="./data/train_a.pdf")
    #dp.ParseBlock(max_seq=512)
    
    #bm25 = BM25(dp.data)
    
    query = "吉利银河E8的续航"
    docs = bm25.GetBM25TopK(query, 10)
    
    # 测试 Rerank
    rerank = reRankLLM()
    reranked_docs = rerank.predict(query, docs)
    
    print(f"\n重排序完成，返回 {len(reranked_docs)} 个文档")

