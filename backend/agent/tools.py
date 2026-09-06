"""The case agent's hands — README §5.2, plus the tools that let it act.

Two families, and the split is the whole point of the product.

**Read tools** are §5.2 verbatim, frozen. Every one is scoped to a single case
and every one returns ids the agent must cite. There is no tool that retrieves
document text by similarity: the agent reaches source text only through
`read_source_doc`, and only for a document it already found *through the
graph*. Graph first, document second — that ordering is D3, and it is what
stops this being a RAG chatbot with a picture next to it.

**Act tools** are what make it an assistant rather than a search box. It records
conclusions, holds open questions, and asks the officer for the evidence it
knows is missing — all written into the case's own memory, all hash-logged to
the custody chain as `infer`. The officer should never have to re-explain the
case, and should never have to read forty pages to find out the system already
knew something.

Every tool here is a plain function taking `CaseContext` first. `loop.py` wraps
them with `@beta_tool` for the model; the API and the tests call them directly,
so the whole tool surface is exercisable with no API key and no network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Sequence

from backend.analytics import metrics as metrics_mod
from backend.custody.chain import CustodyChain
from backend.graph.nx_adapter import case_graphs, neighbourhood, paths_between
from backend.graph.store import CaseStore

MAX_TEXT_SNIPPET = 4000


@dataclass
class CaseContext:
    """Everything a tool may touch. One case, and no way to name another."""

    store: CaseStore
    chain: CustodyChain
    actor: str = "officer"

    @property
    def case_id(self) -> str:
        return self.store.case_id


def _node_out(ctx: CaseContext, node_id: str) -> dict | None:
    node = ctx.store.get_node(node_id)
    return node.to_dict() if node else None


# ------------------------------------------------------------------ §5.2 read

def find_entity(ctx: CaseContext, query: str, type: str | None = None) -> list[dict]:
    """Entities whose name or identifier matches `query`, best match first."""
    return [n.to_dict() for n in ctx.store.search_nodes(query, type=type)]


def neighbours(
    ctx: CaseContext, node_id: str, depth: int = 1, edge_types: Sequence[str] | None = None,
) -> dict:
    """Everything within `depth` hops of a node, in either direction."""
    g, _ = case_graphs(ctx.store)
    node_ids, edge_ids = neighbourhood(g, node_id, depth=depth, edge_types=edge_types)
    return {
        "nodes": [n for n in (_node_out(ctx, i) for i in node_ids) if n],
        "edges": [e.to_dict() for e in (ctx.store.get_edge(i) for i in edge_ids) if e],
    }


def path_between(ctx: CaseContext, a: str, b: str, max_hops: int = 6) -> list[dict]:
    """How two entities are connected: shortest paths, with the edges traversed."""
    _, u = case_graphs(ctx.store)
    paths = paths_between(u, a, b, max_hops=max_hops)
    for p in paths:
        p["labels"] = [
            (ctx.store.get_node(i).label if ctx.store.get_node(i) else i) for i in p["path"]
        ]
    return paths


def timeline(
    ctx: CaseContext, node_id: str | None = None,
    start: str | None = None, end: str | None = None,
) -> list[dict]:
    """Dated events in order — calls, messages, transfers, tower hits."""
    out = []
    for edge in ctx.store.edges(node_id=node_id, start=start, end=end):
        if not edge.ts:
            continue
        src = ctx.store.get_node(edge.src)
        dst = ctx.store.get_node(edge.dst)
        detail = ""
        if edge.attrs.get("amount") is not None:
            detail = f" ({edge.attrs['amount']:,.0f})"
        elif edge.attrs.get("duration_sec"):
            detail = f" ({int(edge.attrs['duration_sec'])}s)"
        out.append({
            "ts": edge.ts,
            "edge_id": edge.id,
            "summary": (f"{src.label if src else edge.src} {edge.type} "
                        f"{dst.label if dst else edge.dst}{detail}"),
        })
    return sorted(out, key=lambda e: e["ts"])


def top_influencers(ctx: CaseContext, metric: str = "betweenness", limit: int = 10) -> list[dict]:
    """Who matters in this network, and the reason each one scored."""
    return metrics_mod.top_influencers(ctx.store, metric=metric, limit=limit)


def communities(ctx: CaseContext) -> list[dict]:
    """The clusters — the cells or groups inside the network."""
    cached = ctx.store.get_analytics("communities")
    if cached and not cached["stale"]:
        return cached["value"]
    _, u = case_graphs(ctx.store)
    return metrics_mod.compute_communities(u)


def anomalies(ctx: CaseContext, window_hours: int = 24) -> list[dict]:
    """Statistically unusual activity: spikes, handset swaps, one-way accounts."""
    cached = ctx.store.get_analytics("anomalies")
    if cached and not cached["stale"]:
        return cached["value"]
    from backend.analytics.anomalies import compute_anomalies

    g, u = case_graphs(ctx.store)
    return compute_anomalies(ctx.store, g, u, window_hours=window_hours)


def read_source_doc(
    ctx: CaseContext, doc_id: str, start: int | None = None, end: int | None = None,
) -> dict:
    """The original text behind a fact — used to *verify* an edge already found
    in the graph, never to search for one."""
    doc = ctx.store.document(doc_id)
    if doc is None:
        return {"error": f"no document {doc_id} in case {ctx.case_id}",
                "available": [d["doc_id"] for d in ctx.store.documents()][:40]}
    path = ctx.store.extracted_path(doc_id)
    if not path.exists():
        return {"error": f"document {doc_id} has no extracted text"}

    text = path.read_text(encoding="utf-8")
    if start is None and end is None:
        body, start, end = text[:MAX_TEXT_SNIPPET], 0, min(len(text), MAX_TEXT_SNIPPET)
    else:
        start = max(0, int(start or 0))
        end = min(len(text), int(end if end is not None else start + 400))
        pad = 160  # a citation with no surrounding sentence is not verifiable
        body = text[max(0, start - pad):min(len(text), end + pad)][:MAX_TEXT_SNIPPET]
    return {"doc_id": doc_id, "filename": doc["filename"], "kind": doc["kind"],
            "start": start, "end": end, "text": body}


# ------------------------------------------------------------------- act tools

def record_conclusion(
    ctx: CaseContext, text: str, node_ids: Sequence[str] = (),
    edge_ids: Sequence[str] = (), confidence: str = "medium",
) -> dict:
    """Write something the agent worked out into the case's memory, so it is
    still known next week and does not have to be re-derived."""
    entry = ctx.store.remember(
        kind="conclusion", text=text, node_ids=node_ids, edge_ids=edge_ids,
        confidence=confidence, status="open",
    )
    ctx.chain.append(action="infer", actor="agent", ref=entry["id"],
                     payload={"text": text, "node_ids": list(node_ids),
                              "edge_ids": list(edge_ids), "confidence": confidence})
    return entry


def open_question(ctx: CaseContext, text: str, what_would_answer_it: str = "") -> dict:
    """Something the agent cannot settle from what it has. Held open across
    sessions and re-checked as new documents arrive."""
    entry = ctx.store.remember(
        kind="open_question", text=text, status="open",
        meta={"what_would_answer_it": what_would_answer_it},
    )
    ctx.chain.append(action="infer", actor="agent", ref=entry["id"],
                     payload={"question": text, "answer_needs": what_would_answer_it})
    return entry


def request_evidence(ctx: CaseContext, what: str, why: str) -> dict:
    """Name the document the case is missing. This is the assistant doing the
    officer's thinking for him: it knows which gap is blocking which answer."""
    entry = ctx.store.remember(kind="request", text=what, status="open", meta={"why": why})
    ctx.chain.append(action="infer", actor="agent", ref=entry["id"],
                     payload={"request": what, "why": why})
    return entry


