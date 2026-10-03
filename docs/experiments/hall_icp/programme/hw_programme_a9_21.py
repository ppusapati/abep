"""A9.21 HW_PROGRAMME: the owner-approved hardware-programme order, one record consumed by the stage artifacts.

Owner decision A9.21 items 6-11 (docs/decisions/OD_2026_10_02_A9_21_OPEN_ITEMS_AND_HARDWARE_PROGRAMME_OWNER_DECISIONS.md;
the verbatim md governs, the json `decisions.HW_PROGRAMME` list is a recorder digest). Each step records its place in
the order, its predecessors and its entry preconditions; `entry_status` evaluates them FAIL-CLOSED:

  * a step whose predecessor has no completion record (or completed after the step's first record) is
    NOT_STARTABLE_PREDECESSOR_INCOMPLETE;
  * a step with a listed precondition registration missing / malformed is NOT_STARTABLE_PRECONDITION_MISSING;
  * a step whose first record precedes a precondition freeze is ENTRY_NOT_MET_FROZEN_AFTER_START (the records are
    out of the step's entry, never re-labelled);
  * only when every predecessor and every precondition is registered is the status ENTRY_PRECONDITIONS_REGISTERED.
    That is a statement about registrations, never a test result: no status here is PASS, GO or START_AUTHORISED (the
    start itself stays the owner / test director's act).

What A9.21 ADDS over the rules already implemented (A9.8 / A9.10 / A9.11 / A9.12 / A9.14 / A9.16 / A9.19 / A9.20) and
what it only places in order (each existing rule is referenced by its enforcing function, never re-implemented):

  6  H-1: S7.1 FEMM analysis points (A9.14 F5-OQ-01, a9_16_h1.femm_analysis_points) BEFORE S7.2 engineering
     channel-point selection (A9.14 F5-OQ-02). NEW: S7.2 cannot start until every authorised analysis point has a
     registered FEMM result (s7_1_results_cover_points); a selection record must assess exactly the A9.21 criteria
     (magnetic feasibility, thermal margin, mass, packaging, manufacturability) and is refused if it uses thrust /
     performance; the selected point is ENGINEERING_FREEZE_CANDIDATE, never thrust-optimised (s7_2_selection_check).
  7  C1 ground reference: H-1 + C1 reference characterization registers I_d,max,H1,Ar before P1-S7 (already enforced
     by p1_campaign.run_campaign: p1_a9_16_rules.freeze_before_stage_reasons + p1_reducer._check_registration, A9.10
     P1Q-07). NEW: its programme place, the C1 role (GROUND_ONLY_LAB_REFERENCE, A9.20) and the statement that it does
     not redefine the RFP propellant requirement.
  8  ICP: Ar engineering / commissioning reference (P1, where already required) -> registered air/N2 ICP-45 campaign
     (ICP-45N, the A9.1 id) -> separate registered Xe-mode campaign. NEW: icp_campaign_check - one gas / mode per
     campaign, its own operating-domain id (refused when missing or shared with another gas / mode) and its own
     provenance; the stage domains, pressure-match tolerance, DWV leakage criteria and stable-region criteria are
     registered before the campaign's first record. The Ar reference keeps its per-stage A9.8 / A9.11 freeze points
     (see RECORDER_READINGS).
  9  P2 impedance map only after the in-house V/I magnitude / phase calibration (admissible under
     p2_a9_16_rules.vi_calibration_check, A9.11 P2Q-07) and its uncertainty budget are FROZEN before the first map
     record (NEW: the freeze-before-map entry).
  10 coupled H-1 + ICP -> P3 thermal -> P4. NEW: the order; P4 acceptance-bearing exposure needs a LOCK2_FROZEN record
     (p4_a9_16_rules.lock2_freeze, A9.12 P4-OQ-03) frozen before the first acceptance-bearing exposure.
  11 measured H-1 thrust / feed map (mandatory) -> AG-12 performance-derived feed requirement -> statewise AG-13
     T - D >= 0. AG-12 / AG-13 live in F9 (docs/architecture/freeze_candidate/); this record holds the dependency only
     (ag12_ag13_dependency: NOT_EVALUATED until the measured map is registered).

Pure: stdlib + the sibling rule modules loaded by path; no file writes (build_hw_programme.py writes the record).
"""
from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
_APP = ROOT / "docs" / "decisions" / "application"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))
import a9_16_lib as L16  # noqa: E402  (A9.8 .. A9.15 owner answers, verbatim excerpts)
import a9_later_lib as LL  # noqa: E402  (A9.17 .. A9.21 pins + verbatim blocks)


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


P1RED = _load("p1_reducer_for_hw_programme", "docs/experiments/hall_icp/p1_icp_bench/p1_reducer.py")
P2RULES = _load("p2_a9_16_rules_for_hw_programme", "docs/experiments/hall_icp/p2_impedance_map/p2_a9_16_rules.py")
P4RULES = _load("p4_a9_16_rules_for_hw_programme", "docs/experiments/hall_icp/p4_anode_materials/p4_a9_16_rules.py")

SCHEMA = "hw_programme_a9_21_v1"
RECORD_REL = "docs/experiments/hall_icp/programme/hw_programme_a9_21_v1.json"
MD_REL = "docs/experiments/hall_icp/programme/HW_PROGRAMME_A9_21.md"
TEST_REL = "tests/test_hw_programme_a9_21.py"
DECISION = "A9.21"
ITEM = "HW_PROGRAMME"

# ---------------------------------------------------------------------------------------------- vocabulary
ENTRY_REGISTERED = "ENTRY_PRECONDITIONS_REGISTERED"
NOT_STARTABLE_PREDECESSOR = "NOT_STARTABLE_PREDECESSOR_INCOMPLETE"
NOT_STARTABLE_PRECONDITION = "NOT_STARTABLE_PRECONDITION_MISSING"
ENTRY_NOT_MET_LATE = "ENTRY_NOT_MET_FROZEN_AFTER_START"
NO_PROGRAMME_PRECONDITION = "NO_A9_21_ENTRY_PRECONDITION_LISTED"
DELEGATED_ONLY = "ENTRY_GATED_BY_EXISTING_STAGE_RULES"
NOT_EVALUATED = "NOT_EVALUATED"
ENTRY_STATUSES = (NOT_STARTABLE_PREDECESSOR, NOT_STARTABLE_PRECONDITION, ENTRY_NOT_MET_LATE, NO_PROGRAMME_PRECONDITION,
                  DELEGATED_ONLY, ENTRY_REGISTERED)
