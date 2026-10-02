"""Intersect changed lines with uncovered lines and group them by function."""
from .models import Gap


def find_gaps(changed, uncovered, functions) -> list[Gap]:
    """Return one Gap per function that has lines both changed and untested.

    Anonymous callbacks roll up to the nearest enclosing named function,
    because they cannot be called directly from a test.
    Lines outside any function are grouped under "<module>".
    """
    gaps = []

    for file, lines in changed.items():
        targets = lines & uncovered.get(file, set())
        if not targets:
            continue

        groups = {}
        for line in targets:
            owners = [
                (name, start, end)
                for name, start, end in functions.get(file, [])
                if start <= line <= end
            ]

            named = [fn for fn in owners if not fn[0].startswith("(anonymous")]
            candidates = named or owners

            if candidates:
                name, start, end = min(
                    candidates,
                    key=lambda function: function[2] - function[1]
                )
            else:
                name = "<module>"
                start = end = line

            groups.setdefault((name, start, end), set()).add(line)

        for (name, start, end), group in groups.items():
            gaps.append(Gap(file, name, start, end, group))

    return sorted(gaps, key=lambda gap: (gap.file, gap.start_line))