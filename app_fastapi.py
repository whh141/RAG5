#!/usr/bin/env python
# coding: utf-8
"""
FastAPI + Vue 前端入口。
该入口只封装现有 Agent 调用，不改变路由、RAG、联网检索、答案合成或评测逻辑。
"""

import asyncio
import shutil
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import app_gradio
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


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web_vue"
STATIC_DIR = WEB_DIR / "static"
VUE_RUNTIME = WEB_DIR / "node_modules" / "vue" / "dist" / "vue.global.prod.js"
KB_DIR = BASE_DIR / "data" / "kb_docs"
FAQ_PATH = BASE_DIR / "data" / "faq_database.json"
_init_lock = Lock()
_kb_lock = Lock()
_kb_status: Dict[str, Any] = {
    "rebuilding": False,
    "needs_rebuild": False,
    "last_rebuild_at": None,
    "last_error": None,
    "document_count": 0,
}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: List[ChatMessage] = Field(default_factory=list)
    session_id: str = "default"


class ChatResponse(BaseModel):
    answer: str
    elapsed_time: float
    intent: str
    route: str
    route_reason: str
    query_rewrite: str
    answer_source: str
    confidence: float
    citations: List[Dict[str, Any]]
    evidence_items: List[Dict[str, Any]]
    sub_results: List[Dict[str, Any]]
    trace: List[Dict[str, Any]]


class KbFileInfo(BaseModel):
    name: str
    extension: str
    size: int
    updated_at: str


class KbStatus(BaseModel):
    rebuilding: bool
    needs_rebuild: bool
    last_rebuild_at: Optional[str]
    last_error: Optional[str]
    document_count: int
    file_count: int
    supported_extensions: List[str]


app = FastAPI(title="Campus RAG QA", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/vendor/vue.global.prod.js")
def vue_runtime() -> FileResponse:
    if not VUE_RUNTIME.exists():
        raise HTTPException(
            status_code=500,
            detail="Vue runtime missing. Run: npm.cmd install --prefix web_vue",
        )
    return FileResponse(VUE_RUNTIME)


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "ready": app_gradio.agent_graph is not None,
        "entry": "fastapi_vue",
    }


@app.get("/api/kb/status", response_model=KbStatus)
def kb_status() -> KbStatus:
    return _current_kb_status()


@app.get("/api/kb/files", response_model=List[KbFileInfo])
def kb_files() -> List[KbFileInfo]:
    return _list_kb_files()


@app.post("/api/kb/upload")
async def upload_kb_files(files: List[UploadFile] = File(...)) -> Dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="请选择要上传的知识库文件")

    saved: List[str] = []
    supported = set(supported_knowledge_extensions())
    validated: List[tuple[UploadFile, Path]] = []
    KB_DIR.mkdir(parents=True, exist_ok=True)

    with _kb_lock:
        for item in files:
            target = _safe_kb_path(item.filename or "")
            extension = target.suffix.lower()
            if extension not in supported:
                raise HTTPException(
                    status_code=400,
                    detail=f"当前未注册 {extension or '无后缀'} 文件解析器",
                )
            validated.append((item, target))

        for item, target in validated:
            with target.open("wb") as output:
                shutil.copyfileobj(item.file, output)
            saved.append(target.name)

        _kb_status["needs_rebuild"] = True
        _kb_status["last_error"] = None

    return {"saved": saved, "status": _current_kb_status().model_dump()}


@app.delete("/api/kb/files/{filename}")
def delete_kb_file(filename: str) -> Dict[str, Any]:
    target = _safe_kb_path(filename)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="知识库文件不存在")

    with _kb_lock:
        target.unlink()
        _kb_status["needs_rebuild"] = True
        _kb_status["last_error"] = None

    return {"deleted": target.name, "status": _current_kb_status().model_dump()}


