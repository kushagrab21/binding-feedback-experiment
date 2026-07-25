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
