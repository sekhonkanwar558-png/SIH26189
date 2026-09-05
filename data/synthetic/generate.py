"""The demo case — README §9.

The demo *is* the dataset. There is no public FIR/CDR corpus and real crime data
would be a legal problem (D8), so we generate one — with a **known ground truth
we planted**, which is the only reason we can stand in front of a judge and say
"the system found X" rather than "the system produced some output".

**This is one scenario, not the shape of the product.** The engine knows about
identifiers, links, timing and structure — never about a crime type. A fraud
case, a homicide or an extortion ring runs through exactly the same ingest,
graph, analytics and agent; what differs is the `case_type` and `brief` the
officer sets on the case (`backend/case.py`), which is what the agent reasons
in the register of. This scenario is trafficking because the evaluating
department is NCRB Women Safety Division (D7), and for no other reason. Adding
a second scenario means adding a builder below, not touching the engine.

The scenario: a trafficking network moving women from villages around Ludhiana
to a receiving group in Delhi.

WHAT IS PLANTED (§9.1), and where each demo beat comes from:

* **A kingpin named in no FIR.** `Harbhajan Dhillon` exists only as a subscriber
  name inside a CDR export. He never contacts a foot soldier — only the two
  intermediaries. He is the answer to demo query 2, and the only way to reach
  him is betweenness.
* **Two clusters with no direct edge.** Ludhiana side and Delhi side share no
  call, no transfer, no document. Every route between them runs through the
  intermediaries or through one account.
* **A call-volume spike** in the hours before the logged incident of 3 August.
* **A financial trail** crossing the two clusters through a single account —
  which is what makes the `single_point_of_contact` finding fire.
* **A tower co-location** on the night of the incident: Ravi's phone and
  Suneel's phone on the same tower at 22:10. This is demo query 1's path, and
  it is deliberately *proximity, not contact* — the system must say so.
* **Ordinary noise**: family calls, salary credits, unrelated numbers, so the
  structure is not visible by eye in the raw files.

Added 2026-09-05, when the last three of §1.1's seven sources got handlers:

* **A criminal register with two repeat offenders** — Manjit Singh and Suneel
  Kumar, three prior cases each, one conviction each — and shared charge sheets
  that link people the current case never links directly.
* **An unattributed social handle**, `@ldh_travels_official`. Three people on
  the Ludhiana side DM it and no file anywhere gives it a real name. It is the
  social-media shape of the same blind spot the kingpin is.
* **A C3-graded intelligence report** which says an organiser exists above the
  intermediaries and cannot name him. Everything inferred from it enters the
  graph at 70% confidence, and the system names the man anyway — from CDR
  metadata the report never had.

**Nothing added after 2026-09-04 crosses the Ludhiana/Delhi divide.** A
co-accused or social edge between the two clusters would be a second bridge,
and the kingpin's betweenness — the whole of demo query 2 — is earned by being
the only one. `test_no_new_source_re_wires_the_two_clusters` enforces it, so
whoever adds the next row finds out here rather than on stage.

Run it:  python -m data.synthetic.generate --case demo-114
Re-runs are safe: node ids and edge keys are stable, so ingesting twice merges.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from backend.case import create_case
from backend.config import IST, REPO_ROOT, case_dir
from backend.custody.chain import CustodyChain
from backend.graph.store import CaseStore

OUT = REPO_ROOT / "data" / "synthetic" / "out"
SEED = 26189
INCIDENT = datetime(2026, 8, 3, 22, 10, tzinfo=IST)

# ---------------------------------------------------------------- the network

# Ludhiana side — recruiters and local movers. Named in the FIRs.
CLUSTER_A = {
    "Ravi Kumar":        "9876543210",
    "Manjit Singh":      "9814227731",
    "Sukhwinder Kaur":   "9855610294",
    "Gurpreet Singh":    "9878004512",
}

# Delhi side — receivers and handlers. Named in bank records, barely in FIRs.
CLUSTER_B = {
    "Suneel Kumar":      "9971204418",
    "Parminder Sethi":   "9968112207",
    "Nisha Rani":        "9910447736",
    "Amarjit Chadha":    "9873320016",
}

# The two intermediaries. Each touches exactly one cluster, and the kingpin.
INTERMEDIARIES = {
    "Jaswant Rai":       "9815778820",   # A side
    "Balraj Thind":      "9958201143",   # B side
}

# Named in no FIR, no statement, no surveillance note. Subscriber metadata only.
KINGPIN = {"Harbhajan Dhillon": "9814009977"}

# Ordinary traffic so the structure is not visible by eye.
NOISE = {
    "Kulwant Kaur":      "9814556677",
    "Simran Bedi":       "9876001122",
    "Tarun Gupta":       "9911223344",
    "Harjit Sandhu":     "9855443322",
    "Rekha Devi":        "9968887766",
}

TOWERS_LDH = ["LDH-014", "LDH-022", "LDH-031", "LDH-007"]
TOWERS_DEL = ["DEL-118", "DEL-204", "DEL-091"]

ACCOUNTS = {
    "Ravi Kumar":       "SBIN0004471/34567891234",
    "Manjit Singh":     "PUNB0182100/60122778341",
    # The single account the money crosses through. Held on the Delhi side.
    "Suneel Kumar":     "HDFC0000523/50100244178",
    "Nisha Rani":       "ICIC0001129/602701554398",
    "Gill Travels":     "PUNB0182100/60155009821",
}

ALL_PEOPLE = {**CLUSTER_A, **CLUSTER_B, **INTERMEDIARIES, **KINGPIN, **NOISE}


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _imei(rng: random.Random) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(15))


# ------------------------------------------------------------------ CDR file

def build_cdr(rng: random.Random) -> list[dict]:
    rows: list[dict] = []
    handsets = {name: _imei(rng) for name in ALL_PEOPLE}
    # The kingpin swaps SIMs: one handset, two numbers. Planted so the
    # handset_swap anomaly has something real to find.
    second_sim = "9814003311"
    handsets["_kingpin_second"] = handsets["Harbhajan Dhillon"]

    def call(a_name: str, b_name: str, when: datetime, *, tower: str,
             seconds: int | None = None, kind: str = "CALL",
             a_number: str | None = None) -> None:
        rows.append({
            "caller": a_number or ALL_PEOPLE[a_name],
            "callee": ALL_PEOPLE[b_name],
            "timestamp": _ts(when),
            "duration_sec": seconds if seconds is not None else rng.randint(18, 340),
            "call_type": kind,
            "imei": handsets[a_name],
            "cell_id": tower,
            "subscriber": a_name,
        })

    start = INCIDENT - timedelta(days=21)

    # --- ordinary traffic inside each cluster, three weeks of it
    for day in range(21):
        when_base = start + timedelta(days=day)
        for names, towers in ((list(CLUSTER_A), TOWERS_LDH), (list(CLUSTER_B), TOWERS_DEL)):
            for _ in range(rng.randint(3, 6)):
                a, b = rng.sample(names, 2)
                call(a, b, when_base + timedelta(hours=rng.randint(8, 22),
                                                 minutes=rng.randint(0, 59)),
                     tower=rng.choice(towers))

    # --- noise: unrelated numbers talking to the periphery and each other
    for day in range(21):
        for _ in range(rng.randint(4, 7)):
            a = rng.choice(list(NOISE))
            b = rng.choice(list(NOISE) + list(CLUSTER_A)[:2] + list(CLUSTER_B)[:2])
            if a == b:
                continue
            call(a, b, start + timedelta(days=day, hours=rng.randint(7, 23),
                                         minutes=rng.randint(0, 59)),
                 tower=rng.choice(TOWERS_LDH + TOWERS_DEL))

    # --- the structure: each intermediary talks to their own cluster only
    for day in range(21):
        when = start + timedelta(days=day, hours=rng.randint(9, 21))
        call("Jaswant Rai", rng.choice(list(CLUSTER_A)), when, tower=rng.choice(TOWERS_LDH))
        call("Balraj Thind", rng.choice(list(CLUSTER_B)),
             when + timedelta(hours=1), tower=rng.choice(TOWERS_DEL))

    # --- the kingpin: only ever the two intermediaries, never a foot soldier
    for day in range(0, 21, 2):
        when = start + timedelta(days=day, hours=rng.randint(20, 23))
        call("Harbhajan Dhillon", "Jaswant Rai", when, tower="LDH-031", seconds=rng.randint(40, 120))
        call("Harbhajan Dhillon", "Balraj Thind", when + timedelta(minutes=rng.randint(5, 40)),
             tower="LDH-031", seconds=rng.randint(40, 120))
    # the SIM swap: same handset, a second number, last week only
    for day in range(15, 21):
        rows.append({
            "caller": second_sim,
            "callee": ALL_PEOPLE["Balraj Thind"],
            "timestamp": _ts(start + timedelta(days=day, hours=21, minutes=rng.randint(0, 59))),
            "duration_sec": rng.randint(30, 90),
            "call_type": "CALL",
            "imei": handsets["Harbhajan Dhillon"],
            "cell_id": "LDH-031",
            "subscriber": "Harbhajan Dhillon",
        })

    # --- the spike: the six hours before the incident, everyone busy at once
    for offset in range(6, 0, -1):
        when = INCIDENT - timedelta(hours=offset)
        for _ in range(rng.randint(3, 5)):
            a, b = rng.sample(list(CLUSTER_A), 2)
            call(a, b, when + timedelta(minutes=rng.randint(0, 55)), tower="LDH-014",
                 seconds=rng.randint(20, 90))
        call("Jaswant Rai", "Ravi Kumar", when + timedelta(minutes=rng.randint(0, 55)),
             tower="LDH-014")
        call("Harbhajan Dhillon", "Jaswant Rai", when + timedelta(minutes=rng.randint(0, 55)),
             tower="LDH-031")

    # --- the tower co-location: demo query 1. Both phones on LDH-014 at 22:10.
    # Note there is NO call between them. The link is proximity, and the system
    # must say so rather than implying contact.
    call("Ravi Kumar", "Manjit Singh", INCIDENT, tower="LDH-014", seconds=64)
    call("Suneel Kumar", "Parminder Sethi", INCIDENT + timedelta(minutes=2),
         tower="LDH-014", seconds=51)

    # --- after the incident the Ludhiana phones go quiet: went_silent fires
    for day in range(1, 12):
        when = INCIDENT + timedelta(days=day, hours=rng.randint(9, 21))
        a, b = rng.sample(list(CLUSTER_B), 2)
        call(a, b, when, tower=rng.choice(TOWERS_DEL))
        for _ in range(rng.randint(2, 4)):
            a, b = rng.sample(list(NOISE), 2)
            call(a, b, when + timedelta(minutes=rng.randint(0, 300)),
                 tower=rng.choice(TOWERS_LDH))

    rows.sort(key=lambda r: r["timestamp"])
    return rows


# ------------------------------------------------------------ financial file

def build_financial(rng: random.Random) -> list[dict]:
    rows: list[dict] = []

    def txn(src_name: str, dst_name: str, when: datetime, amount: int, mode: str = "IMPS") -> None:
        src_ifsc, src_acct = ACCOUNTS[src_name].split("/")
        dst_ifsc, dst_acct = ACCOUNTS[dst_name].split("/")
        rows.append({
            "txn_date": _ts(when),
            "from_account": src_acct,
            "remitter_name": src_name,
            "to_account": dst_acct,
            "beneficiary_name": dst_name,
            "beneficiary_ifsc": dst_ifsc,
            "amount": amount,
            "mode": mode,
            "txn_id": f"UTR{rng.randint(10**9, 10**10 - 1)}",
        })

    start = INCIDENT - timedelta(days=21)

    # ordinary traffic — salary, rent, small transfers, on both sides
    for day in range(0, 21, 2):
        when = start + timedelta(days=day, hours=rng.randint(10, 18))
        txn("Ravi Kumar", "Manjit Singh", when, rng.randint(2000, 9000), "UPI")
        txn("Nisha Rani", "Suneel Kumar", when + timedelta(hours=2),
            rng.randint(1500, 7000), "UPI")

    # the crossing: the ONLY money route between the two clusters, and it runs
    # through Gill Travels into one Delhi account. §9.1's financial trail.
    for day in (4, 9, 14, 19):
        when = start + timedelta(days=day, hours=rng.randint(11, 17))
        txn("Manjit Singh", "Gill Travels", when, rng.randint(40000, 70000), "NEFT")
        txn("Gill Travels", "Suneel Kumar", when + timedelta(hours=rng.randint(2, 8)),
            rng.randint(38000, 68000), "NEFT")

    # the outlier, two days before the incident
    txn("Manjit Singh", "Gill Travels", INCIDENT - timedelta(days=2, hours=4), 480000, "RTGS")
    txn("Gill Travels", "Suneel Kumar", INCIDENT - timedelta(days=1, hours=20), 465000, "RTGS")

    rows.sort(key=lambda r: r["txn_date"])
    return rows


# ---------------------------------------------------------------- FIR texts

def build_firs() -> list[tuple[str, str]]:
    """Three FIRs and a surveillance note. The kingpin is in none of them —
    that is the whole point, so do not add him here."""
    return [
        ("fir_114_001.txt", f"""FIRST INFORMATION REPORT

