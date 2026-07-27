# Experiment 3 — "The Composition Window": PRE-REGISTRATION

**Registered:** 2026-07-27 (step V3-P3). **Tag:** `v3-prereg` (this commit).
**Status when written:** the two composition tiers are FROZEN (V3-P1.1); a 10-task-per-tier
**dev** calibration has been run and disclosed (V3-P2.1); the **test** splits (k1 = 60 tasks,
k2 = 48 tasks) are **sealed and untouched**. This document fixes the roster, the predictions
(verbatim), the analysis plan, the budget, and the hard gate **before** any test-set episode is
run. No API call is made in the step that writes it.

The scientific question: Experiment 1 found binding feedback helps *weak-to-mid* models and is a
null at the ceiling; Experiment 2 walked a 7-model capability ladder at fixed task difficulty
(k ≈ 0, single-bug corpus) and reproduced that shape. Experiment 3 turns the other knob —
**task difficulty via bug composition** — to test whether the "capability window" in which
binding helps is a property of the *model* or of the *model–task pair*: as we raise k (the number
of simultaneous, independent bugs), does the window **slide** so that models which were at the
ceiling at k ≈ 0 fall into the false-claiming regime and start being helped by binding?

---

## 1. Inherited and FIXED (immutable for v3; carried from v1/v2 for comparability)

**1.1 The two frozen composition tiers** (V3-P1.1; regenerate-only; later-discovered broken tasks
are excluded and logged, never fixed):

| tier | bugs (k+1) | tasks | freeze tag | `freeze_hash_k.py` sha256 |
|------|-----------|-------|------------|----------------------------|
| k1 | 2 | 70 (280 files) | `v3-freeze-k1` | `0fd7cc51ecc24e3f6a959b064ce64ac26f29ed113c639f214eb416d48bd2c23b` |
| k2 | 3 | 58 (232 files) | `v3-freeze-k2` | `0ac8644e83d3d5c21a17bccc6e32ac0d815168cfd211cabc5268e8f87f4a1a40` |

Each task is exactly k+1 frozen **v1 mutations** applied verbatim on distinct source lines of one
v1 seed; `reference.py` / `tests.py` are the seed's own files byte-for-byte. Nothing is authored;
the generator only *selects and composes* v1 mutations.

**1.2 The splits** (V3-P1.1; per-tier `split.json`; dev = first 10 task_ids = 10 distinct seeds by
round-robin construction; test = the remainder):

| tier | split.json sha256 | dev | **test (confirmatory)** |
|------|-------------------|-----|-------------------------|
| k1 | `ce9de6db0ee266f5d5e73a25cf1796c8bd102a639cbea2ae4d536e1c8d55bea6` | 10 | **60** |
| k2 | `a745efb527ca5cfc03dd7f40d97f2d27412496c02807678f20576dc477ac4f24` | 10 | **48** |

Only the **test** tasks decide any prediction below. The 20 dev tasks were used for calibration
(V3-P2.1) and are **not** confirmatory evidence.

