"""The case agent — README §3.4.

The product is not "a graph with a chat box". It is an assistant working under
an investigating officer, on one case, who has already read everything and is
expected to come back with something useful. Three entry points:

* `ask(question)`   — an investigation, not a lookup. The model runs a real
                      tool loop over the graph, verifies what it found against
                      the source documents, and returns the §5.3 contract.
* `brief()`         — what it says *without being asked*, after new documents
                      land: what changed, what it now believes, what it wants
                      next. This is the difference between an assistant and a
                      search box.
* `investigate(id)` — take one finding and work it: pull the paths, read the
                      documents behind them, write a conclusion into case
                      memory, and open a question if it cannot settle it.

Three rules the code enforces so they cannot be prompted away:

1. **Findings come from the graph, not the model.** `analytics/anomalies.py`
   computes them deterministically. The model narrates and investigates them.
   That is D3, and it is why the assistant is still useful offline.
2. **Every answer is verified before it is returned** (`contract.verify`). A
   citation that does not exist in the graph is stripped and reported.
3. **Everything it does is written down** — conclusions and questions into case
   memory, every inference into the hash-chained custody log. The officer can
   ask "why do you think that" a month later and get the same answer.
"""

from __future__ import annotations

import os
from typing import Any, Callable

from backend.agent import tools as T
from backend.agent import offline as offline_mod
from backend.agent.contract import (ANSWER_SCHEMA, empty_answer, parse, verify,
                                    verified_vacuously)
from backend.agent.tools import CaseContext
from backend.case import agent_context_header
from backend.config import ANTHROPIC_MODEL

MAX_TOOL_ITERATIONS = int(os.environ.get("SIH_MAX_TOOL_ITERATIONS", "14"))
EFFORT = os.environ.get("SIH_EFFORT", "high")
MAX_TOKENS = 16000

SYSTEM = """You are the case agent for a single criminal investigation, working \
under the investigating officer who opened this case. You are not a general \
assistant and you are not a search box: you have already read every document in \
this case, and the officer's time is the scarcest thing in the room.

This case could be anything — a fraud, a homicide, an extortion ring, a \
disappearance. What it is will be stated at the top of the message, in the \
officer's own words. Reason in the register of *that* case: the same evidence \
means different things in a financial investigation and in a missing-person \
one, and you should say what it means here.

HOW YOU WORK

Use your tools. Every factual claim you make must come from a tool result in \
this conversation. You have no knowledge of this case other than what the tools \
return, and you must never fill a gap from general knowledge — not a name, not a \
date, not a relationship.

Work the question properly before answering:
- Start by locating the entities involved (`find_entity`). Names in a question \
rarely match ids exactly.
- Follow the structure (`path_between`, `neighbours`, `timeline`).
- Then VERIFY. When an edge matters to your answer, call `read_source_doc` on \
one of its sources and check the text actually says what the edge claims. An \
answer that has not been checked against a document is a draft, not an answer.
- Prefer several small tool calls over one guess.

WHAT AN ANSWER LOOKS LIKE

Answer in the officer's terms, not the graph's. He wants "Ravi's number shared a \
tower with Suneel's at 22:10 on 3 August, and Suneel holds the account" — not a \
description of nodes and edges. Lead with the finding. Keep it short; he is \
reading this between other work.

Cite everything: `cited_nodes` and `cited_edges` are the ids you actually used, \
and `highlight_path` is the route through the graph the officer should see lit \
up. These are checked against the real graph after you answer, so a citation you \
did not get from a tool will be caught and will discredit the whole answer.

Be exact about strength of evidence. A tower co-location is proximity, not \
contact. A co-occurrence edge means two names appeared near each other in one \
document — that is a lead, not a relationship. Put that in `caveats` rather than \
softening the answer itself.

If the case does not contain the answer, say so plainly and use \
`request_evidence` to name the document that would settle it. "I don't have it, \
here is what would tell you" is a good answer. Inventing a plausible one is the \
only unforgivable failure here.

BEING USEFUL WITHOUT BEING ASKED

You keep the case's memory. Use `recall` to check what you already concluded so \
you do not repeat yourself, `record_conclusion` when you work something out that \
is worth keeping, and `open_question` for what you could not settle. The officer \
should never have to tell you the same thing twice, and should never have to read \
a file to find out something you already know."""


class AgentUnavailable(RuntimeError):
    """No API key, no network, or the API declined. Never fatal — the caller
    falls back to the deterministic path."""


