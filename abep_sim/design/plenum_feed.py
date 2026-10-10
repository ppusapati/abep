"""A9.7 F4 plenum / feed synthesis (owner directive OD_2026_10_01_A9_7, lane fo_a9_7_f4_plenum_feed).

New design-synthesis code. It couples

    intake (F1 IF-A1 record) -> filter (F2 FilterStage) -> compressor (F3 design, DragCompressor physics)
        -> plenum (abep_sim.reservoir physics) -> feed valve / orifice -> H-1 inlet (HALL_INLET_Z0, F5)

and solves the transient, species-resolved plenum balance (A9.7 F4; recorder reading of the formula):

    dm_s/dt = mdot_s,compressor - mdot_s,Hall - mdot_s,losses (+ R_s, the mass-conserving O -> O2 wall conversion)

with  mdot_s,compressor = gross through-flow of the compressor (Gaede cascade of DragCompressor),
      mdot_s,Hall       = feed-valve flow (molecular orifice law of abep_sim.reservoir, Reservoir.conductance),
      mdot_s,losses     = back-leak through the compressor (DragCompressor leak conductance, i.e. the backflow toward
                          the filter / intake; the F2 / F1 backflow then acts at the compressor-inlet node) + external
                          plenum leakage (Reservoir leak path),
      R_s               = Reservoir wall recombination R_O = -gamma (cbar_O / 4) A_w n_O m_O, R_O2 = +same mass.

It calls (never modifies) abep_sim.compressor.DragCompressor, abep_sim.reservoir.Reservoir, abep_sim.materials,
abep_sim.design.filter_stage (F2) and abep_sim.design.compressor_synthesis (F3); it reads the committed F1 / F3
interface records. Not wired into archengine; golden benchmarks cannot move.

Physics (free-molecular throughout; every relation below is the one the called module uses, or a stated derivation):
  * intake + filter at the compressor-inlet node (pressure p2,s; quasi-steady, see QUASI_STEADY_NOTE): F1 net-flow
    law mdot_net,s = mdot_fwd,s (1 - p2,s / p_passive,s) written as q_net = f_s - e_s p2,s in throughput units
    (Pa m^3/s, q = mdot k T / m). A filter between the intake exit and the compressor inlet is combined by the
    gap-reflection series (our derivation, no source): D = t_f + t_u (1 - a) r_f / (1 - (1 - a) r_u),
    E = r_b + t_u (1 - a) t_b / (1 - (1 - a) r_u) - 1, f = q_fwd D, e = -E A cbar / 4, with a = phi K_back the
    intake escape probability, recovered from the F1 record as a = e_F1 / (A cbar / 4). For F2 'none' (t = 1, r = 0)
    D = 1 and E = -a: the F1 law is reproduced exactly (test).
  * compressor: per-species linear Gaede characteristic of every turbo row / drag stage, exactly as
    DragCompressor._run_once evaluates it (K = K0 - (K0 - 1) Q / (S p_in)), inverted for the throughput at given inlet
    and outlet pressures: p_out = A_c p_in - B_c Q with (A_c, B_c) composed stage by stage; plus the module's
    outlet-to-inlet leak C_L (p_out - p_in). The cascade mirror reproduces _run_once (p_out, P_el, mass, T) to 1e-12
    (test). Unlike DragCompressor.run, the inlet pressure is NOT fixed: it follows from the coupled node balance
    (F1-ID-04 / IFD-F3-05).
  * plenum: Reservoir physics (Reservoir.conductance, wall recombination with materials.DB gamma_O(T)); the feed
    valve plus the downstream path is one molecular orifice of orifice-equivalent area A_eq (Clausing factor 1 by
    definition), downstream pressure neglected (upper bound on the valve flow); the steady state reproduces
    Reservoir.steady_state at the same inflow (test).
  * domain (fail closed): every compressor stage outlet and the compressor inlet <= 0.1 Pa (F3 P-MOLECULAR-LIMIT,
    Chiggiato 2013 Sec. 4.1.2); every stage K in [1, K0] (the characteristic is defined only there; F3 R_CLIP);
    feed-orifice Knudsen number upper bound (atomic-O cross section TBD, omitted) >= 0.5 (F3 P-KN-FREE-MOLECULAR);
    compressor lumped temperature <= materials.DB T_max (F3 R_THERMAL). A plenum target above the compressor's
    admissible outlet is NOT_EVALUATED_OUT_OF_DOMAIN (A9.13 S6.8) and is never extrapolated.

Evidence discipline (CLAUDE.md rules 3, 4, 6, 10; docs/EVIDENCE.md; A9.7 F7 rule): MODE_STRICT refuses
(NOT_EVALUATED, blockers listed) while any input is TBD or an uncited code default. MODE_PARAMETRIC runs on the
labelled code defaults / parametric cases and labels every output PARAMETRIC_SENSITIVITY. The H-1 required inlet state
is TBD (F5 IFD-F4-01..05): it is a parametric requirement sweep and the output is a feasibility region, never a
chosen requirement. Searches return Pareto sets with every infeasible point kept with its reasons; nothing is a
winner, a selection or a PASS.

A9.13 owner decisions applied (A9.16 step 3 design layer; docs/decisions/OD_2026_10_01_A9_13_*, json sha256 9afaca45...;
the shared rules live in abep_sim/design/upstream_a9_13.py):
  * S6.8 / OQ-F3-03: every compressor / plenum result touching a pressure above 0.1 Pa is NOT_EVALUATED_OUT_OF_DOMAIN
    (``ST_OOD``); no flow / state is offered from it; the transitional candidate model is never consumed.
  * S6.10 / OQ-F4-01: ``scheduled_operation`` runs the orbit-state-scheduled plenum setpoint (BASELINE control mode,
    schedule on controller-available inputs only, never frozen) and ``compare_control_modes`` reports it next to the
    fixed setpoint (fallback / degraded mode and comparison reference).
  * S6.11 / OQ-F4-02: this module's <= 0.1 Pa high-conductance branch is the labelled sensitivity / fallback study; the
    higher-pressure compression path is the primary direction (NOT_EVALUATED_OUT_OF_DOMAIN until S6.8 closes).
  * S6.12 / OQ-F4-03: the transient metrics (2 % band, 60 s window, E0-E7, orbit modulation) are PROVISIONAL
    (``TRANSIENT_FRAMEWORK``); ``feed_quality`` compares them with measured H-1 tolerances, which govern when tighter.
  * S6.17 / OQ-F78-03: ripple is a hard feed-quality constraint, not a Pareto objective (``OBJECTIVES`` excludes it;
    the value is still reported as ``ripple_transfer_shaft``).
  * S6.5 / S6.19: the filter is a separate element (F2); 'none' (FC-00) is a reference bound only (``FilterCase.role``).
  * S6.21 / F9-OQ-02: ``R_FLOW`` belongs to the parametric requirement sweep only; no fixed mg/s flight gate.
  * S6.13 / OQ-F4-04 (NO_REQUIREMENT_RELAXATION): the flow gap is worked in the owner order (performance-derived H-1
    feed requirement first, PENDING_EVIDENCE; then capture / collection; then compressor / feed efficiency; then the
    scheduled setpoint, ``u13.flow_gap_record``); 0.38 mg/s is ground characterization only; a result over a subset of
    the required states (higher-density-only operation) is labelled SENSITIVITY_ONLY_NOT_BASELINE
    (``scheduled_operation`` / ``u13.state_coverage``) and never lowers the feed requirement.

A9.14 S9.8 OD3 / A9.13 S6.14 OQ-F4-05: the F1 records are evaluated at every required state of the frozen design-state
set v2 (plus the design-case reference point h200_f150 at index 0); every statewise reduction here is over that full
set. The set is a broad envelope (inclination / LTAN TBD, A9.21): results carry isy.ORBIT_BASIS_LABEL.
"""
from __future__ import annotations

import dataclasses
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import numpy as np

from ..compressor import DragCompressor
from ..constants import K_B, M_SPECIES, MU_EARTH, R_EARTH
from ..materials import DB
from ..reservoir import Reservoir
from . import compressor_synthesis as cs
from . import filter_stage as fs
from . import intake_synthesis as isy
from . import upstream_a9_13 as u13

SCHEMA = "f4_plenum_feed_v1"
VERSION = "1.0.0"
SPECIES = ("O", "N2", "O2")

MODE_STRICT = "strict"
MODE_PARAMETRIC = "parametric_sensitivity"
MODES = (MODE_STRICT, MODE_PARAMETRIC)
LABEL_PARAMETRIC = "PARAMETRIC_SENSITIVITY"

# ------------------------------------------------------------------------------------------------- statuses / reasons
ST_FEASIBLE = "FEASIBLE_UNDER_PARAMETRIC_SENSITIVITY_INPUTS"
ST_INFEASIBLE = "INFEASIBLE"
ST_OOD = u13.NOT_EVALUATED_OOD             # A9.13 S6.8: above 0.1 Pa nothing is evaluated (was INFEASIBLE_OUT_OF_DOMAIN)
ST_MODEL_ERROR = "MODEL_ERROR"
ST_NOT_EVALUATED = "NOT_EVALUATED"
FORBIDDEN_STATUS_WORDS = ("PASS", "SELECTED", "WINNER", "QUALIFIED", "OPTIMUM")

R_TARGET_ABOVE_DOMAIN = "PLENUM_TARGET_ABOVE_COMPRESSOR_ADMISSIBLE_OUTLET"          # OOD
R_STAGE_DOMAIN = "COMPRESSOR_STAGE_OR_INLET_PRESSURE_ABOVE_FREE_MOLECULAR_LIMIT"    # OOD
R_CHARACTERISTIC = "GAEDE_CHARACTERISTIC_OUTSIDE_K_1_TO_K0"                        # OOD
R_KN_FEED = "FEED_ORIFICE_KNUDSEN_UPPER_BOUND_BELOW_FREE_MOLECULAR_LIMIT"           # OOD
R_THERMAL = "COMPRESSOR_TEMPERATURE_ABOVE_MATERIAL_SERVICE_LIMIT"                  # infeasible
R_DEADHEAD = "TARGET_AT_OR_ABOVE_DEAD_HEAD_PRESSURE"                                # infeasible
R_FLOW = "DELIVERED_FLOW_BELOW_REQUIREMENT"     # parametric requirement sweep only (S6.21: no fixed mg/s flight gate)
R_UPSTREAM_F1 = "F1_INTAKE_INFEASIBLE_AT_STATE"                                     # infeasible (propagated)
R_NOT_SETTLED = "TRANSIENT_NOT_SETTLED_WITHIN_WINDOW"                               # infeasible (state not maintained)
R_SATURATED = "VALVE_SATURATED_SETPOINT_NOT_MAINTAINED"                             # infeasible (state not maintained)
R_TRAJ_DOMAIN = "TRAJECTORY_PLENUM_PRESSURE_ABOVE_DOMAIN"                           # OOD
R_INTEGRATOR = "INTEGRATOR_FAILED"                                                  # model error
R_CONSERVATION = "MASS_CONSERVATION_RESIDUAL_ABOVE_TOLERANCE"                       # model error
R_BISECTION = "ORIFICE_AREA_BISECTION_RESIDUAL_ABOVE_TOLERANCE_OR_BRACKET_SATURATED"  # model error (SW-06)
OOD_REASONS = (R_TARGET_ABOVE_DOMAIN, R_STAGE_DOMAIN, R_CHARACTERISTIC, R_KN_FEED, R_TRAJ_DOMAIN)
MODEL_ERROR_REASONS = (R_INTEGRATOR, R_CONSERVATION, R_BISECTION)
# R_BISECTION appended last so the existing REASON_BITS are unchanged
REASONS = (R_TARGET_ABOVE_DOMAIN, R_STAGE_DOMAIN, R_CHARACTERISTIC, R_KN_FEED, R_THERMAL, R_DEADHEAD, R_FLOW,
           R_UPSTREAM_F1, R_NOT_SETTLED, R_SATURATED, R_TRAJ_DOMAIN, R_INTEGRATOR, R_CONSERVATION, R_BISECTION)


def status_from_reasons(reasons) -> str:
    """MODEL_ERROR beats OUT_OF_DOMAIN beats INFEASIBLE; no reasons = feasible under parametric inputs."""
    if not reasons:
        return ST_FEASIBLE
    if any(r in MODEL_ERROR_REASONS for r in reasons):
        return ST_MODEL_ERROR
    if any(r in OOD_REASONS for r in reasons):
        return ST_OOD
    return ST_INFEASIBLE


