"""Review fixes on the A9.9 production-model range (2026-10-01): one focused regression test per fix.

D-02/N2  archengine: a non-admissible gas state never displaces an admissible one and never returns status 'OK'.
D-03/N4  archengine: the S2.3/MCC-03 rotor qualification travels with gas states and architecture results.
D-04/N3  system: the collected composition comes from the species-resolved collection (S2.1).
D-06/N5  rotor_strength.qualify_rotor fails closed on non-finite / negative tip speed or rpm.
D-07/N6  IntakeSurface refuses missing, non-finite, negative or all-zero fractions (no default composition).
D-08     mission5 passes the AO-aged accommodation unclipped.

The rotor-strength basis used below is the SYNTHETIC TEST FIXTURE of tests/test_rotor_strength_basis.py (round numbers
exercising the logic only; never material data, unregistered after each test)."""
import inspect
import math

import pandas as pd
import pytest

from abep_sim import archengine as AE
from abep_sim import rotor_strength as RS
from abep_sim.atmosphere import atmosphere
from abep_sim.intake import IntakeParams, CompressorParams, collection
from abep_sim.intake_tpmc import IntakeSurface, frozen_surface_build_atmosphere, frozen_surface_path
from abep_sim.mission_env import Spacecraft


# ------------------------------------------------------------------------------------------------ D-06 / N5
def _fixture():
    return RS.RotorStrengthBasis(
        basis_id="TEST-SYNTHETIC-REVIEW", materials_db_key="Ti6Al4V", material_spec="SYNTHETIC-SPEC",
        product_form="synthetic bar", condition="synthetic", section_thickness_range_m=(0.01, 0.10),
        design_temperature_K=400.0, allowable_basis="A-basis", allowable_source="SYNTHETIC TEST FIXTURE",
        allowables=(RS.AllowablePoint(300.0, 800e6, 900e6), RS.AllowablePoint(500.0, 600e6, 700e6)),
        density_kg_m3=4000.0, density_source="SYNTHETIC TEST FIXTURE", factor_yield=1.25, factor_ultimate=1.5,
        factors_source="SYNTHETIC TEST FIXTURE", max_design_speed_rpm=90000.0, proof_spin_basis="SYNTHETIC",
        registration="TEST")


@pytest.fixture
def registered():
    b = RS.register_basis(_fixture())
    yield b
    RS.unregister_basis(b.basis_id)


@pytest.mark.parametrize("tip,rpm", [(math.nan, 50000.0), (300.0, math.nan), (math.inf, 50000.0), (300.0, math.inf),
                                     (-1.0, 50000.0), (300.0, -1.0), (None, 50000.0), (True, 50000.0)])
def test_qualify_rotor_non_finite_speed_fails_closed(registered, tip, rpm):
    q = RS.qualify_rotor(registered.basis_id, "Ti6Al4V", tip, rpm, 300.0, 0.02)
    assert q["rotor_qualification"] == RS.Q_NOT_EVALUATED_OUT_OF_DOMAIN and q["rotor_ok"] is False
    assert any("finite" in r for r in q["rotor_qualification_reasons"])


def test_qualify_rotor_valid_speed_still_passes(registered):
    q = RS.qualify_rotor(registered.basis_id, "Ti6Al4V", 300.0, 50000.0, 300.0, 0.02)
    assert q["rotor_qualification"] == RS.Q_PASS and q["rotor_ok"] is True
    q0 = RS.qualify_rotor(registered.basis_id, "Ti6Al4V", 0.0, 0.0, 300.0, 0.02)       # at rest: infinite margins
    assert q0["rotor_qualification"] == RS.Q_PASS and q0["margin_yield"] == math.inf


# ------------------------------------------------------------------------------------------------ D-07 / N6
@pytest.fixture(scope="module")
def surf():
    df = pd.read_csv(frozen_surface_path())
    return IntakeSurface(df[df.scattering == "maxwell"].reset_index(drop=True),
                         m_mean_build_kg=frozen_surface_build_atmosphere()["m_mean"])


