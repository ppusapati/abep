"""P2 ICP impedance-map reducer (follow-on fo_a9_p2_impedance_prep, trigger T_A9_P2_IMPEDANCE_PREP).

Pure, deterministic, standard library only (``cmath``/``math``). It converts CALIBRATED measurement records of the
13.56 MHz RF chain into the antenna-plane impedance Z_antenna = R + jX and the power-accounting quantities that owner
decision A9.2 (docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json, rf_measurement_reference) requires
to be retained: P_forward, P_reflected, |Gamma|, VSWR and, where possible,
P_delivered = P_forward - P_reflected - P_line/match,loss.  P_forward is never used as the plasma power.

It does not predict anything: no thrust, efficiency, discharge current, electron current, impedance or plasma state is
computed from a model. Every output is a transformation of a supplied measurement through a supplied calibration.
Missing calibration, a record without a reference plane, uncalibrated phase and any attempt to label P_forward (or any
input) as plasma power raise (CLAUDE.md rule 3: no silent fallbacks, no hidden defaults).

Reference planes (docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json reference_planes):
  RP-GEN  generator output connector (generator-internal meters are not a measurement plane, ICD ICP-14)
  RP-CPL  directional-coupler plane on the generator / 50-ohm side of the LOCAL matching network (A9.2)
  RP-MIN  input connector of the local matching network (end of the 50-ohm line, incl. the vacuum feedthrough)
  RP-ANT  antenna terminals (output side of the local matching network) - the plane of Z_antenna
  RP-VI   sensing plane of the V/I probe (at, or joined by a characterized fixture to, RP-ANT)

Two-port convention: ABCD matrices with port 1 toward the generator and port 2 toward the antenna,
V1 = A V2 + B I2, I1 = C V2 + D I2, I2 flowing into the load (Z_L = V2 / I2). S-parameters are referenced to Z0 at
both ports. Complex numbers are carried in JSON as [re, im].

Not wired into archengine (goldens do not move). Not imported by any abep_sim module.
"""
from __future__ import annotations

import cmath
import math

SCHEMA_ID = "p2_impedance_record_v1"
CAL_SCHEMA_ID = "p2_calibration_set_v1"
PLANES = ("RP-GEN", "RP-CPL", "RP-MIN", "RP-ANT", "RP-VI")
DATA_CLASSES = ("measured", "synthetic_test")
RECORD_PHASES = ("DUMMY_LOAD", "COLD_ANTENNA_POWERED_UNLIT", "HOT_MAP")
METHODS = ("vi_probe", "deembed")
LOSS_METHODS = ("two_port", "declared_bound", "not_available")
SWEEP_DIRECTIONS = ("up", "down", "reference", "single")
MODE_LABELS = ("UNLIT", "E", "H", "UNCERTAIN")
RATING_STATUS = "TBD_AFTER_IMPEDANCE_MAP"
SYNTHETIC_LABEL = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE"

# Single source of the record contract: the builder writes the JSON schema from these tuples and the tests check both.
REQUIRED_RECORD_FIELDS = (
    "schema", "record_id", "data_class", "phase", "calibration_set_id", "f_Hz", "Z0_ohm", "reference_planes",
    "methods", "loss_method", "coupler", "vi_probe", "match_state", "factors", "plasma_state", "sweep", "settling",
    "temperatures_K", "cold_reference_id", "p1_stable_region_ref", "antenna_current",
)
REQUIRED_FACTOR_FIELDS = (
    "P_RF_setpoint_W", "mdot_hall_anode_mg_s", "mdot_icp_dedicated_mg_s", "gas_mode", "gas", "p_icp_source_Pa",
    "p_chamber_Pa", "hall_state", "V_collector_V", "I_collector_A", "P_mains_in_W",
)
REQUIRED_CAL_FIELDS = ("schema", "calibration_set_id", "data_class", "f_Hz", "Z0_ohm", "power_sensors", "coupler",
                       "two_ports", "vi_probe", "loss_bounds", "cold_references", "antenna_current_probe")
