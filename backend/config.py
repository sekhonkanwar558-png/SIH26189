"""Paths, model id and the case-isolation guard.

Every path a case can touch comes from `case_dir()`. Nothing else in the
backend builds a case path by string concatenation — that is what keeps
README §2.4 (case isolation by construction) true rather than aspirational.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:  # optional; the backend runs fine without a .env
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_a, **_k):  # type: ignore[misc]
        return False

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

CASES_ROOT = Path(os.environ.get("SIH_CASES_ROOT") or (REPO_ROOT / "data" / "cases"))

# README §4 D5: Anthropic only. Overridable so a teammate can test on a cheaper
# model without editing code — the id itself carries no date suffix (§0.3).
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

IST = timezone(timedelta(hours=5, minutes=30))

# A case id becomes a directory name. Anything that could escape the cases
# root — separators, dots, drive letters — is rejected rather than sanitised,
# because silently rewriting an id would let two cases collide on one store.
_CASE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{0,63}$")


class BadCaseId(ValueError):
    """Raised when a case id could name something outside the cases root."""


def now_iso() -> str:
    """Current time, IST, ISO-8601 with offset. All timestamps we write use this."""
    return datetime.now(IST).isoformat(timespec="seconds")


def check_case_id(case_id: str) -> str:
    if not isinstance(case_id, str) or not _CASE_ID_RE.match(case_id):
        raise BadCaseId(
            f"invalid case id {case_id!r}: lowercase letters, digits, '_' and '-' only, "
            "1-64 chars, must start alphanumeric"
        )
    return case_id


def case_dir(case_id: str) -> Path:
    """The one function that turns a case id into a path. §5.5 layout."""
    return CASES_ROOT / check_case_id(case_id)


def list_case_ids() -> list[str]:
    if not CASES_ROOT.exists():
        return []
    out = []
    for p in sorted(CASES_ROOT.iterdir()):
        if p.is_dir() and (p / "meta.json").exists():
            try:
                out.append(check_case_id(p.name))
            except BadCaseId:
                continue  # a stray directory is not a case
    return out
