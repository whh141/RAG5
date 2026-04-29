#!/usr/bin/env python
# coding: utf-8

from typing import Any, Dict

from fastapi import APIRouter

from server.deps import get_runtime


router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> Dict[str, Any]:
    status = get_runtime().status.as_dict()
    status["entry"] = "fastapi_server"
    return status