FORBIDDEN_KEY_PREFIXES = ("P_plasma", "P_absorbed_plasma")
# Nested-object contracts (single source; the builder writes them into the JSON schema, the reducer enforces them).
NESTED_REQUIRED = {
    "coupler": ("P_sens_fwd_W", "P_sens_ref_W", "power_sensor_cal_id", "reflection_raw"),
    "vi_probe": ("V_raw", "I_raw", "vi_cal_id"),
    "match_state": ("tuning_state_id", "positions", "auto_tune", "loss_bound_id"),
    "factors": REQUIRED_FACTOR_FIELDS,
    "plasma_state": ("lit", "mode", "optical_signal_V"),
    "sweep": ("sweep_id", "direction", "index"),
    "settling": ("dwell_s", "settled"),
    "antenna_current": ("I_rms_A", "probe_cal_id"),
}
NULLABLE_OBJECTS = ("vi_probe", "antenna_current")
# Evidence tag derived from the gas (A9 evidence order; A9.3 OQ-RFQ-02, OQ-VI-05). Optional record field
# 'engineering_control' names a required engineering-control sequence; its only value now is "OQ-VI-05".
ENGINEERING_CONTROLS = ("OQ-VI-05",)
TAG_AR = "ENGINEERING_ONLY_NON_SCORING (A9.3 OQ-RFQ-02: Ar)"
TAG_VI05 = "REQUIRED_ENGINEERING_CONTROL_NON_SCORING (A9.3 OQ-VI-05)"
TAG_N2 = "N2_STAGE (A9 evidence order)"
TAG_O2 = "O2_BEARING_NO_ATOMIC_O (A9 evidence order)"
TAG_OTHER = "OTHER_GAS_UNCLASSIFIED_NON_SCORING"
TAG_NONE = "NO_GAS_NOT_APPLICABLE (calibration / dummy-load / unlit record)"
EVIDENCE_TAGS = (TAG_AR, TAG_VI05, TAG_N2, TAG_O2, TAG_OTHER, TAG_NONE)


class P2ReducerError(ValueError):
    """Base class of every refusal raised by the reducer."""


class MissingCalibrationError(P2ReducerError):
    pass


class ReferencePlaneError(P2ReducerError):
    pass


class UncalibratedPhaseError(P2ReducerError):
    pass


class ForwardAsPlasmaError(P2ReducerError):
    pass


class RecordError(P2ReducerError):
    pass


class SequenceError(P2ReducerError):
    """A HOT_MAP record without a P1 stable-region reference (A9.3: P1 stable plasma -> P2 plasma impedance map)."""


# ------------------------------------------------------------------------------------------------ basic relations
def cx(v, what):
    """[re, im] -> complex; refuses anything else (no implicit zero imaginary part)."""
    if not (isinstance(v, (list, tuple)) and len(v) == 2):
        raise RecordError(f"{what}: complex value must be [re, im], got {v!r}")
    re_, im_ = (_finite(v[0], what + ".re"), _finite(v[1], what + ".im"))
    return complex(re_, im_)


def _finite(x, what):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(float(x)):
        raise RecordError(f"{what}: finite number required, got {x!r}")
    return float(x)


def gamma_from_z(z, z0):
    """Reflection coefficient of load z on a line of real characteristic impedance z0."""
    if z0 <= 0:
        raise RecordError("Z0 must be > 0")
    if z + z0 == 0:
        raise RecordError("Z_L = -Z0: reflection coefficient undefined")
    return (z - z0) / (z + z0)


def z_from_gamma(g, z0):
    if g == 1:
        raise RecordError("Gamma = 1 (open): impedance undefined")
    return z0 * (1 + g) / (1 - g)


def vswr(gmag):
    if not 0 <= gmag < 1:
        raise RecordError(f"|Gamma| = {gmag} outside [0, 1): VSWR undefined")
    return (1 + gmag) / (1 - gmag)


def gamma_mag_from_powers(p_fwd, p_ref):
    if p_fwd <= 0 or p_ref < 0:
        raise RecordError("P_forward must be > 0 and P_reflected >= 0")
    if p_ref > p_fwd:
        raise RecordError("P_reflected > P_forward at the coupler plane: inconsistent reading")
    return math.sqrt(p_ref / p_fwd)


def s_to_abcd(s11, s12, s21, s22, z0):
    if s21 == 0:
        raise RecordError("S21 = 0: two-port has no transmission, cannot be de-embedded")
    a = ((1 + s11) * (1 - s22) + s12 * s21) / (2 * s21)
    b = z0 * ((1 + s11) * (1 + s22) - s12 * s21) / (2 * s21)
    c = ((1 - s11) * (1 - s22) - s12 * s21) / (2 * s21 * z0)
    d = ((1 - s11) * (1 + s22) + s12 * s21) / (2 * s21)
    return (a, b, c, d)


def abcd_to_s(abcd, z0):
    a, b, c, d = abcd
    den = a + b / z0 + c * z0 + d
    return ((a + b / z0 - c * z0 - d) / den, 2 * (a * d - b * c) / den, 2 / den, (-a + b / z0 - c * z0 + d) / den)


def cascade(m1, m2):
    a1, b1, c1, d1 = m1
    a2, b2, c2, d2 = m2
    return (a1 * a2 + b1 * c2, a1 * b2 + b1 * d2, c1 * a2 + d1 * c2, c1 * b2 + d1 * d2)


def z_in(abcd, z_load):
    a, b, c, d = abcd
    return (a * z_load + b) / (c * z_load + d)


def deembed_load(abcd, z_input):
    """Z_L at port 2 from the impedance seen at port 1: Z_L = (D Z_in - B) / (A - C Z_in)."""
    a, b, c, d = abcd
    den = a - c * z_input
    if den == 0:
        raise RecordError("de-embedding singular (A - C Z_in = 0)")
    return (d * z_input - b) / den


