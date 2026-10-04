"""Render Results as a report."""

from .models import Result, count_tests


KEPT = ("passed", "bug_found")


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def render_markdown(results: list[Result]) -> str:
    """Render results as a Markdown report."""
    lines = ["# testgap report", ""]
    if not results:
        lines.append("No untested changes found.")
        return "\n".join(lines) + "\n"

    kept = [count_tests(r.test_code) for r in results if r.status in KEPT]
    added = sum(total for total, _ in kept)
    skipped = sum(skip for _, skip in kept)
    bugs = sum(len(r.bugs) for r in results)
    questions = sum(len(r.questions) for r in results)
    lines.append(f"{_count(len(results), 'function')} checked, {_count(added, 'test')} added ({skipped} skipped until the bug is fixed), "
                 f"{_count(bugs, 'bug')}, {_count(questions, 'question')}.")
    lines += ["", "| Function | Result | Attempts |", "|---|---|---|"]
    for r in results:
        name = _cell(f"{r.gap.file} / {r.gap.function}")
        lines.append(f"| `{name}` | {_cell(r.status.replace('_', ' '))} | {r.attempts} |")

    for r in results:
        fixes = {fix.get("bug"): fix for fix in r.fixes}
        for i, bug in enumerate(r.bugs):
            lines += ["", f"**Suspected bug** in `{r.gap.file}` / `{r.gap.function}`", "", bug]
            if i == 0 and r.skipped_same_bug:
                lines += ["", f"{r.skipped_same_bug} more tests were skipped as likely caused by the same bug."]
            fix = fixes.get(bug)
            if fix and fix["verified"]:
                lines += ["", "Suggested fix (verified):", "", "```diff",
                          fix["diff"].rstrip("\n"), "```"]
            elif fix:
                lines += ["", "A fix was attempted but failed verification."]

    all_questions = [(r, q) for r in results for q in r.questions]
    if all_questions:
        lines += ["", "## Questions", ""]
        for r, q in all_questions:
            lines.append(f"- `{r.gap.file}` / `{r.gap.function}`: {q}")

    return "\n".join(lines) + "\n"
