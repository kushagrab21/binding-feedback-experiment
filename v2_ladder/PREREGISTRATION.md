# Experiment 2 — The Capability Ladder — PRE-REGISTRATION

**Registered at V2-P1 and tagged `v2-prereg`. Locked before any episode was run.** The
ladder, the external capability ranking, the ranking rule, and the five predictions below are
fixed at the tag; **no number or prediction changes after tagging** (the † MMLU figures are
frozen as transcribed regardless of later verification, per the ranking rule). No test-set
episode precedes this registration — `v2_ladder/runs/logs/` holds only its `.gitkeep`.

**Thesis (carried from v1).** v1 showed a *positive interaction*: binding feedback (done is
computed by the checker, never declared) helped the weak model (+9.2 pp) and did nothing for
the strong one (+0.0 pp), under D18 bare-code presentation, temp 0, step cap 8, on the 87
held-out tasks. v1 had only two rungs. Experiment 2 replaces the two-point contrast with a
**capability ladder** of 7 rungs spanning ≥3 providers, to trace how the binding advantage
Δ = success(binding) − success(advisory) varies with model capability — in particular to
probe the exploratory **"too weak to rescue"** window below the v1 weak anchor, where a model
may be too weak for forced iteration to recover it.

**Inherited verbatim from v1 (immutable; re-verified at V2-P0, commit `4cf73f4`):** the
97-task frozen corpus (`FREEZE_HASH
dfc14c26ec267b03c2789752cf7e63c34a06fd3b94dc6cebe14f9f70b62f2017`), the 10/87 dev/test split
(`split.json` sha256 `6f69be75d4c1b1ea0348e7b0217ac83e7cfc8c19732a6d6d71e2ec5be9e75015`),
the D18 bare-code presentation (`show_description:false`), the exact advisory/binding prompts,
step cap 8, temperature 0, and the frozen checker + static guard. Both hashes were recomputed
char-for-char against these pins at V2-P0 and matched. Nothing under `phase1_tasks/` …
`phase7_writeup/` is edited, moved, or renamed. Dev set only through V2-P4; the 87 test tasks
are untouched until then. Keys are never printed or committed.

---

## (a) The ladder — exact snapshot IDs and routes

Seven rungs. **Anchors** (rungs at the v1 endpoints) run via the existing **OpenAI direct**
route (`https://api.openai.com/v1/chat/completions`, `OPENAI_API_KEY`). **Ladder rungs** run
via **OpenRouter** (`https://openrouter.ai/api/v1/chat/completions`, `OPENROUTER_API_KEY`, new
resolver at `v2_ladder/adapter/keys.py`). Every rung is a **plain chat model** (no
reasoning-token models), honors **temperature 0**, and takes the v1 OpenAI-style `messages`
array unchanged. Availability and exact IDs were confirmed against `GET
https://openrouter.ai/api/v1/models` (metadata only — no completion) on **2026-07-26**.

| # | snapshot ID (exact) | route | provider | class | $ /1M in | $ /1M out |
|---|---|---|---|---|---|---|
| 1 | `meta-llama/llama-3.2-3b-instruct` | OpenRouter | Meta | open-weights 3B (weakest) | 0.05 | 0.33 |
| 2 | `meta-llama/llama-3.1-8b-instruct` | OpenRouter | Meta | open-weights 8B | 0.05 | 0.08 |
| 3 | `qwen/qwen-2.5-7b-instruct` | OpenRouter | Alibaba/Qwen | open-weights 7B | 0.04 | 0.10 |
| 4 | `anthropic/claude-3-haiku` | OpenRouter | Anthropic | small hosted (Haiku-class) | 0.25 | 1.25 |
| 5 | `gpt-4o-mini-2024-07-18` | **OpenAI direct** | OpenAI | v1 **weak anchor** | 0.15 | 0.60 |
| 6 | `google/gemini-2.5-flash-lite` | OpenRouter | Google | mid hosted (Flash-class) | 0.10 | 0.40 |
| 7 | `gpt-4.1-2025-04-14` | **OpenAI direct** | OpenAI | v1 **strong anchor** | 2.00 | 8.00 |

