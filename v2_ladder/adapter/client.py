"""V2 ladder — the model-client adapter (one ``complete`` interface, two routes).

Experiment 2 runs 7 rungs. Two of them (the v1 anchors, rungs 5 and 7) go through
the **OpenAI-direct** route; the other five go through **OpenRouter**. Both routes
present the identical ``complete(messages) -> {text, tokens_in, tokens_out, model}``
interface the v1 harnesses already expect, so the frozen Phase-3 / Phase-4 harnesses
drive either route unchanged.

Reuse discipline (no frozen v1 file is edited):

* The OpenAI-direct route delegates to v1's ``OpenAIChatClient`` **verbatim** — so its
  TLS context, its 429/5xx retry/backoff, its key resolution, and its token parsing are
  literally the v1 code path.
* The OpenRouter route runs its own ``urllib`` POST loop, but **imports** v1's
  ``_ssl_context`` (TLS trust anchors), ``_scrub`` (key-safe error text), the backoff
  shape, and — for token parsing — calls ``OpenAIChatClient._parse`` unchanged. The key
  comes from ``v2_ladder/adapter/keys.py`` (``resolve_openrouter_key``).

Every rung records its ``provider`` and ``route``; every call records ``tokens_in``,
``tokens_out``, and a per-call ``cost`` at the rung's registered per-1M prices. The
OpenRouter route also stashes the last raw ``usage`` block and the assistant
``reasoning`` field (if any) so the rung-6 reasoning-free smoke can inspect them. The
request body is **exactly** ``{model, temperature, messages}`` on both routes — no
``reasoning``/thinking parameter is ever sent (this is what makes the rung-6 check a
faithful test of the default behavior). Keys are never printed or logged.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

# --- wire up v1 helpers (frozen; imported, never edited) --------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_PHASE3 = os.path.join(_REPO_ROOT, "phase3_advisory")
if _PHASE3 not in sys.path:
    sys.path.insert(0, _PHASE3)

from providers import (  # noqa: E402  (path set up above)
    OpenAIChatClient,
    _scrub,
    _ssl_context,
)
from keys import resolve_openrouter_key  # noqa: E402  (sibling module)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


# ---------------------------------------------------------------------------
# The ladder (rank 1 = weakest … rank 7 = strongest), fixed by PREREGISTRATION.md.
# ``pin`` / ``pout`` are USD per 1,000,000 tokens (in / out) as registered in §(a)/§(e).
# ``slug`` is the filesystem-safe cell-dir prefix (model IDs contain '/').
# ---------------------------------------------------------------------------
RUNGS = [
    {"rank": 1, "slug": "rung1_llama-3.2-3b",           "model": "meta-llama/llama-3.2-3b-instruct", "route": "openrouter", "provider": "Meta",         "pin": 0.05, "pout": 0.33},
    {"rank": 2, "slug": "rung2_llama-3.1-8b",           "model": "meta-llama/llama-3.1-8b-instruct", "route": "openrouter", "provider": "Meta",         "pin": 0.05, "pout": 0.08},
    {"rank": 3, "slug": "rung3_qwen2.5-7b",             "model": "qwen/qwen-2.5-7b-instruct",        "route": "openrouter", "provider": "Alibaba/Qwen", "pin": 0.04, "pout": 0.10},
    {"rank": 4, "slug": "rung4_claude-3-haiku",         "model": "anthropic/claude-3-haiku",         "route": "openrouter", "provider": "Anthropic",    "pin": 0.25, "pout": 1.25},
    {"rank": 5, "slug": "rung5_gpt-4o-mini",            "model": "gpt-4o-mini-2024-07-18",           "route": "openai",     "provider": "OpenAI",       "pin": 0.15, "pout": 0.60},
    {"rank": 6, "slug": "rung6_gemini-2.5-flash-lite",  "model": "google/gemini-2.5-flash-lite",     "route": "openrouter", "provider": "Google",       "pin": 0.10, "pout": 0.40},
    # Rung 7's registered snapshot is gpt-4.1-2025-04-14. The project has access to it
    # ONLY via the alias `gpt-4.1` (a direct snapshot-ID request 403s), which resolves to
    # exactly that snapshot — this is precisely how v1 ran the strong anchor (v1
    # config.model='gpt-4.1', every v1 log resolved to 'gpt-4.1-2025-04-14'). So the
    # request id is the alias; the registered snapshot is what actually executes.
    {"rank": 7, "slug": "rung7_gpt-4.1", "model": "gpt-4.1-2025-04-14", "request_id": "gpt-4.1", "route": "openai", "provider": "OpenAI", "pin": 2.00, "pout": 8.00},
]

RUNGS_BY_SLUG = {r["slug"]: r for r in RUNGS}


def episode_cost(tokens_in, tokens_out, rung):
    """USD cost of an episode given its token totals and the rung's per-1M prices."""
    return (tokens_in / 1_000_000.0) * rung["pin"] + (tokens_out / 1_000_000.0) * rung["pout"]


