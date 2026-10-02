from .models import Gap


def find_gaps(changed, uncovered, functions) -> list[Gap]:
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

            if owners:
                name, start, end = min(
                    owners,
                    key=lambda function: function[2] - function[1]
                )
            else:
                name = "<module>"
                start = end = line

            groups.setdefault((name, start, end), set()).add(line)

        for (name, start, end), group in groups.items():
            gaps.append(Gap(file, name, start, end, group))

    return sorted(gaps, key=lambda gap: (gap.file, gap.start_line))