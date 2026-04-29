#!/usr/bin/env python
# coding: utf-8

import asyncio
import shutil
from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from agent.runtime import KB_DIR
from server.deps import MAX_UPLOAD_BYTES, get_runtime, require_token, safe_kb_path
from server.schemas import KbFileInfo, KbFilesResponse, KbStatus


router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])


def _list_kb_files() -> List[KbFileInfo]:
    runtime = get_runtime()
    if not KB_DIR.exists():
        return []

    supported = set(runtime.supported_extensions())
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


def _status() -> KbStatus:
    runtime = get_runtime()
    status = runtime.status.as_dict()
    return KbStatus(
        **status,
        file_count=len(_list_kb_files()),
        supported_extensions=runtime.supported_extensions(),
    )


@router.get("/status", response_model=KbStatus)
def kb_status() -> KbStatus:
    return _status()


@router.get("/files", response_model=KbFilesResponse)
def kb_files() -> KbFilesResponse:
    return KbFilesResponse(files=_list_kb_files())


@router.post("/upload", dependencies=[Depends(require_token)])
async def upload_kb_files(files: List[UploadFile] = File(...)) -> Dict[str, object]:
    if not files:
        raise HTTPException(status_code=400, detail="请选择要上传的知识库文件")

    runtime = get_runtime()
    supported = set(runtime.supported_extensions())
    KB_DIR.mkdir(parents=True, exist_ok=True)
    saved: List[str] = []

    for item in files:
        target = safe_kb_path(item.filename or "")
        if target.suffix.lower() not in supported:
            raise HTTPException(status_code=400, detail=f"当前未注册 {target.suffix or '无后缀'} 文件解析器")

        size = 0
        with target.open("wb") as output:
            while True:
                chunk = await item.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    target.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="上传文件超过大小限制")
                output.write(chunk)
        saved.append(target.name)

    runtime.mark_needs_rebuild()
    return {"saved": saved, "status": _status().model_dump()}


@router.delete("/files/{filename}", dependencies=[Depends(require_token)])
def delete_kb_file(filename: str) -> Dict[str, object]:
    target = safe_kb_path(filename)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="知识库文件不存在")

    target.unlink()
    get_runtime().mark_needs_rebuild()
    return {"deleted": target.name, "status": _status().model_dump()}


@router.post("/rebuild", response_model=KbStatus, dependencies=[Depends(require_token)])
async def rebuild_kb() -> KbStatus:
    runtime = get_runtime()
    if runtime.status.rebuilding:
        raise HTTPException(status_code=409, detail="知识库正在重新向量化")
    try:
        await asyncio.to_thread(runtime.rebuild_knowledge_base)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _status()
