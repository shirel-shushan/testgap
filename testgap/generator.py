"""Generate, run and validate tests for a single Gap."""
import json
from dataclasses import dataclass
from pathlib import Path

from . import llm, prompts
from .models import Result
from .runlog import NullLogger, failing_tests, failure_details, file_failed_to_load

MAX_ATTEMPTS = 3
CONFIDENCE_THRESHOLD = 0.7
MAX_CLASSIFIED = 3
TEST_BROKEN = ("SyntaxError", "Cannot find module", "is not a function",
               "is not defined", "Failed to resolve import")


@dataclass
class Verdict:
    is_code_bug: bool
    explanation: str = ""
    confidence: float | None = None


def _numbered(source: str) -> str:
    return "\n".join(f"{i:4d}  {line}" for i, line in enumerate(source.splitlines(), 1))


def hide_body(source: str, start_line: int, end_line: int) -> str:
    """Return the source with the function body between start and end replaced by a marker."""
    out = []
    for i, line in enumerate(source.splitlines(), 1):
        if start_line < i < end_line:
            if i == start_line + 1:
                out.append("  /* implementation hidden */")
            continue
        out.append(line)
    return "\n".join(out)


def write_spec(gap, source) -> str:
    """Ask the model what the function should do, without showing its body."""
    msg = (
        f"Function: {gap.function} in {gap.file}\n\n"
        f"Source, with the body of {gap.function} hidden:\n"
        f"```javascript\n{hide_body(source, gap.start_line, gap.end_line)}\n```"
    )
    return llm.ask(prompts.load("spec"), msg, max_tokens=1500)


def classify(gap, source, test_code, test_name, details, spec="", logger=None) -> Verdict:
    """Decide whether one failing test exposes a bug in the code."""
    if any(marker in details for marker in TEST_BROKEN):
        return Verdict(False)

    msg = (
        f"Function under test: {gap.function} "
        f"(lines {gap.start_line}-{gap.end_line} of {gap.file})\n\n"
        f"SPEC:\n{spec}\n\n"
        f"Source:\n{_numbered(source)}\n\n"
        f"Test file:\n```javascript\n{test_code}\n```\n\n"
        f"Classify only this one failing test: {test_name}\n"
        f"Its failure details:\n{details[-3000:]}"
    )
    try:
        reply = llm.ask(prompts.load("classify"), msg, max_tokens=1500)
    except llm.TruncatedResponse:
        return Verdict(False, "classifier output truncated")
    (logger or NullLogger()).classifier_reply(reply, test_name)

    try:
        data = json.loads(llm.extract_json(reply))
    except ValueError:
        return Verdict(False)

    confidence = float(data.get("confidence", 0))
    is_bug = data.get("verdict") == "code_bug" and confidence >= CONFIDENCE_THRESHOLD
    return Verdict(is_bug, str(data.get("explanation", "")), confidence)


def _fix_instructions(skip: list[tuple[str, str]], fix: list[str]) -> str:
    skip_list = "; ".join(f'"{name}" (explanation: {why})' for name, why in skip) or "(none)"
    fix_list = "; ".join(f'"{name}"' for name in fix) or "(none)"
    return (
        "\n\nInstructions for this fix:\n"
        "Change these tests to it.skip and add a comment above each: "
        f"// testgap: suspected bug - <explanation>: {skip_list}. "
        f"Fix these tests that are wrong: {fix_list}. "
        "Do not change any other test.\n"
    )


SHORTER = ("\n\nYour previous answer was cut off. Write a shorter file: at most 20 test cases, "
           "use it.each tables for similar cases.")


def _ask_code(system, msg, logger) -> str:
    """Ask for a test file; on truncation retry once asking for a shorter one."""
    try:
        return llm.extract_code(llm.ask(system, msg))
    except llm.TruncatedResponse:
        logger.truncated()
    return llm.extract_code(llm.ask(system, msg + SHORTER))


def process(gap, adapter, repo, logger=None) -> Result:
    logger = logger or NullLogger()
    repo_path = Path(repo)
    source = (repo_path / gap.file).read_text(encoding="utf-8")

    test_rel = adapter.test_path_for(gap.file, gap.function)
    test_path = repo_path / test_rel
    import_path = adapter.import_path_for(test_rel, gap.file)
    example = adapter.example_test(repo)

    spec = write_spec(gap, source)
    logger.spec(spec)
    spec_block = f"\n\nSPEC (expected behavior, written without seeing the implementation):\n{spec}\n"

    try:
        code = _ask_code(
            prompts.load("generate"),
            prompts.generate_msg(gap, source, import_path, example) + spec_block,
            logger,
        )
    except llm.TruncatedResponse:
        return Result(gap, "gave_up", "", 0, "model output truncated")

    bugs: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(code, encoding="utf-8")

        logger.begin_attempt(attempt, code)
        passed, output = adapter.run_test_file(repo, test_rel)
        logger.test_run(passed, output)

        if passed:
            adapter.refresh()
            still_missing = gap.lines & adapter.uncovered_lines(repo).get(gap.file, set())
            if not still_missing:
                return Result(gap, "passed", code, attempt, bugs=bugs)
            feedback = f"Tests pass, but lines {sorted(still_missing)} are still not executed."
        else:
            names = failing_tests(output)[:MAX_CLASSIFIED]
            if file_failed_to_load(output):
                logger.load_failed()
                feedback = ("The test file failed to load (syntax or import error), "
                            "so no individual tests ran:\n" + output[-3000:])
            elif not names:
                feedback = output[-3000:]
            else:
                details = failure_details(output)
                skip: list[tuple[str, str]] = []
                fix: list[str] = []
                for name in names:
                    verdict = classify(gap, source, code, name, details.get(name, ""), spec, logger)
                    logger.verdict(verdict, name)
                    if verdict.is_code_bug:
                        entry = f"{name}: {verdict.explanation}"
                        if entry not in bugs:
                            bugs.append(entry)
                        skip.append((name, verdict.explanation))
                    else:
                        fix.append(name)
                feedback = output[-3000:] + _fix_instructions(skip, fix)

        try:
            code = _ask_code(
                prompts.load("fix"),
                prompts.fix_msg(gap, source, import_path, code, feedback) + spec_block,
                logger,
            )
        except llm.TruncatedResponse:
            test_path.unlink(missing_ok=True)
            return Result(gap, "gave_up", code, attempt, "model output truncated", bugs=bugs)

    test_path.unlink(missing_ok=True)
    return Result(gap, "gave_up", code, MAX_ATTEMPTS, bugs=bugs)