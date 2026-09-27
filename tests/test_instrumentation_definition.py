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
            assert row[key]["value"] == pytest.approx(plan[key]["value"], rel=1e-5)
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