# ----------------------------------------------------------------------------------------------- cited / labelled values
P_DOMAIN_PA = cs.P_MOLECULAR_LIMIT_PA            # 0.1 Pa (F3 P-MOLECULAR-LIMIT, Chiggiato 2013 Sec. 4.1.2)
KN_MIN = cs.KN_FREE_MOLECULAR_MIN                # 0.5 (F3 P-KN-FREE-MOLECULAR, Chiggiato 2013 Table 7)
SIGMA_C_M2 = dict(cs.SIGMA_C_M2)                 # N2, O2 (Chiggiato Table 6); O TBD
K_TOL = 1e-9                                     # relative tolerance on the [1, K0] characteristic bounds (numerics)
SETTLE_BAND = 0.02                               # metric definition (not a requirement)
RTOL = 1e-5                                      # solve_ivp relative tolerance (convergence vs 1e-8 reported by the study)
RTOL_REFERENCE = 1e-8                            # tighter tolerance of the numerical-convergence check
ATOL_SCALED = 1e-11                              # solve_ivp absolute tolerance on the scaled states
MASS_TOL = 1e-6                                  # |mass residual| / throughput (CLAUDE.md rule 4 gate for F4)
BISECT_ITERS = 90                                # log-area bisection steps (relative bracket width < 1e-12)
A_EQ_BRACKET_M2 = (1e-12, 1e2)                   # orifice-equivalent area search bracket (residual reported)
BISECT_RTOL = 1e-6                               # gate on the bisection residual |p/target - 1| (numerics, SW-06)
INTEGRATOR_METHOD = "LSODA"                      # stiff-safe (automatic stiff BDF switching; scipy solve_ivp)
INTEGRATOR_REFERENCE = "BDF"                     # independent stiff method of the convergence check

QUASI_STEADY_NOTE = ("the compressor-inlet node (between the intake/filter exit and the first rotor row) is solved "
                     "algebraically at every instant (its volume is TBD; it is quasi-steady when V_inlet / (e + alpha) "
                     "<< the plenum time constant; the inlet-node time constant per m^3 of inlet volume is reported)")

REFERENCES = {
    "SRC-F1": {"path": "docs/design_synthesis/f1_intake/f1_intake_synthesis_v1.json",
               "use": "if_a1_interface.records_per_unit_area (IF-A1 per species: mdot_fwd, p_passive, T, K_back), "
                      "infeasible_reasons (C-DRAG-RFP per state), coverage_rule (orbit states, scenarios)"},
    "SRC-F2": {"path": "abep_sim/design/filter_stage.py",
               "use": "FilterStage.none / FilterStage.tbd + SensitivityCase; apply() forward fractions and "
                      "backflow_coupling() backflow fractions"},
    "SRC-F3": {"path": "docs/design_synthesis/f3_compressor/f3_compressor_synthesis_v1.json; "
                       "docs/design_synthesis/f3_compressor/f3_compressor_designs_v1.json",
               "use": "union of the per-case Pareto ids (the compressor set) and the design grid records"},
    "SRC-F5": {"path": "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json",
               "use": "interface demands IFD-F4-01..07, IFS-F4-01..03 (H-1 inlet demand TBD; ground characterization "
                      "range 0.38-3.2 mg/s owner row 73)"},
    "SRC-H23": {"path": "docs/hardware/h2/h2_3_gas_path_plenum/h2_3_gas_path_plenum_v1.json",
                "use": "H23-02 delivered-flow range, H23-06 IF-A5 pressure analog, H23-17 compressor ripple TBD, "
                       "H23-18 valve bandwidth TBD (0.1/1/10 Hz evaluated there), H23-07 valve authority r = 1..3"},
    "SRC-CHIGGIATO2013": dict(cs.SOURCES["SRC-CHIGGIATO2013"]),
    "SRC-RESERVOIR-PY": {"path": "abep_sim/reservoir.py",
                         "use": "Reservoir.conductance (K A cbar / 4), wall recombination, leak path; "
                                "size_orifice_for_pressure (cross-check); code defaults uncited"},
    "SRC-COMPRESSOR-PY": {"path": "abep_sim/compressor.py", "use": "DragCompressor characteristic, power, mass, T"},
    "SRC-MATERIALS-PY": {"path": "abep_sim/materials.py", "use": "gamma_O(T), T_max_K (literature-class priors, uncited)"},
    "SRC-CONSTANTS-PY": {"path": "abep_sim/constants.py", "use": "K_B, M_SPECIES, MU_EARTH, R_EARTH"},
}


def _p(pid, value, units, basis, source, evidence_class, status, **extra):
    d = {"id": pid, "value": value, "units": units, "basis": basis, "source": source,
         "evidence_class": evidence_class, "status": status}
    d.update(extra)
    return d


RES_DEFAULTS = {f.name: f.default for f in dataclasses.fields(Reservoir)}
T_CHAIN_K = 350.0          # checked against every F1 record (load_f1_records refuses otherwise)


def parameter_registry() -> list[dict]:
    """Every input of the F4 model: value or TBD, units, basis, source, evidence class, status."""
    g_ti = DB["Ti6Al4V"].gamma_O(T_CHAIN_K)
    return [
        _p("F4-P-01", T_CHAIN_K, "K", "single chain gas temperature: F1 IF-A1 T_K (= intake_tpmc IntakeGeometry.T_wall_K "
           "code default); used for the compressor T_gas, the plenum and the offered feed T (isothermal chain)",
           "SRC-F1 if_a1 T_K", "assumed", "ASSUMED_ISOTHERMAL_CHAIN (TBD: H2-5 thermal network; ICD G-07)"),
        _p("F4-P-02", P_DOMAIN_PA, "Pa", "admissible pressure of every compressor stage outlet and inlet (free-molecular "
           "Gaede characteristic domain); the plenum target cap", "SRC-CHIGGIATO2013 Sec. 4.1.2 via F3 "
           "P-MOLECULAR-LIMIT", "inferred", "CITED (F3)"),
        _p("F4-P-03", KN_MIN, "-", "minimum Knudsen number for the molecular orifice law at the feed valve "
           "(Kn = lambda / D_eq, D_eq = sqrt(4 A_eq / pi))", "SRC-CHIGGIATO2013 Table 7 via F3 P-KN-FREE-MOLECULAR",
           "inferred", "CITED (F3)"),
        _p("F4-P-04", dict(SIGMA_C_M2), "m^2", "N2 / O2 collision cross sections for lambda (O omitted: Kn is an upper "
           "bound, the check is necessary, not sufficient)", "SRC-CHIGGIATO2013 Table 6 via F3 P-SIGMA-C-N2/O2",
           "inferred", "CITED (F3); P-SIGMA-C-O TBD"),
        _p("F4-P-05", "TBD", "m^2", "external plenum leak area (to space)", "none", "TBD", "TBD",
           parametric_case_value=RES_DEFAULTS["leak_area_m2"],
           parametric_case_source="abep_sim/reservoir.py Reservoir.leak_area_m2 code default (uncited)"),
        _p("F4-P-06", "TBD", "-", "plenum wall O recombination probability gamma (H2-3 H23-22, owner GP-D03)", "none",
           "TBD", "TBD", parametric_cases={"WALL-G0": 0.0, "WALL-TI64-DB": g_ti},
           parametric_case_source="WALL-G0: definitional non-catalytic bound; WALL-TI64-DB: materials.DB['Ti6Al4V']."
                                  "gamma_O(350 K) (literature-class prior, uncited)"),
        _p("F4-P-07", "TBD", "-", "plenum geometry for the wall area: right circular cylinder L = D (A_w = 6 pi r^2, "
           "V = 2 pi r^3); shape TBD (H2-7 envelope)", "geometric convention", "assumed", "PARAMETRIC_CONVENTION"),
        _p("F4-P-08", "TBD", "Hz", "metering-valve actuator bandwidth f_v (first-order lag tau_v = 1/(2 pi f_v))",
           "SRC-H23 H23-18 (TBD; evaluated at 0.1 / 1 / 10 Hz there, assumed)", "TBD", "TBD",
           parametric_cases=[0.1, 1.0, 10.0], nominal_parametric=1.0),
        _p("F4-P-09", "TBD", "-", "valve authority r = A_eq,max / A_eq at the design operating point", "SRC-H23 H23-07 "
           "(valve authority r = 1..3, assumed there)", "TBD", "TBD", parametric_case_value=3.0),
        _p("F4-P-10", "TBD", "mixed", "H-1 required inlet state (mdot_s, P, T, x_s, transient tolerances)",
           "SRC-F5 IFD-F4-01..05 (TBD)", "TBD", "TBD (parametric requirement sweep, see requirement_sweep)"),
        _p("F4-P-11", "TBD", "-", "orbit-scale modulation of the free-stream density along one revolution: the F1 "
           "states are points of the orbit-resolved design-state set v2 (local time, latitude, season and solar "
           "activity extrema), but the revolution through them needs the inclination / LTAN, which are TBD (A9.21; no "
           "code default as mission truth), so no amplitude is derived from the dataset (A9.13 S6.14: no invented "
           "amplitude); the parametric sinusoid stays a labelled sensitivity", "SRC-F1 coverage_rule", "TBD", "TBD",
           parametric_case_value=0.2),
        _p("F4-P-12", SETTLE_BAND, "-", "settling / recovery band (metric definition, not a requirement)", "definition",
           "definition", "DEFINITION"),
        _p("F4-P-13", {"method": INTEGRATOR_METHOD, "rtol": RTOL, "reference_method": INTEGRATOR_REFERENCE,
                       "rtol_convergence_reference": RTOL_REFERENCE,
                       "atol_scaled": ATOL_SCALED}, "-",
           "scipy.integrate.solve_ivp, stiff-safe LSODA (automatic stiff BDF switching) with analytic Jacobian, "
           "restarted at every event; a sample is re-run with BDF at the reference tolerance (numerical_convergence)",
           "definition", "definition", "DEFINITION"),
        _p("F4-P-14", MASS_TOL, "-", "mass-conservation gate: |m(t) - m(0) - (integrated in - out)| / integrated "
           "throughput (CLAUDE.md rule 4)", "definition", "definition", "DEFINITION"),
        _p("F4-P-15", "derived", "s", "orbital period T = 2 pi sqrt((R_E + h)^3 / mu) at the state altitude (circular "
           "Kepler orbit)", "SRC-CONSTANTS-PY MU_EARTH, R_EARTH", "model-derived", "DERIVED"),
        _p("F4-P-16", "TBD", "kg", "plenum mass (wall thickness, material, ports): TBD; volume V and wall area A_w are "
           "the mass proxies (monotone for any positive wall areal mass)", "none", "TBD", "TBD"),
        _p("F4-P-17", "TBD", "Hz / -", "compressor outlet ripple frequency and amplitude (H23-17 TBD); the shaft "
           "frequency rpm/60 of the F3 design is used as the LOWEST possible ripple frequency (blade passing = blades "
           "x rpm/60 >= rpm/60), so the reported plenum ripple transfer is an upper bound", "SRC-H23 H23-17; F3 design",
           "model-derived", "TBD amplitude; frequency bound DERIVED"),
        _p("F4-P-18", "TBD", "m^3", "compressor-inlet node volume (quasi-steady assumption, see quasi_steady_note)",
           "none", "TBD", "TBD"),
    ]


def orbital_period_s(alt_km: float) -> float:
    a = R_EARTH + alt_km * 1e3
    return 2.0 * math.pi * math.sqrt(a ** 3 / MU_EARTH)


def cbar(species: str, T_K: float) -> float:
    return fs.mean_speed_m_s(species, T_K)


def kT_over_m(species: str, T_K: float) -> float:
    return K_B * T_K / M_SPECIES[species]


# =================================================================================================== intake records
@dataclass(frozen=True)
class IntakeState:
    """F1 IF-A1 record scaled to an intake area, as throughput-unit coefficients of the F1 net-flow law."""
    candidate: str              # d-collapsed F1 candidate id A{A}_Ld{L}_phi{phi}
    area_m2: float
    state: str
    scenario: str
    T_K: float
    mdot_fwd_kgps: Mapping[str, float]
    p_passive_Pa: Mapping[str, float]
    K_back: Mapping[str, float]
    f1_status: str              # FEASIBLE_AT_STATE or the F1 reason
    source: str

    @property
    def alt_km(self) -> float:
        return isy.state_alt_km(self.state)

    def q_fwd(self) -> dict:
        return {s: self.mdot_fwd_kgps[s] / M_SPECIES[s] * K_B * self.T_K for s in SPECIES}

    def e_f1(self) -> dict:
        """F1 escape conductance [m^3/s]: back = mdot_fwd p / p_passive -> e = q_fwd / p_passive."""
        q = self.q_fwd()
        return {s: q[s] / self.p_passive_Pa[s] for s in SPECIES}

    def escape_probability(self) -> dict:
        """a_s = e_s / (A cbar_s / 4) (= phi K_back,s by the F1 CR_passive definition)."""
        e = self.e_f1()
        return {s: e[s] / (self.area_m2 * cbar(s, self.T_K) / 4.0) for s in SPECIES}


def f1_candidate_id(area_m2: float, L_over_d: float, phi: float) -> str:
    return f"A{area_m2:g}_Ld{L_over_d:g}_phi{phi:g}"


