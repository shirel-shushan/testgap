from testgap.runlog import failing_tests, failure_details

OUTPUT = """\
 \x1b[31m❯\x1b[39m tests/add.test.js (3 tests | 2 failed)
   \x1b[31m×\x1b[39m add > adds negatives 3ms
   \x1b[31m×\x1b[39m add > handles zero 1ms
 FAIL  tests/add.test.js > add > adds negatives
AssertionError: expected 1 to be -3
 ❯ tests/add.test.js:5:20
 FAIL  tests/add.test.js > add > handles zero
AssertionError: expected 0 to be 1

- Expected
+ Received
 ❯ tests/add.test.js:9:20
 FAIL  tests/add.test.js > add > handles zero
 ✓ add > adds positives
"""


def test_short_names_and_dedupe():
    assert failing_tests(OUTPUT) == ["adds negatives", "handles zero"]


def test_passing_output_has_no_failures():
    assert failing_tests(" ✓ add > works\n Tests 1 passed") == []


def test_failure_details():
    details = failure_details(OUTPUT)
    assert set(details) == {"adds negatives", "handles zero"}
    assert "expected 1 to be -3" in details["adds negatives"]
    assert "expected 0 to be 1" in details["handles zero"]
    assert "expected 1" not in details["handles zero"]
