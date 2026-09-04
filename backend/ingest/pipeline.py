"""Document in, graph out — README §3.1 → §3.2 → §3.3, in that order.

One call per document:

    text -> identifiers + names (with offsets)
         -> nodes and edges (every one carrying its provenance)
         -> custody entries (ingest, then extract)
         -> analytics recomputed
         -> counts back to the caller

Two structural rules this module exists to hold:

* **Nothing enters the graph without a source.** Every node and edge built here
  passes `{doc_id, start, end}` through, and `schema.py` refuses the rest.
* **Ingesting the same file twice is a no-op on the graph.** Node ids and edge
  natural keys are stable, so re-running the generator or re-uploading an FIR
  merges rather than doubles. The demo depends on this.

Structured sources (CDR, bank statements) become real typed edges — `CALLED`,
`TRANSFERRED_TO`. Unstructured prose becomes `MENTIONED_IN` plus weak
`CO_OCCURS` links, and `OWNS` where a phone sits right beside a person's name.
Weak links are marked weak (low `weight`, low `confidence`) rather than
excluded, because betweenness over a graph of only strong edges misses exactly
the broker the demo is built to find.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from backend.config import now_iso
from backend.custody.chain import CustodyChain, sha256_hex
from backend.graph.schema import Edge, Node, SchemaError, make_id
from backend.graph.store import CaseStore
from backend.ingest import structured
from backend.ingest.ner import extract_named_entities
from backend.ingest.patterns import Extraction, extract_datetimes, extract_identifiers
from backend.ingest.readers import ReadResult, read_document

# How close two mentions must be, in characters, to count as co-occurring.
# A paragraph, roughly. Document-wide pairing would make every FIR a clique.
CO_OCCUR_WINDOW = 600
# How close a phone must be to a name to read as "this person's number".
OWNS_WINDOW = 120

CO_OCCUR_WEIGHT = 0.3
CO_OCCUR_CONFIDENCE = 0.4
OWNS_CONFIDENCE = 0.6

# Entity types worth linking to each other in prose. Documents and events are
# excluded: everything in a document co-occurs with the document.
_LINKABLE = {"person", "phone", "organization", "location", "vehicle", "account", "device"}


@dataclass
class IngestResult:
    doc_id: str
    kind: str
    chars: int
    nodes_new: int = 0
    edges_new: int = 0
    entities: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "doc_id": self.doc_id, "kind": self.kind, "chars": self.chars,
            "nodes_new": self.nodes_new, "edges_new": self.edges_new,
            "entities": self.entities, "warnings": self.warnings,
        }


def make_doc_id(store: CaseStore, filename: str, sha256: str | None = None) -> str:
    """`doc:fir_114_001` — readable, stable, and unique inside the case.

    Identical bytes are the same document, however they are named. An officer
    who re-uploads the same PDF, or a collector that runs twice, must not get a
    second copy of the same evidence in the graph — so a matching sha256 wins
    over the filename. The custody chain still records the second upload: that
    it happened is a fact, that it is new evidence is not.
    """
    if sha256:
        for doc in store.documents():
            if doc["sha256"] == sha256:
                return doc["doc_id"]

    stem = re.sub(r"[^a-z0-9]+", "_", Path(filename).stem.lower()).strip("_") or "doc"
    candidate = f"doc:{stem}"
    n = 1
    while store.document(candidate) is not None:
        n += 1
        candidate = f"doc:{stem}_{n:03d}"
    return candidate


def ingest_file(
    store: CaseStore,
    chain: CustodyChain,
    path: Path,
    *,
    kind: str | None = None,
    actor: str = "system",
    doc_id: str | None = None,
) -> IngestResult:
    """Read a file off disk, copy it into the case, and fold it into the graph."""
    path = Path(path)
    read = read_document(path, kind=kind)
    doc_id = doc_id or make_doc_id(store, path.name, read.sha256)

    # The original is kept inside the case directory: §5.5 `docs/`, so a
    # citation can be traced to the bytes that were uploaded, not just to text.
    kept = store.dir / "docs" / f"{doc_id.replace(':', '__')}{path.suffix.lower()}"
    kept.parent.mkdir(parents=True, exist_ok=True)
    if path.resolve() != kept.resolve():
        shutil.copy2(path, kept)

    return ingest_read(store, chain, read, doc_id=doc_id, filename=path.name, actor=actor)


def ingest_text(
    store: CaseStore,
    chain: CustodyChain,
    text: str,
    *,
    filename: str,
    kind: str = "note",
    actor: str = "system",
) -> IngestResult:
    """Same pipeline for text that never was a file (a pasted statement)."""
    read = ReadResult(text=text, kind=kind, sha256=sha256_hex(text))
    return ingest_read(store, chain, read, doc_id=make_doc_id(store, filename, read.sha256),
                       filename=filename, actor=actor)


def ingest_read(
    store: CaseStore,
    chain: CustodyChain,
    read: ReadResult,
    *,
    doc_id: str,
    filename: str,
    actor: str = "system",
) -> IngestResult:
    result = IngestResult(doc_id=doc_id, kind=read.kind, chars=len(read.text))
    before = store.counts()

    store.register_document(
        doc_id=doc_id, filename=filename, kind=read.kind,
        sha256=read.sha256, char_len=len(read.text),
        meta=read.meta | {"ingested_by": actor},
    )
    store.extracted_path(doc_id).write_text(read.text, encoding="utf-8")

    # Custody entry #1: these bytes arrived. Written before anything is derived
    # from them, so the chain records the input independently of the output.
    chain.append(action="ingest", actor=actor, ref=doc_id,
                 payload_sha256=read.sha256)

    # The document is a node, so `MENTIONED_IN` has somewhere to point and the
    # graph can answer "which documents name this person".
    self_source = [{"doc_id": doc_id, "start": 0, "end": len(read.text)}]
    store.upsert_node(Node(
        id=doc_id, type="document", label=filename,
        attrs={"kind": read.kind, "sha256": read.sha256, "chars": len(read.text)},
        sources=self_source,
    ))

    if read.rows:
        counts = structured.ingest_rows(store, read.rows, doc_id=doc_id, kind=read.kind,
                                        text=read.text)
        result.warnings += counts.get("warnings", [])

    # Proximity linking is for prose only. In a CSV, "near each other in the
    # file" means "near each other in time", not "related" — running it over a
    # CDR export links every number to whoever happens to sit in the next rows
    # and buries the real structure under thousands of meaningless edges. The
    # structured handler above already produced this file's real edges; we
    # still sweep the text for identifiers in columns it did not recognise.
    entity_ids = _ingest_prose(store, read.text, doc_id=doc_id,
                               link_proximity=not read.rows)
    result.entities = entity_ids

    after = store.counts()
    result.nodes_new = after["nodes"] - before["nodes"]
    result.edges_new = after["edges"] - before["edges"]

    # Custody entry #2: this is what we derived. Separate from the ingest entry
    # so tampering with an inference is distinguishable from tampering with
    # evidence — which is the distinction that matters in the real domain.
    chain.append(action="extract", actor="system", ref=doc_id,
                 payload={"nodes_new": result.nodes_new, "edges_new": result.edges_new,
                          "entities": entity_ids})
    store.commit()
    return result


# ---------------------------------------------------------------- prose -> graph

def _ingest_prose(
    store: CaseStore, text: str, *, doc_id: str, link_proximity: bool = True,
) -> list[str]:
    """Identifiers + names out of free text, then the links between them.

    `link_proximity=False` for structured files — see `ingest_read`.
    """
    extractions = extract_identifiers(text) + extract_named_entities(text)
    dates = extract_datetimes(text)

    placed: list[tuple[str, int, int]] = []          # (node_id, start, end)
    for ex in extractions:
        try:
            node_id = make_id(ex.node_type, ex.value)
        except SchemaError:
            continue
        first, last = _window_for(ex.start, dates)
        store.upsert_node(Node(
            id=node_id, type=ex.node_type, label=ex.label,
            attrs={"aliases": [ex.label]} | (ex.attrs or {}),
            first_seen=first, last_seen=last,
            sources=[{"doc_id": doc_id, "start": ex.start, "end": ex.end}],
        ))
        placed.append((node_id, ex.start, ex.end))

    doc_source = [{"doc_id": doc_id, "start": 0, "end": len(text)}]
    for node_id, start, end in placed:
        store.upsert_edge(Edge(
            src=node_id, dst=doc_id, type="MENTIONED_IN",
            attrs={"offset": start}, weight=1.0, confidence=1.0,
            sources=[{"doc_id": doc_id, "start": start, "end": end}],
        ))

    if link_proximity:
        _link_proximity(store, placed, doc_id=doc_id)
    return sorted({node_id for node_id, _, _ in placed})


def _window_for(pos: int, dates: list[tuple[int, int, str]]) -> tuple[str | None, str | None]:
    """The timestamps nearest a mention become that entity's seen-window. A
    document with no date leaves both None rather than inventing `now`."""
    if not dates:
        return None, None
    near = sorted(dates, key=lambda d: abs(d[0] - pos))[:3]
    stamps = sorted(iso for _, _, iso in near)
    return stamps[0], stamps[-1]


def _link_proximity(store: CaseStore, placed: list[tuple[str, int, int]], *, doc_id: str) -> None:
    """`OWNS` where a phone sits beside a name; `CO_OCCURS` for everything else
    mentioned nearby. Both are weak by construction and labelled as such."""
    people = [(i, s, e) for i, s, e in placed if i.startswith("person:")]
    linkable = [(i, s, e) for i, s, e in placed if i.split(":", 1)[0] in _LINKABLE]

    # Only the NEAREST person claims an identifier. "Ravi Kumar was seen with
    # one Manjit Singh (mob. 9814227731)" puts both names inside the window, and
    # linking both makes Ravi the owner of Manjit's phone — a false edge that
    # then shows up as a real-looking path. A number has one holder in a
    # sentence; the closest name is the honest guess, and it is still only a
    # guess, which is what `confidence` records.
    owned: set[tuple[str, str]] = set()
    for oid, os_, oe in linkable:
        if not oid.startswith(("phone:", "account:", "vehicle:", "device:")):
            continue
        best: tuple[int, str] | None = None
        for pid, ps, pe in people:
            gap = os_ - pe if os_ >= pe else ps - oe
            if 0 <= gap <= OWNS_WINDOW and (best is None or gap < best[0]):
                best = (gap, pid)
        if best is None:
            continue
        gap, pid = best
        ps, pe = next((s, e) for i, s, e in people if i == pid)
        store.upsert_edge(Edge(
            src=pid, dst=oid, type="OWNS",
            attrs={"basis": "text_proximity", "gap_chars": gap},
            weight=1.0, confidence=OWNS_CONFIDENCE,
            sources=[{"doc_id": doc_id, "start": min(ps, os_), "end": max(pe, oe)}],
        ))
        owned.add((pid, oid))

    for idx, (a_id, a_s, a_e) in enumerate(linkable):
        for b_id, b_s, b_e in linkable[idx + 1:]:
            if a_id == b_id or (a_id, b_id) in owned or (b_id, a_id) in owned:
                continue
            gap = b_s - a_e if b_s >= a_e else a_s - b_e
            if gap > CO_OCCUR_WINDOW:
                continue
            src, dst = sorted((a_id, b_id))      # undirected fact, stable key
            store.upsert_edge(Edge(
                src=src, dst=dst, type="CO_OCCURS",
                attrs={"basis": "same_document", "gap_chars": max(gap, 0)},
                weight=CO_OCCUR_WEIGHT, confidence=CO_OCCUR_CONFIDENCE,
                sources=[{"doc_id": doc_id,
                          "start": min(a_s, b_s), "end": max(a_e, b_e)}],
            ))
