"""FastAPI routes — the contract the front end is built against.

**This file is the boundary between the two halves of the project.** Everything
below it (ingest, graph, analytics, agent, custody) is the backend team's. The
front end — every screen, every pixel, the split-screen layout, the Cytoscape
canvas — is Jashan's, built on top of these endpoints. See README §5.6, which
is the frozen shape of what comes back, and §10.1 for who owns what.

Design rules for anyone adding a route here:

* **Return contract shapes, not view models.** `/ask` returns §5.3 exactly. No
  endpoint here decides how anything looks; that is not this file's job.
* **Every route is scoped to a case.** The case id is in the path, it is
  validated, and every handler opens exactly one `CaseStore` from it. There is
  no endpoint that reads across cases except `GET /api/cases`, which reads only
  metadata (§2.4).
* **Never leak the API key.** Not in an error, not in a health check (§8).
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend import case as case_mod
from backend.agent.loop import CaseAgent, model_available
from backend.agent.tools import CaseContext
from backend.analytics.metrics import recompute
from backend.config import ANTHROPIC_MODEL, BadCaseId, check_case_id
from backend.custody.chain import CustodyChain
from backend.graph.nx_adapter import case_graphs
from backend.graph.store import CaseStore
from backend.ingest.ner import ner_backend
from backend.agent.loop import AgentUnavailable
from backend.ingest.pipeline import ingest_file, ingest_text

app = FastAPI(
    title="SIH26189 — Criminal Network Analysis",
    description="Per-case investigative agent over a per-case knowledge graph.",
    version="0.1.0",
)

# The front end runs on its own dev server. Wide open is correct for a local
# investigative tool that never leaves the machine; it is not correct for a
# deployment, and whoever deploys this must narrow it.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)


# ------------------------------------------------------------------- helpers

def _open(case_id: str) -> tuple[CaseStore, CustodyChain]:
    try:
        check_case_id(case_id)
    except BadCaseId as exc:
        raise HTTPException(400, str(exc)) from exc
    if case_mod.read_meta(case_id) is None:
        raise HTTPException(404, f"no case {case_id!r}")
    return CaseStore(case_id), CustodyChain(case_id)


def _ctx(case_id: str, actor: str = "officer") -> CaseContext:
    store, chain = _open(case_id)
    return CaseContext(store, chain, actor=actor)


# -------------------------------------------------------------------- models

class CaseCreate(BaseModel):
    case_id: str = Field(..., description="lowercase letters, digits, - and _")
    title: str = ""
    officer: str = "officer:unknown"
    case_type: str = Field("", description="free text: fraud, homicide, extortion, ...")
    brief: str = Field("", description="what the officer wants the agent to know going in")


class CaseUpdate(BaseModel):
    title: str | None = None
    case_type: str | None = None
    brief: str | None = None
    status: str | None = None


class TextIngest(BaseModel):
    filename: str = "note.txt"
    text: str
    kind: str = "note"


class Question(BaseModel):
    question: str
    actor: str = "officer"


# --------------------------------------------------------------------- meta

@app.get("/api/health")
def health() -> dict:
    """What is actually wired up. Reports whether a reasoning model is
    reachable — never the key itself (§8)."""
    return {
        "ok": True,
        "model": ANTHROPIC_MODEL,
        "model_available": model_available(),
        "ner": ner_backend(),
        "cases": len(case_mod.list_cases()),
    }


# -------------------------------------------------------------------- cases

@app.get("/api/cases")
def list_cases(officer: str | None = Query(None)) -> list[dict]:
    """Every case, or one officer's. He runs several at once and each has its
    own agent, its own graph and its own memory."""
    return case_mod.list_cases(officer)


@app.post("/api/cases", status_code=201)
def create_case(body: CaseCreate) -> dict:
    try:
        meta = case_mod.create_case(
            body.case_id, title=body.title, officer=body.officer,
            case_type=body.case_type, brief=body.brief,
        )
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from exc
    except BadCaseId as exc:
        raise HTTPException(400, str(exc)) from exc
    return meta.to_dict()


@app.get("/api/cases/{case_id}")
def get_case(case_id: str) -> dict:
    store, chain = _open(case_id)
    with store:
        meta = case_mod.read_meta(case_id)
        return {
            **meta.to_dict(),
            "counts": store.counts(),
            "documents": store.documents(),
            "custody": chain.verify(),
            "ner": ner_backend(),
        }


@app.patch("/api/cases/{case_id}")
def update_case(case_id: str, body: CaseUpdate) -> dict:
    meta = case_mod.update_meta(case_id, **body.model_dump(exclude_none=True))
    if meta is None:
        raise HTTPException(404, f"no case {case_id!r}")
    return meta.to_dict()


@app.delete("/api/cases/{case_id}")
def delete_case(case_id: str, confirm: str = Query(..., description="must equal the case id")):
    if confirm != case_id:
        raise HTTPException(400, "pass ?confirm=<case_id> to delete a case")
    if not case_mod.delete_case(case_id):
        raise HTTPException(404, f"no case {case_id!r}")
    return {"deleted": case_id}


# ---------------------------------------------------------------- documents

@app.post("/api/cases/{case_id}/documents")
async def upload_document(
    case_id: str, file: UploadFile = File(...), kind: str | None = Query(None),
    actor: str = Query("officer"),
) -> dict:
    """The officer's one job: hand the bot a document. Everything else —
    parsing, entity extraction, graph, analytics, custody — happens here, with
    no model in the path (§3.1), so a 40-page upload comes back in seconds."""
    store, chain = _open(case_id)
    suffix = Path(file.filename or "upload").suffix
    with store:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = Path(tmp.name)
        try:
            # The officer's name for the file, not the tempfile's: it becomes
            # the doc id, every citation label and the custody reference.
            result = ingest_file(store, chain, tmp_path, kind=kind, actor=actor,
                                 doc_id=None, filename=file.filename)
        except ValueError as exc:
            raise HTTPException(415, str(exc)) from exc
        finally:
            tmp_path.unlink(missing_ok=True)
        stats = recompute(store)
        return {"document": result.as_dict(), "analytics": stats,
                "counts": store.counts()}


@app.post("/api/cases/{case_id}/documents/text")
def upload_text(case_id: str, body: TextIngest, actor: str = Query("officer")) -> dict:
    store, chain = _open(case_id)
    with store:
        result = ingest_text(store, chain, body.text, filename=body.filename,
                             kind=body.kind, actor=actor)
        stats = recompute(store)
        return {"document": result.as_dict(), "analytics": stats,
                "counts": store.counts()}


@app.get("/api/cases/{case_id}/documents")
def list_documents(case_id: str) -> list[dict]:
    store, _ = _open(case_id)
    with store:
        return store.documents()


@app.get("/api/cases/{case_id}/source")
def source_text(case_id: str, doc_id: str, start: int | None = None,
                end: int | None = None) -> dict:
    """The text behind a citation. This is what a citation clicks through to."""
    ctx = _ctx(case_id)
    with ctx.store:
        from backend.agent.tools import read_source_doc

        result = read_source_doc(ctx, doc_id, start, end)
        if "error" in result:
            raise HTTPException(404, result["error"])
        return result


# -------------------------------------------------------------------- graph

@app.get("/api/cases/{case_id}/graph")
def get_graph(case_id: str, include_documents: bool = Query(False)) -> dict:
    """The whole case graph. Document nodes are excluded by default — they are
    hubs that connect everything named in a report to everything else and make
    the picture unreadable. Pass ?include_documents=true to see them."""
    store, _ = _open(case_id)
    with store:
        nodes = [n.to_dict() for n in store.nodes()
                 if include_documents or n.type != "document"]
        keep = {n["id"] for n in nodes}
        edges = [e.to_dict() for e in store.edges()
                 if e.src in keep and e.dst in keep]
        return {"nodes": nodes, "edges": edges, "counts": store.counts()}


@app.get("/api/cases/{case_id}/nodes/{node_id:path}")
def get_node(case_id: str, node_id: str) -> dict:
    """One entity's full profile: attributes, every link, and every document it
    was extracted from with the offsets."""
    store, _ = _open(case_id)
    with store:
        node = store.get_node(node_id)
        if node is None:
            raise HTTPException(404, f"no entity {node_id!r} in case {case_id!r}")
        edges = store.edges(node_id=node_id)
        neighbour_ids = {e.dst if e.src == node_id else e.src for e in edges}
        return {
            "node": node.to_dict(),
            "edges": [e.to_dict() for e in edges],
            "neighbours": [n.to_dict() for n in
                           (store.get_node(i) for i in sorted(neighbour_ids)) if n],
            # Deduplicated: `sources` holds an offset per mention, so mapping
            # it straight to documents listed the same FIR three times and the
            # interface read "out of 12 documents" on a case that has nine.
            "documents": [d for d in (store.document(i) for i in
                                      dict.fromkeys(s["doc_id"] for s in node.sources)) if d],
        }


@app.get("/api/cases/{case_id}/path")
def get_path(case_id: str, a: str, b: str, max_hops: int = 6) -> list[dict]:
    ctx = _ctx(case_id)
    with ctx.store:
        from backend.agent.tools import path_between

        return path_between(ctx, a, b, max_hops=max_hops)


# ---------------------------------------------------------------- analytics

@app.get("/api/cases/{case_id}/analytics")
def get_analytics(case_id: str, metric: str = "betweenness", limit: int = 10) -> dict:
    ctx = _ctx(case_id)
    with ctx.store:
        from backend.agent import tools as T

        return {
            "influencers": T.top_influencers(ctx, metric=metric, limit=limit),
            "communities": T.communities(ctx),
            "anomalies": T.anomalies(ctx),
            "findings": (ctx.store.get_analytics("findings") or {}).get("value", []),
        }


@app.post("/api/cases/{case_id}/analytics/recompute")
def force_recompute(case_id: str) -> dict:
    store, _ = _open(case_id)
    with store:
        return recompute(store)


@app.get("/api/cases/{case_id}/timeline")
def get_timeline(case_id: str, node_id: str | None = None,
                 start: str | None = None, end: str | None = None) -> list[dict]:
    ctx = _ctx(case_id)
    with ctx.store:
        from backend.agent.tools import timeline

        return timeline(ctx, node_id, start, end)


# -------------------------------------------------------------------- agent

@app.post("/api/cases/{case_id}/ask")
def ask(case_id: str, body: Question) -> dict:
    """The officer's question, answered by this case's agent. Returns §5.3."""
    ctx = _ctx(case_id, actor=body.actor)
    with ctx.store:
        try:
            return CaseAgent(ctx).ask(body.question, actor=body.actor)
        except AgentUnavailable as exc:
            # 503, not a fabricated answer: the assistant is either
            # working or honestly unavailable (D22). The UI shows this
            # with a retry; everything else in the case still works.
            raise HTTPException(503, f"shikonye is unavailable: {exc}") from exc


@app.get("/api/cases/{case_id}/brief")
def brief(case_id: str) -> dict:
    """What the agent says without being asked: what changed, what it now
    believes, and what it wants next."""
    ctx = _ctx(case_id)
    with ctx.store:
        try:
            return CaseAgent(ctx).brief()
        except AgentUnavailable as exc:
            # 503, not a fabricated answer: the assistant is either
            # working or honestly unavailable (D22). The UI shows this
            # with a retry; everything else in the case still works.
            raise HTTPException(503, f"shikonye is unavailable: {exc}") from exc


@app.post("/api/cases/{case_id}/findings/{finding_id}/investigate")
def investigate(case_id: str, finding_id: str) -> dict:
    ctx = _ctx(case_id)
    with ctx.store:
        try:
            return CaseAgent(ctx).investigate(finding_id)
        except AgentUnavailable as exc:
            # 503, not a fabricated answer: the assistant is either
            # working or honestly unavailable (D22). The UI shows this
            # with a retry; everything else in the case still works.
            raise HTTPException(503, f"shikonye is unavailable: {exc}") from exc


@app.get("/api/cases/{case_id}/memory")
def get_memory(case_id: str, kind: str | None = None, status: str | None = None) -> list[dict]:
    """Everything the agent has concluded, asked or requested on this case."""
    store, _ = _open(case_id)
    with store:
        return store.memory(kind=kind, status=status)


@app.post("/api/cases/{case_id}/memory/{mem_id}/close")
def close_memory(case_id: str, mem_id: str, status: str = Query("resolved")) -> dict:
    store, _ = _open(case_id)
    with store:
        entry = store.close_memory(mem_id, status)
        if entry is None:
            raise HTTPException(404, f"no memory entry {mem_id!r}")
        return entry


# ------------------------------------------------------------- conversation

@app.get("/api/cases/{case_id}/conversation")
def conversation(case_id: str, limit: int = 200) -> dict:
    """The officer's thread with shikonye, oldest first.

    It lives on the case, not in a browser: open the case on another machine, or
    hand it to a colleague, and the conversation is there. That is also what lets
    `ask` send the model a real exchange rather than one cold question.
    """
    store, _ = _open(case_id)
    with store:
        return {"turns": store.conversation(limit=limit)}


@app.delete("/api/cases/{case_id}/conversation")
def clear_conversation(case_id: str, confirm: str = Query(...)) -> dict:
    """Start the thread again. `confirm` must be the case id — this deletes what
    the assistant and the officer said to each other, and nothing else brings it
    back. The custody chain still holds every question that was asked."""
    if confirm != case_id:
        raise HTTPException(400, "confirm must be the case id")
    store, _ = _open(case_id)
    with store:
        return {"cleared": store.clear_conversation()}


# ------------------------------------------------------------------ custody

@app.get("/api/cases/{case_id}/custody")
def custody(case_id: str, limit: int | None = None) -> dict:
    """The hash-chained log, and whether it still verifies. §3.6, §9.3."""
    _, chain = _open(case_id)
    return {"verification": chain.verify(), "entries": chain.entries(limit)}
