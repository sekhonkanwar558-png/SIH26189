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
   That is D3: the model can only ever describe what the graph already holds.

   **There is no fallback and there must not be one** (D22). If the assistant
   cannot run, the officer is told so and gets a retry — never a graph lookup
   dressed up as an answer. A degraded impostor that answers some questions and
   silently cannot answer others is worse than an outage, because he cannot tell
   which one he is talking to. The graph, the documents, the findings, the paths
   and the custody chain all remain fully usable without it; what stops is the
   assistant, and it says so.
2. **Every answer is verified before it is returned** (`contract.verify`). A
   citation that does not exist in the graph is stripped and reported.
3. **Everything it does is written down** — conclusions and questions into case
   memory, every inference into the hash-chained custody log. The officer can
   ask "why do you think that" a month later and get the same answer.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Callable

from backend.agent import tools as T
from backend.agent.contract import (ANSWER_SCHEMA, empty_answer, parse, verify,
                                    verified_vacuously)
from backend.agent.tools import CaseContext
from backend.case import agent_context_header
from backend.config import ANTHROPIC_MODEL

# uvicorn configures this logger at INFO. A bare module logger would be silent
# in the server console unless someone edits a logging config, and the one
# thing we want visible on a $3 budget is what a question cost.
log = logging.getLogger("uvicorn.error")

MAX_TOOL_ITERATIONS = int(os.environ.get("SIH_MAX_TOOL_ITERATIONS", "14"))
EFFORT = os.environ.get("SIH_EFFORT", "high")
MAX_TOKENS = 16000
# How much of the thread the model sees. Long enough that a real working
# session holds together; bounded so a case worked for months does not send
# a year of conversation on every question.
CONVERSATION_TURNS = int(os.environ.get("SIH_CONVERSATION_TURNS", "24"))
# How many findings one briefing covers. The same number is shown to the
# model and marked delivered; they must not drift apart.
BRIEF_FINDINGS = 8

# One blank line between two blocks of text.
PARA = """

"""

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
- Never guess what a tool could tell you. But when a step needs several \
facts, ask for them in the SAME turn: parallel calls cost one round-trip \
and serial ones cost several, and the officer is sitting there waiting.

WHAT AN ANSWER LOOKS LIKE

Answer in the officer's terms, not the graph's. He wants "these two numbers were \nin the same place an hour before it happened, and one holds the account" — not a \ndescription of nodes and edges. Lead with the finding. Keep it short; he is \
reading this between other work.

Cite everything: `cited_nodes` and `cited_edges` are the ids you actually used, \
and `highlight_path` is the route through the graph the officer should see lit \
up. These are checked against the real graph after you answer, so a citation not \
from a tool is caught and discredits the answer.

Be exact about strength of evidence. Being in the same place is not contact. A \nco-occurrence edge means two names appeared near each other in one \ndocument — that is a lead, not a relationship. Put that in `caveats` rather than \
softening the answer itself.

If the case does not contain the answer, say so plainly and use \
`request_evidence` to name the document that would settle it. "I don't have it, \
here is what would tell you" is a good answer. Inventing a plausible one is the \
only unforgivable failure here.

WHAT THE OFFICER CAN ACTUALLY SEE

One chat, and the graph when your answer has a route through it. No document list, no findings panel, no custody screen, no commands. **Anything he cannot see, he gets by asking you** — so answer "what's in this case", "what have you found", "where did that come from", "has this been tampered with" in words, fully, rather than sending him to look. Use `chain_of_custody` for tampering, integrity, or whether the record can be trusted.

He is not technical. He says "the account the money went to", never an id. Resolving that is your job and it is never his. Do not ask him for an id, do not print ids in your answer, and do not teach him a syntax.

WHAT YOU ARE RUNNING ON

This case has a brain on disk — its graph, its analytics, its memory, its custody chain — and it grows every time a document arrives. You are not holding this case in a context window; you are querying that brain with tools. So never say you have "read" something you did not just fetch, never claim the case holds something because it feels likely, and what you record with `record_conclusion` outlives this conversation and is read back to you months from now.

BEING USEFUL WITHOUT BEING ASKED

You keep the case's memory: `recall` what you concluded before, `record_conclusion` \nwhat is worth keeping, `open_question` what you could not settle. He should never \ntell you a thing twice.

