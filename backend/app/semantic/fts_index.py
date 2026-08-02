"""SQLite FTS5/BM25 index for the compact compiled semantic catalog."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path
from typing import Any
from uuid import uuid4

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u3400-\u9fff]+", flags=re.UNICODE)
CJK_PATTERN = re.compile(r"^[\u3400-\u9fff]+$", flags=re.UNICODE)


class FtsUnavailableError(RuntimeError):
    pass


def build_fts_index(path: Path, documents: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # sqlite3.Connection's context manager commits/rolls back but does not close the
    # handle.  Relying on ref-count finalization made a second compile intermittently
    # fail with WinError 32.  Build a closed temporary database and publish it with one
    # atomic replace so readers never observe a half-built FTS catalog.
    temporary_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with closing(sqlite3.connect(temporary_path)) as connection, connection:
            connection.execute(
                """
                    CREATE VIRTUAL TABLE documents USING fts5(
                        item_id UNINDEXED,
                        item_type UNINDEXED,
                        physical_path,
                        display_name,
                        aliases,
                        description,
                        business_domain,
                        usage_guidance,
                        payload UNINDEXED,
                        tokenize='unicode61 remove_diacritics 2'
                    )
                    """
            )
            connection.executemany(
                """
                    INSERT INTO documents(
                        item_id, item_type, physical_path, display_name, aliases,
                        description, business_domain, usage_guidance, payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                (
                    (
                        document["item_id"],
                        document["item_type"],
                        _searchable_text(str(document.get("physical_path", ""))),
                        _searchable_text(str(document.get("display_name", ""))),
                        _searchable_text(" ".join(document.get("aliases", ()))),
                        _searchable_text(str(document.get("description", ""))),
                        _searchable_text(str(document.get("business_domain", ""))),
                        _searchable_text(str(document.get("usage_guidance", ""))),
                        json.dumps(document, ensure_ascii=False, sort_keys=True),
                    )
                    for document in documents
                ),
            )
        os.replace(temporary_path, path)
    except sqlite3.OperationalError as error:
        raise FtsUnavailableError(f"SQLite FTS5 is unavailable: {error}") from error
    finally:
        temporary_path.unlink(missing_ok=True)


def build_match_expression(query: str) -> str:
    tokens = _search_tokens(query)[:60]
    if not tokens:
        return '"__no_semantic_token__"'
    return " OR ".join(f'"{token.replace(chr(34), "")}"' for token in tokens)


def _search_tokens(value: str) -> list[str]:
    tokens: list[str] = []
    for token in TOKEN_PATTERN.findall(value.lower()):
        tokens.append(token)
        if CJK_PATTERN.fullmatch(token) and len(token) > 1:
            for width in (2, 3, 4):
                tokens.extend(
                    token[index : index + width] for index in range(len(token) - width + 1)
                )
    return list(dict.fromkeys(tokens))


def _searchable_text(value: str) -> str:
    return " ".join(_search_tokens(value))


def search_fts(path: Path, query: str, *, limit: int) -> list[tuple[dict[str, Any], float]]:
    expression = build_match_expression(query)
    with closing(sqlite3.connect(path)) as connection:
        rows = connection.execute(
            """
            SELECT payload, bm25(documents, 0.0, 0.0, 12.0, 10.0, 7.0, 4.0, 3.0, 2.0, 0.0)
            FROM documents
            WHERE documents MATCH ?
            ORDER BY 2
            LIMIT ?
            """,
            (expression, limit),
        ).fetchall()
    return [(json.loads(payload), float(rank)) for payload, rank in rows]
