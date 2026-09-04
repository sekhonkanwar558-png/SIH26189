"""What the system noticed on its own — README §3.3, and the curiosity layer.

Two products here, and the difference matters:

* **Anomalies** are statistical: a call-volume spike, a handset carrying three
  SIMs, an account that only ever receives. Mechanical, cheap, per §5.2.
* **Findings** are what the case agent *volunteers to the officer without being
  asked*. Same evidence, ranked by how much it should change what he does next,
  each one carrying the node and edge ids it rests on.

Findings are computed here, deterministically, from the graph — **not by the
model**. The model narrates them; it does not invent them. That keeps D3 true
(the graph causes the answer) and means the assistant is still useful with no
API key, no network, and no budget — which on the demo machine at 11:00 on the
9th is not a hypothetical.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

import networkx as nx

from backend.graph.store import CaseStore

TEMPORAL_EDGE_TYPES = ("CALLED", "MESSAGED", "TRANSFERRED_TO", "LOCATED_AT")


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


# --------------------------------------------------------------- anomalies

def compute_anomalies(store: CaseStore, g: nx.MultiDiGraph, u: nx.Graph,
                      window_hours: int = 24) -> list[dict]:
    out: list[dict] = []
    out += _volume_spikes(store, window_hours)
    out += _handset_swaps(store, g)
    out += _one_way_accounts(store, g)
    out += _outlier_transfers(store)
    out += _went_silent(store)
    return sorted(out, key=lambda a: (-a.get("score", 0), a["kind"]))


def _volume_spikes(store: CaseStore, window_hours: int) -> list[dict]:
    """A node's own contact rate against its own baseline. Comparing a node to
    itself, not to the network, is what makes this survive a graph where one
    number is legitimately busy all day."""
    per_node: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    for edge in store.edges(types=TEMPORAL_EDGE_TYPES):
        ts = _dt(edge.ts)
        if ts is None:
            continue
        per_node[edge.src].append((ts, edge.id or ""))
        per_node[edge.dst].append((ts, edge.id or ""))

    out = []
    for node_id, events in per_node.items():
        if len(events) < 6:
            continue
        buckets: dict[datetime, list[str]] = defaultdict(list)
        for ts, edge_id in events:
            key = ts.replace(minute=0, second=0, microsecond=0)
            key -= timedelta(hours=key.hour % max(1, window_hours // 24 or 1))
            buckets[key].append(edge_id)

        counts = [len(v) for v in buckets.values()]
        if len(counts) < 3:
            continue
        mean = statistics.mean(counts)
        sd = statistics.pstdev(counts) or 1.0
        for bucket, edge_ids in sorted(buckets.items()):
            n = len(edge_ids)
            z = (n - mean) / sd
            if z >= 2.5 and n >= max(3, mean * 2):
                node = store.get_node(node_id)
                out.append({
                    "kind": "volume_spike",
                    "node_ids": [node_id],
                    "edge_ids": edge_ids,
                    "ts": bucket.isoformat(timespec="seconds"),
                    "score": round(float(z), 2),
                    "description": (
                        f"{node.label if node else node_id} had {n} contacts in the hour "
                        f"from {bucket:%d %b %H:%M} against a case average of {mean:.1f} "
                        f"({z:.1f} standard deviations above its own baseline)."
                    ),
                })
    return out


def _handset_swaps(store: CaseStore, g: nx.MultiDiGraph) -> list[dict]:
    """One IMEI, several numbers. The classic burner pattern, and invisible
    unless the handset is a node in its own right (see structured.py)."""
    out = []
    for device in store.nodes(type="device"):
        edges = [e for e in store.edges(node_id=device.id) if e.type == "REGISTERED_TO"]
        phones = sorted({e.dst for e in edges if e.dst.startswith("phone:")})
        if len(phones) < 2:
            continue
        labels = [(store.get_node(p).label if store.get_node(p) else p) for p in phones]
        out.append({
            "kind": "handset_swap",
            "node_ids": [device.id] + phones,
            "edge_ids": [e.id for e in edges if e.id],
            "ts": device.first_seen,
            "score": float(len(phones)),
            "description": (
                f"Handset {device.label} carried {len(phones)} different numbers "
                f"({', '.join(labels)}). One person changing SIMs looks like several "
                f"people until the IMEI is followed."
            ),
        })
    return out


def _one_way_accounts(store: CaseStore, g: nx.MultiDiGraph) -> list[dict]:
    """Accounts that only receive, or only send. A collection point and a
    payout point look identical in a ledger and opposite in a graph."""
    incoming: Counter = Counter()
    outgoing: Counter = Counter()
    edges_by_node: dict[str, list[str]] = defaultdict(list)
    for edge in store.edges(types=("TRANSFERRED_TO",)):
        incoming[edge.dst] += 1
        outgoing[edge.src] += 1
        edges_by_node[edge.dst].append(edge.id or "")
        edges_by_node[edge.src].append(edge.id or "")

    out = []
    for node_id in set(incoming) | set(outgoing):
        got, sent = incoming[node_id], outgoing[node_id]
        if got + sent < 3:
            continue
        if sent == 0 or got == 0:
            node = store.get_node(node_id)
            direction = "only received" if sent == 0 else "only sent"
            out.append({
                "kind": "one_way_account",
                "node_ids": [node_id],
                "edge_ids": edges_by_node[node_id],
                "ts": node.first_seen if node else None,
                "score": float(got + sent),
                "description": (
                    f"Account {node.label if node else node_id} {direction} money — "
                    f"{got + sent} transactions, all in one direction."
                ),
            })
    return out


def _outlier_transfers(store: CaseStore) -> list[dict]:
    amounts = []
    edges = [e for e in store.edges(types=("TRANSFERRED_TO",))
             if isinstance(e.attrs.get("amount"), (int, float))]
    if len(edges) < 5:
        return []
    amounts = [float(e.attrs["amount"]) for e in edges]
    median = statistics.median(amounts)
    threshold = max(median * 5, median + 2 * (statistics.pstdev(amounts) or 1))

    out = []
    for edge in edges:
        amount = float(edge.attrs["amount"])
        if amount < threshold:
            continue
        out.append({
            "kind": "large_transfer",
            "node_ids": [edge.src, edge.dst],
            "edge_ids": [edge.id or ""],
            "ts": edge.ts,
            "score": round(amount / max(median, 1), 2),
            "description": (
                f"Transfer of {amount:,.0f} is {amount / max(median, 1):.0f}x the case "
                f"median of {median:,.0f}."
            ),
        })
    return out


def _went_silent(store: CaseStore) -> list[dict]:
    """A number busy for weeks, then nothing. Often a discarded SIM, and the
    date it stops is usually the date something happened."""
    activity: dict[str, list[datetime]] = defaultdict(list)
    for edge in store.edges(types=("CALLED", "MESSAGED")):
        ts = _dt(edge.ts)
        if ts:
            activity[edge.src].append(ts)
            activity[edge.dst].append(ts)
    if not activity:
        return []
    latest = max(ts for stamps in activity.values() for ts in stamps)

    out = []
    for node_id, stamps in activity.items():
        if len(stamps) < 8:
            continue
        stamps.sort()
        span = (stamps[-1] - stamps[0]).total_seconds() / 86400
        quiet = (latest - stamps[-1]).total_seconds() / 86400
        if span >= 3 and quiet >= max(3.0, span * 0.4):
            node = store.get_node(node_id)
            out.append({
                "kind": "went_silent",
                "node_ids": [node_id],
                "edge_ids": [],
                "ts": stamps[-1].isoformat(timespec="seconds"),
                "score": round(quiet, 1),
                "description": (
                    f"{node.label if node else node_id} was active for {span:.0f} days and "
                    f"has been silent for the last {quiet:.0f}. Last contact "
                    f"{stamps[-1]:%d %b %H:%M}."
                ),
            })
    return out


# ----------------------------------------------------------------- findings

def compute_findings(
    store: CaseStore,
    g: nx.MultiDiGraph,
    u: nx.Graph,
    metrics: dict[str, dict[str, float]],
    communities: list[dict],
    anomalies: list[dict],
) -> list[dict]:
    """What the assistant leads with. Ordered by how much it should change the
    officer's next hour, not by how large the number is."""
    membership = {m: c["cluster_id"] for c in communities for m in c["members"]}
    findings: list[dict] = []

    findings += _hidden_brokers(store, u, metrics, membership)
    findings += _undocumented_people(store, u, metrics)
    findings += _cluster_joins(store, u, communities, membership)

    severity_of = {"volume_spike": "medium", "handset_swap": "high",
                   "one_way_account": "medium", "large_transfer": "medium",
                   "went_silent": "low"}
    for a in anomalies[:12]:
        findings.append({
            "kind": a["kind"],
            "severity": severity_of.get(a["kind"], "low"),
            "headline": a["description"].split(".")[0][:140],
            "detail": a["description"],
            "node_ids": a.get("node_ids", []),
            "edge_ids": [e for e in a.get("edge_ids", []) if e],
            "ts": a.get("ts"),
        })

    rank = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: (rank.get(f["severity"], 3), f["kind"]))
    for i, f in enumerate(findings, start=1):
        f["id"] = f"f{i}"
    return findings


