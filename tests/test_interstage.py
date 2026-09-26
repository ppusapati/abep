"""Tests for abep_sim/interstage.py (lane 18, interstage_v1).

Fixture species "X", "X2", "X+", "X2+", "X++" and every fixture number below are SYNTHETIC TEST DATA
(source "test fixture - not physical data", evidence class "assumed"). They exercise the bookkeeping and never stand for
nitrogen, oxygen or xenon. Hand-calculated checks against the cited sources use only the formulas and the published
example numbers named in each test.
"""
import dataclasses
import json
import math
import os

import pytest

from abep_sim import interstage as ist
from abep_sim.constants import AMU, E_CHARGE, K_B

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = os.path.join(ROOT, "schemas", "architecture_comparison", "interstage_v1.schema.json")
FIX = "test fixture - not physical data"


def S(value, unit):
    return ist.Sourced(value, unit, FIX, "assumed", "fixture")


def rate(k, variable, lo, hi, exponent=0.0, x_ref=1.0):
    return ist.RateCoefficient(variable, k, x_ref, exponent, lo, hi, FIX, "assumed", "fixture")


M_X = 14.0 * AMU
M_X2 = 28.0 * AMU


def species():
    return (
        ist.Species("X2", 0, {"X": 2}, S(M_X2, "kg"), S(0.0, "eV")),
        ist.Species("X", 0, {"X": 1}, S(M_X, "kg"), S(4.0, "eV")),
        ist.Species("X2+", 1, {"X": 2}, S(ist.ion_mass_from_neutral(M_X2, 1), "kg"), S(15.0, "eV")),
        ist.Species("X+", 1, {"X": 1}, S(ist.ion_mass_from_neutral(M_X, 1), "kg"), S(18.0, "eV")),
        ist.Species("X++", 2, {"X": 1}, S(ist.ion_mass_from_neutral(M_X, 2), "kg"), S(47.0, "eV")),
    )


def reactions():
    th = ist.RECOMBINING_ELECTRON_THERMAL
    return (
        ist.VolumeReaction("dr_X2+", ("e", "X2+"), ("X", "X"), rate(2e-13, "electron_temperature_eV", 0.5, 50.0, -0.5),
                           th),
        ist.VolumeReaction("rr_X+", ("e", "X+"), ("X",), rate(1e-18, "electron_temperature_eV", 0.5, 50.0), th),
        ist.VolumeReaction("rr_X++", ("e", "X++"), ("X+",), rate(1e-18, "electron_temperature_eV", 0.5, 50.0), th),
        ist.VolumeReaction("ct_X+_X2", ("X+", "X2"), ("X", "X2+"), rate(1e-16, "ion_axial_energy_eV", 0.1, 100.0),
                           ist.NO_ELECTRON),
        ist.VolumeReaction("iz_X2", ("e", "X2"), ("X2+", "e", "e"), rate(1e-15, "electron_temperature_eV", 1.0, 100.0),
                           S(15.0, "eV")),
        ist.VolumeReaction("iz_X", ("e", "X"), ("X+", "e", "e"), rate(1e-15, "electron_temperature_eV", 1.0, 100.0),
                           S(14.0, "eV")),
        ist.VolumeReaction("iz_X+", ("e", "X+"), ("X++", "e", "e"), rate(1e-16, "electron_temperature_eV", 1.0, 100.0),
                           S(29.0, "eV")),
    )


EXCLUSIONS = {
    "ion_neutral_charge_transfer:X2+": "test fixture exclusion",
    "ion_neutral_charge_transfer:X++": "test fixture exclusion",
    "electron_impact_ionization:X2+": "test fixture exclusion",
    "electron_impact_ionization:X++": "test fixture exclusion",
}


