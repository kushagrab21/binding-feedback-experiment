# The capability window for completion-gating

*Experiment 2 of the binding-feedback study. Plain-language write-up; every number traces to
`v2_ladder/analysis/results.md`, regenerated deterministically from 1218 committed episodes.*

## The question we carried forward

Experiment 1 found something clean: if you stop letting an LLM agent declare *itself* finished —
and instead let a checker decide "done," ignoring the model's own `DONE` — a **weak** model
solves more tasks (+9.2 points) and a **strong** model is unchanged (+0.0). We called it
*binding* feedback, and the effect was an *interaction*: it helped the weak, not the strong.

But two points make a line, and a line is a story you can over-tell. "Binding helps weaker
models" invites the obvious extrapolation: the weaker the model, the more it should help. If
that were true, completion-gating would be a general safety net — bolt it on, and the frailer
the model, the more you'd gain.

So we built a ladder. Seven models across five providers, ranked before we ran anything by
published benchmarks (LMArena Elo and MMLU), from Llama-3.2-3B at the bottom to GPT-4.1 at the
top, with the two Experiment-1 anchors sitting inside it. Same tasks, same bare-code
presentation, same temperature and step cap. We pre-registered the monotone prediction — Δ
should *decrease* with capability rank, i.e. grow as models get weaker — and five specific
claims, and locked them with a git tag before the first paid call.

## What the ladder actually shows

The extrapolation is **wrong**, and wrong in an interesting way.

```
Δ (binding − advisory), points, strongest → weakest:
GPT-4.1              +0.0
Gemini-2.5-flash-lt  +9.2
GPT-4o-mini          +9.2
Claude-3-Haiku      +11.5      \
Qwen2.5-7B          +14.9       > the payoff zone
                                /
Llama-3.1-8B         +2.3
Llama-3.2-3B         -3.4       <- binding makes it WORSE
```

Binding help is not monotone in weakness. It rises to a **peak in the middle of the ladder**
(Qwen2.5-7B, +14.9 points, the single most-helped model in either experiment) and then **falls
off a cliff at the bottom**, going *negative* at the weakest rung. The pre-registered
one-sided Spearman for "Δ decreases with capability rank" comes out at rho = −0.13 (exact
7!-permutation p = 0.62) — not just unconfirmed but slightly the wrong sign, because the weak
end reverses the trend. Prediction (i), "binding never hurts," is disconfirmed outright: at
Llama-3.2-3B binding is **3.4 points worse** than advisory.

This is the *capability window*. Completion-gating pays off only for models inside a band, and
the band has both a ceiling and a floor.

## Rung 1, the cautionary tale: too weak to rescue

Llama-3.2-3B is the model binding was supposed to help most, and it's the one binding hurt.

Look at what the model does in advisory mode: **30 of its 87 episodes hit the step cap** — it
never converges and never even declares itself done; it just keeps emitting non-passing code
until the loop runs out. It is not confidently wrong (only **1** false-DONE all run); it is
*diffusely* wrong. Advisory still scrapes 66/87, because on the tasks it *can* do, its first or
second draft happens to pass.

Now bind it. Binding's whole mechanism is "you may not stop while the checker is red — keep
submitting." For a model that had a good draft and quit too early, that's a rescue. For a model
that is thrashing, it's just… more thrashing, and now the harness's other machinery bites:
**nine tasks that advisory solved, binding lost** — every one ending `escalated` (it repeated a
failed answer three times) or `step_cap` (it burned all eight turns still failing). Net, binding
drops it to 63/87. Forcing a model to keep going only helps if "keep going" leads somewhere; for
a model too weak to improve on feedback, the extra turns are extra chances to escalate or stall,
and the paired McNemar (b=9, c=6) tilts *against* binding.

The registered exploratory prediction (v) called this shape — "a model can be too weak to
rescue" — and it is observed, though not exactly by the mechanism we guessed (we expected
false-DONEs binding couldn't repair; what we got was diffuse step-capping and lost ground). We
score it as exploratory, as registered, and let the raw counts stand.

## Rungs 3–5, the payoff zone: strong enough to be wrong, strong enough to be fixed

The middle of the ladder is where completion-gating earns its keep, and the mechanism is exactly
Experiment 1's, now visible as a *band* instead of a point:

- **Qwen2.5-7B** (+14.9, McNemar p = 0.00024): 16 advisory false-DONEs — the most of any rung —
  and binding converts 13 of those failures into solves, **12 of them genuine forced repairs**
  (a FAILED verdict, a changed submission, then PASS).
- **Claude-3-Haiku** (+11.5, p = 0.013): 15 advisory false-DONEs, 12 rescued, 10 forced repairs.
- **GPT-4o-mini** (+9.2, p = 0.0078) and **Gemini-2.5-Flash-Lite** (+9.2): the Experiment-1 weak
  anchor reproduces its +9.2 *exactly*, and a same-class model from a different provider lands
  on the same number.

What these models share is a *specific competence profile*: capable enough to produce a
plausible, wrong answer and confidently declare it done (that's the false-DONE the bare-code D18
presentation manufactures — the edge case lived in the withheld docstring), **and** capable
enough that, once the checker refuses the declaration, they can actually iterate to the fix. The
binding advantage is the size of the overlap between "will false-DONE" and "can repair on
feedback." Too strong (GPT-4.1) and there's nothing to repair — it iterates to correct *before*
declaring done, 87/87 either way. Too weak (Llama-3.2-3B) and the repair never comes. In
between, the two conditions overlap, and the overlap peaks at Qwen.

Notice the discordant-task bug types line up with the mechanism: across the payoff rungs the
tasks binding rescues concentrate in **missing-edge-case** bugs (8 of Qwen's 13, 6 of Claude's,
6 of GPT-4o-mini's) — the same spec-carrying class Experiment 1 flagged, whose required behavior
was documented only in the description D18 withholds.

## The one prediction the ceiling confirmed

Prediction (iv) — for a model already at advisory ceiling, binding should cost no more — holds
where it can be tested. GPT-4.1 solves 87/87 in *both* modes, so it is the only at-ceiling rung,
and its binding run is **cheaper** ($0.104 vs $0.157): with nothing to repair, binding stops the
moment the checker goes green, while advisory spends extra tokens composing its `DONE`. Gating a
model that doesn't need gating is close to free.

## What this does and doesn't establish

The honest scope. This is one corpus (the same 97 buggy-Python-repair tasks as Experiment 1) and
one presentation regime (D18, docstrings and comments stripped). Experiment 2 varied *capability*
and held everything else fixed, on purpose — so what it establishes is the *shape*: completion
gating is a **windowed** intervention, not a monotone safety net, for this task family under this
presentation. Where the window's edges sit for other task families, other presentations, or a
different step cap is untested here. The top rung is a single provider (GPT-4.1), so the ceiling
of the curve rests on one vendor; the two open-weight cells at the weak end had to be re-run
through a hard-deadline recovery path after slow-provider hangs (all logs are schema-identical
and the interruption is logged, but it happened). And "rank" is a pre-registered ordering from
published benchmarks, not a measurement on these tasks.

What it does establish is enough to change the design advice. If you are reaching for
completion-gating to shore up a weak agent, the useful question is not "is the model weak?" but
"is the model *in the window* — wrong in a way that a checker can catch, and competent enough to
act on the catch?" Below that window, gating an agent doesn't rescue it; it just makes it fail
more expensively.
