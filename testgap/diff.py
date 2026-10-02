"""Extract changed line numbers from a git diff."""

from pathlib import Path


def parse_diff(diff_text: str) -> dict[str, set[int]]:
    """Parse unified diff text into changed lines per file.

    Args:
        diff_text: Output of ``git diff -U0`` (or similar unified diff).

    Returns:
        Mapping of repo-relative POSIX file path -> set of 1-based line
        numbers that were added or modified in the new version of the file.
        Deleted files are omitted.
    """
    raise NotImplementedError


def changed_lines(repo: str | Path, base: str = "main") -> dict[str, set[int]]:
    """Return lines changed in ``repo`` relative to ``base``.

    Args:
        repo: Path to the git repository.
        base: Branch or ref to diff against.

    Returns:
        Mapping of repo-relative POSIX file path -> set of changed
        1-based line numbers (see ``parse_diff``).
    """
    raise NotImplementedError
