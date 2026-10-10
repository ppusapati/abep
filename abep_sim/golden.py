"""Golden benchmark cases (stabilisation gate 6).

Each case records the intermediate state of the chain — not only the final thrust — so that any later implementation
(Julia/Rust) can be checked stage by stage: atmosphere -> intake -> compressor/reservoir -> source plasma -> accelerator
-> power/thermal/mass/life -> spacecraft T/D -> mission. Values are produced by the frozen scenario (frozen NRLMSIS
dataset + frozen TPMC surface), so they are deterministic on any machine.

    python -m abep_sim.golden generate      # rewrite abep_sim/data/golden_v2.json (only on an intentional model change)
    python -m abep_sim.golden check         # compare; also run by the test suite

golden_v2 (owner decision A9.18 GOLDEN, 2026-10-01: NEW_ADMISSIBLE_CONVERGED_GOLDEN;
RETAIN_OLD_AS_NONCONVERGED_REGRESSION_REFERENCE). The golden_v1 design point of the gas-path-dependent cases (gas_path
at the default reservoir setpoint, accelerators on make_gas_fn(0.7, "nominal"), architecture_closure / mission at
intake area 1.3 m2, p_level 0.05 Pa) is not converged under G-03..G-05 (orifice setpoint unbracketed; at 1.3 m2 also
Gaede OUT_OF_MODEL_DOMAIN). Those cases are kept, values unchanged, as the `nonconverged_reference` fixture
(NONCONVERGED_REFERENCE / EXPECTED_NONCONVERGENCE): `check` recomputes them, compares them with the frozen v1 values and
asserts that the solver refuses them. The canonical gas-path-dependent cases now sit at GOLDEN_DESIGN_POINT, chosen by
the deterministic rule `select_design_point` (first admissible point of the default close_architecture gas grid in its
own iteration order; see SELECTION_RULE). golden_v1.json is kept unchanged as history.
"""
from __future__ import annotations
import copy, functools, hashlib, json, os, math

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
GOLDEN_FILE = os.path.join(DATA_DIR, "golden_v2.json")
GOLDEN_V1_FILE = os.path.join(DATA_DIR, "golden_v1.json")      # history (A9.18): never rewritten


def _flt(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, bool) or v is None or isinstance(v, str):
            out[k] = v
        elif isinstance(v, (int, float)):
            out[k] = float(v)
    return out


def case_atmosphere():
    from .atmosphere import atmosphere
    out = {}
    for alt in (180.0, 200.0, 230.0):
        for sol in ("low", "mean", "high"):
            a = atmosphere(alt, sol)
            out[f"{int(alt)}_{sol}"] = _flt({k: a[k] for k in ("rho", "fO", "fN2", "fO2", "T", "n", "V", "n_O")})
    return out


def case_intake():
    from .atmosphere import atmosphere
    from .intake import IntakeParams, collection
    atm = atmosphere(200.0, "mean"); out = {}
    for sc in ("maxwell", "cll"):
        for a, ld in ((0.8, 5.0), (0.95, 10.0), (0.5, 3.0)):
            c = collection(IntakeParams(area_m2=0.7, accommodation=a, use_tpmc=True, L_over_d=ld, scattering=sc), atm)
            out[f"{sc}_a{a}_ld{ld}"] = _flt({k: c[k] for k in ("eta_c", "C_D", "mdot_collected", "mdot_incident") if k in c})
    return out


def case_source_plasma():
    from .plasma_chem import Chamber, solve_global
    md = {"O": 0.40e-6, "N2": 0.50e-6, "O2": 0.10e-6}; out = {}
    for P in (100.0, 300.0):
        st = solve_global(Chamber(magnetised_wall_factor=0.3, volume_m3=1e-3, wall_area_m2=0.06), md, P, f_cutoff_Hz=2.45e9)
        out[f"P{int(P)}"] = _flt({"Te_eV": st.Te_eV, "n_e": st.n_e, "util_total": st.util_total, "eV_per_ion": st.eV_per_usable_ion,
                                  "P_iz_W": st.power["ionisation_excitation_W"], "P_wall_W": st.power["wall_W"],
                                  "I_exit_A": sum(st.ion_exit_A.values()), "sustained": st.sustained})
    return out


def case_hall():
    from .plasma_devices import coupled_channel, hall_run_coupled
    out = {}
    r = hall_run_coupled(coupled_channel(), 250.0, {"N2": 2e-6})
    out["anchor_N2"] = _flt({k: r[k] for k in ("T_N", "P_d_W", "I_d_A", "I_beam_A", "eta_b", "Te_eV", "n_e", "P_jet_W", "f_cx", "util_hall")})
    for md, start in ((1.0, "cold"), (1.3, "cold"), (1.7, "cold"), (1.7, "hot")):
        f = {"O": 0.43 * md * 1e-6, "N2": 0.51 * md * 1e-6, "O2": 0.06 * md * 1e-6}
        r = hall_run_coupled(coupled_channel(L_m=0.20), 275.0, f, start=start)
        out[f"air_{md}_{start}"] = _flt({k: r.get(k) for k in ("T_N", "P_d_W", "I_d_A", "Te_eV", "n_e", "P_jet_W", "ignited")})
    f = {"O": 0.43e-6, "N2": 0.51e-6, "O2": 0.06e-6}
    r = hall_run_coupled(coupled_channel(L_m=0.20), 275.0, f, {"O+": 0.17, "N2+": 0.10, "O2+": 0.03})
    out["air_1.0_seed0.3A"] = _flt({k: r.get(k) for k in ("T_N", "P_d_W", "Te_eV", "n_e")})
    return out



