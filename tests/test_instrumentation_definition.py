"""W4 instrumentation definition (fo_instrumentation_definition; docs/experiments/instrumentation/).

Checks that the definition reproduces byte for byte from its pinned inputs, that every number carries unit, evidence
class and source, that it stays a DRAFT with PROPOSED non-RFP thresholds, that it covers every lane-25 measurement, every
bus_power_boundary_v1 component (exactly once), every owner-named W4 item and every held-out validation observable,
that the derivations are correct, that it names no preferred architecture, and that missing or changed inputs raise.
Fast (well under a second of computation); no Julia, no simulator run.
"""
from __future__ import annotations

import ast
import functools
import importlib.util
import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs" / "experiments" / "instrumentation"
SCRIPT = DIR / "build_instrumentation_definition.py"


def _load(root_override: Path | None = None):
    spec = importlib.util.spec_from_file_location("_test_instr_builder", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if root_override is not None:
        mod.ROOT = root_override
        mod.HERE = root_override / "docs" / "experiments" / "instrumentation"
    return mod


B = _load()


@functools.lru_cache(maxsize=None)
def _built():
    return B.build()


@functools.lru_cache(maxsize=None)
def _stored():
    return json.loads((DIR / "instrumentation_definition_v1.json").read_text(encoding="utf-8"))


def test_pinned_inputs_verify():
    pins = B.verify_inputs()
    assert sorted(pins) == sorted(B.PINNED)


def test_reproduces_byte_for_byte():
    doc = _built()
    assert (DIR / "instrumentation_definition_v1.json").read_text(encoding="utf-8") == B.dumps(doc)
    assert (DIR / "INSTRUMENTATION_DEFINITION.md").read_text(encoding="utf-8") == B.render_md(doc)
    assert B.main(["--check"]) == 0


def test_number_discipline_and_tamper_detection():
    doc = _stored()
    B.validate(doc)
    assert B.numeric_leaf_errors(doc) == []
    bad = json.loads(json.dumps(doc))
    bad["instruments"][0]["required_uncertainty"]["bare"] = 0.5
    assert B.numeric_leaf_errors(bad)
    with pytest.raises(ValueError):
        B.validate(bad)
    bad = json.loads(json.dumps(doc))
    bad["derived"]["k_one_sided"]["evidence_class"] = "guessed"
    assert B.numeric_leaf_errors(bad)


def test_draft_status_proposed_thresholds_and_rfp_values():
    doc = _stored()
    assert doc["status"] == "DRAFT_PENDING_OWNER"
    for t in doc["proposed_thresholds"]:
        assert t["status"] == "PROPOSED" and t["evidence_class"] == "assumed"
    from abep_sim.constants import RFP
    rfp = doc["requirement_basis"]["rfp"]
    assert rfp["thrust_min"]["value"] == RFP.thrust_min_mN == 12.0
    assert rfp["thrust_capability"]["value"] == RFP.thrust_max_mN == 25.0
    assert rfp["power_max"]["value"] == RFP.power_max_W == 1500.0
    assert all(v["status"] == "RFP" for v in rfp.values())
    bad = json.loads(json.dumps(doc))
    bad["proposed_thresholds"][0]["status"] = "DECIDED"
    with pytest.raises(ValueError):
        B.validate(bad)


def test_requirement_basis_equals_lane25():
    doc = _stored()
    draft = json.loads((ROOT / B.L25).read_text(encoding="utf-8"))
    for n, row in doc["requirement_basis"]["lane25_by_n"].items():
        plan = draft["derived_numbers"]["plan_by_n"][n]
        for key in ("u_T_max", "u_P_max", "u_inst_max", "sigma_lnR_max", "k_primary"):
            assert row[key]["value"] == plan[key]["value"]  # copied bit-for-bit (A3-repair-2)
    assert doc["requirement_basis"]["lane25_by_n"]["4"]["u_T_max"]["value"] == pytest.approx(0.0049836144, rel=1e-6)


def test_bus_power_channels_cover_v1_exactly_once():
    doc = _stored()
    comps = [r["component"] for r in doc["bus_power_channels"]]
    expected = list(B.V1_COMMON) + ["rf_source", "ecr_source", "ecr_magnet"]
    assert sorted(comps) == sorted(expected) and len(comps) == len(set(comps))
    rows = {r["component"]: r for r in doc["bus_power_channels"]}
    assert rows["compressor"]["lab_status"] == "ABSENT_IN_LAB"
    assert rows["rf_source"]["architectures"] == ["rf_hall"]
    assert rows["ecr_source"]["architectures"] == ["ecr_hall"] == rows["ecr_magnet"]["architectures"]
    for c in B.V1_COMMON:
        assert rows[c]["architectures"] == ["hall_only", "rf_hall", "ecr_hall"]
    # cross-check against the contract module's source when it is present (read as text, never imported)
    ab = ROOT / "abep_sim" / "arch_boundary.py"
    if ab.exists():
        tree = ast.parse(ab.read_text(encoding="utf-8"))
        found = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name in ("COMMON_COMPONENTS", "PREIONIZER_COMPONENTS", "BOUNDARY_VERSION"):
                    found[name] = ast.literal_eval(node.value)
        assert found["BOUNDARY_VERSION"] == B.BOUNDARY_VERSION
        assert tuple(found["COMMON_COMPONENTS"]) == B.V1_COMMON
        assert {k: tuple(v) for k, v in found["PREIONIZER_COMPONENTS"].items()} == B.V1_PREIONIZER


def test_coverage_lane25_owner_items_and_validation_observables():
    doc = _stored()
    draft = json.loads((ROOT / B.L25).read_text(encoding="utf-8"))
    covered = {m for i in doc["instruments"] for m in i["lane25_measurements"]}
    assert covered == {m["id"] for m in draft["measurements"]}
    text = " ".join((i["name"] + " " + i["quantity"]).lower() for i in doc["instruments"])
    for item in ("thrust stand", "bus-power", "discharge", "mass flow", "feed pressure", "feed temperature",
                 "background pressure", "b(z)", "extinction", "rga", "optical emission", "exb", "retarding potential",
                 "divergence", "langmuir", "i_d(t)"):
        assert item in text, item
    od = json.loads((ROOT / B.OD).read_text(encoding="utf-8"))
    assert doc["owner_disposition"]["statement"] == od["workstreams"]["W4_instrumentation"]
    vo = {v["id"] for v in doc["validation_observables"]}
    assert len(vo) == 10
    for v in vo:
        assert any(v in i["validation_observables"] for i in doc["instruments"]), v
    for d in doc["decision_quantities"]:
        assert any(i["serves"][d["id"]] == "D" for i in doc["instruments"]), d["id"]
    assert {d["id"] for d in doc["decision_quantities"]} == {"DQ-RARCH", "DQ-TABS", "DQ-PBUS", "DQ-SUST", "DQ-KNEE"}


def test_milestones_and_compliance():
    doc = _stored()
    ms = doc["milestones"]
    assert ms["supports"] == ["A"]
    for m in ("A", "B", "C"):
        assert ms[m]["needs_next"]
    assert any("admitted Hall transport closure" in s for s in ms["B"]["needs_next"])
    text = json.dumps(doc)
    for bad in ("sgb-screen", "winner", "preferred architecture", "ELIMINATED"):
        assert bad not in text
    for arch in ("hall_only", "rf_hall", "ecr_hall"):
        assert arch in text
    statuses = {i["feasibility"]["status"] for i in doc["instruments"]}
    assert statuses <= {"FEASIBLE_IN_PRINCIPLE", "AT_RISK", "TBD", "OPTIONAL", "INFEASIBLE_AS_STATED"}
    assert "AT_RISK" in statuses                          # honest flags exist (thrust stand, RF power, flow, ...)
    refs = {r["id"]: r for r in doc["references"]}
    for r in refs.values():
        acc = r["access"]
        if any(w in acc for w in ("abstract only", "metadata only", "not read")):
            assert "verify" in acc or "not re-accessed" in acc, r["id"]


def test_derivations():
    k = B.k_one_sided(0.05)
    assert k == pytest.approx(1.6448536, rel=1e-6)
    g = B.lower_gate(12.0, 0.01, k)
    assert g["pass_min"] * (1 - k * 0.01) == pytest.approx(12.0)
    assert g["fail_max"] * (1 + k * 0.01) == pytest.approx(12.0)
    assert g["fail_max"] < 12.0 < g["pass_min"]
    p = B.upper_gate(1500.0, 0.01, k)
    assert p["pass_max"] < 1500.0 < p["fail_min"]
    # channel-sum lemma on deterministic examples
    for powers in ([1.0], [900.0, 50.0, 50.0], [300.0, 300.0, 300.0, 300.0], [1e3, 1e-3]):
        us = [0.005] * len(powers)
        assert B.channel_sum_u(powers, us) <= 0.005 + 1e-15
    assert B.channel_sum_u([1.0], [0.005]) == pytest.approx(0.005)
    # mass fraction uncertainty vs a finite-difference propagation
    m1, m2, u1, u2 = 0.2, 0.8, 0.01, 0.02
    w = m1 / (m1 + m2)
    h = 1e-7
    dw1 = ((m1 * (1 + h)) / (m1 * (1 + h) + m2) - w) / h
    dw2 = (m1 / (m1 + m2 * (1 + h)) - w) / h
    assert B.mass_fraction_u(w, u1, u2) == pytest.approx(math.hypot(dw1 * u1, dw2 * u2), rel=1e-5)
    # one-way flux: n v_mean / 4 x m
    from abep_sim.constants import K_B, M_SPECIES
    pPa, T, m = 1e-3, 300.0, M_SPECIES["N2"]
    n = pPa / (K_B * T)
    vbar = math.sqrt(8 * K_B * T / (math.pi * m))
    assert B.one_way_mass_flux(pPa, m, T, K_B) == pytest.approx(n * vbar / 4 * m, rel=1e-12)
    # stop sensitivity at plan reproduces h = delta/2 and the package's R < 0.97531
    doc = _stored()
    row = doc["derived"]["stop_rule_sensitivity_n4"]["x1.0"]
    assert row["h"]["value"] == pytest.approx(0.025, rel=1e-6)
    assert row["R_stop_below"]["value"] == pytest.approx(0.97531, abs=1e-5)
    assert row["unresolved_impossible"] == "boundary"
    assert doc["derived"]["stop_rule_sensitivity_n4"]["x3.0"]["equivalent_reachable"] == "no"
    for bad in (lambda: B.lower_gate(12.0, 0.7, k), lambda: B.mfc_relative_u(0.01, 1.5),
                lambda: B.mass_fraction_u(1.0, 0.01, 0.01), lambda: B.channel_sum_u([], []),
                lambda: B.one_way_mass_flux(-1.0, m, T, K_B), lambda: B.k_one_sided(0.7)):
        with pytest.raises(ValueError):
            bad()


def test_stored_numbers_consistent_with_derivations():
    doc = _stored()
    der = doc["derived"]
    k = der["k_one_sided"]["value"]
    assert der["absolute_thrust_gate"]["0.01"]["pass_min_12mN"]["value"] == pytest.approx(12.0 / (1 - k * 0.01), rel=1e-5)
    assert der["absolute_power_gate"]["0.01"]["pass_max_W"]["value"] == pytest.approx(1500.0 / (1 + k * 0.01), rel=1e-5)
    uT = doc["requirement_basis"]["lane25_by_n"]["4"]["u_T_max"]["value"]
    assert der["repeatability_absolute_by_n"]["4"]["sigma_T_at_12mN"]["value"] == pytest.approx(uT * 12e3, rel=1e-5)


def _copy_inputs(tmp_path: Path) -> Path:
    for rel in list(B.PINNED) + ["docs/experiments/instrumentation/pinned_inputs.json"]:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dst)
    return tmp_path


