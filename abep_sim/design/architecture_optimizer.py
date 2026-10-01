"""A9.7 F7 full coupled architecture optimizer (owner directive OD_2026_10_01_A9_7, lane fo_a9_7_f7_f8_coupled_optimizer).

New design-synthesis code. ONE common design vector

    x = [x_intake (F1), x_filter (F2), x_compressor (F3), x_plenum (F4), x_Hall (F5), x_ICP (F6), x_RF (P2 / RFQ v2),
         x_thermal (P3)]

whose blocks, bounds and evidence status are read from the lanes that own them (``design_vector_blocks``), and for every
vector the system objectives of A9.7 F7

    T - D_spacecraft,  P_bus,  m_wet,  Q_reject,  I_e,cap - I_d,max,  life / material indicators

each evaluated or REFUSED with a reason and the minimal evidence that would unlock it (``evaluate_system``). Hard
constraints from the RVM (``HARD_CONSTRAINTS``: < 1.5 kW, < 40 kg wet, >= 12 mN, 25 mN capability, I_e margin > 0,
50 K thermal margin, > 15,000 h firing, plus F1's intake-face drag bound and the drag-compensation condition) FAIL
CLOSED: a constraint that cannot be evaluated is NOT_EVALUATED and never counts as satisfied.

What can be computed today (and is): the evaluable UPSTREAM sub-problem F1 -> F2 -> F3 -> F4 (intake TPMC records,
filter gap-reflection coupling, Gaede compressor cascade, plenum held at a set pressure; every relation is the one
abep_sim.design.plenum_feed uses, called, never copied) over the committed lane grids, giving a multi-objective Pareto
set per (surface scenario, filter case, wall case, plenum set pressure) context (``upstream_context`` /
``pareto_mask``). These are Pareto sets WITHIN THE F3 FRONT-UNION SUBSET of compressor designs (32 of the 48 designs
that pass F3's inlet-independent gates; INT-01 limitation, recorded in F4 / F7 / F9), not over the admissible
compressor space. Every Pareto member carries the list of NOT_EVALUATED system objectives. The full-system ranking
(``rank_full_system``) is implemented (non-dominated sorting layers, no scalarisation, no winner) and REFUSES
(REFUSED_INCOMPLETE) while any system objective of any candidate is not EVALUATED; it is exercised by the tests with
synthetic fixtures labelled SYNTHETIC_TEST_DATA_NOT_EVIDENCE, and a synthetic-only ranking is labelled as such
(mixing synthetic and evidence refuses).

Design decisions recorded here (evidence discipline, CLAUDE.md rules 3, 6, 10; docs/EVIDENCE.md; A9.7 F7):
  * The filter case is a CONTEXT axis, not a searched variable: the only benefit of a filter (contamination / AO
    protection, F2) is NOT_EVALUATED, so comparing a filter against 'none' on flow alone would silently score that TBD
    benefit as zero. Each filter case gets its own Pareto set.
  * The surface scenario (alpha, kernel), the wall O-recombination case and the plenum set pressure P_set (H-1 inlet
    requirement TBD, F5 IFD-F4-01..05) are context axes too: never chosen by the search.
  * No TBD input is converted into an assumed value to obtain an optimum. The upstream numbers are labelled
    PARAMETRIC_SENSITIVITY: they inherit the uncited code-default compressor coefficients (F3), the parametric filter
    cases (F2/F4), the assumed isothermal chain temperature (F4-P-01) and the parametric leak (F4-P-05) exactly as the
    lanes declared them; mass objectives use proxies (intake wall area, plenum volume) where the mass is TBD, and the
    compressor mass of the DragCompressor model (code-default coefficients) is labelled parametric.
  * Thrust T needs an admitted Hall response map. The credible set is EMPTY and P5-N2 v1 is INCONCLUSIVE, so T and
    T - D are NOT_EVALUATED for every vector; x_Hall is bounded (F5 windows, admissibility function) but no objective
    depends on it today, so it is not searched.
  * P_bus uses the A9-02 boundary module abep_sim.bus_boundary_a9 (called, never modified): the official ledger keeps
    the compressor slot TBD (row 22: the compressor ICD has not supplied it) and is PARTIAL_BOUNDARY; a separate,
    labelled parametric-sensitivity ledger books the F3/F4 compressor draw and reports its lower bound only.
  * Mass: allocation, evidence floor, parametric design value and CBE are kept in separate columns (mass/power v2
    rule); m_wet is EVALUATED only from a closed roll-up whose terms are all CBE or measured.

Not wired into archengine; no existing module is modified; golden benchmarks cannot move. Nothing here is a design, a
selection, a winner, a requirement or a PASS.

A9.13 / A9.14 / A9.15 / A9.17 owner decisions applied (A9.16 step 3 design layer; shared rules and decision hashes in
abep_sim/design/upstream_a9_13.py; requirement source docs/requirements/rfp_official/rfp_registration_v1.json):
  * S6.15 / OQ-F78-01 + A9.14 S9.7: HC-08 (AG-13) is a hard STATEWISE constraint T_available(state) -
    D_spacecraft(state) >= 0 evaluated from a ``statewise_T_minus_D`` record (upstream_a9_13.
    statewise_drag_compensation over the required state set; statewise, worst-state and orbit-averaged margins); a
    single T - D number never closes it; a REFERENCE_PARAMETRIC spacecraft drag (S6.18) never closes it.
  * S6.21 / F9-OQ-02: HC-11 (AG-12) is statewise feed-state sufficiency against a VALIDATED H-1 map, NOT_EVALUATED
    until that map exists; there is no fixed mg/s gate (0.38-3.2 mg/s = characterization coverage only).
  * S6.17 / OQ-F78-03: ripple left the upstream Pareto objectives; HC-12 compares it with a measured H-1 tolerance
    (NOT_EVALUATED while TBD). The system comparison is Pareto-only (``system_pareto``); no weighted scalar.
  * S6.16 / OQ-F78-02: robustness over EVERY admitted surface scenario (``require_all_admitted_scenarios``).
  * S6.20 / F9-OQ-01: the robust Pareto set is carried versioned (``robust_pareto_set``); no representative.
  * S6.5 / S6.19: filter context FC-00 is a REFERENCE BOUND (``context_role``); the filter is its own element.
  * S6.8 / S6.11: set pressures <= 0.1 Pa are the sensitivity / fallback branch; the higher-pressure primary direction
    is NOT_EVALUATED_OUT_OF_DOMAIN until admitted transitional evidence exists (``higher_pressure_branch``).
  * A9.15: HC-10 dual propellant capability (ambient air + Xe, two separate tanks / paths; RFP-P18-08).
"""
from __future__ import annotations

import functools
import importlib.util
import json
import math
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from .. import bus_boundary_a9 as bb
from .. import rotor_strength as rs
from ..constants import M_SPECIES
from . import filter_stage as fs
from . import intake_synthesis as isy
from . import plenum_feed as pf
from . import upstream_a9_13 as u13

REPO = Path(__file__).resolve().parents[2]
SCHEMA = "f7_architecture_optimizer_v1"
VERSION = "1.0.0"
LANE = "fo_a9_7_f7_f8_coupled_optimizer"
LANE_KEY = "A9_7_F78"
DIRECTIVE = "docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md"
SPECIES = ("O", "N2", "O2")
STATES = tuple(s.id for s in isy.ENVELOPE_STATES)          # h200_f150 (design state) + the four RFP-band corners
DESIGN_STATE = isy.DESIGN_STATE.id
LABEL_PARAMETRIC = "PARAMETRIC_SENSITIVITY"
SYN_CLASS = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE"
FORBIDDEN_STATUS_WORDS = ("PASS", "SELECTED", "WINNER", "QUALIFIED", "OPTIMUM")

# lane inputs (read; the JSON outputs are the committed lane deliverables)
F1_REL = "docs/design_synthesis/f1_intake/f1_intake_synthesis_v1.json"
F2_REL = "docs/design_synthesis/f2_filter/f2_filter_stage_v1.json"
F3_REL = "docs/design_synthesis/f3_compressor/f3_compressor_synthesis_v1.json"
F3D_REL = "docs/design_synthesis/f3_compressor/f3_compressor_designs_v1.json"
F4_REL = "docs/design_synthesis/f4_plenum/f4_plenum_feed_v1.json"
F5_REL = "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json"
F5_BUILDER_REL = "docs/hardware/h1_freeze_candidate/build_h1_freeze_candidate.py"
F6_REL = "docs/design_synthesis/f6_icp_geometry/f6_icp_geometry_v1.json"
P1_REL = "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json"
P2_REL = "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json"
P3_REL = "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json"
P4_REL = "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json"
MP_REL = "docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json"
RFQ_REL = "docs/procurement/rfq_a9_v2/rfq_a9_v2.json"
RVM_REL = "docs/requirements/rvm_a9/rvm_a9_v1.json"
ENS_REL = "hallthruster_bridge/ensemble/transport_ensemble_v0.json"
VAL_REL = "hallthruster_bridge/validation/VALIDATION_RELEASE_v1.json"
PARITY_REL = "docs/performance/abep_core/parity_report_v1.json"

# ------------------------------------------------------------------------------------------------- vocabularies
EVALUATED = "EVALUATED"
PARAMETRIC_ONLY = "PARAMETRIC_SENSITIVITY_ONLY"           # numbers exist but rest on assumed / parametric inputs
INCOMPLETE = "INCOMPLETE_EVIDENCE"                         # partial terms only (lower bound / allocation)
NOT_EVALUATED = "NOT_EVALUATED"
SYNTHETIC_ONLY = "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE"
OBJECTIVE_STATUSES = (EVALUATED, PARAMETRIC_ONLY, INCOMPLETE, NOT_EVALUATED, SYNTHETIC_ONLY)
RANKABLE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived")

C_MET = "MET_ON_SUPPLIED_VALUES"                           # only on an EVALUATED (or, in a synthetic-only ranking,
#                                                            SYNTHETIC) value or an A9-02 gate verdict
C_VIOLATED = "VIOLATED"
C_NOT_EVALUATED = "NOT_EVALUATED"
# A9.7 consolidated verification round 1 (OPT-01 / SW-01): a comparison on a parametric / assumed / allocation value is
# sensitivity information only. It is reported under its own status and never counts as MET (fail closed).
C_MET_PARAMETRIC = "MET_ON_PARAMETRIC_VALUES_SENSITIVITY_ONLY_NOT_MET"
C_VIOLATED_PARAMETRIC = "VIOLATED_ON_PARAMETRIC_VALUES_SENSITIVITY_ONLY"
CONSTRAINT_STATUSES = (C_MET, C_VIOLATED, C_NOT_EVALUATED, C_MET_PARAMETRIC, C_VIOLATED_PARAMETRIC)

RANK_REFUSED_INCOMPLETE = "REFUSED_INCOMPLETE"
RANK_REFUSED_NO_FEASIBLE = "REFUSED_NO_FEASIBLE_CANDIDATE"
RANK_REFUSED_MIXED = "REFUSED_MIXED_SYNTHETIC_AND_EVIDENCE"
RANK_REFUSED_PARAMETRIC_UPSTREAM = "REFUSED_PARAMETRIC_UPSTREAM_OBJECTIVE"
RANK_COMPUTED = "PARETO_LAYERS_COMPUTED_NOT_A_SELECTION"
RANK_COMPUTED_SYNTHETIC = "PARETO_LAYERS_COMPUTED_SYNTHETIC_TEST_ONLY_NOT_EVIDENCE"
RANK_STATUSES = (RANK_REFUSED_INCOMPLETE, RANK_REFUSED_NO_FEASIBLE, RANK_REFUSED_MIXED, RANK_COMPUTED,
                 RANK_COMPUTED_SYNTHETIC)

CONFIGURATIONS = bb.CONFIGURATIONS                       # hall_c1_reference (control / fallback), hall_icp_neutralizer


class OptimizerError(ValueError):
    """Malformed input to the F7 optimizer (never a physics verdict)."""


@functools.lru_cache(maxsize=64)
def _read_json_cached(path: str, mtime_ns: int) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_json(rel: str, repo: Path = REPO) -> dict:
    """Parsed lane deliverable (cached on path + mtime; callers never mutate the returned object)."""
    p = Path(repo) / rel
    return _read_json_cached(str(p), p.stat().st_mtime_ns)


def _var(vid, block, symbol, value, units, basis, source, evidence_class, status, **extra):
    d = {"id": vid, "block": block, "symbol": symbol, "value": value, "units": units, "basis": basis,
         "source": source, "evidence_class": evidence_class, "status": status}
    d.update(extra)
    return d