FIR No: 114/2026
Police Station: Division 3, Ludhiana
District Ludhiana
Date of report: 04/08/2026 at 09:15

On 03/08/2026 at 22:10 hrs, complainant Smt. Rajwinder Kaur, resident of
Village Dhandari, reported that her daughter aged 19 years left the house on
the evening of 03/08/2026 and did not return. The complainant stated that her
daughter had been in contact with one Ravi Kumar (mob. 98765-43210) of the same
village, who had offered her employment at a garment unit in Delhi.

Enquiry revealed that accused Ravi Kumar was seen near Dhandari Kalan railway
station on the night of 03/08/2026 along with one Manjit Singh (mob.
9814227731). A vehicle bearing registration PB 10 AB 1234 was seen at the spot.

Case registered under sections relating to kidnapping and trafficking of a
minor. Investigation taken up by SI Harpreet Kaur.
"""),
        ("fir_114_002.txt", """FIRST INFORMATION REPORT

FIR No: 118/2026
Police Station: Division 3, Ludhiana
Date of report: 11/08/2026 at 16:40

Complainant Shri Balbir Chand of Sector 32 reported that his sister-in-law was
induced to travel to Delhi on 22/07/2026 on the promise of domestic work. The
travel was arranged through Gill Travels, whose office is at Dhandari Kalan.

