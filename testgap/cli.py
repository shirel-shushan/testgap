"""Command-line entry point: ``testgap run --repo PATH``."""

import argparse
import sys
from pathlib import Path

from . import diff, gaps
from .adapters import VitestAdapter
from .models import Result


def cmd_run(args: argparse.Namespace) -> int:
    adapter = VitestAdapter()
    uncovered = adapter.uncovered_lines(args.repo)
    functions = adapter.functions(args.repo)

    if args.all:
        changed = {file: set(lines) for file, lines in uncovered.items()}
    else:
        changed = diff.changed_lines(args.repo, args.base)

    found = gaps.find_gaps(changed, uncovered, functions)
    if args.only:
        wanted = {name.strip() for name in args.only.split(",") if name.strip()}
        found = [gap for gap in found if gap.function in wanted]
    for gap in found:
        lines = ",".join(str(n) for n in sorted(gap.lines))
        print(f"{gap.file}:{gap.start_line}-{gap.end_line} {gap.function} -> {lines}")
    if not found:
        print("No gaps found.")

    results = []
    if args.generate:
        from . import generator, runlog

        for gap in found[: args.max_gaps]:
            logger = runlog.RunLogger(args.repo, gap) if args.verbose else None
            result = generator.process(gap, adapter, args.repo, logger)
            results.append(result)
            print(f"{gap.file} {gap.function} -> {result.status} ({result.attempts})")
            for bug in result.bugs:
                print(f"    BUG? {bug}")
            for question in result.questions:
                print(f"    QUESTION? {question}")
            if args.suggest_fixes and result.bugs:
                from . import fixer

                source = (Path(args.repo) / gap.file).read_text(encoding="utf-8")
                for bug in result.bugs:
                    fix = fixer.suggest_fix(gap, source, bug, result.test_code, adapter, args.repo)
                    if fix is None:
                        continue
                    result.fixes.append(fix)
                    label = "verified" if fix["verified"] else "not verified"
                    print(f"    FIX ({label}):")
                    for line in fix["diff"].splitlines():
                        print(f"      {line}")

    if args.report:
        from . import report

        done = {id(r.gap) for r in results}
        results += [Result(gap, "not generated") for gap in found if id(gap) not in done]
        Path(args.report).write_text(report.render_markdown(results), encoding="utf-8")
        print(f"Report written to {args.report}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="testgap", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="find changed-but-untested functions")
    run.add_argument("--repo", required=True, help="path to the JavaScript repo")
    run.add_argument("--base", default="main", help="branch to diff against (default: main)")
    run.add_argument("--all", action="store_true", help="treat every uncovered line as changed")
    run.add_argument("--generate", action="store_true", help="generate tests for the gaps")
    run.add_argument("--verbose", action="store_true",
                     help="with --generate, save specs/tests/outputs to <repo>/.testgap/runs and print per-attempt details")
    run.add_argument("--suggest-fixes", action="store_true",
                     help="with --generate, suggest a fix for each bug and verify it by running the tests")
    run.add_argument("--max-gaps", type=int, default=3, help="max gaps to generate for (default: 3)")
    run.add_argument("--only", metavar="NAME[,NAME...]",
                     help="only process gaps whose function name is in this comma-separated list")
    run.add_argument("--report", metavar="FILE",
                     help="write a Markdown report to FILE (with or without --generate)")
    run.set_defaults(func=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