def make_case(**kw):
    """Consistent fixture case; keyword overrides replace top-level fields or known sub-fields."""
    L = kw.pop("length", 0.05)
    R = kw.pop("radius", 0.02)
    B = kw.pop("B", 0.0)
    G_X2 = kw.pop("G_X2", 5.6e17)
    closure = kw.pop("closure", ist.H_LIEBERMAN)
    capture = kw.pop("capture", 0.9)
    A_hall = kw.pop("A_hall", 1.0e-3)
    A_leak = kw.pop("A_leak", 2.0e-4)
    n_steps = kw.pop("n_steps", 60)
    n_supplied = kw.pop("n_supplied", None)
    ions = ("X2+", "X+", "X++")
    wall = ist.WallModel(
        closure, "floating", {"X2+": ("X2",), "X+": ("X",), "X++": ("X",)},
        {i: S(1e-18, "m^2") for i in ions} if closure == ist.H_LIEBERMAN else None,
        {i: S(kw.pop("h", 0.3), "-") for i in ions} if closure == ist.H_EXPLICIT else None)
    case = ist.InterstageCase(
        case_id="fixture", architecture=kw.pop("architecture", "rf_hall"),
        energy_reference="fixture: X2 ground state = 0 eV (synthetic)",
        species=species(),
        source_exit=ist.SourceExitState(
            ion_density={"X2+": S(1e16, "m^-3"), "X+": S(5e15, "m^-3"), "X++": S(1e14, "m^-3")},
            ion_axial_speed={"X2+": S(3000.0, "m s^-1"), "X+": S(5000.0, "m s^-1"), "X++": S(6000.0, "m s^-1")},
            electron_temperature=S(5.0, "eV"),
            neutral_density=n_supplied or {"X2": S(1.0e19, "m^-3"), "X": S(0.0, "m^-3")},
            neutral_flow={"X2": S(G_X2, "s^-1"), "X": S(0.0, "s^-1")},
            neutral_temperature=S(300.0, "K")),
        geometry=ist.CircularDuct(S(L, "m"), S(R, "m"), "fixture wall", S(B, "T")),
        wall=wall, reactions=kw.pop("reactions", reactions()),
        wall_atom_recombination=kw.pop("war", (ist.WallAtomRecombination("X", "X2", S(0.1, "-")),)),
        process_exclusions=kw.pop("exclusions", dict(EXCLUSIONS)),
        neutral_conductance=ist.NeutralConductanceModel(
            ist.NC_SANTELER, {"X2": S(0.43e-18, "m^2"), "X": S(0.3e-18, "m^2")}, None, None),
        junction=ist.JunctionModel({i: S(capture, "-") for i in ions}, S(A_hall, "m^2"), S(A_leak, "m^2"),
                                   S(0.02, "m")),
        electron_energy_closure=kw.pop("electron_energy_closure", ist.ELECTRON_CLOSURE_ISOTHERMAL),
        numerics=ist.Numerics(n_steps, 1e-6, 1e-9, 1e-6, 1e-12, 200, 0.8, kw.pop("anderson", 4)))
    assert not kw, f"unused overrides {kw}"
    return case


def consistent(case):
    """Replace the supplied neutral entry densities by the flow-path values (the source lane's job)."""
    n = ist.flow_path_entry_densities(case)
    st = dataclasses.replace(case.source_exit, neutral_density={k: S(v, "m^-3") for k, v in n.items()})
    return dataclasses.replace(case, source_exit=st)