def transfer_efficiency(abcd, z_load):
    """Fraction of the net power entering port 1 that reaches a load z_load at port 2 (1 for a lossless network)."""
    a, b, c, d = abcd
    v1 = a * z_load + b
    i1 = c * z_load + d
    p1 = (v1 * i1.conjugate()).real
    if p1 <= 0:
        raise RecordError("non-positive input power in the two-port efficiency")
    return z_load.real / p1


def correct_reflection(m_raw, e00, e11, e10e01):
    """One-port three-term error model: Gamma = (m - e00) / (e10e01 + e11 (m - e00))."""
    den = e10e01 + e11 * (m_raw - e00)
    if den == 0:
        raise RecordError("reflection correction singular")
    return (m_raw - e00) / den


def fixture_to_plane(abcd_fix, v_p, i_p):
    """Voltage and current at the far side of a fixture from the probe-side values (inverse ABCD)."""
    a, b, c, d = abcd_fix
    det = a * d - b * c
    if det == 0:
        raise RecordError("fixture ABCD singular")
    return ((d * v_p - b * i_p) / det, (-c * v_p + a * i_p) / det)


def line_peak_stress(p_fwd, gmag, z0):
    """Peak voltage and current on a Z0 line carrying forward power p_fwd with reflection |Gamma| (standing wave)."""
    return (math.sqrt(2 * p_fwd * z0) * (1 + gmag), math.sqrt(2 * p_fwd / z0) * (1 + gmag))


# ------------------------------------------------------------------------------------------------ guards
def _is_plasma_power_key(k):
    """A key naming plasma power: the forbidden prefixes, or 'plasma' anywhere in a power-like key
    (starts with 'P_' / 'p_', contains 'power' or 'pwr', or carries a watt unit suffix '_W' / '_kW' / '_mW')."""
    if not isinstance(k, str):
        return False
    if k.startswith(FORBIDDEN_KEY_PREFIXES):
        return True
    kl = k.lower()
    if "plasma" not in kl:
        return False
    return (kl.startswith("p_") or "power" in kl or "pwr" in kl or kl.endswith(("_w", "_kw", "_mw"))
            or any(t in kl for t in ("_w_", "_kw_", "_mw_")))


