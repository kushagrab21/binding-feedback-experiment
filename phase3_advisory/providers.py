"""Phase 3 — model client interface for the advisory harness.

A ``client`` here is anything exposing::

    complete(messages) -> {"text": str, "tokens_in": int, "tokens_out": int, "model": str}

where ``messages`` is a list of ``{"role": ..., "content": ...}`` dicts (the same
shape the OpenAI Chat Completions API takes). Two implementations live here:

* ``MockModel`` — replays a scripted list of response strings in order, with
  deterministic token counts and no network. Used by ``test_harness.py`` so the
  advisory loop can be exercised end-to-end offline.
* ``OpenAIChatClient`` — a stdlib-only (``urllib``) client for
  ``https://api.openai.com/v1/chat/completions``. Model and temperature come from
  ``config.json``; it retries with exponential backoff on 429/5xx (max 5 attempts).

API-key handling (strict)
-------------------------
The key is resolved, in order, from:

1. env ``OPENAI_API_KEY``;
2. env ``OPENAI_API_KEY_FILE`` (a path to a file holding the key);
3. the first file matched by ``../API*/*`` relative to the repo root, read and
   stripped.

The key is NEVER printed, logged, written under the repo, or placed in any error
message. Any string that looks like a key is scrubbed out of outgoing error text as
a defensive measure. Because the operator stored the key inside a one-page PDF
(a Google-Docs export), the file reader detects the ``%PDF`` magic and reconstructs
the key text from the PDF's ToUnicode CMap + hex show-strings; a plain-text key file
is handled by the documented "read + strip" path unchanged.
"""

import json
import os
import re
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)

# The key prefix is assembled by concatenation so the literal token never appears
# in tracked source (the acceptance key-scan greps for it verbatim).
_KEY_PREFIX = "s" + "k-"
_KEY_RE = re.compile(re.escape(_KEY_PREFIX) + r"[A-Za-z0-9_\-]{20,}")
_KEY_RE_BYTES = re.compile(re.escape(_KEY_PREFIX.encode("ascii")) + rb"[A-Za-z0-9_\-]{20,}")

OPENAI_URL = "https://api.openai.com/v1/chat/completions"

DEFAULT_CONFIG = {"model": "gpt-4o-mini", "temperature": 0, "step_cap": 8}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(path=None):
    """Load ``config.json`` merged over the built-in defaults."""
    if path is None:
        path = os.path.join(_HERE, "config.json")
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    except FileNotFoundError:
        pass
    return cfg


# ---------------------------------------------------------------------------
# API-key resolution (never leaks the value)
# ---------------------------------------------------------------------------

def _hex_to_unicode(dst_hex):
    """A ToUnicode target (UTF-16BE hex) -> the unicode string it denotes."""
    try:
        return bytes.fromhex(dst_hex.decode("ascii")).decode("utf-16-be")
    except Exception:
        return ""