# ================================================================================================= design vector blocks
BLOCK_ORDER = ("x_intake", "x_filter", "x_compressor", "x_plenum", "x_Hall", "x_ICP", "x_RF", "x_thermal")
BLOCK_STATES = ("SEARCHED", "CONTEXT_AXIS_NOT_SEARCHED", "BOUNDED_NOT_SEARCHED_NO_EVALUABLE_OBJECTIVE",
                "NOT_SEARCHABLE_BOUNDS_TBD")


def _f5_builder(repo: Path = REPO):
    """The F5 builder module (for its fail-closed geometric_admissibility); imported by path, read-only."""
    spec = importlib.util.spec_from_file_location("_f7_h1_builder", Path(repo) / F5_BUILDER_REL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def design_vector_blocks(repo: Path = REPO) -> list[dict]:
    """The common design vector, block by block, with every variable's value / bounds / TBD, units, basis, source,
    evidence class and status taken from the lane that owns it."""
    f1, f3, f4, f5, f6 = (read_json(r, repo) for r in (F1_REL, F3_REL, F4_REL, F5_REL, F6_REL))
    p3, mp = read_json(P3_REL, repo), read_json(MP_REL, repo)
    blocks = []

    v = f1["design_space"]["variables"]
    blocks.append({"block": "x_intake", "lane": "F1", "path": F1_REL, "state": "SEARCHED", "variables": [
        _var("x_intake.A", "x_intake", "A", v["area_m2"], "m^2", "intake frontal (ram) area grid", f"{F1_REL} "
             "design_space.variables.area_m2", "assumed", "SEARCHED (F1 grid)"),
        _var("x_intake.d", "x_intake", "d", v["d_mm"], "mm", "channel diameter; flow, drag and wall area are "
             "d-invariant at fixed L/d (F1-02), so d is collapsed in the coupled search", f"{F1_REL} design_space",
             "assumed", "COLLAPSED (d-invariant objectives)"),
        _var("x_intake.L_over_d", "x_intake", "L/d", v["L_over_d"], "-", "channel aspect ratio grid (frozen TPMC "
             "surface nodes)", f"{F1_REL} design_space", "assumed", "SEARCHED (F1 grid)"),
        _var("x_intake.phi", "x_intake", "phi", v["phi"], "-", "open-area fraction grid (frozen surface nodes)",
             f"{F1_REL} design_space", "assumed", "SEARCHED (F1 grid)"),
        _var("x_intake.alpha_kernel", "x_intake", "(alpha, kernel)", f1["design_space"]["scenario_axes"], "-",
             "surface accommodation and gas-surface kernel: TBD evidence (F1-P-07 / F1-P-08), carried as scenario "
             "axis, never optimised", f"{F1_REL} items F1-P-07, F1-P-08", "TBD", "CONTEXT_AXIS (uncertainty, F8)"),
        _var("x_intake.theta", "x_intake", "theta", [0.0, 5.0], "deg", "pointing error: no AOCS budget (F1-P-09); "
             "0 deg everywhere, 5 deg (largest frozen node) at the design state only", f"{F1_REL} items F1-P-09",
             "TBD", "CONTEXT_AXIS (uncertainty, F8)"),
        _var("x_intake.structure", "x_intake", "(t_wall, coating, support)", "TBD", "mixed", "structural inputs "
             "of the geometric mass model are TBD (F1-P-02..05); the code-default case is a labelled parametric "
             "sensitivity case; the wall area is the mass proxy", f"{F1_REL} items F1-P-02..05", "TBD", "TBD"),
    ]})

    blocks.append({"block": "x_filter", "lane": "F2 (through F4 filter cases)", "path": F2_REL,
                   "state": "CONTEXT_AXIS_NOT_SEARCHED", "variables": [
        _var("x_filter.case", "x_filter", "filter case", [f.case_id for f in pf.filter_cases()], "-",
             "F4 filter cases built through F2's public API: 'none' (FC-00 REFERENCE BOUND only, A9.13 S6.5), "
             "loss-free parametric screens tau 0.9 / 0.7 / 0.5 and the repository placeholder law "
             "(PLACEHOLDER_NOT_A_FLIGHT_DESIGN). Every real filter concept is TBD in F2. Context axis: the filter's "
             "protection benefit is NOT_EVALUATED, so a flow-only comparison against 'none' would score that TBD "
             "benefit as zero", f"{F2_REL}; abep_sim/design/plenum_feed.py filter_cases()", "TBD",
             "CONTEXT_AXIS (every filter number is PARAMETRIC_SENSITIVITY)"),
        _var("x_filter.mass", "x_filter", "m_filter", "TBD", "kg", "filter areal mass / face area TBD (F2)",
             F2_REL, "TBD", "TBD"),
        _var("x_filter.role", "x_filter", "role", {f.case_id: f.role for f in pf.filter_cases()}, "-",
             "A9.13 S6.4 / S6.5 / S6.19: separate production-path element between IF-A1 and IF-A2; baseline "
             "inert / low-recombination; catalytic O -> O2 research variant only; FC-00 reference bound only",
             "abep_sim/design/filter_stage.py ROLES / INTERFACE_POSITION", "definition", "DEFINITION"),
    ]})

    sv = {x["id"]: x for x in f3["search_variables"]}
    f4sv = {x["id"]: x for x in f4["search_variables"]}
    comp_vars = [
        _var("x_compressor.design_id", "x_compressor", "design", f4sv["x_compressor"]["value"], "-",
             "union of the F3 per-case Pareto ids (the compressor set F4 coupled; N_drag = 0 for every member: no "
             "drag-stage design is feasible, F3-01)", f"{F4_REL} search_variables x_compressor; {F3D_REL}",
             "model-derived (PARAMETRIC_SENSITIVITY)", "SEARCHED (F3 front union only: 32 of the 48 designs passing F3's "
             "inlet-independent gates; sets are Pareto within this subset, INT-01)")]
    for k in ("N_turbo", "A_turbo", "R_turbo", "N_drag", "R_rotor", "RPM", "h", "w", "L", "xi"):
        if k in sv:
            x = sv[k]
            comp_vars.append(_var(f"x_compressor.{k}", "x_compressor", k, x["value"], x["units"], x["basis"],
                                  f"{F3_REL} search_variables {k} ({x['source']})", x["evidence_class"],
                                  x["status"]))
    fixed = [c for c in f3["coefficients"] if c.get("role") == "FIXED_CODE_DEFAULT"]
    comp_vars.append(_var("x_compressor.fixed_coefficients", "x_compressor", "DragCompressor coefficients",
                          {c["id"]: c["value"] for c in fixed}, "mixed", "uncited code defaults (not searched: no "
                          "accessed open source gives a value or a range, compressor_downselect CD-01); local "
                          "elasticities only in F8", f"{F3_REL} coefficients (role FIXED_CODE_DEFAULT)", "assumed",
                          "FIXED_CODE_DEFAULT_UNCITED"))
    comp_vars.append(_var("x_compressor.hub_ratio", "x_compressor", "nu = R_hub / R_tip",
                          list(cs_hub_ratios()), "-", "A9.13 S6.7 explicit hub ratio / blade span; searched values are a "
                          "declared PARAMETRIC_SENSITIVITY coverage of [0, 1); nu = 0 = zero-hub analytical bound only; "
                          "bounds TBD from shaft / bearing, rotor structural, motor / interface, manufacturability and "
                          "pumping interfaces", "abep_sim/design/compressor_synthesis.py HUB_RATIO_PARAMETRIC",
                          "assumed", "SEARCHED_IN_F3 (PARAMETRIC_SENSITIVITY; the F7 front-union subset predates it)"))
    blocks.append({"block": "x_compressor", "lane": "F3", "path": F3_REL, "state": "SEARCHED",
                   "variables": comp_vars})

    pv = [_var(f"x_plenum.{x['id'].split('.', 1)[-1]}", "x_plenum", x["id"].split(".", 1)[-1], x["value"],
               x["units"], x["basis"], f"{F4_REL} search_variables {x['id']}", x["evidence_class"], x["status"])
          for x in f4["search_variables"] if x["id"].startswith("x_plenum.")]
    pv.append(_var("x_plenum.P_set", "x_plenum", "P_set", list(UPSTREAM_TARGETS_PA), "Pa", "plenum set pressure "
                   "(H-1 required inlet state TBD, F4-P-10 / F5 IFD-F4-01..05): requirement-level context axis of "
                   "the <= 0.1 Pa sensitivity / fallback branch (A9.13 S6.11); the higher-pressure primary direction "
                   "is NOT_EVALUATED_OUT_OF_DOMAIN (S6.8) and not repeated here",
                   f"{F4_REL} requirement_sweep.P_req_Pa (<= 0.1 Pa)", "TBD", "CONTEXT_AXIS (requirement sweep)"))
    pv.append(_var("x_plenum.wall_gamma", "x_plenum", "gamma_O wall", "TBD", "-", "plenum wall O recombination "
                   "probability (F4-P-06): WALL-G0 (gamma = 0 bound, owner H1F-IN-02 lining) nominal context, "
                   "WALL-TI64-DB (uncited DB prior) sensitivity context", f"{F4_REL} items F4-P-06", "TBD",
                   "CONTEXT_AXIS"))
    pv.append(_var("x_plenum.mass", "x_plenum", "m_plenum", "TBD", "kg", "plenum mass TBD (F4-P-16); volume is the "
                   "mass proxy", f"{F4_REL} items F4-P-16", "TBD", "TBD"))
    pv.append(_var("x_plenum.control_mode", "x_plenum", "control mode", dict(u13.CONTROL_MODES), "-",
                   "A9.13 S6.10: orbit-state-scheduled setpoint = baseline (controller-available inputs only, "
                   "schedule NOT_FROZEN); fixed setpoint = fallback / reference", "abep_sim/design/plenum_feed.py "
                   "scheduled_operation / compare_control_modes", "definition", "DEFINITION"))
    blocks.append({"block": "x_plenum", "lane": "F4", "path": F4_REL, "state": "SEARCHED", "variables": pv})

    xd = f5["x_hall_design_space"]["definition"]
    hv = [_var(f"x_Hall.{k}", "x_Hall", k, {"window": b}, "mm", "F5 x_Hall bound (window, OPEN)",
               f"{F5_REL} x_hall_design_space.definition.variables.{k}", "model-derived", "OPEN (window)")
          for k, b in xd["variables"].items()]
    hv.append(_var("x_Hall.constraints", "x_Hall", "geometric windows", xd["constraints"], "mixed",
                   "area, d/h, L/h windows and the inner-coil solid-core floor; admissibility via the F5 builder's "
                   "geometric_admissibility (fail closed)", f"{F5_REL} x_hall_design_space.definition.constraints",
                   "model-derived", "OPEN"))
    rollup = f5["freeze_rollup"]["counts"]
    hv.append(_var("x_Hall.freeze_rollup", "x_Hall", "77 H-1 parameters", rollup, "-", "freeze-status counts of the "
                   "H-1 engineering-article parameters (FREEZE_CANDIDATE items are owner rules, not design values)",
                   f"{F5_REL} freeze_rollup", "assumed", "NOT_FROZEN"))
    blocks.append({"block": "x_Hall", "lane": "F5", "path": F5_REL,
                   "state": "BOUNDED_NOT_SEARCHED_NO_EVALUABLE_OBJECTIVE", "variables": hv,
                   "not_evaluated": xd["not_evaluated"]})

    iv = [_var(f"x_ICP.{x['symbol']}", "x_ICP", x["symbol"], {"lo": x["bounds"]["lo"], "hi": x["bounds"]["hi"]},
               x["units"], x["name"], f"{F6_REL} design_vector.variables {x['id']}", x["bounds"]["evidence_class"]
               or "TBD", x["bounds"]["status"], requires=x["bounds"]["requires"])
          for x in f6["design_vector"]["variables"]]
    blocks.append({"block": "x_ICP", "lane": "F6", "path": F6_REL, "state": "NOT_SEARCHABLE_BOUNDS_TBD",
                   "variables": iv})

    chain = mp["power"]["icp_rf_chain"]
    rv = [
        _var("x_RF.frequency", "x_RF", "f_RF", bb.RF_FREQUENCY_HZ, "Hz", "13.56 MHz ICP drive (row 72 / A9)",
             f"{MP_REL} items MPV2-P07; abep_sim/bus_boundary_a9.py RF_FREQUENCY_HZ", "owner-allocation",
             "OWNER_GIVEN"),
        _var("x_RF.chain_topology", "x_RF", "RF chain", chain["chain"], "-", "flight-representative DC-RF source, "
             "directional coupler, 50-ohm line, local adjustable match, antenna (A9.2 / A9.3 decisions)",
             f"{MP_REL} power.icp_rf_chain", "assumed", "LOCAL_MATCH_SELECTED_FOR_DEVELOPMENT"),
        _var("x_RF.component_ratings", "x_RF", "ratings", "TBD", "W; V; A", "RF component ratings",
             f"{P2_REL}; {RFQ_REL}", "TBD", "TBD_AFTER_IMPEDANCE_MAP"),
        _var("x_RF.source_efficiency", "x_RF", "eta_DC->RF", "TBD", "-", chain["flight_source_efficiency"],
             f"{MP_REL} items MPV2-P08", "TBD", "TBD"),
        _var("x_RF.lab_forward_range", "x_RF", "P_fwd lab", list(bb.LAB_RF_FORWARD_W_RANGE), "W", "laboratory "
             "source + inline chain sizing: a TEST capability, never a flight allowance (row 72)",
             "abep_sim/bus_boundary_a9.py LAB_RF_FORWARD_W_RANGE", "owner-allocation", "TEST_CAPABILITY_ONLY"),
    ]
    blocks.append({"block": "x_RF", "lane": "P2 framework / RFQ v2 / mass-power v2", "path": P2_REL,
                   "state": "NOT_SEARCHABLE_BOUNDS_TBD", "variables": rv})

    tv = []
    for it in p3["items"]:
        if it["id"].split("-")[1] in ("G", "R", "K", "M"):
            val = it["value"] if not isinstance(it["value"], (dict, list)) else "see source"
            ec = "TBD" if str(it.get("status", "")).startswith(("TBD", "PENDING")) else \
                ("owner-allocation" if it.get("status") == "OWNER_GIVEN" else "assumed")
            tv.append(_var(f"x_thermal.{it['id']}", "x_thermal", it["id"], val, it.get("units", "-"),
                           it.get("name", ""), f"{P3_REL} items {it['id']}", ec, it.get("status")))
    blocks.append({"block": "x_thermal", "lane": "P3", "path": P3_REL, "state": "NOT_SEARCHABLE_BOUNDS_TBD",
                   "variables": tv})
    if [b["block"] for b in blocks] != list(BLOCK_ORDER):
        raise RuntimeError("design-vector block order")
    return blocks


def cs_hub_ratios() -> tuple:
    from . import compressor_synthesis as cs
    return cs.HUB_RATIO_PARAMETRIC


def hall_admissibility(h_mm: float, d_mean_mm: float, L_mm: float, assumptions: str = "worst_case_assumptions",
                       repo: Path = REPO) -> dict:
    """x_Hall geometric admissibility through the F5 builder's fail-closed function (never a PASS; every Hall
    performance quantity stays NOT_EVALUATED)."""
    return _f5_builder(repo).geometric_admissibility(h_mm, d_mean_mm, L_mm, assumptions)


# ================================================================================================= upstream inputs
UPSTREAM_TARGETS_PA = (0.002, 0.005, 0.01, 0.02, 0.05, 0.1)   # F4 requirement sweep up to the 0.1 Pa domain cap
VOLUMES_M3 = (1e-3, 1e-2, 1e-1)                                # F4 search grid x_plenum.V
WALL_CASES = ("WALL-G0", "WALL-TI64-DB")                       # F4-P-06 parametric cases
UPSTREAM_OBJECTIVES = (
    ("mdot_delivered_min_kgps", "max", "kg/s", "delivered (valve) total flow, minimum over the five orbit states at "
     "one plenum set pressure (single setpoint for all states)"),
    ("drag_intake_max_N", "min", "N", "intake-face drag, maximum over the five orbit states (F1 convention: full "
     "aperture, spacecraft body excluded)"),
    ("P_compressor_el_max_W", "min", "W", "compressor electrical input (DragCompressor model, code-default "
     "coefficients), maximum over states"),
    ("m_compressor_max_kg", "min", "kg", "compressor mass of the DragCompressor model (code-default coefficients; "
     "PARAMETRIC, not a CBE), maximum over states (torque-dependent motor term)"),
    ("intake_wall_area_m2", "min", "m^2", "intake honeycomb wall area 2 phi A L/d: mass proxy (structural inputs "
     "TBD; monotone for any positive wall areal mass)"),
    ("plenum_V_m3", "min", "m^3", "plenum volume: required-volume and mass proxy (plenum mass TBD, F4-P-16)"),
)
# A9.13 S6.17: ripple is a hard feed-quality constraint against a measured H-1 tolerance (HC-12), never a Pareto
# objective; it is still computed and reported on every member. Heat-rejection burden: NOT_EVALUATED (P3); its only
# upstream partial term is bounded by the compressor electrical input already in P_compressor_el_max_W.
REPORTED_CONSTRAINT_COLUMNS = ("ripple_transfer_shaft",)
OBJ_KEYS = tuple(o[0] for o in UPSTREAM_OBJECTIVES)
OBJ_SENSE = {o[0]: o[1] for o in UPSTREAM_OBJECTIVES}
UPSTREAM_STATUS_FEASIBLE = pf.ST_FEASIBLE


@dataclass
class UpstreamInputs:
    f1: dict
    candidates: tuple            # d-collapsed F1 candidate ids A{A}_Ld{L}_phi{phi}
    geometry: dict               # candidate -> (A, L/d, phi)
    scenarios: tuple
    records: dict                # (candidate, scenario, state) -> pf.IntakeState
    plants: dict                 # design id -> pf.CompressorPlant
    designs: dict                # design id -> F3 design grid record
    filters: dict                # case id -> pf.FilterCase
    drag_per_area: dict          # (scenario, L/d, phi, state) -> (drag per m^2 [N], se per m^2 [N])
    species_rows: list = field(repr=False, default_factory=list)


def _cid(A: float, Ld: float, phi: float) -> str:
    return pf.f1_candidate_id(A, Ld, phi)


def drag_table(f1: dict) -> dict:
    """Per-state intake-face drag per unit frontal area from the committed F1 species table (theta 0):
    D/A = q sum_s w_s C_D,s with q = 1/2 rho V^2 and w_s the free-stream mass fractions of the frozen atmosphere
    (the F1 candidate_state_metrics expression; reproduces F1 candidate_metrics drag_N to the 6-digit rounding, test).
    SE combined in quadrature from C_D_species_se."""
    cols = f1["species_table"]["columns"]
    atm = {s.id: s.atm() for s in isy.ENVELOPE_STATES}
    wkey = {"O": "fO", "N2": "fN2", "O2": "fO2"}
    acc: dict = {}
    for row in f1["species_table"]["rows"]:
        r = dict(zip(cols, row))
        if r["theta_deg"] != 0.0:
            continue
        a = atm[r["state_id"]]
        q = 0.5 * a["rho"] * a["V"] ** 2
        k = (f"{r['scattering']}_a{r['alpha']:g}", float(r["L_over_d"]), float(r["phi"]), r["state_id"])
        d, v = acc.get(k, (0.0, 0.0))
        se = r["C_D_species_se"] if r["C_D_species_se"] is not None else float("nan")
        acc[k] = (d + q * a[wkey[r["species"]]] * r["C_D_species"], v + (q * a[wkey[r["species"]]] * se) ** 2)
    return {k: (d, math.sqrt(v)) for k, (d, v) in acc.items()}


def load_upstream_inputs(repo: Path = REPO) -> UpstreamInputs:
    f1 = read_json(F1_REL, repo)
    areas = tuple(float(a) for a in f1["design_space"]["variables"]["area_m2"])
    recs = pf.load_f1_records(f1, areas)
    records = {(r.candidate, r.scenario, r.state): r for r in recs}
    geom = {}
    for A in areas:
        for Ld in f1["design_space"]["variables"]["L_over_d"]:
            for phi in f1["design_space"]["variables"]["phi"]:
                geom[_cid(A, float(Ld), float(phi))] = (A, float(Ld), float(phi))
    cands = tuple(sorted(geom, key=lambda c: geom[c]))
    scenarios = tuple(f1["pareto"]["envelope"].keys())
    for c in cands:
        for sc in scenarios:
            for st in STATES:
                if (c, sc, st) not in records:
                    raise RuntimeError(f"F1 record missing for {c} {sc} {st}")
    f4 = read_json(F4_REL, repo)
    ids = [x for x in f4["search_variables"] if x["id"] == "x_compressor"][0]["value"]
    grid = {x["id"]: x for x in read_json(F3D_REL, repo)["design_grid"]}
    plants = {i: pf.CompressorPlant.from_design(grid[i]) for i in ids}
    filters = {f.case_id: f for f in pf.filter_cases()}
    return UpstreamInputs(f1=f1, candidates=cands, geometry=geom, scenarios=scenarios, records=records, plants=plants,
                          designs={i: grid[i] for i in ids}, filters=filters, drag_per_area=drag_table(f1))


def wall_gamma(wall: str) -> float:
    g = {"WALL-G0": 0.0, "WALL-TI64-DB": pf.DB["Ti6Al4V"].gamma_O(pf.T_CHAIN_K)}
    if wall not in g:
        raise OptimizerError(f"unknown wall case {wall!r}")
    return g[wall]


def plenum(V: float, wall: str) -> pf.Plenum:
    return pf.Plenum(float(V), wall_gamma(wall), wall, pf.RES_DEFAULTS["leak_area_m2"])


def ripple_transfer_arrays(side_e: Mapping, plant: pf.CompressorPlant, pl: pf.Plenum, a_eq) -> np.ndarray:
    """Vectorized twin of plenum_feed.ripple_transfer (same expression; equality pinned by a test): least attenuated
    species of 1 / sqrt(1 + (2 pi f tau_s)^2), tau_s = V / (k_s + G_s + leak_s (+ k_rec for O)), f = shaft frequency."""
    ch = plant.characteristic()
    CL = plant.leak_m3_s
    a_eq = np.asarray(a_eq, dtype=float)
    out = None
    for s in SPECIES:
        A, B = ch[s]
        alpha, beta = A / B + CL, 1.0 / B + CL
        e = np.asarray(side_e[s], dtype=float)
        k = e * beta / (e + alpha)
        g = pl.feed_c(s) * a_eq + pl.leak_m3_s(s) + (pl.k_rec_m3_s() if s == "O" else 0.0)
        tau = pl.volume_m3 / (k + g)
        tr = 1.0 / np.sqrt(1.0 + (2.0 * math.pi * plant.shaft_hz * tau) ** 2)
        out = tr if out is None else np.maximum(out, tr)
    return out


def intake_mass_code_default(A: float, Ld: float, phi: float) -> float:
    """F1 geometric intake mass under the labelled code-default structural case (PARAMETRIC_SENSITIVITY_CASE; every
    structural input except the Al density is uncited). d-invariant at fixed L/d (test)."""
    d0 = isy.GeometryCandidate(A, 10.0, Ld, phi)
    return isy.intake_mass(d0, isy.STRUCTURAL_CODE_DEFAULT)["m_intake_kg"]


def design_id(cand: str, filt: str, comp: str, V: float, P: float) -> str:
    return f"{cand}|{filt}|{comp}|V{V:g}|P{P:g}"


def context_id(scenario: str, filt: str, wall: str, P: float) -> str:
    return f"{scenario}|{filt}|{wall}|P{P:g}"


SYSTEM_NOT_EVALUATED_CODES = ("T_minus_D", "P_bus", "m_wet", "Q_reject", "I_e_margin", "life_material")


def upstream_context(inp: UpstreamInputs, scenario: str, filt: str, wall: str, volumes=VOLUMES_M3,
                     targets=UPSTREAM_TARGETS_PA, candidates=None, compressors=None) -> dict:
    """Evaluate every upstream vector (candidate x compressor x V x P_set) of ONE (scenario, filter, wall) context.

    Calls plenum_feed.steady_sweep (the F4 fail-closed gates: F1 per-state feasibility, domain cap, dead-head,
    characteristic, stage domain, feed Knudsen, thermal) at every orbit state. A vector is
    FEASIBLE_UNDER_PARAMETRIC_SENSITIVITY_INPUTS only when every state is feasible at the one set pressure; otherwise
    its reasons (union over states) are kept and it never enters a Pareto set. Returns column arrays over the flattened
    (candidate, compressor, V, target) grid, in that nesting order."""
    cands = tuple(candidates or inp.candidates)
    comps = tuple(compressors or inp.plants)
    if scenario not in inp.scenarios:
        raise OptimizerError(f"unknown scenario {scenario!r}")
    fc = inp.filters[filt]
    recs = [inp.records[(c, scenario, st)] for c in cands for st in STATES]
    side = pf.intake_side(recs, fc)
    f1ok = np.array([r.f1_status == "FEASIBLE_AT_STATE" for r in recs])
    nC, nS, nT, nV, nK = len(cands), len(STATES), len(targets), len(volumes), len(comps)
    gam = wall_gamma(wall)
    shape = (nC, nK, nV, nT)
    out = {k: np.full(shape, np.nan) for k in ("mdot_delivered_min_kgps", "P_compressor_el_max_W",
                                               "m_compressor_max_kg", "ripple_transfer_shaft", "xO_flow_min",
                                               "xO_flow_max", "a_eq_design_m2", "deadhead_margin_min",
                                               "kn_upper_min", "T_comp_max_K", "mdot_delivered_design_kgps")}
    bits_all = np.zeros(shape, dtype=np.int64)
    d_idx = STATES.index(DESIGN_STATE)
    side_e_design = {s: side["e"][s].reshape(nC, nS)[:, d_idx] for s in SPECIES}
    for ki, comp in enumerate(comps):
        plant = inp.plants[comp]
        cache = None
        for vi, V in enumerate(volumes):
            pl = plenum(V, wall)
            if cache is None or gam > 0.0:      # WALL-G0 steady state is volume-independent (F4 test); reuse it
                cache = pf.steady_sweep(side, plant, pl, targets, f1ok)
            sw = cache
            bits = sw["bits"].reshape(nC, nS, nT)
            ok = (bits == 0)
            all_ok = ok.all(axis=1)
            bits_all[:, ki, vi, :] = np.bitwise_or.reduce(bits, axis=1)
            md = sw["mdot_total_kgps"].reshape(nC, nS, nT)
            pel = sw["P_el_W"].reshape(nC, nS, nT)
            mc = sw["m_compressor_kg"].reshape(nC, nS, nT)
            tc = sw["T_comp_K"].reshape(nC, nS, nT)
            xo = sw["x_s_flow_mole"]["O"].reshape(nC, nS, nT)
            pd = sw["p_deadhead_Pa"].reshape(nC, nS, nT)
            kn = sw["Kn_upper"].reshape(nC, nS, nT)
            aeq = sw["a_eq_m2"].reshape(nC, nS, nT)
            tg = np.asarray(targets, dtype=float)[None, None, :]
            with np.errstate(all="ignore"), warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)

                def red(arr, fn):
                    return np.where(all_ok, fn(np.where(ok, arr, np.nan), axis=1), np.nan)
                out["mdot_delivered_min_kgps"][:, ki, vi, :] = red(md, np.nanmin)
                out["P_compressor_el_max_W"][:, ki, vi, :] = red(pel, np.nanmax)
                out["m_compressor_max_kg"][:, ki, vi, :] = red(mc, np.nanmax)
                out["T_comp_max_K"][:, ki, vi, :] = red(tc, np.nanmax)
                out["xO_flow_min"][:, ki, vi, :] = red(xo, np.nanmin)
                out["xO_flow_max"][:, ki, vi, :] = red(xo, np.nanmax)
                out["deadhead_margin_min"][:, ki, vi, :] = red((pd - tg) / tg, np.nanmin)
                out["kn_upper_min"][:, ki, vi, :] = red(kn, np.nanmin)
                a_d = aeq[:, d_idx, :]
                out["a_eq_design_m2"][:, ki, vi, :] = np.where(all_ok, a_d, np.nan)
                out["mdot_delivered_design_kgps"][:, ki, vi, :] = np.where(all_ok, md[:, d_idx, :], np.nan)
                rip = ripple_transfer_arrays({s: side_e_design[s][:, None] for s in SPECIES}, plant, pl, a_d)
                out["ripple_transfer_shaft"][:, ki, vi, :] = np.where(all_ok, rip, np.nan)
    # per-candidate quantities (independent of compressor / plenum)
    drag = np.empty(nC)
    drag_se = np.empty(nC)
    capt = np.empty(nC)
    for ci, c in enumerate(cands):
        A, Ld, phi = inp.geometry[c]
        dd = [inp.drag_per_area[(scenario, Ld, phi, st)] for st in STATES]
        j = int(np.argmax([x[0] for x in dd]))
        drag[ci], drag_se[ci] = A * dd[j][0], A * dd[j][1]
        capt[ci] = min(sum(inp.records[(c, scenario, st)].mdot_fwd_kgps.values()) for st in STATES)
    feasible = (bits_all == 0)
    bcast = lambda a: np.broadcast_to(a[:, None, None, None], shape)
    out["drag_intake_max_N"] = np.where(feasible, bcast(drag), np.nan)
    out["drag_intake_max_se_N"] = np.where(feasible, bcast(drag_se), np.nan)
    out["mdot_captured_min_kgps"] = np.where(feasible, bcast(capt), np.nan)
    wall_area = np.array([2.0 * inp.geometry[c][2] * inp.geometry[c][0] * inp.geometry[c][1] for c in cands])
    out["intake_wall_area_m2"] = np.where(feasible, bcast(wall_area), np.nan)
    out["plenum_V_m3"] = np.where(feasible, np.broadcast_to(np.asarray(volumes, float)[None, None, :, None], shape),
                                  np.nan)
    return {"scenario": scenario, "filter": filt, "wall": wall, "candidates": cands, "compressors": comps,
            "volumes": tuple(volumes), "targets": tuple(targets), "bits": bits_all, "feasible": feasible,
            "arrays": out, "context_role": context_role(fc),
            "design_direction": [u13.classify_pressure_target(t)["design_direction"] for t in targets]}