def _client():
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise AgentUnavailable("the anthropic package is not installed") from exc
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise AgentUnavailable("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic()


def model_available() -> bool:
    try:
        _client()
        return True
    except AgentUnavailable:
        return False


# --------------------------------------------------------------- tool binding

def _bind(ctx: CaseContext) -> list[Callable]:
    """Build model-facing tools bound to one case.

    The schemas come from these signatures and docstrings, so the wording here
    is part of the system's behaviour — keep it accurate. They are built per
    request because each is closed over exactly one `CaseContext`, which is how
    a tool is made structurally incapable of naming another case.
    """
    from anthropic import beta_tool

    @beta_tool
    def find_entity(query: str, type: str = "") -> str:
        """Find people, phones, accounts, vehicles, locations or organisations in this case by name or identifier.

        Args:
            query: A name, phone number, account number or fragment of one.
            type: Optionally restrict to person, phone, organization, location, vehicle, account, device, event or document.
        """
        return _json(T.find_entity(ctx, query, type or None))

    @beta_tool
    def neighbours(node_id: str, depth: int = 1, edge_types: str = "") -> str:
        """Everything directly connected to an entity, out to `depth` hops.

        Args:
            node_id: The entity id, e.g. person:ravi_kumar.
            depth: How many hops out to walk. Keep to 1 or 2; 3 returns most of the case.
            edge_types: Optional comma-separated filter, e.g. "CALLED,TRANSFERRED_TO".
        """
        types = [t.strip() for t in edge_types.split(",") if t.strip()] or None
        return _json(T.neighbours(ctx, node_id, depth=depth, edge_types=types))

    @beta_tool
    def path_between(a: str, b: str, max_hops: int = 6) -> str:
        """How two entities are connected: the shortest routes between them and the edges on each.

        Args:
            a: Start entity id.
            b: End entity id.
            max_hops: Longest path to consider.
        """
        return _json(T.path_between(ctx, a, b, max_hops=max_hops))

    @beta_tool
    def timeline(node_id: str = "", start: str = "", end: str = "") -> str:
        """Dated activity in order — calls, messages, transfers and tower hits.

        Args:
            node_id: Optionally restrict to one entity.
            start: ISO timestamp lower bound, e.g. 2026-08-03T00:00:00+05:30.
            end: ISO timestamp upper bound.
        """
        return _json(T.timeline(ctx, node_id or None, start or None, end or None))

    @beta_tool
    def top_influencers(metric: str = "betweenness", limit: int = 10) -> str:
        """Who matters most in this network, with the reason each one scored.

        Args:
            metric: "betweenness" for brokers and bridges, "pagerank" or "degree" for volume.
            limit: How many to return.
        """
        return _json(T.top_influencers(ctx, metric=metric, limit=limit))

    @beta_tool
    def communities() -> str:
        """The clusters in this network — the separate groups and who is in each."""
        return _json(T.communities(ctx))

    @beta_tool
    def anomalies(window_hours: int = 24) -> str:
        """Unusual activity the system detected: call spikes, handset swaps, one-way accounts, numbers that went silent.

        Args:
            window_hours: Bucket size for volume analysis.
        """
        return _json(T.anomalies(ctx, window_hours=window_hours))

    @beta_tool
    def read_source_doc(doc_id: str, start: int = -1, end: int = -1) -> str:
        """Read the original document text behind a fact, to check that it says what the graph claims.

        Args:
            doc_id: Document id, e.g. doc:fir_114_001, from an entity's or edge's sources.
            start: Character offset to read from. Omit for the start of the document.
            end: Character offset to read to.
        """
        return _json(T.read_source_doc(
            ctx, doc_id,
            None if start < 0 else start,
            None if end < 0 else end,
        ))

    @beta_tool
    def recall(query: str = "", kind: str = "") -> str:
        """What you already concluded, asked or requested on this case in earlier sessions.

        Args:
            query: Optional text to search your own notes for.
            kind: Optionally one of conclusion, open_question, request, briefing, note.
        """
        return _json(T.recall(ctx, query, kind or None))

    @beta_tool
    def record_conclusion(text: str, node_ids: str = "", edge_ids: str = "",
                          confidence: str = "medium") -> str:
        """Save something you worked out, so it is still known next week without re-deriving it.

        Args:
            text: The conclusion, in one or two sentences the officer would understand.
            node_ids: Comma-separated node ids it rests on.
            edge_ids: Comma-separated edge ids it rests on.
            confidence: high, medium or low.
        """
        return _json(T.record_conclusion(
            ctx, text, _ids(node_ids), _ids(edge_ids), confidence))

    @beta_tool
    def open_question(text: str, what_would_answer_it: str = "") -> str:
        """Record something you could not settle from the case as it stands. It is re-checked as new documents arrive.

        Args:
            text: The question.
            what_would_answer_it: The document or record that would resolve it.
        """
        return _json(T.open_question(ctx, text, what_would_answer_it))

    @beta_tool
    def request_evidence(what: str, why: str) -> str:
        """Tell the officer which document the case is missing and what it would unlock.

        Args:
            what: The record needed, e.g. "CDR for 9915xxxxxx covering 1-10 August".
            why: What it would settle.
        """
        return _json(T.request_evidence(ctx, what, why))

    return [find_entity, neighbours, path_between, timeline, top_influencers,
            communities, anomalies, read_source_doc, recall,
            record_conclusion, open_question, request_evidence]


def _ids(raw: str) -> list[str]:
    return [x.strip() for x in (raw or "").split(",") if x.strip()]


def _json(value: Any) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, default=str)[:60000]


