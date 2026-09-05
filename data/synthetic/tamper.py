"""Break the custody chain on purpose, then put it back — README §9.3.

The demo has a beat where the chain is tampered with live and the system names
the exact entry that broke. There was no way to *perform* it: the UI has no
tamper control, correctly, and editing a JSONL file by hand on stage is not a
demo. This is that beat, as one command.

    python -m data.synthetic.tamper --case demo-114            # break entry 2
    python -m data.synthetic.tamper --case demo-114 --restore  # put it back

It rewrites one entry's `ref` the way somebody covering their tracks would —
leaving every hash untouched and changing only what the entry *says*, which is
the attack the chain exists to catch. Then `GET /api/cases/{id}/custody`
reports `valid: false` and `broken_at: 2`, and the Custody panel shows it.

**It refuses to run on a case that is not marked synthetic.** This is a tool
that damages evidence, and the only thing standing between it and a real case
file is a check, so the check is not optional and not a flag. A backup is
written beside the chain and `--restore` reads it; the demo case can also just
be regenerated, which is the real safety net.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys

from backend.case import read_meta
from backend.custody.chain import CustodyChain


class NotSynthetic(RuntimeError):
    """Raised rather than returned: refusing must be impossible to ignore."""


def _guard(case_id: str) -> None:
    meta = read_meta(case_id)
    if meta is None:
        raise NotSynthetic(f"no case {case_id!r}")
    if not meta.synthetic:
        raise NotSynthetic(
            f"{case_id!r} is not a synthetic case. This tool damages a custody "
            "chain and will not touch case data that could be real. Run it "
            "against the generated demo case."
        )


def break_chain(case_id: str, entry: int = 2, ref: str = "doc:forged") -> dict:
    """Alter one entry in place. Returns what `verify()` says afterwards."""
    _guard(case_id)
    chain = CustodyChain(case_id)
    backup = chain.path.with_suffix(chain.path.suffix + ".intact")
    if not backup.exists():
        shutil.copy2(chain.path, backup)

    lines = chain.path.read_text(encoding="utf-8").splitlines()
    if not 1 <= entry <= len(lines):
        raise SystemExit(f"entry {entry} is out of range (1..{len(lines)})")

    # Parse and re-serialise rather than string-replacing: an earlier version of
    # the equivalent test replaced a substring that was not on the target line
    # and silently tampered with nothing, which is the worst possible outcome
    # for a demo about detecting tampering.
    row = json.loads(lines[entry - 1])
    row["ref"] = ref
    lines[entry - 1] = json.dumps(row, sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=False)
    chain.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return chain.verify()


def restore(case_id: str) -> dict:
    _guard(case_id)
    chain = CustodyChain(case_id)
    backup = chain.path.with_suffix(chain.path.suffix + ".intact")
    if not backup.exists():
        raise SystemExit("no .intact backup beside the chain — regenerate the case")
    shutil.copy2(backup, chain.path)
    backup.unlink()
    return chain.verify()


def main() -> int:
    ap = argparse.ArgumentParser(description="Break/restore a synthetic case's custody chain (§9.3).")
    ap.add_argument("--case", default="demo-114")
    ap.add_argument("--entry", type=int, default=2, help="1-indexed entry to alter")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()

    try:
        result = restore(args.case) if args.restore else break_chain(args.case, args.entry)
    except NotSynthetic as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2

    if args.restore:
        print(f"restored — chain valid: {result['valid']}")
    else:
        print(f"broken at entry {result.get('broken_at')} — chain valid: {result['valid']}")
        print(f"reason: {result.get('reason', '')}")
        print(f"\nrestore with:  python -m data.synthetic.tamper --case {args.case} --restore")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
