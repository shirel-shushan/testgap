from testgap.models import Gap, Result
from testgap.report import render_markdown

GAP = Gap("src/math.js", "average", 1, 5, {3})


def test_no_gaps():
    out = render_markdown([])
    assert out.startswith("# testgap report")
    assert "No untested changes found." in out
    assert "| Function |" not in out


def test_one_passed_result():
    out = render_markdown([Result(GAP, "passed", "code", 2)])
    assert "1 functions checked, 1 tests added, 0 bugs, 0 questions." in out
    assert "| Function | Result | Attempts |" in out
    assert "| `src/math.js / average` | passed | 2 |" in out
    assert "Suspected bug" not in out


def test_bug_with_verified_fix_renders_diff_block():
    bug = "loop skips the last element"
    diff = "--- a/src/math.js\n+++ b/src/math.js\n-  for (i = 0; i < n - 1; i++)\n+  for (i = 0; i < n; i++)\n"
    result = Result(GAP, "gave_up", "code", 3, bugs=[bug], questions=["empty input?"],
                    fixes=[{"bug": bug, "diff": diff, "verified": True, "output": ""}])
    out = render_markdown([result])
    assert "1 bugs, 1 questions" in out
    assert "**Suspected bug** in `src/math.js` / `average`" in out
    assert bug in out
    assert "Suggested fix (verified)" in out
    assert "```diff\n" + diff + "```" in out
    assert "- `src/math.js` / `average`: empty input?" in out
