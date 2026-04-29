#!/usr/bin/env python
# coding: utf-8
"""Shared Agent runtime independent of Gradio and FastAPI."""

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from agent.config.model_config import ModelConfig
from agent.graph import build_agent_graph
from agent.nodes.tool_executor import set_tools
from agent.state import AgentState
from agent.tools import RAGTool, TavilyTool
from bm25_retriever import BM25
from config import LLM_BACKEND
from faiss_retriever import FaissRetriever
from llm_model import get_llm_model
from pdf_parse import load_knowledge_documents, supported_knowledge_extensions
from rerank_model import reRankLLM


BASE_DIR = Path(__file__).resolve().parents[1]
KB_DIR = BASE_DIR / "data" / "kb_docs"
FAQ_PATH = BASE_DIR / "data" / "faq_database.json"
MODEL_PATH = BASE_DIR / "pre_train_model" / "Qwen-7B-Chat"


@dataclass
class RuntimeStatus:
    ready: bool = False
    rebuilding: bool = False
    needs_rebuild: bool = False
    last_rebuild_at: Optional[str] = None
    last_error: Optional[str] = None
    document_count: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ready": self.ready,
            "rebuilding": self.rebuilding,
            "needs_rebuild": self.needs_rebuild,
            "last_rebuild_at": self.last_rebuild_at,
            "last_error": self.last_error,
            "document_count": self.document_count,
        }


class AgentRuntime:
    """Owns the single Agent graph and knowledge-base lifecycle."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._status = RuntimeStatus()
        self._graph = None

    @property
    def status(self) -> RuntimeStatus:
        return self._status

    def ensure_ready(self) -> None:
        if self._graph is not None and self._status.ready:
            return
        self.rebuild_knowledge_base()

    def invoke(self, message: str, history: List[Dict[str, str]]) -> tuple[Dict[str, Any], float]:
        self.ensure_ready()
        if self._status.rebuilding:
            raise RuntimeError("知识库正在重新向量化，请稍后再问")

        start_time = time.time()
        with self._lock:
            result = self._graph.invoke(self._initial_state(message, history))
        return result, time.time() - start_time

    def rebuild_knowledge_base(self) -> None:
        with self._lock:
            self._status.rebuilding = True
            self._status.ready = False
            self._status.last_error = None
            try:
                documents = load_knowledge_documents(
                    kb_dir=str(KB_DIR),
                    faq_path=str(FAQ_PATH),
                )

                faiss_retriever = FaissRetriever(documents=documents)
                bm25_retriever = BM25(documents)
                llm = get_llm_model(model_path=str(MODEL_PATH), backend=LLM_BACKEND)
                rerank = reRankLLM()

                rag_tool = RAGTool(
                    faiss_retriever=faiss_retriever,
                    bm25_retriever=bm25_retriever,
                    rerank_model=rerank,
                    llm=llm,
                )
                tavily_tool = TavilyTool(max_results=5) if ModelConfig.TAVILY_API_KEY else None

                set_tools(rag_tool, tavily_tool)
                self._graph = build_agent_graph()
                self._status.document_count = len(documents)
                self._status.last_rebuild_at = datetime.now().isoformat(timespec="seconds")
                self._status.needs_rebuild = False
                self._status.ready = True
            except Exception as exc:
                self._graph = None
                self._status.last_error = str(exc)
                self._status.ready = False
                raise
            finally:
                self._status.rebuilding = False

    def mark_needs_rebuild(self) -> None:
        self._status.needs_rebuild = True
        self._status.last_error = None

    def supported_extensions(self) -> List[str]:
        return supported_knowledge_extensions()

    def _initial_state(self, message: str, history: List[Dict[str, str]]) -> AgentState:
        return {
            "user_question": message,
            "conversation_history": history,
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


runtime = AgentRuntime()
