"""本地账号、密码与登录会话的 SQLite 仓储。"""

from __future__ import annotations

import hashlib
import secrets
import time
import uuid
from dataclasses import dataclass

from app.database import connect


@dataclass(frozen=True)
class User:
    id: str
    email: str


class SQLiteAuthRepository:
    """Cookie 中只保存原始会话令牌；数据库中只保存其哈希值。"""

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_user(self, email: str, password_hash: str) -> User:
        user = User(id=uuid.uuid4().hex, email=email)
        with connect() as connection:
            connection.execute(
                "INSERT INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (user.id, user.email, password_hash, time.time()),
            )
        return user

    def find_user_with_password(self, email: str) -> tuple[User, str] | None:
        with connect() as connection:
            row = connection.execute(
                "SELECT id, email, password_hash FROM users WHERE email = ?", (email,)
            ).fetchone()
        if row is None:
            return None
        return User(id=row["id"], email=row["email"]), row["password_hash"]

    def create_session(self, user_id: str, max_age_seconds: int) -> str:
        token = secrets.token_urlsafe(32)
        now = time.time()
        with connect() as connection:
            connection.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (now,))
            connection.execute(
                """
                INSERT INTO auth_sessions (token_hash, user_id, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (self._token_hash(token), user_id, now + max_age_seconds, now),
            )
        return token

    def get_user_for_session(self, token: str | None) -> User | None:
        if not token:
            return None
        now = time.time()
        with connect() as connection:
            row = connection.execute(
                """
                SELECT users.id, users.email
                FROM auth_sessions
                JOIN users ON users.id = auth_sessions.user_id
                WHERE auth_sessions.token_hash = ? AND auth_sessions.expires_at > ?
                """,
                (self._token_hash(token), now),
            ).fetchone()
        return None if row is None else User(id=row["id"], email=row["email"])

    def revoke_session(self, token: str | None) -> None:
        if not token:
            return
        with connect() as connection:
            connection.execute(
                "DELETE FROM auth_sessions WHERE token_hash = ?", (self._token_hash(token),)
            )

    def migrate_scope(self, old_scope_id: str, new_scope_id: str) -> None:
        """把匿名 scope 的持久化资料和对话绑定给已登录用户。"""
        if old_scope_id == new_scope_id:
            return
        with connect() as connection:
            connection.execute(
                "UPDATE knowledge_sources SET scope_id = ? WHERE scope_id = ?",
                (new_scope_id, old_scope_id),
            )
            connection.execute(
                "UPDATE knowledge_chunks SET scope_id = ? WHERE scope_id = ?",
                (new_scope_id, old_scope_id),
            )

            conversations = connection.execute(
                """
                SELECT id, title, intents_json, created_at, updated_at
                FROM conversations WHERE scope_id = ?
                """,
                (old_scope_id,),
            ).fetchall()
            for conversation in conversations:
                conversation_id = conversation["id"]
                exists = connection.execute(
                    "SELECT 1 FROM conversations WHERE scope_id = ? AND id = ?",
                    (new_scope_id, conversation_id),
                ).fetchone()
                target_id = conversation_id if exists is None else uuid.uuid4().hex
                connection.execute(
                    """
                    INSERT INTO conversations (id, scope_id, title, intents_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        target_id,
                        new_scope_id,
                        conversation["title"],
                        conversation["intents_json"],
                        conversation["created_at"],
                        conversation["updated_at"],
                    ),
                )
                messages = connection.execute(
                    """
                    SELECT position, role, content, created_at
                    FROM conversation_messages
                    WHERE scope_id = ? AND conversation_id = ?
                    ORDER BY position
                    """,
                    (old_scope_id, conversation_id),
                ).fetchall()
                connection.executemany(
                    """
                    INSERT INTO conversation_messages
                    (scope_id, conversation_id, position, role, content, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (new_scope_id, target_id, row["position"], row["role"], row["content"], row["created_at"])
                        for row in messages
                    ],
                )
                connection.execute(
                    "DELETE FROM conversations WHERE scope_id = ? AND id = ?",
                    (old_scope_id, conversation_id),
                )
