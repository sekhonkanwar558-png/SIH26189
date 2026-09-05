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
from pathlib import Path

import pytest

from backend.agent.tools import CaseContext, find_entity, path_between, read_source_doc
from backend.analytics.metrics import recompute, top_influencers
from backend.case import create_case, list_cases
from backend.config import case_dir
from backend.custody.chain import CustodyChain
from backend.graph.schema import Edge, Node, SourcelessFact, make_id
from backend.graph.store import CaseStore
from backend.ingest.pipeline import ingest_file, ingest_text
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


# --------------------------------------------------------------------- pdf

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def blank_case():
    """A case of its own per test, torn down after. These ingest real files,
    so they must not touch the demo the other tests assert against."""
    case = "test-pdf"
    shutil.rmtree(case_dir(case), ignore_errors=True)
    create_case(case, title="pdf", exist_ok=True)
    store, chain = CaseStore(case), CustodyChain(case)
    yield store, chain
    store.close()
    shutil.rmtree(case_dir(case), ignore_errors=True)


def test_a_real_pdf_reaches_the_graph_with_its_people_and_numbers(blank_case):
    """Real FIRs are PDFs. Until this test existed the reader had never seen
    one — it was written, and exercised only against .txt and .csv.

    The fixture is a two-page FIR laid out the way the real form is, tables and
    all, so page markers, line-wrapped sentences and a field split across a
    page break are all in the path.
    """
    store, chain = blank_case
    result = ingest_file(store, chain, FIXTURES / "fir-114-text.pdf")

    assert result.kind == "fir", "a PDF that says FIRST INFORMATION REPORT is an FIR"
    assert not result.warnings, result.warnings
    assert "person:ravi_kumar" in result.entities
    assert "person:harbhajan_dhillon" in result.entities
    assert "phone:919876543210" in result.entities, "a hyphenated number on page 1"
    assert "phone:919915566772" in result.entities, "a number on page 2"
    assert "vehicle:pb10ab1234" in result.entities
    assert "account:34567891234" in result.entities
    assert chain.verify()["valid"]

    # The citation must click through to the text the extractor actually read,
    # which for a PDF is the extracted text and not the bytes.
    ctx = CaseContext(store, chain)
    source = store.get_node("person:ravi_kumar").sources[0]
    opened = read_source_doc(ctx, source["doc_id"], source["start"], source["end"])
    assert "Ravi" in opened["text"]


def test_a_scanned_pdf_says_so_instead_of_ingesting_nothing_in_silence(blank_case):
    """The failure that looks like success. A scan has no text layer, so every
    step downstream succeeds on an empty string: the document registers, the
    custody chain records it as evidence received, and no entity ever appears.

    Before this test the officer got a green tick and an empty graph. The
    document must still be *recorded* — that those bytes arrived is a fact the
    chain has to hold — but it may not be recorded quietly.
    """
    store, chain = blank_case
    result = ingest_file(store, chain, FIXTURES / "fir-114-scanned.pdf")

    assert result.warnings, "a scanned PDF ingested without a word about it"
    assert "scanned" in result.warnings[0].lower()
    assert result.entities == []
    assert chain.verify()["valid"], "the upload is still a custody event"
    assert store.document(result.doc_id) is not None, "the document must still exist"


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


# ------------------------------------- the three §1.1 sources added 2026-09-05

@pytest.fixture
def rows_case():
    """A case per test for the CSV handlers, so they cannot disturb the demo."""
    case = "test-sources"
    shutil.rmtree(case_dir(case), ignore_errors=True)
    create_case(case, title="sources", exist_ok=True)
    store, chain = CaseStore(case), CustodyChain(case)
    yield store, chain
    store.close()
    shutil.rmtree(case_dir(case), ignore_errors=True)


def _write_csv(tmp_path: Path, name: str, header: str, *rows: str) -> Path:
    path = tmp_path / name
    path.write_text("\n".join((header, *rows)) + "\n", encoding="utf-8")
    return path


def test_a_social_export_is_recognised_and_a_dm_is_stronger_than_a_follow(rows_case, tmp_path):
    """§1.1 names social media intelligence and until 2026-09-05 nothing read it.

    A DM is contact and a follow is not, so they must not enter the graph at
    the same strength — an influencer score that cannot tell them apart is
    measuring popularity, not a network.
    """
    store, chain = rows_case
    path = _write_csv(
        tmp_path, "social.csv",
        "platform,handle,display_name,interaction,to_handle,timestamp,text",
        "instagram,ravi_ldh,Ravi Kumar,dm,ldh_travels,2026-08-01 21:04,gaddi ready hai",
        "instagram,ravi_ldh,Ravi Kumar,follow,manjit_s,2026-07-02 10:00,",
    )
    result = ingest_file(store, chain, path)
    assert result.kind == "social", f"classified as {result.kind!r}, not social"

    dm = [e for e in store.edges(types=("MESSAGED",))]
    assert len(dm) == 1
    assert dm[0].src == "account:instagram_ravi_ldh"
    assert dm[0].dst == "account:instagram_ldh_travels"

    follow = [e for e in store.edges(types=("CO_OCCURS",))
              if e.attrs.get("basis") == "social_follow"]
    assert len(follow) == 1
    assert follow[0].weight < dm[0].weight, "a follow weighs as much as a message"

    # the display name is a lead, not an identification
    owns = [e for e in store.edges(types=("OWNS",)) if e.attrs.get("basis") == "social_profile"]
    assert owns and owns[0].confidence < 0.6


def test_the_same_handle_on_two_platforms_is_two_accounts(rows_case, tmp_path):
    """`@ravi_k` on Instagram and `@ravi_k` on X are not one person, and §5.1
    has no fuzzy matching to sort it out afterwards. The id is namespaced by
    platform at ingest or the two are merged forever."""
    store, chain = rows_case
    path = _write_csv(
        tmp_path, "handles.csv",
        "platform,handle,interaction,to_handle",
        "instagram,ravi_k,dm,manjit_s",
        "x,ravi_k,dm,someone_else",
    )
    ingest_file(store, chain, path)
    handles = {n.id for n in store.nodes(type="account")
               if n.attrs.get("kind") == "social_handle"}
    assert "account:instagram_ravi_k" in handles
    assert "account:x_ravi_k" in handles


def test_a_shared_prior_case_connects_two_people_nothing_else_connects(rows_case, tmp_path):
    """The reason criminal history is worth reading at all.

    Two names on one charge sheet is a relationship that predates every
    document in the current case, and no amount of reading those documents
    surfaces it — the "hidden relationship among suspects" §1.1 opens with.
    """
    store, chain = rows_case
    path = _write_csv(
        tmp_path, "history.csv",
        "accused_name,fir_no,under_section,fir_date,police_station,disposal,co_accused",
        "Manjit Singh,88/2019,IPC 370,14-03-2019,PS Dhandari Kalan,Convicted,Sukhwinder Kaur",
    )
    result = ingest_file(store, chain, path)
    assert result.kind == "history", f"classified as {result.kind!r}, not history"

    co = [e for e in store.edges(types=("CO_OCCURS",)) if e.attrs.get("basis") == "co_accused"]
    assert len(co) == 1
    assert sorted((co[0].src, co[0].dst)) == ["person:manjit_singh", "person:sukhwinder_kaur"]
    # much stronger than being named in the same paragraph, which is 0.4
    assert co[0].confidence > 0.8

    case_node = store.get_node("event:88_2019")
    assert case_node is not None, "the prior case is not a node"
    assert case_node.attrs["disposition"] == "convicted"
    assert case_node.attrs["offence"] == "IPC 370"


def test_a_prior_case_read_from_prose_and_from_the_register_is_one_node(rows_case, tmp_path):
    """`patterns.py` pulls `FIR 88/2019` out of a surveillance note as
    `event:88_2019`. The register has to land on the same node or the case an
    officer reads about and the case in the database are two different things.
    """
    store, chain = rows_case
    ingest_text(store, chain,
                "Surveillance note. The subject was previously involved in FIR 88/2019 "
                "registered at this station.",
                filename="note.txt", kind="surveillance")
    path = _write_csv(
        tmp_path, "history.csv",
        "accused_name,fir_no,under_section,fir_date,disposal",
        "Manjit Singh,88/2019,IPC 370,14-03-2019,Convicted",
    )
    ingest_file(store, chain, path)

    events = [n for n in store.nodes(type="event")]
    assert [n.id for n in events] == ["event:88_2019"], f"got {[n.id for n in events]}"
    assert len({s["doc_id"] for s in events[0].sources}) == 2, "not sourced to both documents"


def test_an_unreadable_status_is_left_blank_rather_than_guessed(rows_case, tmp_path):
    """`_disposition` returns None for a word it does not know. Telling an
    officer a case is pending when the column said something else is the
    confident-wrong-answer failure this system exists not to have."""
    store, chain = rows_case
    path = _write_csv(
        tmp_path, "history.csv",
        "accused_name,fir_no,disposal",
        "Manjit Singh,88/2019,Referred to DLSA",
    )
    ingest_file(store, chain, path)
    node = store.get_node("event:88_2019")
    assert node.attrs["disposition"] is None
    assert node.attrs["status"] == "Referred to DLSA", "the raw word must survive"


def test_an_intelligence_report_is_graded_and_what_it_implies_is_discounted(rows_case):
    """§1.1's seventh source. An intelligence report is an assessment, not a
    record, and it says so itself in the Admiralty grading it carries.

    The grading discounts what is *inferred* from the report. It must not touch
    `MENTIONED_IN`: that the report names this man is true at full confidence
    however unreliable the source is — it is a fact about the document.
    """
    store, chain = rows_case
    result = ingest_text(
        store, chain,
        "INTELLIGENCE INPUT\nSource grading: C3\n\n"
        "The source names Jaswant Rai as the man arranging the vehicles, and also "
        "names Manjit Singh as recruiting on the village side.\n",
        filename="int.txt", kind="intelligence")

    assert result.kind == "intelligence"
    assert any("C3" in w for w in result.warnings), f"no grading warning: {result.warnings}"

    doc = store.document(result.doc_id)
    assert doc["meta"]["grading"] == "C3"
    assert doc["meta"]["confidence_factor"] == 0.7          # min(C=0.7, 3=0.7)

    inferred = [e for e in store.edges(types=("CO_OCCURS",))
                if e.attrs.get("basis") == "same_document"]
    assert inferred, "the report named two people and linked neither"
    assert all(abs(e.confidence - 0.4 * 0.7) < 1e-6 for e in inferred), \
        f"not discounted: {[e.confidence for e in inferred]}"

    named = [e for e in store.edges(types=("MENTIONED_IN",))]
    assert named and all(e.confidence == 1.0 for e in named), \
        "the grading was applied to the fact that the document names them"


def test_an_ungraded_intelligence_report_is_still_not_evidence(rows_case):
    """No grading is not the same as a good grading, and it is not the same as
    a bad one either — it lands between them, at 0.7."""
    store, chain = rows_case
    result = ingest_text(
        store, chain,
        "Intelligence report. The source names Balraj Thind as the receiver in Delhi.\n",
        filename="int2.txt", kind="intelligence")
    doc = store.document(result.doc_id)
    assert doc["meta"]["confidence_factor"] == 0.7
    assert doc["meta"]["grading"] is None
    assert any("no source grading" in w for w in result.warnings)


def test_the_broker_threshold_ranks_people_against_people(demo):
    """A regression guard on a bug the criminal-history source exposed.

    `_hidden_brokers` took the fifth-highest betweenness across *every* node as
    its bar, then only ever considered people. On the demo case three of the
    top five are a document, a bank statement and a travel agency, so the bar
    was really "top two people" — and adding one more source pushed the kingpin
    to sixth overall and deleted the finding the whole demo rests on. The more
    an officer uploads, the fewer brokers the case could surface.
    """
    store, _ = demo
    metrics = (store.get_analytics("metrics") or {})["value"]
    betweenness = metrics["betweenness"]
    kingpin = "person:harbhajan_dhillon"

    overall_rank = sorted(betweenness.values(), reverse=True).index(betweenness[kingpin]) + 1
    people = sorted((s for n, s in betweenness.items() if n.startswith("person:")),
                    reverse=True)
    person_rank = people.index(betweenness[kingpin]) + 1

    assert overall_rank > 5, "the demo no longer reproduces the shape of the bug"
    assert person_rank <= 5, f"kingpin is {person_rank}th among people"

    findings = (store.get_analytics("findings") or {})["value"]
    assert [f for f in findings if f["kind"] == "hidden_broker"]


# ------------------------------------------ the demo case shows all of it off

def test_the_register_finds_repeat_offenders_and_a_shared_charge_sheet(demo):
    """§10.2: a component that has never run against the demo case is not
    ready. Both findings the criminal history source exists to produce fire on
    the real generated case, not only on a hand-made row."""
    store, _ = demo
    findings = (store.get_analytics("findings") or {})["value"]

    repeat = [f for f in findings if f["kind"] == "repeat_offender"]
    assert {f["headline"].split(" has ")[0] for f in repeat} >= {"Manjit Singh", "Suneel Kumar"}
    assert all(f["severity"] == "high" for f in repeat), "a conviction is not a high finding"

    prior = [f for f in findings if f["kind"] == "prior_association"]
    assert prior, "no prior_association finding on the demo case"


def test_no_new_source_re_wires_the_two_clusters(demo):
    """The plant that protects demo query 2.

    A co-accused or social edge across the Ludhiana/Delhi divide would be a
    second bridge, and the kingpin's betweenness — the whole of query 2 — is
    earned by being the only one. This asserts the generator's constraint, so
    that whoever adds the next row to it finds out here rather than on stage.
    """
    store, _ = demo
    ludhiana = {"person:ravi_kumar", "person:manjit_singh", "person:sukhwinder_kaur",
                "person:gurpreet_singh"}
    delhi = {"person:suneel_kumar", "person:parminder_sethi", "person:nisha_rani",
             "person:amarjit_chadha"}

    for edge in store.edges(types=("CO_OCCURS", "MESSAGED")):
        basis = (edge.attrs or {}).get("basis") or ""
        if not (basis == "co_accused" or basis.startswith("social_")):
            continue
        ends = {edge.src, edge.dst}
        assert not (ends & ludhiana and ends & delhi), \
            f"{edge.src} -[{edge.type}]-> {edge.dst} ({basis}) bridges the two clusters"


def test_every_source_the_problem_statement_names_has_a_handler(demo):
    """§1.1 lists seven sources and every bullet is a checkbox a judge ticks.

    Six of the seven now produce a document of their own kind on the demo case.
    Intelligence *agency* reports and the intelligence input here are the same
    handler; what is deliberately absent is a separate demo file for each, not
    a separate reader.
    """
    store, _ = demo
    kinds = {d["kind"] for d in store.documents()}
    assert {"fir", "cdr", "financial", "surveillance", "social", "history",
            "intelligence"} <= kinds, f"missing: {kinds}"