@pytest.mark.parametrize("fr", [None, {}, {"O": 0.0, "N2": 0.0, "O2": 0.0}, {"O": 0.5, "N2": -0.2, "O2": 0.0},
                                {"O": math.nan, "N2": 0.5, "O2": 0.0}, {"O": math.inf, "N2": 0.5, "O2": 0.0},
                                {"O": 0.5, "N2": 0.5, "He": -0.1}, {"O": "0.5", "N2": 0.5}])
def test_intake_surface_refuses_bad_fractions(surf, fr):
    with pytest.raises(ValueError):
        surf(5.0, 0.8, 0.8, 0.0, fractions=fr)


def test_intake_surface_valid_fractions_unchanged(surf):
    r = surf(5.0, 0.8, 0.8, 0.0, fractions={"O": 0.3, "N2": 0.6, "O2": 0.1})
    # independent hand recombination recorded by the review (finding N6)
    assert r["C_D"] == pytest.approx(2.054149416, rel=1e-8)
    assert r["CR_passive"] == pytest.approx(169.278379, rel=1e-8)
    assert r["eta_c"] == pytest.approx(0.615007, rel=1e-6)
    r2 = surf(5.0, 0.8, 0.8, 0.0, fractions={"O": 0.3, "N2": 0.6, "O2": 0.1, "He": 0.0})
    assert r2["C_D"] == r["C_D"]


# ------------------------------------------------------------------------------------------------ D-08
def test_mission_passes_aged_accommodation_unclipped(monkeypatch):
    import abep_sim.mission5 as M5
    assert "min(alpha, 1.0)" not in inspect.getsource(M5.run_mission_generic)
    assert "min(alpha, 1.0)" not in inspect.getsource(M5.run_phase5)
    monkeypatch.setattr(M5, "surface_ageing_alpha", lambda *a, **k: 1.05)       # out of the frozen alpha domain
    arch = {"T_mN": 20.0, "P_bus_W": 1000.0, "mdot_air_mgps": 1.0, "x_area": 0.7, "architecture": "self+resistojet"}
    with pytest.raises(ValueError, match="extrapolation"):
        M5.run_mission_generic(arch, Spacecraft(bus_frontal_m2=0.10, pointing_sigma_deg=0.5), {}, hours=12.0, dt_h=6.0)


# ------------------------------------------------------------------------------------------------ D-04 / N3
def test_gas_path_uses_species_resolved_collected_composition():
    from abep_sim.system import Config, evaluate
    ip = IntakeParams(area_m2=0.7, accommodation=0.8, use_tpmc=True, L_over_d=5)
    r = evaluate(Config("hall_1stage", 200, "mean", ip, CompressorParams(ratio=2000), vd_V=275, gaspath_physics=True))
    atm = atmosphere(200.0, "mean")
    col = collection(IntakeParams(area_m2=0.7, accommodation=0.8, use_tpmc=True, L_over_d=5), atm)
    sp = col["mdot_collected_species"]; tot = sum(sp.values())
    assert tot == pytest.approx(col["mdot_collected"], rel=1e-12)
    assert r["collected_composition_basis"] == "species_resolved_collection_A9.9_S2.1"
    for s, k in (("O", "fO_collected"), ("N2", "fN2_collected"), ("O2", "fO2_collected")):
        assert r[k] == pytest.approx(sp[s] / tot, rel=1e-12)
    # the species-resolved composition differs materially from the free-stream split it replaces (review: ~-4.5 % on O)
    assert r["fO_collected"] / atm["fO"] - 1.0 < -0.02 and r["fN2_collected"] > atm["fN2"]
    # the parametric intake keeps the free-stream split, explicitly labelled
    rp = evaluate(Config("hall_1stage", 200, "mean", IntakeParams(area_m2=0.7, accommodation=0.8), CompressorParams(ratio=2000), vd_V=275))
    assert rp["collected_composition_basis"] == "free_stream_mass_fractions_parametric_intake"
    assert rp["fO_collected"] == atm["fO"]


# ------------------------------------------------------------------------------------------------ D-03 / N4
@pytest.fixture(scope="module")
def real_gas():
    return AE.make_gas_fn()(0.7, 0.05)


