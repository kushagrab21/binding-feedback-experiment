"""V3 calibration — shared config (roster, tiers, task/split resolution).

This is the ONE place the calibration roster, the two composition tiers, and the
D18 config are named, so the per-cell runner (``run_one_cell_v3.py``), the
orchestrator (``run_calibration.py``), and the report (``report.py``) cannot drift.

Everything model-facing is the **v2 adapter, verbatim**: the roster is exactly five
of v2's frozen ``RUNGS`` dicts, selected by slug, so their snapshots, routes,
providers, and per-1M prices are byte-identical to what v2's manifests recorded.
No frozen v1/v2 file is edited; this module only *imports* and *selects*.

Roster (5 models): the four "window" models whose advisory success the calibration
checks against the 40-70% band —

    qwen-2.5-7b, claude-3-haiku, gpt-4o-mini, gemini-2.5-flash-lite

— plus ``gpt-4.1`` as the **ceiling probe** (watched for advisory false-DONEs, NOT a
band member). Tiers k1 (2 bugs) and k2 (3 bugs); DEV tasks only (each tier's
``split.json['dev']``); the test splits are untouched this step.
"""

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_V3 = os.path.dirname(_HERE)
_REPO = os.path.dirname(_V3)

# Reuse the v2 adapter + shared runner verbatim (harness modules, D18 config, helpers).
sys.path.insert(0, os.path.join(_REPO, "v2_ladder", "adapter"))
sys.path.insert(0, os.path.join(_REPO, "v2_ladder", "runs"))
import client as C            # noqa: E402  (the v2 adapter)
import runner as R            # noqa: E402  (harness modules + D18_CONFIG + helpers)

# --- roster: five v2 rungs selected by slug (dicts reused verbatim) ----------
ROSTER = [
    ("qwen-2.5-7b",           "rung3_qwen2.5-7b"),
    ("claude-3-haiku",        "rung4_claude-3-haiku"),
    ("gpt-4o-mini",           "rung5_gpt-4o-mini"),
    ("gemini-2.5-flash-lite", "rung6_gemini-2.5-flash-lite"),
    ("gpt-4.1",               "rung7_gpt-4.1"),          # ceiling probe (NOT a band member)
]
MODEL_SLUGS = [m for m, _ in ROSTER]
RUNG_BY_MODEL = {m: C.RUNGS_BY_SLUG[slug] for m, slug in ROSTER}
WINDOW_MODELS = ["qwen-2.5-7b", "claude-3-haiku", "gpt-4o-mini", "gemini-2.5-flash-lite"]
CEILING_PROBE = "gpt-4.1"

MODES = ["advisory", "binding"]
MODE_MODULE = {"advisory": R.ADVISORY, "binding": R.BINDING}

# --- tiers: the two FROZEN composition tiers (dev tasks only) ----------------
TIERS = {
    "k1": {
        "tier": 1, "n_bugs": 2,
        "dir": os.path.join(_V3, "tasks", "k1"),
        "split": os.path.join(_V3, "tasks", "k1", "split.json"),
        "freeze_hash": "0fd7cc51ecc24e3f6a959b064ce64ac26f29ed113c639f214eb416d48bd2c23b",
    },
    "k2": {
        "tier": 2, "n_bugs": 3,
        "dir": os.path.join(_V3, "tasks", "k2"),
        "split": os.path.join(_V3, "tasks", "k2", "split.json"),
        "freeze_hash": "0ac8644e83d3d5c21a17bccc6e32ac0d815168cfd211cabc5268e8f87f4a1a40",
    },
}
TIER_KEYS = ["k1", "k2"]

# D18 config, verbatim from the v2 runner (temp 0, step cap 8, show_description False).
D18_CONFIG = R.D18_CONFIG
PRESENTATION = R.PRESENTATION

LOGS_ROOT = os.path.join(_HERE, "logs")
MANIFEST_PATH = os.path.join(_HERE, "manifest.json")


def cell_name(model_slug, mode, tier_key):
    """Committed cell-dir name: ``<model-slug>__<mode>__k{1,2}``."""
    return "%s__%s__%s" % (model_slug, mode, tier_key)


def dev_task_ids(tier_key):
    """The tier's 10 DEV task ids (sorted). ONLY these may be opened this step."""
    with open(TIERS[tier_key]["split"], "r", encoding="utf-8") as fh:
        split = json.load(fh)
    return sorted(split["dev"])


def task_dir(tier_key, task_id):
    return os.path.join(TIERS[tier_key]["dir"], task_id)


def repo_root():
    return _REPO
