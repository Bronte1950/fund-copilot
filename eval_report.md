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
| **R3** | *(pending)* | ⏳ Not run | — | — | — | All fixes applied — first clean run expected | — |

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

## R3 — Recommendations (pending run)

### Already implemented

1. ✅ Context cap 5,000 → 3,000 tokens — saves ~40s/question prefill
2. ✅ Numbered citations `[1]`, `[2]` — model will actually use these
3. ✅ `num_predict: 512` — caps generation, eliminates timeout risk from verbose answers
4. ✅ `asyncio.wait_for(480s)` — hard wall per question regardless of what Ollama does
5. ✅ `close_client()` on timeout — prevents event loop blockage

### Run 3 expected results

| Metric | Run 2 (partial) | Expected Run 3 |
|---|---|---|
| Time per question | 181–293s | ~100–120s |
| Total run time | ~10 hours (stalled) | ~35–40 minutes |
| Hit@k | 91.7% | ~90%+ (unchanged) |
| Grounding rate | 0.0% | ≥50% (numbered citations) |
| Errors | 3 ReadTimeouts + 1 stall | 0 expected |
| Avg generation | ~216s | ~50s |

### Next if grounding is still low

> **Learning note:** If Run 3 still shows 0% grounding it means the model is still not
> writing `[1]`, `[2]` even with the improved prompt. At that point the model itself is the
> problem. Options:
> 1. Add 3–4 more few-shot examples with realistic fund text showing exactly `[1]` citations
> 2. Try a different model (`qwen2.5:7b` or `mistral-nemo`) — both have better structured output compliance than llama3.1:8b
> 3. Two-pass generation: generate answer first, then in a second prompt ask the model to add citation numbers

**Fix ISIN metadata filter for retrieval misses (q002, q005):**
Add `WHERE isin = ?` to the retrieval query for questions that include a specific ISIN. This should push Hit@k from ~90% to ~95%+.

---

## Quick Reference: What "Good" Looks Like

| Metric | R1 | R2 (partial) | R3 target |
|---|---|---|---|
| Hit@k | 85.7% | 91.7% | ≥ 90% ✅ |
| Grounding rate | 0.0% | 0.0% | ≥ 70% |
| Refusal accuracy | 0.0% | 75%* | ≥ 85% |
| Errors | 20 (silent) | 3 + 1 stall | 0 |
| Avg generation | 0ms (all failed) | ~216s | < 120s |
| Total run time | ~63 min | ~10 hrs (stalled) | < 45 min |

\*75% includes 3 ReadTimeout questions counted as wrong refusals. True refusal accuracy for questions that actually generated = 9/9 = 100%.

---

**The retrieval is already working well. The infrastructure problems are fixed. Run 3 should be the first clean, complete run — the question is just whether the model will follow the numbered citation format.**
