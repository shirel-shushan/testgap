"""Suggest and verify a fix for a bug found in a Gap."""
import difflib
import re
import textwrap
from pathlib import Path

from . import llm, prompts
from .generator import _numbered

_SKIP = re.compile(r"""\bit\.skip\((?P<q>['"`])(?P<title>.*?)(?P=q)""")


def unskip_named(test_code: str, bug_text: str) -> str:
    """Turn it.skip into it for tests whose title starts this bug's text ("name: explanation")."""
    def repl(m):
        if bug_text.startswith(m["title"] + ": "):
            return f"it({m['q']}{m['title']}{m['q']}"
        return m.group(0)
    return _SKIP.sub(repl, test_code)


def _nl_terminated(lines: list[str]) -> list[str]:
    """Ensure every line ends with a newline so difflib doesn't merge the last line with the next."""
    return [l if l.endswith("\n") else l + "\n" for l in lines]


def _signature(function: str) -> re.Pattern:
    name = re.escape(function)
    return re.compile(rf"\bfunction\s*\*?\s*{name}\b|\b{name}\s*=(?![=>])")


def drop_before_signature(code: str, function: str) -> str:
    """Drop lines above the one holding the signature, e.g. a doc comment the original already has."""
    sig = _signature(function)
    lines = code.splitlines()
    for i, line in enumerate(lines):
        if sig.search(line):
            return "\n".join(lines[i:])
    return code


def pick_fix_block(reply: str, function: str) -> str:
    """The fenced block that defines `function` ("function name" or "name ="), else the last one."""
    blocks = llm.extract_code_blocks(reply)
    if not blocks:
        return reply.strip()
    sig = _signature(function)
    for block in blocks:
        if sig.search(block):
            return block
    return blocks[-1]


def suggest_fix(gap, source, bug_text, test_code, adapter, repo) -> dict | None:
    msg = (
        f"Source file: {gap.file}\n```javascript\n{_numbered(source)}\n```\n\n"
        f"Function: {gap.function} (lines {gap.start_line}-{gap.end_line})\n"
        f"Bug: {bug_text}\n\n"
        f"Failing test file:\n```javascript\n{test_code}\n```\n"
    )
    try:
        fixed = drop_before_signature(
            pick_fix_block(llm.ask(prompts.load("suggest_fix"), msg), gap.function), gap.function)
    except llm.TruncatedResponse:
        return None

    repo_path = Path(repo)
    src_path = repo_path / gap.file
    original = src_path.read_bytes()
    text = original.decode("utf-8")
    lines = text.splitlines(keepends=True)
    eol = "\r\n" if "\r\n" in text else "\n"
    old_fn = lines[gap.start_line - 1:gap.end_line]
    indent = ""
    if old_fn:
        first = old_fn[0]
        indent = first[:len(first) - len(first.lstrip())]
    body = textwrap.dedent(fixed).splitlines()
    new_fn = [(indent + line if line.strip() else line) + eol for line in body]
    if old_fn and new_fn and not old_fn[-1].endswith(("\n", "\r")):
        new_fn[-1] = new_fn[-1][: -len(eol)]
    patched = "".join(lines[:gap.start_line - 1] + new_fn + lines[gap.end_line:])
    diff = "".join(difflib.unified_diff(
        _nl_terminated(old_fn), _nl_terminated(new_fn), f"a/{gap.file}", f"b/{gap.file}"))

    test_rel = adapter.test_path_for(gap.file, gap.function)
    tmp_rel = test_rel.replace(".test.js", ".fix.test.js")
    tmp_path = repo_path / tmp_rel
    try:
        src_path.write_bytes(patched.encode("utf-8"))
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(unskip_named(test_code, bug_text), encoding="utf-8")
        ok_new, out_new = adapter.run_test_file(repo, tmp_rel)
        ok_old, out_old = adapter.run_existing_suite(repo)
        tmp_path.unlink(missing_ok=True)
    finally:
        src_path.write_bytes(original)
        tmp_path.unlink(missing_ok=True)

    verified = bool(ok_new and ok_old)
    reason = ""
    if not ok_new:
        reason = "bug test still fails: " + out_new[-500:]
    elif not ok_old:
        reason = "existing suite fails: " + out_old[-500:]
    return {"bug": bug_text, "diff": diff, "verified": verified, "output": reason}