# ---------------------------------------------------------------------------------------------------------------------
# A9.18 golden design point (owner decision OD_2026_10_01_A9_18, decision GOLDEN)
# ---------------------------------------------------------------------------------------------------------------------
# The default gas-path grid of archengine.close_architecture (its `gas_vars or {...}` literal; a test checks that this
# copy matches) and its iteration order: area ascending (outer loop), p_level ascending (inner loop).
DEFAULT_GAS_GRID = {"area": [0.6, 0.7, 0.85], "p_level": [0.02, 0.05, 0.1]}
# The point the rule below selects. `generate` and the `design_point_selection` case re-run the rule; if it no longer
# selects this point, that is a model change (the golden moves; justify, regenerate, log), never a silent re-pick.
GOLDEN_DESIGN_POINT = {"area": 0.7, "p_level": 0.05}
# The golden_v1 point, retained only as the non-converged regression reference.
V1_DESIGN_POINT = {"area": 1.3, "p_level": 0.05}
# Fixed (unchanged from golden_v1) closure scenario of the architecture_closure / mission cases.
# A9.22 G4 (owner decision 2026-10-03, CATHODELESS_ACTIVE_BASELINE): this LaB6 Xe hollow-cathode closure is kept ONLY as
# HISTORICAL_NON_FLIGHT_REGRESSION (numerical reproducibility of committed history). It must not participate in
# architecture closure, selection, optimisation, current RFP compliance, flight mass/power/Xe budgets or design
# decisions; require_flight_eligible_case() refuses those uses. The active flight architecture is hall_icp_neutralizer
# (case hall_icp_neutralizer_reference).
HISTORICAL_NON_FLIGHT_ROLE = "HISTORICAL_NON_FLIGHT_REGRESSION"
HISTORICAL_NON_FLIGHT_ARCHITECTURE = "hall_internal+hall+lab6_xe"
HISTORICAL_NON_FLIGHT_CASES = ("architecture_closure", "mission")
GOLDEN_P_BUS_MAX_W = 2500.0
ACTIVE_REFERENCE_ARCHITECTURE = "hall_icp_neutralizer"
ACTIVE_REFERENCE_ROLE = "GOVERNED_REFERENCE_ACTIVE_ARCHITECTURE_PARTIAL"
FLIGHT_USES = ("architecture_closure", "architecture_selection", "optimisation", "rfp_compliance", "flight_budget",
               "design_decision")


class HistoricalNonFlightError(RuntimeError):
    """A HISTORICAL_NON_FLIGHT_REGRESSION golden case was requested for a flight use (A9.22 G4)."""


def require_flight_eligible_case(case: str, use: str) -> None:
    """Refuse a historical non-flight golden case for any FLIGHT_USES purpose. Regression reproduction ('regression')
    is the only use those cases have."""
    if use not in FLIGHT_USES + ("regression",):
        raise ValueError(f"unknown golden use {use!r}; one of {FLIGHT_USES + ('regression',)}")
    if use in FLIGHT_USES and CASE_ROLES.get(case) == HISTORICAL_NON_FLIGHT_ROLE:
        raise HistoricalNonFlightError(
            f"golden case {case!r} is {HISTORICAL_NON_FLIGHT_ROLE} ({HISTORICAL_NON_FLIGHT_ARCHITECTURE}, LaB6 Xe hollow "
            f"cathode): it must not be used for {use!r} (A9.22 G4; active architecture {ACTIVE_REFERENCE_ARCHITECTURE})")


def load_case(case: str, use: str) -> dict:
    """The stored golden_v2 case for a declared use (guarded: historical non-flight cases only for 'regression')."""
    require_flight_eligible_case(case, use)
    with open(GOLDEN_FILE) as f:
        return json.load(f)["cases"][case]

SELECTION_RULE = {
    "id": "A9.18-SEL-1 FIRST_ADMISSIBLE_IN_DEFAULT_GRID_ORDER",
    "rule": ("Walk the default close_architecture gas grid (DEFAULT_GAS_GRID: area [0.6, 0.7, 0.85] m2 x p_level "
             "[0.02, 0.05, 0.1] Pa) in the solver's own loop order (area ascending outer, p_level ascending inner) and "
             "take the FIRST point that is admissible (ADMISSIBILITY_CRITERIA). Nothing else (thrust, mass, power, T/D, "
             "closeness to golden_v1 numbers) enters the choice."),
    "neutrality": ("The grid and its order are fixed by archengine.close_architecture before any result is seen; the rule "
                   "reads only pass/fail admissibility verdicts, never a performance value, so it is neither a performance "
                   "optimum nor tuned to reproduce golden_v1. Cross-check (not used for the choice): the declared "
                   "alternative 'admissible point closest to the golden_v1 point (1.3 m2, 0.05 Pa), same p_level first, "
                   "then smallest |delta area|' selects the same point (0.7 m2, 0.05 Pa)."),
    "fixed_scenario": ("unchanged from golden_v1: architecture hall_internal+hall+lab6_xe, DesignConstraints(P_bus_max "
                       "2500 W), Spacecraft(bus_frontal_m2=0.10, pointing_sigma_deg=0.5), size_arrays, mission_envelope "
                       "(margin 1.0); gas state make_gas_fn() defaults (alpha 0.8, L/d 5, 200 km, mean solar, frozen "
                       "NRLMSIS + frozen TPMC surface, CompressorParams(ratio=2000), p_target = p_level)"),
}
ADMISSIBILITY_CRITERIA = (
    "inputs accepted by every input-validation rule (no ValueError from intake surface / TPMC / gas path)",
    "atmosphere from the frozen NRLMSIS dataset (atm_source 'NRLMSIS 2.1 frozen scenario ...'), TPMC intake model",
    "G-03 compressor recirculation converged (comp_converged)",
    "G-04 reservoir steady state converged (res_converged)",
    "G-05 orifice sizing converged AND bracketed/reachable (orifice_converged, orifice_bracketed)",
    "gaspath_status == CONVERGED",
    "MCC-02 Gaede domain: comp_gaede_domain_ok, comp_gaede_K_unclipped_min >= 1, gaspath_domain_status == IN_DOMAIN",
    "no unsized compressor fallback (comp_sized)",
    "rotor inside the labelled legacy sensitivity cap (comp_rotor_within_legacy_sensitivity_cap); rotor qualification "
    "PASS or the labelled NOT_EVALUATED_MATERIAL_BASIS (S2.3: no registered rotor-strength basis exists)",
    "close_architecture at that single gas point returns a closed design: status / evidence_class in {OK, "
    "PARAMETRIC_SENSITIVITY}, closes_constraints True, |ledger_resid| < 0.02 (gate 4)",
)
# PHY-06 repair: A9.18 item 1 asks for a golden point "inside the registered model domain". The 0-D Hall calibration
# envelope (archengine.CALIBRATION / calibration_status: Marchioni & Cappelli 2021 N2 extended channel, SPT-100 Xe) is
# NOT an admissibility criterion here; it is recorded for every closed grid point (hall_calibration,
# hall_calibration_extrapolation) and never silent.
HALL_CALIBRATION_DOMAIN = {
    "criterion": "0-D Hall calibration envelope (archengine.CALIBRATION['hall'], calibration_status)",
    "status": "RECORDED_NOT_GATING_OWNER_CONFIRMATION_REQUESTED",
    "statement": ("The 0-D Hall closure and its calibration envelope are withdrawn (CLAUDE.md 'Superseded / withdrawn': "
                  "all absolute Hall results of the 0-D closure, incl. the Marchioni calibration on an invented "
                  "geometry). This golden is a reproducibility reference of a converged numerical state, not physics "
                  "evidence, so the withdrawn envelope is not treated as part of the 'registered model domain' of A9.18 "
                  "item 1 for golden purposes. The selected point carries calibration = 'extrapolation' (worst relative "
                  "excursion recorded in cases.architecture_closure and in the grid scan); every closed point of the "
                  "default grid is an extrapolation (provenance.full_grid_scan). If the owner rules the envelope part "
                  "of the registered domain, SELECTION_RULE finds no admissible point and the golden must be re-decided; "
                  "it is never re-picked silently."),
    "basis": "docs/decisions/OD_2026_10_01_A9_18_GOLDEN_AND_BASELINE_OWNER_DECISIONS.md item 1; CLAUDE.md withdrawn list",
}
ROTOR_LABEL = ("comp_rotor_qualification = NOT_EVALUATED_MATERIAL_BASIS, comp_sizing_mode = PARAMETRIC_SENSITIVITY, "
               "architecture status / evidence_class = PARAMETRIC_SENSITIVITY, feasible False. A9.9 S2.3 allows a rotor "
               "to be explored as PARAMETRIC_SENSITIVITY while no rotor-strength basis is registered; it forbids only a "
               "qualified rotor_ok = true. The golden checks reproducibility of a converged numerical state, not "
               "qualification, so it carries this labelled state; it is not design evidence and not a qualified rotor.")


