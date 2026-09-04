"""SQLite -> NetworkX, and the path queries the agent's tools sit on.

Two views of the same case graph, because they answer different questions:

* `build_multigraph()` keeps every parallel edge — forty calls between two
  phones are forty edges, which is what `timeline` and `anomalies` need.
* `collapse(G)` folds them into one undirected weighted `nx.Graph` — which is
  what centrality, communities and shortest paths need. Direction is dropped
  deliberately: "how is Ravi connected to the account" is a question about
  connection, not about who dialled whom.

`distance = 1 / weight` on the collapsed graph, so a heavily-evidenced link is
a *shorter* hop. NetworkX treats a `weight` argument as a cost, so passing raw
weight would make well-evidenced links look far apart — the exact opposite.
"""

from __future__ import annotations

from typing import Iterable, Sequence

import networkx as nx

from backend.graph.store import CaseStore


def build_multigraph(store: CaseStore) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for n in store.nodes():
        g.add_node(n.id, **n.to_dict())
    for e in store.edges():
        g.add_edge(e.src, e.dst, key=e.id, **e.to_dict())
    return g


def collapse(g: nx.MultiDiGraph) -> nx.Graph:
    """Undirected, one edge per pair, weights summed, with `distance = 1/weight`
    and the list of underlying edge ids kept on `edge_ids` so a path can always
    be traced back to the facts that produced it."""
    u = nx.Graph()
    u.add_nodes_from(g.nodes(data=True))
    for src, dst, key, data in g.edges(keys=True, data=True):
        w = float(data.get("weight", 1.0))
        if u.has_edge(src, dst):
            slot = u[src][dst]
            slot["weight"] += w
            slot["edge_ids"].append(key)
            slot["types"].add(data.get("type"))
        else:
            u.add_edge(src, dst, weight=w, edge_ids=[key], types={data.get("type")})
    for _, _, slot in u.edges(data=True):
        slot["distance"] = 1.0 / max(slot["weight"], 1e-6)
        slot["types"] = sorted(t for t in slot["types"] if t)
    return u


def case_graphs(store: CaseStore) -> tuple[nx.MultiDiGraph, nx.Graph]:
    g = build_multigraph(store)
    return g, collapse(g)


OWNERSHIP_EDGES = ("OWNS", "REGISTERED_TO")
_OWNABLE = ("phone:", "account:", "device:", "vehicle:")


def project_people(u: nx.Graph, g: nx.MultiDiGraph) -> tuple[nx.Graph, dict[str, str]]:
    """Fold each identifier into the person who holds it.

    Centrality on the raw graph answers the wrong question. A kingpin whose only
    edge is `OWNS` to his own phone scores near zero, because every path runs
    through the phone node and stops at him. But "who matters in this network"
    is a question about *people*, and a person and their SIM are not two actors.

    So: every phone, account, device and vehicle with a known holder is
    contracted into that holder, and an edge between two identifiers becomes an
    edge between their owners. Identifiers with no known holder stay as
    themselves — an unattributed number is genuinely a separate actor until
    somebody attributes it.

    Returns the projected graph and the `identifier -> owner` map, so a score
    can always be traced back to the identifiers that earned it.
    """
    owner: dict[str, str] = {}
    for src, dst, data in g.edges(data=True):
        if data.get("type") not in OWNERSHIP_EDGES:
            continue
        # OWNS runs person -> identifier; REGISTERED_TO runs device -> phone.
        person, identifier = (src, dst) if src.startswith("person:") else (dst, src)
        if person.startswith("person:") and identifier.startswith(_OWNABLE):
            owner.setdefault(identifier, person)

    # A device registered to a phone that belongs to a person belongs to that
    # person too — one more hop, which is what makes a handset swap visible.
    for _ in range(2):
        for identifier, holder in list(owner.items()):
            if holder in owner:
                owner[identifier] = owner[holder]

    resolve = lambda n: owner.get(n, n)  # noqa: E731

    p = nx.Graph()
    for node, data in u.nodes(data=True):
        target = resolve(node)
        if target not in p:
            p.add_node(target, **(u.nodes[target] if target in u else data))
        p.nodes[target].setdefault("absorbed", [])
        if target != node:
            p.nodes[target]["absorbed"].append(node)

    for a, b, data in u.edges(data=True):
        ra, rb = resolve(a), resolve(b)
        if ra == rb:
            continue  # an owner's link to their own SIM is not a relationship
        w = float(data.get("weight", 1.0))
        if p.has_edge(ra, rb):
            slot = p[ra][rb]
            slot["weight"] += w
            slot["edge_ids"] += data.get("edge_ids", [])
        else:
            p.add_edge(ra, rb, weight=w, edge_ids=list(data.get("edge_ids", [])))
    for _, _, slot in p.edges(data=True):
        slot["distance"] = 1.0 / max(slot["weight"], 1e-6)
    return p, owner


