# The window that didn't slide

*Experiment 3 of the binding-feedback study. Plain-language write-up; every number traces to
`v3_window/analysis/results.md`, regenerated deterministically from 1,296 committed episodes. The
k0 column is Experiment 2's frozen test data, cited by v2's committed manifests — not re-run.*

## The question we carried forward

Experiment 1 found that *binding* feedback — letting a checker, not the model's own `DONE`, decide
when a task is finished — helps a weak model and does nothing for a strong one. Experiment 2
walked that up a seven-model ladder and found the help is a **capability window**: it pays off in
a middle band, does nothing at the ceiling, and can even *hurt* the weakest model. But Experiment
2 held task difficulty fixed — one bug per task, k ≈ 0. So the window it drew was a window in
*model* space, at a single difficulty.

That leaves a sharp question. Is the window a property of the **model**, or of the **model–task
pair**? If it's the pair, then difficulty and capability should trade off: make the task harder,
and a model that used to sail through should start tripping — writing a plausible-but-wrong answer
and declaring it done — and binding should start helping it. In other words, **the window should
slide up the capability axis as the task gets harder**. Push difficulty far enough and even
GPT-4.1 should fall into the regime where completion-gating earns its keep.

We tested this by turning difficulty into a knob we could crank: **bug composition**. A k1 task is
two real Experiment-1 bugs stacked on one function; a k2 task is three. Nothing is invented — each
task is k+1 verbatim v1 mutations on distinct lines of one v1 seed, so "harder" means "more
independent things to get right at once," on the same corpus, same bare-code presentation, same
temperature and cap. Six models spanning the v2 ladder from a bottom-edge anchor (Llama-3.1-8B) to
the top (GPT-4.1), 1,296 episodes, predictions locked with a git tag before the first paid call.
The headline prediction, **P2**, was blunt: GPT-4.1's advisory false-DONE count, zero at k ≈ 0,
becomes **positive at k2**, and its Δ turns positive there — the window slides to the ceiling.

## What the tiers actually show

The window did **not** slide. It **deepened in place**.

```
Δ (binding − advisory), points, per model — k0 → k1 → k2:
GPT-4.1                +0.0  →  +0.0  →  +0.0      the ceiling never moves
Gemini-2.5-flash-lite  +9.2  → +23.3  → +22.9
GPT-4o-mini            +9.2  → +23.3  → +22.9
Claude-3-Haiku        +11.5  → +26.7  → +25.0
Qwen2.5-7B            +14.9  → +31.7  → +22.9      the peak — deepens, then plateaus
Llama-3.1-8B           +2.3  → +10.0  →  +2.1
```

Two things happen at once, and only one of them was predicted.

**The predicted-shape part (P1, confirmed).** Every model *already inside* the window gets helped
**more** as the bugs compose. The binding advantage roughly **doubles** from k0 to k1 for all four
window models — Qwen from +14.9 to +31.7 points, Claude from +11.5 to +26.7, the two mid anchors
from +9.2 to +23.3 — and stays large at k2, every cell McNemar-significant (p ≤ 0.004, and down to
p ≈ 4e-6 for Qwen at k1). More bugs per task means more chances to leave one unfixed and
confidently declare done, so the advisory arm false-DONEs more; binding refuses the declaration
and the model repairs. The mechanism from Experiments 1 and 2 is not just intact under
composition — it is *amplified*.

**The un-predicted part (P2, disconfirmed).** GPT-4.1 does not move. Zero advisory false-DONEs at
k0, zero at k1, **zero at k2**. 60/60 and 48/48 solved in both modes. Δ = +0.0 at every tier.
Three simultaneous bugs — a task hard enough that Qwen false-DONEs 40% of the time — was not
enough to knock the strongest model into the false-claiming regime even once. The window's ceiling
is anchored to the *model*, not to the difficulty. It did not slide.

So the honest picture is an **interaction, not a translation**. Composition amplifies binding for
models that were already in the window; it does not drag stronger models into it. The window got
deeper where it already was, and its top edge stayed exactly where Experiment 2 put it.

## The mediator moves with the effect

The thing that makes P1 work and P2 fail is visible in one number: the **advisory false-DONE
rate**, the rate at which a model in plain advisory mode declares a still-failing task done.

