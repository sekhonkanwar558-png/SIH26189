"""What must be true for the demo to work — README §10.2.

"A component that has never once run against the demo case is not ready,
however complete it looks." These tests run the whole pipeline against the
generated case and assert the things we planted (§9.1) actually come back out.

Run:  python -m pytest tests -q
"""

from __future__ import annotations

import json
import shutil
import time

import pytest

from backend.agent.tools import CaseContext, find_entity, path_between, read_source_doc
from backend.analytics.metrics import recompute, top_influencers
from backend.case import create_case, list_cases
from backend.config import case_dir
from backend.custody.chain import CustodyChain
from backend.graph.schema import Edge, Node, SourcelessFact, make_id
from backend.graph.store import CaseStore
from backend.ingest.pipeline import ingest_text
from data.synthetic.generate import generate

DEMO = "test-demo-114"


@pytest.fixture(scope="module")
def demo():
    result = generate(DEMO, reset=True, ingest=True)
    store = CaseStore(DEMO)
    yield store, result
    store.close()
    shutil.rmtree(case_dir(DEMO), ignore_errors=True)


# ------------------------------------------------------------------- schema

def test_the_same_number_written_four_ways_is_one_entity():
    ids = {make_id("phone", raw) for raw in
           ("9876543210", "+91 98765-43210", "09876543210", "+91-98765 43210")}
    assert ids == {"phone:919876543210"}


def test_a_fact_with_no_source_is_rejected():
    with pytest.raises(SourcelessFact):
        Node(id="person:x", type="person", label="X", sources=[])
    with pytest.raises(SourcelessFact):
        Edge(src="person:a", dst="person:b", type="CO_OCCURS", sources=[])


# -------------------------------------------------------------------- store

def test_ingesting_the_same_document_twice_does_not_double_the_graph(tmp_path):
    case = "test-idempotent"
    shutil.rmtree(case_dir(case), ignore_errors=True)
    create_case(case, title="idempotency", exist_ok=True)
    store, chain = CaseStore(case), CustodyChain(case)
    text = "complainant Smt. Rajwinder Kaur reported that one Ravi Kumar (mob. 9876543210) fled."

    ingest_text(store, chain, text, filename="a.txt")
    first = store.counts()
    ingest_text(store, chain, text, filename="a.txt")
    second = store.counts()

    assert second["nodes"] == first["nodes"], "re-ingest created duplicate entities"
    store.close()
    shutil.rmtree(case_dir(case), ignore_errors=True)


# ------------------------------------------------------------------ custody

def test_altering_one_entry_breaks_the_chain_from_that_point(demo):
    _, _result = demo
    chain = CustodyChain(DEMO)
    assert chain.verify()["valid"] is True

    backup = chain.path.read_text(encoding="utf-8")
    lines = backup.splitlines()
    assert len(lines) >= 3

    # Rewrite the second entry the way someone covering their tracks would:
    # keep the hashes, change what the entry says. Parsing rather than
    # string-replacing matters — an earlier version of this test replaced a
    # substring that was not on that line and silently tampered with nothing.
    entry = json.loads(lines[1])
    entry["ref"] = "doc:forged"
    lines[1] = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    chain.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        broken = chain.verify()
        assert broken["valid"] is False
        assert broken["broken_at"] == 2
    finally:
        chain.path.write_text(backup, encoding="utf-8")
    assert chain.verify()["valid"] is True


# ---------------------------------------------------------------- isolation

def test_two_cases_of_different_kinds_share_nothing():
    """One officer, several cases, each with its own bot — and no query in the
    system can reach across them, because the other case is a different file."""
    other = "test-fraud-221"
    shutil.rmtree(case_dir(other), ignore_errors=True)
    create_case(other, title="Vendor invoice fraud", officer="officer:io_114",
                case_type="financial fraud",
                brief="Duplicate invoices paid to a shell vendor over eight months.",
                exist_ok=True)
    store, chain = CaseStore(other), CustodyChain(other)
    ingest_text(store, chain,
                "Accused Deepak Mahajan (mob. 9812345678) raised invoices through "
                "Orbit Traders. Payment of Rs 90,000 to A/C No. 91234567890.",
                filename="complaint.txt")
    recompute(store)

    # nothing from the trafficking case leaked in
    assert store.get_node("person:harbhajan_dhillon") is None
    assert store.search_nodes("Ravi Kumar") == []
    assert store.get_node("person:deepak_mahajan") is not None

    # and the engine did its job on a completely different kind of case
    assert store.counts()["nodes"] >= 4

    officer_cases = [c["case_id"] for c in list_cases("officer:io_114")]
    assert other in officer_cases

    store.close()
    shutil.rmtree(case_dir(other), ignore_errors=True)


# -------------------------------------------------------- the planted truth