def test_missing_or_changed_input_raises(tmp_path):
    root = _copy_inputs(tmp_path)
    mod = _load(root)
    mod.verify_inputs()                                   # the copy verifies
    (root / B.L25).unlink()
    with pytest.raises(FileNotFoundError):
        mod.verify_inputs()
    root2 = _copy_inputs(tmp_path / "b")
    mod2 = _load(root2)
    with open(root2 / B.OD, "a", encoding="utf-8") as f:
        f.write(" ")
    with pytest.raises(mod2.InputChanged):
        mod2.verify_inputs()
    root3 = _copy_inputs(tmp_path / "c")
    (root3 / "docs/experiments/instrumentation/pinned_inputs.json").unlink()
    with pytest.raises(FileNotFoundError):
        _load(root3).verify_inputs()


# ----------------------------------------------------------------------------------------------------------------------
# control C5 (A2 addendum): AO/lifetime register v2 W4 provisions and MCQ-W4-* adopted (revision v1-r2)
# ----------------------------------------------------------------------------------------------------------------------
def test_c5_covers_every_w4_provision_of_register_and_mcq():
    doc = _stored()
    aol = json.loads((ROOT / B.AOL).read_text(encoding="utf-8"))
    mcq = json.loads((ROOT / B.MCQ).read_text(encoding="utf-8"))
    w4 = {r["requirement"] for r in aol["interface_table"]["rows"] if r["adopter"] == "W4"}
    assert len(w4) == 19
    mcqw4 = {r["id"] for r in mcq["requirements"] if r["id"].startswith("MCQ-W4-")}
    assert mcqw4 == {"MCQ-W4-01", "MCQ-W4-02", "MCQ-W4-03"}
    rows = {r["provision"]: r for r in doc["c5_adoption"]["rows"]}
    assert set(rows) == w4 | mcqw4 and len(rows) == len(doc["c5_adoption"]["rows"])
    ids = {i["id"] for i in doc["instruments"]} | {p["id"] for p in doc["procedures"]}
    for pid, r in rows.items():
        assert r["status"] in ("ADOPTED", "ADOPTED_PARTIAL", "NOT_ADOPTED")
        assert set(r["adopted_ids"]) <= ids
        derived = sorted([i["id"] for i in doc["instruments"] if pid in i["traces_to_provisions"]] +
                         [p["id"] for p in doc["procedures"] if pid in p["provisions"]])
        assert r["adopted_ids"] == derived, pid
        if r["status"] != "ADOPTED":
            assert r["needs"], pid
    counts = {k: v["value"] for k, v in doc["c5_adoption"]["counts"].items()}
    assert sum(counts.values()) == len(rows)


