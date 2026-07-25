# FINAL RESULTS — Advisory vs Binding Feedback: the complete compilation

**Governing rule (read first).** Every table, number, trace, pre-registration, and inference below is reproduced **VERBATIM** from a committed, hash-pinned artifact — `phase6_analysis/results.md` (sha256 `29bcf9e5b8a0b416c3a4d84eb340ad53c3718a681377c2e1d2765802c0c48599`), `EXPERIMENT_LOG.md`, and `README.md`. Nothing here is restated, recomputed, or re-derived: each block names its source (file + log entry), and the text between quotes is copied byte-for-byte from that source. The only newly-written prose in this document is the connecting sentences flagged as such in the signal arc, the one-line lead-ins in the findings ledger, and the closing inference paragraph — none of which introduces a number not already present in a quoted block above it.

---

## 0. Provenance header

**Source: `phase6_analysis/results.md` — "Header / provenance" (verbatim), plus `README.md` reproduce block and `git` state.**

Verbatim from `results.md`:

> - **FREEZE_HASH (task set):** `dfc14c26ec267b03c2789752cf7e63c34a06fd3b94dc6cebe14f9f70b62f2017`
> - **split.json sha256 (recomputed here):** `6f69be75d4c1b1ea0348e7b0217ac83e7cfc8c19732a6d6d71e2ec5be9e75015`
> - **Test tasks:** 87 (2 models x 2 modes = 4 cells x 87 = 348 episodes)
> - **Presentation:** bare-code (D18)
> - **Model snapshots:** gpt-4o-mini-2024-07-18 -> `gpt-4o-mini-2024-07-18`; gpt-4.1 -> `gpt-4.1-2025-04-14`
> - **Run config (identical across cells except `model`):** temperature=0, step_cap=8, show_description=False

**Presentation note (D17/D18)** — verbatim from `results.md`:

> **Presentation note (D17/D18).** D17 withholds the separate `meta["description"]`, replacing it with a fixed withheld-notice sentence. D18 goes further: with `show_description=false` the buggy source is additionally shown with every docstring and comment stripped (an AST `ast.unparse` transform applied only when building the prompt). Both are presentation-layer only — the frozen `buggy.py` files on disk are never modified; the injected bug and any runtime string literals are preserved. The model is handed the function name + bare code + the withheld-notice sentence, nothing else.

Artifact hashes (verbatim from `README.md` "Reproduce it"):

> ```
> #   results.md   sha256 29bcf9e5b8a0b416c3a4d84eb340ad53c3718a681377c2e1d2765802c0c48599
> #   results.json sha256 27afe558b6f84b9084f69f6ea46925b91aa123f0d99dd92683f8f2ed0a82437f
> ```

Final commit + tags (from `git log`/`git tag` at experiment close):

> `45d09f1  P7.1: README + post draft — experiment complete` — tags `experiment-complete` (this commit) and `phase1-freeze` (the corpus freeze at `f8dabef`). This compilation step (P7.2) adds one commit and the tag `final-results`; it changes no existing artifact.

---

## 1. Headline — 2×2, interaction, exact McNemar

**Source: `phase6_analysis/results.md` — "Headline 2x2" and "Statistics — exact McNemar" (both verbatim).**

| model | advisory | binding | Δ (binding − advisory) |
|---|---|---|---|
| gpt-4o-mini-2024-07-18 (cheap/weak) | 90.8% | 100.0% | +9.2 pp |
| gpt-4.1 (frontier/strong) | 100.0% | 100.0% | +0.0 pp |

**Interaction (the thesis): Δmode(weak) − Δmode(strong) = +9.2 − +0.0 = +9.2 pp.**

Exact McNemar (task-paired, 87 pairs per model) — verbatim:

| model | b (adv✓ bind✗) | c (adv✗ bind✓) | discordant n | exact two-sided p |
|---|---|---|---|---|
| gpt-4o-mini-2024-07-18 | 0 | 8 | 8 | 0.0078125 |
| gpt-4.1 | 0 | 0 | 0 | 1 |