def context_role(fc: pf.FilterCase) -> str:
    """A9.13 S6.5: FC-00 contexts are reference bounds, never admissible flight architectures."""
    return "REFERENCE_BOUND_FC00_NOT_ADMISSIBLE" if fc.reference_bound_only else "ARCHITECTURE_CONTEXT"


def higher_pressure_branch(targets_Pa=(0.2, 0.5, 1.0)) -> list[dict]:
    """A9.13 S6.11 primary direction, recorded as NOT_EVALUATED_OUT_OF_DOMAIN until S6.8 closes (no number is
    produced or extrapolated). The default targets only illustrate the record; they are not requirements."""
    return [u13.classify_pressure_target(t) for t in targets_Pa]


def pareto_mask(F: np.ndarray, senses: Sequence[str], chunk: int = 256) -> np.ndarray:
    """Non-dominated rows of F (n x k) under weak dominance; 'max' objectives are negated. Ties (identical rows) are
    all kept. Rows with any non-finite value are never non-dominated (fail closed). Deterministic."""
    F = np.asarray(F, dtype=float)
    if F.ndim != 2 or F.shape[1] != len(senses):
        raise OptimizerError("objective matrix shape")
    G = F * np.array([-1.0 if s == "max" else 1.0 for s in senses])[None, :]
    finite = np.isfinite(G).all(axis=1)
    keep = finite.copy()
    idx_f = np.nonzero(finite)[0]
    H = G[idx_f]
    for i0 in range(0, len(idx_f), chunk):
        blk = H[i0:i0 + chunk]
        le = (H[None, :, :] <= blk[:, None, :]).all(axis=2)
        lt = (H[None, :, :] < blk[:, None, :]).any(axis=2)
        dom = (le & lt).any(axis=1)
        keep[idx_f[i0:i0 + chunk]] = ~dom
    return keep