def test_c5_review_findings_closed():
    doc = _stored()
    ins = {i["id"]: i for i in doc["instruments"]}
    assert [i["id"] for i in doc["instruments"]] == [f"INS-{n:02d}" for n in range(1, 25)]
    assert "AOL-RC-02" in ins["INS-21"]["traces_to_provisions"]                    # anode resistance
    assert "AOL-CX-03" in ins["INS-22"]["traces_to_provisions"]                    # near-C-1 RGA sampling
    assert "AOL-CX-04" in ins["INS-23"]["traces_to_provisions"]                    # temperature near the cathode
    assert {"INS-19", "INS-20"} <= set(next(r for r in doc["c5_adoption"]["rows"]
                                            if r["provision"] == "AOL-WC-01")["adopted_ids"])   # witness metrology
    assert ins["INS-24"]["traces_to_provisions"] == ["MCQ-W4-01", "MCQ-W4-02", "MCQ-W4-03"]
    # every new requirement is TBD (no invented instrument accuracy)
    for n in range(19, 25):
        assert ins[f"INS-{n}"]["required_uncertainty"]["value"]["value"] == "TBD"
    # measured_hardware record fields come from the pinned schema
    schema = json.loads((ROOT / B.TL_SCHEMA).read_text(encoding="utf-8"))
    assert doc["c5_adoption"]["measured_hardware_fields"] == B._find_key(schema, "measured_hardware")[
        "evidence_record_fields"]
    # versioning: stays v1 with a change log, the original base commit is kept
    assert doc["version"] == "v1" and doc["revision"] == "v1-r2"
    assert doc["base_commit"] == "510e464fb8e128e4cf3325572a4d36ad33a4899d"
    assert [c["revision"] for c in doc["change_log"]] == ["v1-r1", "v1-r2", "v1-r2", "v1-r2", "v1-r2"]
    assert [c["entry"] for c in doc["change_log"]] == ["v1-r1", "v1-r2/C5", "v1-r2/A3", "v1-r2/A3-repair",
                                                       "v1-r2/A3-repair-2"]
    assert doc["change_log"][-1]["amendment"] == "A3"


