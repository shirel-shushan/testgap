"""Prompt templates and message builders."""

from importlib import resources

from .models import Gap


def load(name: str) -> str:
    return resources.files("testgap").joinpath("prompts", f"{name}.txt").read_text(encoding="utf-8")


def _numbered(source: str) -> str:
    return "\n".join(f"{i}: {line}" for i, line in enumerate(source.splitlines(), 1))


def _context(gap: Gap, source: str, import_path: str) -> str:
    untested = ", ".join(str(n) for n in sorted(gap.lines))
    return (
        f"Source file: {gap.file}\n"
        f"```javascript\n{_numbered(source)}\n```\n\n"
        f"Function under test: {gap.function} (lines {gap.start_line}-{gap.end_line})\n"
        f"UNTESTED line numbers: {untested}\n"
        f"Import the source with exactly this path: {import_path}\n"
    )


def generate_msg(gap: Gap, source: str, import_path: str, example_test: str) -> str:
    example = example_test or "(none available)"
    return (
        f"{_context(gap, source, import_path)}\n"
        f"Existing test file, as a style example:\n```javascript\n{example}\n```\n"
    )


def fix_msg(gap: Gap, source: str, import_path: str, test_code: str, feedback: str) -> str:
    return (
        f"{_context(gap, source, import_path)}\n"
        f"Your previous test:\n```javascript\n{test_code}\n```\n\n"
        f"Failure feedback:\n{feedback}\n"
    )
