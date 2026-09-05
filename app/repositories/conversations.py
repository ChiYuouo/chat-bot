"""会话和消息的 SQLite 仓储。"""

from __future__ import annotations

import json
import time
from typing import Any

from app.database import connect


class SQLiteConversationRepository:
    """会话必须通过 scope_id 读取，避免不同 scope 的数据混用。"""

    def load_conversation(
        self, scope_id: str, conversation_id: str
    ) -> tuple[list[dict[str, str]], list[str]] | None:
        with connect() as connection:
            conversation = connection.execute(
                """
                SELECT intents_json FROM conversations
                WHERE id = ? AND scope_id = ?
                """,
                (conversation_id, scope_id),
            ).fetchone()
            if conversation is None:
                return None
            rows = connection.execute(
                """
                SELECT role, content FROM conversation_messages
                WHERE scope_id = ? AND conversation_id = ?
                ORDER BY position
                """,
                (scope_id, conversation_id),
            ).fetchall()
        return (
            [{"role": row["role"], "content": row["content"]} for row in rows],
            list(json.loads(conversation["intents_json"])),
        )

    def list_conversations(self, scope_id: str) -> list[dict[str, Any]]:
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT conversations.id, conversations.title,
                       conversations.created_at, conversations.updated_at,
                       conversation_messages.role, conversation_messages.content,
                       conversation_messages.created_at AS message_created_at
                FROM conversations
                LEFT JOIN conversation_messages
                    ON conversation_messages.scope_id = conversations.scope_id
                    AND conversation_messages.conversation_id = conversations.id
                WHERE conversations.scope_id = ?
                ORDER BY conversations.updated_at DESC, conversation_messages.position
                """,
                (scope_id,),
            ).fetchall()
        conversations: dict[str, dict[str, Any]] = {}
        for row in rows:
            conversation = conversations.setdefault(
                row["id"],
                {
                    "id": row["id"],
                    "title": row["title"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "messages": [],
                },
            )
            if row["role"] is not None:
                conversation["messages"].append({
                    "role": row["role"],
                    "content": row["content"],
                    "created_at": row["message_created_at"],
                })
        return list(conversations.values())

    def rename_conversation(
        self, scope_id: str, conversation_id: str, title: str
    ) -> bool:
        with connect() as connection:
            cursor = connection.execute(
                """
                UPDATE conversations
                SET title = ?, updated_at = ?
                WHERE id = ? AND scope_id = ?
                """,
                (title, time.time(), conversation_id, scope_id),
            )
        return cursor.rowcount == 1

    def delete_conversation(self, scope_id: str, conversation_id: str) -> bool:
        with connect() as connection:
            cursor = connection.execute(
                "DELETE FROM conversations WHERE id = ? AND scope_id = ?",
                (conversation_id, scope_id),
            )
        return cursor.rowcount == 1

    def save_conversation(
        self,
        scope_id: str,
        conversation_id: str,
        messages: list[dict[str, Any]],
        intents: list[str],
    ) -> None:
        now = time.time()
        title = next(
            (
                str(message["content"]).strip()[:80]
                for message in messages
                if message.get("role") == "user" and str(message.get("content", "")).strip()
            ),
            "新对话",
        )
        title = " ".join(title.split())
        if len(title) > 24:
            title = f"{title[:24]}…"
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations (
                    id, scope_id, title, intents_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope_id, id) DO UPDATE SET
                    intents_json = excluded.intents_json,
                    updated_at = excluded.updated_at
                """,
                (
                    conversation_id,
                    scope_id,
                    title,
                    json.dumps(intents, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                DELETE FROM conversation_messages
                WHERE scope_id = ? AND conversation_id = ?
                """,
                (scope_id, conversation_id),
            )
            connection.executemany(
                """
                INSERT INTO conversation_messages (
                    scope_id, conversation_id, position, role, content, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        scope_id,
                        conversation_id,
                        position,
                        str(message["role"]),
                        str(message["content"]),
                        now,
                    )
                    for position, message in enumerate(messages)
                ],
            )
