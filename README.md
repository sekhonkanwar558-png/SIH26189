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

## 0.5 THE PIVOT — 2026-09-05, and it supersedes several sections below

**Read this before §3, §10 or the decision table.** Kanwar changed the product's
face on the evening of 2026-09-05. The engine did not move; what an officer sees
did, completely, and several sections written before this are now wrong where
they disagree with it.

**In his words, across one conversation:**

> *"why do we need that offline analysis anywhere, dont keep that at all, just
> keep llm calls only for every search from anything"*
>
> *"just keep bot peak at its best working as true real assistant at any time an
> officer needs"*
>
> *"our main target isss providing a peak assistant 'Suishōdama' working at all
> problems an officer talks to him, it should be like talking to some teammate
> and feel realistic"*
>
> *"it shouldnt just be a sloppy 'system prompt' behinddd"*
>
> *"remove those different sections buttons of documents, other on side, just one
> chat interface and option to graph… one clean chatgpt like interface, but great
> shit at backend"*
>
> *"dont just push slash commands at all, the bot should only fire from chat
> message, because we are making for non technical peopleee"*

### The pivot in full — every instruction, verbatim, in order

**These are the actual prompts, unedited.** They are here rather than summarised
because the next agent to pick this up needs to know what was asked for, not what
I concluded from it — and because he gave the reasons as he went, and the reasons
are the useful half.

**On killing the offline path**

> 1. *"hey wait why do we need that offline anyalsis anywhere, dont keep that at
>    all, just keep llm calls only for every search from anything"*
> 2. *"just remove that offline analysis shit from anywhere"*
> 3. *"just keep bot peakk at its best working as true real assistant at any time
>    an officer needs"*
> 4. *"i will do real test after everythings will be made, you just make ittt for
>    peak experience"*

**On what Suishōdama has to be**

> 5. *"our main target isss providing a peak assistant 'Suishōdama' working at all
>    problems an officers talk to him, it should be like talking to some teammate
>    and feel realistic"*
> 6. *"it shouldnt just be a sloppy 'system prompt' behinddd"*
> 7. *"it should feel like real shit and tempting to an officer to interact with
>    it"*
> 8. *"both the prompt and backend structure needs to be well sexyy peakkk"*
> 9. *"not anything justt normal chattt doing everyhting an officer asks it to
>    doo"*
> 10. *"bit backend should peakesttttttt"*

**On the interface**

> 11. *"and dont just push slash commands at all, the bot or assistant should only
>     fire from chat message, because we are making for non technical peopleee,
>     make sure its too easy and just simple interactions but great peak machinery
>     working at backend"*
> 12. *"and even remove those different sections buttons of 'documents', other on
>     side, just one chat interface and option to graphh, it should be veryy easyy
>     to interact just one clean chatgpt like interface, but great shit at
>     backend"*
> 13. *"are you getting, we are shifting to great minimalistic chatgpt like chat
>     interface, but great shts at backend"*
> 14. *"add as less buttons and elements poosible, just keep shit very simple and
>     minimallll"*
> 15. *"front end very easyy to useee with less elements but with great chatgpt
>     design, but at backend doing peak loops, graphs, shitttsss"*
> 16. *"it should look peakk for an officer"*

**On the look**

> 17. *"and fix the design like it should look premium like chatgpt chat interface
>     with buttons and all elements whitish and very sexy lookin, just copy
>     chatgpt s chat design interface and for even graph designs liek chatgpt
>     hasss"*
> 18. *"just simply copy every chatgpts design elementtttt"*
> 19. *"just simply copy everything from chagptsssss design every depth element"*
> 20. *"at every point, pure lookin like chatgpt"*

**On the name**

> 21. *"and just remove that 'caselens' name and that logo of caselens from every
>     place, just one name 'Suishōdama' both of bot and of page toooo, nothing logo
>     and nothing elseee"*
> 22. *"just one 'Suishōdama' everywhere without any logo or shitt, chatgpt but with
>     great sexy peakkk depth case assistant"*

**On how to carry it out**

> 23. *"keep on deleting any old shit or elements you already did and work on this
>     newww face, product is moving too"*
> 24. *"just keep on deleting old design elementsssss, as you build newww designnn"*
> 25. *"just keep on updating the products neww pivott in readmeesss"*
> 26. *"it needs a big pivoottt now, just keep on digesting evryhting i am saying
>     in prompts to readme to keep shit updated with new pivotts and keep on
>     building"*
> 27. *"its a whole new pivootttt"*

**A note on #17–20, because an agent reading them literally will do the wrong
thing.** "Copy ChatGPT" means the *idiom* — a centred column, a light near-white
ground, a rounded composer with attach and send, a quiet conversation rail, the
message treatment, generous whitespace. It does **not** mean their branding,
wordmark, logo or proprietary assets, none of which are ours to ship. What was
built follows the idiom and carries none of the marks.

### What that means, concretely

1. **There is no offline mode and no fallback. Ever.** `/ask`, `/brief` and
   `/investigate` either run the model or return **503** and say the assistant is
   unavailable. The old graph-lookup fallback is deleted, not disabled. **D22.**
2. **Suishōdama is the product.** One name — spelled exactly that way, macron and
   all — for the assistant and the application. **No CaseLens, no logo, no wordmark, nowhere.** **D24.**
3. **One chat.** No section rail, no Documents/Findings/Memory/Custody panels. A
   conversation, and the graph when an answer has one to show. Everything an
   officer wants he gets by *typing a sentence*. **D25.**
4. **No commands, no syntax, no ids typed by a human.** No slash commands, no
   `@mentions`, and never "type the account number". The officer is not
   technical; he says "the Ludhiana account" and the assistant resolves it with
   its tools. **D26.**
5. **The conversation lives on the case, server-side**, not in the browser. It is
   what makes "and what about him?" work at all, and it means a colleague opening
   the same case sees what was already asked. **D27.**
6. **The depth is in the machinery, not the prompt.** Per-case thread, a referent
   set carried between turns as ids, `claim_type` on the answer contract, act
   tools, self-verification, custody. A longer system prompt is not a mechanism.

### What this supersedes

- **The old design specification is deleted, not archived.** It was §3.5a: the
  Calm Civic Forensic palette, the 60/40 split, the six named workspace sections
  and the labelled tablet drawer. All of it described a product that no longer
  exists, and a dead spec in a file four agents read is something one of them
  will eventually build to. **§3.5 now describes the interface that is actually
  there.**
- **D14, D16, D17 are superseded** by D24–D26 — see the notes on those rows.
- **§10.1a and §10.1b (who owns the front end) are replaced by one section.**
  Kanwar took the interface, then changed it. **Jashan: nothing you built is
  being criticised — the product moved under it.**
- **`docs/demo-script.md`'s offline variant is deleted**, and so is its
  instruction to type an account number, which only ever existed to work around
  the fallback that no longer exists.

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

### 2.5 It is not a chat with a context window — 2026-09-06

**This is the distinction the whole product rests on, and it is the one a judge is most likely to test.** Kanwar, 2026-09-06, in his own words:

> *"one thing we doing different from a simple chat interface with some token context window is that we are proving everyone a brain of their own in each case with graphs and loops which keeps on developing as person interacts and gives more documents so we cant at all work as a one chat as context window, we are just a bot doing calls based on brain and graph of case so its nothing like context window anywheree its personal bot for each case working case's brainn."*

**The mechanism, stated plainly.** A chat assistant holds the case in its context window: the documents are pasted in, the window fills, and what falls out of it is gone. This one holds nothing. **Every case has a brain on disk** — a graph, its analytics, its memory, its custody chain — and the assistant is a **bot making calls against that brain**. It arrives at each turn knowing nothing and asks the case, with tools, in a loop.

**Three things follow, and each one is checkable:**

1. **The brain grows; a window only fills up.** Every document an officer hands over widens the graph permanently, and every analytic re-runs across the whole case. Document forty is not competing for room with document one — it is making document one worth more, because a link needs both ends. *(This is the opposite of a context window, where the fortieth document is what pushes the first one out.)*
2. **The brain outlives the conversation.** Clear the thread and ask again: the same answer comes back, cited to the same nodes. Nothing the officer said is load-bearing; the graph is. **This is the cheapest demonstration of the whole claim and it takes ten seconds** — see `docs/demo-script.md`.
3. **The brain is per case, and it is his.** Not a tenant, not a filter over a shared store — a different file (§2.4). Two officers, two cases, two brains, and no query exists that could reach across.

**What that demands of the interface (D29).** If the brain is the product, the interface has to make it visible without becoming a dashboard again:

