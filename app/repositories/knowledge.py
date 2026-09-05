"""知识资料和 Chunk 的 SQLite 仓储。"""

from __future__ import annotations

import json
import time
from typing import Any, Iterable

from langchain_core.documents import Document

from app.database import connect
from app.models import KnowledgeSource


class SQLiteKnowledgeRepository:
    """只负责持久化，不负责调用 Embedding 或 Chroma。"""

    def save_source(
        self,
        scope_id: str,
        source: KnowledgeSource,
        chunks: Iterable[Any],
    ) -> list[Document]:
        documents = [
            Document(
                page_content=str(chunk.page_content),
                metadata=dict(chunk.metadata),
            )
            for chunk in chunks
        ]
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO knowledge_sources (
                    id, scope_id, name, modality, chunk_count, url, content_hash,
                    duration_seconds, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source.source_id,
                    scope_id,
                    source.name,
                    source.modality,
                    source.chunk_count,
                    source.url,
                    source.content_hash,
                    source.duration_seconds,
                    source.created_at,
                ),
            )
            connection.executemany(
                """
                INSERT INTO knowledge_chunks (
                    id, source_id, scope_id, chunk_index, content, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(document.metadata["chunk_id"]),
                        source.source_id,
                        scope_id,
                        index,
                        document.page_content,
                        json.dumps(document.metadata, ensure_ascii=False, default=str),
                        time.time(),
                    )
                    for index, document in enumerate(documents)
                ],
            )
        return documents

    def load_sources(self, scope_id: str) -> dict[str, KnowledgeSource]:
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, modality, chunk_count, url, content_hash,
                       duration_seconds, created_at
                FROM knowledge_sources
                WHERE scope_id = ?
                ORDER BY created_at, id
                """,
                (scope_id,),
            ).fetchall()
        return {
            row["id"]: KnowledgeSource(
                source_id=row["id"],
                name=row["name"],
                modality=row["modality"],
                chunk_count=row["chunk_count"],
                url=row["url"],
                content_hash=row["content_hash"],
                duration_seconds=row["duration_seconds"],
                created_at=row["created_at"],
            )
            for row in rows
        }

    def load_chunks(self, scope_id: str) -> list[Document]:
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT content, metadata_json
                FROM knowledge_chunks
                WHERE scope_id = ?
                ORDER BY source_id, chunk_index
                """,
                (scope_id,),
            ).fetchall()
        return [
            Document(
                page_content=row["content"],
                metadata=json.loads(row["metadata_json"]),
            )
            for row in rows
        ]

    def delete_source(self, scope_id: str, source_id: str) -> bool:
        with connect() as connection:
            cursor = connection.execute(
                "DELETE FROM knowledge_sources WHERE id = ? AND scope_id = ?",
                (source_id, scope_id),
            )
        return cursor.rowcount == 1

    def clear_scope(self, scope_id: str) -> None:
        with connect() as connection:
            connection.execute(
                "DELETE FROM knowledge_sources WHERE scope_id = ?", (scope_id,)
            )