def context_pareto(ctx: dict, objectives=OBJ_KEYS) -> dict:
    """Pareto set per set pressure of one evaluated context. Returns {P_set: {n_evaluated, n_feasible, status counts,
    reason counts, members: [row dicts]}}; every member carries the NOT_EVALUATED system objectives."""
    arr = ctx["arrays"]
    cands, comps, vols, tgs = ctx["candidates"], ctx["compressors"], ctx["volumes"], ctx["targets"]
    res = {}
    for ti, P in enumerate(tgs):
        sl = (slice(None), slice(None), slice(None), ti)
        feas = ctx["feasible"][sl]
        bits = ctx["bits"][sl]
        idx = np.argwhere(feas)
        F = np.column_stack([arr[k][sl][feas] for k in objectives]) if len(idx) else np.zeros((0, len(objectives)))
        mask = pareto_mask(F, [OBJ_SENSE[k] for k in objectives]) if len(idx) else np.zeros(0, bool)
        status_counts: dict = {}
        reason_counts: dict = {}
        for b in bits.ravel():
            rs = pf.reasons_from_bits(int(b))
            st = pf.status_from_reasons(rs)
            status_counts[st] = status_counts.get(st, 0) + 1
            for r in rs:
                reason_counts[r] = reason_counts.get(r, 0) + 1
        members = []
        for (ci, ki, vi), m in zip(idx, mask):
            if not m:
                continue
            g = (ci, ki, vi, ti)
            row = {"design_id": design_id(cands[ci], ctx["filter"], comps[ki], vols[vi], P),
                   "candidate": cands[ci], "compressor": comps[ki], "V_m3": vols[vi], "P_set_Pa": P}
            for k in objectives:
                row[k] = float(arr[k][g])
            for k in ("mdot_captured_min_kgps", "drag_intake_max_se_N", "mdot_delivered_design_kgps", "xO_flow_min",
                      "xO_flow_max", "deadhead_margin_min", "kn_upper_min", "T_comp_max_K", "a_eq_design_m2"):
                row[k] = float(arr[k][g])
            for k in REPORTED_CONSTRAINT_COLUMNS:
                if k in arr:
                    row[k] = float(arr[k][g])
            row["ripple_feed_quality"] = u13.ripple_feed_quality(row.get("ripple_transfer_shaft"), u13.VALUE_PARAMETRIC,
                                                                 u13.h1_tolerance_tbd("ripple"))["status"]
            row["characterization_coverage"] = u13.characterization_coverage(row["mdot_delivered_min_kgps"])["position"]
            row["context_role"] = ctx.get("context_role", "ARCHITECTURE_CONTEXT")
            row["system_not_evaluated"] = list(SYSTEM_NOT_EVALUATED_CODES)
            members.append(row)
        members.sort(key=lambda r: r["design_id"])
        res[P] = {"context_id": context_id(ctx["scenario"], ctx["filter"], ctx["wall"], P),
                  "n_evaluated": int(bits.size), "n_feasible": int(feas.sum()), "status_counts": status_counts,
                  "reason_counts": reason_counts, "n_pareto": len(members), "members": members}
    return res


# ================================================================================================= system objectives
def _obj(name, status, value=None, units="", evidence_class=None, source=None, reason=None, unlock=None, **extra):
    if status not in OBJECTIVE_STATUSES:
        raise OptimizerError(f"objective status {status!r}")
    d = {"objective": name, "status": status, "value": value, "units": units, "evidence_class": evidence_class,
         "source": source, "reason": reason, "unlock": unlock}
    d.update(extra)
    return d


def supplied_objective(name: str, rec: Mapping | None, units: str) -> dict | None:
    """Admit a caller-supplied objective record {value, evidence_class, source, parametric?}. Synthetic data is
    labelled SYNTHETIC_TEST_ONLY_NOT_EVIDENCE; parametric / assumed / allocation values never become EVALUATED."""
    if rec is None:
        return None
    for k in ("value", "evidence_class", "source"):
        if k not in rec:
            raise OptimizerError(f"supplied {name}: '{k}' missing")
    v = rec["value"]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
        raise OptimizerError(f"supplied {name}: value must be a finite number (a TBD is not supplied)")
    ec = rec["evidence_class"]
    if ec == SYN_CLASS:
        st = SYNTHETIC_ONLY
    elif rec.get("parametric") or ec not in RANKABLE_CLASSES:
        st = PARAMETRIC_ONLY
    else:
        st = EVALUATED
    return _obj(name, st, float(v), units, ec, rec["source"], reason=None if st == EVALUATED else
                f"supplied value of class {ec!r}{' (parametric)' if rec.get('parametric') else ''} is not rankable "
                "evidence", supplied=True)


# ----------------------------------------------------------------------------------------------- Hall / T - D
def hall_response_status(repo: Path = REPO) -> dict:
    """Admitted Hall transport members (credible set) and the P5-N2 v1 decision; read-only."""
    ens = read_json(ENS_REL, repo)
    members = list(ens.get("members", []))
    try:
        val = read_json(VAL_REL, repo)
        dec = val.get("decision")
    except FileNotFoundError:
        dec = None
    return {"admitted_members": members, "credible_set": "EMPTY" if not members else "NON_EMPTY",
            "p5_n2_v1_decision": dec, "sources": [ENS_REL, VAL_REL]}