def _gas_record(area: float, p_level: float) -> dict:
    """Raw closure (system.physics_closure) of the gas state that archengine.make_gas_fn()(area, p_level) wraps (same
    Config). A9.22: only raw keys are read from it (identical values to the legacy merged system.evaluate record)."""
    from .system import Config, physics_closure
    from .intake import IntakeParams, CompressorParams
    return physics_closure(Config("hall_1stage", 200, "mean", IntakeParams(area_m2=area, accommodation=0.8, use_tpmc=True, L_over_d=5),
                           CompressorParams(ratio=2000), vd_V=275, gaspath_physics=True, p_margin_over_pmin=3.0,
                           p_target_Pa=float(p_level)))


# A9.22 G1 (governed baseline change, 2026-10-03): the canonical closure integrates the neutralizer Xe over the mission
# duration basis (operating_inputs.MISSION_HOURS = 26,280 h). The golden_v1 non-converged reference fixture is history
# and is recomputed exactly as golden_v1 generated it, on the pre-A9.22 26,000 h basis.
def _canonical_xe_hours() -> float:
    from .operating_inputs import MISSION_HOURS
    return float(MISSION_HOURS)


def _v1_xe_hours() -> float:
    from .operating_inputs import HISTORICAL_MISSION_HOURS_PRE_A9_22
    return float(HISTORICAL_MISSION_HOURS_PRE_A9_22)


@functools.lru_cache(maxsize=None)
def _closure_cached(area: float, p_level: float, firing_hours: float) -> dict:
    """close_architecture of the fixed golden scenario at one gas point (pure function of the key, rule 5)."""
    from . import archengine as AE
    from .mission_env import Spacecraft
    gf = AE.make_gas_fn(); A = {AE.arch_name(x): x for x in AE.enumerate_architectures()}
    sc = Spacecraft(bus_frontal_m2=0.10, pointing_sigma_deg=0.5)
    return AE.close_architecture(A[HISTORICAL_NON_FLIGHT_ARCHITECTURE], gf, sc, AE.DesignConstraints(GOLDEN_P_BUS_MAX_W),
                                 gas_vars={"area": [area], "p_level": [p_level]}, size_arrays=True, mission_envelope=True,
                                 envelope_margin=1.0, keep_candidates=False, firing_hours=firing_hours)


def _closure(area: float, p_level: float, firing_hours: float | None = None) -> dict:
    return copy.deepcopy(_closure_cached(area, p_level, _canonical_xe_hours() if firing_hours is None else float(firing_hours)))


