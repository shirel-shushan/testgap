"""Generate, run and validate tests for a single Gap."""
import json
import re
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
    is_unclear: bool = False
    line: int | None = None


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


def _evidence_lines(evidence, source) -> list[int]:
    """1-based numbers of the source lines containing the evidence (whitespace ignored)."""
    def squash(text):
        return re.sub(r"\s+", "", text)

    needle = squash(evidence)
    if not needle:
        return []
    return [i for i, line in enumerate(source.splitlines(), 1) if needle in squash(line)]


MIN_QUOTE_LEN = 12


def _evidence_candidates(evidence: str) -> list[str]:
    """The whole evidence plus every quoted substring (' " or `) of at least MIN_QUOTE_LEN chars."""
    quoted = re.findall(r"'([^']+)'|\"([^\"]+)\"|`([^`]+)`", evidence)
    parts = [q for group in quoted for q in group if len(q) >= MIN_QUOTE_LEN]
    return [evidence, *parts]


def _evidence_found(evidence, source, line) -> bool:
    """True if some candidate appears on a source line other than the reported one (+-1)."""
    for candidate in _evidence_candidates(evidence):
        for n in _evidence_lines(candidate, source):
            if line is None or abs(n - line) > 1:
                return True
    return False


def _backticked(text: str) -> set[str]:
    return set(re.findall(r"`([^`]+)`", text))


def _prune_questions(bugs: list["Verdict"], questions: list[tuple[str, "Verdict"]]) -> list[str]:
    """Drop questions that restate a bug: same line, or (no line) a shared `quoted` identifier."""
    bug_lines = {b.line for b in bugs if b.line is not None}
    bug_tokens = set().union(*(_backticked(b.explanation) for b in bugs)) if bugs else set()
    kept = []
    for entry, verdict in questions:
        if verdict.line is not None:
            if verdict.line in bug_lines:
                continue
        elif _backticked(verdict.explanation) & bug_tokens:
            continue
        kept.append(entry)
    return kept


def _dedupe_key(gap, verdict: Verdict):
    """One report per (function, line); without a line, per explanation text."""
    return (gap.function, verdict.line if verdict.line is not None else verdict.explanation)


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
    kind = data.get("verdict")
    explanation = str(data.get("explanation", ""))
    evidence = data.get("evidence")
    line = data.get("line")
    line = line if isinstance(line, int) and not isinstance(line, bool) else None
    if kind == "code_bug":
        text = evidence if isinstance(evidence, str) else ""
        if not any(_evidence_lines(c, source) for c in _evidence_candidates(text)):
            kind = "unclear"
            explanation += " (no evidence in file)"
        elif not _evidence_found(text, source, line):
            kind = "unclear"
            explanation += " (evidence is the faulty line itself)"
    is_bug = kind == "code_bug" and confidence >= CONFIDENCE_THRESHOLD
    return Verdict(is_bug, explanation, confidence, kind == "unclear", line)


def _fix_instructions(skip: list[tuple[str, str]], fix: list[str],
                      ask: list[tuple[str, str]] | None = None,
                      same_bug: list[str] | None = None, bug_name: str = "") -> str:
    skip_list = "; ".join(f'"{name}" (explanation: {why})' for name, why in skip) or "(none)"
    ask_part = ""
    if ask:
        ask_list = "; ".join(f'"{name}" (explanation: {why})' for name, why in ask)
        ask_part = ("Also change these tests to it.skip with a comment above each: "
                    f"// testgap: question - <explanation>: {ask_list}. ")
    if same_bug:
        same_list = "; ".join(f'"{name}"' for name in same_bug)
        ask_part += ("Also change these tests to it.skip with a comment above each: "
                     f"// testgap: likely the same bug as {bug_name}: {same_list}. ")
    fix_list = "; ".join(f'"{name}"' for name in fix) or "(none)"
    return (
        "\n\nInstructions for this fix:\n"
        "Change these tests to it.skip and add a comment above each: "
        f"// testgap: suspected bug - <explanation>: {skip_list}. "
        f"{ask_part}"
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
    bug_verdicts: list[Verdict] = []
    questions: list[tuple[str, Verdict]] = []
    seen_bugs: set = set()
    seen_questions: set = set()
    skipped_same_bug: set[str] = set()
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
                return Result(gap, "passed", code, attempt, bugs=bugs, questions=_prune_questions(bug_verdicts, questions),
                      skipped_same_bug=len(skipped_same_bug))
            if bugs:
                # The uncovered lines are the buggy ones: every test reaching them fails and
                # is skipped, and skipped tests do not count, so more attempts cannot help.
                return Result(gap, "bug_found", code, attempt, bugs=bugs,
                              questions=_prune_questions(bug_verdicts, questions),
                              skipped_same_bug=len(skipped_same_bug))
            feedback = f"Tests pass, but lines {sorted(still_missing)} are still not executed."
        else:
            all_names = failing_tests(output)
            names = all_names[:MAX_CLASSIFIED]
            if file_failed_to_load(output):
                logger.load_failed()
                feedback = ("The test file failed to load (syntax or import error), "
                            "so no individual tests ran:\n" + output[-3000:])
            elif not names:
                feedback = output[-3000:]
            else:
                details = failure_details(output)
                skip: list[tuple[str, str]] = []
                ask: list[tuple[str, str]] = []
                fix: list[str] = []
                bug_name = ""
                for name in names:
                    verdict = classify(gap, source, code, name, details.get(name, ""), spec, logger)
                    logger.verdict(verdict, name)
                    if verdict.is_unclear:
                        entry = f"{name}: {verdict.explanation}"
                        key = _dedupe_key(gap, verdict)
                        if key not in seen_questions:
                            seen_questions.add(key)
                            questions.append((entry, verdict))
                        ask.append((name, verdict.explanation))
                    elif verdict.is_code_bug:
                        bug_name = bug_name or name
                        entry = f"{name}: {verdict.explanation}"
                        key = _dedupe_key(gap, verdict)
                        if key not in seen_bugs:
                            seen_bugs.add(key)
                            bugs.append(entry)
                            bug_verdicts.append(verdict)
                        skip.append((name, verdict.explanation))
                    else:
                        fix.append(name)
                same_bug = all_names[MAX_CLASSIFIED:] if bug_name else []
                skipped_same_bug.update(same_bug)
                feedback = output[-3000:] + _fix_instructions(skip, fix, ask, same_bug, bug_name)

        try:
            code = _ask_code(
                prompts.load("fix"),
                prompts.fix_msg(gap, source, import_path, code, feedback) + spec_block,
                logger,
            )
        except llm.TruncatedResponse:
            test_path.unlink(missing_ok=True)
            return Result(gap, "gave_up", code, attempt, "model output truncated", bugs=bugs, questions=_prune_questions(bug_verdicts, questions),
                      skipped_same_bug=len(skipped_same_bug))

    test_path.unlink(missing_ok=True)
    return Result(gap, "gave_up", code, MAX_ATTEMPTS, bugs=bugs, questions=_prune_questions(bug_verdicts, questions),
                      skipped_same_bug=len(skipped_same_bug))