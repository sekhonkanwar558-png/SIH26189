"""Build the SIH 2026 internal-hackathon progress report for PS 26189.

The brief is narrow and every part of it is a hard limit, so the limits are
checked in code rather than eyeballed:

    1. Problem statement name .......... 10-15 words
    2. Abstract ........................ 150-200 words
    3. Work done till 22:00 on the 8th . max 50 words
    4. Work left ....................... max 50 words
    5. Challenges faced ................ at most 2

    Five headings and no others. 2-3 pages. Titled "Progress report <team>".

A section that breaks a limit fails the build. Nothing here is allowed to go out
on the strength of somebody having counted carefully once.

The look is the product's own: near-white ground, one ink, hairline rules, and
Evidence Amber as the only saturated colour -- the same palette as the running
interface, read straight out of frontend/src/index.css. Inter is embedded from
the frontend's own dependency, so the PDF needs no network and no installed font.

    python build_progress_report.py
    pwsh ~/bin/html2pdf.ps1 progress_report.html -Out "Progress report Suishodama.pdf"
"""

from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONT_DIR = HERE.parent / "frontend" / "node_modules" / "@fontsource-variable" / "inter" / "files"
OUT_HTML = HERE / "progress_report.html"

TEAM = "Suishōdama"
TITLE = f"Progress report {TEAM}"

# --------------------------------------------------------------------- content

# 1 -- 10-15 words.
PS_NAME = (
    "AI-Powered Criminal Network Analysis System — entity extraction, "
    "relationship mapping and key-influencer identification"
)

# 2 -- 150-200 words.
ABSTRACT = [
    "An investigating officer already holds the connections he needs. They sit unread "
    "across FIRs, call-detail records, bank statements, surveillance logs, criminal "
    "histories and intelligence reports, and finding them means holding hundreds of "
    "identifiers in his head at once. Suishōdama gives every case an investigator of its own.",

    "Opening a case creates a self-contained file on disk carrying that case's knowledge "
    "graph, analytics, memory and hash-chained chain of custody. Documents are parsed "
    "deterministically, with no model anywhere in the ingest path, into people, phone "
    "numbers, vehicles, accounts, locations and organisations, each traceable to the "
    "character offset it was read from. The analytics layer computes the findings: "
    "person-projected centrality that treats a man and his SIM as one actor, Louvain "
    "community detection, and hidden brokers ranked person against person.",

    "The officer types plain English. The assistant begins every question knowing nothing "
    "and queries the case brain through tools, so the case lives on disk rather than in a "
    "context window. It grows where a window only fills, it outlives the conversation, and "
    "no case can reach another. Every citation is verified against the graph before the "
    "officer sees it.",
]

# 3 -- max 50 words.
WORK_DONE = (
    "Prototype complete and running end to end. All seven source kinds ingest "
    "deterministically; the demo case holds 125 nodes, 1,148 links and 61 custody entries. "
    "Graph, analytics, tool-using assistant, graph view and tamper-evident custody log "
    "all work. 38 tests pass; ingest is linear, 106 KB in 3.8 seconds."
)

# 4 -- max 50 words.
WORK_LEFT = (
    "Recording the demo video and preparing the final presentation for offline evaluation. "
    "On the system itself: rehearsing the six-minute demo against the running prototype, and "
    "widening evaluation beyond the trafficking case. OCR for scanned documents stays "
    "deliberately out of scope, so evidence is never read through a lossy step."
)

# 5 -- at most 2.
CHALLENGES = [
    (
        "Ingest was too slow to survive a real case file.",
        "106 KB of documents took 63 seconds, and the cost was growing with the square of the "
        "input — so a full chargesheet bundle would never have finished at all. The ingest path "
        "was rebuilt to scale linearly. The same 106 KB now takes 3.8 seconds, and eight times "
        "the document costs 7.4 times the time instead of sixty-four.",
    ),
    (
        "The most important man in the network scored near zero.",
        "The problem statement asks the system to identify key influencers, and the measure for "
        "that is how many routes between people run through a person. But a kingpin whose only "
        "recorded link is to his own phone sits at a dead end — every route stops at the handset "
        "— so he ranked near the bottom. A man and his SIM are not two actors. Every phone, "
        "account, device and vehicle with a known holder is now folded into that holder before "
        "anything is scored, while identifiers nobody has attributed stay as themselves. That "
        "single choice is the difference between finding him and not.",
    ),
]

HEADINGS = [
    "Problem statement",
    "Abstract",
    "Work done till 10:00 PM on 8th September",
    "Work left",
    "Challenges faced",
]

# ----------------------------------------------------------------------- guards


def words(text: str) -> int:
    """Count words the way a reader would: an em-dash is punctuation, not a word."""
    cleaned = re.sub(r"[—–]", " ", text)
    return len([w for w in cleaned.split() if re.search(r"[0-9A-Za-zÀ-ſ]", w)])


