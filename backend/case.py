"""Case lifecycle — README §5.5.

One officer runs several cases at once and each one gets its own agent. That is
not a feature bolted on top; it is what a case *is* here: a directory, a SQLite
file, a custody chain and a memory that no other case can reach (§2.4).

**The system is not built for one kind of crime.** Nothing in ingest, the graph,
the analytics or the agent knows what a trafficking case is — they know
identifiers, links, timing and structure, which every investigation has. What
makes a case specific is written here: `case_type` and `brief` are the officer's
own words about what he is working, and they are threaded into the agent's
context so the same engine reasons like a fraud analyst on a fraud case and like
a homicide analyst on a homicide. The demo case (§9) is one scenario, not the
shape of the product.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from backend.config import CASES_ROOT, case_dir, check_case_id, now_iso
from backend.custody.chain import CustodyChain
from backend.graph.store import CaseStore


@dataclass
class CaseMeta:
    case_id: str
    title: str = ""
    officer: str = "officer:unknown"
    case_type: str = ""       # free text: "financial fraud", "homicide", "extortion"...
    brief: str = ""           # what the officer wants the agent to know going in
    status: str = "open"
    created: str = field(default_factory=now_iso)
    updated: str = field(default_factory=now_iso)
    synthetic: bool = False

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: dict) -> "CaseMeta":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


def meta_path(case_id: str) -> Path:
    return case_dir(case_id) / "meta.json"


def create_case(
    case_id: str, *, title: str = "", officer: str = "officer:unknown",
    case_type: str = "", brief: str = "", synthetic: bool = False,
    exist_ok: bool = False,
) -> CaseMeta:
    check_case_id(case_id)
    if meta_path(case_id).exists() and not exist_ok:
        raise FileExistsError(f"case {case_id!r} already exists")

    meta = CaseMeta(case_id=case_id, title=title or case_id, officer=officer,
                    case_type=case_type, brief=brief, synthetic=synthetic)
    store = CaseStore(case_id)          # creates the directory tree and graph.db
    store.close()
    CustodyChain(case_id)               # creates an empty chain
    write_meta(meta)
    return meta


def read_meta(case_id: str) -> CaseMeta | None:
    path = meta_path(case_id)
    if not path.exists():
        return None
    try:
        return CaseMeta.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, TypeError):
        return CaseMeta(case_id=case_id, title=case_id)


def write_meta(meta: CaseMeta) -> CaseMeta:
    meta.updated = now_iso()
    meta_path(meta.case_id).parent.mkdir(parents=True, exist_ok=True)
    meta_path(meta.case_id).write_text(
        json.dumps(meta.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


def update_meta(case_id: str, **fields) -> CaseMeta | None:
    meta = read_meta(case_id)
    if meta is None:
        return None
    for key, value in fields.items():
        if key in CaseMeta.__dataclass_fields__ and key != "case_id" and value is not None:
            setattr(meta, key, value)
    return write_meta(meta)


def list_cases(officer: str | None = None) -> list[dict]:
    """Every case on this machine, newest first. An officer's own list is a
    filter over the same directory — there is no cross-case store to consult."""
    if not CASES_ROOT.exists():
        return []
    out = []
    for path in CASES_ROOT.iterdir():
        if not path.is_dir() or not (path / "meta.json").exists():
            continue
        meta = read_meta(path.name)
        if meta is None or (officer and meta.officer != officer):
            continue
        row = meta.to_dict()
        try:
            with CaseStore(meta.case_id, create=False) as store:
                row["counts"] = store.counts()
                row["open_questions"] = len(
                    store.memory(kind="open_question", status="open", limit=200))
        except (FileNotFoundError, Exception):
            row["counts"] = {"nodes": 0, "edges": 0, "documents": 0}
        out.append(row)
    return sorted(out, key=lambda c: c.get("updated", ""), reverse=True)


def delete_case(case_id: str) -> bool:
    """Removes the whole case directory. The only destructive call in the
    backend — the API keeps it behind an explicit confirmation."""
    path = case_dir(case_id)
    if not path.exists():
        return False
    shutil.rmtree(path)
    return True


def agent_context_header(case_id: str) -> str:
    """The case's own words, prepended to whatever the agent is asked.

    This is what makes one engine work across every kind of case: the officer
    says what he is investigating, and it is in front of the agent on every
    turn — alongside the graph, which supplies the facts.
    """
    meta = read_meta(case_id)
    if meta is None:
        return ""
    bits = [f"Case {meta.case_id}"]
    if meta.title:
        bits.append(f'titled "{meta.title}"')
    if meta.case_type:
        bits.append(f"— a {meta.case_type} case")
    header = " ".join(bits) + "."
    if meta.brief:
        header += (f"\n\nWhat the investigating officer told you about this case:\n"
                   f"{meta.brief.strip()}")
    return header
