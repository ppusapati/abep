"""Tests for the A9.7 F5 H-1 freeze-candidate definition (lane fo_a9_7_f5_h1_freeze_candidate).

Run: python -m pytest -q tests/test_h1_freeze_candidate.py   (about 1-2 s: one deterministic in-memory rebuild).
"""
from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "hardware" / "h1_freeze_candidate"
SCRIPT = LANE / "build_h1_freeze_candidate.py"
JSON_PATH = LANE / "h1_freeze_candidate_v1.json"
MD_PATH = LANE / "H1_FREEZE_CANDIDATE.md"

FREEZE = {"FREEZE_CANDIDATE", "OPEN", "TBD_AFTER_EVIDENCE", "TBD_OWNER"}
EVIDENCE = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "owner-allocation"}
PARALLEL_MODULES = ("abep_sim.design.intake_synthesis", "abep_sim.design.filter_stage",
                    "abep_sim.design.compressor_synthesis", "abep_sim.design.icp_geometry_synthesis")


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_h1_freeze_candidate_t", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def builder():
    return _load_builder()


@pytest.fixture(scope="module")
def doc(builder):
    return builder.build_document()


@pytest.fixture(scope="module")
def committed():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def _walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _walk(v, f"{path}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk(v, f"{path}/{i}")
    else:
        yield path, o


def _numbers(v):
    return [x for _, x in _walk(v) if isinstance(x, (int, float)) and not isinstance(x, bool)]


def test_committed_files_are_current(builder, doc):
    assert builder.dumps(doc) == JSON_PATH.read_text(encoding="utf-8")
    assert builder.render_md(doc) == MD_PATH.read_text(encoding="utf-8")
    assert builder.main(["--check"]) == 0


def test_required_sections(committed):
    for key in ("parameters", "interface_demands", "open_owner_questions", "m16_impact", "pins",
                "consumed_deliverables", "hall_response_domain", "bz_reference", "anode_investigation",
                "x_hall_design_space", "consistency_checks", "freeze_rollup", "a9_7_f5_coverage"):
        assert key in committed, key
    assert committed["architecture_status"] == "INVESTIGATION_HYPOTHESIS"
    assert committed["article_freeze_state"].startswith("NOT_FROZEN")


def test_pins_and_consumed_hashes(committed, builder):
    for key, (rel, sha) in builder.PINS.items():
        assert _sha(rel) == sha, rel
        assert committed["pins"][key] == {"path": rel, "sha256": sha}
    for key, v in committed["consumed_deliverables"].items():
        assert _sha(v["path"]) == v["sha256"], v["path"]


def test_pin_mismatch_is_refused():
    mod = _load_builder()
    rel, _ = mod.PINS["H21"]
    mod.PINS = dict(mod.PINS)
    mod.PINS["H21"] = (rel, "0" * 64)
    with pytest.raises(SystemExit, match="REFUSED"):
        mod.build_document()


def test_parameter_rows(committed):
    params = committed["parameters"]
    ids = [p["id"] for p in params]
    assert len(ids) == len(set(ids))
    for p in params:
        for f in ("id", "group", "name", "value", "units", "tolerance", "evidence_class", "source", "basis",
                  "freeze_status", "freeze_point", "evidence_to_freeze_candidate"):
            assert f in p, (p["id"], f)
        assert p["freeze_status"] in FREEZE, p["id"]
        assert p["freeze_point"] in committed["freeze_points"], p["id"]
        tbd = isinstance(p["value"], str) and p["value"].startswith("TBD")
        if tbd:
            assert p["evidence_class"] is None, p["id"]
            assert p["freeze_status"] != "FREEZE_CANDIDATE", p["id"]
        else:
            assert p["evidence_class"] in EVIDENCE, p["id"]
        if p["freeze_status"] != "FREEZE_CANDIDATE":
            assert p["evidence_to_freeze_candidate"], p["id"]
        assert p["source"], p["id"]
    counts = {s: sum(p["freeze_status"] == s for p in params) for s in FREEZE}
    assert counts == committed["freeze_rollup"]["counts"]
    # an engineering article with OPEN / TBD items is not frozen; every group is populated
    assert counts["OPEN"] + counts["TBD_AFTER_EVIDENCE"] + counts["TBD_OWNER"] > 0
    assert {p["group"] for p in params} == set(committed["groups"])


def test_sources_resolve_and_hashes_match(committed, builder):
    for p in committed["parameters"]:
        for s in p["source"]:
            assert _sha(s["path"]) == s["sha256"], (p["id"], s["path"])
            if s["path"].endswith(".json") and s["pointer"] != "/":
                builder.resolve(json.loads((REPO / s["path"]).read_text(encoding="utf-8")), s["pointer"])


def test_a97_f5_bullets_covered(committed):
    a97 = (REPO / "docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md").read_text(encoding="utf-8")
    cov = committed["a9_7_f5_coverage"]
    assert len(cov) == 8
    for c in cov:
        assert f"* {c['bullet']}" in a97
        assert c["parameters"], c["bullet"]


def test_anode_statuses_and_investigation_list(committed):
    st = committed["anode_statuses"]
    assert st["316L_FLIGHT_ANODE"] == "REJECTED_AS_CURRENT_BASELINE"
    assert st["FINAL_ANODE_MATERIAL"] == "OPEN"
    assert st["ANODE_THERMAL_CLOSURE"] == "UNRESOLVED"
    by_id = {p["id"]: p for p in committed["parameters"]}
    assert by_id["H1F-AN-04"]["value"] == "REJECTED_AS_CURRENT_BASELINE"
    assert by_id["H1F-AN-05"]["freeze_status"] != "FREEZE_CANDIDATE"
    assert by_id["H1F-AN-06"]["freeze_status"] != "FREEZE_CANDIDATE"
    assert by_id["H1F-AN-07"]["value"].startswith("TBD")  # no invented anode temperature target (row 87)
    a92 = (REPO / "docs/decisions/OD_2026_09_30_A9_2_A907_FOLLOWUP_OWNER_DECISIONS.md").read_text(encoding="utf-8")
    items = committed["anode_investigation"]
    assert len(items) == 8
    for x in items:
        assert f"* {x['item_verbatim']}" in a92
        assert x["status"] == "OPEN"
    # no refractory metal selected for its melting point
    for p in committed["parameters"]:
        if p["group"] in ("AN", "MA") and p["freeze_status"] == "FREEZE_CANDIDATE":
            assert not any(m in json.dumps(p["value"]) for m in ("tungsten", "molybdenum", "platinum", "TZM"))


def test_no_hall_performance(committed):
    ens = json.loads((REPO / "hallthruster_bridge/ensemble/transport_ensemble_v0.json").read_text(encoding="utf-8"))
    assert ens["members"] == []
    hr = committed["hall_response_domain"]
    assert hr["admitted_members"] == [] and hr["admitted_domains"] == [] and hr["p5_n2_v1_promotable"] == []
    assert set(hr["performance_outputs"].values()) == {"NOT_EVALUATED"}
    for r in committed["x_hall_design_space"]["probe_evaluations"]:
        assert r["performance"] == "NOT_EVALUATED"
    perf = [d for d in committed["interface_demands"] if d["id"] == "IFS-F7-02"][0]
    assert perf["status"] == "NOT_EVALUATED"
    # no thrust / current / efficiency value in the parameter table
    for p in committed["parameters"]:
        assert "mN" not in p["units"], p["id"]


def test_no_p5_value_transferred(committed):
    p5_vals = set()
    for rel in ("hallthruster_bridge/bfield/p5_vacuum_Br_centerline_1p6kW.csv",
                "hallthruster_bridge/bfield/p5_vacuum_Br_centerline_3p0kW.csv"):
        rows = [r for r in (REPO / rel).read_text(encoding="utf-8").splitlines() if r and not r.startswith("#")]
        for r in csv.DictReader(rows):
            p5_vals.add(round(float(r["Br_G"]), 2))
    p5_vals.add(130.0)  # P5-N2 peak radial field (Table 2 analog AN-P5N2)
    for p in committed["parameters"]:
        if p["group"] == "BZ":
            for x in _numbers(p["value"]):
                assert round(float(x), 2) not in p5_vals, (p["id"], x)
    bz = committed["bz_reference"]
    assert bz["vyovrinda_specific_bz_evidence"].startswith("NONE")
    assert {v["role"] for v in bz["p5_files"].values()} == {"REFERENCE_FOR_P5_ONLY"}
    for p in committed["parameters"]:
        if p["group"] == "BZ":
            assert p["freeze_status"] != "FREEZE_CANDIDATE", p["id"]


def test_no_pass_and_no_winner(committed):
    for path, v in _walk(committed):
        if isinstance(v, str):
            assert v.strip().upper() != "PASS", path
            if path.endswith(("/status", "/result", "/freeze_status")):
                assert "PASS" not in v.upper().split("_"), path
    text = JSON_PATH.read_text(encoding="utf-8").lower()
    assert "winner\"" not in text and "selected_design_point" not in text


def test_forbidden_substring_absent():
    needle = "xe" + "_ledger"
    for p in (SCRIPT, JSON_PATH, MD_PATH, Path(__file__)):
        assert needle not in p.read_text(encoding="utf-8"), p.name


def test_interface_demands(committed, builder):
    ids = {d["id"]: d for d in committed["interface_demands"]}
    f4 = [d for d in committed["interface_demands"] if d["direction"] == "H-1 <- F4"]
    joined = " ".join(d["quantity"] for d in f4)
    for q in ("mdot_s", "pressure P", "temperature T", "x_s", "transient quality"):
        assert q in joined, q
    for d in f4:
        assert isinstance(d["value"], str) and d["value"].startswith("TBD"), d["id"]
        assert d["counterpart"].startswith("abep_sim/design/plenum_feed.py"), d["id"]     # integration pass
    dirs = {d["direction"] for d in committed["interface_demands"]}
    assert "H-1 -> F4" in dirs and "H-1 -> F6" in dirs and "H-1 <- F6" in dirs
    for d in committed["interface_demands"]:
        if any(d["direction"].endswith(x) or f"<- {x} " in d["direction"] or f"-> {x}" in d["direction"]
               for x in ("F0", "F1", "F2", "F3", "F4", "F6", "F7/F8", "F9")):
            assert "PENDING" not in d["counterpart"], d["id"]          # resolved to real paths + record ids
    assert "IFD-F6-03" in ids
    mc02 = next(p for p in committed["parameters"] if p["id"] == "H1F-MC-02")
    assert mc02["freeze_status"] == "OPEN"            # PHY-01: assumed analog choice, not owner-given
    src = (Path(__file__).resolve().parents[1] / "docs/hardware/h1_freeze_candidate/build_h1_freeze_candidate.py").read_text()
    for m in PARALLEL_MODULES:                       # the H-1 builder never imports the parallel lanes' modules
        assert ("import " + m) not in src and ("from " + m) not in src, m


def test_geometric_admissibility(builder):
    xdef = builder.x_hall_definition()
    r = builder.geometric_admissibility(12.0, 70.0, 103.2, "worst_case_assumptions", xdef)
    assert r["status"] == "WITHIN_DECLARED_GEOMETRIC_WINDOWS" and r["performance"] == "NOT_EVALUATED"
    r = builder.geometric_admissibility(12.0, 70.0, 200.0, "nominal_assumptions", xdef)  # L/h 16.7 > 12
    assert r["status"] == "OUTSIDE_DECLARED_GEOMETRIC_WINDOWS" and any("L/h" in v for v in r["violations"])
    r = builder.geometric_admissibility(12.0, 46.0, 103.2, "worst_case_assumptions", xdef)  # below the coil floor
    assert r["status"] == "OUTSIDE_DECLARED_GEOMETRIC_WINDOWS" and any("floor" in v for v in r["violations"])
    r = builder.geometric_admissibility(25.0, 100.0, 250.0, "nominal_assumptions", xdef)
    assert r["status"] == "OUT_OF_DOMAIN"
    r = builder.geometric_admissibility(float("nan"), 70.0, 100.0, "nominal_assumptions", xdef)
    assert r["status"] == "OUT_OF_DOMAIN"
    with pytest.raises(ValueError):
        builder.geometric_admissibility(12.0, 70.0, 103.2, "optimistic", xdef)
    statuses = {"WITHIN_DECLARED_GEOMETRIC_WINDOWS", "OUTSIDE_DECLARED_GEOMETRIC_WINDOWS", "OUT_OF_DOMAIN"}
    assert all(builder.geometric_admissibility(h, d, 10 * h, a, xdef)["status"] in statuses
               for h in (8.0, 12.0, 17.0) for d in (40.0, 60.0, 100.0)
               for a in ("nominal_assumptions", "worst_case_assumptions"))


def test_admissibility_does_not_mutate_definition(builder):
    xdef = builder.x_hall_definition()
    before = copy.deepcopy(xdef)
    builder.geometric_admissibility(12.0, 70.0, 103.2, "nominal_assumptions", xdef)
    assert xdef == before


def test_consistency_checks(committed):
    res = {c["id"]: c["result"] for c in committed["consistency_checks"]}
    assert res.pop("CC-07") == "DISCREPANCY_RECORDED"
    assert set(res.values()) == {"CONSISTENT"}


def test_design_point_not_selected(committed):
    by_id = {p["id"]: p for p in committed["parameters"]}
    cp = by_id["H1F-CH-11"]
    assert cp["freeze_status"] == "TBD_OWNER" and cp["value"].startswith("TBD")
    assert "NOT a design selection" in cp["note"]
    for pid in ("H1F-CH-02", "H1F-CH-03", "H1F-CH-04", "H1F-CH-05", "H1F-CH-10"):
        assert by_id[pid]["freeze_status"] == "OPEN"


def test_owner_questions_are_new(committed):
    oq4 = json.loads((REPO / "docs/budgets/owner_decisions/owner_questions_state_v4.json").read_text(encoding="utf-8"))
    existing = {r["id"] for r in oq4["rows"]}
    for q in committed["open_owner_questions"]:
        assert q["id"] not in existing
        assert q["id"].startswith("F5-OQ-")
    for q in committed["existing_owner_questions_touched"]:
        assert q["id"] in existing


def test_m16_no_state_change(committed):
    rows = {m["m16_row"]: m for m in committed["m16_impact"]}
    assert set(rows) == {9, 10, 13, 20, 21}
    for m in rows.values():
        assert m["state_change"] is False and m["proposed_state"] == m["v4_state"]


def test_coil_mass_correction_carried(committed):
    by_id = {p["id"]: p for p in committed["parameters"]}
    v = by_id["H1F-CO-13"]["value"]
    assert v["complete_coil_copper_estimate_kg_RP1_fNI2"] == 1.579
    assert v["sensitivity_basis_60W_fixed_NI_kg_NOT_coil_mass"] == 0.136
    assert by_id["H1F-MC-08"]["value"]["total_kg"] == 3.504


def test_no_freeze_candidate_depends_on_open_row(committed):
    """PHY-03: a FREEZE_CANDIDATE row never names (in value, basis or evidence note) an H1F row that is not itself a
    FREEZE_CANDIDATE, and the coil-supply channel count (from the OPEN coil arrangement MC-02) is not owner-given."""
    import re
    by_id = {p["id"]: p for p in committed["parameters"]}
    for p in committed["parameters"]:
        if p["freeze_status"] != "FREEZE_CANDIDATE":
            continue
        txt = json.dumps([p["value"], p["basis"], p.get("evidence_note", "")])
        deps = set(re.findall(r"H1F-[A-Z]{2}-\d\d", txt)) - {p["id"]}
        assert all(by_id[d]["freeze_status"] == "FREEZE_CANDIDATE" for d in deps), (p["id"], deps)
        h21 = [s for s in p["source"] if "h2_1_hall_chamber_magnet" in s["path"]]
        assert not any(s["pointer"].startswith(f"/design_parameters/{i}/") for s in h21 for i in (26,)), p["id"]
    assert by_id["H1F-MC-02"]["freeze_status"] == "OPEN"
    co14 = by_id["H1F-CO-14"]
    assert co14["freeze_status"] == "OPEN" and co14["evidence_class"] == "assumed"
    assert "trim" in co14["value"] and "H1F-MC-02" in co14["value"]
    co01 = by_id["H1F-CO-01"]
    assert co01["freeze_status"] == "FREEZE_CANDIDATE" and "trim" not in co01["value"]