REGISTRATION_FIELDS = ("registration_id", "frozen_utc", "sha256")
COMPLETION_FIELDS = ("record_id", "completed_utc", "sha256")
DEPENDENCY_BASES = {
    "EXPLICIT_A9_21": "the order is stated in the verbatim A9.21 item",
    "EXISTING_OWNER_RULE": "an earlier owner decision already orders it; A9.21 confirms it",
    "PHYSICAL_PREREQUISITE_RECORDER": "recorder reading: the step needs the article the predecessor produces (it is not "
                                      "an owner-stated order; the owner may reverse it)",
}
H1_SELECTION_CRITERIA = ("magnetic_feasibility", "thermal_margin", "mass", "packaging", "manufacturability")
H1_POINT_STATUS = "ENGINEERING_FREEZE_CANDIDATE"
H1_NOT_THRUST_OPTIMISED = "NOT_THRUST_OPTIMISED"
PERFORMANCE_WORDS = ("thrust", "isp", "specific_impulse", "efficiency", "t_minus_d", "t-d", "drag_margin", "performance",
                     "discharge_current", "anode_efficiency")
C1_ROLE = LL.C1_ROLE                                    # GROUND_ONLY_LAB_REFERENCE (A9.20)
ICP_CAMPAIGN_STEPS = ("ICP-45N", "ICP-XE-MODE")
ICP_CAMPAIGN_MODE = {"ICP-45N": "AIR_PRIMARY", "ICP-XE-MODE": "XE_CONTINGENCY"}
ICP_CAMPAIGN_CLOSURES = ("stage_domains", "pressure_match_tolerance", "dwv_leakage_criteria", "stable_region_criteria")
ICP_CAMPAIGN_REQUIRED = ("campaign_id", "programme_step", "gas", "supply_mode", "operating_domain", "provenance",
                         "closures", "first_record_utc")
DOMAIN_FIELDS = ("domain_id", "frozen_utc", "basis", "sha256")
PROVENANCE_FIELDS = ("registration_set_id", "frozen_utc", "sha256", "source")
P2_CAL_ROUTE = "IN_HOUSE_VNA_TRACEABLE"
LOCK2_STATUS = "LOCK2_FROZEN"
P1_SUPPLY_MODE = P1RED.P1_SUPPLY_MODE


class ProgrammeError(ValueError):
    """A malformed or rule-violating programme input (refused; never repaired or re-labelled)."""


_HEX = re.compile(r"^[0-9a-f]{64}$")


def parse_utc(ts, where):
    if not isinstance(ts, str) or not ts.strip():
        raise ProgrammeError(f"{where}: an ISO-8601 timestamp with a UTC offset is required, got {ts!r}")
    t = ts.strip()
    if t.endswith(("Z", "z")):
        t = t[:-1] + "+00:00"
    try:
        d = datetime.datetime.fromisoformat(t)
    except ValueError:
        raise ProgrammeError(f"{where}: {ts!r} is not ISO-8601")
    if d.tzinfo is None or d.utcoffset() is None:
        raise ProgrammeError(f"{where}: {ts!r} has no UTC offset")
    return d.astimezone(datetime.timezone.utc)


def _s(x):
    return isinstance(x, str) and bool(x.strip())


def _registration_reasons(reg, name, fields=REGISTRATION_FIELDS):
    """[] when reg carries every field (non-empty; sha256 a hex digest; frozen_utc ISO-8601 with offset)."""
    if not isinstance(reg, dict):
        return [f"{name}: not registered"]
    why = [f"{name}: {k} missing" for k in fields if not _s(reg.get(k))]
    if _s(reg.get("sha256")) and not _HEX.match(reg["sha256"]):
        why.append(f"{name}: sha256 {reg['sha256']!r} is not a sha256 hex digest")
    for k in ("frozen_utc", "completed_utc"):
        if k in fields and _s(reg.get(k)):
            try:
                parse_utc(reg[k], f"{name}.{k}")
            except ProgrammeError as e:
                why.append(str(e))
    return why


# ---------------------------------------------------------------------------------------------- step validators
def v_registered(reg, name):
    return _registration_reasons(reg, name)


H1_FREEZE_CANDIDATE_REL = "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json"