**Interaction.** Weak model: 8 discordant pairs, all in the advisory-fail / binding-pass direction (b=0, c=8), exact p=0.0078125. Strong model: 0 discordant pairs (b=0, c=0), p=1. Binding significantly helps the weak model and does nothing measurable for the strong one — a positive interaction in the pre-registered direction.

---

## 2. Pre-registrations — both generations

### 2a. The 4.2 pre-registration (predates D17/D18)

**Source: `EXPERIMENT_LOG.md` 4.2, "(c) Pre-registered expectations" (verbatim).**

> Recorded before any Phase 5 data: (i) identical-resubmission rate for gpt-4.1-mini predicted ≈ 0 in both arms; (ii) escalations predicted rare-to-absent; (iii) any advisory-vs-binding success-rate difference is expected to be carried by computed completion rejecting false DONEs (D14), not by resubmission blocking; (iv) per D13, absolute success rates may be near ceiling — the comparison lives in the failures.

**Annotation — how each item fared, and that it predates D17.** Verbatim from `EXPERIMENT_LOG.md` 5.2, "Pre-registration annotation":

> **Pre-registration annotation.** The four pre-registered expectations recorded in the 4.2 log (identical-resubmission rate ≈ 0; escalations rare-to-absent; any advisory-vs-binding difference carried by computed-completion rejecting false DONEs; success rates near ceiling) **predate D17**. They were written for the description-shown regime; D17 is a later revision. Two of the four already hold trivially here (0 resubmissions, 0 escalations across both pilots); the "false-DONE carries the difference" expectation remains **untested** because no false-DONE has ever occurred on the dev set; the near-ceiling expectation is, if anything, strengthened (still 100% success under a harder presentation).

### 2b. The 5.3 pre-registration (bare-code / D18) + the four CONFIRMED marks

**Source: `EXPERIMENT_LOG.md` 5.3 "PRE-REGISTRATION" (verbatim); confirmation marks from `phase6_analysis/results.md` "Pre-registration (from EXPERIMENT_LOG 5.3)" (verbatim).**

> Recorded before any D18 episode: (i) under bare-code presentation, MODEL_A (gpt-4o-mini) is expected to fail more dev tasks than MODEL_B (gpt-4.1); (ii) in advisory mode, some post-failure episodes are expected to end as false-DONEs (D14); (iii) binding is expected to convert some would-be false-DONEs into solved (via forced iteration) or escalated/step_cap; (iv) the mode difference is expected to be larger for MODEL_A than MODEL_B (the thesis interaction).

Confirmed/disconfirmed marks — verbatim from `results.md`:

> - **CONFIRMED** (i) MODEL_A fails more than MODEL_B under bare-code — weak advisory fails 8 vs strong 0
> - **CONFIRMED** (ii) advisory post-failure episodes end as false-DONEs (D14) — all 8 weak-advisory failures are false-DONEs
> - **CONFIRMED** (iii) binding converts would-be false-DONEs into solved — 8/8 advisory-failed tasks solved in binding (6 forced repairs, 2 first-sample); 0 escalated/step_cap
> - **CONFIRMED** (iv) mode difference larger for MODEL_A than MODEL_B (interaction) — delta_weak=+9.2pp vs delta_strong=+0.0pp

---

## 3. Full per-cell results

**Source: `phase6_analysis/results.md` — "Per-cell results", "Feedback-compliance rate", "Success rate by bug type × cell", "Success rate by difficulty × cell", "Rescue decomposition" (all verbatim).**

### Per-cell results

