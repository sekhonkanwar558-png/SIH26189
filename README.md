# Suishōdama

**An investigator you can hand the pile to.**

Smart India Hackathon 2026 · Problem statement **SIH26189** — *AI-Powered Criminal Network Analysis System*
Ministry of Home Affairs → **National Crime Records Bureau, Women Safety Division**
Category: Software · Theme: Blockchain & Cybersecurity

---

## Contents

**The product**
[The problem](#the-problem) ·
[What Suishōdama is](#what-suishōdama-is) ·
[Not a chat with your documents in it](#not-a-chat-with-your-documents-in-it) ·
[How an officer uses it](#how-an-officer-uses-it) ·
[The thing nobody planted](#the-thing-nobody-planted)

**The engineering**
[Architecture at a glance](#architecture-at-a-glance) ·
[The fourteen problems](#the-fourteen-problems) ·
[The system, layer by layer](#the-system-layer-by-layer) ·
[Performance, measured](#performance-measured) ·
[Determinism](#determinism)

**Reference**
[HTTP API](#http-api) ·
[The answer contract](#the-answer-contract) ·
[Agent tools](#agent-tools) ·
[Graph schema](#graph-schema) ·
[Setup](#setup)

**Running it**
[The demo case](#the-demo-case) ·
[Demo run sheet](#demo-run-sheet) ·
[Testing](#testing) ·
[What it does not do](#what-it-does-not-do) ·
[Decisions](#decisions)

---

# The problem

An investigating officer opens a trafficking case. On his desk: three FIRs, two CDR exports, a bank statement, a surveillance log, a criminal-history printout, an intelligence report, a social-media export.

**Every connection he needs is already in that pile.** He will not find them — because finding them means holding four hundred phone numbers in his head at once, and noticing that the number appearing twice in a call log is the same number registered to a name in a document he read nine days ago.

NCRB's own statement says exactly this: the data exists, the links are missed. It asks for a system that ingests fragmented, unstructured law-enforcement data, extracts people, locations, vehicles, phone numbers and organisations, builds relationship maps, **identifies key influencers**, and detects suspicious patterns.

Seven source kinds are named in the statement. Suishōdama has a handler for all seven:

| Source | Reader | Becomes |
|---|---|---|
| FIRs, chargesheets | PDF / text, cue-based NER | People, places, vehicles, `CO_OCCURS`, `OWNS` |
| Call detail records | CSV | `CALLED`, `MESSAGED`, `LOCATED_AT`, `REGISTERED_TO` |
| Financial records | CSV | `TRANSFERRED_TO` with amounts |
| Surveillance logs | Prose | Tower hits, sightings, `CO_OCCURS` |
| Social media exports | CSV | Platform-namespaced `account` nodes, DMs stronger than follows |
| Criminal history registers | CSV | Prior cases as `event` nodes, co-accused links |
| Intelligence reports | Prose + Admiralty grading | Everything inferred, **discounted by the grading** |

---

# What Suishōdama is

**The unit of the product is a case, not a dashboard.**

An officer opens a case. That case gets an agent of its own — its own knowledge graph, its own analytics, its own memory, its own hash-chained chain of custody, in its own file on disk. Nothing crosses between cases, and not because a filter says so: a different case is a different SQLite file, reached through the one function that turns a case id into a path.

He hands that case documents. He asks it things in English. It answers with the route through the graph lit up beside the sentence, and every claim traceable back to the character offset in the document it came from.

> **Everyone else will submit a dashboard.** A dashboard cannot be asked anything, and the investigator's real problem is not seeing the network once — it is interrogating it over months.

**One chat. That is the whole interface.** No section rail, no panels, no commands, nothing typed but English. Everything you would expect to be a tab — the documents, the findings, the chain of custody, an entity's history — he gets by asking for it, which is one skill instead of six. The graph opens when an answer has a route to show, and whenever he wants to look.

---

# Not a chat with your documents in it

This is the distinction the whole system rests on, and it is the question a judge is most likely to test.

**A chat assistant holds the case in its context window.** Documents are pasted in, the window fills, and what falls out is gone. Document forty competes for room with document one. Clear the thread and the case is gone with it.

**Suishōdama holds nothing.** The case's brain is on disk. The assistant arrives at every turn knowing nothing about the case and asks — one tool call at a time. Three consequences, each checkable in front of a judge:

**1. The brain grows where a window only fills.** Document forty makes document one *worth more*, because a link needs both ends. The counter under the composer is the only number in the product, and it is there because it changes.

**2. It outlives the conversation.** Clear the thread. Ask again. Same answer, same citations. The knowledge is in the case, not in the thread.

**3. The prompt is O(1) in the size of the case.** Nine documents or nine thousand — the request leaving the machine is the same size.

## What is actually sent on one question

Every question is a fresh request. It is written to the case — the thread and the custody chain — **before** any model call, so it survives a failure. What travels:

- **The standing brief**, re-read from disk every call: who it is, this case's type and the officer's own brief, its counts, up to 8 computed findings, 8 recorded conclusions, 8 open questions.
- **The last 24 turns of conversation.**
- **The new question**, with the entity ids the last answer rested on attached — so *"and him?"* binds to something real rather than hopefully.

**No documents. No graph. No tool results from any earlier question.** Nothing of the case is in the prompt until the model asks for it by name, and every result that comes back is capped.

**There is no compaction anywhere.** Nothing is ever summarised and dropped.

## Where context does grow — said out loud, rather than waiting to be caught on it

Two places, both bounded, and neither of them the case:

- **Inside one question**, the tool loop accumulates: iteration five re-sends one through four. Capped at **14 iterations** and discarded the moment the answer returns. This is also the cost driver — a heavy question costs roughly the *sum* over its iterations, not the largest one.
- **The 24-turn cut is a hard truncation, not a summary.** A standing instruction given in turn one and never repeated is not in front of the model at turn thirty.

Nothing about the *case* is lost either way. The thread is on disk, the facts are in the graph, and whatever the assistant worked out was written to case memory and returns in the standing brief for ever.

> **It is a window over the conversation. It is never a window over the case.**

**The corollary, and it is the right one: the core is the graph and the knowledge, not the model call.** Structurally, not as a claim — findings are computed by the analytics layer and the model only narrates them; every fact must come from a tool result; every citation is verified against the real graph *in code* before the officer sees it; the model holds nothing between turns. Its entire surface is two functions, so an on-premises model would drop in without touching ingest, the graph, analytics, custody or the interface.

What the model *is* load-bearing for: deciding what to ask the brain, turning *"the Ludhiana account"* into an id, and writing the sentence an officer reads.

---

# How an officer uses it

There are four things he can do, and he learns all of them in about eleven seconds.

## 1. Open a case

`+ New case`. It has no name yet and he is not asked to invent one — **the case names itself from the first thing he says to it.** The empty screen offers three openings, because with no panels to explore, the empty screen is the only place discoverability can live:

> *What is this case about?* · *Who matters most here?* · *What have you found that I haven't asked about?*

Under the composer, one line: **the brain**. Nothing yet.

## 2. Hand it a document

Drag it onto the window, or use the paperclip. PDF, CSV, or text. That is his whole job.

What happens next needs nobody:

```
fir_114_003.pdf — the brain grew by 14 entities and 39 links.
```

The line under the composer updates. **116 entities · 1,148 links · 9 documents.** He watches the case get bigger, permanently.

**A document that could not be read says so.** A scanned PDF with no text layer would otherwise register with a green tick, a valid custody entry and zero entities — indistinguishable from a document that genuinely had nothing in it. It reports what it could not read instead.

## 3. Ask it things

In English, the way he would ask a colleague who had already read the file.

> **"How is Ravi connected to the Ludhiana account?"**

The answer lands, and the graph opens beside it with the route lit hop by hop — Ravi Kumar → Manjit Singh → the two accounts → the account itself. He never typed an id. *"The Ludhiana account"* is not what the graph holds; the graph holds `account:50100244178`, and resolving one to the other is the assistant's job.

Under the answer: **Rests on 5 entities and 12 links.** One click opens the trail. Another opens **the exact line of the FIR the claim was read out of**, at its character offsets.

> **"Who matters most in this case?"**

It names **Harbhajan Dhillon** — who appears in exactly one document, a call log, and in no FIR, no surveillance report and no statement. Twenty-two per cent of every shortest path in the network runs through him, because he is the only thing joining two groups that otherwise never touch.

**No officer reading the reports in this case would ever have written his name down.**

## 4. Look at the brain

The **Brain** control sits above the conversation, so an officer who has just opened a case and wants to *look* at it has somewhere to press.

It does not draw the whole case at once. 116 entities as one cloud of identical grey dots is a picture of *having* a graph, not a way of reading one. It opens on a readable core — the answer's own route, or the most connected entities and the identifiers that bridge them — and **every node fans out to its own connections on a click**, born at its parent so the eye keeps hold of where it came from.

- **A type is drawn, not written.** Nine shapes carry the nine node types, with a desaturated tone second, so the distinction survives both a projector and a colour-blind judge. Size is degree — the case's own argument about who matters.
- **The same click again folds it away**, taking everything that came in behind it. Four levels deep is reversible without starting over.
- **Nodes drag.** A force layout puts two names on top of each other often enough, and an officer's own arrangement of a network is part of how he thinks about it.
- **Every node opens to what is inside it** — every document it appears in, each row opening to the exact passage. Its connections are listed and clickable, which adds them to the graph.
- **The key at the foot doubles as a filter.**
- **Evidence Amber is the only saturated colour in the product**, and it means one thing: *this is the path the answer rests on*. Nothing is ever drawn between two nodes that have no edge.

## And the fifth thing, which is not a screen

> **"Has anything in this case been tampered with?"**

Every document ingested and every inference made is hash-chained to the one before it. Break an entry and it names **the entry and the reason** — not "a problem somewhere".

The chain of custody has no panel. It is a question, like everything else.

---

# The thing nobody planted

The prompt had never asked the assistant to *volunteer*, though volunteering is the entire pitch: a tool shows you what you already suspect, and this one surfaces what you did not ask about.

One clause was added. The first answer after it ended with *"One more thing you didn't ask about"* and named **Simran Bedi** — unnamed in any FIR, her handset hitting four Ludhiana towers and three Delhi ones, in direct call contact with both principals.

**A second Ludhiana–Delhi bridge, independent of the money trail. She is not in the ground-truth file.** Nobody designed that finding. Every claim it made about her was checked against the graph afterwards and holds — it under-stated twice.

That is the strongest evidence the project has that the system **analyses rather than recites**, and it is the answer to the sharpest question a judge can ask.

---

# Architecture at a glance

```
                  ┌──────────────────────────────────────────────┐
   documents ───► │ 1. INGEST        no model in this path       │
                  │    readers → patterns → NER → pipeline       │
                  └───────────────────┬──────────────────────────┘
                                      │  every fact carries {doc_id, start, end}
                  ┌───────────────────▼──────────────────────────┐
                  │ 2. GRAPH         one SQLite file per case    │
                  │    stable ids · idempotent merge · provenance│
                  └───────────────────┬──────────────────────────┘
                                      │  recomputed on write
                  ┌───────────────────▼──────────────────────────┐
                  │ 3. ANALYTICS     deterministic, cached       │
                  │    centrality · Louvain · anomalies · FINDINGS│
                  └───────────────────┬──────────────────────────┘
                                      │  the model never invents these
                  ┌───────────────────▼──────────────────────────┐
                  │ 4. AGENT         13 tools · verified contract│
                  │    ask · brief · investigate                 │
                  └───────────────────┬──────────────────────────┘
                                      │  answer contract + verified block
                  ┌───────────────────▼──────────────────────────┐
                  │ 5. API           22 endpoints, all case-scoped│
                  └───────────────────┬──────────────────────────┘
                                      │
                  ┌───────────────────▼──────────────────────────┐
                  │ 6. INTERFACE     one chat + the brain        │
                  └──────────────────────────────────────────────┘

        ┌─────────────────────────────────────────────────────────┐
        │ CUSTODY CHAIN — hash-linked, append-only, per case       │
        │ every ingest, every extract, every query, every infer    │
        └─────────────────────────────────────────────────────────┘
```

## One question, end to end

1. Officer types **"How is Ravi connected to the Ludhiana account?"**
2. The question is written to the conversation table and to the custody chain **before any model call** — so it survives a failure.
3. The standing brief is assembled from disk: case identity, counts, findings, conclusions, open questions. The last 24 turns are attached, plus the referent ids from the previous answer.
4. The model calls `find_entity("Ravi")` → `person:ravi_kumar`. Then `find_entity("Ludhiana account")` → `account:50100244178`.
5. `path_between(...)` returns the route with the underlying edge ids.
6. `read_source_doc(...)` on the edges that matter — **it checks the document actually says what the edge claims.** An answer that has not been checked against a document is a draft.
7. The model returns the structured answer: prose, `cited_nodes`, `cited_edges`, `highlight_path`, `claim_type`, `confidence`, `caveats`.
8. **`verify()` checks every id against the real graph in code.** Anything that does not exist is stripped and reported, and the answer is marked unverified.
9. The answer is written to the conversation and hash-logged as an `infer` entry.
10. The chat renders it; the brain opens and lights exactly that path, hop by hop; the evidence trail opens to the line of the FIR.

---

# The fourteen problems

This is the part that is worth telling. Fourteen problems, what each one actually was, and what it cost to solve.

## 1. The prompt does not grow with the case

**The problem.** If the size of the case decides how much text reaches the model, then the case *is* the context window after all, and everything above is a slogan.

**What we found.** No tool result had a ceiling. On a 3,265-node case built from a 2,000-row CDR — *small*, next to a real one — a single `timeline` call returned **419,224 characters**, about 105,000 tokens. `communities` returned 81,035. `neighbours` on a busy number, 42,430. The only limit anywhere was a string slice at 60,000 characters, which cut **mid-object**: on any case big enough to reach it the model received text that was not valid JSON, with nothing saying so.

**The fix.** A fixed ceiling on this side of the boundary — **40 items, 12,000 characters** — regardless of case size. Truncation is *structural* (fewer items, never half an item) and always announced, with a note telling the model to narrow the question and call again.

**The detail worth knowing:** when a result is still too large, it halves **every** list in the structure repeatedly rather than the longest one. `communities` is thirty lists of four thousand — cutting the single longest each round converges in hundreds of rounds, and the first version gave up and returned an error instead, taking a working tool away from the agent exactly when the case got big enough to need it. Halving everything converges in log₂ of the longest list, whatever the breadth. The shape is preserved, so a caller reading `nodes` and `edges` still finds `nodes` and `edges`.

## 2. Ingest was quadratic — three times over

**Measured, not argued.** 27 KB of prose took 5 seconds. 53 KB took 16. **106 KB took 63 seconds.** A real chargesheet bundle would never have finished.

The cause was provenance. Every node's `sources` list grew one entry per mention, and was re-read, re-merged and re-serialised on every single upsert.

**Now: 3.8 seconds, and linear** — eight times the document costs 7.4 times the time. A test fails if any one of the three quadratics comes back.

About **1.4 seconds for forty pages** including every analytic. A 50,000-row CDR is about a minute and a half — linear and honest, but not instant.

## 3. Provenance is capped; the count is kept

The same unbounded list was copied into every tool result. **One entity reached the model as a 23,000-character blob.**

The rule now: **up to three offsets per document**, hard ceiling of 60. So *"which documents name this man"* stays exactly as true as it was; what is dropped is the fourth offset inside a document already represented, which no answer has ever needed.

**The true count is not lost** — it is recorded as `prose_mentions`. *Named 400 times* is a more useful fact than 400 offsets, and a citation needs one place in the document because `read_source_doc` opens it.

## 4. Prompt caching, and why the system prompt is three blocks

**The problem.** The tool loop re-sent its whole accumulated context on every one of up to 14 iterations, at full price. Nothing in the codebase cached anything.

**The fix, and the structural half is the interesting one.** Caching is a **prefix match**, so a single system string would have thrown the cached entry away every time a document landed. The standing brief is split into three blocks with breakpoints between them:

| Block | Changes when | Cached |
|---|---|---|
| The standing instructions — universal, identical for every case this product will ever run | never | ✅ ~2,100 tokens |
| This case: identity, counts, computed findings | a document lands | ✅ |
| What it has concluded, what it is still holding open | every answer | ✗ small by design |

Plus **top-level automatic caching on the tool loop**, which moves forward with the runner — so iteration nine re-reads iterations one to eight at a tenth of the price instead of paying full rate again.

**Measured live across nine real calls: two input tokens at full price per request, everything else served from cache. $0.10 a question → $0.0235.**

Caching is an optimisation and must never be the reason an officer gets no answer, so a rejected breakpoint retries once, uncached, and a rejected request costs nothing.

## 5. Centrality is scored on a person-projected graph

**This single design choice is the difference between finding the kingpin and not.**

A kingpin whose only edge is `OWNS` to his own phone scores near zero on the raw graph, because every path runs through the phone node and stops there. But *"who matters in this network"* is a question about **people**, and a man and his SIM are not two actors.

So every phone, account, device and vehicle with a known holder is contracted into that holder, and an edge between two identifiers becomes an edge between their owners. A device registered to a phone that belongs to a person belongs to that person too — one more hop, which is what makes a handset swap visible.

**Identifiers with no known holder stay as themselves** — an unattributed number is genuinely a separate actor until somebody attributes it.

The projected graph is built by one function, so a score and the sentence explaining it can never disagree about which graph they came from.

## 6. Findings are computed, and a finding outranks a ranking

**Findings are not generated by the model.** The analytics layer computes them deterministically from the graph, each carrying the node and edge ids it rests on. The model narrates and investigates them. That is what keeps *"the graph causes the answer"* structurally true rather than a promise.

Ten kinds, split by what they are:

| Anomalies — statistical | Findings — what it volunteers |
|---|---|
| `volume_spike` | `hidden_broker` |
| `handset_swap` | `undocumented_person` |
| `one_way_account` | `single_point_of_contact` |
| `large_transfer` | `repeat_offender` |
| `went_silent` | `prior_association` |

**And then the finding has to reach the assistant.** Asked *who matters most*, the agent once named the woman sitting on 38% of shortest paths — who is named in four documents and whom the officer already knows. The `hidden_broker` finding naming a man in **no** report was **first of twenty-six** in the analytics layer, and the model never saw it: the brief carried counts, conclusions and open questions but not findings, so *"lead with the finding"* was an instruction with nothing attached.

**The system's best insight was structurally unreachable by the assistant that was supposed to deliver it.**

Fixed by putting findings in the standing brief with the rule that **a finding naming someone the paperwork does not names opens the answer**. Centrality ranks *position*, never novelty, and its top name is one the officer could have given you himself. Paid for by stripping node and edge id lists out of memory entries — eight conclusions were 10,600 characters of which the model needs the sentence, and they *grow as the case is worked*, which was putting case size back into prompt size. **Net cost: negative.**

## 7. The hidden-broker threshold ranks people against people

Its bar used to be the fifth-highest betweenness across *every* node. But only a person can be a broker — so ranking them against document and organisation hubs sets the bar by nodes that were never candidates.

On the demo case, three of the top five scores are a document, a bank statement and a travel agency. **"Top five" quietly meant "top two people" — and the more documents an officer uploaded, the fewer real brokers the case could surface.**

Found when adding the criminal-history source pushed the kingpin to sixth overall and deleted the centrepiece of the demo outright. **The graph was right the whole time; the yardstick was wrong.**

## 8. Every citation is verified in code

A model that hallucinates `e_9999` is caught here, not by a judge.

`verify()` checks every returned node and edge id against the case graph. Unknown ids are **stripped and reported**, the answer is marked `verified.ok = false`, confidence drops to low, and a caveat says exactly which ids failed. The interface shows it. An answer whose citations failed is not an answer, and hiding that is the one thing that would make this dishonest.

**With one deliberate exception.** An officer talks to a teammate about more than the graph — *"what should I ask the bank for?"*, *"draft what I tell my SHO"*. None of that asserts a case fact and none of it cites a node. So the model declares `claim_type` — `evidence` or `guidance` — and the citation requirement applies to the kind that can be wrong about the case. Flagging the rest put a red panel on half of a normal conversation and trained the officer to ignore the one warning that matters.

**The honest edge of this guard, stated because nothing else will state it:** it checks **citations, not assertions**. Every node id in an answer is proved against the graph; a sentence carrying no ids passes through untouched. Live, the agent once wrote that the entries after a break *"all sit correctly on the hash chain"* — which no tool told it, because `verify()` stops at the first break. True by luck. The guard is real and its edge is exactly where the ids stop.

## 9. Betweenness: exact below 500 nodes, estimated above, and it says which

Exact betweenness is O(V·E), and a recompute runs after **every ingest**. Measured on a 2,685-node case: **exact 36.4s, sampled (k=128) 2.2s** — 36.4 of a 38.7-second recompute. On a real case file the officer would wait minutes for the graph to settle after each document.

Above 500 projected nodes it samples 128 pivots **with a fixed seed**, so it is deterministic — the same case gives the same numbers on every machine — and it preserves the ranking at the top, which is all any finding reads.

**Where it is an estimate, the system says so.** The sentence the officer reads says *"about"*. An estimate is never read out as a measurement. The demo case is 125 nodes, so it stays exact to the last decimal.

Louvain runs with a fixed seed for the same reason: the same graph must produce the same clusters every run, or the demo says something different each time it is rehearsed.

## 10. An intelligence report is graded, and what it implies is discounted

The problem statement names intelligence agency reports as a source, and one was being read as an ordinary note — **an uncorroborated tip from an untested source entering the graph at exactly the confidence a bank record does.**

Intelligence carries the **Admiralty grading** (reliability A–F, credibility 1–6) for precisely this reason, and it maps onto our `confidence` field almost exactly. The factor is the **lower of the two axes, not their product**: they are independent judgements in the standard, and multiplying them invents a precision we do not have.

The grading multiplies the confidence of everything *inferred* from the report — **never** the fact that it names who it names. An ungraded intelligence report still gets 0.7: no grading is not the same as a good one.

## 11. Case isolation is by construction, not by permission

Every path a case can touch comes from **one function**. Nothing else in the backend builds a case path by string concatenation.

A case id becomes a directory name, so anything that could escape the cases root — separators, dots, drive letters — is **rejected rather than sanitised**, because silently rewriting an id would let two cases collide on one store.

Every agent tool is closed over exactly one `CaseContext`, built per request. **There is no tool that can name another case**, and no class that can reach one. The only endpoint that reads across cases is the case list, and it reads metadata only.

## 12. Hash-chained chain of custody

The honest reading of the *Blockchain & Cybersecurity* theme. No token, no consensus — just the property that actually matters for evidence: **you cannot quietly rewrite history.**

```
hash = sha256(prev_hash + canonical_json(entry_without_hash))
```

Append-only, one JSON object per line, one chain per case. Five actions: `ingest`, `extract`, `infer`, `query`, `export`. Every document that arrives and every inference the system draws gets an entry. Altering any earlier entry breaks every hash after it.

`verify()` **returns** the first break rather than raising, because the officer sees this and a broken chain is a *finding*, not a crash. It names the entry and the reason.

`canonical_json` is sorted-key, no-space UTF-8. It must stay byte-exact or every chain written by an earlier version fails to verify.

**It ran live.** The chain was broken at entry 2, the question was typed into the chat, and the answer named **entry #2 and why** — then refused to over-claim: *"I don't have the actual content of that broken entry #2 in front of me… so I can't yet tell you which document, edge or conclusion it altered."* Inventing a filename was the easy failure and the demo-killing one.

## 13. Nothing speaks unprompted

**Two typed questions once produced five billed model calls.** Three were unprompted: opening a case fired a briefing, and — the part that made it a loop — *answering a question caused another one*, because an answer records conclusions, conclusions become findings, and the next refetch saw fresh findings and ran the model again. One of those unprompted calls returned nothing usable and wrote *"the assistant did not return a usable answer"* into the officer's thread.

**Nothing in the product now speaks unless asked.** The "assistant unreachable" banner moved onto a health check that costs nothing — it was previously discovered by making a paid call and watching it fail.

## 14. No fallback, and no web tool

Two capabilities deleted rather than kept warm, for the same reason: **a capability that half-exists is one a demo eventually leans on.**

**There is no offline mode.** `/ask` either runs the model or returns 503 saying the assistant is unavailable. A degraded impostor that answers some questions and silently cannot answer others is worse than an outage, because the officer cannot tell which one he is talking to. The graph, the documents, the findings, the paths and the custody chain all remain fully usable; what stops is the assistant, and it says so.

**There is no web search.** The OSINT boundary had been built and left empty — a tool that logged every call, never received case content, and had no provider behind it. Deleting it buys a claim worth more than the feature:

> **The only thing in this product that reaches the network is the model call.** Ingest, the graph, every analytic, the custody chain and the case memory all run on the officer's machine.

For a system being shown to NCRB, *"what leaves this building?"* is a question with one short answer. It also matches how an investigator already works: he searches, and what he finds becomes a document the case ingests like any other.

**The honest edge of that claim, before a judge finds it:** intelligence has to see evidence. What travels with a model call is the standing brief, the recent conversation, and the tool results the model asked for — and those include **excerpts of the documents themselves**, capped per call. The files are never uploaded whole and nothing is sent that the assistant did not ask for by name. But the passages it reads do leave the machine. That is now the *only* thing that does.

---

# The system, layer by layer

Six layers, and a hash chain running underneath all of them. Each is a directory under `backend/`, and the ordering is real — nothing reaches back up.

## 0. The shape of a case on disk

A case is a directory. That is the entire isolation model.

```
data/cases/{case_id}/
  meta.json          title, officer, case_type, brief, status, synthetic
  graph.db           SQLite — nodes, edges, documents, analytics,
                     agent_memory, conversation, counters
  custody.jsonl      the hash chain, append-only, one JSON object per line
  docs/              the original uploaded files, under the officer's filename
  extracted/         the plain text of each document, with stable offsets
```

**`config.case_dir()` is the only function in the backend that turns a case id into a path.** Nothing else builds one by string concatenation, which is what keeps isolation a property rather than an aspiration. Ids are validated against `^[a-z0-9][a-z0-9_\-]{0,63}$`.

**Why a case carries its own type and brief.** `meta.json` holds `case_type` (free text: *"financial fraud"*, *"homicide"*, *"extortion"*) and `brief` — the officer's own words about what he is working. Nothing in ingest, the graph, the analytics or the agent knows what a trafficking case is. They know identifiers, links, timing and structure, which every investigation has. Those two fields are threaded into the agent's standing brief on every turn, which is what lets one engine reason like a fraud analyst on a fraud case and like a homicide analyst on a homicide.

## 1. Ingest — and there is no model in this path

`backend/ingest/` · `readers.py` → `patterns.py` + `ner.py` → `structured.py` → `pipeline.py`

```
text → identifiers + names (with offsets)
     → nodes and edges (every one carrying its provenance)
     → custody entries (ingest, then extract)
     → analytics recomputed
     → counts back to the caller
```

**No model runs here.** Phone numbers, IMEIs, account numbers, IFSC codes, vehicle registrations, UPI handles, FIR numbers and timestamps are format-regular: regex extracts them faster, cheaper and *identically every time* — which is what makes the same document produce the same graph twice.

### `readers.py` — bytes to text with stable offsets

One job: produce *the* text for a document, once, and never produce a different text for the same bytes. The extracted text is written into the case directory and is what `read_source_doc` serves — **so what a judge clicks through to is literally what the extractor read.**

| Suffix | Path |
|---|---|
| `.pdf` | `pypdf` per page, classified from what it says |
| `.csv` `.tsv` | parsed to rows, classified from its columns |
| `.txt` `.md` `.log` `.json` | read directly, classified from what it says |

**Nine document kinds**: `fir` `surveillance` `intelligence` `note` (prose) · `cdr` `financial` `social` `history` (tables) · `other` (read, but unrecognised).

**A document we could not read must say so.** `_read_pdf` counts pages under `MIN_PAGE_CHARS = 12` as blank and returns a `warnings` list; a PDF where every page is blank is classified `other`, never `note` — guessing a kind off page markers would put a confident label on a document nobody has seen the inside of.

**Intelligence grading** lives here too. `read_grading()` parses the Admiralty scale in any of three written forms, and `confidence_factor()` returns the lower of the two axes.

### `patterns.py` — deterministic identifiers

A frozen `Extraction` dataclass: node type, value, human label, **character offsets**, and which pattern fired.

Patterns are tried in order and **a match overlapping an already-claimed span is dropped**, so the order encodes specificity: a 15-digit IMEI must be claimed before anything shorter can nibble at it. IFSC first, then IMEI, then account numbers, and so on down.

### `ner.py` — names out of prose

**Role cues (always on, deterministic).** Police reports name people in a handful of fixed frames — *"complainant Smt. X"*, *"one Ravi Kumar"*, *"Y s/o Z"*, *"accused …"*. Matching those frames is far more precise on FIR prose than a general capitalised-run heuristic, and it costs nothing. Same for organisations and places.

**spaCy (optional, adds recall).** If `en_core_web_sm` is installed, PERSON / ORG / GPE / LOC spans are taken too. If it is not, the system still runs, and `ner_backend()` reports which layers are live so nobody has to guess.

Both layers emit the same `Extraction`, and the pipeline dedupes on the resulting node id — so a name found by both is one node with two sources.

**Two regex lessons paid for in bugs:**

- The cue *word* is case-insensitive (*"Accused"* opens a sentence); the *name* that follows must not be. A blanket `re.IGNORECASE` makes `[A-Z]` match lowercase, and the person pattern then swallows *"registered to Suneel Kumar"* whole.
- No `\.?` between name words. It lets a name run across a full stop and produce *"Manjit Singh. Accused Sukhwinder"* as one person.

### `structured.py` — tables to typed edges

Four of the seven sources arrive as tables: **CDR**, **financial**, **social**, **criminal history**.

**These are the strong edges.** A CDR row is not an inference: A called B at 22:10 for 94 seconds off tower LDH-014, and that becomes exactly one `CALLED` edge carrying exactly that.

Column names vary by operator and by bank, so each field is matched against a **list of aliases** rather than one fixed header. An unrecognised column is not an error — it is reported in `warnings`, so whoever exported the file can see what was ignored instead of it vanishing silently.

**Edge directions, decided once so the whole team reads the graph the same way:**

| | |
|---|---|
| `phone:A -[CALLED]-> phone:B` | A dialled B |
| `phone:A -[MESSAGED]-> phone:B` | A texted B |
| `account:X -[TRANSFERRED_TO]-> account:Y` | money moved X to Y |
| `person:P -[OWNS]-> phone / account` | a subscriber or holder record |
| `device:I -[REGISTERED_TO]-> phone:N` | handset I carried number N |
| `phone:A -[LOCATED_AT]-> location:T` | A used tower T |
| `account:H -[MESSAGED]-> account:H2` | a DM or reply between two handles |
| `person:P -[MENTIONED_IN]-> event:C` | P is named in prior case C |
| `person:P -[CO_OCCURS]-> person:Q` | P and Q charged in the same case |

**The `device → phone` direction is deliberate: it is how a burner swap is found.** One handset with several numbers registered to it is one person changing SIMs, and that is visible only when the IMEI is the source node.

**Social:** a handle is an `account` node **namespaced by platform** — the same handle on two platforms is two accounts, because it is two accounts. A DM is a stronger edge than a follow. A display name gives a weak `OWNS` at 0.45 confidence, because a display name is a claim, not a record.

**Criminal history:** a prior case is an `event` node; two people on one charge sheet get a `CO_OCCURS` at 0.85 with `basis: co_accused`. A disposition string is mapped to convicted / acquitted, and **an unreadable status is left blank rather than guessed.** Three or more priors makes a repeat offender.

**No new node or edge type was added for the two sources that came last.** A `FOLLOWS` and a `CHARGED_IN` edge would each read better and would each cost a contract change and a front-end update. A handle is an `account`, a prior case is an `event`, and what kind of link a `CO_OCCURS` is gets said in `attrs.basis`.

### `pipeline.py` — prose to graph

| Constant | Value | Why |
|---|---|---|
| `CO_OCCUR_WINDOW` | 600 chars | A paragraph, roughly. Document-wide pairing would make every FIR a clique. |
| `OWNS_WINDOW` | 120 chars | Close enough to read as *"this person's number"*. |
| `CO_OCCUR_WEIGHT` | 0.3 | Weak, and marked weak. |
| `CO_OCCUR_CONFIDENCE` | 0.4 | |
| `OWNS_CONFIDENCE` | 0.6 | |

**Weak links are marked weak rather than excluded, because betweenness over a graph of only strong edges misses exactly the broker we are built to find.**

**Two rules learned by measurement:**

- **Proximity linking is prose only.** Running co-occurrence over a CDR export links whoever happens to sit in adjacent rows — it added **606 meaningless edges** and buried the real structure.
- **It claims the nearest name only.** Linking every person within the window to a nearby number gave one man ownership of another's phone, which then produced a real-looking false path.

Documents and events are excluded from proximity linking entirely: everything in a document co-occurs with the document.

**Ingesting the same file twice is a no-op on the graph.** Node ids and edge natural keys are stable, so re-running the generator or re-uploading an FIR merges rather than doubles.

## 2. The graph

`backend/graph/` · `schema.py` (frozen) · `store.py` (SQLite) · `nx_adapter.py` (NetworkX)

### `store.py` — one SQLite file per case

| Table | Holds |
|---|---|
| `nodes` | id, type, label, attrs, first/last seen, **sources** |
| `edges` | id, natural key, src, dst, type, attrs, weight, confidence, ts, **sources** |
| `documents` | doc_id, filename, kind, sha256, ingested_at, char_len, meta |
| `analytics` | cached results, each stamped with the `graph_rev` it was computed at |
| `agent_memory` | conclusions, open questions, evidence requests, briefings delivered |
| `conversation` | the officer's thread — **on the case, not in the browser** |
| `counters` | id sequences |

**`graph_rev` is bumped on every write**, and every analytics cache carries the rev it was computed at — so a stale cache is *detectable* rather than merely old.

**Merging is the interesting part.** `upsert_node` on an existing id unions the sources, unions the attrs, widens the `[first_seen, last_seen]` window, and keeps the better label. `upsert_edge` merges on `natural_key`, so two calls between the same pair at different times are two edges, while the same call ingested twice is one edge with two sources.

**`_merge_sources` is where ingest was quadratic** — see [problem 2](#2-ingest-was-quadratic--three-times-over). The rule now is `MAX_SOURCES_PER_DOC = 3`, hard ceiling `MAX_SOURCES = 60`, and the true count is returned so `note_mentions` can record `prose_mentions`.

**Memory ids are content-derived**, so the same conclusion recorded twice is one row. An assistant that repeats itself every ingest is worse than one that says nothing.

### `nx_adapter.py` — two views, and a third

**`build_multigraph()`** keeps every parallel edge — forty calls between two phones are forty edges, which is what `timeline` and `anomalies` need.

**`collapse(g)`** folds them into one undirected weighted graph — which is what centrality, communities and shortest paths need. Direction is dropped deliberately: *"how is Ravi connected to the account"* is a question about connection, not about who dialled whom. The underlying edge ids are kept on `edge_ids`, so a path can always be traced back to the facts that produced it.

> **`distance = 1 / weight`.** NetworkX reads a `weight` argument as a **cost**, so passing raw weight would make well-evidenced links look *far apart* — the exact opposite of what is meant.

**`project_people(u, g)`** is the third view, and it is the one that finds the kingpin — see [problem 5](#5-centrality-is-scored-on-a-person-projected-graph). Two resolution passes, self-edges dropped after contraction, and it returns the `identifier → owner` map alongside the graph so a score can always be traced back to the identifiers that earned it.

## 3. Analytics

`backend/analytics/` · `metrics.py` · `anomalies.py`

**Computed on write, not on demand.** `recompute()` runs after every ingest and caches everything into the `analytics` table with the `graph_rev` it was computed at.

`analysis_graph()` is a single function returning the person-projected graph. Metrics, communities and findings all read it, so **a score and the sentence explaining it can never disagree about which graph they came from.**

| Metric | Meaning |
|---|---|
| `betweenness` | Who sits on the routes — **the broker metric** |
| `pagerank` | Weighted connection volume |
| `degree` | Weighted direct connections |

**Communities** are Louvain, which NetworkX has shipped since 3.0 — no extra dependency. Fixed seed, on the same projected graph.

### `explain()` — the sentence an officer reads

Facts only, all of them checkable:

> *"Harbhajan Dhillon lies on 22% of the shortest paths in this network; 2 direct contacts; bridges 2 groups that otherwise do not touch; **named in no report — appears only in cdr data**."*

That last clause is the distinction the whole system exists to surface. *"In 1 document"* is true of a man named only in a CDR export **and** of a man named in an FIR, and those are not the same fact — so it names the kinds.

### Anomalies and findings

**Anomalies are statistical.** Mechanical, cheap, computed over the multigraph and the raw edge table:

| Kind | What it is |
|---|---|
| `volume_spike` | Call volume in a window well above baseline |
| `handset_swap` | One IMEI carrying several numbers |
| `one_way_account` | An account that only ever receives |
| `large_transfer` | A statistical outlier by amount |
| `went_silent` | A number that stops after sustained activity |

**Findings are what the assistant volunteers.** Same evidence, ranked by how much it should change the officer's next hour, each carrying the node and edge ids it rests on:

| Kind | Severity | What it is |
|---|---|---|
| `hidden_broker` | high | High betweenness, few direct contacts, **named in no report** |
| `undocumented_person` | | Exists only in CDR or bank data |
| `single_point_of_contact` | | One node joining two clusters that otherwise never touch |
| `repeat_offender` | | Three or more priors in the register |
| `prior_association` | | Two people linked by a shared charge sheet and nothing else |

**`_hidden_brokers` is the finding the system exists to produce.** High betweenness, few direct contacts, named in no document. *A dashboard cannot surface this, because nobody thinks to look for a name they have never read.*

Three filters: `person:` prefix, degree ≤ 6, and not named in any document of a **report kind** — `fir`, `surveillance`, `note`, `intelligence`. `intelligence` belongs in that list: an intelligence report names people, and a man named in one is not invisible however thin the report is. `cdr`, `financial`, `history` and `social` do not — they are records generated by what somebody *did*, not accounts written by somebody who was watching.

## 4. The agent

`backend/agent/` · `loop.py` (the model) · `tools.py` (13 tools) · `contract.py` (verification)

Three entry points:

| | |
|---|---|
| `ask(question)` | An investigation, not a lookup. A real tool loop over the graph, verified against source documents. |
| `brief()` | What it says after new documents land: what changed, what it now believes, what it wants next. |
| `investigate(id)` | Take one finding and work it — pull the paths, read the documents, write a conclusion, open a question if it cannot settle it. |

**Three rules the code enforces so they cannot be prompted away:**

1. **Findings come from the graph, not the model.**
2. **Every answer is verified before it is returned.** A citation that does not exist in the graph is stripped and reported.
3. **There is no fallback.** If the assistant cannot run, the officer is told so and gets a retry — never a graph lookup dressed up as an answer.

### What the model receives

**`_system()` returns three blocks with two cache breakpoints** — see [problem 4](#4-prompt-caching-and-why-the-system-prompt-is-three-blocks).

**The case's identity belongs in the system block rather than the first user turn**, because it is true of every turn. Put it in a message and it either gets repeated on each one or slides out of the window as the thread grows — and an assistant that forgets which case it is on halfway through a conversation is not a teammate.

**Everything in the brief is slimmed.** A finding carries every node and edge it rests on — ~19,000 characters for eight. A memory entry carries ids, timestamps and meta; eight conclusions came to 10,600 characters of which the model needs the sentence. Both are stripped to headline and detail, because **they grow as the case is worked**, which puts case size back into prompt size.

**`_messages()`** sends the last 24 turns, adjacent same-role turns merged, always opening with the officer. The new question carries the **referent set** — the entities the last answer actually rested on, as `Label (id)` pairs — so *"him"* and *"that account"* have something real to bind to. **Asking a model to remember harder is not a mechanism; handing it the ids is.**

### The loop

The SDK's tool runner owns the loop; we own the bound tools, the contract and the caps.

| | |
|---|---|
| `MAX_TOOL_ITERATIONS` | 14 |
| `MAX_TOKENS` | 16,000 |
| `EFFORT` | high |
| thinking | adaptive |
| output | JSON schema — the answer contract |

Every API failure mode maps to `AgentUnavailable`, which the API turns into a **503** with a retry: not found, rate limited, any status error, connection error, and a model refusal.

**When the model returns no text at all**, the contract's fallback says *"the assistant did not return a usable answer"* — correct behaviour, and useless to debug from. So the two ways to get there are logged by name: the iteration cap (the loop ran out before it wrote an answer) and `max_tokens` (thinking ate the budget and the JSON was truncated). **Both are the most expensive call the system can make, returning nothing.**

### Cost accounting, and its honest limit

`_log_usage` writes one console line and one row to `output/cost.jsonl`: input, cache-read, cache-write and output tokens, plus a dollar figure at recorded list prices.

**It runs once per question, on the final message the runner returns after the loop has already finished.** So each row records the **last request**, not the sum over up to fourteen iterations.

> **The ledger is a floor, not a bill.** On a fixed budget, *"we have spent $0.23"* could be wrong by two or three times, and nothing on this machine can say. Only the vendor console can.

It is wrapped whole in a `try`, because **a bookkeeping failure must never cost an officer an answer.** What the line *is* an exact read on: if `cache_read` is 0 on every question after the first, the cached prefix is being invalidated somewhere and the loop is costing several times what it should.

## 5. The custody chain

`backend/custody/chain.py` — about 130 lines. See [problem 12](#12-hash-chained-chain-of-custody) for the design.

```jsonc
{
  "seq": 12,
  "ts": "2026-09-06T18:04:11+05:30",
  "actor": "officer",
  "action": "ingest",              // ingest | extract | infer | query | export
  "ref": "doc:fir_114_003",
  "payload_sha256": "…",
  "prev_hash": "…",
  "hash": "…"
}
```

`verify()` checks three things per entry — the sequence number, that `prev_hash` matches the previous entry's hash, and that the entry's content still hashes to its recorded hash.

`append()` is the only write path, and it has **six call sites, all downstream of an officer uploading or asking.** No scheduler, no thread, no startup hook.

## 6. The interface

`frontend/src/` — React 19 · Vite · TypeScript · Tailwind v4 · Cytoscape.js · TanStack Query · React Router · Lucide

| File | What it is |
|---|---|
| `pages/Chat.tsx` | The whole product — one conversation per case |
| `components/Brain.tsx` | The case's graph, interactive |
| `components/Evidence.tsx` | The trail from a sentence back to a line in a document |

**Thirteen of the twenty-two endpoints are called from the chat.** The other nine are reached *by asking*, because the agent's own tools cover them. After the pivot that is the design rather than a gap.

**Near-colourless.** One ink, two greys, hairline borders. An officer reads text here for an hour, and every accent not carrying meaning competes with the words. **Evidence Amber is the only saturated colour and it means exactly one thing:** *this is the path the answer rests on*.

**Cytoscape's own press feedback is off.** Out of the box a press answers with a translucent grey disc under the node — on a near-colourless product it is the loudest thing on screen, it says only *"you pressed"*, and it covers the thing being pressed to say it. Feedback is a border now, which follows the node's real shape: a circle drawn around a hexagon is a second shape competing with the one that carries meaning.

**Consecutive hops light the real edge between them.** A finding's unordered set lights its members only, because a set is not a journey anyone can take. **Nothing is ever drawn between two nodes with no edge.**

### Three interface bugs worth keeping in the record

**`square` is not a valid shape in Cytoscape.** It was accepted in silence and then blanked the **entire** node layer — 125 nodes present, visible, correctly positioned and styled, and not one pixel drawn. *A component reporting correct-looking state while doing nothing at all.*

**The first frame is composed, not revealed.** The graph is fitted **synchronously**, before it is ever painted. The tempting alternative — hold the canvas at `opacity: 0` and fade it in once a frame callback has fitted it — makes *visibility itself* depend on a frame arriving, and its failure mode is a graph that is perfectly correct and completely invisible. That is the bug above, again. A late frame now costs an unfitted moment, which is visible and recoverable.

**The seed showed 16 phone numbers, 7 towers and one person**, because ranking by raw connection count puts the switchboard above the people using it. The backend had already solved this by projecting onto persons before ranking; the interface had not read its own lesson.

**And a caution about tooling rather than code.** Two hours once went to *diagnostics that were themselves wrong* — a pixel check that reported an empty canvas on a graph that was drawing correctly, and a hidden browser pane that silently throttles Cytoscape's whole draw loop. **When the instrument and the subject can both be broken, screenshot the running thing.**

---

# Performance, measured

Every number here was measured on this machine, not estimated.

| Operation | Before | After |
|---|---|---|
| Ingest, 27 KB prose | 5 s | — |
| Ingest, 53 KB prose | 16 s | — |
| **Ingest, 106 KB prose** | **63 s** | **3.8 s** |
| Scaling | quadratic, three times over | **linear** — 8× the document costs 7.4× the time |
| Forty pages + every analytic | — | ~1.4 s |
| 50,000-row CDR | — | ~90 s |
| Betweenness, 2,685 nodes | 36.4 s exact | 2.2 s sampled (k=128) |
| Largest single tool result | 419,224 chars | **12,000 chars, hard ceiling** |
| One entity in the prompt | 23,000 chars | 3 offsets + a count |
| Cost per question | ~$0.10 | **$0.0235** |
| Full-price input tokens per request | everything | **2** |
| Test suite | — | 38 passed, ~35 s |

**Demo case:** 125 nodes (116 entities + 9 documents), 1,148 edges, 61 custody entries, 7 source kinds.

---

# Determinism

The same input must produce the same output, every run, on every machine. Four places where that is enforced deliberately:

1. **No model in the ingest path.** Regex and cue patterns extract identically every time.
2. **Stable node ids and edge natural keys.** Ingesting twice merges rather than doubles.
3. **Fixed seeds** on sampled betweenness (`seed=42`) and Louvain (`seed=42`). The same graph produces the same clusters and the same ranking every run — or the demo says something different each time it is rehearsed.
4. **Byte-exact canonical JSON** in the custody chain.

The one place that is *not* deterministic is the model call itself — which is why every fact it states must come from a tool result, every citation is verified in code, and the findings it leads with were computed before it ever ran.

---

# HTTP API

FastAPI, 22 routes. Live schema while the server is running: `http://127.0.0.1:8000/docs`

**Rules that hold everywhere:**

- **Everything is scoped to a case.** The id is in the path, validated, and every handler opens exactly one store. **The only endpoint that reads across cases is `GET /api/cases`, and it reads metadata only.**
- **Endpoints return contract shapes, not view models.** No route decides how anything looks.
- **The API key is never returned.** Not in a response, not in an error, not in the health check.
- **Timestamps are ISO-8601 with an IST offset.**

| Code | When |
|---|---|
| `200` / `201` | Fine |
| `400` | A confirmation parameter did not match |
| `404` | No such case, entity, or memory entry |
| `409` | Case already exists |
| `415` | A file that is not a readable document at all |
| `422` | Bad case id, or a schema violation |
| **`503`** | **`Suishōdama is unavailable`.** Never a fabricated answer. |

### Health

`GET /api/health` → `{ok, model, model_available, ner, cases}`

> **`model_available` reports whether a key is set, not whether it works.** It constructs a client and nothing more — it never calls the API — so a typo, a revoked key, an empty balance and a dead network all report `true`. **Before a demo, ask Suishōdama a question rather than reading a green tick.**

### Cases

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/cases?officer=` | `[CaseMeta + counts]` |
| `POST` | `/api/cases` | `201` + the created case |
| `GET` | `/api/cases/{id}` | meta + counts + documents + custody verification |
| `PATCH` | `/api/cases/{id}` | update `title` / `case_type` / `brief` / `status` |
| `DELETE` | `/api/cases/{id}?confirm={id}` | deletes the case directory |

```jsonc
// POST /api/cases
{
  "case_id":   "case-mtpjemj1-b7s1",
  "title":     "Suspected trafficking network — Ludhiana to Delhi",
  "officer":   "officer:io_114",
  "case_type": "human trafficking",     // free text
  "brief":     "what the officer wants the agent to know going in"
}
```

**`case_type` and `brief` are the officer's own words, and they are load-bearing** — threaded into the agent's standing brief on every turn. Nothing else in the system knows what kind of crime it is looking at.

### Documents

| Method | Path | Returns |
|---|---|---|
| `POST` | `/api/cases/{id}/documents` | multipart upload → `{document, analytics, counts}` |
| `POST` | `/api/cases/{id}/documents/text` | `{filename, text, kind}` → the same shape |
| `GET` | `/api/cases/{id}/documents` | every document with kind, sha256, size |
| `GET` | `/api/cases/{id}/source?doc_id=&start=&end=` | **the text behind a citation** |

> **`document.warnings` is a list of plain-language strings and must be shown to the officer when non-empty.** An unreadable scan returns **200 with a warning**, not an error — because a document that ingests in silence is worse than one that fails. A file that is not a readable document at all returns **415**.

**The upload is filed under the officer's filename**, not the server's temp name — in the document list, in every citation, and in the custody log. (Twenty-five passing tests and a 125-node demo case did not catch that it once wasn't; the first minute of driving the real interface did.)

### Graph

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/cases/{id}/graph?include_documents=false` | `{nodes, edges, counts}` |
| `GET` | `/api/cases/{id}/nodes/{node_id}` | `{node, edges, neighbours, documents}` |
| `GET` | `/api/cases/{id}/path?a=&b=&max_hops=6` | `[{path, labels, edges, length}]` |
| `GET` | `/api/cases/{id}/timeline?node_id=&start=&end=` | `[{ts, edge_id, summary}]` |

**Document nodes are excluded from `/graph` by default.** They are hubs that connect everything named in a report to everything else, and they make the picture unreadable.

**`documents` on `/nodes/{id}` is deduplicated.** `sources` holds an offset per mention, so mapping it straight to documents once listed the same FIR three times and the interface read *"out of 12 documents"* on a case that holds nine.

### Analytics

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/cases/{id}/analytics?metric=&limit=` | `{influencers, communities, anomalies, findings}` |
| `POST` | `/api/cases/{id}/analytics/recompute` | forces a recompute |

```jsonc
{
  "node_id":   "person:harbhajan_dhillon",
  "label":     "Harbhajan Dhillon",
  "score":     0.222,
  "metric":    "betweenness",
  "estimated": false,
  "why": "Harbhajan Dhillon lies on 22% of the shortest paths in this network; 2 direct contacts; bridges 2 groups that otherwise do not touch; named in no report — appears only in cdr data."
}
```

> **`estimated` is not decoration.** Above 500 projected nodes betweenness is sampled, and `why` then says **"about"**.

### The agent

| Method | Path | Returns |
|---|---|---|
| `POST` | `/api/cases/{id}/ask` | `{question, actor}` → the answer contract |
| `GET` | `/api/cases/{id}/brief` | what the agent says unprompted |
| `POST` | `/api/cases/{id}/findings/{fid}/investigate` | works one finding |

All three return **503** when the model cannot be reached. There is no degraded briefing carrying the findings with an apology attached — that is exactly what was deleted.

> **Nothing calls `/brief` on its own any more.** `POST /ask` is the only thing in the interface that reaches the model; a briefing is obtained by asking for one.

### Memory and conversation

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/cases/{id}/memory?kind=&status=` | conclusions, open questions, evidence requests |
| `POST` | `/api/cases/{id}/memory/{mem_id}/close?status=resolved` | mark one resolved |
| `GET` | `/api/cases/{id}/conversation?limit=200` | `{turns}` — oldest first |
| `DELETE` | `/api/cases/{id}/conversation?confirm={id}` | `{cleared: n}` |

**The thread lives on the case, not in a browser.** Open the case on another machine, or hand it to a colleague, and the conversation is there. Roles are `officer` and `suishodama` — ASCII, matching each other; a database enum is not a place for a macron.

**Clearing it is the demonstration of the whole differentiator.** Clear the thread, ask the same question, get the same answer with the same citations. The custody chain still holds every question that was asked.

### Custody

`GET /api/cases/{id}/custody?limit=` →

```jsonc
{
  "verification": {
    "valid": true, "entries": 61,
    "head": "efc7a1c0…", "broken_at": null, "reason": null
  },
  "entries": [ /* … */ ]
}
```

On a broken chain, `valid` is `false` and `broken_at` names **the entry**, with `reason` saying which of the three checks failed.

---

# The answer contract

What `/ask`, `/brief` and `/investigate` return. Enforced as a JSON schema on the model's structured output, then **checked in code**.

```jsonc
{
  "answer": "Ravi Kumar's phone and Suneel Kumar's phone both hit tower LDH-014 at 22:10 on 3 August. That is proximity, not contact — there is no call between the two numbers.",

  "cited_nodes":    ["person:ravi_kumar", "phone:919876543210", "location:ldh_014"],
  "cited_edges":    ["e_1042", "e_1043"],
  "highlight_path": ["person:ravi_kumar", "phone:919876543210", "location:ldh_014"],

  "claim_type": "evidence",        // "evidence" | "guidance"
  "confidence": "high",            // "high" | "medium" | "low"
  "caveats":    ["Tower co-location is proximity, not contact."],

  "verified": {                    // added by the backend, always present
    "ok": true,
    "dropped_nodes": [],
    "dropped_edges": []
  }
}
```

**If `verified.ok` is false, show it.** An answer whose citations failed is not an answer, and hiding that is the one thing that would make this dishonest.

**`claim_type` — why an answer is allowed to cite nothing.**

| `claim_type` | Must cite? | Meaning |
|---|---|---|
| `evidence` | **yes** | It stated something as fact about this case — a name, a link, a date, a number |
| `guidance` | no | Advice, a plan, a next step, a clarifying question |

*When in doubt it is evidence.* **Citing something that does not exist is a failure in either kind.** A brand-new case with nothing found yet returns a vacuous pass — nothing was checked, so nothing was dropped and nothing failed; reporting a failure there would put a red panel on every new case.

**`highlight_path` is a render instruction** — an ordered list of node ids. Lighting exactly those, in order, is what makes the graph the reasoning rather than a decoration.

> **A finding's `node_ids` is never returned as a `highlight_path`.** A finding's node list is an unordered *set* — not a journey anyone can take — so returning it as a path draws a route that does not exist. A finding answer lights its subject only; the rest is still cited, and the evidence trail shows it.

---

# Agent tools

Every tool takes a `CaseContext` first and is **bound per request, closed over exactly one case.** There is no tool that can name another case. The schemas the model sees come from the Python signatures and docstrings, so that wording is part of the system's behaviour.

### Nine read tools

| Tool | Signature | Returns |
|---|---|---|
| `find_entity` | `(query, type="")` | Entities whose name or id matches, best match first |
| `neighbours` | `(node_id, depth=1, edge_types="")` | Everything within *n* hops, either direction |
| `path_between` | `(a, b, max_hops=6)` | Shortest paths, with edges traversed and human labels |
| `timeline` | `(node_id="", start="", end="")` | Dated events in order |
| `top_influencers` | `(metric="betweenness", limit=10)` | Who matters, and **the reason each one scored** |
| `communities` | `()` | The clusters — the cells inside the network |
| `anomalies` | `(window_hours=24)` | Spikes, handset swaps, one-way accounts, outliers, silences |
| `read_source_doc` | `(doc_id, start=-1, end=-1)` | **The source text behind a citation** |
| `chain_of_custody` | `(limit=12)` | The hash chain and whether it still verifies |

### Four act tools

| Tool | Signature | Effect |
|---|---|---|
| `recall` | `(query="", kind="")` | Read what this case already concluded |
| `record_conclusion` | `(text, node_ids, edge_ids, confidence)` | Write a conclusion into case memory |
| `open_question` | `(text, what_would_answer_it)` | Hold a question it could not settle |
| `request_evidence` | `(what, why)` | Name the document that would settle it |

**All four are hash-logged to the custody chain as `infer`.** They are what make it an assistant rather than a search box: **the officer should never have to explain the case twice, and should never have to read forty pages to find out the system already knew something.**

> **There is no tool that retrieves document text by similarity.** The agent reaches source text only through `read_source_doc`, and only for a document it already found *through the graph*. **Graph first, document second** — that ordering is what stops this being a RAG chatbot with a picture next to it.

**`chain_of_custody` is a read tool because there is no custody panel.** The interface has one chat, so *"has this been tampered with?"* is answered in the conversation like everything else.

The tools are plain functions taking `CaseContext` first; the loop wraps them for the model, and the API and the tests call them directly. **The whole tool surface is exercisable with no API key and no network.**

---

# Graph schema

**Nine node types** · `person` `phone` `organization` `location` `vehicle` `account` `device` `event` `document`

**Eight edge types** · `CALLED` `MESSAGED` `TRANSFERRED_TO` `CO_OCCURS` `OWNS` `LOCATED_AT` `REGISTERED_TO` `MENTIONED_IN`

```jsonc
// Node
{
  "id":         "person:harbhajan_dhillon",   // {type}:{normalised_value} — STABLE
  "type":       "person",
  "label":      "Harbhajan Dhillon",
  "attrs":      { "prose_mentions": 3 },
  "first_seen": "2026-08-01T09:12:00+05:30",
  "last_seen":  "2026-08-14T21:40:00+05:30",
  "sources":    [ { "doc_id": "doc:cdr_114_001", "start": 4821, "end": 4839 } ]
}

// Edge
{
  "id":         "e_1042",
  "src":        "phone:919876543210",
  "dst":        "location:ldh_014",
  "type":       "LOCATED_AT",
  "attrs":      { "basis": "cdr_tower" },
  "weight":     1.0,
  "confidence": 1.0,
  "ts":         "2026-08-03T22:10:00+05:30",
  "sources":    [ { "doc_id": "doc:cdr_114_001", "start": 12043, "end": 12102 } ]
}
```

## Ids are stable, so ingest is idempotent

A node id is `{type}:{normalised_value}`. The same real-world entity always produces the same id, so ingesting a document twice **merges into the existing node** instead of creating a second one.

> **All entity resolution in this system is that one property.** There is no fuzzy matching — a deliberate choice, because a false merge in an evidence system is worse than a missed one.

| Type | Normalisation |
|---|---|
| `person` | lowercase, split on non-alphanumerics, **leading honorifics stripped** (`shri` `smt` `dr` `late` …) |
| `phone` | Indian mobiles → `91` + ten digits; `+91`, `091`, `0`-prefixed and bare forms collapse. Anything else keeps its digits, so a landline still gets a stable id rather than being dropped |
| `vehicle`, `device` | all separators removed — registration numbers have no real word boundaries |
| everything else | slugified |

Document nodes use the prefix **`doc:`**, not `document:`, because `sources[].doc_id`, `custody.ref` and `read_source_doc` all speak that form.

## No fact without provenance

**No node and no edge may exist with an empty `sources` array.** Enforced in the schema and again in the store — a sourceless fact raises, it does not warn.

Every extraction carries `{doc_id, start, end}` — character offsets into the extracted text. That is not bookkeeping: it is what makes a citation click through to the line it came from, and what makes the whole verification chain possible.

## `confidence`, and what moves it

| Source | Confidence |
|---|---|
| A CDR row, a bank transaction | 1.0 — it is a record, not an inference |
| Co-accused on one charge sheet | 0.85 |
| A phone beside a name in prose (`OWNS`) | 0.6 |
| A social handle's display name | 0.45 |
| Text proximity (`CO_OCCURS`) | 0.4 |
| **Anything inferred from an intelligence report** | **× its Admiralty grading** |

---

# Setup

**Stack** — Python 3.11+ (verified on 3.12) · FastAPI · NetworkX · SQLite · Anthropic SDK
**Frontend** — Node 20.19+ or 22.12+ · React 19 · Vite · TypeScript · Tailwind v4 · Cytoscape.js · TanStack Query · React Router · Lucide

**Everything runs from the repo root**, not from `backend/` — `data.synthetic` and `backend.*` are one import tree.

```bash
python -m venv .venv
.venv\Scripts\activate                              # Windows; source .venv/bin/activate elsewhere
pip install -r requirements.txt

cp .env.example .env                                # then put the key in .env

python -m data.synthetic.generate --case demo-114   # build the demo case
python -m pytest tests -q                           # 38 passed
uvicorn backend.api.main:app --reload               # http://127.0.0.1:8000/docs
```

Second terminal, still from the repo root:

```bash
pnpm --dir frontend install
pnpm --dir frontend dev                             # http://127.0.0.1:5173
```

If `pnpm` is not on your PATH: `corepack enable` once, or use `npx pnpm@10`. **Do not `npm install` in `frontend/`** — it writes a second lockfile beside `pnpm-lock.yaml` and the two disagree.

Frontend checks: `pnpm --dir frontend build` · `pnpm --dir frontend lint`

## What needs a key and what does not

**Most of it runs without one.** Ingest, the graph, analytics, findings, custody and the whole brain panel need no model at all, so a cold clone can build the demo case and explore it.

**`/ask`, `/brief` and `/investigate` return 503** without a key or a network. That is deliberate — the offline path was deleted, not disabled.

## The API key

- Read from the environment as `ANTHROPIC_API_KEY`, from `.env`, which is gitignored from the first commit.
- **It must never appear in this file, in any committed file, in a log line, in an error message, or in a chat.** This repo being private is not protection — git history is permanent.
- If it is ever committed it must be **revoked in the console**, not just deleted from the file.
- `GET /api/health` reports whether a model is reachable and which NER layers are live. **It never reports the key.**

## Optional: spaCy

The always-on cue patterns handle FIR prose. spaCy adds recall on documents shaped differently:

```bash
pip install spacy && python -m spacy download en_core_web_sm
```

## Tunables

| Variable | Default | What it bounds |
|---|---|---|
| `ANTHROPIC_MODEL` | `claude-sonnet-5` | The model |
| `SIH_EFFORT` | `high` | Reasoning effort |
| `SIH_MAX_TOOL_ITERATIONS` | `14` | The tool loop — this is the cost ceiling |
| `SIH_CONVERSATION_TURNS` | `24` | How much thread the model sees |
| `SIH_BETWEENNESS_EXACT_MAX` | `500` | Above this, betweenness is estimated |
| `SIH_BETWEENNESS_PIVOTS` | `128` | Sampled pivots when it is |
| `SIH_CASES_ROOT` | `./data/cases` | Where cases live |

## Repo layout

```
backend/
  ingest/      readers · patterns · ner · structured · pipeline
  graph/       schema (frozen) · store (SQLite) · nx_adapter (NetworkX)
  analytics/   metrics (centrality, Louvain) · anomalies (findings)
  agent/       loop (the model) · tools (13) · contract (verification)
  custody/     chain (hash-linked, append-only)
  api/         main (FastAPI, 22 routes)
  case.py      case lifecycle · config.py  paths and the isolation guard
frontend/src/
  pages/Chat.tsx          the whole product — one conversation per case
  components/Brain.tsx    the case's graph, interactive
  components/Evidence.tsx the trail from a sentence to a line in a document
data/synthetic/
  generate.py  the demo case · tamper.py  the custody beat
tests/
  test_core.py  38 guards
docs/
  demo-fraud-complaint.txt   the second case used in the demo
```

---

# The demo case

**The demo is the dataset.** No public FIR/CDR corpus exists and real crime data would be a legal problem — so we generate one, **with a ground truth we planted.** That is the only reason anyone can stand in front of a judge and say *"the system found X"* rather than *"the system produced some output"*.

```bash
python -m data.synthetic.generate --case demo-114
```

**125 nodes** — 116 entities and 9 documents — **1,148 links**, **61 custody entries**, across all seven source kinds.

The scenario is a trafficking network moving women from villages around Ludhiana to a receiving group in Delhi. **It is trafficking because the evaluating department is NCRB Women Safety Division, and for no other reason.** Nothing in the engine knows what trafficking is — it knows identifiers, links, timing and structure, which every investigation has. Adding a second scenario means adding a builder, not touching the engine.

## What is planted

- **A kingpin named in no FIR.** He exists only as a subscriber name inside a CDR export, never contacts a foot soldier, and the only way to reach him is betweenness.
- **Two clusters with no direct edge.** Ludhiana and Delhi share no call, no transfer, no document. Every route between them runs through the intermediaries or through one account.
- **A tower co-location** on the night of the incident — deliberately *proximity, not contact*. The system must say so, and does.
- **A call-volume spike**, a financial trail crossing the clusters through a single account, two repeat offenders with shared charge sheets, an unattributed social handle three people DM, and a C3-graded intelligence report that says an organiser exists and cannot name him — **the system names him anyway**, from CDR metadata the report never had.
- **Ordinary noise**: family calls, salary credits, unrelated numbers, so the structure is not visible by eye in the raw files.

**Nothing added after the first build crosses the Ludhiana/Delhi divide.** A second bridge would destroy the kingpin's betweenness, which is the whole of the second demo query. A test enforces it, so whoever adds the next row finds out there rather than on stage.

## The trap worth knowing cold

He is **third** by raw betweenness (0.222), behind two people named in four and seven documents respectively. **Ranking alone would have named the wrong person, and naming her proves nothing** — the officer already knows who she is.

What the system leads with is the *finding*: high betweenness **and** absent from every report. If a judge asks *"why him and not the top of your list"*, that is the answer, and it is better than the one they expected.

---

# Demo run sheet

**Nine minutes of content. Rehearse it three times on the machine that will run it.** A demo that has been run three times beats a better system that has been run once.

## 0 · Before you speak

Twenty minutes before, in this order, and **do not skip the second one**:

```bash
python -m data.synthetic.generate --case demo-114   # rebuild the case, clean
python -m pytest tests -q                           # 38 passed
uvicorn backend.api.main:app --port 8000            # terminal 1
pnpm --dir frontend dev                             # terminal 2
```

1. Open `http://127.0.0.1:5173` and click the case. The line under the composer must read **116 entities · 1,148 links · 9 documents**.
2. **Check the assistant is alive.** Ask it anything and make sure an answer comes back. **There is no offline mode**: with no key or no network, Suishōdama says it is unavailable and nothing else in the demo works. Check before the room fills, not at minute four.
3. Copy `tests/fixtures/fir-114-text.pdf` to the desktop, renamed to something an officer would recognise — `fir_114_003.pdf`. You will upload it live.
4. Have `docs/demo-fraud-complaint.txt` to hand for §6.
5. **Open a third terminal** in the repo root for the tamper command. Do not make the room watch you find a terminal.
6. **Close every other tab.** The chat and the graph are the demo.

**Screen width matters.** The graph panel needs **1024px or wider**; below that the conversation is the whole screen and the split — the entire argument — is gone.

## 1 · The problem, in their words *(45s)*

Do not open with the architecture. Open with the officer.

> "An investigating officer in a trafficking case is holding an FIR, two CDR exports, a bank statement and a surveillance log. Every connection he needs is already in that pile. He will not find them, because finding them means holding four hundred phone numbers in his head at once. NCRB's own statement says it: the data exists and the links are missed."

Then the one sentence that separates this from the other submissions:

> "Everyone will show you a dashboard of that pile. A dashboard cannot be asked anything. We give every case its own investigator — its own graph, its own memory, and an assistant that has already read all of it."

**Do not say "knowledge graph" yet.** Say it after they have seen one.

## 2 · The officer's one job *(60s)*

**Point at the line under the composer first.**

> "That is this case's brain. Not a chat history — a graph on disk that this case owns. Watch what happens when he hands it one more document."

Upload the PDF live — drag it onto the window. Then **stop and let them read the line**:

> **fir_114_003.pdf — the brain grew by N entities and M links.**

> "That is the officer's whole job. Hand it a document. Everything after this happened without anyone asking for it — and it is *permanent*. Document forty is not competing for room with document one, the way it would be in a chat window. It is making document one worth more, because a link needs both ends."

Then ask: **What is in this case?** It names the nine documents and the seven kinds. **Say that number out loud: seven of seven.**

**If the upload fails, do not debug it.** Say "that ran this morning, here is the document it produced" and move on. You lose fifteen seconds. You lose the room if you start reading a stack trace.

## 3 · Query one — the graph causes the answer *(2 min)*

**This is the one that proves it is not a chatbot with a picture next to it.**

> **How is Ravi connected to the Ludhiana account?**

While the answer lands, say nothing. Let them watch the path light up hop by hop. Then:

1. **Read the path aloud from the graph, not from the text.**
2. Click **Rests on 5 entities and 12 links**. Open one, then **Open the line it came from**. The source document opens on the exact line.
3. Say the thing that matters most in the whole demo:

   > "It cannot say anything the graph does not contain. Every id in that answer is checked against the graph before you see it, and anything that does not exist is stripped and reported. That is why this is not a chatbot."

**Ask it the way a person speaks — that is the point.** **Never type an id on stage.** If you do, you have shown them a database with a text box on it.

## 4 · Query two — the moment *(2 min)*

**Everything before this was setup.** Slow down.

> **Who matters most in this case?**

The answer names **Harbhajan Dhillon**.

1. Open the evidence trail and expand him. **Read out of 1 document** — a call log. No FIR, no surveillance report, no statement.
2. Ask plainly: **"Which documents name him?"** One. Let that sit.
3. Say it:

   > "No officer reading the reports in this case would ever have written his name down. He is not in them. He is a row of metadata in a phone log, he owns two SIMs, and twenty-two per cent of every shortest path in this network runs through him — because he is the only thing joining two groups that otherwise never touch."

**Then stop talking for two seconds.** That is the moment the room understands what the system does.

**If a judge asks how a man with two links can be that central** — that is the person-projected graph, and it is worth knowing cold. A man and his SIM are not two actors; on the raw graph every path would stop dead at the handset and he would score near zero. **That single design choice is the difference between finding him and not.**

## 5 · The theme — chain of custody *(60s)*

They will ask where the blockchain is. Answer it before they do.

> **Has anything in this case been tampered with?**

It answers from the chain: intact, and how many entries it covers.

> "Blockchain and Cybersecurity is the theme. Evidence does not need a token, it needs to be tamper-evident. Every document that arrives and every conclusion the system draws is hash-chained to the one before it."

Then break it, live:

```bash
python -m data.synthetic.tamper --case demo-114
```

Ask again. **It names entry 2** — not "a problem somewhere", the exact entry, with the reason. Then put it back:

```bash
python -m data.synthetic.tamper --case demo-114 --restore
```

Ask once more: intact. **Restore is byte-identical**, so the demo carries on with this case straight afterwards — there is a test that fails if it ever stops being.

Ten seconds of doing beats a minute of claiming. (The tool refuses to run on any case not marked synthetic, which is worth saying out loud if a judge looks alarmed that a "break the evidence" command exists at all.)

## 6 · It is not a trafficking tool *(45s)*

The shortest section, and it closes a real objection.

Click **+ New case**, drop `docs/demo-fraud-complaint.txt` on the window, ask **"what is this?"**. The brain line goes from nothing to eleven entities. Nothing from the trafficking case is in it, and nothing from it reaches the trafficking case.

> "Nothing in the engine knows what trafficking is. It knows identifiers, links, timing and structure. The case carries its own type and the officer's own brief, and that is what the assistant reasons in the register of. A fraud case, a homicide, a missing person — same engine, different brain."

**If you are short on time, cut this section, not §4.**

## 7 · Close *(30s)*

> "One officer, one case, one assistant that has read everything and can be asked the same question again in six months and give the same cited answer. Not a dashboard of a pile of documents. An investigator you can hand the pile to."

## If something breaks

**The rule: never debug in front of the room.** Every failure has a next sentence; say it and keep moving.

| Breaks | Say | Then |
|---|---|---|
| Upload fails | "That ran this morning — here is what it produced." | Go to §3. |
| An answer is slow | Nothing. Talk over it: the officer's problem, the nine documents. | Wait. |
| An answer is wrong or thin | "It only says what the graph contains — let me show you the graph." | Ask query 1. |
| The graph panel does not open | The answer had no route to show. | Ask query 1; its answer always has one. |
| Suishōdama says it is unavailable | "The assistant is a model call; the case is on disk and untouched." | Check key and network. **Nothing else works until it is back.** |
| The API is down | "Two-terminal setup — one moment." | Restart uvicorn. Case data survives. |
| A judge asks for OCR on a scan | "It detects a scan and tells the officer it could not read it, rather than accepting it silently. Reading it means OCR, which puts a lossy step in front of the evidence — that is a decision, not an oversight." | |
| A judge asks about real data | "Synthetic, deliberately: no public FIR/CDR corpus exists and real crime data is a legal problem. Because we planted the structure, we can prove the system found it." | |

## Questions to expect, and the honest answer

**"Is the AI making this up?"** — No, and it is structurally prevented from doing so. Findings are computed from the graph before the model sees them. Every citation is checked against the graph before display and stripped if it does not exist. Open the evidence trail and click through to the line in the document: **that trail is the answer to this question.**

**"So it is ChatGPT with our documents pasted in?"** — No, and this is the distinction worth being precise about. **Nothing is pasted in.** The case has a graph on disk and the assistant queries it with tools, one call at a time, so the amount of text the model ever sees is fixed — it does not grow as the case grows. **Clear the conversation and ask again: same answer, same citations.** The knowledge is in the case, not in the thread.

**"How is this different from a link-analysis tool?"** — A tool visualises what you already suspect. This one volunteers what you did not ask about — §4 is a man no officer would have written down.

**"What if the data is wrong?"** — Every node carries its source and its confidence, and the confidence differs by source: an intelligence tip from an ungraded source does not enter at the confidence a bank record does. A tower co-location is reported as proximity and never as contact.

**"How long to ingest a real case file?"** — About **1.4 seconds** for forty pages including every analytic, and it is **linear in document size** — a 50,000-row CDR is about ninety seconds. No model in the ingest path is the reason, and a test fails if one appears or if the scaling stops being linear.

**"Does it scale?"** — One SQLite file per case, and a case is the unit. **It scales the way case files do: sideways.**

## The interface, and why there is so little of it

**One chat. That is the whole product.** If a judge asks where the rest of it is, that question is the pitch:

> "An investigating officer is not going to learn six screens. He hands it a document and he asks it things, the way he would ask a colleague who had already read the file. Everything you would expect to be a tab — the documents, the findings, the chain of custody, an entity's history — he gets by asking for it, which is one skill instead of six."

**The line under the composer is the argument in one sentence.** It is the only number in the product, it is there because it *changes*, and §2 is built around watching it change.

---

# Testing

```bash
python -m pytest tests -q     # 38 passed in ~35s
```

The suite is not a coverage exercise. Every test is a **guard on a property the product claims**:

- The same number written four ways is one entity; a fact with no source is rejected; ingesting the same document twice does not double the graph.
- **The kingpin is named in no report and the system leads with him.**
- Ravi reaches the Delhi account **through the tower**, and no call between the two numbers exists — so the system cannot claim contact.
- Two cases of different kinds share nothing. Altering one custody entry breaks the chain **at that entry**.
- A real two-page FIR in PDF reaches the graph and its citation opens. **A scan says it could not be read** instead of ingesting in silence.
- An upload over HTTP is filed under **the officer's** filename — in the document list, in every citation, and in the custody chain.
- **Ingest is linear in document size**, and the guard fails if any of the three quadratics returns.
- **No tool can put more than its ceiling in front of the model**, and what it does return is still valid JSON.
- A man named 400 times keeps three offsets and the count — and the offset that is kept still opens.
- Betweenness is exact on the demo case and **says "about"** when it is an estimate.
- **The universal prompt carries no case in it** — the test fails on any planted name, any ten-digit identifier, or any concrete node id.
- Influence is scored on people, not on SIM cards. The broker threshold ranks people against people.
- No source added later re-wires the two clusters.
- A conversational answer is not branded unverified; a brief on an empty case still carries the `verified` block.
- The tamper tool refuses a case that is not synthetic, and restores byte-identically.

## How we know the guards are awake

**Every new guard is mutation-checked**: revert the fix, watch the test fail, restore the fix.

On the last pass, **three of five new guards did not fail.** Two asserted against the very constant they were testing — which passes at any setting — and one had a bar loose enough to sit on both sides of the bug. All three were rewritten.

> **A guard that has never failed is not a guard.**

---

# What it does not do

Stated here so nobody has to discover it in a demo.

- **A scanned PDF is announced, not read.** No OCR. Reading one means putting a lossy step in front of the evidence, which is a decision, not an oversight.
- **A 50,000-row CDR takes about ninety seconds** to ingest and recompute. Linear and honest, but not instant — and nothing in the interface tells the officer how long a large file will take.
- **There is no offline mode.** No key or no network means no assistant. The key and a working connection are demo-day requirements, not to-do items.
- **The self-verification checks citations, not assertions.** A sentence carrying no ids passes through untouched.
- **The cost ledger is a floor, not a bill.** Usage is logged once per question, on the final message after the tool loop has finished — so each row is the *last request*, not the sum over up to fourteen iterations. The vendor console holds the real number.
- **`prose_mentions` counts prose only.** A structured row's mentions are not counted, and the attribute name says so.
- **The cue NER reads two intelligence frames, not every one.** Widening the regex to leap a clause reintroduces a bug we already paid for.
- **Entity resolution is exact-match on normalised ids.** No fuzzy matching, by choice.
- **The graph panel needs 1024px or wider.** Below that the conversation is the whole screen.

---

# Decisions

**Every design decision, its reason, and its date.** The numbers are referenced from source comments (`D3`, `D22`, `D30`…), so they are stable and are never renumbered.

A decision without its reason gets re-opened by the next person who thinks the alternative looks better.

## The shape of the product

| # | Decision | Reason | Date |
|---|---|---|---|
| **D1** | Per-case agent, not a global dashboard | A visualisation cannot be asked anything, and the investigator's problem is not seeing the network once but interrogating it over months. **The whole differentiator.** | 09-03 |
| **D10** | The agent acts; it does not just answer | *"it shouldnt just be system prompt calling claude… not just a prompt."* Per-case memory across sessions, recorded conclusions, held questions, named evidence gaps. | 09-04 |
| **D12** | The engine is crime-type agnostic; the case carries its own type and brief | *"it should work for any case… so it mold in every case possible."* Nothing in ingest, graph, analytics or the agent knows what trafficking is. | 09-04 |
| **D25** | One chat interface. No section rail, no panels. | *"just one chat interface and option to graph… one clean chatgpt like interface, but great shit at backend."* Six navigable sections is a filing cabinet, and an officer under time pressure does not explore a filing cabinet. | 09-05 |
| **D26** | Nothing is invoked by syntax. No commands, no ids typed by a human. | *"the bot should only fire from chat message, because we are making for non technical peopleee."* The moment a command language exists, the interface has two classes of user. | 09-05 |
| **D29** | The case's brain is a visible, growing thing — not a context window, and not a dashboard | *"we are just a bot doing calls based on brain and graph of case so its nothing like context window anywheree."* The fortieth document makes the first worth more. | 09-06 |
| **D44** | Nothing speaks unprompted | *"just remove any always running or unprompted callsss… an officer can ask it anything when needed."* Two typed questions had produced five billed calls, three unprompted. | 09-06 |
| **D47** | It volunteers | The pitch was always that this surfaces what you did not ask about — **and the prompt never said so.** One clause, and the first live answer named someone not in the ground truth. | 09-06 |

## The engine

| # | Decision | Reason | Date |
|---|---|---|---|
| **D2** | SQLite + NetworkX. Not Neo4j. | A service that must install, authenticate and stay up is the wrong dependency for six people building remotely across 24 hours. Per-case isolation becomes *a different file* instead of a permissions model. | 09-04 |
| **D3** | The graph causes the answer; it does not illustrate it | Otherwise the split screen is theatre and a judge finds out in one question. **Enforced by the contract, not asked for in a prompt.** | 09-04 |
| **D4** | No LLM in the ingest path | Cost, speed, determinism. The same document must extract identically every time. | 09-03 |
| **D11** | Findings are computed from the graph; the model narrates them | Keeps D3 structurally true, and keeps the analytics layer useful with no key, no network and no budget. | 09-04 |
| **D13** | Centrality is scored on a person-projected graph | A kingpin whose only edge is `OWNS` to his own SIM scores near zero on the raw graph. **A man and his SIM are not two actors.** | 09-04 |
| **D15** | Proximity linking is prose-only, and claims the nearest name only | Both learned by measurement: co-occurrence over a CDR added **606 meaningless edges**; linking every nearby person to a number produced a real-looking false path. | 09-04 |
| **D18** | A document we could not read must say so | A silent scan is **worse than an error**, being indistinguishable from a document that had nothing in it. | 09-05 |
| **D19** | The last two sources introduced no new node or edge type | The schema is frozen and the interface is built against it. A handle is an `account`, a prior case is an `event`. **If you are about to add one, this is why it is not there.** | 09-05 |
| **D20** | An intelligence report is graded, and what it implies is discounted | An uncorroborated tip was entering at exactly the confidence a bank record does. The factor is the **lower** of the two Admiralty axes, never their product. | 09-05 |
| **D21** | The hidden-broker threshold ranks people against people | "Top five" quietly meant "top two people", **and the more documents an officer uploaded the fewer brokers the case could surface.** | 09-05 |
| **D31** | Provenance capped at three offsets per document; the count kept | One entry per mention made ingest quadratic and put a 23,000-character node in front of the model. | 09-06 |
| **D32** | Betweenness exact below 500 projected nodes, estimated above — and says which | 36.4 s of a 38.7 s recompute, and a recompute runs after every ingest. **An estimate is never read out as a measurement.** | 09-06 |

## The agent, and what it costs

| # | Decision | Reason | Date |
|---|---|---|---|
| **D5** | Anthropic API only (`claude-sonnet-5`) | Cost is bounded *because* of D4 — we send graph subgraphs, never documents. | 09-04 |
| **D22** | There is no offline mode and no fallback. Ever. | *"why do we need that offline analysis anywhere, dont keep that at all."* **A degraded impostor is worse than an outage, because the officer cannot tell which one he is talking to.** | 09-05 |
| **D27** | The conversation is stored on the case, not the browser | The officer was reading a thread and talking to something with no memory of it. The referent set is carried forward **as ids** — asking a model to remember harder is not a mechanism. | 09-05 |
| **D30** | Every tool result is bounded before it reaches the model | `timeline` put **419,224 characters** into one call on a small case. **If case size decides how much text reaches the model, the case is the context window.** | 09-06 |
| **D42** | Prompt caching, and the system prompt split to make it work | Caching is a prefix match, so one string would have thrown the entry away on every ingest. **~$0.10 → $0.0235 a question.** | 09-06 |
| **D45** | Computed findings go in the standing brief, and a finding outranks a ranking | The `hidden_broker` finding was **#1 of 26** and the model never saw it. Paid for by slimming memory entries. **Net cost: negative.** | 09-06 |
| **D46** | The universal prompt carries no case in it | *"no demo case names or shit s anywhere pleasee, it a real peak tool after all."* An officer working a fraud was being handed someone else's case as the model of a good answer. **18 characters shorter**, and guarded by a test. | 09-06 |

## Evidence and trust

| # | Decision | Reason | Date |
|---|---|---|---|
| **D6** | Hash-chained custody as the theme answer | Correct for evidence on its own merits, and it answers *Blockchain & Cybersecurity* **without bolting on a token.** ~100 lines. | 09-04 |
| **D23** | A finding's `node_ids` is never an answer's `highlight_path` | A finding's node list is an unordered **set** — not a journey anyone can take. Returning it as a path draws a route that does not exist, **which is D3 inverted.** | 09-05 |
| **D33** | Anything the officer cannot see, he can ask for — including the custody chain | D25 removed every panel, and with them the only surface for the theme beat the round is judged on. | 09-06 |
| **D41** | No web tool. The officer browses; we make what he brings back useful. | *"lets not keep it anywhere for now, we can tell user to go through browser themselves."* Buys a claim worth more than the feature: **the only thing that reaches the network is the model call.** | 09-06 |

## The interface

| # | Decision | Reason | Date |
|---|---|---|---|
| **D16** | React + Vite + TypeScript, Tailwind v4, Cytoscape.js, TanStack Query, React Router, Lucide | Survived the pivot intact — the stack was never the problem. **Radix removed**: the pivot deleted every dialog, dropdown, tab and tooltip it was there for. | 09-05, rev. 09-06 |
| **D24 → D43** | One name: `Suishōdama` — capital S, macron. No logo. | **The spelling is fixed by the team name on the SIH submission form**, so the product carries what the judges have on paper. The source said `Suishōdama` while two CSS classes rendered it lowercase — **which a grep cannot see and only looking at it caught.** Stored role is ASCII `suishodama`: a database enum is not a place for a macron. | 09-05, superseded 09-06 |
| **D28** | Near-colourless; Evidence Amber is the only saturated colour | An officer reads text here for an hour. **The one colour in the product is also the one claim that matters.** | 09-05 |
| **D34** | The graph opens on a readable core and opens further where he asks it to | One cloud of identical grey dots is **a picture of *having* a graph, not a way of reading one.** Nothing already on screen moves. | 09-06 |
| **D35** | A type is drawn, not written | Nine shapes, desaturated tone second — survives a projector and a colour-blind judge. **In a diagram the type of a thing *is* meaning**, so D28 is kept rather than bent. | 09-06 |
| **D36** | Every node opens to what is inside it | The entity panel lives *inside* the brain panel, never beside it. **A thing clicked on the picture and a thing read in a sentence are the same thing.** | 09-06 |
| **D37** | The brain has a control of its own, above the conversation | It could only be opened by something that required something to have happened first. An officer who wants to *look* had nowhere to press. | 09-06 |
| **D38** | The graph answers the hand | *"should be appealing to interact."* **Reverses** an earlier "a thing to read, not to rearrange" — an officer's own arrangement of a network is part of how he thinks about it. Four levels deep is reversible. | 09-06 |
| **D39** | Cytoscape's press feedback is off, and nothing replaces it with a shape of its own | *"those circles whenever i slide or click"* — the loudest thing on a near-colourless screen, and **it covers the thing being pressed to say "you pressed".** Feedback follows the node's real shape now. | 09-06 |
| **D40** | The first frame is composed, not revealed | Fading in on a frame callback **makes visibility itself depend on a frame arriving, and its failure mode is a graph that is perfectly correct and completely invisible.** That bug has already happened twice. | 09-06 |

## The demo

| # | Decision | Reason | Date |
|---|---|---|---|
| **D7** | The demo case is trafficking / repeat-offender | The department is NCRB **Women Safety Division**. Same code, story built for the actual evaluators. | 09-04 |
| **D8** | Synthetic data only, with a planted structure | No public corpus exists and real crime data would be a legal problem. **Planting a known network is what makes the demo provable.** | 09-04 |

## Superseded, and why they are still here

| # | Decision | What happened |
|---|---|---|
| **D9** | ~~This README is the only shared context file~~ | True while six people built against it in parallel. The build is done; this file is product documentation now, not a shared scratchpad. |
| **D14** | ~~The backend builds no UI and makes no design decisions~~ | True while the front end belonged to someone else. It changed hands and was then pivoted. |
| **D17** | ~~Calm Civic Forensic visual language; light mode only~~ | The light-only half survived and is now D28. The palette, the 60/40 split and the six sections it named describe a product that no longer exists — **deleted, not archived.** |

---

<div align="center">

**Suishōdama** · SIH26189 · NCRB Women Safety Division

*One officer, one case, one assistant that has read everything —
and can be asked the same question in six months and give the same cited answer.*

</div>