def load_f1(repo: Path) -> dict:
    """The F1 deliverable as its consumers read it: the committed compact core view, expanded to the deliverable's
    layout (A9.22 item 9; the 36.7 MB full output is an evidence archive; values identical, intake_synthesis)."""
    return isy.load_f1_view(repo)


_F1_STATE_REASON = re.compile(r"(?:C-DRAG-RFP|MODEL_ERROR) at (\S+?)(?=: |$)")


def f1_state_infeasibility(f1: dict) -> dict:
    """{(scenario, d-collapsed candidate id): {state: reason}} from F1 envelope infeasible_reasons (C-DRAG-RFP /
    MODEL_ERROR at a state). The state id is the text between 'at ' and ': ' (design-state ids contain ':' but no
    space); every id must be an evaluated F1 state (fail closed)."""
    known = set(f1["coverage_rule"]["orbit_states"])
    out: dict = {}
    for sc, cands in f1["infeasible_reasons"]["envelope"].items():
        for cid, reasons in cands.items():
            m = re.match(r"A([\d.]+)_d[\d.]+_Ld([\d.]+)_phi([\d.]+)$", cid)
            key = (sc, f1_candidate_id(float(m.group(1)), float(m.group(2)), float(m.group(3))))
            for r in reasons:
                for st in _F1_STATE_REASON.findall(r):
                    if st not in known:
                        raise RuntimeError(f"F1 reason names an unknown state {st!r}: {r!r}")
                    prev = out.setdefault(key, {}).get(st)
                    if prev is not None and prev != r:
                        raise RuntimeError(f"F1 d-collapse inconsistent for {key} at {st}: {prev!r} vs {r!r}")
                    out[key][st] = r
    return out


def load_f1_records(f1: dict, areas_m2, scenarios=None, states=None) -> list[IntakeState]:
    """IntakeState for every F1 unit-area record x area (d-invariant per F1-02), with the F1 per-state feasibility."""
    infeas = f1_state_infeasibility(f1)
    out = []
    for r in f1["if_a1_interface"]["records_per_unit_area"]:
        if scenarios is not None and r["scenario"] not in scenarios:
            continue
        if states is not None and r["state"] not in states:
            continue
        if not r["converged"] or r["theta_deg"] != 0.0:
            raise RuntimeError(f"F1 record {r['candidate']} {r['state']} is not converged / not theta 0")
        m = re.match(r"unit_area_Ld([\d.]+)_phi([\d.]+)$", r["candidate"])
        Ld, phi = float(m.group(1)), float(m.group(2))
        for a in areas_m2:
            if abs(r["T_K"] - T_CHAIN_K) > 1e-9:
                raise RuntimeError("F1 record temperature differs from the F4 chain temperature")
            cid = f1_candidate_id(a, Ld, phi)
            f1s = infeas.get((r["scenario"], cid), {}).get(r["state"], "FEASIBLE_AT_STATE")
            out.append(IntakeState(
                candidate=cid, area_m2=float(a), state=r["state"], scenario=r["scenario"], T_K=float(r["T_K"]),
                mdot_fwd_kgps={s: r["species"][s]["mdot_fwd_kgps"] * a for s in SPECIES},
                p_passive_Pa={s: r["species"][s]["p_passive_Pa"] for s in SPECIES},
                K_back={s: r["species"][s]["K_back"] for s in SPECIES}, f1_status=f1s,
                source=f"SRC-F1 if_a1_interface.records_per_unit_area[{r['candidate']}/{r['state']}/{r['scenario']}]"
                       f" x A = {a:g} m^2"))
    return out


# =================================================================================================== filter cases
@dataclass(frozen=True)
class FilterCase:
    """Per-species fractions of the F2 stage used by the gap-reflection series model."""
    case_id: str
    label: str
    stage_id: str
    t_f: Mapping[str, float]     # forward transmission (declared forward incidence)
    r_f: Mapping[str, float]     # forward reflection
    t_b: Mapping[str, float]     # backflow transmission (diffuse, from the compressor side)
    r_b: Mapping[str, float]     # backflow reflection
    t_u: Mapping[str, float]     # diffuse transmission from the intake side (reciprocity: = t_b, loss-free)
    r_u: Mapping[str, float]
    areal_mass_kg_m2: float | None
    overrides: tuple = ()
    note: str = ""
    role: str = fs.ROLE_BASELINE          # A9.13: FC-00 'none' carries fs.ROLE_REFERENCE_BOUND (reference only)

    @property
    def reference_bound_only(self) -> bool:
        return self.role == fs.ROLE_REFERENCE_BOUND

    def coefficients(self, a: Mapping[str, float]) -> tuple[dict, dict]:
        """(D_s, E_s): delivered fraction of the forward ram flow and net backflow factor per incident molecule."""
        D, E = {}, {}
        for s in SPECIES:
            den = 1.0 - (1.0 - a[s]) * self.r_u[s]
            D[s] = self.t_f[s] + self.t_u[s] * (1.0 - a[s]) * self.r_f[s] / den
            E[s] = self.r_b[s] + self.t_u[s] * (1.0 - a[s]) * self.t_b[s] / den - 1.0
        return D, E


def _unit_inlet() -> fs.InletState:
    one = {s: 1.0 for s in SPECIES}
    return fs.InletState(mdot_forward_kgps=one, mdot_back_incident_kgps=dict(one),
                         back_incident_basis="normalized unit back-incident flow (fractions only)", T_gas_K=T_CHAIN_K,
                         incidence="diffuse_thermal", knudsen_number=None, label="NORMALIZED_UNIT_INPUT",
                         provenance="F4 fraction extraction (NORMALIZED_UNIT_INPUT)")


def filter_case_from_stage(case_id: str, stage: fs.FilterStage, case: fs.SensitivityCase | None, note: str = ""
                           ) -> FilterCase:
    """Extract the F2 fractions through F2's public API (apply() forward, backflow_coupling() backflow). Refuses when
    F2 refuses (a TBD stage without a sensitivity case never yields numbers)."""
    res = stage.apply(_unit_inlet(), case)
    if not res.numeric:
        raise fs.FilterStageError(f"F2 refused ({res.status}): {res.missing}")
    bc = stage.backflow_coupling(T_CHAIN_K, case)
    if bc["status"] != "NUMERIC":
        raise fs.FilterStageError(f"F2 backflow coupling refused: {bc}")
    t_f = {s: res.species[s]["fractions_forward"]["transmitted"] for s in SPECIES}
    r_f = {s: res.species[s]["fractions_forward"]["reflected"] for s in SPECIES}
    t_b = {s: bc["species"][s]["to_upstream"] for s in SPECIES}
    r_b = {s: bc["species"][s]["reflected_to_plenum"] for s in SPECIES}
    for s in SPECIES:
        if res.species[s]["fractions_forward"]["captured"] or res.species[s]["fractions_forward"]["converted"] or \
                bc["species"][s]["captured"] or bc["species"][s]["converted"]:
            raise fs.FilterStageError("F4 gap model carries loss-free filter cases only (capture / conversion TBD)")
    areal = None if stage.kind == "none" else (case.overrides.get("areal_mass_kg_m2") if case else None)
    return FilterCase(case_id=case_id, label=res.label, stage_id=stage.stage_id, t_f=t_f, r_f=r_f, t_b=t_b, r_b=r_b,
                      t_u=dict(t_b), r_u=dict(r_b), areal_mass_kg_m2=areal,
                      overrides=tuple(sorted((o["parameter"], o["value"]) for o in res.overrides_used)), note=note,
                      role=stage.role)


def filter_none() -> FilterCase:
    return filter_case_from_stage("F4-FIL-NONE", fs.FilterStage.none(), None,
                                  note="F2 'none' definitional identity: FC-00 REFERENCE BOUND only, never an admissible "
                                       "flight architecture (A9.13 S6.5)")


def filter_parametric(tau: float) -> FilterCase:
    """Species-independent loss-free element with transmission tau both ways (diffuse incidence, reciprocity)."""
    stage = fs.FilterStage.tbd(f"F4-PARAM-T{tau:g}", "FC-PARAMETRIC", forward_incidence="diffuse_thermal",
                               description="F4 parametric loss-free screen")
    ov = {"face_area_m2": 1.0, "areal_mass_kg_m2": 1.0}
    for s in SPECIES:
        ov.update({f"tau_f.{s}": tau, f"tau_b.{s}": tau, f"alpha_conductance.{s}": tau,
                   f"capture_f.{s}": 0.0, f"capture_b.{s}": 0.0, f"conversion_f.{s}": 0.0, f"conversion_b.{s}": 0.0})
    case = fs.SensitivityCase(case_id=f"SC-F4-T{tau:g}", label=f"PARAMETRIC_SENSITIVITY (F4 loss-free screen tau={tau:g})",
                              overrides=ov, regime_assumption="free_molecular",
                              rationale="F4 bounding case: filter transmission TBD (F2); face area / areal mass "
                                        "placeholders 1 (not used by F4 except as a label)")
    fc = filter_case_from_stage(f"F4-FIL-T{tau:g}", stage, case,
                                note="PARAMETRIC_SENSITIVITY: loss-free, species-independent, reciprocal (t_u = t_b)")
    return dataclasses.replace(fc, areal_mass_kg_m2=None)


def filter_placeholder() -> FilterCase:
    stage = fs.FilterStage.tbd("F4-PLACEHOLDER", "FC-REPO-PLACEHOLDER", forward_incidence="diffuse_thermal",
                               description="repository placeholder filter law")
    fc = filter_case_from_stage("F4-FIL-PLACEHOLDER", stage, fs.placeholder_sensitivity_case(stage),
                                note="PLACEHOLDER_NOT_A_FLIGHT_DESIGN via F2 placeholder_sensitivity_case; diffuse "
                                     "intake-side transmission taken = tau_b (reciprocity assumption)")
    return fc


def filter_cases(taus=(0.9, 0.7, 0.5)) -> list[FilterCase]:
    """Every F4 filter case: FC-00 'none' (REFERENCE BOUND only, A9.13 S6.5) plus the inert loss-free parametric
    screens and the repository placeholder (both baseline-role PARAMETRIC_SENSITIVITY cases)."""
    return [filter_none()] + [filter_parametric(t) for t in taus] + [filter_placeholder()]


def element_filter_cases(taus=(0.9, 0.7, 0.5)) -> list[FilterCase]:
    """The filter cases that model an actual element between IF-A1 and IF-A2 (FC-00 excluded: reference bound only)."""
    return [f for f in filter_cases(taus) if not f.reference_bound_only]


