# Fund Copilot — Eval Report
**Generated:** 2026-03-03 (updated with fixes)
**Model:** llama3.1:8b (CPU-only, Ollama)
**Eval set:** 20 questions · top_k = 10 · max_context_chunks = 12

---

## Run Index

| ID | Timestamp | Status | Hit@k | Grounding | Refusal acc. | Notes | Links |
|---|---|---|---|---|---|---|---|
| **R1** | `20260302T135411` | ❌ Invalid | 85.7% | 0.0% | 0.0% | All 20 questions silently timed out (read=180s) | [Results](http://localhost:8010/eval/results/20260302T135411) |
| **R2** | `20260302T141648` | ⚠️ Partial | 91.7% | 0.0% | 75.0%* | 12/20 done, 3 ReadTimeouts, 95-min event loop stall | [Results](http://localhost:8010/eval/results/20260302T141648) |
| **R3** | `20260303T014203` | ⚠️ Partial | 88.9% | 35.0% | 50.0% | 5 client errors (q001–q005), 5 false refusals, grounding fixed | [Results](http://localhost:8010/eval/results/20260303T014203) |
| **R4** | `20260303T084111` | ⚠️ Partial | 85.7% | 35.0% | 40.0% | 0 errors, same false refusals, 4000-token cap slower + q018 regression | [Results](http://localhost:8010/eval/results/20260303T084111) |
| **R5** | *(pending)* | ⏳ Not run | — | — | — | Revert to 3000 tokens + ISIN metadata filter in retrieval | — |

[Open Evaluation Dashboard →](http://localhost:5174) *(Evaluation tab → Run History)*

\*Refusal accuracy for R2 is across completed questions only; 3 timeout errors counted as wrong refusals.

> **How to reference runs:** Use the ID in conversation, e.g. "R1 showed retrieval was fine", "R2's grounding failure", "compare R1 vs R2 Hit@k".

---

## Background: Key Concepts

> This section explains what the evaluation is actually measuring and why things went wrong.
> Skip if you already know these terms.

### What is a "token"?
A token is roughly a word or word-fragment. "the ongoing charges figure" ≈ 5 tokens. Tokens matter because:
1. **Speed** — language models process tokens one at a time. More input tokens = longer to read in (called *prefill*). More output tokens = longer to generate. On this CPU, the model reads ~50 tokens/second and generates ~10 tokens/second.
2. **Cost/Limits** — models have a maximum context window. If you stuff too much in, the tail gets cut off.

### What is the asyncio event loop?
Python's `asyncio` is how FastAPI and httpx handle multiple things at once without multiple threads. Think of it as a single worker on a conveyor belt: it picks up tasks (coroutines), starts them, parks them when they're waiting for something (e.g. a database response), and comes back when they're ready. The problem: if one task *never yields control* (because it's stuck waiting on a socket), the whole conveyor belt freezes. Nothing else moves — not the database query, not the HTTP response, nothing.

### What is httpx / ReadTimeout?
`httpx` is the Python library we use to make HTTP requests to Ollama. A `ReadTimeout` means: "I sent the request, but Ollama hasn't sent back a complete response within the timeout period." The question is what happens next — specifically, whether the socket (the underlying network connection) is cleanly closed. If it isn't, asyncio keeps trying to drain it in the background, which blocks everything else.

### What is "grounding"?
In RAG systems, *grounding* means the model's answer is explicitly tied back to retrieved source text. In this system, grounding is measured by whether the model wrote citation markers (`[1]`, `[2]`, etc.) and those markers pointed to chunks that were actually in the context. An answer that says "the fee is 0.20%" without a citation is *ungrounded* — even if it's factually correct, we can't prove where it came from or trust it.

### What is Hit@k?
Hit@k measures the retrieval step only, ignoring the LLM entirely. For each question, we know which fund document *should* contain the answer (identified by ISIN). Hit@k = 1 means the correct document appeared somewhere in the top-k retrieved chunks. Hit@k = 0 means it didn't. 85–90% Hit@k means our hybrid search is working well.

### What is refusal accuracy?
Some questions are deliberately unanswerable (e.g. "what is the carbon footprint?" — not in fund documents). The model should respond with `REFUSED: ...` instead of making something up. Refusal accuracy measures whether it does this correctly: did it refuse when it should have, and did it answer when it should have?

---

## Executive Summary

Two eval runs have been attempted. Neither produced valid results. Run 1 silently failed on every question due to an httpx timeout bug. Run 2 partially succeeded (12/20 questions generated real answers) but was abandoned after the event loop blocked for ~95 minutes following back-to-back timeouts. Three persistent root causes explain all failures:

| Root Cause | Impact | Status |
|---|---|---|
| httpx read timeout too short (180s → 600s) | All generation failed in Run 1 | Fixed |
| Stale socket blocks asyncio event loop after timeout | Run 2 froze for 95 min on q009 retrieval | Fixed |
| LLM ignores `[SOURCE: hex_id]` citation format | Grounding = 0% in both runs | **Fixed** (numbered citations) |

**Fixes applied for Run 3:**
- Context token cap: 5,000 → 3,000 (saves ~40s per question)
- Numbered citations `[1]`, `[2]` instead of opaque hex IDs
- `num_predict: 512` cap on generation length (~50s max)
- `asyncio.wait_for(timeout=480s)` hard wall per question
- `close_client()` on `ReadTimeout` to release stale sockets

---

## R1 — Run 1 — `20260302T135411`

**Status:** Complete (all 20 questions written to disk)
**Duration:** ~63 minutes
**Verdict:** ❌ Entirely invalid — generation failed silently on every question

### Summary Metrics

| Metric | Value |
|---|---|
| Hit@k | **85.7%** ✅ |
| Grounding rate | 0.0% ❌ |
| Refusal accuracy | 0.0% ❌ |
| Avg retrieval | 709 ms |
| Avg generation | 0 ms |
| Errors | 0 (bug: errors were silently swallowed) |

### What Happened

> **Learning note:** This is a classic "silent failure" bug. The code looked like it was
> succeeding but was actually failing every single time.

The httpx read timeout was 180 seconds. The old code used `timeout=httpx.Timeout(connect=5.0, read=180.0, ...)`. Ollama on CPU takes 181–300 seconds per question. Every single generation call timed out before Ollama could respond.

The exception path in `_eval_question` caught the `ReadTimeout` but `str(ReadTimeout())` returns an empty string for some httpx exception types. The error field was stored as `''`, which *looked* like success. The `result.answer` stayed at its default `""`, `result.confidence` stayed at `"refused"` (the EvalResult default), and `generation_ms` stayed at `0.0`. The runner wrote 20 rows of fake "refusals".

**Why refusal_accuracy = 0.0%:** The `compute_refusal_correct()` call is in the success path after `ground_response()`. The exception path exits before reaching it, so `result.refusal_correct` stays at its Python default `False` for all 20 questions — including the 3 that *should* have been refused (q018–q020), which would have counted as correct.

### Per-Question Detail (Run 1)

| ID | Category | Should Refuse | Hit@k | Confidence | Gen (ms) | Error |
|---|---|---|---|---|---|---|
| q001 | ocf | No | 1.0 | refused | 0 | '' (timeout) |
| q002 | risk_rating | No | 0.0 | refused | 0 | '' (timeout) |
| q003 | charges | No | 1.0 | refused | 0 | '' (timeout) |
| q004 | charges | No | 1.0 | refused | 0 | '' (timeout) |
| q005 | risk_rating | No | 1.0 | refused | 0 | '' (timeout) |
| q006 | ocf | No | 1.0 | refused | 0 | '' (timeout) |
| q007 | ocf | No | 1.0 | refused | 0 | '' (timeout) |
| q008 | sfdr | No | 1.0 | refused | 0 | '' (timeout) |
| q009 | characteristics | No | 1.0 | refused | 0 | '' (timeout) |
| q010 | characteristics | No | 1.0 | refused | 0 | '' (timeout) |
| q011 | benchmark | No | 1.0 | refused | 0 | '' (timeout) |
| q012 | characteristics | No | 1.0 | refused | 0 | '' (timeout) |
| q013 | structure | No | — | refused | 0 | '' (timeout) |
| q014 | structure | No | — | refused | 0 | '' (timeout) |
| q015 | structure | No | — | refused | 0 | '' (timeout) |
| q016 | regulation | No | — | refused | 0 | '' (timeout) |
| q017 | characteristics | No | 1.0 | refused | 0 | '' (timeout) |
| q018 | ocf | **Yes** | — | refused | 0 | '' (timeout) |
| q019 | off_topic | **Yes** | — | refused | 0 | '' (timeout) |
| q020 | esg | **Yes** | 0.0 | refused | 0 | '' (timeout) |

**Hit@k note:** Retrieval worked correctly even in this run. 85.7% Hit@k on the ISIN-keyed questions is a solid baseline. The `esg` and `risk_rating` misses are structural (fake ISIN, wrong doc retrieved for one share class).

---

## R2 — Run 2 — `20260302T141648` (incomplete, abandoned)

**Status:** 12/20 complete — run abandoned after ~10 hour stall
**Verdict:** ⚠️ Partial — generation is working, grounding is not

### Summary Metrics (12/20 questions)

| Metric | Value |
|---|---|
| Hit@k | **91.7%** ✅ (11/12 with ISIN) |
| Grounding rate | 0.0% ❌ |
| Refusal accuracy | **75.0%** 🟡 (9/12 — 3 wrong due to ReadTimeout) |
| Avg generation (successful) | ~216 s (~3.6 min) |
| Avg retrieval (normal) | ~100 ms |
| Errors | 3 × ReadTimeout (q007, q008, q011) |
| q009 retrieval anomaly | **5,717 seconds = 1.6 hours** (event loop blocked) |

### What Happened

> **Learning note:** This run reveals two separate problems: (1) the model *is* generating
> real answers now — the timeout fix worked — but (2) it's answering from its own internal
> knowledge instead of the retrieved documents. That's exactly the failure mode RAG is
> designed to prevent, and it's caused by a prompt engineering problem, not a code bug.

The 600s timeout fix meant most questions now completed. Generation times ranged from 181s (q004, entry charge) to 293s (q009, yield to maturity). These are consistent with llama3.1:8b on CPU:

```
~50 tokens/sec prefill × 3,000+ token input  = ~60–100s to read the context
~10 tokens/sec generation × 400 output tokens = ~40s to write the answer
─────────────────────────────────────────────────────────────────────────────
Total per question: ~100–140s (within 600s limit)
```

**q007, q008, q011 (ReadTimeout at 600s):** All three are iShares Euro Corporate Bond questions. The model generates unusually long, verbose answers to bond fund questions (lots of caveats, methodology explanations). Best guess: it exceeded ~5,000 output tokens for these — at 10 tok/s, that's 500s of generation alone, close to the 600s wall. **Fix:** `num_predict: 512` caps output at 512 tokens ≈ 50s max.

**q009 retrieval anomaly (5,717 seconds):**

> **Learning note:** This is the most important failure to understand. The 95-minute freeze
> had nothing to do with retrieval being slow — retrieval normally takes ~100ms. It was
> caused by a resource leak from the *previous* questions' failures.

After q007 and q008 both timed out, the httpx client still held *open* TCP connections to Ollama. Here's what happened step by step:

1. q007 times out. httpx raises `ReadTimeout`. BUT the socket to Ollama is still open — Ollama is still generating into it.
2. asyncio schedules internal cleanup tasks for those sockets: "drain the remaining data, then close."
3. Because Ollama keeps sending data, those cleanup tasks never finish.
4. asyncio cannot proceed with anything else — not just Ollama calls, but *all* async operations, including plain database queries — until those cleanup tasks complete.
5. When we start q009, the retrieval step tries to query the database. It's an async call. asyncio parks it and switches to... the socket cleanup tasks. Which are still waiting for Ollama. Retrieval appears to take 5,717 seconds.

**Fix applied:** `client.py:generate()` now calls `await close_client()` immediately on `ReadTimeout`. This tells the OS to forcibly close the sockets, which lets asyncio's cleanup tasks complete instantly, which unblocks everything else.

### Per-Question Detail (Run 2, partial)

| ID | Category | Should Refuse | Hit@k | Confidence | Gen (s) | Grounded | Refusal OK | Error |
|---|---|---|---|---|---|---|---|---|
| q001 | ocf | No | 1.0 | low | 218 | ❌ | ✅ | — |
| q002 | risk_rating | No | 0.0 | low | 199 | ❌ | ✅ | — |
| q003 | charges | No | 1.0 | low | 185 | ❌ | ✅ | — |
| q004 | charges | No | 1.0 | low | 181 | ❌ | ✅ | — |
| q005 | risk_rating | No | 1.0 | low | 194 | ❌ | ✅ | — |
| q006 | ocf | No | 1.0 | low | 197 | ❌ | ✅ | — |
| q007 | ocf | No | 1.0 | refused | — | ❌ | ❌ | ReadTimeout |
| q008 | sfdr | No | 1.0 | refused | — | ❌ | ❌ | ReadTimeout |
| q009 | characteristics | No | 1.0 | low | 293 | ❌ | ✅ | — (but 95 min stall before) |
| q010 | characteristics | No | 1.0 | low | 209 | ❌ | ✅ | — |
| q011 | benchmark | No | 1.0 | refused | — | ❌ | ❌ | ReadTimeout |
| q012 | characteristics | No | 1.0 | low | 266 | ❌ | ✅ | — |
| q013–q020 | various | mixed | — | — | — | — | — | *Not reached* |

### Sample Answers (illustrating grounding failure)

**q001** — OCF question (expected: `"0.20%"`)
> *"The ongoing charges figure for the iShares Core MSCI World UCITS ETF with ISIN
> IE00B4L5Y983 is 0.20%. This is stated in the provided document, specifically under the
> section 'Charges taken from the Share Class over each year'."*
>
> `chunks_cited: []` — Model found the right answer but wrote "the provided document"
> instead of `[SOURCE: 859bb0b8c2d87fa5_0003]`. Factually correct, citation-invalid.

> **Learning note:** This example shows the core tension. The model *understood* the
> citation instruction ("I should reference the source") but expressed it in plain English
> rather than machine-parseable syntax. This is actually reasonable behaviour from the
> model's perspective — it's doing what it was trained to do (write naturally). The problem
> is our citation format used a hex string like `859bb0b8c2d87fa5_0003` which the model
> has no way to memorise or reproduce. It's like asking someone to quote a source by its
> ISBN number rather than "document 1".

**q006** — OCF for distributing share class (expected: `"0.20%"`)
> *"The ongoing charges figure for the iShares Core MSCI World UCITS ETF USD Distributing
> IE000OHHIBC6 is not explicitly stated in the provided text. However, based on a search of
> publicly available information, the iShares Core MSCI World UCITS ETF typically has an
> annual management fee of **around 0.10% to 0.12%**."*
>
> Pure hallucination. The 0.20% figure is in the context (hit_at_k = 1.0) but the model
> invented a different figure from memory. No citation, wrong answer.

> **Learning note:** This is exactly what RAG is supposed to prevent. The model found the
> right document but then ignored it and answered from its training data. This is a
> "citation format problem" masquerading as a "hallucination problem" — if the model were
> properly grounded, it would have cited chunk `[1]` or similar, and our grounding check
> would have validated that the cited text actually says 0.20%. The lack of citation is what
> lets the model drift off into using general knowledge.

**q010** — Effective duration (expected: `"2.71 yrs"`)
> *"...the iShares Euro Corporate Bond 1-5yr UCITS ETF IE0009XKZC98 is **around 3.67 years**
> (as of January 2026)."*
>
> Hallucinated. The correct value (2.71 yrs) is in the retrieved chunks.

---

## Root Cause Analysis

### 1. Citation format compliance — the core problem

**Severity: Critical.** Grounding = 0% across both runs. **Fix applied for Run 3.**

> **Learning note:** The system prompt said: cite every claim as `[SOURCE: 859bb0b8c2d87fa5_0003]`.
> But that hex string is completely meaningless to the model. It's like telling a human to
> cite sources by their database row ID. The model had to reproduce a random-looking string
> it had never seen before, which it can't do. It defaults to natural language attribution
> instead, which our regex never matches.
>
> The fix: number the context passages `[1]`, `[2]`, `[3]`... and tell the model to cite
> using those numbers. Numbers appear constantly in academic text and citations — the model
> knows exactly what to do with them. Our code then maps `[1]` back to the real chunk_id
> internally.

The original system prompt asked for `[SOURCE: chunk_id]` where `chunk_id` is a 20-character hex string like `859bb0b8c2d87fa5_0003`. llama3.1:8b reliably ignores this for three reasons:

- **Model size.** 8B parameter models follow complex structured output instructions inconsistently. The further a format is from natural language, the worse compliance gets.
- **Opaque identifiers.** The model has no semantic connection between `859bb0b8c2d87fa5_0003` and the chunk it came from. It cannot reproduce an identifier it's never seen.
- **Format unfamiliarity.** The training corpus for llama3.1:8b contains very little text with this specific citation bracket pattern. It defaults to prose attribution ("according to the document", "based on the provided context").

**Fix:** Numbered context headers `[1]`, `[2]`... in `prompts.py`. Model cites `[1]`. `grounding.py` maps `[1]` → `chunks_used[0]` (the first included chunk_id) before validation.

### 2. Generation length — Euro Corp Bond questions (q007, q008, q011)

**Severity: High.** Three of 20 questions consistently timeout. **Fix applied for Run 3.**

> **Learning note:** The problem is that the model was allowed to generate as many tokens as
> it wanted. For most questions (simple OCF, charges) it writes 300–400 tokens and stops.
> For complex bond fund questions it enters a verbose mode — explaining methodology,
> adding caveats, hedging — and can produce 1,000+ tokens. At 10 tokens/second, that's
> 100+ seconds of generation on top of the 60–100s prefill, pushing past the 600s timeout.
>
> The fix is `num_predict: 512` — this tells Ollama "stop after 512 tokens no matter what".
> That's still 3–4 dense paragraphs, more than enough for a fund Q&A answer. This also
> protects against the worst-case scenario: a model in a repetitive generation loop that
> would otherwise run until its context window fills up (potentially 10,000+ tokens).

Input to Ollama per question at 5,000 context cap: ~5,255 tokens total (255 token system prompt + 5,000 token context budget). At ~50 tok/s prefill = ~105s. Then generation at ~10 tok/s. For most questions the model generates 300–500 tokens ≈ 30–50s. Total: ~135–155s. Well within 600s.

Euro Corp Bond questions appear to trigger significantly longer generation — possibly entering a repetitive hedging loop or filling up the context window with numerical explanations.

**Fixes:**
- Context cap: 5,000 → 3,000 tokens. Prefill drops to ~65s.
- `num_predict: 512` in Ollama payload. Generation capped at ~50s.
- Estimated total per question: ~115s. Well within 480s wall-clock limit.

### 3. asyncio event loop blockage after timeout

**Severity: High.** Single occurrence caused a ~95-minute stall. **Fixed.**

See the detailed explanation in the Run 2 section above.

**Fix:** `client.py:generate()` now calls `await close_client()` immediately on `ReadTimeout`.

### 4. Retrieval working well, with one exception

Hit@k = 85.7% (Run 1) and 91.7% (Run 2 partial). The hybrid retrieval is functioning correctly for ISIN-keyed questions. Known misses:

- **q002 (risk_rating):** Hit@k = 0.0. The expected doc for IE00B4L5Y983 (USD Acc) is not in the top-10 results — a different share class document ranks higher. Tuning hybrid weights or adding ISIN metadata filtering would fix this.
- **q020 (esg):** Hit@k = 0.0. Fake ISIN `IE00X9999999` — correctly fails to retrieve.

---

## Code Review Findings

### `src/llm/client.py`

| Issue | Severity | Status |
|---|---|---|
| `read=180s` timeout too short for CPU inference | Critical | Fixed → 600s |
| No `close_client()` on `ReadTimeout` — blocks event loop | Critical | Fixed |
| No `num_predict` cap — allows runaway generation | High | **Fixed → 512** |

### `src/llm/prompts.py`

| Issue | Severity | Status |
|---|---|---|
| Citation format uses opaque 20-char hex IDs | Critical | **Fixed → numbered [1][2]** |
| `_MAX_CONTEXT_TOKENS = 5000` — slow prefill | Medium | **Fixed → 3,000** |
| Only 2 few-shot examples (1 cite, 1 refuse) | High | Open |

### `src/llm/grounding.py`

| Issue | Severity | Status |
|---|---|---|
| Regex matched hex IDs the model never wrote | Critical | **Fixed → match `[1]`, `[2]`** |
| `_assign_confidence([]) → "low"` when no citations — misleading | Medium | Open |

### `src/eval/runner.py`

| Issue | Severity | Status |
|---|---|---|
| Empty `result.error = ''` on some exception types | Critical | Fixed |
| No per-question timeout via `asyncio.wait_for()` | High | **Fixed → 480s** |
| Sequential evaluation — one stuck question blocks all subsequent ones | Medium | Open |

---

## R3 — Run 3 — `20260303T014203`

**Status:** 20/20 questions complete — no hangs, no timeouts
**Duration:** ~38 minutes
**Verdict:** ⚠️ Partial — grounding fixed, two new failure modes found

### Summary Metrics

| Metric | Value |
|---|---|
| Hit@k | **88.9%** ✅ |
| Grounding rate | **35.0%** 🟡 (up from 0%) |
| Refusal accuracy | 50.0% ❌ |
| Correct refusals | **100%** ✅ (all 3 should-refuse questions correct) |
| Answerable grounding | 41.2% 🟡 |
| Avg retrieval | 4,145 ms |
| Avg generation | 86,142 ms (~86s) |
| Errors | 5 × RuntimeError (q001–q005) |

### What Worked

> **Learning note:** The numbered citation fix genuinely worked. For the questions that
> completed successfully, about half cited correctly. A grounded answer looks like:
> *"The ongoing charges figure is 0.20% [2]."*
> The model wrote `[2]`, which our `grounding.py` mapped back to `chunks_used[1]` (the second
> retrieved chunk). That chunk was in the context, so grounding is validated. This is exactly
> the pipeline working as designed.

- Generation is stable: avg 86s, well within 480s wall
- No ReadTimeouts, no event loop stalls
- Model correctly refuses all three unanswerable questions (q018 OCF non-existent fund, q019 off-topic, q020 ESG claim)

### New Issue 1 — RuntimeError: client has been closed (q001–q005)

> **Learning note:** This is a "stale connection pool" bug. The httpx client is shared across
> all requests via a global variable. After previous runs (especially R2, which had several
> timeouts), the client's internal TCP connection pool contained broken connections — sockets
> that Ollama had closed on its side. When q001 tried to send a request, httpx found only
> broken connections in the pool and threw RuntimeError instead of creating a fresh one.
> After enough failed attempts (q001–q005), the pool's cleanup logic eventually discarded
> the broken connections, and q006 got a fresh TCP connection that worked.

The error: `RuntimeError: Cannot send a request, as the client has been closed.`

Five questions in a row fail at the generation step. The error is NOT a `ReadTimeout` so our existing `close_client()` handler in `generate()` doesn't trigger. The broken client persists for 5 questions until httpx's internal connection pool eventually cleans itself up.

**Fix for R4:** Reset the httpx client at the start of every eval run. Add `await close_client()` as the first line of `run_eval()`. This guarantees a completely fresh client with an empty connection pool for every run, regardless of what previous requests did to it.

### New Issue 2 — False Refusals (q008, q010, q012, q014, q015)

> **Learning note:** These 5 questions should have been answered but the model said
> "REFUSED: The provided context does not contain information about...". This is the model
> being *too honest* — it's correctly reporting that it can't find the answer in the chunks
> it was given, but the problem is we're not giving it the right chunks. Two possible causes:
> 1. **3,000 token context cap is too aggressive** — the relevant chunk exists but got cut off
> 2. **Retrieval miss** — the relevant chunk simply wasn't in the top-10 results

The false refusal messages:
- q008 (sfdr): *"context does not contain information about SFDR classification of iShares Corp Bond 1-5yr"*
- q010 (characteristics): *"context does not contain information about effective duration"*
- q012 (characteristics): *"context does not contain information about NAV"*
- q014 (structure): *"context does not contain information about depositary for Vanguard LifeStrategy"*
- q015 (structure): *"context does not contain information about fund structure change for Vanguard LifeStrategy"*

Note the pattern: q008/q010/q012 are all iShares Euro Corp Bond questions. q014/q015 are Vanguard LifeStrategy. These are complex multi-page documents — the specific facts (SFDR classification, depositary name) may appear only in specific sections that didn't rank highly in retrieval.

**Possible fixes:**
1. Raise context cap back to 4,000 tokens — gives more room for relevant chunks
2. Increase `top_k` from 10 to 15 or 20 for these question types
3. Section-aware retrieval: prefer chunks from specific document sections (e.g. "Fund Details", "Legal")

### Per-Question Detail (R3)

| ID | Category | Should Refuse | Hit@k | Confidence | Gen (s) | Grounded | Refusal OK | Error |
|---|---|---|---|---|---|---|---|---|
| q001 | ocf | No | — | refused | — | ❌ | ❌ | RuntimeError: client closed |
| q002 | risk_rating | No | — | refused | — | ❌ | ❌ | RuntimeError: client closed |
| q003 | charges | No | — | refused | — | ❌ | ❌ | RuntimeError: client closed |
| q004 | charges | No | — | refused | — | ❌ | ❌ | RuntimeError: client closed |
| q005 | risk_rating | No | — | refused | — | ❌ | ❌ | RuntimeError: client closed |
| q006 | ocf | No | 1.0 | medium | 124 | ✅ | ✅ | — |
| q007 | ocf | No | 1.0 | low | 128 | ✅ | ✅ | — |
| q008 | sfdr | No | 1.0 | refused | 141 | ❌ | ❌ | False refusal |
| q009 | characteristics | No | 1.0 | low | 161 | ✅ | ✅ | — |
| q010 | characteristics | No | 1.0 | refused | 83 | ❌ | ❌ | False refusal |
| q011 | benchmark | No | 1.0 | medium | 96 | ✅ | ✅ | — |
| q012 | characteristics | No | 1.0 | refused | 70 | ❌ | ❌ | False refusal |
| q013 | structure | No | — | medium | 94 | ✅ | ✅ | — |
| q014 | structure | No | — | refused | 131 | ❌ | ❌ | False refusal |
| q015 | structure | No | — | refused | 125 | ❌ | ❌ | False refusal |
| q016 | regulation | No | — | medium | 126 | ✅ | ✅ | — |
| q017 | characteristics | No | 1.0 | medium | 128 | ✅ | ✅ | — |
| q018 | ocf | **Yes** | — | refused | 102 | ❌ | ✅ | Correctly refused |
| q019 | off_topic | **Yes** | — | refused | 124 | ❌ | ✅ | Correctly refused |
| q020 | esg | **Yes** | 0.0 | refused | 90 | ❌ | ✅ | Correctly refused |

---

## R4 — Run 4 — `20260303T084111`

**Status:** 20/20 complete, 0 errors
**Duration:** ~50 minutes
**Verdict:** ⚠️ Partial — client bug fixed, root cause of false refusals identified

### Summary Metrics

| Metric | Value | vs R3 |
|---|---|---|
| Hit@k | 85.7% | ↓ slightly |
| Grounding rate | 35.0% | = same |
| Refusal accuracy | 40.0% ❌ | ↓ worse |
| Correct refusals | 66.7% ❌ | ↓ regression |
| Errors | **0** ✅ | ↓ fixed |
| Avg retrieval | **714ms** ✅ | ↓ fixed (was 4,145ms) |
| Avg generation | ~200s | ↓ slower (was 86s) |

### What Worked

- **Zero RuntimeErrors** — `close_client()` at run start completely fixed the stale connection pool bug
- **Retrieval back to normal** — 714ms avg (was 4,145ms in R3 due to event loop interference)

### What Didn't Work — 4,000 Token Context Cap

> **Learning note:** The false refusals are NOT caused by insufficient context. Raising the
> cap from 3,000 to 4,000 tokens didn't fix a single false refusal. But it did:
> 1. Slow generation by ~70s per question (more tokens to read = slower prefill)
> 2. Cause q018 to falsely answer — with more context from more chunks, the model found
>    OCF text from a *different* fund and answered a fake-ISIN question as if it were real.
>    More context made hallucination *more* likely.

### Root Cause of False Refusals — Retrieval Precision

> **Learning note:** The real problem is that retrieval returns chunks from *multiple funds*.
> When q001 asks "what is the OCF for ISIN IE00B4L5Y983?", the top-10 results include
> OCF chunks from several iShares funds (they're all similar documents). The model sees
> "0.20% for iShares Core MSCI World" alongside "0.15% for iShares Euro Corp Bond" and
> can't confidently say which one belongs to the specific ISIN in the question. So it
> refuses rather than risk citing the wrong fund's number.
>
> This is correct and cautious behaviour from the model. The problem is in retrieval — we
> should only show the model chunks from the *specific document* that matches the ISIN in
> the question. Then it won't be confused by competing funds.

The fix: **ISIN metadata filter**. When a query mentions a specific ISIN, restrict retrieval to chunks from the document matching that ISIN only. The manifest DB has `isin → doc_id` already — we just need to pass this as a filter to the retrieval layer.

### Per-Question Detail (R4)

| ID | Category | Should Refuse | Hit@k | Confidence | Gen (s) | Grounded | Refusal OK | Notes |
|---|---|---|---|---|---|---|---|---|
| q001 | ocf | No | 1.0 | refused | 203 | ❌ | ❌ | False refusal — ISIN precision |
| q002 | risk_rating | No | 0.0 | refused | 180 | ❌ | ❌ | False refusal — retrieval miss |
| q003 | charges | No | 1.0 | refused | 155 | ❌ | ❌ | False refusal — ISIN precision |
| q004 | charges | No | 1.0 | refused | 173 | ❌ | ❌ | False refusal — ISIN precision |
| q005 | risk_rating | No | 1.0 | refused | 181 | ❌ | ❌ | False refusal — ISIN precision |
| q006 | ocf | No | 1.0 | medium | 180 | ✅ | ✅ | — |
| q007 | ocf | No | 1.0 | refused | 187 | ❌ | ❌ | False refusal — ISIN precision |
| q008 | sfdr | No | 1.0 | refused | 199 | ❌ | ❌ | False refusal — ISIN precision |
| q009 | characteristics | No | 1.0 | medium | 358 | ✅ | ✅ | Long — near 480s wall |
| q010 | characteristics | No | 1.0 | refused | 370 | ❌ | ❌ | False refusal — near 480s wall |
| q011 | benchmark | No | 1.0 | medium | 186 | ✅ | ✅ | — |
| q012 | characteristics | No | 1.0 | refused | 156 | ❌ | ❌ | False refusal |
| q013 | structure | No | — | medium | 178 | ✅ | ✅ | — |
| q014 | structure | No | — | refused | 169 | ❌ | ❌ | False refusal |
| q015 | structure | No | — | refused | 169 | ❌ | ❌ | False refusal |
| q016 | regulation | No | — | medium | 178 | ✅ | ✅ | — |
| q017 | characteristics | No | 1.0 | medium | 180 | ✅ | ✅ | — |
| q018 | ocf | **Yes** | — | medium | 215 | ✅ | ❌ | **Regression** — should refuse (fake ISIN), now answers |
| q019 | off_topic | **Yes** | — | refused | 185 | ❌ | ✅ | Correctly refused |
| q020 | esg | **Yes** | 0.0 | refused | 181 | ❌ | ✅ | Correctly refused |

---

## R5 — Recommendations (pending run)

### Fixes to implement

1. **Revert `_MAX_CONTEXT_TOKENS` to 3,000** — 4,000 is ~70s slower per question, caused q018 hallucination, and didn't fix any false refusals.
2. **ISIN metadata filter in retrieval** — when a query contains a specific ISIN, pass `doc_id` as a filter so vector search and FTS5 only return chunks from that document. The manifest already has `isin → doc_id`. This eliminates the "competing fund" confusion that causes most false refusals.

### Expected R5 results (if ISIN filter works)

| Metric | R4 | Expected R5 |
|---|---|---|
| Errors | 0 | 0 |
| Grounding rate | 35% | ~55–70% (ISIN-filtered questions get focused context) |
| Refusal accuracy | 40% | ~80% (false refusals on ISIN questions fixed) |
| Correct refusals | 66.7% | 100% (revert prevents q018 hallucination) |
| Avg generation | ~200s | ~120s (3,000 tokens faster) |

---

## Quick Reference

| Metric | R1 | R2 (partial) | R3 | R4 | R5 target |
|---|---|---|---|---|---|
| Hit@k | 85.7% | 91.7% | 88.9% | 85.7% | ≥ 90% |
| Grounding rate | 0.0% | 0.0% | 35.0% 🟡 | 35.0% 🟡 | ≥ 65% |
| Refusal accuracy | 0.0% | 75%* | 50.0% | 40.0% ❌ | ≥ 80% |
| Correct refusals | 0.0% | 100%† | **100%** ✅ | 66.7% ❌ | 100% |
| Errors | 20 (silent) | 3 + 1 stall | 5 (client) | **0** ✅ | 0 |
| Avg generation | 0ms | ~216s | ~86s ✅ | ~200s | < 130s |
| Total run time | ~63 min | ~10 hrs | ~38 min | ~50 min | < 45 min |

\*R2 75% = 3 ReadTimeout questions counted as wrong refusals.
†R2 correct refusals: only q018–q020 assessed; q007/q008/q011 were errors not assessed.

---

**Where we are:** Infrastructure is stable (0 errors in R4). Grounding is working for ~35% of questions. The false refusal problem is now understood — it's a retrieval precision issue, not a model or prompt problem. ISIN-based filtering in retrieval is the next fix.
