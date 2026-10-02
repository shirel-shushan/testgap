"""Command-line entry point: ``testgap run --repo PATH``."""

import argparse
import sys

from . import diff, gaps
from .adapters import VitestAdapter


def cmd_run(args: argparse.Namespace) -> int:
    adapter = VitestAdapter()
    uncovered = adapter.uncovered_lines(args.repo)
    functions = adapter.functions(args.repo)

    if args.all:
        changed = {file: set(lines) for file, lines in uncovered.items()}
    else:
        changed = diff.changed_lines(args.repo, args.base)

    found = gaps.find_gaps(changed, uncovered, functions)
    for gap in found:
        lines = ",".join(str(n) for n in sorted(gap.lines))
        print(f"{gap.file}:{gap.start_line}-{gap.end_line} {gap.function} -> {lines}")
    if not found:
        print("No gaps found.")

    if args.generate:
        from . import generator

        for gap in found[: args.max_gaps]:
            result = generator.process(gap, adapter, args.repo)
            print(f"{gap.file} {gap.function} -> {result.status} ({result.attempts})")

    if args.report:
        print(f"note: --report not implemented yet; skipping {args.report}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="testgap", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="find changed-but-untested functions")
    run.add_argument("--repo", required=True, help="path to the JavaScript repo")
    run.add_argument("--base", default="main", help="branch to diff against (default: main)")
    run.add_argument("--all", action="store_true", help="treat every uncovered line as changed")
    run.add_argument("--generate", action="store_true", help="generate tests for the gaps")
    run.add_argument("--max-gaps", type=int, default=3, help="max gaps to generate for (default: 3)")
    run.add_argument("--report", metavar="FILE", help="write a report to FILE")
    run.set_defaults(func=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
