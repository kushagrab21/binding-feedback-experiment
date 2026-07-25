# Bug Taxonomy — the final 8 types

This document fixes the **closed vocabulary** of bug types used everywhere in the
experiment. Every `candidate_bug_types` entry in `SEEDS.json`, every `bug_type` in a
task's `meta.json`, and the `ALLOWED_BUG_TYPES` set in `validate_seeds.py` MUST be one
of the eight types below. Nothing outside this set is permitted.

The eight types are chosen to be **mutually distinguishable** (a reviewer can classify a
given one-line mutation into exactly one bucket in almost all cases) and **jointly
sufficient** to cover the mutations the seed corpus admits. Each type is a *class of
single, local edit* to a correct function that (a) changes observable behaviour on at
least one input and (b) is therefore catchable by a deterministic test — the two
properties that make a mutation usable as a task.

The final eight:

1. `off-by-one`
2. `wrong-comparison`
3. `wrong-operator`
4. `inverted-condition`
5. `wrong-variable`
6. `missing-edge-case`
7. `wrong-return`
8. `input-mutation`

---

## 1. `off-by-one`

**Definition.** A boundary that is displaced by exactly one: a loop bound, range
endpoint, slice index, initial counter, or `+1`/`-1` term is one unit too large or too
small. The comparison *operator* and the *variables* are correct; only the numeric
boundary is wrong. This is the classic fencepost error. (It also absorbs the
"accumulator seeded to the wrong integer" case — e.g. a counter started at `1` instead
of `0` — because that is an off-by-one in the seed value; see the mapping table.)

**Before / after.**
```python
# correct: scan indices 0 .. len-1
right = len(s) - 1
# buggy: reads one past the end (IndexError on non-empty input)
right = len(s)
```

**Detectable by tests because.** The displaced boundary either raises `IndexError`, or
includes/excludes exactly one element at the extreme of the range — so a test that
exercises the first or last element (or an empty/one-element input) diverges from the
reference.

---

## 2. `wrong-comparison`

**Definition.** A comparison operator is replaced by a *different* comparison operator
of the same arity: `<`↔`<=`, `>`↔`>=`, `==`↔`!=`, `<`↔`>`. The operands and the branch
structure are unchanged; only the relational test is wrong. (Distinguished from
`off-by-one`, which keeps the operator and shifts a boundary, and from
`inverted-condition`, which negates the *whole* predicate / swaps the branches.)

**Before / after.**
```python
# correct: strict — a later char must exceed the best to win (keeps earliest on ties)
if counts[ch] > best_count:
# buggy: non-strict — ties now overwrite, returning the wrong "most common" char
if counts[ch] >= best_count:
```

**Detectable by tests because.** The two operators differ exactly on the boundary case
(equal operands, or the `<` vs `>` reversal). A test whose input hits that case — a tie,
an equal-to-bound value, an exact match — produces a different result under the mutant.

---

## 3. `wrong-operator`

**Definition.** An arithmetic, bitwise, or boolean *operator* is swapped for another:
`+`↔`-`, `*`↔`//`, `%`↔`//`, `and`↔`or`. The operands are correct and in the right place;
only the operation combining them is wrong. (Comparison operators belong to
`wrong-comparison`; this type is for value-producing/logical operators. Arithmetic
operator errors are genuinely distinct from comparison errors, which is why
`wrong-operator` is retained alongside `wrong-comparison` in the eight.)

**Before / after.**
```python
# correct: accumulate the digit
total += n % 10
# buggy: subtracts instead, corrupting the sum
total -= n % 10
```

**Detectable by tests because.** The two operators agree only on degenerate operands
(e.g. `+` and `-` agree only when the right operand is `0`; `and` and `or` agree only
when both operands share a truth value). Any test with non-degenerate operands separates
them.

---

## 4. `inverted-condition`

**Definition.** A boolean predicate is logically negated as a whole, or the two arms of
an `if`/`else` are swapped, so the true and false paths are exchanged: `if x:`→`if not
x:`, dropping or adding a `not`, or swapping `and`↔`or` *in a way that inverts the
guard's truth on the relevant inputs*. Unlike `wrong-comparison`, the change flips the
*decision*, not just the relation at one boundary.

**Before / after.**
```python
# correct: a value already seen means "not all unique"
if item in seen:
    return False
# buggy: inverted guard — returns False for the fresh values instead
if item not in seen:
    return False
```

**Detectable by tests because.** Inverting a guard exchanges outputs on whole classes of
input (every duplicate vs every non-duplicate), so almost any non-trivial test that
reaches the branch flips its result.

---

## 5. `wrong-variable`

**Definition.** A syntactically valid but *semantically wrong* name/operand is used in
place of the intended one: two operands are swapped, the wrong index or accumulator is
referenced, or `a` is used where `b` was meant. Types still line up (so it parses and
runs); the value is drawn from the wrong place. (This subsumes the "swapped operands"
case.)

**Before / after.**
```python
# correct: append the inner element
for item in sub:
    result.append(item)
# buggy: appends the sub-list itself — wrong operand, no flattening
for item in sub:
    result.append(sub)
```

