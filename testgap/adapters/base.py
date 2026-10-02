"""Interface every test-runner coverage adapter implements."""

from abc import ABC, abstractmethod
import os
from pathlib import Path, PurePosixPath


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

    @abstractmethod
    def refresh(self) -> None:
        """Drop cached coverage so the next query re-runs the test suite."""

    def import_path_for(self, test_path: str, source_file: str) -> str:
        """Relative ESM import path from a test file to a source file."""
        test_dir = PurePosixPath(test_path.replace("\\", "/")).parent
        rel = os.path.relpath(source_file.replace("\\", "/"), start=test_dir).replace("\\", "/")
        return rel if rel.startswith(".") else f"./{rel}"

    def example_test(self, repo: str | Path) -> str:
        """Contents of the first hand-written ``*.test.js`` under tests/, or ""."""
        tests = Path(repo) / "tests"
        generated = tests / "generated"
        for path in sorted(tests.rglob("*.test.js")):
            if generated not in path.parents:
                return path.read_text(encoding="utf-8")
        return ""