def test_c5_validation_rejects_inconsistencies():
    doc = _stored()
    bad = json.loads(json.dumps(doc))
    bad["c5_adoption"]["rows"][0]["status"] = "NOT_ADOPTED"
    with pytest.raises(ValueError):
        B.validate(bad)
    bad = json.loads(json.dumps(doc))
    r = next(r for r in bad["c5_adoption"]["rows"] if r["status"] == "ADOPTED_PARTIAL")
    r["needs"] = None
    with pytest.raises(ValueError):
        B.validate(bad)
    bad = json.loads(json.dumps(doc))
    bad["derived"]["life_h"] = {"value": 15000.0, "unit": "h", "evidence_class": "model-derived", "source": "x"}
    with pytest.raises(ValueError):
        B.validate(bad)
    bad = json.loads(json.dumps(doc))
    bad["instruments"][20]["traces_to_provisions"] = ["AOL-XX-99"]
    with pytest.raises(ValueError):
        B.validate(bad)


def test_c5_missing_disposition_raises(monkeypatch):
    disp = dict(B.C5_DISPOSITION)
    disp.pop("AOL-CX-03")
    monkeypatch.setattr(B, "C5_DISPOSITION", disp)
    with pytest.raises(ValueError):
        B.build()


# ----------------------------------------------------------------------------------------------------------------------
# owner addendum A3 (instrument semantics; stays v1-r2)
# ----------------------------------------------------------------------------------------------------------------------
def test_a3_adopted_without_changing_ids_and_pins_hw_c1_09():
    doc = _stored()
    a3 = json.loads((ROOT / B.A3).read_text(encoding="utf-8"))
    rows = {r["decision"]: r for r in doc["a3_adoption"]["rows"]}
    assert set(rows) == set(a3["decisions"])
    for k, r in rows.items():
        assert r["owner_text"] == a3["decisions"][k]
    assert B.A3 in {p["path"] for p in doc["inputs"]}
    hw = json.loads((ROOT / B.HWR).read_text(encoding="utf-8"))
    assert "HW-C1-09" in B._walk_ids(hw, set())
    assert "HW-C1-09" in doc["c5_adoption"]["w3_ids_cited"]
    assert doc["revision"] == "v1-r2" and doc["version"] == "v1"


