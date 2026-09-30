"""State v3 = state v2 with exactly the eight A9.3 tier-1 answers applied; outputs current."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "docs" / "budgets" / "owner_decisions"


def _builder():
    spec = importlib.util.spec_from_file_location("state_v3", HERE / "build_owner_questions_state_v3.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_state_v3_applies_only_a9_3_answers_and_is_current():
    doc = _builder().build()
    v2 = json.loads((HERE / "owner_questions_state_v2.json").read_text(encoding="utf-8"))
    changed = {r3["id"] for r2, r3 in zip(v2["rows"], doc["rows"]) if r2 != r3}
    assert changed == {"OQ-VI-03", "OQ-VI-05", "OQ-A907-02", "ICPQ-06", "OQ-RFQ-06", "OQ-RFQ-07", "OQ-RFQ-02", "OQ-RFQ-10"}
    assert doc["open_count"] == v2["open_count"] - 8
    assert (HERE / "owner_questions_state_v3.json").read_text(encoding="utf-8") == json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