def authorised_femm_points():
    """The authorised S7.1 analysis points as the H-1 freeze candidate records them (femm_analysis_points, A9.14
    F5-OQ-01; a9_16_h1.femm_analysis_points). Fail closed: refused when the record is missing or names none."""
    p = ROOT / H1_FREEZE_CANDIDATE_REL
    try:
        pts = json.loads(p.read_text(encoding="utf-8"))["femm_analysis_points"]["points"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ProgrammeError(f"authorised FEMM analysis points unreadable from {H1_FREEZE_CANDIDATE_REL}: {e!r}")
    auth = [x["probe"] for x in pts if isinstance(x, dict) and x.get("authorised_analysis_point") is True]
    if not auth:
        raise ProgrammeError(f"{H1_FREEZE_CANDIDATE_REL} records no authorised FEMM analysis point")
    return auth


def v_femm_points(reg, name):
    """S7.1 output: the authorised FEMM analysis points (A9.14 F5-OQ-01) each with a registered result record. The
    registration's authorised_points must include every point the H-1 record authorises (a self-declared subset is
    not 'every authorised point')."""
    why = _registration_reasons(reg, name)
    if why:
        return why
    declared = reg.get("authorised_points")
    if isinstance(declared, list):
        omitted = [p for p in authorised_femm_points() if p not in declared]
        if omitted:
            why.append(f"{name}: authorised_points omit the H-1 authorised analysis points {omitted} "
                       f"({H1_FREEZE_CANDIDATE_REL} femm_analysis_points)")
    return why + s7_1_results_cover_points(declared, reg.get("results"))


def v_i_d_max(reg, name):
    """C1 reference output consumed at P1-S7: the existing P1 registration form (A9.10 P1Q-07; p1_reducer constants).
    The full check (basis, uncertainty, points, margin rule) stays p1_reducer._check_registration in the campaign."""
    if not isinstance(reg, dict):
        return [f"{name}: not registered"]
    why = [f"{name}: {k} missing" for k in P1RED.REGISTRATION_REQUIRED if k not in reg or reg[k] in (None, "")]
    for key, want in (("propellant", P1RED.I_D_MAX_PROPELLANT), ("electron_source", P1RED.I_D_MAX_ELECTRON_SOURCE),
                      ("envelope_id", P1RED.I_D_MAX_ENVELOPE), ("scope", P1RED.I_D_MAX_SCOPE)):
        if key in reg and reg[key] != want:
            why.append(f"{name}: {key} = {reg[key]!r}, required {want!r} (A9.10 P1Q-07; A9.21 item 7)")
    if _s(reg.get("frozen_utc")):
        try:
            parse_utc(reg["frozen_utc"], f"{name}.frozen_utc")
        except ProgrammeError as e:
            why.append(str(e))
    return why


def v_vi_calibration(reg, name):
    """A9.21 item 9 + A9.11 P2Q-07: the in-house V/I magnitude / phase calibration is admissible under the P2 rule
    and frozen (registration id, frozen_utc, sha256)."""
    why = _registration_reasons(reg, name)
    if why:
        return why
    cal = reg.get("calibration_record")
    if not isinstance(cal, dict) or cal.get("route") != P2_CAL_ROUTE:
        return [f"{name}: calibration_record must be the in-house V/I calibration (route {P2_CAL_ROUTE}, A9.21 item 9; "
                "A9.11 P2Q-07)"]
    try:
        res = P2RULES.vi_calibration_check(cal)
    except P2RULES.RuleError as e:
        return [f"{name}: {e}"]
    if res.get("status") != "CALIBRATION_ADMISSIBLE":
        return [f"{name}: p2_a9_16_rules.vi_calibration_check -> {res.get('status')} {res.get('missing', '')}".rstrip()]
    return []


def v_uncertainty_budget(reg, name):
    why = _registration_reasons(reg, name)
    if not why and not _s(reg.get("budget_id")):
        why.append(f"{name}: budget_id missing (the frozen V/I + map uncertainty budget)")
    return why


def v_lock2(reg, name):
    """A9.12 P4-OQ-03 LOCK-2 record: the output of p4_a9_16_rules.lock2_freeze (status LOCK2_FROZEN), frozen."""
    why = _registration_reasons(reg, name)
    if why:
        return why
    lk = reg.get("lock2")
    if not isinstance(lk, dict) or lk.get("status") != LOCK2_STATUS or not lk.get("thresholds"):
        return [f"{name}: lock2 must be a {LOCK2_STATUS} record from p4_a9_16_rules.lock2_freeze (thresholds frozen; "
                "A9.12 P4-OQ-03)"]
    miss = [s for s in P4RULES.LOCK2_THRESHOLD_SLOTS if s not in lk["thresholds"]]
    return [f"{name}: LOCK-2 thresholds missing {miss}"] if miss else []


def v_thrust_feed_map(reg, name):
    why = _registration_reasons(reg, name)
    if not why and reg.get("evidence_class") != "measured":
        why.append(f"{name}: evidence_class {reg.get('evidence_class')!r}: the H-1 thrust / feed map must be measured "
                   "(A9.21 item 11; A9.13 F9-OQ-02), never model-derived")
    return why


VALIDATORS = {"registered": v_registered, "femm_points": v_femm_points, "i_d_max_h1_ar": v_i_d_max,
              "vi_calibration": v_vi_calibration, "uncertainty_budget": v_uncertainty_budget, "lock2": v_lock2,
              "thrust_feed_map": v_thrust_feed_map, "icp_campaign": None}   # icp_campaign: icp_campaign_check
STEP_START = "STEP_START"


# ---------------------------------------------------------------------------------------------- the order
def _pre(pid, what, validator, enforced_by, sources, freeze_before="the step's first record", gates=STEP_START):
    """gates = STEP_START: evaluated by entry_status (fail closed). Anything else names the sub-stage an EXISTING rule
    gates (listed for the record, enforced by `enforced_by`, not re-implemented here)."""
    if validator not in VALIDATORS:
        raise ProgrammeError(f"unknown validator {validator}")
    return {"id": pid, "what": what, "validator": validator, "enforced_by": enforced_by, "sources": list(sources),
            "freeze_before": freeze_before, "gates": gates}


def _step(sid, item, title, artifact, kind, predecessors, preconditions, outputs, note):
    return {"id": sid, "owner_item": item, "title": title, "artifact": artifact, "kind": kind,
            "predecessors": [{"step": p, "basis": b} for p, b in predecessors], "entry_preconditions": preconditions,
            "outputs": outputs, "note": note}


ARTIFACTS = {
    "H1": "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json",
    "P1": "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
    "P2": "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json",
    "P3": "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v2.json",
    "P4": "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json",
    "F9": "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json",
}
_P1C = "docs/experiments/hall_icp/p1_icp_bench/p1_campaign.py:run_campaign"
_P1R = "docs/experiments/hall_icp/p1_icp_bench/p1_a9_16_rules.py"
_H1 = "docs/hardware/h1_freeze_candidate/a9_16_h1.py"
_ME = "docs/experiments/hall_icp/programme/hw_programme_a9_21.py"


def _campaign_pre(step):
    return [_pre(f"{step}-PRE-01", "campaign registration of THIS gas / mode: own operating domain (domain_id), own "
                 "provenance (registration_set_id) and the four closures - stage domains, pressure-match tolerance, "
                 "DWV leakage criteria, stable-region criteria - each frozen before the campaign's first record",
                 "icp_campaign", f"{_ME}:icp_campaign_check", ["P1-IT-52", "P1Q-11", "P1-IT-55", "P1Q-20", "P1Q-01"],
                 freeze_before="the campaign's first record")]


STEPS = [
    _step("H1-S7.1", 6, "H-1 S7.1 FEMM analysis points (FEMM-class axisymmetric magnetostatics of MC-1 at the "
          "authorised ANALYSIS_POINTS; not a selection)", "H1", "ANALYSIS", [],
          [_pre("H1-S7.1-PRE-01", "authorised analysis-point set and geometry ids registered (femm_analysis_points, "
                "worst-case geometric admissibility)", "registered", f"{_H1}:femm_analysis_points", ["F5-OQ-01"])],
          ["FEMM result record per authorised point (result_id, sha256, geometry_id, solver_configuration_id)"],
          "FEMM_AUTHORISED_NOT_RUN today; no Hall performance is inferred from magnetic feasibility"),
    _step("H1-S7.2", 6, "H-1 S7.2 engineering channel-point selection on magnetic feasibility, thermal margin, mass, "
          "packaging and manufacturability", "H1", "SELECTION", [("H1-S7.1", "EXPLICIT_A9_21")],
          [_pre("H1-S7.2-PRE-01", "S7.1 FEMM results registered for EVERY authorised analysis point", "femm_points",
                f"{_ME}:s7_1_results_cover_points", ["F5-OQ-01", "F5-OQ-02"])],
          [f"selected engineering point, status {H1_POINT_STATUS} ({H1_NOT_THRUST_OPTIMISED}); checked by "
           "s7_2_selection_check"],
          "the point stays an engineering freeze candidate; thrust is measured later (H1-THRUST-FEED-MAP), never a "
          "selection input"),
    _step("C1-REF", 7, "H-1 + C1 reference characterization in HI-AR (C1 GROUND_ONLY_LAB_REFERENCE; reference / "
          "engineering campaign) registering I_d,max,H1,Ar", "P1", "REFERENCE_CAMPAIGN",
          [("H1-S7.2", "PHYSICAL_PREREQUISITE_RECORDER")], [],
          ["I_d,max,H1,Ar registration (p1_campaign registrations.i_d_max_registration; A9.10 P1Q-07 form)"],
          "does not redefine the RFP propellant requirement; the flight-relevant I_d,max,H1 is a later separate "
          "registration; C1 never flight hardware (A9.19 / A9.20)"),
    _step("ICP-AR-REF", 8, "ICP Ar engineering / commissioning reference, P1-S0 .. P1-S6 (preserved where already "
          "required)", "P1", "COMMISSIONING_REFERENCE_CAMPAIGN", [],
          [_pre("ICP-AR-REF-PRE-01", "per-stage operating domains (unique domain_id, frozen before the stage's first "
                "record)", "registered", f"{_P1R}:check_operating_domains / domain_freeze_reasons",
                ["P1-IT-52"], freeze_before="each P1 stage's first record", gates="EACH_P1_STAGE (existing rule)"),
           _pre("ICP-AR-REF-PRE-02", "RF-ON / RF-OFF pressure-match tolerance (installed-gauge derived)", "registered",
                f"{_P1R}:check_pressure_match_registration", ["P1Q-11"],
                freeze_before="the first P1-S4 matched pair", gates="P1-S4 (existing rule)"),
           _pre("ICP-AR-REF-PRE-03", "per-path DWV leakage limits (registered before the DWV test)", "registered",
                f"{_P1R}:reduce_dwv_reverification; p1_reducer.reduce_readiness", ["P1-IT-55", "P1Q-20"],
                freeze_before="the DWV test", gates="P1-G0 (existing rule)"),
           _pre("ICP-AR-REF-PRE-04", "stable-region criteria frozen and hashed (derived from P1-S2 .. S4 evidence)",
                "registered", f"{_P1R}:check_stable_criteria_registration", ["P1Q-01"],
                freeze_before="the first P1-S5 dwell", gates="P1-S5 (existing rule)")],
          ["P1-S0 .. S6 records (Ar is not a flight supply mode)"],
          "the Ar reference keeps its per-stage freeze points (RR-01); its stages need no C1-REF registration "
          "(A9.10 P1Q-07 gates P1-S7 only)"),
    _step("ICP-45A-P1-S7", 7, "P1-S7 / P1-S7H ICP-45A Ar capacity (engineering-only) - consumes I_d,max,H1,Ar", "P1",
          "COMMISSIONING_REFERENCE_STAGE", [("C1-REF", "EXPLICIT_A9_21"), ("ICP-AR-REF", "EXISTING_OWNER_RULE")],
          [_pre("ICP-45A-P1-S7-PRE-01", "I_d,max,H1,Ar registered from the H-1 + C1 reference characterization, "
                "frozen before the first P1-S7 record", "i_d_max_h1_ar",
                f"{_P1C} (p1_a9_16_rules.freeze_before_stage_reasons + p1_reducer._check_registration)",
                ["P1Q-07"], freeze_before="the first P1-S7 record")],
          ["ICP-45A status (EVALUATED_ENGINEERING_ONLY at most; NOT_EVALUATED without the registration)"],
          "A9.21 item 7 + the Ar commissioning reference of item 8"),
    _step("ICP-45N", 8, "registered air/N2 ICP-45 campaign (ICP-45N; supply mode AIR_PRIMARY)", "P1",
          "REGISTERED_CAMPAIGN", [("ICP-45A-P1-S7", "EXPLICIT_A9_21")], _campaign_pre("ICP-45N"),
          ["ICP-45N campaign report (own domain id + provenance)"],
          "own operating domain and provenance; refused if it shares a domain id with another gas / mode"),
    _step("ICP-XE-MODE", 8, "separate registered Xe operating-mode campaign (supply mode XE_CONTINGENCY)", "P1",
          "REGISTERED_CAMPAIGN", [("ICP-45N", "EXPLICIT_A9_21")], _campaign_pre("ICP-XE-MODE"),
          ["Xe-mode campaign report (own domain id + provenance)"],
          "separate from ICP-45N: never pooled with N2 records, never sharing its domain id"),
    _step("P2-MAP", 9, "P2 ICP impedance map", "P2", "CAMPAIGN", [],
          [_pre("P2-MAP-PRE-01", "in-house V/I magnitude / relative-phase calibration admissible and frozen",
                "vi_calibration", "docs/experiments/hall_icp/p2_impedance_map/p2_a9_16_rules.py:vi_calibration_check",
                ["P2Q-07"], freeze_before="the first impedance-map record"),
           _pre("P2-MAP-PRE-02", "uncertainty budget of the V/I calibration frozen", "uncertainty_budget",
                f"{_ME}:entry_status", ["P2Q-07"], freeze_before="the first impedance-map record")],
          ["P2 impedance map (RF ratings TBD_AFTER_IMPEDANCE_MAP until then)"], "A9.21 item 9"),
    _step("COUPLED-H1-ICP", 10, "coupled H-1 + ICP operation", "P3", "CAMPAIGN", [], [],
          ["coupled H-1 + ICP operation records (heat terms for P3)"],
          "A9.21 item 10 names no predecessor or registration for the coupled operation itself"),
    _step("P3-THERMAL", 10, "P3 coupled H-1 / ICP thermal closure", "P3", "ANALYSIS_AND_TEST",
          [("COUPLED-H1-ICP", "EXPLICIT_A9_21")], [],
          ["coupled thermal result (ICP_COUPLED_THERMAL stays UNRESOLVED until then; never PASS)"], "A9.21 item 10"),
    _step("P4-ACCEPTANCE-EXPOSURE", 10, "P4 acceptance-bearing coupon exposure", "P4", "CAMPAIGN",
          [("P3-THERMAL", "EXPLICIT_A9_21")],
          [_pre("P4-PRE-01", "LOCK-2 acceptance thresholds frozen (after metrology commissioning)", "lock2",
                "docs/experiments/hall_icp/p4_anode_materials/p4_a9_16_rules.py:lock2_freeze", ["P4-OQ-03"],
                freeze_before="the first acceptance-bearing exposure")],
          ["P4 acceptance results"], "metrology commissioning (standards / blanks / sacrificial coupons) is not an "
                                     "acceptance-bearing exposure and is not ordered by this step"),
    _step("H1-THRUST-FEED-MAP", 11, "measured H-1 thrust / feed map (mandatory)", "H1", "CAMPAIGN", [], [],
          ["measured thrust-versus-feed map of H-1 for the actual composition (evidence_class measured)"],
          "A9.21 item 11 names no predecessor; A9.13 F9-OQ-02"),
    _step("AG-12", 11, "AG-12 performance-derived, statewise feed requirement (F9 gate; referenced only)", "F9",
          "EXTERNAL_GATE_REFERENCE", [("H1-THRUST-FEED-MAP", "EXPLICIT_A9_21")],
          [_pre("AG-12-PRE-01", "measured H-1 thrust / feed map registered", "thrust_feed_map",
                f"{_ME}:ag12_ag13_dependency", ["F9-OQ-02"], freeze_before="AG-12 evaluation")],
          ["AG-12 statewise feed requirement (in F9)"], "lives in F9; this record holds the dependency only"),
    _step("AG-13", 11, "AG-13 statewise T - D >= 0 check (F9 gate; referenced only)", "F9", "EXTERNAL_GATE_REFERENCE",
          [("AG-12", "EXPLICIT_A9_21")], [], ["AG-13 statewise result (in F9)"],
          "lives in F9; D_spacecraft also needs the host-spacecraft drag ICD (A9.21 EXTERNAL_INPUTS, stays TBD)"),
]
STEP_BY_ID = {s["id"]: s for s in STEPS}
ARTIFACT_STEPS = {k: [s["id"] for s in STEPS if s["artifact"] == k] for k in ARTIFACTS}
ITEM_HEADS = {6: "6. H-1 engineering build", 7: "7. C1 ground reference", 8: "8. ICP programme",
              9: "9. P2 impedance map", 10: "10. Coupled H-1 + ICP", 11: "11. Measured H-1 thrust/feed map"}
RECORDER_READINGS = [
    {"id": "RR-01", "item": 8,
     "reading": "'Before it starts, close the stage domains, pressure-match tolerance, DWV leakage criteria and "
                "stable-region criteria' is applied to each REGISTERED campaign (ICP-45N, ICP-XE-MODE): all four are "
                "registered before that campaign's first record. The Ar engineering / commissioning reference (P1) "
                "keeps its existing per-stage freeze points (A9.8 P1-IT-52 / P1Q-11 / P1-IT-55, A9.11 P1Q-01), "
                "because its stable-region criteria are derived from its own P1-S2 .. S4 evidence and could not be "
                "closed before P1 starts; 'preserve ... where already required' keeps it as it is",
     "alternative": "close all four before the first P1 (Ar) record as well; that would contradict A9.11 P1Q-01",
     "status": "RECORDER_READING_OWNER_MAY_REVERSE"},
    {"id": "RR-02", "item": 7,
     "reading": "C1-REF is placed after H1-S7.2 only because the characterization needs the built H-1 article "
                "(PHYSICAL_PREREQUISITE_RECORDER); A9.21 states only 'before P1-S7'",
     "status": "RECORDER_READING_OWNER_MAY_REVERSE"},
    {"id": "RR-03", "item": 8,
     "reading": "the step ids ICP-AR-REF / ICP-45A-P1-S7 / ICP-XE-MODE are recorder labels (A9.1 names ICP-45A / "
                "ICP-45N); the ICP-45N campaign follows the Ar reference INCLUDING its P1-S7 ICP-45A capacity stage "
                "(A9.1 order ICP-45A then ICP-45N); no criterion, value or duration is attached here",
     "status": "RECORDER_LABEL"},
]


def _check_order():
    seen = set()
    for s in STEPS:
        for p in s["predecessors"]:
            if p["step"] not in seen:
                raise ProgrammeError(f"{s['id']}: predecessor {p['step']} not earlier in the programme order")
            if p["basis"] not in DEPENDENCY_BASES:
                raise ProgrammeError(f"{s['id']}: dependency basis {p['basis']}")
        seen.add(s["id"])


_check_order()


# ---------------------------------------------------------------------------------------------- evaluators
def entry_status(step_id, evidence=None):
    """Fail-closed entry status of one programme step.

    evidence = {"completed": {step_id: {record_id, completed_utc, sha256}},
                "registrations": {precondition_id: registration},
                "first_record_utc": ISO-8601 or None (the step has not started),
                "campaign": campaign object (ICP-45N / ICP-XE-MODE only; its first_record_utc governs),
                "other_campaigns": [...], "ar_reference_domain_ids": [...]}.
    A missing key is the explicit 'nothing registered' state. Preconditions whose `gates` is not STEP_START are
    enforced by the existing rule they name and listed as delegated."""
    if step_id not in STEP_BY_ID:
        raise ProgrammeError(f"unknown programme step {step_id!r}")
    s = STEP_BY_ID[step_id]
    ev = evidence or {}
    if not isinstance(ev, dict):
        raise ProgrammeError("evidence must be an object")
    done = ev.get("completed") or {}
    regs = ev.get("registrations") or {}
    camp = ev.get("campaign")
    first_ts = ev.get("first_record_utc")
    if step_id in ICP_CAMPAIGN_STEPS and isinstance(camp, dict):
        if first_ts is not None and first_ts != camp.get("first_record_utc"):
            raise ProgrammeError(f"{step_id}: evidence.first_record_utc differs from the campaign's first_record_utc")
        first_ts = camp.get("first_record_utc")
    first = parse_utc(first_ts, f"{step_id}.first_record_utc") if first_ts else None
    pred_why, pre_why, late, delegated, campaign = [], [], [], [], None
    for p in s["predecessors"]:
        c = done.get(p["step"])
        why = _registration_reasons(c, f"predecessor {p['step']} completion", COMPLETION_FIELDS)
        if why:
            pred_why += why
        elif first is not None and parse_utc(c["completed_utc"], "completed_utc") >= first:
            late.append(f"predecessor {p['step']} completed at {c['completed_utc']}, not before the first "
                        f"{step_id} record")
    for pre in s["entry_preconditions"]:
        if pre["gates"] != STEP_START:
            delegated.append({"id": pre["id"], "gates": pre["gates"], "enforced_by": pre["enforced_by"]})
            continue
        if pre["validator"] == "icp_campaign":
            if not isinstance(camp, dict):
                pre_why.append(f"{pre['id']}: no campaign registration for {step_id}")
                continue
            if camp.get("programme_step") != step_id:
                raise ProgrammeError(f"{step_id}: campaign is registered for {camp.get('programme_step')!r}")
            others, ar_ids = ev.get("other_campaigns") or (), ev.get("ar_reference_domain_ids") or ()
            campaign = icp_campaign_check(camp, others, ar_ids)
            # the separation checks need what they compare against (an omitted set is not 'no conflict')
            if not ar_ids:
                pre_why.append(f"{pre['id']}: Ar reference (P1) stage domain ids not supplied; own-domain separation "
                               "cannot be checked")
            for earlier in ICP_CAMPAIGN_STEPS[:ICP_CAMPAIGN_STEPS.index(step_id)]:
                if not any(isinstance(o, dict) and o.get("programme_step") == earlier for o in others):
                    pre_why.append(f"{pre['id']}: the {earlier} campaign registration is not supplied; own-domain / "
                                   "own-provenance separation cannot be checked")
            pre_why += campaign["missing"]
            late += campaign["late"]
            continue
        reg = regs.get(pre["id"])
        why = VALIDATORS[pre["validator"]](reg, pre["id"])
        if why:
            pre_why += why
        elif first is not None and parse_utc(reg["frozen_utc"], "frozen_utc") >= first:
            late.append(f"{pre['id']} frozen at {reg['frozen_utc']}, not before {pre['freeze_before']}")
    gating = [p for p in s["entry_preconditions"] if p["gates"] == STEP_START]
    if pred_why:
        status = NOT_STARTABLE_PREDECESSOR
    elif pre_why:
        status = NOT_STARTABLE_PRECONDITION
    elif late:
        status = ENTRY_NOT_MET_LATE
    elif not s["predecessors"] and not gating:
        status = DELEGATED_ONLY if delegated else NO_PROGRAMME_PRECONDITION
    else:
        status = ENTRY_REGISTERED
    return {"step": step_id, "status": status, "predecessor_reasons": pred_why, "precondition_reasons": pre_why,
            "late_freeze_reasons": late, "delegated_preconditions": delegated, "campaign": campaign,
            "rule": "fail closed: a missing registration never defaults; ENTRY_PRECONDITIONS_REGISTERED is a "
                    "registration statement, not a test result or a start authorisation"}


def s7_1_results_cover_points(authorised_points, results):
    """[] when every authorised S7.1 analysis point has one registered FEMM result; else the reasons."""
    if not isinstance(authorised_points, list) or not authorised_points or not all(_s(p) for p in authorised_points):
        return ["S7.1: authorised_points must be the non-empty list of authorised FEMM analysis points"]
    if not isinstance(results, list):
        return ["S7.1: results must be a list of FEMM result records"]
    need = ("probe", "result_id", "sha256", "geometry_id", "solver_configuration_id")
    why, have = [], {}
    for i, r in enumerate(results):
        miss = [k for k in need if not (isinstance(r, dict) and _s(r.get(k)))]
        if miss:
            why.append(f"S7.1 result {i}: {miss} missing")
            continue
        if not _HEX.match(r["sha256"]):
            why.append(f"S7.1 result {r['result_id']}: sha256 is not a hex digest")
            continue
        have.setdefault(r["probe"], []).append(r["result_id"])
    absent = [p for p in authorised_points if p not in have]
    if absent:
        why.append(f"S7.1 FEMM results missing for authorised analysis points {absent} (S7.2 needs every point)")
    extra = sorted(set(have) - set(authorised_points))
    if extra:
        why.append(f"S7.1 results for points {extra} that are not authorised analysis points (owner may add them; "
                   "not silently included)")
    return why


def s7_2_selection_check(selection, femm_registration):
    """A9.21 item 6 / A9.14 F5-OQ-02: a selection record is admissible only after S7.1 covers every authorised point,
    assesses exactly the five A9.21 criteria, uses no thrust / performance input, and labels the point
    ENGINEERING_FREEZE_CANDIDATE / NOT_THRUST_OPTIMISED. Raises ProgrammeError; returns the admitted record."""
    why = v_femm_points(femm_registration, "S7.1 FEMM registration")
    if why:
        raise ProgrammeError("S7.2 selection refused before S7.1 is complete: " + "; ".join(why))
    if not isinstance(selection, dict):
        raise ProgrammeError("S7.2 selection must be an object")
    for k in ("selection_id", "point_id", "frozen_utc", "criteria", "status", "optimisation_basis"):
        if k not in selection:
            raise ProgrammeError(f"S7.2 selection: {k} missing")
    parse_utc(selection["frozen_utc"], "S7.2 selection frozen_utc")
    if parse_utc(selection["frozen_utc"], "S7.2") <= parse_utc(femm_registration["frozen_utc"], "S7.1"):
        raise ProgrammeError("S7.2 selection frozen before the S7.1 FEMM registration (A9.21 item 6: S7.1 first)")
    crit = selection["criteria"]
    if not isinstance(crit, dict):
        raise ProgrammeError("S7.2 selection: criteria must map criterion -> assessment record")
    perf = [k for k in crit if any(w in k.lower() for w in PERFORMANCE_WORDS)]
    if perf:
        raise ProgrammeError(f"S7.2 selection uses performance criteria {perf}: the point is not thrust-optimised "
                             "(A9.21 item 6; A9.14 F5-OQ-02)")
    miss = [c for c in H1_SELECTION_CRITERIA if not (isinstance(crit.get(c), dict) and _s(crit[c].get("record_id")))]
    extra = sorted(set(crit) - set(H1_SELECTION_CRITERIA))
    if miss or extra:
        raise ProgrammeError(f"S7.2 selection criteria: missing assessments {miss}, unlisted criteria {extra} (A9.21 "
                             f"item 6 lists {list(H1_SELECTION_CRITERIA)})")
    if selection["status"] != H1_POINT_STATUS or selection["optimisation_basis"] != H1_NOT_THRUST_OPTIMISED:
        raise ProgrammeError(f"S7.2 selection status {selection['status']!r} / basis "
                             f"{selection['optimisation_basis']!r}: only {H1_POINT_STATUS} / {H1_NOT_THRUST_OPTIMISED}")
    pid = selection["point_id"]
    if pid not in femm_registration["authorised_points"]:
        raise ProgrammeError(f"S7.2 point {pid!r} is not an authorised S7.1 analysis point")
    return {"status": H1_POINT_STATUS, "optimisation_basis": H1_NOT_THRUST_OPTIMISED, "point_id": pid,
            "selection_id": selection["selection_id"]}


def icp_campaign_check(campaign, other_campaigns=(), ar_reference_domain_ids=()):
    """A9.21 item 8 for a REGISTERED gas / mode campaign (ICP-45N or ICP-XE-MODE).

    Refused (ProgrammeError): not a registered campaign step; gas not of the step's supply mode (one gas / mode per
    campaign; the gas -> mode map is p1_reducer.icp_supply_mode, A9.19); no own operating-domain id or a domain id
    already used by another gas / mode campaign or by the Ar reference; no own provenance.
    Returned status (fail closed): NOT_STARTABLE_PRECONDITION_MISSING when a closure is unregistered,
    ENTRY_NOT_MET_FROZEN_AFTER_START when a closure / domain / provenance was frozen at or after the first record,
    else ENTRY_PRECONDITIONS_REGISTERED (registration statement; the predecessor order is entry_status)."""
    if not isinstance(campaign, dict):
        raise ProgrammeError("campaign must be an object")
    miss = [k for k in ICP_CAMPAIGN_REQUIRED if k not in campaign]
    if miss:
        raise ProgrammeError(f"campaign: {miss} missing (first_record_utc null = not started)")
    step = campaign["programme_step"]
    if step not in ICP_CAMPAIGN_STEPS:
        raise ProgrammeError(f"campaign {campaign['campaign_id']!r}: programme_step {step!r} is not a registered "
                             f"gas / mode campaign {ICP_CAMPAIGN_STEPS} (the Ar reference is P1)")
    try:
        mode = P1RED.icp_supply_mode(campaign["gas"], campaign["supply_mode"], f"campaign {campaign['campaign_id']}")
    except P1RED.P1RecordError as e:
        raise ProgrammeError(str(e))
    if mode != ICP_CAMPAIGN_MODE[step]:
        raise ProgrammeError(f"campaign {campaign['campaign_id']!r}: gas {campaign['gas']!r} is supply mode {mode}, "
                             f"but {step} is the {ICP_CAMPAIGN_MODE[step]} campaign (one gas / mode per campaign)")
    dom = campaign["operating_domain"]
    why = _registration_reasons(dom, "operating_domain", DOMAIN_FIELDS)
    if why:
        raise ProgrammeError(f"campaign {campaign['campaign_id']!r} refused: no own operating domain - " +
                             "; ".join(why) + " (A9.21 item 8: each gas / mode gets its own operating domain)")
    prov = campaign["provenance"]
    why = _registration_reasons(prov, "provenance", PROVENANCE_FIELDS)
    if why:
        raise ProgrammeError(f"campaign {campaign['campaign_id']!r} refused: no own provenance - " + "; ".join(why))
    for o in other_campaigns:
        if not isinstance(o, dict):
            raise ProgrammeError("other_campaigns entries must be campaign objects")
        if o.get("campaign_id") == campaign["campaign_id"]:
            if o.get("programme_step") != step:
                raise ProgrammeError(f"campaign_id {campaign['campaign_id']!r} is registered for both "
                                     f"{o.get('programme_step')!r} and {step!r}: one gas / mode per campaign "
                                     "(A9.21 item 8)")
            continue
        odom = (o.get("operating_domain") or {}).get("domain_id")
        if odom == dom["domain_id"] and o.get("programme_step") != step:
            raise ProgrammeError(f"domain_id {odom!r} is used by campaign {o.get('campaign_id')!r} "
                                 f"({o.get('programme_step')}) and {campaign['campaign_id']!r} ({step}): each gas / "
                                 "mode has its own operating domain (A9.21 item 8)")
        if (o.get("provenance") or {}).get("registration_set_id") == prov["registration_set_id"] and \
                o.get("programme_step") != step:
            raise ProgrammeError(f"registration_set_id {prov['registration_set_id']!r} shared with "
                                 f"{o.get('campaign_id')!r}: each gas / mode has its own provenance (A9.21 item 8)")
    if dom["domain_id"] in set(ar_reference_domain_ids):
        raise ProgrammeError(f"domain_id {dom['domain_id']!r} is an Ar reference (P1) stage domain: the "
                             f"{ICP_CAMPAIGN_MODE[step]} campaign needs its own")
    clo = campaign["closures"]
    if not isinstance(clo, dict):
        raise ProgrammeError("closures must map closure -> registration")
    extra = sorted(set(clo) - set(ICP_CAMPAIGN_CLOSURES))
    if extra:
        raise ProgrammeError(f"closures: unknown keys {extra}")
    first = parse_utc(campaign["first_record_utc"], "first_record_utc") if campaign["first_record_utc"] else None
    missing, late = [], []
    for c in ICP_CAMPAIGN_CLOSURES:
        w = _registration_reasons(clo.get(c), c)
        if w:
            missing += w
        elif first is not None and parse_utc(clo[c]["frozen_utc"], c) >= first:
            late.append(f"{c} frozen at {clo[c]['frozen_utc']}, not before the campaign's first record")
    for name, reg in (("operating_domain", dom), ("provenance", prov)):
        if first is not None and parse_utc(reg["frozen_utc"], name) >= first:
            late.append(f"{name} frozen at {reg['frozen_utc']}, not before the campaign's first record")
    status = NOT_STARTABLE_PRECONDITION if missing else (ENTRY_NOT_MET_LATE if late else ENTRY_REGISTERED)
    return {"campaign_id": campaign["campaign_id"], "programme_step": step, "supply_mode": mode,
            "domain_id": dom["domain_id"], "registration_set_id": prov["registration_set_id"], "status": status,
            "missing": missing, "late": late}


def ag12_ag13_dependency(thrust_feed_map_registration=None):
    """A9.21 item 11: AG-12 (performance-derived statewise feed requirement) needs the measured H-1 thrust / feed map;
    AG-13 (statewise T - D >= 0) follows AG-12. Both gates live in F9; this only states whether the programme input
    exists. Never PASS: without the map both are NOT_EVALUATED; with it they become evaluable in F9."""
    why = v_thrust_feed_map(thrust_feed_map_registration, "H1-THRUST-FEED-MAP")
    state = NOT_EVALUATED if why else "INPUT_REGISTERED_EVALUATE_IN_F9"
    return {"AG-12": {"programme_input": state, "reasons": why, "gate_location": ARTIFACTS["F9"]},
            "AG-13": {"programme_input": state if not why else NOT_EVALUATED, "after": "AG-12",
                      "gate_location": ARTIFACTS["F9"],
                      "also_needs": "host-spacecraft drag ICD (A9.21 EXTERNAL_INPUTS; stays TBD)"}}


# ---------------------------------------------------------------------------------------------- record
def _sources(qids):
    return [{"question_id": q, "cite": L16.cite(q), "decision_code": L16.answer(q)["decision_code"]} for q in qids]


def document() -> dict:
    """The programme-order record (deterministic)."""
    steps = []
    for i, s in enumerate(STEPS, 1):
        st = json.loads(json.dumps(s))
        st["order_index"] = i
        st["artifact_path"] = ARTIFACTS[s["artifact"]]
        st["successors"] = [t["id"] for t in STEPS if any(p["step"] == s["id"] for p in t["predecessors"])]
        for pre in st["entry_preconditions"]:
            pre["sources"] = _sources(pre["sources"])
        st["entry_status_now"] = entry_status(s["id"])["status"]
        steps.append(st)
    items = {}
    for n, head in ITEM_HEADS.items():
        items[str(n)] = {"verbatim": LL.block(DECISION, head),
                         "steps": [s["id"] for s in STEPS if s["owner_item"] == n]}
    dec = LL.LOADED[DECISION]
    return {
        "schema": SCHEMA,
        "id": "hw_programme_a9_21_v1",
        "title": "A9.21 hardware-programme order (items 6-11) with fail-closed entry preconditions",
        "generated_by": "docs/experiments/hall_icp/programme/build_hw_programme.py",
        "library": _ME,
        "test": TEST_REL,
        "decision": {"key": DECISION, "item": ITEM, "cite": LL.cite(DECISION, ITEM),
                     "decision_json": dec["json"], "decision_json_sha256": dec["json_sha256"],
                     "decision_md": dec["md"], "decision_md_sha256": dec["md_sha256"],
                     "recorder_digest": LL.digest(DECISION, ITEM),
                     "governs": "the verbatim md; the json list is a recorder digest"},
        "related_decisions": {"A9.20": LL.cite("A9.20"), "c1_role": C1_ROLE},
        "owner_items_verbatim": items,
        "entry_status_vocabulary": list(ENTRY_STATUSES),
        "dependency_bases": DEPENDENCY_BASES,
        "steps": steps,
        "artifact_steps": ARTIFACT_STEPS,
        "icp_campaign_rule": {
            "steps": list(ICP_CAMPAIGN_STEPS), "supply_mode": dict(ICP_CAMPAIGN_MODE),
            "required": list(ICP_CAMPAIGN_REQUIRED), "closures": list(ICP_CAMPAIGN_CLOSURES),
            "operating_domain_fields": list(DOMAIN_FIELDS), "provenance_fields": list(PROVENANCE_FIELDS),
            "gas_to_mode": "p1_reducer.icp_supply_mode (A9.19)",
            "refusals": ["programme_step not ICP-45N / ICP-XE-MODE", "gas not of the step's supply mode",
                         "operating domain missing (no own domain_id)", "domain_id shared with another gas / mode "
                         "campaign or an Ar reference stage domain", "provenance missing or registration_set_id shared "
                         "with another gas / mode campaign"],
            "content_checks": "the numerical domain factors and criteria are registered by the campaign (none is "
                              "set here); their content checks are the campaign reducer's (the existing P1 rules "
                              "are the Ar-step templates)"},
        "h1_selection_rule": {"criteria": list(H1_SELECTION_CRITERIA), "status": H1_POINT_STATUS,
                              "optimisation_basis": H1_NOT_THRUST_OPTIMISED,
                              "refused_inputs": list(PERFORMANCE_WORDS)},
        "ag12_ag13_now": ag12_ag13_dependency(None),
        "recorder_readings": RECORDER_READINGS,
        "what_this_is_not": ["not a schedule: no date, duration or resource is set",
                             "no numerical criterion, domain bound, tolerance or threshold is set; every one is a "
                             "registration of the campaign that owns it",
                             "not a test result; no status is PASS / GO / START_AUTHORISED",
                             "not the ICP go / no-go gate before LOCK-1 (A9.21 ICP_GATE, F9 / RVM)",
                             "does not change AG-12 / AG-13 (F9) or any M16 state"],
    }


def canonical(doc) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def record_sha256() -> str:
    """sha256 of the committed record; refuses when it is stale (the stage artifacts consume a current record)."""
    p = ROOT / RECORD_REL
    if not p.exists():
        raise ProgrammeError(f"{RECORD_REL} missing: run build_hw_programme.py")
    data = p.read_bytes()
    if data.decode("utf-8") != canonical(document()):
        raise ProgrammeError(f"{RECORD_REL} is stale: run build_hw_programme.py")
    return hashlib.sha256(data).hexdigest()


def artifact_view(key: str) -> dict:
    """The block a stage artifact embeds: its steps (place, predecessors, successors, entry preconditions with the
    enforcing rule) and their fail-closed entry status with nothing registered, plus the record pin."""
    if key not in ARTIFACTS or key == "F9":
        raise ProgrammeError(f"no stage artifact {key!r}")
    doc = document()
    by = {s["id"]: s for s in doc["steps"]}
    view = {
        "programme_record": RECORD_REL, "programme_record_sha256": record_sha256(), "library": _ME,
        "decision": doc["decision"]["cite"],
        "order": [s["id"] for s in doc["steps"]],
        "steps": [{k: by[sid][k] for k in ("id", "order_index", "owner_item", "title", "kind", "predecessors",
                                           "successors", "entry_preconditions", "outputs", "note",
                                           "entry_status_now")} for sid in ARTIFACT_STEPS[key]],
        "owner_items_verbatim": {n: doc["owner_items_verbatim"][n]["verbatim"]
                                 for n in sorted({str(by[sid]["owner_item"]) for sid in ARTIFACT_STEPS[key]},
                                                 key=int)},
        "rule": "fail closed (hw_programme_a9_21.entry_status): a step is NOT_STARTABLE while a predecessor "
                "completion or a listed precondition registration is missing; never PASS / GO / START_AUTHORISED",
    }
    if key == "H1":
        view["ag12_ag13_dependency"] = doc["ag12_ag13_now"]
    if key == "P1":
        view["icp_campaign_rule"] = doc["icp_campaign_rule"]
        view["recorder_readings"] = [r for r in RECORDER_READINGS if r["item"] in (7, 8)]
    return view


def render_view_md(view: dict) -> list:
    """Markdown lines for a stage artifact's companion document."""
    out = ["", "## A9.21 hardware-programme place (owner items 6-11)", "",
           f"Programme record `{view['programme_record']}` (sha256 `{view['programme_record_sha256']}`); decision "
           f"{view['decision']}.", "", "Order: " + " -> ".join(view["order"]), ""]
    for n, txt in view["owner_items_verbatim"].items():
        out.append(f"> {txt}")
        out.append("")
    out += ["| step | # | predecessors | entry preconditions | entry status now |", "|---|---|---|---|---|"]
    for s in view["steps"]:
        preds = ", ".join(f"{p['step']} ({p['basis']})" for p in s["predecessors"]) or "-"
        pres = "; ".join(f"{p['id']}: {p['what']} [{p['enforced_by']}]" for p in s["entry_preconditions"]) or "-"
        out.append(f"| {s['id']} | {s['order_index']} | {preds} | {pres} | {s['entry_status_now']} |")
    out += ["", view["rule"], ""]
    return out
