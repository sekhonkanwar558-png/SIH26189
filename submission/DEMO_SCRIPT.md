# Demo spine — one structure, two cuts

The README run sheet is **8 minutes** by its own section timings. Two things have
to come out of it and they must not disagree with each other:

* the **video** — deliverable 4, *strictly* 1–4 minutes, due Wed 9 Sep 12:30
* the **offline slot** — Tue 15 Sep, **6 minutes for presentation *and* prototype together**

So there is one spine below, in priority order, and both cuts drop from the tail.
**§4 is never cut.** It is the only beat that proves the system analyses rather
than recites, and it is the one nobody designed.

| § | Beat | Offline (6:00) | Video (3:30) | Cuttable? |
|---|---|---|---|---|
| 1 | The officer's pile | 0:30 | 0:25 | compress, never drop |
| 2 | Hand it a document | 0:45 | 0:35 | compress |
| 3 | Query one — the graph causes the answer | 1:30 | 0:55 | compress |
| 4 | Query two — the man nobody would have written down | 2:00 | 1:00 | **never** |
| 5 | Custody, broken live | 1:00 | 0:25 | compress |
| 6 | Close | 0:15 | 0:10 | — |
| — | *(§6 of the run sheet — "not a trafficking tool")* | **cut** | **cut** | first to go |

**Dropped from the run sheet in both cuts:** the new-case / fraud-complaint beat.
It closes a real objection, but it is 45 seconds spent proving a negative and the
run sheet already nominates it as the first thing to cut.

---

## Before recording — the same twenty minutes as the live demo

```bash
python -m data.synthetic.generate --case demo-114   # rebuild the case, clean
python -m pytest tests -q                           # 38 passed
uvicorn backend.api.main:app --port 8000            # terminal 1
pnpm --dir frontend dev                             # terminal 2
```

* Line under the composer must read **116 entities · 1,148 links · 9 documents**.
* **Ask it anything first and get an answer back.** No key or no network and there
  is no demo — there is no offline mode.
* `tests/fixtures/fir-114-text.pdf` on the desktop as **`fir_114_003.pdf`**.
* A **third terminal**, already in the repo root, for the tamper command.
* **Window ≥1024px** or the graph panel never appears and the split — the whole
  argument — is gone.
* Every other tab closed. Record at 1080p or better.

---

## The video — shot by shot, 3:30

Narration is written to be read at a normal pace. Where it says **[silence]**,
say nothing and let the screen do the work; those pauses are load-bearing.

### 0:00 – 0:25 · The pile

**On screen:** the case open, chat empty, the line under the composer visible.

> An investigating officer in a trafficking case is holding an FIR, two CDR
> exports, a bank statement and a surveillance log. Every connection he needs is
> already in that pile. He will not find them, because finding them means holding
> four hundred phone numbers in his head at once. NCRB's own problem statement
> says it — the data exists, and the links are missed.
>
> Everyone will show you a dashboard of that pile. A dashboard cannot be asked
> anything. We give every case its own investigator.

### 0:25 – 1:00 · Hand it a document

**On screen:** drag `fir_114_003.pdf` onto the window. Hold on the brain line as
it changes.

> That line is this case's brain — not a chat history, a graph on disk that this
> case owns.

**[silence — let the line change on camera]**

> That is the officer's whole job. Hand it a document. Everything after that
> happened without anyone asking, and it is permanent. Document forty is not
> competing for room with document one the way it would in a chat window — it is
> making document one worth more, because a link needs both ends.

### 1:00 – 1:55 · The graph causes the answer

**On screen:** type **How is Ravi connected to the Ludhiana account?** Let the
path light up hop by hop. Then click *Rests on 5 entities and 12 links*, open one,
click through to the source line.

**[silence while the answer lands]**

> It cannot say anything the graph does not contain. Every identifier in that
> answer is checked against the graph before you see it, and anything that does
> not exist is stripped and reported.

**On screen:** the source document opens at the exact character offsets.

> That is the document, at the line it came from. That trail is why this is not a
> chatbot with a picture next to it.

### 1:55 – 2:55 · The man nobody would have written down

**Slow down. This is the beat.**

**On screen:** type **Who matters most in this case?** The answer names
**Harbhajan Dhillon**. Expand the evidence trail — *out of 1 document*.

> No officer reading the reports in this case would ever have written his name
> down. He is not in them. He is a row of metadata in a phone log, he owns two
> SIMs, and twenty-two per cent of every shortest path in this network runs
> through him — because he is the only thing joining two groups that otherwise
> never touch.

**[silence — two full seconds, on his evidence trail]**

### 2:55 – 3:20 · Break the evidence

**On screen:** ask **Has anything in this case been tampered with?** → intact.
Cut to the third terminal, run the tamper command, ask again.

```bash
python -m data.synthetic.tamper --case demo-114
```

> Blockchain and Cybersecurity is the theme. Evidence does not need a token — it
> needs to be tamper-evident. Every document that arrives and every conclusion
> the system draws is hash-chained to the one before it.

**On screen:** it names **entry 2**, with the reason. Restore.

```bash
python -m data.synthetic.tamper --case demo-114 --restore
```

> Not "a problem somewhere" — that entry, and why.

### 3:20 – 3:30 · Close

> One officer, one case, one assistant that has read everything, and can be asked
> the same question in six months and give the same cited answer. Not a dashboard
> of a pile of documents. An investigator you can hand the pile to.

---

## The offline slot — what the extra 2:30 buys

Same six beats, same order. The extra time goes in three places and nowhere else:

1. **§2, +10s** — read *seven of seven* out loud after asking *what is in this case?*
2. **§3, +35s** — read the path aloud **from the graph, not the text**, and ask it
   the way a person speaks. **Never type an id on stage**; if you do, you have
   shown them a database with a text box on it.
3. **§4, +60s** — ask *"which documents name him?"* and let the answer sit. Then
   handle the question that always comes: a man with two links scoring that high
   is the **person-projected graph** — a man and his SIM are not two actors, and
   on the raw graph every path would stop dead at the handset.

**If you are running over, cut §5 to the claim without the live break.** Cut §4
last, and never.

**The failure table in the README applies unchanged.** Never debug in front of the
room; every failure has a next sentence.