# ------------------------------------------------------------------------------------ conservation, full case
def test_full_case_conserves_particles_charge_mass_energy():
    res = ist.solve_interstage(consistent(make_case()))
    assert res["status"] == "OK", res["status_reason"]
    cons = res["conservation"]
    assert cons["passed"]
    assert max(cons["elements_rel"].values()) < 1e-12
    assert cons["charge_rel"] < 1e-12 and cons["mass_rel"] < 1e-12 and cons["energy_rel"] < 1e-12
    assert 0.0 < res["eta_duct"] < 1.0
    assert res["eta_transport"] == pytest.approx(0.9 * res["eta_duct"], rel=1e-12)   # uniform capture 0.9
    assert res["numerics"]["step_doubling_rel_change"] <= 1e-6
    # every loss channel is active and reported
    assert all(v["wall_loss_flow_s"] > 0 for v in res["ions"].values())
    assert all(v["events_s"] > 0 for v in res["reactions"].values())
    led = res["energy_ledger_W"]
    assert led["sinks"]["wall_electron"] > 0 and led["sinks"]["volume_reaction_heat_radiation"] > 0
    # charge-state fractions are normalised per element and evolve along the duct
    for key in ("entry", "exit", "delivered"):
        assert sum(res["charge_state_fractions"][key]["X"].values()) == pytest.approx(1.0, abs=1e-12)
    assert res["charge_state_fractions"]["entry"]["X"] != res["charge_state_fractions"]["exit"]["X"]
    # neutral leakage split by effective area (free-molecular: species-independent)
    nt = res["neutrals"]["X2"]
    assert nt["leak_flow_s"] / nt["exit_flow_s"] == pytest.approx(2e-4 / 1.2e-3, rel=1e-12)
    assert nt["pressure_drop_Pa"] > 0
    assert res["neutral_transport"]["regime_duct"] == "free_molecular"
    assert res["provenance"] and all(p["evidence_class"] in ist.EVIDENCE_CLASSES for p in res["provenance"])


def test_explicit_h_and_strong_b_bracket_wall_loss():
    base = consistent(make_case(closure=ist.H_EXPLICIT, h=0.5))
    r_h = ist.solve_interstage(base)
    strong = consistent(make_case(closure=ist.H_STRONG_B, B=0.02))
    r_b = ist.solve_interstage(strong)
    assert r_h["status"] == r_b["status"] == "OK"
    assert all(v["wall_loss_flow_s"] == 0 for v in r_b["ions"].values())
    assert r_b["eta_duct"] > r_h["eta_duct"]
    assert r_b["wall"]["magnetization"]["electron_gyroradius_m"] > 0
    assert r_b["conservation"]["energy_rel"] < 1e-12 and r_h["conservation"]["energy_rel"] < 1e-12


# ---------------------------------------------------------------------------------------------- limiting cases
def test_zero_length_gives_unit_transport_and_no_losses():
    case = consistent(make_case(length=0.0, capture=1.0, A_leak=0.0))
    res = ist.solve_interstage(case)
    assert res["status"] == "OK", res["status_reason"]
    assert res["eta_duct"] == 1.0 and res["eta_transport"] == 1.0 and res["eta_junction"] == 1.0
    assert all(v["wall_loss_flow_s"] == 0 and v["exit_flow_s"] == v["entry_flow_s"] for v in res["ions"].values())
    assert all(v["events_s"] == 0 for v in res["reactions"].values())
    assert res["energy_ledger_W"]["electron_heat_from_source_W"] == 0
    assert all(v == 0 for v in res["energy_ledger_W"]["sinks"].values())
    nt = res["neutrals"]["X2"]
    assert nt["leak_flow_s"] == 0 and nt["to_hall_flow_s"] == nt["entry_flow_s"]
    # zero-length duct = its entrance aperture (Santeler tau(0) = 1, Chiggiato Eq. 20): drop = Q / (<v> A / 4)
    A = math.pi * 0.02 ** 2
    vbar = math.sqrt(8 * K_B * 300.0 / (math.pi * M_X2))
    assert nt["pressure_drop_Pa"] == pytest.approx(5.6e17 * K_B * 300.0 / (0.25 * vbar * A), rel=1e-12)
    assert res["neutral_transport"]["transmission_probability"] == 1.0


def test_closed_channel_transmits_nothing():
    """Junction closed to the Hall channel (no ion capture, no Hall-path conductance): nothing is delivered and
    everything leaves through the leak path, with conservation intact."""
    case = consistent(make_case(capture=0.0, A_hall=0.0, A_leak=1.2e-3))
    res = ist.solve_interstage(case)
    assert res["status"] == "OK", res["status_reason"]
    assert res["eta_transport"] == 0.0 and res["eta_transport_mass"] == 0.0
    assert res["mass_delivery_fraction"] == 0.0
    assert all(v["delivered_to_hall_flow_s"] == 0 for v in res["ions"].values())
    assert all(v["to_hall_flow_s"] == 0 for v in res["neutrals"].values())
    assert res["conservation"]["passed"]


