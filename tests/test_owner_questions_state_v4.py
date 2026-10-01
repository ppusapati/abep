"""Owner-question state v4 (A9.6 sec. 5-7, 18): v3 rows + every lane question since v3, re-classified; outputs current."""
import copy
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "docs" / "budgets" / "owner_decisions"


def _builder():
    spec = importlib.util.spec_from_file_location("state_v4", HERE / "build_owner_questions_state_v4.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _builder()
DOC = B.build()
V3 = json.loads((HERE / "owner_questions_state_v3.json").read_text(encoding="utf-8"))
ROWS = DOC["rows"]
BY_ID = {}
for _r in ROWS:
    BY_ID.setdefault(_r["id"], []).append(_r)
RECLASS = {"ANSWERED_BY_A9_4", "ANSWERED_BY_A9_5", "DERIVED", "TBD_OWNER", "SUPERSEDED"}


def _load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_outputs_are_current():
    for path, text in B.outputs(DOC).items():
        assert path.read_text(encoding="utf-8") == text, path.name
    json.loads((HERE / "owner_questions_state_v4.json").read_text(encoding="utf-8"))


def test_v3_pinned_and_every_v3_row_present():
    assert DOC["pins"]["state_v3"]["sha256"] == hashlib.sha256((HERE / "owner_questions_state_v3.json").read_bytes()).hexdigest()
    assert len(ROWS) >= len(V3["rows"])
    for r3, r4 in zip(V3["rows"], ROWS):
        assert (r3["no"], r3["id"]) == (r4["no"], r4["id"])
        if r3["status"] != "OPEN":
            assert r4 == r3, r3["id"]
        else:
            assert r4["v3_status"] == "OPEN" and r4["status"] in RECLASS, r3["id"]
            assert {k: v for k, v in r4.items() if k in r3 and k not in ("status", "status_detail")} == \
                   {k: v for k, v in r3.items() if k not in ("status", "status_detail")}
    assert sum(1 for r in ROWS if r.get("v3_status") == "OPEN") == V3["open_count"]
    assert not any(r["status"] == "OPEN" for r in ROWS)
    assert [r["no"] for r in ROWS] == list(range(1, len(ROWS) + 1))


LANE_CONTAINERS = [
    ("docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json", "open_owner_questions"),
    ("docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json", "a9_6_incorporation.derived_resolutions"),
    ("docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json", "open_owner_questions"),
    ("docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json", "open_owner_questions"),
    ("docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json", "open_owner_questions"),
    ("docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json", "open_owner_questions"),
    ("docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json", "open_owner_questions"),
    ("docs/procurement/rfq_a9_v2/rfq_a9_v2.json", "open_owner_questions.new"),
    ("docs/procurement/rfq_a9_v2/rfq_a9_v2.json", "open_owner_questions.closed_since_previous_revision"),
]


def test_every_lane_question_present_no_orphans():
    for path, loc in LANE_CONTAINERS:
        for q in B.resolve(_load(path), loc):
            rid = q["id"]
            if q.get("disposition") == "TBD_OWNER":  # remaining part of a split question -> carried by the base row
                base = BY_ID[rid.split(" ")[0]]
                assert base[0]["status"] == "TBD_OWNER" and any(rid in s for s in base[0]["related_sources"])
                continue
            assert rid in BY_ID, f"orphan lane question {rid} ({path})"
    for rid in B.EXPECTED_NEW:
        assert rid in BY_ID, rid
    for rid, status in (("P1Q-10", "ANSWERED_BY_A9_4"), ("P1Q-13", "ANSWERED_BY_A9_4"), ("P1Q-14", "ANSWERED_BY_A9_4"),
                        ("P2Q-05", "ANSWERED_BY_A9_4"), ("P1Q-15", "ANSWERED_BY_A9_5"), ("P1Q-16", "ANSWERED_BY_A9_5"),
                        ("P1Q-21", "DERIVED"), ("P1Q-22", "DERIVED"), ("P1Q-23 (a)", "DERIVED"), ("P1Q-23 (b)", "DERIVED"),
                        ("P1Q-19 (ext)", "DERIVED"), ("P1Q-19", "TBD_OWNER"), ("OQ-RFQV2-07", "DERIVED")):
        assert [r["status"] for r in BY_ID[rid]] == [status], rid


def test_every_added_row_has_a_resolvable_source():
    added = [r for r in ROWS if r["no"] > len(V3["rows"])]
    assert added
    for r in added:
        ref = r["source_ref"]
        hit = B.resolve(_load(ref["path"]), ref["locator"])
        assert isinstance(hit, (dict, str)), r["id"]
        if isinstance(hit, dict) and "id" in hit:
            assert hit["id"] in (r["id"], "A9.4 " + r["id"], "A9.5 " + r["id"]), r["id"]


def test_ids_carried_by_lanes_are_rows():
    carried = set()
    rfq = _load("docs/procurement/rfq_a9_v2/rfq_a9_v2.json")["open_owner_questions"]
    carried |= {x["id"] for x in rfq["carried_open_from_v1"] + rfq["carried_open_from_lanes"] + rfq["v1_questions_answered_since"]}
    carried |= set(_load("docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json")["existing_open_owner_questions_carried"])
    carried |= {x["id"] for x in _load("docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json")["open_questions_carried"]}
    carried |= set(_load("docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json")["open_register_status"])
    for q in _load("docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json")["open_owner_questions"]:
        if q.get("related_existing_open"):
            carried.add(q["related_existing_open"].split(" ")[0])
    missing = sorted(c for c in carried if c not in BY_ID)
    assert not missing, missing


def test_status_vocabulary_closed():
    vocab = set(DOC["status_vocabulary"])
    assert vocab == (set(V3["status_vocabulary"]) - {"OPEN"}) | {"ANSWERED_BY_A9_4", "ANSWERED_BY_A9_5", "DERIVED", "TBD_OWNER"}
    assert {r["status"] for r in ROWS} <= vocab
    assert not any("PASS" in r["status"] for r in ROWS)
    assert DOC["counts"] == {k: sum(1 for r in ROWS if r["status"] == k) for k in DOC["counts"]}
    assert sum(DOC["counts"].values()) == len(ROWS)


def test_derived_rows_name_rule_and_existing_artifact():
    derived = [r for r in ROWS if r["status"] == "DERIVED"]
    assert derived
    for r in derived:
        assert r.get("derived_rule") and r.get("implemented_in") and r.get("implemented_paths"), r["id"]
        for p in r["implemented_paths"]:
            assert (ROOT / p).exists(), (r["id"], p)


def test_tbd_owner_rows_have_dependency_and_blocker():
    tbd = [r for r in ROWS if r["status"] == "TBD_OWNER"]
    assert len(tbd) == DOC["tbd_owner_count"]
    for r in tbd:
        assert r["dependency"] and set(r["dependency"]) <= set(DOC["dependency_vocabulary"]), r["id"]
        assert r["blocks"] and set(r["blocks"]) <= set(DOC["blocks_vocabulary"]), r["id"]
        assert ("BLOCKS_P1_LATER_STAGE" in r["blocks"]) == bool(r.get("blocks_stage")), r["id"]
        if "NOTHING_IMMEDIATE" in r["blocks"]:
            assert r["blocks"] == ["NOTHING_IMMEDIATE"], r["id"]
        assert r["classification_basis"], r["id"]
    # the owner-stated examples of A9.6 sec. 7 dependencies are used where they apply
    assert "MEASURED_H1_DISCHARGE_CURRENT" in BY_ID["P1Q-07"][0]["dependency"]
    assert "P2_IMPEDANCE_DATA" in BY_ID["ICPQ-11"][0]["dependency"]


def test_answered_rows_point_into_pinned_decisions():
    for r in ROWS:
        if r["status"] in ("ANSWERED_BY_A9_4", "ANSWERED_BY_A9_5"):
            path, key = r["answer_pointer"].split(" decisions.")
            dec = _load(path)
            assert key == r["id"] and key in dec["decisions"]
            assert r["answer_sha256"] == hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            assert r["answer_excerpt"].startswith(dec["decisions"][key]["status"])


def test_groups_disjoint_and_live():
    seen = set()
    for g in DOC["question_groups"]:
        assert g["relation"] in DOC["group_relation_vocabulary"]
        for m in g["members"]:
            assert m not in seen
            seen.add(m)
            assert [r.get("group") for r in BY_ID[m] if r["status"] == "TBD_OWNER"] == [g["id"]]


def test_historical_blobs_match_git_when_available():
    for key, blob in B.HIST_BLOBS.items():
        try:
            data = subprocess.run(["git", "show", f"{blob['commit']}:{blob['path']}"], cwd=ROOT, capture_output=True,
                                  check=True, timeout=30).stdout
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pytest.skip("git history not available")
        assert hashlib.sha256(data).hexdigest() == blob["sha256"], key
        qs = {q["id"]: q for q in json.loads(data)["open_owner_questions"]}
        for rid, h in B.HISTORICAL_QUESTIONS.items():
            if h["blob"] == key:
                assert qs[rid]["question"] == h["question"], rid


def test_fail_closed_on_unclassified_or_missing_inputs(monkeypatch):
    orig = dict(B.TBD)
    tbd = dict(orig)
    tbd.pop("P2Q-10")  # an unclassified lane question has no hidden default
    monkeypatch.setattr(B, "TBD", tbd)
    with pytest.raises(SystemExit):
        B.build()
    monkeypatch.setattr(B, "TBD", orig)
    bad = copy.deepcopy(B.DERIVED_V3)
    bad["MQ-08"]["implemented_paths"] = ["docs/does/not/exist.json"]
    monkeypatch.setattr(B, "DERIVED_V3", bad)
    with pytest.raises(SystemExit):
        B.build()
    with pytest.raises(KeyError):
        B.resolve({"a": [{"id": "X"}]}, "a[id=Y]")


def test_no_forbidden_substring_in_code():
    needle = "xe_" + "ledger"
    for p in (HERE / "build_owner_questions_state_v4.py", Path(__file__)):
        assert needle not in p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------------------------------------------------
# register completion (lane A9_6_M16): lane-24 open decisions carried by RVM rows (RVM-ID-11) and RVMQ-01 (RVM-ID-10)
# ---------------------------------------------------------------------------------------------------------------------
HGM_REL = "docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json"
RVM_REL = "docs/requirements/rvm_a9/rvm_a9_v1.json"
ANS_REL = "docs/decisions/OD_2026_09_29_owner_answers_147.json"
REGISTERED = ["OD2", "OD3", "OD5", "OD6", "OD12", "OD13", "OD14", "RVMQ-01"]


def test_register_completion_rows_present_once_with_pinned_source():
    assert DOC["pins"]["lane24_hard_gate_matrix"]["sha256"] == hashlib.sha256((ROOT / HGM_REL).read_bytes()).hexdigest()
    assert DOC["pins"]["owner_answers_147"]["sha256"] == hashlib.sha256((ROOT / ANS_REL).read_bytes()).hexdigest()
    hgm = _load(HGM_REL)
    for rid in REGISTERED:
        assert len(BY_ID.get(rid, [])) == 1, rid
        r = BY_ID[rid][0]
        assert r["no"] > len(V3["rows"])
        if rid.startswith("OD"):
            od = B.resolve(hgm, r["source_ref"]["locator"])
            assert r["source_ref"]["path"] == HGM_REL and od["id"] == rid
            assert r["question"] == od["topic"] and r["alternatives"] == od["options"]
        assert r["rvm_rows"], rid


def test_every_lane24_decision_carried_by_an_rvm_row_is_registered():
    rvm = _load(RVM_REL)
    carried = {o["id"] for row in rvm["rows"] for o in row.get("open_readings", []) if o.get("register") == HGM_REL}
    assert carried == set(B.LANE24_REGISTERED)
    for oid in carried:
        assert BY_ID[oid][0]["status"] in ("TBD_OWNER", "SUPERSEDED")
        for row in rvm["rows"]:
            if any(o["id"] == oid for o in row.get("open_readings", [])):
                assert row["id"] in BY_ID[oid][0]["rvm_rows"]
    for q in rvm["open_owner_questions"]:
        assert q["id"] in BY_ID, q["id"]
    for dem in ("RVM-ID-10", "RVM-ID-11"):
        assert B.resolve(rvm, f"interface_demands[id={dem}]")


def test_register_completion_classification_is_conservative():
    answers = {a["row"]: a for a in _load(ANS_REL)["answers"]}
    for rid in REGISTERED:
        r = BY_ID[rid][0]
        if rid in B.LANE24_SUPERSEDED:
            sb = r["superseded_by"]
            assert r["status"] == "SUPERSEDED"
            assert sb["owner_answer_verbatim"] == answers[sb["owner_row"]]["owner_answer_verbatim"]
            assert sb["sha256"] == DOC["pins"]["owner_answers_147"]["sha256"]
            for p in r["implemented_paths"]:
                assert (ROOT / p).exists()
        else:
            assert r["status"] == "TBD_OWNER", rid
            assert "OWNER_JUDGMENT" in r["dependency"]
            for rel in r.get("related_owner_answers", []):
                assert rel["owner_answer_verbatim"] == answers[rel["owner_row"]]["owner_answer_verbatim"]
                assert rel["why_not_settled"]
    assert set(B.LANE24_SUPERSEDED) == {"OD13"}
    assert "OFFICIAL_RFP_TEXT" in DOC["dependency_vocabulary"]


def test_register_completion_grouped():
    groups = {g["id"]: g for g in DOC["question_groups"]}
    assert groups["DG-RFP-ENVELOPE"]["members"] == ["OD2", "OD3"]
    assert groups["DG-RFP-START"]["members"] == ["OD5", "OD14"]
    assert groups["DG-RFP-UNGATED"]["members"] == ["OD12", "RVMQ-01"]
    assert "OD6" in groups["DG-XE-FUNC"]["members"]
    assert BY_ID["OD13"][0].get("group") is None


def test_register_completion_fails_closed(monkeypatch):
    monkeypatch.setattr(B, "LANE24_REGISTERED", [x for x in B.LANE24_REGISTERED if x != "OD5"])
    with pytest.raises(SystemExit):
        B.build()
    monkeypatch.setattr(B, "LANE24_REGISTERED", B.LANE24_REGISTERED + ["OD5"])
    monkeypatch.setattr(B, "HGM_SHA", "0" * 64)
    with pytest.raises(SystemExit):
        B.build()
