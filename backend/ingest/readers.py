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
    # fir | surveillance | intelligence | note        (prose)
    # cdr | financial | social | history              (tables)
    # other                                           (read, but unrecognised)
    kind: str
    sha256: str
    rows: list[dict] = field(default_factory=list)   # populated for CSV
    meta: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


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
        text, warnings, pages, blank = _read_pdf(path)
        # Classified from what it says, like every other prose document. This
        # branch used to assume "fir" for anything ending in .pdf, which is
        # wrong for the bank statements and criminal-history printouts §1.1
        # names as sources — and `kind` is what the agent is told it is.
        # A PDF we could not read a word of is "other", not a note: guessing a
        # kind off page markers would put a confident label on a document
        # nobody has seen the inside of.
        read_kind = "other" if blank == pages else _classify_text(text)
        final_kind = kind or read_kind
        factor, grading = confidence_factor(final_kind, text)
        return ReadResult(
            text=text, kind=final_kind, sha256=digest,
            meta={"pages": pages, "pages_without_text": blank,
                  "confidence_factor": factor} | grading,
            warnings=warnings,
        )

    if suffix in CSV_SUFFIXES:
        rows, text = _read_csv(path)
        return ReadResult(
            text=text, kind=kind or _classify_csv(rows), sha256=digest,
            rows=rows, meta={"columns": list(rows[0]) if rows else []},
        )

    if suffix in TEXT_SUFFIXES or suffix == "":
        text = path.read_text(encoding="utf-8", errors="replace")
        final_kind = kind or _classify_text(text)
        factor, grading = confidence_factor(final_kind, text)
        return ReadResult(text=text, kind=final_kind, sha256=digest,
                          meta={"confidence_factor": factor} | grading)

    raise ValueError(
        f"unsupported file type {suffix!r}. Supported: "
        f"{sorted(PDF_SUFFIXES | CSV_SUFFIXES | TEXT_SUFFIXES)}"
    )


# Fewer alphanumeric characters than this on a page and there is nothing on it
# to read — a page number, or specks off a scan. A real page of an FIR runs to
# several hundred.
MIN_PAGE_CHARS = 12


