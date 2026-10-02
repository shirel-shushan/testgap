from testgap.diff import parse_diff

SAMPLE = """\
diff --git a/src/a.js b/src/a.js
--- a/src/a.js
+++ b/src/a.js
@@ -26 +26,2 @@
-old
+new1
+new2
@@ -40,3 +41,0 @@
-gone
"""

def test_range_with_count():
    assert parse_diff(SAMPLE)["src/a.js"] == {26, 27}

def test_pure_deletion_adds_nothing():
    assert 41 not in parse_diff(SAMPLE)["src/a.js"]

def test_deleted_file_ignored():
    text = "--- a/x.js\n+++ /dev/null\n@@ -1,3 +0,0 @@\n"
    assert parse_diff(text) == {}

def test_single_line_without_count():
    text = "+++ b/b.js\n@@ -5 +7 @@\n"
    assert parse_diff(text) == {"b.js": {7}}

def test_file_with_only_deletions_is_omitted():
    text = "+++ b/c.js\n@@ -10,3 +9,0 @@\n"
    assert parse_diff(text) == {}