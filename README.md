# Binding Feedback Experiment

Does it matter whether an LLM agent *decides for itself* that it is done, or whether
"done" is *computed* for it by a checker it cannot overrule? This repository is a
complete, reproducible experiment on that question — **advisory** feedback (the model
may declare the task finished) vs **binding** feedback (completion is decided by the
checker, and the model's own "DONE" is ignored) — run over a frozen corpus of buggy-code
repair tasks against two OpenAI models.

Everything below traces to a hash-pinned artifact. The full build trail — every step, its
raw command output, and every deviation — is in [`EXPERIMENT_LOG.md`](EXPERIMENT_LOG.md).

---

## Claim & result

**Thesis.** Binding feedback helps a *weak* model and does *nothing* for a *strong* one —
a positive interaction, not a main effect. The mechanism is narrow and specific: binding
removes the *false-DONE exit*, the failure mode in which a model confidently declares a
wrong answer finished.

**The 2×2 (held-out test set, 87 tasks, D18 bare-code presentation, temp 0):**

| model | advisory | binding | Δ (binding − advisory) |
|---|---|---|---|
| gpt-4o-mini-2024-07-18 (cheap / **weak**) | **90.8%** (79/87) | **100.0%** (87/87) | **+9.2 pp** |
| gpt-4.1-2025-04-14 (frontier / **strong**) | 100.0% (87/87) | 100.0% (87/87) | +0.0 pp |

**Interaction (the thesis): Δmode(weak) − Δmode(strong) = +9.2 − 0.0 = +9.2 pp.**

Exact task-paired **McNemar** (stdlib `math.comb`, no SciPy): the weak model has 8
discordant pairs, *all* in the advisory-fail / binding-pass direction (b=0, c=8), exact
two-sided **p = 0.0078125**; the strong model has **0** discordant pairs (p = 1). Binding
significantly helps the weak model and moves nothing measurable for the strong one.

**Mechanism (why the effect exists and where it comes from).** All **8** of the weak
model's advisory failures were **false-DONEs** — the model submitted wrong code *and*
declared it done, and advisory accepted the declaration regardless of the checker's
verdict. **6 of those 8** were `missing-edge-case` bugs, whose required behavior (a guard
that raises on a boundary input) was documented only in the task description/docstring —
exactly the information the D18 presentation withholds — so the weak model had no
non-checker way to recover it. Binding's advantage came **entirely from computed
completion**: it simply refuses to let the model quit while the checker is red. The other
two binding mechanisms — identical-resubmission blocking and escalation — **never fired
once** in the entire run (see D15); the strong model never false-DONEd because in advisory
it *iterated to a correct answer before declaring done*.

---

## Method

**Corpus (Phase 1).** 97 frozen tasks, each a short stdlib-pure Python function with a
**single** injected bug drawn from a closed 8-type taxonomy (`off-by-one`,
`wrong-comparison`, `wrong-operator`, `inverted-condition`, `wrong-variable`,
`missing-edge-case`, `wrong-return`, `input-mutation`). Tasks are generated from 25
hand-written seed functions by a mutation manifest, then **frozen**: content fingerprint
`FREEZE_HASH = dfc14c26ec267b03c2789752cf7e63c34a06fd3b94dc6cebe14f9f70b62f2017` (git tag
`phase1-freeze`). A deterministic **10 dev / 87 test** split
(`split.json` sha256 `6f69be75d4c1b1ea0348e7b0217ac83e7cfc8c19732a6d6d71e2ec5be9e75015`)
reserves 10 tasks for pilots; the 87 test tasks stayed unopened until the full run. Each
task carries a computed difficulty tag (easy / medium / hard, by kill-count).

**Checker / judge (Phase 2).** `run_checks` runs a submission against the task's frozen
test suite in an isolated subprocess and returns a deterministic verdict (`PASSED`, or
`FAILED` + each failing test name and an error excerpt; temp-dir paths scrubbed). A
**static, AST-based pre-execution guard** rejects the obvious network / filesystem / OS /
dynamic-exec surface before any code runs. This is a mitigation, **not an OS-level
sandbox** — see Limitations.

**The two harnesses (Phases 3 & 4).** Both share *everything that must be shared* by
direct import: the task-presentation builder, the verdict renderer, the reply parser, the
JSONL logger, and `run_checks`. The feedback *content* is therefore byte-identical across
arms. They differ in **exactly three structural ways, and no others**:

1. **Done is computed, not declared.** *Advisory:* a bare `DONE` line ends the episode and
   the declaration is accepted **regardless of the last verdict** — this is what makes a
   false-DONE possible. *Binding:* there is no declare-done action; `status = "solved"` iff
   `run_checks` passes; any `DONE` line is ignored as text (`done_ignored`). This is the
   single divergence point that carries the whole result.
2. **Identical resubmission is rejected** (binding only): a byte-identical resubmission
   after a failure is not re-checked; the prior verdict is re-sent verbatim.
3. **Escalation** (binding only): three consecutive identical failed submissions end the
   episode `status = "escalated"`.

**Models & config.** `gpt-4o-mini-2024-07-18` (cheap / weak) and `gpt-4.1-2025-04-14`
(frontier / strong); **temperature 0**, **step cap 8**, both models identical across arms.
(The originally-planned `gpt-4.1-nano` was un-provisioned on this project; the substitution
is deviation **D16**.)

**Presentation — D18 bare-code (the regime in which the effect exists).** This must be
stated plainly. Under the natural *spec-shown* presentation, **both models one-shot
essentially everything** and there is no advisory-vs-binding signal at all. The
discriminating regime was reached in a logged, pre-registered arc:

- **P5.1** — spec shown (description + buggy source): both models one-shot all 10 dev
  tasks; zero FAILED verdicts. **No signal.**
- **D17** — withhold the separate `meta["description"]`, but the buggy source (with its
  docstrings) is still shown: still both models one-shot everything. **Still no signal.**
- **D18** — additionally strip *all* docstrings and comments from the presented source (a
  deterministic `ast.parse` → `ast.unparse` transform applied **only when building the
  prompt** — the frozen `buggy.py` files on disk are never modified, and runtime string
  literals such as error messages are preserved). The model is handed the function name +
  bare code + one fixed withheld-notice sentence. **This is the first and only regime in
  which the corpus discriminates the modes.** The full 348-episode run uses D18.

The effect is real, but it exists **only** under this deliberately spec-starved
presentation. That is reported, not hidden — it is itself a finding (see the post).

---

## Limitations

Every one of these is drawn from the experiment ledger; none is omitted.

1. **Synthetic tasks.** Single-mutation bugs in short stdlib functions — not organic
   bugs from real codebases.
2. **Possible training-data contamination.** The seed functions are common utilities;
   the models may have seen them. This inflates *absolute* success rates but not the
   *differential* (advisory-vs-binding) comparison, which is what the thesis rests on.
3. **Two models, one provider (OpenAI), one regime.** The effect is demonstrated for one
   weak/strong pair, compressed into the single discriminating D18 presentation.
4. **The effect rests on 8 tasks, concentrated in one bug class.** All 8 weak-advisory
   failures, and 6 of them are `missing-edge-case`. This is a narrow base.
5. **2 of the 8 "rescues" are temp-0 sampling variance, not iteration.** `task_002` and
   `task_091` passed on binding's *first* submission while advisory false-DONEd the same
   task. The honest count is **6 genuine forced repairs** + 2 first-sample passes = 8; the
   +9.2 pp includes that small stochastic component.
6. **Binding's resubmission-blocking and escalation never engaged (D15).** This model
   never resubmits a byte-identical block under opaque feedback, so two of binding's three
   mechanisms are mock-verified but never exercised live. The measured advantage is from
   computed completion alone.
7. **No OS-level sandbox in the checker.** The pre-execution guard is a static
   over-approximation only; a real sandbox (seccomp / namespaces / container) would be
   required before trusting this judge on untrusted or non-stdlib-pure code.
8. **D17/D18 were adopted pre-test-set but post-pilot.** The presentation was hardened in
   response to the dev-set ceiling, then pre-registered before any test-set episode ran —
   but it was not fixed in advance of seeing the pilots.

---

## Reproduce it

All commands run from the repository root. Task regeneration and the analysis are
**offline and deterministic**; only re-running the 348 episodes needs an OpenAI key.

```bash
# 1. Regenerate + validate the frozen corpus (offline, deterministic)
python3 phase1_tasks/seeds/validate_seeds.py            # 25 seeds, AST + invariants
python3 phase1_tasks/generator/generate_tasks.py        # rewrites 97 tasks byte-identically
python3 phase1_tasks/generator/validate_tasks.py        # 97 accepted, invariants hold
python3 phase1_tasks/generator/freeze_hash.py           # must print FREEZE_HASH dfc14c26…

# 2. Test the judge and both harnesses (offline, MockModel only — no key)
cd phase2_checker  && python3 -m unittest test_checker  && cd ..
cd phase3_advisory && python3 -m unittest test_harness  && cd ..
cd phase4_binding  && python3 -m unittest test_harness  && cd ..

# 3. Regenerate the results table from the committed episode logs (offline, deterministic)
python3 phase6_analysis/analyze.py                      # writes phase6_analysis/results.{md,json}
#   results.md   sha256 29bcf9e5b8a0b416c3a4d84eb340ad53c3718a681377c2e1d2765802c0c48599
#   results.json sha256 27afe558b6f84b9084f69f6ea46925b91aa123f0d99dd92683f8f2ed0a82437f

# 4. (OPTIONAL — needs an OpenAI key via env) re-run the live episodes
#    export OPENAI_API_KEY=…   then:   python3 phase5_runs/run_full.py
```

`analyze.py` reads only the committed Phase-5 JSONL logs, the cell manifests, the frozen
task metas, and the frozen checker; it makes no API calls and writes nothing outside
`phase6_analysis/`. Two runs produce byte-identical output.

---

## Experiment 2 — the capability ladder

Experiment 1 had two points (weak, strong). **Experiment 2 replaces the two-point contrast
with a 7-rung capability ladder across 5 providers** — Llama-3.2-3B, Llama-3.1-8B, Qwen2.5-7B,
Claude-3-Haiku, GPT-4o-mini, Gemini-2.5-Flash-Lite, GPT-4.1 (weakest→strongest, ranked before
any episode from published LMArena Elo + MMLU; see [`v2_ladder/PREREGISTRATION.md`](v2_ladder/PREREGISTRATION.md),
tag `v2-prereg`) — and traces how the binding advantage **Δ = success(binding) − success(advisory)**
moves along it. Same frozen corpus, same D18 bare-code presentation, temp 0, cap 8; **87 test
tasks × 7 rungs × 2 modes = 1218 episodes**, all committed, 0 errors, regenerated by one
deterministic command ([`v2_ladder/analysis/analyze_v2.py`](v2_ladder/analysis/analyze_v2.py) →
[`results.md`](v2_ladder/analysis/results.md)).

**The finding is a *capability window*, not a monotone trend.** Binding does not help more the
weaker the model. It helps in a **middle band** and fails at *both* ends: it does nothing for a
model already at ceiling (GPT-4.1), and it **actively hurts** the weakest model (Llama-3.2-3B),
which is too weak for forced iteration to rescue. The pre-registered monotone prediction — "Δ
decreases with capability rank," a one-sided Spearman expected positive — is **not confirmed**
(rho = −0.13, exact 7!-permutation p = 0.62), precisely because the weak end reverses.

**The curve — Δ by capability rank (1 = strongest), with exact task-paired McNemar:**

| rank | model | advisory | binding | Δ (pp) | McNemar (b,c) | exact p |
|---|---|---|---|---|---|---|
| 1 | GPT-4.1 (strong anchor) | 87/87 | 87/87 | +0.0 | (0,0) | 1 |
| 2 | Gemini-2.5-Flash-Lite | 79/87 | 87/87 | +9.2 | (0,8) | 0.0078 |
| 3 | GPT-4o-mini (weak anchor) | 79/87 | 87/87 | +9.2 | (0,8) | 0.0078 |
| 4 | Claude-3-Haiku | 72/87 | 82/87 | +11.5 | (2,12) | 0.013 |
| 5 | Qwen2.5-7B | 71/87 | 84/87 | **+14.9** | (0,13) | **0.00024** |
| 6 | Llama-3.1-8B | 80/87 | 82/87 | +2.3 | (3,5) | 0.73 |
| 7 | Llama-3.2-3B (weakest) | 66/87 | 63/87 | **−3.4** | (9,6) | 0.61 |

```
Δ (pp), strongest→weakest:
rank1 GPT-4.1              +0.0  |
rank2 Gemini-2.5-flash-lt  +9.2  |#####
rank3 GPT-4o-mini          +9.2  |#####
rank4 Claude-3-Haiku      +11.5  |######      <- payoff zone (McNemar-significant)
rank5 Qwen2.5-7B          +14.9  |#######
rank6 Llama-3.1-8B         +2.3  |#
rank7 Llama-3.2-3B         -3.4  ##|           <- too weak to rescue: binding HURTS
                               ^ zero
```

Both v1 anchors land where Experiment 1 put them — **GPT-4o-mini Δ = +9.2 pp** (identical to v1)
and **GPT-4.1 Δ = +0.0** — a clean replication inside the larger design. The payoff is the
**rung 3–5 band** (Qwen2.5-7B, Claude-3-Haiku, GPT-4o-mini/Gemini): capable enough to write a
plausible-but-wrong answer and false-DONE it, capable enough that forced iteration then repairs
it — Qwen2.5-7B is the peak at +14.9 pp (McNemar p = 0.00024, 12 forced repairs). The write-up is
[`v2_ladder/writeup/post_v2.md`](v2_ladder/writeup/post_v2.md).

**Deflations (read these next to the curve, not in a footnote).**
- **Prediction (i) — "binding never hurts" — is DISCONFIRMED.** At Llama-3.2-3B binding is
  *3.4 pp worse* than advisory (63 vs 66 solved): 9 tasks it solved in advisory it *lost* under
  binding (all ending `escalated`/`step_cap`), against 6 it gained. A model that never converges
  spends the whole cap-8 loop failing; forcing it to keep going is not free. "Binding is weakly
  dominant" was true across two points in v1; it is **false** across the ladder.
- **Two of the 14 cells were produced by a recovery runner.** `rung2 Llama-3.1-8B advisory` and
  `rung3 Qwen2.5-7B binding` wedged mid-run on slow-trickle OpenRouter connections that evade a
  socket timeout; they were re-run to completion with a SIGALRM hard per-episode deadline
  (`v2_ladder/runs/run_one_cell.py`) after a live probe confirmed the provider was healthy. All
  1218 logs are byte-schema identical and the two cells carry identical provenance fields — but
  the interruption is on the record (EXPERIMENT_LOG V2-P4.1), not hidden.
- **One corpus, one regime.** Experiment 2 reuses the *same* 97-task corpus and the *same* D18
  bare-code presentation as v1 — it varies *capability*, and nothing else. So the capability-window
  shape is established for these buggy-Python-repair tasks under docstring-withheld presentation;
  whether the window sits at the same place for other task families or other presentations is
  untested here. The top rung is also single-provider (GPT-4.1), a limitation recorded at
  registration.

---

## Experiment 3 — the composition window (the window that didn't slide)

Experiment 2 found the binding advantage is a **capability window** at *fixed* task difficulty
(k ≈ 0, one bug per task). **Experiment 3 turns the other knob — task difficulty via bug
composition** — to ask whether that window is a property of the *model* or of the *model–task
pair*. If it is the pair, then raising k (the number of simultaneous, independent bugs) should
make the window **slide**: models that were at the ceiling at k ≈ 0 should fall into the
false-claiming regime and start being helped by binding. Two frozen tiers — **k1 = 2 bugs** (60
test tasks), **k2 = 3 bugs** (48 test tasks) — each task exactly k+1 verbatim v1 mutations
composed on distinct lines of one v1 seed. Same D18 bare-code presentation, temp 0, cap 8; 6
models (weakest→strongest: Llama-3.1-8B, Qwen2.5-7B, Claude-3-Haiku, GPT-4o-mini,
Gemini-2.5-Flash-Lite, GPT-4.1) × 2 modes × (60 + 48) = **1,296 episodes**, all committed, 0
errors, regenerated by one deterministic command
([`v3_window/analysis/analyze_v3.py`](v3_window/analysis/analyze_v3.py) →
[`results.md`](v3_window/analysis/results.md)). Predictions were locked before the first paid
call ([`v3_window/PREREGISTRATION.md`](v3_window/PREREGISTRATION.md), tag `v3-prereg`). The k0
column is **not re-run** — it is Experiment 2's frozen test data (all six models were v2 rungs),
cited by v2's committed manifests.

**The finding, interaction-first: composition *widens and deepens* the window in place, but the
window does not *slide* up the capability axis.** Every window model gains *more* from binding as
bugs compose — the Δ roughly **doubles** from k0 to k1 and stays large at k2, all four window
models Δ > 0 at both tiers with McNemar p ≤ 0.004 (**P1 confirmed**). But the ceiling model
GPT-4.1 **never enters the false-claiming regime**: 0 advisory false-DONEs and Δ = 0 at *every*
k. The window did not slide up to it. Composition is an interaction that amplifies binding for
models *already inside* the window; it does not drag stronger models in.

**The Δ-vs-k matrix — Δ = success(binding) − success(advisory), pp, per model across k0 → k1 → k2:**

| model | Δ@k0 | Δ@k1 | Δ@k2 | advisory false-DONE rate k0→k1→k2 |
|---|---|---|---|---|
| GPT-4.1 (top anchor) | +0.0 | +0.0 | +0.0 | 0% → 0% → 0% |
| Gemini-2.5-Flash-Lite | +9.2 | +23.3 | +22.9 | 9.2% → 23.3% → 22.9% |
| GPT-4o-mini | +9.2 | +23.3 | +22.9 | 9.2% → 23.3% → 22.9% |
| Claude-3-Haiku | +11.5 | +26.7 | +25.0 | 17.2% → 31.7% → 31.2% |
| Qwen2.5-7B | +14.9 | **+31.7** | +22.9 | 18.4% → **40.0%** → 33.3% |
| Llama-3.1-8B (bottom anchor) | +2.3 | +10.0 | +2.1 | 4.6% → 11.7% → 10.4% |

```
Δ (binding − advisory), pp — one row per model, k0 → k1 → k2:
GPT-4.1                k0  +0.0   k1  +0.0   k2  +0.0     <- ceiling at every k: window never reaches it
Gemini-2.5-flash-lite  k0  +9.2   k1 +23.3   k2 +22.9
GPT-4o-mini            k0  +9.2   k1 +23.3   k2 +22.9
Claude-3-Haiku         k0 +11.5   k1 +26.7   k2 +25.0
Qwen2.5-7B             k0 +14.9   k1 +31.7   k2 +22.9     <- peak; window deepens in place at k1
Llama-3.1-8B           k0  +2.3   k1 +10.0   k2  +2.1
```

The mediator moves with the effect: as bugs compose, each window model's advisory **false-DONE
rate** rises (Qwen 18%→40%, Claude 17%→32%, the two anchors 9%→23%) — more simultaneous bugs mean
more chances to leave one unfixed and confidently declare done — and binding converts those
false-DONEs into forced repairs (a FAILED verdict, a changed submission, then PASS: nearly every
one of binding's wins is a *forced* repair, not a sampling fluke). The window's mechanism is
intact and stronger; it just stays anchored to the same middle band of models.

**Deflations (read these next to the matrix, not in a footnote).**
- **The headline prediction (P2) — "the window slides; GPT-4.1 enters the false-claiming regime by
  k2" — is DISCONFIRMED.** GPT-4.1's advisory false-DONE count is **0 at k0 and still 0 at k2**
  (independently re-derived from raw logs), its Δ is **+0.0 at every tier**, and it solves 60/60
  and 48/48 in both modes. Three simultaneous bugs did not make the strongest model false-claim.
  P2 was staked deliberately *against* the dev glimpse (which already showed GPT-4.1 clean at k2)
  — registering it anyway, and reporting it disconfirmed, is the point of pre-registration.
- **The deepening is at k1, then plateaus.** Δ roughly doubles k0→k1 but does **not** keep growing
  k1→k2 — most window models dip slightly (Qwen +31.7→+22.9), tracking a matching dip in
  false-DONE rate, because at 3 bugs both arms lose ground. The window deepened once and held; it
  did not widen without limit.
- **P3 (escalation-attributed losses) is small and only weakly directional.** Across all 12 cells
  just **4** b-direction discordants (advisory✓/binding✗) ended `escalated`; **3 of the 4** are at
  the bottom-edge anchor Llama-3.1-8B (k1 1 → k2 2), so the concentration-and-growth pattern is
  present but rests on single-digit counts.
- **P4 (cost at ceiling) is CONFIRMED**, on the one at-ceiling model: GPT-4.1 binding is cheaper
  than advisory at both tiers ($0.078 ≤ $0.112 at k1; $0.067 ≤ $0.092 at k2).
- **P5 (exploratory) — a slight rightward peak shift.** The argmax-Δ model is Qwen at k0 and k1,
  then Claude-3-Haiku (one step stronger) at k2 — a weak shift toward stronger models, scored
  exploratory as registered, not a confirmatory result.

**Scope and limits.** One corpus and one presentation regime, as in v1/v2 (buggy-Python repair,
D18 docstrings stripped). Difficulty is composed from **verbatim v1 mutations** — each k-tier task
is k+1 real v1 bugs stacked on one seed, so tasks are **multi-label** (the bug-type breakdown
counts each constituent) and the difficulty axis is *bug count*, not novel bug families or longer
programs; whether the window slides under a different kind of harder task is untested here. Only
three k points (0, 1, 2) are measured, the top rung is a single provider (GPT-4.1), and the
publish-gate condition of the pre-registration was **waived by the courier** (deviation **V3-D1**,
verbatim "ya I waive the gate"; the timestamp-ordering half of the gate was still discharged —
`v3-prereg` precedes the first test episode). The write-up is
[`v3_window/writeup/post_v3.md`](v3_window/writeup/post_v3.md).

---

## Provenance note

> The harness and analysis were built with AI assistance under execution-verified
> acceptance gates: every phase advanced only on raw command output audited against
> EXPERIMENT_LOG.md, which records all deviations.

---

## Repository map

```
EXPERIMENT_LOG.md      append-only source of truth: one entry per step, raw output, all deviations (D1–D18)
README.md              this file
phase1_tasks/          the corpus
  seeds/               25 stdlib-pure seed functions + suites + validators
  generator/           mutation manifest, task generator, taxonomy, difficulty tagging, freeze-hash, dev/test split
  tasks/               97 frozen task_NNN/ dirs (buggy.py, reference.py, tests.py, meta.json) — IMMUTABLE
  validation/          split.json (10 dev / 87 test)
phase2_checker/        checker.py (run_checks + static guard) + test_checker.py
phase3_advisory/       advisory harness.py, providers.py (Mock + OpenAI client), config.json, fixtures, tests
phase4_binding/        binding harness.py (imports advisory; 3 structural diffs), tests, acceptance episodes
phase5_runs/           run_pilot.py / run_full.py / report scripts, per-cell manifests, committed 348-episode logs
phase6_analysis/       analyze.py → results.md / results.json (hash-pinned, deterministic)
phase7_writeup/        post.md (plain-language write-up)
```

**Standing rules honored throughout:** `phase1_tasks/` is immutable (later-discovered
broken tasks are excluded and logged, never edited); the builder writes infrastructure
only and never solves a task or runs episodes by hand; the API key is never printed,
logged, or committed; staging is always explicit (never `git add -A`).
