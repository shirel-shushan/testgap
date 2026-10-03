import json

from testgap import generator
from testgap.models import Gap

GAP = Gap("src/a.js", "add", 1, 3, {2})
FAIL_OUTPUT = """\
 FAIL  t.test.js > add > bad sum
AssertionError: expected 3 to be 4
 ❯ t.test.js:5:1
 FAIL  t.test.js > add > bad import
AssertionError: expected 1 to be 2
 ❯ t.test.js:9:1
"""


class FakeAdapter:
    def __init__(self):
        self.runs = [(False, FAIL_OUTPUT), (True, "ok")]

    def test_path_for(self, file, function): return "tests/a.test.js"
    def import_path_for(self, test_rel, file): return "../src/a.js"
    def example_test(self, repo): return ""
    def run_test_file(self, repo, rel): return self.runs.pop(0)
    def refresh(self): pass
    def uncovered_lines(self, repo): return {}


def test_code_bug_skipped_and_wrong_test_fixed(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.js").write_text("function add(a, b) {\n  return a - b;\n}\n")
    fix_msgs = []

    def ask(system, msg, **kw):
        if system == generator.prompts.load("classify"):
            bug = "bad sum" in msg.split("Classify only this one failing test:")[1].splitlines()[0]
            return json.dumps({"verdict": "code_bug" if bug else "test_wrong",
                               "confidence": 0.9, "explanation": "subtracts",
                               "evidence": "return a - b;", "line": 2})
        if system == generator.prompts.load("fix"):
            fix_msgs.append(msg)
        return "```javascript\ntest()\n```"

    monkeypatch.setattr(generator.llm, "ask", ask)
    result = generator.process(GAP, FakeAdapter(), tmp_path)

    assert len(fix_msgs) == 1
    assert "Change these tests to it.skip" in fix_msgs[0]
    assert '"bad sum"' in fix_msgs[0] and '"bad import"' in fix_msgs[0]
    skip_part, fix_part = fix_msgs[0].split("Fix these tests that are wrong:")
    assert "bad sum" in skip_part and "bad import" in fix_part
    assert result.status == "passed"
    assert result.bugs == ["bad sum: subtracts"]


def test_unclear_goes_to_questions_and_skip_not_bugs(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.js").write_text("function add(a, b) {\n  return a - b;\n}\n")
    fix_msgs = []

    def ask(system, msg, **kw):
        if system == generator.prompts.load("classify"):
            return json.dumps({"verdict": "unclear", "confidence": 0.4, "explanation": "is 0 allowed?"})
        if system == generator.prompts.load("fix"):
            fix_msgs.append(msg)
        return "```javascript\ntest()\n```"

    monkeypatch.setattr(generator.llm, "ask", ask)
    result = generator.process(GAP, FakeAdapter(), tmp_path)

    assert result.bugs == []
    assert result.questions == ["bad sum: is 0 allowed?"]  # same explanation, no line: deduped
    skip_part = fix_msgs[0].split("Fix these tests that are wrong:")[0]
    assert "// testgap: question - <explanation>" in skip_part
    assert '"bad sum"' in skip_part and '"bad import"' in skip_part


def _subtract_src(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.js").write_text("function add(a, b) {\n  return a - b;\n}\n")


def test_two_code_bugs_on_same_line_give_one_bug(tmp_path, monkeypatch):
    _subtract_src(tmp_path)

    def ask(system, msg, **kw):
        if system == generator.prompts.load("classify"):
            name = msg.split("Classify only this one failing test:")[1].splitlines()[0].strip()
            return json.dumps({"verdict": "code_bug", "confidence": 0.9, "explanation": f"why {name}",
                               "evidence": "return a - b;", "line": 2})
        return "```javascript\ntest()\n```"

    monkeypatch.setattr(generator.llm, "ask", ask)
    result = generator.process(GAP, FakeAdapter(), tmp_path)
    assert len(result.bugs) == 1


def test_code_bug_without_line_deduped_by_explanation(tmp_path, monkeypatch):
    _subtract_src(tmp_path)

    def ask(system, msg, **kw):
        if system == generator.prompts.load("classify"):
            return json.dumps({"verdict": "code_bug", "confidence": 0.9, "explanation": "same",
                               "evidence": "return a - b;"})
        return "```javascript\ntest()\n```"

    monkeypatch.setattr(generator.llm, "ask", ask)
    result = generator.process(GAP, FakeAdapter(), tmp_path)
    assert len(result.bugs) == 1


def _ok_adapter():
    a = FakeAdapter()
    a.runs = [(True, "ok")]
    return a


def _src(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.js").write_text("function add(a, b) {\n  return a + b;\n}\n")


def test_truncated_retries_once_with_shorter_instruction(tmp_path, monkeypatch):
    _src(tmp_path)
    gen_msgs = []

    def ask(system, msg, **kw):
        if system == generator.prompts.load("generate"):
            gen_msgs.append(msg)
            if len(gen_msgs) == 1:
                raise generator.llm.TruncatedResponse("partial")
        return "```javascript\ntest()\n```"

    monkeypatch.setattr(generator.llm, "ask", ask)
    result = generator.process(GAP, _ok_adapter(), tmp_path)
    assert len(gen_msgs) == 2
    assert "at most 20 test cases" in gen_msgs[1] and "it.each" in gen_msgs[1]
    assert "at most 20" not in gen_msgs[0]
    assert result.status == "passed"


def test_truncated_twice_gives_up(tmp_path, monkeypatch):
    _src(tmp_path)

    def ask(system, msg, **kw):
        if system == generator.prompts.load("generate"):
            raise generator.llm.TruncatedResponse("partial")
        return "spec"

    monkeypatch.setattr(generator.llm, "ask", ask)
    result = generator.process(GAP, _ok_adapter(), tmp_path)
    assert result.status == "gave_up"
    assert result.explanation == "model output truncated"


PARSE_FAIL = """\
 FAIL  tests/a.test.js [ tests/a.test.js ]
Error: Failed to parse source for import analysis because the content contains invalid JS syntax.
 \u276f TransformPluginContext._formatError node_modules/vite/x.js:1:1

\u23af\u23af\u23af Failed Suites 1 \u23af\u23af\u23af
"""


def test_load_failure_yields_no_failing_tests_and_no_classify(tmp_path, monkeypatch):
    from testgap.runlog import failing_tests
    assert failing_tests(PARSE_FAIL) == []

    _src(tmp_path)
    adapter = FakeAdapter()
    adapter.runs = [(False, PARSE_FAIL), (True, "ok")]
    systems, fix_msgs = [], []

    def ask(system, msg, **kw):
        systems.append(system)
        if system == generator.prompts.load("fix"):
            fix_msgs.append(msg)
        return "```javascript\ntest()\n```"

    monkeypatch.setattr(generator.llm, "ask", ask)
    result = generator.process(GAP, adapter, tmp_path)
    assert generator.prompts.load("classify") not in systems
    assert "failed to load" in fix_msgs[0] and "Failed to parse source" in fix_msgs[0]
    assert result.status == "passed"


def test_ask_raises_truncated_on_max_tokens(monkeypatch):
    from types import SimpleNamespace
    from testgap import llm

    resp = SimpleNamespace(content=[SimpleNamespace(text="half")], stop_reason="max_tokens")
    client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: resp))
    monkeypatch.setattr(llm, "_get_client", lambda: client)
    try:
        llm.ask("s", "u")
    except llm.TruncatedResponse as e:
        assert e.partial == "half"
    else:
        raise AssertionError("expected TruncatedResponse")
