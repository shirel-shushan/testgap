"""Generate, run and validate tests for a single Gap."""
from pathlib import Path

from . import llm, prompts
from .models import Result

MAX_ATTEMPTS = 3


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
            feedback = output[-3000:]

        reply = llm.ask(
            prompts.load("fix"),
            prompts.fix_msg(gap, source, import_path, code, feedback),
        )
        code = llm.extract_code(reply)

    test_path.unlink(missing_ok=True)
    return Result(gap, "gave_up", code, MAX_ATTEMPTS)