def admissibility(area: float, p_level: float) -> dict:
    """Verdict of one grid point under ADMISSIBILITY_CRITERIA (labels only; no performance value is used)."""
    try:
        r = _gas_record(area, p_level)
    except ValueError as e:
        return {"verdict": "INPUT_REFUSED", "admissible": False, "reason": str(e)}
    gas_checks = {
        "frozen_atmosphere": str(r.get("atm_source", "")).startswith("NRLMSIS 2.1 frozen scenario"),
        "tpmc_intake": r.get("intake_model") == "tpmc",
        "g03_compressor_converged": bool(r["comp_converged"]),
        "g04_reservoir_converged": bool(r["res_converged"]),
        "g05_orifice_converged": bool(r["orifice_converged"]),
        "g05_orifice_bracketed": bool(r["orifice_bracketed"]),
        "gaspath_converged": r["gaspath_status"] == "CONVERGED",
        "gaede_domain_ok": bool(r["comp_gaede_domain_ok"]) and r["comp_gaede_K_unclipped_min"] >= 1.0,
        "in_domain": r["gaspath_domain_status"] == "IN_DOMAIN",
        "compressor_sized": bool(r["comp_sized"]),
        "rotor_within_legacy_cap": bool(r["comp_rotor_within_legacy_sensitivity_cap"]),
        "rotor_label_allowed": r["comp_rotor_qualification"] in ("PASS", "NOT_EVALUATED_MATERIAL_BASIS"),
    }
    out = {"checks": gas_checks, "gaspath_status": r["gaspath_status"], "gaspath_domain_status": r["gaspath_domain_status"],
           "gaspath_not_converged": ",".join(r["gaspath_not_converged"]), "comp_rotor_qualification": r["comp_rotor_qualification"]}
    failed = [k for k, ok in gas_checks.items() if not ok]
    if failed:
        verdict = ("GASPATH_MODEL_NOT_CONVERGED" if r["gaspath_status"] != "CONVERGED" else
                   "GASPATH_OUT_OF_MODEL_DOMAIN" if r["gaspath_domain_status"] != "IN_DOMAIN" else "GASPATH_NOT_ADMISSIBLE")
        return {**out, "verdict": verdict, "admissible": False, "reason": "failed: " + ",".join(failed)}
    c = _closure(area, p_level)
    out["closure_status"] = c.get("status")
    closed = (c.get("status") in ("OK", "PARAMETRIC_SENSITIVITY") and c.get("evidence_class") == c.get("status")
              and c.get("closes_constraints") is True and abs(c.get("ledger_resid", 1.0)) < 0.02)
    # recorded, never gating (HALL_CALIBRATION_DOMAIN)
    out["hall_calibration"] = c.get("calibration"); out["hall_calibration_extrapolation"] = c.get("extrapolation")
    if not closed:
        return {**out, "verdict": f"CLOSURE_{c.get('status')}", "admissible": False, "reason": str(c.get("reason", ""))}
    return {**out, "verdict": "ADMISSIBLE", "admissible": True, "reason": ""}


def select_design_point(grid: dict | None = None, full_scan: bool = False) -> tuple:
    """Apply SELECTION_RULE. Returns (selected {area, p_level} or None, ordered list of visited verdicts). With
    full_scan the whole grid is evaluated (provenance only; the choice is still the first admissible point)."""
    grid = grid or DEFAULT_GAS_GRID
    visited = []; selected = None
    for area in grid["area"]:
        for p in grid["p_level"]:
            v = admissibility(area, p)
            visited.append({"area": area, "p_level": p, **v})
            if v["admissible"] and selected is None:
                selected = {"area": area, "p_level": p}
                if not full_scan:
                    return selected, visited
    return selected, visited


def case_design_point_selection():
    _, visited = select_design_point()
    return {"rule_id": SELECTION_RULE["id"], "grid_area_m2": {str(i): float(a) for i, a in enumerate(DEFAULT_GAS_GRID["area"])},
            "grid_p_level_Pa": {str(i): float(p) for i, p in enumerate(DEFAULT_GAS_GRID["p_level"])},
            "visited": {f"A{v['area']}_p{v['p_level']}": {"verdict": v["verdict"], "admissible": v["admissible"],
                                                          **({"hall_calibration": v["hall_calibration"]}
                                                             if v.get("hall_calibration") is not None else {})}
                        for v in visited},
            "hall_calibration_domain_status": HALL_CALIBRATION_DOMAIN["status"],
            "selected": _flt({"area_m2": visited[-1]["area"], "p_level_Pa": visited[-1]["p_level"]}) if visited[-1]["admissible"] else {}}


_GAS_PATH_KEYS = ("eta_c", "C_D", "mdot_air_mgps", "p_in_Pa", "P_comp_W", "m_comp_kg", "m_intake_kg", "fO_inlet", "fO2_inlet", "drag_mN")
_GAS_PATH_LABELS = ("gaspath_status", "gaspath_domain_status", "comp_converged", "res_converged", "orifice_converged",
                    "orifice_bracketed", "comp_sized", "comp_gaede_domain_ok", "comp_gaede_K_unclipped_min", "comp_iterations",
                    "comp_residual", "res_iterations", "res_residual", "res_balance_residual_rel", "orifice_p_residual_rel",
                    "comp_rotor_qualification", "comp_sizing_mode", "comp_rotor_within_legacy_sensitivity_cap",
                    "comp_turbo_rows", "comp_drag_stages", "comp_rpm", "p_target_Pa")
_CLOSURE_KEYS = ("status", "x_Vd", "x_L_ch", "T_mN", "P_bus_W", "P_jet_W", "ledger_resid", "T_over_D_sc", "MEV_kg", "CBE_kg",
                 "A_array_m2", "m_system_kg", "life_sys_h", "Q_waste_W", "A_rad_m2", "xe_kg")
_CLOSURE_LABELS = ("x_area", "x_p_level", "evidence_class", "evidence_admissible", "feasible", "closes_constraints", "gaspath_status",
                   "gaspath_domain_status", "comp_rotor_qualification", "comp_sizing_mode", "calibration", "extrapolation",
                   "optimum_at_search_edge", "firing_hours_for_xe")
_MISSION_KEYS = ("mission_closed", "min_alt_km", "D_mean_mN", "T_mean_mN", "P_bus_mean_W", "P_bus_peak_W", "ao_fluence_m2", "fired_hours")
_MISSION_LABELS = ("architecture_status", "evidence_class", "evidence_admissible")


def _accelerator_values(gas: dict) -> dict:
    from . import archengine as AE
    A = {AE.arch_name(x): x for x in AE.enumerate_architectures()}
    out = {}
    g = AE._propulsion(A["ecr+grids+lab6_xe"], gas, {"P_ion": 800.0, "Vb": 1000.0, "A_grid": 1.2e-2, "gap": 1e-3})
    out["ecr_grids"] = _flt({"T_N": g["T_N"], "P_acc_W": g["P_acc_W"], "I_beam_A": g["I_beam_A"], "P_hat": g["P_hat"], "f_cx": g["f_cx"],
                             "life_h": g["life_items"]["grids"], "chi": g["chi_preion"]})
    AE.NOZZLE_ENERGY_BOUND["on"] = False                       # as in golden_v1 (the module default; set explicitly)
    n = AE._propulsion(A["ecr+mag_nozzle"], gas, {"P_ion": 700.0, "B0": 0.0875, "R_m": 50.0, "A_throat": 3e-3})
    out["ecr_nozzle"] = _flt({"T_N": n["T_N"], "E_i_eV": n["E_i_eV"], "eta_det": n["eta_det"], "m_acc": n["m_acc"], "chi": n["chi_preion"]})
    h = AE._propulsion(A["ecr+hall+lab6_xe"], gas, {"P_ion": 100.0, "Vd": 300.0, "L_ch": 0.20})
    out["ecr_hall"] = _flt({"T_N": h["T_N"], "P_acc_W": h["P_acc_W"], "I_beam_A": h["I_beam_A"], "chi": h["chi_preion"], "P_neut_W": h["P_neut_W"]})
    return out