def hall_gated_thrust(name: str, rec: Mapping | None, repo: Path = REPO) -> dict | None:
    """Route a supplied thrust record through the same admitted-Hall-member check as thrust_minus_drag (OPT-01): a
    non-synthetic thrust record is refused (NOT_EVALUATED) while the credible Hall set is EMPTY, so HC-01 / HC-02
    can never be met on a Hall performance prediction without an admitted transport member."""
    if rec is None or rec["status"] == SYNTHETIC_ONLY:
        return rec
    hall = hall_response_status(repo)
    if hall["admitted_members"]:
        return rec
    return _obj(name, NOT_EVALUATED, None, rec.get("units", "N"), reason=f"a {rec['status']} thrust record was "
                f"supplied but the credible Hall set is EMPTY (no admitted transport member: refused)",
                unlock=[UNLOCK["T"]], refused_supplied_status=rec["status"])


UNLOCK = {
    "T": "an ADMITTED Hall transport member (credible set non-empty: a screening candidate promoted by pre-registered "
         "predictive evidence, CLAUDE.md next-work 1/3) AND a design-specific Hall map (own H-1 geometry and B(z), "
         "HallMap trustworthy, chemistry_trustworthy) whose domain contains the offered feed state; or a measured H-1 "
         "thrust on the delivered feed (hardware pivot Phase 1-3, thrust stand RFQ-01)",
    "D_spacecraft": "spacecraft frontal area / body + array drag model (F1-ID-08: no spacecraft geometry in the "
                    "repository) at the same orbit states",
    "P_bus": "every installed A9-02 slot load and supply efficiency at a registered condition (Hall discharge from "
             "the registered H-1 envelope, coils from the frozen MC-1, RF generator DC input measured, compressor "
             "ICD row 22, valve drivers, thermal, housekeeping, front end) on the p_bus_1ms_max basis with a "
             "conformant gate measurement (A9.1 OQ-A902-01)",
    "m_wet": "a CBE or measured mass for every mass/power v2 BOM line (no CBE exists) plus the Xe load case "
             "(XA9Q-01 / MQ-09) and the MQ-01 margin reading decided by the owner",
    "Q_reject": "the P3 coupled network solved: ICP geometry P3-G-01..08, emittances P3-R-01..04, conductances "
                "P3-K-01..06, heat terms from P1/P2 data (Q_RF/match, Q_collector) and Phase-1 plume data (Q_plume)",
    "I_e_margin": "registered I_d,max,H1 (A9.3 OQ-A907-02, from measured H-1 operation) AND a P1 ICP-45A result "
                  "EVALUATED_ENGINEERING_ONLY (discharge-OFF capacity, one-sided LCB, A9.4 P1Q-10 / A9.5 P1Q-16); "
                  "for hall_c1_reference a registered C1 emission capacity",
    "life": "Hall wall-erosion life (needs an admitted Hall map with wall_life_trustworthy) or a life test; anode / "
            "collector material with gate-admissible evidence (P4: all 352 gate cells INCOMPLETE_EVIDENCE); intake "
            "/ plenum / filter AO compatibility (coupon programme, owner row 132)",
}


def thrust_minus_drag(drag_intake_N: float | None, drag_intake_se_N: float | None = None, thrust: Mapping | None = None,
                      spacecraft_drag: Mapping | None = None, repo: Path = REPO, intake_drag: Mapping | None = None) -> dict:
    """T - D_spacecraft with D = D_intake (F1) + D_body (TBD unless supplied). Refused unless T comes from an admitted
    Hall response (supplied record) AND the credible set is non-empty, and D_body is supplied. The F1 intake drag is
    PARAMETRIC (TBD surface scenario) unless a supplied ``intake_drag`` record replaces it; the composite is EVALUATED
    only when T, D_body and D_intake all are (PR #36 review)."""
    hall = hall_response_status(repo)
    di = supplied_objective("D_intake", intake_drag, "N")
    if di is not None:
        drag_intake_N, drag_intake_se_N = di["value"], None
    t = supplied_objective("T", thrust, "N")
    db = supplied_objective("D_body", spacecraft_drag, "N")
    missing = []
    if t is None:
        missing.append("T: no admitted Hall response map (credible set " + hall["credible_set"] + ")")
    elif t["status"] == EVALUATED and not hall["admitted_members"]:
        missing.append("T: a non-synthetic thrust record was supplied but the credible Hall set is EMPTY "
                       "(no admitted transport member: refused)")
        t = None
    if db is None:
        missing.append("D_spacecraft: spacecraft body / array drag TBD (F1-ID-08)")
    di_status = di["status"] if di is not None else (PARAMETRIC_ONLY if drag_intake_N is not None else NOT_EVALUATED)
    partial = {"D_intake_N": drag_intake_N, "D_intake_se_N": drag_intake_se_N,
               "D_intake_status": di_status,
               "D_intake_basis": (f"supplied intake-drag record ({di['source']})" if di is not None else
                                  "F1 intake-face drag (frozen TPMC surface / direct TPMC; surface scenario is a TBD "
                                  "context axis), max over the five orbit states")}
    if missing:
        return _obj("T_minus_D_spacecraft_N", NOT_EVALUATED, None, "N", reason="; ".join(missing),
                    unlock=[UNLOCK["T"], UNLOCK["D_spacecraft"]], partial=partial)
    if drag_intake_N is None:
        return _obj("T_minus_D_spacecraft_N", NOT_EVALUATED, None, "N", reason="intake drag not evaluated",
                    unlock=[UNLOCK["T"]], partial=partial)
    sts = (t["status"], db["status"], di_status)
    st = SYNTHETIC_ONLY if SYNTHETIC_ONLY in sts else \
        (EVALUATED if all(x == EVALUATED for x in sts) else PARAMETRIC_ONLY)
    val = t["value"] - (drag_intake_N + db["value"])
    return _obj("T_minus_D_spacecraft_N", st, val, "N",
                evidence_class=SYN_CLASS if st == SYNTHETIC_ONLY else "model-derived",
                source=f"T: {t['source']}; D_body: {db['source']}; "
                       f"D_intake: {di['source'] if di is not None else 'F1'}", partial=partial,
                thrust_N=t["value"], drag_total_N=drag_intake_N + db["value"])


# ----------------------------------------------------------------------------------------------- P_bus
def _slot_texts(mp: dict, config: str) -> dict:
    return {s["slot"]: s for s in mp["power"]["configurations"][config]["slots"]}


def _eff_path(text: str) -> str:
    m = re.search(r"path (internal_bus|direct)", text)
    if not m:
        raise RuntimeError(f"no supply path in mass/power v2 efficiency text: {text!r}")
    return m.group(1)


def official_ledger(config: str, repo: Path = REPO, compressor_P_W: float | None = None,
                    compressor_source: str = "") -> dict:
    """A9-02 steady ledger with every installed slot TBD as mass/power v2 records it. With compressor_P_W the
    compressor slot carries that (model-derived, PARAMETRIC) draw: a labelled sensitivity ledger, never the official
    one (row 22: the compressor ICD has not supplied the load)."""
    mp = read_json(MP_REL, repo)
    slots = _slot_texts(mp, config)
    loads, effs = {}, {}
    for s in bb.installed_slots(config):
        rec = slots[s]
        if s == "reserved_dc_port":
            loads[s] = {"P_W": 0.0, "evidence_class": "assumed",
                        "source": f"{MP_REL} power.configurations.{config} reserved_dc_port: '{rec['status']}'"}
        elif s == "compressor" and compressor_P_W is not None:
            loads[s] = {"P_W": float(compressor_P_W), "evidence_class": "model-derived",
                        "source": compressor_source or "F3/F4 DragCompressor cascade (code-default coefficients)"}
        else:
            loads[s] = {"P_W": bb.TBD, "tbd_requires": rec["status"]}
        if s == "icp_rf_source":
            loads[s]["plane"] = "generator_dc_input"       # the only RF-chain plane crossing the bus (row 72)
        effs[s] = {"value": bb.TBD, "tbd_requires": rec["efficiency"], "path": _eff_path(rec["efficiency"])}
    fe = {"value": bb.TBD, "tbd_requires": "front-end converter efficiency (row 111): TBD"}
    label = "OFFICIAL_A9_02_STATE" if compressor_P_W is None else LABEL_PARAMETRIC
    return bb.ledger(config, loads, effs, fe, label=label)


def bus_power(config: str, compressor_P_W: float | None, supplied: Mapping | None = None, repo: Path = REPO) -> dict:
    """P_bus objective. EVALUATED only from supplied COMPLETE ledgers (steady + start-up steps) whose loads are all of
    a rankable class; the RFP gate verdict of bus_boundary_a9.rfp_power_gate is carried for the hard constraint.
    Otherwise NOT_EVALUATED with the official ledger status and the parametric lower bound."""
    if supplied is not None:
        steady, startup = supplied["steady"], supplied["startup"]
        gate = bb.rfp_power_gate(steady, startup)
        def _ledger_classes(led):
            # every evidence class that enters P_bus: loads, slot efficiencies, front-end efficiency (PR #36 review)
            c = set(led["load_evidence_classes"])
            c |= {it["efficiency_evidence_class"] for it in led["items"]
                  if it.get("efficiency") is not None and it.get("efficiency_evidence_class")}
            if any(it.get("path") == "internal_bus" and it.get("state") != "OFF" for it in led["items"]):
                c.add(led["front_end"]["evidence_class"] or "TBD")
            return c
        classes = _ledger_classes(steady)
        for s in startup:
            classes |= _ledger_classes(s)
        if steady["status"] != "COMPLETE":
            return _obj("P_bus_W", INCOMPLETE, None, "W", reason=f"supplied steady ledger {steady['status']}",
                        unlock=[UNLOCK["P_bus"]], gate_verdict=gate["verdict"],
                        lower_bound_W=steady["P_bus_lower_bound_W"])
        syn = supplied.get("synthetic", False)
        st = SYNTHETIC_ONLY if syn else (EVALUATED if classes <= set(RANKABLE_CLASSES) else PARAMETRIC_ONLY)
        return _obj("P_bus_W", st, steady["P_bus_W"], "W", evidence_class=SYN_CLASS if syn else
                    ",".join(sorted(classes)), source=supplied.get("source", "supplied A9-02 ledgers"),
                    gate_verdict=gate["verdict"], power_basis=steady["power_basis"])
    off = official_ledger(config, repo)
    par = official_ledger(config, repo, compressor_P_W) if compressor_P_W is not None else None
    return _obj("P_bus_W", NOT_EVALUATED, None, "W",
                reason=f"A9-02 official ledger status {off['status']} ({len(off['tbd'])} TBD terms; compressor load "
                       "TBD per row 22); every Hall / ICP / C1 / valve / thermal / housekeeping load and every supply "
                       "efficiency is TBD", unlock=[UNLOCK["P_bus"]],
                official_status=off["status"], official_lower_bound_W=off["P_bus_lower_bound_W"],
                parametric_lower_bound_W=None if par is None else par["P_bus_lower_bound_W"],
                parametric_status=None if par is None else par["status"],
                gate_verdict="NOT_EVALUABLE",
                allocation_context={"design_allocation_W": bb.DESIGN_ALLOCATION_W,
                                    "common_allocation_W": bb.COMMON_ALLOCATION_W,
                                    "rule": "owner allocations (rows 109, 114), never gates or predictions"})


# ----------------------------------------------------------------------------------------------- m_wet
MASS_LINES_DESIGN = {"AL-01": "intake (+ filter / duct)", "AL-02": "compressor + drive", "AL-03": "plenum / feed",
                     "AL-05": "ICP neutralizer"}


