# Demo script — SIH26189, Suishōdama

**The run sheet for the 8th.** Written 2026-09-05, rewritten 2026-09-06 for the pivot
(README §0.5). Read this with README §9 open; it is the *how*, and §9 is the *why*.
If the two disagree, §9 wins and this file is stale — fix it here.

**Nine minutes of content. Rehearse it three times on the machine that will run
it** (README §10.3, hours 22–24). A demo that has been run three times beats a
better system that has been run once.

---

## 0. Before you speak

Do this in the twenty minutes before the round, in this order, and **do not skip
the second one**.

```bash
python -m data.synthetic.generate --case demo-114   # rebuild the case, clean
python -m pytest tests -q                           # 38 passed
uvicorn backend.api.main:app --port 8000            # terminal 1
pnpm --dir frontend dev                             # terminal 2
```

1. Open `http://127.0.0.1:5173` and click **Suspected trafficking network —
   Ludhiana to Delhi**. The line under the composer must read **116 entities ·
   1,148 links · 9 documents** — 116 entities plus the 9 documents is the
   125 nodes README §11 quotes.
2. **Check the assistant is alive.** Ask it anything — "what is this case
   about?" — and make sure an answer comes back. **There is no offline mode**
   (D22): with no API key or no network, `Suishōdama` says it is unavailable and
   nothing else in the demo works. The key and the connection are requirements,
   not to-do items. Check them before the room fills, not at minute four.
3. Have `tests/fixtures/fir-114-text.pdf` on the desktop, renamed to something an
   officer would recognise — `fir_114_003.pdf`. You will upload it live (§2).
4. Have `docs/demo-fraud-complaint.txt` to hand for §6.
5. **Open a third terminal** in the repo root, for the §5 tamper command. Do not
   make the room watch you find a terminal.
6. **Close every other tab.** The chat and the graph are the demo.

**Screen width matters.** The graph panel needs **1024px or wider**; below that
the conversation is the whole screen and the split — which is the entire
argument in §3 — is gone. Check the projector before you start and use your own
screen if you have to.

---

## 1. The problem, in their words (45 seconds)

Do not open with the architecture. Open with the officer.

> "An investigating officer in a trafficking case is holding an FIR, two CDR
> exports, a bank statement and a surveillance log. Every connection he needs is
> already in that pile. He will not find them, because finding them means holding
> four hundred phone numbers in his head at once. NCRB's own statement says it:
> the data exists and the links are missed."

Then the one sentence that separates this from the other submissions:

> "Everyone will show you a dashboard of that pile. A dashboard cannot be asked
> anything. We give every case its own investigator — its own graph, its own
> memory, and an assistant that has already read all of it."

**Do not say "knowledge graph" yet.** Say it after they have seen one.

---

## 2. The officer's one job (60 seconds)

**Point at the line under the composer first.** *116 entities, 1,148 links, 9
documents.* Say what it is:

> "That is this case's brain. Not a chat history — a graph on disk that this
> case owns. Watch what happens when he hands it one more document."

Now upload `fir_114_003.pdf` live, in front of them — drag it onto the window,
or use the paperclip. Then **stop and let them read the line**:

> **fir_114_003.pdf — the brain grew by N entities and M links.**

> "That is the officer's whole job. Hand it a document. Everything after this
> happened without anyone asking for it — and it is *permanent*. Document forty
> is not competing for room with document one, the way it would be in a chat
> window. It is making document one worth more, because a link needs both ends."

Then ask it, in the composer:

> **What is in this case?**

It names the nine documents and the seven kinds — FIR, CDR, financial,
surveillance, social, criminal history, intelligence. **Every source the problem
statement names.** Say that number out loud: seven of seven.

**If the upload fails, do not debug it.** Say "that ran this morning, here is the
document it produced" and move to the next section. You lose fifteen seconds. You
lose the room if you start reading a stack trace.

---

## 3. Demo query 1 — the graph causes the answer (2 minutes)

**This is the one that proves it is not a chatbot with a picture next to it.**

Ask:

> **How is Ravi connected to the Ludhiana account?**

While the answer lands, say nothing. Let them watch the path light up hop by hop
on the right. Then:

