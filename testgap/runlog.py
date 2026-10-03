"""Optional per-run logging for ``testgap run --verbose``."""
import json
import re
from pathlib import Path

_FAIL_LINE = re.compile(r"^\s*(?:FAIL|[×✗✕])\s+(.+?)\s*$")
_ANSI = re.compile(r"\[[0-9;]*m")
_DETAILS_MAX = 1500


def _short_name(raw: str) -> str:
    return re.sub(r"\s+\d+ms$", "", raw).split(" > ")[-1].strip()


def _clean_lines(output: str) -> list[str]:
    return _ANSI.sub("", output).splitlines()


_LOAD_FAIL_LINE = re.compile(r"^\s*FAIL\s+(\S+)\s+\[\s*\S+\s*\]\s*$")


def file_failed_to_load(output: str) -> bool:
    """True when vitest could not load the test file (no individual test results)."""
    lines = _clean_lines(output)
    if any("Failed Suites" in line for line in lines):
        return True
    return any(_LOAD_FAIL_LINE.match(line) and " > " not in line for line in lines)


def failing_tests(output: str) -> list[str]:
    """Short names (last segment after " > ") of failing tests, in order, each once.

    Empty when the file itself failed to load: there are no per-test failures then.
    """
    if file_failed_to_load(output):
        return []
    names = []
    for line in _clean_lines(output):
        match = _FAIL_LINE.match(line)
        if match:
            name = _short_name(match.group(1))
            if name not in names:
                names.append(name)
    return names


def failure_details(output: str) -> dict[str, str]:
    """Map each failing test's short name to its assertion error snippet."""
    details: dict[str, str] = {}
    current = None
    block: list[str] = []

    def flush():
        if current is not None:
            text = "\n".join(block).strip()[:_DETAILS_MAX]
            if text or current not in details:
                details[current] = text

    for line in _clean_lines(output):
        match = _FAIL_LINE.match(line)
        if match:
            flush()
            current, block = _short_name(match.group(1)), []
        elif current is not None:
            stripped = line.strip()
            if stripped.startswith(("❯", "⎯", "✓", "✔", "↓", "Test Files", "Tests ")):
                flush()
                current, block = None, []
            else:
                block.append(line)
    flush()
    return details


class NullLogger:
    """Default logger: does nothing."""

    def spec(self, text): pass
    def begin_attempt(self, number, code): pass
    def test_run(self, passed, output): pass
    def classifier_reply(self, reply, name=""): pass
    def verdict(self, verdict, name=""): pass
    def truncated(self): pass
    def load_failed(self): pass


class RunLogger(NullLogger):
    """Saves artifacts under <repo>/.testgap/runs/<file stem>.<function>/ and prints a summary."""

    def __init__(self, repo, gap, echo=print):
        self.dir = Path(repo) / ".testgap" / "runs" / f"{Path(gap.file).stem}.{gap.function}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.echo = echo
        self.n = 0

    def _write(self, name, text):
        (self.dir / name).write_text(text, encoding="utf-8")

    def spec(self, text):
        self._write("spec.txt", text)

    def begin_attempt(self, number, code):
        self.n = number
        self._write(f"attempt_{number}.test.js", code)

    def test_run(self, passed, output):
        self._write(f"attempt_{self.n}.output.txt", output)
        self.echo(f"    attempt {self.n}: {'passed' if passed else 'failed'}")
        for name in failing_tests(output):
            self.echo(f"      failing: {name}")

    def classifier_reply(self, reply, name=""):
        slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")[:50] or "test"
        self._write(f"attempt_{self.n}.verdict.{slug}.json", reply)

    def verdict(self, verdict, name=""):
        if verdict.confidence is not None:
            label = "code_bug" if verdict.is_code_bug else "not a bug"
            self.echo(f"      verdict for {name}: {label} (confidence {verdict.confidence})")

    def truncated(self):
        self.echo("    response truncated, retrying shorter")

    def load_failed(self):
        self.echo("    file failed to load")