Be curious. If working his question turns up something he did not ask about and \nwould want — a name the paperwork never has, a pattern that contradicts the file — \ngive it a line at the end. You are worth having because you volunteer what he did \nnot think to ask."""


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
    """Whether a key is *set* — not whether it works.

    This constructs a client and nothing more: it never calls the API, so a
    typo, a revoked key, an empty balance and a dead network all report True.
    `GET /api/health` says the same thing, which is why the demo script tells
    the presenter to ask Suishōdama a question rather than read a green tick.
    """
    try:
        _client()
        return True
    except AgentUnavailable:
        return False


def _uncached(params: dict[str, Any]) -> dict[str, Any]:
    """The same request with every cache breakpoint removed.

    Used only when the API rejects caching. The top-level marker is simply not
    passed; the explicit one lives inside a `system` block and has to be lifted
    out of the copy, or the retry is rejected for the same reason.
    """
    out = dict(params)
    system = out.get("system")
    if isinstance(system, list):
        out["system"] = [{k: v for k, v in block.items() if k != "cache_control"}
                         for block in system]
    return out


# Sonnet 5 list prices, $ per million tokens, recorded 2026-09-06. Cache reads
# are a tenth of the input rate and cache writes a quarter above it. These are
# here to make the console number predictable, not to replace it — the console
# is what actually bills, and if these two disagree, the console is right.
_USD_PER_MTOK = {"in": 2.00, "cache_read": 0.20, "cache_write": 2.50, "out": 10.00}


def _log_usage(message: Any) -> None:
    """Print what the last request of this run cost, and whether caching bit.

    **This is one request, not one question.** The tool loop makes up to
    """ + str(MAX_TOOL_ITERATIONS) + """ of them and a question costs roughly their sum, so this line is
    a floor on the question and an exact read on one thing that matters: if
    `cache_read` is 0 on every question after the first, the cached prefix is
    being invalidated somewhere and the loop is costing several times what it
    should.
    """
    u = getattr(message, "usage", None)
    if u is None:
        return
    fresh = getattr(u, "input_tokens", 0) or 0
    read = getattr(u, "cache_read_input_tokens", 0) or 0
    write = getattr(u, "cache_creation_input_tokens", 0) or 0
    out = getattr(u, "output_tokens", 0) or 0
    usd = (fresh * _USD_PER_MTOK["in"] + read * _USD_PER_MTOK["cache_read"]
           + write * _USD_PER_MTOK["cache_write"] + out * _USD_PER_MTOK["out"]) / 1_000_000
    log.info("Suishōdama: last request — in=%s cache_read=%s cache_write=%s out=%s ~$%.4f",
             fresh, read, write, out, usd)

    # Also to disk, because the console line scrolls away and lives in whatever
    # window uvicorn was started in. On a fixed budget the question "what have I
    # spent so far" has to be answerable after the fact. `output/` is gitignored.
    # Wrapped whole: a bookkeeping failure must never cost an officer an answer.
    try:
        import json
        from datetime import datetime
        rec = {"at": datetime.now().astimezone().isoformat(timespec="seconds"),
               "model": ANTHROPIC_MODEL, "in": fresh, "cache_read": read,
               "cache_write": write, "out": out, "usd": round(usd, 6)}
        path = Path(__file__).resolve().parents[2] / "output" / "cost.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + chr(10))
    except Exception:  # noqa: BLE001 - bookkeeping is never worth an exception
        pass


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
    def chain_of_custody(limit: int = 12) -> str:
        """Whether this case's evidence record is intact, and what it last recorded.

        Use this whenever the officer asks about tampering, integrity, the chain
        of custody, or whether the record can be trusted. It reports the
        verification and the most recent entries, not the whole ledger.

        Args:
            limit: How many recent entries to return.
        """
        return _json(T.chain_of_custody(ctx, limit))

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
            communities, anomalies, read_source_doc, chain_of_custody, recall,
            record_conclusion, open_question, request_evidence]


def _ids(raw: str) -> list[str]:
    return [x.strip() for x in (raw or "").split(",") if x.strip()]


# What one tool call may put in front of the model. Measured 2026-09-06 on a
# 3,265-node case built from a 2,000-row CDR — *small*, next to a real one:
# `timeline` returned 419,224 characters (~105k tokens) in a single call,
# `communities` 81,035 and `neighbours` on a busy number 42,430. Nothing capped
# any of it.
#
# **This is the failure the whole product is an argument against** (§2.5). If a
# case's size decides how much text reaches the model, then the case *is* the
# context window after all, and the thing degrades into exactly the chatbot we
# say it is not — slower and more expensive with every document, until it stops
# answering at all.
#
# So the ceiling is on this side of the boundary, and it is fixed: the model
# sees a constant amount of the case however large the case gets. What it does
# not see, it can still reach — by narrowing the question and calling again,
# which is what the note in a truncated result tells it to do.
MAX_TOOL_ITEMS = 40
MAX_TOOL_CHARS = 12000
# Provenance is bounded in the store (`graph.store._merge_sources`); one ref is
# all a citation needs, and `read_source_doc` opens it.
KEEP_SOURCES = 1


def _slim(value: Any) -> Any:
    """Strip a graph row to what an answer can actually use.

    A node arrives with every offset it was ever seen at and every attribute
    ingest attached. The model needs the id (to cite), the label (to say), the
    type, and one place to look — everything else is weight it pays for on
    every turn.
    """
    if isinstance(value, list):
        return [_slim(v) for v in value]
    if not isinstance(value, dict):
        return value

    if "sources" in value and isinstance(value.get("sources"), list):
        out = {k: _slim(v) for k, v in value.items() if k != "sources"}
        refs = value["sources"]
        out["sources"] = refs[:KEEP_SOURCES]
        if len(refs) > KEEP_SOURCES:
            out["source_count"] = len(refs)
        return out
    return {k: _slim(v) for k, v in value.items()}


def _json(value: Any) -> str:
    """Serialise a tool result for the model — bounded, and honest when it cut.

    The old version ended in `[:60000]`, which sliced the JSON **mid-object**:
    on any case big enough to reach it the model received text that was not
    valid JSON at all, with nothing saying so. Truncation here is structural —
    fewer items, never half an item — and it is always announced.
    """
    import json

    def dump(v: Any) -> str:
        return json.dumps(v, ensure_ascii=False, default=str)

    value = _slim(value)

    if isinstance(value, list) and len(value) > MAX_TOOL_ITEMS:
        value = {"items": value[:MAX_TOOL_ITEMS], "shown": MAX_TOOL_ITEMS,
                 "total": len(value),
                 "note": f"{len(value) - MAX_TOOL_ITEMS} more not shown. Narrow the "
                         f"question — by name, by type or by time — and call again."}

    text = dump(value)
    if len(text) <= MAX_TOOL_CHARS:
        return text

    # Still too big. Halve **every** list in the structure, repeatedly, until it
    # fits — and keep the shape, because a caller reading `nodes` and `edges`
    # must still find `nodes` and `edges`.
    #
    # It halves all of them rather than the longest one, and that is not a
    # detail: `communities` is thirty lists of four thousand, so cutting the
    # single longest each round converges in hundreds of rounds and the first
    # version of this gave up and returned an error instead — taking a working
    # tool away from the agent exactly when the case got big enough to need it.
    # Halving everything converges in log2 of the longest list, whatever the
    # breadth.
    def halved(node: Any) -> Any:
        if isinstance(node, list):
            return [halved(v) for v in node[: max(1, len(node) // 2)]]
        if isinstance(node, dict):
            return {k: halved(v) for k, v in node.items()}
        return node

    def widest(node: Any) -> int:
        if isinstance(node, list):
            return max([len(node)] + [widest(v) for v in node])
        if isinstance(node, dict):
            return max([0] + [widest(v) for v in node.values()])
        return 0

    if isinstance(value, list):
        value = {"items": value, "total": len(value)}
    note = ("Cut to fit — this is part of the result. Narrow the question by name, "
            "type or time and call again.")

    while widest(value) > 1:
        value = halved(value) | {"note": note}
        text = dump(value)
        if len(text) <= MAX_TOOL_CHARS:
            return text

    return dump({"error": "This result is too large to return. Ask something narrower.",
                 "kind": type(value).__name__})


# ------------------------------------------------------------------- the agent

class CaseAgent:
    """One agent per case. Holds no state of its own — the case does."""

    def __init__(self, ctx: CaseContext):
        self.ctx = ctx

    # ------------------------------------------------------------------- ask

    def ask(self, question: str, *, actor: str = "officer") -> dict:
        """One turn of a conversation, not one query against a search box.

        The thread lives on the case (`store.conversation`), so the model is
        handed the real exchange and the officer can say "and him?" — and so his
        colleague opening the same case tomorrow sees what was already asked and
        answered, instead of starting the relationship again.
        """
        self.ctx.chain.append(action="query", actor=actor, ref=f"question:{question[:120]}",
                              payload={"question": question})
        self.ctx.store.say(role="officer", text=question, actor=actor)

        # No fallback. If the assistant cannot run, the officer is told that —
        # he is not handed a graph lookup dressed up as an answer. `ask` is the
        # bot doing its job or the bot being honestly unavailable, nothing in
        # between; the API turns this into a 503 the UI shows with a retry.
        answer = verify(
            self._run(self._messages(question), system=self._system()), self.ctx.store)

        self.ctx.store.say(role="suishodama", text=answer.get("answer", ""),
                           answer=answer, node_ids=answer.get("cited_nodes") or [])
        self.ctx.chain.append(
            action="infer", actor="agent", ref=f"answer:{question[:80]}",
            payload={"answer": answer.get("answer"),
                     "cited_nodes": answer.get("cited_nodes"),
                     "cited_edges": answer.get("cited_edges")},
        )
        return answer

    # ------------------------------------------------- what the model receives

    def _system(self) -> list[dict]:
        """The standing brief: who it is, and which case it is on.

        The case's identity belongs here rather than in the first user turn,
        because it is true of every turn. Put it in a message and it either gets
        repeated on each one or slides out of the window as the thread grows —
        and an assistant that forgets which case it is on halfway through a
        conversation is not a teammate.

        **Two blocks, and the split is the cost control.** The first is
        identical on every request this product ever makes; the second changes
        the moment a document lands or the agent records a conclusion. Caching
        is a prefix match, so a single string would put the volatile half inside
        the cached prefix and throw the entry away on every ingest. The
        breakpoint sits between them: `tools` render ahead of `system`, so what
        is cached here is the tool schemas plus the standing instructions —
        about 2,100 tokens, comfortably over Sonnet 5's 1,024-token minimum —
        and it is re-read at a tenth of the price on every question after the
        first. What follows the breakpoint is small and genuinely per-request.
        """
        overview = T.case_overview(self.ctx)
        counts = overview["counts"]
        # Headline, detail and severity only. A finding also carries every node
        # and edge it rests on — dozens of ids each, and around 19,000 characters
        # for eight of them. That is uncached weight on every single request, for
        # ids the model can ask for the moment it wants one.
        # Same treatment for what it has already worked out. A memory entry
        # carries every node and edge it touched plus timestamps and meta; eight
        # conclusions came to 10,600 characters of which the model needs the
        # sentence. And these *grow as the case is worked*, so leaving them fat
        # puts the size of the case back into the size of the prompt — the exact
        # thing §3.10 removed everywhere else.
        def _slim(rows, keys, n=8):
            return [{k: r.get(k) for k in keys if r.get(k) not in (None, "", [])}
                    for r in (rows or [])[:n]]

        findings = _slim(overview.get("findings"),
                         ("id", "kind", "headline", "detail"))
        conclusions = _slim(overview.get("conclusions"), ("id", "text", "confidence"))
        open_questions = _slim(overview.get("open_questions"), ("id", "text"))
        return [
            {"type": "text", "text": SYSTEM,
             "cache_control": {"type": "ephemeral"}},
            # Second breakpoint: everything that changes only when a document is
            # ingested. The findings belong here rather than after it — they are
            # the most valuable thing in the brief and would otherwise be paid
            # for at full rate on every question. Here they are re-read at a
            # tenth, and an upload simply re-writes the entry once.
            {"type": "text", "text": f"""THIS CASE