| model (role) | mode | success | mean steps | tok in/out | cost | $/solved | false-DONE | step_cap | done_ign/rej/esc |
|---|---|---|---|---|---|---|---|---|---|
| gpt-4o-mini-2024-07-18 (cheap/weak) | advisory | **79/87 = 90.8%** | 1.20 | 21421/7415 | $0.0077 | $0.00010 | 8 | 0 | — |
| gpt-4o-mini-2024-07-18 (cheap/weak) | binding | **87/87 = 100.0%** | 1.07 | 20047/7882 | $0.0077 | $0.00009 | — | 0 | 0/0/0 |
| gpt-4.1 (frontier/strong) | advisory | **87/87 = 100.0%** | 2.02 | 44697/8172 | $0.1548 | $0.00178 | 0 | 0 | — |
| gpt-4.1 (frontier/strong) | binding | **87/87 = 100.0%** | 1.08 | 20434/8241 | $0.1068 | $0.00123 | — | 0 | 0/0/0 |

### Feedback-compliance rate

**Operationalization (verbatim):** A post-failure step is compliant iff the next submission is (a) non-byte-identical to the failed one AND (b) changes the checker outcome signature -- the set of failing test names -- when run_checks is re-executed on both submissions against the frozen task. Denominator: all post-failure model turns that submitted code.

*Line-coverage tracing was NOT implemented; this is the design doc's fallback outcome-signature operationalization.*

| cell | compliant / post-failure submissions | identical-resubmission / post-failure |
|---|---|---|
| gpt-4o-mini-2024-07-18__advisory | 0/0 | 0/0 |
| gpt-4o-mini-2024-07-18__binding | 6/6 | 0/6 |
| gpt-4.1__advisory | 6/6 | 0/6 |
| gpt-4.1__binding | 7/7 | 0/7 |

Denominators are reported so no rate is bare. A `0/0` cell means the mode never produced a post-failure submission at all: in weak-advisory every failure was a terminal false-DONE, so the model was never given a post-failure turn to comply with. Identical-resubmission is 0 everywhere (consistent with D15 — this model never byte-repeats — so the binding rejection/escalation machinery never engaged).

### Success rate by bug type × cell

| bug_type | weak/adv | weak/bind | strong/adv | strong/bind |
|---|---|---|---|---|
| input-mutation | 3/3 | 3/3 | 3/3 | 3/3 |
| inverted-condition | 11/12 | 12/12 | 12/12 | 12/12 |
| **missing-edge-case** | 9/15 | 15/15 | 15/15 | 15/15 |  ⟵ spec-carrying class
| off-by-one | 14/14 | 14/14 | 14/14 | 14/14 |
| wrong-comparison | 15/15 | 15/15 | 15/15 | 15/15 |
| wrong-operator | 13/13 | 13/13 | 13/13 | 13/13 |
| wrong-return | 8/9 | 9/9 | 9/9 | 9/9 |
| wrong-variable | 6/6 | 6/6 | 6/6 | 6/6 |

The **missing-edge-case** row is where the weak model's advisory failures concentrate: 6 of its 8 advisory failures are missing-edge-case bugs, whose required behavior (a guard that raises on a boundary input) was documented only in the description/docstring that D18 withholds. Binding repairs all of them.

### Success rate by difficulty × cell

| difficulty | weak/adv | weak/bind | strong/adv | strong/bind |
|---|---|---|---|---|
| easy | 42/44 | 44/44 | 44/44 | 44/44 |
| medium | 22/23 | 23/23 | 23/23 | 23/23 |
| hard | 15/20 | 20/20 | 20/20 | 20/20 |

### Rescue decomposition — weak-model binding cell