1. **Read the path aloud from the graph, not from the text.** Ravi Kumar →
   Manjit Singh → the two accounts → 50100244178.
2. Click **Rests on 5 entities and 12 links** under the answer. Open one of
   them, then **Open the line it came from**. **The source document opens on the
   exact line the claim came from.**
3. Say the thing that matters most in the whole demo:

   > "It cannot say anything the graph does not contain. Every id in that answer
   > is checked against the graph before you see it, and anything that does not
   > exist is stripped and reported. That is why this is not a chatbot."

**Ask it the way a person speaks — that is the point.** "The Ludhiana account"
is not what the graph holds; the graph holds `account:50100244178`, and resolving
one to the other is the assistant's job (D26). **Never type an id on stage.** If
you do, you have shown them a database with a text box on it.

---

## 4. Demo query 2 — the moment (2 minutes)

**Everything before this was setup.** Slow down.

> **Who matters most in this case?**

The answer names **Harbhajan Dhillon**.

Then, and this is the whole pitch:

1. Open the evidence trail and expand **Harbhajan Dhillon**. It reads **read out
   of 1 document** — a call log. **No FIR, no surveillance report, no
   statement.**
2. Ask it plainly: **"Which documents name him?"** One. Let that sit.
3. Say it:

   > "No officer reading the reports in this case would ever have written his
   > name down. He is not in them. He is a row of metadata in a phone log, he
   > owns two SIMs, and twenty-two per cent of every shortest path in this
   > network runs through him — because he is the only thing joining two groups
   > that otherwise never touch."

**Then stop talking for two seconds.** That is the moment the room understands
what the system does.

**Know this trap, because a judge may ask for the ranking:** he is **third** by
raw betweenness (0.222), behind Sukhwinder Kaur (0.380) and Manjit Singh (0.278)
— both named in four and seven documents respectively. Ranking alone would have
named Sukhwinder, and naming her proves nothing, because an officer already knows
who she is. What the system leads with is the *finding* — high betweenness **and**
absent from every report. If a judge asks "why him and not the top of your list",
that is the answer, and it is better than the one they expected.

**And if a judge asks how a man with two links can be that central** — that is
D13, and it is worth knowing cold. Centrality is scored on a person-projected
graph: a man and his SIM are not two actors. His two SIMs carry the calls; on the
raw graph every path would stop dead at the handset and he would score near zero.
That single design choice is the difference between finding him and not.

---

## 5. The theme — chain of custody (60 seconds)

They will ask where the blockchain is. Answer it before they do.

Ask:

> **Has anything in this case been tampered with?**

It answers from the chain: intact, and how many entries it covers.

> "Blockchain and Cybersecurity is the theme. Evidence does not need a token, it
> needs to be tamper-evident. Every document that arrives and every conclusion
> the system draws is hash-chained to the one before it."

Then break it, live. Have this ready in a third terminal:

```bash
python -m data.synthetic.tamper --case demo-114
```

Ask the same question again. **It names entry 2** — not "a problem somewhere",
the exact entry, with the reason. Then put it back:

```bash
python -m data.synthetic.tamper --case demo-114 --restore
```

Ask once more: **intact**. Restore is byte-identical, so the demo carries on with
this case straight afterwards — there is a test that fails if it ever stops
being.

Ten seconds of doing beats a minute of claiming. (The tool refuses to run on any
case not marked synthetic, which is worth saying out loud if a judge looks
alarmed that a "break the evidence" command exists at all.)

---

## 6. It is not a trafficking tool (45 seconds)

The shortest section and it closes a real objection.

Click **+ New case**, drop `docs/demo-fraud-complaint.txt` onto the window, and
ask **"what is this?"**. The brain line goes from nothing to **eleven entities**, which is exactly what
the upload said it read:
three people, the shell firm, the account, the vehicle, three phone numbers.
Nothing from the trafficking case is in it, and nothing from it reaches the
trafficking case.

> "Nothing in the engine knows what trafficking is. It knows identifiers, links,
> timing and structure. The case carries its own type and the officer's own brief,
> and that is what the assistant reasons in the register of. A fraud case, a
> homicide, a missing person — same engine, different brain."