def _mission(r: dict) -> tuple:
    from . import archengine as AE
    from .mission_env import Spacecraft
    from .mission5 import run_mission_generic
    gf = AE.make_gas_fn()
    sc = Spacecraft(bus_frontal_m2=0.10, pointing_sigma_deg=0.5)
    pm = AE.propulsion_map(r, gf)
    scm = copy.copy(sc); scm.array_area_m2 = r["A_array_m2"]
    m = run_mission_generic(r, scm, gf(r["x_area"], r["x_p_level"]), hours=4000.0, dt_h=6.0, pmap=pm, P_bus_max_W=GOLDEN_P_BUS_MAX_W)
    return pm, m


def _gas_key(pt: dict) -> str:
    return f"A{pt['area']}_p{pt['p_level']}"


def case_gas_path():
    """Gas path at the A9.18 golden design point (converged, in domain; p_target = p_level). Values plus the G-03..G-05 /
    MCC-02 / S2.3 labels of the state."""
    pt = GOLDEN_DESIGN_POINT
    r = _gas_record(pt["area"], pt["p_level"])
    return {_gas_key(pt): _flt({k: r[k] for k in _GAS_PATH_KEYS + _GAS_PATH_LABELS if k in r})}


def case_accelerators():
    """Accelerator physics on the gas state of the golden design point (golden_v1 used make_gas_fn()(0.7, 'nominal'),
    an unbracketed-orifice state; kept in nonconverged_reference)."""
    from . import archengine as AE
    gas = AE.make_gas_fn()(GOLDEN_DESIGN_POINT["area"], GOLDEN_DESIGN_POINT["p_level"])
    return {"gas_point": {"area_m2": float(gas["area"]), "p_level_Pa": float(GOLDEN_DESIGN_POINT["p_level"]),
                          "gaspath_status": gas["gaspath_status"], "gaspath_domain_status": gas["gaspath_domain_status"]},
            **_accelerator_values(gas)}


def case_architecture_closure():
    """HISTORICAL_NON_FLIGHT_REGRESSION (A9.22 G4): LaB6 Xe hollow-cathode closure, reproducibility only."""
    pt = GOLDEN_DESIGN_POINT
    r = _closure(pt["area"], pt["p_level"])
    return {"golden_role": HISTORICAL_NON_FLIGHT_ROLE, "architecture": HISTORICAL_NON_FLIGHT_ARCHITECTURE,
            "ext_hall_2p5kW": _flt({k: r.get(k) for k in _CLOSURE_KEYS + _CLOSURE_LABELS})}


def case_mission():
    """HISTORICAL_NON_FLIGHT_REGRESSION (A9.22 G4): mission run of the LaB6 Xe hollow-cathode closure."""
    pt = GOLDEN_DESIGN_POINT
    r = _closure(pt["area"], pt["p_level"])
    pm, m = _mission(r)
    return {"golden_role": HISTORICAL_NON_FLIGHT_ROLE, "architecture": HISTORICAL_NON_FLIGHT_ARCHITECTURE,
            "map_T_N": {str(s): float(t) for s, t in zip(pm["scale"], pm["T_N"])},
            "mission_4000h": _flt({k: m[k] for k in _MISSION_KEYS + _MISSION_LABELS})}


# --- A9.22 G4: governed reference case of the active flight architecture hall_icp_neutralizer ----------------------
NOT_EVALUATED = "NOT_EVALUATED_NO_ADMITTED_MODEL"
HALL_ICP_COMPOSITION = {
    "accelerator": "Hall accelerator (H-1 class)",
    "electron_source_neutralizer": "downstream RF/ICP electron source / neutralizer (13.56 MHz ICP; A9 topology)",
    "hollow_cathode": "none (no conventional hollow cathode, no LaB6 in the flight architecture)",
    "supply_modes": "air (intake -> filter -> compressor -> gas chamber -> valve) and Xe (Xe chamber -> valve)",
}
# Why each block is not evaluated (rule 6: no invented operating point; rule 8: no new propulsion family).
HALL_ICP_NOT_EVALUATED = {
    "hall_discharge_thrust_power": (
        "the 0-D Hall closure (plasma_devices.hall_run_coupled) is withdrawn (CLAUDE.md 'Superseded / withdrawn'); the "
        "HallThruster.jl transport credible set is empty (gate 3 FAIL; HallMap loads admitted members only), so no "
        "admitted model gives thrust, discharge power/current or anode efficiency"),
    "icp_neutralizer": (
        "archengine's only RF electron source, Neutralizer 'rf_cathode', is an air-fed plasma-bridge cathode (5 cm3 "
        "cavity, 3 mm orifice, extraction factor calibrated to AMPCAT microwave data, validated current capped at 0.5 A, "
        "life ceiling without data): it does not represent the A9 downstream 13.56 MHz ICP electron source honestly. "
        "ICP-45 capacity is NOT_EVALUATED until I_d,max,H1 is registered (A9.3-A9.6); RF ratings "
        "TBD_AFTER_IMPEDANCE_MAP; ICP gas feed unbooked (A9 recorder flag)"),
    "xe_supply_mode_flow": (
        "no admitted Xe flow for the Hall or the ICP neutralizer in either supply mode (A9.19/A9.20: Xe is the "
        "contingency / emergency supply mode); a Xe mass needs a flow and a duty profile, neither registered"),
    "p_bus_and_ppu": ("needs the Hall discharge and ICP loads above; the bus power boundary for hall_icp_neutralizer "
                      "is v2 work (A9.22 G8)"),
    "thermal": "coupled H-1 / ICP thermal closure UNRESOLVED (A9 binding status; never reported as PASS)",
    "life": "Hall channel wall life needs wall_life_trustworthy Hall maps (none admitted); ICP life not modelled",
    "mission_closure": "needs thrust and P_bus maps of an admitted Hall member; none exists",
}
HALL_ICP_MASS_LINES_NOT_EVALUATED = ("hall_accelerator", "icp_neutralizer", "rf_power_and_matching", "ppu",
                                     "thermal", "xe_load", "xe_tank", "harness", "structure")