def test_closed_duct_is_infeasible_for_neutral_throughput():
    case = make_case()
    nc = ist.NeutralConductanceModel(ist.NC_TRANSMISSION, case.neutral_conductance.collision_cross_section,
                                     S(0.0, "-"), None)
    res = ist.solve_interstage(dataclasses.replace(case, neutral_conductance=nc))
    assert res["status"] == "INFEASIBLE" and res["eta_transport"] is None


def test_junction_closed_to_all_neutral_paths_is_infeasible():
    res = ist.solve_interstage(make_case(A_hall=0.0, A_leak=0.0))
    assert res["status"] == "INFEASIBLE" and res["eta_transport"] is None


def test_longer_duct_transmits_less():
    res = [ist.solve_interstage(consistent(make_case(length=L, n_steps=150))) for L in (0.01, 0.05, 0.1)]
    assert [r["status"] for r in res] == ["OK"] * 3
    assert res[0]["eta_duct"] > res[1]["eta_duct"] > res[2]["eta_duct"]


# ------------------------------------------------------------------------------ hand-calculated source points
def test_bohm_speed_and_flux_hand_calculation():
    # u_B = (e T_e / M)^(1/2), Lieberman short course slide 41: 28 u, 5 eV
    u = ist.bohm_speed(5.0, 28.0 * AMU, 1)
    assert u == pytest.approx(math.sqrt(5.0 * 1.602176634e-19 / (28.0 * 1.66053906660e-27)), rel=1e-15)
    assert u == pytest.approx(4150.85, rel=1e-5)
    assert ist.bohm_speed(5.0, 28.0 * AMU, 2) == pytest.approx(math.sqrt(2) * u, rel=1e-15)
    assert ist.bohm_wall_flux(1e16, 0.4, u) == pytest.approx(0.4 * 1e16 * u, rel=1e-15)
    # Lieberman slide 52 example: argon, T_e ~ 3.5 V -> u_B ~ 2.9e3 m/s (approximate Ar mass 40 u, 2 s.f. check)
    assert round(ist.bohm_speed(3.5, 40.0 * AMU, 1), -2) == 2900.0


def test_lieberman_h_factors_reproduce_slide_52_example():
    # R = 0.15 m, l = 0.3 m, lambda_i = 0.03 m -> h_l ~ h_R ~ 0.3 (slides 44, 52)
    hR = ist.h_radial_lieberman(0.15, 0.03)
    hl = ist.h_axial_lieberman(0.3, 0.03)
    assert hR == pytest.approx(0.8 / 3.0, rel=1e-15)
    assert hl == pytest.approx(0.86 / math.sqrt(8.0), rel=1e-15)
    assert round(hR, 1) == round(hl, 1) == 0.3
    assert ist.h_radial_lieberman(0.02, math.inf) == pytest.approx(0.4, rel=1e-15)


def test_floating_sheath_reduces_to_lieberman_single_species():
    M = 40.0 * AMU
    Vs = ist.floating_sheath_potential(3.0, [(1, 1e16, ist.bohm_speed(3.0, M, 1))])
    assert Vs == pytest.approx(0.5 * 3.0 * math.log(M / (2 * math.pi * ist.M_E)), rel=1e-12)
    assert round(Vs / 3.0, 1) == 4.7          # "V_s ~ 4.7 T_e for argon" (slide 48)