def recall(ctx: CaseContext, query: str = "", kind: str | None = None) -> list[dict]:
    """What the agent already concluded, asked, or requested on this case."""
    if query:
        return ctx.store.search_memory(query)
    return ctx.store.memory(kind=kind)


def chain_of_custody(ctx: CaseContext, limit: int = 12) -> dict:
    """Whether this case's evidence record is intact, and the last things it recorded.

    Added 2026-09-06. The interface has no Custody panel any more (D25), so an
    officer asking *"has anything been tampered with?"* was, until this tool
    existed, asking a question the assistant had no way to answer — about the
    one property the **Blockchain & Cybersecurity** theme is judged on. The
    chain was still being written and still verifiable over HTTP; nothing could
    reach it by asking, which is the only way in now.

    It reports the verification and the tail, never the whole chain: an answer
    is a sentence, not a ledger dump.
    """
    verification = ctx.chain.verify()
    return {
        "intact": bool(verification.get("valid")),
        "entries": verification.get("entries", 0),
        "broken_at": verification.get("broken_at"),
        "reason": verification.get("reason"),
        "recent": ctx.chain.entries(limit=limit),
    }


def case_overview(ctx: CaseContext) -> dict:
    """One call that orients the agent at the start of a run: size of the case,
    what has been ingested, the standing findings, and its own open threads."""
    findings = ctx.store.get_analytics("findings")
    return {
        "case_id": ctx.case_id,
        "counts": ctx.store.counts(),
        "documents": [{"doc_id": d["doc_id"], "kind": d["kind"], "filename": d["filename"]}
                      for d in ctx.store.documents()],
        "findings": (findings or {}).get("value", [])[:10],
        "open_questions": ctx.store.memory(kind="open_question", status="open", limit=20),
        "conclusions": ctx.store.memory(kind="conclusion", limit=20),
        "requests": ctx.store.memory(kind="request", status="open", limit=20),
    }


# --------------------------------------------------------------------- registry

READ_TOOLS = {
    "find_entity": find_entity,
    "neighbours": neighbours,
    "path_between": path_between,
    "timeline": timeline,
    "top_influencers": top_influencers,
    "communities": communities,
    "anomalies": anomalies,
    "read_source_doc": read_source_doc,
    "chain_of_custody": chain_of_custody,
}

ACT_TOOLS = {
    "record_conclusion": record_conclusion,
    "open_question": open_question,
    "request_evidence": request_evidence,
    "recall": recall,
    "case_overview": case_overview,
}

ALL_TOOLS = READ_TOOLS | ACT_TOOLS


def call(ctx: CaseContext, name: str, **kwargs) -> Any:
    """Direct dispatch, for the API and the tests — the same tools the agent binds."""
    if name not in ALL_TOOLS:
        raise KeyError(f"unknown tool {name!r}; available: {sorted(ALL_TOOLS)}")
    return ALL_TOOLS[name](ctx, **kwargs)
