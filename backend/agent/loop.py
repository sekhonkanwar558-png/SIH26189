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

import os
from typing import Any, Callable

from backend.agent import tools as T
from backend.agent.contract import (ANSWER_SCHEMA, empty_answer, parse, verify,
                                    verified_vacuously)
from backend.agent.tools import CaseContext
from backend.case import agent_context_header
from backend.config import ANTHROPIC_MODEL

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

        self.ctx.store.say(role="shikonye", text=answer.get("answer", ""),
                           answer=answer, node_ids=answer.get("cited_nodes") or [])
        self.ctx.chain.append(
            action="infer", actor="agent", ref=f"answer:{question[:80]}",
            payload={"answer": answer.get("answer"),
                     "cited_nodes": answer.get("cited_nodes"),
                     "cited_edges": answer.get("cited_edges")},
        )
        return answer

    # ------------------------------------------------- what the model receives

    def _system(self) -> str:
        """The standing brief: who it is, and which case it is on.

        The case's identity belongs here rather than in the first user turn,
        because it is true of every turn. Put it in a message and it either gets
        repeated on each one or slides out of the window as the thread grows —
        and an assistant that forgets which case it is on halfway through a
        conversation is not a teammate.
        """
        overview = T.case_overview(self.ctx)
        counts = overview["counts"]
        return f"""{SYSTEM}

THIS CASE

{self._header()}

It holds {counts['nodes']} entities and {counts['edges']} links drawn from {counts['documents']} documents. That is the whole of what you know about it; anything outside it you find with a tool or you do not say.

What you have already concluded here:
{_json(overview['conclusions'][:8])}

What you are still holding open:
{_json(overview['open_questions'][:8])}"""

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
            if turn["role"] != "shikonye":
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
        self.ctx.store.say(role="shikonye", text=narrative.get("answer", ""),
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
            if turn["role"] == "shikonye" and turn.get("answer"):
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
        self.ctx.store.say(role="shikonye", text=answer.get("answer", ""),
                           answer=answer, node_ids=answer.get("cited_nodes") or [],
                           actor="agent")
        return answer

    # -------------------------------------------------------------- the loop

    def _run(self, prompt: str | list[dict], *, system: str | None = None) -> dict:
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
        try:
            runner = client.beta.messages.tool_runner(
                model=ANTHROPIC_MODEL,
                max_tokens=MAX_TOKENS,
                tools=_bind(self.ctx),
                max_iterations=MAX_TOOL_ITERATIONS,
                thinking={"type": "adaptive"},
                output_config={
                    "effort": EFFORT,
                    "format": {"type": "json_schema", "schema": ANSWER_SCHEMA},
                },
                system=system or SYSTEM,
                messages=messages,
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

