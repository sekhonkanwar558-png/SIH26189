"""Hash-chained chain of custody — README §3.6, contract §5.4.

Append-only, one JSON object per line, one chain per case. Every document
ingested and every inference the system makes gets an entry, hash-linked to the
one before it. Altering any earlier entry breaks every hash after it, which is
the demo in §9.3 and the honest answer to the *Blockchain & Cybersecurity*
theme — no token, no consensus, just the property that actually matters for
evidence: you cannot quietly rewrite history.

    hash = sha256(prev_hash + canonical_json(entry_without_hash))

`canonical_json` is sorted-key, no-space, UTF-8 JSON. It must stay byte-exact
or every chain written by an earlier version fails to verify. Do not "tidy" it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterator

from backend.config import case_dir, now_iso

GENESIS = "0" * 64

ACTIONS = ("ingest", "extract", "infer", "query", "export")


class CustodyError(RuntimeError):
    pass


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def entry_hash(entry: dict, prev_hash: str) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return sha256_hex(prev_hash + canonical_json(body))


class CustodyChain:
    """The per-case audit log. `append()` is the only way to write one."""

    def __init__(self, case_id: str):
        self.case_id = case_id
        self.path: Path = case_dir(case_id) / "custody.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    # ------------------------------------------------------------------ append

    def append(
        self,
        *,
        action: str,
        actor: str,
        ref: str,
        payload: Any = None,
        payload_sha256: str | None = None,
    ) -> dict:
        if action not in ACTIONS:
            raise CustodyError(f"unknown action {action!r}; §5.4 lists {ACTIONS}")
        if payload_sha256 is None:
            payload_sha256 = sha256_hex(canonical_json(payload if payload is not None else {}))

        seq, prev = self._tail()
        entry = {
            "seq": seq + 1,
            "ts": now_iso(),
            "actor": actor,
            "action": action,
            "ref": ref,
            "payload_sha256": payload_sha256,
            "prev_hash": prev,
        }
        entry["hash"] = entry_hash(entry, prev)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(canonical_json(entry) + "\n")
        return entry

    def _tail(self) -> tuple[int, str]:
        last = None
        for last in self.read():  # noqa: B007 — we want the final value
            pass
        return (last["seq"], last["hash"]) if last else (0, GENESIS)

    # ------------------------------------------------------------------- read

    def read(self) -> Iterator[dict]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def entries(self, limit: int | None = None) -> list[dict]:
        rows = list(self.read())
        return rows[-limit:] if limit else rows

    # ----------------------------------------------------------------- verify

    def verify(self) -> dict:
        """Walk the chain. Returns the first break rather than raising, because
        the UI shows this and a broken chain is a *finding*, not a crash."""
        prev = GENESIS
        count = 0
        for i, entry in enumerate(self.read(), start=1):
            count = i
            if entry.get("seq") != i:
                return _broken(i, entry, f"sequence gap: expected {i}, found {entry.get('seq')}")
            if entry.get("prev_hash") != prev:
                return _broken(i, entry, "prev_hash does not match the previous entry's hash")
            if entry.get("hash") != entry_hash(entry, prev):
                return _broken(i, entry, "entry content does not match its hash — it was altered")
            prev = entry["hash"]
        return {"valid": True, "entries": count, "head": prev, "broken_at": None, "reason": None}


def _broken(seq: int, entry: dict, reason: str) -> dict:
    return {
        "valid": False,
        "entries": seq,
        "head": None,
        "broken_at": seq,
        "reason": reason,
        "entry": entry,
    }