def wet_mass(config: str, design_masses: Mapping | None = None, supplied: Mapping | None = None,
             repo: Path = REPO) -> dict:
    """m_wet objective. Allocation, evidence floor, parametric design value and CBE stay in separate columns (mass /
    power v2 rule). EVALUATED only from a supplied closed roll-up {value, evidence_class, source,
    all_terms_resolved: True}; otherwise NOT_EVALUATED with the mass/power v2 wet roll-up envelope (allocation
    readings) and the per-line view."""
    mp = read_json(MP_REL, repo)
    if supplied is not None:
        if not supplied.get("all_terms_resolved"):
            return _obj("m_wet_kg", INCOMPLETE, None, "kg", reason="supplied roll-up has unresolved terms",
                        unlock=[UNLOCK["m_wet"]])
        o = supplied_objective("m_wet_kg", supplied, "kg")
        return o
    wets = [w for r in mp["rollups"] if r["configuration"] == config for w in r["wet"]
            if w["reference"] == "HARD_40_WET"]
    known = [w["wet_known_kg"] for w in wets]
    states = sorted({w["state"] for w in wets})
    lines = []
    dm = dict(design_masses or {})
    for ln in mp["lines"][config]:
        lid = ln["line"]
        lines.append({"line": lid, "name": ln["owner_name"], "allocation_kg": ln.get("allocation_kg"),
                      "evidence_floor_kg": ln.get("evidence_floor_kg"), "cbe_kg": None, "measured_kg": None,
                      "design_parametric": dm.get(lid), "state": ln["state"]})
    return _obj("m_wet_kg", NOT_EVALUATED, None, "kg",
                reason="no CBE or measured mass exists for any BOM line (mass/power v2); the wet roll-ups against "
                       f"the 40 kg limit are {states} under every reading",
                unlock=[UNLOCK["m_wet"]], wet_known_allocation_envelope_kg=[min(known), max(known)] if known else None,
                wet_rollup_states=states, lines=lines,
                rule="allocation / evidence floor / design-parametric / CBE never merged")


# ----------------------------------------------------------------------------------------------- Q_reject
def heat_rejection(compressor_P_W: float | None, supplied: Mapping | None = None, repo: Path = REPO) -> dict:
    """Q_reject objective from the P3 coupled network; NOT_EVALUATED while its evaluations are INCOMPLETE_EVIDENCE.
    The only design-dependent partial term today is an UPPER bound on the compressor-local dissipation
    (<= electrical input; PARAMETRIC)."""
    if supplied is not None:
        return supplied_objective("Q_reject_W", supplied, "W")
    p3 = read_json(P3_REL, repo)
    fce = {k: v["status"] for k, v in p3["fail_closed_evaluations"].items()}
    return _obj("Q_reject_W", NOT_EVALUATED, None, "W",
                reason=f"P3 framework {p3['status']}; fail-closed evaluations {fce}; ICP_COUPLED_THERMAL and "
                       "ANODE_THERMAL_CLOSURE UNRESOLVED (never reported as PASS)", unlock=[UNLOCK["Q_reject"]],
                p3_evaluations=fce,
                partial={"compressor_local_dissipation_upper_bound_W": compressor_P_W,
                         "basis": "electrical input = local dissipation + energy carried by the gas, so the local "
                                  "dissipation is at most P_el (PARAMETRIC, code-default coefficients)"})


# ----------------------------------------------------------------------------------------------- I_e margin
def electron_margin(config: str, supplied: Mapping | None = None, repo: Path = REPO) -> dict:
    """I_e,cap - I_d,max objective (RVM-15). EVALUATED only from a supplied record carrying the one-sided lower
    confidence bound margin and both registrations; NOT_EVALUATED today (ICP-45 NOT_EVALUATED, I_d,max,H1 TBD)."""
    if supplied is not None:
        return supplied_objective("I_e_cap_minus_I_d_max_A", supplied, "A")
    mp = read_json(MP_REL, repo)
    it = {i["id"]: i for i in mp["items"]}
    return _obj("I_e_cap_minus_I_d_max_A", NOT_EVALUATED, None, "A",
                reason=("ICP-45 NOT_EVALUATED: I_d,max,H1 " + str(it["MPV2-P09"]["value"]) + " (not registered) and "
                        "no P1 data; ICP electron-current capacity PENDING_ICP45" if config == "hall_icp_neutralizer"
                        else "C1 emission capacity not registered; I_d,max,H1 TBD (C1 CONTROL_FALLBACK)"),
                unlock=[UNLOCK["I_e_margin"]],
                context={"bench_discharge_ceiling_A": it["MPV2-P10"]["value"],
                         "rule": "the 8.33 A stand ceiling is a ground rating, never I_d,max,H1"})


# ----------------------------------------------------------------------------------------------- life / material
def life_material_indicators(design: Mapping | None = None, repo: Path = REPO) -> dict:
    """Life / material indicators per block with their evidence state (no indicator is EVALUATED as life)."""
    p4 = read_json(P4_REL, repo)
    f3 = read_json(F3_REL, repo)
    par = {p["id"]: p for p in f3["parameters"]}
    ind = []
    rotor = None
    if design is not None and design.get("u_tip_turbo_mps") is not None:
        rho = par["P-TI64-DENSITY"]["value"]
        allow = par["P-TI64-FTY-A-BASIS"]["value"] / par["P-STRESS-SAFETY"]["value"]
        sig = rho * design["u_tip_turbo_mps"] ** 2
        rotor = {"sigma_tip_Pa": sig, "allowable_over_safety_Pa": allow, "stress_margin": 1.0 - sig / allow,
                 "status": PARAMETRIC_ONLY, "stress_case": "LEGACY_PARAMETRIC_SENSITIVITY",
                 "stress_case_label": rs.LEGACY_SENSITIVITY_LABEL,
                 "basis": "sigma = rho u^2 (F3 gate); cited A-basis Fty / uncited safety "
                 "factor 2 and uncited density (F3 P-TI64-FTY-A-BASIS, P-STRESS-SAFETY, P-TI64-DENSITY)",
                 "rotor_qualification": rs.qualify_rotor(design.get("rotor_strength_basis_id"),
                                                         design.get("rotor_material", "Ti6Al4V"),
                                                         design["u_tip_turbo_mps"], design.get("rpm", float("nan")),
                                                         float("nan"), design.get("rotor_stock_thickness_m"))
                 ["rotor_qualification"]}
    ind.append({"block": "x_compressor", "indicator": "rotor structural acceptance (registered basis only, A9.9 S2.3; "
                "the Ti-6Al-4V 827 MPa x 2.0 margin is the legacy PARAMETRIC_SENSITIVITY case)", "value": rotor,
                "status": PARAMETRIC_ONLY if rotor else NOT_EVALUATED})
    ind.append({"block": "x_compressor", "indicator": "bearing / motor life", "value": None, "status": NOT_EVALUATED,
                "unlock": "compressor_downselect T-4 / life evidence"})
    ind.append({"block": "x_intake", "indicator": "AO compatibility of the honeycomb wall / coating", "value": None,
                "status": NOT_EVALUATED, "unlock": "coating selection and AO coupon evidence (F1-P-03/04)"})
    ind.append({"block": "x_filter", "indicator": "AO / material applicability", "value": None,
                "status": NOT_EVALUATED, "unlock": "F2 evidenced filter records (NO_ATOMIC_O surrogates never prove "
                                                  "AO life, owner row 132)"})
    ind.append({"block": "x_plenum", "indicator": "wall O recombination / material", "value": None,
                "status": NOT_EVALUATED, "unlock": "GP-D03 + coupon evidence (F4-P-06)"})
    ind.append({"block": "x_Hall", "indicator": "anode material", "value": p4["final_material_status"],
                "status": NOT_EVALUATED, "fixed_statuses": {k: v["status"] for k, v in p4["fixed_statuses"].items()},
                "gate_cells": len(p4["gate_matrix"]),
                "gate_cells_incomplete": sum(1 for g in p4["gate_matrix"] if g.get("outcome", g.get("status"))
                                             == "INCOMPLETE_EVIDENCE")})
    ind.append({"block": "x_Hall", "indicator": "wall erosion / firing life > 15,000 h (RVM-12)", "value": None,
                "status": NOT_EVALUATED, "unlock": UNLOCK["life"]})
    ind.append({"block": "x_ICP", "indicator": "collector material", "value": "OPEN", "status": NOT_EVALUATED})
    return _obj("life_material", NOT_EVALUATED, None, "-", reason="no life model or life evidence for any block; P4 "
                "gates all INCOMPLETE_EVIDENCE; the only number is a parametric rotor stress margin",
                unlock=[UNLOCK["life"]], indicators=ind)


def _life_material(design: Mapping | None, supplied: Mapping | None, repo: Path = REPO) -> dict:
    """The life / material indicator set; a supplied closed assessment record sets its status (synthetic stays
    SYNTHETIC_TEST_ONLY_NOT_EVIDENCE, assumed / allocation stays PARAMETRIC_SENSITIVITY_ONLY)."""
    lm = life_material_indicators(design, repo)
    so = supplied_objective("life_material", supplied, "-")
    if so is None:
        return lm
    return dict(lm, status=so["status"], value=so["value"], evidence_class=so["evidence_class"],
                source=so["source"], reason=so["reason"], supplied=True)


SYSTEM_OBJECTIVES = (
    ("T_minus_D_spacecraft_N", "max"), ("P_bus_W", "min"), ("m_wet_kg", "min"), ("Q_reject_W", "min"),
    ("I_e_cap_minus_I_d_max_A", "max"),
)
SYSTEM_OBJECTIVE_CODE = {"T_minus_D_spacecraft_N": "T_minus_D", "P_bus_W": "P_bus", "m_wet_kg": "m_wet",
                         "Q_reject_W": "Q_reject", "I_e_cap_minus_I_d_max_A": "I_e_margin",
                         "life_material": "life_material"}

# ----------------------------------------------------------------------------------------------- hard constraints
HARD_CONSTRAINTS = (
    {"id": "HC-01", "rvm": "RVM-02", "rfp": "RFP-P18-06", "quantity": "T (sustained, atmospheric propellant)",
     "comparator": ">=", "limit": 0.012, "units": "N", "objective": "thrust_N", "category": "rfp_recorded"},
    {"id": "HC-02", "rvm": "RVM-03", "rfp": "RFP-P18-06; RFP-P18-10",
     "quantity": "demonstrated thrust capability at P_bus < 1500 W", "comparator": ">=",
     "limit": 0.025, "units": "N", "objective": "thrust_capability_N", "category": "rfp_recorded"},
    {"id": "HC-03", "rvm": "RVM-04", "rfp": "RFP-P18-10", "quantity": "P_bus,1ms,max (steady and start-up, A9-02 gate)",
     "comparator": "<", "limit": 1500.0, "units": "W", "objective": "P_bus_W", "category": "rfp_recorded"},
    {"id": "HC-04", "rvm": "RVM-06", "rfp": "RFP-P18-11", "quantity": "wet propulsion-system mass", "comparator": "<",
     "limit": 40.0, "units": "kg", "objective": "m_wet_kg", "category": "rfp_recorded"},
    {"id": "HC-05", "rvm": "RVM-15", "quantity": "I_e,cap - I_d,max,H1 (one-sided LCB)", "comparator": ">",
     "limit": 0.0, "units": "A", "objective": "I_e_cap_minus_I_d_max_A", "category": "derived_from_owner_decision"},
    {"id": "HC-06", "rvm": "RVM-17", "quantity": "thermal margin below validated limits", "comparator": ">=",
     "limit": 50.0, "units": "K", "objective": "thermal_margin_K", "category": "derived_project"},
    {"id": "HC-07", "rvm": "RVM-12", "rfp": "RFP-P19-01", "quantity": "cumulative firing time capability",
     "comparator": ">", "limit": 15000.0, "units": "h", "objective": "firing_life_h", "category": "rfp_recorded"},
    {"id": "HC-08", "rvm": "AG-13 (owner decision A9.13 S6.15 / OQ-F78-01; A9.14 S9.7 statewise quantifier)",
     "rfp": "RFP-P18-04; RFP-P18-06",
     "quantity": "T_available(state) - D_spacecraft(state) at EVERY required state (statewise; worst state governs; "
                 "the orbit average never hides a deficit)", "comparator": ">=", "limit": 0.0, "units": "N",
     "objective": "statewise_T_minus_D", "category": "owner_decision_hard_statewise", "statewise": True},
    {"id": "HC-09", "rvm": "F1 C-DRAG-RFP (RFP thrust max as recorded, F1-P-11)",
     "quantity": "intake-face drag at every orbit state", "comparator": "<=", "limit": 0.025, "units": "N",
     "objective": "drag_intake_max_N", "category": "upstream (evaluable now; necessary, not sufficient)"},
    {"id": "HC-10", "rvm": "A9.15 RFP-compliant propellant policy", "rfp": "RFP-P18-08; RFP-P17-05",
     "quantity": "ambient-air AND Xe operating capability with two separate propellant tanks / paths "
                 "(1 = both demonstrated)", "comparator": ">=", "limit": 1.0, "units": "-",
     "objective": "propellant_capability", "category": "rfp_recorded"},
    {"id": "HC-11", "rvm": "AG-12 (owner decision A9.13 S6.21 / F9-OQ-02)", "rfp": "RFP-P18-06; RFP-P18-05",
     "quantity": "statewise feed-state sufficiency (mdot, P, T, composition, ripple) vs the requirement derived from "
                 "the required thrust and a VALIDATED H-1 map (no fixed mg/s gate)", "comparator": ">=", "limit": 0.0,
     "units": "-", "objective": "feed_state_sufficiency", "category": "owner_decision_hard_statewise",
     "statewise": True},
    {"id": "HC-12", "rvm": "A9.13 S6.17 / S6.12 feed-quality", "rfp": "-",
     "quantity": "compressor / plenum ripple <= measured H-1 ripple tolerance", "comparator": "<=", "limit": None,
     "units": "-", "objective": "ripple_feed_quality", "category": "owner_decision_hard_constraint"},
)
# constraints whose record is a pre-evaluated upstream_a9_13 constraint result (status carried, not recomputed)
PRE_EVALUATED_OBJECTIVES = ("statewise_T_minus_D", "feed_state_sufficiency", "ripple_feed_quality")


