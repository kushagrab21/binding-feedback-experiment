"""V2 ladder — OpenRouter API-key resolution (never leaks the value).

Experiment 2 routes the ladder rungs through OpenRouter while the two v1 anchors
keep the existing OpenAI direct route. This module adds an ``OPENROUTER_API_KEY``
resolver with the SAME strict discipline as v1's OpenAI resolver, and — critically —
**without editing any frozen v1 file**. The PDF/CMap extraction, the sibling-folder
walk, and the scrub helper are imported from ``phase3_advisory/providers.py`` and
reused verbatim; only the env-var names and an OpenRouter-prefix filter are new.

Resolution order (mirrors v1):

1. env ``OPENROUTER_API_KEY``;
2. env ``OPENROUTER_API_KEY_FILE`` (a path to a file holding the key; PDF-aware);
3. the first file under a sibling ``API*/`` folder that yields an **OpenRouter**
   key — router-named files are tried first, and a candidate is accepted only if
   the recovered token carries the OpenRouter prefix (``sk-or-``). This is what
   disambiguates the OpenRouter key file from the OpenAI key file that lives in the
   same ``api_key/`` folder.

The key is NEVER printed, logged, written under the repo, or placed in an error
message. No network call is made here — resolution is offline; smoke calls come at
V2-P2.
"""

import os
import sys

# Import v1's helpers WITHOUT modifying the frozen module. providers.py resolves no
# key at import time (resolution is lazy), so this import is side-effect free.
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_PHASE3 = os.path.join(_REPO_ROOT, "phase3_advisory")
if _PHASE3 not in sys.path:
    sys.path.insert(0, _PHASE3)

from providers import (  # noqa: E402  (path set up above)
    _api_folder_files,
    _read_key_file,
    _scrub,
)

# OpenRouter keys carry a distinctive prefix (``sk-or-v1-…``). Assembled by
# concatenation so no key-shaped literal ever appears in tracked source.
_OR_PREFIX = "sk-" + "or-"


def _looks_like_openrouter(token):
    return isinstance(token, str) and token.startswith(_OR_PREFIX)


def resolve_openrouter_key():
    """Resolve the OpenRouter key per the strict order. Returns the key string.

    Raises ``RuntimeError`` (with no key material in the message) if none is found.
    """
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key.strip()

    key_file = os.environ.get("OPENROUTER_API_KEY_FILE")
    if key_file:
        token = _read_key_file(key_file)
        if token:
            return token
        raise RuntimeError("OPENROUTER_API_KEY_FILE was set but no key could be read from it")

    # Sibling API*/ folder. The folder holds BOTH the OpenAI key file and the
    # OpenRouter key file, so we (a) try router-named files first and (b) accept a
    # candidate only when the recovered token has the OpenRouter prefix — this
    # guarantees we never hand back the OpenAI key for an OpenRouter request.
    def _router_first(path):
        base = os.path.basename(path).lower()
        return (0 if ("router" in base) else 1, base)

    last_exc = None
    for path in sorted(_api_folder_files(), key=_router_first):
        try:
            token = _read_key_file(path)
        except Exception as exc:  # noqa: BLE001 - try the next candidate
            last_exc = exc
            continue
        if _looks_like_openrouter(token):
            return token

    if last_exc is not None:
        raise RuntimeError("found a sibling API*/ file but could not read an OpenRouter key from it")
    raise RuntimeError(
        "no OpenRouter API key found: set OPENROUTER_API_KEY, or OPENROUTER_API_KEY_FILE, "
        "or place an OpenRouter key file (sk-or-…) under a sibling API*/ folder"
    )


__all__ = ["resolve_openrouter_key", "_scrub"]