def case_hall_icp_neutralizer_reference():
    """Governed reference case of the active flight architecture (A9.22 G4): only quantities the admitted, upstream
    (architecture-common) models compute at the golden design point: air supply-mode gas path, mission-basis AO exposure
    and coating lives, intake / compressor mass lines (PARAMETRIC_SENSITIVITY). Everything else is
    NOT_EVALUATED_NO_ADMITTED_MODEL with its reason; nothing is fabricated."""
    from . import archengine as AE
    from .life import LifeInputs, intake_life
    from .operating_inputs import MISSION_HOURS, FIRING_HOURS, FIRING_HOURS_LABEL
    pt = GOLDEN_DESIGN_POINT
    r = _gas_record(pt["area"], pt["p_level"])
    gas = AE.make_gas_fn()(pt["area"], pt["p_level"])
    il = intake_life(LifeInputs(ao_flux_ram_m2_s=r["ao_flux_m2s"], intake_alpha0=0.8, mission_h=MISSION_HOURS))
    air = _flt({"mdot_air_mgps": r["mdot_air_mgps"], "p_in_Pa": r["p_in_Pa"], "fO_inlet": r["fO_inlet"],
                "fO2_inlet": r["fO2_inlet"], "eta_c": r["eta_c"], "C_D": r["C_D"], "intake_drag_mN": r["drag_mN"],
                "P_comp_W": r["P_comp_W"], "gaspath_status": r["gaspath_status"],
                "gaspath_domain_status": r["gaspath_domain_status"],
                "comp_rotor_qualification": str(r["comp_rotor_qualification"]),
                "comp_sizing_mode": str(r["comp_sizing_mode"])})
    mass = {"intake": _flt({"cbe_kg": r["m_intake_kg"], "status": "PARAMETRIC_SENSITIVITY",
                            "basis": "system.evaluate intake model (F1Q-02: budgeting only, never a CBE / frozen mass)"}),
            "compressor": _flt({"cbe_kg": r["m_comp_kg"], "status": "PARAMETRIC_SENSITIVITY",
                                "basis": "compressor sizing under the labelled legacy tip-speed cap (S2.3 / MCC-03)"}),
            **{k: {"status": NOT_EVALUATED} for k in HALL_ICP_MASS_LINES_NOT_EVALUATED},
            "totals": {"CBE_kg": NOT_EVALUATED, "MEV_kg": NOT_EVALUATED,
                       "reason": "most mass lines have no admitted model; a partial sum is not a system mass"}}
    return {
        "architecture": ACTIVE_REFERENCE_ARCHITECTURE, "golden_role": ACTIVE_REFERENCE_ROLE,
        "composition": dict(HALL_ICP_COMPOSITION),
        "design_point": _flt({"area_m2": pt["area"], "p_level_Pa": pt["p_level"], "alt_km": 200.0, "solar": "mean",
                              "accommodation": 0.8, "L_over_d": 5.0}),
        "operating_basis": _flt({"mission_hours": MISSION_HOURS, "mission_hours_basis": "A9.22 G1 MISSION_DURATION_26280_H",
                                 "firing_life_assumption_h": FIRING_HOURS, "firing_life_label": FIRING_HOURS_LABEL}),
        "supply_modes": {"air": {"status": "EVALUATED_UPSTREAM_ONLY", **air},
                         "xe": {"status": NOT_EVALUATED, "reason": HALL_ICP_NOT_EVALUATED["xe_supply_mode_flow"]}},
        "ao_exposure_mission": _flt({"ao_flux_ram_m2_s": r["ao_flux_m2s"], "ao_fluence_m2": il["ao_fluence_m2"],
                                     "intake_coating_erosion_um": il["coating_erosion_um"],
                                     "intake_coating_ok": il["coating_ok"], "alpha_end": il["alpha_end"],
                                     "blade_coating_life_h": gas["blade_life_h"], "intake_life_h": gas["intake_life_h"]}),
        "mass_ledger": mass,
        "not_evaluated": {k: {"status": NOT_EVALUATED, "reason": v} for k, v in HALL_ICP_NOT_EVALUATED.items()},
        "excluded_from": "flight compliance / selection claims: this is a partial reference, not a closure",
    }


# --- golden_v1 point: NONCONVERGED_REFERENCE / EXPECTED_NONCONVERGENCE regression fixture --------------------------
NONCONVERGED_ROLE = "NONCONVERGED_REFERENCE"
NONCONVERGED_EXPECTATION = "EXPECTED_NONCONVERGENCE"
NONCONVERGED_CASES = ("gas_path", "accelerators", "architecture_closure", "mission")


