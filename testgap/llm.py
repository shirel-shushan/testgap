"""LLM client used to generate tests."""

import json
import os
import re

from anthropic import Anthropic

MODEL = os.environ.get("TESTGAP_MODEL", "claude-haiku-4-5-20251001")

_client: Anthropic | None = None


class TruncatedResponse(Exception):
    """The model hit max_tokens before finishing; ``partial`` holds what it wrote."""

    def __init__(self, partial: str = ""):
        super().__init__("model output truncated (max_tokens reached)")
        self.partial = partial


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        key = os.environ.get("TESTGAP_API_KEY")
        if not key:
            raise RuntimeError("TESTGAP_API_KEY is not set; export it to use --generate.")
        _client = Anthropic(api_key=key)
    return _client


def ask(system: str, user: str, max_tokens: int = 12000) -> str:
    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = response.content[0].text if response.content else ""
    if response.stop_reason == "max_tokens":
        raise TruncatedResponse(text)
    return text


def extract_code(text: str) -> str:
    """First ```javascript/js/plain fenced block, else the stripped text."""
    m = re.search(r"```(?:javascript|js)?[ \t]*\r?\n(.*?)```", text, re.DOTALL)
    if not m:
        return text.strip()
    # Drop leading blank lines and trailing whitespace, but keep the first line's indent
    return re.sub(r"\A\s*\n", "", m.group(1)).rstrip()


def extract_json(text: str) -> str:
    """Return the last top-level JSON object in text.

    Prefers a ```json fenced block. Otherwise scans left to right, skipping
    braces that are not valid JSON (e.g. JavaScript code), and returns the
    last object found, preferring one that has a "verdict" key."""
    fenced = re.findall(r"```json[ \t]*\r?\n(.*?)```", text, re.DOTALL)
    if fenced:
        return fenced[-1].strip()

    decoder = json.JSONDecoder()
    found = []
    i = 0
    while i < len(text):
        if text[i] == "{":
            try:
                obj, end = decoder.raw_decode(text, i)
            except ValueError:
                i += 1
                continue
            if isinstance(obj, dict):
                found.append(obj)
            i = end
        else:
            i += 1

    if not found:
        return text.strip()
    with_verdict = [o for o in found if "verdict" in o]
    return json.dumps((with_verdict or found)[-1])