(Rung order above follows the capability ranking derived in (b): #1 weakest → #7 strongest.)

Providers spanned: OpenAI, Meta, Alibaba/Qwen, Anthropic, Google — **5 providers**.
Weak-heavy by design: **four rungs (1–4) sit below the v1 weak anchor** (rung 5), which is
exactly the "too weak to rescue" region the ladder is built to probe. Three open-weights rungs
(Llama-3.2-3B, Llama-3.1-8B, Qwen2.5-7B) anchor the weak end deliberately.

**Reasoning-token note (rung 6).** Gemini 2.5 Flash-Lite has an *optional* thinking mode that
is **off by default**; the adapter sends only `{model, temperature, messages}` (no `reasoning`
/ thinking parameter), so it behaves as a plain chat model and emits no reasoning tokens.

**Rung-6 fallback rule.** If the V2-P2 smoke shows `google/gemini-2.5-flash-lite` emitting
reasoning tokens or refusing temp 0 under a `{model, temperature, messages}`-only call, it is
replaced by the strongest available Google flash-class model that passes the same check, as a
logged deviation, before any test-set episode; its rank is then re-derived from the same
sources and rule.

---

## (b) External capability ranking (fixed rule over cited published numbers)

**Two published sources**, both snapshotted on **2026-07-26**:

**Source A — LMArena / Chatbot Arena, text-arena Elo.**
Canonical: <https://lmarena.ai/leaderboard>. Numbers retrieved 2026-07-26 from the
republishing aggregator <https://metatext.io/benchmarks/lmarena-elo>. Snapshot used (higher =
stronger):

| model | Elo |
|---|---|
| gpt-4.1 | 1382 |
| gemini-2.5-flash-lite (…-preview-06-17) | 1368 |
| gpt-4o-mini | 1287 |
| claude-3-haiku | 1195 |
| llama-3.1-8b | 1187 |
| llama-3.2-3b | 1110 |
| qwen2.5-7b-instruct | *not listed in the retrieved top-192 snapshot* |

**Provenance caveat.** Source-A Elo was read from the metatext.io republication of the
lmarena.ai leaderboard rather than from lmarena.ai directly; the URL and the exact numbers
used are embedded above so the snapshot is auditable, and the republication route is recorded
here as the one provenance caveat on the ranking inputs.

**Source B — vendor-published MMLU (5-shot), classic 0–100 scale**, from official model
cards / release posts (higher = stronger). Each figure was fetch-checked on 2026-07-26 and
marked accordingly; **no figure changes after tagging regardless of verification outcome**:

| model | MMLU (5-shot) | source card | verification |
|---|---|---|---|
| gpt-4.1 | 90.2 | <https://openai.com/index/gpt-4-1/> | † unverifiable at registration — transcribed figure retained; rank position corroborated by Source A |
| gemini-2.5-flash-lite | 84.5 | <https://deepmind.google/models/gemini/flash-lite/> | † unverifiable at registration — transcribed figure retained; rank position corroborated by Source A |
| gpt-4o-mini | 82.0 | <https://openai.com/index/gpt-4o-mini-advancing-cost-efficient-intelligence/> | † unverifiable at registration — transcribed figure retained; rank position corroborated by Source A |
| claude-3-haiku | 75.2 | <https://www.anthropic.com/news/claude-3-family> | † unverifiable at registration — transcribed figure retained; rank position corroborated by Source A |
| qwen2.5-7b-instruct | 74.2 | <https://qwenlm.github.io/blog/qwen2.5-llm/> | ✓ verified by fetch 2026-07-26 |
| llama-3.1-8b-instruct | 69.4 | <https://ai.meta.com/blog/meta-llama-3-1/> | † unverifiable at registration — transcribed figure retained; rank position corroborated by Source A |
| llama-3.2-3b-instruct | 63.4 | <https://ai.meta.com/blog/llama-3-2-connect-2024-vision-edge-mobile-devices/> | † unverifiable at registration — transcribed figure retained; rank position corroborated by Source A |

