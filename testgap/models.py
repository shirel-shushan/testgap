"""Core data types."""

import re
from dataclasses import dataclass, field


@dataclass
class Gap:
    """A function containing changed lines that no test covers."""

    file: str
    function: str
    start_line: int
    end_line: int
    lines: set[int]


@dataclass
class Result:
    """Outcome of trying to close a Gap with a generated test."""

    gap: Gap
    status: str
    test_code: str = ""
    attempts: int = 0
    explanation: str = ""
    bugs: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    fixes: list[dict] = field(default_factory=list)
    skipped_same_bug: int = 0


_TEST_CASE = re.compile(r"(?<![\w.])(?:it|test)(\.skip)?\(")


def count_tests(code: str) -> tuple[int, int]:
    """Return (test cases, skipped test cases) in a test file."""
    found = _TEST_CASE.findall(code)
    return len(found), sum(1 for skip in found if skip)
