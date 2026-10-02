"""Interface every test-runner coverage adapter implements."""

from abc import ABC, abstractmethod
from pathlib import Path


class CoverageAdapter(ABC):
    """Runs a JS test suite with coverage and exposes the results.

    All file paths returned are repo-relative POSIX paths (e.g. ``src/pricing.js``).
    """

    @abstractmethod
    def uncovered_lines(self, repo: str | Path) -> dict[str, set[int]]:
        """Return file -> set of 1-based line numbers not executed by any test."""

    @abstractmethod
    def functions(self, repo: str | Path) -> dict[str, list[tuple[str, int, int]]]:
        """Return file -> list of (function name, start_line, end_line)."""

    @abstractmethod
    def run_test_file(self, repo: str | Path, test_path: str) -> tuple[bool, str]:
        """Run a single test file; return (passed, combined output)."""

    @abstractmethod
    def test_path_for(self, source_file: str, function: str) -> str:
        """Return the repo-relative path where a generated test should live."""
