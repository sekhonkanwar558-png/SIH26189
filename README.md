# SIH26189 — AI-Powered Criminal Network Analysis System

**Smart India Hackathon 2026 · Ministry of Home Affairs → NCRB, Women Safety Division · Software · Blockchain & Cybersecurity**

> ## ⚠️ Every agent working in this repo: read this file to the end before you write anything.
>
> There is no other shared context. Four people are building this in parallel, each with their own AI agent, in a 24-hour window. **This file is the only thing keeping those agents in pace with each other.** If you skim it, you will re-decide something that is already decided, invent a second version of a schema that already exists, or build a thing someone else is building right now.
>
> **Section 0 tells you how to work here. Read it first.**

---

## 0. How to work in this repo

**Read this before your first action in any session. These rules exist because four agents are editing one project at once.**

### 0.1 Before you start

1. **Read this entire file.** Not the section that looks relevant — all of it. The decisions in §4 and the contracts in §5 are what stop your work from colliding with someone else's.
2. **Check §11 (Current State)** to find out what actually exists right now. This file describes the whole project; §11 tells you which parts are built.
3. **Check §10 (Ownership)** before you write code. If your workstream has an owner and it isn't you, do not build in it — say so to your human and ask.

### 0.2 The rules that keep us in pace

**Do not re-decide what is in §4.** Every decision there carries the reason it was made. If you think a decision is wrong — and some of them may be — say so to your human and let them raise it. Do not quietly implement the alternative because it looks better to you. A repo where two agents each chose the "obviously better" database has no working demo at 11:00 on the 9th.

**The contracts in §5 are frozen.** The graph schema, the tool API and the answer shape are how six people's work fits together. If you genuinely need to change one, that is a conversation, not a commit: change §5 first, tell everyone, then write code. Code that disagrees with §5 is a bug, even if it runs.

**Never invent a fact into this file.** If you don't know something, write `UNKNOWN` and say what would answer it. A confident wrong line here propagates into four agents at once. That is the single worst failure mode this repo has.

**Record what you changed before you finish.** Append to §12 (Changelog). One line: what you built, what you changed in this file, anything the next agent must know. An agent that builds something and doesn't write it down has broken pace for everyone who starts after it.

**If you changed a contract, a decision, or the current state — update this file in the same commit as the code.** Not afterwards. Documentation that lags by even one commit is how the next agent gets a wrong answer.

**Never commit a secret.** See §8. The API key belongs to a teammate, not to this project.

### 0.3 What your training data will get wrong

You are likely to write these from memory and be wrong. They cause silent failures or 400s:

| You may recall | Correct for this project |
|---|---|
| `thinking: {type: "enabled", budget_tokens: N}` | `thinking: {type: "adaptive"}` — `budget_tokens` is **rejected with a 400** on Sonnet 5 |
| Assistant message prefill to force output shape | **Removed** — returns 400. Use `output_config.format` (structured outputs) instead |
| `output_format: {...}` | `output_config: {format: {...}}` |
| A date-suffixed model id | The model string is exactly `claude-sonnet-5` — no date suffix |
| `client.messages.create` loop written by hand | Prefer `client.beta.messages.tool_runner` with `@beta_tool` — it drives the tool loop for us |
| `client.messages.parse(output_config=...)` | The **helper** takes `output_format=<PydanticModel>`; **`messages.create` and `tool_runner` take `output_config={"format": {...}}`**. Both exist, they are not interchangeable, and mixing them is a 400 |
| `tool_runner` can't do structured output | It can — it accepts `output_config`, `thinking`, `system` and `max_iterations`. `runner.until_done()` returns the final message. Verified against `anthropic` 1.3.0 |

If you are unsure about an Anthropic API shape, **do not guess** — check the official docs rather than your recollection.

**Two things this project does that are not the model's job, and must not be moved into a prompt:** citations are verified against the real graph in code after the model answers (`agent/contract.py`), and findings are computed from the graph before the model sees them (`analytics/anomalies.py`). Asking a prompt to be truthful is not the same as checking.

---

## 1. What we are building, and what we are judged on

### 1.1 The problem statement, verbatim

Do not paraphrase this. It is the ground truth and the evaluators wrote it.

> **Background.** Modern criminal activities are increasingly organized and interconnected. Criminals often operate through networks involving associates, intermediaries, financial channels, communication links, locations, and events. Law enforcement agencies collect large volumes of data from sources such as: FIRs and police reports · Call Detail Records (CDRs) · Financial transaction records · Surveillance reports · Social media intelligence · Criminal history databases · Intelligence agency reports.
>
> Despite having access to this information, investigators frequently face challenges in identifying hidden relationships among suspects because the data is fragmented, unstructured, and distributed across multiple systems. Manual analysis can be slow, labor-intensive, and prone to missing critical connections. With advances in Artificial Intelligence (AI), Machine Learning (ML), Natural Language Processing (NLP), and Graph Analytics, it is now possible to automatically discover relationships, detect patterns, and generate insights that can assist investigators in understanding criminal networks more effectively.
>
> **Description.** The objective is to develop an AI-powered system that can analyze large volumes of criminal and intelligence-related data to uncover hidden networks and relationships among individuals, organizations, locations, and events.
>
> **The system should:**
> - Collect and process data from multiple sources.
> - Extract important entities such as people, locations, vehicles, phone numbers, and organizations.
> - Build relationship maps showing how different entities are connected.
> - Identify key individuals who play influential roles within criminal networks.
> - Detect suspicious patterns and unusual activities.
> - Assist investigators by providing visual and analytical insights.
>
> **Expected Solution.** Develop an AI-powered system that automatically analyzes structured and unstructured crime-related data to uncover criminal networks, identify key influencers, detect suspicious patterns, and provide actionable intelligence for investigators.

**Every bullet above is a checkbox a judge will tick.** §3 maps each one to the component that satisfies it. If you build something that satisfies none of them, it does not matter how good it is.

### 1.2 Facts about the statement

| | |
|---|---|
| **PS number** | SIH26189 |
| **Organisation** | Ministry of Home Affairs |
| **Department** | National Crime Records Bureau (NCRB), **Women Safety Division** |
| **Category** | Software |
| **Theme** | Blockchain & Cybersecurity |
| **National idea-submission deadline** | 30 September 2026 |
| **Ideas submitted nationally** (read 2026-09-03) | **2 of 500** |

Two things follow from that table and both shape the build:

**The department is Women Safety Division, not "MHA" generally.** The people evaluating this work on trafficking, repeat offenders, and cases that cross jurisdictions. Our demo case is built for them — see §9.

### 1.2a Every source in §1.1, and what reads it

The background paragraph lists **seven** sources by name. Each is a checkbox, and this is where each one stands — as of 2026-09-05 all seven have a handler and all seven appear in the demo case.

| Source named in §1.1 | `kind` | Reader | What it produces |
|---|---|---|---|
| FIRs and police reports | `fir` | prose + cue NER | entities, `MENTIONED_IN`, weak `CO_OCCURS`, `OWNS` by proximity |
| Call Detail Records | `cdr` | `structured._ingest_cdr` | `CALLED`, `MESSAGED`, `REGISTERED_TO`, `LOCATED_AT`, subscriber `OWNS` |
| Financial transaction records | `financial` | `structured._ingest_financial` | `TRANSFERRED_TO`, holder `OWNS` |
| Surveillance reports | `surveillance` | prose + cue NER | as FIR |
| **Social media intelligence** | `social` | `structured._ingest_social` | handles as `account`, `MESSAGED` for DMs and replies, weak `CO_OCCURS` for mentions and follows, `LOCATED_AT` for geotags |
| **Criminal history databases** | `history` | `structured._ingest_history` | prior cases as `event`, `MENTIONED_IN` per accused, **`CO_OCCURS` between co-accused**, `LOCATED_AT` to the station |
| **Intelligence agency reports** | `intelligence` | prose + `readers.read_grading` | as FIR, **discounted by the report's Admiralty source grading** (D20) |

The three in bold were built 2026-09-05. Before that a social export and a criminal register were read as `other` — the text was swept for identifiers and every relationship in the file was thrown away — and an intelligence report was filed as an ordinary `note` and believed as if it were an FIR.

**The demo case carries one file of each**, so none of this is a claim about code that has never run: `test_every_source_the_problem_statement_names_has_a_handler`.

**The theme says Blockchain & Cybersecurity and the statement never mentions blockchain.** Most teams will either ignore this or bolt on a pointless token. We do the honest version: a hash-chained chain of custody over evidence and inferences (§3.6). It is correct on its own merits for law-enforcement evidence, and it answers the theme without lying.

### 1.3 Timeline

| When | What |
|---|---|
| 2026-08-28 | Team registered (registration closed 31 Aug 11:59 PM) |
| **2026-09-08, 11:00 IST** | **Internal Hackathon starts — online** |
| **2026-09-09, 11:00 IST** | **Internal Hackathon ends. 24 hours.** |
| 2026-09-30 | National idea-submission deadline (if we advance) |

SIH runs in two phases: this internal college round, then selected teams go to the national finals. PEC's SPOC is **Dr. Kanu Goel**. Team rules: **6 members, at least one woman, all from one college**, and team details cannot be altered once entered.

---

## 2. The idea

### 2.1 In one sentence

