#!/usr/bin/env python
# coding: utf-8
"""
会话 API 与聊天持久化 smoke test。

使用临时 SQLite 和 fake runtime，不写入 data/conversations.sqlite3。
"""

import csv
import json
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from server.storage import ConversationStore  # noqa: E402
import server.api.chat as chat_api  # noqa: E402
import server.api.conversations as conversation_api  # noqa: E402


OUT_DIR = Path(__file__).resolve().parent
REPORT_PATH = OUT_DIR / "conversation_smoke_report.json"
RESULTS_CSV = OUT_DIR / "conversation_smoke_results.csv"


class FakeStatus:
    rebuilding = False


class FakeRuntime:
    status = FakeStatus()

    def __init__(self, calls: list[dict]) -> None:
        self.calls = calls

    def invoke(self, message: str, history: list[dict]):
        self.calls.append({"message": message, "history": history})
        return (
            {
                "final_answer": f"答复:{message}",
                "intent": "simple_fact",
                "route": "retrieve_local",
                "route_reason": "smoke test",
                "query_rewrite": message,
                "answer_source": "local_rag",
                "confidence": 1.0,
                "citations": [],
                "evidence_items": [],
                "sub_results": [],
                "trace": [{"stage": "fake_runtime"}],
            },
            0.01,
        )


def main() -> None:
    results: list[dict] = []
    calls: list[dict] = []

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        store = ConversationStore(Path(tmp) / "conversation_smoke.sqlite3")
        store.init_db()
        conversation_api.conversation_store = store
        chat_api.conversation_store = store
        chat_api.get_runtime = lambda: FakeRuntime(calls)

        app = FastAPI()
        app.include_router(conversation_api.router)
        app.include_router(chat_api.router)
        client = TestClient(app)

        sid = None
        sid = run_step(results, "初始会话列表为空", lambda: assert_equal(
            client.get("/api/conversations").json(),
            {"conversations": []},
        )) or sid

        created = {}
        run_step(results, "创建会话", lambda: created.update(
            {"conversation": assert_status(client.post("/api/conversations"), 200).json()["conversation"]}
        ))
        sid = created["conversation"]["id"]

        run_step(results, "空会话详情可读取", lambda: assert_equal(
            client.get(f"/api/conversations/{sid}").json()["messages"],
            [],
        ))

        run_step(results, "第一轮聊天写入成功", lambda: assert_status(
            client.post("/api/chat", json={"session_id": sid, "message": "第一问"}),
            200,
        ))

        run_step(results, "第一轮聊天无历史输入", lambda: assert_equal(calls[-1]["history"], []))

        run_step(results, "第二轮聊天写入成功", lambda: assert_status(
            client.post("/api/chat", json={"session_id": sid, "message": "第二问"}),
            200,
        ))

        run_step(results, "第二轮自动读取上一轮历史", lambda: assert_equal(len(calls[-1]["history"]), 2))

        run_step(results, "消息顺序为 user/assistant/user/assistant", lambda: assert_equal(
            [
                item["role"]
                for item in client.get(f"/api/conversations/{sid}").json()["messages"]
            ],
            ["user", "assistant", "user", "assistant"],
        ))

        run_step(results, "首条用户消息自动生成标题", lambda: assert_equal(
            client.get(f"/api/conversations/{sid}").json()["conversation"]["title"],
            "第一问",
        ))

        run_step(results, "重命名会话成功", lambda: assert_equal(
            client.patch(f"/api/conversations/{sid}", json={"title": "重命名"}).json()["title"],
            "重命名",
        ))

        run_step(results, "空消息返回 422", lambda: assert_equal(
            client.post("/api/chat", json={"session_id": sid, "message": ""}).status_code,
            422,
        ))

        run_step(results, "无效 session 返回 404", lambda: assert_equal(
            client.post("/api/chat", json={"session_id": "missing", "message": "test"}).status_code,
            404,
        ))

        run_step(results, "删除会话成功", lambda: assert_equal(
            client.delete(f"/api/conversations/{sid}").json()["deleted"],
            sid,
        ))

        run_step(results, "删除后详情返回 404", lambda: assert_equal(
            client.get(f"/api/conversations/{sid}").status_code,
            404,
        ))

    passed = sum(1 for item in results if item["status"] == "PASS")
    report = {
        "experiment": "conversation_persistence_smoke",
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(passed / len(results), 4) if results else 0.0,
        "uses_production_db": False,
        "results": results,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_results(results)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def run_step(results: list[dict], test_item: str, fn):
    started = time.perf_counter()
    try:
        value = fn()
        results.append({
            "test_item": test_item,
            "status": "PASS",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "note": "",
        })
        return value
    except Exception as exc:
        results.append({
            "test_item": test_item,
            "status": "FAIL",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "note": str(exc),
        })
        return None


def assert_status(response, expected_status: int):
    if response.status_code != expected_status:
        raise AssertionError(f"expected {expected_status}, got {response.status_code}: {response.text}")
    return response


def assert_equal(actual, expected):
    if actual != expected:
        raise AssertionError(f"expected {expected!r}, got {actual!r}")
    return actual


def write_results(results: list[dict]) -> None:
    with RESULTS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["test_item", "status", "elapsed_ms", "note"])
        writer.writeheader()
        writer.writerows(results)


if __name__ == "__main__":
    main()
