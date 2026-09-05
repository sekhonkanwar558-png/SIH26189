"""The answer contract — README §5.3 — and the check that makes it mean something.

§5.3 says `cited_nodes` and `cited_edges` must not be empty, and that an empty
citation list is an error because it means the agent answered from its own
knowledge rather than from the case. That is a rule about *behaviour*, so it is
enforced in code rather than asked for in a prompt: `verify()` checks every id
the model returned against the case graph and reports what did not exist.

A model that hallucinates `e_9999` gets caught here, not by a judge.
"""

from __future__ import annotations

import json
import re
from typing import Any

from backend.graph.store import CaseStore

CONFIDENCE_LEVELS = ("high", "medium", "low")

ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "string",
            "description": "The answer for the investigating officer. Plain, specific, "
                           "and built only from what the tools returned.",
        },
        "cited_nodes": {
            "type": "array", "items": {"type": "string"},
            "description": "Node ids the answer rests on, exactly as the tools returned them.",
        },
        "cited_edges": {
            "type": "array", "items": {"type": "string"},
            "description": "Edge ids the answer rests on, e.g. e_1042.",
        },
        "highlight_path": {
            "type": "array", "items": {"type": "string"},
            "description": "Ordered node ids forming the path to light up on the graph. "
                           "Empty if the answer is not about a connection.",
        },
        "confidence": {"type": "string", "enum": list(CONFIDENCE_LEVELS)},
        "caveats": {
            "type": "array", "items": {"type": "string"},
            "description": "What would make this wrong. Tower co-location is proximity, "
                           "not contact; a co-occurrence edge is not a relationship.",
        },
    },
    "required": ["answer", "cited_nodes", "cited_edges", "highlight_path",
                 "confidence", "caveats"],
    "additionalProperties": False,
}


def empty_answer(message: str, *, confidence: str = "low") -> dict:
    return {"answer": message, "cited_nodes": [], "cited_edges": [],
            "highlight_path": [], "confidence": confidence, "caveats": []}


def verified_vacuously() -> dict:
    """The `verified` block for an answer that cites nothing *because there was
    nothing to cite*.

    §5.6 describes this block as always present, and it was not: `/brief` on a
    case with no findings returned early with a bare message and no `verified`
    at all, so the front end had to read a documented field defensively.

    This is deliberately not `verify()` on an empty answer, which fails on
    purpose: there, a model was asked about a case and answered without resting
    on it. Here the system itself is saying it has found nothing yet — a
    statement about the case, not a claim drawn from it. Nothing was checked, so
    nothing was dropped and nothing failed. Reporting `ok: false` would put a
    red "could not be verified" panel on every brand-new case.
    """
    return {"ok": True, "dropped_nodes": [], "dropped_edges": []}


def parse(text: str) -> dict:
    """Structured outputs guarantee valid JSON in the first text block. This is
    the belt-and-braces path for the case where something upstream changed."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"\{.*\}", text or "", re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return empty_answer(
        "The assistant did not return a usable answer. Nothing was invented in its place.",
    )


def verify(answer: dict, store: CaseStore) -> dict:
    """Check every cited id against the graph. Unknown ids are removed and
    reported — an answer that cites something which does not exist is worse
    than one that admits it found nothing."""
    answer = dict(answer)
    answer.setdefault("caveats", [])
    dropped_nodes, dropped_edges = [], []

    kept_nodes = []
    for node_id in answer.get("cited_nodes") or []:
        (kept_nodes if store.get_node(node_id) else dropped_nodes).append(node_id)
    kept_edges = []
    for edge_id in answer.get("cited_edges") or []:
        (kept_edges if store.get_edge(edge_id) else dropped_edges).append(edge_id)

    path = [n for n in (answer.get("highlight_path") or []) if store.get_node(n)]

    answer["cited_nodes"] = kept_nodes
    answer["cited_edges"] = kept_edges
    answer["highlight_path"] = path
    answer["verified"] = {
        "ok": bool(kept_nodes) and not dropped_nodes and not dropped_edges,
        "dropped_nodes": dropped_nodes,
        "dropped_edges": dropped_edges,
    }

    if dropped_nodes or dropped_edges:
        answer["caveats"].append(
            "Some citations did not exist in this case's graph and were removed: "
            + ", ".join(dropped_nodes + dropped_edges)
        )
        answer["confidence"] = "low"

    if not kept_nodes:
        # §5.3: treat this as an error and say so, rather than showing prose
        # that looks like an answer.
        answer["caveats"].append(
            "No verifiable citation — this answer is not backed by anything in the case "
            "graph and should not be relied on."
        )
        answer["confidence"] = "low"
        answer["verified"]["ok"] = False

    return answer
