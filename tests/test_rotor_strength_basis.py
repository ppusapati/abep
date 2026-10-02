"""A9.9 S2.3 + S2.5 MCC-03: rotor structural acceptance requires a registered rotor-strength basis.

The numeric basis built in these tests is a SYNTHETIC TEST FIXTURE (round numbers chosen only to exercise the
logic). It is not material data and is never registered outside the test that creates it."""
import math

import pytest

from abep_sim import rotor_strength as RS
from abep_sim.compressor import DragCompressor
from abep_sim.materials import DB

MD = {"O": 0.45e-6, "N2": 0.50e-6, "O2": 0.05e-6}


def _fixture(**kw):
    base = dict(basis_id="TEST-SYNTHETIC", materials_db_key="Ti6Al4V", material_spec="SYNTHETIC-SPEC",
                product_form="synthetic bar", condition="synthetic", section_thickness_range_m=(0.01, 0.10),
                design_temperature_K=400.0, allowable_basis="A-basis", allowable_source="SYNTHETIC TEST FIXTURE",
                allowables=(RS.AllowablePoint(300.0, 800e6, 900e6), RS.AllowablePoint(500.0, 600e6, 700e6)),
                density_kg_m3=4000.0, density_source="SYNTHETIC TEST FIXTURE", factor_yield=1.25,
                factor_ultimate=1.5, factors_source="SYNTHETIC TEST FIXTURE", max_design_speed_rpm=90000.0,
                proof_spin_basis="SYNTHETIC", registration="TEST")
    base.update(kw)
    return RS.RotorStrengthBasis(**base)


@pytest.fixture
def registered():
    b = RS.register_basis(_fixture())
    yield b
    RS.unregister_basis(b.basis_id)


def test_registry_is_empty_and_reference_record_is_not_registered():
    assert RS.REGISTRY == {}
    ref = RS.REFERENCE_RECORDS["REF-TI64-ANNEALED-PLATE-RT-ABASIS-MMPDS06"]
    assert ref["status"] == "INCOMPLETE_REFERENCE_NOT_REGISTERED"
    assert ref["Fty_Pa"] == 827e6 and ref["Ftu_Pa"] == 896e6 and ref["product_form"] == "annealed plate"


def test_no_basis_is_not_evaluated_and_never_rotor_ok():
    for mat in ("Ti6Al4V", "Al6061", "CFRP"):
        r = DragCompressor(rotor_material=mat, rpm=1000.0).run(0.005, MD)     # far inside any cap
        assert r["rotor_ok"] is False
        assert r["rotor_qualification"] == RS.Q_NOT_EVALUATED_MATERIAL_BASIS
        assert r["sizing_mode"] == RS.SIZING_PARAMETRIC_SENSITIVITY
        assert r["u_max_basis"] == RS.LEGACY_SENSITIVITY_LABEL
        assert r["rotor_within_legacy_sensitivity_cap"] is True


def test_legacy_cap_numerics_unchanged_without_basis():
    c = DragCompressor(rotor_material="Ti6Al4V")
    m = DB["Ti6Al4V"]
    legacy = math.sqrt(m.yield_MPa * 1e6 / (2.0 * m.density))
    assert c.u_max() == c.u_max_legacy_sensitivity() == legacy


def test_basis_inputs_are_not_dataclass_fields():
    import dataclasses
    names = {f.name for f in dataclasses.fields(DragCompressor)}
    assert "rotor_strength_basis_id" not in names and "rotor_stock_thickness_m" not in names
    a, b = DragCompressor(), DragCompressor().set_rotor_strength_basis("X", 0.05)
    assert a.rotor_strength_basis_id is None and b.rotor_strength_basis_id == "X"


def test_size_for_without_basis_is_parametric_sensitivity():
    s = DragCompressor(turbo_area_m2=0.45, turbo_radius_m=0.40, rotor_material="CFRP").size_for(0.005, MD, 5)
    assert s["sized"] and s["rotor_ok"] is False and s["sizing_mode"] == RS.SIZING_PARAMETRIC_SENSITIVITY


