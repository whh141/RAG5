#!/usr/bin/env python
# coding: utf-8

from fastapi import APIRouter, Depends, HTTPException

from server.deps import require_token
from server.schemas import (
    ConversationCreateResponse,
    ConversationDetail,
    ConversationInfo,
    ConversationRenameRequest,
    ConversationsResponse,
)
from server.storage import conversation_store


router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _conversation_info(data: dict) -> ConversationInfo:
    return ConversationInfo(**data)


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("", response_model=ConversationsResponse)
def list_conversations() -> ConversationsResponse:
    return ConversationsResponse(
        conversations=[_conversation_info(item) for item in conversation_store.list_conversations()]
    )


@router.post("", response_model=ConversationCreateResponse, dependencies=[Depends(require_token)])
def create_conversation() -> ConversationCreateResponse:
    conversation = conversation_store.create_conversation()
    return ConversationCreateResponse(conversation=_conversation_info(conversation))


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str) -> ConversationDetail:
    try:
        conversation = conversation_store.require_conversation(conversation_id)
        messages = conversation_store.get_messages(conversation_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    return ConversationDetail(
        conversation=_conversation_info(conversation),
        messages=messages,
    )


@router.patch("/{conversation_id}", response_model=ConversationInfo, dependencies=[Depends(require_token)])
def rename_conversation(
    conversation_id: str,
    request: ConversationRenameRequest,
) -> ConversationInfo:
    try:
        conversation = conversation_store.rename_conversation(conversation_id, request.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise _not_found(exc) from exc
    return _conversation_info(conversation)


@router.delete("/{conversation_id}", dependencies=[Depends(require_token)])
def delete_conversation(conversation_id: str) -> dict:
    try:
        conversation_store.delete_conversation(conversation_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    return {"deleted": conversation_id}