def check() -> None:
    failures: list[str] = []

    def limit(label: str, n: int, lo: int | None, hi: int | None) -> None:
        if lo is not None and n < lo:
            failures.append(f"{label}: {n} words, minimum {lo}")
        elif hi is not None and n > hi:
            failures.append(f"{label}: {n} words, maximum {hi}")
        else:
            bound = f"{lo}-{hi}" if lo else f"max {hi}"
            print(f"  ok   {label:<40} {n:>3} words  ({bound})")

    limit("1. Problem statement name", words(PS_NAME), 10, 15)
    limit("2. Abstract", sum(words(p) for p in ABSTRACT), 150, 200)
    limit("3. Work done till 22:00 on the 8th", words(WORK_DONE), None, 50)
    limit("4. Work left", words(WORK_LEFT), None, 50)

    if len(CHALLENGES) > 2:
        failures.append(f"5. Challenges faced: {len(CHALLENGES)}, maximum 2")
    else:
        print(f"  ok   {'5. Challenges faced':<40} {len(CHALLENGES):>3} items   (max 2)")

    if len(HEADINGS) != 5:
        failures.append(f"headings: {len(HEADINGS)}, and the brief allows five and no others")

    if failures:
        print("\nFAILED -- the brief is a set of hard limits:", file=sys.stderr)
        for f in failures:
            print(f"  x    {f}", file=sys.stderr)
        sys.exit(1)


# ------------------------------------------------------------------------ fonts

LATIN = ("U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,"
         "U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD")
LATIN_EXT = ("U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,"
             "U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,"
             "U+2113,U+2C60-2C7F,U+A720-A7FF")


def font_face(filename: str, unicode_range: str) -> str:
    path = FONT_DIR / filename
    if not path.exists():
        sys.exit(f"Missing font: {path}\nRun `pnpm install` in frontend/ first.")
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return (
        "@font-face{font-family:'Inter Variable';font-style:normal;"
        "font-display:block;font-weight:100 900;"
        f"src:url(data:font/woff2;base64,{b64}) format('woff2-variations');"
        f"unicode-range:{unicode_range};}}"
    )


# -------------------------------------------------------------------------- CSS

CSS = """
@page{ size:A4; margin:22mm 22mm 20mm; }
*{ box-sizing:border-box; }
html,body{ margin:0; padding:0; background:#ffffff; }
body{
  font-family:'Inter Variable',Inter,ui-sans-serif,system-ui,sans-serif;
  font-synthesis:none; -webkit-font-smoothing:antialiased;
  color:#0d0d0d; font-size:11pt; line-height:1.6;
}
/* A paragraph never splits across pages, but a section may -- otherwise the
   whole of "Challenges faced" is pushed to page 2 and page 1 ends a third empty. */
p{ margin:0 0 .7em; break-inside:avoid; }
p:last-child{ margin-bottom:0; }

h1{ margin:0; font-size:16pt; font-weight:600; line-height:1.3; }
.meta{ margin:4pt 0 0; font-size:10pt; color:#55555f; }
header{ margin-bottom:20pt; }

section{ margin-bottom:16pt; }
section:last-child{ margin-bottom:0; }
/* a heading never sits alone at the foot of a page */
h2{ margin:0 0 5pt; font-size:11pt; font-weight:600; break-after:avoid; }
"""

# ------------------------------------------------------------------------- HTML


def build() -> str:
    abstract = "\n".join(f"    <p>{p}</p>" for p in ABSTRACT)
    challenges = "\n".join(
        f"    <p>{n}. <b>{lead}</b> {body}</p>"
        for n, (lead, body) in enumerate(CHALLENGES, 1)
    )
    fonts = font_face("inter-latin-wght-normal.woff2", LATIN) + font_face(
        "inter-latin-ext-wght-normal.woff2", LATIN_EXT
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{TITLE}</title>
<style>{fonts}{CSS}</style>
</head>
<body>

<header>
  <h1>{TITLE}</h1>
  <p class="meta">Smart India Hackathon 2026 &middot; Internal Hackathon &middot; Problem statement SIH26189</p>
</header>

<section>
  <h2>{HEADINGS[0]}</h2>
  <p>{PS_NAME}</p>
</section>

<section>
  <h2>{HEADINGS[1]}</h2>
{abstract}
</section>

<section>
  <h2>{HEADINGS[2]}</h2>
  <p>{WORK_DONE}</p>
</section>

<section>
  <h2>{HEADINGS[3]}</h2>
  <p>{WORK_LEFT}</p>
</section>

<section>
  <h2>{HEADINGS[4]}</h2>
{challenges}
</section>

</body>
</html>
"""


if __name__ == "__main__":
    print("Checking the brief's limits\n")
    check()
    OUT_HTML.write_text(build(), encoding="utf-8")
    print(f"\nWrote {OUT_HTML.name}  ({OUT_HTML.stat().st_size / 1024:.0f} KB, fonts embedded)")