# ------------------------------------------------------------------- the agent

class CaseAgent:
    """One agent per case. Holds no state of its own — the case does."""

    def __init__(self, ctx: CaseContext):
        self.ctx = ctx

    # ------------------------------------------------------------------- ask

    def ask(self, question: str, *, actor: str = "officer") -> dict:
        self.ctx.chain.append(action="query", actor=actor, ref=f"question:{question[:120]}",
                              payload={"question": question})
        try:
            answer = self._run(self._question_prompt(question))
        except AgentUnavailable as exc:
            answer = self._offline_answer(question, str(exc))

        answer = verify(answer, self.ctx.store)
        self.ctx.chain.append(
            action="infer", actor="agent", ref=f"answer:{question[:80]}",
            payload={"answer": answer.get("answer"),
                     "cited_nodes": answer.get("cited_nodes"),
                     "cited_edges": answer.get("cited_edges")},
        )
        return answer

    def _header(self) -> str:
        """The case's own identity and the officer's brief, in front of the
        agent on every turn. This is what lets one engine work a fraud case and
        a homicide without either being special-cased — the graph supplies the
        facts, this supplies what kind of case they belong to."""
        return agent_context_header(self.ctx.case_id) or f"Case {self.ctx.case_id}."

    def _question_prompt(self, question: str) -> str:
        overview = T.case_overview(self.ctx)
        return (
            f"{self._header()}\n\n"
            f"The graph holds {overview['counts']['nodes']} entities "
            f"and {overview['counts']['edges']} links from "
            f"{overview['counts']['documents']} documents.\n\n"
            f"What you already concluded on this case:\n{_json(overview['conclusions'][:8])}\n\n"
            f"Questions you are still holding open:\n{_json(overview['open_questions'][:8])}\n\n"
            f"The officer asks:\n\n{question}\n\n"
            "Work it with your tools, verify the edges that matter against their source "
            "documents, then answer."
        )

    # ----------------------------------------------------------------- brief

    def brief(self, *, since_rev: int | None = None, actor: str = "system") -> dict:
        """What the assistant says on its own initiative.

        The findings themselves are computed by `analytics/` — deterministic,
        cited, and available with no API key. The model turns them into
        something an officer can act on and files what it concludes. If there
        is no model available, the deterministic brief is still returned: the
        officer is never left with nothing.
        """
        findings = (self.ctx.store.get_analytics("findings") or {}).get("value", []) or []
        counts = self.ctx.store.counts()
        already = {m["text"] for m in self.ctx.store.memory(kind="briefing", limit=200)}
        fresh = [f for f in findings if f.get("headline") not in already]

        deterministic = {
            "case_id": self.ctx.case_id,
            "counts": counts,
            "findings": findings[:8],
            "new_findings": len(fresh),
            "requests": self.ctx.store.memory(kind="request", status="open", limit=10),
            "open_questions": self.ctx.store.memory(kind="open_question", status="open", limit=10),
        }

        if not findings:
            # §5.6 says `verified` is always present on /brief. It was not here,
            # and the front end had to read a documented field defensively.
            # Nothing was cited because nothing has been found yet, which is a
            # pass with nothing in it — not a verification failure.
            narrative = empty_answer(
                "Nothing stands out in this case yet. Add documents — CDRs and bank "
                "statements produce the strongest links.", confidence="low",
            )
            narrative["verified"] = verified_vacuously()
            deterministic["narrative"] = narrative
            return deterministic

        try:
            narrative = self._run(self._brief_prompt(fresh or findings, counts))
        except AgentUnavailable as exc:
            narrative = self._offline_brief(findings, str(exc))

        deterministic["narrative"] = verify(narrative, self.ctx.store)
        for f in fresh[:6]:
            self.ctx.store.remember(kind="briefing", text=f.get("headline", ""),
                                    node_ids=f.get("node_ids", []),
                                    edge_ids=f.get("edge_ids", []), status="delivered")
        return deterministic

    def _brief_prompt(self, findings: list[dict], counts: dict) -> str:
        return (
            f"{self._header()}\n\n"
            f"It now holds {counts['nodes']} entities and "
            f"{counts['edges']} links from {counts['documents']} documents.\n\n"
            "The analysis layer surfaced these, computed from the graph — they are facts, "
            "not suggestions, and you should verify the ones you lead with:\n"
            f"{_json(findings[:8])}\n\n"
            "Brief the investigating officer. He has not looked at this case today and has "
            "no time to read it. Lead with the single thing that should change what he does "
            "next, verify it against a source document before you state it, and say plainly "
            "what you would want next. Use record_conclusion for anything worth keeping and "
            "request_evidence for the gap that is actually blocking you."
        )

    # ----------------------------------------------------------- investigate

    def investigate(self, finding_id: str) -> dict:
        """Work one finding properly: pull the paths, read the documents behind
        them, and write down what it concludes."""
        findings = (self.ctx.store.get_analytics("findings") or {}).get("value", []) or []
        finding = next((f for f in findings if f.get("id") == finding_id), None)
        if finding is None:
            return empty_answer(f"No finding {finding_id} in this case.")

        prompt = (
            f"{self._header()}\n\n"
            f"Investigate this finding properly and tell the officer "
            f"whether it holds up:\n\n{_json(finding)}\n\n"
            "Pull the paths involved, read the source documents behind the edges it rests on, "
            "and say whether the evidence supports it, contradicts it, or is too thin either "
            "way. Record what you conclude. If a specific missing document would settle it, "
            "request it by name."
        )
        try:
            answer = self._run(prompt)
        except AgentUnavailable as exc:
            answer = self._offline_finding(finding, str(exc))
        return verify(answer, self.ctx.store)

    # -------------------------------------------------------------- the loop

    def _run(self, prompt: str) -> dict:
        """One tool-driven run. The SDK's tool runner owns the loop; we own the
        bound tools, the contract and the iteration cap."""
        import anthropic

        client = _client()
        try:
            runner = client.beta.messages.tool_runner(
                model=ANTHROPIC_MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM,
                tools=_bind(self.ctx),
                max_iterations=MAX_TOOL_ITERATIONS,
                thinking={"type": "adaptive"},
                output_config={
                    "effort": EFFORT,
                    "format": {"type": "json_schema", "schema": ANSWER_SCHEMA},
                },
                messages=[{"role": "user", "content": prompt}],
            )
            message = runner.until_done()
        except anthropic.NotFoundError as exc:
            raise AgentUnavailable(f"model {ANTHROPIC_MODEL} not available: {exc}") from exc
        except anthropic.RateLimitError as exc:
            raise AgentUnavailable(f"rate limited: {exc}") from exc
        except anthropic.APIStatusError as exc:
            raise AgentUnavailable(f"API returned {exc.status_code}: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise AgentUnavailable(f"could not reach the API: {exc}") from exc

        if getattr(message, "stop_reason", None) == "refusal":
            details = getattr(message, "stop_details", None)
            raise AgentUnavailable(f"the model declined this request ({details})")

        text = next((b.text for b in message.content if getattr(b, "type", "") == "text"), "")
        return parse(text)

    # ------------------------------------------------------- offline fallback

    def _offline_answer(self, question: str, reason: str) -> dict:
        """No model? Still answer — and answer the *question*, not the name.

        This used to hand the whole sentence to `find_entity`, which is a
        substring match on labels, so any question phrased as a question matched
        nothing at all. §9.2 demo query 1 is phrased as a question, so with no
        key the centrepiece of the pitch returned "Nothing in this case matches
        that name or identifier."

        `agent/offline.py` routes it over the graph instead — a path between two
        named entities, the centrality ranking, an entity profile, or the
        candidates it could not choose between. On the demo machine at 11:00
        this is the difference between a live system and a dead one.
        """
        return offline_mod.answer(self.ctx, question, reason)

    def _offline_brief(self, findings: list[dict], reason: str) -> dict:
        top = findings[0]
        return {
            "answer": top.get("detail") or top.get("headline", ""),
            "cited_nodes": top.get("node_ids", []),
            "cited_edges": top.get("edge_ids", []),
            "highlight_path": top.get("node_ids", [])[:6],
            "confidence": "medium",
            "caveats": [
                f"Written from the graph's own analysis; the reasoning model is unavailable "
                f"({reason}). The finding itself is computed from the case data and stands.",
            ],
        }

    def _offline_finding(self, finding: dict, reason: str) -> dict:
        return {
            "answer": finding.get("detail", ""),
            "cited_nodes": finding.get("node_ids", []),
            "cited_edges": finding.get("edge_ids", []),
            "highlight_path": finding.get("node_ids", [])[:6],
            "confidence": "low",
            "caveats": [f"Not investigated — the reasoning model is unavailable ({reason})."],
        }
