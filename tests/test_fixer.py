import pytest

from testgap import fixer
from testgap.models import Gap

SRC = "const x = 1;\nfunction add(a, b) {\n  return a - b;\n}\nexport { add };\n"
GAP = Gap("src/a.js", "add", 2, 4, {3})
BUG = "bad sum: subtracts"
TEST = (
    "it.skip('bad sum', () => {});\n"
    "it.skip('bad sum two', () => {});\n"
    "it.skip(\"other\", () => {});\n"
)


class Adapter:
    def __init__(self, new=(True, "ok"), old=(True, "ok"), boom=False):
        self.new, self.old, self.boom = new, old, boom
        self.seen_test = None
        self.seen_src = None

    def test_path_for(self, f, fn): return "tests/generated/a.add.test.js"

    def run_test_file(self, repo, rel):
        self.seen_test = (repo / rel).read_text()
        self.seen_src = (repo / "src/a.js").read_text()
        if self.boom:
            raise RuntimeError("boom")
        return self.new

    def run_existing_suite(self, repo): return self.old


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/a.js").write_text(SRC, newline="")
    monkeypatch.setattr(fixer.llm, "ask",
                        lambda *a, **k: "```javascript\nfunction add(a, b) {\n  return a + b;\n}\n```")
    return tmp_path


def run(repo, adapter):
    return fixer.suggest_fix(GAP, SRC, BUG, TEST, adapter, repo)


def read_src(repo):
    return (repo / "src/a.js").read_bytes().decode()


def test_source_restored_and_patched_during_run(repo):
    a = Adapter()
    res = run(repo, a)
    assert read_src(repo) == SRC
    assert "return a + b;" in a.seen_src and "export { add };" in a.seen_src
    assert "-  return a - b;" in res["diff"] and "+  return a + b;" in res["diff"]
    assert not (repo / "tests/generated/a.add.fix.test.js").exists()


def test_indented_reply_diff_is_one_line(repo, monkeypatch):
    reply = "    function add(a, b) {\n      return a + b;\n    }"
    monkeypatch.setattr(fixer.llm, "ask", lambda *a, **k: "```javascript\n" + reply + "\n```")
    res = run(repo, Adapter())
    changed = [l for l in res["diff"].splitlines()
               if l[:1] in "+-" and not l.startswith(("---", "+++"))]
    assert changed == ["-  return a - b;", "+  return a + b;"]


def test_source_restored_when_run_raises(repo):
    with pytest.raises(RuntimeError):
        run(repo, Adapter(boom=True))
    assert read_src(repo) == SRC
    assert not (repo / "tests/generated/a.add.fix.test.js").exists()


@pytest.mark.parametrize("new,old,expected", [
    ((True, ""), (True, ""), True),
    ((False, "x"), (True, ""), False),
    ((True, ""), (False, "x"), False),
])
def test_verified_needs_both(repo, new, old, expected):
    res = run(repo, Adapter(new=new, old=old))
    assert res["verified"] is expected
    assert bool(res["output"]) is (not expected)


def test_only_named_test_unskipped(repo):
    a = Adapter()
    run(repo, a)
    assert "it('bad sum'," in a.seen_test
    assert "it.skip('bad sum two'" in a.seen_test
    assert 'it.skip("other"' in a.seen_test


def test_truncated_returns_none(repo, monkeypatch):
    def ask(*a, **k): raise fixer.llm.TruncatedResponse("x")
    monkeypatch.setattr(fixer.llm, "ask", ask)
    assert run(repo, Adapter()) is None
