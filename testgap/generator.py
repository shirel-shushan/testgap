"""Generate, run and validate tests for a single Gap."""
import json
from dataclasses import dataclass
from pathlib import Path

from . import llm, prompts
from .models import Result

MAX_ATTEMPTS = 3
CONFIDENCE_THRESHOLD = 0.7
TEST_BROKEN = ("SyntaxError", "Cannot find module", "is not a function",
               "is not defined", "Failed to resolve import")


@dataclass
class Verdict:
    is_code_bug: bool
    explanation: str = ""


def _numbered(source: str) -> str:
    return "\n".join(f"{i:4d}  {line}" for i, line in enumerate(source.splitlines(), 1))


def classify(gap, source, test_code, output) -> Verdict:
    """Decide whether a failing test exposes a bug in the code."""
    if any(marker in output for marker in TEST_BROKEN):
        return Verdict(False)

    msg = (
        f"Function under test: {gap.function} "
        f"(lines {gap.start_line}-{gap.end_line} of {gap.file})\n\n"
        f"Source:\n{_numbered(source)}\n\n"
        f"Test:\n```javascript\n{test_code}\n```\n\n"
        f"Failure output:\n{output[-3000:]}"
    )
    reply = llm.ask(prompts.load("classify"), msg, max_tokens=500)
    try:
        data = json.loads(llm.extract_json(reply))
    except ValueError:
        return Verdict(False)

    is_bug = (data.get("verdict") == "code_bug"
              and float(data.get("confidence", 0)) >= CONFIDENCE_THRESHOLD)
    explanation = f'{data.get("test_name", "")}: {data.get("explanation", "")}'
    return Verdict(is_bug, explanation)


def process(gap, adapter, repo) -> Result:
    repo_path = Path(repo)
    source = (repo_path / gap.file).read_text(encoding="utf-8")

    test_rel = adapter.test_path_for(gap.file, gap.function)
    test_path = repo_path / test_rel
    import_path = adapter.import_path_for(test_rel, gap.file)
    example = adapter.example_test(repo)

    reply = llm.ask(
        prompts.load("generate"),
        prompts.generate_msg(gap, source, import_path, example),
    )
    code = llm.extract_code(reply)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(code, encoding="utf-8")

        passed, output = adapter.run_test_file(repo, test_rel)

        if passed:
            adapter.refresh()
            still_missing = gap.lines & adapter.uncovered_lines(repo).get(gap.file, set())
            if not still_missing:
                return Result(gap, "passed", code, attempt)
            feedback = f"Tests pass, but lines {sorted(still_missing)} are still not executed."
        else:
            verdict = classify(gap, source, code, output)
            if verdict.is_code_bug:
                test_path.unlink(missing_ok=True)
                return Result(gap, "suspected_bug", code, attempt, verdict.explanation)
            feedback = output[-3000:]

        reply = llm.ask(
            prompts.load("fix"),
            prompts.fix_msg(gap, source, import_path, code, feedback),
        )
        code = llm.extract_code(reply)

    test_path.unlink(missing_ok=True)
    return Result(gap, "gave_up", code, MAX_ATTEMPTS)