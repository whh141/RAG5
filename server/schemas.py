#!/usr/bin/env python
# coding: utf-8
"""HTTP schemas for the FastAPI server."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str = Field(min_length=1)


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


class KbFilesResponse(BaseModel):
    files: List[KbFileInfo]


class KbStatus(BaseModel):
    ready: bool
    rebuilding: bool
    needs_rebuild: bool
    last_rebuild_at: Optional[str]
    last_error: Optional[str]
    document_count: int
    file_count: int
    supported_extensions: List[str]


class ConversationInfo(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class ConversationsResponse(BaseModel):
    conversations: List[ConversationInfo]


class ConversationCreateResponse(BaseModel):
    conversation: ConversationInfo


class ConversationDetail(BaseModel):
    conversation: ConversationInfo
    messages: List[ChatMessage]


class ConversationRenameRequest(BaseModel):
    title: str = Field(min_length=1)