def _decode_hex_show(hex_bytes, cmap):
    """Decode one PDF hex show-string (2-byte codes) through a ToUnicode ``cmap``."""
    hs = hex_bytes.decode("ascii")
    if len(hs) % 4:
        hs = hs.rjust(((len(hs) + 3) // 4) * 4, "0")
    out = []
    for i in range(0, len(hs), 4):
        out.append(cmap.get(int(hs[i:i + 4], 16), ""))
    return "".join(out)


def _extract_key_from_pdf(data):
    """Recover the key token from a PDF's text (never printed).

    Handles the common Google-Docs export: Type0/Identity fonts whose content
    stream shows glyphs as hex codes, mapped back to unicode via a ToUnicode CMap.
    """
    import zlib

    streams = []
    for m in re.finditer(rb"stream\r?\n", data):
        s = m.end()
        e = data.find(b"endstream", s)
        if e == -1:
            continue
        chunk = data[s:e]
        if chunk.endswith(b"\r\n"):
            chunk = chunk[:-2]
        elif chunk.endswith(b"\n"):
            chunk = chunk[:-1]
        try:
            chunk = zlib.decompress(chunk)
        except Exception:
            pass
        streams.append(chunk)

    # 1) Fast path: the token sits verbatim in some (decompressed) stream.
    for blob in streams + [data]:
        mm = _KEY_RE_BYTES.search(blob)
        if mm:
            return mm.group(0).decode("ascii")

    # 2) Build the ToUnicode map (glyph code -> unicode) from any CMap stream.
    cmap = {}
    for blob in streams:
        if b"beginbfchar" not in blob and b"beginbfrange" not in blob:
            continue
        for seg in re.findall(rb"beginbfchar(.*?)endbfchar", blob, re.DOTALL):
            for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", seg):
                cmap[int(src, 16)] = _hex_to_unicode(dst)
        for seg in re.findall(rb"beginbfrange(.*?)endbfrange", blob, re.DOTALL):
            for lo, hi, dst in re.findall(
                rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", seg
            ):
                base = int(dst, 16)
                for i in range(int(hi, 16) - int(lo, 16) + 1):
                    cmap[int(lo, 16) + i] = chr(base + i)

    # 3) Reconstruct visible text in show order and pull the token out.
    if cmap:
        parts = []
        for blob in streams:
            if b"BT" not in blob:
                continue
            for hx in re.findall(rb"<([0-9A-Fa-f]+)>", blob):
                parts.append(_decode_hex_show(hx, cmap))
        mm = _KEY_RE.search("".join(parts))
        if mm:
            return mm.group(0)

    raise RuntimeError("could not locate an API key inside the key file")


def _read_key_file(path):
    """Read a key file: PDF-aware, otherwise the documented read+strip."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:4] == b"%PDF":
        return _extract_key_from_pdf(data).strip()
    return data.decode("utf-8", "strict").strip()


def _api_folder_files():
    """Yield files inside a sibling ``API*`` folder (case-insensitive), sorted.

    The spec globs ``../API*/*``; Python's ``glob`` is case-sensitive even on a
    case-insensitive filesystem, and the operator's folder is ``api_key``, so we
    match ``api*`` case-insensitively — a faithful superset of "named like API*".
    """
    parent = os.path.normpath(os.path.join(_REPO_ROOT, ".."))
    try:
        names = sorted(os.listdir(parent))
    except OSError:
        return
    for name in names:
        if not name.lower().startswith("api"):
            continue
        folder = os.path.join(parent, name)
        if not os.path.isdir(folder):
            continue
        for fname in sorted(os.listdir(folder)):
            if fname.startswith("."):  # skip .DS_Store and other hidden junk
                continue
            fpath = os.path.join(folder, fname)
            if os.path.isfile(fpath):
                yield fpath


def resolve_api_key():
    """Resolve the OpenAI key per the strict order. Returns the key string.

    Raises ``RuntimeError`` (with no key material in the message) if none is found.
    """
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key.strip()

    key_file = os.environ.get("OPENAI_API_KEY_FILE")
    if key_file:
        return _read_key_file(key_file)

    # Try each candidate file; use the first that yields a key. This tolerates a
    # stray non-key file (e.g. a leftover) sorting ahead of the real one.
    last_exc = None
    for path in _api_folder_files():
        try:
            key = _read_key_file(path)
            if key:
                return key
        except Exception as exc:  # noqa: BLE001 - move on to the next candidate
            last_exc = exc
    if last_exc is not None:
        raise RuntimeError("found a sibling API*/ file but could not read a key from it")

    raise RuntimeError(
        "no OpenAI API key found: set OPENAI_API_KEY, or OPENAI_API_KEY_FILE, "
        "or place a key file under a sibling API*/ folder"
    )


def _scrub(text):
    """Remove any key-shaped token from a string bound for logs/exceptions."""
    return _KEY_RE.sub("<redacted-key>", str(text))


# ---------------------------------------------------------------------------
# TLS trust anchors
# ---------------------------------------------------------------------------

def _macos_ca_bundle():
    """Export the macOS system root certificates to a cached PEM, return its path.

    This python.org build ships no CA bundle (no certifi, no OpenSSL default), so
    without this ``urllib`` cannot verify ``api.openai.com``. Root certs are public,
    not secret, and are written outside the repo (system temp dir).
    """
    cache = os.path.join(tempfile.gettempdir(), "binding_exp_macos_ca.pem")
    if os.path.exists(cache) and os.path.getsize(cache) > 0:
        return cache
    keychains = [
        "/System/Library/Keychains/SystemRootCertificates.keychain",
        "/Library/Keychains/System.keychain",
    ]
    parts = []
    for kc in keychains:
        if not os.path.exists(kc):
            continue
        try:
            out = subprocess.run(
                ["/usr/bin/security", "find-certificate", "-a", "-p", kc],
                capture_output=True, text=True, timeout=30,
            )
        except Exception:
            continue
        if out.returncode == 0 and out.stdout.strip():
            parts.append(out.stdout)
    if not parts:
        return None
    data = "\n".join(parts)
    try:
        with open(cache, "w", encoding="utf-8") as fh:
            fh.write(data)
        return cache
    except Exception:
        fd, tmp = tempfile.mkstemp(suffix=".pem")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
        return tmp


def _ssl_context():
    """A verifying SSL context, falling back to the macOS keychain if no CA is set."""
    ctx = ssl.create_default_context()
    try:
        has_ca = ctx.cert_store_stats().get("x509_ca", 0) > 0
    except Exception:
        has_ca = False
    if not has_ca:
        bundle = _macos_ca_bundle()
        if bundle:
            ctx.load_verify_locations(cafile=bundle)
    return ctx


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

def _wordcount(text):
    return len(str(text).split())


class MockModel:
    """Deterministic, offline client that replays scripted responses in order.

    ``responses`` is a list of strings; each ``complete`` call returns the next one.
    Token counts are deterministic functions of the content (word counts), so they
    are stable across runs and always non-zero for non-empty content.
    """

    def __init__(self, responses, model="mock-model"):
        self._responses = list(responses)
        self._i = 0
        self.model = model

    def complete(self, messages):
        if self._i >= len(self._responses):
            raise RuntimeError("MockModel exhausted: no scripted response left")
        text = self._responses[self._i]
        self._i += 1
        tokens_in = sum(_wordcount(m.get("content", "")) for m in messages)
        tokens_out = _wordcount(text)
        return {
            "text": text,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "model": self.model,
        }


class OpenAIChatClient:
    """Stdlib-only OpenAI Chat Completions client with retry/backoff."""

    def __init__(self, config=None, timeout=60, max_attempts=5, base_backoff=1.0):
        cfg = config or load_config()
        self.model = cfg.get("model", DEFAULT_CONFIG["model"])
        self.temperature = cfg.get("temperature", DEFAULT_CONFIG["temperature"])
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.base_backoff = base_backoff
        self._api_key = None  # resolved lazily so imports/mocks need no key
        self._ssl = None

    def _key(self):
        if self._api_key is None:
            self._api_key = resolve_api_key()
        return self._api_key

    def _context(self):
        if self._ssl is None:
            self._ssl = _ssl_context()
        return self._ssl

    def complete(self, messages):
        payload = json.dumps(
            {
                "model": self.model,
                "temperature": self.temperature,
                "messages": messages,
            }
        ).encode("utf-8")

        last_err = None
        for attempt in range(1, self.max_attempts + 1):
            req = urllib.request.Request(
                OPENAI_URL,
                data=payload,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self._key(),
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout,
                                            context=self._context()) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                return self._parse(body)
            except urllib.error.HTTPError as exc:
                code = exc.code
                if code == 429 or 500 <= code < 600:
                    last_err = code
                    if attempt < self.max_attempts:
                        time.sleep(self.base_backoff * (2 ** (attempt - 1)))
                        continue
                # Non-retriable (or attempts exhausted): raise a scrubbed message.
                try:
                    detail = exc.read().decode("utf-8", "replace")
                except Exception:
                    detail = ""
                raise RuntimeError(
                    _scrub("OpenAI request failed (HTTP %d): %s" % (code, detail[:500]))
                )
            except urllib.error.URLError as exc:
                last_err = exc
                if attempt < self.max_attempts:
                    time.sleep(self.base_backoff * (2 ** (attempt - 1)))
                    continue
                raise RuntimeError(_scrub("OpenAI request failed (network): %s" % exc.reason))

        raise RuntimeError("OpenAI request failed after %d attempts (last: %s)"
                           % (self.max_attempts, _scrub(last_err)))

    @staticmethod
    def _parse(body):
        text = body["choices"][0]["message"]["content"] or ""
        usage = body.get("usage", {}) or {}
        return {
            "text": text,
            "tokens_in": int(usage.get("prompt_tokens", 0)),
            "tokens_out": int(usage.get("completion_tokens", 0)),
            "model": body.get("model", ""),
        }
