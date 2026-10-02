"""LLM client used to generate tests."""

import os
import re

from anthropic import Anthropic

MODEL = os.environ.get("TESTGAP_MODEL", "claude-haiku-4-5-20251001")

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        key = os.environ.get("TESTGAP_API_KEY")
        if not key:
            raise RuntimeError("TESTGAP_API_KEY is not set; export it to use --generate.")
        _client = Anthropic(api_key=key)
    return _client


def ask(system: str, user: str, max_tokens: int = 4000) -> str:
    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=0,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def extract_code(text: str) -> str:
    """First ```javascript/js/plain fenced block, else the stripped text."""
    m = re.search(r"```(?:javascript|js)?[ \t]*\r?\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def extract_json(text: str) -> str:
    """First {...} block (outermost braces, greedy), else the stripped text."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return m.group(0) if m else text.strip()