**The unit of the product is a case, not a dashboard.** An investigating officer opens a case; that case gets an agent of its own, with its own isolated knowledge graph, its own memory, and its own history to be interrogated — for as long as the case is open.

### 2.2 In the author's words

Kanwar, 2026-09-03:

> *"whenever a new cbi or any new officer takes command of a case or even an officer starting a criminal case, we will deliver his team a personal bot working differently for each case he open in our product, and users work is to deliver our bot documents and all copies of any details be it phone details or any FIR copies or anything else related to case or person or criminal, and our bot on backend will develop a separate graphical knowledge brain for each case an officer opens… and can [handle] more than one cases with each case having separate knowledge graphs and links… and finally a peak bot actually helping officers in real life."*

### 2.3 Why this and not a dashboard — read this before you propose a feature

The obvious build for this problem statement is: upload a CSV, render a graph, compute centrality, print an LLM summary. **That is what most teams submitting against SIH26189 will build, and it was considered and rejected here.**

The reason is that a static visualisation **cannot be asked anything**. An investigator's real problem is not seeing the network once — it is interrogating it repeatedly, over months, as new documents arrive, while running four other cases at the same time. A dashboard shows you what you already thought to look for. An agent answers the question you just thought of at 2am.

**Practical consequence for you as an agent working here:** if a feature makes the system better at *displaying* and no better at *answering*, it is probably the wrong feature. Check it against §9 — does it make one of the two demo queries land harder?

### 2.4 Case isolation is not a nice-to-have

Every case is a separate graph, separate memory, separate custody chain, separate directory on disk. Nothing crosses between them, **by construction and not by a filter** — there is no query that can reach another case's data, because the other case is a different SQLite file.

This is a correctness property in the real domain (evidence from one investigation must not contaminate another) and it is also the thing that makes the demo legible: you can open two cases side by side and show they know nothing about each other.

---

## 3. Architecture

Five pieces. Each maps to bullets in §1.1.

```
                       ┌───────────────────────────────────────┐
   FIRs, CDRs,         │  1. INGEST         (no LLM in path)   │
   bank statements ───▶│  PDF→text · regex · NER · provenance  │
   any case doc        └────────────────┬──────────────────────┘
                                        │ entities + relations
                                        ▼
                       ┌───────────────────────────────────────┐
                       │  2. PER-CASE GRAPH   SQLite+NetworkX  │
                       │  one file per case · full provenance  │
                       └────────────────┬──────────────────────┘
                                        │ on every write
                                        ▼
                       ┌───────────────────────────────────────┐
                       │  3. ANALYTICS                          │
                       │  betweenness · pagerank · communities  │
                       │  temporal anomalies                    │
                       └────────────────┬──────────────────────┘
                                        │ tools query the graph
                                        ▼
   officer's question ─▶┌──────────────────────────────────────┐
                        │  4. CASE AGENT   claude-sonnet-5     │
                        │  tools over the graph, never RAG     │
                        └────────────────┬─────────────────────┘
                                         │ answer + cited ids + path
                                         ▼
                        ┌──────────────────────────────────────┐
                        │  5. SPLIT-SCREEN UI                  │
                        │  chat ◀──▶ live graph (path lights)  │
                        └──────────────────────────────────────┘

   every ingest and every answer ──▶  6. HASH-CHAINED CUSTODY LOG (per case)
```

### 3.1 Ingest — and there is no model in this path

Satisfies: *"Collect and process data from multiple sources"*, *"Extract important entities"*.

PDF and text extraction, then two extractors in order:

1. **Deterministic regex** for the format-regular things, which is most of what matters in Indian police data and which an LLM has no business guessing at: phone numbers, IMEIs, bank account numbers, IFSC codes, vehicle registrations, FIR numbers, dates and timestamps.
2. **NER** (spaCy, or GLiNER if we want zero-shot entity types) for people, organisations and locations.

**Every extraction records where it came from** — document id and character offsets. This is not optional bookkeeping: it is what makes §3.4's citations possible, and citations are what make this system not a chatbot. **A node or edge with no provenance is a bug.**

Why no LLM here: cost, speed, and determinism. An officer uploading 40 pages should wait seconds, not minutes, and the same document must produce the same entities every time.

**Tables go to a handler, not to the identifier sweep.** `readers._classify_csv` picks the handler from columns nothing else has — a CDR, a bank statement, a social export or a criminal register — and `structured.ingest_rows` turns each row into typed edges. A table with no handler is still read and swept for identifiers, and it says so in `warnings`; what it loses is every *relationship* the columns encode, which is the whole value of a table. That was the state of social and criminal-history files until 2026-09-05.

**One kind of document is discounted rather than believed.** An intelligence report is an assessment, and it carries an Admiralty source grading saying how much of one — `Source grading: C3`, or reliability and credibility on separate lines. `readers.read_grading` reads it and everything *inferred* from that report enters the graph at that confidence (D20). It never touches `MENTIONED_IN`: that the report names this man is a fact about the document and is true at full confidence however thin the source is.

### 3.2 The per-case graph

Satisfies: *"Build relationship maps showing how different entities are connected."*

One SQLite file per case, loaded into NetworkX for analysis. Schema is frozen in §5.1.

Edges come from three sources:
- **CDR** — A called B, with timestamp, duration, cell tower.
- **Financial** — X transferred to Y, with amount and timestamp.
- **Co-occurrence** — A and B named in the same document (weaker, and weighted as such).

Entity resolution is deliberately simple: normalise, then match on exact identifier (a phone number is a phone number). Fuzzy person-name merging is a rabbit hole; if we do it at all it is suggested to the user, never applied silently.

### 3.3 Analytics — computed on write, not on demand

Satisfies: *"Identify key individuals who play influential roles"*, *"Detect suspicious patterns and unusual activities."*

Runs after every ingest so answers are instant:

- **Betweenness centrality** → the bridges. The middleman who connects two groups that never touch each other directly. **This is the metric that finds the person no FIR names.**
- **PageRank / degree** → who is central by volume of connection.
- **Louvain community detection** → the cells or gangs within the network.
- **Temporal anomaly** → call-volume and transaction spikes in a window around crime timestamps.

All four are cheap, deterministic and explainable — an officer can be told *why* someone scored high, which an embedding cannot do.

### 3.4 The case agent — and the one rule that matters

Satisfies: *"Assist investigators by providing visual and analytical insights."*

**The agent does not do retrieval over document text. It calls tools that query the graph.** Its tools are in §5.2.

This is the difference between our submission and a RAG chatbot with a graph picture next to it, and a judge will probe it. The proof is structural: every answer returns the **node and edge IDs it traversed** (§5.3), the UI highlights exactly those, and each citation clicks through to the source document and character range it came from. Nothing in the answer can exist without a path through the graph that produced it.

The agent reads source documents only through `read_source_doc`, to verify an edge it already found. That ordering — graph first, document second — is the whole design.

Model: `claude-sonnet-5`, adaptive thinking. Overridable via `ANTHROPIC_MODEL`.

### 3.5 Split-screen UI

**This section is Jashan's, and it is the only part of §3 that is.** What follows is the one *behavioural* requirement the architecture places on the front end. Everything else — layout, library, look, motion, the lot — is his call (§10.1a, D14).

**The requirement:** when the agent answers, **the exact path it used lights up**. `highlight_path` in the answer contract (§5.3) is an ordered list of node ids, and rendering exactly those is what makes the split screen *the reasoning* rather than a picture next to some text. A judge will probe this (D3). Everything else about how the graph is drawn is a design decision.

Beyond that: a citation must click through to the source text (`GET /source`, §5.6), and a node must open its profile (`GET /nodes/{id}` returns attributes, edges, neighbours and every document it was extracted from). Both endpoints exist and return real data now.

Chat-left / graph-right and Cytoscape.js were the original sketch. **They are a suggestion, not a decision** — they are not in §4 and nothing in the backend depends on either.

### 3.5a Frontend design specification — decided by Jashan, 2026-09-05

The frontend is deliberately calm, light and explicit because investigating officers may not be technical users. It must never look like a dark "hacker" dashboard. Product name: **CaseLens**. Tagline: **"See every connection."** The assistant name is exactly **`shikonye`**, lowercase everywhere, with no avatar or logo.

**Visual foundation:** `#F7F8FA` page, white panels, `#20252B` primary text, `#245B8A` Civic Blue actions, `#C58B2A` Evidence Amber paths and citations, thin light-grey borders, almost no shadow, 10px panel corners, 12px chat bubbles, Inter bundled locally, 16px body text and 14px metadata. Status never relies on colour alone. There is no dark theme.

**Navigation and cases:** labelled white left sidebar, 240px expanded / 72px collapsed, pale-blue selected item, officer identity at the bottom. The case list opens directly and uses searchable detailed list cards ordered by recent activity, simple Status and Case Type filters, a blue **New Case** button, and a collapsed Closed Cases section. New Case is a short centred form; the technical case id is generated and hidden. Edit, Close and Delete live in a three-dot menu; deletion requires typing the case title.

**Case workspace:** labelled case navigation is `shikonye`, Documents, Connections, Findings, Memory, Custody. The default workspace is 60% `shikonye` / 40% Connections with a draggable divider; the assistant may resize from 40% to 75%. Either panel can enter Focus mode. Tablet uses one-at-a-time `shikonye` and Connections tabs.