# =================================================================================================== compressor plant
@dataclass(frozen=True)
class CompressorPlant:
    design_id: str
    design: Mapping
    comp: DragCompressor = field(compare=False, repr=False)

    @classmethod
    def from_design(cls, design: Mapping, T_K: float = T_CHAIN_K) -> "CompressorPlant":
        cs.validate_design(design)
        kw = cs.module_defaults()
        kw.update({"turbo_rows": int(design["N_turbo"]), "turbo_area_m2": float(design["A_turbo_m2"]),
                   "turbo_radius_m": float(design.get("R_turbo_m", cs.r_turbo_from_area(float(design["A_turbo_m2"])))),
                   "n_stages": int(design["N_drag"]), "rpm": float(design["rpm"]),
                   "rotor_material": design["rotor_material"], "T_gas_K": float(T_K)})
        return cls(design_id=str(design["id"]), design=dict(design), comp=DragCompressor(**kw))

    def stages(self) -> list[dict]:
        """[{kind, K0: {s}, S}] in flow order, exactly as DragCompressor._run_once builds them."""
        c = self.comp
        u_t = c.turbo_radius_m * c.rpm * 2 * math.pi / 60.0
        S_t = c.turbo_kS * u_t * c.turbo_area_m2
        u = c.u
        h, w, L = c.h_mm * 1e-3, c.w_mm * 1e-3, c.L_per_stage_m
        S0 = c.xi * u * h * w / 2.0
        out = []
        for _ in range(c.turbo_rows):
            out.append({"kind": "turbo", "S": S_t, "u": u_t, "A_term": c.turbo_area_m2 * c.turbo_blade_area_frac * 2,
                        "K0": {s: math.exp(c.turbo_kK * u_t / c._cbar(M_SPECIES[s])) for s in SPECIES}})
        for _ in range(c.n_stages):
            out.append({"kind": "drag", "S": S0, "u": u, "A_term": 2 * L * w,
                        "K0": {s: math.exp(2 * u * L / (c._cbar(M_SPECIES[s]) * h) * c.xi) for s in SPECIES}})
        return out

    def characteristic(self) -> dict:
        """Per species (A_c, B_c): p_out = A_c p_in - B_c Q for the whole cascade (Q in Pa m^3/s, constant through
        the machine); composed stage by stage from p_{i+1} = K0 p_i - Q (K0 - 1) / S."""
        out = {}
        for s in SPECIES:
            A, B = 1.0, 0.0
            for st in self.stages():
                K0 = st["K0"][s]
                A, B = K0 * A, K0 * B + (K0 - 1.0) / st["S"]
            out[s] = (A, B)
        return out

    @property
    def leak_m3_s(self) -> float:
        return self.comp.leak_conductance_m3_s

    @property
    def shaft_hz(self) -> float:
        return self.comp.rpm / 60.0

    def cascade(self, p_in: Mapping[str, float], Q: Mapping[str, float]) -> dict:
        """Forward mirror of DragCompressor._run_once at given per-species inlet partial pressures and throughputs
        (no clipping: the unclipped K is returned for the domain gate). Power, mass and temperature use the module's
        expressions verbatim."""
        c = self.comp
        p = {s: float(p_in[s]) for s in SPECIES}
        P_gas = 0.0
        k_min_rel, k_max_rel, p_stage_max = math.inf, -math.inf, sum(p.values())
        for st in self.stages():
            for s in SPECIES:
                K0 = st["K0"][s]
                cb = c._cbar(M_SPECIES[s])
                K = K0 - (K0 - 1.0) * Q[s] / max(st["S"] * p[s], 1e-30)
                k_min_rel = min(k_min_rel, K)                       # must be >= 1
                k_max_rel = max(k_max_rel, K / K0)                  # must be <= 1
                p_mean = 0.5 * p[s] * (1 + K)
                P_gas += p_mean * (st["u"] / cb) * st["A_term"] * (2 / math.sqrt(math.pi)) * st["u"]
                p[s] *= K
            p_stage_max = max(p_stage_max, sum(p.values()))
        omega = c.rpm * 2 * math.pi / 60.0
        P_bear = c.k_bear_W_per_rads * omega
        P_el = (P_gas + P_bear) / c.eta_motor + c.P_ctrl_W
        torque = (P_gas + P_bear) / omega
        rm = DB[c.rotor_material]
        m_rotor = (math.pi * c.rotor_radius_m ** 2 * c.rotor_disc_thickness_m * rm.density * c.n_stages * 0.7
                   + c.turbo_area_m2 * c.turbo_disc_thickness_m * rm.density * c.turbo_rows * c.turbo_blade_area_frac
                   + 0.15 * c.turbo_rows)
        m_motor = c.motor_kg_per_Nm * max(torque, 0.01) + 0.25
        mass = m_rotor * (1 + c.stator_mass_factor) + m_motor + c.bearing_kg
        T = c.T_sink_K + (P_gas + P_bear * 0.5 + P_el - (P_gas + P_bear)) / c.conductance_to_sink_W_K
        return {"p_out": p, "p_out_total": sum(p.values()), "K_min": k_min_rel, "K_over_K0_max": k_max_rel,
                "p_stage_max": p_stage_max, "P_gas_W": P_gas, "P_bear_W": P_bear, "P_el_W": P_el,
                "torque_Nm": torque, "mass_kg": mass, "T_comp_K": T}


# =================================================================================================== plenum
@dataclass(frozen=True)
class Plenum:
    volume_m3: float
    gamma_wall: float                 # O recombination probability (parametric case)
    wall_case: str
    leak_area_m2: float               # parametric case value (Reservoir code default)
    T_K: float = T_CHAIN_K

    def __post_init__(self):
        """Refuse a malformed plenum (SW-06): V > 0, 0 <= gamma <= 1, leak >= 0, T > 0, all finite."""
        def _f(name, v):
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
                raise ValueError(f"Plenum.{name}={v!r} must be a finite number")
            return float(v)
        if not _f("volume_m3", self.volume_m3) > 0.0:
            raise ValueError("Plenum.volume_m3 must be > 0")
        if not 0.0 <= _f("gamma_wall", self.gamma_wall) <= 1.0:
            raise ValueError("Plenum.gamma_wall must be in [0, 1]")
        if not _f("leak_area_m2", self.leak_area_m2) >= 0.0:
            raise ValueError("Plenum.leak_area_m2 must be >= 0")
        if not _f("T_K", self.T_K) > 0.0:
            raise ValueError("Plenum.T_K must be > 0")

    @property
    def wall_area_m2(self) -> float:
        r = (self.volume_m3 / (2.0 * math.pi)) ** (1.0 / 3.0)
        return 6.0 * math.pi * r * r

    def reservoir(self, a_eq_m2: float = 1e-6) -> Reservoir:
        """A Reservoir with this plenum's geometry, feed orifice A_eq (K = 1), leak, T; upstream_collisions = 0 (no
        compressor-internal recombination: DragCompressor carries none). wall_material only feeds gamma: when the
        parametric gamma is not the DB value, Reservoir.steady_state cannot represent it (cross-check skipped)."""
        return Reservoir(volume_m3=self.volume_m3, wall_area_m2=self.wall_area_m2, wall_material="Ti6Al4V",
                         T_K=self.T_K, anode_orifice_area_m2=a_eq_m2, anode_orifice_K=1.0,
                         leak_area_m2=self.leak_area_m2, upstream_collisions=0.0, upstream_material="Ti6Al4V")

    def k_rec_m3_s(self) -> float:
        """Reservoir wall recombination: O atom loss rate = gamma (cbar_O / 4) A_w n_O (throughput units: x p_O)."""
        return self.gamma_wall * cbar("O", self.T_K) / 4.0 * self.wall_area_m2

    def leak_m3_s(self, s: str) -> float:
        return self.reservoir().conductance(s, self.leak_area_m2)

    def feed_c(self, s: str) -> float:
        """Feed conductance per unit orifice-equivalent area [m^3/s per m^2] (Reservoir.conductance, K = 1)."""
        return self.reservoir().conductance(s, 1.0, 1.0)


# =================================================================================================== chain (steady)
@dataclass(frozen=True)
class Chain:
    """One intake state x filter case x compressor x plenum: linear free-molecular network coefficients."""
    intake: IntakeState
    filt: FilterCase
    plant: CompressorPlant
    plenum: Plenum

    def node_coefficients(self, density_factor: float = 1.0) -> dict:
        """Per species: f [Pa m^3/s], e [m^3/s], alpha, beta [m^3/s], A_c, B_c. density_factor scales the free-stream
        density (F1 law: mdot_fwd and p_passive both proportional to n_inf, so f scales and e does not)."""
        a = self.intake.escape_probability()
        D, E = self.filt.coefficients(a)
        q = self.intake.q_fwd()
        ch = self.plant.characteristic()
        CL = self.plant.leak_m3_s
        out = {}
        for s in SPECIES:
            A, B = ch[s]
            out[s] = {"f": q[s] * D[s] * density_factor,
                      "e": -E[s] * self.intake.area_m2 * cbar(s, self.intake.T_K) / 4.0,
                      "alpha": A / B + CL, "beta": 1.0 / B + CL, "A_c": A, "B_c": B, "D": D[s], "E": E[s], "a": a[s]}
        return out


def solve_pressures(co: Mapping, a_eq, k_rec: float, leak: Mapping, feed_c: Mapping):
    """Steady per-species plenum (p3) and compressor-inlet (p2) partial pressures for orifice-equivalent area a_eq
    (scalar or numpy array). Closed form of the linear network; O -> O2 recombination is triangular (O first)."""
    a_eq = np.asarray(a_eq, dtype=float)
    p3, p2 = {}, {}
    for s in ("O", "N2", "O2"):
        c = co[s]
        den_n = c["e"] + c["alpha"]
        q0 = c["alpha"] * c["f"] / den_n
        k = c["e"] * c["beta"] / den_n
        g = feed_c[s] * a_eq + leak[s]
        if s == "O":
            p3[s] = q0 / (k + g + k_rec)
        elif s == "O2":
            p3[s] = (q0 + k_rec * p3["O"] * M_SPECIES["O"] / M_SPECIES["O2"]) / (k + g)
        else:
            p3[s] = q0 / (k + g)
        p2[s] = (c["f"] + c["beta"] * p3[s]) / den_n
    return p3, p2


def area_for_pressure(co, target_Pa, k_rec, leak, feed_c):
    """Orifice-equivalent area holding the plenum at target (vectorized log bisection; p3_total is strictly
    decreasing in a_eq). Returns (a_eq, p_deadhead, residual_rel, ok) where ok = target strictly below dead-head.
    A non-finite or non-positive target is refused (ValueError). Callers gate the residual with bisection_failed()."""
    target = np.asarray(target_Pa, dtype=float)
    if not np.all(np.isfinite(target)) or np.any(target <= 0.0):
        raise ValueError("plenum target pressure must be finite and > 0")
    p_dead = sum(solve_pressures(co, 0.0, k_rec, leak, feed_c)[0].values())
    p_dead = np.broadcast_to(np.asarray(p_dead, dtype=float), np.broadcast_shapes(np.shape(p_dead), target.shape))
    ok = target < p_dead
    lo = np.full(p_dead.shape, math.log(A_EQ_BRACKET_M2[0]))
    hi = np.full(p_dead.shape, math.log(A_EQ_BRACKET_M2[1]))
    for _ in range(BISECT_ITERS):
        mid = 0.5 * (lo + hi)
        p = sum(solve_pressures(co, np.exp(mid), k_rec, leak, feed_c)[0].values())
        above = p > target
        lo = np.where(above, mid, lo)
        hi = np.where(above, hi, mid)
    a = np.exp(0.5 * (lo + hi))
    p = sum(solve_pressures(co, a, k_rec, leak, feed_c)[0].values())
    resid = np.abs(p / np.where(target > 0, target, 1.0) - 1.0)
    return a, p_dead, resid, ok


def bisection_failed(a_eq, resid):
    """True where the orifice-area bisection did not converge to BISECT_RTOL or saturated at the search bracket
    (fail closed: no operating point is offered from such a solution, SW-06)."""
    a_eq = np.asarray(a_eq, dtype=float)
    resid = np.asarray(resid, dtype=float)
    sat = (a_eq >= A_EQ_BRACKET_M2[1] * (1.0 - 1e-9)) | (a_eq <= A_EQ_BRACKET_M2[0] * (1.0 + 1e-9))
    return ~(resid <= BISECT_RTOL) | sat


def lambda_upper_m(p3: Mapping[str, float], T_K: float) -> float:
    denom = sum(p3[s] / (K_B * T_K) * SIGMA_C_M2[s] for s in SIGMA_C_M2)
    return math.inf if denom <= 0 else 1.0 / (math.sqrt(2.0) * denom)


def steady_operating_point(chain: Chain, target_Pa: float, density_factor: float = 1.0, feed_factor: float = 1.0
                           ) -> dict:
    """Fully gated steady state with the plenum held at target_Pa (pressure regulation). Returns the record offered
    to H-1 (mdot_s, P, T, x_s) plus the domain / feasibility reasons. Never returns flows for a target above the
    compressor's admissible outlet (NOT_EVALUATED_OUT_OF_DOMAIN, A9.13 S6.8)."""
    reasons = []
    if chain.intake.f1_status != "FEASIBLE_AT_STATE":
        reasons.append(R_UPSTREAM_F1)
    if target_Pa > P_DOMAIN_PA:
        reasons.append(R_TARGET_ABOVE_DOMAIN)
        return {"status": status_from_reasons(reasons), "reasons": reasons, "target_Pa": target_Pa,
                "offered": None}
    co = chain.node_coefficients(density_factor)
    pl = chain.plenum
    leak = {s: pl.leak_m3_s(s) for s in SPECIES}
    fc = {s: pl.feed_c(s) * feed_factor for s in SPECIES}
    k_rec = pl.k_rec_m3_s()
    a, p_dead, resid, ok = area_for_pressure(co, target_Pa, k_rec, leak, fc)
    a, p_dead, resid, ok = float(a), float(p_dead), float(resid), bool(ok)
    rec = {"target_Pa": target_Pa, "p_deadhead_Pa": p_dead, "a_eq_m2": a, "bisection_residual_rel": resid}
    if not ok:
        reasons.append(R_DEADHEAD)
        rec.update({"status": status_from_reasons(reasons), "reasons": reasons, "offered": None})
        return rec
    if bool(bisection_failed(a, resid)):
        reasons.append(R_BISECTION)
        rec.update({"status": status_from_reasons(reasons), "reasons": reasons, "offered": None})
        return rec
    rec.update(_operating_record(chain, co, a, k_rec, leak, fc))
    reasons += rec.pop("_reasons")
    rec["reasons"] = reasons
    rec["status"] = status_from_reasons(reasons)
    if rec["status"] in (ST_OOD, ST_MODEL_ERROR):
        # fail closed: no flow / state is offered from outside the model domain (never extrapolated)
        keep = ("target_Pa", "p_deadhead_Pa", "a_eq_m2", "bisection_residual_rel", "reasons", "status")
        diag = {"compressor_K_min": rec["compressor"]["K_min"],
                "compressor_K_over_K0_max": rec["compressor"]["K_over_K0_max"],
                "compressor_p_stage_max_Pa": rec["compressor"]["p_stage_max_Pa"],
                "compressor_inlet_P_Pa": rec["compressor_inlet_P_Pa"],
                "feed_Kn_upper_O_omitted": rec["feed"]["Kn_upper_O_omitted"]}
        rec = {k: rec[k] for k in keep}
        rec["offered"] = None
        rec["domain_diagnostics"] = diag
    return rec


