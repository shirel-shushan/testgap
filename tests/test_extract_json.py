import json
from testgap.llm import extract_json

REAL_REPLY = """**The problem:** `subtotal <= coupon.minSubtotal` with { valid: true } expected.

```javascript
if (coupon.minSubtotal !== undefined && subtotal < coupon.minSubtotal) {
  return { valid: false, reason: 'BELOW_MINIMUM' };
}
```

```json
{"verdict": "code_bug", "confidence": 0.95, "explanation": "uses <= instead of <"}
```
"""


def test_picks_final_json_block_after_code_with_braces():
    data = json.loads(extract_json(REAL_REPLY))
    assert data["verdict"] == "code_bug"
    assert data["confidence"] == 0.95


def test_unfenced_json_at_the_end():
    text = 'Code: { a: 1 }. Answer: {"verdict": "test_wrong", "confidence": 0.8}'
    assert json.loads(extract_json(text))["verdict"] == "test_wrong"