"""One SQLite file per case — README §2.4, §3.2, §5.5.

`CaseStore` is the isolation boundary. It is opened for exactly one case id and
every path it touches comes from `config.case_dir()`. There is no query in this
class that can reach another case's data, because the other case is a different
file. Do not add a shared store that spans cases (§5.5).

Writes are idempotent by design: nodes merge on their stable id, edges merge on
`Edge.natural_key()`. Ingesting the same document twice must not double the
graph — the demo depends on that, and so does re-running the generator.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Sequence

from backend.config import case_dir, check_case_id, now_iso
from backend.graph.schema import Edge, Node, SourcelessFact

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    label       TEXT NOT NULL,
    attrs       TEXT NOT NULL DEFAULT '{}',
    first_seen  TEXT,
    last_seen   TEXT,
    sources     TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS ix_nodes_type  ON nodes(type);
CREATE INDEX IF NOT EXISTS ix_nodes_label ON nodes(label);

CREATE TABLE IF NOT EXISTS edges (
    id          TEXT PRIMARY KEY,
    nat_key     TEXT NOT NULL UNIQUE,
    src         TEXT NOT NULL REFERENCES nodes(id),
    dst         TEXT NOT NULL REFERENCES nodes(id),
    type        TEXT NOT NULL,
    attrs       TEXT NOT NULL DEFAULT '{}',
    weight      REAL NOT NULL DEFAULT 1.0,
    confidence  REAL NOT NULL DEFAULT 1.0,
    ts          TEXT,
    sources     TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS ix_edges_src  ON edges(src);
CREATE INDEX IF NOT EXISTS ix_edges_dst  ON edges(dst);
CREATE INDEX IF NOT EXISTS ix_edges_type ON edges(type);
CREATE INDEX IF NOT EXISTS ix_edges_ts   ON edges(ts);

CREATE TABLE IF NOT EXISTS documents (
    doc_id      TEXT PRIMARY KEY,
    filename    TEXT NOT NULL,
    kind        TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    char_len    INTEGER NOT NULL DEFAULT 0,
    meta        TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS analytics (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    graph_rev   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS counters (
    name  TEXT PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
);

-- What the case agent knows and has already said. This is what makes it an
-- assistant working a case over months rather than a chat box that forgets
-- between questions: conclusions it reached, questions it is still holding,
-- evidence it has asked the officer for, and what it has already briefed so it
-- does not repeat itself.
CREATE TABLE IF NOT EXISTS agent_memory (
    id         TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'open',
    text       TEXT NOT NULL,
    node_ids   TEXT NOT NULL DEFAULT '[]',
    edge_ids   TEXT NOT NULL DEFAULT '[]',
    confidence TEXT,
    created    TEXT NOT NULL,
    updated    TEXT NOT NULL,
    graph_rev  INTEGER NOT NULL DEFAULT 0,
    meta       TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_mem_kind   ON agent_memory(kind);
CREATE INDEX IF NOT EXISTS ix_mem_status ON agent_memory(status);
"""


