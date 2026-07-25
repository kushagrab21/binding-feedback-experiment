# When "done" isn't the model's call to make

Give a coding agent a bug to fix and it will, sooner or later, tell you it's finished.
The interesting question is what your system does with that claim. Two options:

- **Advisory:** the model says "DONE," and you believe it. Completion is *declared*.
- **Binding:** the model doesn't get to say "DONE." A checker runs the tests, and *it*
  decides whether the task is solved. Completion is *computed*.

These sound almost the same. Most of the time they *are* the same — a good model submits
correct code and both systems agree it's done. This experiment is about the times they
disagree, and about which kind of model that disagreement rescues.

## The false-DONE

The failure mode that separates the two designs has a name here: the **false-DONE**. The
model submits code that is *wrong*, and in the same breath declares the task finished. Under
advisory, that declaration ends the episode — a wrong answer stands, because the model was
allowed to be the judge of its own work. Under binding, the declaration is ignored; the
checker is still red, so the episode continues and the model has to try again.

A false-DONE isn't laziness. It's a confident model that has *reconstructed the wrong
spec*. If the task is "count the divisors of n," and nobody told the model that `n < 1` is
supposed to raise an error, then a function that happily counts the divisors of `-6` looks
complete to the model. It only looks *wrong* to a test suite that knows the hidden rule.

## The setup

We built 97 small Python functions, each with exactly one injected bug (an off-by-one, a
flipped comparison, a deleted edge-case guard, and so on), and froze them. We ran two
models — a cheap/weak one (`gpt-4o-mini`) and a frontier/strong one (`gpt-4.1`) — through
both an advisory and a binding harness that are *identical* except for the three structural
rules that make binding binding. Same tasks, same prompts, same checker, temperature 0.

There was one twist we had to add to see anything at all, and it's worth being honest
about (see "The uncomfortable finding" below): with the normal task description in hand,
**both models one-shot almost everything**, and advisory-vs-binding makes no difference
whatsoever. To create *any* daylight between the two designs, we had to withhold the spec —
strip the description, the docstrings, and the comments, and hand the model only the bare
buggy code and the checker. Starved of the spec, the model has to *learn* the hidden rules
from the checker's feedback. That's the regime where the two designs finally diverge.

## The one task that shows it

Here is the same model, on the same bug, in both harnesses. The bug: `count_divisors` had
its "raise on `n < 1`" guard deleted, and we stripped the docstring that documented it. The
model has no way to know the guard is required except by failing the test.

**Advisory** — the model submits a fix *and* declares done in one turn. The checker fails
it. Advisory accepts the declaration anyway:

```
MODEL: <code>  DONE
CHECK: FAILED — test_negative_raises: ValueError not raised
END:   status = model_declared_done   passed = False
```

**Binding** — same model, same first mistake. But there is no "DONE" to accept. The FAILED
verdict goes back into the conversation, and the model repairs it:

```
MODEL: <code>            (no DONE — it can't declare)
CHECK: FAILED — test_negative_raises: ValueError not raised
       (verdict fed back)
MODEL: <corrected code>
CHECK: PASSED — all tests passed
END:   status = solved   passed = True
```

Same model, same bug, same first-turn failure. Advisory ends *wrong*; binding ends *right*.
Nothing changed except who was allowed to call the task finished.

## The result

Across all 87 held-out test tasks:

| model | advisory | binding | difference |
|---|---|---|---|
| gpt-4o-mini (weak) | **90.8%** | **100%** | **+9.2 points** |
| gpt-4.1 (strong) | 100% | 100% | +0.0 points |

Binding lifts the weak model by 9.2 points and does *nothing* for the strong one. That gap
is the whole story: this is an **interaction**, not a blanket improvement. Statistically,
the weak model had 8 tasks where the two designs disagreed and *all 8* went advisory-fail /
binding-pass (exact McNemar p = 0.0078); the strong model had zero disagreements.

**Why the strong model doesn't need it:** it also hit failing tests on several tasks — but
in advisory it *iterated to a correct answer before declaring done*, instead of quitting
wrong. Binding's safety net only catches a model that would otherwise let go too early.
Every one of the weak model's 8 advisory failures was a false-DONE, and 6 of those 8 were
the same species of bug — a **missing edge case** whose only documentation was the spec we
withheld. Strip the spec, and the failures pile up in exactly the bugs the spec was
carrying. Binding catches them because it never lets the model stop on red.

One honest deflation: of the 8 tasks binding "rescued," 2 weren't really repairs — at
temperature 0 the two arms happened to draw slightly different first submissions, and
binding's first draft passed where advisory's false-DONEd. So the honest count is **6 genuine
forced repairs** plus 2 lucky first samples. And two of binding's three mechanisms — blocking
identical resubmissions, and escalating after repeated stalls — never fired once. The entire
advantage came from the simplest mechanism: *don't let the model quit while the checker is
red.*

## The uncomfortable finding

The thing we had to do to see the effect is a result in its own right. **Modern models
one-shot single-mutation bugs until you starve them of the spec.** With the description
present — even with just the docstrings present — both a weak and a strong model fixed
essentially every task on the first try, and it made no difference at all whether they were
allowed to declare themselves done. The advisory-vs-binding distinction only *matters* in
the narrow regime where the model genuinely doesn't know the rules and has to discover them
from feedback. When the model already knows the answer, letting it grade its own homework is
harmless. The danger — and the case for binding — is precisely the case where it *doesn't*
know, and doesn't know that it doesn't know.

## Reading this honestly

The effect is real and statistically clean, but narrow: two models, one provider, one
deliberately spec-starved presentation, and a base of 8 tasks concentrated in a single bug
class — with 2 of those 8 being sampling luck rather than repair. What it demonstrates is a
*mechanism*, cleanly isolated: when a weak model would confidently declare a wrong answer
finished, computing completion instead of trusting the declaration converts that failure
into a fix. Whether the mechanism is worth its cost in a real agent — where checkers are
imperfect and iteration isn't free — is the question this experiment sets up rather than
settles.

Every number here regenerates from committed logs with one offline command; the full build
trail, including all eighteen logged deviations, is in `EXPERIMENT_LOG.md`.