**If you are short on time, cut this section, not §4.** It answers an objection
rather than making the argument.

---

## 7. Close (30 seconds)

> "One officer, one case, one assistant that has read everything and can be asked
> the same question again in six months and give the same cited answer. Not a
> dashboard of a pile of documents. An investigator you can hand the pile to."

---

## The interface, and why there is so little of it

**One chat. That is the whole product** (D25). If a judge asks where the rest of
it is, that question is the pitch:

> "An investigating officer is not going to learn six screens. He hands it a
> document and he asks it things, the way he would ask a colleague who had
> already read the file. Everything you would expect to be a tab — the documents,
> the findings, the chain of custody, an entity's history — he gets by asking for
> it, which is one skill instead of six."

**There are no commands and nothing to type but English** (D26). Do not type an
entity id on stage, ever. Say "the Ludhiana account" — resolving that is the
assistant's job, and doing it in front of them is the demonstration.

**The line under the composer is the argument in one sentence.** It is the only
number in the product, it is there because it *changes*, and §2 is built around
watching it change.

**If the assistant cannot be reached, it says so and nothing else pretends.**
There is no degraded mode (D22): the graph, the documents and the custody chain
are all still there and still true, and Suishōdama tells him plainly that it is
unavailable rather than answering anyway. **So the round needs the key and a
network.** Check both before you start — §0.

## If something breaks

**The rule: never debug in front of the room.** Every failure below has a next
sentence; say it and keep moving.

| Breaks | Say | Then |
|---|---|---|
| Upload fails | "That ran this morning — here is what it produced." | Go to §3. |
| An answer is slow | Nothing. Talk over it: the officer's problem, the nine documents. | Wait. |
| An answer is wrong or thin | "It only says what the graph contains — let me show you the graph." | Ask query 1, which lights the route. |
| The graph panel does not open | The answer had no route to show. | Ask query 1; its answer always has one. |
| Suishōdama says it is unavailable | "The assistant is a model call; the case is on disk and untouched." | Check the key and the network. **Nothing else in the demo works until it is back** (D22). |
| The API is down | "Two-terminal setup — one moment." | Restart uvicorn. Case data is on disk and survives. |
| A judge asks for OCR on a scan | "It detects a scan and tells the officer it could not read it, rather than accepting it silently. Reading it means OCR, which puts a lossy step in front of the evidence — that is a decision, not an oversight." | §13. |
| A judge asks about real data | "Synthetic, deliberately: no public FIR/CDR corpus exists and real crime data is a legal problem. Because we planted the structure, we can prove the system found it." | §9.1. |

---

## Questions to expect, and the honest answer

- **"Is the AI making this up?"** — No, and it is structurally prevented from
  doing so. Findings are computed from the graph before the model sees them.
  Every citation is checked against the graph before display and stripped if it
  does not exist. Open the evidence trail and click through to the line in the
  document: that trail is the answer to this question.
- **"So it is ChatGPT with our documents pasted in?"** — No, and this is the
  distinction worth being precise about. Nothing is pasted in. The case has a
  graph on disk and the assistant queries it with tools, one call at a time, so
  the amount of text the model ever sees is fixed — it does not grow as the case
  grows. **Clear the conversation and ask again: same answer, same citations.**
  The knowledge is in the case, not in the thread.
- **"How is this different from a link-analysis tool?"** — A tool visualises what
  you already suspect. This one volunteers what you did not ask about — §4 is a
  man no officer would have written down.
- **"What if the data is wrong?"** — Every node carries its source and its
  confidence, and the confidence differs by source: an intelligence tip from an
  ungraded source does not enter at the confidence a bank record does. A tower
  co-location is reported as proximity and never as contact.
- **"How long to ingest a real case file?"** — About **1.4 seconds** for forty
  pages including every analytic, and it is **linear in document size** — a
  50,000-row CDR is about a minute and a half. No model in the ingest path (D4)
  is the reason, and a test fails if one appears or if the scaling stops being
  linear.
- **"Does it scale?"** — One SQLite file per case, and a case is the unit. It
  scales the way case files do: sideways.
