"""Checks on the DRDO RFP requirement traceability matrix (docs/traceability/)."""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TDIR = os.path.join(ROOT, "docs", "traceability")
JSON_PATH = os.path.join(TDIR, "rtm_v1.json")
STATUSES = {"modeled", "partial", "open", "blocked_by_gate_3"}
METHODS = {"analysis", "test", "demonstration", "inspection"}
EVIDENCE_CLASSES = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}


def _doc():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_json_parses_and_has_requirements():
    d = _doc()
    assert d["schema"] == "abep-rtm-v1"
    assert d["rfp_document_in_repository"] is False
    assert len(d["requirements"]) > 0
    ids = [r["id"] for r in d["requirements"]]
    assert len(ids) == len(set(ids))


def test_every_requirement_has_source_status_and_verification_method():
    for r in _doc()["requirements"]:
        assert r["source"]["where"].strip(), r["id"]
        pr = r["source"]["page_ref"]
        if r["category"] == "derived_project":
            assert "not an RFP clause" in pr, r["id"]
        else:
            assert pr == "verify against RFP document", r["id"]
        assert r["status"] in STATUSES, r["id"]
        assert r["verification_method"] and set(r["verification_method"]) <= METHODS, r["id"]
        assert r["open_gap"].strip(), r["id"]


def test_numeric_values_carry_source_and_evidence_class():
    for r in _doc()["requirements"]:
        v = r["value"]
        if v is None:
            continue
        assert v["value_source"].strip(), r["id"]
        assert v["evidence_class"] in EVIDENCE_CLASSES, r["id"]


def test_nothing_gate3_blocked_claims_verified():
    d = _doc()
    for r in d["requirements"]:
        if r["gate3_dependent"] or r["status"] == "blocked_by_gate_3":
            assert r["status"] != "verified", r["id"]
            assert "verified" not in r["verification_status"].lower().replace("not_verified", ""), r["id"]
    # no row anywhere is marked verified (nothing is hardware-verified yet)
    assert all(r["status"] != "verified" for r in d["requirements"])
    # Hall-performance requirements must be marked gate-3 dependent
    for rid in ("RFP-THR-MIN", "RFP-THR-MAX", "RFP-PWR", "RFP-FIRING", "DER-NETDRAG", "DER-HALL-CLOSURE"):
        r = next(x for x in d["requirements"] if x["id"] == rid)
        assert r["gate3_dependent"] and r["status"] == "blocked_by_gate_3", rid


def test_model_refs_exist_in_code():
    for r in _doc()["requirements"]:
        for m in r["model_quantities"]:
            path, name = m["ref"].split("::")
            src = open(os.path.join(ROOT, path), encoding="utf-8").read()
            assert re.search(rf"^\s*(def|class)\s+{re.escape(name)}\b", src, re.M), m["ref"]


def test_evidence_files_exist_and_chains_cover_requirements():
    d = _doc()
    for r in d["requirements"]:
        for e in r["current_evidence"]:
            assert os.path.exists(os.path.join(ROOT, e["ref"])), e["ref"]
    ids = {r["id"] for r in d["requirements"]}
    chained = {c["requirement_id"] for c in d["chains"]}
    assert chained == ids
    for c in d["chains"]:
        assert all(c[k].strip() for k in ("design_feature", "verification", "evidence"))