def _j(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


# Identifiers are written with assorted separators — 98765-43210, +91 98765
# 43210, 9876543210 — and all normalise to one id. The label is what the
# officer reads, so it should be the cleanest form seen, not the longest.
_IDENTIFIER_TYPES = {"phone", "account", "device", "vehicle"}


def _better_label(node_type: str, current: str, incoming: str) -> str:
    if node_type in _IDENTIFIER_TYPES:
        noise = lambda s: (sum(not c.isalnum() for c in s), -len(s))  # noqa: E731
        return min((current, incoming), key=noise)
    # For names, longer is usually fuller: "Ravi" -> "Ravi Kumar".
    return max((current, incoming), key=len)


class CaseStore:
    """Open with `CaseStore(case_id)`; use as a context manager or call `close()`."""

    def __init__(self, case_id: str, *, create: bool = True):
        self.case_id = check_case_id(case_id)
        self.dir = case_dir(case_id)
        if not self.dir.exists():
            if not create:
                raise FileNotFoundError(f"case {case_id!r} does not exist")
        for sub in ("", "docs", "extracted"):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)
        self.db_path = self.dir / "graph.db"
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # --------------------------------------------------------------- lifecycle

    def __enter__(self) -> "CaseStore":
        return self

    def __exit__(self, *exc) -> None:
        self.commit()
        self.close()

    def close(self) -> None:
        self.conn.close()

    def commit(self) -> None:
        self.conn.commit()

    # ---------------------------------------------------------------- counters

    def _next(self, name: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO counters(name, value) VALUES(?, 1) "
            "ON CONFLICT(name) DO UPDATE SET value = value + 1 RETURNING value",
            (name,),
        )
        return int(cur.fetchone()[0])

    def graph_rev(self) -> int:
        """Bumped on every write. Analytics caches carry the rev they were
        computed at, so a stale cache is detectable rather than merely old."""
        row = self.conn.execute("SELECT value FROM counters WHERE name='graph_rev'").fetchone()
        return int(row[0]) if row else 0

    def _touch(self) -> None:
        self._next("graph_rev")

    # ------------------------------------------------------------------- nodes

    def upsert_node(self, node: Node) -> Node:
        """Merge into an existing node of the same id: union the sources, union
        the attrs, widen the [first_seen, last_seen] window."""
        row = self.conn.execute("SELECT * FROM nodes WHERE id=?", (node.id,)).fetchone()
        if row is None:
            self.conn.execute(
                "INSERT INTO nodes(id,type,label,attrs,first_seen,last_seen,sources) "
                "VALUES(?,?,?,?,?,?,?)",
                (node.id, node.type, node.label, _j(node.attrs),
                 node.first_seen, node.last_seen, _j(node.sources)),
            )
            self._touch()
            return node

        merged_sources = {
            (s["doc_id"], s.get("start"), s.get("end")): s
            for s in json.loads(row["sources"]) + node.sources
        }
        attrs = json.loads(row["attrs"])
        for k, v in node.attrs.items():
            if k == "aliases":
                attrs["aliases"] = sorted(set(attrs.get("aliases", [])) | set(v))
            elif v not in (None, "", [], {}):
                attrs[k] = v
        seen = [x for x in (row["first_seen"], node.first_seen) if x]
        first = min(seen) if seen else None
        seen = [x for x in (row["last_seen"], node.last_seen) if x]
        last = max(seen) if seen else None
        label = _better_label(node.type, row["label"], node.label)

        self.conn.execute(
            "UPDATE nodes SET label=?, attrs=?, first_seen=?, last_seen=?, sources=? WHERE id=?",
            (label, _j(attrs), first, last, _j(list(merged_sources.values())), node.id),
        )
        self._touch()
        return self.get_node(node.id)

    def get_node(self, node_id: str) -> Node | None:
        row = self.conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
        return self._node(row) if row else None

    def nodes(self, *, type: str | None = None) -> list[Node]:
        if type:
            rows = self.conn.execute("SELECT * FROM nodes WHERE type=?", (type,))
        else:
            rows = self.conn.execute("SELECT * FROM nodes")
        return [self._node(r) for r in rows]

    def search_nodes(self, query: str, *, type: str | None = None, limit: int = 25) -> list[Node]:
        """Substring match on label and id, ranked: exact label match, then a
        prefix match, then anything containing the query."""
        q = (query or "").strip().lower()
        if not q:
            return []
        sql = "SELECT * FROM nodes WHERE (lower(label) LIKE ? OR lower(id) LIKE ?)"
        args: list = [f"%{q}%", f"%{q}%"]
        if type:
            sql += " AND type=?"
            args.append(type)
        rows = [self._node(r) for r in self.conn.execute(sql, args)]

        def rank(n: Node) -> tuple:
            lbl = n.label.lower()
            return (0 if lbl == q else 1 if lbl.startswith(q) else 2, len(lbl))

        return sorted(rows, key=rank)[:limit]

    @staticmethod
    def _node(row: sqlite3.Row) -> Node:
        return Node(
            id=row["id"], type=row["type"], label=row["label"],
            attrs=json.loads(row["attrs"]), first_seen=row["first_seen"],
            last_seen=row["last_seen"], sources=json.loads(row["sources"]),
        )

    # ------------------------------------------------------------------- edges

    def upsert_edge(self, edge: Edge) -> Edge:
        """Merge on `natural_key`. Two calls between the same pair at different
        times are two edges; the same fact seen in two documents is one edge
        with two sources."""
        for end in (edge.src, edge.dst):
            if self.get_node(end) is None:
                raise SourcelessFact(f"edge endpoint {end} does not exist as a node")

        key = edge.natural_key()
        row = self.conn.execute("SELECT * FROM edges WHERE nat_key=?", (key,)).fetchone()
        if row is None:
            edge.id = f"e_{self._next('edge_id')}"
            self.conn.execute(
                "INSERT INTO edges(id,nat_key,src,dst,type,attrs,weight,confidence,ts,sources) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (edge.id, key, edge.src, edge.dst, edge.type, _j(edge.attrs),
                 edge.weight, edge.confidence, edge.ts, _j(edge.sources)),
            )
            self._touch()
            return edge

        merged = {
            (s["doc_id"], s.get("start"), s.get("end")): s
            for s in json.loads(row["sources"]) + edge.sources
        }
        attrs = json.loads(row["attrs"])
        attrs.update({k: v for k, v in edge.attrs.items() if v is not None})
        self.conn.execute(
            "UPDATE edges SET attrs=?, weight=?, confidence=?, sources=? WHERE id=?",
            (_j(attrs), max(row["weight"], edge.weight),
             max(row["confidence"], edge.confidence), _j(list(merged.values())), row["id"]),
        )
        self._touch()
        edge.id = row["id"]
        return edge

    def get_edge(self, edge_id: str) -> Edge | None:
        row = self.conn.execute("SELECT * FROM edges WHERE id=?", (edge_id,)).fetchone()
        return self._edge(row) if row else None

    def edges(
        self,
        *,
        node_id: str | None = None,
        types: Sequence[str] | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[Edge]:
        sql = "SELECT * FROM edges WHERE 1=1"
        args: list = []
        if node_id:
            sql += " AND (src=? OR dst=?)"
            args += [node_id, node_id]
        if types:
            sql += " AND type IN (" + ",".join("?" * len(types)) + ")"
            args += list(types)
        if start:
            sql += " AND ts >= ?"
            args.append(start)
        if end:
            sql += " AND ts <= ?"
            args.append(end)
        return [self._edge(r) for r in self.conn.execute(sql + " ORDER BY ts, id", args)]

    @staticmethod
    def _edge(row: sqlite3.Row) -> Edge:
        e = Edge(
            src=row["src"], dst=row["dst"], type=row["type"],
            attrs=json.loads(row["attrs"]), weight=row["weight"],
            confidence=row["confidence"], sources=json.loads(row["sources"]),
        )
        e.id = row["id"]
        return e

    # --------------------------------------------------------------- documents

    def register_document(
        self, doc_id: str, filename: str, kind: str, sha256: str,
        char_len: int = 0, meta: dict | None = None,
    ) -> None:
        self.conn.execute(
            "INSERT INTO documents(doc_id,filename,kind,sha256,ingested_at,char_len,meta) "
            "VALUES(?,?,?,?,?,?,?) ON CONFLICT(doc_id) DO UPDATE SET "
            "filename=excluded.filename, kind=excluded.kind, sha256=excluded.sha256, "
            "char_len=excluded.char_len, meta=excluded.meta",
            (doc_id, filename, kind, sha256, now_iso(), char_len, _j(meta or {})),
        )

    def documents(self) -> list[dict]:
        out = []
        for r in self.conn.execute("SELECT * FROM documents ORDER BY ingested_at, doc_id"):
            d = dict(r)
            d["meta"] = json.loads(d["meta"])
            out.append(d)
        return out

    def document(self, doc_id: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["meta"] = json.loads(d["meta"])
        return d

    def extracted_path(self, doc_id: str) -> Path:
        """Where a document's plain text lives. Kept inside the case directory
        so `read_source_doc` cannot reach outside it."""
        safe = doc_id.replace(":", "__").replace("/", "_").replace("\\", "_")
        return self.dir / "extracted" / f"{safe}.txt"

    # --------------------------------------------------------------- analytics

    def put_analytics(self, key: str, value: Any) -> None:
        self.conn.execute(
            "INSERT INTO analytics(key,value,computed_at,graph_rev) VALUES(?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
            "computed_at=excluded.computed_at, graph_rev=excluded.graph_rev",
            (key, _j(value), now_iso(), self.graph_rev()),
        )
        self.conn.commit()

    def get_analytics(self, key: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM analytics WHERE key=?", (key,)).fetchone()
        if not r:
            return None
        return {
            "value": json.loads(r["value"]),
            "computed_at": r["computed_at"],
            "graph_rev": r["graph_rev"],
            "stale": r["graph_rev"] != self.graph_rev(),
        }

    # ------------------------------------------------------------ agent memory

    MEMORY_KINDS = ("conclusion", "open_question", "request", "briefing", "note")

    def remember(
        self, *, kind: str, text: str, node_ids: Sequence[str] = (),
        edge_ids: Sequence[str] = (), confidence: str | None = None,
        status: str = "open", meta: dict | None = None, mem_id: str | None = None,
    ) -> dict:
        """Write one thing the agent knows. Ids are content-derived, so the same
        conclusion reached twice updates rather than duplicating — an assistant
        that repeats itself every ingest is worse than one that says nothing."""
        if kind not in self.MEMORY_KINDS:
            raise ValueError(f"unknown memory kind {kind!r}; allowed {self.MEMORY_KINDS}")
        mem_id = mem_id or f"m_{abs(hash((kind, text.strip().lower()))) % (10 ** 12):012d}"
        now = now_iso()
        self.conn.execute(
            "INSERT INTO agent_memory(id,kind,status,text,node_ids,edge_ids,confidence,"
            "created,updated,graph_rev,meta) VALUES(?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET text=excluded.text, status=excluded.status, "
            "node_ids=excluded.node_ids, edge_ids=excluded.edge_ids, "
            "confidence=excluded.confidence, updated=excluded.updated, "
            "graph_rev=excluded.graph_rev, meta=excluded.meta",
            (mem_id, kind, status, text, _j(list(node_ids)), _j(list(edge_ids)),
             confidence, now, now, self.graph_rev(), _j(meta or {})),
        )
        self.conn.commit()
        return self.memory_entry(mem_id)

    def memory_entry(self, mem_id: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM agent_memory WHERE id=?", (mem_id,)).fetchone()
        return self._memory(r) if r else None

    def memory(
        self, *, kind: str | None = None, status: str | None = None, limit: int = 100,
    ) -> list[dict]:
        sql = "SELECT * FROM agent_memory WHERE 1=1"
        args: list = []
        if kind:
            sql += " AND kind=?"
            args.append(kind)
        if status:
            sql += " AND status=?"
            args.append(status)
        sql += " ORDER BY updated DESC LIMIT ?"
        args.append(limit)
        return [self._memory(r) for r in self.conn.execute(sql, args)]

    def search_memory(self, query: str, limit: int = 20) -> list[dict]:
        q = (query or "").strip().lower()
        if not q:
            return self.memory(limit=limit)
        rows = self.conn.execute(
            "SELECT * FROM agent_memory WHERE lower(text) LIKE ? ORDER BY updated DESC LIMIT ?",
            (f"%{q}%", limit),
        )
        return [self._memory(r) for r in rows]

    def close_memory(self, mem_id: str, status: str = "resolved") -> dict | None:
        self.conn.execute(
            "UPDATE agent_memory SET status=?, updated=? WHERE id=?",
            (status, now_iso(), mem_id),
        )
        self.conn.commit()
        return self.memory_entry(mem_id)

    @staticmethod
    def _memory(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["node_ids"] = json.loads(d["node_ids"])
        d["edge_ids"] = json.loads(d["edge_ids"])
        d["meta"] = json.loads(d["meta"])
        return d

    # ------------------------------------------------------------------- stats

    def counts(self) -> dict[str, int]:
        def one(sql: str) -> int:
            return int(self.conn.execute(sql).fetchone()[0])

        return {
            "nodes": one("SELECT count(*) FROM nodes"),
            "edges": one("SELECT count(*) FROM edges"),
            "documents": one("SELECT count(*) FROM documents"),
            "graph_rev": self.graph_rev(),
        }
