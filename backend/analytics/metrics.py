"""Who matters, and why — README §3.3.

Four algorithms, all cheap, all deterministic, all *explainable*. That last one
is the requirement that rules out an embedding: an officer acting on this has
to be able to be told why a name came up, and defend it later. So every score
here ships with a `why` string built from the graph itself — how many
communities the node bridges, how many of the shortest paths run through it,
how many documents name it (often zero, which is the point).

Recomputed after every ingest so answers are instant (§3.3), and cached against
`graph_rev` so a stale cache announces itself instead of quietly lying.
"""

from __future__ import annotations

import math
from typing import Any

import networkx as nx

from backend.graph.nx_adapter import case_graphs, project_people
from backend.graph.store import CaseStore

METRICS = ("betweenness", "pagerank", "degree")


def analysis_graph(store: CaseStore) -> nx.Graph:
    """The graph every score and every cluster is computed on.

    One function, so a score and the sentence explaining it can never disagree
    about which graph they came from. See `nx_adapter.project_people` for why
    it is the projected graph and not the raw one.
    """
    g, u = case_graphs(store)
    p, _owner = project_people(u, g)
    return p


def compute_metrics(p: nx.Graph, _unused: Any = None) -> dict[str, dict[str, float]]:
    """Scored on the person-projected graph (see `nx_adapter.project_people`),
    because "who matters" is a question about people and a man and his SIM are
    not two actors. Unattributed identifiers still score in their own right."""
    if p.number_of_nodes() == 0:
        return {m: {} for m in METRICS}

    # `distance` (1/weight), not `weight`: NetworkX reads the weight argument
    # as a cost, so passing raw weight would make well-evidenced links look far
    # apart and invert the whole result.
    betweenness = nx.betweenness_centrality(p, weight="distance", normalized=True)
    try:
        pagerank = nx.pagerank(p, weight="weight")
    except nx.PowerIterationFailedConvergence:
        pagerank = {n: 1.0 / p.number_of_nodes() for n in p}
    degree = {n: float(d) for n, d in p.degree(weight="weight")}

    return {"betweenness": betweenness, "pagerank": pagerank, "degree": degree}


def compute_communities(u: nx.Graph) -> list[dict]:
    """Louvain — the cells inside the network. NetworkX ships it since 3.0, so
    this needs no extra dependency (D2: nothing that has to be installed and
    stay up). Run on the same projected graph as the scores."""
    if u.number_of_nodes() == 0:
        return []
    seed_graph = u.subgraph([n for n in u if u.degree(n) > 0])
    if seed_graph.number_of_nodes() == 0:
        return []
    # seed fixed: the same graph must produce the same clusters every run, or
    # the demo says something different each time it is rehearsed.
    clusters = nx.community.louvain_communities(seed_graph, weight="weight", seed=42)
    out = []
    for i, members in enumerate(sorted(clusters, key=len, reverse=True)):
        members = sorted(members)
        out.append({
            "cluster_id": f"c{i + 1}",
            "members": members,
            "size": len(members),
            "people": [m for m in members if m.startswith("person:")],
        })
    return out


def _community_of(communities: list[dict]) -> dict[str, str]:
    return {m: c["cluster_id"] for c in communities for m in c["members"]}


def explain(
    node_id: str,
    metric: str,
    score: float,
    u: nx.Graph,
    store: CaseStore,
    membership: dict[str, str],
) -> str:
    """The sentence an officer reads. Facts only, all of them checkable."""
    node = store.get_node(node_id)
    label = node.label if node else node_id
    neighbours = list(u.neighbors(node_id)) if node_id in u else []
    bridged = sorted({membership.get(n) for n in neighbours} - {None, membership.get(node_id)})
    doc_count = len({s["doc_id"] for s in (node.sources if node else [])})

    bits = []
    if metric == "betweenness":
        bits.append(f"lies on {score:.0%} of the shortest paths in this network")
    elif metric == "pagerank":
        bits.append(f"ranks {score:.3f} by weighted connection volume")
    else:
        bits.append(f"has {int(score)} weighted connections")

    bits.append(f"{len(neighbours)} direct contact{'s' if len(neighbours) != 1 else ''}")

    if len(bridged) >= 2:
        bits.append(f"bridges {len(bridged)} groups that otherwise do not touch")
    elif bridged:
        bits.append(f"reaches into group {bridged[0]}")

    if node and node.type == "person":
        # Influence without paperwork — the distinction the whole system exists
        # to surface. "In 1 document" is true of a man named only in a CDR
        # export and of a man named in an FIR, and those are not the same fact.
        kinds = {(store.document(s["doc_id"]) or {}).get("kind")
                 for s in (node.sources if node else [])}
        reports = kinds & {"fir", "surveillance", "note"}
        if not doc_count:
            bits.append("named in no source document at all")
        elif not reports:
            records = ", ".join(sorted(k for k in kinds if k)) or "records"
            bits.append(f"named in no report — appears only in {records} data")
        else:
            bits.append(f"named in {doc_count} document{'s' if doc_count != 1 else ''}")

    return f"{label} " + "; ".join(bits) + "."


def top_influencers(
    store: CaseStore, metric: str = "betweenness", limit: int = 10,
    *, node_types: tuple[str, ...] = ("person",),
) -> list[dict]:
    """§5.2 `top_influencers`. Defaults to people — an officer asking who
    matters means who, not which cell tower."""
    if metric not in METRICS:
        raise ValueError(f"unknown metric {metric!r}; §5.2 allows {METRICS}")

    cached = store.get_analytics("metrics")
    p = analysis_graph(store)
    if cached and not cached["stale"]:
        scores = cached["value"][metric]
        communities = (store.get_analytics("communities") or {}).get("value") or []
    else:
        scores = compute_metrics(p)[metric]
        communities = compute_communities(p)

    membership = _community_of(communities)
    u = p  # explain() reads neighbours from the graph the score came from
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    out = []
    for node_id, score in ranked:
        if node_types and not node_id.startswith(tuple(f"{t}:" for t in node_types)):
            continue
        out.append({
            "node_id": node_id,
            "label": (store.get_node(node_id).label if store.get_node(node_id) else node_id),
            "score": round(float(score), 6),
            "metric": metric,
            "why": explain(node_id, metric, float(score), u, store, membership),
        })
        if len(out) >= limit:
            break
    return out


def recompute(store: CaseStore) -> dict[str, Any]:
    """Run everything and cache it. Called after every ingest (§3.3)."""
    from backend.analytics.anomalies import compute_anomalies, compute_findings

    g, u = case_graphs(store)
    p, _owner = project_people(u, g)
    metrics = compute_metrics(p)
    communities = compute_communities(p)
    store.put_analytics("metrics", metrics)
    store.put_analytics("communities", communities)

    anomalies = compute_anomalies(store, g, u)
    store.put_analytics("anomalies", anomalies)

    # Findings read the projected graph too, so "3 direct contacts" in a
    # headline means the same thing as the score that put it there.
    findings = compute_findings(store, g, p, metrics, communities, anomalies)
    store.put_analytics("findings", findings)

    return {
        "nodes": u.number_of_nodes(),
        "edges": g.number_of_edges(),
        "communities": len(communities),
        "anomalies": len(anomalies),
        "findings": len(findings),
        "graph_rev": store.graph_rev(),
    }