The complainant stated that payment of Rs 45,000 was made to Gill Travels by
one Manjit Singh. Accused Sukhwinder Kaur (mob. 9855610294) is stated to have
accompanied the victim to the bus stand.

Enquiry is being made from the proprietor of Gill Travels.
"""),
        ("fir_114_003.txt", """FIRST INFORMATION REPORT

FIR No: 121/2026
Police Station: Sarai Rohilla, Delhi
Date of report: 19/08/2026 at 09:41

On 19 August 2026 at 09:41 AM, a rescue was effected at a premises in Delhi
following information received. Two women were recovered.

Statement of one of the recovered persons names one Suneel Kumar as the person
who received them on arrival, and states that a woman known to them as Nisha
arranged their stay. Suneel Kumar is stated to hold an account with HDFC bank
into which payments were credited.

The recovered persons could not identify who had arranged their travel from
Punjab.
"""),
        ("surveillance_note_07.txt", """SURVEILLANCE OBSERVATION REPORT

Observation period: 28/07/2026 to 02/08/2026
Officer: HC Jagtar Singh

Premises of Gill Travels, Dhandari Kalan, kept under observation. Vehicle
PB 10 AB 1234 observed at the premises on 29/07/2026 and again on 01/08/2026.

One Jaswant Rai was observed visiting the premises on 30/07/2026 and remained
for approximately forty minutes. He was not previously known at this office and
was not carrying any documents.