def test_a3_instrument_semantics():
    doc = _stored()
    ins = {i["id"]: i for i in doc["instruments"]}
    i23 = ins["INS-23"]
    assert "MANDATORY" in i23["principle"] and "HW-C1-09" in i23["principle"]
    assert any("never as emitter temperature" in n and "'unmeasured'" in n for n in i23["notes"])
    assert any("unmeasured" in n and "cathode-tube" in n for n in ins["INS-18"]["notes"])
    i22 = ins["INS-22"]
    assert any("QUALITATIVE" in n and "S1a" in n and "never supports an exposure-dose or lifetime claim" in n
               for n in i22["notes"])
    assert any("quantitative for the AO/lifetime programme" in c for c in i22["calibration"])
    p12 = next(p for p in doc["procedures"] if p["id"] == "INS-P-12")
    assert "k = 2" in p12["statement"] and "effective degrees of freedom" in p12["statement"]
    assert any("ISO/IEC 17025" in c for c in ins["INS-19"]["calibration"])
    assert any("ISO/IEC 17025" in c for c in ins["INS-20"]["calibration"])


def test_a3_validation_rejects_missing_semantics():
    doc = _stored()
    bad = json.loads(json.dumps(doc))
    i23 = next(i for i in bad["instruments"] if i["id"] == "INS-23")
    i23["notes"] = [n for n in i23["notes"] if "never as emitter temperature" not in n]
    with pytest.raises(ValueError):
        B.validate(bad)
    bad = json.loads(json.dumps(doc))
    i22 = next(i for i in bad["instruments"] if i["id"] == "INS-22")
    i22["notes"] = [n for n in i22["notes"] if "QUALITATIVE" not in n]
    with pytest.raises(ValueError):
        B.validate(bad)
    bad = json.loads(json.dumps(doc))
    next(p for p in bad["procedures"] if p["id"] == "INS-P-12")["statement"] = "k: owner"
    with pytest.raises(ValueError):
        B.validate(bad)


