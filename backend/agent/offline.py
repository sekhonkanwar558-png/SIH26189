"""The answer when there is no model — README D11, and what decides whether the
demo survives a dead network.

`CaseAgent.ask` falls back here when the API has no key, is unreachable, or is
rate-limited. The fallback it replaces handed the officer's whole sentence to
`find_entity`, which is a substring match on node labels, so:

    "How is Ravi connected to the Ludhiana account?"
        -> LIKE '%how is ravi connected to the ludhiana account?%'
        -> "Nothing in this case matches that name or identifier."

It answered *names*, not questions — and §9.2 demo query 1 is a question. So
with no key the centrepiece of the pitch returned nothing at all.

This routes the question instead, deterministically, with no model in the path:

    two entities named     -> the path between them, lit on the graph (D3)
    an influence question  -> the ranked people, which is demo query 2 entire
    one entity named       -> that entity, its type, and its strongest links
    a phrase it cannot pin -> the candidates, said out loud
    nothing recognised     -> the case's leading finding, labelled as not an
                              answer to the question that was asked

**It does not guess.** A router that silently picks one of three candidates and
presents the result as the answer is the exact failure this system exists to
prevent: well-formed, confident, unfounded. Where it cannot resolve a phrase it
says which candidates it holds and asks.

**It also cannot invent a node that is not there.** "The Ludhiana account" is how
a person says it; the graph holds `account:50100244178`. No amount of routing
fixes that, and pretending otherwise would be the same failure. What this does is
resolve everything it *can* and name precisely what it could not, so the
officer's next sentence lands. `docs/demo-script.md` says the same thing: run
offline and query 1 is asked with the account named, or traced on the graph.

Every answer built here cites real ids read out of the graph, so
`contract.verify()` passes on its merits rather than by exemption.
"""

from __future__ import annotations

import re

from backend.agent import tools as T
from backend.agent.tools import CaseContext
from backend.analytics.anomalies import REPORT_KINDS

# Words that are never the name of an entity: question words, articles,
# prepositions, and the vocabulary of talking about a case at all.
STOPWORDS = frozenset("""
a an and any are as at be been both but by can could did do does for from
had has have how i if in into is it its me much my no nor not of on one or
our out over should show so some than that the their them then there these
they this those to told under until up us was we were what when where which
who whom whose why will with would you your
about anything anyone something someone please tell know
case cases network networks graph system evidence document documents file
files report reports data record records link links linked connection
connections connected connect relationship relationships
""".split())

# A word that names a *kind* of thing rather than a thing. "the Ludhiana
# account" is a qualifier plus a constraint, and the constraint is worth using:
# it turns fifteen matches on "account" into a search inside one type.
TYPE_WORDS = {
    "person": "person", "people": "person", "man": "person", "men": "person",
    "woman": "person", "women": "person", "suspect": "person",
    "suspects": "person", "accused": "person", "victim": "person",
    "phone": "phone", "phones": "phone", "mobile": "phone", "number": "phone",
    "numbers": "phone", "sim": "phone",
    "account": "account", "accounts": "account", "handle": "account",
    "profile": "account",
    "vehicle": "vehicle", "vehicles": "vehicle", "car": "vehicle",
    "location": "location", "locations": "location", "place": "location",
    "tower": "location", "address": "location",
    "organisation": "organization", "organization": "organization",
    "company": "organization", "agency": "organization", "firm": "organization",
    "device": "device", "handset": "device", "imei": "device",
}

# The officer is asking how two things join up.
CONNECTION_CUES = ("connect", "link", "relat", "between", "route", "path",
                   "reach", "tie", "associat")

# The officer is asking who matters — §9.2 demo query 2, answered in full
# offline, because influence is computed from the graph and never modelled.
INFLUENCE_CUES = ("who matters", "most important", "key player", "key figure",
                  "kingpin", "mastermind", "ringleader", "running", "runs this",
                  "in charge", "most central", "most influential", "biggest",
                  "leader", "boss", "top of", "who should i", "who is behind")

# A phrase matching more nodes than this, with none of them an exact label, is
# vocabulary rather than a name. "account" matches fifteen and means none.
GENERIC_ABOVE = 6

MAX_PHRASE_TOKENS = 3

_TOKEN = re.compile(r"[@+]?[0-9a-z][0-9a-z.'-]*", re.IGNORECASE)


def _tokens(question: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(question or "")]


def _is_identifier(token: str) -> bool:
    """A phone number, an account number, an IMEI, a handle. These are looked up
    however common they look — an officer who types a number means it."""
    return token.startswith("@") or len(re.sub(r"\D", "", token)) >= 6


