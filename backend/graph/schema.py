"""The frozen graph contract — README §5.1.

Node ids are `{type}:{normalised_value}` and are *stable*: the same real-world
entity always produces the same id, so ingesting a document twice merges into
the existing node instead of creating a second one. All entity resolution in
this system is that one property; there is no fuzzy matching (§3.2).

One documented exception to the id rule, which comes from §5.1's own examples:
document nodes use the prefix `doc:` (`doc:fir_114_001`), not `document:`,
because `sources[].doc_id`, `custody.ref` and `read_source_doc` all speak that
form. `ID_PREFIX` below is the single place that knows it.

The other rule from §5.1: **no node and no edge may exist with an empty
`sources` array.** It is enforced here and again in the store.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

NODE_TYPES = (
    "person", "phone", "organization", "location",
    "vehicle", "account", "device", "event", "document",
)

EDGE_TYPES = (
    "CALLED", "MESSAGED", "TRANSFERRED_TO", "CO_OCCURS",
    "OWNS", "LOCATED_AT", "REGISTERED_TO", "MENTIONED_IN",
)

ID_PREFIX = {"document": "doc"}          # §5.1's own example wins
TYPE_FOR_PREFIX = {"doc": "document"} | {t: t for t in NODE_TYPES}


class SchemaError(ValueError):
    """A fact that does not satisfy §5.1."""


class SourcelessFact(SchemaError):
    """A node or edge with no provenance. §3.1: this is a bug, not a warning."""


# ---------------------------------------------------------------- normalising

_TITLES = {"mr", "mrs", "ms", "miss", "shri", "smt", "sh", "sri", "dr", "kum", "late"}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def normalise_person(name: str) -> str:
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", str(name).strip().lower()) if p]
    while parts and parts[0] in _TITLES:
        parts.pop(0)
    return "_".join(parts)


def normalise_phone(raw: str) -> str:
    """Indian numbers to a single canonical form: 91 + ten digits.

    Anything that is not recognisably a ten-digit Indian mobile is kept as its
    digits, so a landline or a foreign number still gets a stable id rather
    than being dropped.
    """
    d = re.sub(r"\D", "", str(raw))
    if len(d) == 13 and d.startswith("091"):
        d = d[3:]
    elif len(d) == 12 and d.startswith("91"):
        d = d[2:]
    elif len(d) == 11 and d.startswith("0"):
        d = d[1:]
    if len(d) == 10 and d[0] in "6789":
        return "91" + d
    return d


def normalise_vehicle(raw: str) -> str:
    """`PB 10 AB 1234`, `PB-10-AB-1234` and `PB10AB1234` are one vehicle.
    Registration numbers have no real word boundaries, so separators go."""
    return re.sub(r"[^a-z0-9]+", "", str(raw).strip().lower())


_NORMALISERS = {
    "person": normalise_person,
    "phone": normalise_phone,
    "vehicle": normalise_vehicle,
    "device": normalise_vehicle,   # IMEIs, same reasoning
}


def normalise(type_: str, value: str) -> str:
    return _NORMALISERS.get(type_, _slug)(value)


def make_id(type_: str, value: str) -> str:
    if type_ not in NODE_TYPES:
        raise SchemaError(f"unknown node type {type_!r}; §5.1 lists {NODE_TYPES}")
    norm = normalise(type_, value)
    if not norm:
        raise SchemaError(f"{type_} value {value!r} normalises to an empty id")
    return f"{ID_PREFIX.get(type_, type_)}:{norm}"


def type_of(node_id: str) -> str:
    prefix = str(node_id).split(":", 1)[0]
    if prefix not in TYPE_FOR_PREFIX:
        raise SchemaError(f"id {node_id!r} has no recognised type prefix")
    return TYPE_FOR_PREFIX[prefix]


# -------------------------------------------------------------------- records

def _clean_sources(sources: Iterable[dict] | None) -> list[dict]:
    """Dedupe and validate provenance. Offsets are optional (a CSV row has no
    character range in a text file) but `doc_id` never is."""
    seen, out = set(), []
    for s in sources or []:
        doc_id = s.get("doc_id")
        if not doc_id:
            raise SourcelessFact(f"source {s!r} has no doc_id")
        key = (doc_id, s.get("start"), s.get("end"))
        if key in seen:
            continue
        seen.add(key)
        rec = {"doc_id": doc_id}
        if s.get("start") is not None:
            rec["start"] = int(s["start"])
        if s.get("end") is not None:
            rec["end"] = int(s["end"])
        out.append(rec)
    return out


@dataclass
class Node:
    id: str
    type: str
    label: str
    attrs: dict[str, Any] = field(default_factory=dict)
    first_seen: str | None = None
    last_seen: str | None = None
    sources: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.type not in NODE_TYPES:
            raise SchemaError(f"unknown node type {self.type!r}")
        if not str(self.id).startswith(ID_PREFIX.get(self.type, self.type) + ":"):
            raise SchemaError(f"node id {self.id!r} does not match type {self.type!r}")
        self.sources = _clean_sources(self.sources)
        if not self.sources:
            raise SourcelessFact(f"node {self.id} has no sources (§5.1)")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "type": self.type, "label": self.label,
            "attrs": self.attrs, "first_seen": self.first_seen,
            "last_seen": self.last_seen, "sources": self.sources,
        }


@dataclass
class Edge:
    src: str
    dst: str
    type: str
    attrs: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    confidence: float = 1.0
    sources: list[dict] = field(default_factory=list)
    id: str | None = None          # assigned by the store on first insert

    def __post_init__(self) -> None:
        if self.type not in EDGE_TYPES:
            raise SchemaError(f"unknown edge type {self.type!r}; §5.1 lists {EDGE_TYPES}")
        if self.src == self.dst:
            raise SchemaError(f"self-loop on {self.src} ({self.type})")
        self.sources = _clean_sources(self.sources)
        if not self.sources:
            raise SourcelessFact(f"edge {self.src}-[{self.type}]->{self.dst} has no sources (§5.1)")

    @property
    def ts(self) -> str | None:
        """Timestamps live in `attrs` so the §5.1 shape is unchanged; the store
        also keeps a denormalised column so `timeline()` can index on it."""
        return self.attrs.get("ts")

    def natural_key(self) -> str:
        """What makes two edges the same edge. Re-ingesting a document merges
        onto this key instead of appending a duplicate."""
        return f"{self.src}|{self.type}|{self.dst}|{self.ts or ''}"

    def to_dict(self) -> dict:
        return {
            "id": self.id, "src": self.src, "dst": self.dst, "type": self.type,
            "attrs": self.attrs, "weight": self.weight,
            "confidence": self.confidence, "sources": self.sources,
        }