def _operating_record(chain: Chain, co, a_eq: float, k_rec: float, leak, fc) -> dict:
    """Everything at a given orifice-equivalent area: species flows, conservation, compressor gates."""
    T = chain.intake.T_K
    p3, p2 = solve_pressures(co, a_eq, k_rec, leak, fc)
    p3 = {s: float(v) for s, v in p3.items()}
    p2 = {s: float(v) for s, v in p2.items()}
    reasons = []
    Q = {s: (co[s]["A_c"] * p2[s] - p3[s]) / co[s]["B_c"] for s in SPECIES}
    L = {s: chain.plant.leak_m3_s * (p3[s] - p2[s]) for s in SPECIES}
    km = {s: 1.0 / kT_over_m(s, T) for s in SPECIES}              # kg per (Pa m^3)
    mdot_h1 = {s: fc[s] * a_eq * p3[s] * km[s] for s in SPECIES}
    mdot_leak = {s: leak[s] * p3[s] * km[s] for s in SPECIES}
    mdot_comp = {s: Q[s] * km[s] for s in SPECIES}
    mdot_back = {s: L[s] * km[s] for s in SPECIES}
    rec_mass = k_rec * p3["O"] * km["O"]
    net_intake = {s: (co[s]["f"] - co[s]["e"] * p2[s]) * km[s] for s in SPECIES}
    # conservation (inlet node and plenum, per species, recombination mass-conserving)
    res_in = max(abs(net_intake[s] - (mdot_comp[s] - mdot_back[s])) for s in SPECIES)
    conv = {"O": -rec_mass, "N2": 0.0, "O2": rec_mass}
    res_pl = max(abs(mdot_comp[s] - mdot_back[s] - mdot_h1[s] - mdot_leak[s] + conv[s]) for s in SPECIES)
    scale = max(sum(mdot_comp.values()), 1e-300)
    cas = chain.plant.cascade(p2, Q)
    cas_res = max(abs(cas["p_out"][s] / p3[s] - 1.0) for s in SPECIES)
    if cas["K_min"] < 1.0 - K_TOL or cas["K_over_K0_max"] > 1.0 + K_TOL:
        reasons.append(R_CHARACTERISTIC)
    if cas["p_stage_max"] > P_DOMAIN_PA * (1 + 1e-12) or sum(p2.values()) > P_DOMAIN_PA:
        reasons.append(R_STAGE_DOMAIN)
    p3t = sum(p3.values())
    lam = lambda_upper_m(p3, T)
    d_eq = math.sqrt(4.0 * a_eq / math.pi)
    kn = lam / d_eq
    if kn < KN_MIN:
        reasons.append(R_KN_FEED)
    if cas["T_comp_K"] > DB[chain.plant.comp.rotor_material].T_max_K:
        reasons.append(R_THERMAL)
    mt = sum(mdot_h1.values())
    nmol = {s: mdot_h1[s] / M_SPECIES[s] for s in SPECIES}
    nt = sum(nmol.values())
    return {
        "_reasons": reasons,
        "offered": {"mdot_s_kgps": mdot_h1, "mdot_total_kgps": mt, "P_Pa": p3t, "p_s_Pa": p3, "T_K": T,
                    "x_s_flow_mole": {s: nmol[s] / nt for s in SPECIES} if nt > 0 else None,
                    "w_s_flow_mass": {s: mdot_h1[s] / mt for s in SPECIES} if mt > 0 else None,
                    "x_s_plenum_mole": {s: p3[s] / p3t for s in SPECIES}},
        "compressor_inlet_p_s_Pa": p2, "compressor_inlet_P_Pa": sum(p2.values()),
        "mdot_compressor_gross_kgps": mdot_comp, "mdot_compressor_backleak_kgps": mdot_back,
        "mdot_plenum_leak_kgps": mdot_leak, "mdot_recombined_O_kgps": rec_mass, "mdot_intake_net_kgps": net_intake,
        "conservation_residual_rel": {"inlet_node": res_in / scale, "plenum": res_pl / scale,
                                      "cascade_p_out": cas_res},
        "compressor": {"P_el_W": cas["P_el_W"], "P_gas_W": cas["P_gas_W"], "mass_kg": cas["mass_kg"],
                       "T_comp_K": cas["T_comp_K"], "K_min": cas["K_min"], "K_over_K0_max": cas["K_over_K0_max"],
                       "p_stage_max_Pa": cas["p_stage_max"]},
        "feed": {"a_eq_m2": a_eq, "d_eq_m": d_eq, "Kn_upper_O_omitted": kn, "lambda_upper_m": lam},
    }


REASON_BITS = {r: 1 << i for i, r in enumerate(REASONS)}


def reasons_from_bits(bits: int) -> list[str]:
    return [r for r in REASONS if int(bits) & REASON_BITS[r]]


def intake_side(intakes: list, filt: FilterCase, density_factor: float = 1.0) -> dict:
    """Arrays over intake records of the compressor-inlet node source f_s [Pa m^3/s] and escape e_s [m^3/s]."""
    f = {s: np.empty(len(intakes)) for s in SPECIES}
    e = {s: np.empty(len(intakes)) for s in SPECIES}
    for j, it in enumerate(intakes):
        a = it.escape_probability()
        D, E = filt.coefficients(a)
        q = it.q_fwd()
        for s in SPECIES:
            f[s][j] = q[s] * D[s] * density_factor
            e[s][j] = -E[s] * it.area_m2 * cbar(s, it.T_K) / 4.0
    return {"f": f, "e": e}


def cascade_arrays(plant: CompressorPlant, p_in: Mapping, Q: Mapping) -> dict:
    """Vectorized twin of CompressorPlant.cascade (same expressions; equality pinned by a test)."""
    c = plant.comp
    p = {s: np.array(p_in[s], dtype=float, copy=True) for s in SPECIES}
    P_gas = np.zeros(np.broadcast_shapes(*[np.shape(p[s]) for s in SPECIES], *[np.shape(Q[s]) for s in SPECIES]))
    k_min = np.full(P_gas.shape, np.inf)
    k_max_rel = np.full(P_gas.shape, -np.inf)
    p_stage_max = sum(p.values()) + 0.0 * P_gas
    for st in plant.stages():
        for s in SPECIES:
            K0 = st["K0"][s]
            cb = c._cbar(M_SPECIES[s])
            K = K0 - (K0 - 1.0) * Q[s] / np.maximum(st["S"] * p[s], 1e-30)
            k_min = np.minimum(k_min, K)
            k_max_rel = np.maximum(k_max_rel, K / K0)
            P_gas = P_gas + 0.5 * p[s] * (1 + K) * (st["u"] / cb) * st["A_term"] * (2 / math.sqrt(math.pi)) * st["u"]
            p[s] = p[s] * K
        p_stage_max = np.maximum(p_stage_max, sum(p.values()))
    omega = c.rpm * 2 * math.pi / 60.0
    P_bear = c.k_bear_W_per_rads * omega
    P_el = (P_gas + P_bear) / c.eta_motor + c.P_ctrl_W
    torque = (P_gas + P_bear) / omega
    rm = DB[c.rotor_material]
    m_rotor = (math.pi * c.rotor_radius_m ** 2 * c.rotor_disc_thickness_m * rm.density * c.n_stages * 0.7
               + c.turbo_area_m2 * c.turbo_disc_thickness_m * rm.density * c.turbo_rows * c.turbo_blade_area_frac
               + 0.15 * c.turbo_rows)
    mass = m_rotor * (1 + c.stator_mass_factor) + c.motor_kg_per_Nm * np.maximum(torque, 0.01) + 0.25 + c.bearing_kg
    T = c.T_sink_K + (P_gas + P_bear * 0.5 + P_el - (P_gas + P_bear)) / c.conductance_to_sink_W_K
    return {"p_out": p, "K_min": k_min, "K_over_K0_max": k_max_rel, "p_stage_max": p_stage_max, "P_el_W": P_el,
            "mass_kg": mass, "T_comp_K": T, "P_gas_W": P_gas}


def steady_sweep(side: dict, plant: CompressorPlant, plenum: Plenum, targets_Pa, f1_ok=None) -> dict:
    """Gated steady operating points for MANY intake records (rows) x plenum targets (columns) with one compressor,
    filter (already folded into `side`) and plenum: the study path. Reason bits per point (REASON_BITS); quantities
    outside the model domain are NaN (never extrapolated). steady_operating_point() is the scalar reference."""
    tg = np.asarray(targets_Pa, dtype=float)[None, :]
    n = len(side["f"]["O"])
    ch = plant.characteristic()
    CL = plant.leak_m3_s
    co = {s: {"f": side["f"][s][:, None], "e": side["e"][s][:, None], "A_c": ch[s][0], "B_c": ch[s][1],
              "alpha": ch[s][0] / ch[s][1] + CL, "beta": 1.0 / ch[s][1] + CL} for s in SPECIES}
    leak = {s: plenum.leak_m3_s(s) for s in SPECIES}
    fc = {s: plenum.feed_c(s) for s in SPECIES}
    k_rec = plenum.k_rec_m3_s()
    bits = np.zeros((n, tg.shape[1]), dtype=np.int64)
    if f1_ok is not None:
        bits |= np.where(np.asarray(f1_ok)[:, None], 0, REASON_BITS[R_UPSTREAM_F1])
    above = np.broadcast_to(tg > P_DOMAIN_PA, bits.shape)
    bits |= np.where(above, REASON_BITS[R_TARGET_ABOVE_DOMAIN], 0)
    tgt = np.where(tg > P_DOMAIN_PA, P_DOMAIN_PA, tg)          # placeholder target for masked columns only
    a, p_dead, resid, ok = area_for_pressure(co, tgt, k_rec, leak, fc)
    a = np.broadcast_to(a, bits.shape)
    bits |= np.where(~above & ~ok, REASON_BITS[R_DEADHEAD], 0)
    bis_bad = np.broadcast_to(bisection_failed(a, resid), bits.shape)
    bits |= np.where(~above & ok & bis_bad, REASON_BITS[R_BISECTION], 0)
    p3, p2 = solve_pressures(co, a, k_rec, leak, fc)
    Q = {s: (co[s]["A_c"] * p2[s] - p3[s]) / co[s]["B_c"] for s in SPECIES}
    cas = cascade_arrays(plant, p2, Q)
    char_bad = (cas["K_min"] < 1.0 - K_TOL) | (cas["K_over_K0_max"] > 1.0 + K_TOL)
    stage_bad = (cas["p_stage_max"] > P_DOMAIN_PA * (1 + 1e-12)) | (sum(p2.values()) > P_DOMAIN_PA)
    T = T_CHAIN_K
    denom = sum(p3[s] / (K_B * T) * SIGMA_C_M2[s] for s in SIGMA_C_M2)
    kn = (1.0 / (math.sqrt(2.0) * denom)) / np.sqrt(4.0 * a / math.pi)
    live = ~above & ok & ~bis_bad
    bits |= np.where(live & char_bad, REASON_BITS[R_CHARACTERISTIC], 0)
    bits |= np.where(live & stage_bad, REASON_BITS[R_STAGE_DOMAIN], 0)
    bits |= np.where(live & (kn < KN_MIN), REASON_BITS[R_KN_FEED], 0)
    bits |= np.where(live & (cas["T_comp_K"] > DB[plant.comp.rotor_material].T_max_K), REASON_BITS[R_THERMAL], 0)
    km = {s: 1.0 / kT_over_m(s, T) for s in SPECIES}
    md = {s: fc[s] * a * p3[s] * km[s] for s in SPECIES}
    in_domain = live & ~char_bad & ~stage_bad & (kn >= KN_MIN)
    nan = np.where(in_domain, 1.0, np.nan)
    mt = sum(md.values())
    nmol = {s: md[s] / M_SPECIES[s] for s in SPECIES}
    nt = sum(nmol.values())
    return {"bits": bits, "in_domain": in_domain, "mdot_total_kgps": mt * nan,
            "mdot_s_kgps": {s: md[s] * nan for s in SPECIES}, "x_s_flow_mole": {s: nmol[s] / nt * nan for s in SPECIES},
            "P_el_W": cas["P_el_W"] * nan, "m_compressor_kg": cas["mass_kg"] * nan, "T_comp_K": cas["T_comp_K"] * nan,
            "a_eq_m2": a * nan, "p_deadhead_Pa": np.broadcast_to(p_dead, bits.shape) * 1.0,
            "bisection_residual_rel": np.broadcast_to(resid, bits.shape) * nan, "Kn_upper": kn * nan}