def test_generated_files_are_current():
    out = subprocess.run([sys.executable, os.path.join(TDIR, "build_rtm.py"), "--check"],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stdout + out.stderr


# ---------------------------------------------------------------- cross-lane consistency (lane 24 hard gates)
HG_MATRIX = os.path.join(ROOT, "docs", "architecture_comparison", "hard_gates", "hard_gate_matrix_v1.json")


def _hg_matrix():
    import pytest
    if not os.path.exists(HG_MATRIX):
        pytest.skip("lane-24 hard-gate matrix not present in this checkout")
    with open(HG_MATRIX, encoding="utf-8") as f:
        return json.load(f)


def _row(d, rid):
    return next(r for r in d["requirements"] if r["id"] == rid)


def test_status_milestones_and_architecture_ids():
    d = _doc()
    assert d["status"] == "DRAFT_PENDING_OWNER"
    assert d["architectures"] == ["hall_only", "rf_hall", "ecr_hall"]
    assert d["milestones"]["supports"] and set(d["milestones"]["supports"]) <= {"A", "B", "C"}
    assert d["milestones"]["to_reach_B"].strip() and d["milestones"]["to_reach_C"].strip()
    assert "single-lens" in d["milestones"]["verification_protocol"]
    q = d["three_questions"]
    assert q["i_conditional_selection_now"] and q["ii_what_blocks_physics_backed_selection"] and q["iii_what_could_overturn"]
    txt = json.dumps(d).lower()
    assert not re.search(r"(hall_only|rf_hall|ecr_hall) (is|was) (eliminated|the baseline|selected|preferred)", txt)
    assert d["compliance_claim"].startswith("none")


def test_thresholds_match_rfpconstraints():
    sys.path.insert(0, ROOT)
    from abep_sim.constants import RFPConstraints
    rfp = RFPConstraints()
    d = _doc()
    lim = lambda rid: _row(d, rid)["value"]["limit"]
    assert f"{rfp.thrust_min_mN:g}" in lim("RFP-THR-MIN")
    assert f"{rfp.thrust_max_mN:g}" in lim("RFP-THR-MAX")
    assert f"{rfp.power_max_W / 1000:g}" in lim("RFP-PWR") and _row(d, "RFP-PWR")["value"]["unit"] == "kW"
    assert f"{rfp.mass_max_kg:g}" in lim("RFP-MASS")
    assert f"{rfp.ignition_hours:g}" in lim("RFP-FIRING")
    assert f"{rfp.mission_hours:g}" in lim("RFP-MISSION")
    assert lim("RFP-ALT") == f"{rfp.alt_min_km:g}-{rfp.alt_max_km:g}"


def test_hard_gate_xrefs_resolve_and_cover_matrix():
    m = _hg_matrix()
    d = _doc()
    gates = {g["id"]: g for g in m["gates"]}
    crit = {c["id"]: (g["id"], c) for g in m["gates"] for c in g["criteria"]}
    ods = {o["id"] for o in m["open_owner_decisions"]}
    rids = {r["id"] for r in m["rfp"]["recorded_in"]}
    used_gates, used_rids = set(), set()
    for r in d["requirements"]:
        x = r["hard_gate_xref"]
        assert x["note"].strip(), r["id"]
        assert set(x["gates"]) <= set(gates), r["id"]
        for c in x["criteria"]:
            assert c in crit and crit[c][0] in x["gates"], (r["id"], c)
        assert set(x["open_owner_decisions"]) <= ods, r["id"]
        assert set(r["rfp_record_refs"]) <= rids, r["id"]
        used_gates |= set(x["gates"])
        used_rids |= set(r["rfp_record_refs"])
    assert used_gates == set(gates), set(gates) - used_gates      # every lane-24 gate is traced
    assert used_rids == rids, rids - used_rids                      # every recorded RFP source is traced
    # thresholds agree with lane 24 where both carry a number
    lim = lambda rid: _row(d, rid)["value"]["limit"]
    for cid, rid, scale in (("G1.thrust_floor", "RFP-THR-MIN", 1), ("G1.thrust_ceiling", "RFP-THR-MAX", 1),
                            ("G1.peak_capability_25mN", "RFP-THR-MAX", 1), ("G2.bus_power_max", "RFP-PWR", 1000),
                            ("G3.mass_mev", "RFP-MASS", 1), ("G4.firing_life", "RFP-FIRING", 1),
                            ("G5.mission_capability", "RFP-MISSION", 1)):
        assert f"{crit[cid][1]['threshold'] / scale:g}" in lim(rid), (cid, rid)
        assert cid in _row(d, rid)["hard_gate_xref"]["criteria"], (cid, rid)


def test_open_readings_are_carried():
    _hg_matrix()
    d = _doc()
    thr = _row(d, "RFP-THR-MAX")
    assert "OD1" in thr["hard_gate_xref"]["open_owner_decisions"]
    assert {"G1.thrust_ceiling", "G1.peak_capability_25mN"} <= set(thr["hard_gate_xref"]["criteria"])
    ign = _row(d, "RFP-IGN-SUST")
    assert ign["category"] != "derived_project" and "OD14" in ign["hard_gate_xref"]["open_owner_decisions"]
    pwr = _row(d, "RFP-PWR")
    refs = {e["ref"] for e in pwr["current_evidence"]}
    assert "docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md" in refs
    assert "schemas/architecture_comparison/bus_power_boundary_v1.json" in refs
    assert "TBD" in pwr["statement"] and "not present" not in json.dumps(pwr)
    # every requirement lane 24 records but does not gate has its own row
    for rid in ("RFP-IC", "RFP-REDUND", "RFP-AO-TEST", "RFP-NASCENT-O"):
        assert _row(d, rid)["hard_gate_xref"]["gates"] == [], rid
    assert len(m_ := _hg_matrix()["rfp_requirements_recorded_not_gated"]) == 4, m_
