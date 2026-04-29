#!/usr/bin/env python
# coding: utf-8

import asyncio
import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from server.deps import get_runtime, require_token
from server.schemas import ChatRequest, ChatResponse
from server.storage import conversation_store


router = APIRouter(prefix="/api/chat", tags=["chat"])


def _history_payload(session_id: str) -> List[Dict[str, str]]:
    return [
        {"role": item["role"], "content": item["content"]}
        for item in conversation_store.get_messages(session_id)
    ]


def _chat_response(result: Dict[str, Any], elapsed_time: float) -> ChatResponse:
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


def _sse(event: str, payload: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("", response_model=ChatResponse, dependencies=[Depends(require_token)])
async def chat(request: ChatRequest) -> ChatResponse:
    runtime = get_runtime()
    if runtime.status.rebuilding:
        raise HTTPException(status_code=409, detail="知识库正在重新向量化，请稍后再问")

    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="消息不能为空")

    try:
        conversation_store.require_conversation(request.session_id)
        history = _history_payload(request.session_id)
        result, elapsed_time = await asyncio.to_thread(
            runtime.invoke,
            message,
            history,
        )
        response = _chat_response(result, elapsed_time)
        conversation_store.append_exchange(request.session_id, message, response.answer)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return response


@router.post("/stream", dependencies=[Depends(require_token)])
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    runtime = get_runtime()
    if runtime.status.rebuilding:
        raise HTTPException(status_code=409, detail="知识库正在重新向量化，请稍后再问")

    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="消息不能为空")
    try:
        conversation_store.require_conversation(request.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    async def event_generator():
        yield _sse("status", {"message": "开始处理"})
        yield _sse("status", {"message": "初始化运行时"})
        try:
            history = _history_payload(request.session_id)
            result, elapsed_time = await asyncio.to_thread(
                runtime.invoke,
                message,
                history,
            )
            response_model = _chat_response(result, elapsed_time)
            conversation_store.append_exchange(request.session_id, message, response_model.answer)
            response = response_model.model_dump()
            for item in response["trace"]:
                stage = item.get("stage")
                if stage:
                    yield _sse("trace", item)
            answer = response.get("answer", "") or ""
            for start in range(0, len(answer), 24):
                yield _sse("token", {"content": answer[start : start + 24]})
            yield _sse("done", response)
        except Exception as exc:
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")