def _reasoning_from(body):
    """Return (reasoning_text, reasoning_tokens) discovered in an OpenRouter response.

    OpenRouter surfaces optional thinking either as a non-empty ``message.reasoning``
    string or as ``usage.completion_tokens_details.reasoning_tokens`` (mirroring the
    OpenAI reasoning-model shape). We look in both places; a plain chat model leaves
    both empty/zero.
    """
    reasoning_text = ""
    try:
        msg = body["choices"][0]["message"]
        reasoning_text = msg.get("reasoning") or msg.get("reasoning_content") or ""
    except Exception:
        pass
    reasoning_tokens = 0
    usage = body.get("usage", {}) or {}
    details = usage.get("completion_tokens_details", {}) or {}
    for k in ("reasoning_tokens", "reasoning"):
        v = details.get(k) or usage.get(k)
        if isinstance(v, int):
            reasoning_tokens = max(reasoning_tokens, v)
    return reasoning_text, reasoning_tokens


class LadderClient:
    """One rung's client. ``complete(messages)`` returns the v1-shaped response dict.

    ``model`` is the exact snapshot ID (what the harness logs). ``route`` / ``provider``
    are recorded for the manifest. ``temperature`` is fixed to 0 (temp-0 protocol). The
    request body is only ``{model, temperature, messages}``.
    """

    def __init__(self, rung, timeout=60, max_attempts=5, base_backoff=1.0):
        self.rung = rung
        # ``snapshot`` is the registered rung model; ``model`` is the API request id
        # (identical except rung 7, where the registered snapshot is reached via its
        # alias). The harness logs ``self.model``; the resolved snapshot appears in each
        # model_response's ``model`` field (from the API), mirroring v1 exactly.
        self.snapshot = rung["model"]
        self.model = rung.get("request_id", rung["model"])
        self.route = rung["route"]
        self.provider = rung["provider"]
        self.pin = rung["pin"]
        self.pout = rung["pout"]
        self.temperature = 0
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.base_backoff = base_backoff
        # rung-6 introspection: raw usage + reasoning of the last OpenRouter call
        self.last_usage = None
        self.last_reasoning_text = ""
        self.last_reasoning_tokens = 0
        # OpenAI-direct route: delegate verbatim to the frozen v1 client.
        self._openai = None
        if self.route == "openai":
            self._openai = OpenAIChatClient({"model": self.model, "temperature": 0})
        else:
            self._key = None
            self._ssl = None

    # -- OpenRouter route (own loop; reuses v1 TLS/backoff/scrub/parse) --------
    def _openrouter_key(self):
        if self._key is None:
            self._key = resolve_openrouter_key()
        return self._key

    def _context(self):
        if self._ssl is None:
            self._ssl = _ssl_context()
        return self._ssl

    def _complete_openrouter(self, messages):
        payload = json.dumps(
            {"model": self.model, "temperature": self.temperature, "messages": messages}
        ).encode("utf-8")

        last_err = None
        for attempt in range(1, self.max_attempts + 1):
            req = urllib.request.Request(
                OPENROUTER_URL,
                data=payload,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self._openrouter_key(),
                },
            )
            try:
                with urllib.request.urlopen(
                    req, timeout=self.timeout, context=self._context()
                ) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                # rung-6 introspection before we discard the raw body
                self.last_usage = body.get("usage", {}) or {}
                self.last_reasoning_text, self.last_reasoning_tokens = _reasoning_from(body)
                return OpenAIChatClient._parse(body)  # reuse v1 token parsing verbatim
            except urllib.error.HTTPError as exc:
                code = exc.code
                if code == 429 or 500 <= code < 600:
                    last_err = code
                    if attempt < self.max_attempts:
                        time.sleep(self.base_backoff * (2 ** (attempt - 1)))
                        continue
                try:
                    detail = exc.read().decode("utf-8", "replace")
                except Exception:
                    detail = ""
                raise RuntimeError(
                    _scrub("OpenRouter request failed (HTTP %d): %s" % (code, detail[:500]))
                )
            except urllib.error.URLError as exc:
                last_err = exc
                if attempt < self.max_attempts:
                    time.sleep(self.base_backoff * (2 ** (attempt - 1)))
                    continue
                raise RuntimeError(_scrub("OpenRouter request failed (network): %s" % exc.reason))

        raise RuntimeError(
            "OpenRouter request failed after %d attempts (last: %s)"
            % (self.max_attempts, _scrub(last_err))
        )

    # -- unified interface ----------------------------------------------------
    def complete(self, messages):
        if self.route == "openai":
            return self._openai.complete(messages)
        return self._complete_openrouter(messages)


def make_client(rung_or_slug):
    """Build a LadderClient from a rung dict or its slug."""
    rung = rung_or_slug if isinstance(rung_or_slug, dict) else RUNGS_BY_SLUG[rung_or_slug]
    return LadderClient(rung)
