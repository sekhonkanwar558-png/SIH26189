"""Tabular rows -> typed edges — README §3.2.

Four of §1.1's seven sources arrive as tables and are handled here: **CDR**,
**financial records**, **social media intelligence** and **criminal history**.
(FIRs, surveillance notes and intelligence reports are prose and go through
`pipeline._ingest_prose` instead.)

These are the strong edges. A CDR row is not an inference: A called B at 22:10
for 94 seconds off tower LDH-014, and that becomes exactly one `CALLED` edge
carrying exactly that. Everything the agent later says about contact between
two people traces back to rows like these.

**No new node or edge type was added for the two sources that came last**
(social, criminal history) — see D19. §5.1 is frozen and the front end is being
built against it; a handle is an `account`, a prior case is an `event`, and
what kind of link a `CO_OCCURS` is gets said in `attrs.basis`, which is where
this module already put `text_proximity` and `cdr_handset`.

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
* `account:H-[MESSAGED]->      account:H2` a DM or reply between two handles
* `person:P -[OWNS]->          account:H`  a handle's display name, weakly
* `person:P -[MENTIONED_IN]->  event:C`    P is named in prior case C
* `person:P -[CO_OCCURS]->     person:Q`   P and Q charged in the same case
* `event:C -[LOCATED_AT]->     location:S` case C was registered at station S

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

# Social media intelligence. Exports differ wildly by platform and by whichever
# OSINT tool produced the file, so `interaction` is matched loosely and an
# unrecognised value degrades to a weak link rather than being dropped.
SOCIAL_COLUMNS = {
    "platform":    ("platform", "network", "site", "source_platform", "app"),
    "handle":      ("handle", "username", "user", "screen_name", "from_handle", "author",
                    "profile", "account", "from", "source_handle"),
    "target":      ("to_handle", "target_handle", "target", "peer", "mentioned", "mentions",
                    "in_reply_to", "reply_to", "follows", "followed", "to", "with"),
    "interaction": ("interaction", "action", "relation", "event", "type", "activity"),
    "display":     ("display_name", "name", "full_name", "real_name", "profile_name"),
    "ts":          ("ts", "timestamp", "datetime", "date", "posted_at", "created_at", "time"),
    "text":        ("text", "content", "message", "post", "body", "caption"),
    "url":         ("url", "link", "permalink", "post_url", "profile_url"),
    "location":    ("location", "place", "geo", "geotag", "checkin"),
}

# Criminal history databases — prior cases against a named person.
HISTORY_COLUMNS = {
    "person":     ("person", "name", "accused", "accused_name", "offender", "suspect",
                   "subject", "full_name", "offender_name"),
    "case_no":    ("case_no", "case_number", "fir_no", "fir_number", "crime_no", "cr_no",
                   "rc_no", "case_id", "fir"),
    "offence":    ("offence", "offense", "section", "sections", "ipc_section", "act",
                   "charge", "crime_head", "under_section"),
    "ts":         ("date", "ts", "date_of_offence", "registration_date", "incident_date",
                   "timestamp", "year", "fir_date"),
    "station":    ("police_station", "ps", "station", "thana", "jurisdiction"),
    "court":      ("court", "court_name", "trial_court"),
    "status":     ("status", "disposal", "case_status", "outcome", "result", "verdict"),
    "co_accused": ("co_accused", "coaccused", "associates", "other_accused", "accomplices"),
    "role":       ("role", "involvement", "accused_role"),
}

# A conviction is not a charge. The agent is told which it is, and
# `_repeat_offenders` in analytics counts them separately.
_CONVICTED = ("convict", "guilty", "sentenc")
_ACQUITTED = ("acquit", "discharg", "closed", "cancel", "untrac")

# How co-accused splits: "Manjit Singh; Gurpreet Singh" or comma-separated.
_LIST_SEPARATORS = re.compile(r"\s*[;,|/]\s*|\s+and\s+", re.IGNORECASE)


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
    if kind == "social":
        return _ingest_social(store, rows, doc_id=doc_id, text=text)
    if kind == "history":
        return _ingest_history(store, rows, doc_id=doc_id, text=text)
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
            attrs: dict | None = None, label: str | None = None) -> str | None:
    """`label` differs from `value` only where the id has to carry more than a
    human should read: a social handle is namespaced by platform so Instagram's
    `@ravi_k` and X's `@ravi_k` stay two accounts, but nobody wants to see
    `instagram:@ravi_k` in a citation."""
    try:
        node_id = make_id(node_type, value)
    except SchemaError:
        return None
    shown = (label or str(value)).strip()
    store.upsert_node(Node(
        id=node_id, type=node_type, label=shown,
        attrs={"aliases": [shown]} | (attrs or {}),
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


# ------------------------------------------------- social media intelligence

# A DM is a message and reads like one. A public reply is still contact, but
# weaker — anyone can reply to anyone. A mention or a follow is a tie, not a
# conversation, so it carries a low weight and says which it is in `basis`.
# `weight` is how strong the tie is; `confidence` is how sure we are it is real.
# An export records all four with the same certainty, so confidence barely
# moves and weight does the work.
SOCIAL_INTERACTIONS = {
    "dm":      ("MESSAGED",  1.0, 0.90, "social_dm"),
    "message": ("MESSAGED",  1.0, 0.90, "social_dm"),
    "chat":    ("MESSAGED",  1.0, 0.90, "social_dm"),
    "reply":   ("MESSAGED",  0.6, 0.85, "social_reply"),
    "comment": ("MESSAGED",  0.6, 0.85, "social_reply"),
    "mention": ("CO_OCCURS", 0.3, 0.80, "social_mention"),
    "tag":     ("CO_OCCURS", 0.3, 0.80, "social_mention"),
    "post":    ("CO_OCCURS", 0.3, 0.80, "social_mention"),
    "follow":  ("CO_OCCURS", 0.2, 0.85, "social_follow"),
    "friend":  ("CO_OCCURS", 0.2, 0.85, "social_follow"),
    "connect": ("CO_OCCURS", 0.2, 0.85, "social_follow"),
}
_SOCIAL_DEFAULT = ("CO_OCCURS", 0.2, 0.5, "social_unspecified")

# A display name is whatever the account holder typed into a box. It is a lead,
# not an identification, and the OWNS edge it produces says so — lower than the
# 0.6 that text proximity earns in an FIR, because an FIR was written by an
# officer and a profile name was not.
SOCIAL_OWNS_CONFIDENCE = 0.45


def _handle_node(store: CaseStore, raw: str, platform: str, source: dict,
                 extra: dict | None = None) -> str | None:
    """`@ravi_k` on Instagram and `@ravi_k` on X are two accounts.

    The id is namespaced by platform for that reason; the label is not, because
    the platform is in `attrs` and a citation should read `@ravi_k`. Where the
    file never says which platform it is, everything lands under `social`,
    which is honest — one namespace we cannot split, rather than a distinction
    we invented.
    """
    handle = str(raw).strip().lstrip("@")
    if not handle:
        return None
    return _ensure(
        store, "account", f"{platform}:{handle}", source,
        {"kind": "social_handle", "platform": platform, "handle": handle} | (extra or {}),
        label=f"@{handle}",
    )


def _ingest_social(store: CaseStore, rows: list[dict], *, doc_id: str, text: str) -> dict:
    warnings: list[str] = []
    if rows and not _pick(rows[0], SOCIAL_COLUMNS["handle"]):
        warnings.append(
            f"{doc_id}: no handle/username column found in {sorted(rows[0])}; "
            f"expected one of {SOCIAL_COLUMNS['handle']}"
        )
        return {"warnings": warnings}

    linked = 0
    for i, row in enumerate(rows):
        span = _row_span(text, i)
        source = {"doc_id": doc_id} | {k: v for k, v in span.items() if k in ("start", "end")}

        raw_handle = _pick(row, SOCIAL_COLUMNS["handle"])
        if not raw_handle:
            continue
        platform = _slugish(_pick(row, SOCIAL_COLUMNS["platform"]) or "social")
        ts = parse_ts(_pick(row, SOCIAL_COLUMNS["ts"]))
        url = _pick(row, SOCIAL_COLUMNS["url"])

        a_id = _handle_node(store, raw_handle, platform, source,
                            {"profile_url": url} if url else None)
        if not a_id:
            continue

        # The display name is the only bridge from a handle to a person, and it
        # is a weak one. Without it the handle stays an actor of its own, which
        # is the correct read of an unattributed account.
        display = _pick(row, SOCIAL_COLUMNS["display"])
        if display:
            person_id = _ensure(store, "person", display, source)
            if person_id:
                store.upsert_edge(Edge(
                    src=person_id, dst=a_id, type="OWNS",
                    attrs={"basis": "social_profile", "platform": platform,
                           "display_name": display},
                    weight=1.0, confidence=SOCIAL_OWNS_CONFIDENCE, sources=[source],
                ))

        place = _pick(row, SOCIAL_COLUMNS["location"])
        if place:
            place_id = _ensure(store, "location", place, source, {"kind": "social_geotag"})
            if place_id:
                store.upsert_edge(Edge(
                    src=a_id, dst=place_id, type="LOCATED_AT",
                    attrs={"ts": ts, "basis": "social_geotag"},
                    weight=1.0, confidence=0.7, sources=[source],
                ))

        # One row can name several counterparties: a post mentions three people.
        raw_target = _pick(row, SOCIAL_COLUMNS["target"])
        if not raw_target:
            continue
        interaction = (_pick(row, SOCIAL_COLUMNS["interaction"]) or "").strip().lower()
        edge_type, weight, confidence, basis = _social_kind(interaction)
        body = _pick(row, SOCIAL_COLUMNS["text"])

        for target in _split_list(raw_target):
            b_id = _handle_node(store, target, platform, source)
            if not b_id or b_id == a_id:
                continue
            src, dst = (a_id, b_id)
            if edge_type == "CO_OCCURS":
                src, dst = sorted((a_id, b_id))   # undirected fact, stable key
            store.upsert_edge(Edge(
                src=src, dst=dst, type=edge_type,
                attrs={"ts": ts, "basis": basis, "platform": platform,
                       "interaction": interaction or None, "url": url,
                       "excerpt": (body[:200] if body else None)},
                weight=weight, confidence=confidence, sources=[source],
            ))
            linked += 1

    if rows and not linked:
        warnings.append(
            f"{doc_id}: {len(rows)} social rows were read and every handle in them was "
            "recorded, but no row named a second account, so no relationship could be "
            f"built. Expected one of {SOCIAL_COLUMNS['target']}."
        )
    return {"warnings": warnings}


def _social_kind(interaction: str) -> tuple[str, float, float, str]:
    for key, spec in SOCIAL_INTERACTIONS.items():
        if key in interaction:
            return spec
    return _SOCIAL_DEFAULT


# ------------------------------------------------ criminal history databases

# Being charged in the same case is a far stronger tie than being named in the
# same paragraph (pipeline's CO_OCCURS is weight 0.3), and it is recorded by a
# court rather than inferred by us — so it is weighted like a call and only
# discounted for the one thing that is genuinely uncertain: whether two people
# with the same written name are the same person. §5.1 has no fuzzy matching,
# which is exactly why this is 0.85 and not 0.95.
CO_ACCUSED_CONFIDENCE = 0.85


def _ingest_history(store: CaseStore, rows: list[dict], *, doc_id: str, text: str) -> dict:
    warnings: list[str] = []
    if rows and not (_pick(rows[0], HISTORY_COLUMNS["person"])
                     and _pick(rows[0], HISTORY_COLUMNS["case_no"])):
        warnings.append(
            f"{doc_id}: a criminal history file needs a person column and a case-number "
            f"column; found {sorted(rows[0])}. Expected one of "
            f"{HISTORY_COLUMNS['person']} and one of {HISTORY_COLUMNS['case_no']}."
        )
        return {"warnings": warnings}

    for i, row in enumerate(rows):
        span = _row_span(text, i)
        source = {"doc_id": doc_id} | {k: v for k, v in span.items() if k in ("start", "end")}

        person = _pick(row, HISTORY_COLUMNS["person"])
        case_no = _pick(row, HISTORY_COLUMNS["case_no"])
        if not person or not case_no:
            continue

        person_id = _ensure(store, "person", person, source)
        # The case number alone is the id, deliberately. `patterns.py` pulls
        # `FIR 88/2019` out of prose as `event:88_2019`, and a prior case named
        # in a surveillance note has to be the same node as the same case in
        # this database or the whole point is lost. Namespacing by station
        # would be safer against two stations sharing a number, and it would
        # break that merge — which is the more valuable of the two.
        status = (_pick(row, HISTORY_COLUMNS["status"]) or "").strip()
        ts = parse_ts(_pick(row, HISTORY_COLUMNS["ts"]))
        offence = _pick(row, HISTORY_COLUMNS["offence"])
        station = _pick(row, HISTORY_COLUMNS["station"])
        case_id = _ensure(
            store, "event", case_no, source,
            {"kind": "prior_case", "offence": offence, "status": status or None,
             "disposition": _disposition(status), "station": station,
             "court": _pick(row, HISTORY_COLUMNS["court"]), "ts": ts},
            label=f"Case {case_no}" if case_no[:1].isdigit() else case_no,
        )
        if not person_id or not case_id:
            continue

        store.upsert_edge(Edge(
            src=person_id, dst=case_id, type="MENTIONED_IN",
            attrs={"basis": "criminal_history", "role": _pick(row, HISTORY_COLUMNS["role"]),
                   "offence": offence, "status": status or None,
                   "disposition": _disposition(status), "ts": ts},
            weight=1.0, confidence=0.95, sources=[source],
        ))

        if station:
            station_id = _ensure(store, "location", station, source,
                                 {"kind": "police_station"})
            if station_id:
                store.upsert_edge(Edge(
                    src=case_id, dst=station_id, type="LOCATED_AT",
                    attrs={"basis": "case_jurisdiction", "ts": ts},
                    weight=1.0, confidence=0.95, sources=[source],
                ))

        # The edge this source exists for. Two names on one charge sheet is the
        # hidden relationship §1.1 asks for, and it survives even where neither
        # person appears in any other document in the case.
        for other in _split_list(_pick(row, HISTORY_COLUMNS["co_accused"]) or ""):
            other_id = _ensure(store, "person", other, source)
            if not other_id or other_id == person_id:
                continue
            store.upsert_edge(Edge(
                src=other_id, dst=case_id, type="MENTIONED_IN",
                attrs={"basis": "criminal_history", "role": "co-accused",
                       "offence": offence, "status": status or None,
                       "disposition": _disposition(status), "ts": ts},
                weight=1.0, confidence=0.95, sources=[source],
            ))
            src, dst = sorted((person_id, other_id))
            store.upsert_edge(Edge(
                src=src, dst=dst, type="CO_OCCURS",
                attrs={"basis": "co_accused", "case": case_id, "offence": offence,
                       "status": status or None, "ts": ts},
                weight=1.0, confidence=CO_ACCUSED_CONFIDENCE, sources=[source],
            ))
    return {"warnings": warnings}


def _disposition(status: str) -> str | None:
    """`convicted` / `acquitted` / `pending` out of whatever the register wrote.

    Unrecognised is None, never `pending` — telling an officer a case is open
    when the column said something we did not understand is the kind of
    confident wrong answer this system exists not to give.
    """
    low = (status or "").strip().lower()
    if not low:
        return None
    if any(token in low for token in _CONVICTED):
        return "convicted"
    if any(token in low for token in _ACQUITTED):
        return "acquitted"
    if any(token in low for token in ("pend", "trial", "investigat", "open", "chargesheet")):
        return "pending"
    return None


def _split_list(raw: str) -> list[str]:
    return [part.strip() for part in _LIST_SEPARATORS.split(str(raw or "")) if part.strip()]


def _slugish(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_") or "social"