def _from_u13(status: str) -> tuple[str, str | None]:
    """Map an upstream_a9_13 constraint status onto this module's (constraint status, value status)."""
    return {u13.C_MET: (C_MET, EVALUATED), u13.C_VIOLATED: (C_VIOLATED, EVALUATED),
            u13.C_MET_SYNTHETIC: (C_MET, SYNTHETIC_ONLY), u13.C_VIOLATED_SYNTHETIC: (C_VIOLATED, SYNTHETIC_ONLY),
            u13.C_MET_PARAMETRIC: (C_MET_PARAMETRIC, PARAMETRIC_ONLY),
            u13.C_VIOLATED_PARAMETRIC: (C_VIOLATED_PARAMETRIC, PARAMETRIC_ONLY)}.get(status, (C_NOT_EVALUATED, None))


def _cmp(v: float, comparator: str, limit: float) -> bool:
    return {">=": v >= limit, ">": v > limit, "<": v < limit, "<=": v <= limit}[comparator]


def evaluate_constraints(values: Mapping) -> list[dict]:
    """Fail-closed hard constraints. ``values``: objective name -> objective record (status + value) or None.
    A constraint is MET_ON_SUPPLIED_VALUES or VIOLATED only on an EVALUATED or SYNTHETIC numeric value (the label
    travels with it; rank_full_system never lets synthetic and evidence meet). On a PARAMETRIC_SENSITIVITY_ONLY value
    (assumed, owner-allocation, code-default or parametric inputs) the comparison is reported as
    MET_ON_PARAMETRIC_VALUES_SENSITIVITY_ONLY_NOT_MET / VIOLATED_ON_PARAMETRIC_VALUES_SENSITIVITY_ONLY and never
    counts as satisfied (A9.7: a TBD is never converted to an assumed value to obtain an optimum). Anything else is
    NOT_EVALUATED. HC-03 uses the A9-02 gate verdict when one is carried (PASS -> met, FAIL -> violated,
    NOT_EVALUABLE -> not evaluated) only on an EVALUATED or SYNTHETIC ledger; on a PARAMETRIC_SENSITIVITY_ONLY ledger the
    verdict maps to the parametric sensitivity statuses, and on any other status to NOT_EVALUATED."""
    out = []
    for c in HARD_CONSTRAINTS:
        rec = values.get(c["objective"])
        st, basis = C_NOT_EVALUATED, "no evaluable value (fail closed: never counted as satisfied)"
        if c["objective"] in PRE_EVALUATED_OBJECTIVES:
            if rec is None:
                basis = ("no statewise record over the required state set (a single value never closes a statewise "
                         "constraint; A9.13 S6.15 / S6.21 / A9.14 S9.7)" if c.get("statewise") else
                         "measured H-1 tolerance / ripple not evaluated (A9.13 S6.17)")
                vst = None
            else:
                st, vst = _from_u13(rec.get("status"))
                basis = f"upstream_a9_13 {c['objective']} status {rec.get('status')}"
                if rec.get("average_hides_violation"):
                    basis += "; orbit average non-negative but a state is below zero (the statewise result governs)"
            out.append({"id": c["id"], "rvm": c["rvm"], "rfp": c.get("rfp"), "quantity": c["quantity"],
                        "rule": c["quantity"], "status": st, "value_status": vst, "basis": basis})
            continue
        if rec is not None and c["id"] == "HC-03" and rec.get("gate_verdict") is not None:
            gv = rec["gate_verdict"]
            vst = rec.get("status")
            if vst in (EVALUATED, SYNTHETIC_ONLY):
                st = {"PASS": C_MET, "FAIL": C_VIOLATED}.get(gv, C_NOT_EVALUATED)
                basis = f"bus_boundary_a9.rfp_power_gate verdict {gv} ({vst})"
            elif vst == PARAMETRIC_ONLY:
                # the gate ignores evidence class: on assumed / parametric loads its verdict is a sensitivity
                # comparison only and never counts as satisfied (fail closed; OPT-04)
                st = {"PASS": C_MET_PARAMETRIC, "FAIL": C_VIOLATED_PARAMETRIC}.get(gv, C_NOT_EVALUATED)
                basis = (f"bus_boundary_a9.rfp_power_gate verdict {gv} on {vst} ledger values: sensitivity "
                         "comparison only, never counted as satisfied (fail closed)")
            else:
                st = C_NOT_EVALUATED
                basis = (f"bus_boundary_a9.rfp_power_gate verdict {gv} but value status {vst}: "
                         "not evaluable (fail closed)")
        elif rec is not None and rec.get("status") in (EVALUATED, PARAMETRIC_ONLY, SYNTHETIC_ONLY) and \
                rec.get("value") is not None and math.isfinite(float(rec["value"])):
            ok = _cmp(rec["value"], c["comparator"], c["limit"])
            if rec["status"] == PARAMETRIC_ONLY:
                st = C_MET_PARAMETRIC if ok else C_VIOLATED_PARAMETRIC
                basis = (f"value {rec['value']:.6g} {c['units']} ({rec['status']}): sensitivity comparison only, "
                         "never counted as satisfied (fail closed)")
            else:
                st = C_MET if ok else C_VIOLATED
                basis = f"value {rec['value']:.6g} {c['units']} ({rec['status']})"
        out.append({"id": c["id"], "rvm": c["rvm"], "rfp": c.get("rfp"), "quantity": c["quantity"],
                    "rule": f"{c['comparator']} {c['limit']:g} {c['units']}", "status": st,
                    "value_status": None if rec is None else rec.get("status"), "basis": basis})
    return out


def evaluate_system(upstream_row: Mapping | None, config: str, design: Mapping | None = None,
                    supplied: Mapping | None = None, repo: Path = REPO) -> dict:
    """Every system objective of one design vector (upstream sub-vector from an F7 row; x_Hall / x_ICP / x_RF /
    x_thermal through the supplied records) and the fail-closed hard constraints. ``supplied`` keys: thrust,
    thrust_capability, spacecraft_drag, bus (ledgers), m_wet, Q_reject, I_e_margin, thermal_margin, firing_life,
    life_material (a record {value, evidence_class, source} standing for a closed life / material assessment),
    drag_intake_max (a record replacing the row's parametric F1 intake-drag value for HC-09), statewise_T_minus_D
    (upstream_a9_13.statewise_drag_compensation result, HC-08), feed_state_sufficiency (upstream_a9_13.
    feed_state_sufficiency result, HC-11), ripple_feed_quality (upstream_a9_13.ripple_feed_quality result, HC-12),
    propellant_capability (a record, 1 = air AND Xe operation demonstrated, HC-10) and propellant_paths (the
    modelled paths; default MODELLED_PROPELLANT_PATHS, checked structurally against A9.15)."""
    if config not in CONFIGURATIONS:
        raise OptimizerError(f"unknown configuration {config!r}")
    s = dict(supplied or {})
    row = dict(upstream_row or {})
    pel = row.get("P_compressor_el_max_W")
    objs = {
        "T_minus_D_spacecraft_N": thrust_minus_drag(row.get("drag_intake_max_N"), row.get("drag_intake_max_se_N"),
                                                    s.get("thrust"), s.get("spacecraft_drag"), repo,
                                                    intake_drag=s.get("drag_intake_max")),
        "P_bus_W": bus_power(config, pel, s.get("bus"), repo),
        "m_wet_kg": wet_mass(config, {"AL-02": {"m_compressor_max_kg": row.get("m_compressor_max_kg"),
                                                 "status": LABEL_PARAMETRIC, "allocation_kg": 5.5}}
                             if row.get("m_compressor_max_kg") is not None else None, s.get("m_wet"), repo),
        "Q_reject_W": heat_rejection(pel, s.get("Q_reject"), repo),
        "I_e_cap_minus_I_d_max_A": electron_margin(config, s.get("I_e_margin"), repo),
        "life_material": _life_material(design, s.get("life_material"), repo),
    }
    cvals = dict(objs)
    for k, name, units in (("thrust", "thrust_N", "N"), ("thrust_capability", "thrust_capability_N", "N"),
                           ("thermal_margin", "thermal_margin_K", "K"), ("firing_life", "firing_life_h", "h")):
        cvals[name] = supplied_objective(name, s.get(k), units)
        if k in ("thrust", "thrust_capability"):
            cvals[name] = hall_gated_thrust(name, cvals[name], repo)
    if row.get("drag_intake_max_N") is not None:
        cvals["drag_intake_max_N"] = _obj("drag_intake_max_N", PARAMETRIC_ONLY, row["drag_intake_max_N"], "N",
                                          "model-derived", "F1 (TPMC) at a TBD surface scenario")
    if s.get("drag_intake_max") is not None:     # a supplied (e.g. measured / synthetic) intake-drag record
        cvals["drag_intake_max_N"] = supplied_objective("drag_intake_max_N", s["drag_intake_max"], "N")
    # A9.13 S6.15 / S6.21 / S6.17 pre-evaluated statewise / feed-quality records (never recomputed from one number)
    for k in PRE_EVALUATED_OBJECTIVES:
        cvals[k] = s.get(k)
    if cvals["ripple_feed_quality"] is None and row.get("ripple_transfer_shaft") is not None:
        cvals["ripple_feed_quality"] = u13.ripple_feed_quality(row["ripple_transfer_shaft"], u13.VALUE_PARAMETRIC,
                                                               u13.h1_tolerance_tbd("ripple"))
    prop = u13.propellant_paths_check(s.get("propellant_paths", MODELLED_PROPELLANT_PATHS))
    cvals["propellant_capability"] = supplied_objective("propellant_capability", s.get("propellant_capability"), "-")
    cons = evaluate_constraints(cvals)
    ne = [SYSTEM_OBJECTIVE_CODE[k] for k, v in objs.items() if v["status"] != EVALUATED]
    return {"configuration": config, "design_id": row.get("design_id"), "objectives": objs, "constraints": cons,
            "propellant_paths": prop,
            "system_not_evaluated": ne,
            "constraints_not_evaluated": [c["id"] for c in cons if c["status"] == C_NOT_EVALUATED],
            "constraints_violated": [c["id"] for c in cons if c["status"] == C_VIOLATED]}


# ----------------------------------------------------------------------------------------------- full-system ranking
def nondominated_layers(F: np.ndarray, senses: Sequence[str]) -> np.ndarray:
    """Non-dominated sorting: layer 1 = Pareto set, layer 2 = Pareto set of the rest, ... (no scalarisation)."""
    n = len(F)
    layer = np.zeros(n, dtype=int)
    rest = np.arange(n)
    k = 0
    while len(rest):
        k += 1
        m = pareto_mask(F[rest], senses)
        if not m.any():
            raise OptimizerError("non-finite objective in a ranked record")
        layer[rest[m]] = k
        rest = rest[~m]
    return layer


def _upstream_value(ev: Mapping, key: str) -> tuple[float | None, str | None]:
    """An upstream objective for the full-system ranking must carry its status (OPT-03): either a record
    {value, status} in ev['upstream'][key], or a bare number with its status in ev['upstream_status'][key]. A bare
    number without a status is treated as unlabelled (None) and refused."""
    v = (ev.get("upstream") or {}).get(key)
    if isinstance(v, Mapping):
        return v.get("value"), v.get("status")
    return v, (ev.get("upstream_status") or {}).get(key)