def test_unregistered_or_incomplete_basis_refused():
    for bad in (dict(proof_spin_basis=None), dict(factor_yield=0.9),
                dict(allowables=(RS.AllowablePoint(300.0, 950e6, 900e6),)),
                dict(design_temperature_K=600.0),                       # outside the table: no extrapolation
                dict(density_kg_m3=float("nan")), dict(product_form=""), dict(allowable_source="")):
        with pytest.raises(ValueError):
            RS.register_basis(_fixture(**bad))
    assert RS.REGISTRY == {}
    r = DragCompressor(rpm=1000.0).set_rotor_strength_basis("NOT-REGISTERED", 0.05).run(0.005, MD)
    assert r["rotor_qualification"] == RS.Q_NOT_EVALUATED_MATERIAL_BASIS and r["rotor_ok"] is False


def test_duplicate_registration_refused(registered):
    with pytest.raises(ValueError):
        RS.register_basis(_fixture())


def test_registered_basis_margins_on_yield_and_ultimate(registered):
    c = DragCompressor(rpm=10000.0).set_rotor_strength_basis(registered.basis_id, 0.05)
    r = c.run(0.005, MD)
    assert r["sizing_mode"] == RS.SIZING_REGISTERED_BASIS
    u = max(r["u_mps"], r["u_turbo_mps"])
    sigma = 4000.0 * u ** 2
    Fty, Ftu = 700e6, 800e6                            # linear at 400 K between the fixture points
    assert r["margin_yield"] == pytest.approx(Fty / (1.25 * sigma) - 1)
    assert r["margin_ultimate"] == pytest.approx(Ftu / (1.5 * sigma) - 1)
    assert r["rotor_qualification"] == RS.Q_PASS and r["rotor_ok"] is True
    # the cap is the more restrictive of yield and ultimate (here ultimate: 800/1.5 < 700/1.25)
    assert c.u_max() == pytest.approx(math.sqrt(min(Fty / 1.25, Ftu / 1.5) / 4000.0))


def test_registered_basis_failures_and_domain(registered):
    over = DragCompressor(rpm=60000.0).set_rotor_strength_basis(registered.basis_id, 0.05).run(0.005, MD)      # turbo tip ~1885 m/s, far above the cap
    assert over["rotor_qualification"] == RS.Q_FAIL and over["rotor_ok"] is False
    assert over["margin_ultimate"] < 0 and over["margin_yield"] < 0
    r = DragCompressor(rpm=1000.0, rotor_material="Al6061").set_rotor_strength_basis(registered.basis_id, 0.05).run(0.005, MD)     # no material transfer
    assert r["rotor_qualification"] == RS.Q_NOT_EVALUATED_MATERIAL_BASIS
    assert r["sizing_mode"] == RS.SIZING_PARAMETRIC_SENSITIVITY
    for t in (None, 0.5):                                         # stock section missing / outside the basis
        r = DragCompressor(rpm=1000.0).set_rotor_strength_basis(registered.basis_id, t).run(0.005, MD)
        assert r["rotor_qualification"] == RS.Q_NOT_EVALUATED_MATERIAL_BASIS and not r["rotor_ok"]
    q = RS.qualify_rotor(registered.basis_id, "Ti6Al4V", 100.0, 1000.0, 450.0, 0.05)   # above design temperature
    assert q["rotor_qualification"] == RS.Q_NOT_EVALUATED_OUT_OF_DOMAIN and not q["rotor_ok"]
    q = RS.qualify_rotor(registered.basis_id, "Ti6Al4V", 100.0, 95000.0, 350.0, 0.05)  # above max design speed
    assert q["rotor_qualification"] == RS.Q_FAIL and not q["rotor_ok"]


def test_registered_basis_caps_size_for(registered):
    c = DragCompressor(turbo_area_m2=0.45, turbo_radius_m=0.40).set_rotor_strength_basis(registered.basis_id, 0.05)
    s = c.size_for(0.005, MD, 5)
    assert max(s["u_mps"], s["u_turbo_mps"]) <= c.u_max() * (1 + 1e-9)


def test_system_gaspath_fails_closed_without_basis():
    from abep_sim.system import Config, evaluate
    from abep_sim.intake import IntakeParams, CompressorParams
    r = evaluate(Config("hall_1stage", 200, "mean", IntakeParams(area_m2=0.7, accommodation=0.8, use_tpmc=True, L_over_d=5),
                        CompressorParams(ratio=2000), vd_V=275, gaspath_physics=True))
    assert r["comp_rotor_qualification"] == RS.Q_NOT_EVALUATED_MATERIAL_BASIS
    assert r["comp_rotor_ok"] is False and r["comp_sizing_mode"] == RS.SIZING_PARAMETRIC_SENSITIVITY
    assert r["chk_compressor_feasible"] is False and r["rfp_compliant"] is False
