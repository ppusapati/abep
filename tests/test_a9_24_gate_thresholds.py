"""A9.24 item 5 (owner decision 2026-10-04, docs/decisions/OD_2026_10_04_A9_24_*): HC-05..HC-12 dispositions.

The thresholds live in the assessment-layer artefact config/assessment/gate_thresholds_v1.json (status / provenance per
gate), read by abep_sim.configuration.load_gate_thresholds for abep_sim/assessment/design_gates.py; the design module
abep_sim/design/engineering_constraints.py holds none of them (HC-09 stays its design-generation filter, read from the
engineering constraints). HC-12 has no threshold (TBD_PENDING_MEASURED_H1) and evaluates NOT_EVALUATED.
"""
from __future__ import annotations

import ast
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from abep_sim import configuration as cfg
from abep_sim.assessment import design_gates as dg
from abep_sim.design import architecture_optimizer as ao
from abep_sim.design import engineering_constraints as ec

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"


def _remanifest(root: Path):
    man = json.loads((root / cfg.MANIFEST_REL).read_text(encoding="utf-8"))
    for rel in man["files"]:
        b = (root / rel).read_bytes()
        man["files"][rel] = {"sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
    (root / cfg.MANIFEST_REL).write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")


@pytest.fixture()
def cfg_copy(tmp_path):
    dst = tmp_path / "config"
    shutil.copytree(CONFIG, dst)
    return dst


def test_dispositions_recorded_per_gate():
    g = cfg.load_gate_thresholds()["gates"]
    assert tuple(g) == cfg.GATE_IDS
    layers = {k: v["layer"] for k, v in g.items()}
    assert layers["HC-06"] == "ASSESSMENT_PROTECTION_POLICY"
    assert layers["HC-09"] == "DESIGN_GENERATION_FILTER_ALSO_REPORTED_IN_ASSESSMENT"
    assert all(layers[k] == "ASSESSMENT_ONLY" for k in ("HC-05", "HC-07", "HC-08", "HC-10", "HC-11", "HC-12"))
    assert (g["HC-05"]["comparator"], g["HC-05"]["value"], g["HC-05"]["units"]) == (">", 0.0, "-")
    assert "I_e,cap / I_d,max,H1 - 1" in g["HC-05"]["criterion"]
    assert g["HC-05"]["evaluation_without_lower_bound"] == "NOT_EVALUATED"
    assert (g["HC-06"]["value"], g["HC-06"]["units"]) == (50.0, "K") and "never inside thermal" in g["HC-06"]["criterion"]
    assert g["HC-07"]["kind"] == "CONSTRAINT_REFERENCE" and g["HC-07"]["constraint_ref"] == "firing_life_h"
    assert g["HC-09"]["kind"] == "CONSTRAINT_REFERENCE" and g["HC-09"]["constraint_ref"] == "intake_drag_generation_limit_mN"
    assert (g["HC-08"]["value"], g["HC-11"]["value"], g["HC-10"]["value"]) == (0.0, 0.0, 1.0)
    assert g["HC-12"]["value"] is None and g["HC-12"]["status"] == "TBD_PENDING_MEASURED_H1"
    assert g["HC-12"]["evaluation_until_frozen"] == "NOT_EVALUATED"
    for k, v in g.items():
        assert v["provenance"] and any("A9.24 item 5" in p for p in v["provenance"]), k


def test_limits_identical_and_resolved_from_single_sources():
    lim = cfg.load_gate_thresholds()["limits"]
    ecv = cfg.load_engineering_constraints()
    assert lim["HC-07"] == ecv["ignition_hours"] == 15000.0
    assert lim["HC-09"] == ec.INTAKE_DRAG_GENERATION_LIMIT_N == 0.025
    assert {k: dg.HARD_CONSTRAINT_LIMITS[k] for k in cfg.GATE_IDS} == lim
    assert [c["limit"] for c in dg.HARD_CONSTRAINTS] == [dg.HARD_CONSTRAINT_LIMITS[c["id"]] for c in dg.HARD_CONSTRAINTS]


def test_hc12_not_evaluated_without_a_measured_basis():
    hc12 = [c for c in dg.evaluate_constraints({}) if c["id"] == "HC-12"][0]
    assert hc12["status"] == ao.C_NOT_EVALUATED


def test_hc05_uses_the_lower_bound_of_the_ratio_margin_only():
    """Owner correction 2026-10-04: HC-05 compares M_n,LB (M_n = I_e,cap / I_d,max,H1 - 1) with 0; a point difference
    record, or an M_n record without an uncertainty basis, is NOT_EVALUATED."""
    def hc05(vals):
        return [c for c in dg.evaluate_constraints(vals) if c["id"] == "HC-05"][0]
    point = {"status": ao.EVALUATED, "value": 1.0, "units": "A"}
    assert hc05({"I_e_cap_minus_I_d_max_A": point})["status"] == ao.C_NOT_EVALUATED
    assert hc05({"M_n_LB": {"status": ao.EVALUATED, "value": 0.2}})["status"] == ao.C_NOT_EVALUATED
    assert hc05({})["status"] == ao.C_NOT_EVALUATED
    ok = {"status": ao.EVALUATED, "value": 0.2, "uncertainty_basis": "one-sided lower bound (test)"}
    assert hc05({"M_n_LB": ok})["status"] == ao.C_MET
    assert hc05({"M_n_LB": {**ok, "value": -0.01}})["status"] == ao.C_VIOLATED
    assert hc05({"M_n_LB": {**ok, "value": 0.0}})["status"] == ao.C_VIOLATED       # strict: M_n,LB > 0


def test_design_module_holds_no_hc05_hc12_literal():
    """No numeric HC-05..HC-12 threshold assignment in the design seam (A9.24 item 5)."""
    tree = ast.parse((ROOT / "abep_sim/design/engineering_constraints.py").read_text(encoding="utf-8"))
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, (int, float)):
            raise AssertionError(f"numeric literal assigned in the design seam: {ast.unparse(n)}")
    src = (ROOT / "abep_sim/design/engineering_constraints.py").read_text(encoding="utf-8")
    for gid in ("HC-05", "HC-06", "HC-07", "HC-08", "HC-10", "HC-11", "HC-12"):
        assert f'"{gid}"' not in src, gid


def test_threshold_change_moves_assessment_limit_only(cfg_copy):
    p = cfg_copy / cfg.GATE_THRESHOLDS_REL
    d = json.loads(p.read_text(encoding="utf-8"))
    d["gates"]["HC-06"]["value"] = 60.0
    p.write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8")
    _remanifest(cfg_copy)
    assert cfg.load_gate_thresholds(cfg_copy)["limits"]["HC-06"] == 60.0
    assert cfg.load_operating_inputs(cfg_copy) == cfg.load_operating_inputs()
    assert cfg.load_engineering_constraints(cfg_copy) == cfg.load_engineering_constraints()


def test_tbd_threshold_cannot_carry_a_default(cfg_copy):
    p = cfg_copy / cfg.GATE_THRESHOLDS_REL
    d = json.loads(p.read_text(encoding="utf-8"))
    d["gates"]["HC-12"]["value"] = 0.05
    p.write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8")
    _remanifest(cfg_copy)
    with pytest.raises(cfg.ConfigurationError, match="no default"):
        cfg.load_gate_thresholds(cfg_copy)
