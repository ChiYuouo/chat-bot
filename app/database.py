"""SQLite 连接与建表。

SQLite 保存可恢复的业务数据；向量及其索引仍由 Chroma 负责。
"""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


_schema_lock = threading.RLock()
_initialized_paths: set[Path] = set()

_CONVERSATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    title TEXT NOT NULL,
    intents_json TEXT NOT NULL DEFAULT '[]',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (scope_id, id)
);

CREATE INDEX IF NOT EXISTS idx_conversations_scope_updated
    ON conversations(scope_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS conversation_messages (
    scope_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (scope_id, conversation_id, position),
    FOREIGN KEY (scope_id, conversation_id)
        REFERENCES conversations(scope_id, id)
        ON DELETE CASCADE
);
"""


_AUTH_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    expires_at REAL NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_user
    ON auth_sessions(user_id);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires
    ON auth_sessions(expires_at);
"""


def database_path() -> Path:
    configured = os.getenv("COPILOT_DATABASE_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "data" / "copilot.sqlite3"


def _open_connection(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """提供一个已完成建表、开启外键约束的短生命周期连接。"""
    path = database_path()
    initialize_database(path)
    connection = _open_connection(path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(path: Path | None = None) -> None:
    """创建当前版本所需的资料与 Chunk 表，可重复执行。"""
    target = path or database_path()
    with _schema_lock:
        if target in _initialized_paths and target.exists():
            return
        connection = _open_connection(target)
        try:
            connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS knowledge_sources (
                id TEXT PRIMARY KEY,
                scope_id TEXT NOT NULL,
                name TEXT NOT NULL,
                modality TEXT NOT NULL,
                chunk_count INTEGER NOT NULL,
                url TEXT,
                content_hash TEXT,
                duration_seconds REAL,
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_knowledge_sources_scope
                ON knowledge_sources(scope_id, created_at);

            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (source_id) REFERENCES knowledge_sources(id)
                    ON DELETE CASCADE,
                UNIQUE(source_id, chunk_index)
            );

            CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_scope_source
                ON knowledge_chunks(scope_id, source_id, chunk_index);

            """
            + _CONVERSATION_SCHEMA
            + _AUTH_SCHEMA
            )
            connection.commit()
            _initialized_paths.add(target)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
