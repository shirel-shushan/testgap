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
    assert "1 function checked, 1 test added, 0 bugs, 0 questions." in out
    assert "| Function | Result | Attempts |" in out
    assert "| `src/math.js / average` | passed | 2 |" in out
    assert "Suspected bug" not in out


def test_bug_with_verified_fix_renders_diff_block():
    bug = "loop skips the last element"
    diff = "--- a/src/math.js\n+++ b/src/math.js\n-  for (i = 0; i < n - 1; i++)\n+  for (i = 0; i < n; i++)\n"
    result = Result(GAP, "gave_up", "code", 3, bugs=[bug], questions=["empty input?"],
                    fixes=[{"bug": bug, "diff": diff, "verified": True, "output": ""}])
    out = render_markdown([result])
    assert "1 bug, 1 question." in out
    assert "**Suspected bug** in `src/math.js` / `average`" in out
    assert bug in out
    assert "Suggested fix (verified)" in out
    assert "```diff\n" + diff + "```" in out
    assert "- `src/math.js` / `average`: empty input?" in out


def test_unverified_fix_hides_diff():
    bug = "loop skips the last element"
    diff = "--- a/src/math.js\n+++ b/src/math.js\n-  old\n+  new\n"
    result = Result(GAP, "gave_up", "code", 3, bugs=[bug],
                    fixes=[{"bug": bug, "diff": diff, "verified": False, "output": "fails"}])
    out = render_markdown([result])
    assert "A fix was attempted but failed verification." in out
    assert "```diff" not in out
    assert "+  new" not in out
    assert "Suggested fix" not in out


def test_summary_plurals():
    other = Gap("src/math.js", "sum", 7, 9, {8})
    results = [
        Result(GAP, "passed", "code", 1, bugs=["a", "b"], questions=["q1", "q2"]),
        Result(other, "passed", "code", 1),
    ]
    out = render_markdown(results)
    assert "2 functions checked, 2 tests added, 2 bugs, 2 questions." in out


def test_same_bug_skips_line_under_bug():
    from testgap.models import Gap, Result
    r = Result(Gap("a.js", "f", 1, 2, {1}), "passed", bugs=["t: why"], skipped_same_bug=3)
    out = render_markdown([r])
    assert "3 more tests were skipped as likely caused by the same bug." in out
    assert "more tests" not in render_markdown([Result(r.gap, "passed", bugs=["t: why"])])