**1.3 Harness / presentation / decode — identical to v1 and v2 (comparability is the whole point):**
- **D18 presentation** ("bare-code": `show_description = false` — the model sees only the buggy
  source and the checker's verdicts, never the spec). Decode: **temperature 0**. Step cap: **8**.
- The **v1 advisory harness** (`phase3_advisory/harness.py`) and **v1 binding harness**
  (`phase4_binding/harness.py`) run **unchanged**. The frozen **Phase-2 checker**
  (`phase2_checker/checker.py`) decides pass/fail.
- The **three binding mechanisms are unchanged for v3** (this is a registered constraint —
  binding's definition is NOT altered to accommodate composed bugs):
  1. **`done_ignored`** — a bare `DONE` line is logged and ignored as text; only a checker PASS
     ends a binding episode.
  2. **`resubmission_rejected`** — a byte-identical resubmission of the previously-failed code is
     rejected without re-running the checker; the same verdict text is re-sent verbatim.
  3. **`escalated`** — one failed check followed by **two** identical resubmissions
     (`consecutive_identical` reaching 3) ends the episode as `escalated`.

**1.4 The model transport — the v2 adapter, verbatim.** Every model is one of v2's frozen `RUNGS`
dicts selected by slug (`v2_ladder/adapter/client.py`), so its **snapshot, route, provider, and
per-1M prices are byte-identical to what v2's manifests recorded.** OpenAI-direct route delegates
to the frozen v1 `OpenAIChatClient`; OpenRouter route reuses v1 TLS/scrub/parse by import. Request
body is exactly `{model, temperature:0, messages}` — no reasoning parameter ever sent. Keys are
never printed, logged, or committed.

---

## 2. The full-run roster (6 models) and the k=0 anchor

The full run uses **6 models**, chosen to span the v2 ladder from a **bottom-edge anchor** to the
**top anchor**, with the four "window" models in between:

| role | model (v3 slug) | v2 snapshot | route | price in/out per 1M |
|------|-----------------|-------------|-------|---------------------|
| bottom-edge anchor | `llama-3.1-8b` | `meta-llama/llama-3.1-8b-instruct` | OpenRouter | 0.05 / 0.08 |
| window | `qwen-2.5-7b` | `qwen/qwen-2.5-7b-instruct` | OpenRouter | 0.04 / 0.10 |
| window | `claude-3-haiku` | `anthropic/claude-3-haiku` | OpenRouter | 0.25 / 1.25 |
| window | `gpt-4o-mini` | `gpt-4o-mini-2024-07-18` | OpenAI-direct | 0.15 / 0.60 |
| window | `gemini-2.5-flash-lite` | `google/gemini-2.5-flash-lite` | OpenRouter | 0.10 / 0.40 |
| top anchor | `gpt-4.1` | `gpt-4.1-2025-04-14` (via alias `gpt-4.1`) | OpenAI-direct | 2.00 / 8.00 |

**Roster decision — `llama-3.2-3b` is DROPPED (logged).** In v2's committed full run
(`k ≈ 0`, single-bug corpus, advisory arm), `llama-3.2-3b` scored **66/87 with 30 step_caps** —
it is *below the window even at k = 0*: it does not converge, so binding cannot rescue it (v2 saw
binding *below* advisory for it, Δ = −3.4 pp). Raising k pushes it further out of range, adding
only near-zero-signal step_cap noise and OpenRouter trickle-hang exposure at 3× the episode count.
`llama-3.1-8b` is kept as the bottom-edge anchor because at k = 0 it is **still mostly capable**
(80/87, only 3 step_caps, 4 false-DONEs) — the right place to watch escalation-attributed loss
(P3) grow with k.

**The k = 0 line is taken from v2's committed full run — it is NOT re-run.** The Δ-vs-k matrix
(§4) uses v2's frozen test-set numbers as the k0 column for every roster model that v2 ran (all six
were v2 rungs). This keeps k0 comparable and spends no budget. Anchor k0 facts, from v2's committed
manifests (advisory arm, 87 test tasks):

```
gpt-4.1        advisory 87/87   false-DONE 0    step_cap 0     (top anchor: null at k0)
llama-3.1-8b   advisory 80/87   false-DONE 4    step_cap 3     (bottom-edge anchor)
llama-3.2-3b   advisory 66/87   false-DONE 1    step_cap 30    (dropped: below-window at k0)
```

---

## 3. Dev-glimpse disclosure (registered AFTER this glimpse; it is NOT confirmatory)

These predictions were written **after** the V3-P2.1 dev calibration — a **10-task-per-tier
glimpse** (200 episodes, dev split only). Full disclosure of that glimpse, quoted from V3-P2.1:

> **(a) BAND CHECK — window models' advisory success vs the 40–70% band**
> k1: qwen 5/10=50% [IN], claude-3-haiku 7/10=70% [IN], gpt-4o-mini 7/10=70% [IN],
> gemini 5/10=50% [IN] — **4/4 in band.**
> k2: qwen 4/10=40% [IN], claude-3-haiku 7/10=70% [IN], gpt-4o-mini **8/10=80% [OUT, high edge]**,
> gemini 6/10=60% [IN] — **3/4 in band.**
>
> **(b) gpt-4.1 WATCH (ceiling probe, advisory):**
> k1: success 10/10, **false-DONEs 0**, step_caps 0.
> k2: success 10/10, **false-DONEs 0**, step_caps 0.
>
> Window binding = 9–10/10 everywhere on dev; every window-model advisory *miss* on dev was a
> false-DONE; the only binding escalations were qwen (1 per tier).

**What this glimpse means for the predictions, stated honestly:**
- The four window models sit at the **top edge** of the 40–70% band on dev, and gpt-4o-mini's k2
  dev cell pokes *above* it (80%). A 10-task cell has ≈ ±15 pp of sampling noise, so this is a
  weak instrument reading, not a result.
- **Crucially, gpt-4.1 showed _0 false-DONEs on dev at BOTH tiers_ (including k2).** Prediction
  **(P2)** below nonetheless registers that gpt-4.1's advisory false-DONE count becomes **> 0 at
  k2 on the sealed test split**. This runs *against* the (tiny, noisy) dev signal on purpose:
  10 dev tasks is far too few to surface a low-rate false-claiming event that the theory expects
  to appear only under the harder, larger 48-task k2 **test** distribution. P2 is therefore a
  genuinely **risky** prediction, not a restatement of what dev already showed.

The confirmatory tests in §4 run **only** on the sealed test splits (k1 = 60, k2 = 48).

---

## 4. PREDICTIONS (verbatim — scored against this exact text)

**(P1)** For each window model (qwen-2.5-7b, claude-3-haiku, gpt-4o-mini, gemini-2.5-flash-lite),
Δ = success(binding) − success(advisory) > 0 at each of k1 and k2, by per-model task-paired exact
McNemar.

**(P2)** The capability window is a property of the model–task pair, not the model: as k rises,
models ABOVE the k≈0 window enter the false-claiming regime. Operationally: gpt-4.1's advisory
false-DONE count, 0 at v1/v2's corpus (k≈0), becomes >0 at tier k2 (3 simultaneous bugs);
correspondingly its Δ becomes positive at k2. More generally, each model's Δ-vs-k is increasing
over the k range in which its advisory false-DONE rate is increasing.

**(P3)** b-direction discordants (advisory✓/binding✗) whose binding episode ends escalated are
counted separately as escalation-attributed losses. EXPECTED: they concentrate at the weak edge
(llama-3.1-8b) and grow with k. Binding's definition is NOT changed for v3; this converts the known
escalation wart into a measured quantity.

**(P4)** For any model at advisory ceiling (100%) within a tier, binding total cost ≤ advisory
total cost in that tier.

**(P5)** EXPLORATORY: the window peak (the argmax-Δ model) shifts toward stronger models as k
increases across k0 → k1 → k2.

---

## 5. Analysis plan (deterministic, one command; scored against §4 verbatim)

Run on the committed test-run logs + manifests only; no randomness, no API calls:

1. **Per model × tier 2×2 + exact McNemar** (the v1 method, `phase6_analysis`): the paired
   advisory-vs-binding table per (model, tier), with the exact two-sided McNemar p-value and Δpp.
2. **Δ-vs-k matrix** — one line per model, columns **k0 (from v2's committed test data), k1, k2**;
   Δ = success(binding) − success(advisory) in pp. Scores P1 (window rows > 0 at k1, k2), P2
   (gpt-4.1 row 0 → positive by k2; monotone-increasing where false-DONE rate increases), and P5
   (argmax-Δ model index vs k).
3. **False-DONE-vs-k mediator surface** — advisory false-DONE rate per (model, k) across
   k0/k1/k2; the mediator P2 ties Δ to. gpt-4.1's k0=0 → k2>0 transition is read here.
4. **Escalation-attributed-loss table** — per (model, tier): count of b-direction discordants
   (advisory✓ / binding✗) whose binding episode `status == escalated`. Scores P3 (concentration at
   llama-3.1-8b; growth with k).
5. **Rescue decomposition** (v1 method): of binding's a-direction wins (advisory✗ / binding✓),
   the split into **forced** (first submission already differed) vs **first-sample** rescues.
6. **Cost check** — per (model, tier) advisory vs binding total cost, restricted to models at
   advisory ceiling (100%) in that tier. Scores P4.
7. **Bug-type breakdown of discordants** — the constituent bug types (from each task's `meta.json`)
   of the discordant tasks in both directions.
8. **Scorecard** — every prediction P1–P5 marked SUPPORTED / NOT-SUPPORTED / EXPLORATORY against
   its verbatim §4 text, with the numbers that decide it.

---

## 6. Budget

- **v3 cumulative hard cap: $20.00. Stop-gate: $12.00.** Cumulative v3 spend to date (calibration,
  V3-P2.1): **$0.074336**.
- **Full run = 6 models × 2 modes × 108 test tasks (60 k1 + 48 k2) = 1,296 episodes.**
- **Projected full-run cost ≈ $0.415**, from calibration actuals (per-model per-tier per-episode
  cost × the 60/48 test-split sizes) for the five calibrated models, and from v2's committed
  full-run per-episode cost for the un-calibrated bottom-edge anchor `llama-3.1-8b`. Breakdown:
  gpt-4.1 ≈ $0.313 (≈ 75% of the bill), claude-3-haiku ≈ $0.046, gpt-4o-mini ≈ $0.021,
  gemini ≈ $0.016, llama-3.1-8b ≈ $0.012, qwen ≈ $0.006. **Projected cumulative v3 after the full
  run ≈ $0.49** — an order of magnitude under the stop-gate, two under the cap.

---

## 7. THE P4 GATE (hard; no test-set episode may run until BOTH conditions hold)

**No test-set episode may be run until:**

**(a)** the tag **`v3-prereg`** exists, and a **timestamp-ordered proof** is produced at the P4
step showing that this pre-registration commit (and its tag) **precede** the first test-run commit
(`git show v3-prereg --format='%ci'` predating the run logs' commit time); **and**

**(b)** the **courier's publish confirmation is logged verbatim in the ledger** (`EXPERIMENT_LOG.md`)
— the live-call authorization for the confirmatory full run is recorded word-for-word before the
first paid test episode.

Until both hold, `v3_window/runs/logs/` and `v3_window/runs/manifests/` stay empty (`.gitkeep`
only). This gate is the pre-registration's teeth: it makes "predictions registered before data"
a checkable, timestamped fact, not a claim.