- **What the brain holds is on screen at all times** — entities, links, documents — as one quiet line, never a panel. It is the only number in the product, and it is there because it *changes*.
- **When it grows, it says what grew.** A document that adds 37 entities and 214 links says so, in that moment, next to the conversation. That single sentence is the difference between "it uploaded" and "it learned something".
- **The graph is the brain, not an illustration of an answer.** It opens by itself when an answer has a route through it, and the officer can open it whenever he wants to look — that is the "option to graph" the pivot kept (§0.5, #12).
- **What it has worked out is part of the brain, not part of the thread.** Conclusions recorded and questions held open belong to the case and survive the conversation being cleared, so they are shown with the brain and never as chat scrollback.

**What it does not mean.** It is not a licence to add panels back. Everything above is one line of text, one panel that already existed, and no new place to navigate to. The conversation stays the only way in (D26).

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
                        │  5. ONE CHAT  (Suishōdama)             │
                        │  conversation ◀─▶ the case's brain   │
                        │  the graph opens when there is a     │
                        │  route to light                      │
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

### 3.5 The interface — one chat, and the graph when there is a route

**This describes what is built.** It replaced a six-section workspace on the night of 2026-09-05; §0.5 is why, and D24–D28 are the decisions. Anything in this repo that still describes panels, tabs, a section rail or a second product name is stale — delete it, do not build to it.

**The shape.** A case rail on the left, a single conversation in a centred column, and the graph on the right **only when an answer has a route to show**. Nothing else is on screen. The officer types a sentence; that is the entire interaction vocabulary (D26). There is no landing page, no case form, no settings screen and no login: `/` is the same screen with no case open.

**The one behavioural requirement the architecture places on the interface:** when the agent answers, **the exact path it used lights up**. `highlight_path` (§5.3) is an ordered list of node ids, and rendering exactly those — hop by hop, with the real edge between each pair — is what makes the split screen *the reasoning* rather than a picture beside some text. A judge will probe this (D3). **Nothing is ever drawn between two nodes with no edge between them.**

**Beyond that:** a citation must click through to the source text (`GET /source`), and a node must open its profile (`GET /nodes/{id}` — attributes, edges, neighbours, and every document it was extracted from). Both endpoints exist and return real data.

**How the brain is opened, and what it answers to (D37, D38).** Three ways in, and they are the same panel: the **Brain** control at the top right of the conversation, the line under the composer, and an answer's own *show it on the brain*. Escape closes it. Inside, the vocabulary is the hand — drag a node anywhere, click one to open its connections, click it again to fold them away, hover to see what it is and how many links it has, double-click the empty canvas to put everything back on screen. The key along the foot says what each shape means and doubles as a filter: press *account* and every account on screen stands out while the rest fades. None of it destroys anything, and the reset control returns the graph to where it opened.

**The visual language (D28).** Near-colourless on purpose: a white ground, one ink `#0d0d0d`, two greys, `#ececef` hairlines, `#f4f4f5` for a raised surface. **Evidence Amber `#b8791f` is the only saturated colour in the product and it means exactly one thing — this is what the answer rests on.** Danger red is the second exception and it means a verification failed. An officer reads text here for an hour; every accent that is not carrying meaning is competing with the words.

Inter, bundled locally. 15px body at `leading-7`, 13px for anything secondary. Rounded corners, no ornament, no shadow beyond the composer's hairline lift. **Light only** — an officer's tool should not read as a hacker console.

**The idiom is ChatGPT's, and the word "copy" in his instruction means the idiom** (§0.5, #17–20): a centred column, a rounded composer with attach and send, a quiet conversation rail, generous whitespace, actions that appear on hover rather than sitting on screen. It does **not** mean their branding, wordmark, logo or assets, none of which are ours to ship, and none of which are in this repo.


### 3.6 Hash-chained custody log

Satisfies the **Blockchain & Cybersecurity** theme, honestly.

Append-only log per case. Every document ingested and every inference the system makes gets an entry, hash-linked to the one before it. Tampering with any earlier entry breaks every hash after it. Format in §5.4.

In the real domain this matters because evidence handling has to be auditable; in the demo it takes ten seconds to show and it is a genuine answer to "where's the blockchain?" that doesn't involve inventing a coin.

### 3.7 The end-to-end trace

Follow this when you're unsure how your piece connects to the rest.

1. Officer opens **Case #114**. An empty conversation, an empty graph, a fresh custody chain.
2. Uploads three FIR PDFs, a CDR export for two numbers, one bank statement.
3. **Ingest** pulls text, regex takes the identifiers, NER takes the names — every extraction carrying its document and offsets.
4. **Graph** builds: entities deduped into nodes, CDR rows into `CALLED` edges, transactions into `TRANSFERRED_TO`, same-document mentions into `CO_OCCURS`.
5. **Analytics** run on write. Betweenness, PageRank, communities, temporal spikes — all cached.
6. Officer asks: **"How is Ravi connected to the Ludhiana account?"**
7. **Agent** calls `path_between("person:ravi", "account:...")`. Graph returns `Ravi → phone 98xxx → tower co-location 3 Aug 22:10 → Suneel → account`. Agent calls `read_source_doc` on the two edges sourced from FIRs to verify them. Writes one sentence, returns cited node and edge IDs plus `highlight_path`.
8. **The chat** shows the answer; the brain opens on the right and lights exactly that path, hop by hop. *Rests on 5 entities* under the answer opens the trail, and one click on an entity opens the line of the FIR it was read out of.
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

### 3.10 Huge documents, and the context that must not grow with them

**Read this before you add a tool, a metric or an ingest step.** Everything here was measured on 2026-09-06, on a case built from a 2,000-row CDR and 106 KB of prose — *small*, next to a real case file — and every number below is from that machine, not an estimate.

**The claim in §2.5 is only true if it is true at size.** A per-case brain that the assistant queries with tools is not a context window — but that stops being a distinction the moment the tool *results* grow with the case, because then the case is back inside the prompt and the thing degrades into exactly the chatbot we say it is not: slower and more expensive with every document, until it stops answering.

Four things were wrong, and each one had the same shape — fine on the demo case, fatal on a real one.

**1. Ingest was quadratic, three times over.** 27 KB of prose took 5s, 53 KB took 16s, 106 KB took **63s**; a 1 MB chargesheet bundle would not have finished. Every one was a scan of the whole document repeated per item in it:

- the identifier extractor asked *"does this overlap anything claimed so far?"* by walking every earlier claim — 72 million comparisons on one CDR. It is a byte mask now.
- the seen-window sorted every date in the document for every entity in it — 48 million. It is a bisect now.
- a CSV row's character span re-split the entire file, per row. The line offsets are computed once.

**106 KB now takes 3.8s, and it is linear** — 8x the document costs 7.4x the time, asserted by `test_ingest_is_linear_in_document_size`.

**2. Provenance grew one entry per mention.** A man named 400 times carried 400 offsets, re-read and re-serialised on every upsert — which is what made ingest quadratic — and then arrived in the model's context as a **23,000-character node**. A citation needs *a* place in the document, not every place: the store keeps **three offsets per document** and the count is written separately as `prose_mentions`, which is a more useful fact than the offsets were. That node is now 350 characters.

**3. No tool result had a ceiling.** `timeline` returned **419,224 characters** — about 105,000 tokens — in a single call. `communities` returned 81,035. The only limit anywhere was a `[:60000]` slice of the JSON string, which cut **mid-object**: on any case big enough to reach it, the model was handed text that was not valid JSON, with nothing saying so.

Now every tool result passes through one bound (`agent/loop.py`, `_json`): graph rows are slimmed to what an answer can use, lists are capped, and anything still over **12,000 characters** is shrunk *structurally* — fewer items, never half an item — with a note telling the model what was cut and to narrow the question. **The model sees a constant amount of the case however large the case gets**, and `test_no_tool_can_put_more_than_its_ceiling_in_front_of_the_model` asserts it against a literal, not against the constant.

**4. Betweenness is exact only while exact is affordable.** It was **36.4s of a 38.7s recompute** on a 2,685-node case, and a recompute runs after every ingest. Above **500 projected nodes** it is estimated from 128 sampled pivots with a fixed seed — deterministic, same numbers on every machine, and it preserves the ranking at the top, which is all any finding reads. **The demo case is 125 nodes, so it is still exact to the last decimal.** Where it is an estimate the system says "about" in the sentence the officer reads, because an estimate read out as a measurement is the thing a judge asks the method of.

**What this does not fix, and you should know it before you promise it:** a 50,000-row CDR still takes about a minute and a half to ingest and recompute. That is linear and it is honest, but it is not instant, and nothing in the interface currently tells an officer how long a large file will take.

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
| D14 | ~~**The backend builds no UI and makes no design decisions**~~ **SUPERSEDED 09-05 (§0.5)** | True while the front end was Jashan's. Kanwar took the interface on 09-05 and then pivoted it; §10.1a records who owns what now. | 09-04 |
| D15 | **Proximity linking is for prose only, and claims the nearest name only** | Both learned by measurement, not opinion. Running co-occurrence over a CDR export links whoever sits in adjacent rows and added 606 meaningless edges, burying the real structure. And linking every person within the window to a nearby number gave Ravi ownership of Manjit's phone, which then produced a real-looking false path. | 09-04 |
| D16 | **Frontend stack: React + Vite + TypeScript, Tailwind v4, Cytoscape.js, TanStack Query, React Router, Lucide** | Jashan's original choice, and it survived the pivot intact — the stack was never the problem. **Radix is no longer used**: the pivot removed every dialog, dropdown, tab and tooltip it was there for. | 09-05, revised 09-06 |
| D17 | ~~**Calm Civic Forensic visual language; light mode only**~~ **SUPERSEDED by D25/D28 (§0.5)** | The light-only half survived and is now D28. The palette, the 60/40 split and the six sections it named describe a product that no longer exists; the spec that carried them is deleted, not archived. | 09-05 |
| D18 | **A document we could not read must say so; it must never ingest in silence** | A scan has no text layer, so every step after the reader succeeds on an empty string — the document registers, custody records it as evidence received, and no entity ever appears, with nothing saying why. That is worse than an error, because it is indistinguishable from a document that had nothing in it. `read_document` counts blank pages and returns a `warnings` list; `POST /documents` passes it through and **the front end must display it**. Adding OCR is a *separate* decision and is not taken here (§13). | 09-05 |
| D19 | **The two sources added last introduced no new node or edge type** | §5.1 is frozen and the front end is being built against it three days out. A social handle is an `account` namespaced by platform, a prior case is an `event`, and what kind of link a `CO_OCCURS` is gets said in `attrs.basis` — where `text_proximity`, `cdr_handset` and `co_accused` all already live. A `FOLLOWS` and a `CHARGED_IN` edge would each read better and would each cost a contract change, a message to four people and a front-end update. **If you are about to add one, this is why it is not there.** | 09-05 |
| D20 | **An intelligence report is graded, and what it implies is discounted** | §1.1 names intelligence agency reports as a source, and until now one was read as an ordinary note — an uncorroborated tip from an untested source entered the graph at exactly the confidence a bank record does. Intelligence carries the Admiralty grading (reliability A–F, credibility 1–6) for precisely this reason, and it maps onto §5.1's `confidence` almost exactly. The factor is the **lower** of the two axes, not their product: they are independent judgements in the standard and multiplying them invents a precision we do not have. An ungraded intelligence report still gets 0.7 — no grading is not the same as a good one. | 09-05 |
| D21 | **`_hidden_brokers` ranks people against people** | Its bar was the fifth-highest betweenness across *every* node, and then only people were ever candidates. On the demo case three of the top five are a document, a bank statement and a travel agency — so "top five" quietly meant "top two people", and **the more documents an officer uploaded the fewer brokers the case could surface.** Adding the criminal-history source pushed the kingpin to sixth overall and deleted demo query 2 outright. The graph was right; the yardstick was wrong. Guarded by `test_the_broker_threshold_ranks_people_against_people`. | 09-05 |
| D22 | **There is no offline mode and no fallback. Ever.** | Kanwar's call, 09-05: *"why do we need that offline analysis anywhere, dont keep that at all."* `/ask`, `/brief` and `/investigate` either run the model or return **503** saying the assistant is unavailable. A degraded impostor that answers some questions and silently cannot answer others is worse than an outage, because the officer cannot tell which one he is talking to. **The key and a working network are demo-day requirements.** `backend/agent/offline.py` is deleted, not disabled. | 09-05 |
| D23 | **A finding's `node_ids` is never returned as an answer's `highlight_path`** | The UI walks `highlight_path` hop by hop as an ordered route. A finding's `node_ids` is an unordered *set* — `[harbhajan, cdr_doc, ldh_031, jaswant, balraj, device]` is not a journey anyone can take — so returning the set as a path draws a route that does not exist, which is D3 inverted. A finding answer lights its subject only; the rest of the set is still cited and Evidence shows it. | 09-05 |
| D24 | **One name: `Suishōdama` — spelled exactly that way, capital S and the macron — for the assistant and the product. No logo.** | Kanwar's call, 09-05: *"just one 'Suishōdama' everywhere without any logo or shitt."* The spelling is fixed by the team name on the SIH submission form (09-06), so it is written the same way in the interface, the page title and this file. CaseLens was a second thing to learn for no gain — an officer does not need a brand between him and the case. The assistant has a name because you talk to it; the application does not need one on top. | 09-05 |
| D25 | **One chat interface. No section rail, no panels.** | *"just one chat interface and option to graph… one clean chatgpt like interface, but great shit at backend."* Six navigable sections is a filing cabinet, and an officer under time pressure does not explore a filing cabinet. Everything the panels showed — documents, findings, memory, the custody chain, an entity's profile — is reachable by asking for it, which is one skill instead of six. The graph appears when an answer has a route to show. | 09-05 |
| D26 | **Nothing is invoked by syntax. No slash commands, no ids typed by a human.** | *"the bot should only fire from chat message, because we are making for non technical peopleee."* A command language is a second product the officer has to learn, and the moment one exists the interface has two classes of user. He says "the Ludhiana account" and the assistant resolves it — resolving it is the assistant's job and it has `find_entity` to do it with. | 09-05 |
| D27 | **The conversation is stored on the case, not in the browser** | A teammate remembers the line above. `ask` used to send `messages=[{one prompt}]`, so the officer was reading a thread and talking to something with no memory of it — "and what about him?" could not work because there was no him. The thread is a table on the case: it survives a reload, reaches a colleague opening the same case, and is what makes multi-turn possible at all. The referent set (the ids the last answer rested on) is carried forward **as ids**, because asking a model to remember harder is not a mechanism. | 09-05 |
| D28 | **Near-colourless interface; Evidence Amber is the only saturated colour and it means one thing** | An officer reads text here for an hour. Every accent not carrying meaning competes with the words. One ink, two greys, hairline borders — and amber exclusively for *this is the path the answer rests on*, so the one colour in the product is also the one claim that matters. | 09-05 |
| D29 | **The case's brain is a visible, growing thing — not a context window, and not a dashboard either** | Kanwar's call, 09-06: *"we are just a bot doing calls based on brain and graph of case so its nothing like context window anywheree."* A chat assistant that pastes documents into a window forgets the first one to fit the fortieth. This one holds the case on disk and queries it, so the fortieth document makes the first worth more. The interface shows what the brain holds, says what grew when it grows, and lets the officer open it — in one line of text and one panel, because D25 still stands. §2.5. | 09-06 |
| D30 | **Every tool result is bounded before it reaches the model** | Measured 09-06: `timeline` put 419,224 characters — ~105k tokens — into one tool call on a *small* case, and the only limit was a string slice that cut mid-object and produced invalid JSON. If the size of the case decides how much text reaches the model then the case is the context window, and §2.5 is a slogan rather than an architecture. Truncation is structural and always announced. §3.10. | 09-06 |
| D31 | **Provenance is capped at three offsets per document; the count is kept separately** | One entry per mention made ingest quadratic (63s for 106 KB) and put a 23,000-character node in front of the model. A citation needs one place in the document — `read_source_doc` opens it — and *named 400 times* is a better fact than 400 offsets. `prose_mentions`, and it says prose because that is all it counts. §3.10. | 09-06 |
| D32 | **Betweenness is exact below 500 projected nodes and estimated above it — and says which** | It was 36.4s of a 38.7s recompute, and a recompute runs after every ingest. Sampled pivots with a fixed seed are deterministic and preserve the top of the ranking, which is all a finding reads. The demo case stays exact. An estimate is never read out as a measurement: the sentence says "about". §3.10. | 09-06 |
| D33 | **Anything the officer cannot see, he can ask for — including the custody chain** | The pivot removed every panel (D25), and with them the only surface for the *Blockchain & Cybersecurity* beat the round is judged on. `chain_of_custody` is a read tool, so *"has this been tampered with?"* is answered in the conversation like everything else. §5.2. | 09-06 |
| D34 | **The graph opens on a readable core and opens further where he asks it to** | 116 entities and 1,148 links arriving as one cloud of identical grey dots is a picture of *having* a graph, not a way of reading one. It opens on the answer's own nodes, or on people and organisations plus the phones, accounts and places that bridge two or more of them — a network rather than a grid of islands — and every node fans out to its own neighbours on a click, born at its parent so the eye keeps hold of where it came from. Nothing already on screen moves. | 09-06 |
| D35 | **A type is drawn, not written** | Shape carries it (ellipse, round-rectangle, hexagon, pentagon, rhomboid, diamond, barrel, cut-rectangle, rectangle) and a desaturated tone second, so it survives a projector and a colour-blind judge. This is the one surface in the product that is a diagram rather than prose, and in a diagram the type of a thing *is* meaning — so D28 is kept rather than bent. **Evidence Amber is untouched** and overrides type whenever a node is lit. Node size is degree, which is the case's own argument about who matters. | 09-06 |
| D36 | **Every node opens to what is inside it** | The entity panel lives *inside* the brain panel and never beside it (D25). It lists every document the entity appears in, each row opening to the exact passage with its character offsets — the same trail `Evidence` draws under an answer, because a thing clicked on the picture and a thing read in a sentence are the same thing. Its connections are listed and clickable, which adds them to the graph and opens them. | 09-06 |
| D37 | **The brain has a control of its own, above the conversation** | Kanwar's call, 09-06. It could only be opened by pressing the line under the composer or an answer's own *show it on the brain* — both of which require something to have happened first. An officer who has just opened a case and wants to *look* at it had nowhere to press. One button, top right, beside the case's name; Escape closes it. The line under the composer still opens it and still carries the argument. | 09-06 |
| D38 | **The graph answers the hand** | *"should be appealing to interact."* Nodes are draggable — this **reverses** the earlier "a thing to read, not to rearrange", because a force layout puts two names on top of each other often enough and an officer's own arrangement of a network is part of how he thinks about it. A click opens an entity and **the same click again closes it**, taking everything that came in behind it, so four levels deep is reversible without starting over. Hovering grows a node, rings it in its own outline and names it. The key at the foot doubles as a filter. Nothing is destroyed by any of it and the reset control puts it all back. | 09-06 |
| D39 | **Cytoscape's own press feedback is switched off, and nothing replaces it with a shape of its own** | Out of the box a press answers with a translucent grey disc under the node, and another under the cursor when the canvas is dragged — *"those circles whenever i slide or click"*. On a near-colourless product it is the loudest thing on screen, it says only "you pressed", and it covers the thing being pressed to say it. Feedback is now a border, which follows the node's real shape: a circle drawn around a hexagon is a second shape competing with the one that carries meaning. | 09-06 |
| D40 | **The first frame is composed, not revealed** | The graph is fitted synchronously, before it is ever painted. The tempting alternative — hold the canvas at `opacity: 0`, fade it in once a frame callback has fitted it — makes *visibility itself* depend on a frame arriving, and its failure mode is a graph that is perfectly correct and completely invisible. That is the bug this panel has already produced twice (the `square` shape, 09-06 earlier). A late frame now costs an unfitted moment, which is visible and recoverable. | 09-06 |
| D41 | **No web tool. The officer browses; we make what he brings back useful.** | Kanwar's call, 09-06: *"lets not keep it anywhere for now, we can tell user to go through browser themselves and get us the info and our bot will make that shit peak after that."* It had been a logged stub with no provider — the boundary built and the decision deferred. Deleting it settles the deferral in the honest direction and buys a claim worth more than the feature: **the only thing in this product that reaches the network is the model call.** Everything else — ingest, the graph, every analytic, the custody chain, the memory — runs on the officer's machine. `search_web` is deleted, not disabled, and `web_search` went from the custody action list with it. | 09-06 |
| D42 | **Prompt caching, and the system prompt split in two to make it work.** | The tool loop re-sent its whole accumulated context on every one of up to 14 iterations at full price, and nothing in the codebase cached anything — a heavy question cost roughly the *sum* over its iterations. `_system()` now returns two blocks: the standing instructions with the breakpoint on them, and the case's changing numbers after it. One string would have thrown the cached prefix away on every ingest, because caching is a prefix match. Top-level automatic caching covers the growing loop. Caching is an optimisation and never a reason an officer gets no answer, so a rejected breakpoint retries once uncached. `effort` stays `high`: caching is free, effort is a quality trade. | 09-06 |
| D43 | **The name is `Suishōdama` — capital S, macron, spelled exactly that way.** | It is the team name on the SIH submission form, so the product carries the same spelling the judges already have on paper. This replaces D24's lowercase rule outright: the two `lowercase` classes in the interface were removed, because the source said `Suishōdama` while the screen said `suishōdama` and only looking at it caught that. The stored conversation role is ASCII `suishodama`, matching `officer` beside it — a database enum is not a place for a macron. | 09-06 |
| D44 | **Nothing speaks unprompted. The officer asks; it answers.** | Kanwar's call, 09-06: *"just remove any always running or unprompted callsss, we dont need them, an officer can ask it anything when needed."* Opening a case fired `/brief` — a full model call — and it refired whenever it was refetched: an answer records conclusions, conclusions make new findings, and the next refetch saw fresh ones and ran the model again. **Two typed questions produced five billed calls, three unprompted, one of which returned nothing usable.** `askCase` is now the only thing in the interface that reaches the model. `/brief` still exists on the API; he gets a briefing by asking for one. The "assistant unreachable" banner moved onto `GET /api/health`, which costs nothing — it was previously discovered by making a paid call and watching it fail. | 09-06 |
| D45 | **The computed findings go in the standing brief, and a finding outranks a ranking.** | Asked *who matters most*, the agent named the woman on 38% of shortest paths — who is named in four documents and whom the officer already knows. The `hidden_broker` finding naming a man in **no** report was #1 of 26 in the analytics layer and the model never saw it: the brief carried counts, conclusions and open questions but not findings, and §3.4's "lead with the finding" was an instruction with no findings attached. The brief now carries them, with the rule that **if a finding names someone the paperwork does not, that person opens the answer**. Paid for by stripping node and edge id lists out of memory entries — eight conclusions were 10,600 characters of which the model needs the sentence, and they grow as the case is worked, which was putting case size back into prompt size. **Net cost: negative.** | 09-06 |
| D46 | **The universal prompt carries no case in it.** | Kanwar's call, 09-06: *"no demo case names or shit s anywhere pleasee, it a real peak tool after all — then only we can check if it works well for every other case."* The system prompt is sent for every case of every kind, and three of its worked examples were lifted from the trafficking demo: two suspects by name, a tower co-location, a place, and a real account id. An officer working a fraud was being handed someone else's case as the model of a good answer. Rewritten to teach the same rules with no case in them, and **18 characters shorter than before**. A test now fails on any planted name, any 10-digit identifier, or any concrete node id in that block. | 09-06 |
| D47 | **It volunteers.** | The pitch has always been that a tool shows what you already suspect while this one surfaces what you did not ask about (§2.3) — and the prompt never said so. One clause added, paid for by compressing the memory paragraph. First live answer after it went in ended with *"One more thing you didn't ask about"* and named **Simran Bedi**, a second independent Ludhiana–Delhi bridge that **is not in the planted ground truth** (§9.1). Every claim it made about her was checked against the graph and holds; it under-stated twice. | 09-06 |

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
| `chain_of_custody` | `(limit: int = 12)` | `{intact, entries, broken_at, reason, recent: [...]}` — **added 2026-09-06.** The interface has no custody panel any more (D25), so *"has this been tampered with?"* was a question about the one property the theme is judged on that the assistant had no way to answer. |

**There is no web tool, and there must not be one (D41).** Kanwar's call, 2026-09-06: *"lets not keep it anywhere for now, we can tell user to go through browser themselves and get us the info and our bot will make that shit peak after that."* The officer searches the web himself and hands what he finds to the case as a document; the system's job starts there. **No tool reaches the network except the model call itself** — `search_web` is deleted, not stubbed, and `web_search` is gone from the custody chain's action list with it.

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

`hash = sha256(prev_hash + canonical_json(entry_without_hash))`. The first entry uses `prev_hash = "0" * 64`. `action` is one of `ingest` · `extract` · `infer` · `query` · `export`. *(`web_search` was removed on 2026-09-06 with the tool that wrote it — D41. No custody file has ever contained one: it was never bound to the model.)*

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
2. **`/brief` returns deterministic findings *and* a narrative — and with no model it returns neither.** `findings` is computed from the graph and needs nothing external; `narrative` is the model's version of them. **But `/brief` itself is a 503 when the model cannot be reached** (D22): there is no degraded briefing carrying the findings with an apology in `caveats`, because a fallback is exactly what was deleted. `/ask` and `/investigate` are the same. The interface says the assistant is unreachable and that the case is untouched, and it says it on opening the case rather than after he has typed a question. **`verified` is always present**, including on a case with no documents, where it reports a pass with nothing in it (`contract.verified_vacuously`) rather than being absent.

3. **`highlight_path` is the render instruction.** It is an ordered list of node ids. Lighting exactly those, in order, is what makes the graph the reasoning rather than a decoration (D3).

---

## 6. Repo layout

Actual, as built.

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
    store.py        one SQLite file per case; nodes, edges, docs, analytics, agent_memory,
                    and the per-case conversation (D27)
    nx_adapter.py   NetworkX views, path finding, project_people (D13)
  analytics/
    metrics.py      betweenness, pagerank, degree, Louvain, the `why` strings
    anomalies.py    spikes, handset swaps, one-way accounts + the findings layer (§3.8)
  agent/
    tools.py        §5.2 read tools + the act tools
    contract.py     §5.3 schema and verify() — the citation check
    loop.py         ask / brief / investigate, tool_runner. No fallback path (D22)
  custody/
    chain.py        the hash chain (§5.4)
  api/
    main.py         FastAPI — §5.6, the front end's contract
frontend/           React + Vite + TypeScript — one chat (D25)
  src/pages/Chat.tsx          the whole product: rail, conversation, composer
  src/components/             the graph panel and the evidence trail
  src/lib/api.ts              the §5.6 client
  src/types.ts                the §5.1/§5.3/§5.6 shapes, mirrored
  src/index.css               the palette (D28) and the two animations
data/
  cases/            per-case stores (gitignored)
  synthetic/
    generate.py     the demo case generator + the planted ground truth
    tamper.py       breaks/restores a synthetic case's custody chain (§9.3 live)
    out/            the generated CSVs, FIRs and GROUND_TRUTH.json
tests/
  test_core.py      the planted-truth assertions and the regression guards
docs/
  demo-script.md    the run sheet for the 8th
  demo-fraud-complaint.txt   the §6 crime-type-agnostic beat, uploaded live
```

---


## 7. Setup

**Stack:** Python 3.11+ (verified on 3.12) · FastAPI · NetworkX · SQLite · Anthropic SDK. Frontend: Node.js 20.19+ or 22.12+ · React · Vite · TypeScript · Tailwind CSS v4 · Lucide · Cytoscape.js · TanStack Query · React Router. **Radix, clsx and tailwind-merge were removed on 09-06** — they were there for the dialogs, dropdowns, tabs and tooltips of the workspace the pivot deleted.

**Everything runs from the repo root**, not from `backend/` — `data.synthetic` and `backend.*` are one import tree, and splitting the root breaks it.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate  elsewhere
pip install -r requirements.txt

cp .env.example .env            # then put the key in .env — see §8

python -m data.synthetic.generate --case demo-114   # build the demo case (§9)
python -m pytest tests -q                           # 38 tests, all should pass
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

**Most of it runs without an API key** — ingest, the graph, analytics, findings, custody and the whole brain panel need no model at all (D4, D11), so a cold clone can build the demo case and explore it. **`/ask`, `/brief` and `/investigate` return 503**, because D22 deleted the offline path on purpose: no key or no network means no assistant, and nothing pretends otherwise. *(This paragraph promised a deterministic fallback and `caveats` until 2026-09-06 — the thing D22 removed on 09-05.)*

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

**And one the generator made without anyone planting it.** Asked who matters most on 2026-09-06, the assistant volunteered **Simran Bedi** — unnamed in any FIR, whose handset hits four Ludhiana towers and three Delhi ones and who is in direct call contact with both Manjit Singh and Suneel Kumar. **That is a second Ludhiana–Delhi bridge, independent of the Gill Travels money trail, and it is not in `GROUND_TRUTH.json`.** Every claim was checked against the graph afterwards and holds. Worth knowing before a judge asks, because it is the strongest evidence available that the system analyses rather than recites: nobody designed that finding.

### 9.2 The two queries we demo

**1. "How is Ravi connected to the Ludhiana account?"** — proves the graph causes the answer. The route lights hop by hop on the brain, and *Rests on 5 entities* opens the trail down to the line of the FIR the claim was read out of.

**2. "Who matters most in this case?"** — the system names a man who appears in **zero FIRs**, found by betweenness bridging two clusters that otherwise never touch. Then his row in the evidence trail reads *read out of 1 document* — a call log — and he really is in no report.

That second one is the moment the room understands what the system does. Everything else is setup for it.

### 9.3 Then the theme

**Ask it** — *"has anything in this case been tampered with?"* — and it answers off the chain (D33). Break one entry with `data.synthetic.tamper`, ask again, and it names **entry 2** and why. Restore, ask once more: intact. Ten seconds, and it answers "where's the blockchain?" before anyone asks it. There is no custody panel to open; after D25 there is nothing to open anything from.

---

## 10. Ownership and the 24 hours

### 10.1 Workstreams

Contracts (§5) are frozen in the first hour so these can run in parallel without meeting until integration.

| Workstream | Scope | Owner | State |
|---|---|---|---|
| A · Ingest & extraction | PDF/CSV parsing, regex, NER, provenance | Kanwar | **built** |
| B · Graph & analytics | schema, SQLite store, NetworkX, the four algorithms | Kanwar | **built** |
| C · Agent & tools | tool implementations, agent loop, answer contract | Kanwar | **built** |
| **D · Everything the user sees** | the whole interface — one chat, the graph panel, the evidence trail | **Kanwar**, since 09-05 (§10.1a) | **built**, and rebuilt by the pivot |
| E · Synthetic data | the generator and the planted structure (§9.1) | Kanwar | **built** |
| F · Custody + demo script | hash chain, `docs/demo-script.md`, the run-through | Kanwar / `UNASSIGNED` | chain built, script not written |

**Roster is `UNKNOWN`.** Known so far: **Jashan Garg** (repo owner), **Kanwar Sekhon**, **Gurpartap** (holds the API key). SIH requires six with at least one woman. **Whoever knows the full roster: fill this table in and delete this line.**

### 10.1a Who owns what — rewritten 2026-09-06

**This replaces the old §10.1a/§10.1b split, which said the backend builds no UI. It has not been true since 09-05 and it must not be followed.**

**Kanwar owns both halves right now** — ingest, graph, analytics, the agent, custody, the HTTP API, *and* the interface. The front end moved to him on the evening of 09-05 because the workspace was the only thing standing between a working backend and a demo, and then the pivot (§0.5) replaced that workspace with one chat.

**Jashan built the shell and the Cases screen at 02:09 on 09-05, and none of it was wrong.** The product moved under it. If he picks the interface back up, **§3.5 is the specification** and his judgement on how it looks still wins — but it has to be the interface in §3.5, not the one in the spec that used to be here.

**Where the boundary is, if the front end splits again:** `frontend/` is one side, `backend/` + `data/` + `tests/` the other, and **§5.6 is the seam**. It is frozen and it has not moved through two interface rewrites, which is the whole reason those rewrites were cheap.


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
| 16–20 | Custody chain, the evidence trail, polish |
| **20–22** | **Integration #3 — feature freeze.** Nothing new after this. |
| 22–24 | Demo rehearsed end to end at least three times, on the demo machine, **with the key loaded and the network checked** (D22 — there is no offline run) |

**Feature freeze at hour 20 is not negotiable.** A demo that has been run three times beats a better system that has been run once.

---

## 11. Current state

**Updated 2026-09-06. Whoever changes this project: change this section too.**

**Everything is built, and the live model call has now run — nine of them.** The backend is feature-complete against §1.1, the interface is the one chat of §0.5, and the agent loop was exercised end to end against the real Anthropic API on 2026-09-06 evening on Kanwar's own key. `docs/demo-script.md` is written and current.

| Part | State |
|---|---|
| Ingest — PDF/CSV/text, regex identifiers, cue NER, provenance | **built, tested** — PDF exercised against a real file, readable and scanned |
| **Ingest at size** | **linear, measured** (09-06) — 8x the document costs 7.4x the time; three quadratics removed. §3.10 |
| Sources — all seven of §1.1 | **built, tested** — see §1.2a |
| Graph — SQLite per case, §5.1 schema, idempotent merge | **built, tested** |
| Analytics — betweenness, pagerank, degree, Louvain, anomalies, findings | **built, tested**; betweenness exact under 500 projected nodes, estimated and labelled above it (D32) |
| Agent — 9 read tools + 5 act tools, tool loop, §5.3 contract, self-verification | **built and run live** (09-06) — nine real calls, every citation verified against the graph |
| **Tool results — bounded** | **built, tested** (09-06) — nothing can put more than 12,000 characters in front of the model, whatever the case holds. D30 |
| **Prompt caching** | **built and verified live** (09-06) — two explicit breakpoints plus top-level automatic caching on the tool loop. Measured across nine real calls: **2 input tokens at full price on every one**, the rest served from cache. **$0.0235 a question**, down from ~$0.10. D42 |
| Custody — hash chain, tamper detection, **reachable by asking** (D33) | **built, tested, and now run live** (09-06 night) — the §9.3 beat performed end to end: chain broken, asked in the chat, **it named entry 2 and why**, restored byte-identical |
| API — every endpoint in §5.6 | **built**, returning real data |
| Demo case — generator + planted ground truth | **built, tested** — **125 nodes: 116 entities and 9 documents**, 1,148 links. The interface says *116 entities · 1,148 links · 9 documents*, because a document is a node but it is not an entity and an upload reports the two separately. |
| **Front end — one chat** | **built, driven in a browser against `demo-114` (2026-09-06)**: the thread, the evidence trail, the brain panel with the route lit hop by hop, upload by paperclip and by drag-and-drop, and the brain line reporting what each document added |
| **The brain panel — interactive** | **rebuilt 2026-09-06, and driven again the same evening.** Opens on a readable core laid out into the shape of the panel, every node opens on a click and **closes on the next one**, nodes are draggable, hover names them, and the key at the foot filters by type. Reached by its own **Brain** control. D34–D40 |
| `docs/demo-script.md` | **written, current with the pivot** |

**`python -m pytest tests -q` → 38 passed** (re-run 2026-09-06 night, 78s). What that covers, beyond the §9.1 plants:

- The kingpin is named in **no report** and the system **leads with him** (§9.2 query 2).
- Ravi reaches the Delhi account **through the tower**, and no call between the two numbers exists, so the system cannot claim contact (§9.2 query 1).
- Two cases of different kinds share nothing; altering one custody entry breaks the chain **at that entry**.
- A real two-page FIR in PDF reaches the graph and its citation opens; **a scan says it could not be read** instead of ingesting in silence.
- No source added after 09-04 crosses the Ludhiana/Delhi divide, so the kingpin is still the only bridge.
- An upload over HTTP is filed under **the officer's** filename, in the document list, the citations and the custody chain.
- **Ingest is linear in document size**, and the guard fails if any one of the three quadratics comes back.
- **No tool can put more than its ceiling in front of the model**, and what it does return is still valid JSON.
- A man named 400 times keeps **three offsets and the count**, and the offset that is kept still opens.
- Betweenness is **exact on the demo case** and **says "about"** when it is an estimate.

**Every new guard was mutation-checked** — the fix reverted, the test watched to fail, the fix restored. Three of the five did not fail the first time: two asserted against the same constant they were testing, which passes at any setting, and one had a bar loose enough to sit on both sides of the bug. **A guard that has never failed is not a guard**, and two of these had to be rewritten before they were.

**Not done, and honest about it:**

- **The agent loop has run against the live API — nine calls on 2026-09-06 evening.** The key is **Kanwar's own, with about $3 on it** (§8), which is a demo budget rather than a development one; **$0.21 of it is spent.** What was verified live: it refuses to invent a document that does not exist; it distinguishes proximity from contact unprompted; it leads with the hidden-broker finding; it synthesises across bank, CDR and criminal-history in one answer; and **clearing the thread and re-asking returns the same finding with the same citations** — §2.5's claim, demonstrated. **The custody/tamper beat of §9.3 has now run too** — see the bullet below; there is nothing left in the demo that has never been performed.
- **The custody beat ran live on the night of 2026-09-06, and it passed.** The chain was broken at entry 2, the question was typed in the chat, and the answer named **entry #2** and the reason — *"the recorded content no longer matches its stored hash… altered after it was logged, not new evidence added"* — then the chain was restored to a byte-identical head. Two things worth knowing that only a live run showed. It **refused to over-claim**: *"I don't have the actual content of that broken entry #2 in front of me… so I can't yet tell you which document, edge or conclusion it altered"*, where inventing a filename was the easy failure. And it exercised a path nothing else had — **an answer that cites zero graph nodes** — without erroring or being branded unverified. One overreach, said here because nothing else will say it: the answer claims the later entries *"all sit correctly on the hash chain"*, which **no tool told it** — `verify()` stops at the first break and never checks 3–61. It is true by luck, not by evidence.
- **The cost figures in this file are floors, not the bill.** `_log_usage` (`loop.py:854`) runs **once per question**, on the final message the SDK's `tool_runner` returns after the whole loop has finished — so each row in `output/cost.jsonl` is the **last request** of that question, not the sum over its iterations, exactly as its own docstring warns. The ledger reads **$0.2288 across 10 rows**; the real spend against the ~$3 is higher by however many iterations each question took, and **nothing on this machine knows that number.** Read the Anthropic console for the true figure before the 8th — on this budget a 2–3× error matters.
- **A 50,000-row CDR takes about a minute and a half** to ingest and recompute. Linear and honest, but not instant, and nothing in the interface tells the officer how long a large file will take.
- **Nothing in the product reaches the network except the model call.** The web tool is deleted (D41): the officer browses himself and hands over what he finds.
- **A scanned PDF is announced, not read.** No OCR; whether scans are in scope is still §13's question.
- **`prose_mentions` counts prose only** — a structured row's mentions are not counted, and the attribute name says so. Volume in a CDR is already visible as links.
- **The cue NER reads two intelligence frames, not every one.** Widening the regex to leap a clause is the D15 bug again.
- **exposurie** (Kanwar's other project) is paused for this.

**What the interface reaches, and what it deliberately does not.** Thirteen of §5.6's twenty-two endpoints are called from the chat: the case list and its lifecycle, the conversation and clearing it, `/ask`, `/brief`, `/documents` (upload), `/graph`, `/nodes/{id}`, `/source` and `/memory`. **The other nine are reached by asking** — `/path`, `/timeline`, `/analytics`, `/custody` and `/findings/{id}/investigate` are all things the agent's own tools cover, and after D25 that is the design rather than a gap. `POST /documents/text` and `POST /analytics/recompute` have no caller and need none.

**Three defects were found by driving the interface today, and none of them by a test:**

- **`/nodes/{id}` counted one document once per offset.** Ravi Kumar read "out of 12 documents" on a case that holds nine. Deduplicated.
- **The evidence trail showed ids.** `person:manjit_singh` where the officer should read "Manjit Singh" — D26 broken in a screen written the day D26 was written. It fetches the entity before it draws the row now.
- **A case whose assistant is unreachable said nothing** until the officer had typed a question and pressed send. It says so on opening the case.

---


## 12. Changelog

- **2026-09-04** — README created. Problem statement recorded verbatim from sih.gov.in; architecture, decisions D1–D9 and contracts §5.1–5.5 written from the 09-03/09-04 design discussion. No code yet. Roster still unknown.

- **2026-09-04, evening (Kanwar + Claude)** — **the whole backend, built and tested.** Ingest, graph, analytics, agent, custody, API, demo generator, 12 tests. What the next agent needs to know:
  - **Front end is untouched and is Jashan's** — every visual and design decision, not just "the UI layer". New **§10.1a** says so explicitly and **§5.6** is the frozen API he builds against. The backend deliberately built no interface of any kind (**D14**).
  - **New decisions D10–D15.** The agent acts rather than only answering (§3.8); findings are computed from the graph so the system works offline (D11); the engine is crime-type agnostic and the case carries its own type and brief (D12, §3.9); centrality runs on a person-projected graph (D13).
  - **Two contract clarifications, no contract changes.** §5.1 now records the `doc:` prefix exception that was already in its own examples, and the id-normalisation rules. §5.2 gained the act tools.
  - **§7 setup was wrong and is corrected** — everything runs from the repo root (`uvicorn backend.api.main:app`), not from `backend/`. `numpy` and `scipy` are required (NetworkX pagerank needs them). spaCy is genuinely optional.
  - **Three bugs found by measurement, worth not reintroducing** (D15): co-occurrence linking run over a CDR export created 606 meaningless edges and buried the real structure; the ownership heuristic gave one man another man's phone and produced a plausible false path; a name pattern crossed a full stop and merged two people into `person:manjit_singh_accused_sukhwinder`.
  - **Untested:** the live API call. No key on the build machine, and **deferred on purpose** until the rest is built (§11) — nothing downstream is blocked on it, because findings, the graph, analytics and custody all work with no model at all (D11).

- **2026-09-05 (Jashan + Codex)** — **frontend milestone 1 built.** Added the React + Vite + TypeScript application in `frontend/`, bundled Inter locally, established the Calm Civic Forensic tokens, added the 240px/72px desktop sidebar and labelled tablet drawer, and connected the Cases screen to the real `/api/cases` endpoint. Search and filters, detailed case cards, create/edit/pause/close/delete controls, typed-title delete confirmation, persisted officer and accessibility settings, skeleton/empty/reconnect states and four-second success feedback are implemented. Browser QA created a temporary case through the real API, verified it appeared first, then removed that exact temporary case through typed-title confirmation; desktop and tablet layouts have zero browser console errors. `pnpm --dir frontend build`, `pnpm --dir frontend lint` and all 12 backend tests pass. §3.5a records Jashan's locked design direction; D16–D17 record the frontend stack and visual language. Next: replace the temporary case route with the live 60/40 `Suishōdama` + Connections workspace.

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
  - **All six sections are live**: `Suishōdama` (opening brief, conversation with date separators, attachments with per-file progress and Change Type, Copy / View Evidence / Show Path, confidence never invented as a percentage), Documents (upload, D18 warnings, per-document grading), Connections (Cytoscape, community-grouped layout, type tints, three node sizes, dashed inferred links, Search / Filter / Fit / Reset / Legend, node drawer, relationship popover, positions and filters remembered per case), Findings (Investigate posts a real §5.3 answer into the conversation), Memory, Custody.
  - **`highlight_path` renders two different shapes, and the difference is deliberate.** An answer's ordered path lights hop by hop in Evidence Amber with the edge between each pair. A finding's `node_ids` is an unordered set with no hops, so the links *inside* the set are lit instead and the banner says "entities", not "path". Nothing is ever drawn between two nodes that have no edge.
  - **A path through a document node turns document nodes back on** — `/graph` drops them by default — as an override held only while the path is shown, and the banner says so. The officer's own filter comes back when the path is cleared.
  - **Three bugs worth not reintroducing.** Cytoscape injects `__________cytoscape_container { position: relative }` at runtime, which beat Tailwind's `absolute` and collapsed the canvas to zero height — the container is sized inline now, and a `ResizeObserver` calls `cy.resize()` because the panel also changes size on every divider drag and focus toggle. `AnswerCard` read `verified.ok` through a block `/brief` omits on an empty case and white-screened the whole workspace — hence `PanelBoundary`, so one panel failing can never take the case, the graph and the navigation with it. And `/nodes/{id}` returns one entry per citation, so one CDR naming a man 34 times listed the same file 34 times; the drawer groups by document now.
  - **Three defects found and left for the backend, all recorded in §11.** A live upload is filed under the server's temp filename (`tmpXXXX.pdf`) and it reaches the document list, every citation and the custody chain — invisible in the demo case, visible the moment a judge asks to upload something. `/brief` omits `verified` on an empty case. And the offline `/ask` fallback answers names but not questions, which means demo query 1 returns nothing without the key.
  - **`/path` is wired to a real control.** The entity drawer traces a route between two entities in two clicks — open one, "Trace a route from this entity", open the second — which is demo query 1 asked directly on the graph. **19 of §5.6's 22 endpoints are reached from the UI**; §11 names the three that are not and why.
  - **The entity drawer is a docked column on desktop, not an overlay.** Connections is only 40% of the workspace, so a 360px drawer over it left a sliver of graph; the drawer is now a third column and the split is computed over what remains after it. On tablet it stays an overlay, because there is only one column there.
  - **Verified in a real browser, not by reading the code**: the demo case end to end at 1440×900 and 820×1024, zero console errors, the scanned-PDF warning shown to the officer on a real upload, a citation opening on the exact CDR row it came from, and an empty case rendering rather than crashing. `pnpm build` and `pnpm lint` are clean and the backend's 25 tests still pass.
  - `.gitignore` gained `.gstack/` — a scratch directory the browser tooling writes into the repo root. Not project state; ignored so it cannot be committed by accident.


- **2026-09-05, late (Kanwar + Claude)** — **the three open backend defects closed, and `docs/demo-script.md` written. The repo has one unfinished item left: the live model call.** What the next agent needs to know:
  - **An upload is filed under the officer's filename again.** `ingest_file` takes `filename`; `main.py` passes `file.filename`; the name is basenamed because a browser may send a path. **The test goes over HTTP on purpose** — the defect was `main.py` never passing the argument, so a unit test of `ingest_file` would have passed against the bug. Mutation-checked: reverting `main.py` alone fails it with `doc:tmplsegj3yr`.
  - **`/brief` carries `verified` on an empty case** — `contract.verified_vacuously()`, a pass with nothing in it. Not `verify()` on an empty answer, which fails by design; nothing was cited because nothing has been found, and `ok: false` would put a red panel on every new case. §5.6 note 2 updated.
  - **Offline `/ask` routes the question — D22, new `backend/agent/offline.py`.** Two entities named gives the path between them with `highlight_path` set, so the split screen works with no key; an influence question gives the finding; a type word gives what the case holds of that kind; an unresolvable phrase gives **the candidates, named, rather than a confident guess**. §13's offline risk is now answered for both demo queries.
  - **Two bugs the first version of that router had, both caught before they shipped and both worth not reintroducing.** A type word was constraining the *whole sentence*, so "the Ludhiana **account**" resolved *Ravi* to the Instagram handle `@ravi_ldh` and answered about a different Ravi — a type word now qualifies only the phrase beside it. And `_route_influence` answered from raw betweenness, which names **Sukhwinder Kaur** (0.380, in four documents) rather than Harbhajan Dhillon (0.222, in one) — it leads with the `hidden_broker` finding now, because the finding is what encodes *central **and** absent from every report*, and the ranking throws that away.
  - **The influence answer claimed something about the evidence that was not read off the evidence, and driving the UI is what caught it.** It ended with *"the busiest people are … and every one of them is already named in the reports"* — listing the top three by raw centrality. **Gurpreet Singh is on that list and is in no report at all** (a CDR, the criminal register and a social export), so the answer named him one sentence after saying the man who matters is the one nobody reported. It now filters that list through the document kinds and the sentence is true by construction, guarded by `test_the_offline_influence_answer_never_calls_an_undocumented_person_documented`. Every test in this session passed while it was wrong; the browser is what showed it.
  - **D23: a finding's `node_ids` is never returned as an answer's `highlight_path`.** The UI walks that field hop by hop as an ordered route; a finding's ids are an unordered set, so returning the set draws a journey nobody can take. Findings light their subject only.
  - **The kingpin test was weak and the mutation check is what found it.** It asserted `"Harbhajan Dhillon" in answer` — which passed against a version that led with Sukhwinder Kaur and listed him third in a trailing "Then:". It asserts `startswith` now. **A guard that has never failed is not a guard**; all six new behaviours were mutation-checked.
  - **`data/synthetic/tamper.py` makes the §9.3 beat performable.** There was no way to break the chain live — the UI has no tamper control, correctly. One command breaks entry 2, the API names it, `--restore` is byte-identical so the demo continues on the same case. **It refuses any case not marked `synthetic`**, and that check is not a flag.
  - **Two claims in the repo were wrong and are corrected.** A 40-page ingest plus full recompute takes **~1.4s**, not "well under a second" — true before the last three sources widened the recompute, measured now rather than estimated. And the demo script's first draft told the presenter to point at "five direct contacts" on Harbhajan's node; **the drawer shows two `OWNS` edges to his own SIMs**, because the five is computed on the person-projected graph (D13). A number that is not on screen is a number a judge will check.
  - **25 → 35 tests, all passing.** Frontend untouched: no contract moved.

- **2026-09-05, night (Kanwar + Claude)** — **THE PIVOT. Read §0.5 before anything else in this file.** The product's face was replaced: one chat called `Suishōdama`, no offline mode, no CaseLens, no panels, no commands. The engine did not move. What the next agent needs to know:
  - **§0.5 carries all 27 of his instructions verbatim**, in order, with the reasons he gave. That section is the source of truth for this pivot; where anything below it disagrees, §0.5 wins.
  - **D22–D28 are new. D14, D16 and D17 are superseded**, and §3.5a is retired as the interface spec — kept only as the record of what was built and why it changed. **§10.1a/§10.1b no longer describe reality.** Jashan: nothing you built was wrong, the product moved under it.
  - **`backend/agent/offline.py` is deleted.** `/ask`, `/brief` and `/investigate` return **503** when the model cannot be reached. **The key and a network are now demo-day requirements**, not "before the 8th" items — there is no version of this that survives a dead room, and that is deliberate (D22).
  - **The conversation is a table on the case** (`store.say` / `store.conversation`, `GET`/`DELETE /api/cases/{id}/conversation`). `ask` used to send `messages=[{one prompt}]`: the officer read a thread and talked to something with no memory of it. The ids the last answer rested on are carried into the next turn **as ids** — D27.
  - **`claim_type` is new on the §5.3 contract** (`evidence` | `guidance`) and `verify()` enforces citations only on `evidence`. Advice and clarifying questions assert no case fact; failing them put a red panel on half a normal conversation.
  - **`/brief` is idempotent** and no longer greets on every case open. It also marked six findings delivered while showing eight, so "nothing new to say" could never come true; shown and delivered are the same number now (`BRIEF_FINDINGS`).
  - **The front end is 8 files, down from 30** — `pages/Chat.tsx`, `components/GraphPanel.tsx`, `lib/api.ts`, `types.ts`, `config.ts`, `App.tsx`, `main.tsx`, `index.css`. Everything else was deleted, on his instruction, rather than left dead.
  - **30 → 33 tests.** Build and lint clean. `docs/demo-script.md` updated: the offline variant is gone, and it now tells the presenter **never to type an entity id on stage** — saying "the Ludhiana account" and having it resolved is the demonstration (D26).


- **2026-09-06 (Kanwar + Claude)** — **the pivot's dead skin removed, the interface built on top of it, and the backend made to survive a real case file.** What the next agent needs to know:
  - **Every pre-pivot design description is deleted, not archived.** §3.5a (the Calm Civic Forensic spec, the 60/40 split, the six workspace sections) is gone; **§3.5 now describes the interface that exists**. §10.1a/§10.1b are replaced by one short ownership section. §6's tree, §5.6's note 2, §10.3's "offline-safe" row, §13's offline line, D22's row and `frontend/README.md` all said things that stopped being true on 09-05. A dead spec in a file four agents read is something one of them will eventually build to.
  - **New §2.5, in his words: this is not a chat with a context window.** Each case has a brain on disk that grows with every document, and the assistant queries it with tools. Three consequences are checkable, and the cheapest is that **clearing the thread changes no answer**. **D29** is the interface half: what the brain holds is on screen at all times as one line, it says what grew when it grows, and the graph is the brain rather than a picture of an answer.
  - **The interface gained four things and no new place to navigate to.** The evidence trail under an answer (cited entity → its documents → the exact line, `GET /source`); the brain line under the composer, which becomes *"fir_114_003.pdf — the brain grew by 7 entities and 29 links"* the moment a document lands; drag-and-drop anywhere on the screen; and three opening questions on an empty case, because with no panels the empty screen is the only place discoverability can live. The graph now also opens on an answer's cited *set*, lighting the links inside it and never a route (D23).
  - **There is no stop button, deliberately.** The run is server-side and the answer is recorded on the case whether the tab waits or not, so a control that only stopped the waiting would be telling him something untrue. Deleting a case now takes two clicks — it destroys a brain.
  - **§3.10 is the new backend section and it is all measurement.** Ingest was **quadratic three times over** (106 KB of prose: 63s → 3.8s, now linear); provenance grew one offset per mention and put a **23,000-character node** in the model's context (350 now); **no tool result had a ceiling** — `timeline` returned **419,224 characters** in one call — and the only limit was a string slice that cut mid-object into invalid JSON; and exact betweenness was **36.4s of a 38.7s recompute** that runs after every ingest. **D30–D32.**
  - **`chain_of_custody` is a new read tool — D33, §5.2.** The pivot removed the custody panel and with it the only surface for the theme the round is judged on. It is a question now, like everything else.
  - **The system prompt gained what the model could not know**: that the officer sees one chat and gets everything else by asking, that he will say "the Ludhiana account" and never an id, and that it is querying a brain rather than holding the case in a window.
  - **25 → 37 tests, all mutation-checked.** Three of the five new guards were asleep on the first attempt: two asserted against the constant they were testing, one had a bar that sat on both sides of the bug. Fixed and re-checked.
  - **The dead code went with the dead spec.** `frontend/` dropped **eight dependencies** — every Radix package, `clsx`, `tailwind-merge` — which existed for the dialogs, dropdowns, tabs and tooltips of the deleted workspace; the lockfile went from 2,087 lines to 980. Four API-client functions with no caller (`getHealth`, `getCase`, `getDocuments`, `getCustody`) and eleven types nothing referenced are gone. **Also purged from this file**: the block diagram's "SPLIT-SCREEN UI" box, §3.7's "empty workspace", §7's Radix line, §9.2's "open the source view", §9.3's "open the custody log", §10.3's "entity panel", and §5.6's note 2 — which still promised a briefing that arrives with an apology in `caveats` when the model is down, a thing D22 deleted a day earlier.
  - **Three defects the browser found and the tests did not**: `/nodes/{id}` counted a document once per offset (12 documents on a 9-document case); the evidence trail printed entity ids at an officer who must never see one (D26); and a case with an unreachable assistant said nothing until he had typed a question.

- **2026-09-06, later (Kanwar + Claude)** — **the brain panel became an instrument, and the interface stopped looking like a prototype.** No contract moved; `frontend/` only. What the next agent needs to know:
  - **The graph was a picture of having a graph, not a way of reading one.** It drew all 125 nodes as identical 9px grey dots with no labels, no type, no hover and **no click handler at all** — an officer could not tell a person from a bank account, and nothing happened when he pressed one. **D34: the graph opens on a readable core and opens further where he asks it to.** People and organisations first, then the phones, accounts and places that bridge two or more of them; every node fans out to its own neighbours on a click, born at their parent so the eye keeps hold of where they came from, and nothing already on screen moves.
  - **D35: a type is drawn, not written.** Shape carries it (ellipse/hexagon/pentagon/diamond/barrel/rectangle) and a desaturated tone second, so it survives a projector and a colour-blind judge. **Evidence Amber is untouched and still means exactly one thing** (D28) — it overrides type whenever a node is lit. Node size is degree, which is the case's own argument about who matters.
  - **D36: every node opens to what is inside it.** The entity panel — *inside* the brain panel, never a second surface (D25) — lists every document the entity appears in, and each row opens to **the exact passage with its character offsets**, the same trail `Evidence` draws under an answer. Its connections are listed too and each is clickable, which adds it to the graph and opens it. A structured row that links without quoting prose says so rather than showing an empty box.
  - **Four defects found by driving it, three of which no test could see.** `square` is **not a cytoscape node shape** — it was accepted into the stylesheet in silence and then failed in the renderer's shape lookup, blanking **the entire node layer**: 26 nodes present, `visible()`, correctly positioned and styled, and not one pixel drawn. `cy.resize()` **returns early when the box has not changed**, so the opening frame never landed and the graph appeared only if you happened to resize the window; it needs an explicit `forceRender()`. The seed of "busiest 26" was **16 phone numbers, 7 towers and one person** — raw degree ranks the switchboard above the people using it, the same reason the backend projects onto persons before ranking (D13). And the post-expand fit ran *before* the entity panel had taken its share of the canvas, so new nodes landed underneath it.
  - **A caution for whoever debugs this canvas next:** `getImageData` on cytoscape's stacked canvases reported **zero painted pixels on a graph that was drawing correctly**, and a hidden browser pane throttles `requestAnimationFrame` — which is cytoscape's whole draw loop — so the canvas is blank for reasons that have nothing to do with the code. **Two of the hours spent here went to diagnostics that were themselves wrong.** Screenshot the running app; do not trust pixel sampling.
  - **The look.** The palette did not change and must not: near-colourless, one ink, hairlines, amber alone carrying meaning. What was missing was never colour — it was layering, a type scale with a hierarchy in it, one easing curve (`--ease-out-soft`) used by everything that moves, and states that respond. Restraint had been reading as unfinished.
  - **37 tests still pass, build and lint clean.** `README` §7 was corrected while here: it promised an offline fallback with `caveats` that **D22 deleted the day before**, and said 35 tests.

- **2026-09-06, evening (Kanwar + Claude)** — **the brain got a door, and the graph got a hand.** `frontend/` only; no contract, no endpoint and no backend line moved. What the next agent needs to know:
  - **D37: the brain has its own control.** Top right of the conversation, beside the case's name, and Escape closes it. It was reachable only from the line under the composer or an answer's *show it on the brain* — both of which need something to have happened first, so an officer who just wanted to look had nowhere to press. Pressing it draws the panel in the same frame: the shell and *Opening…* appear while `GET /graph` is still in flight, because waiting for data before drawing anything read as a dead button.
  - **D38: click to open, click again to close.** Expansion used to be one-way — four levels in, the only way back was to rebuild the graph, so people stopped clicking. Each node now records *who brought it on screen*, and closing an entity folds away its children and theirs. Nothing the officer did not open is ever touched, so an answer's route cannot be collapsed out from under him. **Nodes are also draggable now, which reverses the old "a thing to read, not to rearrange"** — his call, and the better reason: a force layout puts two names on top of each other often enough.
  - **D39: cytoscape's grey discs are gone** — *"those circles whenever i slide or click"*. `active-bg-opacity`, the node/edge `:active` overlays and the selection box are all zeroed, and `autounselectify` turns off cytoscape's second selection so only `.picked` is ours. Feedback is a **border**, because a border follows the node's real shape and an overlay disc draws a circle around a hexagon.
  - **The layout is laid out into the shape of the panel.** `boundingBox` is the container's own width and height. Without it the force layout composes on a square, the fit scales that square to the width of a tall narrow panel, and the result is a small graph marooned between two empty bands — most of the reason the picture read as thin. With it, plus `nodeOverlap: 45` for the phones that all hang off the same three people, the graph fills the panel.
  - **D40, and it is the important one: the first frame is composed, not revealed.** A held-dark canvas faded in from the frame callback looked better and was a trap — it makes *visibility* depend on a frame arriving, and its failure mode is a graph that is correct in every respect and completely invisible. That is this panel's own bug from earlier the same day. It fits synchronously now; a late frame costs an unfitted moment instead of a blank one.
  - **A real defect the console found: the frame callback was calling a destroyed cytoscape.** React mounts twice in development, and the first instance's `requestAnimationFrame` arrived after that instance had been torn down — it checked `cyRef.current` (live, but the *second* core) and then used its own captured, dead one, throwing `isHeadless` of null and taking the opening fit with it. All three deferred callbacks now compare identity: `if (cyRef.current !== cy) return`.
  - **A hover that grows the node, a tooltip that says what it is and how many links it has, a key that filters by type, and a double-click on empty canvas to fit.** The key defaults to open — shape is the picture's whole vocabulary, and a vocabulary nobody is given is a picture nobody can read.
  - **Small things across the product:** one easing curve is now Tailwind's default so a bare `transition` cannot disagree with it, the panel slides in with a soft edge shadow, prose gets `text-wrap: pretty`, and the entity panel takes 38% rather than 46% so the graph keeps its room.
  - **D41: the web tool is gone.** His call, same session. It was a logged stub with a provider nobody had chosen, and deleting it is worth more than wiring one: **the only thing in this product that reaches the network is now the model call itself.** Ingest, the graph, every analytic, custody and memory all run on the officer's machine, and that is a sentence a judge from a police department will care about more than an OSINT lookup. `search_web` deleted from `tools.py`, `web_search` removed from `custody/chain.py`'s `ACTIONS`, and every mention in §5.2, §5.4, §10.3 and §11 with them. It was never bound into the model's tool list, so nothing the model could do has changed and no custody file anywhere contains one.
  - **Verified in a browser against `demo-114`**, not only typed: 23 → 28 nodes on a click and 28 → 23 on the next one, the tooltip reading *Manjit Singh · person · 19 links*, the key fading 64 elements and flagging 4, hover resolving 30px → 35px. **37 tests, `tsc`, `oxlint` and `build` all clean.** Note for whoever drives this next: the in-app preview pane throttles `requestAnimationFrame`, which is cytoscape's entire draw loop **and its style transitions** — a blank or frozen canvas there says nothing about the code. Call `forceRender()` before screenshotting, or look at it in a real browser.

- **2026-09-06, later still (Kanwar + Claude)** — **the bill was bounded before the first live call, and the product was renamed.** No contract moved. What the next agent needs to know:
  - **The budget changed shape.** The key is Kanwar's own with about **$3** on it, not Gurpartap's ~$8. At Sonnet 5's $2/$10 per MTok that is roughly two full demo run-throughs, so cost stopped being a footnote and became a constraint. §11 says so.
  - **D42: prompt caching, and it needed the system prompt split in two.** There was no caching anywhere, and the tool loop re-sent everything on every one of up to 14 iterations. `_system()` now returns two blocks — standing instructions with the breakpoint, the case's changing counts after it — because caching is a prefix match and one string would have discarded the entry on every ingest. Measured before writing it: the cached prefix is **~2,100 tokens** against Sonnet 5's **1,024** minimum, so it actually takes; below that it would have silently done nothing.
  - **A rejected breakpoint retries once without caching.** A 400 costs nothing, and an optimisation must never be why an officer gets no answer.
  - **Every answer now logs `in / cache_read / cache_write / out` and an estimated dollar figure.** That line is the check: `cache_read` at 0 on every question after the first means the prefix is being invalidated. **None of this is proven live** — the tests prove the request's shape, not that the cache is hit.
  - **`effort` stays `high` and thinking stays adaptive.** Caching is free; effort is a quality trade, and this is being shown to judges.
  - **D43: the product is `Suishōdama`** — capital S, macron, exactly as written on the SIH submission form. D24's lowercase rule is gone. **The rename was not finished when the source said the new name**: two `lowercase` Tailwind classes still rendered it `suishōdama` on screen, which a grep cannot see and a screenshot can. The stored conversation role is ASCII `suishodama` next to `officer`; no row anywhere carried the old role, so nothing needed migrating.
  - **37 tests, `tsc`, `oxlint` and `build` all clean**, and the new cache guard was mutation-checked twice — breakpoint removed (failed), blocks merged (failed), restored. `demo-114` was regenerated, which also cleared a stray rehearsal question out of its custody chain.

- **2026-09-06, evening (Kanwar + Claude)** — **the model call ran for the first time, the bill was brought under control, the product was renamed, and the prompt was decoupled from the demo.** What the next agent needs to know:
  - **The name is `Suishōdama`** — capital S, macron, exactly as on the SIH submission form. D43. Every occurrence of the old name is gone from code, interface, page title, tests and this file; the stored conversation role is ASCII `suishodama` beside `officer`. Two `lowercase` classes were still rendering it in small letters after the source had been renamed — **a grep cannot see that and a screenshot can.**
  - **The live API works.** Nine calls, **$0.21 of a ~$3 personal budget**. Verified: refuses to invent an absent document; separates proximity from contact unprompted; leads with the hidden-broker finding; synthesises bank + CDR + criminal history in one answer; and **clears-and-re-asks to the same answer with the same citations**, which is §2.5 demonstrated rather than claimed.
  - **D42 prompt caching, measured: 2 input tokens at full price per call, $0.0235 a question, down from ~$0.10.** Three system blocks now — universal, per-case (identity, counts, findings), per-question (memory). The first two are cached.
  - **D44: nothing speaks unprompted.** Opening a case used to fire a model call, and answering a question caused another one. Two typed questions had produced five billed calls.
  - **D45: the findings reach the model, and a finding outranks a ranking.** This is the one that cost the demo its centrepiece and got it back — read the decision row before touching `_system()`.
  - **D46: the universal prompt carries no case in it**, guarded by a test that rejects planted names, 10-digit identifiers and concrete node ids.
  - **D47: it volunteers** — and the first answer after that clause went in found a bridge nobody planted (§9.1).
  - **The interface**: his message now appears the instant he presses send (a 40–50s wait used to look like nothing had happened); the graph's "what it has worked out" panel is gone — he asks instead.
  - **`output/cost.jsonl`** (gitignored) records tokens and an estimated dollar figure for every call, because the console line scrolls away and lives in whatever window uvicorn was started in.
  - **38 tests**, every new guard mutation-checked. Two of them were asleep on the first attempt and had to be rewritten — one asserted on a section heading that survives when the data behind it is deleted.
  - **Still never run live: the custody/tamper beat (§9.3)**, which is the theme the round is judged on. *(Closed the same night — see the entry below.)*

- **2026-09-06, night (Kanwar + Claude)** — **a full readiness pass before submission work starts, and the last unperformed beat performed.** No code changed; everything below is verification, and two of the numbers in this file were wrong. What the next agent needs to know:
  - **The custody/tamper beat ran live and passed** — the last part of the demo that had never been performed, and the one the *Blockchain & Cybersecurity* theme is judged on. Chain broken at entry 2, asked in the chat, and the answer **named entry #2 and the reason**. It also refused to name the document it could not see, and it exercised a path nothing else had: **an answer citing zero graph nodes**. One ungrounded claim in it, recorded in §11 — it asserts the later entries verify, which `verify()` never checked.
  - **`pytest` → 38 passed, not 37.** The count was stale in three places — §7, §11 and `docs/demo-script.md`'s pre-flight block, which is the one a presenter reads twenty minutes before the round. The 38th arrived with D46 in the previous commit and the counts were never moved.
  - **The cost figures in this file are floors.** `_log_usage` runs once per question on the final message, so `output/cost.jsonl` records the **last request**, not the sum over the tool loop's iterations. Ledger reads **$0.2288 / 10 rows**; the true spend is higher and unknown here. **Read the console before the 8th.**
  - **Re-verified, nothing moved:** `tsc`/`oxlint`/`build` clean; the API serves `demo-114` at 125 nodes / 1,148 edges / 9 documents; the interface driven in a browser — thread, graph fan-out (28 of 116 on a click), entity profile at *24 links · in 7 of 9 documents*, and a citation opening to the exact passage. Custody restored byte-identical after the test (`head efc7a1c0…`, 61 entries).
  - **Confirmed by grep, because it is the promise the product rests on: nothing runs on its own.** The chain has one write path and six call sites, all downstream of an officer uploading or asking; `verify()` never writes. No background task, thread, scheduler or startup hook in the backend; no `refetchInterval` anywhere in the front end. The four automatic queries — cases, conversation, graph, health — cost nothing, and `ask` is a mutation.
  - **Known and deliberately not fixed** (Kanwar's call): three empty rehearsal cases sit in the sidebar, and §8 still names the wrong key holder — it is Kanwar's key, not Gurpartap's, as §11 and the 09-06 entry above both say.

Append one line per session. What you built · what you changed in this file · what the next agent needs to know.

---

## 13. Open questions

Answer these in-place when you learn the answer, and say who answered it.

- **Who are the six team members?** Two on GitHub, Gurpartap named as a third. SIH requires six, at least one woman.
- **Does the internal round score prototype, presentation, or both?** The PEC circular does not say. Changes how hours 20–24 are spent.
- **Is there a submission artefact besides the demo** — idea PPT, doc, video? The national round wants an idea presentation; the internal round's requirement is unconfirmed.
- **Do we present live or pre-record?** Online mode; unconfirmed. **The offline half of this was answered and then reversed on 2026-09-05:** there is no offline mode any more (D22), by his instruction and against advice given at the time. `/ask` needs the key and the network. **If the round is presented live, that is now a single point of failure with no mitigation** — the mitigation available is to pre-record, and that is a decision nobody has taken.
- **Are scanned documents in scope?** Real FIRs are often photographs of paper, which have no text layer at all. As of 2026-09-05 the system detects them and says so (D18) but cannot read them; reading them means OCR, which is a dependency nobody has agreed to and which would put a lossy step in front of the graph. **Kanwar's call, not an agent's.**
