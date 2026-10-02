"""Combine diff and coverage data into Gaps."""

from .models import Gap


def find_gaps(
    changed: dict[str, set[int]],
    uncovered: dict[str, set[int]],
    functions: dict[str, list[tuple[str, int, int]]],
) -> list[Gap]:
    """Find functions whose changed lines are not covered by tests.

    Args:
        changed: file -> changed line numbers (from ``diff.changed_lines``).
        uncovered: file -> uncovered line numbers (from the coverage adapter).
        functions: file -> list of (name, start_line, end_line) (from the
            coverage adapter).

    Returns:
        One Gap per function that contains at least one line that is both
        changed and uncovered; ``Gap.lines`` holds those lines.
    """
    raise NotImplementedError