def _v1_values_and_refusal() -> tuple:
    """Recompute the golden_v1 gas-path-dependent cases exactly as golden_v1 did (same inputs; same keys) and the labels
    proving that the solver refuses them."""
    from . import archengine as AE
    from .system import Config, physics_closure
    from .intake import IntakeParams, CompressorParams
    vals = {"gas_path": {}}; refusal = {"gas_path": {}}
    for area in (0.7, 1.3):
        r = physics_closure(Config("hall_1stage", 200, "mean", IntakeParams(area_m2=area, accommodation=0.8, use_tpmc=True, L_over_d=5),
                            CompressorParams(ratio=2000), vd_V=275, gaspath_physics=True))
        vals["gas_path"][f"A{area}"] = _flt({k: r[k] for k in _GAS_PATH_KEYS if k in r})
        refusal["gas_path"][f"A{area}"] = {"gaspath_status": r["gaspath_status"], "gaspath_not_converged": ",".join(r["gaspath_not_converged"]),
                                           "gaspath_domain_status": r["gaspath_domain_status"],
                                           "orifice_bracketed": bool(r["orifice_bracketed"]),
                                           # stored label name kept; its value is the raw model feasibility flag
                                           # (the legacy chk_compressor_feasible was assess(): raw comp_feasible)
                                           "chk_compressor_feasible": bool(r["comp_feasible"])}
    gas = AE.make_gas_fn()(0.7, "nominal")
    vals["accelerators"] = _accelerator_values(gas)
    cls, _ = AE.gas_evidence_class(gas)
    refusal["accelerators"] = {"gas_state": "make_gas_fn()(0.7, 'nominal')", "gaspath_status": gas["gaspath_status"],
                               "gaspath_not_converged": gas["gaspath_not_converged"], "evidence_class": cls}
    r = _closure(V1_DESIGN_POINT["area"], V1_DESIGN_POINT["p_level"], firing_hours=_v1_xe_hours())
    vals["architecture_closure"] = {"ext_hall_2p5kW": _flt({k: r.get(k) for k in _CLOSURE_KEYS})}
    refusal["architecture_closure"] = {"ext_hall_2p5kW": {k: r.get(k) for k in (
        "status", "evidence_class", "evidence_admissible", "feasible", "gaspath_status", "gaspath_not_converged",
        "gaspath_domain_status", "gaspath_out_of_domain")}}
    pm, m = _mission(r)
    vals["mission"] = {"map_T_N": {str(s): float(t) for s, t in zip(pm["scale"], pm["T_N"])},
                       "mission_4000h": _flt({k: m[k] for k in _MISSION_KEYS})}
    refusal["mission"] = {"mission_4000h": {k: m[k] for k in _MISSION_LABELS}}
    return vals, refusal


def refusal_violations(refusal: dict) -> list:
    """Semantic EXPECTED_NONCONVERGENCE assertions (independent of the stored labels): every fixture state must be
    refused — never CONVERGED / admissible / feasible."""
    bad = []
    for k, lab in refusal["gas_path"].items():
        if lab["gaspath_status"] != "MODEL_NOT_CONVERGED" or lab["chk_compressor_feasible"]:
            bad.append(f"gas_path/{k} not refused: {lab}")
    if refusal["accelerators"]["evidence_class"] == "OK" or refusal["accelerators"]["gaspath_status"] == "CONVERGED":
        bad.append(f"accelerators gas state not refused: {refusal['accelerators']}")
    c = refusal["architecture_closure"]["ext_hall_2p5kW"]
    if c["status"] != "MODEL_NOT_CONVERGED" or c["evidence_admissible"] or c["feasible"]:
        bad.append(f"architecture_closure not refused: {c}")
    m = refusal["mission"]["mission_4000h"]
    if m["evidence_admissible"] or m["architecture_status"] != "MODEL_NOT_CONVERGED":
        bad.append(f"mission not refused: {m}")
    return bad


def case_nonconverged_reference():
    vals, refusal = _v1_values_and_refusal()
    return {"role": NONCONVERGED_ROLE, "expectation": NONCONVERGED_EXPECTATION,
            "design_point": _flt({"area_m2": V1_DESIGN_POINT["area"], "p_level_Pa": V1_DESIGN_POINT["p_level"]}),
            "values": vals, "refusal": refusal, "refusal_violations": {str(i): v for i, v in enumerate(refusal_violations(refusal))}}


CASES = {"atmosphere": case_atmosphere, "intake": case_intake, "design_point_selection": case_design_point_selection,
         "gas_path": case_gas_path, "source_plasma": case_source_plasma, "hall": case_hall, "accelerators": case_accelerators,
         "architecture_closure": case_architecture_closure, "mission": case_mission,
         "nonconverged_reference": case_nonconverged_reference,
         "hall_icp_neutralizer_reference": case_hall_icp_neutralizer_reference}
CASE_ROLES = {**{k: "CANONICAL" for k in CASES}, "design_point_selection": "SELECTION_RECORD",
              "nonconverged_reference": f"{NONCONVERGED_ROLE} / {NONCONVERGED_EXPECTATION}",
              **{k: HISTORICAL_NON_FLIGHT_ROLE for k in HISTORICAL_NON_FLIGHT_CASES},
              "hall_icp_neutralizer_reference": ACTIVE_REFERENCE_ROLE}
# frozen inputs whose hashes the golden carries (CLAUDE.md rule 1)
FROZEN_INPUTS = ("atmosphere_msis21_v1.csv", "atmosphere_msis21_v1.json", "intake_surface_v1.csv", "intake_surface_v1.json")


def _sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _code_version() -> dict:
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    def git(*a):
        try:
            return subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, timeout=30).stdout
        except Exception:                                       # not a checkout (installed package): say so, no guess
            return ""
    head = git("rev-parse", "HEAD").strip()
    dirty = [ln[3:] for ln in git("status", "--porcelain", "--untracked-files=all", "--", "abep_sim").splitlines()
             if len(ln) > 3 and not ln.endswith(os.path.basename(GOLDEN_FILE))]
    return {"git_head_at_generation": head or "UNAVAILABLE",
            "abep_sim_paths_differing_from_head_at_generation": sorted(dirty),
            "note": "the generating code is git_head_at_generation plus the listed working-tree paths (the commit that "
                    "adds this file); the golden comparison, not this record, is the reproducibility gate"}


