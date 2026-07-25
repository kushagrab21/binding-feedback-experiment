"""Behavioral spot-check for the Phase 1 seed corpus.

Imports every seed function named in the CASES table and asserts concrete
input -> output pairs, including edge cases and expected exceptions. Prints
one line per seed (``seed_NNN function_name: PASS (k assertions)``) and a
final summary. Exits 0 iff every assertion holds, non-zero otherwise.

    python3 phase1_tasks/seeds/spotcheck_seeds.py

This file is the committed, reproducible replacement for the ad-hoc spot
check used in step 1.2. It is intentionally self-contained (it does not read
SEEDS.json) so it exercises behaviour independently of the manifest.
"""

import importlib.util
import sys
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent

RAISES = "__raises__"  # sentinel marking a case that must raise.

# seed_id -> (function_name, [(args_tuple, expected | (RAISES, ExcType)), ...])
CASES = {
    "seed_001": ("clamp", [
        ((5, 0, 10), 5),
        ((-3, 0, 10), 0),
        ((99, 0, 10), 10),
        ((0, 0, 0), 0),
        ((1, 10, 0), (RAISES, ValueError)),
    ]),
    "seed_002": ("digit_sum", [
        ((0,), 0),
        ((9,), 9),
        ((1234,), 10),
        ((100,), 1),
        ((-1,), (RAISES, ValueError)),
    ]),
    "seed_003": ("count_divisors", [
        ((1,), 1),
        ((6,), 4),
        ((7,), 2),
        ((12,), 6),
        ((0,), (RAISES, ValueError)),
    ]),
    "seed_004": ("gcd_two", [
        ((12, 18), 6),
        ((0, 5), 5),
        ((-8, 12), 4),
        ((7, 7), 7),
        ((0, 0), (RAISES, ValueError)),
    ]),
    "seed_005": ("is_palindrome", [
        (("",), True),
        (("a",), True),
        (("aba",), True),
        (("abba",), True),
        (("ab",), False),
    ]),
    "seed_006": ("count_vowels", [
        (("",), 0),
        (("AeiOux",), 5),
        (("bcdfg",), 0),
        (("Yy",), 0),
    ]),
    # --- seed_007 rewritten in 1.2-R; edge cases: empty, single word,
    #     collapsed multiple spaces, trailing/leading whitespace ---
    "seed_007": ("reverse_words", [
        (("a b c",), "c b a"),
        (("  a  b c ",), "c b a"),
        (("",), ""),
        (("single",), "single"),
        (("x  y",), "y x"),
    ]),
    "seed_008": ("caesar_shift", [
        (("abcXYZ", 1), "bcdYZA"),
        (("Hi!", -1), "Gh!"),
        (("abc", 0), "abc"),
        (("xyz", 3), "abc"),
        (("ABC", 1), "BCD"),
    ]),
    # --- seed_009 rewritten in 1.2-R; edge cases: duplicate collapse,
    #     negatives, single value (raises), all-equal (raises) ---
    "seed_009": ("second_largest", [
        (([5, 5, 3],), 3),
        (([1, 2, 3],), 2),
        (([3, 1, 2, 3, 1],), 2),
        (([-1, -2],), -2),
        (([1],), (RAISES, ValueError)),
        (([7, 7, 7],), (RAISES, ValueError)),
    ]),
    "seed_010": ("flatten_one_level", [
        (([[1, 2], [3]],), [1, 2, 3]),
        (([],), []),
        (([[], [1]],), [1]),
        (([[1], [2], [3]],), [1, 2, 3]),
    ]),
    "seed_011": ("chunk", [
        (([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]]),
        (([], 3), []),
        (([1, 2, 3], 1), [[1], [2], [3]]),
        (([1, 2], 5), [[1, 2]]),
        (([1], 0), (RAISES, ValueError)),
    ]),
    # --- seed_012 rewritten in 1.2-R; edge cases: empty, k == len (wrap
    #     to identity), k > len ---
    "seed_012": ("rotate_left", [
        (([1, 2, 3, 4], 1), [2, 3, 4, 1]),
        (([1, 2, 3], -1), [3, 1, 2]),
        (([], 2), []),
        (([1, 2, 3], 3), [1, 2, 3]),
        (([1, 2, 3], 5), [3, 1, 2]),
    ]),
    # --- seed_013 rewritten in 1.2-R; edge cases: empty, single, all-same ---
    "seed_013": ("word_frequencies", [
        ((["a", "b", "a"],), {"a": 2, "b": 1}),
        (([],), {}),
        ((["x"],), {"x": 1}),
        ((["a", "a", "a"],), {"a": 3}),
    ]),
    # --- seed_014 rewritten in 1.2-R; edge cases: empty dicts, disjoint
    #     keys, colliding keys that cancel ---
    "seed_014": ("merge_sum", [
        (({"a": 1, "b": 2}, {"b": 3, "c": 4}), {"a": 1, "b": 5, "c": 4}),
        (({}, {}), {}),
        (({"x": 1}, {}), {"x": 1}),
        (({}, {"y": 2}), {"y": 2}),
        (({"k": 1}, {"k": -1}), {"k": 0}),
    ]),
    "seed_015": ("most_common_char", [
        (("aabbb",), "b"),
        (("abcabc",), "a"),
        (("x",), "x"),
        (("",), (RAISES, ValueError)),
    ]),
    "seed_016": ("is_valid_identifier", [
        (("_x1",), True),
        (("Abc_9",), True),
        (("1x",), False),
        (("",), False),
        (("a-b",), False),
    ]),
    "seed_017": ("is_leap_year", [
        ((2000,), True),
        ((1900,), False),
        ((2024,), True),
        ((2023,), False),
        ((2100,), False),
    ]),
    "seed_018": ("all_unique", [
        (([1, 2, 3],), True),
        (([1, 1],), False),
        (([],), True),
        ((["a", "b", "a"],), False),
    ]),
    "seed_019": ("binary_search", [
        (([1, 3, 5, 7], 5), 2),
        (([1, 3, 5, 7], 4), -1),
        (([], 1), -1),
        (([1, 3, 5, 7], 1), 0),
        (([1, 3, 5, 7], 7), 3),
    ]),
    "seed_020": ("bubble_sort", [
        (([3, 1, 2],), [1, 2, 3]),
        (([],), []),
        (([1],), [1]),
        (([5, 4, 3, 2, 1],), [1, 2, 3, 4, 5]),
        (([2, 2, 1],), [1, 2, 2]),
    ]),
    # --- parsing seeds appended in 1.2-R stage 3 ---
    "seed_021": ("parse_signed_int", [
        (("42",), 42),
        (("-7",), -7),
        (("+0",), 0),
        (("0",), 0),
        (("123",), 123),
        (("",), (RAISES, ValueError)),
        (("-",), (RAISES, ValueError)),
        (("1a",), (RAISES, ValueError)),
        ((" 5",), (RAISES, ValueError)),
    ]),
    "seed_022": ("parse_hhmm", [
        (("00:00",), 0),
        (("23:59",), 1439),
        (("13:45",), 825),
        (("01:02",), 62),
        (("24:00",), (RAISES, ValueError)),
        (("1:00",), (RAISES, ValueError)),
        (("aa:bb",), (RAISES, ValueError)),
        (("12:60",), (RAISES, ValueError)),
    ]),
    "seed_023": ("parse_roman", [
        (("III",), 3),
        (("IV",), 4),
        (("IX",), 9),
        (("LVIII",), 58),
        (("MCMXCIV",), 1994),
        (("",), (RAISES, ValueError)),
        (("IIU",), (RAISES, ValueError)),
    ]),
    "seed_024": ("parse_csv_line", [
        (("a,b,c",), ["a", "b", "c"]),
        (('"a,b",c',), ["a,b", "c"]),
        (('a,"b""c",d',), ["a", 'b"c', "d"]),
        (("",), [""]),
        (("a,",), ["a", ""]),
    ]),
    "seed_025": ("parse_version", [
        (("1.2.3",), (1, 2, 3)),
        (("10.0",), (10, 0)),
        (("1",), (1,)),
        (("",), (RAISES, ValueError)),
        (("1..2",), (RAISES, ValueError)),
        (("1.a",), (RAISES, ValueError)),
    ]),
}


