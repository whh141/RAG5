#!/usr/bin/env python
# coding: utf-8
"""SQLite-backed conversation storage."""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional

from agent.runtime import BASE_DIR


DB_PATH = BASE_DIR / "data" / "conversations.sqlite3"


class ConversationStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._lock = Lock()

    def init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_conversations_updated_at
                    ON conversations(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
                    ON messages(conversation_id, id);
                """
            )

    def create_conversation(self, title: str = "新对话") -> Dict[str, str]:
        now = self._now()
        conversation_id = uuid.uuid4().hex
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, title, now, now),
            )
        return {"id": conversation_id, "title": title, "created_at": now, "updated_at": now}

    def list_conversations(self) -> List[Dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM conversations
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, str]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM conversations
                WHERE id = ?
                """,
                (conversation_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_messages(self, conversation_id: str) -> List[Dict[str, str]]:
        self.require_conversation(conversation_id)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY id ASC
                """,
                (conversation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def append_exchange(self, conversation_id: str, user_message: str, assistant_message: str) -> None:
        now = self._now()
        title = self._title_from_message(user_message)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT title FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
            if row is None:
                raise KeyError("会话不存在")

            current_title = str(row["title"])
            next_title = title if current_title == "新对话" else current_title
            conn.execute(
                """
                INSERT INTO messages (conversation_id, role, content, created_at)
                VALUES (?, 'user', ?, ?), (?, 'assistant', ?, ?)
                """,
                (conversation_id, user_message, now, conversation_id, assistant_message, now),
            )
            conn.execute(
                """
                UPDATE conversations
                SET title = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_title, now, conversation_id),
            )

    def rename_conversation(self, conversation_id: str, title: str) -> Dict[str, str]:
        normalized = title.strip()
        if not normalized:
            raise ValueError("会话标题不能为空")

        now = self._now()
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE conversations
                SET title = ?, updated_at = ?
                WHERE id = ?
                """,
                (normalized, now, conversation_id),
            )
            if cursor.rowcount == 0:
                raise KeyError("会话不存在")
        conversation = self.get_conversation(conversation_id)
        if conversation is None:
            raise KeyError("会话不存在")
        return conversation

    def delete_conversation(self, conversation_id: str) -> None:
        with self._lock, self._connect() as conn:
            cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            if cursor.rowcount == 0:
                raise KeyError("会话不存在")

    def require_conversation(self, conversation_id: str) -> Dict[str, str]:
        conversation = self.get_conversation(conversation_id)
        if conversation is None:
            raise KeyError("会话不存在")
        return conversation

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def _title_from_message(message: str) -> str:
        compact = " ".join(message.strip().split())
        return compact[:24] if compact else "新对话"


conversation_store = ConversationStore()