**Detectable by tests because.** The wrong variable holds a different value on any input
where the two variables differ (nearly always), so the output diverges — often
structurally (wrong shape/type of result), which tests catch immediately.

---

## 6. `missing-edge-case`

**Definition.** A guard, branch, or case that the contract requires is *omitted or
narrowed*, so a boundary/special input is mishandled: a dropped validation (`if n < 0:
raise`), an un-handled empty/`None`/single-element input, an alphabet or case that is
left out, or an `else` branch that is deleted. The main path is correct; a specific case
is simply not covered. (This subsumes both "boundary-omission" and "missing-case".)

**Before / after.**
```python
# correct: reject the undefined input
if n < 0:
    raise ValueError("n must be non-negative")
# buggy: guard removed — negative n now loops zero times and silently returns 0
```

**Detectable by tests because.** By construction there is an input in the missing case;
a test that supplies it (the empty string, a negative number, an absent key, a tie) gets
the wrong answer or a missing exception, while typical inputs still pass.

---

## 7. `wrong-return`

**Definition.** The function returns the *wrong value* on some path: the wrong variable
is returned, a wrong default/sentinel is emitted on the fallback path, `True`/`False`
are swapped, a `return` fires too early (short-circuiting later work), or the wrong
container/type is returned. The computation may be right; what leaves the function is
wrong. (This subsumes both "early-return" and "wrong-default": a wrong default is just
the wrong value emitted on the empty/absent/fallback path.)

**Before / after.**
```python
# correct: return the character
return best_char
# buggy: returns the count instead — right computation, wrong thing returned
return best_count
```

**Detectable by tests because.** The returned object is compared directly by the test;
returning a different variable, sentinel, or type mismatches the expected value (often a
type error in the assertion), and an early return skips inputs that only the later code
handles.

---

## 8. `input-mutation`

**Definition.** The function mutates a caller-owned mutable argument (a `list`, `dict`,
or `set`) that its contract promises to leave unchanged — typically by *aliasing* the
input instead of copying it (`result = nums` rather than `result = list(nums)`;
`result = a` rather than `result = {}`) and then writing through the alias. The returned
value may even be correct; the defect is the visible side effect on the caller's object.

**Before / after.**
```python
# correct: sort a copy, leave the caller's list untouched
result = list(nums)
# buggy: aliases the argument, so the in-place swaps mutate the caller's list
result = nums
```

**Detectable by tests because.** A test passes a mutable argument, records its contents,
calls the function, and asserts the argument is unchanged — the aliasing mutant fails
that assertion even when its return value looks right. This type is deliberately the
**sparsest**: it is a candidate only for seeds that take a mutable argument the contract
says is not mutated (see below).

---

## Retirement mapping: provisional 10-type vocabulary → final 8

The provisional vocabulary used through steps 1.2 / 1.2-R
(`off-by-one, boundary-omission, wrong-comparison, wrong-operator, inverted-condition,
swapped-operands, missing-case, early-return, accumulator-init-error, wrong-default`) is
**retired**. Every retired label maps onto exactly one of the final eight. Four names
carry over unchanged; six are folded in:

| Retired type            | Final type          | Rationale                                                                                     |
| ----------------------- | ------------------- | --------------------------------------------------------------------------------------------- |
| `off-by-one`            | `off-by-one`        | Unchanged.                                                                                     |
| `wrong-comparison`      | `wrong-comparison`  | Unchanged.                                                                                     |
| `wrong-operator`        | `wrong-operator`    | Unchanged; retained as distinct from `wrong-comparison` (arithmetic/logical vs relational).   |
| `inverted-condition`    | `inverted-condition`| Unchanged.                                                                                     |
| `boundary-omission`     | `missing-edge-case` | An omitted boundary case *is* a missing edge case; merged for a single "unhandled case" bucket.|
| `missing-case`          | `missing-edge-case` | Same bucket as above — an unhandled case is a missing edge case.                               |
| `swapped-operands`      | `wrong-variable`    | Swapping operands is using the wrong variable in each position; a special case of `wrong-variable`. |
| `early-return`          | `wrong-return`      | Returning too early is one way of returning the wrong value on a path; folded into `wrong-return`. |
| `accumulator-init-error`| `off-by-one`        | Best-fit: the canonical instance is seeding a counter/accumulator to `1` instead of `0` — an off-by-one in the initial value, the same fencepost error class. |
| `wrong-default`         | `wrong-return`      | Best-fit: a wrong default is the wrong value emitted on the fallback/absent/empty path — i.e. returning the wrong value, which `wrong-return` already covers. |

The two "best-fit" folds (`accumulator-init-error`, `wrong-default`) are the only ones
that are not near-synonyms; each is justified on its row above. After this mapping, **no
label outside the eight survives as an operative vocabulary term** anywhere in the repo.
(The step-1.2 / 1.2-R entries in `EXPERIMENT_LOG.md` still name the retired terms; that
is a historical record in an append-only log, not an operative label, and is left intact
by design.)
