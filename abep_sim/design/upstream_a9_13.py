"""A9.13 S6 upstream-architecture rules as executable design-layer code (A9.16 step 3, design-layer lane).

Owner decisions implemented here (immutable records; the verbatim .md governs; companion-JSON sha256 pinned in
``DECISIONS`` and checked by ``verify_decision_records``):

  A9.13 (docs/decisions/OD_2026_10_01_A9_13_S6_UPSTREAM_ARCHITECTURE_OWNER_DECISIONS.md)
    S6.8  / OQ-F3-03   above 0.1 Pa every compressor / plenum result is NOT_EVALUATED_OUT_OF_DOMAIN; the transitional
                       model (abep_sim/compressor_transitional.py) is CANDIDATE_NOT_ADMITTED and never consumed
    S6.10 / OQ-F4-01   orbit-state-scheduled plenum setpoint = baseline control mode; fixed setpoint = fallback and
                       reference; the schedule depends only on controller-available state and is never frozen here
    S6.11 / OQ-F4-02   higher-pressure compression = primary design direction; <= 0.1 Pa high-conductance branch =
                       labelled sensitivity / fallback
    S6.12 / OQ-F4-03   F4 transient metrics provisional (pre-LOCK-2); a measured H-1 tolerance governs when tighter
    S6.13 / OQ-F4-04   flow gap, NO_REQUIREMENT_RELAXATION: (1) performance-derived H-1 feed requirement (S6.21,
                       PENDING_EVIDENCE: measured H-1 thrust / feed map), (2) capture / collection, (3) compressor /
                       feed efficiency, (4) scheduled setpoint (S6.10); 0.38 mg/s = ground characterization only;
                       dense-state-only operation = sensitivity, never baseline while S6.15 is not met
                       (``flow_gap_record`` / ``refuse_feed_requirement_lowering`` / ``state_coverage``)
    S6.15 / OQ-F78-01  AG-13 / HC-08: T_available(state) - D_spacecraft(state) >= 0 at EVERY required state
                       (statewise, worst-state and orbit-averaged margins; the average never hides a deficit)
    S6.16 / OQ-F78-02  robustness over EVERY admitted Maxwell / CLL / accommodation scenario until DI-1.3 narrows them
    S6.17 / OQ-F78-03  ripple = hard feed-quality constraint vs a measured H-1 tolerance; Pareto comparison over
                       worst-state margin, drag, upstream power, mass, volume and heat-rejection burden; no weighted scalar
    S6.18 / OQ-F78-04  reference spacecraft drag (abep_sim/spacecraft_reference_drag) is REFERENCE_PARAMETRIC only
    S6.20 / F9-OQ-01   a versioned robust Pareto SET is carried; no representative is selected
    S6.21 / F9-OQ-02   AG-12 = statewise feed-state sufficiency (mass flow, pressure, temperature, composition, ripple
                       quality) against the requirement derived from the required thrust and a VALIDATED H-1 map;
                       NOT_EVALUATED until that map exists; no fixed mg/s gate (0.38-3.2 mg/s = coverage only)
    S6.22 / F9-OQ-03   a gate closes only on determining evidence: never a PASS / MET on assumptions or parametrics
  A9.14 S9.7 / OD2     statewise envelope quantifier (abep_sim.statewise.statewise_quantifier)
  A9.15                RFP propellant policy: ambient air AND Xe capability, two separate propellant tanks / paths
  A9.19 / A9.20        (abep_sim/design/a9_19_architecture.py) amend A9.15 on the ROLE of Xe: two supply modes
                       AIR_PRIMARY / XE_CONTINGENCY; the HC-10 Xe path role is CONTINGENCY_EMERGENCY; no hollow cathode
  A9.17                the official RFP is registered (docs/requirements/rfp_official/rfp_registration_v1.json) and is
                       the requirement source (clause ids RFP-Pnn-mm)

Nothing here invents a number: tolerances, H-1 maps, schedules and spacecraft drag are caller-supplied records with an
evidence status. Every verdict is fail-closed; no status is ever PASS / SELECTED / WINNER / QUALIFIED (the
statewise quantifier's internal PASS / FAIL is mapped onto the design-layer constraint vocabulary below).
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Sequence

from . import a9_19_architecture as a919

REPO = Path(__file__).resolve().parents[2]

# ================================================================================================= decision records
DECISIONS = {
    "A9.9": {"md": "docs/decisions/OD_2026_10_01_A9_9_S2_MODEL_CHANGE_OWNER_DECISIONS.md",
             "json": "docs/decisions/OD_2026_10_01_A9_9_s2_model_change_owner_decisions.json",
             "json_sha256": "b6010d9d2856ab21b15d49e477ade8246b9d6e90d4dfa1cc07c4468c10a1e47b",
             "ids": ["S2.3 / OQ-F3-01", "S2.5 MCC-03"]},
    "A9.13": {"md": "docs/decisions/OD_2026_10_01_A9_13_S6_UPSTREAM_ARCHITECTURE_OWNER_DECISIONS.md",
              "json": "docs/decisions/OD_2026_10_01_A9_13_s6_upstream_architecture_owner_decisions.json",
              "json_sha256": "9afaca459efe27556033d836814f71bd03203711627899f3ffc494567d763b23",
              "ids": ["S6.3 / F2-OQ-01", "S6.4 / F2-OQ-02", "S6.5 / F2-OQ-03", "S6.6 / F2-OQ-04", "S6.7 / OQ-F3-02",
                      "S6.8 / OQ-F3-03", "S6.9 / OQ-F3-04", "S6.10 / OQ-F4-01", "S6.11 / OQ-F4-02",
                      "S6.12 / OQ-F4-03", "S6.15 / OQ-F78-01", "S6.16 / OQ-F78-02", "S6.17 / OQ-F78-03",
                      "S6.18 / OQ-F78-04", "S6.19 / UPSTREAM_ICD-Q1", "S6.20 / F9-OQ-01", "S6.21 / F9-OQ-02",
                      "S6.22 / F9-OQ-03"]},
    "A9.14": {"md": "docs/decisions/OD_2026_10_01_A9_14_S7_S10_OWNER_DECISIONS.md",
              "json": "docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json",
              "json_sha256": "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c",
              "ids": ["S9.7 / OD2"]},
    "A9.15": {"md": "docs/decisions/OD_2026_10_01_A9_15_RFP_PROPELLANT_POLICY_OWNER_DECISION.md",
              "json": "docs/decisions/OD_2026_10_01_A9_15_rfp_propellant_policy_owner_decision.json",
              "json_sha256": "a928e87fa37aa6ad875fa1505041f21ea145919ebb86286df0e34629c966e309",
              "ids": ["RFP-COMPLIANT PROPELLANT POLICY (governing_rule)"]},
    "A9.17": {"md": "docs/decisions/OD_2026_10_01_A9_17_DATA_ARTIFACT_OWNER_DECISIONS.md",
              "json": "docs/decisions/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json",
              "json_sha256": "9fd77c95c2f3142bb3e2faf68145e1225a29b307d22f86bf93a8cd562914c3ad",
              "ids": ["RFP (registration of the official RFP as the requirement source)"]},
}
# Decisions applied by the design-state / F1Q-02 / flow-gap step (kept out of DECISIONS so the citation records that
# other builders already pin through cite() do not change; checked by verify_state_set_decision_records)
STATE_SET_DECISIONS = {
    "A9.13": {"json": DECISIONS["A9.13"]["json"], "json_sha256": DECISIONS["A9.13"]["json_sha256"],
              "ids": ["S6.1 / F1Q-02", "S6.13 / OQ-F4-04", "S6.14 / OQ-F4-05", "S6.15 / OQ-F78-01",
                      "S6.21 / F9-OQ-02"]},
    "A9.14": {"json": DECISIONS["A9.14"]["json"], "json_sha256": DECISIONS["A9.14"]["json_sha256"],
              "ids": ["S9.8 / OD3"]},
    "A9.17": {"json": DECISIONS["A9.17"]["json"], "json_sha256": DECISIONS["A9.17"]["json_sha256"],
              "ids": ["ORBIT (inclination / LTAN TBD from the official mission ICD; broad design-state envelope)"]},
    "A9.21": {"md": "docs/decisions/OD_2026_10_02_A9_21_OPEN_ITEMS_AND_HARDWARE_PROGRAMME_OWNER_DECISIONS.md",
              "json": "docs/decisions/OD_2026_10_02_A9_21_open_items_and_hardware_programme_owner_decisions.json",
              "json_sha256": "78766d3adaaa6d38730ce82607a1cd0a03ae34186c911d4189e2fd9251db6549",
              "ids": ["EXTERNAL_INPUTS (inclination / LTAN not specified: no code default as mission truth)"]},
}
RFP_REGISTRATION = "docs/requirements/rfp_official/rfp_registration_v1.json"
# RFP clauses this module cites (verbatim text in the registration; tests check that every id exists there)
RFP_CLAUSES = {
    "chain": "RFP-P16-02",            # Intake -> Filter -> Compressor -> Gas Chamber -> Valve -> Thruster
    "density_increase": "RFP-P17-04",  # increases the density of the collected gases to a usable level of ionization
    "n2_o_xe": "RFP-P17-05",           # ionize N2 and atomic O in the same thruster; capability to use Xe
    "altitude": "RFP-P18-04",          # 180 to 230 km
    "intake_sizing": "RFP-P18-05",     # decided by air density based on solar activity and altitude
    "thrust": "RFP-P18-06",            # 12 mN to 25 mN (from expected drag to compensate)
    "propellants": "RFP-P18-08",       # ambient air and Xenon; two separate propellant tanks
    "power": "RFP-P18-10",             # < 1500 W
    "mass": "RFP-P18-11",              # < 40 kg
    "life": "RFP-P19-01",              # 26000 h mission, > 15000 h ignition
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_decision_records(repo: Path = REPO) -> dict:
    """Re-hash every cited decision JSON (immutable records); returns {decision: True/False}."""
    return {k: _sha256(Path(repo) / d["json"]) == d["json_sha256"] for k, d in DECISIONS.items()}


def verify_state_set_decision_records(repo: Path = REPO) -> dict:
    """Re-hash the decision JSONs behind STATE_SET_DECISIONS; returns {decision: True/False}."""
    return {k: _sha256(Path(repo) / d["json"]) == d["json_sha256"] for k, d in STATE_SET_DECISIONS.items()}


def cite(*keys: str) -> list[dict]:
    """Citation records (path + json sha256 + ids) for the given decision keys."""
    return [{"decision": k, "md": DECISIONS[k]["md"], "json": DECISIONS[k]["json"],
             "json_sha256": DECISIONS[k]["json_sha256"], "ids": list(DECISIONS[k]["ids"])} for k in keys]


# ================================================================================================= vocabulary
NOT_EVALUATED = "NOT_EVALUATED"
NOT_EVALUATED_OOD = "NOT_EVALUATED_OUT_OF_DOMAIN"
NOT_EVALUATED_MATERIAL_BASIS = "NOT_EVALUATED_MATERIAL_BASIS"
PARAMETRIC_SENSITIVITY = "PARAMETRIC_SENSITIVITY"
REFERENCE_PARAMETRIC = "REFERENCE_PARAMETRIC_NOT_FLIGHT"
SYNTHETIC = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE"
# value statuses a caller may attach to a supplied record
VALUE_EVIDENCE = "EVIDENCE"                    # determining evidence (measured / validated, A9.13 S6.22)
VALUE_PARAMETRIC = PARAMETRIC_SENSITIVITY
VALUE_REFERENCE = REFERENCE_PARAMETRIC
VALUE_SYNTHETIC = SYNTHETIC
VALUE_TBD = "TBD"
VALUE_STATUSES = (VALUE_EVIDENCE, VALUE_PARAMETRIC, VALUE_REFERENCE, VALUE_SYNTHETIC, VALUE_TBD)

# design-layer constraint statuses (same strings as architecture_optimizer's C_* vocabulary)
C_MET = "MET_ON_SUPPLIED_VALUES"
C_VIOLATED = "VIOLATED"
C_NOT_EVALUATED = NOT_EVALUATED
C_MET_PARAMETRIC = "MET_ON_PARAMETRIC_VALUES_SENSITIVITY_ONLY_NOT_MET"
C_VIOLATED_PARAMETRIC = "VIOLATED_ON_PARAMETRIC_VALUES_SENSITIVITY_ONLY"
C_MET_SYNTHETIC = "MET_ON_SYNTHETIC_TEST_DATA_NOT_EVIDENCE"
C_VIOLATED_SYNTHETIC = "VIOLATED_ON_SYNTHETIC_TEST_DATA_NOT_EVIDENCE"
FORBIDDEN_STATUS_WORDS = ("PASS", "SELECTED", "WINNER", "QUALIFIED", "OPTIMUM")


class A913RuleError(ValueError):
    """A request that an owner decision forbids (refused, never repaired)."""


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def combine_value_status(statuses: Sequence[str]) -> str:
    """Weakest-link evidence status of a composite: TBD > SYNTHETIC > REFERENCE > PARAMETRIC > EVIDENCE."""
    st = set(statuses)
    bad = st - set(VALUE_STATUSES)
    if bad:
        raise A913RuleError(f"unknown value status(es) {sorted(bad)}")
    for s in (VALUE_TBD, VALUE_SYNTHETIC, VALUE_REFERENCE, VALUE_PARAMETRIC):
        if s in st:
            return s
    return VALUE_EVIDENCE


def constraint_status(ok: bool | None, value_status: str) -> str:
    """Map a comparison onto the constraint vocabulary: MET / VIOLATED only on determining evidence (S6.22)."""
    if ok is None or value_status == VALUE_TBD:
        return C_NOT_EVALUATED
    if value_status == VALUE_EVIDENCE:
        return C_MET if ok else C_VIOLATED
    if value_status == VALUE_SYNTHETIC:
        return C_MET_SYNTHETIC if ok else C_VIOLATED_SYNTHETIC
    return C_MET_PARAMETRIC if ok else C_VIOLATED_PARAMETRIC


# ================================================================================================= S6.8 / S6.11 domain
P_FREE_MOLECULAR_LIMIT_PA = 0.1      # = compressor_synthesis.P_MOLECULAR_LIMIT_PA (Chiggiato 2013 Sec. 4.1.2; test)
DOMAIN_IN = "IN_FREE_MOLECULAR_DOMAIN"
TRANSITIONAL_MODEL = {
    "module": "abep_sim/compressor_transitional.py",
    "evidence_status": "CANDIDATE_NOT_ADMITTED",
    "consumed_as_evidence": False,
    "rule": "A9.13 S6.8: no extrapolated > 0.1 Pa result is a valid architecture point until the transitional model has "
            "an admitted evidence basis and / or is validated against T-1 / T-2 hardware data",
}

DD_HIGHER_PRESSURE = "DD-HP"
DD_LOW_PRESSURE_FALLBACK = "DD-LE0P1"
DESIGN_DIRECTIONS = (
    {"id": DD_HIGHER_PRESSURE, "name": "higher-pressure compression path (compressor / feed chain producing the H-1 "
     "pressure and mass-flow state)", "role": "PRIMARY_DESIGN_DIRECTION",
     "evaluation_status": NOT_EVALUATED_OOD,
     "basis": "A9.13 S6.11 (RFP-P17-04: the compressor / gas reservoir increase the collected density to a usable "
              "ionization level); evaluable only once the > 0.1 Pa domain is closed by admitted evidence (S6.8)"},
    {"id": DD_LOW_PRESSURE_FALLBACK, "name": "<= 0.1 Pa high-conductance feed branch",
     "role": "SENSITIVITY_FALLBACK_STUDY_NOT_PRIMARY", "evaluation_status": PARAMETRIC_SENSITIVITY,
     "basis": "A9.13 S6.11: continued as a sensitivity / fallback study; never frozen as the primary architecture "
              "merely because the current compressor model stops at 0.1 Pa"},
)


def pressure_domain_status(p_max_Pa) -> str:
    """IN_FREE_MOLECULAR_DOMAIN when every pressure touched is <= 0.1 Pa, else NOT_EVALUATED_OUT_OF_DOMAIN
    (fail closed: a non-finite pressure is out of domain)."""
    if not _finite(p_max_Pa) or float(p_max_Pa) < 0.0:
        return NOT_EVALUATED_OOD
    return DOMAIN_IN if float(p_max_Pa) <= P_FREE_MOLECULAR_LIMIT_PA else NOT_EVALUATED_OOD


def classify_pressure_target(p_target_Pa: float) -> dict:
    """Design direction and domain status of a plenum / compressor-outlet target pressure (S6.8 + S6.11)."""
    if not _finite(p_target_Pa) or p_target_Pa <= 0.0:
        raise A913RuleError("target pressure must be finite and > 0")
    if p_target_Pa <= P_FREE_MOLECULAR_LIMIT_PA:
        return {"target_Pa": float(p_target_Pa), "design_direction": DD_LOW_PRESSURE_FALLBACK,
                "role": "SENSITIVITY_FALLBACK_STUDY_NOT_PRIMARY", "domain_status": DOMAIN_IN,
                "label": PARAMETRIC_SENSITIVITY}
    return {"target_Pa": float(p_target_Pa), "design_direction": DD_HIGHER_PRESSURE, "role": "PRIMARY_DESIGN_DIRECTION",
            "domain_status": NOT_EVALUATED_OOD, "label": NOT_EVALUATED_OOD,
            "reason": "above the 0.1 Pa free-molecular domain; the transitional model is CANDIDATE_NOT_ADMITTED "
                      "(A9.13 S6.8): no result is offered, none is extrapolated",
            "unlock": "admitted transitional-regime evidence (T-1 / T-2 compressor characterization or a "
                      "pre-registered held-out published dataset; abep_sim/compressor_transitional.py admission plan)"}


def refuse_candidate_evidence(obj) -> None:
    """Raise when ``obj`` is (or carries) a result of the CANDIDATE_NOT_ADMITTED transitional model (S6.8)."""
    st = getattr(obj, "evidence_status", None)
    if st is None and isinstance(obj, Mapping):
        st = obj.get("evidence_status")
    if st == TRANSITIONAL_MODEL["evidence_status"] or getattr(obj, "valid_design_evidence", True) is False:
        raise A913RuleError("transitional-regime candidate results are CANDIDATE_NOT_ADMITTED and are never consumed "
                            "as design evidence (A9.13 S6.8)")


# ================================================================================================= S6.10 setpoint schedule
CONTROL_MODE_SCHEDULED = "ORBIT_STATE_SCHEDULED_SETPOINT"
CONTROL_MODE_FIXED = "FIXED_SETPOINT"
CONTROL_MODES = {CONTROL_MODE_SCHEDULED: "BASELINE_CONTROL_MODE",
                 CONTROL_MODE_FIXED: "FALLBACK_DEGRADED_MODE_AND_COMPARISON_REFERENCE"}
SCHEDULE_STATUS = "NOT_FROZEN"      # until the compressor / feed / H-1 validated domains exist (S6.10)
# Kinds of controller-available inputs. The schedule never reads truth quantities of the environment model.
INPUT_KINDS = ("onboard_measurement", "onboard_estimate", "onboard_navigation_or_clock", "uplinked_command")
# Environment-model truth keys (atmosphere / TPMC / simulator internals) that no controller can read directly. An
# onboard ESTIMATE of such a quantity is admissible only as a separately named input 'est:<key>' with its estimator.
ORACLE_KEYS = ("rho_kg_m3", "n_O_m3", "n_N2_m3", "n_O2_m3", "n_He_m3", "n_Ar_m3", "n_N_m3", "x_O", "x_N2", "x_O2",
               "T_K", "f107", "f107a", "ap", "scenario", "mdot_fwd_kgps", "p_passive_Pa", "K_back", "flux_corot_kg_m2_s",
               "surface_scenario", "f1_status")


@dataclass(frozen=True)
class ScheduleInput:
    """One controller-available input: its name in the controller state, its kind and its (sensor / estimator /
    navigation) source."""
    name: str
    kind: str
    source: str

    def __post_init__(self):
        if self.kind not in INPUT_KINDS:
            raise A913RuleError(f"schedule input kind {self.kind!r} not in {INPUT_KINDS}")
        if not self.name.strip() or not self.source.strip():
            raise A913RuleError("schedule input needs a name and a source")
        if self.name in ORACLE_KEYS:
            raise A913RuleError(f"{self.name!r} is an environment-model truth quantity, not controller-available "
                                "(A9.13 S6.10); use an onboard estimate named 'est:<key>' with its estimator source")
        if self.name.startswith("est:") and self.kind != "onboard_estimate":
            raise A913RuleError("an 'est:' input must be of kind onboard_estimate")


@dataclass(frozen=True)
class SetpointSchedule:
    """Orbit-state-scheduled plenum setpoint (BASELINE control mode, S6.10): a piecewise-linear table of setpoint
    versus ONE controller-available input. Never frozen; outside the tabulated input range it refuses (no
    extrapolation). Setpoints above 0.1 Pa are allowed in the table (higher-pressure primary direction, S6.11) but
    evaluate to NOT_EVALUATED_OUT_OF_DOMAIN downstream."""
    schedule_id: str
    input: ScheduleInput
    breakpoints: tuple            # ((x0, p0_Pa), (x1, p1_Pa), ...), strictly increasing x
    label: str
    basis: str
    status: str = SCHEDULE_STATUS

    def __post_init__(self):
        if self.status != SCHEDULE_STATUS:
            raise A913RuleError("the setpoint schedule is never frozen before the compressor / feed / H-1 validated "
                                "domains exist (A9.13 S6.10)")
        if PARAMETRIC_SENSITIVITY not in self.label and SYNTHETIC not in self.label:
            raise A913RuleError("a schedule is a PARAMETRIC_SENSITIVITY (or synthetic test) object until the "
                                "validated domains exist; its label must say so")
        if not self.basis.strip():
            raise A913RuleError("schedule basis must be stated")
        bp = tuple(self.breakpoints)
        if len(bp) < 1:
            raise A913RuleError("schedule needs at least one breakpoint")
        xs = [b[0] for b in bp]
        if any(not (_finite(x) and _finite(p) and p > 0.0) for x, p in bp):
            raise A913RuleError("breakpoints must be finite with setpoint > 0")
        if xs != sorted(xs) or len(set(xs)) != len(xs):
            raise A913RuleError("breakpoint inputs must be strictly increasing")

    @property
    def mode(self) -> str:
        return CONTROL_MODE_SCHEDULED

    def setpoint(self, controller_state: Mapping) -> dict:
        """Setpoint for one controller state (a mapping holding ONLY controller-available inputs)."""
        bad = sorted(set(controller_state) & set(ORACLE_KEYS))
        if bad:
            raise A913RuleError(f"controller state carries environment-truth keys {bad} (A9.13 S6.10)")
        if self.input.name not in controller_state:
            return {"status": NOT_EVALUATED, "setpoint_Pa": None, "mode": self.mode,
                    "reason": f"controller input {self.input.name!r} missing"}
        x = controller_state[self.input.name]
        if not _finite(x):
            return {"status": NOT_EVALUATED, "setpoint_Pa": None, "mode": self.mode, "reason": "input not finite"}
        x = float(x)
        bp = self.breakpoints
        if len(bp) == 1:
            if x != bp[0][0]:
                return {"status": NOT_EVALUATED_OOD, "setpoint_Pa": None, "mode": self.mode,
                        "reason": "input outside the single tabulated point (no extrapolation)"}
            p = bp[0][1]
        else:
            if not bp[0][0] <= x <= bp[-1][0]:
                return {"status": NOT_EVALUATED_OOD, "setpoint_Pa": None, "mode": self.mode,
                        "reason": f"input {x} outside the schedule range [{bp[0][0]}, {bp[-1][0]}] (no extrapolation)"}
            p = None
            for (x0, p0), (x1, p1) in zip(bp, bp[1:]):
                if x0 <= x <= x1:
                    p = p0 + (p1 - p0) * (x - x0) / (x1 - x0)
                    break
        return {"status": "EVALUATED_SCHEDULE", "setpoint_Pa": float(p), "mode": self.mode, "label": self.label,
                "schedule_status": self.status, "domain": classify_pressure_target(float(p))}

    def to_dict(self) -> dict:
        return {"schedule_id": self.schedule_id, "mode": self.mode, "role": CONTROL_MODES[self.mode],
                "input": {"name": self.input.name, "kind": self.input.kind, "source": self.input.source},
                "breakpoints": [list(b) for b in self.breakpoints], "label": self.label, "basis": self.basis,
                "status": self.status}


@dataclass(frozen=True)
class FixedSetpoint:
    """Fixed plenum setpoint: fallback / degraded mode and the comparison reference (S6.10)."""
    setpoint_Pa: float
    label: str
    basis: str

    def __post_init__(self):
        if not (_finite(self.setpoint_Pa) and self.setpoint_Pa > 0):
            raise A913RuleError("fixed setpoint must be finite and > 0")
        if not self.basis.strip():
            raise A913RuleError("fixed setpoint basis must be stated")

    @property
    def mode(self) -> str:
        return CONTROL_MODE_FIXED

    def setpoint(self, controller_state: Mapping) -> dict:
        bad = sorted(set(controller_state) & set(ORACLE_KEYS))
        if bad:
            raise A913RuleError(f"controller state carries environment-truth keys {bad} (A9.13 S6.10)")
        return {"status": "EVALUATED_FIXED", "setpoint_Pa": float(self.setpoint_Pa), "mode": self.mode,
                "label": self.label, "domain": classify_pressure_target(float(self.setpoint_Pa))}

    def to_dict(self) -> dict:
        return {"mode": self.mode, "role": CONTROL_MODES[self.mode], "setpoint_Pa": self.setpoint_Pa,
                "label": self.label, "basis": self.basis}


def controller_view(full_state: Mapping, inputs: Sequence[ScheduleInput], mapping: Mapping[str, str]) -> dict:
    """Project a simulator state onto the declared controller inputs. ``mapping``: input name -> key in full_state
    (e.g. {'nav:alt_km': 'alt_km'}); a truth key may feed only an 'est:' input (its estimator is the declared source)."""
    out = {}
    for inp in inputs:
        key = mapping.get(inp.name)
        if key is None:
            raise A913RuleError(f"no source key mapped for controller input {inp.name!r}")
        if key in ORACLE_KEYS and not inp.name.startswith("est:"):
            raise A913RuleError(f"{inp.name!r} would read environment truth {key!r} directly (A9.13 S6.10)")
        if key not in full_state:
            raise A913RuleError(f"state has no {key!r} for controller input {inp.name!r}")
        out[inp.name] = full_state[key]
    return out


# ================================================================================================= S6.12 transients
F4_TRANSIENT_FRAMEWORK = {
    "status": "PROVISIONAL_PRE_LOCK2_ENGINEERING_CHARACTERIZATION",
    "settling_band_frac": 0.02, "observation_window_s": 60.0,
    "events": ["E0_hold", "E1_setpoint_up", "E2_setpoint_down", "E3_feed_path_step", "E4_feed_path_restore",
               "E5_supply_down", "E6_supply_up", "E7_supply_restore"],
    "outputs": ["settling_time_s", "peak_deviation_frac", "valve_travel", "ripple_transfer"],
    "orbit_modulation_cases": True,
    "rule": "A9.13 S6.12: retained for engineering development; not final H-1 tolerances. At LOCK-2 the measured H-1 "
            "feed sensitivity determines the allowable pressure / flow / composition bands; if it is tighter than the "
            "provisional F4 metric the H-1 limit governs (never relaxed to the F4 2 % band)",
    "source": "abep_sim/design/plenum_feed.py SETTLE_BAND, WINDOW_S, event_sequence",
}


@dataclass(frozen=True)
class H1Tolerance:
    """Allowable feed disturbance band of H-1 for one quantity (fraction of nominal). ``status`` EVIDENCE only for a
    measured H-1 feed-sensitivity result; TBD carries no value."""
    quantity: str                 # 'pressure' | 'mass_flow' | 'composition' | 'ripple'
    value_frac: float | None
    status: str
    source: str

    def __post_init__(self):
        if self.quantity not in ("pressure", "mass_flow", "composition", "ripple"):
            raise A913RuleError(f"unknown H-1 tolerance quantity {self.quantity!r}")
        if self.status not in VALUE_STATUSES:
            raise A913RuleError(f"status {self.status!r} not in {VALUE_STATUSES}")
        if self.status == VALUE_TBD:
            if self.value_frac is not None:
                raise A913RuleError("a TBD tolerance carries no value")
        elif not (_finite(self.value_frac) and self.value_frac > 0):
            raise A913RuleError("tolerance must be finite and > 0")
        if not self.source.strip():
            raise A913RuleError("tolerance needs a source")


def h1_tolerance_tbd(quantity: str) -> H1Tolerance:
    return H1Tolerance(quantity, None, VALUE_TBD, "H-1 measured feed sensitivity (LOCK-2; F5 IFD-F4-01..05): TBD")


def governing_band(quantity: str, f4_provisional_frac: float, h1: H1Tolerance | None) -> dict:
    """Which band governs (S6.12). Acceptance is the H-1 tolerance (NOT_EVALUATED while TBD); the engineering
    design target is the tighter of the two once H-1 is measured, so H-1 is never relaxed to the F4 band."""
    if not (_finite(f4_provisional_frac) and f4_provisional_frac > 0):
        raise A913RuleError("F4 provisional band must be finite and > 0")
    if h1 is None or h1.status == VALUE_TBD:
        return {"quantity": quantity, "acceptance_limit_frac": None, "acceptance_status": NOT_EVALUATED,
                "engineering_target_frac": float(f4_provisional_frac), "governing": "F4_PROVISIONAL_ENGINEERING_ONLY",
                "reason": "measured H-1 tolerance TBD (LOCK-2)"}
    tighter_h1 = h1.value_frac < f4_provisional_frac
    return {"quantity": quantity, "acceptance_limit_frac": h1.value_frac, "acceptance_status": h1.status,
            "engineering_target_frac": min(h1.value_frac, float(f4_provisional_frac)),
            "governing": "H1_MEASURED_TOLERANCE" if tighter_h1 else "H1_MEASURED_TOLERANCE (F4 band tighter: kept as "
                                                                    "engineering target only)",
            "h1_source": h1.source}


# A9.22: ripple_feed_quality moved to abep_sim/assessment/design_gates.py


# ================================================================================================= statewise quantifier
def _quantify(states, margin_fn, requirement_id):
    from ..statewise import statewise_quantifier                 # pure; reads no repository-only data
    return statewise_quantifier(states, margin_fn, requirement_id)


def statewise_envelope(requirement_id: str, states: Sequence[Mapping], margin_fn: Callable[[Mapping], float],
                       value_status: str) -> dict:
    """A9.14 S9.7 statewise envelope requirement: every required state must satisfy the requirement; the worst
    state and the orbit average are reported additionally; the average never hides a statewise deficit.

    ``value_status`` is the evidence status of the margins (VALUE_*). The quantifier's internal PASS / FAIL is mapped
    onto the constraint vocabulary: MET / VIOLATED only on determining evidence (S6.22)."""
    if value_status not in VALUE_STATUSES:
        raise A913RuleError(f"value_status {value_status!r} not in {VALUE_STATUSES}")
    q = _quantify(states, margin_fn, requirement_id)
    if q["verdict"] == "MODEL_ERROR" or value_status == VALUE_TBD:
        st = C_NOT_EVALUATED
    else:
        st = constraint_status(q["verdict"] == "PASS", value_status)
    per = [{"state_id": p["state_id"], "margin": p["margin"],
            "state_status": (C_NOT_EVALUATED if p["status"] == "MODEL_ERROR" or value_status == VALUE_TBD
                             else constraint_status(p["status"] == "PASS", value_status))}
           for p in q["per_state"]]
    return {"requirement_id": requirement_id, "status": st, "value_status": value_status,
            "n_states": q["n_states"], "n_states_below_zero": q["n_fail"], "n_model_error": q["n_model_error"],
            "worst_state": None if q["worst_state"] is None else
            {"state_id": q["worst_state"]["state_id"], "margin": q["worst_state"]["margin"]},
            "orbit_average_margin": q["orbit_average_margin"],
            "orbit_average_note": "informational only; the statewise result governs (A9.14 S9.7, A9.13 S6.15)",
            "average_hides_violation": q["average_hides_violation"], "per_state": per, "errors": q["errors"],
            "authority": cite("A9.14", "A9.13")}


# ================================================================================================= S6.15 AG-13 / HC-08
def _rec_value(rec: Mapping, what: str) -> tuple[float, str]:
    if not isinstance(rec, Mapping):
        raise A913RuleError(f"{what} record must be a mapping")
    st = rec.get("status")
    if st not in VALUE_STATUSES:
        raise A913RuleError(f"{what} status {st!r} not in {VALUE_STATUSES}")
    v = rec.get("value_N")
    if st == VALUE_TBD:
        return float("nan"), st
    if not _finite(v):
        raise A913RuleError(f"{what} value_N must be finite")
    return float(v), st


# A9.22: statewise_drag_compensation (AG-13 / HC-08) moved to abep_sim/assessment/design_gates.py


def reference_drag_fn(case_id: str, *, intake_projected_area_m2: float, intake_cd: float, intake_source: str,
                      intake_accounting: str, velocity_key: str = "v_rel_corot_m_s") -> Callable[[Mapping], dict]:
    """A drag_fn built on abep_sim.spacecraft_reference_drag.reference_drag (REFERENCE_PARAMETRIC only, never closure):
    density and relative speed are read from the orbit-resolved state itself (rho_kg_m3, ``velocity_key``)."""
    from .. import spacecraft_reference_drag as srd

    def fn(st: Mapping) -> dict:
        if velocity_key not in st:
            raise A913RuleError(f"state {st.get('state_id')!r} carries no {velocity_key!r} (relative speed); use "
                                "atmosphere_orbit.orbit_states")
        r = srd.reference_drag(case_id, rho_kg_m3=st["rho_kg_m3"], v_rel_m_s=st[velocity_key],
                               intake_projected_area_m2=intake_projected_area_m2, intake_cd=intake_cd,
                               intake_source=intake_source,
                               atmosphere_state={"source": "abep_sim.atmosphere_orbit", "state_id": st["state_id"]},
                               intake_accounting=intake_accounting)
        return {"value_N": r["D_total_N"], "status": VALUE_REFERENCE, "source": f"spacecraft_reference_drag {case_id}",
                "state_id": st["state_id"], "freeze_status": r["freeze_status"], "flags": r["flags"]}
    return fn


# ================================================================================================= S6.21 AG-12
CHARACTERIZATION_COVERAGE_MGPS = (0.38, 3.2)     # owner row 73 ground range: coverage only, never PASS / FAIL
FEED_STATE_FIELDS = ("mdot_kgps", "P_Pa", "T_K", "x_mole", "ripple_frac")


def characterization_coverage(mdot_kgps: float) -> dict:
    """Where a delivered flow sits relative to the 0.38-3.2 mg/s ground-characterization range (S6.21: coverage
    information only; it is never a flight requirement, never a pass / fail gate)."""
    if not _finite(mdot_kgps):
        return {"role": "CHARACTERIZATION_COVERAGE_NOT_A_REQUIREMENT", "mdot_mgps": None, "position": NOT_EVALUATED}
    m = float(mdot_kgps) * 1e6
    lo, hi = CHARACTERIZATION_COVERAGE_MGPS
    pos = "BELOW_COVERAGE" if m < lo else ("ABOVE_COVERAGE" if m > hi else "WITHIN_COVERAGE")
    return {"role": "CHARACTERIZATION_COVERAGE_NOT_A_REQUIREMENT", "mdot_mgps": m, "position": pos,
            "coverage_mgps": list(CHARACTERIZATION_COVERAGE_MGPS)}


def refuse_fixed_mass_flow_gate(gate) -> None:
    """S6.21: a fixed mg/s flight gate (0.38 mg/s, ~1.3 mg/s or any other number) is never applied."""
    if gate is not None:
        raise A913RuleError("A9.13 S6.21: no fixed mass-flow flight gate; AG-12 is a feed-state sufficiency gate "
                            "derived from the required thrust and a validated H-1 thrust-versus-feed map")


H1_MAP_VALIDATED = "VALIDATED"


# A9.22: feed_state_sufficiency (AG-12 / HC-11) moved to abep_sim/assessment/design_gates.py


# ================================================================================================= S6.13 OQ-F4-04 flow gap
# A9.13 S6.13 / OQ-F4-04, owner answer NO_REQUIREMENT_RELAXATION: the order in which the upstream flow gap is worked.
# The feed requirement is never lowered to what a chain happens to deliver; 0.38 mg/s is ground characterization only.
FLOW_GAP_AUTHORITY = "A9.13 S6.13 / OQ-F4-04 (NO_REQUIREMENT_RELAXATION)"
GROUND_CHARACTERIZATION_ONLY_MGPS = 0.38
FLOW_GAP_ORDER = (
    {"rank": 1, "lever": "PERFORMANCE_DERIVED_H1_FEED_REQUIREMENT", "authority": "A9.13 S6.21 / F9-OQ-02",
     "what": "derive the minimum feed state from the required drag-compensation thrust at every required state "
             "through the measured / validated H-1 thrust-versus-feed map (AG-12)",
     "status": "PENDING_EVIDENCE", "needs": "measured / validated H-1 thrust-versus-feed map (none exists)"},
    {"rank": 2, "lever": "CAPTURE_COLLECTION", "authority": "A9.13 S6.13",
     "what": "raise capture / collection within the drag (S6.15 statewise), mass and pointing constraints",
     "status": "OPEN"},
    {"rank": 3, "lever": "COMPRESSOR_DOMAIN_PUMPING_FEED_EFFICIENCY", "authority": "A9.13 S6.13",
     "what": "compressor domain, pumping and feed efficiency", "status": "OPEN"},
    {"rank": 4, "lever": "SCHEDULED_SETPOINT", "authority": "A9.13 S6.10 / OQ-F4-01",
     "what": "orbit-state-scheduled plenum setpoint (baseline control mode, not frozen)", "status": "OPEN"},
)
DENSE_STATE_ONLY_ROLE = "SENSITIVITY_ONLY_NOT_BASELINE"
FULL_STATE_SET = "FULL_REQUIRED_STATE_SET"
STATE_SUBSET = "STATE_SUBSET_SENSITIVITY_ONLY"
# bases a flight feed requirement may never be set from (fail closed)
FORBIDDEN_FEED_REQUIREMENT_BASES = ("GROUND_CHARACTERIZATION", "CHARACTERIZATION_COVERAGE", "DELIVERABLE_FRONTIER",
                                    "DENSE_STATE_ONLY", "STATE_SUBSET", "FIXED_MASS_FLOW_GATE")
PERFORMANCE_DERIVED_BASIS = "PERFORMANCE_DERIVED_VALIDATED_H1_MAP"


def flow_gap_record() -> dict:
    """The owner-ordered handling of the upstream flow gap (S6.13), carried in F4 / F7 outputs."""
    return {"authority": FLOW_GAP_AUTHORITY, "decision_record": {"json": STATE_SET_DECISIONS["A9.13"]["json"],
                                                                 "json_sha256": STATE_SET_DECISIONS["A9.13"]["json_sha256"],
                                                                 "id": "S6.13 / OQ-F4-04"},
            "order": [dict(x) for x in FLOW_GAP_ORDER],
            "rule": "no requirement relaxation: the flight feed requirement is performance-derived (rank 1, S6.21) "
                    "and is PENDING_EVIDENCE until a measured / validated H-1 thrust-versus-feed map exists; it is never "
                    "lowered to a deliverable frontier, a state subset or a characterization value",
            "ground_characterization_mgps": GROUND_CHARACTERIZATION_ONLY_MGPS,
            "ground_characterization_role": "GROUND_CHARACTERIZATION_ONLY_NEVER_A_FLIGHT_REQUIREMENT",
            "dense_state_only_operation": {"role": DENSE_STATE_ONLY_ROLE,
                                           "rule": "operation restricted to higher-density states is a sensitivity; it "
                                                   "cannot be baseline while it violates S6.15 (T - D >= 0 at EVERY "
                                                   "required state); S6.15 is NOT_EVALUATED today, so it is never "
                                                   "baseline-admissible"},
            "flight_feed_requirement": flight_feed_requirement()}


def flight_feed_requirement(h1_map=None) -> dict:
    """The flight feed requirement: performance-derived only (S6.21, rank 1 of S6.13). PENDING_EVIDENCE (no value)
    until a VALIDATED H-1 thrust-versus-feed map exists; a synthetic map never produces a flight requirement."""
    st = None if h1_map is None else getattr(h1_map, "status", None)
    if st != H1_MAP_VALIDATED:
        return {"status": "PENDING_EVIDENCE", "value": None, "basis": PERFORMANCE_DERIVED_BASIS,
                "needs": FLOW_GAP_ORDER[0]["needs"], "authority": [FLOW_GAP_AUTHORITY, "A9.13 S6.21 / F9-OQ-02"]}
    return {"status": "DERIVE_PER_STATE_FROM_VALIDATED_MAP", "value": None, "basis": PERFORMANCE_DERIVED_BASIS,
            "rule": "per required state via feed_state_sufficiency (AG-12); never a single number"}


def refuse_feed_requirement_lowering(basis: str, value_mgps=None) -> None:
    """S6.13 fail-closed guard: a flight feed requirement may only come from the performance-derived basis (S6.21).
    Any attempt to set it from the ground characterization value, the characterization coverage, a deliverable
    frontier, a dense-state-only / state-subset frontier or a fixed mg/s gate is refused."""
    if basis == PERFORMANCE_DERIVED_BASIS:
        return
    if basis in FORBIDDEN_FEED_REQUIREMENT_BASES or (value_mgps is not None and _finite(value_mgps)
                                                     and math.isclose(float(value_mgps),
                                                                      GROUND_CHARACTERIZATION_ONLY_MGPS)):
        raise A913RuleError(f"{FLOW_GAP_AUTHORITY}: a flight feed requirement is never set from {basis!r}"
                            + (f" ({value_mgps} mg/s)" if value_mgps is not None else "")
                            + "; it is performance-derived (S6.21) and PENDING_EVIDENCE until a validated H-1 map "
                              "exists; 0.38 mg/s is ground characterization only")
    raise A913RuleError(f"{FLOW_GAP_AUTHORITY}: unknown feed-requirement basis {basis!r} (only "
                        f"{PERFORMANCE_DERIVED_BASIS})")


def state_coverage(used_state_ids: Sequence[str], required_state_ids: Sequence[str]) -> dict:
    """S6.13 / S6.15: a result over a subset of the required states (e.g. the higher-density states only) is a
    sensitivity, never baseline; a result over the full required set is eligible (its own gates still apply)."""
    used, req = list(dict.fromkeys(used_state_ids)), list(dict.fromkeys(required_state_ids))
    if not req:
        raise A913RuleError("the required state set is empty")
    missing = [s for s in req if s not in set(used)]
    if not missing:
        return {"coverage": FULL_STATE_SET, "baseline_admissible_by_coverage": True, "n_required": len(req),
                "n_used_required": len(req), "missing": []}
    return {"coverage": STATE_SUBSET, "role": DENSE_STATE_ONLY_ROLE, "baseline_admissible_by_coverage": False,
            "n_required": len(req), "n_used_required": len(req) - len(missing), "missing_count": len(missing),
            "rule": f"{FLOW_GAP_AUTHORITY}: operation on a state subset is a sensitivity; it cannot be baseline while "
                    "S6.15 statewise drag compensation is violated or NOT_EVALUATED at any required state"}


def dense_state_only_operation(used_state_ids: Sequence[str], required_state_ids: Sequence[str],
                               s615_record: Mapping | None = None) -> dict:
    """Classify an operation restricted to a state subset (S6.13): baseline only if it covers every required state
    AND S6.15 is MET at every required state on determining evidence; otherwise SENSITIVITY_ONLY_NOT_BASELINE."""
    cov = state_coverage(used_state_ids, required_state_ids)
    s615 = (s615_record or {}).get("status", C_NOT_EVALUATED)
    if cov["coverage"] != FULL_STATE_SET:
        role = DENSE_STATE_ONLY_ROLE
    elif s615 == C_MET:
        role = "BASELINE_ELIGIBLE"
    else:
        role = "BASELINE_BLOCKED_S6_15_NOT_MET"
    return {**cov, "s6_15_status": s615, "role": role, "authority": FLOW_GAP_AUTHORITY}


# ================================================================================================= S6.16 surface scenarios
def require_all_admitted_scenarios(used: Sequence[str], admitted: Sequence[str],
                                   narrowing_record: Mapping | None = None) -> dict:
    """S6.16: robustness must cover EVERY admitted Maxwell / CLL / accommodation scenario. A subset is accepted only
    with a pre-registered DI-1.3 narrowing record (measured, applicable accommodation evidence, pre-registered
    mapping); the previous full-range cases are then preserved as sensitivity records."""
    used_s, adm = set(used), set(admitted)
    if not adm:
        raise A913RuleError("no admitted surface scenarios supplied")
    extra = sorted(used_s - adm)
    if extra:
        raise A913RuleError(f"scenarios {extra} are not admitted")
    missing = sorted(adm - used_s)
    if not missing:
        return {"status": "ALL_ADMITTED_SCENARIOS_COVERED", "admitted": sorted(adm), "narrowed": False}
    if narrowing_record is None:
        raise A913RuleError(f"robustness set omits admitted scenarios {missing}; a favourable surface model is never "
                            "selected (A9.13 S6.16); narrowing needs a pre-registered DI-1.3 record")
    for k in ("preregistration_id", "measurement_source", "mapping", "admitted_range"):
        if not str(narrowing_record.get(k, "")).strip():
            raise A913RuleError(f"DI-1.3 narrowing record lacks {k!r}")
    if narrowing_record.get("evidence_status") != VALUE_EVIDENCE:
        raise A913RuleError("DI-1.3 narrowing needs measured, applicable accommodation evidence")
    return {"status": "NARROWED_BY_PREREGISTERED_DI_1_3", "admitted": sorted(adm), "narrowed": True,
            "used": sorted(used_s), "preserved_as_sensitivity": missing,
            "narrowing_record": dict(narrowing_record)}


def robust_over_scenarios(per_scenario: Mapping[str, bool], admitted: Sequence[str]) -> dict:
    """Feasible only if feasible in EVERY admitted scenario (no favourable-scenario selection)."""
    require_all_admitted_scenarios(list(per_scenario), admitted)
    bad = sorted(s for s, ok in per_scenario.items() if not ok)
    return {"robust_feasible": not bad, "infeasible_in": bad, "n_scenarios": len(per_scenario)}


# ================================================================================================= S6.17 / S6.20 Pareto
PARETO_OBJECTIVES_S6_17 = (
    ("worst_state_margin", "max", "worst-state thrust / feed margin (AG-12 / AG-13); NOT_EVALUATED until a validated "
     "H-1 map and the spacecraft drag basis exist; the worst-state delivered flow is the upstream proxy"),
    ("drag_N", "min", "spacecraft / intake drag (worst state)"),
    ("P_upstream_W", "min", "upstream electrical power (worst state)"),
    ("mass_kg", "min", "hardware mass (or a declared monotone proxy)"),
    ("volume_m3", "min", "required volume (or a declared monotone proxy)"),
    ("Q_reject_W", "min", "thermal-rejection burden"),
)
HARD_CONSTRAINTS_FIRST = ("AG-12 feed-state / thrust sufficiency", "AG-13 statewise drag compensation", "power",
                          "mass", "thermal", "material / life", "H-1 feed-quality tolerances (ripple)")


def _dominates(a, b, senses) -> bool:
    better = False
    for x, y, s in zip(a, b, senses):
        if s == "max":
            x, y = -x, -y
        if x > y:
            return False
        if x < y:
            better = True
    return better


# A9.22: pareto_s6_17 (S6.17 system comparison) moved to abep_sim/assessment/design_gates.py


REGENERATION_TRIGGERS = (
    "S2 production-model corrections (A9.9)",
    "intake-surface v2",
    "filter implementation / evidence (S6.19)",
    "compressor search expanded beyond the inherited F3-front subset (hub ratio / blade span, S6.7)",
    "T-1 / T-2 compressor data",
    "DI-1.3 surface-accommodation evidence",
)


class RepresentativeSelectionRefused(A913RuleError):
    """S6.20: no single upstream representative is selected before LOCK-1."""


@dataclass(frozen=True)
class RobustParetoSet:
    """Versioned robust Pareto set carried to LOCK-1 (S6.20). Never reduced to a representative here."""
    set_id: str
    version: str
    members: tuple
    objectives: tuple
    label: str
    provenance: str
    regeneration_triggers: tuple = REGENERATION_TRIGGERS
    regenerated_after: tuple = ()

    def __post_init__(self):
        if not self.set_id.strip() or not self.version.strip() or not self.provenance.strip():
            raise A913RuleError("set_id, version and provenance are required")
        if len(set(self.members)) != len(self.members):
            raise A913RuleError("duplicate member ids")
        if any(w in self.label for w in FORBIDDEN_STATUS_WORDS):
            raise A913RuleError("the set label may not carry a selection word")

    def representative(self):
        raise RepresentativeSelectionRefused("A9.13 S6.20: carry the versioned robust Pareto set; no representative "
                                             "is selected until the regeneration triggers close and a selection rule "
                                             "is proposed")

    def engineering_reference(self, member_id: str, purpose: str) -> dict:
        """A member explicitly labelled as an engineering reference for a downstream study that needs one point."""
        if member_id not in self.members:
            raise A913RuleError(f"{member_id!r} is not a member of {self.set_id} v{self.version}")
        if not purpose.strip():
            raise A913RuleError("state the downstream purpose")
        return {"member_id": member_id, "set_id": self.set_id, "version": self.version,
                "label": "ENGINEERING_REFERENCE_NOT_THE_FROZEN_ARCHITECTURE", "purpose": purpose,
                "rule": "A9.13 S6.20: downstream studies evaluate all members or label a member an engineering "
                        "reference"}

    def pending_triggers(self) -> list:
        return [t for t in self.regeneration_triggers if t not in self.regenerated_after]

    def to_dict(self) -> dict:
        return {"set_id": self.set_id, "version": self.version, "members": list(self.members),
                "n_members": len(self.members), "objectives": list(self.objectives), "label": self.label,
                "provenance": self.provenance, "representative": "NONE (S6.20)",
                "regeneration_triggers": list(self.regeneration_triggers),
                "pending_regeneration_triggers": self.pending_triggers(), "authority": cite("A9.13")}


# ================================================================================================= A9.15 propellants
AIR_PATH = ("intake", "filter", "compressor", "atmospheric_gas_chamber", "valve")
XE_PATH = ("xe_tank", "valve")
PROPELLANT_POLICY = {
    "rule": "A9.15 as amended by A9.19 on the ROLE of Xe: the system supports BOTH ambient atmospheric propellant "
            "(180-230 km) and Xenon; two separate propellant tanks / paths (two supply modes AIR_PRIMARY and "
            "XE_CONTINGENCY); both feed the ONE Hall accelerator and the ONE RF/ICP neutralizer. Xe capability is "
            "RFP-required (RFP-P17-05 'an extra input system to take care any problems on board unforeseen problems'; "
            "RFP-P18-08) and its role is contingency / emergency (A9.19); no hollow cathode, so no C1 Xe branch in "
            "flight (A9.19 / A9.20: C1 ground-only)",
    "rfp_clauses": [RFP_CLAUSES["n2_o_xe"], RFP_CLAUSES["propellants"], RFP_CLAUSES["chain"]],
    "air_path": list(AIR_PATH), "xe_path": list(XE_PATH),
    "supply_modes": list(a919.SUPPLY_MODES), "xe_path_role": a919.XE_PATH_ROLE, "air_path_role": a919.AIR_PATH_ROLE,
}


# A9.22: propellant_paths_check (HC-10 structural check) moved to abep_sim/assessment/design_gates.py


# ================================================================================================= A9.22 moves
# These assessments live in abep_sim/assessment/design_gates.py (A9.22 layer separation). The deprecated import shims
# that re-exported them from this module were removed with the programme-layer split (callers import design_gates /
# abep_sim.programme.design_synthesis); the names are kept here as the record of what moved.
MOVED_TO_ASSESSMENT = ("ripple_feed_quality", "statewise_drag_compensation", "feed_state_sufficiency", "pareto_s6_17",
                       "propellant_paths_check")