# =================================================================================================== transient
@dataclass(frozen=True)
class Controller:
    """Normalized PI on plenum pressure: u_cmd = u_ff (1 + Kp eps + (Kp / Ti) I), eps = (p - r) / r, with
    back-calculation anti-windup dI/dt = eps + (clip(u_cmd, 0, 1) - u_cmd) / (Kp u_ff) (tracking time = Ti; continuous
    right-hand side, so the stiff integrator never chatters on a switching rule); actuator first-order lag
    du/dt = (clip(u_cmd, 0, 1) - u) / tau_v. u = A_eq / A_eq,max; u_ff = 1 / authority (bumpless start)."""
    Kp: float
    Ti_s: float
    f_valve_hz: float
    authority: float

    @property
    def id(self) -> str:
        return f"Kp{self.Kp:g}_Ti{self.Ti_s:g}_fv{self.f_valve_hz:g}_r{self.authority:g}"

    @property
    def tau_v(self) -> float:
        return 1.0 / (2.0 * math.pi * self.f_valve_hz)


@dataclass(frozen=True)
class Event:
    """One segment of a test sequence: what changes at t_start (setpoint, feed-path factor, intake state, free-stream
    density factor, density modulation amplitude) and how long it runs."""
    name: str
    kind: str                 # 'hold' | 'setpoint' | 'feed_path' | 'supply' | 'orbit'
    duration_s: float
    setpoint_Pa: float
    feed_factor: float
    intake: IntakeState
    orbit_amplitude: float = 0.0
    orbit_period_s: float = 0.0
    density: float = 1.0

    def density_at(self, t):
        """Free-stream density factor at time t after the event (F1 law: f_s proportional to it)."""
        if self.kind == "orbit":
            return self.density * (1.0 + self.orbit_amplitude * np.sin(2.0 * math.pi * np.asarray(t) / self.orbit_period_s))
        return self.density * np.ones_like(np.asarray(t, dtype=float))


class TransientRun:
    """Simulate the coupled chain under a controller through a sequence of events (solver restarted at each event).

    States (scaled): p_s / r0 for O, N2, O2 (plenum partial pressures), u (valve opening), I (integral of eps), and
    three cumulative mass integrals / (mdot_scale x 1 s): compressor gross through-flow into the plenum, all outflows
    (compressor back-leak + valve + external leak) and the recombined O mass. Plenum balance per species in throughput
    units (V dp_s/dt = q_s,compressor-net - G_s u p_s - c_leak,s p_s -/+ recombination) with the compressor-inlet node
    solved algebraically (q_s,compressor-net = (alpha f - e beta p_s) / (e + alpha), i.e. gross Q_s minus back-leak L_s).
    The right-hand side is linear in p except the valve term G u p; an analytic Jacobian is supplied to the stiff solver."""

    def __init__(self, filt: FilterCase, plant: CompressorPlant, plenum: Plenum, ctrl: Controller,
                 design_intake: IntakeState, r0_Pa: float, rtol: float = RTOL, method: str | None = None):
        self.filt, self.plant, self.plenum, self.ctrl = filt, plant, plenum, ctrl
        self.rtol = rtol
        self.method = method or INTEGRATOR_METHOD
        self.T = plenum.T_K
        self.leak = [plenum.leak_m3_s(s) for s in SPECIES]
        self.fc = [plenum.feed_c(s) for s in SPECIES]
        self.k_rec = plenum.k_rec_m3_s()
        self.km = [1.0 / kT_over_m(s, self.T) for s in SPECIES]
        self.mO_mO2 = M_SPECIES["O"] / M_SPECIES["O2"]
        self.r0 = float(r0_Pa)
        co = Chain(design_intake, filt, plant, plenum).node_coefficients()
        leak_d = dict(zip(SPECIES, self.leak))
        fc_d = dict(zip(SPECIES, self.fc))
        a, p_dead, resid, ok = area_for_pressure(co, r0_Pa, self.k_rec, leak_d, fc_d)
        if not bool(ok):
            raise ValueError("design setpoint at or above dead-head: no steady operating point to start from")
        if bool(bisection_failed(a, resid)):
            raise ValueError("design setpoint orifice-area bisection did not converge (R_BISECTION)")
        self.a_ss = float(a)
        self.a_max = ctrl.authority * self.a_ss
        self.u_ff = 1.0 / ctrl.authority
        p3, _ = solve_pressures(co, self.a_ss, self.k_rec, leak_d, fc_d)
        self.p_init = [float(p3[s]) for s in SPECIES]
        self.mdot_scale = sum(self.fc[i] * self.a_ss * self.p_init[i] * self.km[i] for i in range(3))
        self.design_intake = design_intake

    def _u_cmd(self, eps: float, I: float) -> float:
        c = self.ctrl
        return self.u_ff * (1.0 + c.Kp * eps + (c.Kp / c.Ti_s) * I)

    def _event_coeffs(self, ev: Event) -> dict:
        co = Chain(ev.intake, self.filt, self.plant, self.plenum).node_coefficients()
        out = {"q0": [], "k": [], "dQ": [], "Q0": [], "dL": [], "L0": []}
        CL = self.plant.leak_m3_s
        for s in SPECIES:
            c = co[s]
            den = c["e"] + c["alpha"]
            out["q0"].append(c["alpha"] * c["f"] / den)              # compressor-net inflow at p = 0
            out["k"].append(c["e"] * c["beta"] / den)                # its slope
            # gross Q = Q0 + dQ p ; back-leak L = L0 + dL p  (for the bookkeeping integrals)
            out["Q0"].append(c["A_c"] * c["f"] / den / c["B_c"])
            out["dQ"].append((c["A_c"] * c["beta"] / den - 1.0) / c["B_c"])
            out["L0"].append(-CL * c["f"] / den)
            out["dL"].append(CL * (1.0 - c["beta"] / den))
        return out

    def _make(self, ev: Event):
        V, r0 = self.plenum.volume_m3, self.r0
        cf = self._event_coeffs(ev)
        q0, k, Q0, dQ, L0, dL = cf["q0"], cf["k"], cf["Q0"], cf["dQ"], cf["L0"], cf["dL"]
        G = [self.fc[i] * self.a_max * ev.feed_factor for i in range(3)]
        cl, km, kr, mr = self.leak, self.km, self.k_rec, self.mO_mO2
        orbit = ev.kind == "orbit"
        w = 2.0 * math.pi / ev.orbit_period_s if orbit else 0.0
        amp = ev.orbit_amplitude
        d0 = ev.density
        rset = ev.setpoint_Pa
        Kp, Ti, tau, uff = self.ctrl.Kp, self.ctrl.Ti_s, self.ctrl.tau_v, self.u_ff
        ms = self.mdot_scale

        def dens(t):
            return d0 * (1.0 + amp * math.sin(w * t)) if orbit else d0

        def ctrl_terms(p_tot, u, I):
            eps = (p_tot - rset) / rset
            ucmd = uff * (1.0 + Kp * eps + (Kp / Ti) * I)
            hi, lo = ucmd > 1.0, ucmd < 0.0
            usat = 1.0 if hi else (0.0 if lo else ucmd)
            return eps, ucmd, hi, lo, usat

        def rhs(t, y):
            d = dens(t)
            p = [y[0] * r0, y[1] * r0, y[2] * r0]
            u, I = y[3], y[4]
            eps, ucmd, hi, lo, usat = ctrl_terms(p[0] + p[1] + p[2], u, I)
            rec = kr * p[0]
            dp = []
            ins = outs = 0.0
            for i in range(3):
                net = q0[i] * d - k[i] * p[i] - G[i] * u * p[i] - cl[i] * p[i]
                if i == 0:
                    net -= rec
                elif i == 2:
                    net += rec * mr
                dp.append(net / V / r0)
                Qg = Q0[i] * d + dQ[i] * p[i]
                Lb = L0[i] * d + dL[i] * p[i]
                ins += Qg * km[i]
                outs += (Lb + G[i] * u * p[i] + cl[i] * p[i]) * km[i]
            du = (usat - u) / tau
            dI = eps + (usat - ucmd) / (Kp * uff)
            return [dp[0], dp[1], dp[2], du, dI, ins / ms, outs / ms, rec * km[0] / ms]

        def jac(t, y):
            p = [y[0] * r0, y[1] * r0, y[2] * r0]
            u, I = y[3], y[4]
            eps, ucmd, hi, lo, usat = ctrl_terms(p[0] + p[1] + p[2], u, I)
            J = np.zeros((8, 8))
            for i in range(3):
                J[i, i] = -(k[i] + G[i] * u + cl[i]) / V
                J[i, 3] = -G[i] * p[i] / V / r0
            J[0, 0] -= kr / V
            J[2, 0] += kr * mr / V
            sat = hi or lo
            # d eps / d y_i = r0 / rset; d ucmd / d y_i = uff Kp r0 / rset; d ucmd / d I = uff Kp / Ti
            for i in range(3):
                J[3, i] = 0.0 if sat else uff * Kp / tau * r0 / rset
                J[4, i] = 0.0 if sat else r0 / rset            # saturated: eps' - ucmd' / (Kp uff) = 0
            J[3, 3] = -1.0 / tau
            J[3, 4] = 0.0 if sat else uff * Kp / Ti / tau
            J[4, 4] = -1.0 / Ti if sat else 0.0
            for i in range(3):
                J[5, i] = dQ[i] * km[i] * r0 / ms
                J[6, i] = (dL[i] + G[i] * u + cl[i]) * km[i] * r0 / ms
                J[6, 3] += G[i] * p[i] * km[i] / ms
            J[7, 0] = kr * km[0] * r0 / ms
            return J

        return rhs, jac

    def steady_start(self, intake: IntakeState, setpoint_Pa: float, density: float = 1.0):
        """Initial state = the steady state of `intake` held at setpoint by this controller: (y0, u_ss). u_ss > 1 means
        the valve authority cannot hold the setpoint at that state (the caller records R_SATURATED)."""
        co = Chain(intake, self.filt, self.plant, self.plenum).node_coefficients(density)
        leak_d, fc_d = dict(zip(SPECIES, self.leak)), dict(zip(SPECIES, self.fc))
        a, p_dead, resid, ok = area_for_pressure(co, setpoint_Pa, self.k_rec, leak_d, fc_d)
        if not bool(ok):
            return None, None
        u_ss = float(a) / self.a_max
        p3, _ = solve_pressures(co, float(a), self.k_rec, leak_d, fc_d)
        I = (u_ss / self.u_ff - 1.0) * self.ctrl.Ti_s / self.ctrl.Kp          # eps = 0 at the steady state
        return [float(p3[s]) / self.r0 for s in SPECIES] + [u_ss, I, 0.0, 0.0, 0.0], u_ss

    def run(self, events: list, n_eval: int = 150, y_start=None) -> dict:
        from scipy.integrate import solve_ivp
        V, r0 = self.plenum.volume_m3, self.r0
        y = list(y_start) if y_start is not None else \
            [self.p_init[i] / r0 for i in range(3)] + [self.u_ff, 0.0, 0.0, 0.0, 0.0]
        mass = lambda yy: sum(max(yy[i], 0.0) * r0 * V * self.km[i] for i in range(3))
        m0 = mass(y)
        t0, segs, nfev, cum_in, cum_out = 0.0, [], 0, 0.0, 0.0
        for ev in events:
            rhs, jac = self._make(ev)
            te = np.unique(np.concatenate([[0.0], np.geomspace(1e-6 * max(ev.duration_s, 1.0), ev.duration_s,
                                                                n_eval)]))
            te[-1] = ev.duration_s
            y0 = list(y[:5]) + [0.0, 0.0, 0.0]
            sol = solve_ivp(rhs, (0.0, ev.duration_s), y0, method=self.method, jac=jac, rtol=self.rtol,
                            atol=ATOL_SCALED, t_eval=te)
            nfev += sol.nfev
            if not sol.success:
                return {"ok": False, "reason": R_INTEGRATOR, "message": str(sol.message), "segments": segs,
                        "nfev": nfev}
            y = list(sol.y[:, -1])
            cum_in += sol.y[5, -1] * self.mdot_scale
            cum_out += sol.y[6, -1] * self.mdot_scale
            segs.append(self._segment_record(ev, t0, sol))
            t0 += ev.duration_s
        resid = abs((mass(y) - m0) - (cum_in - cum_out)) / max(cum_in, 1e-300)
        return {"ok": True, "segments": segs, "mass_residual_rel": resid, "throughput_kg": cum_in, "nfev": nfev}

    def _segment_record(self, ev: Event, t0: float, sol) -> dict:
        r0 = self.r0
        t = sol.t
        ps = [np.maximum(sol.y[i], 0.0) * r0 for i in range(3)]
        p = ps[0] + ps[1] + ps[2]
        u = sol.y[3]
        a_eq = u * self.a_max * ev.feed_factor
        md = [self.fc[i] * a_eq * ps[i] * self.km[i] for i in range(3)]
        mdot = md[0] + md[1] + md[2]
        nmol = [md[i] / M_SPECIES[s] for i, s in enumerate(SPECIES)]
        nt = nmol[0] + nmol[1] + nmol[2]
        xO = np.where(nt > 0, nmol[0] / np.where(nt > 0, nt, 1.0), np.nan)
        ucmd_end = self._u_cmd((p[-1] - ev.setpoint_Pa) / ev.setpoint_Pa, float(sol.y[4, -1]))
        # compressor domain along the trajectory (fail closed on transients, not only at steady states)
        co = Chain(ev.intake, self.filt, self.plant, self.plenum).node_coefficients()
        d = ev.density_at(t)
        p2 = {s: (co[s]["f"] * d + co[s]["beta"] * ps[i]) / (co[s]["e"] + co[s]["alpha"])
              for i, s in enumerate(SPECIES)}
        Q = {s: (co[s]["A_c"] * p2[s] - ps[i]) / co[s]["B_c"] for i, s in enumerate(SPECIES)}
        cas = cascade_arrays(self.plant, p2, Q)
        return {"event": ev.name, "kind": ev.kind, "t_start_s": t0, "duration_s": ev.duration_s, "t": t, "p": p,
                "mdot": mdot, "u": u, "xO": xO, "setpoint_Pa": ev.setpoint_Pa,
                "saturated_end": bool(ucmd_end > 1.0 + 1e-9 or ucmd_end < -1e-9), "intake_state": ev.intake.state,
                "K_min": float(np.min(cas["K_min"])), "K_over_K0_max": float(np.max(cas["K_over_K0_max"])),
                "p_stage_max_Pa": float(np.max(cas["p_stage_max"])),
                "p_inlet_max_Pa": float(np.max(p2["O"] + p2["N2"] + p2["O2"])),
                "P_el_max_W": float(np.max(cas["P_el_W"])),
                "T_comp_max_K": float(np.max(cas["T_comp_K"])),
                "T_comp_limit_K": float(DB[self.plant.comp.rotor_material].T_max_K)}