@app.post("/api/kb/rebuild", response_model=KbStatus)
async def rebuild_kb() -> KbStatus:
    if _kb_status["rebuilding"]:
        raise HTTPException(status_code=409, detail="知识库正在重新向量化")

    try:
        await asyncio.to_thread(_rebuild_knowledge_base)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _current_kb_status()


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message cannot be empty")
    if _kb_status["rebuilding"]:
        raise HTTPException(status_code=409, detail="知识库正在重新向量化，请稍后再问")

    history = [
        {"role": item.role, "content": item.content}
        for item in request.history
    ]

    try:
        result, elapsed_time = await asyncio.to_thread(_invoke_agent, message, history)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(
        answer=result.get("final_answer", "") or "",
        elapsed_time=elapsed_time,
        intent=result.get("intent", ""),
        route=result.get("route", ""),
        route_reason=result.get("route_reason", ""),
        query_rewrite=result.get("query_rewrite", ""),
        answer_source=result.get("answer_source", ""),
        confidence=float(result.get("confidence", 0.0)),
        citations=result.get("citations", []) or [],
        evidence_items=result.get("evidence_items", []) or [],
        sub_results=result.get("sub_results", []) or [],
        trace=result.get("trace", []) or [],
    )


def _invoke_agent(message: str, history: List[Dict[str, str]]) -> tuple[Dict[str, Any], float]:
    _ensure_initialized()
    start_time = time.time()
    with _kb_lock:
        result = app_gradio.agent_graph.invoke(_initial_state(message, history))
    elapsed_time = time.time() - start_time
    return result, elapsed_time


def _ensure_initialized() -> None:
    if app_gradio.agent_graph is not None:
        return
    with _init_lock:
        if app_gradio.agent_graph is None:
            _rebuild_knowledge_base()


def _initial_state(message: str, history: List[Dict[str, str]]) -> AgentState:
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


def _current_kb_status() -> KbStatus:
    return KbStatus(
        rebuilding=bool(_kb_status["rebuilding"]),
        needs_rebuild=bool(_kb_status["needs_rebuild"]),
        last_rebuild_at=_kb_status["last_rebuild_at"],
        last_error=_kb_status["last_error"],
        document_count=int(_kb_status["document_count"]),
        file_count=len(_list_kb_files()),
        supported_extensions=supported_knowledge_extensions(),
    )


def _list_kb_files() -> List[KbFileInfo]:
    if not KB_DIR.exists():
        return []

    supported = set(supported_knowledge_extensions())
    files: List[KbFileInfo] = []
    for path in sorted(KB_DIR.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or path.suffix.lower() not in supported:
            continue
        stat = path.stat()
        files.append(
            KbFileInfo(
                name=path.name,
                extension=path.suffix.lower(),
                size=stat.st_size,
                updated_at=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            )
        )
    return files


def _safe_kb_path(filename: str) -> Path:
    safe_name = Path(filename).name
    if not safe_name or safe_name != filename:
        raise HTTPException(status_code=400, detail="文件名非法")

    target = (KB_DIR / safe_name).resolve()
    kb_root = KB_DIR.resolve()
    if target.parent != kb_root:
        raise HTTPException(status_code=400, detail="文件路径非法")
    return target


def _rebuild_knowledge_base() -> None:
    with _kb_lock:
        _kb_status["rebuilding"] = True
        _kb_status["last_error"] = None
        try:
            document_count = _rebuild_agent_runtime()
            _kb_status["document_count"] = document_count
            _kb_status["last_rebuild_at"] = datetime.now().isoformat(timespec="seconds")
            _kb_status["needs_rebuild"] = False
        except Exception as exc:
            _kb_status["last_error"] = str(exc)
            raise
        finally:
            _kb_status["rebuilding"] = False


def _rebuild_agent_runtime() -> int:
    documents = load_knowledge_documents(
        kb_dir=str(KB_DIR),
        faq_path=str(FAQ_PATH),
    )

    faiss_retriever = FaissRetriever(documents=documents)
    bm25_retriever = BM25(documents)
    llm = get_llm_model(
        model_path=str(BASE_DIR / "pre_train_model" / "Qwen-7B-Chat"),
        backend=LLM_BACKEND,
    )
    rerank = reRankLLM()

    rag_tool = RAGTool(
        faiss_retriever=faiss_retriever,
        bm25_retriever=bm25_retriever,
        rerank_model=rerank,
        llm=llm,
    )
    tavily_tool = TavilyTool(max_results=5) if ModelConfig.TAVILY_API_KEY else None

    set_tools(rag_tool, tavily_tool)
    app_gradio.agent_graph = build_agent_graph()
    return len(documents)


if __name__ == "__main__":
    import uvicorn

    _ensure_initialized()
    uvicorn.run(
        "app_fastapi:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )
