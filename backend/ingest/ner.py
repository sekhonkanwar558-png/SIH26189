"""People, organisations and places out of unstructured report text — §3.1.

Two layers, and the order matters:

1. **Role cues** (always on, deterministic). Police reports name people in a
   handful of fixed frames — "complainant Smt. X", "one Ravi Kumar", "Y s/o Z",
   "accused ...". Matching those frames is far more precise on FIR prose than a
   general capitalised-run heuristic, and it costs nothing. Same for
   organisations ("... Bank", "... Travels", "Police Station X") and places
   ("Village X", "District Y").
2. **spaCy** (optional, adds recall). If `en_core_web_sm` is installed we also
   take its PERSON / ORG / GPE / LOC spans. If it is not installed the system
   still runs — the demo case is built from documents the cue layer handles —
   and `ner_backend()` reports which layers were live so nobody has to guess.

Both layers emit the same `Extraction` with offsets, and the pipeline dedupes
on the resulting node id, so a name found by both is one node with two sources.
"""

from __future__ import annotations

import functools
import re

from backend.ingest.patterns import Extraction

# Words that pass a capitalisation test but are never a person.
_STOP = {
    "police", "station", "district", "tehsil", "village", "sector", "court",
    "bank", "branch", "road", "street", "colony", "nagar", "chowk", "market",
    "the", "on", "at", "in", "of", "and", "shri", "smt", "mr", "mrs", "ms",
    "dr", "sub", "inspector", "head", "constable", "complaint", "statement",
    "first", "information", "report", "annexure", "exhibit", "accused",
    "complainant", "suspect", "victim", "witness", "informant", "deceased",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
}

# No `\.?` between name words: it lets a name run across a full stop and
# produce "Manjit Singh. Accused Sukhwinder" as one person. Honorifics are
# matched by the cue patterns and stripped by `schema.normalise_person`, so
# nothing here needs to swallow a dot.
_NAME = r"(?:[A-Z][a-z]{1,15}\s+){0,3}[A-Z][a-z]{1,15}"
# "Sector 32" and "Phase 7" are places whose name is a number.
_PLACE = rf"(?:{_NAME}(?:\s+\d{{1,3}})?|\d{{1,3}})"

# The cue WORD is case-insensitive ("Accused" opens a sentence); the NAME that
# follows must not be. A blanket re.IGNORECASE makes `[A-Z]` match lowercase,
# and the person pattern then swallows "registered to Suneel Kumar" whole.
_PERSON_CUES = [
    re.compile(r"\b(?i:complainant|accused|suspect|victim|witness|informant|deceased|"
               r"one|named|names|identifies|identified as|arrested|absconding)\s+"
               r"(?i:Shri|Smt\.?|Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Kum\.?)?\s*"
               rf"(?P<name>{_NAME})"),
    re.compile(rf"\b(?i:Shri|Smt\.?|Mr\.?|Mrs\.?|Ms\.?|Dr\.?)\s+(?P<name>{_NAME})"),
    re.compile(rf"(?P<name>{_NAME})\s+(?i:s|w|d)/o\b"),
    # Intelligence reports do not use FIR frames. They put the name first and
    # the claim after it — "X is reported to be running the vehicles" — and
    # with only the cues above, a graded report naming two men put neither of
    # them in the graph. §1.1 lists intelligence reports as a source; a handler
    # that reads the grading and drops the names is not one.
    re.compile(rf"(?P<name>{_NAME}),?\s+(?:is|was|has been)?\s*"
               r"(?i:reported|believed|assessed|suspected|understood)\s+to\s+be"),
]

_ORG_CUES = [
    re.compile(rf"(?P<name>{_NAME}\s+(?:Bank|Travels|Transport|Enterprises|Traders|"
               r"Trading|Logistics|Hotel|Lodge|Motors|Agency|Agencies|Consultancy))\b"),
    re.compile(rf"\b(?:Police Station|P\.?S\.?)\s+(?P<name>{_NAME})"),
    re.compile(rf"(?P<name>{_NAME})\s+(?:Pvt\.?\s*Ltd\.?|Private Limited|Ltd\.?)\b"),
]

_LOC_CUES = [
    # Named places keep the bare name — "Ludhiana", not "District Ludhiana" —
    # so a bare later mention resolves to the same node.
    re.compile(rf"\b(?i:Village|Vill\.?|District|Distt\.?|Tehsil|Sector|Colony|Nagar|"
               rf"Chowk|Mohalla)\s+(?P<name>{_NAME})"),
    # Numbered places have no name without their cue word: "Sector 32".
    re.compile(r"(?P<name>(?i:Sector|Phase|Block|Ward)\s+\d{1,3})\b"),
    re.compile(rf"\b(?i:at|in|near|from|towards)\s+(?P<name>{_NAME})\s+"
               r"(?i:railway station|bus stand|border|checkpost|highway|bypass)"),
]


def _clean(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip(" .,;:")).strip()


def _plausible(name: str, min_words: int = 1) -> bool:
    words = name.split()
    if len(words) < min_words or len(name) < 3:
        return False
    if all(w.lower() in _STOP for w in words):
        return False
    return words[0].lower() not in _STOP


def cue_entities(text: str) -> list[Extraction]:
    out: list[Extraction] = []
    for node_type, cues, min_words in (
        ("person", _PERSON_CUES, 1),
        ("organization", _ORG_CUES, 2),
        ("location", _LOC_CUES, 1),
    ):
        for pattern in cues:
            for m in pattern.finditer(text):
                name = _clean(m.group("name"))
                if not _plausible(name, min_words):
                    continue
                start = m.start("name")
                out.append(Extraction(
                    node_type=node_type, value=name, label=name,
                    start=start, end=start + len(m.group("name")),
                    kind="cue", attrs={"extractor": "cue"},
                ))
    return out


_SPACY_MAP = {"PERSON": "person", "ORG": "organization",
              "GPE": "location", "LOC": "location", "FAC": "location"}


@functools.lru_cache(maxsize=1)
def _nlp():
    """Loaded once. Returns None if spaCy or the model is missing — that is a
    supported configuration, not an error."""
    try:
        import spacy
        return spacy.load("en_core_web_sm")
    except Exception:
        return None


def spacy_entities(text: str) -> list[Extraction]:
    nlp = _nlp()
    if nlp is None:
        return []
    out: list[Extraction] = []
    for ent in nlp(text).ents:
        node_type = _SPACY_MAP.get(ent.label_)
        if not node_type:
            continue
        name = _clean(ent.text)
        if not _plausible(name):
            continue
        out.append(Extraction(
            node_type=node_type, value=name, label=name,
            start=ent.start_char, end=ent.start_char + len(ent.text),
            kind="ner", attrs={"extractor": "spacy", "spacy_label": ent.label_},
        ))
    return out


def extract_named_entities(text: str) -> list[Extraction]:
    return cue_entities(text) + spacy_entities(text)


def ner_backend() -> dict:
    """What actually ran, so the API can report it instead of the team guessing
    why a name was or was not picked up."""
    return {"cue_patterns": True, "spacy": _nlp() is not None,
            "spacy_model": "en_core_web_sm" if _nlp() is not None else None}