No other persons of interest were observed during the period.
"""),
    ]


# -------------------------------------------------- criminal history file

# Every prior case planted here links people who are ALREADY in the same
# community. That is a deliberate constraint, not a lack of imagination: a
# co-accused edge between the Ludhiana side and the Delhi side would be a
# second bridge across the two clusters, and the kingpin's betweenness — the
# whole of demo query 2 — is earned by being the only one. The register
# deepens what the case already shows; it does not re-wire it.
PRIOR_CASES = [
    # Manjit Singh: the repeat offender on the Ludhiana side, one conviction.
    {"accused_name": "Manjit Singh", "fir_no": "88/2019", "under_section": "IPC 370",
     "fir_date": "14-03-2019", "police_station": "PS Dhandari Kalan",
     "court": "Sessions Court Ludhiana", "disposal": "Convicted",
     "co_accused": "Sukhwinder Kaur", "role": "main accused"},
    {"accused_name": "Manjit Singh", "fir_no": "212/2021", "under_section": "IPC 420",
     "fir_date": "02-09-2021", "police_station": "PS Dhandari Kalan",
     "court": "JMIC Ludhiana", "disposal": "Pending trial", "co_accused": "", "role": ""},
    {"accused_name": "Manjit Singh", "fir_no": "47/2023", "under_section": "IPC 366",
     "fir_date": "21-01-2023", "police_station": "PS Sahnewal",
     "court": "Sessions Court Ludhiana", "disposal": "Acquitted",
     "co_accused": "Gurpreet Singh", "role": "accused"},

    # Suneel Kumar: the same pattern on the Delhi side.
    {"accused_name": "Suneel Kumar", "fir_no": "19/2020", "under_section": "IPC 370",
     "fir_date": "08-02-2020", "police_station": "PS Kapashera",
     "court": "Sessions Court Dwarka", "disposal": "Convicted",
     "co_accused": "Parminder Sethi", "role": "main accused"},
    {"accused_name": "Suneel Kumar", "fir_no": "133/2022", "under_section": "IPC 370/34",
     "fir_date": "17-06-2022", "police_station": "PS Kapashera",
     "court": "Sessions Court Dwarka", "disposal": "Pending trial",
     "co_accused": "Nisha Rani", "role": "accused"},
    {"accused_name": "Suneel Kumar", "fir_no": "08/2024", "under_section": "IPC 363",
     "fir_date": "11-01-2024", "police_station": "PS Dwarka North",
     "court": "JMIC Dwarka", "disposal": "Under investigation", "co_accused": "", "role": ""},

    # Ordinary record, below the repeat-offender threshold — so the finding has
    # something to not fire on.
    {"accused_name": "Ravi Kumar", "fir_no": "301/2022", "under_section": "IPC 279",
     "fir_date": "30-11-2022", "police_station": "PS Dhandari Kalan",
     "court": "JMIC Ludhiana", "disposal": "Acquitted", "co_accused": "", "role": ""},
    {"accused_name": "Nisha Rani", "fir_no": "77/2021", "under_section": "IPC 411",
     "fir_date": "19-05-2021", "police_station": "PS Kapashera",
     "court": "JMIC Dwarka", "disposal": "Acquitted", "co_accused": "", "role": ""},
    {"accused_name": "Gurpreet Singh", "fir_no": "254/2020", "under_section": "IPC 323",
     "fir_date": "07-10-2020", "police_station": "PS Sahnewal",
     "court": "JMIC Ludhiana", "disposal": "Compounded", "co_accused": "", "role": ""},
]


def build_history() -> list[dict]:
    return list(PRIOR_CASES)


# ---------------------------------------------------- social media intel file

# `ldh_travels_official` carries no display name anywhere in this file, and
# three separate people DM it. It is the social-media shape of the same blind
# spot the kingpin is: an actor the network revolves around that no document
# ever attaches to a human being.
SOCIAL_ROWS = [
    ("instagram", "ravi_ldh", "Ravi Kumar", "follow", "manjit_s", 22, "", ""),
    ("instagram", "ravi_ldh", "Ravi Kumar", "follow", "sukhi_k", 22, "", ""),
    ("instagram", "manjit_s", "Manjit Singh", "follow", "gurpreet_gs", 21, "", ""),
    ("instagram", "ravi_ldh", "Ravi Kumar", "dm", "ldh_travels_official", 9,
     "gaddi kal raat tak ready ho jayegi?", ""),
    ("instagram", "manjit_s", "Manjit Singh", "dm", "ldh_travels_official", 8,
     "teen hain, subah nikalna hai", ""),
    ("instagram", "sukhi_k", "Sukhwinder Kaur", "dm", "ldh_travels_official", 6,
     "paisa aa gaya kya", ""),
    ("instagram", "ldh_travels_official", "", "mention", "ravi_ldh; manjit_s", 5,
     "booking confirmed for tomorrow", "Dhandari Kalan, Ludhiana"),
    ("instagram", "gurpreet_gs", "Gurpreet Singh", "reply", "manjit_s", 4,
     "haan bhaji pta hai", ""),

    ("facebook", "suneel_delhi", "Suneel Kumar", "follow", "nisha_r", 20, "", ""),
    ("facebook", "suneel_delhi", "Suneel Kumar", "dm", "parminder_sethi", 7,
     "gaadi pahunch rahi hai raat ko", ""),
    ("facebook", "nisha_r", "Nisha Rani", "reply", "suneel_delhi", 6, "theek hai", ""),
    ("facebook", "parminder_sethi", "Parminder Sethi", "mention", "suneel_delhi", 3,
     "shipment received", "Kapashera, New Delhi"),

    # noise: two ordinary accounts with nothing to do with any of it
    ("instagram", "kulwant_k", "Kulwant Kaur", "follow", "ravi_ldh", 30, "", ""),
    ("instagram", "harleen_photo", "Harleen Kaur", "reply", "kulwant_k", 26,
     "lovely pictures", ""),
]


def build_social() -> list[dict]:
    rows = []
    for platform, handle, display, action, target, days_before, text, place in SOCIAL_ROWS:
        rows.append({
            "platform": platform,
            "handle": handle,
            "display_name": display,
            "interaction": action,
            "to_handle": target,
            "timestamp": _ts(INCIDENT - timedelta(days=days_before)),
            "text": text,
            "url": f"https://{platform}.com/{handle}",
            "location": place,
        })
    return rows


# ------------------------------------------------------ intelligence report

# Graded C3 — "fairly reliable source, possibly true information" — so
# everything inferred from it enters the graph at 70% confidence and the
# officer is told so at upload. It names Jaswant Rai and it deliberately does
# NOT name the kingpin: the report knows there is someone above the
# intermediaries and cannot say who, and the system names him anyway from CDR
# metadata. Adding him here would also break the claim demo query 2 rests on.
INTELLIGENCE_REPORT = """INTELLIGENCE INPUT — LUDHIANA RANGE
Reference: INT/LDH/2026/0431
Date: 28 July 2026
Source grading: C3
Source reliability: C   Information credibility: 3

