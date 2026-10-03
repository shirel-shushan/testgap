"""Core data types."""

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