def test_gas_path_state_carries_rotor_qualification(real_gas):
    g = real_gas
    assert g["comp_sizing_mode"] == RS.SIZING_PARAMETRIC_SENSITIVITY
    assert g["comp_rotor_qualification"] == RS.Q_NOT_EVALUATED_MATERIAL_BASIS
    assert g["comp_u_max_basis"] == RS.LEGACY_SENSITIVITY_LABEL
    assert AE.gas_evidence_class(g)[0] == "PARAMETRIC_SENSITIVITY"
    from abep_sim import arch_compare as ac
    u = ac.UpstreamState.from_gas_path(g, "TEST")                      # labelled, not dropped
    assert u.labels["comp_rotor_qualification"] == RS.Q_NOT_EVALUATED_MATERIAL_BASIS


# ------------------------------------------------------------------------------------------------ D-02 / N2
def _states(real_gas):
    ok = dict(real_gas, comp_rotor_qualification="PASS")              # TEST-ONLY label: as if a basis qualified it
    better_J = {"mdot_air": real_gas["mdot_air"] * 1.3, "p_in": real_gas["p_in"] * 1.3}
    nc = dict(real_gas, **better_J, gaspath_status="MODEL_NOT_CONVERGED", gaspath_not_converged="orifice_sizing")
    ood = dict(real_gas, **better_J, gaspath_domain_status="OUT_OF_MODEL_DOMAIN",
               gaspath_out_of_domain="compressor_gaede_stage_capacity")
    par = dict(real_gas, **better_J)                                   # PARAMETRIC_SENSITIVITY (no registered basis)
    return {"ok": ok, "nc": nc, "ood": ood, "par": par}


def _close(states, levels):
    A = {AE.arch_name(x): x for x in AE.enumerate_architectures()}
    return AE.close_architecture(A["self+resistojet"], lambda area, p: states[p], Spacecraft(bus_frontal_m2=0.10,
                                 array_area_m2=5.0, pointing_sigma_deg=0.5), AE.DesignConstraints(2500.0),
                                 gas_vars={"area": [0.7], "p_level": levels}, keep_candidates=False)


def test_inadmissible_state_never_displaces_admissible(real_gas):
    st = _states(real_gas)
    alone = {k: _close(st, [k]) for k in st}
    assert all(r.get("closes_constraints") for r in alone.values()), {k: r.get("status") for k, r in alone.items()}
    # the inadmissible variants have the better objective on their own ...
    assert alone["nc"]["T_minus_kD_mN"] > alone["ok"]["T_minus_kD_mN"]
    # ... but never win against an admissible state
    r = _close(st, ["nc", "ood", "par", "ok"])
    assert r["status"] == "OK" and r["feasible"] is True and r["evidence_admissible"] is True and r["x_p_level"] == "ok"
    # among inadmissible states the better evidence class wins: PARAMETRIC_SENSITIVITY > OUT_OF_MODEL_DOMAIN > NOT_CONVERGED
    assert _close(st, ["nc", "ood", "par"])["x_p_level"] == "par"
    assert _close(st, ["nc", "ood"])["x_p_level"] == "ood"


@pytest.mark.parametrize("key,status", [("nc", "MODEL_NOT_CONVERGED"), ("ood", "OUT_OF_MODEL_DOMAIN"),
                                        ("par", "PARAMETRIC_SENSITIVITY")])
def test_inadmissible_best_is_never_reported_ok(real_gas, key, status):
    r = _close(_states(real_gas), [key])
    assert r["status"] == status == r["evidence_class"] and r["feasible"] is False and r["evidence_admissible"] is False
    assert r["closes_constraints"] is True and math.isfinite(r["T_mN"])            # raw state kept for diagnostics
    assert r["comp_rotor_qualification"] in (RS.Q_NOT_EVALUATED_MATERIAL_BASIS, "PASS")
    pm = AE.propulsion_map(r, lambda area, p: _states(real_gas)[p], scales=(1.0,))
    assert pm["architecture_status"] == status and pm["evidence_admissible"] is False


def test_unlabelled_synthetic_state_is_not_ok(real_gas):
    bare = {k: v for k, v in real_gas.items() if not k.startswith(("gaspath_", "comp_rotor", "comp_sizing", "comp_u_max"))}
    r = _close({"bare": bare}, ["bare"])
    assert r["status"] == "GASPATH_STATUS_NOT_REPORTED" and r["feasible"] is False