1. A source in the Dhandari transport trade reports that a small group has been
moving young women out of the villages east of Ludhiana over the past four
months, using private taxis booked late at night rather than buses.

2. The source names Jaswant Rai (mob. 9815778820) as the man who arranges the
vehicles. He is described as taking instructions rather than giving them, and
the source was clear that Rai is not the organiser.

3. The source states that the money does not come from Ludhiana and that Rai is
paid by someone he has never met in person. The source could not name this
person and has not seen him. No description is available.

4. The source also names Manjit Singh, already known to this office, as
recruiting on the village side. This part of the report is uncorroborated.

5. Assessment: the group is small, disciplined about phones, and appears to be
one link in a longer chain. Identification of the organiser should be treated
as the priority requirement.

END OF REPORT
"""

# ------------------------------------------------------------------- writing

def write_files(out_dir: Path, rng: random.Random) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    cdr = build_cdr(rng)
    cdr_path = out_dir / "cdr_ludhiana_delhi.csv"
    with cdr_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(cdr[0]))
        writer.writeheader()
        writer.writerows(cdr)
    written.append(cdr_path)

    fin = build_financial(rng)
    fin_path = out_dir / "bank_statements.csv"
    with fin_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fin[0]))
        writer.writeheader()
        writer.writerows(fin)
    written.append(fin_path)

    for name, body in build_firs():
        path = out_dir / name
        path.write_text(body, encoding="utf-8")
        written.append(path)

    history = build_history()
    history_path = out_dir / "criminal_history.csv"
    with history_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(history[0]))
        writer.writeheader()
        writer.writerows(history)
    written.append(history_path)

    social = build_social()
    social_path = out_dir / "social_media_intel.csv"
    with social_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(social[0]))
        writer.writeheader()
        writer.writerows(social)
    written.append(social_path)

    intel_path = out_dir / "intelligence_input_ldh.txt"
    intel_path.write_text(INTELLIGENCE_REPORT, encoding="utf-8")
    written.append(intel_path)

    ground_truth = {
        "note": "What we planted. The demo proves the system found these without being told.",
        "kingpin": {
            "name": "Harbhajan Dhillon",
            "phone": "9814009977",
            "claim": "Named in no FIR, statement or surveillance note. Reachable only through "
                     "betweenness on CDR metadata. Contacts the two intermediaries and nobody else.",
        },
        "intermediaries": list(INTERMEDIARIES),
        "clusters": {"ludhiana": list(CLUSTER_A), "delhi": list(CLUSTER_B)},
        "financial_crossing": "Manjit Singh -> Gill Travels -> Suneel Kumar, the only money "
                              "route between the two clusters.",
        "tower_colocation": {
            "tower": "LDH-014", "when": INCIDENT.isoformat(),
            "phones": ["9876543210 (Ravi Kumar)", "9971204418 (Suneel Kumar)"],
            "claim": "Proximity, not contact. There is no call between these two numbers.",
        },
        "spike": f"Six hours before {INCIDENT:%d %b %H:%M}, Ludhiana-side call volume rises sharply.",
        "handset_swap": "One IMEI carries 9814009977 and 9814003311 — the kingpin changing SIMs.",
        "repeat_offenders": {
            "Manjit Singh": "3 prior cases, one conviction under IPC 370.",
            "Suneel Kumar": "3 prior cases, one conviction under IPC 370.",
            "claim": "Both are found from the criminal history file alone, and both are "
                     "already central in the current case — the register says the pattern "
                     "is not new.",
        },
        "prior_associations": [
            "Manjit Singh + Sukhwinder Kaur, FIR 88/2019 (convicted).",
            "Suneel Kumar + Parminder Sethi, FIR 19/2020 (convicted).",
        ],
        "unattributed_handle": {
            "handle": "@ldh_travels_official",
            "claim": "Three Ludhiana-side people DM it and no file anywhere gives it a "
                     "real name. The social-media shape of the same blind spot the "
                     "kingpin is.",
        },
        "intelligence_grading": {
            "document": "intelligence_input_ldh.txt",
            "grading": "C3",
            "claim": "Everything inferred from the report enters at 70% confidence, and "
                     "the officer is told so at upload. The report says an organiser "
                     "exists and cannot name him; the system names him from CDR "
                     "metadata anyway.",
        },
        "clusters_not_re_wired": "No co-accused or social edge crosses the Ludhiana/Delhi "
                                 "divide. The kingpin stays the only bridge, which is what "
                                 "demo query 2 rests on.",
    }
    gt_path = out_dir / "GROUND_TRUTH.json"
    gt_path.write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")
    return written


def generate(case_id: str = "demo-114", *, reset: bool = True, ingest: bool = True) -> dict:
    rng = random.Random(SEED)
    files = write_files(OUT, rng)

    if not ingest:
        return {"case_id": case_id, "files": [str(f) for f in files], "ingested": False}

    if reset and case_dir(case_id).exists():
        shutil.rmtree(case_dir(case_id))

    from backend.analytics.metrics import recompute
    from backend.ingest.pipeline import ingest_file

    create_case(
        case_id,
        title="Suspected trafficking network — Ludhiana to Delhi",
        officer="officer:io_114",
        case_type="human trafficking",
        brief=(
            "Missing 19-year-old from Village Dhandari, last seen 3 August 2026. Two more "
            "women recovered in Delhi on 19 August. I think the two ends are the same "
            "operation but I have nothing linking them. I want to know who is running it."
        ),
        synthetic=True,
        exist_ok=True,
    )
    store = CaseStore(case_id)
    chain = CustodyChain(case_id)

    results = []
    for path in files:
        if path.name == "GROUND_TRUTH.json":
            continue
        results.append(ingest_file(store, chain, path, actor="system").as_dict())

    stats = recompute(store)
    store.commit()
    store.close()
    return {"case_id": case_id, "documents": results, "analytics": stats,
            "ground_truth": str(OUT / "GROUND_TRUTH.json")}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the SIH26189 demo case (README §9).")
    parser.add_argument("--case", default="demo-114", help="case id to build into")
    parser.add_argument("--files-only", action="store_true",
                        help="write the CSV/FIR files without ingesting them")
    parser.add_argument("--keep", action="store_true",
                        help="ingest into the existing case instead of rebuilding it")
    args = parser.parse_args()

    result = generate(args.case, reset=not args.keep, ingest=not args.files_only)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
