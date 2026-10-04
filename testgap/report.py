"""Render Results as a report."""

from .models import Result


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_markdown(results: list[Result]) -> str:
    """Render results as a Markdown report."""
    lines = ["# testgap report", ""]
    if not results:
        lines.append("No untested changes found.")
        return "\n".join(lines) + "\n"

    added = sum(1 for r in results if r.status == "passed")
    bugs = sum(len(r.bugs) for r in results)
    questions = sum(len(r.questions) for r in results)
    lines.append(f"{len(results)} functions checked, {added} tests added, "
                 f"{bugs} bugs, {questions} questions.")
    lines += ["", "| Function | Result | Attempts |", "|---|---|---|"]
    for r in results:
        name = _cell(f"{r.gap.file} / {r.gap.function}")
        lines.append(f"| `{name}` | {_cell(r.status)} | {r.attempts} |")

    for r in results:
        fixes = {fix.get("bug"): fix for fix in r.fixes}
        for bug in r.bugs:
            lines += ["", f"**Suspected bug** in `{r.gap.file}` / `{r.gap.function}`", "", bug]
            fix = fixes.get(bug)
            if fix:
                label = "verified" if fix["verified"] else "not verified"
                lines += ["", f"Suggested fix ({label}):", "", "```diff",
                          fix["diff"].rstrip("\n"), "```"]

    all_questions = [(r, q) for r in results for q in r.questions]
    if all_questions:
        lines += ["", "## Questions", ""]
        for r, q in all_questions:
            lines.append(f"- `{r.gap.file}` / `{r.gap.function}`: {q}")

    return "\n".join(lines) + "\n"
