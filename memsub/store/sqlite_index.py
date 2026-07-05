"""SQLite metadata index: threads, spans, blocks, checkpoints, provenance
edges (derived_from / supersedes), redaction generations (spec B.2, B.7).

All reads of spans/blocks/checkpoints go through here so redaction can fail
closed in one place (GT5).
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
    thread_id TEXT PRIMARY KEY,
    redaction_generation INTEGER NOT NULL DEFAULT 0,
    next_logical_position INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS spans (
    span_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    token_start INTEGER NOT NULL,
    token_end INTEGER NOT NULL,          -- exclusive
    role TEXT NOT NULL,
    text_uri TEXT NOT NULL,
    tokens_uri TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    redaction_generation INTEGER NOT NULL DEFAULT 0,
    redacted INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS blocks (
    block_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    body_json TEXT NOT NULL,             -- full MemoryBlock (spec 6.1)
    invalidated INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    body_json TEXT NOT NULL,             -- full ThreadCheckpoint (spec 6.2)
    token_start INTEGER NOT NULL DEFAULT 0,
    token_end INTEGER NOT NULL DEFAULT 0,  -- logical coverage, for redaction
    invalidated INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS edges (
    child_id TEXT NOT NULL,              -- artifact deriving from parent
    parent_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('derived_from', 'supersedes')),
    PRIMARY KEY (child_id, parent_id, kind)
);
CREATE INDEX IF NOT EXISTS idx_spans_thread ON spans(thread_id, token_start);
CREATE INDEX IF NOT EXISTS idx_edges_parent ON edges(parent_id, kind);
CREATE INDEX IF NOT EXISTS idx_ckpt_thread ON checkpoints(thread_id, created_at);
"""


class SqliteIndex:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    # -- threads -------------------------------------------------------------
    def create_thread(self, thread_id: str) -> None:
        self.conn.execute(
            "INSERT INTO threads (thread_id, created_at) VALUES (?, ?)",
            (thread_id, time.time()),
        )
        self.conn.commit()

    def get_thread(self, thread_id: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM threads WHERE thread_id = ?", (thread_id,)
        ).fetchone()

    def set_next_logical_position(self, thread_id: str, pos: int) -> None:
        self.conn.execute(
            "UPDATE threads SET next_logical_position = ? WHERE thread_id = ?",
            (pos, thread_id),
        )
        self.conn.commit()

    def bump_redaction_generation(self, thread_id: str) -> int:
        self.conn.execute(
            "UPDATE threads SET redaction_generation = redaction_generation + 1 "
            "WHERE thread_id = ?", (thread_id,),
        )
        self.conn.commit()
        return int(self.get_thread(thread_id)["redaction_generation"])

    # -- spans ---------------------------------------------------------------
    def insert_span(self, **cols: Any) -> None:
        cols.setdefault("created_at", time.time())
        keys = ", ".join(cols)
        marks = ", ".join("?" for _ in cols)
        self.conn.execute(
            f"INSERT INTO spans ({keys}) VALUES ({marks})", tuple(cols.values())
        )
        self.conn.commit()

    def get_span(self, span_id: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM spans WHERE span_id = ?", (span_id,)
        ).fetchone()

    def spans_for_thread(self, thread_id: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM spans WHERE thread_id = ? ORDER BY token_start",
            (thread_id,),
        ).fetchall()

    def mark_span_redacted(self, span_id: str, generation: int) -> None:
        self.conn.execute(
            "UPDATE spans SET redacted = 1, redaction_generation = ? WHERE span_id = ?",
            (generation, span_id),
        )
        self.conn.commit()

    # -- blocks --------------------------------------------------------------
    def insert_block(self, block_id: str, thread_id: str, body: dict) -> None:
        self.conn.execute(
            "INSERT INTO blocks (block_id, thread_id, body_json, created_at) "
            "VALUES (?, ?, ?, ?)",
            (block_id, thread_id, json.dumps(body), time.time()),
        )
        self.conn.commit()

    def get_block_row(self, block_id: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM blocks WHERE block_id = ?", (block_id,)
        ).fetchone()

    def blocks_for_thread(self, thread_id: str, include_invalidated: bool = False) -> list[sqlite3.Row]:
        q = "SELECT * FROM blocks WHERE thread_id = ?"
        if not include_invalidated:
            q += " AND invalidated = 0"
        return self.conn.execute(q + " ORDER BY created_at", (thread_id,)).fetchall()

    def invalidate_artifact(self, artifact_id: str) -> None:
        self.conn.execute("UPDATE blocks SET invalidated = 1 WHERE block_id = ?", (artifact_id,))
        self.conn.execute("UPDATE checkpoints SET invalidated = 1 WHERE checkpoint_id = ?", (artifact_id,))
        self.conn.commit()

    # -- checkpoints ---------------------------------------------------------
    def insert_checkpoint(self, checkpoint_id: str, thread_id: str,
                          parent_checkpoint_id: Optional[str], body: dict,
                          token_start: int, token_end: int) -> None:
        self.conn.execute(
            "INSERT INTO checkpoints (checkpoint_id, thread_id, parent_checkpoint_id,"
            " body_json, token_start, token_end, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (checkpoint_id, thread_id, parent_checkpoint_id, json.dumps(body),
             token_start, token_end, time.time()),
        )
        self.conn.commit()

    def get_checkpoint_row(self, checkpoint_id: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,)
        ).fetchone()

    def latest_checkpoint(self, thread_id: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM checkpoints WHERE thread_id = ? AND invalidated = 0 "
            "ORDER BY created_at DESC LIMIT 1", (thread_id,),
        ).fetchone()

    def checkpoints_for_thread(self, thread_id: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM checkpoints WHERE thread_id = ?", (thread_id,)
        ).fetchall()

    # -- provenance edges ----------------------------------------------------
    def add_edge(self, child_id: str, parent_id: str, kind: str = "derived_from") -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO edges (child_id, parent_id, kind) VALUES (?, ?, ?)",
            (child_id, parent_id, kind),
        )
        self.conn.commit()

    def children_of(self, parent_id: str, kind: str = "derived_from") -> list[str]:
        rows = self.conn.execute(
            "SELECT child_id FROM edges WHERE parent_id = ? AND kind = ?",
            (parent_id, kind),
        ).fetchall()
        return [r["child_id"] for r in rows]

    def parents_of(self, child_id: str, kind: str = "derived_from") -> list[str]:
        rows = self.conn.execute(
            "SELECT parent_id FROM edges WHERE child_id = ? AND kind = ?",
            (child_id, kind),
        ).fetchall()
        return [r["parent_id"] for r in rows]

    def close(self) -> None:
        self.conn.close()
