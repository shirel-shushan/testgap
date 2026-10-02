import json
from pathlib import Path

import pytest

from testgap.adapters.vitest import VitestAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "coverage-final.json"


class FakeVitestAdapter(VitestAdapter):
    """Skips running vitest; counts how often coverage would have run."""

    def __init__(self):
        super().__init__()
        self.runs = 0

    def _run_coverage(self, root):
        self.runs += 1


def _json_str(p: Path) -> str:
    # Native absolute path escaped for embedding in a JSON string.
    return json.dumps(str(p))[1:-1]


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "coverage").mkdir(parents=True)
    text = (
        FIXTURE.read_text(encoding="utf-8")
        .replace("__REPO__", _json_str(repo))
        .replace("__OUTSIDE__", _json_str(tmp_path / "elsewhere"))
    )
    (repo / "coverage" / "coverage-final.json").write_text(text, encoding="utf-8")
    return repo


def test_paths_normalized_to_repo_relative_posix(repo):
    uncovered = FakeVitestAdapter().uncovered_lines(repo)
    assert set(uncovered) == {"src/pricing.js", "src/util/strings.js"}


def test_files_outside_repo_are_dropped(repo):
    assert not any(f.endswith("other.js") for f in FakeVitestAdapter().functions(repo))


def test_uncovered_lines_from_zero_count_statements(repo):
    uncovered = FakeVitestAdapter().uncovered_lines(repo)
    # statement 1 spans lines 6-8, statement 2 is line 9; both have count 0
    assert uncovered["src/pricing.js"] == {6, 7, 8, 9}
    assert uncovered["src/util/strings.js"] == set()


def test_functions_from_fnmap(repo):
    fns = FakeVitestAdapter().functions(repo)
    assert fns["src/pricing.js"] == [
        ("roundMoney", 1, 3),
        ("applyDiscount", 5, 10),
        ("total", 12, 14),
    ]
    assert fns["src/util/strings.js"] == []


def test_coverage_runs_once_per_instance(repo):
    adapter = FakeVitestAdapter()
    adapter.uncovered_lines(repo)
    adapter.functions(repo)
    adapter.uncovered_lines(str(repo))
    assert adapter.runs == 1


def test_test_path_for():
    assert VitestAdapter().test_path_for("src/pricing.js", "applyDiscount") == (
        "tests/generated/pricing.applyDiscount.test.js"
    )
