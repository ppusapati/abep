"""Checks for the consolidated owner decision register (docs/budgets/owner_decisions/, fo_a6_integration_refresh)."""
import hashlib
import importlib.util
import json
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "docs", "budgets", "owner_decisions")
JSON_PATH = os.path.join(DIR, "owner_decision_register_v1.json")
MD_PATH = os.path.join(DIR, "OWNER_DECISION_REGISTER.md")
XE = "docs/budgets/xe_ledger/xe_ledger_v1.json"
P1F = "docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json"
PMI = "schemas/interfaces/preionizer_module_icd_v1.json"
HWDEF = "docs/experiments/hardware/hardware_requirements_v1.json"
M16 = "docs/budgets/subsystem_maturity/subsystem_maturity_v2.json"
NEEDED_BY = {"NOW", "before H2 freeze", "LOCK-1", "LOCK-2", "later", "UNSTATED"}


def _builder():
    spec = importlib.util.spec_from_file_location("build_owner_decision_register", os.path.join(DIR, "build_owner_decision_register.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _builder()


def _load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def _sha(rel):
    with open(os.path.join(ROOT, rel), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _ptr(doc, pointer):
    cur = doc
    for part in pointer.lstrip("/").split("/"):
        if part:
            cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


@pytest.fixture(scope="module")
def doc():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def built():
    return B.build(ROOT)


def test_committed_files_reproduce(doc, built):
    assert doc == built, "stale: run build_owner_decision_register.py --write"
    with open(MD_PATH, encoding="utf-8") as f:
        assert f.read() == B.render_md(built)


def test_pins_and_no_mutable_governance(doc):
    for rel, h in list(doc["pins"]["sha256"].items()) + list(doc["pins"]["computed_at_build"].items()):
        assert _sha(rel) == h, rel
    text = json.dumps(doc["pins"])
    for forbidden in ("lane_registry_v1.json", "trigger_registry_v1.json", "trigger_ledger", "runtime_state.json", "fired_triggers"):
        assert forbidden not in text


def test_complete_and_verbatim(doc):
    items = {it["register_id"]: it for it in doc["items"]}
    xe = _load(XE)
    p1 = _load(P1F)
    pmi = _load(PMI)["x-preionizer-module-icd"]
    hw = _load(HWDEF)
    m16 = _load(M16)
    want = [d["id"] for d in xe["open_owner_decisions"]]
    assert want == [f"OD-XE-{i}" for i in range(1, 9)]
    want += [r["id"] for r in p1["reconciliation_items"]]
    assert [r["id"] for r in p1["reconciliation_items"]] == [f"R-{i:02d}" for i in range(1, 15)]
    want += [f"P1F-OOD-{i:02d}" for i in range(1, len(p1["open_owner_decisions"]) + 1)]
    want += [q["id"] for q in pmi["owner_questions"]]
    assert [q["id"] for q in pmi["owner_questions"]] == [f"PMQ-{i:02d}" for i in range(1, 8)]
    relayed = re.findall(r"HWQ-\d\d", next(q["question"] for q in pmi["owner_questions"] if q["id"] == "PMQ-07"))
    assert relayed == ["HWQ-01", "HWQ-04", "HWQ-05", "HWQ-06", "HWQ-07", "HWQ-15"]
    want += relayed
    want += [q["id"] for q in m16["open_owner_questions"]]
    assert [it["register_id"] for it in doc["items"]] == want
    srcs = {XE: xe, P1F: p1, PMI: _load(PMI), HWDEF: hw, M16: m16}
    for it in doc["items"]:
        assert _ptr(srcs[it["source_path"]], it["json_pointer"]) == it["verbatim"], it["register_id"]
        assert it["source_sha256"] == _sha(it["source_path"])
    assert items["HWQ-15"]["verbatim"]["question"].startswith("Whether the module interfaces are frozen before Phase 1")


def test_status_open_and_no_decision(doc):
    assert all(it["status"] == "OPEN" for it in doc["items"])
    assert doc["summary"]["all_status_open"] is True
    text = json.dumps(doc)
    assert "sgb-screen-0" not in text
    assert "winner" not in text.replace("no winner", "").replace("no_winner", "")


def test_needed_by_rule(doc):
    items = {it["register_id"]: it for it in doc["items"]}
    for it in doc["items"]:
        nb = it["needed_by"]
        assert nb["value"] in NEEDED_BY
        if nb["value"] == "UNSTATED":
            assert not nb["matches"] and not nb["gates_named"] and "via_items" not in nb
        else:
            assert nb["value"] == (nb["gates_named"] or [nb["value"]])[0] or "via_items" in nb
    # spot checks against the sources' own words
    assert items["P1F-OOD-01"]["needed_by"]["value"] == "LOCK-1"
    assert items["R-11"]["needed_by"]["value"] == "LOCK-1"
    # relayed HWQ items: the sources' own deadline statements (hardware register stage / HW-PIM texts, ICD annex texts,
    # W2 routing of HWQ-01..HWQ-15 to the LOCK-1 decision brief)
    for h in ("HWQ-01", "HWQ-04", "HWQ-05", "HWQ-06", "HWQ-07", "HWQ-15"):
        assert items[h]["needed_by"]["value"] == "LOCK-1", h
    ins = lambda h: {m["in"] for m in items[h]["needed_by"]["matches"]}
    assert any(w.endswith("/requirements/68/verification/stage") for w in ins("HWQ-05"))
    assert any(w.endswith("/annexes/ANNEX-ECR/module_specific_items/2/text") for w in ins("HWQ-05"))
    assert any(w.endswith("/requirements/58/text") for w in ins("HWQ-06"))
    assert any(w.endswith("/annexes/ANNEX-RF/deviations/0/proposed_control") for w in ins("HWQ-06"))
    assert any(w.endswith("W2_fo_lock1_decision_brief") for w in ins("HWQ-01"))
    assert items["HWQ-15"]["needed_by"]["gates_named"] == ["LOCK-1", "LOCK-2"]
    assert items["R-02"]["needed_by"]["gates_named"] == ["LOCK-1", "LOCK-2"]
    assert all(v == "LOCK-1" for v in items["PMQ-07"]["needed_by"]["via_items"].values())
    assert items["PMQ-07"]["needed_by"]["value"] == "LOCK-1"      # earliest over the relayed HWQ items (HWQ-04)
    assert items["R-14"]["needed_by"]["value"] == "UNSTATED"      # 'LOCK-1 brief' is a document name, masked
    assert all(items[f"OD-XE-{i}"]["needed_by"]["value"] == "UNSTATED" for i in range(1, 9))


def test_relevance_marks_carry_verbatim_anchors(doc):
    for it in doc["items"]:
        for key in ("can_change_budget", "can_change_a7_blocker"):
            c = it[key]
            assert c["reason"]
            if c["value"] in ("YES", "CAN_CHANGE", "MEASUREMENT_CONDITION_ONLY"):
                anc = c["anchor"]
                assert anc and anc["quote"]
                if anc["in"] == "item":
                    assert anc["quote"] in json.dumps(it["verbatim"], ensure_ascii=False) or anc["quote"] in str(it["verbatim"])
        a7 = it["can_change_a7_blocker"]
        assert all(b in (1, 2, 3) for b in a7["blockers"])
    s = doc["summary"]["can_change_a7_blocker"]
    assert set(s["3"]) >= {f"OD-XE-{i}" for i in range(1, 9)}
    assert "R-11" in s["2"] and "R-05" in s["1"]


def test_proposals_verbatim(doc):
    items = {it["register_id"]: it for it in doc["items"]}
    p1 = _load(P1F)
    for r in p1["reconciliation_items"]:
        props = items[r["id"]]["source_proposal_verbatim"]
        assert props[0]["text"] == r["proposal"]
    xe = _load(XE)
    for d in xe["open_owner_decisions"]:
        props = items[d["id"]]["source_proposal_verbatim"]
        if "proposed" in d:
            assert props[0]["text"] == d["proposed"]
        elif "PROPOSED" in json.dumps(d):
            assert any("PROPOSED" in p["text"] for p in props)
        else:
            assert props.startswith("NONE_IN_SOURCE")
    # inline PROPOSED text in relayed HWQ items (and the requirement text that names them) is extracted
    for h, want in (("HWQ-01", "requirements/77/text"), ("HWQ-06", "requirements/58/text"), ("HWQ-15", None)):
        props = items[h]["source_proposal_verbatim"]
        assert isinstance(props, list) and any("PROPOSED" in p["text"] for p in props), h
        if want:
            assert any(p["in"].endswith(want) for p in props), h
    assert isinstance(items["OD-XE-7"]["source_proposal_verbatim"], list)


def test_milestone(doc):
    m = doc["milestone"]
    assert m["supports"] == ["A"] and "No owner decision is taken" in m["statement"] and "NO_BASELINE_YET" in m["statement"]


def test_missing_pins_refuse(tmp_path):
    with pytest.raises(FileNotFoundError):
        B.verify_pins(str(tmp_path))