def settling_time(t: np.ndarray, y: np.ndarray, final: float, band: float = SETTLE_BAND):
    """Time after which |y - final| <= band |final| for the rest of the window; None when the last sample is still
    outside the band (NOT settled within the window). Sampling-resolution upper bound."""
    out = np.abs(y - final) > band * abs(final)
    if not out.any():
        return 0.0
    if out[-1]:
        return None
    last = int(np.nonzero(out)[0][-1])
    return float(t[last + 1])


def segment_metrics(seg: dict, p_prev_final: float) -> dict:
    """Metric definitions (also in the JSON metric_definitions):
      settling_time_s     time from the event until |P - P_final| <= SETTLE_BAND P_final for the rest of the segment
      overshoot_frac      setpoint events: max(0, max sign(dP)(P - P_final)) / |P_final - P_prev|
      peak_deviation_frac regulation events: max |P - r| / r
      flow_recovery_s     time until |mdot - mdot_final| <= SETTLE_BAND mdot_final for the rest of the segment
      ripple_pp_frac      orbit segment: peak-to-peak / mean of P and of mdot over the last full period
      valve_travel        sum |du| over the segment (fraction of full stroke)"""
    t, p, md, u = seg["t"], seg["p"], seg["mdot"], seg["u"]
    r = seg["setpoint_Pa"]
    pf, mf = float(p[-1]), float(md[-1])
    out = {"event": seg["event"], "kind": seg["kind"], "P_final_Pa": pf, "mdot_final_kgps": mf,
           "P_min_Pa": float(p.min()), "P_max_Pa": float(p.max()), "mdot_min_kgps": float(md.min()),
           "mdot_max_kgps": float(md.max()), "xO_min": float(np.nanmin(seg["xO"])),
           "xO_max": float(np.nanmax(seg["xO"])), "valve_travel": float(np.abs(np.diff(u)).sum()),
           "u_min": float(u.min()), "u_max": float(u.max()), "saturated_end": seg["saturated_end"],
           "final_setpoint_error_frac": abs(pf - r) / r}
    if seg["kind"] == "orbit":
        out["ripple_pp_frac_P"] = float((p.max() - p.min()) / p.mean())
        out["ripple_pp_frac_mdot"] = float((md.max() - md.min()) / md.mean())
        out["settling_time_s"] = None
        return out
    out["settling_time_s"] = settling_time(t, p, r)
    out["flow_recovery_s"] = settling_time(t, md, mf)
    if seg["kind"] == "setpoint":
        d = pf - p_prev_final
        out["overshoot_frac"] = float(max(0.0, (np.sign(d) * (p - r)).max()) / abs(d)) if d != 0 else 0.0
        out["peak_deviation_frac"] = None
    else:
        out["overshoot_frac"] = None
        out["peak_deviation_frac"] = float(np.abs(p - r).max() / r)
    return out


def ripple_transfer(chain: Chain, a_eq: float, f_hz: float) -> dict:
    """Open-loop plenum attenuation of a compressor-delivered flow perturbation at f_hz (above the valve / controller
    bandwidth): |dP/P| / |dq/q| = 1 / sqrt(1 + (2 pi f tau_s)^2), tau_s = V / (k_s + G_s + leak_s (+ k_rec for O)).
    The least attenuated species is reported (upper bound)."""
    co = chain.node_coefficients()
    pl = chain.plenum
    out = {}
    for s in SPECIES:
        c = co[s]
        k = c["e"] * c["beta"] / (c["e"] + c["alpha"])
        g = pl.feed_c(s) * a_eq + pl.leak_m3_s(s) + (pl.k_rec_m3_s() if s == "O" else 0.0)
        tau = pl.volume_m3 / (k + g)
        out[s] = {"tau_s": tau, "transfer": 1.0 / math.sqrt(1.0 + (2 * math.pi * f_hz * tau) ** 2)}
    worst = max(SPECIES, key=lambda s: out[s]["transfer"])
    return {"f_hz": f_hz, "species": out, "transfer_max": out[worst]["transfer"], "worst_species": worst,
            "tau_min_s": min(v["tau_s"] for v in out.values()), "tau_max_s": max(v["tau_s"] for v in out.values())}


def inlet_node_tau_per_m3(chain: Chain) -> float:
    """Compressor-inlet node time constant per m^3 of (TBD) inlet volume: max_s 1 / (e_s + alpha_s) [s/m^3]."""
    co = chain.node_coefficients()
    return max(1.0 / (co[s]["e"] + co[s]["alpha"]) for s in SPECIES)


# =================================================================================================== transient case
WINDOW_S = 60.0                 # observation window per event (metric definition; a censored settle is reported)
SETPOINT_STEP = 0.10            # relative setpoint step (up, then back down)
FEED_PATH_STEP = 0.8            # parametric multiplicative step of the downstream feed-path conductance
SUPPLY_STEP = 0.10              # parametric free-stream supply step (+/-), TBD (no time-resolved free stream)
# A9.13 S6.17: ripple is a hard feed-quality constraint (``feed_quality``), not a Pareto objective; its value is still
# reported in every case's objectives record under 'ripple_transfer_shaft'.
OBJECTIVES = ("V_m3", "valve_travel", "settling_max_s", "peak_deviation_max", "P_compressor_el_W")
REPORTED_NOT_OPTIMISED = ("ripple_transfer_shaft",)
TRANSIENT_FRAMEWORK = dict(u13.F4_TRANSIENT_FRAMEWORK, settling_band_frac=SETTLE_BAND, observation_window_s=60.0)


def event_sequence(design: IntakeState, r0: float, window_s: float = WINDOW_S) -> list:
    """The fixed test sequence (definition), all at the design state: hold; setpoint +10 % and back; feed-path
    conductance x0.8 and back; free-stream supply step x(1 - SUPPLY_STEP), then x(1 + SUPPLY_STEP), then back to 1."""
    W = window_s
    return [Event("E0_hold", "hold", 10.0, r0, 1.0, design),
            Event("E1_setpoint_up", "setpoint", W, r0 * (1 + SETPOINT_STEP), 1.0, design),
            Event("E2_setpoint_down", "setpoint", W, r0, 1.0, design),
            Event("E3_feed_path_step", "feed_path", W, r0, FEED_PATH_STEP, design),
            Event("E4_feed_path_restore", "feed_path", W, r0, 1.0, design),
            Event("E5_supply_down", "supply", W, r0, 1.0, design, density=1.0 - SUPPLY_STEP),
            Event("E6_supply_up", "supply", W, r0, 1.0, design, density=1.0 + SUPPLY_STEP),
            Event("E7_supply_restore", "supply", W, r0, 1.0, design, density=1.0)]


def _domain_reasons(segs: list) -> list:
    out = []
    if max(float(np.max(sg["p"])) for sg in segs) > P_DOMAIN_PA:
        out.append(R_TRAJ_DOMAIN)
    if min(sg["K_min"] for sg in segs) < 1.0 - K_TOL or max(sg["K_over_K0_max"] for sg in segs) > 1.0 + K_TOL:
        out.append(R_CHARACTERISTIC)
    if max(sg["p_stage_max_Pa"] for sg in segs) > P_DOMAIN_PA * (1 + 1e-12) or \
            max(sg["p_inlet_max_Pa"] for sg in segs) > P_DOMAIN_PA:
        out.append(R_STAGE_DOMAIN)
    # thermal service limit along the trajectory, as on the steady paths (PR #36 review)
    if any(sg["T_comp_max_K"] > sg["T_comp_limit_K"] for sg in segs):
        out.append(R_THERMAL)
    return out


def orbit_quasi_static(filt: FilterCase, plant: CompressorPlant, plenum: Plenum, states: list, r0: float,
                       amplitude: float, a_max_m2: float, n_phase: int = 24) -> dict:
    """Orbit-scale check at EVERY F1 orbit state: free-stream density 1 + amplitude sin(phase) on n_phase phases, plenum
    held at r0 (quasi-static: the plenum / valve / PI time constants are << the orbital period; verified against the
    full transient by orbit_simulated()). Per state: valve opening u = A_eq / A_eq,max over the orbit (> 1: the
    authority cannot hold r0), dead-head and domain reasons, and the delivered-flow / composition swing."""
    ph = 2.0 * math.pi * np.arange(n_phase) / n_phase
    dens = 1.0 + amplitude * np.sin(ph)
    rows, reasons = [], []
    for st in states:
        side = {"f": {}, "e": {}}
        base = intake_side([st], filt)
        for s in SPECIES:
            side["f"][s] = base["f"][s][0] * dens
            side["e"][s] = np.full(n_phase, base["e"][s][0])
        sw = steady_sweep(side, plant, plenum, [r0])
        bits = np.bitwise_or.reduce(sw["bits"][:, 0])
        rs = reasons_from_bits(int(bits))
        u = sw["a_eq_m2"][:, 0] / a_max_m2
        md = sw["mdot_total_kgps"][:, 0]
        row = {"state": st.state, "reasons": rs, "n_phase": n_phase, "amplitude": amplitude}
        if not rs:
            row.update({"u_min": float(np.min(u)), "u_max": float(np.max(u)), "mdot_min_kgps": float(np.min(md)),
                        "mdot_max_kgps": float(np.max(md)), "ripple_pp_frac_mdot": float((md.max() - md.min()) / md.mean()),
                        "xO_flow_min": float(np.min(sw["x_s_flow_mole"]["O"][:, 0])),
                        "xO_flow_max": float(np.max(sw["x_s_flow_mole"]["O"][:, 0]))})
            if row["u_max"] > 1.0:
                rs = [R_SATURATED]
                row["reasons"] = rs
        reasons += rs
        rows.append(row)
    return {"rows": rows, "reasons": sorted(set(reasons), key=REASONS.index), "amplitude": amplitude}


def orbit_simulated(filt: FilterCase, plant: CompressorPlant, plenum: Plenum, ctrl: Controller, design: IntakeState,
                    state: IntakeState, r0: float, amplitude: float) -> dict:
    """Full transient over one orbital period at `state` (started from its own steady state): the verification of
    orbit_quasi_static (plenum pressure held, delivered-flow swing)."""
    tr = TransientRun(filt, plant, plenum, ctrl, design, r0)
    y0, u_ss = tr.steady_start(state, r0)
    if y0 is None or u_ss > 1.0:
        return {"ok": False, "reason": "NO_STEADY_START"}
    T_orb = orbital_period_s(state.alt_km)
    out = tr.run([Event(f"O_{state.state}", "orbit", T_orb, r0, 1.0, state, amplitude, T_orb)], y_start=y0)
    if not out["ok"]:
        return {"ok": False, "reason": R_INTEGRATOR}
    sg = out["segments"][0]
    md = sg["mdot"]
    return {"ok": True, "state": state.state, "P_dev_max_frac": float(np.abs(sg["p"] / r0 - 1.0).max()),
            "mdot_min_kgps": float(md.min()), "mdot_max_kgps": float(md.max()),
            "mass_residual_rel": out["mass_residual_rel"], "nfev": out["nfev"]}


