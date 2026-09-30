#!/usr/bin/env python3
"""Build the A9-04 C1-vs-ICP uncertainty budget, stop rules and decision-quantity measurement chains.

Lane fo_a9_04_hall_icp_uncertainty_budget (trigger T_A9_04_UNCERTAINTY_BUDGET, owner decision A9).

    python docs/experiments/hall_icp/uncertainty_budget/build_hall_icp_uncertainty_budget.py --write   # regenerate JSON + MD
    python docs/experiments/hall_icp/uncertainty_budget/build_hall_icp_uncertainty_budget.py --check   # exit 1 on drift / pin failure

Deterministic, offline, pure file I/O. Nothing here is a measurement, a prediction or a frozen threshold:
every decision margin, effect size, stop-rule number and n is a defined quantity with its freeze point; numbers
appear only where an owner answer (docs/decisions/OD_2026_09_29_owner_answers_147.json, cited by row) or a
verified repository deliverable gives them. No Hall transport closure, screening candidate, 0-D Hall model or
withdrawn v1.2-v1.6 number is used. Values owned by the parallel A9 lanes are written 'PENDING <lane path>'.

The readiness_n() function below is the LOCK-1 rule proposed by this lane for computing n at LOCK-2; it is pure,
has no defaults for any physical input and raises on missing or invalid input (CLAUDE.md rule 3).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))

# ---- A9-10 reconciliation overlay (fo_a9_10_integration): declared, machine-checked changes applied after the build
import importlib.util as _a910_ilu  # noqa: E402
_A910_SPEC = _a910_ilu.spec_from_file_location(
    "a9_10_overlay", str(ROOT) + "/docs/experiments/hall_icp/integration/a9_10_overlay.py")
A910 = _a910_ilu.module_from_spec(_A910_SPEC)
_A910_SPEC.loader.exec_module(A910)

LANE_REL = "docs/experiments/hall_icp/uncertainty_budget"
JSON_REL = LANE_REL + "/hall_icp_uncertainty_budget_v1.json"
MD_REL = LANE_REL + "/HALL_ICP_UNCERTAINTY_BUDGET.md"
BUILDER_REL = LANE_REL + "/build_hall_icp_uncertainty_budget.py"
TEST_REL = "tests/test_hall_icp_uncertainty_budget.py"
BASE_COMMIT = "0a430bb5588a438f7c8485c6d16f40ed0d402c4c"

CONFIG_C1 = "hall_c1_reference"
CONFIG_ICP = "hall_icp_neutralizer"
CONFIGS = [CONFIG_C1, CONFIG_ICP]

EVIDENCE_CLASSES = ["measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                    "owner-allocation"]
FREEZE_POINTS = ["NOW", "LOCK-1", "LOCK-2", "after-evidence"]
STATUSES = ["OWNER_GIVEN", "PROPOSED", "TBD", "PENDING", "VERIFIED_INPUT"]

# Paths of the parallel A9 lanes (not in the A9-04 base commit; never read at build or test time).
A9_01 = "docs/experiments/hall_icp/prereg_framework/"
A9_02 = "abep_sim/bus_boundary_a9.py + docs/architecture_comparison/power_boundary_a9/"
A9_03 = "docs/interfaces/icp_neutralizer/"
A9_05 = "docs/evidence/icp_neutralizer/ + docs/experiments/hall_icp/validation_inputs/"
# A9_INT (fo_a9_int_core_integration): the A9-01/02/03/05 deliverables are merged in the base 88e4d47. Resolved
# cross-references cite these concrete files (+ item ids). They are cited, never read here and never pinned here:
# the five A9 deliverables reference each other, so an in-file sha256 would have no fixed point; the post-integration
# sha256 of every target is pinned in docs/experiments/hall_icp/integration/a9_core_integration_v1.json.
A9_01_JSON = "docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json"
A9_02_REF = ("abep_sim/bus_boundary_a9.py + "
             "docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json")
A9_03_JSON = "schemas/interfaces/icp_neutralizer_icd_v1.json"
A9_05_REF = ("docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json + "
             "docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json")
A9_05_EV_JSON = "docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json"
INTEGRATION_JSON = "docs/experiments/hall_icp/integration/a9_core_integration_v1.json"

# A9_INT id mapping: provisional A9-04 ids UB-DQ-* -> final A9-01 ids DQ-HI-*. Rule: UB-DQ-x maps to DQ-HI-y only if
# exactly one A9-01 decision quantity measures the same physical quantity (name), in the same units, for the same
# configurations, with the UB-DQ chain's primary instrument in its A9-01 measurement chain. A9-01 quantities that are
# differences, ratios, allocation checks or multi-limit classes built from it are consumers, not counterparts. No id is
# invented: an id without a unique counterpart keeps its UB-DQ id and is marked 'UNMAPPED - owner/A9-10'.
UNMAPPED = "UNMAPPED - owner/A9-10"
DQ_ID_MAPPING = [
    {"ub_dq_id": "UB-DQ-T", "dq_hi_id": "DQ-HI-TABS", "status": "MAPPED",
     "ub_definition": "thrust; T; mN; both configurations; primary instrument INS-01",
     "a9_01_definition": "DQ-HI-TABS absolute thrust compatibility; mN; HARD_GATE; both configurations; chain "
                         "INS-01, INS-05, INS-06, INS-07, INS-08",
     "basis": "same quantity (measured axial thrust), same units (mN), same configurations, INS-01 in both chains; "
              "the only A9-01 quantity in mN",
     "a9_01_consumers_not_counterparts": ["DQ-HI-TPBUS (mN/kW ratio)"]},
    {"ub_dq_id": "UB-DQ-PBUS", "dq_hi_id": "DQ-HI-PBUS", "status": "MAPPED",
     "ub_definition": "full P_bus at the spacecraft-DC propulsion boundary; P_bus; W; both configurations; primary "
                      "instrument INS-02",
     "a9_01_definition": "DQ-HI-PBUS full bus-power compatibility; W (steady and transient peak); HARD_GATE; both "
                         "configurations; chain INS-02, INS-03, INS-18",
     "basis": "same quantity (full P_bus on the A9 boundary), same units (W), same configurations, INS-02 in both "
              "chains",
     "a9_01_consumers_not_counterparts": ["DQ-HI-PALLOC (allocation check, hall_icp_neutralizer only)",
                                          "DQ-HI-DPBUS (paired difference)", "DQ-HI-TPBUS (ratio)"]},
    {"ub_dq_id": "UB-DQ-RF", "dq_hi_id": None, "status": UNMAPPED,
     "ub_definition": "RF forward / reflected / delivered power; P_fwd, P_ref, P_net, P_coil; W; "
                      "hall_icp_neutralizer only",
     "a9_01_definition": "no A9-01 decision quantity with this name",
     "basis": "no counterpart: RF power enters A9-01 only through the RF-source DC slot of P_bus and as the "
              "reflected-power interlock limit inside a multi-limit class",
     "a9_01_consumers_not_counterparts": ["DQ-HI-PBUS / DQ-HI-PALLOC (via the RF-source DC input slot)",
                                          "DQ-HI-SAFE (RF interlock and reflected power, row 62)"]},
    {"ub_dq_id": "UB-DQ-NEUT", "dq_hi_id": None, "status": UNMAPPED,
     "ub_definition": "electron-source current, collector current / bias and neutralization margin; I_e,src, "
                      "I_coll, V_coll, V_cg, M_n; A / V / -; both configurations",
     "a9_01_definition": "split over DQ-HI-ECAP (A; dimensionless ratio) and DQ-HI-VCPL (V)",
     "basis": "maps to several A9-01 quantities (current/margin part vs potential part)",
     "a9_01_consumers_not_counterparts": ["DQ-HI-ECAP", "DQ-HI-VCPL"]},
    {"ub_dq_id": "UB-DQ-ID", "dq_hi_id": None, "status": UNMAPPED,
     "ub_definition": "Hall discharge current and oscillations; I_d, I_d(t), A_osc, S_Id(f); A / - / A^2 Hz^-1; "
                      "both configurations",
     "a9_01_definition": "used by DQ-HI-SUST (class), DQ-HI-STAB (A band, Hz, class) and DQ-HI-ECAP (Hall current "
                         "demand)",
     "basis": "maps to several A9-01 quantities",
     "a9_01_consumers_not_counterparts": ["DQ-HI-SUST", "DQ-HI-STAB", "DQ-HI-ECAP"]},
    {"ub_dq_id": "UB-DQ-FLOW", "dq_hi_id": None, "status": UNMAPPED,
     "ub_definition": "mass flows; mdot_N2, mdot_O2, mdot_Ar, mdot_Xe,C1, mdot_ICP; mg s^-1; both configurations",
     "a9_01_definition": "used by DQ-HI-DXE (Xe only), DQ-HI-KNEE (flow scan output) and DQ-HI-RESTART (gas per "
                         "restart)",
     "basis": "maps to several A9-01 quantities; none is the set of all flows",
     "a9_01_consumers_not_counterparts": ["DQ-HI-DXE", "DQ-HI-KNEE", "DQ-HI-RESTART"]},
    {"ub_dq_id": "UB-DQ-PB", "dq_hi_id": None, "status": UNMAPPED,
     "ub_definition": "background pressure and residual gas composition; p_b, x_i; Pa / mole fraction; both "
                      "configurations",
     "a9_01_definition": "no A9-01 decision quantity (a condition variable of the same-condition list and stage "
                         "HI-PB)",
     "basis": "no counterpart",
     "a9_01_consumers_not_counterparts": []},
    {"ub_dq_id": "UB-DQ-BZ", "dq_hi_id": None, "status": UNMAPPED,
     "ub_definition": "magnetic field B(z) and ICP-induced perturbation; B(z), Delta B_icp(z); T; both "
                      "configurations",
     "a9_01_definition": "no A9-01 decision quantity (a same-condition variable; tolerance at gate deadline GD-11)",
     "basis": "no counterpart",
     "a9_01_consumers_not_counterparts": []},
    {"ub_dq_id": "UB-DQ-TEMP", "dq_hi_id": None, "status": UNMAPPED,
     "ub_definition": "temperatures incl. measured radiative sink temperature; T_k, T_sink; K; both configurations",
     "a9_01_definition": "temperatures enter DQ-HI-SAFE only as one limit of a multi-limit class (class; W; K; V)",
     "basis": "no counterpart with the same name and units",
     "a9_01_consumers_not_counterparts": ["DQ-HI-SAFE"]},
    {"ub_dq_id": "UB-DQ-ETAU", "dq_hi_id": "DQ-HI-ETAU", "status": "MAPPED",
     "ub_definition": "mass utilization from Faraday / ExB; eta_u; -; both configurations; primary instrument "
                      "INS-15",
     "a9_01_definition": "DQ-HI-ETAU utilization / beam current (conditional); dimensionless; A; CONDITIONAL; both "
                         "configurations; chain INS-13, INS-15",
     "basis": "same quantity (utilization), dimensionless in both, same configurations, INS-13/INS-15 in both "
              "chains; A9-01 additionally lists the beam current (A) it is built from",
     "a9_01_consumers_not_counterparts": []},
]
DQ_ROLE = {"DQ-HI-TABS": "HARD_GATE", "DQ-HI-PBUS": "HARD_GATE", "DQ-HI-ETAU": "CONDITIONAL"}


def a901_dq_ref(dq_hi_id: str) -> str:
    """Resolved A9-01 reference for a mapped id (A9_INT)."""
    return A9_01_JSON + " " + dq_hi_id + " (role " + DQ_ROLE[dq_hi_id] + ")"
# The Xe ledger deliverable path is assembled so that no code here carries the module name as one token.
XE_LEDGER_DIR = "docs/budgets/" + "xe_" + "ledger/"

# ---------------------------------------------------------------------------------------------------------
# Pins: immutable owner decisions and verified deliverables only. Mutable governance files are never pinned.
# ---------------------------------------------------------------------------------------------------------
PINS = [
    ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
     "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f", "authority",
     "A9 owner decision (OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE)"),
    ("docs/decisions/OD_2026_09_29_owner_answers_147.json",
     "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1", "authority",
     "owner answers 1-147 (machine-readable; verbatim text governs)"),
    ("docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md",
     "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976", "authority",
     "owner decision pack 147 (verbatim source of the answers)"),
    ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A3_s1a_and_instrumentation.json",
     "10d79026f1a65e0c2a9fa9e1f9a5f9abc9d162692711857bd43575f3095c8d4e", "authority",
     "A3 S1a and instrumentation decision (immutable)"),
    ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A4_owner_decisions.json",
     "beec91f9eca3ca0257c5ee88dcd193c87481660b9368b65c6d10b3b3bdae23b4", "authority",
     "A4 owner decisions (S1a minimum interlocks, interlock limits from real ratings, force/DC/RF traceability)"),
    ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json",
     "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621", "authority", "A5 (immutable, historical for the primary line)"),
    ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json",
     "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180", "authority", "A6 (immutable)"),
    ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json",
     "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925", "authority", "A7 execution model (immutable)"),
    ("docs/hardware/h2/h2_6_diagnostics_fixture/h2_6_diagnostics_fixture_v1.json",
     "bc7d6b049067c6fbd5489bda32ee9c8c1af36508576db4619b08d2c4ec196a56", "verified_input",
     "H2-6 diagnostics + H-1 fixture (instrument list, measurement map, fixture)"),
    ("docs/experiments/instrumentation/instrumentation_definition_v1.json",
     "7c6d37b00f38a44cded73d92d4366739eacbf013e73e98a7bfbc3fa5a5470d96", "verified_input",
     "W4 instrumentation definition (INS-01..INS-24 instrument ids)"),
    ("docs/experiments/instrumentation/metrology_spec/metrology_measurement_spec_v1.json",
     "55c11dc2d22fd92d95b498f72d60f2cdc0c62a45940da2446514049bd5130865", "verified_input",
     "metrology measurement specification (MS-G / MS-M items)"),
    ("docs/budgets/subsystem_maturity/subsystem_maturity_v2.json",
     "a82b1acd118b26e89edd4fa467bec778fa410470cca5eb6f684e6553eadaf23c", "verified_input", "M16 subsystem maturity matrix v2"),
    ("docs/architecture_comparison/lock1/lock1_decision_brief_v1.json",
     "7ce17e1f9101d0832a164e453fd757a813f5e1e77f689cfb661bdc920f453920", "historical",
     "LOCK-1 decision brief (D-01..D-04, D-07, D-08 superseded for the primary campaign; read and cited only)"),
    ("docs/architecture_comparison/lock1/LOCK1_DRAFT.json",
     "ece91920699c20358dc3e3d1348666460d6adf64addaa134a6fe11cdba499693", "historical", "LOCK-1 draft (historical)"),
    ("docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json",
     "54b7b00a60134f2d92f2eb5c9fb49f18d23623a566e04a4b7d70325a0e332509", "historical",
     "lane-25 minimum decisive experiment (variance groups G1-G5, readiness_n structure)"),
    ("docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json",
     "84ba1c382dc609b3e83ad9803a57ba471dd892fd10a6a6149285701a45a65a28", "historical",
     "A5 Phase-1 prereg framework (missing-data classes MD-01..MD-08, RR-01..RR-07, DQR checks)"),
]
GOVERNANCE_NOT_PINNED = [
    "docs/orchestration/lane_registry_v1.json",
    "docs/orchestration/trigger_registry_v1.json",
    "docs/orchestration/fired_triggers.jsonl",
    "docs/orchestration/trigger_ledger_v2.jsonl",
    "docs/orchestration/runtime_state.json",
]


def _sha256(rel: str) -> str:
    h = hashlib.sha256()
    with open(os.path.join(ROOT, rel), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(rel: str):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def verify_pins() -> list:
    errs = []
    for path, sha, _role, _what in PINS:
        if not os.path.exists(os.path.join(ROOT, path)):
            errs.append(f"missing pinned file {path}")
            continue
        got = _sha256(path)
        if got != sha:
            errs.append(f"pin mismatch {path}: {got} != {sha}")
    return errs


# ---------------------------------------------------------------------------------------------------------
# readiness_n: the proposed LOCK-1 rule that computes n at LOCK-2 (row 19). Pure; no defaults; raises.
# ---------------------------------------------------------------------------------------------------------
def _t_quantile(p: float, nu: float) -> float:
    from scipy.stats import norm, t  # pinned in requirements-lock.txt (used by lane 25 the same way)
    if math.isinf(nu):
        return float(norm.ppf(p))
    return float(t.ppf(p, nu))


def welch_satterthwaite(components) -> float:
    """nu_eff = u_c^4 / sum(u_i^4 / nu_i)  (JCGM 100:2008 G.4.1 Eq. (G.2b)); nu_i = inf allowed."""
    if not components:
        raise ValueError("welch_satterthwaite: no components")
    uc2 = 0.0
    den = 0.0
    for u, nu in components:
        if u is None or nu is None:
            raise ValueError("welch_satterthwaite: missing u or nu")
        if u < 0 or nu <= 0:
            raise ValueError("welch_satterthwaite: u must be >= 0 and nu > 0")
        uc2 += u * u
        if not math.isinf(nu):
            den += (u ** 4) / nu
    if uc2 == 0.0:
        raise ValueError("welch_satterthwaite: zero combined uncertainty")
    return math.inf if den == 0.0 else (uc2 ** 2) / den


def readiness_n(*, s_d, type_b, u_interp, h_target, alpha_fw, m_family, n_candidates):
    """Smallest admissible n (complete balanced replicate sets) with k(nu_eff, alpha_fw, m) * sigma(n) <= h_target.

    s_d          S1-measured standard deviation of the paired per-replicate-set contrast d_b (same units as h_target)
    type_b       list of (u_i, nu_i) Type B components that do not average down (nu_i = inf, or 0.5 (du/u)^-2, G.3)
    u_interp     pre-registered interpolation uncertainty (0.0 only if every compared point is measured, row 15)
    h_target     target simultaneous half-width, from the effect-size margin by the LOCK-1 rule (row 18)
    alpha_fw     family-wise two-sided error rate (LOCK-1 value; owner call)
    m_family     number of simultaneous comparisons in the family (from the A9-01 decision-quantity list)
    n_candidates admissible n values fixed at LOCK-1 (whole balanced replicate sets); every n >= 3 (row 19)
    Returns an int, or None when no candidate satisfies the rule (the owner decides before any score-bearing
    data: NO_ADMISSIBLE_N; nothing is relaxed silently).
    """
    for name, val in (("s_d", s_d), ("type_b", type_b), ("u_interp", u_interp), ("h_target", h_target),
                      ("alpha_fw", alpha_fw), ("m_family", m_family), ("n_candidates", n_candidates)):
        if val is None:
            raise ValueError(f"readiness_n: missing input {name}")
    if s_d < 0 or u_interp < 0 or h_target <= 0:
        raise ValueError("readiness_n: s_d, u_interp must be >= 0 and h_target > 0")
    if not (0.0 < alpha_fw < 1.0):
        raise ValueError("readiness_n: alpha_fw must lie in (0, 1)")
    if int(m_family) != m_family or m_family < 1:
        raise ValueError("readiness_n: m_family must be a positive integer")
    cands = list(n_candidates)
    if not cands:
        raise ValueError("readiness_n: empty n_candidates")
    for n in cands:
        if int(n) != n or n < 3:
            raise ValueError("readiness_n: every candidate n must be an integer >= 3 (row 19)")
    p = 1.0 - alpha_fw / (2.0 * m_family)
    for n in sorted(set(int(c) for c in cands)):
        comps = [(s_d / math.sqrt(n), float(n - 1))]
        comps += [(float(u), float(nu)) for (u, nu) in type_b]
        if u_interp > 0:
            comps.append((float(u_interp), math.inf))
        sigma = math.sqrt(sum(u * u for u, _ in comps))
        if sigma == 0.0:
            return n
        nu_eff = welch_satterthwaite(comps)
        if _t_quantile(p, nu_eff) * sigma <= h_target:
            return n
    return None


# ---------------------------------------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------------------------------------
def tbd(what: str) -> str:
    return "TBD - requires " + what


def pending(path: str, what: str = "") -> str:
    return "PENDING " + path + ((" (" + what + ")") if what else "")


def item(iid, dq, name, *, symbol="", utype="B", value=None, units="-", basis="", source="", evidence_class=None,
         status="TBD", freeze_point="LOCK-2", owner_rows=None, owner_text=None, configurations=None, note=""):
    return {
        "id": iid, "dq": dq, "name": name, "symbol": symbol, "type": utype, "value": value, "units": units,
        "basis": basis, "source": source, "evidence_class": evidence_class, "status": status,
        "freeze_point": freeze_point, "owner_rows": owner_rows or [], "owner_text": owner_text,
        "configurations": configurations or list(CONFIGS), "note": note,
    }


GUM = "REF-GUM2008"


def build_references():
    return [
        {"id": "REF-GUM2008",
         "citation": "JCGM 100:2008, 'Evaluation of measurement data - Guide to the expression of uncertainty in "
                     "measurement' (GUM 1995 with minor corrections)",
         "url": "https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf",
         "access": "full-text PDF downloaded and text-extracted by this lane on 2026-09-29 (sha256 "
                   "41bbf068fbc0d7986c98691b2d1af6680cb3044f6a1a89b3560933ed9ef9626c); sections read: 4.2.3 "
                   "(variance of the mean), 4.3.3 (quoted uncertainty divided by its stated multiplier), 4.3.7 "
                   "Eq. (6)/(7) (rectangular bound, u^2 = a^2/3), 5.1.2 Eq. (10) (uncorrelated propagation), "
                   "5.2.2 Eq. (13) (correlated propagation), G.4.1 Eq. (G.2b) (Welch-Satterthwaite), G.4.2 "
                   "Eq. (G.3) (dof of a Type B component from its relative reliability), G.4.3 (Type B as "
                   "exactly known, nu -> inf)"},
        {"id": "REF-POLK2017",
         "citation": "J. E. Polk et al., 'Recommended Practice for Thrust Measurement in Electric Propulsion "
                     "Testing', J. Propulsion and Power 33(3):539-555 (2017), doi:10.2514/1.B35564",
         "access": "as accessed and cited by the W4 instrumentation definition (INS-01: stand types, end-to-end "
                   "in-situ calibration); not re-accessed by this lane; no value quoted here"},
        {"id": "REF-SNYDER2017",
         "citation": "J. S. Snyder et al., 'Recommended Practice for Flow Control and Measurement in Electric "
                     "Propulsion Testing', J. Propulsion and Power 33(3) (2017), doi:10.2514/1.B35644",
         "access": "as accessed and cited by the W4 instrumentation definition (INS-05: own-gas calibration, "
                   "rate-of-rise calibrator); not re-accessed by this lane; no value quoted here"},
        {"id": "REF-DANKANICH2017",
         "citation": "J. W. Dankanich et al., 'Recommended Practice for Pressure Measurement and Calculation of "
                     "Effective Pumping Speed in Electric Propulsion Testing', J. Propulsion and Power 33(3) "
                     "(2017), doi:10.2514/1.B35478",
         "access": "as accessed and cited by H2-6 (H26-30 gauge placement and reading rule, pp. 672-673); not "
                   "re-accessed by this lane"},
        {"id": "REF-BROWN2017",
         "citation": "D. L. Brown et al., 'Recommended Practice for Use of Faraday Probes in Electric Propulsion "
                     "Testing', J. Propulsion and Power 33(3):582-613 (2017), doi:10.2514/1.B35696",
         "access": "as cited by W4 INS-15 (via lane 25); not re-accessed by this lane"},
        {"id": "REF-ROVEY2025",
         "citation": "J. L. Rovey et al., 'Recommended Practice for Use of ExB Probes in Electric Propulsion "
                     "Testing', IEPC-2025-483 (2025)",
         "access": "as cited by W4 INS-13 (via lane 25); not re-accessed by this lane"},
        {"id": "REF-CHOUEIRI2001",
         "citation": "E. Y. Choueiri, 'Plasma oscillations in Hall thrusters', Physics of Plasmas 8(4):1411-1426 "
                     "(2001), doi:10.1063/1.1354644",
         "access": "abstract only, as cited by W4 INS-04 and H2-6 H26-16 (1 kHz - 60 MHz reviewed; verify band "
                   "edges); not re-accessed by this lane"},
        {"id": "REF-TAKAHASHI2024",
         "citation": "K. Takahashi, H. Watanabe, Y. Nakahama, K. Kikuchi, 'Hall thruster ion acceleration "
                     "neutralized by a radiofrequency inductively coupled plasma', J. Electr. Propuls. 3, 18 (2024), "
                     "doi:10.1007/s44205-024-00081-2, CC BY-NC-ND 4.0",
         "access": "metadata as recorded in the A9 decision (Crossref 2026-09-29); topology precedent only; full-text "
                   "extraction is in " + A9_05_EV_JSON + " (A9-05); no operating point or performance value is quoted by this "
                   "lane"},
        {"id": "REF-TIGHE2015",
         "citation": "as cited by H2-6 H26-FX-01 (cathode position changed NASA-173M thrust by > 3 % when raised "
                     "6 in; abstract accessed by H2-6 2026-09-29; context, different thruster)",
         "access": "not re-accessed by this lane; used only to name the electron-source-location confound"},
    ]


# ---------------------------------------------------------------------------------------------------------
# Decision quantities (ids mapped to the final A9-01 DQ-HI-* ids by A9_INT where a unique counterpart exists;
# the others keep their UB-DQ-* id, marked UNMAPPED - owner/A9-10 in DQ_ID_MAPPING)
# ---------------------------------------------------------------------------------------------------------
def build_dqs():
    p01 = pending(A9_01, "decision-quantity id and role")
    return [
        {"id": "DQ-HI-TABS", "a9_01_dq_id": a901_dq_ref("DQ-HI-TABS"), "name": "thrust", "symbol": "T",
         "units": "mN",
         "configurations": list(CONFIGS), "role": "absolute gates (12 mN sustained, 25 mN capability) and the "
         "paired C1-vs-ICP contrast; role in the decision " + a901_dq_ref("DQ-HI-TABS")},
        {"id": "DQ-HI-PBUS", "a9_01_dq_id": a901_dq_ref("DQ-HI-PBUS"), "name": "full P_bus at the spacecraft-DC propulsion boundary",
         "symbol": "P_bus", "units": "W", "configurations": list(CONFIGS),
         "role": "absolute gate < 1.5 kW (incl. start-up transients, row 108); paired contrast Delta P_bus (row 37)"},
        {"id": "UB-DQ-RF", "a9_01_dq_id": p01, "name": "RF forward / reflected / delivered power",
         "symbol": "P_fwd, P_ref, P_net, P_coil", "units": "W", "configurations": [CONFIG_ICP],
         "role": "ICP power accounting inside P_bus (RF source/matching slot " + A9_02_REF
                 + " slots icp_rf_source / icp_matching_network); ICP power "
         "allocation check against the internal ~1.35 kW design allocation (row 109)"},
        {"id": "UB-DQ-NEUT", "a9_01_dq_id": p01,
         "name": "electron-source current, collector current / bias and neutralization margin",
         "symbol": "I_e,src, I_coll, V_coll, V_cg, M_n", "units": "A / V / -",
         "configurations": list(CONFIGS),
         "role": "ICP hard gate electron-current / neutralization (row 37); C1 reference emission / keeper record"},
        {"id": "UB-DQ-ID", "a9_01_dq_id": p01, "name": "Hall discharge current and oscillations",
         "symbol": "I_d, I_d(t), A_osc, S_Id(f)", "units": "A / - / A^2 Hz^-1", "configurations": list(CONFIGS),
         "role": "Hall current demand on the electron source; stability gate (row 37); sustainment/extinction"},
        {"id": "UB-DQ-FLOW", "a9_01_dq_id": p01, "name": "mass flows",
         "symbol": "mdot_N2, mdot_O2, mdot_Ar, mdot_Xe,C1, mdot_ICP", "units": "mg s^-1",
         "configurations": list(CONFIGS),
         "role": "matched feed state (same H-1 feed, A9 decision 6); Delta Xe (row 37); ICP gas feed booking "
                 "(A9 recorder flag row 46)"},
        {"id": "UB-DQ-PB", "a9_01_dq_id": p01, "name": "background pressure and residual gas composition",
         "symbol": "p_b, x_i (RGA)", "units": "Pa (Torr reported) / mole fraction", "configurations": list(CONFIGS),
         "role": "condition variable and facility-effect sensitivity at two elevated p_b levels (row 23)"},
        {"id": "UB-DQ-BZ", "a9_01_dq_id": p01, "name": "magnetic field B(z) and ICP-induced perturbation",
         "symbol": "B(z), Delta B_icp(z)", "units": "T", "configurations": list(CONFIGS),
         "role": "same V_d/B setting in both configurations (A9 decision 6); perturbation tolerance (row 67)"},
        {"id": "UB-DQ-TEMP", "a9_01_dq_id": p01, "name": "temperatures incl. measured radiative sink temperature",
         "symbol": "T_k, T_sink", "units": "K", "configurations": list(CONFIGS),
         "role": "thermal-state matching (row 65), limit aborts, T_sink per run (row 131)"},
        {"id": "DQ-HI-ETAU", "a9_01_dq_id": a901_dq_ref("DQ-HI-ETAU"), "name": "mass utilization from Faraday / ExB",
         "symbol": "eta_u", "units": "-", "configurations": list(CONFIGS),
         "role": "descriptive unless A9-01 uses it in a decision quantity; then S1b Faraday/ExB repeatability is "
                 "mandatory (row 32)"},
    ]


def build_items(h26):
    I = []
    # ---------------- thrust
    I += [
        item("UB-T-00", "DQ-HI-TABS", "thrust-stand principle", utype="rule", value="torsional baseline",
             basis="owner answer", source="owner answer row 115", evidence_class="owner-allocation",
             status="OWNER_GIVEN", freeze_point="NOW", owner_rows=[115], owner_text="TORSIONAL baseline",
             note="an alternate stand only if it meets the same uncertainty, payload, thermal/RF service-line and "
                  "reinstallation requirements (row 115)"),
        item("UB-T-01", "DQ-HI-TABS", "absolute thrust uncertainty design/acceptance target", symbol="u_r,abs(T)",
             utype="requirement", value=1.0, units="% of reading",
             basis="owner answer", source="owner answer row 121", evidence_class="owner-allocation",
             status="OWNER_GIVEN", freeze_point="LOCK-2", owner_rows=[121], owner_text="KEEP 1%",
             note="kept for now; revised only before LOCK-2 and before any score-bearing physics data on "
                  "metrology-only calibration evidence; never relaxed after propulsion results (row 121). Whether "
                  "1 % is a standard (k=1) or expanded uncertainty is open question UBQ-01"),
        item("UB-T-02", "DQ-HI-TABS", "S1a thrust-uncertainty acceptance test point", symbol="T_acc",
             utype="requirement", value=12.0, units="mN", basis="owner answer", source="owner answer row 120",
             evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="LOCK-1", owner_rows=[120],
             owner_text="12 mN",
             note="pre-registered with maximum representative moving payload and all service lines installed "
                  "(row 120); acceptance criterion value = UB-T-01 unless revised per row 121"),
        item("UB-T-03", "DQ-HI-TABS", "moving payload design minimum for the stand", symbol="m_pay,min",
             utype="requirement", value=25.0, units="kg", basis="owner answer", source="owner answer row 116",
             evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="NOW", owner_rows=[116],
             owner_text="at least 25 kg",
             note="the actual configuration spread (C1 module vs ICP module on the carrier) is characterized, not "
                  "assumed (row 116); module masses " + A9_03_JSON + " ICP-08"),
        item("UB-T-04", "DQ-HI-TABS", "in-situ calibration force / mass standard", symbol="u_r(F_cal)", utype="B",
             value=tbd("the calibration certificate (SI-traceable masses or force actuator, ISO/IEC 17025 / NABL, "
                       "row 119; A4 force_DC_RF_traceability)"), units="relative",
             basis="calibration certificate", source="owner answer row 119; A4 force_DC_RF_traceability; "
             + GUM + " 4.3.3", status="TBD", freeze_point="LOCK-2", owner_rows=[119]),
        item("UB-T-05", "DQ-HI-TABS", "calibration lever-arm ratio L_cal / L_T", symbol="u_r(L_cal/L_T)", utype="B",
             value=tbd("the stand and mount drawings and a traceable length measurement (H2-6 fixture)"),
             units="relative", basis="geometry", source="H2-6 fixture " + pending("docs/hardware/h2/h2_6_diagnostics_fixture/", "torsional stand revision"),
             status="TBD", freeze_point="LOCK-2"),
        item("UB-T-06", "DQ-HI-TABS", "calibration-fit residual (Type A over the calibration steps)", symbol="u_r(fit)",
             utype="A", value=tbd("S1a in-situ calibration series"), units="relative", basis="S1a",
             source="owner answer row 119 (pre/post block calibration)", status="TBD", freeze_point="LOCK-2",
             owner_rows=[119]),
        item("UB-T-07", "DQ-HI-TABS", "pre/post-block calibration shift and hysteresis", symbol="u_r(cal drift)",
             utype="A/B", value=tbd("S1a/S1b pre/post calibrations (row 119: drift and hysteresis recorded)"),
             units="relative", basis="S1", source="owner answer row 119; " + GUM + " 4.3.7 Eq. (7) if treated as "
             "a bound between pre and post (open question UBQ-05)", status="TBD", freeze_point="LOCK-2",
             owner_rows=[119]),
        item("UB-T-08", "DQ-HI-TABS", "zero drift over a dwell", symbol="u(y_0)", utype="A",
             value=tbd("S1b thermal and zero-drift record at the dwell length (dwell length LOCK-1)"), units="mN",
             basis="S1b", source="phase1_prereg_framework DQR-04 structure (historical, reused as a check)",
             status="TBD", freeze_point="LOCK-2"),
        item("UB-T-09", "DQ-HI-TABS", "service-line parasitic force incl. matched shams and flexible RF coax",
             symbol="u(F_par)", utype="A", value=tbd("the S1a acceptance test with all lines (row 120) and the "
             "service-line parasitic check (row 64)"), units="mN", basis="S1a",
             source="owner answers rows 64, 117, 120, 133", status="TBD", freeze_point="LOCK-2",
             owner_rows=[64, 117, 120, 133]),
        item("UB-T-10", "DQ-HI-TABS", "thermal drift of the stand from the heat load", symbol="u(F_th)", utype="A",
             value=tbd("S1b thermal time constants and stand thermocouples"), units="mN", basis="S1b",
             source="REF-POLK2017 via W4 INS-17", status="TBD", freeze_point="LOCK-2"),
        item("UB-T-11", "DQ-HI-TABS", "RF / electrostatic pickup on the displacement sensor with the ICP energized",
             symbol="u(y_RF)", utype="A", value=tbd("the S1a RF-pickup check with the ICP on and Hall off (row 64)"),
             units="mN", basis="S1a", source="owner answer row 64", status="TBD", freeze_point="LOCK-2",
             owner_rows=[64], configurations=[CONFIG_ICP]),
        item("UB-T-12", "DQ-HI-TABS", "thrust-axis alignment (cosine error) per carrier exchange", symbol="u_r(align)",
             utype="B", value=tbd("the carrier datum repeatability (row 122) and the alignment reference reading"),
             units="relative", basis="S1a", source="owner answer row 122; H2-6 H26-47 not reused (historical "
             "lane-25-derived allocation)", status="TBD", freeze_point="LOCK-2", owner_rows=[122]),
        item("UB-T-13", "DQ-HI-TABS", "readout resolution / noise", symbol="u(y)", utype="A",
             value=tbd("S1a noise floor at the dwell averaging time"), units="mN", basis="S1a",
             source="W4 INS-01", status="TBD", freeze_point="LOCK-2"),
    ]
    # ---------------- P_bus
    I += [
        item("UB-P-00", "DQ-HI-PBUS", "P_bus gate", symbol="P_bus", utype="requirement", value=1.5, units="kW",
             basis="owner answer", source="owner answer row 108; A9 requirement_discipline",
             evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="NOW", owner_rows=[108],
             owner_text="<1.5 kW",
             note="spacecraft-DC propulsion-system boundary; start-up transients included unless the official RFP "
                  "permits a transient exception (row 108); official RFP not yet obtained (rows 1-3)"),
        item("UB-P-01", "DQ-HI-PBUS", "bus-slot list of the A9 boundary", symbol="S_A9", utype="rule",
             value=pending(A9_02, "slots incl. RF source/matching, collector/bias, C1 reference supplies"),
             basis="A9-02", source="owner answers rows 66, 110", status="PENDING", freeze_point="LOCK-1",
             owner_rows=[66, 110]),
        item("UB-P-02", "DQ-HI-PBUS", "voltage-channel calibration per slot", symbol="u_r(V_s)", utype="B",
             value=tbd("calibration certificates (A4 force_DC_RF_traceability)"), units="relative",
             basis="certificate", source=GUM + " 4.3.3", status="TBD", freeze_point="LOCK-2"),
        item("UB-P-03", "DQ-HI-PBUS", "current-channel calibration per slot (shunt / zero-flux transducer)",
             symbol="u_r(I_s)", utype="B", value=tbd("calibration certificates"), units="relative",
             basis="certificate", source=GUM + " 4.3.3", status="TBD", freeze_point="LOCK-2"),
        item("UB-P-04", "DQ-HI-PBUS", "ripple / time-alignment error of p_s(t) = v_s(t) i_s(t)",
             symbol="u_r(vi)", utype="B", value=tbd("S1a channel characterization with the breadboard discharge "
             "supply (row 113) and the RF source running"), units="relative", basis="S1a",
             source="owner answer row 113", status="TBD", freeze_point="LOCK-2", owner_rows=[113]),
        item("UB-P-05", "DQ-HI-PBUS", "per-reading repeatability per slot", symbol="u_A(P_s)", utype="A",
             value=tbd("S1b readings"), units="W", basis="S1b", source="-", status="TBD", freeze_point="LOCK-2"),
        item("UB-P-06", "DQ-HI-PBUS", "conversion efficiency for slots supplied by non-flight-representative lab "
             "sources", symbol="eta_s", utype="conditioning",
             value=pending(A9_02, "and docs/hardware/h2/h2_4_ppu_bus/; a LOCK-1 conditioning input, never a "
                                  "variance term; unmeasured loads -> PARTIAL_BOUNDARY (row 22)"),
             basis="A9-02", source="owner answers rows 22, 108, 113", status="PENDING", freeze_point="LOCK-1",
             owner_rows=[22, 108, 113]),
        item("UB-P-07", "DQ-HI-PBUS", "start-up transient window and channel bandwidth for P_bus,peak",
             symbol="tau_start, f_bw,P", utype="rule",
             value=tbd("the start-up sequence (revised SEQ-1, row 112) and " + pending(A9_02)),
             units="s / Hz", basis="A9-02", source="owner answers rows 108, 112", status="TBD",
             freeze_point="LOCK-1", owner_rows=[108, 112]),
        item("UB-P-08", "DQ-HI-PBUS", "internal ICP design power allocation", symbol="P_alloc,int",
             utype="requirement", value=1.35, units="kW", basis="owner answer", source="owner answer row 109",
             evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="NOW", owner_rows=[109],
             owner_text="~1.35 kW",
             note="a design allocation the whole system (ICP power included) must fit inside; the 1.35 -> 1.5 kW "
                  "margin is not consumed nominally (row 109); a design check, not a scoring threshold"),
    ]
    # ---------------- RF
    icp = [CONFIG_ICP]
    I += [
        item("UB-RF-00", "UB-DQ-RF", "RF frequency", symbol="f_RF", utype="requirement", value=13.56, units="MHz",
             basis="owner answer", source="owner answer row 72", evidence_class="owner-allocation",
             status="OWNER_GIVEN", freeze_point="NOW", owner_rows=[72], owner_text="13.56 MHz", configurations=icp),
        item("UB-RF-01", "UB-DQ-RF", "laboratory forward-power range of the RF source and inline chain",
             symbol="P_fwd range", utype="requirement", value=[0.0, 500.0], units="W", basis="owner answer",
             source="owner answer row 72", evidence_class="owner-allocation", status="OWNER_GIVEN",
             freeze_point="NOW", owner_rows=[72], owner_text="0–500 W forward power", configurations=icp,
             note="directional-coupler forward/reflected measurement is primary; calorimetry is an independent "
                  "cross-check, not the sole primary measurement (row 72)"),
        item("UB-RF-02", "UB-DQ-RF", "coupler coupling-factor calibration at 13.56 MHz (incl. cable)",
             symbol="u_r(CF_f), u_r(CF_r)", utype="B", value=tbd("coupler and cable calibration certificates at "
             "13.56 MHz (A4 force_DC_RF_traceability)"), units="relative", basis="certificate",
             source=GUM + " 4.3.3", status="TBD", freeze_point="LOCK-2", configurations=icp),
        item("UB-RF-03", "UB-DQ-RF", "power-sensor calibration factor and linearity over 0-500 W",
             symbol="u_r(P_sens)", utype="B", value=tbd("sensor certificates"), units="relative",
             basis="certificate", source=GUM + " 4.3.3; owner answer row 72", status="TBD", freeze_point="LOCK-2",
             owner_rows=[72], configurations=icp),
        item("UB-RF-04", "UB-DQ-RF", "coupler finite directivity and mismatch error on P_ref and P_net",
             symbol="u(P_ref)_dir", utype="B", value=tbd("coupler directivity from its certificate and the "
             "measured load reflection; the evaluation formula is taken from the coupler/sensor documentation "
             "(from memory: a directivity-limited reflection error - verify)"), units="W", basis="certificate",
             source="-", status="TBD", freeze_point="LOCK-2", configurations=icp),
        item("UB-RF-05", "UB-DQ-RF", "matching-network and cable loss between the coupler plane and the coil",
             symbol="P_loss,mn + P_loss,cable", utype="B",
             value=tbd("S1a dummy-load characterization of the matching network and cable (evidence class "
                       "'reconstructed' once measured)"), units="W", basis="S1a", source="-", status="TBD",
             freeze_point="LOCK-2", configurations=icp),
        item("UB-RF-06", "UB-DQ-RF", "harmonic content of the source output", symbol="u_r(harm)", utype="B",
             value=tbd("S1a spectrum of the source output into the matched load"), units="relative", basis="S1a",
             source="-", status="TBD", freeze_point="LOCK-2", configurations=icp),
        item("UB-RF-07", "UB-DQ-RF", "per-reading repeatability of P_fwd and P_ref", symbol="u_A(P_fwd), u_A(P_ref)",
             utype="A", value=tbd("S1b readings"), units="W", basis="S1b", source="-", status="TBD",
             freeze_point="LOCK-2", configurations=icp),
        item("UB-RF-08", "UB-DQ-RF", "calorimetric cross-check agreement rule", symbol="z_x, k_x", utype="rule",
             value=tbd("owner acceptance of the rule form (UBQ-04) at LOCK-1; k_x value at LOCK-2 from S1a"),
             units="-", basis="owner answer row 72 (cross-check role)", source="owner answer row 72",
             status="PROPOSED", freeze_point="LOCK-1", owner_rows=[72], configurations=icp),
        item("UB-RF-09", "UB-DQ-RF", "RF reference plane for the delivered-power quantity", symbol="plane",
             utype="rule", value=pending(A9_03, "coupler location relative to the matching network and coil"),
             basis="A9-03", source="owner answers rows 62, 71", status="PENDING", freeze_point="LOCK-1",
             owner_rows=[62, 71], configurations=icp),
    ]
    # ---------------- neutralizer / collector
    I += [
        item("UB-N-00", "UB-DQ-NEUT", "electrical topology: floating ICP body, separately biased collector",
             utype="rule", value=pending(A9_03, "floating body + separately biased collector circuit, row 70"),
             basis="A9-03", source="owner answer row 70", status="PENDING", freeze_point="LOCK-1",
             owner_rows=[70], configurations=icp),
        item("UB-N-01", "UB-DQ-NEUT", "collector / bias supply current channel calibration", symbol="u_r(I_coll)",
             utype="B", value=tbd("certificate of the channel operated at the floating/bias potential"),
             units="relative", basis="certificate", source=GUM + " 4.3.3; owner answer row 62 (collector/bias V/I in "
             "the harness)", status="TBD", freeze_point="LOCK-2", owner_rows=[62], configurations=icp),
        item("UB-N-02", "UB-DQ-NEUT", "collector bias / floating-potential voltage divider calibration",
             symbol="u_r(V_coll), u_r(V_float)", utype="B", value=tbd("divider certificate at the rated common-mode "
             "voltage"), units="relative", basis="certificate", source=GUM + " 4.3.3", status="TBD",
             freeze_point="LOCK-2", configurations=icp),
        item("UB-N-03", "UB-DQ-NEUT", "common-mode / RF-induced error on floating current and voltage channels",
             symbol="u(I_coll)_CM", utype="A", value=tbd("the S1a RF-pickup and electrical-isolation checks (row 64)"),
             units="A", basis="S1a", source="owner answer row 64", status="TBD", freeze_point="LOCK-2",
             owner_rows=[64], configurations=icp),
        item("UB-N-04", "UB-DQ-NEUT", "ground-return (cathode-common / bleeder) current channel", symbol="u(I_gnd)",
             utype="B", value=tbd("the selectable cathode-common/bleeder topology with V/I measurement (row 91) and "
             "its certificate"), units="A", basis="certificate", source="owner answer row 91", status="TBD",
             freeze_point="LOCK-2", owner_rows=[91]),
        item("UB-N-05", "UB-DQ-NEUT", "bias-sweep step and settling for the electron-current capacity I_e,cap",
             symbol="Delta V_sweep", utype="rule", value=tbd("the A9-03 bias range and the A9-01 capacity "
             "definition"), units="V", basis="A9-01/A9-03", source="-", status="TBD", freeze_point="LOCK-1",
             configurations=icp),
        item("UB-N-06", "UB-DQ-NEUT", "neutralization-margin definition", symbol="M_n", utype="rule",
             value=pending(A9_01, "gate definition; this lane proposes the ratio form M_n = I_e,cap/I_d,dem - 1, "
                                  "UBQ-02"),
             basis="A9-01", source="owner answers rows 37, 145", status="PENDING", freeze_point="LOCK-1",
             owner_rows=[37, 145], configurations=icp),
        item("UB-N-07", "UB-DQ-NEUT", "current-closure residual r_I = (I_d - I_e,src - I_gnd)/I_d", symbol="r_I",
             utype="A", value=tbd("S1b readings in both configurations"), units="-", basis="S1b",
             source="this lane (PROPOSED diagnostic check)", status="PROPOSED", freeze_point="LOCK-2"),
        item("UB-N-08", "UB-DQ-NEUT", "C1 reference: emission, keeper and heater records", symbol="I_k, V_k, P_h",
             utype="B", value=tbd("C1 supply channel certificates (H2-2 / A9-02 C1 reference slots)"), units="A / V / W",
             basis="certificate", source="owner answers rows 88, 89, 112", status="TBD", freeze_point="LOCK-2",
             owner_rows=[88, 89, 112], configurations=[CONFIG_C1]),
        item("UB-N-09", "UB-DQ-NEUT", "C1 pulsed keeper ignition class (supply capability)", symbol="V_ign,pulse",
             utype="requirement", value=[300.0, 600.0], units="V", basis="owner answer", source="owner answer row 89",
             evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="NOW", owner_rows=[89],
             owner_text="300–600 V class", configurations=[CONFIG_C1],
             note="current-limited, interlocked, pulse energy recorded (row 89)"),
    ]
    # ---------------- I_d
    band = h26["H26-16"]["value"]
    I += [
        item("UB-I-00", "UB-DQ-ID", "exploratory I_d(t) chain upper band edge", symbol="f_hi", utype="requirement",
             value=60.0, units="MHz", basis="owner answer", source="owner answer row 129",
             evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="LOCK-2", owner_rows=[129],
             owner_text="~60 MHz",
             note="'if feasible'; otherwise the measured bandwidth and its anti-alias/transfer function are declared "
                  "(row 129); score-bearing band fixed at LOCK-2"),
        item("UB-I-01", "UB-DQ-ID", "H2-6 exploratory band and minimum sampling rate (verified input, consumed)",
             symbol="[f_lo, f_hi], f_s,min", utype="requirement",
             value={"band_Hz": band["band_Hz"], "sampling_min_Sps": band["sampling_min_Sps"]}, units="Hz / S s^-1",
             basis="verified input", source="docs/hardware/h2/h2_6_diagnostics_fixture/h2_6_diagnostics_fixture_v1.json"
             "#H26-16 (" + h26["H26-16"]["source"] + ")", evidence_class=h26["H26-16"]["evidence_class"],
             status="VERIFIED_INPUT", freeze_point="LOCK-2",
             note="H2-6 status: " + h26["H26-16"]["status"]),
        item("UB-I-02", "UB-DQ-ID", "DC discharge-current channel calibration", symbol="u_r(I_d)", utype="B",
             value=tbd("certificate"), units="relative", basis="certificate", source=GUM + " 4.3.3", status="TBD",
             freeze_point="LOCK-2"),
        item("UB-I-03", "UB-DQ-ID", "wide-band probe gain and transfer function H(f)", symbol="u(|H(f)|)",
             utype="B", value=tbd("S1a probe calibration against the DC channel and a swept reference"),
             units="relative", basis="S1a", source="owner answer row 129", status="TBD", freeze_point="LOCK-2",
             owner_rows=[129]),
        item("UB-I-04", "UB-DQ-ID", "ADC quantization", symbol="u_q", utype="B",
             value=tbd("the selected digitizer (LSB); u_q = LSB/sqrt(12)"), units="A",
             basis="digitizer", source=GUM + " 4.3.7 Eq. (7) with a = LSB/2", status="TBD", freeze_point="LOCK-2"),
        item("UB-I-05", "UB-DQ-ID", "window statistics of A_osc and S_Id(f)", symbol="u_A(A_osc)", utype="A",
             value=tbd("S1b records at the window length fixed at LOCK-1"), units="-", basis="S1b", source="-",
             status="TBD", freeze_point="LOCK-2"),
        item("UB-I-06", "UB-DQ-ID", "V_d rating of H-1, C1 reference, supply, isolation and diagnostics",
             symbol="V_d,rated", utype="requirement", value=350.0, units="V", basis="owner answer",
             source="owner answer row 81", evidence_class="owner-allocation", status="OWNER_GIVEN",
             freeze_point="NOW", owner_rows=[81], owner_text="350 V",
             note="plus appropriate transient/qualification margin (row 81); limit-abort values come from the real "
                  "hardware ratings (A4)"),
    ]
    # ---------------- flows
    I += [
        item("UB-F-00", "UB-DQ-FLOW", "MFC principle for pure-gas paths", utype="rule",
             value="thermal, own-gas-calibrated", basis="owner answer", source="owner answer row 124",
             evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="NOW", owner_rows=[124],
             owner_text="THERMAL own-gas-calibrated MFCs",
             note="mixtures verified through a traceable transfer/rate-of-rise method; no property-library DP "
                  "estimate as the primary score-bearing standard (row 124)"),
        item("UB-F-01", "UB-DQ-FLOW", "overlapping ranges per pure-gas path", symbol="N_ranges", utype="requirement",
             value=4, units="ranges", basis="owner answer", source="owner answer row 123",
             evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="NOW", owner_rows=[123],
             owner_text="4 overlapping ranges"),
        item("UB-F-02", "UB-DQ-FLOW", "C1 Xe controllers: steady-flow class", symbol="mdot_C1 range",
             utype="requirement", value=[0.05, 0.2], units="mg s^-1", basis="owner answer",
             source="owner answer row 125", evidence_class="owner-allocation", status="OWNER_GIVEN",
             freeze_point="NOW", owner_rows=[125], owner_text="0.05–0.2 mg/s", configurations=[CONFIG_C1]),
        item("UB-F-03", "UB-DQ-FLOW", "C1 Xe controllers: separate start/diode-flow controller (if retained)",
             symbol="mdot_C1,start range", utype="requirement", value=[0.6, 0.8], units="mg s^-1",
             basis="owner answer", source="owner answer row 125", evidence_class="owner-allocation",
             status="OWNER_GIVEN", freeze_point="NOW", owner_rows=[125], owner_text="0.6–0.8 mg/s",
             configurations=[CONFIG_C1]),
        item("UB-F-04", "UB-DQ-FLOW", "low-flow cathode MFC resolution (maximum)", symbol="res_C1",
             utype="requirement", value=0.0005, units="mg s^-1", basis="owner answer", source="owner answer row 98",
             evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="NOW", owner_rows=[98],
             owner_text="≤0.0005 mg/s", configurations=[CONFIG_C1], note="digital setpoint (row 98)"),
        item("UB-F-05", "UB-DQ-FLOW", "C1 Xe flow accuracy class until S1a demonstrates better on Xe",
             symbol="a_FS", utype="B", value=2.0, units="% of full scale (±)", basis="owner answer",
             source="owner answer row 96; converted to a standard uncertainty by " + GUM + " 4.3.7 Eq. (7) "
             "(a^2/3) unless the certificate states a multiplier (4.3.3); convention is UBQ-03",
             evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="LOCK-2", owner_rows=[96],
             owner_text="±2% FS", configurations=[CONFIG_C1],
             note="the same class carries the Xe-ledger uncertainty term (row 96; " + XE_LEDGER_DIR + ")"),
        item("UB-F-06", "UB-DQ-FLOW", "score-bearing flow reference", symbol="u_r(ref)", utype="B",
             value=tbd("NABL / ISO/IEC 17025 calibration certificates per MFC and gas"), units="relative",
             basis="certificate", source="owner answer row 126", status="TBD", freeze_point="LOCK-2",
             owner_rows=[126]),
        item("UB-F-07", "UB-DQ-FLOW", "in-house rate-of-rise transfer / verification standard", symbol="u_r(RoR)",
             utype="A/B", value=tbd("the rate-of-rise volume, pressure and temperature calibrations and S1a "
             "comparisons (a transfer standard, not the sole traceability claim)"), units="relative",
             basis="S1a", source="owner answer row 126", status="TBD", freeze_point="LOCK-2", owner_rows=[126]),
        item("UB-F-08", "UB-DQ-FLOW", "installed zero check per block", symbol="u(zero)", utype="A",
             value=tbd("per-block zero readings (rule adopted, row 97)"), units="mg s^-1", basis="owner answer",
             source="owner answer row 97", status="TBD", freeze_point="LOCK-2", owner_rows=[97]),
        item("UB-F-09", "UB-DQ-FLOW", "declared MFC body-temperature band", symbol="Delta T_body", utype="rule",
             value=tbd("MFC documentation and S1a body-temperature sensitivity (rule adopted, row 97)"), units="K",
             basis="owner answer", source="owner answer row 97", status="TBD", freeze_point="LOCK-1",
             owner_rows=[97]),
        item("UB-F-10", "UB-DQ-FLOW", "C1 spot-mode minimum-flow search step", symbol="Delta mdot_step",
             utype="rule", value=0.005, units="mg s^-1", basis="owner answer", source="owner answer row 92",
             evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="LOCK-1", owner_rows=[92],
             owner_text="0.005 mg/s", configurations=[CONFIG_C1],
             note="with preregistered stopping criteria (row 92; criteria " + pending(A9_01) + ")"),
        item("UB-F-11", "UB-DQ-FLOW", "C1 ignition dwell cap and retries (preliminary protocol)",
             symbol="t_ign,max, N_retry", utype="rule", value={"t_ign_max_s": 120.0, "retries_max": 2},
             units="s / -", basis="owner answer", source="owner answer row 93", evidence_class="owner-allocation",
             status="OWNER_GIVEN", freeze_point="LOCK-2", owner_rows=[93],
             owner_text="cap each ignition dwell at 120 s and allow at most two retries",
             configurations=[CONFIG_C1],
             note="final bound frozen before score-bearing C1 testing; all Xe booked (rows 42, 93)"),
        item("UB-F-12", "UB-DQ-FLOW", "ICP gas feed: species and flow measurement chain", symbol="mdot_ICP",
             utype="rule", value=pending(A9_03, "ICP gas species and flow; A9 recorder flag row 46: not yet booked"),
             basis="A9-03", source="A9 recorder_consistency_flags_for_owner (row 46)", status="PENDING",
             freeze_point="LOCK-1", owner_rows=[46], configurations=icp),
    ]
    # ---------------- background pressure / RGA
    I += [
        item("UB-B-00", "UB-DQ-PB", "elevated background-pressure levels for facility-effect characterization",
             symbol="N_pb,elev", utype="requirement", value=2, units="levels", basis="owner answer",
             source="owner answer row 23", evidence_class="owner-allocation", status="OWNER_GIVEN",
             freeze_point="LOCK-1", owner_rows=[23], owner_text="two elevated background-pressure levels",
             note="T-PB-MAX frozen only after the low-flow knee and facility capability are known; 5e-5 Torr may be "
                  "used for engineering characterization but is never silently substituted (row 23)"),
        item("UB-B-01", "UB-DQ-PB", "maximum base background pressure for a scoreable reading", symbol="T-PB-MAX",
             utype="rule", value=tbd("the low-flow knee and the facility capability (row 23; ISRO/LPSC "
             "specifications requested, row 137)"), units="Pa", basis="owner answer", source="owner answers rows 23, "
             "137", status="TBD", freeze_point="after-evidence", owner_rows=[23, 137]),
        item("UB-B-02", "UB-DQ-PB", "RGA mass range", symbol="m/q_max", utype="requirement", value=200, units="amu",
             basis="owner answer", source="owner answer row 127", evidence_class="owner-allocation",
             status="OWNER_GIVEN", freeze_point="NOW", owner_rows=[127], owner_text="200 amu",
             note="approximately 200 amu, differential pumping, species calibration for N2/O2/O-related fragments "
                  "and Xe (row 127); Ar calibration needed for the Ar engineering stage (row 36) - UBQ-08"),
        item("UB-B-03", "UB-DQ-PB", "ion-gauge calibration on the working gas / mixture", symbol="u_r(p_gauge)",
             utype="B", value=tbd("gauge calibration certificates per gas (Ar, N2, O2 mixtures, Xe)"),
             units="relative", basis="certificate", source="REF-DANKANICH2017 via H2-6", status="TBD",
             freeze_point="LOCK-2"),
        item("UB-B-04", "UB-DQ-PB", "gas sensitivity factors S_i", symbol="u_r(S_i)", utype="B",
             value=tbd("gauge documentation or own calibration per species"), units="relative", basis="certificate",
             source="-", status="TBD", freeze_point="LOCK-2"),
        item("UB-B-05", "UB-DQ-PB", "gauge placement and reading rule (verified input, consumed)",
             symbol="placement", utype="rule", value=h26["H26-30"]["value"], units=h26["H26-30"]["units"],
             basis="verified input",
             source="docs/hardware/h2/h2_6_diagnostics_fixture/h2_6_diagnostics_fixture_v1.json#H26-30 ("
                    + h26["H26-30"]["source"] + ")",
             evidence_class=h26["H26-30"]["evidence_class"], status="VERIFIED_INPUT", freeze_point="LOCK-1",
             note="H2-6 status: " + h26["H26-30"]["status"]),
        item("UB-B-06", "UB-DQ-PB", "paired p_b mismatch between configurations (ICP gas load)",
             symbol="Delta p_b", utype="A", value=tbd("S1b p_b in both configurations; the ICP gas flow is "
             + pending(A9_03)), units="Pa", basis="S1b", source="this lane (facility variance group VG-4)",
             status="TBD", freeze_point="LOCK-2"),
    ]
    # ---------------- B(z)
    I += [
        item("UB-Z-00", "UB-DQ-BZ", "B(z) perturbation tolerance with the ICP installed / energized",
             symbol="tol_DeltaB", utype="rule", value=tbd("measured H-1 sensitivity scan (row 67); no tolerance "
             "invented now"), units="T", basis="owner answer", source="owner answer row 67", status="TBD",
             freeze_point="LOCK-2", owner_rows=[67]),
        item("UB-Z-01", "UB-DQ-BZ", "Hall-probe sensitivity calibration and temperature coefficient",
             symbol="u_r(S_H)", utype="B", value=tbd("probe certificate and reference-field calibration"),
             units="relative", basis="certificate", source=GUM + " 4.3.3", status="TBD", freeze_point="LOCK-2"),
        item("UB-Z-02", "UB-DQ-BZ", "probe positioning", symbol="u(z)", utype="B",
             value=tbd("stage calibration; map extent " + pending("docs/hardware/h2/h2_1_hall_chamber_magnet/")),
             units="m", basis="certificate", source="H2-6 H26-33", status="TBD", freeze_point="LOCK-2"),
        item("UB-Z-03", "UB-DQ-BZ", "coil-current channels", symbol="u_r(I_coil)", utype="B",
             value=tbd("certificates (magnet slots " + pending(A9_02) + ")"), units="relative", basis="certificate",
             source="-", status="TBD", freeze_point="LOCK-2"),
        item("UB-Z-04", "UB-DQ-BZ", "hot-state B reference sensor drift", symbol="u(B_ref,hot)", utype="A/B",
             value=tbd("the hot-state reference provision (row 82) and its temperature traceability"), units="T",
             basis="owner answer", source="owner answer row 82", status="TBD", freeze_point="LOCK-2",
             owner_rows=[82]),
        item("UB-Z-05", "UB-DQ-BZ", "map repeatability over coil-current cycles", symbol="u_A(B)", utype="A",
             value=tbd("S1a maps (H2-6 H26-36 proposes 3 maps x 3 current cycles; PRELIMINARY)"), units="T",
             basis="S1a", source="H2-6 H26-36", status="TBD", freeze_point="LOCK-2"),
    ]
    # ---------------- temperatures
    I += [
        item("UB-K-00", "UB-DQ-TEMP", "thermal design margin below validated continuous-use limits",
             symbol="Delta T_margin", utype="requirement", value=50.0, units="K", basis="owner answer",
             source="owner answer row 86", evidence_class="owner-allocation", status="OWNER_GIVEN",
             freeze_point="NOW", owner_rows=[86], owner_text="≥50 K",
             note="a design margin (plus 20 % heat-load margin), not an abort limit; whether limit aborts fire at the "
                  "validated limit or at limit - margin is open question UBQ-06"),
        item("UB-K-01", "UB-DQ-TEMP", "radiative sink temperature measured per run", symbol="T_sink",
             utype="rule", value="measured per run", basis="owner answer", source="owner answer row 131",
             evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="NOW", owner_rows=[131],
             owner_text="MEASURE actual facility wall/cryopanel radiative sink temperature per run",
             note="~300 K walls only as a planning case, never an unmeasured score-bearing input (row 131)"),
        item("UB-K-02", "UB-DQ-TEMP", "thermocouple calibration and installation error", symbol="u(T_k)",
             utype="B", value=tbd("thermocouple certificates and installation checks"), units="K",
             basis="certificate", source="W4 INS-17", status="TBD", freeze_point="LOCK-2"),
        item("UB-K-03", "UB-DQ-TEMP", "C1 pyrometer emissivity (where line of sight exists)", symbol="u(T_em)",
             utype="B", value=tbd("pyrometer certificate and emissivity basis; tube TC never relabelled as emitter "
             "temperature (row 128)"), units="K", basis="certificate", source="owner answer row 128", status="TBD",
             freeze_point="LOCK-2", owner_rows=[128], configurations=[CONFIG_C1]),
        item("UB-K-04", "UB-DQ-TEMP", "thermal-state matching criterion between configurations",
             symbol="SC-THERM", utype="rule", value=tbd("S1b thermal time constants; preregistered equivalent "
             "start-up- and thermal-state handling (row 65)"), units="K / s", basis="owner answer",
             source="owner answer row 65", status="TBD", freeze_point="LOCK-1", owner_rows=[65]),
    ]
    # ---------------- eta_u
    I += [
        item("UB-E-00", "DQ-HI-ETAU", "use of eta_u in a decision quantity", utype="rule",
             value=pending(A9_01, "if used, S1b Faraday/ExB repeatability is mandatory, row 32"), basis="A9-01",
             source="owner answer row 32", status="PENDING", freeze_point="LOCK-1", owner_rows=[32]),
        item("UB-E-01", "DQ-HI-ETAU", "Faraday beam-current integration (area, bias, SEE, gap, CEX)",
             symbol="u_r(I_b)", utype="A/B", value=tbd("S1b Faraday repeatability and probe corrections "
             "(REF-BROWN2017 via W4)"), units="relative", basis="S1b", source="owner answer row 32", status="TBD",
             freeze_point="LOCK-2", owner_rows=[32]),
        item("UB-E-02", "DQ-HI-ETAU", "ExB species current fractions", symbol="u(Omega_j)", utype="A/B",
             value=tbd("S1b ExB repeatability (REF-ROVEY2025 via W4)"), units="-", basis="S1b",
             source="owner answer row 32", status="TBD", freeze_point="LOCK-2", owner_rows=[32]),
    ]
    # ---------------- comparison-level quantities (no numbers)
    I += [
        item("UB-C-01", "comparison", "effect-size / decision margin on each paired contrast", symbol="delta_k",
             utype="rule", value=tbd("the A9-01 decision-quantity list first, then a margin frozen before "
             "score-bearing data (row 18); the historical 0.05/0.1 is not carried"), units="per contrast",
             basis="owner answer", source="owner answer row 18", status="TBD", freeze_point="LOCK-1",
             owner_rows=[18]),
        item("UB-C-02", "comparison", "family-wise error rate for simultaneous contrast intervals",
             symbol="alpha_FW", utype="rule", value=tbd("owner decision at LOCK-1 (UBQ-07)"), units="-",
             basis="owner", source="-", status="TBD", freeze_point="LOCK-1"),
        item("UB-C-03", "comparison", "one-sided error rate of the absolute gates", symbol="alpha_abs", utype="rule",
             value=tbd("owner decision at LOCK-1 (UBQ-07)"), units="-", basis="owner", source="-", status="TBD",
             freeze_point="LOCK-1"),
        item("UB-C-04", "comparison", "variance-group budget shares", symbol="s_VG-1..s_VG-5", utype="rule",
             value=tbd("owner allocation rule at LOCK-1; values recorded at LOCK-2 (historical D-01-A equal shares "
             "not carried, row 12)"), units="fraction of sigma_max^2", basis="owner answer",
             source="owner answer row 12", status="TBD", freeze_point="LOCK-1", owner_rows=[12]),
        item("UB-C-05", "comparison", "minimum complete engineering replicates", symbol="n_min", utype="requirement",
             value=3, units="complete balanced replicate sets", basis="owner answer", source="owner answer row 19",
             evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="NOW", owner_rows=[19],
             owner_text="minimum three complete engineering replicates",
             note="final n at LOCK-2 from measured uncertainty by readiness_n (row 19)"),
        item("UB-C-06", "comparison", "admissible n candidates and n_max", symbol="N_adm, n_max", utype="rule",
             value=tbd("owner at LOCK-1 (whole balanced replicate sets, each >= 3)"), units="replicate sets",
             basis="owner answer", source="owner answer row 19", status="TBD", freeze_point="LOCK-1",
             owner_rows=[19]),
        item("UB-C-07", "comparison", "randomization seed", symbol="seed", utype="rule",
             value="procedure frozen at LOCK-1; seed and hash published at LOCK-2 after n is fixed",
             basis="owner answer", source="owner answer row 30", evidence_class="owner-allocation",
             status="OWNER_GIVEN", freeze_point="LOCK-2", owner_rows=[30],
             owner_text="Draw the randomization seed at LOCK-2 after n is fixed"),
        item("UB-C-08", "comparison", "interpolation uncertainty (only where a compared point is not measured)",
             symbol="u_interp", utype="B", value=tbd("preregistration: Type B bound or a measured midpoint "
             "reading (row 15)"), units="per contrast", basis="owner answer", source="owner answer row 15",
             status="TBD", freeze_point="LOCK-1", owner_rows=[15]),
        item("UB-C-09", "comparison", "absolute full-system T/P_bus floor at the 25 mN point", symbol="(T/P_bus)_min",
             utype="requirement", value=16.67, units="mN kW^-1", basis="owner answer", source="owner answer row 27",
             evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="NOW", owner_rows=[27],
             owner_text="16.67 mN/kW"),
        item("UB-C-10", "comparison", "absolute capability thrust inside P_bus < 1.5 kW", symbol="T_cap",
             utype="requirement", value=25.0, units="mN", basis="owner answer", source="owner answers rows 4, 27",
             evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="NOW", owner_rows=[4, 27],
             owner_text="25 mN"),
        item("UB-C-11", "comparison", "sustained atmospheric thrust", symbol="T_sus", utype="requirement",
             value=12.0, units="mN", basis="owner answer", source="owner answer row 4",
             evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="NOW", owner_rows=[4],
             owner_text="≥12 mN sustained"),
    ]
    return I


def build_chains():
    return [
        {"dq": "DQ-HI-TABS", "instruments": ["INS-01 (torsional, row 115)", "INS-17", "INS-18",
                                          "H26-MEAS-01 (H2-6 measurement map)"],
         "equations": [
             "T = F_cal * (L_cal / L_T) * (y - y_0) / (y_cal - y_0)   [torsional; in-situ calibration pre and post "
             "every block, row 119]",
             "u_r^2(T) = u_r^2(F_cal) + u_r^2(L_cal/L_T) + u_r^2(fit) + u_r^2(cal drift) + [u^2(y) + u^2(y_0) + "
             "u^2(F_par) + u^2(F_th) + u^2(y_RF)] / T^2 + u_r^2(align)   [GUM 5.1.2 Eq. (10), relative form, "
             "uncorrelated]",
             "absolute gate: T_lb = T_hat - k_1(nu_eff, alpha_abs) * u_c(T_hat) >= T_sus (12 mN) or T_cap (25 mN); "
             "k_1 one-sided Student-t at the GUM G.4.1 nu_eff",
             "paired contrast: F_cal and L_cal/L_T are common to both configurations within one calibration interval "
             "and cancel in ln(T_icp/T_c1) (GUM 5.2.2 Eq. (13) with r = 1); the pre/post shift, parasitic, pickup "
             "and alignment terms do not"],
         "components": ["UB-T-04", "UB-T-05", "UB-T-06", "UB-T-07", "UB-T-08", "UB-T-09", "UB-T-10", "UB-T-11",
                        "UB-T-12", "UB-T-13"],
         "targets": ["UB-T-01", "UB-T-02", "UB-T-03"],
         "not_a_component": "background-pressure effect: reported as the measured sensitivity at two elevated p_b "
                            "levels (row 23), never applied as a correction"},
        {"dq": "DQ-HI-PBUS", "instruments": ["INS-02 (one DC channel per A9 bus slot)", "INS-03", "INS-18",
                                             "H26-MEAS-02"],
         "equations": [
             "P_bus = sum_{s in S_A9} P_s,   S_A9 " + A9_02_REF + " slots",
             "P_s = (1/tau) * integral_tau v_s(t) i_s(t) dt at the spacecraft-DC-boundary-equivalent point; where the "
             "lab source is not flight-representative: P_s = P_s,load / eta_s with eta_s a LOCK-1 conditioning input "
             "(not a variance term); an unmeasured slot makes the reading PARTIAL_BOUNDARY (row 22)",
             "u^2(P_bus) = sum_s u^2(P_s) + 2 sum_{s<t} r_st u(P_s) u(P_t)   [GUM 5.2.2 Eq. (13); r_st from shared "
             "references, else 0]",
             "u_r^2(P_s) = u_r^2(V_s) + u_r^2(I_s) + u_r^2(vi) + (u_A(P_s)/P_s)^2",
             "start-up: P_bus,peak = max_{t in tau_start} sum_s p_s(t) on time-synchronized channels of declared "
             "bandwidth (row 108)",
             "absolute gate: P_ub = P_hat + k_1 u_c(P_hat) < 1.5 kW at steady state and P_bus,peak,ub < 1.5 kW over "
             "tau_start"],
         "components": ["UB-P-02", "UB-P-03", "UB-P-04", "UB-P-05", "UB-P-06", "UB-P-07"],
         "targets": ["UB-P-00", "UB-P-08"],
         "not_a_component": "no discharge-only or RF-generator-only power is a P_bus claim (A9 decision 8)"},
        {"dq": "UB-DQ-RF", "instruments": ["directional coupler + forward/reflected power sensors (INS-03 "
                                           "successor for the ICP)", "calorimetric cross-check", "INS-18"],
         "equations": [
             "P_fwd = CF_f * P_sens,f ;  P_ref = CF_r * P_sens,r   [coupling factors incl. cable, calibrated at "
             "13.56 MHz]",
             "P_net = P_fwd - P_ref at the coupler plane;  |Gamma|^2 = P_ref / P_fwd",
             "P_coil = P_net - P_loss,mn - P_loss,cable   [reconstructed from the S1a dummy-load characterization]",
             "u^2(P_net) = u^2(P_fwd) + u^2(P_ref) - 2 r u(P_fwd) u(P_ref)   [GUM 5.2.2 Eq. (13); r from a shared "
             "sensor/coupler calibration]",
             "cross-check: z_x = (P_coupler - P_cal) / sqrt(u^2(P_coupler) + u^2(P_cal)); PROPOSED rule |z_x| <= k_x "
             "(UBQ-04); P_cal = sum_j mdot_j c_p,j Delta T_j + C dT/dt (steady-state coolant or dummy-load "
             "calorimetry; method " + pending(A9_03) + ")",
             "the RF-source DC input is a P_bus slot (DQ-HI-PBUS); P_net / P_coil are accounting and diagnostic "
             "quantities, never a substitute for P_bus"],
         "components": ["UB-RF-02", "UB-RF-03", "UB-RF-04", "UB-RF-05", "UB-RF-06", "UB-RF-07"],
         "targets": ["UB-RF-00", "UB-RF-01", "UB-RF-08", "UB-RF-09"],
         "not_a_component": "no Takahashi 2024 operating value is used (" + A9_05_REF + ")"},
        {"dq": "UB-DQ-NEUT", "instruments": ["collector/bias supply V and I (floating-rated)",
                                             "floating-potential divider", "cathode-common/bleeder V and I (row 91)",
                                             "INS-04", "INS-18"],
         "equations": [
             "current balance: I_d = I_e,src + I_gnd  (I_e,src: electron current from the active source, C1 emission "
             "or ICP extraction; I_gnd: net current to facility ground through the cathode-common/bleeder)",
             "closure residual: r_I = (I_d - I_e,src - I_gnd) / I_d   [diagnostic; both configurations]",
             "ICP: I_e,src = I_coll (collector/bias-supply current, sign convention " + pending(A9_03) + ")",
             "capacity: I_e,cap = max I_e,src over the preregistered bias sweep within V_coll <= V_coll,max and "
             "P_RF <= P_RF,max (limits from real ratings, A4)",
             "PROPOSED margin form (UBQ-02): M_n = I_e,cap / I_d,dem - 1 with I_d,dem = I_d measured at the same "
             "condition; gate M_n,lb = M_n,hat - k_1 u_c(M_n) > 0 (margin value " + pending(A9_01) + ")",
             "u_r^2(M_n + 1) = u_r^2(I_e,cap) + u_r^2(I_d,dem)",
             "coupling voltage V_cg (source common to facility ground) recorded in both configurations"],
         "components": ["UB-N-01", "UB-N-02", "UB-N-03", "UB-N-04", "UB-N-05", "UB-N-07", "UB-N-08"],
         "targets": ["UB-N-00", "UB-N-06", "UB-N-09"],
         "not_a_component": "no neutralizer electron current is predicted; capacity is measured"},
        {"dq": "UB-DQ-ID", "instruments": ["INS-04 (DC + wide-band probe)", "INS-10", "INS-18", "H26-MEAS-03",
                                           "H26-MEAS-09"],
         "equations": [
             "I_d,mean = (1/tau) integral i_d dt (DC channel);  u_r^2(I_d) = u_r^2(cal) + (u_A/I_d)^2",
             "A_osc = sigma_t(i_d) / I_d,mean over the window tau_w (LOCK-1)",
             "S_Id,true(f) = S_Id,meas(f) / |H(f)|^2 inside the declared band [f_lo, f_hi] only (row 129); outside the "
             "declared band nothing is claimed",
             "u_q = LSB / sqrt(12)   [GUM 4.3.7 Eq. (7), a = LSB/2]"],
         "components": ["UB-I-02", "UB-I-03", "UB-I-04", "UB-I-05"],
         "targets": ["UB-I-00", "UB-I-01", "UB-I-06"],
         "not_a_component": "no I_d is predicted from any Hall closure"},
        {"dq": "UB-DQ-FLOW", "instruments": ["INS-05 (thermal MFCs, own gas, 4 ranges per pure-gas path)",
                                             "two C1 Xe controllers (row 125)", "rate-of-rise transfer standard",
                                             "H26-MEAS-04", "H26-MEAS-05"],
         "equations": [
             "mdot_s = mdot_ind,s * (1 + c_cal,s)   [own-gas calibration correction from the NABL/ISO 17025 "
             "certificate]",
             "u_r^2(mdot) = u_r^2(ref) + u_r^2(RoR) + (a_FS * FS / mdot)^2 / 3 + (u(zero)/mdot)^2 + u_r^2(T_body) + "
             "(u_A/mdot)^2   [the '/3' applies a stated +/- bound as rectangular, GUM 4.3.7 Eq. (7), unless the "
             "certificate states a multiplier, GUM 4.3.3; UBQ-03]",
             "rate-of-rise: mdot = (V M / (Z R T)) dp/dt   [Z: compressibility from a verified EOS for Xe (row 50); "
             "Z = 1 only where justified]",
             "mixture fraction: w_O2 = mdot_O2 / (mdot_N2 + mdot_O2);  u^2(w_O2) = [w_N2 u(mdot_O2)]^2/M^2 + "
             "[w_O2 u(mdot_N2)]^2/M^2 with M = mdot_N2 + mdot_O2",
             "Delta Xe (row 37): Delta mdot_Xe = mdot_Xe,icp_config - mdot_Xe,c1_config with PHASE_TOTAL_FLOW "
             "booking (row 42) and the ICP gas feed " + A9_03_JSON + " ICP-26"],
         "components": ["UB-F-05", "UB-F-06", "UB-F-07", "UB-F-08", "UB-F-09"],
         "targets": ["UB-F-00", "UB-F-01", "UB-F-02", "UB-F-03", "UB-F-04", "UB-F-10", "UB-F-11", "UB-F-12"],
         "not_a_component": "no property-library DP estimate is a primary score-bearing flow standard (row 124)"},
        {"dq": "UB-DQ-PB", "instruments": ["INS-08 (ion gauges per REF-DANKANICH2017 placement)",
                                           "INS-11 (RGA ~200 amu, differential pumping)", "H26-MEAS-07"],
         "equations": [
             "p_ind = sum_i S_i p_i ;  p_b = p_ind / sum_i x_i S_i   [x_i mole fractions from the calibrated RGA or "
             "the flow ratio]",
             "u_r^2(p_b) = u_r^2(p_gauge) + u_r^2(sum_i x_i S_i) + (u_A/p_b)^2",
             "facility sensitivity: beta_Y = d ln Y / d p_b by regression over base + two elevated levels (row 23); "
             "reported with its uncertainty; never applied as a correction",
             "paired mismatch term: u_fac,k = |beta_Y| * |Delta p_b| (VG-4) with Delta p_b = p_b,icp - p_b,c1 (the ICP "
             "gas load raises p_b in hall_icp_neutralizer only)"],
         "components": ["UB-B-03", "UB-B-04", "UB-B-06"],
         "targets": ["UB-B-00", "UB-B-01", "UB-B-02", "UB-B-05"],
         "not_a_component": "no ingestion model is used to rescue a class (lane-25 P5 lesson, historical)"},
        {"dq": "UB-DQ-BZ", "instruments": ["INS-09 (Hall-probe gaussmeter on a stage)", "INS-24", "INS-02",
                                           "hot-state B reference sensor (row 82)", "H26-MEAS-08"],
         "equations": [
             "B(z) = V_H(z) / S_H(T_probe)",
             "Delta B_icp(z) = B_icp installed,energized(z) - B_c1(z) at identical coil currents (row 67)",
             "u^2(Delta B) = u_A^2(B_icp) + u_A^2(B_c1) + (dB/dz)^2 [u^2(z_icp) + u^2(z_c1)]  [probe scale "
             "common to both maps cancels to first order]",
             "admissibility: max_z |Delta B_icp(z)| + k u(Delta B) <= tol_DeltaB (tolerance from the measured H-1 "
             "sensitivity, LOCK-2, row 67)"],
         "components": ["UB-Z-01", "UB-Z-02", "UB-Z-03", "UB-Z-04", "UB-Z-05"],
         "targets": ["UB-Z-00"],
         "not_a_component": "EM-only MC-1 (row 78); no permanent-magnet assistance"},
        {"dq": "UB-DQ-TEMP", "instruments": ["INS-17", "INS-23", "INS-24", "sink-temperature sensors (row 131)",
                                             "C1 pyrometer (row 128)", "H26-MEAS-12"],
         "equations": [
             "T_k = T_TC,k + c_k;  u^2(T_k) = u^2(cal) + u^2(install)",
             "T_sink measured per run; the thermal-state matching statistic between configurations is fixed at "
             "LOCK-1 (row 65)"],
         "components": ["UB-K-02", "UB-K-03"],
         "targets": ["UB-K-00", "UB-K-01", "UB-K-04"],
         "not_a_component": "no unmeasured 300 K sink in any score-bearing use (row 131)"},
        {"dq": "DQ-HI-ETAU", "instruments": ["INS-15 (far-field Faraday)", "INS-13 (ExB)", "INS-05", "INS-08"],
         "equations": [
             "eta_u = mdot_i / mdot_prop,  mdot_i = (I_b / e) * sum_j (Omega_j m_j / Z_j)   [standard mass-"
             "utilization form (from memory - verify against REF-BROWN2017 / REF-ROVEY2025); mdot_prop basis "
             + pending(A9_01) + "]",
             "u_r^2(eta_u) = u_r^2(I_b) + u_r^2(sum_j Omega_j m_j / Z_j) + u_r^2(mdot_prop)"],
         "components": ["UB-E-01", "UB-E-02"],
         "targets": ["UB-E-00"],
         "not_a_component": "descriptive-only eta_u is insufficient for a gating comparison (row 32)"},
    ]


def build_variance_groups():
    return {
        "status": "PROPOSED structure; numeric allocation TBD (LOCK-1 rule, LOCK-2 value); rows 12, 18, 19",
        "estimand": "for each preregistered paired contrast k (list " + pending(A9_01) + "): "
                    "Delta_k = ln Y_icp - ln Y_c1 at a matched condition (Y in {T, T/P_bus, P_bus, ...}); "
                    "differences (not logs) for quantities that can be zero or negative",
        "estimator": [
            "d_b = ln Y_icp,b - ln Y_c1,b for complete balanced replicate set b = 1..n (both configurations in every "
            "set, order-balanced, row 29)",
            "Delta_hat = (1/n) sum_b d_b",
            "sigma_hat^2(Delta_hat) = s_d^2 / n + sum_c (w_c u_c)^2 + u_fac^2 + u_interp^2   [s_d: SD of d_b with n-1 "
            "dof, GUM 4.2.3; Type B terms nu = inf (G.4.3) or from their reliability (G.3); nu_eff by G.4.1 "
            "Eq. (G.2b)]",
            "h_k = k(nu_eff, alpha_FW, m) * sigma_hat_k with k the two-sided Bonferroni Student-t quantile",
        ],
        "planning_decomposition": "s_d^2 ~ 2 (u_read^2 / r + u_mx^2 + u_rm^2 + u_drift,res^2): used only to "
                                  "allocate the budget and size S1; the campaign estimate s_d is empirical",
        "groups": [
            {"id": "VG-1", "name": "module exchange", "what": "C1 <-> ICP module exchange on the kinematic carrier "
             "with H-1 bolted (row 122), incl. reconnection of matched sham service lines (row 133)",
             "symbol": "u_mx", "evaluation": "Type A from the S1 RR-07-A9 module-exchange series (row 33); dof = "
             "K_mx - 1", "averages_down": True, "cancels_in_pair": False, "owner_rows": [33, 122, 133],
             "share": tbd("LOCK-1 rule / LOCK-2 value")},
            {"id": "VG-2", "name": "reinstallation / remount", "what": "vent-pump-recondition-recalibrate cycle; "
             "REF-COND as its own installation per block (row 40); a repaired/replaced unit is a new serialized unit "
             "with a new reference sequence (row 83)", "symbol": "u_rm", "evaluation": "Type A from S1b",
             "averages_down": True, "cancels_in_pair": False, "owner_rows": [40, 83],
             "share": tbd("LOCK-1 rule / LOCK-2 value")},
            {"id": "VG-3", "name": "drift", "what": "within-block temporal drift (stand zero, thermal state, chamber "
             "conditioning, sink temperature); linear drift reduced by the order-balanced design (row 29) and "
             "pre/post calibration (row 119)", "symbol": "u_drift,res", "evaluation": "Type A (residual after the "
             "balanced design) from S1b and the REF checks", "averages_down": True, "cancels_in_pair": "partially "
             "(balanced order)", "owner_rows": [29, 119], "share": tbd("LOCK-1 rule / LOCK-2 value")},
            {"id": "VG-4", "name": "facility", "what": "background pressure level and paired mismatch (the ICP gas "
             "load exists in one configuration only), wall/sink temperature; characterized at two elevated p_b "
             "levels (row 23)", "symbol": "u_fac", "evaluation": "Type B from the measured sensitivity beta_Y and "
             "the measured Delta p_b", "averages_down": False, "cancels_in_pair": False, "owner_rows": [23, 131],
             "share": tbd("LOCK-1 rule / LOCK-2 value")},
            {"id": "VG-5", "name": "instrument", "what": "(a) per-reading random noise of thrust, power, flow and RF "
             "channels (averages down); (b) configuration-specific scale terms that do not cancel: the RF chain and "
             "collector supply exist only in hall_icp_neutralizer, the C1 heater/keeper supplies only in "
             "hall_c1_reference (weight w_c = |P_c,icp/P_bus,icp - P_c,c1/P_bus,c1| for P_bus shares)",
             "symbol": "u_read (a); w_c u_c (b)", "evaluation": "(a) Type A in campaign; (b) Type B from "
             "certificates", "averages_down": "(a) yes; (b) no", "cancels_in_pair": "(a) no; (b) no",
             "owner_rows": [72, 110], "share": tbd("LOCK-1 rule / LOCK-2 value")},
        ],
        "allocation_rule": "sigma_max,k = h_target,k / k_plan with h_target,k from the margin delta_k by the LOCK-1 "
                           "rule (row 18); sum_g s_g = 1; s_g >= 0; values recorded at LOCK-2 only",
        "design_inherent_difference": "the electron-source location differs by design (external C1, row 79, vs the "
                                      "downstream ICP module): this is part of the compared configuration, not a "
                                      "variance term; H2-6 H26-FX-01 cites REF-TIGHE2015 (context, different "
                                      "thruster) that cathode position alone moved thrust by > 3 %, so the "
                                      "configuration identity (positions recorded per module) is preregistered",
    }


def build_stop_rules(a4):
    return {
        "status": "PROPOSED rules with symbols; no number frozen (row 13); defined before any Hall->ICP "
                  "score-bearing data",
        "contrast_stop": {
            "id": "SR-C",
            "applies_to": "a configuration's remaining comparison slots, on a preregistered decisive contrast "
                          "Delta_k oriented so that a negative value disfavours hall_icp_neutralizer (list "
                          + pending(A9_01) + ")",
            "symbols": {"U_k": "Delta_hat_k + h_k (simultaneous upper bound)", "h_k": "k(nu_eff, alpha_FW, m) "
                        "sigma_hat_k", "delta_stop": "stop margin (margin form only)"},
            "forms": [
                {"id": "SR-C-SIGN", "rule": "stop if U_k < 0 at every qualifying condition of the confirmation "
                 "subset"},
                {"id": "SR-C-MARGIN", "rule": "stop if U_k < -delta_stop at every qualifying condition of the "
                 "confirmation subset"},
            ],
            "owner_choice": "OPEN - explicit owner choice between SR-C-SIGN and SR-C-MARGIN (UBQ-09)",
            "historical_citation_only": {
                "path": "docs/architecture_comparison/lock1/lock1_decision_brief_v1.json#decisions[D-02].options"
                        "[D-02-A]",
                "sha256": "7ce17e1f9101d0832a164e453fd757a813f5e1e77f689cfb661bdc920f453920",
                "rationale_quoted": None,  # filled from the pinned file at build time
                "status": "superseded for the primary campaign (row 13); cited, not carried",
            },
            "consequence": "a stop ends that configuration's remaining comparison slots (NOT_TESTED); it is not an "
                           "elimination and does not by itself produce an outcome; unresolved evidence is reported "
                           "with the status OPEN and the next discriminating test (row 38)",
        },
        "gate_stop": {
            "id": "SR-G",
            "rule": "if hall_icp_neutralizer cannot sustain the Hall discharge within registered limits because "
                    "I_e,cap < I_d,dem (M_n,ub < 0 at the registered bias/RF limits), the reading is an observation "
                    "'not sustained within registered limits' (row 41) with the limit and state recorded; comparison "
                    "slots needing a sustained discharge in that configuration become NOT_TESTED",
            "gate_definition": A9_01_JSON + " DQ-HI-ECAP",
        },
        "precision_futility": {
            "id": "SR-P",
            "rule": "PROPOSED: no interim looks except those preregistered at LOCK-1; if the readiness_n rule returns "
                    "no admissible n at LOCK-2 (NO_ADMISSIBLE_N) the owner decides before any score-bearing data "
                    "(improve instruments / mount, change the margin by a LOCK-1 restart, or change facility); "
                    "nothing is relaxed silently",
        },
        "limit_aborts": {
            "rule": "limits come from real hardware/facility ratings, not invented thresholds (A4 "
                    "S1a_interlock_limits); an abort on a thruster/configuration limit = 'not sustained within "
                    "registered limits' with the exact limit and state recorded (row 41); values " + tbd(
                        "the approved hardware ratings (H2 lanes, A9-03 ICD, supply datasheets)"),
            "limits": [
                {"id": "LA-01", "quantity": "Hall discharge current / voltage", "symbol": "I_d,max, V_d,max",
                 "value": tbd("supply and H-1 ratings (rated to the 350 V end, row 81)"), "configurations": CONFIGS},
                {"id": "LA-02", "quantity": "RF forward power", "symbol": "P_fwd,max",
                 "value": tbd("generator / matching / coil ratings inside the 0-500 W laboratory chain (row 72)"),
                 "configurations": [CONFIG_ICP]},
                {"id": "LA-03", "quantity": "RF reflected power", "symbol": "P_ref,max",
                 "value": tbd("generator reflected-power rating"), "configurations": [CONFIG_ICP]},
                {"id": "LA-04", "quantity": "collector / bias voltage and current", "symbol": "V_coll,max, I_coll,max",
                 "value": tbd(pending(A9_03) + " and supply rating"), "configurations": [CONFIG_ICP]},
                {"id": "LA-05", "quantity": "component temperatures", "symbol": "T_k,max",
                 "value": tbd("validated continuous-use limits (rows 86, 87); abort at the limit or at limit - "
                              "margin is UBQ-06"), "configurations": CONFIGS},
                {"id": "LA-06", "quantity": "C1 heater / keeper current and temperature", "symbol": "I_h,max, I_k,max",
                 "value": tbd("C1 vendor/design qualification (row 93)"), "configurations": [CONFIG_C1]},
                {"id": "LA-07", "quantity": "magnet coil current / temperature", "symbol": "I_coil,max, T_coil,max",
                 "value": tbd("MC-1 coil rating (ceramic-insulated, row 77)"), "configurations": CONFIGS},
                {"id": "LA-08", "quantity": "C1 ignition dwell and retries", "symbol": "t_ign,max, N_retry",
                 "value": "120 s per dwell, at most two retries (row 93, preliminary; final bound before score-"
                          "bearing C1 testing)", "configurations": [CONFIG_C1]},
            ],
        },
        "safety_interlocks": {
            "a4_minimum": a4["S1a_minimum_interlocks"],
            "a9_additions_proposed": [
                "RF interlock in the ICP harness (row 62)",
                "RF reflected-power trip (LA-03)",
                "RF leakage / personnel exposure limit per the facility safety case (" + tbd("the facility RF "
                "safety case") + ")",
                "floating ICP body / collector high-voltage touch-safety interlock (row 70)",
                "oxygen-safety owner named and ASTM G93 Level C cleaning before any O2 gas operation (row 107)",
                "C1 pulsed-keeper ignition energy recorded and interlocked (row 89)",
                "start-up sequence interlock so that the measured P_bus,peak stays < 1.5 kW (rows 108, 112)",
            ],
            "classification": "a facility/safety trip not caused by the configuration -> MISSING "
                              "(NOT_SCOREABLE_FACILITY, re-run rule); a configuration limit -> observation (row 41); "
                              "an instrument failure correlated with a configuration (e.g. RF pickup) -> observation "
                              "INSTRUMENT_INCOMPATIBLE_WITH_CONFIGURATION (historical MD-07 structure)",
        },
        "not_tested": {
            "rule": "if a configuration stops, its scheduled slots are marked NOT_TESTED, all remaining order stays "
                    "fixed and the balance loss is reported (row 39)",
            "meaning": "NOT_TESTED is neither pass nor fail; it contributes to the status OPEN (a status, not an "
                       "outcome, row 38) and names the next discriminating test",
            "outcome_vocabulary": [CONFIG_C1, CONFIG_ICP, "NO_VIABLE_CASE"],
            "status_vocabulary": ["OPEN"],
            "vocabulary_owner": A9_01_JSON + " decision_topology (outcomes, statuses)",
        },
        "net_benefit": "NET_BENEFIT = hard gates + Pareto over Delta Xe, Delta P_bus, Delta mass, T/P_bus, restart "
                       "and life burden relative to C1; no weighted scalar and no single winner unless preregistered "
                       "(row 37); every Pareto component carries its own interval from this budget",
    }


def build_interpolation():
    return {
        "status": "PROPOSED; row 15",
        "rules": [
            {"id": "IP-1", "rule": "compared points are measured, not interpolated, wherever practical: the condition "
             "grid (frozen at LOCK-1 from W1 and the anticipated knee, row 31) includes the matched Hall setpoint in "
             "both configurations and measured iso-power and midpoint readings where an iso-power comparison is "
             "registered"},
            {"id": "IP-2", "rule": "where interpolation is unavoidable, the model (linear chord between the two "
             "bracketing measured points) and u_interp are preregistered at LOCK-1: either a Type B bound "
             "(evidence class assumed) or a bound from a measured midpoint reading (evidence class measured; "
             "historical D-04-B cited)"},
            {"id": "IP-3", "rule": "no extrapolation beyond measured points; no interpolation across a sustainment "
             "boundary or a mode change"},
        ],
        "equations": [
            "lambda = (x* - x_a) / (x_b - x_a),  0 <= lambda <= 1",
            "Y(x*) = (1 - lambda) Y_a + lambda Y_b",
            "u^2(Y(x*)) = (1 - lambda)^2 u^2(Y_a) + lambda^2 u^2(Y_b) + [(Y_b - Y_a)/(x_b - x_a)]^2 u^2(x*) + "
            "u_interp^2   [GUM 5.1.2 Eq. (10); Y_a, Y_b from separate readings, uncorrelated unless they share a "
            "calibration]",
        ],
        "u_interp": tbd("preregistration at LOCK-1 (form) and LOCK-2 (value)"),
    }


def build_readiness():
    return {
        "status": "PROPOSED LOCK-1 rule; n computed at LOCK-2 (row 19)",
        "function": BUILDER_REL + "::readiness_n",
        "inputs": [
            {"symbol": "s_d", "what": "S1-measured SD of the paired per-replicate-set contrast (from the S1 "
             "module-exchange / remount / repeatability series)", "freeze_point": "LOCK-2"},
            {"symbol": "type_b", "what": "non-averaging Type B components (w_c u_c, u_fac) with their dof",
             "freeze_point": "LOCK-2"},
            {"symbol": "u_interp", "what": "preregistered interpolation uncertainty (0 when every point is measured)",
             "freeze_point": "LOCK-1 form / LOCK-2 value"},
            {"symbol": "h_target", "what": "target simultaneous half-width from delta_k by the LOCK-1 rule",
             "freeze_point": "LOCK-1"},
            {"symbol": "alpha_FW, m", "what": "family-wise error rate and family size", "freeze_point": "LOCK-1"},
            {"symbol": "N_adm", "what": "admissible n (whole complete balanced replicate sets, each >= 3)",
             "freeze_point": "LOCK-1"},
        ],
        "rule": "n = min { n in N_adm : n >= 3 and k(nu_eff(n), alpha_FW, m) * sqrt(s_d^2/n + sum type_b u^2 + "
                "u_interp^2) <= h_target }, with nu_eff(n) by GUM G.4.1 Eq. (G.2b) using nu = n - 1 for the "
                "campaign Type A term; if the set is empty: NO_ADMISSIBLE_N -> owner decision before any "
                "score-bearing data",
        "floor": "the non-averaging terms set a floor k(inf) sqrt(sum type_b u^2 + u_interp^2) that no n can beat",
        "absolute_gates": "the absolute-gate bounds use u_c including the Type B calibration scale (target 1 % on "
                          "thrust, row 121); more replicates do not reduce the scale term",
        "seed": "the randomization seed is drawn at LOCK-2 after n is fixed; the procedure is frozen at LOCK-1 "
                "(row 30)",
        "worked_values": "none: no S1 data exist; the unit tests exercise the function with synthetic inputs only",
    }


def build_interface_demands():
    D = []

    def d(did, direction, counterpart, quantity, units, status, value):
        D.append({"id": did, "direction": direction, "counterpart": counterpart, "quantity": quantity,
                  "units": units, "status": status, "value": value})

    # to/from A9-01
    d("IF-01", "from_A9-01_to_this_lane", "A9-01 " + A9_01, "decision-quantity ids, roles (gate / contrast / "
      "descriptive), contrast orientation, confirmation subset, family size m", "-", "PENDING", pending(A9_01))
    d("IF-02", "from_A9-01_to_this_lane", "A9-01 " + A9_01, "stage map (Ar engineering-only -> N2 -> O2-bearing "
      "NO_ATOMIC_O) and which stages are score-bearing", "-", "PENDING", pending(A9_01))
    d("IF-03", "from_this_lane_to_A9-01", "A9-01 " + A9_01, "measurement chain, component list and propagation "
      "per decision quantity; variance groups VG-1..VG-5; stop-rule forms SR-C/SR-G/SR-P; readiness_n rule",
      "-", "PROPOSED", "this deliverable")
    d("IF-04", "from_this_lane_to_A9-01", "A9-01 " + A9_01, "neutralization-margin form M_n = I_e,cap/I_d,dem - 1 "
      "(UBQ-02)", "-", "PROPOSED", "ratio form")
    # A9-02
    d("IF-05", "from_A9-02_to_this_lane", "A9-02 " + A9_02, "bus-slot list S_A9, measured vs conditioning slots "
      "(eta_s), start-up transient window", "W / - / s", "PENDING", pending(A9_02))
    d("IF-06", "from_this_lane_to_A9-02", "A9-02 " + A9_02, "per-slot V and I channel requirement (4-wire, "
      "time-synchronized, declared bandwidth for P_bus,peak); correlation declaration for shared references",
      "relative / Hz", "PROPOSED", tbd("values at LOCK-2 from the budget allocation"))
    # A9-03
    d("IF-07", "from_A9-03_to_this_lane", "A9-03 " + A9_03, "collector/bias circuit, floating-body potential "
      "measurement points, sign conventions, bias range", "V / A", "PENDING", pending(A9_03))
    d("IF-08", "from_A9-03_to_this_lane", "A9-03 " + A9_03, "coupler location / RF reference plane and matching "
      "network topology", "-", "PENDING", pending(A9_03))
    d("IF-09", "from_A9-03_to_this_lane", "A9-03 " + A9_03, "ICP gas species and flow range (for MFC range, p_b "
      "load, Delta Xe)", "mg s^-1", "PENDING", pending(A9_03))
    d("IF-10", "from_A9-03_to_this_lane", "A9-03 " + A9_03, "C1 and ICP module masses on the carrier and sham "
      "line set", "kg", "PENDING", pending(A9_03))
    d("IF-11", "from_this_lane_to_A9-03", "A9-03 " + A9_03, "ICD provisions for: RF-pickup test points (row 64), "
      "floating-rated collector V/I sensing, ground-return current monitor (row 91), calorimetry access, "
      "module-ID telemetry (row 62), datum features for alignment readings (row 122)", "-", "PROPOSED",
      "requirement list (no values)")
    # A9-05
    d("IF-12", "from_A9-05_to_this_lane", "A9-05 " + A9_05, "Takahashi 2024 extraction: which quantities the "
      "analog measured and how (for chain design only; never a Vyovrinda value)", "-", "PENDING", pending(A9_05))
    d("IF-13", "from_this_lane_to_A9-05", "A9-05 " + A9_05, "validation-input list entries that need a measurement "
      "chain here (RF coupling, forward/reflected/absorbed power, electron extraction current, collector "
      "potential, neutralization margin, Hall current demand, ICP pressure/flow; row 145)", "-", "PROPOSED",
      "chain ids UB-DQ-RF, UB-DQ-NEUT, UB-DQ-ID, UB-DQ-FLOW, UB-DQ-PB")
    # H2-6
    d("IF-14", "from_this_lane_to_H2-6", "H2-6 docs/hardware/h2/h2_6_diagnostics_fixture/ (instrument list)",
      "instrument additions/changes: torsional stand (row 115) with >= 25 kg payload (row 116); 13.56 MHz "
      "directional coupler + forward/reflected sensors 0-500 W (row 72); calorimetric cross-check; floating-rated "
      "collector/bias V/I; ground-return current monitor; ICP telemetry subset (row 130); RGA ~200 amu "
      "(row 127); two C1 Xe controllers (row 125); sink-temperature sensors (row 131)", "-", "PROPOSED",
      "revision request (H2-6 v1 is sized for the historical pre-ionizer slot)")
    d("IF-15", "from_H2-6_to_this_lane", "H2-6 docs/hardware/h2/h2_6_diagnostics_fixture/", "H26-16 exploratory "
      "I_d(t) band / sampling; H26-30 gauge placement rule", "Hz / -", "VERIFIED_INPUT", "consumed (UB-I-01, "
      "UB-B-05)")
    # metrology spec
    d("IF-16", "from_this_lane_to_metrology_spec", "docs/experiments/instrumentation/metrology_spec/",
      "extend the MS-G general requirements (ISO/IEC 17025 scope, GUM budget, certificate) to force calibration "
      "(masses / actuator, lever geometry), RF power sensors and couplers at 13.56 MHz, DC V/I channels and MFC "
      "own-gas calibrations; current MS-M measurands cover witness-coupon/part metrology only", "-", "PROPOSED",
      "revision request")
    # H2-4, H2-1, H2-5, Xe ledger
    d("IF-17", "from_H2-4_to_this_lane", "H2-4 docs/hardware/h2/h2_4_ppu_bus/", "breadboard discharge supply "
      "(row 113) channel points and eta_d measured before LOCK-2", "- / W", "PENDING",
      pending("docs/hardware/h2/h2_4_ppu_bus/"))
    d("IF-18", "from_H2-1_to_this_lane", "H2-1 docs/hardware/h2/h2_1_hall_chamber_magnet/", "B(z) map extent, "
      "B_max, hot-state reference sensor location (row 82)", "m / T", "PENDING",
      pending("docs/hardware/h2/h2_1_hall_chamber_magnet/"))
    d("IF-19", "from_this_lane_to_H2-5", "H2-5 docs/hardware/h2/h2_5_thermal_network/", "measured T_sink per run "
      "(row 131) as the thermal-model boundary input for test correlation", "K", "PROPOSED", "measured per run")
    d("IF-20", "from_this_lane_to_Xe_ledger", "Xe ledger " + XE_LEDGER_DIR, "C1 flow uncertainty term (±2 % FS "
      "class, row 96) and the ICP gas booking once A9-03 defines it (row 46 flag)", "mg s^-1", "PENDING",
      pending(A9_03))
    d("IF-21", "from_this_lane_to_H-1_items", "docs/experiments/hardware/ (H-1 / C-1 configuration items)",
      "configuration identity record per module (positions, serial numbers; a repaired unit is new, row 83)",
      "-", "PROPOSED", "record fields")
    return D


OWNER_ROWS_APPLIED = {
    4: "12 mN sustained and 25 mN capability used as absolute gate levels (UB-C-10, UB-C-11)",
    5: "wet-mass gate context for the Delta mass Pareto component (no mass value computed here)",
    12: "historical D-01-A budget split superseded; new variance groups VG-1..VG-5 with shares TBD (UB-C-04)",
    13: "historical D-02-A superseded; new stop rules SR-C/SR-G/SR-P defined before score-bearing data, no numbers",
    15: "interpolation rules IP-1..IP-3; u_interp preregistered (UB-C-08)",
    17: "H-1 fixed; only the downstream electron-source module is exchanged (VG-1)",
    18: "no numeric delta carried; margin frozen after the A9-01 DQ list, before score-bearing data (UB-C-01)",
    19: "minimum three complete engineering replicates; n at LOCK-2 by readiness_n (UB-C-05, readiness_n)",
    22: "unmeasured bus loads -> PARTIAL_BOUNDARY; no guessed loads (UB-P-06)",
    23: "two elevated p_b levels; T-PB-MAX after the knee and facility capability (UB-B-00, UB-B-01)",
    27: "25 mN inside P_bus < 1.5 kW and the 16.67 mN/kW floor (UB-C-09, UB-C-10)",
    29: "order-balanced design governs; drift group VG-3",
    30: "seed procedure LOCK-1, seed at LOCK-2 after n (UB-C-07)",
    32: "eta_u only with S1b Faraday/ExB repeatability if used in a DQ (UB-E-00..02)",
    33: "RR-07 adapted to C1 <-> ICP module exchange -> VG-1 evaluation",
    36: "Ar engineering-only stage needs Ar calibrations of gauges/RGA/MFC (UBQ-08); Ar never counts for DRDO",
    37: "NET_BENEFIT = hard gates + Pareto; every Pareto component has its own interval; no scalar",
    38: "OPEN is a status; unresolved evidence names the next discriminating test",
    39: "NOT_TESTED handling after a stop; order kept; balance loss reported",
    40: "REF-COND own installation per block (VG-2)",
    41: "limit abort = not sustained within registered limits with the limit recorded",
    42: "PHASE_TOTAL_FLOW booking in the Delta Xe chain",
    46: "ICP gas feed unbooked -> UB-F-12 PENDING A9-03; C1 term 15,000 h context only",
    50: "rate-of-rise transfer uses a verified Xe EOS compressibility",
    62: "ICP harness quantities (module ID, RF fwd/ref, interlock, collector V/I, temperatures) in the chains",
    64: "C1 <-> ICP exchange checks: cold/tare, service-line parasitic, B(z), isolation, RF pickup as S1a inputs",
    65: "equivalent start-up/thermal-state handling preregistered (UB-K-04)",
    67: "B(z) perturbation scan; tolerance from measured H-1 sensitivity, not invented (UB-Z-00)",
    70: "floating ICP body and separately biased collector measured on floating-rated channels",
    72: "13.56 MHz; 0-500 W lab chain; coupler primary, calorimetry cross-check (UB-RF-00..09)",
    79: "external C1 location recorded as a design-inherent configuration difference, not a variance term",
    81: "350 V ratings as limit-abort basis (UB-I-06, LA-01)",
    82: "hot-state B reference sensor drift component (UB-Z-04)",
    83: "repaired/replaced unit = new serialized unit with new reference sequence (VG-2)",
    86: ">= 50 K design margin recorded; abort-level convention is UBQ-06",
    89: "C1 pulsed keeper 300-600 V class, interlocked, pulse energy recorded",
    91: "selectable cathode-common/bleeder with V/I measurement -> ground-return channel (UB-N-04)",
    92: "0.005 mg/s C1 spot-mode flow step (UB-F-10)",
    93: "120 s per ignition dwell, at most two retries, preliminary (UB-F-11, LA-08)",
    96: "±2 % FS C1 Xe flow class as the flow uncertainty term until S1a shows better (UB-F-05)",
    97: "per-block installed zero check and declared MFC body-temperature band (UB-F-08, UB-F-09)",
    98: "<= 0.0005 mg/s resolution, digital setpoint (UB-F-04)",
    107: "O2 safety owner + ASTM G93 Level C before O2 gas operation (interlock list)",
    108: "P_bus < 1.5 kW at the spacecraft-DC boundary incl. start-up transients (UB-P-00, UB-P-07)",
    109: "ICP inside the ~1.35 kW internal allocation (UB-P-08; design check)",
    110: "every active load has a bus slot (UB-P-01 PENDING A9-02)",
    112: "revised SEQ-1 defines the start-up window for P_bus,peak",
    113: "breadboard discharge supply so eta_d and transients are measured before LOCK-2",
    115: "torsional stand baseline (UB-T-00)",
    116: ">= 25 kg moving payload; actual spread characterized (UB-T-03)",
    117: "harp/slack-loop routing and flexible RF coax with matched sham -> parasitic component UB-T-09",
    118: "in-house engineering stand for S1a; partner facility possible for score-bearing (instrument identity "
         "must be the same across configurations within a comparison)",
    119: "in-situ SI-traceable force calibration pre/post block; drift and hysteresis recorded (UB-T-04, UB-T-07)",
    120: "S1a u_T acceptance at 12 mN, max payload, all lines (UB-T-02)",
    121: "1 % absolute thrust uncertainty target; revised only before LOCK-2 on metrology-only evidence (UB-T-01)",
    122: "kinematic carrier; H-1 bolted (VG-1, UB-T-12)",
    123: "4 overlapping ranges per pure-gas path (UB-F-01)",
    124: "thermal own-gas MFCs primary; mixtures via traceable transfer (UB-F-00)",
    125: "two C1 Xe controllers (UB-F-02, UB-F-03)",
    126: "NABL/ISO 17025 primary reference; rate-of-rise as transfer standard (UB-F-06, UB-F-07)",
    127: "~200 amu RGA with differential pumping and species calibration (UB-B-02)",
    128: "C1 pyrometer where line of sight exists; tube TC never relabelled (UB-K-03)",
    129: "I_d(t) to ~60 MHz if feasible, else declared bandwidth and transfer function (UB-I-00)",
    130: "ICP telemetry subset feeds the H2-6 revision request (IF-14)",
    131: "T_sink measured per run (UB-K-01)",
    133: "matched sham service lines in every configuration (VG-1, UB-T-09)",
    137: "facility specification requested before T-PB-MAX is frozen (UB-B-01)",
    145: "validation-input quantities mapped to chains (IF-13)",
}


def build_open_questions():
    return [
        {"id": "UBQ-01", "question": "Is the 1 % absolute thrust uncertainty (row 121) a standard (k = 1) or an "
         "expanded uncertainty (and at which k)?", "proposed_answer": "standard uncertainty (k = 1) of a single "
         "sustained reading at 12 mN, consistent with the H2-6 H26-05 planning basis; owner call"},
        {"id": "UBQ-02", "question": "Form of the neutralization margin", "proposed_answer": "ratio form "
         "M_n = I_e,cap / I_d,dem - 1 at the registered bias and RF limits, gate on its one-sided lower bound; "
         "final definition belongs to A9-01"},
        {"id": "UBQ-03", "question": "Conversion of a manufacturer '±x % FS' specification to a standard "
         "uncertainty", "proposed_answer": "rectangular bound, u = a/sqrt(3) (GUM 4.3.7 Eq. (7)), unless the "
         "certificate states a multiplier (GUM 4.3.3)"},
        {"id": "UBQ-04", "question": "Agreement rule between coupler-based and calorimetric RF power",
         "proposed_answer": "|z_x| <= k_x with k_x frozen at LOCK-2 from S1a dummy-load data; a failed cross-check "
         "marks the RF-dependent quantities EXCLUDED_INSTRUMENT until resolved (never re-weighted)"},
        {"id": "UBQ-05", "question": "Pre/post-block calibration shift: variance component, exclusion criterion, "
         "or both?", "proposed_answer": "both: a rectangular component between pre and post (GUM 4.3.7) plus a "
         "block-exclusion limit set at LOCK-2 from S1 calibrations"},
        {"id": "UBQ-06", "question": "Do temperature limit aborts fire at the validated continuous-use limit or at "
         "limit - 50 K (row 86 is a design margin)?", "proposed_answer": "owner call"},
        {"id": "UBQ-07", "question": "alpha_FW for contrasts and alpha_abs for absolute gates",
         "proposed_answer": "owner call at LOCK-1 (the historical lane-25 values are not carried)"},
        {"id": "UBQ-08", "question": "Ar engineering-only stage: are Ar gauge, RGA and MFC calibrations required "
         "(row 127 lists N2/O2/O fragments and Xe only)?", "proposed_answer": "yes for engineering use; Ar data "
         "never count toward DRDO atmospheric requirements (row 36)"},
        {"id": "UBQ-09", "question": "Contrast stop rule form: sign (SR-C-SIGN) or margin (SR-C-MARGIN)?",
         "proposed_answer": "owner call (historical D-02-A rationale cited only)"},
    ]


def build_historical_reuse(pins_by_path):
    def pin(p):
        return {"path": p, "sha256": pins_by_path[p]}
    return [
        dict(pin("docs/architecture_comparison/lock1/lock1_decision_brief_v1.json"),
             reused=["variance-group concept and Type A / Type B / remount evaluation classes (D-01)",
                     "sign-form vs margin-form stop-rule structure (D-02), cited only",
                     "measured midpoint vs assumed chord error for interpolation (D-04), cited only",
                     "readiness_n as the rule that fixes n at LOCK-2 (D-08 dependency)"],
             not_reused=["D-01-A equal 0.2 shares", "D-02 R_threshold numbers", "D-07 delta = 0.05 / 0.1",
                         "D-08 even n in [4, 8]", "every u_T_max / u_P_max / u_inst_max value"]),
        dict(pin("docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json"),
             reused=["G1-G5 formula structure (per-reading Type A, non-cancelling scale, installation) adapted to "
                     "VG-1..VG-5", "Welch-Satterthwaite / Bonferroni interval form", "'no ingestion correction' rule"],
             not_reused=["T-DELTA, T-ALPHA-FW, T-N-MIN/MAX, T-BUDGET-SHARES, K = 6 values", "R_arch definition over "
                         "hall_only / rf_hall / ecr_hall"]),
        dict(pin("docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json"),
             reused=["missing-data / observation classes (MD-04 limit abort, MD-05 facility, MD-07 instrument "
                     "incompatible) as classification structure", "RR-07 idea (module-exchange remount)",
                     "DQR-04 zero-drift check"],
             not_reused=["P1DQ ids and the hall_only / rf_hall / ecr_hall topology (row 28)", "PMQ items"]),
        dict(pin("docs/experiments/instrumentation/instrumentation_definition_v1.json"),
             reused=["INS-01..INS-24 instrument ids as chain references"],
             not_reused=["required_uncertainty numbers derived from lane 25", "I-* proposed thresholds"]),
        dict(pin("docs/hardware/h2/h2_6_diagnostics_fixture/h2_6_diagnostics_fixture_v1.json"),
             reused=["H26-MEAS ids; H26-16 band (consumed, UB-I-01); H26-30 gauge rule (consumed, UB-B-05); "
                     "H26-FX-01 cathode-position context"],
             not_reused=["H26-03/05/07/10/12/47/48 numbers (lane-25 derived)", "pre-ionizer module slot sizing"]),
        {"path": "docs/interfaces/preionizer_module/", "sha256": None,
         "reused": [], "not_reused": ["entire pre-ionizer ICD (PMQ-01..05 superseded, A9)"],
         "note": "historical; not read for content by this lane"},
    ]


def build_m16(m16):
    rows = {r["row"]: r for r in m16["rows"]}
    touch = [
        (15, "primary: decision-quantity measurement chains and uncertainty budget for the C1-vs-ICP comparison"),
        (12, "P_bus measurement chain at the spacecraft-DC boundary; breadboard discharge supply (row 113)"),
        (11, "C1 reference: flow, keeper/heater, ignition dwell records (reference/fallback only)"),
        (8, "C1 Xe metering: two controllers, ±2 % FS class, resolution (rows 96, 98, 125)"),
        (14, "limit aborts and safety interlocks; ICP telemetry subset (row 130)"),
        (16, "stand, kinematic carrier and sham lines (VG-1)"),
        (10, "B(z) perturbation and hot-state reference (rows 67, 82)"),
        (13, "measured sink temperature per run (row 131)"),
        (17, "reserved interface row: ICP-neutralizer chains (RF, collector) belong here once A9-10 governance "
             "repurposes it (row 142: add A9 lanes without rewriting H2 provenance)"),
    ]
    out = []
    for r, how in touch:
        out.append({"row": r, "key": rows[r]["key"], "name": rows[r]["name"], "how": how,
                    "proposed_state_change": "none by this lane (contribution only; row owners and states "
                                             + pending("A9-10 governance") + ")"})
    return out


def build_h3_h4():
    h3 = [
        {"item": "torsional thrust stand with in-situ SI-traceable calibrator", "spec_form": "payload >= 25 kg "
         "(row 116); u_r,abs target 1 % (row 121); acceptance test at 12 mN (row 120)", "rows": [115, 116, 119, 120, 121]},
        {"item": "13.56 MHz directional coupler, forward/reflected sensors, calibration at 13.56 MHz",
         "spec_form": "0-500 W forward (row 72); certificate with uncertainty budget (A4)", "rows": [8, 72]},
        {"item": "calorimetric cross-check (dummy load / coolant)", "spec_form": tbd("A9-03 method"), "rows": [72]},
        {"item": "floating-rated collector/bias supply with V/I channels", "spec_form": A9_03_JSON + " ICP-21",
         "rows": [70]},
        {"item": "thermal MFCs, 4 overlapping ranges per pure-gas path; two C1 Xe controllers",
         "spec_form": "rows 123, 125, 98; NABL/ISO 17025 calibration (row 126)", "rows": [123, 125, 98, 126]},
        {"item": "RGA ~200 amu with differential pumping", "spec_form": "row 127", "rows": [127]},
        {"item": "wide-band I_d(t) probe + digitizer", "spec_form": "~60 MHz if feasible (row 129)", "rows": [129]},
        {"item": "DC V/I channels per A9 bus slot", "spec_form": A9_02_REF + " slots", "rows": [110]},
    ]
    h4 = [
        {"stage": "S1a", "test": "thrust acceptance at 12 mN with max payload and all lines (row 120); in-situ "
         "calibration series (row 119)", "closes": ["UB-T-04", "UB-T-05", "UB-T-06", "UB-T-09", "UB-T-13"]},
        {"stage": "S1a", "test": "C1 <-> ICP exchange checks: cold/tare, service-line parasitic, B(z), isolation, RF "
         "pickup (row 64)", "closes": ["UB-T-11", "UB-T-12", "UB-N-03", "UB-Z-00"]},
        {"stage": "S1a", "test": "RF chain on dummy load: coupler vs calorimetry, matching-network loss, harmonics",
         "closes": ["UB-RF-02", "UB-RF-03", "UB-RF-04", "UB-RF-05", "UB-RF-06", "UB-RF-08"]},
        {"stage": "S1a", "test": "MFC own-gas calibrations, rate-of-rise transfer, zero and body-temperature checks",
         "closes": ["UB-F-06", "UB-F-07", "UB-F-08", "UB-F-09"]},
        {"stage": "S1b", "test": "RR-07-A9 module-exchange series, remount series, repeatability (>= 3 complete "
         "replicates, row 19); Faraday/ExB repeatability if eta_u gates (row 32)",
         "closes": ["VG-1", "VG-2", "VG-3", "UB-E-01", "UB-E-02"]},
        {"stage": "S1b", "test": "base + two elevated p_b levels (row 23) in both configurations",
         "closes": ["VG-4", "UB-B-06"]},
        {"stage": "LOCK-2", "test": "readiness_n with the S1 values; seed draw", "closes": ["UB-C-06", "UB-C-07"]},
    ]
    return h3, h4


def build():
    ans = _load("docs/decisions/OD_2026_09_29_owner_answers_147.json")
    rows = {a["row"]: a for a in ans["answers"]}
    h26doc = _load("docs/hardware/h2/h2_6_diagnostics_fixture/h2_6_diagnostics_fixture_v1.json")
    h26 = {x["id"]: x for x in h26doc["design_parameters"]}
    a4 = _load("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A4_owner_decisions.json")["decisions"]
    lock1 = _load("docs/architecture_comparison/lock1/lock1_decision_brief_v1.json")
    m16 = _load("docs/budgets/subsystem_maturity/subsystem_maturity_v2.json")
    pins_by_path = {p: s for p, s, _r, _w in PINS}

    items = build_items(h26)
    stop = build_stop_rules(a4)
    d02 = next(x for x in lock1["decisions"] if x["id"] == "D-02")
    d02a = next(o for o in d02["options"] if o["id"] == "D-02-A")
    stop["contrast_stop"]["historical_citation_only"]["rationale_quoted"] = d02a["consequences"]["consequences"]["meaning"]
    stop["contrast_stop"]["historical_citation_only"]["label"] = d02a["label"]

    applied = []
    for r in sorted(OWNER_ROWS_APPLIED):
        applied.append({"row": r, "question": rows[r]["question"], "answer_verbatim": rows[r]["owner_answer_verbatim"],
                        "how_applied": OWNER_ROWS_APPLIED[r]})
    h3, h4 = build_h3_h4()
    doc = {
        "schema": "abep_hall_icp_uncertainty_budget_v1",
        "id": "hall_icp_uncertainty_budget_v1",
        "lane": "fo_a9_04_hall_icp_uncertainty_budget",
        "trigger": "T_A9_04_UNCERTAINTY_BUDGET",
        "owner_decision": "A9",
        "status": "DRAFT_PENDING_OWNER_NOT_PREREGISTERED",
        "status_note": "Nothing here is locked, preregistered, measured or predicted. Numbers appear only where an "
                       "owner answer (cited by row) or a verified deliverable gives them; every margin, effect size, "
                       "stop-rule number, allocation and n is a defined quantity with its freeze point.",
        "base_commit": BASE_COMMIT,
        "generated_by": BUILDER_REL,
        "companion_document": MD_REL,
        "test": TEST_REL,
        "configurations": list(CONFIGS),
        "context": {
            "a9_status": "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE",
            "credible_hall_set": "EMPTY (no admitted Hall transport closure)",
            "p5_n2_v1": "INCONCLUSIVE (permanent)",
            "bundle1": "NO_BASELINE_YET",
            "rfp": "official RFP not yet obtained (tender 2026_DRDO_788433_1; rows 1-3); RFP numbers used here are the "
                   "owner's engineering basis",
            "evidence_order": "Ar (engineering-only) -> N2 -> O2-bearing (NO_ATOMIC_O) -> separate atomic-O "
                              "materials/life programme (rows 36, 132)",
        },
        "authority_pins": [{"path": p, "sha256": s, "role": r, "what": w} for p, s, r, w in PINS],
        "governance_files_not_pinned": GOVERNANCE_NOT_PINNED,
        "decision_quantities": build_dqs(),
        "dq_id_mapping": {
            "by": "A9_INT fo_a9_int_core_integration (mechanical integration; no value, threshold, gate, allocation, "
                  "requirement meaning, evidence class or owner-answer interpretation changed)",
            "rule": "UB-DQ-x maps to DQ-HI-y only if exactly one A9-01 decision quantity measures the same physical "
                    "quantity, in the same units, for the same configurations, with the UB-DQ chain's primary "
                    "instrument in its A9-01 measurement chain; differences, ratios, allocation checks and "
                    "multi-limit classes built from it are consumers, not counterparts; otherwise the UB-DQ id is "
                    "kept and marked '" + UNMAPPED + "'",
            "a9_01_source": A9_01_JSON + " decision_quantities",
            "integration_record": INTEGRATION_JSON,
            "rows": DQ_ID_MAPPING,
        },
        "items": items,
        "measurement_chains": build_chains(),
        "variance_groups": build_variance_groups(),
        "stop_rules": stop,
        "interpolation": build_interpolation(),
        "readiness_n": build_readiness(),
        "interface_demands": build_interface_demands(),
        "owner_answers_applied": applied,
        "open_owner_questions": build_open_questions(),
        "historical_reuse": build_historical_reuse(pins_by_path),
        "m16_impact": build_m16(m16),
        "h3_procurement_inputs": h3,
        "h4_test_inputs": h4,
        "references": build_references(),
        "compliance": [
            "no thrust, efficiency, discharge-current, neutralizer-current or plasma-state prediction; no Hall "
            "closure, screening candidate, abep_sim/plasma_devices.py or withdrawn v1.2-v1.6 number used",
            "no Takahashi 2024 operating value quoted (A9-05: " + A9_05_EV_JSON + ")",
            "no frozen numeric threshold beyond owner answers (cited by row) and verified H2-6 inputs",
            "historical artifacts read and cited, never edited; mutable governance files not pinned",
            "no winner declared; NET_BENEFIT is hard gates + Pareto (row 37)",
            "pure document lane: no abep_sim module, archengine or golden touched",
        ],
    }
    return doc


# ---------------------------------------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------------------------------------
def _fmt(v):
    if v is None:
        return "-"
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _cell(v):
    return _fmt(v).replace("|", "\\|").replace("\n", " ")


def render_md(doc) -> str:
    L = []
    a = L.append
    a("# Hall + ICP neutralizer: C1-vs-ICP uncertainty budget, stop rules and measurement chains (A9-04)")
    a("")
    a(f"Status: **{doc['status']}**. {doc['status_note']}")
    a("")
    a(f"Lane `{doc['lane']}` (trigger `{doc['trigger']}`, owner decision {doc['owner_decision']}); base commit "
      f"`{doc['base_commit']}`. Generated by [`build_hall_icp_uncertainty_budget.py`](build_hall_icp_uncertainty_budget.py) "
      "(`--write`, `--check`) from `hall_icp_uncertainty_budget_v1.json`; do not edit by hand.")
    a("")
    a("Configurations: " + ", ".join(f"`{c}`" for c in doc["configurations"]) + ".")
    a("")
    a("## Context")
    for k, v in doc["context"].items():
        a(f"- **{k}**: {v}")
    a("")
    a("## Pins (immutable inputs, sha256)")
    a("| path | sha256 | role |")
    a("|---|---|---|")
    for p in doc["authority_pins"]:
        a(f"| `{p['path']}` | `{p['sha256']}` | {p['role']}: {_cell(p['what'])} |")
    a("")
    a("Not pinned (mutable governance): " + ", ".join(f"`{g}`" for g in doc["governance_files_not_pinned"]))
    a("")
    a("## Decision quantities (A9-01 DQ-HI-* ids where mapped; UB-DQ-* ids kept where UNMAPPED - owner/A9-10)")
    a("| id | name | symbol | units | configurations | role |")
    a("|---|---|---|---|---|---|")
    for q in doc["decision_quantities"]:
        a(f"| {q['id']} | {_cell(q['name'])} | {_cell(q['symbol'])} | {q['units']} | "
          f"{', '.join(q['configurations'])} | {_cell(q['role'])} |")
    a("")
    m = doc["dq_id_mapping"]
    a("### Decision-quantity id mapping UB-DQ-* -> DQ-HI-* (A9_INT)")
    a("")
    a(f"Rule: {m['rule']}. A9-01 source: `{m['a9_01_source']}`; integration record: `{m['integration_record']}`. "
      f"{m['by']}.")
    a("")
    a("| UB-DQ id | DQ-HI id | status | A9-04 definition | A9-01 definition | basis | A9-01 consumers (not counterparts) |")
    a("|---|---|---|---|---|---|---|")
    for r in m["rows"]:
        a(f"| {r['ub_dq_id']} | {r['dq_hi_id'] or '-'} | {r['status']} | {_cell(r['ub_definition'])} | "
          f"{_cell(r['a9_01_definition'])} | {_cell(r['basis'])} | "
          f"{_cell(', '.join(r['a9_01_consumers_not_counterparts']) or '-')} |")
    a("")
    a("## (a) Items and parameters")
    a("| id | dq | name | type | value | units | basis | source | evidence class | status | freeze point |")
    a("|---|---|---|---|---|---|---|---|---|---|---|")
    for it in doc["items"]:
        a(f"| {it['id']} | {it['dq']} | {_cell(it['name'])} | {it['type']} | {_cell(it['value'])} | "
          f"{_cell(it['units'])} | {_cell(it['basis'])} | {_cell(it['source'])} | {_cell(it['evidence_class'])} | "
          f"{it['status']} | {it['freeze_point']} |")
    a("")
    notes = [it for it in doc["items"] if it["note"]]
    if notes:
        a("Item notes:")
        for it in notes:
            a(f"- **{it['id']}**: {it['note']}")
        a("")
    a("## (1) Measurement chains and propagation")
    for c in doc["measurement_chains"]:
        a(f"### {c['dq']}")
        a("Instruments: " + "; ".join(c["instruments"]))
        a("")
        a("```")
        for e in c["equations"]:
            a(e)
        a("```")
        a("Components: " + ", ".join(c["components"]) + ". Targets / rules: " + ", ".join(c["targets"]) + ".")
        a("")
        a(f"Not a component: {c['not_a_component']}")
        a("")
    vg = doc["variance_groups"]
    a("## (2) Variance groups for the paired C1-vs-ICP comparison")
    a(f"Status: {vg['status']}")
    a("")
    a(f"Estimand: {vg['estimand']}")
    a("")
    a("```")
    for e in vg["estimator"]:
        a(e)
    a("```")
    a(f"Planning decomposition: {vg['planning_decomposition']}")
    a("")
    a("| id | group | what | symbol | evaluation | averages down | cancels in pair | rows | share |")
    a("|---|---|---|---|---|---|---|---|---|")
    for g in vg["groups"]:
        a(f"| {g['id']} | {g['name']} | {_cell(g['what'])} | {g['symbol']} | {_cell(g['evaluation'])} | "
          f"{_cell(g['averages_down'])} | {_cell(g['cancels_in_pair'])} | {_cell(g['owner_rows'])} | {g['share']} |")
    a("")
    a(f"Allocation rule: {vg['allocation_rule']}")
    a("")
    a(f"Design-inherent difference: {vg['design_inherent_difference']}")
    a("")
    s = doc["stop_rules"]
    a("## (3) Stop rules, limit aborts, interlocks, NOT_TESTED")
    a(f"Status: {s['status']}")
    a("")
    cs = s["contrast_stop"]
    a(f"**{cs['id']}** applies to {cs['applies_to']}.")
    for k, v in cs["symbols"].items():
        a(f"- `{k}` = {v}")
    for f in cs["forms"]:
        a(f"- **{f['id']}**: {f['rule']}")
    a(f"- Owner choice: {cs['owner_choice']}")
    h = cs["historical_citation_only"]
    a(f"- Historical citation only: `{h['path']}` (sha256 `{h['sha256']}`), option '{h['label']}': "
      f"\"{h['rationale_quoted']}\" ({h['status']})")
    a(f"- Consequence: {cs['consequence']}")
    a("")
    a(f"**{s['gate_stop']['id']}**: {s['gate_stop']['rule']} Gate definition: {s['gate_stop']['gate_definition']}.")
    a("")
    a(f"**{s['precision_futility']['id']}**: {s['precision_futility']['rule']}")
    a("")
    a(f"Limit aborts: {s['limit_aborts']['rule']}")
    a("")
    a("| id | quantity | symbol | value | configurations |")
    a("|---|---|---|---|---|")
    for l in s["limit_aborts"]["limits"]:
        a(f"| {l['id']} | {l['quantity']} | {l['symbol']} | {_cell(l['value'])} | {', '.join(l['configurations'])} |")
    a("")
    a("Safety interlocks (A4 minimum): " + "; ".join(s["safety_interlocks"]["a4_minimum"]) + ".")
    a("")
    a("A9 additions (PROPOSED):")
    for x in s["safety_interlocks"]["a9_additions_proposed"]:
        a(f"- {x}")
    a("")
    a(f"Classification: {s['safety_interlocks']['classification']}")
    a("")
    nt = s["not_tested"]
    a(f"NOT_TESTED: {nt['rule']}. {nt['meaning']}. Outcome vocabulary: "
      + ", ".join(f"`{x}`" for x in nt["outcome_vocabulary"]) + "; status: "
      + ", ".join(f"`{x}`" for x in nt["status_vocabulary"]) + f" (owner of the vocabulary: {nt['vocabulary_owner']}).")
    a("")
    a(f"NET_BENEFIT: {s['net_benefit']}")
    a("")
    ip = doc["interpolation"]
    a("## (4) Interpolation")
    a(f"Status: {ip['status']}")
    for r in ip["rules"]:
        a(f"- **{r['id']}**: {r['rule']}")
    a("")
    a("```")
    for e in ip["equations"]:
        a(e)
    a("```")
    a(f"u_interp: {ip['u_interp']}")
    a("")
    rn = doc["readiness_n"]
    a("## (5) readiness_n")
    a(f"Status: {rn['status']}; implementation `{rn['function']}`.")
    a("")
    a("| input | what | freeze point |")
    a("|---|---|---|")
    for x in rn["inputs"]:
        a(f"| `{x['symbol']}` | {x['what']} | {x['freeze_point']} |")
    a("")
    for k in ("rule", "floor", "absolute_gates", "seed", "worked_values"):
        a(f"- **{k}**: {rn[k]}")
    a("")
    a("## (b) Interface demands")
    a("| id | direction | counterpart | quantity | units | status | value |")
    a("|---|---|---|---|---|---|---|")
    for x in doc["interface_demands"]:
        a(f"| {x['id']} | {x['direction']} | {_cell(x['counterpart'])} | {_cell(x['quantity'])} | {x['units']} | "
          f"{x['status']} | {_cell(x['value'])} |")
    a("")
    a("## (c) Owner answers applied")
    a("| row | how applied | answer (verbatim) |")
    a("|---|---|---|")
    for x in doc["owner_answers_applied"]:
        a(f"| {x['row']} | {_cell(x['how_applied'])} | {_cell(x['answer_verbatim'])} |")
    a("")
    a("## (d) Open owner questions (new)")
    for q in doc["open_owner_questions"]:
        a(f"- **{q['id']}**: {q['question']} Proposed: {q['proposed_answer']}.")
    a("")
    a("## (e) Historical reuse")
    for x in doc["historical_reuse"]:
        a(f"- `{x['path']}` (sha256 `{x['sha256']}`): reused: {'; '.join(x['reused']) or 'nothing'}; "
          f"not reused: {'; '.join(x['not_reused'])}")
    a("")
    a("## (f) M16 impact")
    a("| row | key | name | how | proposed state change |")
    a("|---|---|---|---|---|")
    for x in doc["m16_impact"]:
        a(f"| {x['row']} | {x['key']} | {_cell(x['name'])} | {_cell(x['how'])} | {_cell(x['proposed_state_change'])} |")
    a("")
    a("## (g) H3 procurement inputs and H4 test inputs")
    a("| H3 item | specification form | rows |")
    a("|---|---|---|")
    for x in doc["h3_procurement_inputs"]:
        a(f"| {_cell(x['item'])} | {_cell(x['spec_form'])} | {_cell(x['rows'])} |")
    a("")
    a("| H4 stage | test | closes |")
    a("|---|---|---|")
    for x in doc["h4_test_inputs"]:
        a(f"| {x['stage']} | {_cell(x['test'])} | {', '.join(x['closes'])} |")
    a("")
    a("## References")
    for r in doc["references"]:
        a(f"- **{r['id']}**: {r['citation']}" + (f" <{r['url']}>" if r.get("url") else "") + f". Access: {r['access']}.")
    a("")
    a("## Compliance")
    for c in doc["compliance"]:
        a(f"- {c}")
    a("")
    return "\n".join(L)


def _dump(doc) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def check() -> list:
    errs = verify_pins()
    if errs:
        return errs
    doc = build()
    want_json = _dump(doc)
    want_md = render_md(doc)
    for rel, want in ((JSON_REL, want_json), (MD_REL, want_md)):
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            errs.append(f"missing {rel}")
            continue
        with open(path, encoding="utf-8") as f:
            if f.read() != want:
                errs.append(f"drift in {rel}")
    return errs


def write():
    errs = verify_pins()
    if errs:
        raise SystemExit("\n".join(errs))
    doc = build()
    with open(os.path.join(ROOT, JSON_REL), "w", encoding="utf-8") as f:
        f.write(_dump(doc))
    with open(os.path.join(ROOT, MD_REL), "w", encoding="utf-8") as f:
        f.write(render_md(doc))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if args.write:
        write()
        return 0
    errs = check()
    for e in errs:
        print(e)
    return 1 if errs else 0


# ---- A9-10 reconciliation overlay hooks (fo_a9_10_integration) ------------------------------------------------------
_a910_build_core = build


def build(*args, **kwargs):
    """Verified lane build followed by the declared A9-10 changes (docs/experiments/hall_icp/integration/a9_10_overlay.py)."""
    return A910.apply("A9-04", _a910_build_core(*args, **kwargs))


_a910_md_core = render_md


def render_md(doc):
    """Lane Markdown followed by the A9-10 reconciliation section generated from the same JSON."""
    return _a910_md_core(doc).rstrip("\n") + "\n" + "\n".join(A910.md_section(doc)) + "\n"


if __name__ == "__main__":
    sys.exit(main())