def _hidden_brokers(store, u, metrics, membership) -> list[dict]:
    """High betweenness, few direct contacts, named in no document.

    This is the finding the whole system exists to produce: the person who
    connects the network without appearing in it. A dashboard cannot surface
    this, because nobody thinks to look for a name they have never read.
    """
    betweenness = metrics.get("betweenness", {})
    if not betweenness:
        return []
    scores = sorted(betweenness.values(), reverse=True)
    cut = scores[max(0, min(len(scores) - 1, 4))]

    out = []
    for node_id, score in sorted(betweenness.items(), key=lambda kv: -kv[1]):
        if not node_id.startswith("person:") or score <= 0 or score < cut:
            continue
        node = store.get_node(node_id)
        if node is None:
            continue
        degree = u.degree(node_id) if node_id in u else 0
        docs = {s["doc_id"] for s in node.sources}
        named_in_reports = any(
            (store.document(d) or {}).get("kind") in ("fir", "surveillance", "note")
            for d in docs
        )
        if degree > 6 or named_in_reports:
            continue

        neighbours = list(u.neighbors(node_id)) if node_id in u else []
        bridged = sorted({membership.get(n) for n in neighbours} - {None, membership.get(node_id)})
        out.append({
            "kind": "hidden_broker",
            "severity": "high",
            "headline": f"{node.label} connects this network but appears in no report",
            "detail": (
                f"{node.label} lies on {score:.0%} of the shortest paths in the case with "
                f"only {degree} direct contact{'s' if degree != 1 else ''}"
                + (f", joining {len(bridged)} groups that otherwise never touch" if len(bridged) >= 2 else "")
                + ". They are named in no FIR or surveillance report — the link exists only in "
                  "metadata, which is why manual review would not have surfaced them."
            ),
            "node_ids": [node_id] + neighbours[:8],
            "edge_ids": _edges_around(u, node_id),
            "ts": node.first_seen,
        })
        if len(out) >= 3:
            break
    return out


