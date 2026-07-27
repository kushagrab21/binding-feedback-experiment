"""V3 full run — shared config (roster, tiers, TEST-split resolution, paths).

This is the ONE place the full-run roster (6 models), the two composition tiers, the
D18 config, and the log/manifest layout are named, so the per-cell runner
(``run_one_cell_full.py``) and the orchestrator (``run_full_v3.py``) cannot drift.

Everything model-facing is the **v2 adapter, verbatim**: the roster is exactly six of
v2's frozen ``RUNGS`` dicts, selected by slug, so their snapshots, routes, providers,
and per-1M prices are byte-identical to what v2's manifests recorded. No frozen
v1/v2/v3 file is edited; this module only *imports* and *selects*.

Roster (6 models — PREREGISTRATION §2):
  bottom-edge anchor : llama-3.1-8b
  window             : qwen-2.5-7b, claude-3-haiku, gpt-4o-mini, gemini-2.5-flash-lite
  top anchor         : gpt-4.1
(``llama-3.2-3b`` is DROPPED — a logged roster decision; below the window at k=0.)

Tiers k1 (2 bugs) and k2 (3 bugs); **TEST tasks only** — each tier's
``split.json['test']`` (k1 = 60, k2 = 48). The dev tasks are calibration-only.
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

# --- roster: six v2 rungs selected by slug (dicts reused verbatim) -----------
# Ordered weakest -> strongest so the committed tables read bottom-edge -> top.
ROSTER = [
    ("llama-3.1-8b",          "rung2_llama-3.1-8b"),          # bottom-edge anchor
    ("qwen-2.5-7b",           "rung3_qwen2.5-7b"),            # window
    ("claude-3-haiku",        "rung4_claude-3-haiku"),        # window
    ("gpt-4o-mini",           "rung5_gpt-4o-mini"),           # window
    ("gemini-2.5-flash-lite", "rung6_gemini-2.5-flash-lite"), # window
    ("gpt-4.1",               "rung7_gpt-4.1"),               # top anchor
]
MODEL_SLUGS = [m for m, _ in ROSTER]
RUNG_BY_MODEL = {m: C.RUNGS_BY_SLUG[slug] for m, slug in ROSTER}
WINDOW_MODELS = ["qwen-2.5-7b", "claude-3-haiku", "gpt-4o-mini", "gemini-2.5-flash-lite"]
BOTTOM_ANCHOR = "llama-3.1-8b"
TOP_ANCHOR = "gpt-4.1"

MODES = ["advisory", "binding"]
MODE_MODULE = {"advisory": R.ADVISORY, "binding": R.BINDING}

# --- tiers: the two FROZEN composition tiers (TEST tasks only) ---------------
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

# Pre-registration commit (tag v3-prereg) — recorded into every manifest.
PREREG_TAG_COMMIT = "89c4621b6bcf89831310f694cb913192c46b9e3e"

# deviation V3-D1 — the courier's publish-gate waiver, quoted verbatim.
V3_D1_WAIVER = {
    "id": "V3-D1",
    "what": "P4 gate condition (b) — courier's publish confirmation — WAIVED by the courier.",
    "courier_verbatim": "ya I waive the gate",
    "runner": "Runner-accepted; the write-up's publication is tracked outside the experiment.",
}

LOGS_ROOT = os.path.join(_HERE, "logs", "full")
MANIFESTS_ROOT = os.path.join(_HERE, "manifests")
MANIFESTS_CELL_DIR = os.path.join(MANIFESTS_ROOT, "full")
MASTER_MANIFEST_PATH = os.path.join(MANIFESTS_ROOT, "full_master.json")


def cell_name(model_slug, mode, tier_key):
    """Committed cell-dir name: ``<model-slug>__<mode>__k{1,2}``."""
    return "%s__%s__%s" % (model_slug, mode, tier_key)


def test_task_ids(tier_key):
    """The tier's TEST task ids (sorted). These are the confirmatory tasks."""
    with open(TIERS[tier_key]["split"], "r", encoding="utf-8") as fh:
        split = json.load(fh)
    return sorted(split["test"])


def task_dir(tier_key, task_id):
    return os.path.join(TIERS[tier_key]["dir"], task_id)


def repo_root():
    return _REPO