def test_conductance_hand_points_against_chiggiato():
    # <v>(N2-like 28 u, 293 K) ~ 470 m/s (Chiggiato Table 4); C' = <v>/4 ~ 117.5 m^3 s^-1 m^-2 (Table 8)
    vbar = ist.mean_molecular_speed(293.0, 28.0 * AMU)
    assert vbar == pytest.approx(math.sqrt(8 * 1.380649e-23 * 293.0 / (math.pi * 28.0 * 1.66053906660e-27)), rel=1e-15)
    assert vbar == pytest.approx(470.0, rel=2e-3)
    assert ist.aperture_conductance(1.0, 293.0, 28.0 * AMU) == pytest.approx(117.5, rel=2e-3)
    # Santeler: tau ~ 0.5 for L = D (Chiggiato Fig. 4); exact value of Eq. 21 at L/R = 2
    tau = ist.santeler_transmission_probability(2.0, 1.0)
    assert tau == pytest.approx(1.0 / (1.0 + 0.75 * (1.0 + 1.0 / (3.0 * (1.0 + 2.0 / 7.0)))), rel=1e-15)
    assert tau == pytest.approx(0.5143, abs=1e-4)
    assert ist.santeler_transmission_probability(0.0, 1.0) == 1.0
    # long tubes: tau -> 8R/(3L) within 10 % for L/R >> 20 (Chiggiato Eq. 22 and text)
    assert ist.santeler_transmission_probability(200.0, 1.0) == pytest.approx(8.0 / 600.0, rel=0.10)
    # Kn regimes (Chiggiato Table 7)
    assert ist.flow_regime(0.6) == "free_molecular" and ist.flow_regime(0.1) == "transitional"
    assert ist.flow_regime(0.005) == "viscous"
    lam = ist.molecular_mean_free_path(1e20, 0.43e-18)
    assert lam == pytest.approx(1.0 / (math.sqrt(2) * 1e20 * 0.43e-18), rel=1e-15)


def test_leybold_knudsen_equation_hand_point():
    # d = 1 cm, l = 10 cm, p_bar = 0.01 mbar (1 Pa): C = 135*0.1*0.01 + 12.1*0.1*(1+1.92)/(1+2.37) l/s
    C = ist.knudsen_conductance_air_20C_leybold(0.01, 0.10, 1.0, 1.0)
    expected_l_s = 135.0 * 0.1 * 0.01 + 1.21 * 2.92 / 3.37
    assert C == pytest.approx(expected_l_s * 1e-3, rel=1e-12)
    with pytest.raises(ist.InterstageDomainError):
        ist.knudsen_conductance_air_20C_leybold(0.02, 0.10, 1.0, 1.0)     # l < 10 d


def test_gyroradius_nrl_form():
    r = ist.gyroradius(ist.M_E, 1.0e6, 1, 0.01)
    assert r == pytest.approx(1.0e6 * ist.M_E / (E_CHARGE * 0.01), rel=1e-15)


# ------------------------------------------------------------------------------------------------ refusals
def test_hall_only_is_refused():
    with pytest.raises(ist.InterstageInputError, match="no interstage"):
        ist.solve_interstage(make_case(architecture="hall_only"))
    assert ist.architecture_has_interstage("ecr_hall") and not ist.architecture_has_interstage("hall_only")
    with pytest.raises(ist.InterstageInputError):
        ist.architecture_has_interstage("magnetic_nozzle")


def test_tbd_and_missing_inputs_are_refused():
    case = make_case()
    st = dataclasses.replace(case.source_exit, electron_temperature=ist.TBD("RF source exit T_e from lane 07"))
    with pytest.raises(ist.InterstageTBDError, match="lane 07"):
        ist.solve_interstage(dataclasses.replace(case, source_exit=st))
    st = dataclasses.replace(case.source_exit, electron_temperature=None)
    with pytest.raises(ist.InterstageInputError, match="missing"):
        ist.solve_interstage(dataclasses.replace(case, source_exit=st))
    st = dataclasses.replace(case.source_exit, ion_axial_speed={"X2+": S(3000.0, "m s^-1")})
    with pytest.raises(ist.InterstageInputError, match="missing entries"):
        ist.solve_interstage(dataclasses.replace(case, source_exit=st))
    with pytest.raises(ist.InterstageInputError, match="evidence_class"):
        ist.Sourced(1.0, "m", "x", "guessed", "none")
    with pytest.raises(ist.InterstageInputError, match="unit"):
        ist.solve_interstage(dataclasses.replace(case, geometry=ist.CircularDuct(S(5.0, "cm"), S(0.02, "m"), "w",
                                                                                 S(0.0, "T"))))