def _scan_forbidden(obj, path="record"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if _is_plasma_power_key(k):
                raise ForwardAsPlasmaError(
                    f"{path}.{k}: plasma power is not an input of the impedance chain; P_forward (or P_net) is never "
                    "P_plasma (A9.2 rf_measurement_reference)")
            _scan_forbidden(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _scan_forbidden(v, f"{path}[{i}]")


def _check_labels(rec):
    labels = rec.get("power_labels", {})
    if not isinstance(labels, dict):
        raise RecordError("power_labels must be an object")
    for src, lab in labels.items():
        if "plasma" in str(lab).lower() or "plasma" in str(src).lower():
            raise ForwardAsPlasmaError(f"power_labels: {src} -> {lab}: P_forward / P_net / P_delivered is never "
                                       "labelled as plasma power (A9.2)")


def _require(d, fields, what):
    missing = [f for f in fields if f not in d]
    if missing:
        raise RecordError(f"{what}: missing fields {missing} (explicit null is allowed where the schema says so)")


def validate_calibration_set(cal):
    if not isinstance(cal, dict):
        raise MissingCalibrationError("calibration set must be an object")
    missing = [f for f in REQUIRED_CAL_FIELDS if f not in cal]
    if missing:
        raise MissingCalibrationError(f"calibration set {cal.get('calibration_set_id')!r}: missing {missing}")
    if cal["schema"] != CAL_SCHEMA_ID:
        raise MissingCalibrationError(f"calibration schema {cal['schema']!r} != {CAL_SCHEMA_ID}")
    if cal["data_class"] not in DATA_CLASSES:
        raise MissingCalibrationError(f"calibration data_class {cal['data_class']!r} not in {DATA_CLASSES}")
    _finite(cal["f_Hz"], "calibration f_Hz")
    _finite(cal["Z0_ohm"], "calibration Z0_ohm")


def _two_port_abcd(tp, z0, what):
    for k in ("from_plane", "to_plane", "S11", "S12", "S21", "S22", "cal_id", "phase_calibrated"):
        if k not in tp:
            raise MissingCalibrationError(f"{what}: missing {k}")
    if tp["phase_calibrated"] is not True:
        raise UncalibratedPhaseError(f"{what}: two-port S-parameters are not phase-calibrated (vector calibration "
                                     "required for de-embedding)")
    s = [cx(tp[k], f"{what}.{k}") for k in ("S11", "S12", "S21", "S22")]
    return s_to_abcd(*s, z0)


def network_cpl_to_ant(cal, tuning_state_id):
    """ABCD of RP-CPL -> RP-MIN (line incl. feedthrough) cascaded with RP-MIN -> RP-ANT (local match at the logged
    tuning state). Refuses a missing tuning state: interpolation between characterized states is a separate, declared
    calibration product (CAL-P2-04), never done silently here."""
    z0 = float(cal["Z0_ohm"])
    tps = cal["two_ports"]
    if not isinstance(tps, dict) or "line" not in tps or "match_states" not in tps:
        raise MissingCalibrationError("two_ports must contain 'line' and 'match_states'")
    line = tps["line"]
    if line is None:
        raise MissingCalibrationError("line two-port (RP-CPL -> RP-MIN) not characterized")
    if (line.get("from_plane"), line.get("to_plane")) != ("RP-CPL", "RP-MIN"):
        raise ReferencePlaneError(f"line two-port planes {line.get('from_plane')} -> {line.get('to_plane')} "
                                  "!= RP-CPL -> RP-MIN")
    states = tps["match_states"]
    if not isinstance(states, dict) or tuning_state_id not in states:
        raise MissingCalibrationError(f"local-match tuning state {tuning_state_id!r} has no characterized two-port")
    ms = states[tuning_state_id]
    if (ms.get("from_plane"), ms.get("to_plane")) != ("RP-MIN", "RP-ANT"):
        raise ReferencePlaneError(f"match two-port planes {ms.get('from_plane')} -> {ms.get('to_plane')} "
                                  "!= RP-MIN -> RP-ANT")
    return cascade(_two_port_abcd(line, z0, "line"), _two_port_abcd(ms, z0, f"match_states[{tuning_state_id}]"))


# ------------------------------------------------------------------------------------------------ reduction
def _plane(rec, key):
    rp = rec.get("reference_planes")
    if not isinstance(rp, dict) or not rp:
        raise ReferencePlaneError(f"record {rec.get('record_id')!r} has no reference_planes")
    if key not in rp or rp[key] is None:
        raise ReferencePlaneError(f"record {rec.get('record_id')!r}: no reference plane declared for '{key}'")
    if rp[key] not in PLANES:
        raise ReferencePlaneError(f"record {rec.get('record_id')!r}: plane {rp[key]!r} not in {PLANES}")
    return rp[key]


def _r(x, n=9):
    """Deterministic rounding for reported floats (significant digits)."""
    if x == 0 or not math.isfinite(x):
        return x
    return float(f"{x:.{n}g}")


def _cxo(z):
    return [_r(z.real), _r(z.imag)]


def reduce_record(rec, calibrations):
    """Reduce one calibrated record. ``calibrations`` maps calibration_set_id -> calibration set."""
    if not isinstance(rec, dict):
        raise RecordError("record must be an object")
    _scan_forbidden(rec)
    _check_labels(rec)
    if "reference_planes" not in rec or not rec.get("reference_planes"):
        raise ReferencePlaneError(f"record {rec.get('record_id')!r} has no reference_planes")
    _require(rec, REQUIRED_RECORD_FIELDS, f"record {rec.get('record_id')!r}")
    if rec["schema"] != SCHEMA_ID:
        raise RecordError(f"schema {rec['schema']!r} != {SCHEMA_ID}")
    if rec["data_class"] not in DATA_CLASSES:
        raise RecordError(f"data_class {rec['data_class']!r} not in {DATA_CLASSES}")
    if rec["phase"] not in RECORD_PHASES:
        raise RecordError(f"phase {rec['phase']!r} not in {RECORD_PHASES}")
    if rec["phase"] == "HOT_MAP":
        ref = rec["p1_stable_region_ref"]
        if not isinstance(ref, str) or not ref.strip() or ref.strip().upper().startswith(("PENDING", "TBD")):
            raise SequenceError("HOT_MAP record without a P1 stable-region reference: the plasma impedance map is "
                                "meaningful only inside a stable region handed over by P1 (A9.3 authorizations.P2)")
    for key, fields in NESTED_REQUIRED.items():
        if key in ("coupler", "vi_probe", "antenna_current"):
            continue                                  # checked where used (method / loss / cross-check paths)
        if not isinstance(rec[key], dict):
            raise RecordError(f"{key} must be an object")
        _require(rec[key], fields, key)
    if rec["plasma_state"]["mode"] not in MODE_LABELS:
        raise RecordError(f"plasma_state.mode {rec['plasma_state']['mode']!r} not in {MODE_LABELS}")
    if rec["sweep"]["direction"] not in SWEEP_DIRECTIONS:
        raise RecordError(f"sweep.direction {rec['sweep']['direction']!r} not in {SWEEP_DIRECTIONS}")
    tag = evidence_tag(rec)
    methods = rec["methods"]
    if not isinstance(methods, list) or not methods or any(m not in METHODS for m in methods):
        raise RecordError(f"methods must be a non-empty subset of {METHODS}")
    if rec["loss_method"] not in LOSS_METHODS:
        raise RecordError(f"loss_method {rec['loss_method']!r} not in {LOSS_METHODS}")

    cid = rec["calibration_set_id"]
    if not isinstance(calibrations, dict) or cid not in calibrations:
        raise MissingCalibrationError(f"calibration set {cid!r} not supplied")
    cal = calibrations[cid]
    validate_calibration_set(cal)
    f = _finite(rec["f_Hz"], "f_Hz")
    z0 = _finite(rec["Z0_ohm"], "Z0_ohm")
    if f != float(cal["f_Hz"]):
        raise MissingCalibrationError(f"record f = {f} Hz has no calibration (set {cid!r} is at {cal['f_Hz']} Hz)")
    if z0 != float(cal["Z0_ohm"]):
        raise MissingCalibrationError(f"record Z0 = {z0} ohm differs from calibration Z0 = {cal['Z0_ohm']} ohm")
    synthetic = rec["data_class"] == "synthetic_test" or cal["data_class"] == "synthetic_test"

    # ---- coupler powers at RP-CPL (A9.2: generator / 50-ohm side of the local match)
    cp = rec["coupler"]
    if not isinstance(cp, dict):
        raise RecordError("coupler readings required (the forward/reflected chain is the primary power measurement)")
    if _plane(rec, "coupler_powers") != "RP-CPL":
        raise ReferencePlaneError("forward/reflected power must be measured at RP-CPL (generator / 50-ohm side of the "
                                  "local matching network, A9.2 rf_measurement_reference)")
    _require(cp, NESTED_REQUIRED["coupler"], "coupler")
    ps = cal["power_sensors"]
    if not isinstance(ps, dict) or cp["power_sensor_cal_id"] not in ps:
        raise MissingCalibrationError(f"power-sensor calibration {cp['power_sensor_cal_id']!r} not in the set")
    psc = ps[cp["power_sensor_cal_id"]]
    for k in ("CF_fwd", "CF_ref", "certificate"):
        if k not in psc or psc[k] is None:
            raise MissingCalibrationError(f"power-sensor calibration lacks {k}")
    p_fwd = _finite(psc["CF_fwd"], "CF_fwd") * _finite(cp["P_sens_fwd_W"], "P_sens_fwd_W")
    p_ref = _finite(psc["CF_ref"], "CF_ref") * _finite(cp["P_sens_ref_W"], "P_sens_ref_W")
    g_scalar = gamma_mag_from_powers(p_fwd, p_ref)
    p_net = p_fwd - p_ref
    out = {
        "record_id": rec["record_id"], "phase": rec["phase"], "data_class": rec["data_class"],
        "evidence_status": SYNTHETIC_LABEL if synthetic else "measured (calibrated record reduction)",
        "evidence_tag": tag, "f_Hz": f, "Z0_ohm": z0, "calibration_set_id": cid,
        "at_RP_CPL": {"P_forward_W": _r(p_fwd), "P_reflected_W": _r(p_ref), "P_net_W": _r(p_net),
                      "gamma_mag_from_powers": _r(g_scalar), "VSWR_from_powers": _r(vswr(g_scalar)),
                      "note": "P_net = P_forward - P_reflected at RP-CPL; it includes the line, local-match and antenna "
                              "ohmic losses and is never the plasma power"},
        "factors": rec["factors"], "match_state": rec["match_state"], "plasma_state": rec["plasma_state"],
        "sweep": rec["sweep"], "settling": rec["settling"],
    }

    net = None
    z_ant = {}
    # ---- method B: de-embedding from the calibrated complex reflection at RP-CPL
    if "deembed" in methods:
        if cp["reflection_raw"] is None:
            raise UncalibratedPhaseError("de-embedding requested but only scalar forward/reflected powers were "
                                         "recorded: the complex reflection (magnitude AND phase) is required")
        if _plane(rec, "coupler_reflection") != "RP-CPL":
            raise ReferencePlaneError("complex reflection must be referred to RP-CPL")
        cc = cal["coupler"]
        if not isinstance(cc, dict):
            raise MissingCalibrationError("vector coupler/reflectometer calibration missing")
        if cc.get("phase_calibrated") is not True:
            raise UncalibratedPhaseError("coupler reflection channel is not phase-calibrated")
        for k in ("e00", "e11", "e10e01", "cal_id", "plane"):
            if k not in cc or cc[k] is None:
                raise MissingCalibrationError(f"coupler error model lacks {k}")
        if cc["plane"] != "RP-CPL":
            raise ReferencePlaneError(f"coupler calibration plane {cc['plane']!r} != RP-CPL")
        g_in = correct_reflection(cx(cp["reflection_raw"], "reflection_raw"), cx(cc["e00"], "e00"),
                                  cx(cc["e11"], "e11"), cx(cc["e10e01"], "e10e01"))
        ms = rec["match_state"]
        if not isinstance(ms, dict) or not ms.get("tuning_state_id"):
            raise MissingCalibrationError("match_state.tuning_state_id required to select the characterized network")
        net = network_cpl_to_ant(cal, ms["tuning_state_id"])
        zl = deembed_load(net, z_from_gamma(g_in, z0))
        z_ant["deembed"] = zl
        out["at_RP_CPL"].update({"gamma_complex": _cxo(g_in), "gamma_mag_complex": _r(abs(g_in)),
                                 "gamma_phase_deg": _r(math.degrees(cmath.phase(g_in))),
                                 "gamma_mag_scalar_minus_complex": _r(g_scalar - abs(g_in))})

    # ---- method A: V/I probe at RP-VI, carried to RP-ANT through the characterized fixture
    if "vi_probe" in methods:
        vp = rec["vi_probe"]
        if not isinstance(vp, dict):
            raise RecordError("vi_probe readings required for method 'vi_probe'")
        if _plane(rec, "vi_probe") != "RP-VI":
            raise ReferencePlaneError("V/I readings must be referred to RP-VI")
        _require(vp, NESTED_REQUIRED["vi_probe"], "vi_probe")
        vc = cal["vi_probe"]
        if not isinstance(vc, dict) or vc.get("cal_id") != vp["vi_cal_id"]:
            raise MissingCalibrationError(f"V/I probe calibration {vp['vi_cal_id']!r} not in the set")
        if vc.get("phase_calibrated") is not True:
            raise UncalibratedPhaseError("V/I probe relative phase is not calibrated: R = |Z| cos(phi) is then "
                                         "undetermined for a reactive antenna")
        for k in ("k_V", "k_I", "fixture_abcd", "fixture_from_plane", "fixture_to_plane"):
            if k not in vc or vc[k] is None:
                raise MissingCalibrationError(f"V/I calibration lacks {k} (an absent fixture is declared explicitly "
                                              "as the identity matrix, never assumed)")
        if (vc["fixture_from_plane"], vc["fixture_to_plane"]) != ("RP-VI", "RP-ANT"):
            raise ReferencePlaneError("V/I fixture must map RP-VI -> RP-ANT")
        v_p = cx(vc["k_V"], "k_V") * cx(vp["V_raw"], "V_raw")
        i_p = cx(vc["k_I"], "k_I") * cx(vp["I_raw"], "I_raw")
        fx = vc["fixture_abcd"]
        abcd_fix = (cx(fx[0][0], "fixture.A"), cx(fx[0][1], "fixture.B"), cx(fx[1][0], "fixture.C"),
                    cx(fx[1][1], "fixture.D"))
        v_a, i_a = fixture_to_plane(abcd_fix, v_p, i_p)
        if i_a == 0:
            raise RecordError("zero antenna current at RP-ANT: impedance undefined")
        z_ant["vi_probe"] = v_a / i_a
        out["at_RP_ANT_vi"] = {"V_peak_V": _r(abs(v_a)), "I_peak_A": _r(abs(i_a)),
                               "phase_V_minus_I_deg": _r(math.degrees(cmath.phase(v_a / i_a))),
                               "note": "phasor amplitudes are peak values if the calibration k_V, k_I are stated for peak"
                                       " (the calibration record states the convention)"}
        if "amplitude_convention" in vc:
            out["at_RP_ANT_vi"]["amplitude_convention"] = vc["amplitude_convention"]

    primary = "vi_probe" if "vi_probe" in z_ant else "deembed"
    zp = z_ant[primary]
    out["Z_antenna"] = {m: {"R_ohm": _r(z.real), "X_ohm": _r(z.imag), "plane": "RP-ANT"} for m, z in z_ant.items()}
    out["Z_antenna_primary_method"] = primary
    out["gamma_antenna_vs_Z0"] = {m: _r(abs(gamma_from_z(z, z0))) for m, z in z_ant.items()}
    if len(z_ant) == 2:
        dz = z_ant["vi_probe"] - z_ant["deembed"]
        out["method_difference"] = {"dR_ohm": _r(dz.real), "dX_ohm": _r(dz.imag),
                                    "acceptance": "TBD - agreement rule form LOCK-1, value LOCK-2 (P2Q-03)"}

    # ---- P_line/match,loss and P_delivered (A9.2)
    lm = rec["loss_method"]
    if lm == "two_port":
        if net is None:
            ms = rec["match_state"]
            if not isinstance(ms, dict) or not ms.get("tuning_state_id"):
                raise MissingCalibrationError("two_port loss needs match_state.tuning_state_id")
            net = network_cpl_to_ant(cal, ms["tuning_state_id"])
        eta = transfer_efficiency(net, zp)
        out["P_line_match_loss_W"] = _r(p_net * (1 - eta))
        out["P_delivered_W"] = _r(p_net * eta)
        out["match_line_efficiency"] = _r(eta)
        out["loss_basis"] = "two-port S-parameters (CAL-P2-02/03) at the logged tuning state with Z_antenna " + primary
    elif lm == "declared_bound":
        lb = cal["loss_bounds"]
        bid = rec["match_state"].get("loss_bound_id") if isinstance(rec["match_state"], dict) else None
        if not isinstance(lb, dict) or bid not in lb:
            raise MissingCalibrationError(f"declared loss bound {bid!r} not in the calibration set")
        b = lb[bid]
        for k in ("loss_fraction_max", "source", "evidence_class"):
            if k not in b or b[k] is None:
                raise MissingCalibrationError(f"loss bound {bid!r} lacks {k}")
        fmax = _finite(b["loss_fraction_max"], "loss_fraction_max")
        if not 0 <= fmax < 1:
            raise MissingCalibrationError("loss_fraction_max must lie in [0, 1)")
        out["P_line_match_loss_W"] = {"min": 0.0, "max": _r(p_net * fmax)}
        out["P_delivered_W"] = {"min": _r(p_net * (1 - fmax)), "max": _r(p_net)}
        out["loss_basis"] = f"declared bound {bid} ({b['source']}; {b['evidence_class']})"
    else:
        out["P_line_match_loss_W"] = "TBD - requires the two-port characterization (CAL-P2-02/03) or a declared loss bound"
        out["P_delivered_W"] = "TBD - requires P_line/match,loss; P_net at RP-CPL is not P_delivered"
        out["loss_basis"] = "not_available (declared in the record)"

    # ---- antenna-current cross-check (method C) and cold/hot resistance split (anchor Eq. (1) method)
    ac = rec["antenna_current"]
    if ac is not None:
        _require(ac, NESTED_REQUIRED["antenna_current"], "antenna_current")
        acp = cal["antenna_current_probe"]
        if not isinstance(acp, dict) or acp.get("cal_id") != ac["probe_cal_id"]:
            raise MissingCalibrationError(f"antenna current-probe calibration {ac['probe_cal_id']!r} not in the set")
        if acp.get("k_mag") is None or not acp.get("certificate"):
            raise MissingCalibrationError("antenna current-probe calibration lacks k_mag or its certificate")
        i_rms = _finite(acp.get("k_mag"), "k_mag") * _finite(ac["I_rms_A"], "I_rms_A")
        if i_rms <= 0:
            raise RecordError("antenna current must be > 0")
        pdel = out["P_delivered_W"]
        out["antenna_current_check"] = {
            "I_rms_A": _r(i_rms),
            "R_total_from_P_delivered_ohm": _r(pdel / i_rms ** 2) if isinstance(pdel, float) else
            "TBD - requires a numeric P_delivered",
            "R_total_from_P_net_ohm_incl_line_match": _r(p_net / i_rms ** 2),
            "note": "P_net / I^2 lumps line and match losses into the resistance (R_vac convention of RF-TAKA22-03)"}
    crid = rec["cold_reference_id"]
    if crid is not None:
        crs = cal["cold_references"]
        if not isinstance(crs, dict) or crid not in crs:
            raise MissingCalibrationError(f"cold antenna reference {crid!r} not in the set")
        cr = crs[crid]
        for k in ("R_cold_ohm", "source_record_id", "evidence_class", "antenna_temperature_K"):
            if k not in cr or cr[k] is None:
                raise MissingCalibrationError(f"cold reference {crid!r} lacks {k}")
        r_cold = _finite(cr["R_cold_ohm"], "R_cold_ohm")
        r_hot = zp.real
        if r_hot <= 0:
            raise RecordError("non-positive antenna resistance: cannot split")
        split = {"R_hot_ohm": _r(r_hot), "R_cold_ohm": _r(r_cold), "R_plasma_ohm": _r(r_hot - r_cold),
                 "eta_transfer": _r((r_hot - r_cold) / r_hot), "evidence_class": "reconstructed",
                 "assumption": "antenna-circuit resistance unchanged between the cold reference and the hot point "
                               "(temperature-dependent; UB-P2-Z-07; verify)"}
        pdel = out["P_delivered_W"]
        split["P_absorbed_Rsplit_W"] = (_r(pdel * (r_hot - r_cold) / r_hot) if isinstance(pdel, float)
                                        else "TBD - requires a numeric P_delivered")
        out["resistance_split"] = split
    return out


def evidence_tag(rec):
    """Evidence tag of a record from its gas and engineering-control label (never a score)."""
    ec = rec.get("engineering_control")
    if ec is not None and ec not in ENGINEERING_CONTROLS:
        raise RecordError(f"engineering_control {ec!r} not in {ENGINEERING_CONTROLS} (or null)")
    if ec == "OQ-VI-05":
        return TAG_VI05
    gas = rec["factors"].get("gas")
    if gas is None:
        if rec["phase"] == "HOT_MAP":
            raise RecordError("HOT_MAP record without factors.gas: the evidence stage cannot be tagged")
        return TAG_NONE
    if not isinstance(gas, str) or not gas.strip():
        raise RecordError(f"factors.gas must be a non-empty string or null, got {gas!r}")
    g = gas.strip().upper().replace(" ", "")
    if g in ("AR", "ARGON"):
        return TAG_AR
    if "O2" in g or "O_2" in g or g.startswith(("AIR", "OXYGEN")):
        return TAG_O2
    if g in ("N2", "NITROGEN"):
        return TAG_N2
    return TAG_OTHER


def mismatch_envelope(reduced, phases):
    """Envelope of reduced records for LATER RF component rating. ``phases`` must be given explicitly.

    The result is an input to rating, never a rating: its rating_status stays TBD_AFTER_IMPEDANCE_MAP (A9.2 rf_500W /
    a9_10_statuses) and it carries no margin or factor (k_RF is owner question ICPQ-11)."""
    if not isinstance(phases, (list, tuple)) or not phases or any(p not in RECORD_PHASES for p in phases):
        raise RecordError(f"phases must be a non-empty explicit subset of {RECORD_PHASES}")
    sel = [r for r in reduced if r["phase"] in phases]
    if not sel:
        raise RecordError("mismatch envelope over zero records")
    rs, xs, gl, pf, pr, gc, eff, vlp, ilp, vap, iap, pdl = ([] for _ in range(12))
    for r in sel:
        z = r["Z_antenna"][r["Z_antenna_primary_method"]]
        rs.append(z["R_ohm"])
        xs.append(z["X_ohm"])
        gl.append(r["gamma_antenna_vs_Z0"][r["Z_antenna_primary_method"]])
        c = r["at_RP_CPL"]
        pf.append(c["P_forward_W"])
        pr.append(c["P_reflected_W"])
        gc.append(c["gamma_mag_from_powers"])
        v, i = line_peak_stress(c["P_forward_W"], c["gamma_mag_from_powers"], r["Z0_ohm"])
        vlp.append(v)
        ilp.append(i)
        if "match_line_efficiency" in r:
            eff.append(r["match_line_efficiency"])
        if isinstance(r["P_delivered_W"], float):
            pdl.append(r["P_delivered_W"])
        if "at_RP_ANT_vi" in r:
            vap.append(r["at_RP_ANT_vi"]["V_peak_V"])
            iap.append(r["at_RP_ANT_vi"]["I_peak_A"])
        elif isinstance(r["P_delivered_W"], float) and z["R_ohm"] > 0:
            ipk = math.sqrt(2 * r["P_delivered_W"] / z["R_ohm"])
            iap.append(ipk)
            vap.append(ipk * math.hypot(z["R_ohm"], z["X_ohm"]))

    def rng(v):
        return {"min": _r(min(v)), "max": _r(max(v))} if v else "TBD - no record supplies this quantity"

    classes = sorted({r["data_class"] for r in sel})
    statuses = {r["evidence_status"] for r in sel}
    tags = sorted({r["evidence_tag"] for r in sel})
    if len(classes) > 1 or len(statuses) > 1:
        raise RecordError(f"mismatch envelope refuses to mix data classes / evidence statuses {classes} / "
                          f"{sorted(statuses)}: measured and synthetic records are never combined")
    if len(tags) > 1:
        raise RecordError(f"mismatch envelope refuses to mix evidence tags {tags}: Ar engineering-only, engineering-"
                          "control, N2 and O2-bearing records are enveloped separately")
    synthetic = SYNTHETIC_LABEL in statuses
    return {
        "n_records": len(sel), "phases": list(phases), "data_classes": classes, "evidence_tag": tags[0],
        "evidence_status": SYNTHETIC_LABEL if synthetic else "measured (P2 impedance map reduction)",
        "rating_status": RATING_STATUS,
        "rating_note": "an envelope of measured conditions, not a component rating: ratings (generator, coupler, coax, "
                       "connectors, local-match elements incl. voltage/current, feedthroughs) are selected by the owner"
                       " after the complete map of the P1 stable region; factor k_RF is ICPQ-11 (open)",
        "Z_antenna_R_ohm": rng(rs), "Z_antenna_X_ohm": rng(xs), "gamma_antenna_vs_Z0": rng(gl),
        "P_forward_W_at_RP_CPL": rng(pf), "P_reflected_W_at_RP_CPL": rng(pr), "gamma_mag_at_RP_CPL": rng(gc),
        "VSWR_max_at_RP_CPL": _r(vswr(max(gc))),
        "line_V_peak_max_V": _r(max(vlp)), "line_I_peak_max_A": _r(max(ilp)),
        "match_line_efficiency": rng(eff), "P_delivered_W": rng(pdl),
        "antenna_V_peak_V": rng(vap), "antenna_I_peak_A": rng(iap),
        "relations": "line peaks sqrt(2 P_fwd Z0)(1+|Gamma|), sqrt(2 P_fwd/Z0)(1+|Gamma|) (A9-07 "
                     "recomputations.rf_reference_plane.relations.peaks); antenna peaks from V/I where measured, else "
                     "I_pk = sqrt(2 P_delivered / R), V_pk = I_pk |Z|",
    }