def _provenance(full_scan: list) -> dict:
    import platform
    import numpy, pandas, scipy
    return {
        "owner_decision": "A9.18 GOLDEN = NEW_ADMISSIBLE_CONVERGED_GOLDEN; RETAIN_OLD_AS_NONCONVERGED_REGRESSION_REFERENCE",
        "decision_records": ["docs/decisions/OD_2026_10_01_A9_18_GOLDEN_AND_BASELINE_OWNER_DECISIONS.md",
                             "docs/decisions/OD_2026_10_01_A9_9_S2_MODEL_CHANGE_OWNER_DECISIONS.md (S2.3, S2.4 G-03..G-05, S2.5 MCC-02)"],
        "generator": "python -m abep_sim.golden generate",
        "previous_golden": {"file": "abep_sim/data/golden_v1.json", "sha256": _sha256(GOLDEN_V1_FILE),
                            "status": "retained unchanged as history; its gas-path-dependent values are carried verbatim "
                                      "in cases.nonconverged_reference.values"},
        "frozen_inputs_sha256": {f"abep_sim/data/{f}": _sha256(os.path.join(DATA_DIR, f)) for f in FROZEN_INPUTS},
        "code_version": _code_version(),
        "environment": {"python": platform.python_version(), "numpy": numpy.__version__, "pandas": pandas.__version__,
                        "scipy": scipy.__version__},
        "selection_rule": SELECTION_RULE,
        "admissibility_criteria": list(ADMISSIBILITY_CRITERIA),
        "hall_calibration_domain": HALL_CALIBRATION_DOMAIN,
        "selected_design_point": {"area_m2": GOLDEN_DESIGN_POINT["area"], "p_level_Pa": GOLDEN_DESIGN_POINT["p_level"]},
        "previous_design_point": {"area_m2": V1_DESIGN_POINT["area"], "p_level_Pa": V1_DESIGN_POINT["p_level"],
                                  "status": "MODEL_NOT_CONVERGED (orifice setpoint unbracketed; Gaede OUT_OF_MODEL_DOMAIN)"},
        "full_grid_scan": [{k: v for k, v in s.items() if k != "checks"} | {"failed_checks": sorted(k for k, ok in s.get("checks", {}).items() if not ok)}
                           for s in full_scan],
        "rotor_qualification_label": ROTOR_LABEL,
        "a9_22": {"decision_record": "docs/decisions/OD_2026_10_03_A9_22_layer_separation_owner_decisions.json",
                  "G1": "mission-duration basis 26,280 h (architecture_closure xe_kg integrates over it; the "
                        "nonconverged_reference fixture keeps the pre-A9.22 26,000 h basis of golden_v1)",
                  "G4": (f"{HISTORICAL_NON_FLIGHT_ARCHITECTURE} cases {list(HISTORICAL_NON_FLIGHT_CASES)} are "
                         f"{HISTORICAL_NON_FLIGHT_ROLE}; active reference case hall_icp_neutralizer_reference "
                         f"({ACTIVE_REFERENCE_ROLE}); guards golden.require_flight_eligible_case and "
                         "archengine.require_flight_eligible")},
        "quotability": "historical 0-D / withdrawn-Hall benchmarks (CLAUDE.md 'Superseded / withdrawn'): reproducibility "
                       "references only; absolute values are not quotable",
    }


def generate() -> dict:
    sel, full_scan = select_design_point(full_scan=True)
    if sel != GOLDEN_DESIGN_POINT:
        raise RuntimeError(f"A9.18 selection rule selects {sel}, not GOLDEN_DESIGN_POINT {GOLDEN_DESIGN_POINT}")
    cases = {k: f() for k, f in CASES.items()}
    # the fixture keeps the golden_v1 reference values exactly as frozen (not the recomputed floats)
    v1 = json.load(open(GOLDEN_V1_FILE))["cases"]
    errs = []
    for k in NONCONVERGED_CASES:
        _compare(v1[k], cases["nonconverged_reference"]["values"][k], f"nonconverged_reference/values/{k}", 1e-6, errs)
    if errs or cases["nonconverged_reference"]["refusal_violations"]:
        raise RuntimeError("golden_v1 non-converged reference no longer reproduces / is no longer refused:\n" +
                           "\n".join(errs + list(cases["nonconverged_reference"]["refusal_violations"].values())))
    cases["nonconverged_reference"]["values"] = {k: v1[k] for k in NONCONVERGED_CASES}
    data = {"version": "golden_v2", "model": "ABEP Python Physics Candidate v1.5.1 + A9.9 S2 model changes",
            "case_roles": CASE_ROLES, "provenance": _provenance(full_scan), "cases": cases}
    with open(GOLDEN_FILE, "w") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    return data


# Absolute tolerances for quantities whose reference value is (near) zero by construction, keyed by the final path
# element. A relative check against a stored 0.0 turns floating-point noise into an infinite change. Kept per-key
# (not global) because the golden set also holds legitimately tiny values (e.g. atmospheric densities).
ATOL = {"ledger_resid": 1e-12,   # relative energy-ledger residual; gate is < 2 %, so 1e-12 is pure round-off
        # A9.18: round-off-level solver residuals of a converged gas state (tolerances 1e-6 / 1e-6)
        "res_balance_residual_rel": 1e-12, "orifice_p_residual_rel": 1e-12}


def _compare(ref, new, path, rtol, errs):
    if isinstance(ref, dict):
        for k in ref:
            if not isinstance(new, dict) or k not in new:
                errs.append(f"{path}/{k}: missing"); continue
            _compare(ref[k], new[k], f"{path}/{k}", rtol, errs)
    elif isinstance(ref, float) and isinstance(new, float):
        atol = ATOL.get(path.rsplit("/", 1)[-1], 1e-30)
        if not (math.isclose(ref, new, rel_tol=rtol, abs_tol=atol) or (math.isnan(ref) and math.isnan(new))):
            errs.append(f"{path}: {ref!r} -> {new!r} ({(new / ref - 1) if ref else float('inf'):+.2e})")
    elif ref != new:
        errs.append(f"{path}: {ref!r} -> {new!r}")


def check(cases=None, rtol: float = 1e-6) -> list[str]:
    ref = json.load(open(GOLDEN_FILE))["cases"]
    errs = []
    for k in (cases or CASES):
        new = json.loads(json.dumps(CASES[k]()))
        _compare(ref[k], new, k, rtol, errs)
        if k == "nonconverged_reference":
            # EXPECTED_NONCONVERGENCE: the fixture must still be refused (semantic check, independent of stored labels)
            errs += [f"nonconverged_reference: {v}" for v in new.get("refusal_violations", {}).values()]
    return errs


if __name__ == "__main__":
    # Exit status (owner decision 2026-09-27, CI signalling only): `check` prints "OK" and exits 0 when nothing moved;
    # otherwise it prints one line per deviation and exits 1, so CI can gate on the exit code (CLAUDE.md rule 2).
    # `generate` is unchanged (exit 0 after writing).
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "generate":
        d = generate(); print("written", GOLDEN_FILE, sum(len(v) for v in d["cases"].values()), "entries")
    else:
        e = check(); print("OK" if not e else "\n".join(e))
        sys.exit(1 if e else 0)
