"""A9.16 step 1 - P2 impedance-map rules from the owner decisions of 2026-10-01 (lane P2 IMPEDANCE MAP).

Pure, deterministic, standard library only; imports the P2 reducer by path (same directory). No Julia, no network, not
wired into archengine. Every function returns a status from a fixed vocabulary or raises RuleError; none returns PASS.

Decisions applied (the VERBATIM .md of each was read in full and governs over the json 'summary' digest):
  A9.11 (docs/decisions/OD_2026_10_01_A9_11_s4_p2_owner_decisions.json) P2Q-01, P2Q-03, P2Q-04, P2Q-07, P2Q-08, P2Q-09
  A9.10 (docs/decisions/OD_2026_10_01_A9_10_s3_p1_later_stage_owner_decisions.json) P1Q-24 (k_loss = 2.0 lives in the
        reducer: K_LOSS, loss_check_protocol; P_delivered upper-bound rule)
  A9.14 (docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json) ICPQ-11, P2Q-10 (factors in
        p2_framework.rating_structure; transient check here), P2Q-06, F6-OQ-02

Owner numbers used (exactly the owner's): k_agreement = 2.0, k_transition = 2.0 (A9.11), k_loss = 2.0 (A9.10),
k_RF = 1.5, continuous RF power / current 1.25, thermal 1.20 (A9.14). Every number the owner deferred (periodic ZM-A
cross-check interval, required impedance discrimination, drawing-envelope bounds, fixed-tune representative regions,
...) is a REGISTRATION SLOT: missing -> NOT_EVALUATED_REGISTRATION, never a default.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("p2_impedance_reducer_for_a9_16_rules", str(_HERE / "p2_impedance_reducer.py"))
RED = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RED)

A911 = ("docs/decisions/OD_2026_10_01_A9_11_s4_p2_owner_decisions.json",
        "d8baf59a5b92739698e29d893e89a30995559ee7167814c096dc24599679156c")
A914 = ("docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json",
        "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c")

K_AGREEMENT = 2.0           # A9.11 S4.3 P2Q-03 (ZM-A vs ZM-B and up / down)
K_TRANSITION = 2.0          # A9.11 S4.7 P2Q-09 (HM-R06 non-optical indicators)
K_LOSS = RED.K_LOSS         # A9.10 S3.8 P1Q-24 (single P1 / P2 at-power loss factor)

NOT_EVALUATED_REGISTRATION = "NOT_EVALUATED_REGISTRATION"
NOT_EVALUATED_UNCERTAINTY = "NOT_EVALUATED_UNCERTAINTY"
NOT_EVALUATED_INSTRUMENT = "NOT_EVALUATED_INSTRUMENT"

# ---- P2Q-01 / P2Q-03 ZM-A vs ZM-B
AGREEMENT = "AGREEMENT_WITHIN_K"
METHOD_DISAGREEMENT = "METHOD_DISAGREEMENT"
ZM_B_MISSING_OR_INVALID = "ZM_B_MISSING_OR_INVALID"
ZM_METHOD_FIELDS = ("R_ohm", "X_ohm", "u_R_ohm", "u_X_ohm", "uncertainty_budget_id")
# A9.16 repair COR-07: a ZM-A / ZM-B comparison is only meaningful at the SAME registered operating point and
# configuration; both records name them, and ZM-B must carry an explicit valid = True
ZM_POINT_FIELDS = ("operating_point_id", "configuration_id")
# ---- P2Q-03 up / down
NO_HYSTERESIS = "NO_HYSTERESIS_RESOLVED_AT_REGISTERED_UNCERTAINTY"
RESOLVED_HYSTERESIS = "RESOLVED_HYSTERESIS"
# ---- P2Q-06 thrust stand
ZM_B_STAND_QUALIFIED = "ZM_B_STAND_USE_QUALIFIED_AFTER_BENCH_AGREEMENT"
ZM_B_STAND_NOT_QUALIFIED = "ZM_B_STAND_USE_NOT_QUALIFIED"
ZM_B_STAND_BLOCKED = "ZM_B_STAND_USE_BLOCKED_METHOD_DISAGREEMENT"
# ---- P2Q-04 tuning
RETUNE_MODE = "RETUNED_TO_MIN_REFLECTED_POWER"
FIXED_TUNE_MODE = "FIXED_TUNE_SUB_SWEEP"
RETUNE_FIELDS = ("tuning_mode", "matching_state_id", "encoder_values", "tune_time_s", "residual_reflection")
RESIDUAL_REFLECTION_KEYS = ("gamma_mag", "P_reflected_W")
INTERPOLATION_STEPS = ("CAL-P2-03", "CAL-P2-04")
REPRESENTATIVE_REGION_CLASSES = ("STABLE_NOMINAL_REGION", "OPERATING_ENVELOPE_EDGE", "NEAR_E_H_OR_IMPEDANCE_TRANSITION",
                                 "FLIGHT_MATCH_DESIGN_REGION")
# ---- P2Q-07 V/I calibration
CAL_ROUTES = ("ACCREDITED_ISO_IEC_17025_OR_NABL", "IN_HOUSE_VNA_TRACEABLE")
IN_HOUSE_LABEL = "IN_HOUSE_TRACEABLE_CALIBRATION_NOT_AN_ACCREDITED_LABORATORY_CERTIFICATE"
IN_HOUSE_REQUIRED = (
    "vna_and_cal_kit_certificates", "complex_vi_gain_13_56_MHz", "low_level_short_open_load_checks",
    "precision_50_ohm_reference", "reactive_reference_vna_characterized", "rp_vi_to_rp_ant_fixture",
    "pre_post_calibration_checks", "probe_cable_temperature_phase_drift", "repeatability",
    "uncertainty_propagation", "configuration_ids_raw_data_hashes")
FIXTURE_FORMS = ("CHARACTERIZED", "VERIFIED_PLANES_COINCIDE")
# ---- P2Q-08 isolation
BRIDGE_TARGETS = ("grounded_pressure_transducer", "chamber_facility_ground", "grounded_tubing_manifold",
                  "daq_instrument_chassis", "other_electrical_reference")
ISOLATION_ITEMS = ("isolator", "fittings", "tubing", "pressure_transducer_interface", "feedthroughs", "mounting",
                   "representative_pressure_gas_condition", "electrical_configuration_floating_bias_state")
ISOLATION_QUALIFIED = "ICPQ06_COMPLETE_INSTALLED_PATH_QUALIFIED"
NON_BRIDGING_DOCUMENTED = "NON_BRIDGING_DOCUMENTED_NO_DUPLICATE_TEST"
# ---- P2Q-09 HM-R06 indicators
HM_R06_INDICATORS = ("reflected_power_or_gamma_step_fixed_tuning", "impedance_R_or_X_step", "antenna_rf_current_step",
                     "collector_or_current_path_step", "pressure_step")
# ---- P2Q-10 transient
TRANSIENT_BELOW = "BELOW_MANUFACTURER_TRANSIENT_PEAK_RATING"
TRANSIENT_EXCEEDS = "EXCEEDS_MANUFACTURER_TRANSIENT_PEAK_RATING"
# ---- F6-OQ-02 geometry
INSIDE_ENVELOPE = "EVIDENCED_POINT_INSIDE_DRAWING_ENVELOPE"
OUTSIDE_ENVELOPE = "REFUSED_OUTSIDE_DRAWING_ENVELOPE_NEEDS_DRAWING_REVISION"


class RuleError(ValueError):
    """Malformed input to an owner rule (fail closed; never silently classified)."""


def _num(x, what):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise RuleError(f"{what} must be a finite number, got {x!r}")
    return float(x)


def _ref(x):
    return RED._ref_ok(x)


def _u_diff(ua, ub, r):
    """Combined standard uncertainty of a difference of two estimates with correlation coefficient r (GUM 5.2.2)."""
    v = ua * ua + ub * ub - 2.0 * r * ua * ub
    return math.sqrt(v) if v > 0 else 0.0


def _corr(r, what):
    if r is None:
        return 0.0
    r = _num(r, what)
    if not -1.0 <= r <= 1.0:
        raise RuleError(f"{what} must lie in [-1, 1]")
    return r


# ================================================================================ P2Q-01 / P2Q-03 method agreement
def method_agreement(zm_a, zm_b, *, r_R=None, r_X=None):
    """ZM-A (primary, RP-VI de-embedded to RP-ANT) vs ZM-B (RP-CPL de-embedding) at the SAME operating point; each a
    dict {R_ohm, X_ohm, u_R_ohm, u_X_ohm, uncertainty_budget_id} (its individual budget). z_R = |R_A - R_B| /
    u_c(R_A - R_B), z_X likewise (r_R / r_X: established correlation, default 0); agreement needs both <= 2.0.
    METHOD_DISAGREEMENT keeps both raw values, never an average, and blocks ZM-B stand-only qualification. A missing or
    invalid ZM-B never makes ZM-A independently verified (A9.11 P2Q-01 / P2Q-03). Both records also name the registered
    operating_point_id and configuration_id; ZM-B counts only with an explicit valid = True and the SAME operating
    point and configuration as ZM-A - a ZM-B without a validity flag, flagged invalid, or from another point /
    configuration is ZM_B_MISSING_OR_INVALID (A9.16 repair COR-07)."""
    if not isinstance(zm_a, dict) or any(zm_a.get(k) is None for k in ZM_METHOD_FIELDS + ZM_POINT_FIELDS):
        raise RuleError(f"ZM-A needs {ZM_METHOD_FIELDS + ZM_POINT_FIELDS} (its individual uncertainty budget and the "
                        "registered operating point / configuration; A9.11 P2Q-01)")
    out = {"k_agreement": K_AGREEMENT, "raw_zm_a": dict(zm_a), "raw_zm_b": dict(zm_b) if isinstance(zm_b, dict) else None,
           "averaged_value": None, "averaging": "never (A9.11 P2Q-03)", "zm_a_independently_verified": False,
           "blocks_zm_b_stand_qualification": True}
    why = None
    if not isinstance(zm_b, dict):
        why = "ZM-B per-point cross-check missing"
    elif zm_b.get("valid") is not True:
        why = "ZM-B record carries no explicit valid = True (absent or false validity flag)"
    elif any(zm_b.get(k) is None for k in ZM_METHOD_FIELDS + ZM_POINT_FIELDS):
        why = "ZM-B record incomplete (needs %s)" % ", ".join(ZM_METHOD_FIELDS + ZM_POINT_FIELDS)
    else:
        diff = [k for k in ZM_POINT_FIELDS if zm_b[k] != zm_a[k]]
        if diff:
            why = "ZM-B is from another %s than ZM-A (%s)" % (
                " / ".join(diff), "; ".join("%s: A %r, B %r" % (k, zm_a[k], zm_b[k]) for k in diff))
    if why is not None:
        out.update(status=ZM_B_MISSING_OR_INVALID,
                   reason=why + ": ZM-A is reported but NOT independently verified impedance evidence (A9.11 P2Q-01)")
        return out
    ua_r, ub_r = _num(zm_a["u_R_ohm"], "u_R_ohm(A)"), _num(zm_b["u_R_ohm"], "u_R_ohm(B)")
    ua_x, ub_x = _num(zm_a["u_X_ohm"], "u_X_ohm(A)"), _num(zm_b["u_X_ohm"], "u_X_ohm(B)")
    if min(ua_r, ub_r, ua_x, ub_x) < 0:
        raise RuleError("uncertainties must be >= 0")
    uc_r = _u_diff(ua_r, ub_r, _corr(r_R, "r_R"))
    uc_x = _u_diff(ua_x, ub_x, _corr(r_X, "r_X"))
    if uc_r <= 0 or uc_x <= 0:
        out.update(status=NOT_EVALUATED_UNCERTAINTY, reason="zero combined uncertainty of the difference")
        return out
    z_r = abs(_num(zm_a["R_ohm"], "R_A") - _num(zm_b["R_ohm"], "R_B")) / uc_r
    z_x = abs(_num(zm_a["X_ohm"], "X_A") - _num(zm_b["X_ohm"], "X_B")) / uc_x
    agree = z_r <= K_AGREEMENT and z_x <= K_AGREEMENT
    out.update(z_R=z_r, z_X=z_x, u_c_dR_ohm=uc_r, u_c_dX_ohm=uc_x,
               status=AGREEMENT if agree else METHOD_DISAGREEMENT, zm_a_independently_verified=agree,
               blocks_zm_b_stand_qualification=not agree,
               reason=("z_R and z_X <= k_agreement" if agree else
                       "metrology issue: both raw measurements retained, not averaged; ZM-B not qualified for "
                       "stand-only use until resolved (A9.11 P2Q-03)"))
    return out


def zm_c_resistance_crosscheck(R_A_ohm, u_R_A_ohm, I_rms_A, u_I_rms_A, P_delivered, u_P_delivered_W, *, r=None):
    """ZM-C (A9.11 P2Q-01): calibrated antenna RF current with VERIFIED delivered power -> R_C = P_delivered / I_rms^2,
    an independent resistance / power-loading cross-check of ZM-A (never the primary complex-impedance method). A
    P_delivered that is not a verified number (REFUSED string, upper bound, interval) -> NOT_EVALUATED (A9.10 P1Q-24).
    The normalized difference is REPORTED; the owner registered no separate ZM-C acceptance factor."""
    if isinstance(P_delivered, bool) or not isinstance(P_delivered, (int, float)):
        return {"status": "NOT_EVALUATED_LOSS_UNVERIFIED",
                "reason": "ZM-C needs verified delivered power; an unverified loss gives only the P_net upper bound "
                          "(A9.10 P1Q-24)"}
    p, i = _num(P_delivered, "P_delivered"), _num(I_rms_A, "I_rms_A")
    up, ui = _num(u_P_delivered_W, "u_P_delivered_W"), _num(u_I_rms_A, "u_I_rms_A")
    if i <= 0 or p <= 0:
        raise RuleError("I_rms > 0 and P_delivered > 0 required")
    r_c = p / (i * i)
    u_c = r_c * math.hypot(up / p, 2.0 * ui / i)
    ud = _u_diff(_num(u_R_A_ohm, "u_R_A"), u_c, _corr(r, "r"))
    if ud <= 0:
        return {"status": NOT_EVALUATED_UNCERTAINTY, "R_C_ohm": r_c}
    z = abs(_num(R_A_ohm, "R_A") - r_c) / ud
    return {"status": "REPORTED_INDEPENDENT_R_CROSS_CHECK", "R_C_ohm": r_c, "u_R_C_ohm": u_c, "z_R": z,
            "role": "independent resistance / power-loading cross-check, not the primary complex-impedance method"}


# ================================================================================ P2Q-03 up / down hysteresis
def updown_hysteresis(y_up, u_up, y_down, u_down, *, quantity, factor_level_id, r=None):
    """z_hyst = |Y_up - Y_down| / u_c(Y_up - Y_down) at the SAME registered factor level (A9.11 P2Q-03):
    <= 2.0 -> NO_HYSTERESIS_RESOLVED_AT_REGISTERED_UNCERTAINTY, > 2.0 -> RESOLVED_HYSTERESIS (a physical P2 finding,
    preserved in the map; never an instrumentation failure and never automatically a FAIL)."""
    if not _ref(factor_level_id) or not _ref(quantity):
        raise RuleError("quantity and the registered factor_level_id are required")
    uu, ud = _num(u_up, "u_up"), _num(u_down, "u_down")
    if uu < 0 or ud < 0:
        raise RuleError("uncertainties must be >= 0")
    uc = _u_diff(uu, ud, _corr(r, "r"))
    if uc <= 0:
        return {"quantity": quantity, "factor_level_id": factor_level_id, "status": NOT_EVALUATED_UNCERTAINTY}
    z = abs(_num(y_up, "Y_up") - _num(y_down, "Y_down")) / uc
    return {"quantity": quantity, "factor_level_id": factor_level_id, "z_hyst": z, "k": K_AGREEMENT,
            "status": RESOLVED_HYSTERESIS if z > K_AGREEMENT else NO_HYSTERESIS,
            "interpretation": "physical finding preserved in the map, not a FAIL" if z > K_AGREEMENT else
            "no hysteresis resolved at the registered uncertainty"}


def hysteresis_power_bases(up_record, down_record):
    """HM-R05 / A9.11 P2Q-03: hysteresis is reported against BOTH P_forward and VERIFIED P_delivered. A reduced record
    whose P_delivered is not a verified number gives the P_delivered basis NOT_EVALUATED_LOSS_UNVERIFIED (its upper
    bound P_net is never used as P_delivered; A9.10 P1Q-24)."""
    out = {}
    for name, rec in (("up", up_record), ("down", down_record)):
        if not isinstance(rec, dict) or "at_RP_CPL" not in rec:
            raise RuleError(f"{name}: a reduced record is required")
    out["P_forward_W"] = [up_record["at_RP_CPL"]["P_forward_W"], down_record["at_RP_CPL"]["P_forward_W"]]
    pd = [up_record.get("P_delivered_W"), down_record.get("P_delivered_W")]
    if all(isinstance(x, float) for x in pd) and all(str(r.get("loss_status", "")).startswith("VERIFIED")
                                                     for r in (up_record, down_record)):
        out["P_delivered_W"] = pd
    else:
        out["P_delivered_W"] = "NOT_EVALUATED_LOSS_UNVERIFIED (upper bound only; A9.10 P1Q-24)"
    return out


# ================================================================================ P2Q-06 ZM-B on the thrust stand
def zm_b_stand_qualification(bench_comparisons):
    """ZM-B may be used on the thrust stand (no V/I probe line across the moving stage) only after ZM-A / ZM-B bench
    agreement is demonstrated (A9.14 P2Q-06, A9.11 P2Q-03): every bench comparison (method_agreement outputs, one per
    valid bench map point) AGREEMENT_WITHIN_K; any unresolved METHOD_DISAGREEMENT blocks; a missing / invalid ZM-B or
    an unevaluated point leaves it NOT qualified."""
    if not isinstance(bench_comparisons, list) or not bench_comparisons:
        return {"status": ZM_B_STAND_NOT_QUALIFIED, "reason": "no bench ZM-A / ZM-B comparison"}
    st = [c.get("status") if isinstance(c, dict) else None for c in bench_comparisons]
    if METHOD_DISAGREEMENT in st:
        return {"status": ZM_B_STAND_BLOCKED, "n_points": len(st),
                "reason": "unresolved METHOD_DISAGREEMENT on the bench (A9.11 P2Q-03)"}
    if any(s != AGREEMENT for s in st):
        return {"status": ZM_B_STAND_NOT_QUALIFIED, "n_points": len(st),
                "reason": "bench points without a valid ZM-A / ZM-B agreement"}
    return {"status": ZM_B_STAND_QUALIFIED, "n_points": len(st),
            "zm_a_role": "bench reference and periodic / after-change cross-check (A9.14 P2Q-06)"}


def stand_zm_b_record_check(record, qualification, zm_a_crosschecks, registration):
    """A thrust-stand impedance record by ZM-B: needs the bench qualification, a ZM-A cross-check (AGREEMENT) for the
    record's current stand configuration_id (after any change), and the registered periodic cross-check interval
    (registration {interval_id, max_records_between_crosschecks, frozen_utc}; the owner set no number -> missing
    registration = NOT_EVALUATED_REGISTRATION). A V/I probe line across the moving stage is not routed without a
    recorded necessity basis (A9.14 P2Q-06)."""
    if not isinstance(record, dict) or not _ref(record.get("configuration_id")):
        raise RuleError("stand record needs configuration_id")
    if record.get("vi_probe_line_across_stage") is True and not _ref(record.get("vi_line_necessity_basis_id")):
        return {"status": "REFUSED_UNNECESSARY_VI_LINE_ACROSS_STAGE",
                "reason": "do not route an unnecessary V/I probe line across the moving stage (A9.14 P2Q-06)"}
    if not isinstance(qualification, dict) or qualification.get("status") != ZM_B_STAND_QUALIFIED:
        return {"status": ZM_B_STAND_NOT_QUALIFIED, "reason": "no bench ZM-A / ZM-B agreement demonstrated"}
    if not isinstance(registration, dict) or not _ref(registration.get("interval_id")) or \
            not _ref(registration.get("frozen_utc")) or \
            not isinstance(registration.get("max_records_between_crosschecks"), int) or \
            isinstance(registration.get("max_records_between_crosschecks"), bool) or \
            registration["max_records_between_crosschecks"] < 1:
        return {"status": NOT_EVALUATED_REGISTRATION,
                "reason": "periodic ZM-A cross-check interval not registered (the owner set no number)"}
    cfg = record["configuration_id"]
    xs = [x for x in (zm_a_crosschecks or []) if isinstance(x, dict) and x.get("configuration_id") == cfg]
    if not xs:
        return {"status": "NOT_EVALUATED_NO_ZM_A_CROSSCHECK_AFTER_CHANGE",
                "reason": f"no ZM-A cross-check for stand configuration {cfg!r} (after-change rule)"}
    last = xs[-1]
    if last.get("status") != AGREEMENT:
        return {"status": ZM_B_STAND_BLOCKED, "reason": "latest ZM-A cross-check does not agree"}
    n = record.get("records_since_crosscheck")
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise RuleError("records_since_crosscheck must be a non-negative integer")
    if n > registration["max_records_between_crosschecks"]:
        return {"status": "NOT_EVALUATED_PERIODIC_ZM_A_CROSSCHECK_DUE", "interval_id": registration["interval_id"]}
    return {"status": "ZM_B_STAND_RECORD_ADMISSIBLE", "crosscheck_id": last.get("comparison_id"),
            "interval_id": registration["interval_id"]}


# ================================================================================ P2Q-04 re-tune + fixed-tune
def retune_point_check(point, cal, interpolation_registration=None):
    """Primary hot-map point (A9.11 P2Q-04): re-tuned to the registered minimum-reflected-power condition with the
    matching-state id, element positions / encoder values, tune time and residual reflection logged; the state must be
    a characterized tuning state of the calibration set whose positions equal the logged encoder values, or come from
    the VERIFIED CAL-P2-03 / CAL-P2-04 interpolation rule (registration {rule_id, status VERIFIED, calibration_steps,
    verification_record_ids})."""
    if not isinstance(point, dict):
        raise RuleError("point must be an object")
    miss = [k for k in RETUNE_FIELDS if point.get(k) is None]
    if miss:
        return {"status": "REFUSED_RETUNE_LOG_INCOMPLETE", "missing": miss}
    if point["tuning_mode"] != RETUNE_MODE:
        return {"status": "REFUSED_NOT_RETUNED", "reason": "primary hot-map points are re-tuned at every point"}
    enc = point["encoder_values"]
    if not isinstance(enc, dict) or not enc:
        return {"status": "REFUSED_RETUNE_LOG_INCOMPLETE", "missing": ["encoder_values"]}
    t = _num(point["tune_time_s"], "tune_time_s")
    if t < 0:
        raise RuleError("tune_time_s must be >= 0")
    rr = point["residual_reflection"]
    if not isinstance(rr, dict) or not any(k in rr for k in RESIDUAL_REFLECTION_KEYS):
        return {"status": "REFUSED_RETUNE_LOG_INCOMPLETE", "missing": ["residual_reflection." + "|".join(
            RESIDUAL_REFLECTION_KEYS)]}
    for k in RESIDUAL_REFLECTION_KEYS:
        if k in rr:
            _num(rr[k], "residual_reflection." + k)
    states = ((cal or {}).get("two_ports") or {}).get("match_states") or {}
    ms = states.get(point["matching_state_id"])
    if isinstance(ms, dict) and ms.get("positions") == enc:
        return {"status": "RETUNED_CHARACTERIZED_STATE", "matching_state_id": point["matching_state_id"]}
    reg = interpolation_registration
    if isinstance(reg, dict) and reg.get("status") == "VERIFIED" and _ref(reg.get("rule_id")) \
            and set(reg.get("calibration_steps") or []) and set(reg["calibration_steps"]) <= set(INTERPOLATION_STEPS) \
            and isinstance(reg.get("verification_record_ids"), list) and reg["verification_record_ids"] \
            and all(_ref(x) for x in reg["verification_record_ids"]) and point.get("interpolation_rule_id") == reg["rule_id"]:
        return {"status": "RETUNED_VERIFIED_INTERPOLATION", "rule_id": reg["rule_id"]}
    return {"status": "REFUSED_UNCHARACTERIZED_TUNING_STATE",
            "reason": "only characterized tuning states or the verified CAL-P2-03/04 interpolation rule (A9.11 P2Q-04)"}


def fixed_tune_subsweep_check(selection_rule, subsweep):
    """Fixed-tune sub-sweep (A9.11 P2Q-04): around a pre-registered representative region; the representative-point
    selection rule {rule_id, frozen_utc, region_classes (subset of the four owner classes), text} is recorded BEFORE the
    sub-sweep data are interpreted (frozen_utc < subsweep.first_interpretation_utc, ISO-8601 UTC); one fixed tuning
    state for every point; role SUPPLEMENT to the primary re-tuned map (primary_map_id), never a replacement."""
    if not isinstance(selection_rule, dict) or not _ref(selection_rule.get("rule_id")) or \
            not _ref(selection_rule.get("frozen_utc")) or not _ref(selection_rule.get("text")):
        return {"status": NOT_EVALUATED_REGISTRATION, "reason": "representative-point selection rule not registered"}
    rc = selection_rule.get("region_classes")
    if not isinstance(rc, list) or not rc or not set(rc) <= set(REPRESENTATIVE_REGION_CLASSES):
        raise RuleError(f"region_classes must be a non-empty subset of {REPRESENTATIVE_REGION_CLASSES}")
    if not isinstance(subsweep, dict):
        raise RuleError("subsweep must be an object")
    if subsweep.get("rule_id") != selection_rule["rule_id"] or subsweep.get("region_class") not in rc:
        return {"status": "REFUSED_NOT_A_REGISTERED_REPRESENTATIVE_REGION"}
    if not _ref(subsweep.get("first_interpretation_utc")) or \
            not selection_rule["frozen_utc"] < subsweep["first_interpretation_utc"]:
        return {"status": "REFUSED_SELECTION_RULE_NOT_FROZEN_BEFORE_INTERPRETATION"}
    if subsweep.get("replaces_primary_map") is True or not _ref(subsweep.get("primary_map_id")):
        return {"status": "REFUSED_FIXED_TUNE_REPLACES_PRIMARY",
                "reason": "fixed-tune sub-sweeps supplement the re-tuned primary map, never replace it"}
    pts = subsweep.get("points")
    ts = {p.get("tuning_state_id") for p in pts} if isinstance(pts, list) and pts else set()
    if len(ts) != 1 or not _ref(next(iter(ts), None)) or any(p.get("tuning_mode") != FIXED_TUNE_MODE for p in pts):
        return {"status": "REFUSED_NOT_FIXED_TUNE", "reason": "one fixed tuning state for every sub-sweep point"}
    return {"status": "FIXED_TUNE_SUPPLEMENT_ADMISSIBLE", "tuning_state_id": ts.pop(),
            "role": "flight-match design evidence supplementing the primary re-tuned map"}


# ================================================================================ P2Q-07 V/I calibration
def vi_calibration_check(cal_record):
    """V/I-probe magnitude + relative-phase calibration at 13.56 MHz (A9.11 P2Q-07). Route ACCREDITED_ISO_IEC_17025_
    OR_NABL (laboratory id + scope covering magnitude AND relative phase at 13.56 MHz) or, where no accredited scope
    exists (accredited_scope_unavailable_basis), IN_HOUSE_VNA_TRACEABLE with every IN_HOUSE_REQUIRED element (short /
    open / load checks may be not_applicable with a reason), an explicit relative-phase uncertainty never inferred from
    the magnitude calibration, and a VERIFIED CAL-P2-15 at-power validation. The in-house record is labelled as such."""
    if not isinstance(cal_record, dict) or cal_record.get("route") not in CAL_ROUTES:
        raise RuleError(f"route must be one of {CAL_ROUTES}")
    v15 = cal_record.get("cal_p2_15_at_power_validation")
    v15_ok = isinstance(v15, dict) and v15.get("status") == "VERIFIED" and isinstance(v15.get("record_ids"), list) \
        and v15["record_ids"] and all(_ref(x) for x in v15["record_ids"])
    if cal_record["route"] == CAL_ROUTES[0]:
        sc = cal_record.get("accredited_scope") or {}
        if not _ref(cal_record.get("laboratory_id")) or sc.get("covers_magnitude_13_56_MHz") is not True or \
                sc.get("covers_relative_phase_13_56_MHz") is not True:
            return {"status": "REFUSED_ACCREDITED_SCOPE_NOT_DEMONSTRATED"}
        if not v15_ok:
            return {"status": "NOT_EVALUATED_CAL_P2_15_AT_POWER_VALIDATION_MISSING"}
        return {"status": "CALIBRATION_ADMISSIBLE", "label": "ACCREDITED_LABORATORY_CALIBRATION"}
    if not _ref(cal_record.get("accredited_scope_unavailable_basis")):
        return {"status": "REFUSED_IN_HOUSE_WITHOUT_SCOPE_UNAVAILABILITY_BASIS"}
    content = cal_record.get("content") or {}
    miss = []
    for k in IN_HOUSE_REQUIRED:
        v = content.get(k)
        if k == "low_level_short_open_load_checks" and isinstance(v, dict) and _ref(v.get("not_applicable_reason")):
            continue
        if k == "rp_vi_to_rp_ant_fixture":
            if not (isinstance(v, dict) and v.get("form") in FIXTURE_FORMS and _ref(v.get("record_id"))):
                miss.append(k)
            continue
        if k == "uncertainty_propagation":
            continue
        if not (isinstance(v, dict) and _ref(v.get("record_id"))):
            miss.append(k)
    up = content.get("uncertainty_propagation")
    phase_ok = isinstance(up, dict) and isinstance(up.get("u_relative_phase_deg"), (int, float)) \
        and not isinstance(up.get("u_relative_phase_deg"), bool) and up["u_relative_phase_deg"] > 0 \
        and isinstance(up.get("u_magnitude_rel"), (int, float)) and not isinstance(up.get("u_magnitude_rel"), bool) \
        and up["u_magnitude_rel"] > 0 and _ref(up.get("record_id")) \
        and up.get("relative_phase_basis") not in (None, "", "magnitude_calibration")
    if not phase_ok:
        miss.append("uncertainty_propagation (explicit relative-phase uncertainty, never inferred from magnitude)")
    if miss:
        return {"status": "REFUSED_IN_HOUSE_CONTENT_INCOMPLETE", "missing": miss}
    if not v15_ok:
        return {"status": "NOT_EVALUATED_CAL_P2_15_AT_POWER_VALIDATION_MISSING"}
    return {"status": "CALIBRATION_ADMISSIBLE", "label": IN_HOUSE_LABEL,
            "u_relative_phase_deg": up["u_relative_phase_deg"], "u_magnitude_rel": up["u_magnitude_rel"]}


def vi_measurement_adequacy(u_R_ohm, u_X_ohm, discrimination_registration):
    """A9.11 P2Q-07: if the resulting uncertainty is inadequate for the REGISTERED required impedance discrimination
    ({criterion_id, u_R_max_ohm, u_X_max_ohm, frozen_utc}; no number set here) the measurement is
    NOT_EVALUATED_INSTRUMENT - the uncertainty is never reduced administratively."""
    reg = discrimination_registration
    if not isinstance(reg, dict) or not _ref(reg.get("criterion_id")) or not _ref(reg.get("frozen_utc")) or \
            reg.get("u_R_max_ohm") is None or reg.get("u_X_max_ohm") is None:
        return {"status": NOT_EVALUATED_REGISTRATION, "reason": "required impedance discrimination not registered"}
    ur, ux = _num(u_R_ohm, "u_R_ohm"), _num(u_X_ohm, "u_X_ohm")
    if ur > _num(reg["u_R_max_ohm"], "u_R_max_ohm") or ux > _num(reg["u_X_max_ohm"], "u_X_max_ohm"):
        return {"status": NOT_EVALUATED_INSTRUMENT, "u_R_ohm": ur, "u_X_ohm": ux,
                "reason": "uncertainty inadequate for the registered discrimination; never reduced administratively"}
    return {"status": "ADEQUATE_FOR_REGISTERED_DISCRIMINATION", "criterion_id": reg["criterion_id"]}


# ================================================================================ P2Q-08 isolation boundary
def isolation_path_check(path):
    """ICPQ-06 applies to every ICP plumbing or pressure-sensing path (incl. ICP-34) that can bridge two intended
    isolated potentials (A9.11 P2Q-08). bridges_isolated_potentials True -> an isolating section and a qualification
    of the COMPLETE INSTALLED PATH (every ISOLATION_ITEMS entry verified or not applicable with a reason; the floating /
    bias electrical configuration; no unintended current-return path; registered single-point grounding topology).
    False -> documented non-bridging (no duplicate test). Unknown -> NOT_EVALUATED (a biased / floating point is not
    admissible)."""
    if not isinstance(path, dict) or not _ref(path.get("path_id")):
        raise RuleError("path needs path_id")
    b = path.get("bridges_isolated_potentials")
    if b is False:
        doc = path.get("non_bridging_documentation")
        if isinstance(doc, dict) and _ref(doc.get("document_id")) and _ref(doc.get("basis")):
            return {"status": NON_BRIDGING_DOCUMENTED, "path_id": path["path_id"],
                    "admits_floating_or_biased_point": True}
        return {"status": "NOT_EVALUATED_NON_BRIDGING_UNDOCUMENTED", "admits_floating_or_biased_point": False}
    if b is not True:
        return {"status": "NOT_EVALUATED_BRIDGING_UNKNOWN", "admits_floating_or_biased_point": False}
    tgt = path.get("connects_to")
    if not isinstance(tgt, list) or not tgt or not set(tgt) <= set(BRIDGE_TARGETS):
        raise RuleError(f"connects_to must list the bridged references from {BRIDGE_TARGETS}")
    q = path.get("qualification")
    if not _ref(path.get("isolating_section_id")) or not isinstance(q, dict):
        return {"status": "NOT_EVALUATED_ISOLATION_NOT_QUALIFIED", "admits_floating_or_biased_point": False}
    items = q.get("items") or {}
    miss = [k for k in ISOLATION_ITEMS
            if not (isinstance(items.get(k), dict) and (_ref(items[k].get("verified_id"))
                                                         or _ref(items[k].get("not_applicable_reason"))))]
    if q.get("scope") != "COMPLETE_INSTALLED_PATH" or miss or \
            q.get("no_unintended_current_return_path_demonstrated") is not True or \
            not _ref(q.get("grounding_topology_id")) or not _ref(q.get("electrical_configuration_id")):
        return {"status": "NOT_EVALUATED_ISOLATION_NOT_QUALIFIED", "missing": miss,
                "admits_floating_or_biased_point": False,
                "reason": "the complete installed path (not merely the nominal insulating component) must be "
                          "qualified in the floating / bias configuration (A9.11 P2Q-08)"}
    return {"status": ISOLATION_QUALIFIED, "path_id": path["path_id"], "admits_floating_or_biased_point": True}


# ================================================================================ P2Q-09 HM-R06 indicators
def transition_criteria_registration_check(reg, first_hot_map_reduction_utc):
    """The form (k x u_c over the HM-R06 indicator set) and k_transition = 2.0 are frozen before the first P2 hot-map
    reduction and never adjusted after observing transition locations (A9.11 P2Q-09)."""
    if not isinstance(reg, dict) or not _ref(reg.get("criteria_id")) or not _ref(reg.get("frozen_utc")):
        return {"status": NOT_EVALUATED_REGISTRATION, "reason": "transition criteria not registered"}
    if reg.get("form") != "k_times_uc" or reg.get("k_transition") != K_TRANSITION or \
            tuple(reg.get("indicators") or ()) != HM_R06_INDICATORS:
        raise RuleError(f"registered form must be k_times_uc, k_transition {K_TRANSITION}, indicators "
                        f"{HM_R06_INDICATORS} (A9.11 P2Q-09)")
    if not _ref(first_hot_map_reduction_utc) or not reg["frozen_utc"] < first_hot_map_reduction_utc:
        return {"status": NOT_EVALUATED_REGISTRATION,
                "reason": "criteria frozen at / after the first P2 hot-map reduction"}
    return {"status": "FROZEN_BEFORE_FIRST_HOT_MAP_REDUCTION", "criteria_id": reg["criteria_id"]}


def resolved_transition_indicators(indicators):
    """Adjacent-state difference of every APPLICABLE registered indicator relative to its combined uncertainty:
    resolved when |Delta y| / u_c(Delta y) > 2.0 (covariance via the correlation r when established). The reflected-
    power / |Gamma| indicator applies only at a fixed tuning state; the impedance indicator only where valid impedance
    data exist. A missing uncertainty raises (never silently 'not resolved')."""
    if not isinstance(indicators, list):
        raise RuleError("indicators must be a list")
    resolved, evaluated = [], []
    for ind in indicators:
        if not isinstance(ind, dict) or ind.get("name") not in HM_R06_INDICATORS:
            raise RuleError(f"indicator name must be one of {HM_R06_INDICATORS}")
        if ind.get("applicable") is not True:
            continue
        if ind["name"] == HM_R06_INDICATORS[0] and ind.get("fixed_tuning") is not True:
            continue
        if ind["name"] == HM_R06_INDICATORS[1] and ind.get("valid_impedance_data") is not True:
            continue
        for k in ("y_a", "y_b", "u_a", "u_b"):
            if ind.get(k) is None:
                raise RuleError(f"indicator {ind['name']}: {k} missing (combined uncertainty required)")
        uc = _u_diff(_num(ind["u_a"], "u_a"), _num(ind["u_b"], "u_b"), _corr(ind.get("r"), "r"))
        if uc <= 0:
            raise RuleError(f"indicator {ind['name']}: zero combined uncertainty")
        z = abs(_num(ind["y_b"], "y_b") - _num(ind["y_a"], "y_a")) / uc
        evaluated.append({"name": ind["name"], "z": z})
        if z > K_TRANSITION:
            resolved.append(ind["name"])
    return resolved, evaluated


def classify_with_hm_r06(obs, indicators):
    """A9.11 P2Q-09 classification: optical line of sight lost, saturated or threshold unavailable -> UNCERTAIN
    regardless of the electrical indicators; optical UNLIT + >= 1 resolved registered indicator -> UNCERTAIN with
    electrical_indicator_basis = exactly those indicators; optical UNLIT and none resolved -> UNLIT; optically lit ->
    the registered E/H rule (reducer classify_plasma_state), not overridden by the electrical channels."""
    if not isinstance(obs, dict):
        raise RuleError("obs must be an object")
    resolved, evaluated = resolved_transition_indicators(indicators)
    base = {"evaluated_indicators": evaluated, "k_transition": K_TRANSITION}
    if obs.get("photodiode_line_of_sight_ok") is not True:
        return dict(base, state="UNCERTAIN", electrical_indicator_basis=resolved,
                    reason="optical line of sight lost (or not recorded)")
    if obs.get("photodiode_saturated") is not False:
        return dict(base, state="UNCERTAIN", electrical_indicator_basis=resolved, reason="photodiode saturated")
    if obs.get("unlit_threshold_V") is None or obs.get("optical_signal_V") is None:
        return dict(base, state="UNCERTAIN", electrical_indicator_basis=resolved, reason="optical threshold unavailable")
    sig, thr = _num(obs["optical_signal_V"], "optical_signal_V"), _num(obs["unlit_threshold_V"], "unlit_threshold_V")
    if sig < thr:
        if resolved:
            return dict(base, state="UNCERTAIN", electrical_indicator_basis=resolved,
                        reason="optical UNLIT with statistically resolved non-optical transition evidence; not a proven "
                               "UNLIT cold reference (it does not declare that plasma ignited)")
        return dict(base, state="UNLIT", electrical_indicator_basis=[], reason="optical UNLIT, no resolved indicator")
    full = dict(obs, electrical_ignition_or_mode_transition=bool(resolved),
                electrical_indicator_basis=", ".join(resolved) if resolved else None)
    cls, why = RED.classify_plasma_state(full)
    return dict(base, state=cls, electrical_indicator_basis=resolved, reason=why)


# ================================================================================ P2Q-10 / ICPQ-11
def transient_stress_check(measured_transient_peak, manufacturer_rating):
    """Start-up / reflected-power / transient stress stays below the manufacturer's documented transient / peak rating
    (A9.14 P2Q-10; no factor added). manufacturer_rating {document_id, value, units}; missing -> NOT_EVALUATED."""
    if not isinstance(manufacturer_rating, dict) or not _ref(manufacturer_rating.get("document_id")) or \
            manufacturer_rating.get("value") is None:
        return {"status": "NOT_EVALUATED_NO_MANUFACTURER_TRANSIENT_RATING"}
    m, r = _num(measured_transient_peak, "measured_transient_peak"), _num(manufacturer_rating["value"], "rating")
    return {"status": TRANSIENT_BELOW if m < r else TRANSIENT_EXCEEDS, "document_id": manufacturer_rating["document_id"]}


# ================================================================================ F6-OQ-02 geometry
def geometry_point_check(point, drawing_envelope):
    """A9.14 S7.7 F6-OQ-02: the KC-1 / ICP LOCK-1 drawing envelope ({drawing_id, revision, bounds {var: [lo, hi]}}) is
    the hard design-variable bound; the registered P1 / P2 geometry matrix only marks evidenced points inside it. A
    point outside (or on another drawing revision, or with an unbounded variable) is refused - a test matrix never
    enlarges the envelope without a drawing revision. No envelope registered -> NOT_EVALUATED_REGISTRATION."""
    env = drawing_envelope
    if not isinstance(env, dict) or not _ref(env.get("drawing_id")) or not _ref(env.get("revision")) or \
            not isinstance(env.get("bounds"), dict) or not env["bounds"]:
        return {"status": NOT_EVALUATED_REGISTRATION, "reason": "LOCK-1 drawing envelope not registered"}
    if not isinstance(point, dict) or not _ref(point.get("geometry_id")) or not isinstance(point.get("variables"), dict):
        raise RuleError("geometry point needs geometry_id and variables")
    if point.get("drawing_revision") != env["revision"] or point.get("drawing_id") != env["drawing_id"]:
        return {"status": "REFUSED_DRAWING_REVISION_MISMATCH"}
    out = []
    for var, val in point["variables"].items():
        b = env["bounds"].get(var)
        if not (isinstance(b, (list, tuple)) and len(b) == 2):
            return {"status": "REFUSED_VARIABLE_NOT_BOUNDED_BY_DRAWING", "variable": var}
        lo, hi, v = _num(b[0], var + ".lo"), _num(b[1], var + ".hi"), _num(val, var)
        if not lo <= v <= hi:
            out.append(var)
    if out:
        return {"status": OUTSIDE_ENVELOPE, "variables": out}
    return {"status": INSIDE_ENVELOPE, "geometry_id": point["geometry_id"]}