def _undocumented_people(store, u, metrics) -> list[dict]:
    """People who exist only in CDR or bank data. Weaker than a hidden broker
    but the same class of blind spot, and cheap to state."""
    out = []
    for node in store.nodes(type="person"):
        docs = {s["doc_id"] for s in node.sources}
        kinds = {(store.document(d) or {}).get("kind") for d in docs}
        if kinds & {"fir", "surveillance", "note"} or not kinds:
            continue
        degree = u.degree(node.id) if node.id in u else 0
        if degree < 2:
            continue
        out.append({
            "kind": "undocumented_person",
            "severity": "medium",
            "headline": f"{node.label} appears only in records, never in a report",
            "detail": (
                f"{node.label} has {degree} connections in this case but is named in no FIR or "
                f"statement — only in {', '.join(sorted(k for k in kinds if k))} data."
            ),
            "node_ids": [node.id],
            "edge_ids": _edges_around(u, node.id),
            "ts": node.first_seen,
        })
        if len(out) >= 5:
            break
    return out


def _cluster_joins(store, u, communities, membership) -> list[dict]:
    """The single edges holding two groups together. Cut one and the case
    splits in two — which tells the officer exactly where to push."""
    if len(communities) < 2:
        return []
    pair_edges: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for a, b, data in u.edges(data=True):
        ca, cb = membership.get(a), membership.get(b)
        if ca and cb and ca != cb:
            pair_edges[tuple(sorted((ca, cb)))].append((a, b))

    out = []
    for (ca, cb), pairs in sorted(pair_edges.items(), key=lambda kv: len(kv[1])):
        if len(pairs) > 2:
            continue
        joins = []
        edge_ids: list[str] = []
        for a, b in pairs:
            joins.append(f"{_label(store, a)} - {_label(store, b)}")
            edge_ids += u[a][b].get("edge_ids", [])
        out.append({
            "kind": "single_point_of_contact",
            "severity": "high",
            "headline": f"Groups {ca} and {cb} are joined by only {len(pairs)} link",
            "detail": (
                f"Everything connecting these two groups passes through {'; '.join(joins)}. "
                f"If that link is wrong, the case is two unrelated cases; if it is right, it is "
                f"the handover point."
            ),
            "node_ids": sorted({n for pair in pairs for n in pair}),
            "edge_ids": edge_ids,
            "ts": None,
        })
        if len(out) >= 2:
            break
    return out


def _label(store: CaseStore, node_id: str) -> str:
    node = store.get_node(node_id)
    return node.label if node else node_id


def _edges_around(u: nx.Graph, node_id: str) -> list[str]:
    if node_id not in u:
        return []
    ids: list[str] = []
    for neighbour in u.neighbors(node_id):
        ids += u[node_id][neighbour].get("edge_ids", [])
    return ids[:40]
