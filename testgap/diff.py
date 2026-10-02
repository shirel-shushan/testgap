"""Parse git diff output into changed line numbers per file."""
import re
import subprocess

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_diff(diff_text: str) -> dict[str, set[int]]:
    """Map each repo-relative file path to the line numbers added or
    modified in its new version. Deleted files and files with only
    deletions are omitted."""
    changed = {}
    current = None

    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            path = line[4:]
            if path == "/dev/null":
                current = None  # הקובץ נמחק
            else:
                current = path.removeprefix("b/")

        elif line.startswith("@@"):
            match = HUNK_RE.match(line)
            if match and current is not None:
                start = int(match.group(1))
                count = int(match.group(2)) if match.group(2) is not None else 1
                if count > 0:
                    changed.setdefault(current, set())
                    changed[current].update(range(start, start + count))

    return changed


def changed_lines(repo: str, base: str = "main") -> dict[str, set[int]]:
    """Run git diff against base and return parse_diff of its output."""
    result = subprocess.run(
        ["git", "diff", "--unified=0", f"{base}...HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return parse_diff(result.stdout)