```
advisory false-DONE rate — k0 → k1 → k2:
Qwen2.5-7B            18% → 40% → 33%
Claude-3-Haiku       17% → 32% → 31%
GPT-4o-mini / Gemini  9% → 23% → 23%
Llama-3.1-8B          5% → 12% → 10%
GPT-4.1               0% →  0% →  0%
```

Δ tracks this surface almost exactly. Where composition drives the false-DONE rate up (every
window model, k0→k1), Δ goes up with it. Where the false-DONE rate is pinned at zero (GPT-4.1),
Δ is pinned at zero too. Binding can only convert a false-DONE into a solve if the false-DONE
happens in the first place; GPT-4.1 simply doesn't produce them, at any difficulty we reached, so
there is nothing for binding to catch. And when binding *does* catch one, it is real iteration, not
luck: nearly every one of binding's wins across all cells is a **forced repair** — a FAILED
verdict, a changed resubmission, then PASS — not a first-sample coincidence.

Notice the false-DONE rate itself **dips slightly from k1 to k2** for the window models (Qwen
40%→33%), and Δ dips with it (Qwen +31.7→+22.9). That is why the window *deepens once and
plateaus* rather than widening without bound: at three bugs both arms lose absolute ground, so the
gap between them stops growing. The window's depth is set by how often the model is confidently
wrong *and* able to recover — and that overlap maxed out around k1 for this corpus.

## The deflations, next to the finding

- **P2 was the risky bet, and we lost it — on purpose.** The dev glimpse, disclosed at
  registration, already showed GPT-4.1 clean at k2. We registered P2 anyway, betting the larger
  48-task test set would surface a low-rate false-claim the 10-task dev cell couldn't. It didn't:
  the count is still exactly **0**, re-derived straight from the raw logs. Reporting that as a
  disconfirmation, right beside the confirmed P1, is the whole point of pre-registering.
- **P3 (escalation-attributed losses) is directionally right but tiny.** Binding's definition is
  unchanged for v3, so its known wart — a model that resubmits the same failing answer three times
  ends `escalated` — can turn an advisory solve into a binding loss. Across all 12 cells only
  **4** such b-direction discordants ended escalated, and **3 of the 4** are at the bottom-edge
  anchor Llama-3.1-8B, growing 1→2 from k1 to k2. The predicted concentration-at-the-weak-edge and
  growth-with-k are both there, but on single-digit counts — a measured wart, not a headline.
- **P4 (cost at the ceiling) holds.** GPT-4.1 is the only model at advisory ceiling, and its
  binding run is cheaper than advisory at both tiers ($0.078 vs $0.112 at k1; $0.067 vs $0.092 at
  k2): with nothing to repair, binding stops the instant the checker goes green. Gating a model
  that doesn't need gating stays close to free even as tasks get harder.
- **P5 (exploratory) — a faint rightward drift.** The single most-helped model is Qwen at both k0
  and k1, then Claude-3-Haiku — one rung stronger — at k2. A hint that the *peak* of the window
  edges toward stronger models with difficulty, exactly the shape P2 predicted for the *ceiling*,
  but far too weak to lean on. Scored exploratory, as registered.

## What this does and doesn't establish

The honest scope, in the same spirit as Experiments 1 and 2. One corpus, one presentation regime
(buggy-Python repair, D18 docstrings stripped). Difficulty here is **bug count**, built from
verbatim v1 mutations stacked on a single seed — so a "harder" task is more independent bugs to fix
at once, not a novel bug family, a longer program, or a different kind of reasoning. Because the
tasks are composed, they are **multi-label**: the bug-type breakdown counts each of a task's k+1
constituents, so those rows sum past the task count, and we say so. We measured only three points
on the k axis (0, 1, 2); the top rung is a single provider; and the pre-registration's publish
gate was waived by the courier (deviation V3-D1, logged verbatim), though the timestamp-ordering
half was still discharged — the registration provably precedes the data.

What it establishes is enough to sharpen the Experiment-2 advice. The capability window is real and
it is **robust to task difficulty in the direction that matters**: making the task harder does not
move its ceiling. If a model is strong enough not to false-claim at k ≈ 0, stacking bugs on the
task does not create a false-claiming problem for binding to solve — it stays at the ceiling, and
gating stays free. The payoff from completion-gating deepens for models already in the window as
their tasks get harder, but you cannot buy your way into the window by making the task harder. The
window is a property of the model, not the model–task pair. It didn't slide.
