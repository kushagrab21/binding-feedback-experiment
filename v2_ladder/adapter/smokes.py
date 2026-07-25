"""V2 ladder — per-rung smoke test (one trivial call per rung, 7 total).

For each rung this makes ONE tiny ``{model, temperature:0, messages}`` completion and
prints a one-line acceptance:

    rung<k> <slug>: resolved=<snapshot-id> tokens=<in>/<out> temp0=accepted route=<route>

Rung 6 (``google/gemini-2.5-flash-lite``) additionally confirms the model is
**reasoning-free** under the ``{model, temperature, messages}``-only call: no non-empty
assistant ``reasoning`` field and no ``reasoning_tokens`` in usage, with sane usage
counts. Per the registered rung-6 fallback rule, if rung 6 emits reasoning tokens or
refuses temp 0, the strongest passing Google flash-class candidate replaces it (logged
as a deviation) before any test-set episode.

Prints a final ``SMOKES: n/7 ok`` line and exits 0 iff all 7 rungs (or rung 6's
fallback) pass. Keys are never printed.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import client as C  # noqa: E402

PING = [{"role": "user", "content": "Respond with exactly the single word: pong"}]

# Strongest-first Google flash-class fallbacks for rung 6, per the registered rule.
RUNG6_FALLBACKS = [
    "google/gemini-2.0-flash-001",
    "google/gemini-flash-1.5",
    "google/gemini-flash-1.5-8b",
]


def _one_call(rung):
    """Make one ping call; return (ok, resolved, tin, tout, note, cli)."""
    cli = C.LadderClient(rung)
    try:
        resp = cli.complete(PING)
    except Exception as exc:  # noqa: BLE001
        return False, None, 0, 0, "ERROR: %s" % str(exc)[:160], cli
    tin = int(resp.get("tokens_in", 0))
    tout = int(resp.get("tokens_out", 0))
    resolved = resp.get("model") or rung["model"]
    return True, resolved, tin, tout, "", cli


def _reasoning_free(cli, tin, tout):
    """Rung-6 gate: reasoning-free (no reasoning text / tokens) + sane usage."""
    reasons = []
    if cli.last_reasoning_text:
        reasons.append("non-empty reasoning field")
    if cli.last_reasoning_tokens and cli.last_reasoning_tokens > 0:
        reasons.append("reasoning_tokens=%d" % cli.last_reasoning_tokens)
    if not (tin > 0 and tout > 0):
        reasons.append("usage not sane (in=%d out=%d)" % (tin, tout))
    return (not reasons), reasons


def main():
    lines = []
    n_ok = 0
    deviations = []

    for rung in C.RUNGS:
        ok, resolved, tin, tout, note, cli = _one_call(rung)
        if rung["rank"] == 6:
            if ok:
                free, reasons = _reasoning_free(cli, tin, tout)
                if free:
                    lines.append("rung6 %s: resolved=%s tokens=%d/%d temp0=accepted "
                                 "route=%s reasoning-free=YES (reasoning_tokens=%d)"
                                 % (rung["slug"], resolved, tin, tout, cli.route,
                                    cli.last_reasoning_tokens or 0))
                    n_ok += 1
                    continue
                note = "reasoning-NOT-free: " + "; ".join(reasons)
                ok = False
            # --- registered fallback: strongest passing Google flash-class ---
            fb_applied = None
            for fb_model in RUNG6_FALLBACKS:
                fb_rung = dict(rung, model=fb_model, slug="rung6_" + fb_model.split("/")[-1])
                fok, fresolved, ftin, ftout, fnote, fcli = _one_call(fb_rung)
                if fok:
                    ffree, freasons = _reasoning_free(fcli, ftin, ftout)
                    if ffree:
                        fb_applied = (fb_model, fresolved, ftin, ftout)
                        break
            if fb_applied:
                fb_model, fresolved, ftin, ftout = fb_applied
                deviations.append("rung6 fallback -> %s (rank re-derivation required "
                                  "per registered rule before any test episode)" % fb_model)
                lines.append("rung6 FALLBACK=%s: resolved=%s tokens=%d/%d temp0=accepted "
                             "reasoning-free=YES  [DEVIATION: original %s failed: %s]"
                             % (fb_model, fresolved, ftin, ftout, rung["model"], note))
                n_ok += 1
            else:
                lines.append("rung6 %s: FAILED (%s) and no reasoning-free Google "
                             "flash-class fallback passed -> STOP" % (rung["slug"], note))
            continue

        if ok:
            lines.append("rung%d %s: resolved=%s tokens=%d/%d temp0=accepted route=%s"
                         % (rung["rank"], rung["slug"], resolved, tin, tout, cli.route))
            n_ok += 1
        else:
            lines.append("rung%d %s: %s" % (rung["rank"], rung["slug"], note))

    print("\n".join(lines))
    for d in deviations:
        print("DEVIATION: " + d)
    print("SMOKES: %d/7 ok" % n_ok)
    return 0 if n_ok == 7 else 1


if __name__ == "__main__":
    sys.exit(main())