The six `†` figures could not be re-read from their primary cards at registration (OpenAI
pages returned HTTP 403 to automated fetch; the Anthropic, Meta, and Google cards render their
benchmark tables as images). Only Qwen's 74.2 was machine-readable and is `✓ verified`. Because
every rung's ladder position is fixed by the fully-retrieved Source-A Elo, the ranking does not
depend on the exact `†` values. Note: the post-cutoff "MMLU ≈ 37" figures now circulating are a
*different index scale* (Artificial Analysis Intelligence Index v4.0) and are **not** used here.

**Fixed ranking rule (stated before any episode).**
1. Within each source, rank models 1 = strongest … (ascending rank = stronger).
2. A model's **composite score = mean of its available per-source ranks** (a model absent from
   a source is ranked only on the sources that list it — this applies to `qwen2.5-7b`, absent
   from Source A).
3. Order the ladder by **ascending composite score** (lower = stronger).
4. **Ties broken by Source A** (higher LMArena Elo = stronger). Second tiebreak: Source B MMLU.

**Resulting ranking (weakest rung 1 → strongest rung 7):**

| rung | model | A-rank (Elo) | B-rank (MMLU) | composite (mean) |
|---|---|---|---|---|
| 1 (weakest) | llama-3.2-3b-instruct | 6 | 7 | 6.5 |
| 2 | llama-3.1-8b-instruct | 5 | 6 | 5.5 |
| 3 | qwen2.5-7b-instruct | — | 5 | 5.0 |
| 4 | claude-3-haiku | 4 | 4 | 4.0 |
| 5 | gpt-4o-mini-2024-07-18 | 3 | 3 | 3.0 |
| 6 | gemini-2.5-flash-lite | 2 | 2 | 2.0 |
| 7 (strongest) | gpt-4.1-2025-04-14 | 1 | 1 | 1.0 |

No ties arise, so the tiebreak is not exercised. The two sources agree on the coarse order;
the composite is monotone and total. This fixed rank vector `[1..7]` is the `rank` variable
used by the Spearman test in (d). **The ranking is locked at this tag and is not revised after
any episode is observed.**

---

## (c) Registered predictions

Verbatim from the addendum; these are the pre-registered predictions, locked at this tag:

> (i) Δ ≥ 0 for every model (binding never hurts). (ii) Δ decreases with pre-registered capability rank (Spearman, one-sided). (iii) False-DONE rate in advisory decreases with capability rank. (iv) For models at advisory ceiling, binding total cost ≤ advisory total cost. (v) EXPLORATORY: Δ may be non-monotonic at the weak end — a model can be too weak to rescue (false-DONEs in advisory AND fails to repair under forced iteration, ending at step_cap). If observed, this defines a "capability window" for completion-gating; it is registered as exploratory, not confirmatory.

---

## (d) Analysis plan — VERBATIM

> Per-model exact McNemar on 87 paired tasks; Spearman one-sided of Δ vs rank; false-DONE and
> cost columns; rescue decomposition; bug-type breakdown of discordants.

**Convention: capability rank 1 = strongest. Prediction (ii) is tested as a one-sided Spearman
with expected *positive* correlation between Δ and the numeric rank value (larger rank = weaker
= larger Δ).**

