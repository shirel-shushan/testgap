"""Coverage adapter for Vitest (istanbul-format JSON coverage)."""

import json
import os
import subprocess
from pathlib import Path, PurePosixPath

from .base import CoverageAdapter

COVERAGE_CMD = ["npx", "vitest", "run", "--coverage", "--coverage.reporter=json"]
COVERAGE_FILE = Path("coverage") / "coverage-final.json"
TIMEOUT = 300


def _run(cmd: list[str], repo: Path) -> subprocess.CompletedProcess:
    # npx is a .cmd shim on Windows, so it needs a shell there.
    return subprocess.run(
        cmd,
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=(os.name == "nt"),
        timeout=TIMEOUT,
    )


class VitestAdapter(CoverageAdapter):
    def __init__(self) -> None:
        # resolved repo root -> {repo-relative path: coverage entry}
        self._coverage: dict[Path, dict[str, dict]] = {}

    def refresh(self) -> None:
        self._coverage.clear()

    def _load(self, repo: str | Path) -> dict[str, dict]:
        root = Path(repo).resolve()
        if root not in self._coverage:
            self._run_coverage(root)
            self._coverage[root] = self._parse(root)
        return self._coverage[root]

    def _run_coverage(self, root: Path) -> None:
        proc = _run(COVERAGE_CMD, root)
        # Failing tests give a non-zero exit but still produce coverage.
        if not (root / COVERAGE_FILE).is_file():
            raise RuntimeError(
                f"vitest did not produce {COVERAGE_FILE} (exit {proc.returncode}):\n"
                f"{proc.stdout}\n{proc.stderr}"
            )

    def _parse(self, root: Path) -> dict[str, dict]:
        raw = json.loads((root / COVERAGE_FILE).read_text(encoding="utf-8"))
        result = {}
        for key, entry in raw.items():
            rel = _relative(entry.get("path", key), root)
            if rel is not None:
                result[rel] = entry
        return result

    def uncovered_lines(self, repo: str | Path) -> dict[str, set[int]]:
        result = {}
        for file, entry in self._load(repo).items():
            lines = set()
            for sid, loc in entry["statementMap"].items():
                if entry["s"].get(sid, 0) == 0:
                    lines.update(range(loc["start"]["line"], loc["end"]["line"] + 1))
            result[file] = lines
        return result

    def functions(self, repo: str | Path) -> dict[str, list[tuple[str, int, int]]]:
        result = {}
        for file, entry in self._load(repo).items():
            fns = [
                (fn["name"], fn["loc"]["start"]["line"], fn["loc"]["end"]["line"])
                for fn in entry["fnMap"].values()
            ]
            result[file] = sorted(fns, key=lambda f: f[1])
        return result

    def run_test_file(self, repo: str | Path, test_path: str) -> tuple[bool, str]:
        try:
            proc = _run(["npx", "vitest", "run", test_path], Path(repo).resolve())
        except subprocess.TimeoutExpired as e:
            return False, f"timed out after {TIMEOUT}s\n{e.stdout or ''}{e.stderr or ''}"
        return proc.returncode == 0, proc.stdout + proc.stderr

    def test_path_for(self, source_file: str, function: str) -> str:
        stem = PurePosixPath(source_file.replace("\\", "/")).stem
        return f"tests/generated/{stem}.{function}.test.js"


def _relative(path: str, root: Path) -> str | None:
    """Repo-relative POSIX path, or None if the file is outside the repo."""
    try:
        return Path(path).resolve().relative_to(root).as_posix()
    except ValueError:
        return None
