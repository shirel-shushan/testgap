import pytest

from testgap import prompts
from testgap.adapters import VitestAdapter
from testgap.llm import extract_code, extract_json
from testgap.models import Gap

BS = chr(92)


def test_extract_code_variants():
    assert extract_code("hi\n```javascript\nlet a=1;\n```\nbye") == "let a=1;"
    assert extract_code("```js\nx\n```") == "x"
    assert extract_code("```\nplain\n```") == "plain"
    assert extract_code("```js\na\n```\n```js\nb\n```") == "a"
    assert extract_code("  just text \n") == "just text"


def test_extract_json():
    assert extract_json('Sure: {"a": {"b": 1}} done') == '{"a": {"b": 1}}'
    assert extract_json("none") == "none"


@pytest.mark.parametrize(
    "test_path,source,expected",
    [
        ("tests/generated/a.f.test.js", "src/a.js", "../../src/a.js"),
        ("tests/a.test.js", "src/a.js", "../src/a.js"),
        ("src/a.test.js", "src/a.js", "./a.js"),
        ("a.test.js", "src/a.js", "./src/a.js"),
        ("tests/generated/a.test.js".replace("/", BS), "src/a.js".replace("/", BS), "../../src/a.js"),
    ],
)
def test_import_path_for(test_path, source, expected):
    assert VitestAdapter().import_path_for(test_path, source) == expected


def test_example_test(tmp_path):
    a = VitestAdapter()
    assert a.example_test(tmp_path) == ""
    (tmp_path / "tests" / "generated").mkdir(parents=True)
    (tmp_path / "tests" / "generated" / "g.test.js").write_text("gen")
    assert a.example_test(tmp_path) == ""
    (tmp_path / "tests" / "b.test.js").write_text("real")
    assert a.example_test(tmp_path) == "real"


def test_refresh_clears_cache():
    a = VitestAdapter()
    a._coverage["x"] = {}
    a.refresh()
    assert a._coverage == {}


GAP = Gap(file="src/a.js", function="f", start_line=2, end_line=4, lines={3, 4})
SRC = "line1\nline2\nline3\nline4\n"


def test_generate_msg():
    msg = prompts.generate_msg(GAP, SRC, "../src/a.js", "EXAMPLE")
    assert "3: line3" in msg and "f (lines 2-4)" in msg
    assert "UNTESTED line numbers: 3, 4" in msg
    assert "../src/a.js" in msg and "EXAMPLE" in msg


def test_fix_msg():
    msg = prompts.fix_msg(GAP, SRC, "../src/a.js", "OLDTEST", "boom")
    assert "OLDTEST" in msg and "boom" in msg and "1: line1" in msg


def test_load_prompts():
    assert prompts.load("generate") is not None
    assert prompts.load("fix") is not None