def test_catalogue_records_and_tbd_entries():
    dr = ist.catalogue_entry("dissociative_recombination:N2+")
    assert dr.k_ref_m3_s == pytest.approx(2.2e-13) and dr.exponent == -0.39 and dr.validity_max == 1200.0
    assert "ABSTRACT ONLY" in dr.source
    with pytest.raises(ist.InterstageDomainError, match="outside the source-stated validity"):
        dr.evaluate(3.0 * E_CHARGE / K_B, "N2+ DR at 3 eV")      # interstage T_e: no extrapolation
    assert dr.evaluate(300.0, "check") == pytest.approx(2.2e-13)
    with pytest.raises(ist.InterstageTBDError):
        ist.catalogue_entry("dissociative_recombination:N2+@Te>1200K")
    with pytest.raises(ist.InterstageTBDError):
        ist.catalogue_entry("junction_ion_capture_fraction")
    assert ist.catalogue_entry("ionization_energy:N").value == 14.53413


def test_rate_outside_validity_is_refused():
    rx = list(reactions())
    rx[0] = ist.VolumeReaction("dr_X2+", ("e", "X2+"), ("X", "X"), rate(2e-13, "electron_temperature_eV", 0.01, 1.0),
                               ist.RECOMBINING_ELECTRON_THERMAL)
    with pytest.raises(ist.InterstageDomainError, match="validity"):
        ist.solve_interstage(make_case(reactions=tuple(rx)))


def test_unaddressed_process_is_refused():
    rx = tuple(r for r in reactions() if r.reaction_id != "dr_X2+")
    with pytest.raises(ist.InterstageTBDError, match="volume_recombination:X2\\+"):
        ist.solve_interstage(make_case(reactions=rx))
    with pytest.raises(ist.InterstageTBDError, match="wall_atom_recombination:X"):
        ist.solve_interstage(make_case(war=()))
    # an explicit, justified exclusion is accepted
    ex = dict(EXCLUSIONS, **{"volume_recombination:X2+": "test fixture exclusion"})
    assert ist.solve_interstage(consistent(make_case(reactions=rx, exclusions=ex)))["status"] == "OK"


def test_unbalanced_or_energy_inconsistent_reactions_are_refused():
    bad = reactions() + (ist.VolumeReaction("bad", ("e", "X2"), ("X+", "e", "e"),
                                            rate(1e-15, "electron_temperature_eV", 1.0, 100.0), S(20.0, "eV")),)
    with pytest.raises(ist.InterstageInputError, match="elements"):
        ist.solve_interstage(make_case(reactions=bad))
    rx = list(reactions())
    rx[4] = ist.VolumeReaction("iz_X2", ("e", "X2"), ("X2+", "e", "e"),
                               rate(1e-15, "electron_temperature_eV", 1.0, 100.0), S(10.0, "eV"))   # < 15 eV
    with pytest.raises(ist.InterstageInputError, match="endothermicity"):
        ist.solve_interstage(make_case(reactions=tuple(rx)))


def test_ion_mass_must_close_mass_balance():
    sp = list(species())
    sp[2] = ist.Species("X2+", 1, {"X": 2}, S(M_X2, "kg"), S(15.0, "eV"))      # neutral mass used for the ion
    with pytest.raises(ist.InterstageInputError, match="mass"):
        ist.solve_interstage(dataclasses.replace(make_case(), species=tuple(sp)))


def test_formula_domains_are_enforced():
    with pytest.raises(ist.InterstageDomainError, match="B > 0"):
        ist.solve_interstage(make_case(B=0.01))                        # Lieberman h with a magnetic field
    with pytest.raises(ist.InterstageDomainError, match="requires an axial magnetic field"):
        ist.solve_interstage(make_case(closure=ist.H_STRONG_B, B=0.0))
    with pytest.raises(ist.InterstageDomainError, match="Knudsen"):
        ist.solve_interstage(make_case(G_X2=5.6e19))                  # ~100x pressure: transitional regime
    with pytest.raises(ist.InterstageTBDError, match="electron_energy_closure"):
        ist.solve_interstage(make_case(electron_energy_closure="adiabatic"))


