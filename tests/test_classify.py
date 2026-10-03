import json

from testgap import generator
from testgap.models import Gap

GAP = Gap("src/a.js", "add", 1, 3, {2})
SOURCE = "function add(a, b) {\n  return a - b;\n}\n\n\n// a - b is wrong\n"


def _classify(details="AssertionError: expected 1 to be 2"):
    return generator.classify(GAP, SOURCE, "test()", "adds", details, "spec")


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
    _fake_llm(monkeypatch, json.dumps({"verdict": "code_bug", "confidence": 0.9,
                                       "evidence": "a - b", "line": 2}))
    verdict = _classify()
    assert verdict.is_code_bug is True
    assert verdict.line == 2


def test_code_bug_with_evidence_not_in_source_becomes_unclear(monkeypatch):
    _fake_llm(monkeypatch, json.dumps({"verdict": "code_bug", "confidence": 0.9,
                                       "evidence": "return a * b;", "explanation": "x"}))
    verdict = _classify()
    assert verdict.is_code_bug is False
    assert verdict.is_unclear is True
    assert verdict.explanation.endswith("(no evidence in file)")


def test_evidence_only_on_the_faulty_line_becomes_unclear(monkeypatch):
    for line in (2, 3, 1):  # the faulty line itself or one line off
        _fake_llm(monkeypatch, json.dumps({"verdict": "code_bug", "confidence": 0.9,
                                           "evidence": "return a - b;", "line": line}))
        verdict = _classify()
        assert verdict.is_code_bug is False and verdict.is_unclear is True
        assert verdict.explanation.endswith("(evidence is the faulty line itself)")


DOC_SOURCE = ("/** Returns the sum of two numbers. */\n"
              "function add(a, b) {\n  return a - b;\n}\n")


def _classify_doc(evidence):
    gap = Gap("src/a.js", "add", 2, 4, {3})
    return generator.classify(gap, DOC_SOURCE, "test()", "adds", "AssertionError", "spec")


def test_explanation_containing_quoted_doc_comment_is_accepted(monkeypatch):
    evidence = 'The doc says "Returns the sum of two numbers." but the code subtracts'
    _fake_llm(monkeypatch, json.dumps({"verdict": "code_bug", "confidence": 0.9,
                                       "evidence": evidence, "line": 3}))
    assert _classify_doc(evidence).is_code_bug is True


def test_backtick_and_single_quote_candidates_are_accepted(monkeypatch):
    for evidence in ("doc: `Returns the sum of two numbers.` is violated",
                     "doc: 'Returns the sum of two numbers.' is violated"):
        _fake_llm(monkeypatch, json.dumps({"verdict": "code_bug", "confidence": 0.9,
                                           "evidence": evidence, "line": 3}))
        assert _classify_doc(evidence).is_code_bug is True


def test_explanation_with_nonexistent_quote_becomes_unclear(monkeypatch):
    evidence = 'The doc says "Returns the product of numbers." so this is wrong'
    _fake_llm(monkeypatch, json.dumps({"verdict": "code_bug", "confidence": 0.9,
                                       "evidence": evidence, "line": 3}))
    verdict = _classify_doc(evidence)
    assert verdict.is_code_bug is False and verdict.is_unclear is True
    assert verdict.explanation.endswith("(no evidence in file)")


def test_explanation_quoting_only_the_faulty_line_becomes_unclear(monkeypatch):
    evidence = 'The code does "return a - b;" which is wrong'
    _fake_llm(monkeypatch, json.dumps({"verdict": "code_bug", "confidence": 0.9,
                                       "evidence": evidence, "line": 3}))
    verdict = _classify_doc(evidence)
    assert verdict.is_code_bug is False and verdict.is_unclear is True
    assert verdict.explanation.endswith("(evidence is the faulty line itself)")


def test_evidence_without_line_is_accepted(monkeypatch):
    _fake_llm(monkeypatch, json.dumps({"verdict": "code_bug", "confidence": 0.9, "evidence": "return a - b;"}))
    assert _classify().is_code_bug is True


def test_code_bug_without_evidence_becomes_unclear(monkeypatch):
    _fake_llm(monkeypatch, json.dumps({"verdict": "code_bug", "confidence": 0.9}))
    verdict = _classify()
    assert verdict.is_code_bug is False and verdict.is_unclear is True


def test_low_confidence_is_not_a_bug(monkeypatch):
    _fake_llm(monkeypatch, json.dumps({"verdict": "code_bug", "confidence": 0.5, "evidence": "function add"}))
    assert _classify().is_code_bug is False


def test_unclear_verdict_sets_is_unclear(monkeypatch):
    _fake_llm(monkeypatch, json.dumps({"verdict": "unclear", "confidence": 0.3}))
    verdict = _classify()
    assert verdict.is_unclear is True
    assert verdict.is_code_bug is False


def test_invalid_json_is_not_a_bug(monkeypatch):
    _fake_llm(monkeypatch, "not json at all")
    assert _classify().is_code_bug is False


def test_message_names_single_test_with_only_its_details(monkeypatch):
    calls = _fake_llm(monkeypatch, json.dumps({"verdict": "test_wrong", "confidence": 0.9}))
    _classify("details of adds")
    msg = calls[0][1]
    assert "adds" in msg and "details of adds" in msg
