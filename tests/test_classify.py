import json

from testgap import generator
from testgap.models import Gap

GAP = Gap("src/a.js", "add", 1, 3, {2})


def _classify(output="AssertionError: expected 1 to be 2"):
    return generator.classify(GAP, "function add(a, b) {}", "test()", output)


def _fake_llm(monkeypatch, reply):
    calls = []

    def ask(*args, **kwargs):
        calls.append(args)
        return reply

    monkeypatch.setattr(generator.llm, "ask", ask)
    return calls


def test_syntax_error_skips_llm(monkeypatch):
    calls = _fake_llm(monkeypatch, "unused")
    verdict = _classify("SyntaxError: Unexpected token")
    assert verdict.is_code_bug is False
    assert calls == []


def test_code_bug_with_high_confidence(monkeypatch):
    _fake_llm(monkeypatch, json.dumps({"verdict": "code_bug", "confidence": 0.9}))
    assert _classify().is_code_bug is True


def test_low_confidence_is_not_a_bug(monkeypatch):
    _fake_llm(monkeypatch, json.dumps({"verdict": "code_bug", "confidence": 0.5}))
    assert _classify().is_code_bug is False


def test_invalid_json_is_not_a_bug(monkeypatch):
    _fake_llm(monkeypatch, "not json at all")
    assert _classify().is_code_bug is False