def load(seed_id, func_name):
    path = SEED_DIR / f"{seed_id}.py"
    spec = importlib.util.spec_from_file_location(seed_id, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, func_name)


def is_raises(expected):
    return (isinstance(expected, tuple) and len(expected) == 2
            and expected[0] == RAISES)


def main():
    failures = 0
    total_assertions = 0
    for seed_id in sorted(CASES):
        func_name, cases = CASES[seed_id]
        try:
            func = load(seed_id, func_name)
        except Exception as exc:  # noqa: BLE001 - report any import failure
            print(f"{seed_id} {func_name}: FAIL (import error: {exc})")
            failures += 1
            continue

        problems = []
        for args, expected in cases:
            total_assertions += 1
            if is_raises(expected):
                exc_type = expected[1]
                try:
                    result = func(*args)
                    problems.append(
                        f"{func_name}{args!r} -> {result!r}, "
                        f"expected raise {exc_type.__name__}")
                except exc_type:
                    pass
                except Exception as other:  # noqa: BLE001
                    problems.append(
                        f"{func_name}{args!r} raised {type(other).__name__}, "
                        f"expected {exc_type.__name__}")
            else:
                try:
                    result = func(*args)
                except Exception as exc:  # noqa: BLE001
                    problems.append(
                        f"{func_name}{args!r} raised {type(exc).__name__}, "
                        f"expected {expected!r}")
                    continue
                if result != expected:
                    problems.append(
                        f"{func_name}{args!r} -> {result!r}, "
                        f"expected {expected!r}")

        if problems:
            print(f"{seed_id} {func_name}: FAIL ({len(cases)} assertions)")
            for problem in problems:
                print(f"    {problem}")
            failures += 1
        else:
            print(f"{seed_id} {func_name}: PASS ({len(cases)} assertions)")

    print("---")
    if failures:
        print(f"SPOTCHECK: FAILED ({failures} seed(s) failed, "
              f"{total_assertions} assertions total)")
        return 1
    print(f"SPOTCHECK: OK ({len(CASES)} seeds, "
          f"{total_assertions} assertions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
