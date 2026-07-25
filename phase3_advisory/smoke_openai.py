"""Phase 3.1 — a single live OpenAI call to prove the client + key wiring work.

Sends one trivial request ("Reply with exactly OK") and prints the model id and
token usage on success. It NEVER prints the API key. Cost is a fraction of a cent.

Run from the repo root:  ``python3 phase3_advisory/smoke_openai.py``
"""

import sys

from providers import OpenAIChatClient, load_config


def main():
    client = OpenAIChatClient(load_config())
    result = client.complete(
        [
            {"role": "system", "content": "You are a terse assistant."},
            {"role": "user", "content": "Reply with exactly OK"},
        ]
    )
    text = (result.get("text") or "").strip()
    print("model:", result.get("model"))
    print("tokens_in:", result.get("tokens_in"), "tokens_out:", result.get("tokens_out"))
    print("reply:", repr(text))
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