def rank_full_system(evaluations: Sequence[Mapping], upstream_objectives: Sequence[str] = ()) -> dict:
    """Full-system ranking over evaluated design vectors: non-dominated sorting layers of the system objectives (plus
    optional upstream objective keys present in each record's 'upstream'), after removing vectors that VIOLATE a hard
    constraint or have one not MET on rankable values (fail closed). REFUSED_INCOMPLETE when ANY record has a system
    objective that is not EVALUATED / synthetic, including the life / material indicator set (no subset ranking:
    ranking only what happens to be measurable would bias the set); REFUSED_MIXED when synthetic and evidence records
    meet, in the objectives OR in the values a hard constraint was met on; REFUSED_PARAMETRIC_UPSTREAM when a ranked
    upstream objective is not EVALUATED / synthetic (the committed upstream values are PARAMETRIC_SENSITIVITY). A
    synthetic-only ranking is labelled SYNTHETIC_TEST_ONLY_NOT_EVIDENCE. Never a winner: layer 1 is a set.

    life_material is a gate, not a Pareto axis: it is an indicator set with no scalar (its life scalar is HC-07,
    firing life > 15,000 h); the ranking refuses until it is EVALUATED (or synthetic in a synthetic-only test)."""
    if not evaluations:
        return {"status": RANK_REFUSED_NO_FEASIBLE, "reason": "no candidate supplied", "layers": {}}
    missing = {}
    kinds = set()
    for ev in evaluations:
        for name in [n for n, _ in SYSTEM_OBJECTIVES] + ["life_material"]:
            o = ev["objectives"][name]
            ok_value = name == "life_material" or o["value"] is not None
            if o["status"] not in (EVALUATED, SYNTHETIC_ONLY) or not ok_value:
                missing.setdefault(name, 0)
                missing[name] += 1
            else:
                kinds.add(o["status"])
    if missing:
        return {"status": RANK_REFUSED_INCOMPLETE,
                "reason": "system objectives (incl. the life / material indicator gate) not EVALUATED for some or "
                          "all candidates (fail closed, no subset ranking)", "missing_counts": missing,
                "n_candidates": len(evaluations), "unlock": {k: v for k, v in UNLOCK.items()}, "layers": {}}
    bad_up = {}
    for ev in evaluations:
        for k in upstream_objectives:
            v, st = _upstream_value(ev, k)
            if st not in (EVALUATED, SYNTHETIC_ONLY) or v is None or not math.isfinite(float(v)):
                bad_up.setdefault(k, set()).add(str(st))
            else:
                kinds.add(st)
    if bad_up:
        return {"status": RANK_REFUSED_PARAMETRIC_UPSTREAM,
                "reason": "a ranked upstream objective is not EVALUATED / synthetic (PARAMETRIC_SENSITIVITY or "
                          "unlabelled values never enter an evidence ranking; rank them in the labelled F7 upstream "
                          "Pareto sets instead)", "upstream_statuses": {k: sorted(v) for k, v in bad_up.items()},
                "layers": {}}
    for ev in evaluations:
        for c in ev["constraints"]:
            if c["status"] == C_MET and c.get("value_status") in (EVALUATED, SYNTHETIC_ONLY):
                kinds.add(c["value_status"])
    if kinds == {EVALUATED, SYNTHETIC_ONLY}:
        return {"status": RANK_REFUSED_MIXED, "reason": "synthetic test data and evidence never meet in one ranking "
                "(objectives, ranked upstream values and the values hard constraints were met on)", "layers": {}}
    synthetic = kinds == {SYNTHETIC_ONLY}
    admissible, excluded = [], []
    for ev in evaluations:
        bad = [c["id"] for c in ev["constraints"] if c["status"] != C_MET]
        (excluded if bad else admissible).append((ev, bad))
    if not admissible:
        return {"status": RANK_REFUSED_NO_FEASIBLE, "reason": "every candidate violates a hard constraint or has one "
                "not met on rankable values (NOT_EVALUATED or parametric only; fail closed)",
                "excluded": [{"design_id": e["design_id"], "constraints": b} for e, b in excluded], "layers": {}}
    keys = [k for k, _ in SYSTEM_OBJECTIVES] + list(upstream_objectives)
    senses = [s for _, s in SYSTEM_OBJECTIVES] + [OBJ_SENSE[k] for k in upstream_objectives]
    F = np.array([[ev["objectives"][k]["value"] for k, _ in SYSTEM_OBJECTIVES] +
                  [_upstream_value(ev, k)[0] for k in upstream_objectives] for ev, _ in admissible], dtype=float)
    lay = nondominated_layers(F, senses)
    layers: dict = {}
    for (ev, _), l in zip(admissible, lay):
        layers.setdefault(int(l), []).append(ev["design_id"])
    for l in layers:
        layers[l].sort()
    return {"status": RANK_COMPUTED_SYNTHETIC if synthetic else RANK_COMPUTED,
            "label": SYNTHETIC_ONLY if synthetic else "NOT_A_SELECTION (Pareto layers; no winner)",
            "objectives": keys, "senses": senses, "layers": layers,
            "life_material": "gate only (indicator set, no scalar axis; its life scalar is HC-07)",
            "excluded": [{"design_id": e["design_id"], "constraints": b} for e, b in excluded]}


# ================================================================================================= reporting helpers
def architecture_questions() -> list[dict]:
    """Which architecture-level questions the current evidence can and cannot answer."""
    can, cannot = "CAN_ANSWER_UNDER_PARAMETRIC_INPUTS", "CANNOT_ANSWER"
    return [
        {"id": "AQ-01", "question": "Which upstream intake / compressor / plenum combinations deliver the most flow "
         "for the least drag, compressor power, mass proxy and ripple, per surface scenario and set pressure?",
         "answer_state": can, "basis": "F7 upstream Pareto sets (PARAMETRIC_SENSITIVITY: code-default compressor "
         "coefficients, parametric filter / leak / chain temperature)", "unlock": None},
        {"id": "AQ-02", "question": "Where does the delivered upstream flow sit relative to the 0.38-3.2 mg/s "
         "ground-characterization COVERAGE (not a flight requirement, A9.13 S6.21) at every orbit state with one "
         "plenum setpoint?", "answer_state": can,
         "basis": "F7 upstream frontier per context (see findings); F4-01; coverage only, never PASS / FAIL",
         "unlock": None},
        {"id": "AQ-02b", "question": "Is the delivered feed state sufficient (AG-12) for the required drag-compensation "
         "thrust at every required state?", "answer_state": cannot,
         "basis": "AG-12 is statewise feed-state sufficiency against a VALIDATED H-1 map (A9.13 S6.21): no such map",
         "unlock": [UNLOCK["T"]]},
        {"id": "AQ-03", "question": "Which set pressures can the upstream chain hold at all?", "answer_state": can,
         "basis": "feasible counts per P_set; > 0.1 Pa out of domain (F3/F4)", "unlock": None},
        {"id": "AQ-04", "question": "Does the architecture produce T(state) - D(state) >= 0 at EVERY required state "
         "(statewise, A9.13 S6.15) and >= 12 mN at 180-230 km?",
         "answer_state": cannot, "basis": "no admitted Hall response map; host-spacecraft drag ICD absent (reference "
         "drag is REFERENCE_PARAMETRIC only, S6.18)",
         "unlock": [UNLOCK["T"], UNLOCK["D_spacecraft"]]},
        {"id": "AQ-05", "question": "Does the system close P_bus < 1.5 kW (and the 1.35 kW allocation)?",
         "answer_state": cannot, "basis": "A9-02 ledger PARTIAL_BOUNDARY", "unlock": [UNLOCK["P_bus"]]},
        {"id": "AQ-06", "question": "Does the system close < 40 kg wet?", "answer_state": cannot,
         "basis": "no CBE for any BOM line; wet roll-ups NOT_EVALUABLE", "unlock": [UNLOCK["m_wet"]]},
        {"id": "AQ-07", "question": "Can the ICP (or C1) neutralize the H-1 discharge current with margin?",
         "answer_state": cannot, "basis": "ICP-45 NOT_EVALUATED; I_d,max,H1 not registered",
         "unlock": [UNLOCK["I_e_margin"]]},
        {"id": "AQ-08", "question": "Does the coupled H-1 / ICP thermal design close with >= 50 K margin?",
         "answer_state": cannot, "basis": "P3 INCOMPLETE_EVIDENCE; closures UNRESOLVED", "unlock": [UNLOCK["Q_reject"]]},
        {"id": "AQ-09", "question": "hall_icp_neutralizer vs hall_c1_reference: which configuration is better?",
         "answer_state": cannot, "basis": "every discriminating system objective is NOT_EVALUATED for both "
         "configurations; the upstream chain is common to both (no discrimination there)",
         "unlock": [UNLOCK["I_e_margin"], UNLOCK["P_bus"], UNLOCK["m_wet"]]},
        {"id": "AQ-10", "question": "Which H-1 geometry inside the F5 windows is preferable?", "answer_state": cannot,
         "basis": "every Hall performance quantity NOT_EVALUATED; only geometric admissibility is evaluable",
         "unlock": [UNLOCK["T"]]},
        {"id": "AQ-11", "question": "Which ICP geometry is preferable?", "answer_state": cannot,
         "basis": "F6 bounds all TBD; P1 / P2 no data", "unlock": ["F6-IF-N01..N08 (F6 interface demands)"]},
        {"id": "AQ-12", "question": "Is the upstream Pareto set robust to the TBD surface state, wall recombination, "
         "pointing and TPMC statistics?", "answer_state": can, "basis": "F8 robust filter (scenario set + seeded "
         "MC over quantified TPMC statistics); probabilities only over quantified uncertainty", "unlock": None},
        {"id": "AQ-13", "question": "Is the architecture life-capable (> 15,000 h firing, AO compatibility)?",
         "answer_state": cannot, "basis": "no life model or life evidence", "unlock": [UNLOCK["life"]]},
    ]


def tpmc_backend_policy(repo: Path = REPO) -> dict:
    """F7/F8 run no TPMC: they consume the committed F1 records and their statistical SEs. Recorded policy for any
    future TPMC re-evaluation: backend='rust' only when explicitly requested AND the kernel is ADMITTED in the parity
    report; Python stays authoritative."""
    try:
        verdicts = read_json(PARITY_REL, repo).get("verdicts", {})
    except FileNotFoundError:
        verdicts = {}
    return {"tpmc_invoked_by_f7_f8": False, "default_backend": "python", "parity_verdicts": verdicts,
            "rule": "Rust (abep_sim/design/tpmc_backend.py) only as an explicitly requested accelerator for ADMITTED "
                    "kernels; no Rust result is authoritative; no silent fallback"}


# ================================================================================================= A9.13 / A9.15 additions
# A9.15: the modelled ABEP architecture carries BOTH propellant paths (two separate tanks). The upstream optimizer
# models the air path (F1 -> F2 -> F3 -> F4); the Xe path components are not designed yet (Xe accounting v3), so its
# capability stays NOT_EVALUATED; the structure is still checked.
MODELLED_PROPELLANT_PATHS = {"air": list(u13.AIR_PATH), "xe": list(u13.XE_PATH)}


def require_all_admitted_scenarios(used, inp: UpstreamInputs | None = None, admitted=None, narrowing_record=None):
    """A9.13 S6.16: robustness over EVERY admitted Maxwell / CLL / accommodation scenario (the F1 envelope scenario
    set) unless a pre-registered DI-1.3 narrowing record is supplied."""
    adm = list(admitted) if admitted is not None else list(inp.scenarios)
    return u13.require_all_admitted_scenarios(list(used), adm, narrowing_record)


def statewise_T_minus_D(states, thrust_fn, drag_fn, repo: Path = REPO) -> dict:
    """HC-08 / AG-13 statewise record (A9.13 S6.15) with the admitted-Hall-member gate read from the repository."""
    return u13.statewise_drag_compensation(states, thrust_fn, drag_fn,
                                           hall_admitted=bool(hall_response_status(repo)["admitted_members"]))


def system_pareto(rows, weights=None) -> dict:
    """A9.13 S6.17 system comparison: hard constraints first, then a Pareto filter over worst-state margin, drag,
    upstream power, mass, volume and heat-rejection burden; a weighted scalar is refused."""
    return u13.pareto_s6_17(rows, weights=weights)


def robust_pareto_set(member_ids, version: str, provenance: str, regenerated_after=()) -> "u13.RobustParetoSet":
    """A9.13 S6.20: the versioned robust Pareto set carried to LOCK-1 (no representative)."""
    return u13.RobustParetoSet(set_id="F8-ROBUST-UPSTREAM", version=version, members=tuple(sorted(member_ids)),
                               objectives=tuple(OBJ_KEYS), label=LABEL_PARAMETRIC, provenance=provenance,
                               regenerated_after=tuple(regenerated_after))