def test_inconsistent_neutral_boundary_is_infeasible_with_diagnostics():
    res = ist.solve_interstage(make_case(n_supplied={"X2": S(1.0e19, "m^-3"), "X": S(0.0, "m^-3")}))
    assert res["status"] == "INFEASIBLE" and res["eta_transport"] is None and res["ions"] is None
    assert res["diagnostics"]["flow_path_entry_density_m3"]["X2"] > 0


def test_nonconverged_numerics_are_model_error_without_numbers():
    case = consistent(make_case())
    case = dataclasses.replace(case, numerics=ist.Numerics(1, 1e-14, 1e-9, 1e-6, 1e-12, 200, 0.5, 4))
    res = ist.solve_interstage(case)
    assert res["status"] == "MODEL_ERROR" and res["eta_transport"] is None and res["energy_ledger_W"] is None


def test_compare_with_required_is_a_single_case_condition():
    res = ist.solve_interstage(consistent(make_case()))
    req = ist.Sourced(0.5, "-", "abep_sim/breakeven.py place_evidence eta_transport_min (fixture)", "model-derived", "fixture")
    out = ist.compare_with_required(res, req)
    assert out["margin"] == pytest.approx(res["eta_transport"] - 0.5)
    assert out["condition_met"] == (res["eta_transport"] >= 0.5)
    bad = dict(res, status="MODEL_ERROR")
    with pytest.raises(ist.InterstageInputError):
        ist.compare_with_required(bad, req)


# --------------------------------------------------------------------------------------------- schema / io
def _validate(inst, schema, root, path="$"):
    """Minimal JSON-Schema checker for the keywords used by interstage_v1.schema.json (jsonschema not required)."""
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        return _validate(inst, root["$defs"][name], root, path)
    if "anyOf" in schema:
        errs = []
        for sub in schema["anyOf"]:
            try:
                _validate(inst, sub, root, path)
                return
            except AssertionError as e:
                errs.append(str(e))
        raise AssertionError(f"{path}: no anyOf branch matched: {errs}")
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        ok = {"object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
              "string": lambda v: isinstance(v, str), "boolean": lambda v: isinstance(v, bool),
              "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
              "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
              "null": lambda v: v is None}
        assert any(ok[x](inst) for x in types), f"{path}: {inst!r} is not {types}"
    if "enum" in schema:
        assert inst in schema["enum"], f"{path}: {inst!r} not in {schema['enum']}"
    if "const" in schema:
        assert inst == schema["const"], f"{path}: {inst!r} != {schema['const']!r}"
    if isinstance(inst, dict):
        for k in schema.get("required", []):
            assert k in inst, f"{path}: missing {k}"
        props = schema.get("properties", {})
        for k, v in inst.items():
            if k in props:
                _validate(v, props[k], root, f"{path}.{k}")
            elif schema.get("additionalProperties") is False:
                raise AssertionError(f"{path}: unexpected property {k}")
            elif isinstance(schema.get("additionalProperties"), dict):
                _validate(v, schema["additionalProperties"], root, f"{path}.{k}")
    if isinstance(inst, list) and "items" in schema:
        for i, v in enumerate(inst):
            _validate(v, schema["items"], root, f"{path}[{i}]")
    if isinstance(inst, (int, float)) and not isinstance(inst, bool):
        if "minimum" in schema:
            assert inst >= schema["minimum"], f"{path}: {inst} < minimum"
        if "maximum" in schema:
            assert inst <= schema["maximum"], f"{path}: {inst} > maximum"


