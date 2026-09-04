"""Deterministic identifier extraction — README §3.1.

No model runs here, by decision D4. Phone numbers, IMEIs, account numbers,
IFSC codes, vehicle registrations, UPI handles, FIR numbers and timestamps are
format-regular, and regex extracts them faster, cheaper and *identically every
time* — which is what makes the same document produce the same graph twice.

Every match carries its character offsets. That is not bookkeeping: it is what
makes §3.4's citations click through to the page they came from, and §5.1's
"no fact without provenance" rule enforceable.

Patterns are tried in the order below and a match that overlaps an
already-claimed span is dropped. Order therefore encodes specificity: a
15-digit IMEI must be claimed before anything shorter can nibble at it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from backend.config import IST


@dataclass(frozen=True)
class Extraction:
    node_type: str        # a §5.1 node type
    value: str            # what gets normalised into the node id
    label: str            # what a human reads
    start: int            # character offsets into the extracted text
    end: int
    kind: str             # which pattern fired, for the audit trail
    attrs: dict | None = None


# (kind, node_type, compiled pattern, group index for the value)
# Ordered most-specific first; overlaps with an earlier claim are dropped.
_PATTERNS: list[tuple[str, str, re.Pattern, int]] = [
    ("ifsc", "organization",
     re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"), 0),

    ("imei", "device",
     re.compile(r"(?<![\d\-])(?:IMEI\s*(?:No\.?|Number)?\s*[:\-]?\s*)?(\d{15})(?![\d\-])",
                re.IGNORECASE), 1),

    ("account", "account",
     re.compile(r"\b(?:A/?C|Acc(?:oun)?t|Ac)\s*(?:No\.?|Number|#)?\s*[:\-]?\s*"
                r"([A-Z]{0,4}[\dX]{9,18})\b", re.IGNORECASE), 1),

    ("upi", "account",
     re.compile(r"\b[\w.\-]{3,}@(?:ok[a-z]+|paytm|ybl|upi|apl|ibl|axl|jio)\b",
                re.IGNORECASE), 0),

    ("vehicle", "vehicle",
     re.compile(r"\b([A-Z]{2}[\s\-]?\d{1,2}[\s\-]?[A-Z]{1,3}[\s\-]?\d{4})\b"), 1),

    ("fir", "event",
     re.compile(r"\bF\.?I\.?R\.?\s*(?:No\.?|Number)?\s*[:\-]?\s*(\d{1,5}\s*/\s*\d{2,4})",
                re.IGNORECASE), 1),

    # Reports write mobiles as 9876543210, 98765-43210, +91 98765 43210 and
    # 09876543210. One optional separator after the fifth digit covers all four
    # without letting the pattern wander across unrelated numbers.
    ("phone", "phone",
     re.compile(r"(?<![\d@.\-])(?:\+?91[\s\-]?|0)?[6-9]\d{4}[\s\-]?\d{5}(?![\d\-])"), 0),

    ("email", "account",
     re.compile(r"\b[\w.\-]+@[\w\-]+\.[a-z]{2,}\b", re.IGNORECASE), 0),
]

_MONTHS = ("jan feb mar apr may jun jul aug sep oct nov dec").split()

_DATE_RE = re.compile(
    r"""(?P<full>
        (?:
            (?P<iso>\d{4}-\d{2}-\d{2})
          | (?P<dmy>\b\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b)
          | (?P<dmon>\b\d{1,2}\s+(?:%s)[a-z]*\.?,?\s+\d{4}\b)
        )
        (?:\s*(?:at|,|\bhrs\b)?\s*
            (?P<time>\d{1,2}[:.]\d{2}(?::\d{2})?\s*(?:[AaPp]\.?[Mm]\.?)?)
        )?
    )""" % "|".join(_MONTHS),
    re.VERBOSE | re.IGNORECASE,
)


def extract_identifiers(text: str) -> list[Extraction]:
    """Every format-regular identifier in `text`, with offsets, no overlaps."""
    claimed: list[tuple[int, int]] = []
    out: list[Extraction] = []

    def overlaps(a: int, b: int) -> bool:
        return any(a < end and b > start for start, end in claimed)

    for kind, node_type, pattern, group in _PATTERNS:
        for m in pattern.finditer(text):
            start, end = m.span()
            if overlaps(start, end):
                continue
            raw = (m.group(group) or "").strip()
            if not raw:
                continue
            if kind == "email" and "@" in raw and raw.split("@")[-1].count(".") == 0:
                continue
            claimed.append((start, end))
            out.append(Extraction(
                node_type=node_type, value=raw, label=raw,
                start=start, end=end, kind=kind,
                attrs={"identifier_kind": kind},
            ))
    out.sort(key=lambda e: e.start)
    return out


def extract_datetimes(text: str) -> list[tuple[int, int, str]]:
    """(start, end, ISO-8601 IST) for every date, optionally with a time.

    Timestamps do not become nodes — that would flood the graph with noise.
    They set `first_seen` / `last_seen` on the entities near them and give the
    document a time window, which is what `timeline` and `anomalies` use.
    """
    found: list[tuple[int, int, str]] = []
    for m in _DATE_RE.finditer(text):
        iso = _to_iso(m)
        if iso:
            found.append((m.start(), m.end(), iso))
    return found


def _to_iso(m: re.Match) -> str | None:
    hour = minute = second = 0
    if m.group("time"):
        t = m.group("time").strip().lower().replace(".", ":")
        pm = "pm" in t
        am = "am" in t
        t = re.sub(r"[^\d:]", "", t)
        bits = [int(x) for x in t.split(":") if x]
        if not bits:
            return None
        hour = bits[0]
        minute = bits[1] if len(bits) > 1 else 0
        second = bits[2] if len(bits) > 2 else 0
        if pm and hour < 12:
            hour += 12
        if am and hour == 12:
            hour = 0

    try:
        if m.group("iso"):
            y, mo, d = (int(x) for x in m.group("iso").split("-"))
        elif m.group("dmy"):
            d, mo, y = (int(x) for x in re.split(r"[/\-.]", m.group("dmy")))
            if y < 100:
                y += 2000
            if mo > 12:            # written MM/DD by an American-defaulting tool
                d, mo = mo, d
        else:
            parts = re.split(r"[\s,]+", m.group("dmon").strip())
            d = int(parts[0])
            mo = _MONTHS.index(parts[1][:3].lower()) + 1
            y = int(parts[-1])
        return datetime(y, mo, d, hour, minute, second, tzinfo=IST).isoformat(timespec="seconds")
    except (ValueError, IndexError):
        return None