**Assistant:** a normal WhatsApp/ChatGPT-style continuous conversation with date separators and recent messages first. Both sides use white bubbles distinguished by alignment, borders and sender labels. The composer has no prompt suggestions: only text, document attachment and visible Send. Enter sends, Shift+Enter adds a line, and the input grows to six lines. Attachments show filename, size, detected type, Change Type, Remove and independent progress. Answers expose Copy, View Evidence and Show Path; citations expand under Evidence used. Confidence is High / Medium / Low, never an invented percentage. An unverified answer is hidden behind a clear warning and Retry. `search_web` requires approval for every exact query and reason; results are labelled Web Evidence and never receive case documents.

**Connections:** Cytoscape.js on a white faint-dot canvas, community-grouped force layout, circular icon nodes with soft semantic type tints and three meaningful size levels. Ordinary links are thin light-grey curves; inferred links are dashed. Selecting a result draws `highlight_path` step by step in Evidence Amber and fades unrelated entities; Clear Path remains visible. The toolbar is labelled Search, Filter, Fit, Reset and Legend. Search is always visible. Node details use a right drawer; relationship details use a compact popover. Manual positions and filters are remembered per case on the current device.

**Operational states:** English only; dates use `05 Sep 2026, 14:30`; Indian currency grouping; sensitive phones and accounts are masked until Reveal. Loading uses skeletons plus status text. Errors state what happened and how to recover. Success uses a four-second lower-right toast. Keyboard focus is a 2px Civic Blue ring. Local accessibility settings cover text size, increased light-mode contrast and reduced motion. Fonts, icons and core assets are bundled, so everything except approved web search and live model narration can run with the local backend.

### 3.6 Hash-chained custody log

Satisfies the **Blockchain & Cybersecurity** theme, honestly.

Append-only log per case. Every document ingested and every inference the system makes gets an entry, hash-linked to the one before it. Tampering with any earlier entry breaks every hash after it. Format in §5.4.

In the real domain this matters because evidence handling has to be auditable; in the demo it takes ten seconds to show and it is a genuine answer to "where's the blockchain?" that doesn't involve inventing a coin.

### 3.7 The end-to-end trace

Follow this when you're unsure how your piece connects to the rest.

1. Officer opens **Case #114**. Empty workspace, empty graph, fresh custody chain.
2. Uploads three FIR PDFs, a CDR export for two numbers, one bank statement.
3. **Ingest** pulls text, regex takes the identifiers, NER takes the names — every extraction carrying its document and offsets.
4. **Graph** builds: entities deduped into nodes, CDR rows into `CALLED` edges, transactions into `TRANSFERRED_TO`, same-document mentions into `CO_OCCURS`.
5. **Analytics** run on write. Betweenness, PageRank, communities, temporal spikes — all cached.
6. Officer asks: **"How is Ravi connected to the Ludhiana account?"**
7. **Agent** calls `path_between("person:ravi", "account:...")`. Graph returns `Ravi → phone 98xxx → tower co-location 3 Aug 22:10 → Suneel → account`. Agent calls `read_source_doc` on the two edges sourced from FIRs to verify them. Writes one sentence, returns cited node and edge IDs plus `highlight_path`.
8. **UI** animates exactly that path on the right. Citations on the left click through to the FIR page they came from.
9. **Custody log** records the question, the tools called, and the answer, hash-linked.

### 3.8 The part that makes it an assistant and not a search box

Added 2026-09-04 (D10, D11). The brief that produced it, in Kanwar's words:

> *"a personal ai assistant or bot working intelligently under an officer and really making the cases solve with its intelligent and curious bot working under him, so the officer no needs to go through pages anymore, it should really helppp"*
>
> *"it shouldnt just be system prompt calling claude, it will be everything which we do on our behalf peakkk, not just a prompt"*

A system that only answers questions still requires the officer to know what to ask. Three mechanisms, none of them a prompt:

**1. It volunteers.** After every ingest, `analytics/anomalies.py` computes **findings** — deterministic, ranked by how much they should change the officer's next hour, each carrying the node and edge ids it rests on. `GET /brief` is what the agent says without being asked: what changed, what it now believes, what it wants next.

**Findings are computed from the graph, not written by the model.** The model narrates and investigates them; it never invents one. That is D3 enforced structurally, and it is also why the assistant still works with no API key, no network and no budget — which on the demo machine at 11:00 on the 9th is not a hypothetical.

What it looks for: a **hidden broker** (high betweenness, few contacts, named in no report — the headline demo beat), a **single point of contact** joining two clusters, **handset swaps** (one IMEI, several SIMs), **one-way accounts**, **outlier transfers**, **volume spikes** against a node's own baseline, and numbers that **went silent**.

**2. It remembers.** Every case has an `agent_memory` table: conclusions it reached, questions it is still holding, evidence it has asked for, and what it has already briefed — so it does not repeat itself. The officer never re-explains the case.

**3. It acts.** The agent's tools include `record_conclusion`, `open_question` and `request_evidence` (§5.2), all custody-logged. "I don't have it, and here is the exact document that would settle it" is a good answer; inventing a plausible one is the only unforgivable failure.

**And it verifies itself.** Every answer passes through `contract.verify()` before it reaches the officer: each cited id is checked against the real graph, anything that does not exist is stripped and reported, and an answer left with no citations is flagged as unreliable rather than shown as prose. A model that hallucinates `e_9999` gets caught by us, not by a judge.

### 3.9 One engine, every kind of case

**Nothing in ingest, the graph, the analytics or the agent knows what kind of crime it is looking at.** They know identifiers, links, timing and structure — which every investigation has. The demo is a trafficking case because the evaluating department is NCRB Women Safety Division (D7), and for no other reason.

What makes a case specific is `case_type` and `brief` on the case itself (`backend/case.py`) — the officer's own words, threaded into the agent's context on every turn. The same engine reasons like a fraud analyst on a fraud case and a homicide analyst on a homicide, because the graph supplies the facts and the case supplies what kind of facts they are. A test asserts this: `test_two_cases_of_different_kinds_share_nothing` builds a vendor-invoice-fraud case beside the trafficking one and checks both that the engine works on it and that nothing crosses.

---

## 4. Decisions

**Do not re-open these without talking to a human first.** Each carries its reason. If you implement the alternative because it seemed better, you break the build for five other people.

| # | Decision | Reason | Date |
|---|---|---|---|
| D1 | **Per-case agent, not a global dashboard** | A visualisation cannot be asked anything; the investigator's problem is repeated interrogation over months. This is the whole differentiator. See §2.3. | 09-03 |
| D2 | **SQLite + NetworkX. Not Neo4j.** | Neo4j is a service that must install, authenticate and stay up while six people build remotely across 24 hours and one of them demos. NetworkX has every algorithm we need. Per-case isolation becomes "a different file" instead of a permissions model. | 09-04 |
| D3 | **The graph causes the answer; it does not illustrate it** | Otherwise the split-screen is theatre and a judge finds out in one question. Enforced structurally by the answer contract (§5.3). | 09-04 |
| D4 | **No LLM in the ingest path** | Cost, speed, determinism. Regex handles the format-regular identifiers better than a model does, and the same document must extract identically every time. | 09-03 |
| D5 | **Anthropic API only** (`claude-sonnet-5`) | Author's call. Cost is bounded (~$8 across build and demo) *because* of D4 — we send graph subgraphs, not documents. | 09-04 |
| D6 | **Hash-chained custody as the theme answer** | Correct for evidence on its own merits; answers *Blockchain & Cybersecurity* without bolting on a token. ~100 lines. | 09-04 |
| D7 | **Demo case is trafficking / repeat-offender** | The department is NCRB **Women Safety Division**. Same code, story built for the actual evaluators. | 09-04 |
| D8 | **Synthetic data only, with a planted structure** | No public FIR/CDR corpus exists and real crime data would be a legal problem. Planting a known hidden network is what makes the demo provable. See §9. | 09-04 |
| D9 | **This README is the only shared context file. No pointer file.** | Author's call: every collaborator tells their own agent to read this file directly. | 09-04 |
| D10 | **The agent acts, it does not just answer** | *"it shouldnt just be system prompt calling claude… not just a prompt."* It volunteers findings after every ingest, keeps per-case memory across sessions, records conclusions, holds open questions, and names the evidence it needs. §3.8. | 09-04 |
| D11 | **Findings are computed from the graph; the model narrates them** | Keeps D3 structurally true, and keeps the assistant useful with no key, no network and no budget — the state the demo machine may be in. | 09-04 |
| D12 | **The engine is crime-type agnostic; the case carries its own type and brief** | *"it should work for any case… so it mold in every case possible."* Nothing in ingest, graph, analytics or the agent knows what trafficking is. §3.9. | 09-04 |
| D13 | **Centrality is scored on a person-projected graph** | A kingpin whose only edge is `OWNS` to his own SIM scores near zero on the raw graph, because every path stops at the phone. "Who matters" is a question about people; a man and his SIM are not two actors. `nx_adapter.project_people`. | 09-04 |
| D14 | **The backend builds no UI and makes no design decisions** | Author's call: every visual decision is Jashan's. A "temporary" interface built to test an endpoint anchors decisions that are not the backend's to anchor. §10.1a. | 09-04 |
| D15 | **Proximity linking is for prose only, and claims the nearest name only** | Both learned by measurement, not opinion. Running co-occurrence over a CDR export links whoever sits in adjacent rows and added 606 meaningless edges, burying the real structure. And linking every person within the window to a nearby number gave Ravi ownership of Manjit's phone, which then produced a real-looking false path. | 09-04 |
| D16 | **Frontend stack: React + Vite + TypeScript, Tailwind CSS, Radix Primitives, Lucide, Cytoscape.js, TanStack Query and declarative React Router** | Jashan's call after choosing the full interaction system. It keeps the UI local-first, typed and compatible with the frozen HTTP API. | 09-05 |
| D17 | **Calm Civic Forensic visual language; light mode only** | Officers need an interface that reads like dependable casework, not a technical or "hacker" console. Exact tokens and behavior are in §3.5a. | 09-05 |
| D18 | **A document we could not read must say so; it must never ingest in silence** | A scan has no text layer, so every step after the reader succeeds on an empty string — the document registers, custody records it as evidence received, and no entity ever appears, with nothing saying why. That is worse than an error, because it is indistinguishable from a document that had nothing in it. `read_document` counts blank pages and returns a `warnings` list; `POST /documents` passes it through and **the front end must display it**. Adding OCR is a *separate* decision and is not taken here (§13). | 09-05 |
| D19 | **The two sources added last introduced no new node or edge type** | §5.1 is frozen and the front end is being built against it three days out. A social handle is an `account` namespaced by platform, a prior case is an `event`, and what kind of link a `CO_OCCURS` is gets said in `attrs.basis` — where `text_proximity`, `cdr_handset` and `co_accused` all already live. A `FOLLOWS` and a `CHARGED_IN` edge would each read better and would each cost a contract change, a message to four people and a front-end update. **If you are about to add one, this is why it is not there.** | 09-05 |
| D20 | **An intelligence report is graded, and what it implies is discounted** | §1.1 names intelligence agency reports as a source, and until now one was read as an ordinary note — an uncorroborated tip from an untested source entered the graph at exactly the confidence a bank record does. Intelligence carries the Admiralty grading (reliability A–F, credibility 1–6) for precisely this reason, and it maps onto §5.1's `confidence` almost exactly. The factor is the **lower** of the two axes, not their product: they are independent judgements in the standard and multiplying them invents a precision we do not have. An ungraded intelligence report still gets 0.7 — no grading is not the same as a good one. | 09-05 |
| D21 | **`_hidden_brokers` ranks people against people** | Its bar was the fifth-highest betweenness across *every* node, and then only people were ever candidates. On the demo case three of the top five are a document, a bank statement and a travel agency — so "top five" quietly meant "top two people", and **the more documents an officer uploaded the fewer brokers the case could surface.** Adding the criminal-history source pushed the kingpin to sixth overall and deleted demo query 2 outright. The graph was right; the yardstick was wrong. Guarded by `test_the_broker_threshold_ranks_people_against_people`. | 09-05 |

---

## 5. Contracts — FROZEN

**These are how six people's work fits together. Changing one is a conversation, not a commit: update this section first, tell everyone, then write code.** Code that disagrees with this section is a bug even if it runs.

### 5.1 Graph schema

**Node**

```json
{
  "id": "person:ravi_kumar",
  "type": "person",
  "label": "Ravi Kumar",
  "attrs": { "aliases": ["Ravi"], "age": 34 },
  "first_seen": "2026-08-03T22:10:00+05:30",
  "last_seen": "2026-08-19T09:41:00+05:30",
  "sources": [
    { "doc_id": "doc:fir_114_001", "start": 412, "end": 422 }
  ]
}
```

`id` is `{type}:{normalised_value}` and is stable — the same entity always produces the same id.

`type` is one of: `person` · `phone` · `organization` · `location` · `vehicle` · `account` · `device` · `event` · `document`

**One exception to the id rule, and it comes from this section's own examples:** document nodes use the prefix `doc:` (`doc:fir_114_001`), not `document:`, because `sources[].doc_id`, `custody.ref` and `read_source_doc` all speak that form. `schema.ID_PREFIX` is the single place that knows it. *(Clarification of an inconsistency that was already in this contract — not a change. Nothing needed altering in code or in §5.4.)*

**Normalisation, so two agents produce the same id for the same fact:** phones become `91` + ten digits, so `9876543210`, `98765-43210`, `+91 98765 43210` and `09876543210` are one node. People are lowercased, honorific-stripped and underscore-joined. Vehicles and IMEIs drop *all* separators (`PB 10 AB 1234` and `PB10AB1234` are one vehicle). Everything else is lowercased with runs of non-alphanumerics becoming `_`.

**Edge**

```json
{
  "id": "e_1042",
  "src": "person:ravi_kumar",
  "dst": "phone:919876543210",
  "type": "OWNS",
  "attrs": { "since": "2026-01-04" },
  "weight": 1.0,
  "confidence": 0.95,
  "sources": [
    { "doc_id": "doc:fir_114_001", "start": 512, "end": 534 }
  ]
}
```

`type` is one of: `CALLED` · `MESSAGED` · `TRANSFERRED_TO` · `CO_OCCURS` · `OWNS` · `LOCATED_AT` · `REGISTERED_TO` · `MENTIONED_IN`

**The rule: no node and no edge may exist with an empty `sources` array.** If you cannot say where a fact came from, it does not go in the graph.

### 5.2 Tool API

Every tool is scoped to a single case. Every tool returns IDs the agent must cite.

| Tool | Signature | Returns |
|---|---|---|
| `find_entity` | `(query: str, type: str = None)` | `[Node]` ranked by match |
| `neighbours` | `(node_id: str, depth: int = 1, edge_types: [str] = None)` | `{nodes: [Node], edges: [Edge]}` |
| `path_between` | `(a: str, b: str, max_hops: int = 6)` | `[{path: [id], edges: [id], length: int}]` |
| `timeline` | `(node_id: str = None, start: str = None, end: str = None)` | `[{ts, edge_id, summary}]` |
| `top_influencers` | `(metric: "betweenness"\|"pagerank"\|"degree", limit: int = 10)` | `[{node_id, score, why: str}]` |
| `communities` | `()` | `[{cluster_id, members: [id], size}]` |
| `anomalies` | `(window_hours: int = 24)` | `[{kind, node_ids, edge_ids, ts, description}]` |
| `read_source_doc` | `(doc_id: str, start: int = None, end: int = None)` | `{text, doc_id, start, end}` |
| `search_web` | `(query: str)` | `[{title, url, snippet}]` — OSINT only, never case data |

`search_web` is the one tool that leaves the machine. **Never send case content to it** — send only entity names or identifiers that the officer has already made public, and log every call to the custody chain. *(Implemented as a logged stub — no provider is wired up. It returns a message saying so. That is deliberate: the boundary is in place, the provider is a decision nobody has made.)*

**Act tools** — added 2026-09-04, D10. The tools above let the agent *read*. These let it *work*, and they are the difference between an assistant and a search box:

| Tool | Signature | Does |
|---|---|---|
| `record_conclusion` | `(text, node_ids, edge_ids, confidence)` | writes something it worked out into case memory, so it is still known next week |
| `open_question` | `(text, what_would_answer_it)` | holds something it could not settle; re-checked as documents arrive |
| `request_evidence` | `(what, why)` | names the missing document that is blocking an answer |
| `recall` | `(query, kind)` | reads its own earlier conclusions so it never repeats itself |
| `case_overview` | `()` | orients it at the start of a run: counts, documents, findings, open threads |

Everything these write lands in `agent_memory` in the case's own `graph.db`, and every one is logged to the custody chain as `infer`. **The officer can ask "why do you think that" a month later and get the same answer, with the same citations.**

### 5.3 Answer contract — the agent → UI boundary

Every agent response is this shape. The UI depends on it; do not change it unilaterally.

```json
{
  "answer": "Ravi Kumar connects to the Ludhiana account through two hops: his phone 98xxx shared a cell tower with Suneel Kumar's phone on 3 Aug at 22:10, and Suneel is the registered holder of the account.",
  "cited_nodes": ["person:ravi_kumar", "phone:919876543210", "person:suneel_kumar", "account:sbi_xxxx4471"],
  "cited_edges": ["e_1042", "e_2288", "e_3901"],
  "highlight_path": ["person:ravi_kumar", "phone:919876543210", "person:suneel_kumar", "account:sbi_xxxx4471"],
  "confidence": "high",
  "caveats": ["Tower co-location is proximity, not contact."]
}
```

**`cited_nodes` and `cited_edges` must not be empty.** An answer with no citations means the agent answered from its own knowledge rather than from the case, which is exactly the failure this architecture exists to prevent. Treat an empty citation list as an error and say so in the UI.

### 5.4 Custody log entry

One JSON object per line, append-only, at `data/cases/{case_id}/custody.jsonl`.

```json
{
  "seq": 42,
  "ts": "2026-09-08T14:22:09+05:30",
  "actor": "officer:io_114",
  "action": "ingest",
  "ref": "doc:fir_114_003",
  "payload_sha256": "9f2b...",
  "prev_hash": "00a4...",
  "hash": "7c31..."
}
```

`hash = sha256(prev_hash + canonical_json(entry_without_hash))`. The first entry uses `prev_hash = "0" * 64`. `action` is one of `ingest` · `extract` · `infer` · `query` · `web_search` · `export`.

### 5.5 On-disk layout, per case

```
data/cases/{case_id}/
  graph.db          SQLite — nodes, edges, analytics cache
  docs/             original uploads, content-addressed
  extracted/        text + offsets per document
  custody.jsonl     hash-chained audit log
  meta.json         case title, created, officer, status
```

Nothing outside `data/cases/{case_id}/` is readable by that case's agent. **This is the isolation guarantee — do not add a shared store that spans cases.**

### 5.6 HTTP API — FROZEN, and this is the front end's contract

**Built and running.** Start it (§7) and open `http://127.0.0.1:8000/docs` for the live schema. Every endpoint below already returns real data from the demo case.

Everything is scoped to a case. There is no endpoint that reads across cases except `GET /api/cases`, which reads metadata only.

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/health` | `{ok, model, model_available, ner, cases}` — never the key |
| `GET` | `/api/cases?officer=` | `[CaseMeta + counts]` — one officer, several cases |
| `POST` | `/api/cases` | create: `{case_id, title, officer, case_type, brief}` |
| `GET` | `/api/cases/{id}` | meta + counts + documents + custody verification |
| `PATCH` | `/api/cases/{id}` | update title / case_type / brief / status |
| `DELETE` | `/api/cases/{id}?confirm={id}` | deletes the case directory |
| `POST` | `/api/cases/{id}/documents` | multipart upload → `{document, analytics, counts}`. `document.warnings` is a list of plain-language strings and **must be shown to the officer when non-empty** (D18) — an unreadable scan returns 200 with a warning, not an error. A file that is not a readable PDF at all returns **415** with a one-sentence `detail`. |
| `POST` | `/api/cases/{id}/documents/text` | `{filename, text, kind}` → same shape |
| `GET` | `/api/cases/{id}/documents` | every document with kind, sha256, size |
| `GET` | `/api/cases/{id}/source?doc_id=&start=&end=` | **the text behind a citation** |
| `GET` | `/api/cases/{id}/graph?include_documents=false` | `{nodes, edges, counts}` — the whole graph |
| `GET` | `/api/cases/{id}/nodes/{node_id}` | entity profile: attrs, edges, neighbours, source documents |
| `GET` | `/api/cases/{id}/path?a=&b=&max_hops=6` | `[{path, labels, edges, length}]` |
| `GET` | `/api/cases/{id}/timeline?node_id=&start=&end=` | `[{ts, edge_id, summary}]` |
| `GET` | `/api/cases/{id}/analytics?metric=&limit=` | `{influencers, communities, anomalies, findings}` |
| `POST` | `/api/cases/{id}/analytics/recompute` | forces a recompute |
| `POST` | `/api/cases/{id}/ask` | `{question}` → **the §5.3 answer contract** |
| `GET` | `/api/cases/{id}/brief` | what the agent says unprompted (§3.8) |
| `POST` | `/api/cases/{id}/findings/{fid}/investigate` | works one finding → §5.3 |
| `GET` | `/api/cases/{id}/memory?kind=&status=` | the agent's conclusions, questions, requests |
| `POST` | `/api/cases/{id}/memory/{mem_id}/close` | mark one resolved |
| `GET` | `/api/cases/{id}/custody?limit=` | `{verification, entries}` — §9.3 lives here |

**Three things the front end should know about the shapes:**

1. **`/ask` and `/brief` return §5.3 plus a `verified` block** — `{ok, dropped_nodes, dropped_edges}`. The backend has already checked every citation against the graph and stripped any that did not exist. **If `verified.ok` is false, show that** — an answer whose citations failed is not an answer, and hiding it is the one thing that would make this dishonest.
2. **`/brief` returns deterministic findings *and* a narrative.** `findings` comes from the graph and is always present, even with no API key and no network. `narrative` is the model's version. If the model is unavailable the narrative says so in `caveats` and the findings still stand — design for that state, it is the one the demo machine may be in.
3. **`highlight_path` is the render instruction.** It is an ordered list of node ids. Lighting exactly those, in order, is what makes the split screen the reasoning rather than a decoration (D3).

---

## 6. Repo layout

Actual, as built. `frontend/` is Jashan's and remains isolated from the backend implementation.

```
backend/
  config.py         paths, model id, the case-id guard (all case paths come from here)
  case.py           case lifecycle: create/read/update/list, case_type + brief
  ingest/
    readers.py      pdf/csv/txt -> text with stable offsets
    patterns.py     deterministic identifiers: phone, IMEI, a/c, IFSC, vehicle, FIR, dates
    ner.py          role-cue patterns (always on) + spaCy (optional, adds recall)
    structured.py   CDR + bank rows -> typed edges, with the direction table
    pipeline.py     the orchestrator: doc -> nodes/edges -> custody -> analytics
  graph/
    schema.py       §5.1 frozen contract, id normalisation, the no-source rule
    store.py        one SQLite file per case; nodes, edges, docs, analytics, agent_memory
    nx_adapter.py   NetworkX views, path finding, project_people (D13)
  analytics/
    metrics.py      betweenness, pagerank, degree, Louvain, the `why` strings
    anomalies.py    spikes, handset swaps, one-way accounts + the findings layer (§3.8)
  agent/
    tools.py        §5.2 read tools + the act tools
    contract.py     §5.3 schema and verify() — the citation check
    loop.py         ask / brief / investigate, tool_runner, offline fallback
  custody/
    chain.py        the hash chain (§5.4)
  api/
    main.py         FastAPI — §5.6, the front end's contract
frontend/           React + Vite + TypeScript officer interface
  src/components/   CaseLens shell, accessible dialogs and reusable controls
  src/pages/        case list and case-workspace routes
  src/lib/          frozen API client, formatting and local preferences
data/
  cases/            per-case stores (gitignored)
  synthetic/
    generate.py     the demo case generator + the planted ground truth
    out/            the generated CSVs, FIRs and GROUND_TRUTH.json
tests/
  test_core.py      12 tests, incl. the planted-truth assertions
docs/
  demo-script.md    NOT WRITTEN — workstream F
```

---

## 7. Setup

**Stack:** Python 3.11+ (verified on 3.12) · FastAPI · NetworkX · SQLite · Anthropic SDK. Frontend: Node.js 20.19+ or 22.12+ · React · Vite · TypeScript · Tailwind CSS · Radix Primitives · Lucide · Cytoscape.js · TanStack Query.

**Everything runs from the repo root**, not from `backend/` — `data.synthetic` and `backend.*` are one import tree, and splitting the root breaks it.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate  elsewhere
pip install -r requirements.txt

cp .env.example .env            # then put the key in .env — see §8

python -m data.synthetic.generate --case demo-114   # build the demo case (§9)
python -m pytest tests -q                           # 14 tests, all should pass
uvicorn backend.api.main:app --reload               # http://127.0.0.1:8000/docs
```

Run the frontend from a second terminal, still issuing commands from the repository root:

```bash
pnpm --dir frontend install
pnpm --dir frontend dev                              # http://127.0.0.1:5173
```

**If `pnpm` is not on your PATH** — it is not on every machine here — either `corepack enable` once, or put `npx pnpm@10` wherever this file says `pnpm`. Do not `npm install` in `frontend/`: it writes a second lockfile beside `pnpm-lock.yaml` and the two disagree.

The Vite development server proxies `/api` to `http://127.0.0.1:8000`. Optional, non-secret officer display values are documented in `frontend/.env.example`. Never put a secret in a `VITE_` variable because Vite exposes it to the browser.

Frontend checks:

```bash
pnpm --dir frontend build
pnpm --dir frontend lint
```

**It runs without an API key.** Ingest, the graph, analytics, findings and custody need no model at all (D4, D11). `/ask` and `/brief` fall back to a deterministic graph answer and say so in `caveats`. Only the model's narration and multi-step investigation need the key.

**spaCy is optional** and not in `requirements.txt`. The always-on cue patterns handle FIR prose; spaCy adds recall on documents shaped differently:

```bash
pip install spacy && python -m spacy download en_core_web_sm
```

`GET /api/health` reports which NER layers are live and whether a model is reachable — it never reports the key.

---

## 8. Secrets — read this before you write any config

**The Anthropic API key belongs to Gurpartap, personally. It is not the project's key and it is not yours.**

- The key is read from the environment as `ANTHROPIC_API_KEY`. It lives in `.env`, which is gitignored from the first commit.
- **It must never appear in this file, in any committed file, in a log line, in an error message, or in a chat.** This repo being private is not protection — git history is permanent, and four agents read every file here.
- If you are an agent and you find yourself about to write the key anywhere, stop. Write the variable name.
- If it ever does get committed, it must be **revoked in the Anthropic console**, not just removed from the file. A key in git history is a leaked key forever.

Also in `.env`: `ANTHROPIC_MODEL` (default `claude-sonnet-5`).

---

## 9. The demo — and why the dataset is built before the 8th

**The demo is the dataset.** No public FIR/CDR corpus exists, and using real crime data would be a legal problem. So we generate one — and this is not filler work, it is the highest-leverage thing anyone builds. **It must exist before the round starts.**

### 9.1 What the generator plants

A synthetic trafficking network, built for NCRB Women Safety Division (D7), containing a **known ground truth** we can prove the system found:

- A **kingpin who appears in no FIR at all.** He exists only in CDR metadata. He never contacts the foot soldiers — only two intermediaries.
- **Two clusters** that share no direct edge, joined only through those intermediaries.
- A **call-volume spike** in the hours before a logged incident.
- A **financial trail** that crosses from one cluster to the other through a single account.
- Enough ordinary noise that the structure isn't visible by eye.

Because we planted it, we can state exactly what the system should find and show that it did.

### 9.2 The two queries we demo

**1. "How is Ravi connected to the Ludhiana account?"** — proves the graph causes the answer. The path animates, the citations click through to the source FIR.

**2. "Who matters most in this case?"** — the system names a man who appears in **zero FIRs**, found by betweenness bridging two clusters that otherwise never touch. Then we open the source view and show he really is in no report.

That second one is the moment the room understands what the system does. Everything else is setup for it.

### 9.3 Then the theme

Open the custody log, show every ingest and inference hash-linked, alter one entry, show the chain break. Ten seconds. Answers "where's the blockchain?" before anyone asks it.

---

## 10. Ownership and the 24 hours

### 10.1 Workstreams

Contracts (§5) are frozen in the first hour so these can run in parallel without meeting until integration.

| Workstream | Scope | Owner | State |
|---|---|---|---|
| A · Ingest & extraction | PDF/CSV parsing, regex, NER, provenance | Kanwar | **built** |
| B · Graph & analytics | schema, SQLite store, NetworkX, the four algorithms | Kanwar | **built** |
| C · Agent & tools | tool implementations, agent loop, answer contract | Kanwar | **built** |
| **D · Everything the user sees** | **the entire front end and every design decision — see §10.1a** | **Jashan** (design language, Cases screen) · **Kanwar** (case workspace, 09-05 — see §10.1b) | **built** — every section of §3.5a is live against §5.6 |
| E · Synthetic data | the generator and the planted structure (§9.1) | Kanwar | **built** |
| F · Custody + demo script | hash chain, `docs/demo-script.md`, the run-through | Kanwar / `UNASSIGNED` | chain built, script not written |

**Roster is `UNKNOWN`.** Known so far: **Jashan Garg** (repo owner), **Kanwar Sekhon**, **Gurpartap** (holds the API key). SIH requires six with at least one woman. **Whoever knows the full roster: fill this table in and delete this line.**

### 10.1a The split — read this before you write a line of code

**There are two halves of this project and they do not overlap.**

**Jashan owns everything the user sees.** Not "the UI layer" — *everything visual*. Layout, typography, colour, spacing, motion, the split-screen proportions, how the graph is drawn, what a node looks like, how a citation renders, how the chat reads, the entity panel, the case list, empty states, loading states, error states, the whole visual language. **Every design decision in this project is his.** There is no design system handed down from the backend, no reference mockup, no "we already picked the colours". Nobody has, and nobody is going to.

**Kanwar owns everything underneath.** Ingest, the graph, analytics, the agent, custody, and the HTTP API. That half is built (§11).

**Consequences, both directions:**

- **If you are Jashan's agent:** the backend is done and running. You do not need to wait for anyone, and you do not need to ask what anything should look like — that is your call, entirely. **§5.6 is your contract**: every endpoint, every shape, already frozen and already returning real data from the demo case. Build against it. If you need a field that does not exist, say so and it gets added — do not invent a second API, and do not reshape the data in the client to work around a missing endpoint.
- **If you are Kanwar's agent (or anyone working the backend):** **do not build UI, and do not make design decisions.** No pages, no components, no CSS, no colour choices, no "temporary" front end to test against, no HTML mock so we can see it working. Test with `pytest`, `curl` and `/docs`. Producing a scrappy interface "just to check the endpoint" takes the decision out of Jashan's hands by anchoring it, and it is not yours to anchor. The one thing the backend owes the front end is a clean, honest, documented API — that is in §5.6.

**Where the boundary literally is:** `frontend/` is Jashan's, and nothing outside it is. `backend/`, `data/` and `tests/` are the backend's. The README belongs to whoever is changing something, and §12 records it.

### 10.1b The workspace half moved to Kanwar — 2026-09-05

**Everything in §10.1a above was true until this section, and one part of it no longer is.** Kanwar's call on the evening of 09-05, three days before the internal round: **his side built the case workspace** — the `shikonye` conversation, Connections, Documents, Findings, Memory and Custody — because the Cases screen was the only screen that existed and the workspace is what a judge is actually shown.

**This does not un-assign the front end from Jashan, and it changes nothing about §3.5a.** The workspace was built *to* his specification, not around it: CaseLens, `shikonye` lowercase with no avatar, the Calm Civic Forensic palette, light-only, 60/40 split with a 40–75% draggable divider, focus mode, tablet tabs, masked identifiers until Reveal, four-second toasts, skeletons and stated error states. The design decisions in §3.5a were his and were followed; none were re-taken.

**What this means for whoever picks up next:**

- **Do not rebuild the workspace.** It exists, it runs against the real API, and §11 lists what it covers. Change it, and change §11 with it.
- **Design changes are still Jashan's call.** If the workspace looks wrong to him, his judgement wins over what is there — §3.5a is still the specification, and this is still his front end.
- **The split in §10.1a otherwise stands.** The backend still builds no UI on its own initiative; this was an explicit instruction from Kanwar, not a drift.

### 10.2 Before the 8th

Contracts frozen · synthetic generator built and producing the demo case · each workstream's skeleton running end to end against fake data. **A component that has never once run against the demo case is not ready**, however complete it looks.

### 10.3 The 24 hours

The failure mode of a six-person hackathon is everyone building alone until hour 20 and integrating at hour 22. We integrate three times instead.

| Hours | Focus |
|---|---|
| 0–2 | Contracts confirmed, repo skeleton, everyone can run the app locally |
| 2–8 | Parallel build: A, B, C, D, E against the frozen contracts |
| **8–10** | **Integration #1** — ingest → graph → analytics end to end on the demo case |
| 10–14 | Agent tools wired; first real answer with real citations |
| **14–16** | **Integration #2** — chat → graph highlight working end to end |
| 16–20 | Custody chain, OSINT tool, entity panel, polish |
| **20–22** | **Integration #3 — feature freeze.** Nothing new after this. |
| 22–24 | Demo rehearsed end to end at least three times, on the demo machine, offline-safe |

**Feature freeze at hour 20 is not negotiable.** A demo that has been run three times beats a better system that has been run once.

---

## 11. Current state

**Updated 2026-09-05. Whoever changes this project: change this section too.**

**The entire backend is built and running. The front end is built — Cases screen and the full case workspace, live against the real API. `docs/demo-script.md` and the live model call are what is left.**

| Part | State |
|---|---|
| Ingest — PDF/CSV/text, regex identifiers, cue NER, provenance | **built, tested** — PDF exercised against a real file, readable and scanned (2026-09-05) |
| **Sources — all seven of §1.1** | **built, tested** (2026-09-05) — social, criminal history and graded intelligence were the last three. See §1.2a |
| Graph — SQLite per case, §5.1 schema, idempotent merge | **built, tested** |
| Analytics — betweenness, pagerank, degree, Louvain, anomalies, findings | **built, tested** |
| Agent — 9 read tools + 5 act tools, tool loop, §5.3 contract, self-verification | **built**, exercised offline |
| Custody — hash chain, tamper detection | **built, tested** |
| API — every endpoint in §5.6 | **built**, returning real data |
| Demo case — generator + planted ground truth | **built, tested** |
| **Front end — Cases screen** | **built** — React foundation, design tokens, live Cases list, case CRUD, persisted officer/accessibility settings, loading/empty/error states |
| **Front end — case workspace** | **built, exercised in a browser against `demo-114` (2026-09-05)** — all six §3.5a sections; **19 of §5.6's 22 endpoints are reached** from the UI |
| `docs/demo-script.md` | **NOT WRITTEN** — workstream F |

**Verified against the demo case**, `python -m pytest tests -q` → **25 passed**:

- The kingpin is named in **no report** — only in CDR metadata — and the system **leads with him**: *"Harbhajan Dhillon connects this network but appears in no report."* (§9.2 query 2.)
- Ravi reaches the Delhi account **through the tower co-location**, and there is provably no call between the two numbers, so the system cannot claim contact. (§9.2 query 1.)
- Two cases of **different kinds** (trafficking, vendor fraud) share nothing.
- Altering one custody entry **breaks the chain at that entry**. (§9.3.)
- A 40-page document ingests and re-runs all analytics in **well under a second**.
- A **real two-page FIR in PDF** — tables, wrapped lines, a case that continues across the page break — reaches the graph with its people, both phone numbers, the vehicle and the account, and the citation opens.
- A **scanned PDF** returns a warning saying it could not be read, instead of registering as evidence and adding nothing.
- A **criminal register** names Manjit Singh and Suneel Kumar as repeat offenders — three prior cases each, one conviction each — and links four pairs of people through a **shared charge sheet**, which nothing in the current case links directly.
- A **C3-graded intelligence report** enters everything it implies at **70% confidence** and says so at upload, while the fact that it names those men stays at 100%.
- **No source added after 09-04 crosses the Ludhiana/Delhi divide**, so the kingpin is still the only bridge and demo query 2 still works. This is asserted, not assumed.

Demo case, for scale: **125 nodes (116 entities + 9 documents), 1,148 links, 9 documents, 7 communities, 38 anomalies, 26 findings.**

**Not done, and honest about it:**

- **The agent loop has never run against the live API.** There is no key on the build machine (§8: it is Gurpartap's). Every tool, the contract, the verification and the offline path are tested; the model call itself is not. It remains the highest-risk untested thing in the repo.

  **Deliberately deferred — Kanwar's call, 2026-09-04:** *"live test will be done only when every other part will be built by me and jashan."* Do **not** spend the key probing it before then. The reason it can wait is D11: findings, the graph, analytics and custody all work without a model, so nothing downstream is blocked on this answer. The reason it cannot wait forever is that it is a single point of failure on demo day. **Run it once, together, as soon as the front end can display the result — before the 8th, not on it.**
- `search_web` is a logged stub — no provider chosen.
- **A scanned PDF is announced, not read.** There is no OCR and none was added; whether scans are in scope at all is still open (§13). What changed on 2026-09-05 is that the system now says so rather than accepting the file in silence.
- **exposurie** (Kanwar's other project) is paused for this.
- **The cue NER reads two intelligence frames, not every one.** "The source names X" and "X is reported to be …" are handled; a name followed by a subordinate clause before its verb is not, and that is spaCy's job (`ner_backend()` says which layers are live). Widening the regex to leap a clause is exactly the bug D15 records.
- **Scans still are not read** — unchanged, and still §13's question.

- **A live upload is filed under the server's temp filename. Found 2026-09-05 by driving the real upload through the UI; backend fix, not a front-end one.** `POST /documents` writes the upload to a `tempfile.NamedTemporaryFile` and hands that path to `ingest_file`, which takes its filename from `path.name` (`backend/ingest/pipeline.py:118`). So an officer who uploads `fir_114_003.pdf` gets a document called `tmpegm_u9dr.pdf` and a doc id of `doc:tmpegm_u9dr` — in the document list, in every citation, and in the custody chain. **The demo case does not show this**, because the generator ingests real paths; it only appears on a live upload, which is exactly what a judge asks to see. The fix is to carry `file.filename` through: `ingest_file` needs a `filename: str | None = None` parameter used in place of `path.name` for `make_doc_id` and `register_document`, and `main.py` should pass `file.filename`. Left for whoever owns `backend/` — the front end already sends the real name in the multipart part.

- **`/brief` omits the `verified` block on a case with no documents**, though §5.6 describes it as always present. Harmless now: the front end treats a missing block as "no verification ran" rather than "verification failed", which is the honest reading of an empty case. Worth knowing before anything else consumes `/brief`.

- **The offline `/ask` fallback answers names, not questions.** With no key, `Harbhajan Dhillon` returns a real cited answer, but *"How is Ravi connected to the Ludhiana account?"* returns *"Nothing in this case matches that name or identifier."* — including for demo query 1 (§9.2), phrased as a question. §7 says `/ask` "falls back to a deterministic graph answer", and for `/brief` that is true; for `/ask` it is a bare entity lookup. **If the demo runs without the key for any reason, the centrepiece question returns nothing.** The front end renders whatever comes back honestly, so this is a backend decision: either the fallback learns to route a question at `path_between` / `top_influencers`, or the demo commits to running with the key and §13's offline risk is answered.

**Next, in order:**

1. **`docs/demo-script.md`** (workstream F). The front end can now show everything the script needs to point at, so nothing blocks this. **It is the only unbuilt item left in the whole repo.**
2. **The live API call**, once — together, before the 8th. See above. Every screen that consumes it already handles both outcomes, including the model being unreachable.
3. **The upload filename defect below**, which is a backend fix and is the one thing in this list a judge would see.

*(The case workspace was item 1 and is done — 2026-09-05, §10.1b and §12.)*

**The three §5.6 endpoints the UI does not call, and why** — none is an oversight, and each is a small job if it turns out to be wanted:

- **`POST /documents/text`** — pasting text in as a document. §3.5a's composer is text *or* an attachment, and text there is a question for `shikonye`, not evidence. Nothing in the spec asks for paste-as-evidence.
- **`GET /timeline`** — §3.5a names six workspace sections and a timeline is not one of them. Adding a seventh is a design decision and therefore Jashan's.
- **`POST /analytics/recompute`** — every write path already recomputes server-side and the client invalidates its queries after an upload, so a manual button would only ever confirm what already happened.

*(PDF ingest and the three missing §1.1 sources were items 2 and 3 and are both done — 2026-09-05, §12. Every source the problem statement names now has a handler and a file in the demo case: §1.2a.)*

**Jashan — three things in this change touch what you draw**, and none of them changes §5.6:

- **`event` nodes now appear in `/graph`.** `event` was always a legal §5.1 node type; it had never been in the demo data before. There are 12 on the demo case — 9 prior cases from the register, labelled `Case 88/2019`, with `attrs.offence`, `attrs.disposition` (`convicted` / `acquitted` / `pending` / `null`) and `attrs.station`; and 3 more that `patterns.py` has always pulled out of FIR numbers written in prose, which carry a bare label and no attrs.
- **`MENTIONED_IN` is now a visible edge.** `/graph` drops document nodes by default, so `MENTIONED_IN` used to vanish with them. Person → prior-case edges are `MENTIONED_IN` and they survive that filter.
- **Two new finding kinds**: `repeat_offender` and `prior_association`. Same shape as every other finding, so if you render by `kind` with a fallback they cost you nothing.
- Also: `document.meta.grading` and `document.meta.confidence_factor` exist on intelligence documents, and the D18 `warnings` list carries a plain sentence about it. Displaying that is the same requirement D18 already put on you, not a new one.

---

## 12. Changelog

Append one line per session. What you built · what you changed in this file · what the next agent needs to know.

- **2026-09-04** — README created. Problem statement recorded verbatim from sih.gov.in; architecture, decisions D1–D9 and contracts §5.1–5.5 written from the 09-03/09-04 design discussion. No code yet. Roster still unknown.

- **2026-09-04, evening (Kanwar + Claude)** — **the whole backend, built and tested.** Ingest, graph, analytics, agent, custody, API, demo generator, 12 tests. What the next agent needs to know:
  - **Front end is untouched and is Jashan's** — every visual and design decision, not just "the UI layer". New **§10.1a** says so explicitly and **§5.6** is the frozen API he builds against. The backend deliberately built no interface of any kind (**D14**).
  - **New decisions D10–D15.** The agent acts rather than only answering (§3.8); findings are computed from the graph so the system works offline (D11); the engine is crime-type agnostic and the case carries its own type and brief (D12, §3.9); centrality runs on a person-projected graph (D13).
  - **Two contract clarifications, no contract changes.** §5.1 now records the `doc:` prefix exception that was already in its own examples, and the id-normalisation rules. §5.2 gained the act tools.
  - **§7 setup was wrong and is corrected** — everything runs from the repo root (`uvicorn backend.api.main:app`), not from `backend/`. `numpy` and `scipy` are required (NetworkX pagerank needs them). spaCy is genuinely optional.
  - **Three bugs found by measurement, worth not reintroducing** (D15): co-occurrence linking run over a CDR export created 606 meaningless edges and buried the real structure; the ownership heuristic gave one man another man's phone and produced a plausible false path; a name pattern crossed a full stop and merged two people into `person:manjit_singh_accused_sukhwinder`.
  - **Untested:** the live API call. No key on the build machine, and **deferred on purpose** until the rest is built (§11) — nothing downstream is blocked on it, because findings, the graph, analytics and custody all work with no model at all (D11).

- **2026-09-05 (Jashan + Codex)** — **frontend milestone 1 built.** Added the React + Vite + TypeScript application in `frontend/`, bundled Inter locally, established the Calm Civic Forensic tokens, added the 240px/72px desktop sidebar and labelled tablet drawer, and connected the Cases screen to the real `/api/cases` endpoint. Search and filters, detailed case cards, create/edit/pause/close/delete controls, typed-title delete confirmation, persisted officer and accessibility settings, skeleton/empty/reconnect states and four-second success feedback are implemented. Browser QA created a temporary case through the real API, verified it appeared first, then removed that exact temporary case through typed-title confirmation; desktop and tablet layouts have zero browser console errors. `pnpm --dir frontend build`, `pnpm --dir frontend lint` and all 12 backend tests pass. §3.5a records Jashan's locked design direction; D16–D17 record the frontend stack and visual language. Next: replace the temporary case route with the live 60/40 `shikonye` + Connections workspace.

- **2026-09-05 (Kanwar + Claude)** — **PDF ingest exercised end to end, and the silent failure under it closed.** Two committed fixtures in `tests/fixtures/`: a real two-page FIR laid out like the form (tables, wrapped lines, a statement continuing past the page break) and the same document as an image-only scan. The readable one reaches the graph correctly — Ravi Kumar, Harbhajan Dhillon, a hyphenated number on page 1, a second number on page 2, the vehicle, the account — and its citation opens. **The scan did not: it registered as evidence, wrote a valid custody entry, produced zero entities and said nothing at all** (200, `warnings: []`). Fixed per **D18** — `_read_pdf` now counts blank pages and returns plain-language warnings, which `POST /documents` already passes through in `document.warnings`; **Jashan, the front end must display these.** Two further defects found by the same exercise: every `.pdf` was labelled `kind="fir"` regardless of content (a bank-statement PDF is a source §1.1 names, and `kind` is what the agent is told the document *is*) — PDFs are now classified from their text like every other prose document, and one we could not read a word of is `other` rather than a confident guess; and an encrypted or corrupt PDF raised a raw pypdf error into a **500**, now a **415** with one readable sentence. No OCR was added and §13 records why that stays Kanwar's call. Also corrected §7: `pnpm` is not on every machine here, so the setup block now names `corepack enable` / `npx pnpm@10`. **12 → 14 tests, all passing.** Next backend job is the two §1.1 sources with no handler.

- **2026-09-05 (Kanwar + Claude)** — **the last three sources in §1.1 now have handlers, and the demo case carries one file of each.** New **§1.2a** is the coverage table: seven sources named in the problem statement, seven readers, all seven exercised. What the next agent needs to know:
  - **Social media intelligence** (`structured._ingest_social`). Handles become `account` nodes **namespaced by platform** — `@ravi_k` on Instagram and `@ravi_k` on X are two accounts, and §5.1 has no fuzzy matching to undo a merge afterwards. A DM or reply is `MESSAGED`; a mention or a follow is a weak `CO_OCCURS` carrying its `basis`. A display name buys a `person -[OWNS]-> account` edge at **0.45** — lower than the 0.6 text proximity earns in an FIR, because an FIR was written by an officer and a profile name was typed into a box by its owner.
  - **Criminal history databases** (`structured._ingest_history`). A prior case is an `event` node keyed on the case number *alone*, deliberately: `patterns.py` has always pulled `FIR 88/2019` out of prose as `event:88_2019`, and the register has to land on the same node or the case an officer reads about and the case in the database are two different things. Each accused gets `MENTIONED_IN`; **co-accused get a `CO_OCCURS` at weight 1.0** — two names on one charge sheet is a relationship that predates every document in the current case, and it is the "hidden relationship among suspects" §1.1 opens with. `disposal` is normalised to `convicted` / `acquitted` / `pending`, and to **`null` when the word is not recognised** — never to `pending`.
  - **Intelligence agency reports** — new **D20**. These were being read as ordinary notes, so an uncorroborated tip from an untested source entered the graph at the confidence a bank record does. `readers.read_grading` reads the Admiralty grading (`Source grading: C3`, or reliability and credibility on their own lines) and discounts everything *inferred* from the report. It does **not** touch `MENTIONED_IN`: that the report names this man is a fact about the document and is true whatever the source is worth. Ungraded intelligence still gets 0.7.
  - **No new node or edge type — D19.** §5.1 is frozen and Jashan is building against it three days out. If you are about to add `FOLLOWS` or `CHARGED_IN`, D19 is why they are not there.
  - **A real bug fell out of this, and it is the most important line in this entry — D21.** `_hidden_brokers` set its bar at the fifth-highest betweenness across *every* node, then only ever considered people. Three of the demo's top five are a document, a bank statement and a travel agency, so the bar was really "top two people" — **the more documents an officer uploaded, the fewer brokers the case could surface.** The extra density from the criminal register pushed the kingpin to sixth overall and **deleted demo query 2 outright**. Fixed by ranking people against people. Guarded by `test_the_broker_threshold_ranks_people_against_people`, which fails if the old line comes back.
  - **`_undocumented_people` and `_hidden_brokers` now share `REPORT_KINDS`**, and `intelligence` is in it. A man named in an intelligence report is not invisible, however thin the report is. `cdr`, `financial`, `history` and `social` stay out: those are records of what somebody did, not accounts written by somebody watching.
  - **Two NER cues added** for intelligence prose ("the source names X", "X is reported to be …"), because a graded report naming two men was putting neither in the graph. Deliberately not widened further: a pattern that leaps a subordinate clause is the D15 bug again.
  - **Demo generator**: `criminal_history.csv`, `social_media_intel.csv` and `intelligence_input_ldh.txt`, with the plants recorded in `GROUND_TRUTH.json`. **Nothing added crosses the Ludhiana/Delhi divide** — a co-accused or social edge between the clusters would be a second bridge and the kingpin's betweenness is earned by being the only one. `test_no_new_source_re_wires_the_two_clusters` enforces it so the next person to add a row finds out here rather than on stage.
  - **Jashan: `event` nodes and `MENTIONED_IN` edges now appear in `/graph`**, and there are two new finding kinds. §5.6 is unchanged — see the note at the end of §11.
  - **14 → 25 tests, all passing.** Backend is now feature-complete against §1.1; `docs/demo-script.md` is the only unbuilt backend item left.

- **2026-09-05, evening (Kanwar + Claude)** — **the case workspace, built and driven in a browser against the real API.** The front end is now complete against §3.5a; `docs/demo-script.md` is the last unbuilt thing in the repo. What the next agent needs to know:
  - **Ownership moved for this one workstream — new §10.1b.** §10.1a said the backend builds no UI, and this session was Kanwar explicitly overriding that three days out, because the workspace was the only thing standing between the backend and a demo. **§3.5a was followed, not replaced**; every design decision in it is still Jashan's, and if he wants the workspace to look different his judgement wins.
  - **All six sections are live**: `shikonye` (opening brief, conversation with date separators, attachments with per-file progress and Change Type, Copy / View Evidence / Show Path, confidence never invented as a percentage), Documents (upload, D18 warnings, per-document grading), Connections (Cytoscape, community-grouped layout, type tints, three node sizes, dashed inferred links, Search / Filter / Fit / Reset / Legend, node drawer, relationship popover, positions and filters remembered per case), Findings (Investigate posts a real §5.3 answer into the conversation), Memory, Custody.
  - **`highlight_path` renders two different shapes, and the difference is deliberate.** An answer's ordered path lights hop by hop in Evidence Amber with the edge between each pair. A finding's `node_ids` is an unordered set with no hops, so the links *inside* the set are lit instead and the banner says "entities", not "path". Nothing is ever drawn between two nodes that have no edge.
  - **A path through a document node turns document nodes back on** — `/graph` drops them by default — as an override held only while the path is shown, and the banner says so. The officer's own filter comes back when the path is cleared.
  - **Three bugs worth not reintroducing.** Cytoscape injects `__________cytoscape_container { position: relative }` at runtime, which beat Tailwind's `absolute` and collapsed the canvas to zero height — the container is sized inline now, and a `ResizeObserver` calls `cy.resize()` because the panel also changes size on every divider drag and focus toggle. `AnswerCard` read `verified.ok` through a block `/brief` omits on an empty case and white-screened the whole workspace — hence `PanelBoundary`, so one panel failing can never take the case, the graph and the navigation with it. And `/nodes/{id}` returns one entry per citation, so one CDR naming a man 34 times listed the same file 34 times; the drawer groups by document now.
  - **Three defects found and left for the backend, all recorded in §11.** A live upload is filed under the server's temp filename (`tmpXXXX.pdf`) and it reaches the document list, every citation and the custody chain — invisible in the demo case, visible the moment a judge asks to upload something. `/brief` omits `verified` on an empty case. And the offline `/ask` fallback answers names but not questions, which means demo query 1 returns nothing without the key.
  - **`/path` is wired to a real control.** The entity drawer traces a route between two entities in two clicks — open one, "Trace a route from this entity", open the second — which is demo query 1 asked directly on the graph. **19 of §5.6's 22 endpoints are reached from the UI**; §11 names the three that are not and why.
  - **The entity drawer is a docked column on desktop, not an overlay.** Connections is only 40% of the workspace, so a 360px drawer over it left a sliver of graph; the drawer is now a third column and the split is computed over what remains after it. On tablet it stays an overlay, because there is only one column there.
  - **Verified in a real browser, not by reading the code**: the demo case end to end at 1440×900 and 820×1024, zero console errors, the scanned-PDF warning shown to the officer on a real upload, a citation opening on the exact CDR row it came from, and an empty case rendering rather than crashing. `pnpm build` and `pnpm lint` are clean and the backend's 25 tests still pass.
  - `.gitignore` gained `.gstack/` — a scratch directory the browser tooling writes into the repo root. Not project state; ignored so it cannot be committed by accident.

---

## 13. Open questions

Answer these in-place when you learn the answer, and say who answered it.

- **Who are the six team members?** Two on GitHub, Gurpartap named as a third. SIH requires six, at least one woman.
- **Does the internal round score prototype, presentation, or both?** The PEC circular does not say. Changes how hours 20–24 are spent.
- **Is there a submission artefact besides the demo** — idea PPT, doc, video? The national round wants an idea presentation; the internal round's requirement is unconfirmed.
- **Do we present live or pre-record?** Online mode; unconfirmed. If live, network failure is a real risk and the demo must run fully offline.
- **Are scanned documents in scope?** Real FIRs are often photographs of paper, which have no text layer at all. As of 2026-09-05 the system detects them and says so (D18) but cannot read them; reading them means OCR, which is a dependency nobody has agreed to and which would put a lossy step in front of the graph. **Kanwar's call, not an agent's.**