Operationalization (fixed here, matching v1's frozen Phase-6 methods so v2 reuses them):

- **Per-model exact McNemar on 87 paired tasks.** For each rung, the 87 test tasks are paired
  across the advisory and binding arms (same task, same model, same D18 presentation). Count
  `b` = advisory✓/binding✗ and `c` = advisory✗/binding✓ discordant pairs; report the
  **exact two-sided binomial McNemar p** over `n = b + c` (stdlib `math.comb` only, no SciPy),
  exactly as v1 6.1.
- **Spearman one-sided of Δ vs rank.** Compute per-rung Δ = success(binding) −
  success(advisory) (pp). Test the **one-sided** Spearman rank correlation between Δ and the
  fixed capability `rank` from (b), in the direction fixed by the convention above (prediction
  (ii): larger rank = weaker → larger Δ, expected positive).
- **False-DONE and cost columns.** Per cell (model × mode): success n/87, false-DONE count
  (`model_declared_done ∧ ¬final_passed`), `step_cap` count, `done_ignored/rejected/escalated`,
  mean steps, tokens in/out, and USD cost — the v1 per-cell table shape. Prediction (iii)
  (advisory false-DONE rate vs rank) and prediction (iv) (binding cost ≤ advisory cost at
  advisory ceiling) are read off these columns.
- **Rescue decomposition.** For each rung, on the tasks that are advisory-failed / binding-
  solved, split into **genuine forced repairs** (≥2 checked verdicts: FAILED → byte-changed
  submission → PASSED) vs **first-sample passes** (solved on binding's first submission at
  temp 0 while advisory false-DONE'd the same task), verified from logs — the v1 5.4/6.1
  "6 forced repairs + 2 first-sample" decomposition, per rung. The exploratory prediction (v)
  ("too weak to rescue") is read here as advisory false-DONEs that binding does **not** repair
  (ending at `step_cap`).
- **Bug-type breakdown of discordants.** For each rung, tabulate the discordant (advisory✗/
  binding✓) tasks by the frozen 8-type bug taxonomy (e.g. whether they concentrate in
  `missing-edge-case`, as the 6/8 did in v1), from each task's frozen `meta.json`.

All analysis is read-only over committed v2 episode logs + frozen `phase1_tasks/` metadata +
the frozen `run_checks`; no API calls; deterministic (no wall-clock in outputs), mirroring v1
6.1.

---

## (e) Budget

- **Hard cap: $20** (inherited standing rule; a run that would cross it stops and reports).
- **Expected: < $5.**
- **Projected (padded upper bound): ≈ $1.25** for the full 7-rung run.

**Basis.** Full run = 7 rungs × 2 modes × 87 tasks = **1218 episodes**; 174 episodes/model.
Per-episode tokens are padded to **1500 in / 300 out** — roughly 3–5× the v1 actuals
(v1 cells ran ~250–520 in / ~85–95 out per episode) to cover weak models taking more binding
steps under the cap-8 loop. Prices: OpenRouter rungs from the live catalog (2026-07-26);
OpenAI anchors from OpenAI list price (gpt-4o-mini $0.15/$0.60, gpt-4.1 $2.00/$8.00 per 1M) —
<https://openai.com/api/pricing/>.

| rung | model | route | proj. cost |
|---|---|---|---|
| 1 | llama-3.2-3b-instruct | OpenRouter | $0.030 |
| 2 | llama-3.1-8b-instruct | OpenRouter | $0.017 |
| 3 | qwen-2.5-7b-instruct | OpenRouter | $0.016 |
| 4 | claude-3-haiku | OpenRouter | $0.131 |
| 5 | gpt-4o-mini-2024-07-18 | OpenAI direct | $0.070 |
| 6 | gemini-2.5-flash-lite | OpenRouter | $0.047 |
| 7 | gpt-4.1-2025-04-14 | OpenAI direct | $0.940 |
| | **projected total (padded)** | | **$1.251** |

gpt-4.1 dominates the projection ($0.94 of $1.25) purely on list price; on v1-actual token
usage its real cost is far lower (~$0.31). Even the padded total is ~4× under the $5 expected
and ~16× under the $20 cap.

---

## Decisions

- **8th rung — considered and declined.** An 8th rung `anthropic/claude-haiku-4.5` (OpenRouter,
  confirmed available at $1/$5 per 1M) was considered to give the top of the curve a second
  provider. It is **declined** to stay within the addendum's 5–7-model envelope; the ladder
  stays at **7 rungs**. Consequence, recorded as a **limitation**: the top rung (gpt-4.1) is
  single-provider, so the strong end of the curve rests on one vendor.
- **Rung-6 fallback** and the **Source-A provenance caveat** are stated inline in (a) and (b)
  respectively.
- **Ranking robustness.** Because ladder positions are fixed by the fully-retrieved Source-A
  Elo, the six `†`-unverifiable MMLU figures cannot move any rung; they are retained as
  transcribed and frozen at this tag.