def _adjacent_type(toks: list[str], i: int, size: int) -> str | None:
    """The node type a type word beside this span implies, if any.

    English puts the type word next to what it qualifies: "the Ludhiana
    account", "which vehicle", "Ravi's phone". Anything further away in the
    sentence is qualifying something else.
    """
    for j in (i + size, i - 1, i + size + 1):
        if 0 <= j < len(toks) and toks[j] in TYPE_WORDS:
            return TYPE_WORDS[toks[j]]
    return None


def mentions(ctx: CaseContext, question: str, *, limit: int = 4) -> list[dict]:
    """The entities a question actually names, best phrase first.

    Walks the question's own n-grams, longest first, against the node index. A
    span that has matched is not matched again in pieces, so "Ravi Kumar" is one
    person rather than two failed lookups.

    Each result carries `candidates`: the nodes that phrase matched. More than
    one means the caller must not treat the pick as settled.
    """
    toks = _tokens(question)
    taken = [False] * len(toks)
    found: dict[str, dict] = {}

    for size in range(MAX_PHRASE_TOKENS, 0, -1):
        for i in range(len(toks) - size + 1):
            if any(taken[i:i + size]):
                continue
            span = toks[i:i + size]
            if all(t in STOPWORDS or t in TYPE_WORDS for t in span):
                continue
            if size == 1 and not _is_identifier(span[0]):
                if span[0] in STOPWORDS or span[0] in TYPE_WORDS or len(span[0]) < 3:
                    continue
            phrase = " ".join(span)

            # A type word constrains the phrase *beside* it and nothing else.
            # "How is Ravi connected to the Ludhiana account?" has one type word
            # and it qualifies "Ludhiana", not "Ravi" — applying it across the
            # whole sentence resolved Ravi to the Instagram handle @ravi_ldh
            # and answered a question about a different Ravi entirely.
            constraint = _adjacent_type(toks, i, size)
            hits = ctx.store.search_nodes(phrase, type=constraint)
            if not hits and constraint:
                # The type word may belong to a neighbouring phrase after all.
                hits = ctx.store.search_nodes(phrase)
            if not hits:
                continue

            exact = [h for h in hits if h.label.lower() == phrase]
            if not exact and len(hits) > GENERIC_ABOVE and not _is_identifier(phrase):
                continue

            best = (exact or hits)[0]
            for j in range(i, i + size):
                taken[j] = True
            if best.id in found:
                continue
            found[best.id] = {
                "id": best.id,
                "label": best.label,
                "type": best.type,
                "phrase": phrase,
                "candidates": [{"id": h.id, "label": h.label, "type": h.type}
                               for h in ([best] if exact else hits)[:5]],
            }
            if len(found) >= limit:
                return list(found.values())

    return list(found.values())


def _wants(question: str, cues: tuple[str, ...]) -> bool:
    q = (question or "").lower()
    return any(c in q for c in cues)


def _caveat(reason: str, route: str) -> str:
    return (
        f"The reasoning model is unavailable ({reason}), so this answer is {route}, "
        "read straight off the case graph rather than investigated. The graph, the "
        "findings and the custody chain are unaffected."
    )


def _answer(text: str, *, nodes: list[str], edges: list[str],
            path: list[str] | None = None, confidence: str = "low",
            caveats: list[str] | None = None) -> dict:
    return {
        "answer": text,
        "cited_nodes": sorted(set(nodes)),
        "cited_edges": sorted(set(edges))[:12],
        "highlight_path": path or [],
        "confidence": confidence,
        "caveats": caveats or [],
    }


def _ambiguous(hit: dict) -> str:
    names = ", ".join(f"{c['label']} ({c['type']})" for c in hit["candidates"])
    return f'"{hit["phrase"]}" could be {names}. Name the one you mean.'


# --------------------------------------------------------------------- routes

