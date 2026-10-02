from testgap.gaps import find_gaps


def test_intersection_only():
    gaps = find_gaps(
        {"a.js": {5, 6, 20}},
        {"a.js": {6, 20, 30}},
        {"a.js": [("f", 1, 10), ("g", 15, 25)]},
    )
    assert [(g.function, g.lines) for g in gaps] == [("f", {6}), ("g", {20})]


def test_anonymous_callback_rolls_up_to_named_parent():
    gaps = find_gaps(
        {"a.js": {22}},
        {"a.js": {22}},
        {"a.js": [("calculateSubtotal", 15, 31), ("(anonymous_2)", 20, 28)]},
    )
    assert gaps[0].function == "calculateSubtotal"


def test_innermost_named_function_wins():
    gaps = find_gaps(
        {"a.js": {5}},
        {"a.js": {5}},
        {"a.js": [("outer", 1, 20), ("inner", 4, 6)]},
    )
    assert gaps[0].function == "inner"


def test_line_outside_any_function():
    gaps = find_gaps({"a.js": {3}}, {"a.js": {3}}, {"a.js": [("f", 10, 20)]})
    assert gaps[0].function == "<module>"


def test_file_without_coverage_is_skipped():
    assert find_gaps({"README.md": {1}}, {}, {}) == []


def test_changed_but_covered_is_not_a_gap():
    assert find_gaps({"a.js": {5}}, {"a.js": {9}}, {"a.js": [("f", 1, 10)]}) == []