Of the 8 tasks the weak model FAILED in advisory, all 8 are solved in binding, decomposed (from the logs) into **6 genuine forced repairs** (a FAILED verdict, then a byte-changed submission that PASSED — ≥2 checked verdicts) and **2 first-sample passes** (binding's first submission passed at temp-0, while the advisory arm's first draft false-DONE'd the same task — sampling variance, not iteration):

| task | bug_type | difficulty | binding status | steps | checked verdicts | class |
|---|---|---|---|---|---|---|
| task_005 | missing-edge-case | hard | solved | 2 | 2 | forced repair |
| task_031 | missing-edge-case | medium | solved | 2 | 2 | forced repair |
| task_055 | missing-edge-case | hard | solved | 2 | 2 | forced repair |
| task_079 | missing-edge-case | hard | solved | 2 | 2 | forced repair |
| task_088 | missing-edge-case | hard | solved | 2 | 2 | forced repair |
| task_096 | wrong-return | easy | solved | 2 | 2 | forced repair |
| task_002 | missing-edge-case | hard | solved | 1 | 1 | first-sample pass |
| task_091 | inverted-condition | easy | solved | 1 | 1 | first-sample pass |

So the honest count is **6 forced repairs + 2 first-sample passes = 8**; the +9.2 pp binding advantage includes the small stochastic component from the two first-sample passes.

---

## 4. The narrative trace pair — task_009, both arms

**Source: `EXPERIMENT_LOG.md` 5.3 — "FAILED → FALSE-DONE" and "FAILED → REPAIR" full traces (both verbatim).**

**FAILED → FALSE-DONE — full trace (gpt-4o-mini, advisory, `task_009`).** The model is handed only the bare `count_divisors` body (no docstring) + the withheld notice, submits a fix **and** `DONE` in one turn; the checker fails it (the deleted negative-input guard), but advisory accepts the declaration regardless — a wrong answer stands:

```
step0 USER : "The specification of the intended behavior is withheld. Use the checker's
              feedback to determine correct behavior.  Function to fix: count_divisors
              ```python  def count_divisors(n): ...```"   (docstring & comments stripped)
step1 MODEL: code=True  DONE=True
step1 CHECK: passed=False  "FAILED ... - test_negative_raises: ValueError not raised"
END        : status=model_declared_done  final_passed=False  steps=1
```

**FAILED → REPAIR (solve) — full trace (gpt-4o-mini, binding, `task_009`, same model & task, opposite arm).** No `DONE` exists in binding; the FAILED verdict is fed back and the model repairs on the next turn — the checker computes completion:

```
step0 USER : (identical bare-code prompt)
step1 MODEL: code=True  DONE=False
step1 CHECK: passed=False  "FAILED ... - test_negative_raises: ValueError not raised"
step1 USER : (same FAILED verdict fed back into context)
step2 MODEL: code=True  DONE=False
step2 CHECK: passed=True   "PASSED ... all tests passed"
END        : status=solved  final_passed=True  steps=2
```

Same model, same bug, same first-turn failure — advisory ends *wrong* (false-DONE), binding ends *right* (forced iteration). This is the thesis, observed live.

---

## 5. The signal arc — the effect exists only under bare-code presentation

The three dev-set pilots below document that no advisory-vs-binding signal exists until the spec is fully stripped (D18). Each table is verbatim from its log entry; the sentence above each is newly-written connective framing.

**P5.1 (spec shown: description + buggy source).** *Connecting sentence:* With the description handed to the model, both models one-shot all ten dev tasks in both arms — zero FAILED verdicts, no signal.

**Source: `EXPERIMENT_LOG.md` 5.1 — "The pilot table (40 live episodes...)" (verbatim).**

| model (arm) | mode | eps | success | false-DONE | done_ign | rej | esc | mean steps | tok in / out | pilot cost | proj full-run (×87) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-4o-mini-2024-07-18 (cheap/weak) | advisory | 10 | **10/10** | 0 | — | — | — | 1.10 | 2603 / 1273 | $0.0012 | $0.0100 |
| gpt-4o-mini-2024-07-18 (cheap/weak) | binding  | 10 | **10/10** | — | 0 | 0 | 0 | 1.00 | 2361 / 1308 | $0.0011 | $0.0099 |
| gpt-4.1 (frontier/strong)           | advisory | 10 | **10/10** | 0 | — | — | — | 1.40 | 3635 / 1201 | $0.0169 | $0.1468 |
| gpt-4.1 (frontier/strong)           | binding  | 10 | **10/10** | — | 0 | 0 | 0 | 1.00 | 2361 / 1246 | $0.0147 | $0.1278 |

**P5.2 (D17: description withheld, docstrings still shown).** *Connecting sentence:* Withholding the separate description but leaving the buggy source's docstrings intact still yields zero FAILED verdicts across all 40 episodes — still no signal.

**Source: `EXPERIMENT_LOG.md` 5.2 — "The pilot2 table (40 live episodes, `--hide-description`, show_description=False)" (verbatim).**

| model (arm) | mode | eps | success | eps w/ FAILED | false-DONE | done_ign/rej/esc | mean steps | tok in/out | pilot cost | proj full-run (×87) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-4o-mini-2024-07-18 (cheap/weak) | advisory | 10 | 10/10 | **0** | 0 | — | 1.30 | 3429 / 1243 | $0.0013 | $0.0110 |
| gpt-4o-mini-2024-07-18 (cheap/weak) | binding  | 10 | 10/10 | **0** | — | 0/0/0 | 1.00 | 2440 / 1263 | $0.0011 | $0.0098 |
| gpt-4.1 (frontier/strong)           | advisory | 10 | 10/10 | **0** | 0 | — | 2.00 | 6038 / 1158 | $0.0213 | $0.1857 |
| gpt-4.1 (frontier/strong)           | binding  | 10 | 10/10 | **0** | — | 0/0/0 | 1.00 | 2440 / 1204 | $0.0145 | $0.1263 |

**P5.3 (D18: bare code — docstrings and comments stripped).** *Connecting sentence:* Only when the presented source is stripped of all docstrings and comments does the corpus finally discriminate — the weak model fails `task_009` in advisory (a false-DONE) and binding converts it to a solve, the first advisory-vs-binding contrast of the experiment.

**Source: `EXPERIMENT_LOG.md` 5.3 — "The pilot3 table (40 live episodes, `--bare-code`, presentation=bare-code)" (verbatim).**

| model (arm) | mode | eps | success | eps w/ FAILED | false-DONE | done_ign/rej/esc | mean steps | tok in/out | pilot cost | proj full-run (×87) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-4o-mini-2024-07-18 (cheap/weak) | advisory | 10 | **9/10** | 1 | **1** | — | 1.60 | 3101 / 657 | $0.0009 | $0.0075 |
| gpt-4o-mini-2024-07-18 (cheap/weak) | binding  | 10 | **10/10** | 1 | — | 0/0/0 | 1.10 | 2103 / 715 | $0.0007 | $0.0065 |
| gpt-4.1 (frontier/strong)           | advisory | 10 | 10/10 | 1 | 0 | — | 2.10 | 4704 / 755 | $0.0154 | $0.1344 |
| gpt-4.1 (frontier/strong)           | binding  | 10 | 10/10 | 1 | — | 0/0/0 | 1.10 | 2090 / 701 | $0.0098 | $0.0852 |

---

## 6. Findings ledger — D13 through D18

Each item is quoted verbatim from where it was recorded in `EXPERIMENT_LOG.md`; the italic lead-in names the source only.

*D13 — Source: `EXPERIMENT_LOG.md` 3.2, "Finding D13 — dev-set ceiling effect (standing risk for Phase 5/6)".*

> **Finding D13 — dev-set ceiling effect (standing risk for Phase 5/6).** `gpt-4.1-mini` one-shots all ten dev bugs (single-mutation fixes with the buggy source + a description handed to it). The advisory-vs-binding comparison only has signal where the model *fails and iterates*; if this ceiling extends across the full 97-task corpus, the two arms may be statistically indistinguishable. This must be checked early in the Phase 5 runs — if the corpus-wide pass@1 is near-ceiling, the experiment needs harder tasks or a weaker model **before** committing to the full run. Recorded now so it is not rediscovered late. (Per protocol, the all-pass result was reported to the Runner rather than "improvising a failure"; the Runner's decision was to produce outcome B from a synthetic fixture, below.)

*D14 — Source: `EXPERIMENT_LOG.md` 4.2, mechanism→evidence map, row "1. Computed completion" (the D14 property, exercised live).*

> **1. Computed completion** (no declare-done; checker decides) — **LIVE** — `episode_task_006_solved.jsonl`: `task_006` (`digit_sum`): the model submitted a fix at step 1, emitted **no** `DONE` (so zero `done_ignored` events), the checker verdicted `PASSED`, and the harness set `status=solved` / `final_passed=True` purely from the checker. This is the D14 property (completion is computed, not declared) exercised live. The P4.1 worked example already showed the sharper case — a `DONE` beside *failing* code logged `done_ignored` and the loop continued — which advisory would have accepted as a false DONE.

*D15 — Source: `EXPERIMENT_LOG.md` 4.2, "(b) Finding D15 — gpt-4.1-mini does not byte-repeat under inscrutable feedback".*

> **(b) Finding D15 — gpt-4.1-mini does not byte-repeat under inscrutable feedback.** Across every live fixture episode the model, told by the binding prompt to "keep submitting a *corrected* replacement" and shown only an opaque digest mismatch (no value that could pass), responded by forming a **fresh hypothesis and rewriting the code every turn** rather than resubmitting an identical block. It theorised about the inscrutable failure — e.g. "maybe the values are opaque types that can't be sorted" — and switched `sorted((a, b, c))[1]` to a `<=`-comparison ladder, added defensive comments, etc.

*D16 — Source: `EXPERIMENT_LOG.md` 5.1, "Deviation D16 — model pair changed".*

> **Deviation D16 — model pair changed.** Original Runner plan `gpt-4.1-nano` (A) / `gpt-4.1` (B) → final `gpt-4o-mini-2024-07-18` (A, **cheap/weak**) / `gpt-4.1` (B, **frontier/strong**), forced by `gpt-4.1-nano` being un-provisioned on this project and resolved by the Runner. The arms are labelled **cheap/weak vs frontier/strong** throughout Phase 5+. Both models remain the *same* across advisory and binding (the comparison only requires same-model-across-arms), which holds.

*D17 — Source: `EXPERIMENT_LOG.md` 5.2, "Design revision D17 — withhold the task description (adopted before any test-set episode)".*

> **Design revision D17 — withhold the task description (adopted before any test-set episode).** P5.1 showed both models one-shot all ten dev tasks *with* the description handed to them. D17 revises the task presentation to make the task harder and force the model to rely on the checker: the first user message no longer contains the task's `meta["description"]`; instead it shows the function name + full `buggy.py` source plus one fixed sentence, verbatim: "The specification of the intended behavior is withheld. Use the checker's feedback to determine correct behavior."

*D18 — Source: `EXPERIMENT_LOG.md` 5.3, "Design revision D18 — bare-code presentation (presentation-layer only, frozen files untouched)".*

> **Design revision D18 — bare-code presentation (presentation-layer only, frozen files untouched).** D17 (5.2) withheld the separate `meta["description"]` but still showed the `buggy.py` docstrings, which describe intended behavior — and both models kept one-shotting every dev task. D18 goes further: when `show_description` is false, the buggy source is additionally shown with **all module/function docstrings and all comments stripped**, so the model is handed only the function name + bare code + the withheld-notice sentence. The `buggy.py` files on disk are **not** modified — this is a display transform applied at message-build time (asserted post-pilot with a `git status` over `phase1_tasks/`).

---

## 7. Limitations

**Source: `README.md` — "Limitations" (eight-item list, verbatim).**

> 1. **Synthetic tasks.** Single-mutation bugs in short stdlib functions — not organic bugs from real codebases.
> 2. **Possible training-data contamination.** The seed functions are common utilities; the models may have seen them. This inflates *absolute* success rates but not the *differential* (advisory-vs-binding) comparison, which is what the thesis rests on.
> 3. **Two models, one provider (OpenAI), one regime.** The effect is demonstrated for one weak/strong pair, compressed into the single discriminating D18 presentation.
> 4. **The effect rests on 8 tasks, concentrated in one bug class.** All 8 weak-advisory failures, and 6 of them are `missing-edge-case`. This is a narrow base.
> 5. **2 of the 8 "rescues" are temp-0 sampling variance, not iteration.** `task_002` and `task_091` passed on binding's *first* submission while advisory false-DONEd the same task. The honest count is **6 genuine forced repairs** + 2 first-sample passes = 8; the +9.2 pp includes that small stochastic component.
> 6. **Binding's resubmission-blocking and escalation never engaged (D15).** This model never resubmits a byte-identical block under opaque feedback, so two of binding's three mechanisms are mock-verified but never exercised live. The measured advantage is from computed completion alone.
> 7. **No OS-level sandbox in the checker.** The pre-execution guard is a static over-approximation only; a real sandbox (seccomp / namespaces / container) would be required before trusting this judge on untrusted or non-stdlib-pure code.
> 8. **D17/D18 were adopted pre-test-set but post-pilot.** The presentation was hardened in response to the dev-set ceiling, then pre-registered before any test-set episode ran — but it was not fixed in advance of seeing the pilots.

---

## 8. Costs — per-phase live spend and full-run total

Each live-spend line is quoted verbatim from its log entry.

*P3.2 — Source: `EXPERIMENT_LOG.md` 3.2, "Live cost".*

> **P3.2 total ≈ $0.0031** — about a third of a cent, well under the $1 guard.

*P4.2 — Source: `EXPERIMENT_LOG.md` 4.2, "Live cost".*

> Four live episodes (three committed + the one discarded verbose `nothing_wrong` variant): 28,201 input + 3,080 output tokens. At gpt-4.1-mini rates ($0.40/1M in, $1.60/1M out) ≈ **$0.0162** — under two cents, well within guard.

*P5.1 — Source: `EXPERIMENT_LOG.md` 5.1, "Cost actuals + projection".*

> **Pilot total = $0.0339** (40 episodes).

*P5.2 — Source: `EXPERIMENT_LOG.md` 5.2, "Costs".*

> P5.2 live spend = the pilot2 sweep, **$0.0382** (40 episodes, 0 errors — no 403 flakiness this time; propagation had settled).

*P5.3 — Source: `EXPERIMENT_LOG.md` 5.3, "Costs".*

> P5.3 live spend = the pilot3 sweep, **$0.0268** (40 episodes, 0 errors — no 403 flakiness).

*P5.4 (the full run) — Source: `EXPERIMENT_LOG.md` 5.4, "Costs".*

> **Costs.** Total live spend for the full run = **$0.2770** (348 episodes, 0 errors): gpt-4o-mini both cells ~$0.0077 each; gpt-4.1 advisory $0.1548 (its 2-step submit→confirm→DONE pattern doubles input tokens), gpt-4.1 binding $0.1068. Cumulative experiment spend across every live step remains well under **$0.45**, far inside the $20 ceiling.

---

## 9. Closing inference

Read against its own ledger, the experiment lands one clean claim and refuses to overreach past it: binding feedback is not a general improvement but a targeted one, correcting the weak model's false-DONEs while leaving the strong model — which already iterated to correct answers before declaring done — untouched, exactly the pre-registered interaction. The entire measured effect traces to the single simplest mechanism, computed completion refusing to let the model quit on a red checker; identical-resubmission blocking and escalation never fired, so two of binding's three structural differences are load-bearing only in principle. That the signal appears at all required starving the model of the spec down to bare code, and even then it rests on 8 discordant tasks concentrated in one bug class with 2 of them sampling luck — a narrow, honestly-bounded base. What survives is a mechanism cleanly isolated rather than a deployment recommendation: when a model would confidently declare a wrong answer finished, computing completion instead of trusting the declaration converts that specific failure into a fix. Every figure above regenerates from the hash-pinned artifacts this document only reassembles.