def edge_ids_for_path(u: nx.Graph, path: Sequence[str]) -> list[str]:
    """Every underlying edge id along a node path, in order."""
    ids: list[str] = []
    for a, b in zip(path, path[1:]):
        if u.has_edge(a, b):
            ids.extend(u[a][b].get("edge_ids", []))
    return ids


def paths_between(
    u: nx.Graph,
    a: str,
    b: str,
    *,
    max_hops: int = 6,
    limit: int = 5,
    through_documents: bool = False,
) -> list[dict]:
    """Shortest-first simple paths, each carrying the edge ids it traverses.

    Shortest by hop count, not by weight: an investigator asking how two people
    are connected wants the fewest intermediaries, and a two-hop link through a
    single broker is the answer that matters even if a longer path carries more
    call volume.

    Document nodes are excluded by default. Every entity in a report is joined
    to that report by `MENTIONED_IN`, so a document is a hub that connects
    everything named in it to everything else — "connected because both appear
    in FIR 114" is true and nearly useless, and it shortcuts every real path.
    The honest version of that link is the `CO_OCCURS` edge, which is already
    in the graph and carries its own low confidence.
    """
    if a not in u or b not in u or a == b:
        return []
    if not through_documents:
        blocked = {n for n in u if n.startswith("doc:")} - {a, b}
        if blocked:
            u = u.subgraph([n for n in u if n not in blocked])
    out: list[dict] = []
    try:
        for path in nx.all_simple_paths(u, a, b, cutoff=max_hops):
            out.append({
                "path": list(path),
                "edges": edge_ids_for_path(u, path),
                "length": len(path) - 1,
            })
            if len(out) >= limit * 40:  # bounded: all_simple_paths can explode
                break
    except nx.NetworkXNoPath:
        return []
    out.sort(key=lambda p: (p["length"], -_path_weight(u, p["path"])))
    return out[:limit]


def _path_weight(u: nx.Graph, path: Sequence[str]) -> float:
    return sum(u[x][y].get("weight", 1.0) for x, y in zip(path, path[1:]) if u.has_edge(x, y))


def neighbourhood(
    g: nx.MultiDiGraph,
    node_id: str,
    *,
    depth: int = 1,
    edge_types: Iterable[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Node ids and edge ids within `depth` hops, following edges in either
    direction. Returns ids only — the caller reads full records from the store,
    which keeps one definition of what a Node looks like."""
    if node_id not in g:
        return [], []
    wanted = set(edge_types) if edge_types else None

    seen = {node_id}
    frontier = {node_id}
    edge_ids: list[str] = []
    for _ in range(max(0, depth)):
        nxt: set[str] = set()
        for n in frontier:
            for src, dst, key, data in list(g.out_edges(n, keys=True, data=True)) + \
                                        list(g.in_edges(n, keys=True, data=True)):
                if wanted and data.get("type") not in wanted:
                    continue
                other = dst if src == n else src
                edge_ids.append(key)
                if other not in seen:
                    nxt.add(other)
        seen |= nxt
        frontier = nxt
        if not frontier:
            break
    return sorted(seen), sorted(set(edge_ids))
