"""Bytes on disk -> plain text with stable character offsets.

Everything downstream addresses documents by character offset, so this module
has one job: produce *the* text for a document, once, and never produce a
different text for the same bytes. The extracted text is written into the case
directory and is what `read_source_doc` serves — so what a judge clicks through
to is literally what the extractor read.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

TEXT_SUFFIXES = {".txt", ".md", ".log", ".json"}
CSV_SUFFIXES = {".csv", ".tsv"}
PDF_SUFFIXES = {".pdf"}


@dataclass
class ReadResult:
    text: str
    kind: str                                  # fir | cdr | financial | note | other
    sha256: str
    rows: list[dict] = field(default_factory=list)   # populated for CSV
    meta: dict = field(default_factory=dict)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def read_document(path: Path, *, kind: str | None = None) -> ReadResult:
    suffix = path.suffix.lower()
    digest = sha256_file(path)

    if suffix in PDF_SUFFIXES:
        return ReadResult(text=_read_pdf(path), kind=kind or "fir", sha256=digest)

    if suffix in CSV_SUFFIXES:
        rows, text = _read_csv(path)
        return ReadResult(
            text=text, kind=kind or _classify_csv(rows), sha256=digest,
            rows=rows, meta={"columns": list(rows[0]) if rows else []},
        )

    if suffix in TEXT_SUFFIXES or suffix == "":
        text = path.read_text(encoding="utf-8", errors="replace")
        return ReadResult(text=text, kind=kind or _classify_text(text), sha256=digest)

    raise ValueError(
        f"unsupported file type {suffix!r}. Supported: "
        f"{sorted(PDF_SUFFIXES | CSV_SUFFIXES | TEXT_SUFFIXES)}"
    )


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pypdf is required to ingest PDFs: pip install pypdf") from exc

    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        # The marker is part of the text, so offsets stay valid and a citation
        # can be reported as "page N" without a second pass over the file.
        pages.append(f"[page {i}]\n{page.extract_text() or ''}")
    return "\n\n".join(pages)


def _read_csv(path: Path) -> tuple[list[dict], str]:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    rows = [
        {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        for row in csv.DictReader(io.StringIO(raw), delimiter=delimiter)
    ]
    # The raw file *is* the text: offsets into it are real, so a CDR row can be
    # cited the same way a sentence in an FIR can.
    return rows, raw


_CDR_HINTS = {"caller", "callee", "a_party", "b_party", "duration", "imei", "cell_id", "tower"}
_FIN_HINTS = {"amount", "debit", "credit", "beneficiary", "remitter", "ifsc", "txn_id"}


def _classify_csv(rows: list[dict]) -> str:
    cols = {c.lower().replace(" ", "_") for c in (rows[0] if rows else {})}
    if cols & _CDR_HINTS:
        return "cdr"
    if cols & _FIN_HINTS:
        return "financial"
    return "other"


def _classify_text(text: str) -> str:
    head = text[:2000].lower()
    if re.search(r"\bf\.?i\.?r\.?\b|first information report|police station", head):
        return "fir"
    if "surveillance" in head or "observation report" in head:
        return "surveillance"
    return "note"