def _route_path(ctx: CaseContext, hits: list[dict], reason: str) -> dict:
    """Two entities named, so answer the question that was asked: how do they
    join up. This is §9.2 query 1, and the route that lights the graph."""
    a, b = hits[0], hits[1]
    ambiguity = [_ambiguous(h) for h in (a, b) if len(h["candidates"]) > 1]
    paths = T.path_between(ctx, a["id"], b["id"], max_hops=6)

    if not paths:
        return _answer(
            f"{a['label']} and {b['label']} are both in this case and there is no path "
            f"between them within six hops. That is itself a finding: on the evidence "
            f"uploaded so far, nothing joins them.",
            nodes=[a["id"], b["id"]], edges=[],
            caveats=[_caveat(reason, "a shortest-path search")] + ambiguity,
        )

    best = paths[0]
    labels = best.get("labels") or best["path"]
    text = (
        f"{a['label']} reaches {b['label']} in {best['length']} "
        f"{'hop' if best['length'] == 1 else 'hops'}: " + " -> ".join(labels) + "."
    )
    if len(paths) > 1:
        text += f" {len(paths) - 1} further route(s) exist at this length or longer."
    text += (
        " The path is lit on the graph. Check what each link rests on before relying "
        "on it — a co-occurrence is proximity, not contact."
    )
    return _answer(text, nodes=list(best["path"]), edges=list(best.get("edges") or []),
                   path=list(best["path"]), confidence="medium",
                   caveats=[_caveat(reason, "a shortest-path search")] + ambiguity)


# `highlight_path` on an /ask answer is an ORDERED route: the front end lights
# it hop by hop with the edge between each pair. A finding's `node_ids` is an
# unordered set — `[harbhajan, cdr_doc, ldh_031, jaswant, balraj, device]` is
# not a route anyone can walk — so handing that set over as a path would claim a
# journey that does not exist. Findings light their subject only; everything
# else in the finding is still cited, and Evidence shows it.
# The findings that answer "who matters" better than a raw score does. A
# `hidden_broker` is someone with high betweenness who appears in no report, and
# an `undocumented_person` is someone in the data but in no account of it —
# both are *why* the officer is asking, and neither is the top of the ranking.
INFLUENCE_FINDINGS = ("hidden_broker", "undocumented_person")


def _in_a_report(ctx: CaseContext, node_id: str) -> bool:
    """Is this entity named in a document somebody *wrote about* the case — an
    FIR, a surveillance log, an intelligence report, a note — as opposed to a
    record of what somebody did, like a call log or a bank statement?

    Computed, never assumed. The sentence this feeds used to claim the busiest
    people were "already named in the reports", and Gurpreet Singh, third on
    that list, is in a CDR, a criminal register and a social export and in no
    report at all. A claim about the evidence has to be read off the evidence.
    """
    node = ctx.store.get_node(node_id)
    if node is None:
        return False
    kinds = {(ctx.store.document(src["doc_id"]) or {}).get("kind")
             for src in (node.sources or [])}
    return bool(kinds & set(REPORT_KINDS))


def _route_influence(ctx: CaseContext, reason: str) -> dict | None:
    """Who matters. Computed by `analytics/` and never by a model (D11), so this
    route is identical online and offline — §9.2 query 2, whole.

    **It leads with the finding, not with the top of the ranking, and the demo
    turns on the difference.** Raw betweenness on the demo case ranks Sukhwinder
    Kaur first (0.380); she is named in four documents and no officer needs
    telling about her. The man the room is meant to see is Harbhajan Dhillon,
    third on that ranking (0.222) and named in exactly one document — a call
    log — which is what `hidden_broker` encodes and a bare ranking throws away.
    Answering from the ranking alone would name the wrong person on stage.
    """
    findings = (ctx.store.get_analytics("findings") or {}).get("value", []) or []
    lead = next((f for f in findings if f.get("kind") in INFLUENCE_FINDINGS), None)
    ranked = T.top_influencers(ctx, metric="betweenness", limit=5)
    if not lead and not ranked:
        return None

    if lead:
        # The subject must not appear in the "already in the reports" list. He is
        # third on the raw ranking, so naming the top three put him in a sentence
        # that contradicted the one before it — the answer said he is in no
        # report and then listed him among the people who are.
        subject_ids = set(lead.get("node_ids") or [])
        documented = [r["label"] for r in ranked
                      if r["node_id"] not in subject_ids
                      and _in_a_report(ctx, r["node_id"])]
        text = f"{lead.get('headline', '')}. {lead.get('detail', '')}".strip()
        if documented:
            names = ", ".join(documented)
            text += (f" The names a centrality ranking hands you instead — {names} — "
                     "are all already in the reports, which is why the ranking alone "
                     "would not have surfaced this.")
        subject = list(lead.get("node_ids") or [])[:1]
        nodes = list(lead.get("node_ids") or []) + [r["node_id"] for r in ranked]
        return _answer(text, nodes=nodes, edges=list(lead.get("edge_ids") or []),
                       path=subject, confidence="medium",
                       caveats=[_caveat(reason, "the case's own computed findings")])

    top = ranked[0]
    rest = ", ".join(r["label"] for r in ranked[1:4])
    text = f"{top['label']} ranks highest on betweenness in this case. {top['why']}"
    if rest:
        text += f" Then: {rest}."
    return _answer(text, nodes=[r["node_id"] for r in ranked], edges=[],
                   path=[top["node_id"]], confidence="medium",
                   caveats=[_caveat(reason, "the network's own centrality ranking")])


