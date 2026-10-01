"""Reference spacecraft drag basis (A9.13 S6.18): REFERENCE/PARAMETRIC evaluator, register and builder."""
import ast
import importlib.util
import math
from pathlib import Path

import pytest

from abep_sim import spacecraft_reference_drag as SRD

REPO = Path(__file__).resolve().parents[1]
BUILDER = REPO / "docs/design_synthesis/spacecraft_reference_drag/build_spacecraft_reference_drag.py"
STATE = {"source": "test-orbit-resolved-stub", "state_id": "s0"}


def _call(case_id="RC-DIAMANT", **kw):
    args = dict(rho_kg_m3=2.5e-10, v_rel_m_s=7800.0, intake_projected_area_m2=0.1, intake_cd=2.0,
                intake_source="F1 test stub", atmosphere_state=STATE, intake_accounting="separate_term")
    args.update(kw)
    return SRD.reference_drag(case_id, **args)


def test_drag_equation_and_status():
    r = _call()
    q = 0.5 * 2.5e-10 * 7800.0 ** 2
    assert math.isclose(r["q_Pa"], q)
    assert math.isclose(r["reference_term"]["D_N"], q * 2.2 * 0.5)
    assert math.isclose(r["intake_term"]["D_N"], q * 2.0 * 0.1)
    assert math.isclose(r["D_total_N"], q * (2.2 * 0.5 + 2.0 * 0.1))
    assert r["status"] == "REFERENCE_PARAMETRIC_NOT_FLIGHT"
    assert r["freeze_status"] == "NOT_EVALUATED"
    assert r["label"] == "REFERENCE/PARAMETRIC"
    assert "INTAKE_OVERLAP_UNRESOLVED" in r["flags"]
    assert r["rfp_thrust_band_mN"]["requirement_status"] == "OWNER_STATED_RFP_NOT_REGISTERED"


def test_intake_accounting_guards_double_counting():
    with pytest.raises(ValueError, match="double-counts"):
        _call("RC-ROMANO2018", intake_accounting="separate_term")
    r = _call("RC-ROMANO2018", intake_accounting="contained_in_reference")
    assert r["intake_term"]["added_to_total"] is False
    assert math.isclose(r["D_total_N"], r["reference_term"]["D_N"])
    with pytest.raises(ValueError):
        _call(intake_accounting="maybe")


@pytest.mark.parametrize("bad", [
    dict(rho_kg_m3=None), dict(rho_kg_m3=0.0), dict(rho_kg_m3=-1.0), dict(rho_kg_m3=float("nan")),
    dict(v_rel_m_s=None), dict(intake_projected_area_m2=None), dict(intake_cd=None), dict(intake_cd=True),
    dict(intake_source=""), dict(atmosphere_state={}), dict(atmosphere_state={"source": "x"}),
    dict(intake_accounting=None),
])
def test_missing_or_bad_inputs_raise(bad):
    with pytest.raises((ValueError, TypeError)):
        _call(**bad)


def test_unknown_case_raises():
    with pytest.raises(KeyError):
        _call("RC-FLIGHT")


def test_statewise_margin_same_state_only():
    r = _call()
    m = SRD.statewise_margin(0.012, r, thrust_state=dict(STATE), thrust_source="test")
    assert math.isclose(m["margin_N"], 0.012 - r["D_total_N"])
    assert m["freeze_status"] == "NOT_EVALUATED"
    with pytest.raises(ValueError, match="same atmospheric"):
        SRD.statewise_margin(0.012, r, thrust_state={"source": "x", "state_id": "s1"}, thrust_source="test")
    with pytest.raises(ValueError):
        SRD.statewise_margin(0.012, {"status": "FLIGHT"}, thrust_state=STATE, thrust_source="test")


def test_cases_are_same_source_pairs_and_sourced():
    recs = {r["id"]: r for r in SRD.RECORDS}
    for c in SRD.CASES:
        r = recs[c.record_id]
        assert r["label"] == "REFERENCE/PARAMETRIC"
        assert r["frontal_area_m2"]["value"] == c.a_ref_m2
        cd = r["cd"]["value"]
        assert c.cd in (cd if isinstance(cd, list) else [cd])
        assert c.source.startswith("SRC-") and c.source.split()[0] in SRD.SOURCES


def test_every_record_value_is_sourced_or_tbd():
    fields = ("altitude_km", "mass_kg", "frontal_area_m2", "cd", "cd_model_basis", "attitude_assumption",
              "body_array_configuration")
    for r in SRD.RECORDS:
        for f in fields:
            v = r[f]
            assert v["source"]
            assert 1 <= v["evidence_level"] <= 7
            if v["value"] is None:
                assert v["quantity_type"] == "TBD"
            else:
                assert v["quantity_type"] != "TBD"


def test_band_is_owner_stated():
    assert SRD.RFP_THRUST_BAND["min_mN"] == 12.0 and SRD.RFP_THRUST_BAND["max_mN"] == 25.0
    assert "RFP(1)" in SRD.RFP_THRUST_BAND["source"]


def test_density_free_table():
    for row in SRD.density_free_table():
        assert math.isclose(row["q_at_12mN_Pa"] * row["cd_a_m2"], 0.012, rel_tol=1e-6)
        assert math.isclose(row["q_at_25mN_Pa"] * row["cd_a_m2"], 0.025, rel_tol=1e-6)


def test_module_imports_no_atmosphere():
    tree = ast.parse((REPO / "abep_sim/spacecraft_reference_drag.py").read_text())
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            names |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            names.add(n.module or "")
    assert names <= {"__future__", "math", "dataclasses", "typing"}


def test_builder_check_reproduces():
    spec = importlib.util.spec_from_file_location("build_srd", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main(["--check"]) == 0
