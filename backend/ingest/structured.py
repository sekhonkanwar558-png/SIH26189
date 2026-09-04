"""CDR and financial rows -> typed edges — README §3.2.

These are the strong edges. A CDR row is not an inference: A called B at 22:10
for 94 seconds off tower LDH-014, and that becomes exactly one `CALLED` edge
carrying exactly that. Everything the agent later says about contact between
two people traces back to rows like these.

Column names vary by operator and by bank, so each field is matched against a
list of aliases rather than one fixed header. An unrecognised column is not an
error — it is reported in `warnings` so whoever exported the file can see what
was ignored, instead of it vanishing silently.

**Edge directions, decided once so the whole team reads the graph the same way:**

* `phone:A  -[CALLED]->        phone:B`     A dialled B
* `phone:A  -[MESSAGED]->      phone:B`     A texted B
* `account:X-[TRANSFERRED_TO]->account:Y`   money moved X to Y
* `person:P -[OWNS]->          phone/account`  a subscriber or holder record
* `device:I -[REGISTERED_TO]-> phone:N`     handset I carried number N
* `phone:A  -[LOCATED_AT]->    location:T`  A used tower T

The `device -> phone` direction is deliberate: it is how a burner-swap is
found. One handset with several numbers registered to it is one person
changing SIMs, and that is visible only when the IMEI is the source node.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable, Sequence

from backend.config import IST
from backend.graph.schema import Edge, Node, SchemaError, make_id
from backend.graph.store import CaseStore

# field -> accepted column names, lowercased with spaces/dashes as underscores
CDR_COLUMNS = {
    "caller":     ("caller", "a_party", "calling_number", "from", "msisdn", "caller_number"),
    "callee":     ("callee", "b_party", "called_number", "to", "receiver", "callee_number"),
    "ts":         ("ts", "timestamp", "datetime", "date_time", "call_time", "start_time", "date"),
    "duration":   ("duration", "duration_sec", "duration_seconds", "dur"),
    "call_type":  ("call_type", "type", "cdr_type", "service"),
    "imei":       ("imei", "imei_a", "caller_imei", "handset"),
    "tower":      ("tower", "cell_id", "cell_site", "site_id", "location", "cgi"),
    "subscriber": ("subscriber", "caller_name", "a_party_name", "registered_to"),
}

FIN_COLUMNS = {
    "src":     ("from_account", "remitter_account", "debit_account", "from", "payer_account"),
    "dst":     ("to_account", "beneficiary_account", "credit_account", "to", "payee_account"),
    "amount":  ("amount", "amt", "value", "transaction_amount"),
    "ts":      ("ts", "timestamp", "datetime", "date", "txn_date", "value_date"),
    "txn_id":  ("txn_id", "transaction_id", "reference", "ref_no", "utr"),
    "mode":    ("mode", "channel", "type", "txn_type"),
    "holder":  ("holder", "account_holder", "remitter", "remitter_name", "payer_name"),
    "payee":   ("payee", "beneficiary", "beneficiary_name", "payee_name"),
    "ifsc":    ("ifsc", "ifsc_code", "beneficiary_ifsc"),
}


def _norm_key(key: str) -> str:
    return re.sub(r"[\s\-]+", "_", (key or "").strip().lower())


def _pick(row: dict, aliases: Sequence[str]) -> str | None:
    norm = {_norm_key(k): v for k, v in row.items()}
    for alias in aliases:
        value = norm.get(alias)
        if value not in (None, ""):
            return str(value).strip()
    return None


def parse_ts(raw: str | None) -> str | None:
    """Operators and banks export half a dozen date formats. Unparseable is
    None, never `now` — a wrong timestamp corrupts every temporal analysis."""
    if not raw:
        return None
    raw = str(raw).strip()
    formats = (
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
        "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%d-%m-%Y",
        "%d-%b-%Y %H:%M", "%d %b %Y %H:%M", "%d-%b-%Y",
    )
    try:
        return datetime.fromisoformat(raw).astimezone(IST).isoformat(timespec="seconds")
    except ValueError:
        pass
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=IST).isoformat(timespec="seconds")
        except ValueError:
            continue
    return None


def _amount(raw: str | None) -> float | None:
    if not raw:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", str(raw))
    try:
        return float(cleaned)
    except ValueError:
        return None


def ingest_rows(
    store: CaseStore, rows: list[dict], *, doc_id: str, kind: str, text: str = "",
) -> dict:
    """Dispatch a parsed CSV to the right row handler."""
    if kind == "cdr":
        return _ingest_cdr(store, rows, doc_id=doc_id, text=text)
    if kind == "financial":
        return _ingest_financial(store, rows, doc_id=doc_id, text=text)
    return {"warnings": [f"{doc_id}: CSV kind {kind!r} has no structured handler; "
                         "its text was still extracted and searched for identifiers"]}


def _row_span(text: str, row_index: int, header_offset: int = 1) -> dict:
    """Character range of a CSV row in the raw file, so a CDR edge cites the
    line it came from exactly as an FIR edge cites its sentence."""
    if not text:
        return {"doc_id": "", "start": None, "end": None}
    lines = text.splitlines(keepends=True)
    idx = row_index + header_offset
    if idx >= len(lines):
        return {}
    start = sum(len(x) for x in lines[:idx])
    return {"start": start, "end": start + len(lines[idx])}


def _ensure(store: CaseStore, node_type: str, value: str, source: dict,
            attrs: dict | None = None) -> str | None:
    try:
        node_id = make_id(node_type, value)
    except SchemaError:
        return None
    store.upsert_node(Node(
        id=node_id, type=node_type, label=str(value).strip(),
        attrs={"aliases": [str(value).strip()]} | (attrs or {}),
        sources=[source],
    ))
    return node_id


def _ingest_cdr(store: CaseStore, rows: list[dict], *, doc_id: str, text: str) -> dict:
    warnings: list[str] = []
    if rows and not (_pick(rows[0], CDR_COLUMNS["caller"]) and _pick(rows[0], CDR_COLUMNS["callee"])):
        warnings.append(
            f"{doc_id}: no caller/callee columns found in {sorted(rows[0])}; "
            f"expected one of {CDR_COLUMNS['caller']} and {CDR_COLUMNS['callee']}"
        )
        return {"warnings": warnings}

    for i, row in enumerate(rows):
        span = _row_span(text, i)
        source = {"doc_id": doc_id} | {k: v for k, v in span.items() if k in ("start", "end")}

        a = _pick(row, CDR_COLUMNS["caller"])
        b = _pick(row, CDR_COLUMNS["callee"])
        if not a or not b:
            continue
        a_id = _ensure(store, "phone", a, source)
        b_id = _ensure(store, "phone", b, source)
        if not a_id or not b_id or a_id == b_id:
            continue

        ts = parse_ts(_pick(row, CDR_COLUMNS["ts"]))
        duration = _amount(_pick(row, CDR_COLUMNS["duration"]))
        call_type = (_pick(row, CDR_COLUMNS["call_type"]) or "call").lower()
        edge_type = "MESSAGED" if call_type.startswith(("sms", "msg", "text")) else "CALLED"

        store.upsert_edge(Edge(
            src=a_id, dst=b_id, type=edge_type,
            attrs={"ts": ts, "duration_sec": duration, "call_type": call_type,
                   "tower": _pick(row, CDR_COLUMNS["tower"])},
            weight=1.0, confidence=0.95, sources=[source],
        ))

        imei = _pick(row, CDR_COLUMNS["imei"])
        if imei:
            imei_id = _ensure(store, "device", imei, source)
            if imei_id:
                store.upsert_edge(Edge(
                    src=imei_id, dst=a_id, type="REGISTERED_TO",
                    attrs={"basis": "cdr_handset"}, weight=1.0, confidence=0.95,
                    sources=[source],
                ))

        tower = _pick(row, CDR_COLUMNS["tower"])
        if tower:
            tower_id = _ensure(store, "location", tower, source, {"kind": "cell_tower"})
            if tower_id:
                store.upsert_edge(Edge(
                    src=a_id, dst=tower_id, type="LOCATED_AT",
                    attrs={"ts": ts, "basis": "cdr_tower"}, weight=1.0, confidence=0.9,
                    sources=[source],
                ))

        subscriber = _pick(row, CDR_COLUMNS["subscriber"])
        if subscriber:
            person_id = _ensure(store, "person", subscriber, source)
            if person_id:
                store.upsert_edge(Edge(
                    src=person_id, dst=a_id, type="OWNS",
                    attrs={"basis": "subscriber_record"}, weight=1.0, confidence=0.95,
                    sources=[source],
                ))
    return {"warnings": warnings}


def _ingest_financial(store: CaseStore, rows: list[dict], *, doc_id: str, text: str) -> dict:
    warnings: list[str] = []
    if rows and not (_pick(rows[0], FIN_COLUMNS["src"]) and _pick(rows[0], FIN_COLUMNS["dst"])):
        warnings.append(
            f"{doc_id}: no source/destination account columns found in {sorted(rows[0])}"
        )
        return {"warnings": warnings}

    for i, row in enumerate(rows):
        span = _row_span(text, i)
        source = {"doc_id": doc_id} | {k: v for k, v in span.items() if k in ("start", "end")}

        src_acct = _pick(row, FIN_COLUMNS["src"])
        dst_acct = _pick(row, FIN_COLUMNS["dst"])
        if not src_acct or not dst_acct:
            continue
        src_id = _ensure(store, "account", src_acct, source)
        dst_id = _ensure(store, "account", dst_acct, source,
                         {"ifsc": _pick(row, FIN_COLUMNS["ifsc"])})
        if not src_id or not dst_id or src_id == dst_id:
            continue

        store.upsert_edge(Edge(
            src=src_id, dst=dst_id, type="TRANSFERRED_TO",
            attrs={"ts": parse_ts(_pick(row, FIN_COLUMNS["ts"])),
                   "amount": _amount(_pick(row, FIN_COLUMNS["amount"])),
                   "mode": _pick(row, FIN_COLUMNS["mode"]),
                   "txn_id": _pick(row, FIN_COLUMNS["txn_id"])},
            weight=1.0, confidence=0.95, sources=[source],
        ))

        for column, account_id in (("holder", src_id), ("payee", dst_id)):
            name = _pick(row, FIN_COLUMNS[column])
            if not name:
                continue
            person_id = _ensure(store, "person", name, source)
            if person_id:
                store.upsert_edge(Edge(
                    src=person_id, dst=account_id, type="OWNS",
                    attrs={"basis": "bank_record"}, weight=1.0, confidence=0.95,
                    sources=[source],
                ))
    return {"warnings": warnings}