def transient_case(filt: FilterCase, plant: CompressorPlant, plenum: Plenum, ctrl: Controller, design: IntakeState,
                   r0: float, orbit_check: dict | None = None, window_s: float = WINDOW_S, rtol: float = RTOL,
                   method: str | None = None) -> dict:
    """Event sequence at the design state (solve_ivp, INTEGRATOR_METHOD) plus the orbit check (orbit_quasi_static, computed by the
    caller with A_eq,max = authority x A_eq(design)). Returns metrics, reasons (fail closed) and the Pareto objectives
    (recorded for infeasible cases too; only FEASIBLE cases enter the Pareto filter)."""
    reasons, metrics = [], []
    try:
        tr = TransientRun(filt, plant, plenum, ctrl, design, r0, rtol, method)
    except ValueError:
        return {"status": status_from_reasons([R_DEADHEAD]), "reasons": [R_DEADHEAD], "metrics": [],
                "summary": None, "objectives": None}
    out = tr.run(event_sequence(design, r0, window_s))
    if not out["ok"]:
        return {"status": ST_MODEL_ERROR, "reasons": [R_INTEGRATOR], "metrics": [], "summary": None,
                "objectives": None, "message": out.get("message")}
    if out["mass_residual_rel"] > MASS_TOL:
        reasons.append(R_CONSERVATION)
    prev = r0
    for sg in out["segments"]:
        m = segment_metrics(sg, prev)
        prev = m["P_final_Pa"]
        metrics.append(m)
    for m in metrics[1:]:
        if m["settling_time_s"] is None or m["flow_recovery_s"] is None:
            reasons.append(R_NOT_SETTLED)
        if m["saturated_end"]:
            reasons.append(R_SATURATED)
    reasons += _domain_reasons(out["segments"])
    if orbit_check is not None:
        reasons += orbit_check["reasons"]
    reasons = sorted(set(reasons), key=REASONS.index)
    chain = Chain(design, filt, plant, plenum)
    rip = ripple_transfer(chain, tr.a_ss, plant.shaft_hz)
    op = steady_operating_point(chain, r0)
    reg = metrics[1:]
    settle = [m["settling_time_s"] for m in reg] + [m["flow_recovery_s"] for m in reg]
    obj = {"V_m3": plenum.volume_m3,
           "valve_travel": float(sum(m["valve_travel"] for m in metrics)),
           "settling_max_s": None if any(x is None for x in settle) else float(max(settle)),
           "peak_deviation_max": float(max(m["peak_deviation_frac"] for m in reg if m["peak_deviation_frac"] is not None)),
           "ripple_transfer_shaft": rip["transfer_max"],
           "P_compressor_el_W": op["compressor"]["P_el_W"] if op.get("compressor") else None}
    summary = {"P_min_Pa": min(m["P_min_Pa"] for m in metrics), "P_max_Pa": max(m["P_max_Pa"] for m in metrics),
               "mdot_min_kgps": min(m["mdot_min_kgps"] for m in metrics),
               "mdot_max_kgps": max(m["mdot_max_kgps"] for m in metrics),
               "xO_flow_min": min(m["xO_min"] for m in metrics), "xO_flow_max": max(m["xO_max"] for m in metrics),
               "overshoot_max": max((m["overshoot_frac"] or 0.0) for m in reg),
               "mass_residual_rel": out["mass_residual_rel"], "nfev": out["nfev"],
               "a_eq_design_m2": tr.a_ss, "a_eq_max_m2": tr.a_max, "plenum_tau_s": [rip["tau_min_s"], rip["tau_max_s"]],
               "shaft_hz": plant.shaft_hz}
    if op.get("offered"):
        inv = r0 * plenum.volume_m3 / (K_B * plenum.T_K) * sum(op["offered"]["x_s_plenum_mole"][s] * M_SPECIES[s]
                                                                for s in SPECIES)
        summary["inventory_kg"] = inv
        summary["ride_through_s"] = inv / op["offered"]["mdot_total_kgps"]
    return {"status": status_from_reasons(reasons), "reasons": reasons, "metrics": metrics, "summary": summary,
            "objectives": obj}


# =================================================================================================== strict mode
def strict_blockers() -> list[dict]:
    """MODE_STRICT refuses while any of these is TBD / an uncited default (they all are today)."""
    return [
        {"id": "F3-STRICT", "what": "compressor coefficients", "status": "F3 MODE_STRICT NOT_EVALUATED (22 blockers)",
         "needs": "compressor_downselect T-1..T-9 evidence"},
        {"id": "F2-FILTER", "what": "filter stage", "status": "every real concept TBD; 'none' (FC-00) is a reference "
         "bound only (A9.13 S6.5)", "needs": "evidenced inert / low-recombination filter records (A9.13 S6.3 / S6.19)"},
        {"id": "F4-P-01", "what": "chain gas temperature", "status": "assumed (code default)", "needs": "H2-5 thermal"},
        {"id": "F4-P-05", "what": "plenum leak", "status": "TBD", "needs": "leak specification / test"},
        {"id": "F4-P-06", "what": "plenum wall gamma_O", "status": "TBD", "needs": "GP-D03 + coupon evidence"},
        {"id": "F4-P-08", "what": "valve bandwidth", "status": "TBD", "needs": "metering-valve class (H3)"},
        {"id": "F4-P-09", "what": "valve authority", "status": "TBD", "needs": "metering-valve sizing"},
        {"id": "F4-P-10", "what": "H-1 required inlet state", "status": "TBD", "needs": "F5 IFD-F4-01..05 / Phase 1"},
        {"id": "F4-P-11", "what": "orbit-scale density modulation", "status": "TBD",
         "needs": "registered inclination / LTAN (mission ICD) to sample a revolution of the orbit-resolved dataset"},
        {"id": "F4-P-18", "what": "compressor-inlet node volume", "status": "TBD", "needs": "duct geometry"},
        {"id": "F4-H1-TOL", "what": "measured H-1 feed tolerances (pressure, flow, composition, ripple)",
         "status": "TBD", "needs": "LOCK-2 H-1 feed-sensitivity measurement (A9.13 S6.12 / S6.17)"},
        {"id": "F4-SCHEDULE", "what": "orbit-state setpoint schedule (baseline control mode)", "status": "NOT_FROZEN",
         "needs": "validated compressor / feed / H-1 domains (A9.13 S6.10)"},
    ]


def evaluate(chain: Chain, target_Pa: float, mode: str = MODE_PARAMETRIC) -> dict:
    """Public entry point: MODE_STRICT refuses; MODE_PARAMETRIC returns the labelled steady operating point."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if mode == MODE_STRICT:
        return {"status": ST_NOT_EVALUATED, "blockers": strict_blockers(), "offered": None}
    rec = steady_operating_point(chain, target_Pa)
    rec["label"] = LABEL_PARAMETRIC
    return rec


# =================================================================================================== Pareto
def dominates(a: Mapping, b: Mapping, objectives) -> bool:
    better = False
    for k in objectives:
        if a[k] > b[k]:
            return False
        if a[k] < b[k]:
            better = True
    return better


def _finite_obj(v) -> bool:
    try:
        return v is not None and not isinstance(v, bool) and math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def pareto_ids(rows: list[dict], objectives) -> list[str]:
    """Non-dominated feasible rows (all objectives minimized; ties all kept). Deterministic (sorted by id)."""
    # OPT-04: a row with a non-finite objective never enters dominance (fail closed)
    feas = sorted((r for r in rows if r["status"] == ST_FEASIBLE and
                   all(_finite_obj(r["objectives"].get(k)) for k in objectives)), key=lambda r: r["id"])
    vals = [r["objectives"] for r in feas]
    return [r["id"] for i, r in enumerate(feas)
            if not any(dominates(vals[j], vals[i], objectives) for j in range(len(feas)) if j != i)]


# =================================================================================================== A9.13 S6.10 control
NAV_ALTITUDE_INPUT = u13.ScheduleInput("nav:alt_km", "onboard_navigation_or_clock",
                                     "onboard orbit determination (navigation solution); availability per the "
                                     "spacecraft ICD (TBD)")


def intake_controller_state(intake: IntakeState, inputs=(NAV_ALTITUDE_INPUT,)) -> dict:
    """Controller-available view of an F1 orbit state: only declared inputs (altitude from navigation by default).
    The intake's environment-truth quantities (density, composition, surface scenario) are never exposed."""
    full = {"alt_km": intake.alt_km}
    return u13.controller_view(full, list(inputs), {i.name: i.name.split(":", 1)[1] for i in inputs})


def scheduled_operation(filt: FilterCase, plant: CompressorPlant, plenum: Plenum, intakes: list, control,
                        controller_states: Mapping | None = None) -> dict:
    """Steady operation at every orbit state under one control mode (A9.13 S6.10): ``control`` is an
    upstream_a9_13.SetpointSchedule (BASELINE) or FixedSetpoint (fallback / reference). The setpoint of each state
    comes from that state's controller-available view only; a setpoint above 0.1 Pa is NOT_EVALUATED_OUT_OF_DOMAIN
    (S6.8), and nothing is offered from it. Every point carries the steady_operating_point gates."""
    if not isinstance(control, (u13.SetpointSchedule, u13.FixedSetpoint)):
        raise ValueError("control must be an upstream_a9_13.SetpointSchedule or FixedSetpoint")
    rows = []
    for it in intakes:
        cst = (controller_states or {}).get(it.state) if controller_states else intake_controller_state(it)
        if cst is None:
            raise ValueError(f"no controller state for {it.state}")
        sp = control.setpoint(cst)
        row = {"state": it.state, "scenario": it.scenario, "candidate": it.candidate, "mode": control.mode,
               "mode_role": u13.CONTROL_MODES[control.mode], "controller_state": dict(cst), "setpoint": sp}
        if sp["setpoint_Pa"] is None:
            row.update({"status": sp["status"], "reasons": [], "offered": None})
        else:
            op = steady_operating_point(Chain(it, filt, plant, plenum), sp["setpoint_Pa"])
            row.update({"status": op["status"], "reasons": op["reasons"], "offered": op.get("offered"),
                        "a_eq_m2": op.get("a_eq_m2"),
                        "P_compressor_el_W": (op.get("compressor") or {}).get("P_el_W"),
                        "domain": sp["domain"]})
        rows.append(row)
    ok = [r for r in rows if r["status"] == ST_FEASIBLE]
    md = [r["offered"]["mdot_total_kgps"] for r in ok]
    # A9.13 S6.13: a run over a subset of the required states (e.g. the higher-density states only) is a sensitivity
    # and never baseline (fail closed: the coverage is computed against the frozen design-state set)
    cov = u13.state_coverage([it.state for it in intakes], [s.id for s in isy.required_states()])
    return {"mode": control.mode, "mode_role": u13.CONTROL_MODES[control.mode], "control": control.to_dict(),
            "label": LABEL_PARAMETRIC, "state_coverage": cov,
            "operation_role": "ELIGIBLE_BY_COVERAGE (S6.15 still governs)" if cov["baseline_admissible_by_coverage"]
            else u13.DENSE_STATE_ONLY_ROLE, "orbit_basis": isy.ORBIT_BASIS_LABEL,
            "rows": rows, "n_states": len(rows), "n_feasible": len(ok),
            "all_states_feasible": len(ok) == len(rows),
            "worst_state_mdot_kgps": min(md) if len(ok) == len(rows) and md else None,
            "authority": u13.cite("A9.13")}


def compare_control_modes(filt: FilterCase, plant: CompressorPlant, plenum: Plenum, intakes: list,
                          schedule: "u13.SetpointSchedule", fixed: "u13.FixedSetpoint",
                          controller_states: Mapping | None = None) -> dict:
    """Baseline (scheduled) and fallback / reference (fixed) side by side; no mode is 'selected' here (S6.10)."""
    if not isinstance(schedule, u13.SetpointSchedule) or not isinstance(fixed, u13.FixedSetpoint):
        raise ValueError("compare_control_modes(schedule=SetpointSchedule, fixed=FixedSetpoint)")
    a = scheduled_operation(filt, plant, plenum, intakes, schedule, controller_states)
    b = scheduled_operation(filt, plant, plenum, intakes, fixed, controller_states)
    return {"baseline": a, "fallback_reference": b, "schedule_status": schedule.status,
            "rule": "A9.13 S6.10: scheduled setpoint = baseline control mode; fixed setpoint = fallback / degraded "
                    "mode and comparison reference; the schedule is not frozen"}


# =================================================================================================== A9.13 S6.12 / S6.17
