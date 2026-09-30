"""Post-A9 owner-question triage covers every OPEN state-v2 row exactly once and its outputs are current."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "docs" / "budgets" / "owner_decisions"


def _builder():
    spec = importlib.util.spec_from_file_location("triage", HERE / "build_owner_questions_triage_post_a9.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_triage_partitions_open_questions_and_is_current():
    b = _builder()
    doc = b.build()
    state = json.loads((HERE / "owner_questions_state_v2.json").read_text(encoding="utf-8"))
    open_ids = sorted(r["id"] for r in state["rows"] if r["status"] == "OPEN")
    ids = sorted(q["id"] for t in doc["tiers"] for q in t["questions"])
    assert ids == open_ids
    assert (HERE / "owner_questions_triage_post_a9_v1.json").read_text(encoding="utf-8") == \
        json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    assert doc["status"] == "RECORDER_PROPOSAL_NOT_A_DECISION"