{self._header()}

It holds {counts['nodes']} entities and {counts['edges']} links drawn from {counts['documents']} documents. That is the whole of what you know about it; anything outside it you find with a tool or you do not say.

Computed from the whole graph, deterministic, and not yours to re-derive. The
officer has not seen any of it.

**He already knows everyone in his own reports** — he wrote them. That the man
named in seven documents is the most connected person is his own file read back
to him, not information. Asked who matters, who is running this, who he has
missed, or what to look at: **if a finding names someone the paperwork does not,
that person opens your answer, by name, with the fact that no report mentions
them.** Those already in the reports follow, as the layer beneath — context, not
the answer. Centrality ranks position, never novelty, and its top name is one he
could have given you himself.
{_json(findings)}""",
             "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": f"""What you have already concluded here:
{_json(conclusions)}

What you are still holding open:
{_json(open_questions)}"""},
        ]

    def _messages(self, question: str) -> list[dict]:
        """The conversation so far, then what he just said.

        Referring expressions are resolved **structurally**, not hopefully: the
        entities the last answer actually rested on are attached to this turn as
        ids, so "him" and "that account" have something real to bind to. Asking
        a model to remember harder is not a mechanism; handing it the ids is.
        """
        turns = self.ctx.store.conversation(limit=CONVERSATION_TURNS)
        messages: list[dict] = []
        for turn in turns[:-1]:            # the last turn is this question
            role = "user" if turn["role"] == "officer" else "assistant"
            text = (turn["text"] or "").strip()
            if not text:
                continue
            if messages and messages[-1]["role"] == role:
                messages[-1]["content"] += PARA + text
            else:
                messages.append({"role": role, "content": text})

        content = question
        focus = self._focus(turns)
        if focus:
            content += PARA + (
                "[The entities your last answer rested on, in case I am referring "
                "back to one of them: " + ", ".join(focus) + "]"
            )
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] += PARA + content
        else:
            messages.append({"role": "user", "content": content})

        # A conversation must open with the officer, whatever the store holds.
        while messages and messages[0]["role"] != "user":
            messages.pop(0)
        return messages

    def _focus(self, turns: list[dict]) -> list[str]:
        """Ids from the most recent answer, labelled — the referent set."""
        for turn in reversed(turns):
            if turn["role"] != "suishodama":
                continue
            out = []
            for node_id in (turn.get("node_ids") or [])[:8]:
                node = self.ctx.store.get_node(node_id)
                if node:
                    out.append(f"{node.label} ({node.id})")
            return out
        return []

    def _header(self) -> str:
        """The case's own identity and the officer's brief, in front of the
        agent on every turn. This is what lets one engine work a fraud case and
        a homicide without either being special-cased — the graph supplies the
        facts, this supplies what kind of case they belong to."""
        return agent_context_header(self.ctx.case_id) or f"Case {self.ctx.case_id}."

    # ----------------------------------------------------------------- brief

    def brief(self, *, since_rev: int | None = None, actor: str = "system") -> dict:
        """What the assistant says on its own initiative.

        The findings themselves are computed by `analytics/` — deterministic and
        cited. The model turns them into something an officer can act on, files
        what it concludes, and says it **into the case thread**, because a
        briefing is the assistant talking and that is where it talks.

        **It does not greet him twice for the same thing.** The front end calls
        this every time the case is opened, so briefing unconditionally would
        re-post the same paragraph on every visit and bill a model call for it.
        If nothing has been found since the last briefing, the one it already
        gave is returned as it stands. A teammate who repeats his opening line
        every time you walk in is not one.
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

        if not fresh:
            spoken = self._last_briefing()
            if spoken is not None:
                deterministic["narrative"] = spoken
                deterministic["repeat"] = True
                return deterministic

        # Exactly what the model is shown is exactly what gets marked delivered.
        # It used to be shown eight and mark six, so two findings were quietly
        # re-briefed for ever and "nothing new to say" could never come true on a
        # case with more than a handful of them.
        shown = (fresh or findings)[:BRIEF_FINDINGS]
        narrative = verify(
            self._run(self._brief_prompt(shown, counts),
                      system=self._system()), self.ctx.store)
        deterministic["narrative"] = narrative
        # It said this on this case, so it belongs in the thread the officer
        # reads — not only in the response to whoever happened to call /brief.
        self.ctx.store.say(role="suishodama", text=narrative.get("answer", ""),
                           answer=narrative,
                           node_ids=narrative.get("cited_nodes") or [], actor=actor)
        for f in shown:
            self.ctx.store.remember(kind="briefing", text=f.get("headline", ""),
                                    node_ids=f.get("node_ids", []),
                                    edge_ids=f.get("edge_ids", []), status="delivered")
        return deterministic

    def _last_briefing(self) -> dict | None:
        """The briefing already in the thread, if there is one.

        Read back out of the case rather than regenerated, so re-opening a case
        is instant and free and shows the officer the same words he saw before.
        """
        for turn in reversed(self.ctx.store.conversation(limit=CONVERSATION_TURNS)):
            if turn["role"] == "suishodama" and turn.get("answer"):
                return turn["answer"]
        return None

    def _brief_prompt(self, findings: list[dict], counts: dict) -> str:
        return (
            "The analysis layer surfaced these, computed from the graph — they are facts, "
            "not suggestions, and you should verify the ones you lead with:\n"
            f"{_json(findings)}\n\n"
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
        answer = verify(self._run(prompt, system=self._system()), self.ctx.store)
        self.ctx.store.say(role="suishodama", text=answer.get("answer", ""),
                           answer=answer, node_ids=answer.get("cited_nodes") or [],
                           actor="agent")
        return answer

    # -------------------------------------------------------------- the loop

    def _run(self, prompt: str | list[dict], *,
             system: str | list[dict] | None = None) -> dict:
        """One tool-driven run. The SDK's tool runner owns the loop; we own the
        bound tools, the contract and the iteration cap.

        `prompt` may be a single string or a **real conversation** — the list of
        prior turns plus this one. It used to be a string only, which meant every
        message the officer sent arrived cold: he was looking at a thread and
        talking to something with no memory of the line above. "And what about
        him?" could not work, because there was no him.
        """
        import anthropic

        messages = ([{"role": "user", "content": prompt}]
                    if isinstance(prompt, str) else list(prompt))
        client = _client()
        params: dict[str, Any] = dict(
            model=ANTHROPIC_MODEL,
            max_tokens=MAX_TOKENS,
            tools=_bind(self.ctx),
            max_iterations=MAX_TOOL_ITERATIONS,
            thinking={"type": "adaptive"},
            output_config={
                "effort": EFFORT,
                "format": {"type": "json_schema", "schema": ANSWER_SCHEMA},
            },
            system=system if system is not None else SYSTEM,
            messages=messages,
        )
        try:
            try:
                # Top-level automatic caching, on top of the explicit breakpoint
                # in `_system`. The runner rebuilds the request on every
                # iteration with the tool results appended, and this breakpoint
                # moves forward with it — so iteration nine re-reads iterations
                # one to eight at a tenth of the price instead of paying full
                # rate for them again. The loop is where the money goes: a
                # question costs roughly the *sum* over its iterations.
                message = client.beta.messages.tool_runner(
                    cache_control={"type": "ephemeral"}, **params).until_done()
            except anthropic.BadRequestError as exc:
                # Caching is an optimisation and must never be the reason an
                # officer gets no answer. If the breakpoints are ever rejected —
                # a model without caching, a changed limit — run it again
                # without them. A rejected request costs nothing, so this retry
                # is free, and a real 400 fails the same way twice and lands in
                # the handler below.
                log.warning("Suishōdama: caching rejected, retrying uncached (%s)", exc)
                message = client.beta.messages.tool_runner(**_uncached(params)).until_done()
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

        _log_usage(message)
        text = next((b.text for b in message.content if getattr(b, "type", "") == "text"), "")
        if not (text or "").strip():
            # The contract's fallback turns this into "did not return a usable
            # answer", which is correct behaviour and useless to debug from. The
            # two ways to get here are the iteration cap (the loop ran out before
            # it wrote an answer) and `max_tokens` (thinking ate the budget and
            # the JSON was truncated) — and both are the most expensive call the
            # system can make, returning nothing. Say which one it was.
            log.warning("Suishōdama: no answer text — stop_reason=%s blocks=%s iterations_cap=%s",
                        getattr(message, "stop_reason", None),
                        [getattr(b, "type", "?") for b in message.content],
                        MAX_TOOL_ITERATIONS)
        return parse(text)