def test_schema_describes_case_and_results():
    schema = json.load(open(SCHEMA))
    assert schema["$id"].endswith("interstage_v1") and schema["x-model"]["module"] == "abep_sim/interstage.py"
    case = consistent(make_case())
    d = ist.case_to_dict(case)
    _validate(d, schema["$defs"]["case"], schema)
    assert ist.case_to_dict(ist.case_from_dict(json.loads(json.dumps(d)))) == d          # lossless round trip
    ok = ist.solve_interstage(case)
    _validate(json.loads(json.dumps(ok)), schema["$defs"]["result"], schema)
    bad = ist.solve_interstage(make_case())                                               # INFEASIBLE result
    _validate(json.loads(json.dumps(bad)), schema["$defs"]["result"], schema)
    # schema vocabularies match the module
    defs = schema["$defs"]
    assert defs["case"]["properties"]["architecture"]["enum"] == list(ist.ARCHITECTURES_WITH_INTERSTAGE)
    assert defs["sourced"]["properties"]["evidence_class"]["enum"] == list(ist.EVIDENCE_CLASSES)
    assert defs["wall"]["properties"]["radial_loss_closure"]["enum"] == list(ist.RADIAL_LOSS_CLOSURES)
    assert defs["neutral_conductance"]["properties"]["mode"]["enum"] == list(ist.NEUTRAL_CONDUCTANCE_MODES)
    assert defs["result"]["properties"]["status"]["enum"] == list(ist.STATUS_VALUES)
    assert set(defs["result"]["required"]) == set(ok)


def test_case_from_dict_rejects_unknown_and_missing_keys():
    d = ist.case_to_dict(make_case())
    d2 = dict(d, surprise=1)
    with pytest.raises(ist.InterstageInputError, match="unexpected"):
        ist.case_from_dict(d2)
    d3 = dict(d)
    d3.pop("numerics")
    with pytest.raises(ist.InterstageInputError, match="missing"):
        ist.case_from_dict(d3)
    d4 = json.loads(json.dumps(d))
    d4["source_exit"]["electron_temperature"] = {"tbd": "ECR exit T_e (lane 08)"}
    with pytest.raises(ist.InterstageTBDError, match="lane 08"):
        ist.solve_interstage(ist.case_from_dict(d4))


def test_module_is_not_wired_into_archengine():
    src = open(os.path.join(ROOT, "abep_sim", "archengine.py")).read()
    assert "interstage" not in src.replace("Interstage", "").lower() or "abep_sim.interstage" not in src
    assert "from .interstage" not in src and "import interstage" not in src


# ------------------------------------------------------------------------------ common model, numerics invariance
def test_rf_and_ecr_use_the_identical_model():
    """Same exit state + geometry => identical result; the architecture id only labels the case."""
    rf = ist.solve_interstage(consistent(make_case(architecture="rf_hall")))
    ecr = ist.solve_interstage(consistent(make_case(architecture="ecr_hall")))
    assert rf["status"] == ecr["status"] == "OK"
    assert rf["eta_transport"] == ecr["eta_transport"]
    assert rf["energy_ledger_W"] == ecr["energy_ledger_W"]
    assert rf["not_a_comparison"] and set(rf["milestone_support"]) == {"A", "B", "C"}


def test_anderson_acceleration_does_not_change_the_answer():
    base = consistent(make_case(anderson=0))
    plain = ist.solve_interstage(base)
    acc = ist.solve_interstage(dataclasses.replace(base, numerics=dataclasses.replace(base.numerics,
                                                                                     fixed_point_anderson_depth=4)))
    assert plain["status"] == acc["status"] == "OK"
    assert acc["neutral_transport"]["fixed_point_iterations"] < plain["neutral_transport"]["fixed_point_iterations"]
    assert acc["eta_transport"] == pytest.approx(plain["eta_transport"], rel=1e-9)
    for k in plain["neutrals"]:
        assert acc["neutrals"][k]["p_entry_Pa"] == pytest.approx(plain["neutrals"][k]["p_entry_Pa"], rel=1e-9)
    with pytest.raises(ist.InterstageInputError, match="anderson"):
        ist.solve_interstage(dataclasses.replace(base, numerics=dataclasses.replace(base.numerics,
                                                                                   fixed_point_anderson_depth=-1)))


def test_every_catalogue_record_is_sourced_or_tbd():
    for key, rec in ist.CATALOGUE.items():
        if isinstance(rec, ist.TBD):
            assert rec.requires.strip()
        else:
            assert rec.source.strip() and rec.evidence_class in ist.EVIDENCE_CLASSES, key
    # the abstract-only recombination rates are not labelled 'measured'
    assert ist.catalogue_entry("dissociative_recombination:O2+").evidence_class == "inferred"
    assert all(v.strip() for v in ist.SOURCES.values())
