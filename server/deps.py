#!/usr/bin/env python
# coding: utf-8
"""Shared FastAPI dependencies."""

import os
from pathlib import Path
from typing import Optional

from fastapi import Header, HTTPException

from agent.runtime import BASE_DIR, KB_DIR, runtime


STATIC_DIR = BASE_DIR / "server" / "static"
MAX_UPLOAD_BYTES = int(os.getenv("RAG_MAX_UPLOAD_BYTES", str(30 * 1024 * 1024)))
API_TOKEN = os.getenv("RAG_API_TOKEN", "").strip()


def require_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not API_TOKEN:
        return
    expected = f"Bearer {API_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="认证失败")


def safe_kb_path(filename: str) -> Path:
    safe_name = Path(filename).name
    if not safe_name or safe_name != filename:
        raise HTTPException(status_code=400, detail="文件名非法")

    target = (KB_DIR / safe_name).resolve()
    kb_root = KB_DIR.resolve()
    if target.parent != kb_root:
        raise HTTPException(status_code=400, detail="文件路径非法")
    return target


def get_runtime():
    return runtime