def _route_entity(ctx: CaseContext, hit: dict, reason: str) -> dict:
    """One entity named. Say what it is and what it touches."""
    nb = T.neighbours(ctx, hit["id"], depth=1)
    kinds: dict[str, int] = {}
    for e in nb["edges"]:
        kinds[e["type"]] = kinds.get(e["type"], 0) + 1
    breakdown = ", ".join(f"{n} {k}" for k, n in
                          sorted(kinds.items(), key=lambda kv: -kv[1])[:4])
    text = (f"{hit['label']} is a {hit['type']} in this case with "
            f"{len(nb['edges'])} direct links")
    text += f" ({breakdown})." if breakdown else "."

    caveats = [_caveat(reason, "a direct graph lookup")]
    if len(hit["candidates"]) > 1:
        caveats.append(_ambiguous(hit))
    return _answer(text, nodes=[hit["id"]] + [n["id"] for n in nb["nodes"]][:12],
                   edges=[e["id"] for e in nb["edges"] if e.get("id")],
                   path=[hit["id"]], caveats=caveats)


def _route_type(ctx: CaseContext, question: str, reason: str) -> dict | None:
    """"Which vehicles are in this case?" — a type word, no entity named. The
    officer is asking what the case holds of a kind, which is a question the
    graph answers exactly and a model is not needed for."""
    wanted = next((TYPE_WORDS[t] for t in _tokens(question) if t in TYPE_WORDS), None)
    if not wanted:
        return None
    rows = ctx.store.nodes(type=wanted)
    if not rows:
        return _answer(
            f"This case holds no {wanted} entities at all.",
            nodes=[], edges=[], caveats=[_caveat(reason, "a direct graph lookup")],
        )
    shown = rows[:12]
    listed = ", ".join(n.label for n in shown)
    noun = wanted if len(rows) == 1 else f"{wanted}s"
    text = f"This case holds {len(rows)} {noun}: {listed}"
    text += f", and {len(rows) - len(shown)} more." if len(rows) > len(shown) else "."
    # Same rule: a list of every vehicle in the case is not a route through it.
    return _answer(text, nodes=[n.id for n in shown], edges=[], path=[],
                   caveats=[_caveat(reason, "a direct graph lookup")])


def _route_findings(ctx: CaseContext, reason: str) -> dict:
    """Nothing in the question resolved. Do not answer a question nobody asked —
    say so first, then offer what the case is leading with, labelled as such."""
    findings = (ctx.store.get_analytics("findings") or {}).get("value", []) or []
    unresolved = (
        "Without the reasoning model I could not identify what you are asking about: "
        "nothing in that sentence matches an entity or identifier in this case."
    )
    if not findings:
        return _answer(
            unresolved + " Nothing has been flagged in this case yet either — add "
            "documents, or name an entity directly.",
            nodes=[], edges=[], caveats=[_caveat(reason, "a direct graph lookup")],
        )
    top = findings[0]
    detail = f"{top.get('headline', '')} {top.get('detail', '')}".strip()
    return _answer(
        unresolved + " This is not an answer to your question, but it is what the "
        f"case's own analysis is leading with: {detail}",
        nodes=list(top.get("node_ids") or []), edges=list(top.get("edge_ids") or []),
        path=list(top.get("node_ids") or [])[:1],
        caveats=[_caveat(reason, "the case's computed findings")],
    )


def answer(ctx: CaseContext, question: str, reason: str) -> dict:
    """Route one question over the graph with no model. Never raises: the whole
    point of this path is that something useful comes back."""
    hits = mentions(ctx, question)

    if len(hits) >= 2:
        return _route_path(ctx, hits, reason)

    if _wants(question, INFLUENCE_CUES):
        routed = _route_influence(ctx, reason)
        if routed:
            return routed

    if len(hits) == 1:
        answered = _route_entity(ctx, hits[0], reason)
        if _wants(question, CONNECTION_CUES):
            answered["caveats"].insert(0, (
                f"You asked how {hits[0]['label']} connects to something, and only "
                f"{hits[0]['label']} resolved to an entity here. Name the other side — "
                "an account number, a phone, or a person — and I will trace the route."
            ))
        return answered

    routed = _route_type(ctx, question, reason)
    if routed:
        return routed

    return _route_findings(ctx, reason)
