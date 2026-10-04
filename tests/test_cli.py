from testgap import cli, gaps
from testgap.models import Gap

GAPS = [
    Gap("src/a.js", "add", 1, 3, {2}),
    Gap("src/a.js", "sub", 5, 7, {6}),
    Gap("src/b.js", "mul", 1, 3, {2}),
]


class FakeAdapter:
    def uncovered_lines(self, repo): return {}
    def functions(self, repo): return []


def _run(monkeypatch, capsys, *extra):
    monkeypatch.setattr(cli, "VitestAdapter", FakeAdapter)
    monkeypatch.setattr(gaps, "find_gaps", lambda *a: list(GAPS))
    cli.main(["run", "--repo", "r", "--all", *extra])
    return capsys.readouterr().out


def test_only_filters_by_function_name(monkeypatch, capsys):
    out = _run(monkeypatch, capsys, "--only", "add,mul")
    assert " add " in out and " mul " in out and " sub " not in out


def test_without_only_all_gaps_are_listed(monkeypatch, capsys):
    out = _run(monkeypatch, capsys)
    assert " add " in out and " sub " in out and " mul " in out


def test_only_applies_to_generate(monkeypatch, capsys):
    from testgap import generator
    from testgap.models import Result

    processed = []

    def process(gap, adapter, repo, logger=None):
        processed.append(gap.function)
        return Result(gap, "passed", "", 1)

    monkeypatch.setattr(generator, "process", process)
    _run(monkeypatch, capsys, "--generate", "--only", "sub")
    assert processed == ["sub"]


def test_report_written_without_generate(monkeypatch, capsys, tmp_path):
    path = tmp_path / "report.md"
    _run(monkeypatch, capsys, "--report", str(path))
    text = path.read_text(encoding="utf-8")
    assert "3 functions checked" in text
    assert "| `src/a.js / sub` | not generated | 0 |" in text
