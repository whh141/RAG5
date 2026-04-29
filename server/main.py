#!/usr/bin/env python
# coding: utf-8
"""Production-oriented FastAPI entrypoint."""

import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from server.api.chat import router as chat_router
from server.api.conversations import router as conversations_router
from server.api.health import router as health_router
from server.api.kb import router as kb_router
from server.deps import STATIC_DIR, get_runtime
from server.storage import conversation_store


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    conversation_store.init_db()
    get_runtime().ensure_ready()
    yield


app = FastAPI(title="Campus RAG QA", version="2.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(health_router)
app.include_router(conversations_router)
app.include_router(chat_router)
app.include_router(kb_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/styles.css", include_in_schema=False)
def root_styles() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "styles.css",
        media_type="text/css",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/app.js", include_in_schema=False)
def root_script() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "app.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )
