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

If you are unsure about an Anthropic API shape, **do not guess** — check the official docs rather than your recollection.

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

Chat on the left, live knowledge graph on the right. When the agent answers, **the exact path it used lights up on the right**. The highlight is not decoration — it is a render of `highlight_path` from the answer contract, so it is literally the reasoning.

Cytoscape.js for the graph. Clicking any node opens that entity's profile: its attributes, its edges, and every document it was extracted from.

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

`search_web` is the one tool that leaves the machine. **Never send case content to it** — send only entity names or identifiers that the officer has already made public, and log every call to the custody chain.

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

---

## 6. Repo layout

```
backend/
  ingest/       pdf, regex extractors, NER, provenance
  graph/        schema, sqlite store, networkx adapter
  analytics/    centrality, communities, anomalies
  agent/        tool definitions, agent loop, answer contract
  custody/      hash chain
  api/          FastAPI routes
frontend/
  app/          Next.js
  components/   chat, graph canvas, entity panel
data/
  cases/        per-case stores (gitignored)
  synthetic/    the demo case generator + its output
docs/
  demo-script.md
```

---

## 7. Setup

**Stack:** Python 3.11 · FastAPI · NetworkX · SQLite · spaCy · Next.js · Cytoscape.js · Anthropic SDK.

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
cp .env.example .env        # then put the key in .env — see §8
uvicorn api.main:app --reload

# frontend
cd frontend
npm install
npm run dev

# generate the demo case
python -m data.synthetic.generate --case demo-114
```

`UNKNOWN` until the first code lands — if you are the agent that creates these files, correct this section in the same commit.

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

| Workstream | Scope | Owner |
|---|---|---|
| A · Ingest & extraction | PDF/CSV parsing, regex, NER, provenance | `UNASSIGNED` |
| B · Graph & analytics | schema, SQLite store, NetworkX, the four algorithms | `UNASSIGNED` |
| C · Agent & tools | tool implementations, agent loop, answer contract | `UNASSIGNED` |
| D · UI | split screen, Cytoscape canvas, highlight, entity panel | `UNASSIGNED` |
| E · Synthetic data | the generator and the planted structure (§9.1) | `UNASSIGNED` |
| F · Custody + demo script | hash chain, `docs/demo-script.md`, the run-through | `UNASSIGNED` |

**Roster is `UNKNOWN`.** Known so far: **Jashan Garg** (repo owner), **Kanwar Sekhon**, **Gurpartap** (holds the API key). SIH requires six with at least one woman. **Whoever knows the full roster: fill this table in and delete this line.**

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

**Updated 2026-09-04. Whoever changes this project: change this section too.**

- **Repo:** README only. No code has been written yet.
- **Architecture:** agreed (§3). **Contracts:** written and frozen (§5) — not yet exercised by code.
- **Roster:** `UNKNOWN` — see §10.1.
- **Next:** the team's first working session. Assign §10.1, then build the synthetic generator (§9.1) first, because everything else is tested against its output.
- **exposurie** (Kanwar's other project) is paused for this.

---

## 12. Changelog

Append one line per session. What you built · what you changed in this file · what the next agent needs to know.

- **2026-09-04** — README created. Problem statement recorded verbatim from sih.gov.in; architecture, decisions D1–D9 and contracts §5.1–5.5 written from the 09-03/09-04 design discussion. No code yet. Roster still unknown.

---

## 13. Open questions

Answer these in-place when you learn the answer, and say who answered it.

- **Who are the six team members?** Two on GitHub, Gurpartap named as a third. SIH requires six, at least one woman.
- **Does the internal round score prototype, presentation, or both?** The PEC circular does not say. Changes how hours 20–24 are spent.
- **Is there a submission artefact besides the demo** — idea PPT, doc, video? The national round wants an idea presentation; the internal round's requirement is unconfirmed.
- **Do we present live or pre-record?** Online mode; unconfirmed. If live, network failure is a real risk and the demo must run fully offline.