def _read_pdf(path: Path) -> tuple[str, list[str], int, int]:
    """Text, and an honest account of what could not be read.

    A scanned FIR is a photograph of a document: pypdf returns nothing for it,
    and every step after this one then succeeds on an empty string. The
    document registers, the custody chain records it as evidence received, and
    not one entity ever appears — with nothing anywhere saying why. That is the
    worst shape a failure can take in front of an investigator, because it is
    indistinguishable from a document that genuinely had nothing in it.

    So blank pages are counted and reported. *Reading* them is a different
    question — OCR, and whether scans are in scope at all, is undecided (§13).
    Saying they were not read is not, and does not wait on it.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pypdf is required to ingest PDFs: pip install pypdf") from exc

    try:
        reader = PdfReader(str(path))
        pdf_pages = list(reader.pages)
    except Exception as exc:
        # Encrypted, truncated, or not a PDF at all — pypdf raises a different
        # type for each. The officer needs one sentence, and the API turns a
        # ValueError into a readable 415 instead of a stack trace.
        raise ValueError(
            f"this PDF could not be opened ({exc}). If it is password-protected, "
            "remove the password and upload it again."
        ) from exc

    pages: list[str] = []
    blank = 0
    for i, page in enumerate(pdf_pages, start=1):
        try:
            body = page.extract_text() or ""
        except Exception:
            body = ""          # one damaged page must not cost us the other 39
        if sum(c.isalnum() for c in body) < MIN_PAGE_CHARS:
            blank += 1
        # The marker is part of the text, so offsets stay valid and a citation
        # can be reported as "page N" without a second pass over the file.
        pages.append(f"[page {i}]\n{body}")

    total = len(pdf_pages)
    warnings: list[str] = []
    if total and blank == total:
        warnings.append(
            f"No text could be read from this PDF: all {total} "
            f"page{'s' if total > 1 else ''} appear to be scanned images. "
            "Nothing from this document has entered the case. Upload a text "
            "PDF, or paste its contents in as text."
        )
    elif blank:
        warnings.append(
            f"{blank} of {total} pages in this PDF had no readable text and were "
            "skipped: they appear to be scanned images. Everything on the other "
            f"{total - blank} pages has been read."
        )
    return "\n\n".join(pages), warnings, total, blank


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
_HISTORY_HINTS = {"fir_no", "case_no", "crime_no", "offence", "offense", "co_accused",
                  "disposal", "police_station", "ipc_section", "under_section", "prior_case"}
_SOCIAL_HINTS = {"handle", "username", "screen_name", "platform", "followers", "post_id",
                 "in_reply_to", "reply_to", "mentions", "to_handle", "from_handle"}


def _classify_csv(rows: list[dict]) -> str:
    cols = {c.lower().replace(" ", "_") for c in (rows[0] if rows else {})}
    if cols & _CDR_HINTS:
        return "cdr"
    if cols & _FIN_HINTS:
        return "financial"
    # Checked after the two above and not before: a table is a criminal-history
    # or social export because of columns nothing else has, whereas `date` and
    # `name` are in every file anyone has ever exported.
    if cols & _HISTORY_HINTS:
        return "history"
    if cols & _SOCIAL_HINTS:
        return "social"
    return "other"


def _classify_text(text: str) -> str:
    head = text[:2000].lower()
    # Intelligence is tested first because its cues are the specific ones. The
    # FIR test below matches on "police station", which an intelligence report
    # about a police station would trip.
    if re.search(r"intelligence\s+(report|input|summary|assessment|note)|source\s+report"
                 r"|\bint\.?\s+report\b|source\s+reliability|admiralty", head):
        return "intelligence"
    if re.search(r"\bf\.?i\.?r\.?\b|first information report|police station", head):
        return "fir"
    if "surveillance" in head or "observation report" in head:
        return "surveillance"
    return "note"


# ------------------------------------------- intelligence reports are graded

# The Admiralty code (NATO STANAG 2511), which is what an intelligence report
# actually carries: source reliability A-F, information credibility 1-6. It
# maps onto `confidence` in §5.1 almost exactly, which is the whole reason to
# read it — an assessment from an untested source should not enter the graph at
# the same confidence as a bank record, and until now it did.
_RELIABILITY = {"a": 1.0, "b": 0.85, "c": 0.7, "d": 0.45, "e": 0.25, "f": 0.5}
_CREDIBILITY = {"1": 1.0, "2": 0.85, "3": 0.7, "4": 0.45, "5": 0.25, "6": 0.5}

# `F` and `6` both mean "cannot be judged", not "false" — so both sit at the
# neutral 0.5 rather than at the bottom of the scale.

_GRADE_PAIR = re.compile(
    r"\b(?:source\s+)?(?:grading|grade|admiralty|evaluation)\s*[:\-]?\s*([A-Fa-f])\s*([1-6])\b")
_GRADE_RELIABILITY = re.compile(r"\breliability\s*[:\-]?\s*([A-Fa-f])\b", re.IGNORECASE)
_GRADE_CREDIBILITY = re.compile(r"\bcredibility\s*[:\-]?\s*([1-6])\b", re.IGNORECASE)

# An intelligence report that carries no grading at all. Still an assessment
# rather than evidence, so it is discounted — but only to here, because an
# ungraded report is not the same as a badly graded one.
UNGRADED_INTELLIGENCE = 0.7


def read_grading(text: str) -> dict:
    """The source grading a report carries, and what it does to confidence.

    Returns `{}` when there is none. `factor` is the **lower** of the two axes,
    not their product: reliability and credibility are independent judgements
    in the standard, and multiplying them invents a precision the code does not
    have (a B2 is not 0.72 of anything). The conservative reading — an
    assessment is worth its weaker axis — is also the one an analyst would
    recognise.
    """
    head = text[:4000]
    reliability = credibility = None

    pair = _GRADE_PAIR.search(head)
    if pair:
        reliability, credibility = pair.group(1).lower(), pair.group(2)
    else:
        rel = _GRADE_RELIABILITY.search(head)
        cred = _GRADE_CREDIBILITY.search(head)
        reliability = rel.group(1).lower() if rel else None
        credibility = cred.group(1) if cred else None

    if not reliability and not credibility:
        return {}

    scores = [s for s in (_RELIABILITY.get(reliability or ""),
                          _CREDIBILITY.get(credibility or "")) if s is not None]
    if not scores:
        return {}
    return {
        "source_reliability": (reliability or "").upper() or None,
        "information_credibility": credibility,
        "grading": f"{(reliability or '?').upper()}{credibility or '?'}",
        "confidence_factor": round(min(scores), 3),
    }


def confidence_factor(kind: str, text: str) -> tuple[float, dict]:
    """How much to discount what we infer from this document, and why.

    Everything that is not an intelligence report returns 1.0 — an FIR, a CDR
    and a bank statement are records of what happened, and the confidence
    already attached to each edge type is the right number for them.
    """
    if kind != "intelligence":
        return 1.0, {}
    grading = read_grading(text)
    if grading:
        return grading["confidence_factor"], grading
    return UNGRADED_INTELLIGENCE, {"grading": None, "confidence_factor": UNGRADED_INTELLIGENCE}