def test_the_kingpin_is_named_in_no_report_and_the_system_leads_with_him(demo):
    """§9.2 demo query 2 — the moment the room understands what this does."""
    store, _ = demo
    findings = (store.get_analytics("findings") or {})["value"]
    hidden = [f for f in findings if f["kind"] == "hidden_broker"]
    assert hidden, "no hidden_broker finding — the headline demo beat is gone"

    top = hidden[0]
    assert "person:harbhajan_dhillon" in top["node_ids"]
    assert top["severity"] == "high"
    assert findings[0]["kind"] == "hidden_broker", "the bot does not lead with it"

    # and he really is in no report — that is the claim being made on stage
    node = store.get_node("person:harbhajan_dhillon")
    kinds = {(store.document(s["doc_id"]) or {}).get("kind") for s in node.sources}
    assert kinds == {"cdr"}, f"kingpin appears in {kinds}, expected CDR only"


def test_ravi_reaches_the_delhi_account_through_the_tower(demo):
    """§9.2 demo query 1 — and the link is proximity, not contact."""
    store, _ = demo
    ctx = CaseContext(store, CustodyChain(DEMO))
    ravi = find_entity(ctx, "Ravi Kumar", "person")[0]["id"]
    account = find_entity(ctx, "50100244178")[0]["id"]

    paths = path_between(ctx, ravi, account, max_hops=6)
    assert paths, "no path from Ravi to the Delhi account"

    via_tower = [p for p in paths if any(n.startswith("location:ldh") for n in p["path"])]
    assert via_tower, "the tower co-location route is missing"

    # there is deliberately no call between the two numbers — the system must
    # not be able to claim contact
    calls = [e for e in store.edges(node_id="phone:919876543210")
             if e.type == "CALLED" and e.dst == "phone:919971204418"]
    assert calls == [], "the demo's proximity-not-contact property is broken"


def test_a_persons_phone_is_theirs_and_not_the_next_persons(demo):
    """The proximity heuristic must claim the nearest name only — otherwise it
    invents ownership and every path built on it is fiction."""
    store, _ = demo
    owns = [e for e in store.edges(node_id="person:ravi_kumar") if e.type == "OWNS"]
    owned = {e.dst for e in owns}
    assert "phone:919876543210" in owned
    assert "phone:919814227731" not in owned, "Ravi was given Manjit's phone"


def test_the_handset_swap_and_the_spike_are_both_found(demo):
    store, _ = demo
    kinds = {a["kind"] for a in (store.get_analytics("anomalies") or {})["value"]}
    assert "handset_swap" in kinds, "the SIM-swap pattern was not detected"
    assert "volume_spike" in kinds, "the pre-incident call spike was not detected"


def test_influence_is_scored_on_people_not_on_sim_cards(demo):
    store, _ = demo
    ranked = top_influencers(store, "betweenness", limit=8)
    assert ranked, "no influencers computed"
    assert all(r["node_id"].startswith("person:") for r in ranked)
    labels = [r["label"] for r in ranked]
    assert "Harbhajan Dhillon" in labels, "the kingpin does not rank at all"
    assert all(r["why"] for r in ranked), "a score with no explanation is unusable"


def test_every_citation_can_be_opened(demo):
    """A citation that does not click through is not a citation."""
    store, _ = demo
    ctx = CaseContext(store, CustodyChain(DEMO))
    node = store.get_node("person:harbhajan_dhillon")
    source = node.sources[0]
    result = read_source_doc(ctx, source["doc_id"], source.get("start"), source.get("end"))
    assert "error" not in result
    assert result["text"].strip(), "the cited range is empty"


# ------------------------------------------------------------------- speed

def test_a_document_lands_in_the_graph_in_well_under_a_second():
    """D4: no model in the ingest path, so an officer waits seconds, not
    minutes. This is the test that catches anyone adding one."""
    case = "test-speed"
    shutil.rmtree(case_dir(case), ignore_errors=True)
    create_case(case, title="speed", exist_ok=True)
    store, chain = CaseStore(case), CustodyChain(case)
    page = ("FIR No: 300/2026, Police Station Division 3, Ludhiana. On 03/08/2026 at "
            "22:10 hrs complainant Smt. Rajwinder Kaur stated that accused Ravi Kumar "
            "(mob. 9876543210) driving vehicle PB 10 AB 1234 received Rs 50,000 into "
            "A/C No. 34567891234 (IFSC SBIN0004471). ") * 40   # ~40 pages of prose

    start = time.perf_counter()
    ingest_text(store, chain, page, filename="big.txt")
    recompute(store)
    elapsed = time.perf_counter() - start

    assert store.counts()["nodes"] > 0
    assert elapsed < 5.0, f"ingest+analytics took {elapsed:.2f}s — something slow crept in"
    store.close()
    shutil.rmtree(case_dir(case), ignore_errors=True)