# ----------------------------------------------------------------------------------------------------------------------
# A3 review repair: W3 pinned as an immutable snapshot (no pin cycle), downstream re-pins declared, unique entries
# ----------------------------------------------------------------------------------------------------------------------
def test_w3_pinned_as_immutable_snapshot_not_live_file():
    doc = _stored()
    paths = {p["path"] for p in doc["inputs"]}
    assert B.HWR_LIVE not in paths and B.HWR in paths
    assert B.HWR.startswith("docs/experiments/instrumentation/snapshots/")
    sn = doc["downstream_repin_required"]["w3_snapshot"]
    assert sn["source_path"] == B.HWR_LIVE and sn["source_commit"] in sn["reproduce"]
    bad = json.loads(json.dumps(doc))
    bad["inputs"].append({"path": B.HWR_LIVE, "lane": "W3", "sha256": "0" * 64})
    with pytest.raises(ValueError):
        B.validate(bad)


def test_w3_snapshot_matches_git_commit_when_available():
    sn = B.HWR_SNAPSHOT
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "show", f"{sn['source_commit']}:{sn['source_path']}"],
                             capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git history with the W3 source commit is not available")
    assert out == (ROOT / B.HWR).read_bytes()


def test_downstream_repin_declared():
    doc = _stored()
    dr = doc["downstream_repin_required"]
    files = {c["file"] for c in dr["consumers"]}
    assert {"docs/experiments/lifetime_ao/ao_lifetime_register_v3.json",
            "docs/experiments/hardware/hardware_requirements_v1.json",
            "docs/experiments/s1_readiness/s1_readiness_status_current.json"} <= files
    assert "9a33979" in dr["merge_order"] and "removed from this branch" in dr["merge_order"]
    md = (DIR / "INSTRUMENTATION_DEFINITION.md").read_text(encoding="utf-8")
    assert "Downstream re-pin required" in md and "Pin cycle resolved" in md
    assert "7d373374dc" in md.split("\n")[2]


def test_change_log_entries_unique():
    doc = _stored()
    bad = json.loads(json.dumps(doc))
    bad["change_log"][-1]["entry"] = bad["change_log"][-2]["entry"]
    with pytest.raises(ValueError):
        B.validate(bad)


def test_ins13_cex_wording():
    ins13 = next(i for i in _stored()["instruments"] if i["id"] == "INS-13")
    t = json.dumps(ins13["required_uncertainty"])
    assert "ion-gauge uncertainty is typically 10-20 %" in t and "not the correction's" in t
