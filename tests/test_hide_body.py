from testgap.generator import hide_body

SRC = """// returns x
export function f(x) {
  if (x > 1) return 1;
  return 0;
}
export function g() { return f(2); }"""


def test_body_is_hidden_signature_and_callers_stay():
    out = hide_body(SRC, 2, 5)
    assert "x > 1" not in out
    assert "export function f(x) {" in out
    assert "// returns x" in out
    assert "return f(2)" in out