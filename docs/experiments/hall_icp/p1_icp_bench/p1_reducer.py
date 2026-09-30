"""P1 ICP electron-source bench - pure, deterministic analysis reducer (lane fo_a9_p1_icp_bench, A9.3 P1;
A9.4 incorporated by fo_a9_4_incorporation; owner A9.5 P1Q-15 / P1Q-16 applied by fo_a9_5_closure_rule).

What it does
------------
Takes raw P1 bench records (schema: p1_bench_record_schema_v1.json in this directory, generated from the constants
below by build_p1_icp_bench.py) and returns
  * the electron-current SURFACE table  I_e = f(P_RF, p, mdot, Z_ICP, V_collector)   (A9.3 OQ-A907-02),
  * RF-chain derived quantities |Gamma|, VSWR, P_RF,delivered = P_fwd - P_refl - P_line/match,loss   (A9.2 OQ-A907-11),
  * C_e = P_RF,delivered / I_e and C_e,DC = P_generator,input / I_e, each with its boundary label   (A9.3 OQ-RFQ-06),
  * Kirchhoff current-path closure residuals and the facility-electron contribution check,
  * dwell (stability) metrics, and the OQ-VI-05 topology-control observation class.

What it never does
------------------
* It predicts nothing: every output is arithmetic on recorded values (no Hall closure, no plasma model).
* It never returns PASS for ICP-45 because some current (1 A, 2 A, ...) was reached. The ICP-45A condition is
  evaluated only against a REGISTERED I_d,max,H1 (basis MEASURED_REGISTERED_H1_OPERATION) with an explicit one-sided
  margin rule; the 8.33 A stand ceiling and the 7.5 A power-envelope bound are refused as requirements.
* I_e,cap is never "the largest current in the bundle". Its definition is OWNER_DECIDED (A9.4 P1Q-10,
  CAPACITY_EXTRACTION_FORM; docs/decisions/OD_2026_09_30_A9_4_p1_p2_owner_decisions.json): a discharge-OFF extraction
  measurement - Hall discharge supply OFF and PHYSICALLY disconnected from the H-1 anode, ICP operating, electrons
  extracted to a dedicated, isolated, instrumented electron-collecting electrode, gas / magnetic field / pressure /
  geometry of a registered H-1 operating condition, matched RF-OFF record - with
  I_e,cap = I_e,collector,RFON - I_e,collector,RFOFF (the A9.4 recorder reading, CONFIRMED by owner A9.5 P1Q-16;
  docs/decisions/OD_2026_09_30_A9_5_p1_closure_owner_decisions.json) using SIGNED currents under the same registered
  convention: no absolute-value correction and no zero-clipping (a negative corrected value stays negative and is
  reported as such). Only records registered as record_class ICP45_CAPACITY are candidates; the capacity measurand is
  the dedicated electron-collector terminal current only (current into the H-1 body, facility ground, chamber, floating
  anode or cable shields never counts). Hall-ON records are NEUTRALIZATION_CONSISTENCY and never ICP45_CAPACITY: with
  the H-1 anode as the sink, current continuity makes the ICP-supplied current equal to I_d, so they cannot show
  capacity. Records without the facility correction are excluded (never silently credited); synthetic records give
  arithmetic only (SYNTHETIC_TEST_ONLY_NOT_EVIDENCE, condition_met None). Until I_d,max,H1 is registered from the H-1
  envelope and measured behaviour (never from the 8.33 A bench design ceiling) the ICP-45 result is exactly
  NOT_EVALUATED (never PASS or FAIL; A9.4 execution_decisions.i_d_max_h1).
* Kirchhoff current closure of a capacity point is the OWNER rule A9.5 P1Q-15 (kirchhoff_closure): one global
  convention (conventional current INTO the defined isolated electrical network is positive; every channel transformed
  into it and declaring the registered convention id), R_I = sum_k I_k over every intentional terminal crossing the
  network boundary, u_R = sqrt(sum_k u^2(I_k)) for independent channels (u(I_k) = calibration, zero/offset, resolution,
  repeatability where applicable, registered RF-pickup contribution) or the full covariance form when a registered
  correlation of the channels is supplied; closure-valid only if |R_I| <= 3 u_R AND |R_I| / max(I_e,collector,
  I_scale,min) <= 0.02. The factor 3 and the 2 % are owner constants (never caller parameters; a closure_rule that
  tries to set them is refused); I_scale,min is a REGISTERED instrument-capability floor with no default. An
  unavailable channel is never set to zero: a terminal declared NOT_MEASURED (an intentional return path unmeasured)
  or a channel without its uncertainty components excludes the point. If 3 u_R > 0.02 I_e,collector at the candidate
  (RF-ON) capacity point the point is NOT_EVALUATED_INSTRUMENT - the tolerance is never widened.
* A capacity record (record_class ICP45_CAPACITY) is REFUSED (raised, not flagged) when the anode is not
  DISCONNECTED_FLOATING (OPEN_CIRCUIT_BY_CONSTRUCTION), the discharge supply is not physically disconnected, V_anode is
  not on a high-impedance isolated channel, or the H-1 body single-point metered facility-ground return current
  (terminal h1_body) is not measured continuously (A9.4 P1Q-13). A METERED_RETURN anode is allowed only in a record
  registered as a separate DIAGNOSTIC_VARIANT, which never feeds I_e,cap.
* It never treats P_mains,in (laboratory generator mains input, GROUND/FACILITY_ONLY) as P_bus, and refuses any
  record field whose name reads as a bus quantity (any key that normalises to contain 'bus') and any
  generator.input_boundary text naming a bus.
* P1 records accept only the GROUND/FACILITY_ONLY mains generator (A9.3 OQ-RFQ-06); a
  FLIGHT_REPRESENTATIVE_DC_RF_SOURCE belongs to a later programme and is refused here.
* It never applies a stable-region threshold of its own: criteria are owner inputs; without them the verdict is
  NOT_EVALUATED.
* No hidden defaults: a missing input raises (CLAUDE.md rule 3).

Pure: stdlib + numpy only, no file or network I/O, no global state.
"""
import math

import numpy as np

SCHEMA_ID = "p1_bench_record_v1"
REQUIRED_LABEL = "ENGINEERING_ONLY_NON_SCORING"
TOPOLOGY_CONTROL_LABEL = "REQUIRED_ENGINEERING_CONTROL_NON_SCORING"
FORBIDDEN_LABELS = ("SCORE_BEARING_MEASURED", "QUALIFICATION_CAPABILITY", "ABSOLUTE_DEMONSTRATION",
                    "HELD_OUT_VALIDATION_EVIDENCE", "PASS")
# pattern screen on labels (normalised: upper-case alphanumerics) after removing the permitted 'NONSCORING' token
FORBIDDEN_LABEL_FRAGMENTS = ("SCOREBEARING", "SCORING", "SCORED", "PASS", "QUALIFICATION", "HELDOUT")
P1_GASES = ("Ar",)
GAS_MODES = ("G-REUSE", "DIAGNOSTIC_DEDICATED_FEED")
# hall_discharge_state = state of the DISCHARGE SUPPLY OUTPUT: ON = V_d applied by the discharge supply (output
# enabled, anode connected); OFF = output disabled and anode not connected to it. Whether a discharge is SUSTAINED is
# recorded separately (hall_discharge_sustained; with the supply OFF it must be false). P1-IT-40.
HALL_STATES = ("OFF", "ON")
# H-1 electrical configuration (P1-IT-39, P1Q-13; registered at P1-G0): anode state per supply state
ANODE_STATES = ("DISCONNECTED_FLOATING", "METERED_RETURN", "CONNECTED_TO_DISCHARGE_SUPPLY")
ANODE_STATES_BY_HALL_STATE = {"OFF": ("DISCONNECTED_FLOATING", "METERED_RETURN"),
                              "ON": ("CONNECTED_TO_DISCHARGE_SUPPLY",)}
ANODE_TERMINAL_BASIS = {"DISCONNECTED_FLOATING": "OPEN_CIRCUIT_BY_CONSTRUCTION", "METERED_RETURN": "MEASURED",
                        "CONNECTED_TO_DISCHARGE_SUPPLY": "MEASURED"}
H1_ELECTRICAL_REQUIRED = ("config_id", "anode_state", "V_anode_V", "h1_body_state", "discharge_supply_connection")
# A9.4 P1Q-13: with the discharge supply OFF its output is PHYSICALLY disconnected from the anode (never a commanded
# zero left attached); with it ON the output is connected
SUPPLY_CONNECTIONS = ("PHYSICALLY_DISCONNECTED", "CONNECTED")
SUPPLY_CONNECTION_BY_HALL_STATE = {"OFF": "PHYSICALLY_DISCONNECTED", "ON": "CONNECTED"}
# record classes (A9.4 P1Q-10 / P1Q-13): only ICP45_CAPACITY records can feed I_e,cap; Hall-ON records are
# NEUTRALIZATION_CONSISTENCY and never ICP45_CAPACITY; a METERED_RETURN anode exists only in a separately registered
# DIAGNOSTIC_VARIANT; ENGINEERING_SURFACE = Hall-OFF ignition / surface / stability records (P1-S3..S5)
CAPACITY_LABEL = "ICP45_CAPACITY"
CONSISTENCY_LABEL = "NEUTRALIZATION_CONSISTENCY"
DIAGNOSTIC_LABEL = "DIAGNOSTIC_VARIANT"
SURFACE_LABEL = "ENGINEERING_SURFACE"
RECORD_CLASSES = (CAPACITY_LABEL, CONSISTENCY_LABEL, DIAGNOSTIC_LABEL, SURFACE_LABEL)
RECORD_CLASSES_BY_HALL_STATE = {"OFF": (CAPACITY_LABEL, DIAGNOSTIC_LABEL, SURFACE_LABEL),
                                "ON": (CONSISTENCY_LABEL, DIAGNOSTIC_LABEL)}
# capacity-record electrical monitoring (A9.4 P1Q-13); required object on every ICP45_CAPACITY record.
# unintended_ground_path_found / ground_path_check_id: the recorded outcome and id of the check for any second
# (unintended) ground path of the isolated network (A9.4 P1Q-13 'no second chassis / stand / coax / shield path';
# A9.5 P1Q-15 exclusion 'an unintended ground path is found'); true -> the capacity point is excluded (kept with reason)
CAPACITY_MONITORING_REQUIRED = ("h1_body_ground_config", "I_body_to_ground_continuous", "V_anode_channel",
                                "V_icp_body_V", "V_electron_collector_V", "sign_convention_id",
                                "unintended_ground_path_found", "ground_path_check_id")
H1_BODY_GROUND_CONFIG = "SINGLE_POINT_METERED_FACILITY_GROUND"
V_ANODE_CHANNEL = "HIGH_IMPEDANCE_ISOLATED"
CAPACITY_EXTRA_TERMINALS = ("h1_body",)     # I_body->ground (single metered return), measured continuously
# ICP-45 status vocabulary: NOT_EVALUATED is the only status before I_d,max,H1 is registered (A9.4); it stays
# NOT_EVALUATED whenever no admissible capacity point exists (A9.5 P1Q-16)
ICP45A_STATUSES = ("NOT_EVALUATED", "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE", "EVALUATED_ENGINEERING_ONLY")
# per capacity point (RF-ON ICP45_CAPACITY record with its matched RF-OFF record) outcome vocabulary (A9.5 P1Q-15)
POINT_OUTCOMES = ("CLOSURE_VALID_CANDIDATE", "NOT_EVALUATED_INSTRUMENT", "EXCLUDED")
# ------------------------------------------------------------ A9.5 P1Q-15 Kirchhoff current-closure rule (owner)
A95_REF = "docs/decisions/OD_2026_09_30_A9_5_p1_closure_owner_decisions.json decisions.P1Q-15"
# the one global convention for every ICP-45 capacity record (owner text, A9.5 P1Q-15)
KIRCHHOFF_SIGN_CONVENTION = "CONVENTIONAL_CURRENT_INTO_THE_DEFINED_ISOLATED_ELECTRICAL_NETWORK_IS_POSITIVE"
# owner constants: statistical closure |R_I| <= 3 u_R; fractional closure <= 0.02 (never caller parameters)
CLOSURE_K_SIGMA = 3.0
CLOSURE_FRACTION_MAX = 0.02
# u(I_k) components of every MEASURED channel of a capacity record (A9.5 P1Q-15 'including: ...'); each is required.
# Only 'repeatability where applicable' and 'any registered RF-pickup contribution' may be declared explicitly absent,
# with the exact tokens below (never by omission); resolution must be a positive number.
U_COMPONENTS = ("u_calibration_A", "u_zero_offset_A", "u_resolution_A", "u_repeatability_A", "u_rf_pickup_A")
U_EXPLICIT_ABSENT = {"u_repeatability_A": "NOT_APPLICABLE", "u_rf_pickup_A": "NONE_REGISTERED"}
CLOSURE_RULE_REQUIRED = ("rule_id", "sign_convention", "sign_convention_id", "I_scale_min_A", "I_scale_min_basis")
CLOSURE_RULE_ALLOWED = CLOSURE_RULE_REQUIRED + ("covariance",)
COVARIANCE_REQUIRED = ("covariance_id", "terminals", "correlation")
RF_REFERENCE_PLANE = "GENERATOR_50OHM_SIDE_OF_LOCAL_MATCH"
LOSS_STATUSES = ("MEASURED", "FLAGGED_NOT_MEASURED")
# a MEASURED line/match loss is de-embedded from the two-port data AT the recorded match setting; it is valid only up
# to the residual |Gamma| limit of that characterization (P1-M-03, P1-IT-41)
LOSS_MEASURED_REQUIRED = ("value_W", "source", "match_setting_id", "valid_max_gamma_abs")
GENERATOR_CLASSES = ("GROUND_FACILITY_ONLY_MAINS",)
REFUSED_GENERATOR_CLASSES = ("FLIGHT_REPRESENTATIVE_DC_RF_SOURCE",)
# NOT_MEASURED: a terminal that exists but whose current is unavailable - declared, never silently zero (A9.5 P1Q-15);
# it carries no I_A value and no Kirchhoff residual is formed with it
TERMINAL_BASES = ("MEASURED", "OPEN_CIRCUIT_BY_CONSTRUCTION", "NOT_MEASURED")
# Electron-extraction topology (the electrode that SINKS the extracted electrons; the ICP 'collector' is the
# ion-collecting electrode inside the source, TK-13 / ICD ICP-21). Registered per run at P1-G0 (P1-IT-36, P1Q-09).
EXTRACTION_ELECTRODES = ("DEDICATED_ELECTRON_COLLECTOR_TARGET", "CHAMBER_WALL_FACILITY_GROUND", "H1_ANODE")
EXTRACTION_ELECTRODES_BY_HALL_STATE = {
    "OFF": ("DEDICATED_ELECTRON_COLLECTOR_TARGET", "CHAMBER_WALL_FACILITY_GROUND"),
    "ON": ("H1_ANODE",),
}
REFERENCE_POTENTIALS = ("FACILITY_GROUND", "ICP_BODY", "ELECTRON_COLLECTOR_ELECTRODE")
EXTRACTION_REQUIRED = ("topology_id", "electron_collecting_electrode")
REQUIRED_TERMINALS = {
    ("OFF", "DEDICATED_ELECTRON_COLLECTOR_TARGET"): ("collector_supply", "icp_body", "facility_ground",
                                                     "electron_collector", "hall_anode"),
    ("OFF", "CHAMBER_WALL_FACILITY_GROUND"): ("collector_supply", "icp_body", "facility_ground", "hall_anode"),
    ("ON", "H1_ANODE"): ("collector_supply", "icp_body", "facility_ground", "hall_anode"),
}
# I_e sign convention (declared per record): I_e_A > 0 = net electrons extracted from the ICP; the collector_supply
# terminal carries the same current, I_A = +I_e_A, as conventional current INTO the isolated network (the owner's
# global convention, A9.5 P1Q-15 / KIRCHHOFF_SIGN_CONVENTION)
I_E_SIGN_CONVENTION = "POSITIVE_ELECTRONS_EXTRACTED_FROM_ICP_EQUALS_COLLECTOR_SUPPLY_TERMINAL_INTO_NETWORK"
ICP45A_CAPACITY_STAGES = ("P1-S4", "P1-S7")
# Hall-ON follow-up after discharge-OFF capacity (A9.4 P1Q-10): stage P1-S7H
ICP45A_CONSISTENCY_STAGE = "P1-S7H"
REQUIRED_TEMPERATURES = ("T_icp_dielectric_C", "T_antenna_C", "T_collector_C", "T_match_C", "T_rf_source_C",
                         "T_h1_pole_inner_C", "T_h1_pole_outer_C", "T_sink_C")
PRESSURE_FIELDS = ("p_chamber_Pa",)
REGISTRATION_BASIS = "MEASURED_REGISTERED_H1_OPERATION"
REFUSED_REGISTRATION_BASES = ("STAND_CEILING", "SUPPLY_RATING", "POWER_ENVELOPE_BOUND", "ASSUMED")

OPERATING_POINT_REQUIRED = (
    "schema", "record_kind", "record_id", "run_id", "stage_id", "timestamp_utc", "synthetic", "labels", "gas",
    "gas_mode", "record_class", "hall_discharge_state", "hall_discharge_sustained", "h1_electrical", "rf", "generator", "collector",
    "extraction", "pressures", "flows", "impedance", "terminals", "temperatures", "rf_pickup_check",
)
RF_REQUIRED = ("reference_plane", "P_fwd_W", "P_refl_W", "line_match_loss", "match_setting_id")
GENERATOR_REQUIRED = ("generator_class", "P_generator_input_W", "input_boundary", "instrument")
COLLECTOR_REQUIRED = ("I_e_A", "I_e_sign_convention", "I_e_resolution_A", "V_collector_V", "reference_potential")
FLOWS_REQUIRED = ("mdot_Ar_H1_mg_s", "mdot_icp_dedicated_mg_s")
IMPEDANCE_REQUIRED = ("status",)
SEQUENCE_REQUIRED = ("schema", "record_kind", "record_id", "run_id", "stage_id", "synthetic", "labels", "gas",
                     "classification", "c1_disconnected", "hall_start_registration_id", "steps")
SEQUENCE_SIGNALS = ("t_s", "V_d_V", "I_d_A", "I_e_icp_A", "P_rf_fwd_W", "P_rf_refl_W", "V_collector_V",
                    "V_reference_V")
SEQUENCE_STEPS = (
    (1, "H-1 gas/magnet conditions established."),
    (2, "C1 disconnected/not supplying electrons."),
    (3, "ICP RF OFF."),
    (4, "Apply the preregistered Hall start attempt inside registered limits."),
    (5, "Record whether a sustained Hall discharge exists."),
    (6, "Turn ICP ON using the registered procedure."),
    (7, "Observe whether Hall discharge becomes sustainable."),
)
BOUNDARY_C_E = ("P_RF,delivered at the generator / 50-ohm side of the LOCAL matching network minus the measured "
                "P_line/match,loss (A9.2 OQ-A907-11); RF boundary, not a DC or bus boundary")
BOUNDARY_C_E_UPPER = ("UPPER_BOUND: P_fwd - P_refl at the generator / 50-ohm side of the local match; "
                      "P_line/match,loss NOT measured (explicitly flagged); P_fwd is never P_plasma (A9.2)")
BOUNDARY_C_E_DC = {
    "GROUND_FACILITY_ONLY_MAINS": ("P_mains,in: AC mains input of the LABORATORY 13.56 MHz generator measured by a "
                                   "power analyzer; GROUND/FACILITY_ONLY (A9.3 OQ-RFQ-06); includes laboratory "
                                   "AC/DC stages; NOT P_bus and never evidence for P_bus < 1.5 kW"),
}
I_E_CAP_DEFINITION = ("OWNER_DECIDED (A9.4 P1Q-10, CAPACITY_EXTRACTION_FORM; formula OWNER_CONFIRMED by A9.5 "
                      "P1Q-16): I_e,cap = I_e,collector,RFON - I_e,collector,RFOFF using SIGNED currents under the same "
                      "registered current convention (no absolute-value correction, no zero-clipping; the RF-OFF term "
                      "estimates facility/background electron collection); I_e,collector = current of the dedicated, "
                      "isolated, instrumented electron-collecting electrode (terminal electron_collector, electrons "
                      "collected = -I_A under the registered convention 'conventional current INTO the isolated network "
                      "positive', A9.5 P1Q-15); eligible = record_class ICP45_CAPACITY, stage P1-S4 or P1-S7, Hall "
                      "discharge supply OFF and physically disconnected, anode floating (OPEN_CIRCUIT_BY_CONSTRUCTION), "
                      "gas_mode G-REUSE, P_fwd > 0, rf_pickup_check DONE, h1_point_id in the registration's "
                      "registered_point_ids, and ICP-45A evaluated only when (1) the capacity point passes the A9.5 "
                      "Kirchhoff closure (|R_I| <= 3 u_R and |R_I| / max(I_e,collector, I_scale,min) <= 0.02, RF-ON and "
                      "matched RF-OFF records), (2) the matched RF-OFF correction is valid (P1-D-07), (3) all required "
                      "uncertainties are available (u(I_k) of every channel; u_I_e_A and u_I_d_max_A of the margin rule) "
                      "and (4) I_d,max,H1 is registered; then the preregistered one-sided lower bound M_n,LB of "
                      "M_n = I_e,cap / I_d,max,H1 - 1 must be > 0; until all four exist ICP45 = NOT_EVALUATED. Hall-ON "
                      "records are NEUTRALIZATION_CONSISTENCY and never define I_e,cap")


class P1RecordError(ValueError):
    """Base class: a P1 record cannot be reduced."""


class MissingInputError(P1RecordError):
    """A required input is absent or None."""


class LabelError(P1RecordError):
    """Engineering-only labelling or classification is missing or contradicted."""


class LineMatchLossError(P1RecordError):
    """P_delivered requested without a measured or explicitly flagged line/match loss term."""


class PMainsNotPBusError(P1RecordError):
    """An attempt to use a laboratory generator input (P_mains,in) as P_bus."""


class RegistrationError(P1RecordError):
    """I_d,max,H1 not registered from measured H-1 operation, or margin rule missing."""


class SequenceError(P1RecordError):
    """The OQ-VI-05 seven-step topology-control record is incomplete or out of order."""


class GasModeError(P1RecordError):
    """G-REUSE / dedicated-feed accounting violated (A9.3 OQ-RFQ-10)."""


class ExtractionTopologyError(P1RecordError):
    """Electron-extraction topology undeclared or inconsistent with the Hall discharge state."""


class RFConsistencyError(P1RecordError):
    """Forward / reflected / line-loss readings that no passive RF chain can produce."""


class CapacityConfigurationError(P1RecordError):
    """A capacity record (ICP45_CAPACITY) with a METERED_RETURN / connected anode, a connected discharge supply, no
    high-impedance isolated V_anode channel, no continuous H-1 body ground-current record, or a METERED_RETURN anode
    outside a registered DIAGNOSTIC_VARIANT (A9.4 P1Q-13). Refused, never merely flagged."""


class ClosureRuleError(P1RecordError):
    """A closure_rule that tries to set or widen an owner constant (the factor 3, the 2 %), names another sign
    convention than the owner's, or carries a malformed registered covariance (A9.5 P1Q-15)."""


# ------------------------------------------------------------------------------------------------ helpers
def _req(obj, keys, where):
    if not isinstance(obj, dict):
        raise MissingInputError("%s: expected an object, got %r" % (where, type(obj).__name__))
    for k in keys:
        if k not in obj or obj[k] is None:
            raise MissingInputError("%s: missing required input '%s'" % (where, k))


def _num(x, where, allow_negative=True):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(float(x)):
        raise MissingInputError("%s: expected a finite number, got %r" % (where, x))
    if not allow_negative and x < 0:
        raise P1RecordError("%s: negative value %r not allowed" % (where, x))
    return float(x)


def _labels_ok(rec, where):
    labels = rec.get("labels")
    if not isinstance(labels, list) or REQUIRED_LABEL not in labels:
        raise LabelError("%s: every P1 record (gas %r) must carry the label %s (A9.3 OQ-RFQ-02; owner row 36)"
                         % (where, rec.get("gas"), REQUIRED_LABEL))
    bad = []
    for lab in labels:
        norm = "".join(ch for ch in str(lab).upper() if ch.isalnum()).replace("NONSCORING", "")
        if lab in FORBIDDEN_LABELS or any(frag in norm for frag in FORBIDDEN_LABEL_FRAGMENTS):
            bad.append(lab)
    if bad:
        raise LabelError("%s: P1 records are non-scoring; forbidden label(s) %s" % (where, bad))


def _normalise_key(key):
    return "".join(ch for ch in str(key).lower() if ch.isalnum())


def _refuse_p_bus_claim(obj, where, path=""):
    """Recursive screen: any field name that normalises to contain 'bus' (P_bus_W, Pbus_W, bus_power_W, ...)."""
    if isinstance(obj, dict):
        for key, val in obj.items():
            here = path + "." + str(key) if path else str(key)
            if "bus" in _normalise_key(key):
                raise PMainsNotPBusError("%s: field '%s' present; a P1 bench record never carries P_bus - the "
                                         "laboratory generator input is P_mains,in (GROUND/FACILITY_ONLY, A9.3 "
                                         "OQ-RFQ-06)" % (where, here))
            _refuse_p_bus_claim(val, where, here)
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            _refuse_p_bus_claim(val, where, "%s[%d]" % (path, i))


def p_bus_from_generator_input(record):
    """Always refuses: P_mains,in (or any single generator input) is never P_bus (A9.3 OQ-RFQ-06; A9-02 A902-19)."""
    gen = (record or {}).get("generator") or {}
    raise PMainsNotPBusError(
        "refused: generator input (class %r) is not P_bus. P_bus is all electrical power crossing the spacecraft-side "
        "DC boundary (A9-02); the P1 laboratory generator is GROUND/FACILITY_ONLY and its P_mains,in is an "
        "engineering quantity only" % gen.get("generator_class"))


# ------------------------------------------------------------------------------------------------ validation
def validate_operating_point(rec):
    """Raise on any missing or contradictory input of an 'icp_operating_point' record; return None if valid."""
    rid = "record %r" % (rec.get("record_id") if isinstance(rec, dict) else None)
    _req(rec, OPERATING_POINT_REQUIRED, rid)
    if rec["schema"] != SCHEMA_ID:
        raise P1RecordError("%s: schema %r != %s" % (rid, rec["schema"], SCHEMA_ID))
    if rec["record_kind"] != "icp_operating_point":
        raise P1RecordError("%s: record_kind %r is not icp_operating_point" % (rid, rec["record_kind"]))
    if not isinstance(rec["synthetic"], bool):
        raise MissingInputError("%s: 'synthetic' must be true or false" % rid)
    if rec["gas"] not in P1_GASES:
        raise P1RecordError("%s: gas %r is outside P1 (Ar only, A9.3 P1 authorization; N2 is ICP-45N, not P1)"
                            % (rid, rec["gas"]))
    _labels_ok(rec, rid)
    _refuse_p_bus_claim(rec, rid)
    if rec["hall_discharge_state"] not in HALL_STATES:
        raise P1RecordError("%s: hall_discharge_state %r not in %s" % (rid, rec["hall_discharge_state"], HALL_STATES))
    if not isinstance(rec["hall_discharge_sustained"], bool):
        raise MissingInputError("%s: hall_discharge_sustained must be true or false (recorded against the registered "
                                "sustainment definition, P1-IT-32)" % rid)
    if rec["hall_discharge_state"] == "OFF" and rec["hall_discharge_sustained"]:
        raise P1RecordError("%s: a sustained Hall discharge with the discharge supply OFF is contradictory "
                            "(hall_discharge_state is the supply-output state, P1-IT-40)" % rid)
    h1e = rec["h1_electrical"]
    _req(h1e, H1_ELECTRICAL_REQUIRED, rid + " h1_electrical")
    if not isinstance(h1e["config_id"], str) or not h1e["config_id"].strip():
        raise MissingInputError("%s: h1_electrical.config_id must be the id registered at P1-G0 (P1-IT-39)" % rid)
    if not isinstance(h1e["h1_body_state"], str) or not h1e["h1_body_state"].strip():
        raise MissingInputError("%s: h1_electrical.h1_body_state must be recorded (registered at P1-G0)" % rid)
    _num(h1e["V_anode_V"], rid + " h1_electrical.V_anode_V")
    if h1e["anode_state"] not in ANODE_STATES_BY_HALL_STATE[rec["hall_discharge_state"]]:
        raise P1RecordError("%s: h1_electrical.anode_state %r not allowed with the discharge supply %s (allowed %s; "
                            "P1-IT-39, P1Q-13)" % (rid, h1e["anode_state"], rec["hall_discharge_state"],
                                                   ANODE_STATES_BY_HALL_STATE[rec["hall_discharge_state"]]))
    want_conn = SUPPLY_CONNECTION_BY_HALL_STATE[rec["hall_discharge_state"]]
    if h1e["discharge_supply_connection"] != want_conn:
        raise CapacityConfigurationError(
            "%s: h1_electrical.discharge_supply_connection %r with the discharge supply %s; required %s (A9.4 P1Q-13: "
            "never a commanded-zero supply left electrically attached)"
            % (rid, h1e["discharge_supply_connection"], rec["hall_discharge_state"], want_conn))
    # record class (A9.4 P1Q-10 / P1Q-13)
    rc = rec["record_class"]
    if rc not in RECORD_CLASSES:
        raise P1RecordError("%s: record_class %r not in %s" % (rid, rc, RECORD_CLASSES))
    if rc not in RECORD_CLASSES_BY_HALL_STATE[rec["hall_discharge_state"]]:
        raise CapacityConfigurationError(
            "%s: record_class %r not allowed with the discharge supply %s (allowed %s; Hall-ON records are %s and "
            "never %s, A9.4 P1Q-10)" % (rid, rc, rec["hall_discharge_state"],
                                         RECORD_CLASSES_BY_HALL_STATE[rec["hall_discharge_state"]], CONSISTENCY_LABEL,
                                         CAPACITY_LABEL))
    if rc == DIAGNOSTIC_LABEL:
        dreg = rec.get("diagnostic_registration_id")
        if not isinstance(dreg, str) or not dreg.strip():
            raise MissingInputError("%s: a DIAGNOSTIC_VARIANT record needs its separate registration id "
                                    "(diagnostic_registration_id; A9.4 P1Q-13)" % rid)
    if h1e["anode_state"] == "METERED_RETURN" and rc != DIAGNOSTIC_LABEL:
        raise CapacityConfigurationError(
            "%s: a METERED_RETURN anode is allowed only in a separately registered DIAGNOSTIC_VARIANT record, which "
            "never feeds I_e,cap (A9.4 P1Q-13); record_class is %r" % (rid, rc))
    # gas mode / dedicated feed (A9.1 HIQ-06, A9.3 OQ-RFQ-10)
    flows = rec["flows"]
    _req(flows, FLOWS_REQUIRED, rid + " flows")
    _num(flows["mdot_Ar_H1_mg_s"], rid + " flows.mdot_Ar_H1_mg_s", allow_negative=False)
    mded = _num(flows["mdot_icp_dedicated_mg_s"], rid + " flows.mdot_icp_dedicated_mg_s", allow_negative=False)
    if rec["gas_mode"] not in GAS_MODES:
        raise GasModeError("%s: gas_mode %r not in %s" % (rid, rec["gas_mode"], GAS_MODES))
    if rec["gas_mode"] == "G-REUSE" and mded != 0.0:
        raise GasModeError("%s: G-REUSE requires mdot_ICP,dedicated = 0 (A9.1 HIQ-06; A9.3 OQ-RFQ-10), got %r"
                           % (rid, mded))
    if rec["gas_mode"] == "DIAGNOSTIC_DEDICATED_FEED":
        if "DIAGNOSTIC_VARIABLE_NOT_BASELINE" not in rec["labels"]:
            raise LabelError("%s: a dedicated ICP feed is a diagnostic variable only and must be labelled "
                             "DIAGNOSTIC_VARIABLE_NOT_BASELINE (A9.3 OQ-RFQ-10)" % rid)
        if not flows.get("ledger_booking_id"):
            raise GasModeError("%s: an activated dedicated ICP feed must be booked in the corresponding atmospheric/Xe "
                               "ledger (flows.ledger_booking_id; A9.3 OQ-RFQ-10)" % rid)
    # RF chain (A9.2)
    rf = rec["rf"]
    _req(rf, RF_REQUIRED, rid + " rf")
    if rf["reference_plane"] != RF_REFERENCE_PLANE:
        raise P1RecordError("%s: forward/reflected power must be measured on the generator / 50-ohm side of the local "
                            "matching network (A9.2 OQ-A907-11); got %r" % (rid, rf["reference_plane"]))
    pf = _num(rf["P_fwd_W"], rid + " rf.P_fwd_W", allow_negative=False)
    pr = _num(rf["P_refl_W"], rid + " rf.P_refl_W", allow_negative=False)
    if pf == 0.0 and pr > 0.0:
        raise RFConsistencyError("%s: P_refl = %r W with P_fwd = 0 is not a physical reading of a passive load "
                                 "(RF OFF records carry P_refl = 0)" % (rid, pr))
    if pf > 0 and pr >= pf:
        raise RFConsistencyError("%s: P_refl >= P_fwd (%r >= %r) is not a physical reading of a passive load"
                                 % (rid, pr, pf))
    loss = rf["line_match_loss"]
    if not isinstance(loss, dict) or loss.get("status") not in LOSS_STATUSES:
        raise LineMatchLossError("%s: P_delivered needs the line/match loss term either MEASURED or explicitly "
                                 "FLAGGED_NOT_MEASURED (A9.2); got %r" % (rid, loss))
    if loss["status"] == "MEASURED":
        lw = _num(loss.get("value_W"), rid + " rf.line_match_loss.value_W", allow_negative=False)
        for k in LOSS_MEASURED_REQUIRED:
            if loss.get(k) in (None, ""):
                raise MissingInputError("%s: a MEASURED line/match loss needs '%s' (two-port characterization id, "
                                        "the match setting it was de-embedded at and its residual-|Gamma| "
                                        "validity limit; P1-M-03, P1-IT-41)" % (rid, k))
        if loss["match_setting_id"] != rf["match_setting_id"]:
            raise LineMatchLossError("%s: MEASURED line/match loss characterized at match setting %r but the record "
                                     "is at %r; re-characterize or flag the loss FLAGGED_NOT_MEASURED"
                                     % (rid, loss["match_setting_id"], rf["match_setting_id"]))
        gmax = _num(loss["valid_max_gamma_abs"], rid + " rf.line_match_loss.valid_max_gamma_abs",
                    allow_negative=False)
        if pf > 0.0 and math.sqrt(pr / pf) > gmax:
            raise LineMatchLossError("%s: residual |Gamma| = %.6g exceeds the validity limit %r of the MEASURED loss "
                                     "characterization; flag the loss FLAGGED_NOT_MEASURED"
                                     % (rid, math.sqrt(pr / pf), gmax))
        if pf > 0.0 and lw > pf - pr:
            raise RFConsistencyError("%s: MEASURED line/match loss %r W exceeds P_fwd - P_refl = %r W; P_delivered "
                                     "would be negative - loss characterization inconsistent with this reading"
                                     % (rid, lw, pf - pr))
    # generator (A9.3 OQ-RFQ-06: P1 uses the GROUND/FACILITY_ONLY mains generator only)
    gen = rec["generator"]
    _req(gen, GENERATOR_REQUIRED, rid + " generator")
    if gen["generator_class"] in REFUSED_GENERATOR_CLASSES:
        raise P1RecordError("%s: generator_class %r refused in P1: A9.3 OQ-RFQ-06 fixes P1 to the "
                            "GROUND/FACILITY_ONLY mains generator; a FLIGHT_REPRESENTATIVE_DC_RF_SOURCE belongs to a "
                            "later programme with its own record schema" % (rid, gen["generator_class"]))
    if gen["generator_class"] not in GENERATOR_CLASSES:
        raise P1RecordError("%s: generator_class %r not in %s" % (rid, gen["generator_class"], GENERATOR_CLASSES))
    _num(gen["P_generator_input_W"], rid + " generator.P_generator_input_W", allow_negative=False)
    if not isinstance(gen["input_boundary"], str) or "bus" in _normalise_key(gen["input_boundary"]):
        raise PMainsNotPBusError("%s: generator.input_boundary %r names a bus; the P1 generator input is P_mains,in "
                                 "(GROUND/FACILITY_ONLY, A9.3 OQ-RFQ-06), never P_bus" % (rid, gen["input_boundary"]))
    # collector (the ICP ion-collecting electrode; TK-13, ICD ICP-21)
    col = rec["collector"]
    _req(col, COLLECTOR_REQUIRED, rid + " collector")
    i_e = _num(col["I_e_A"], rid + " collector.I_e_A")
    if col["I_e_sign_convention"] != I_E_SIGN_CONVENTION:
        raise P1RecordError("%s: collector.I_e_sign_convention %r is not the declared convention %s"
                            % (rid, col["I_e_sign_convention"], I_E_SIGN_CONVENTION))
    res = _num(col["I_e_resolution_A"], rid + " collector.I_e_resolution_A", allow_negative=False)
    if res <= 0.0:
        raise MissingInputError("%s: collector.I_e_resolution_A must be > 0 (instrument resolution of the I_e "
                                "channel, from its certificate)" % rid)
    _num(col["V_collector_V"], rid + " collector.V_collector_V")
    if col["reference_potential"] not in REFERENCE_POTENTIALS:
        raise ExtractionTopologyError("%s: collector.reference_potential %r not in %s (the reference of V_collector "
                                      "is declared per record and registered at P1-G0)"
                                      % (rid, col["reference_potential"], REFERENCE_POTENTIALS))
    # electron-extraction topology (P1-IT-36)
    ext = rec["extraction"]
    _req(ext, EXTRACTION_REQUIRED, rid + " extraction")
    if not isinstance(ext["topology_id"], str) or not ext["topology_id"].strip():
        raise ExtractionTopologyError("%s: extraction.topology_id must be the id registered at P1-G0" % rid)
    electrode = ext["electron_collecting_electrode"]
    if electrode not in EXTRACTION_ELECTRODES:
        raise ExtractionTopologyError("%s: electron_collecting_electrode %r not in %s"
                                      % (rid, electrode, EXTRACTION_ELECTRODES))
    # pressures, impedance, temperatures, pickup
    _req(rec["pressures"], PRESSURE_FIELDS, rid + " pressures")
    for k in PRESSURE_FIELDS:
        _num(rec["pressures"][k], rid + " pressures." + k, allow_negative=False)
    imp = rec["impedance"]
    _req(imp, IMPEDANCE_REQUIRED, rid + " impedance")
    if imp["status"] == "MEASURED":
        _num(imp.get("R_ohm"), rid + " impedance.R_ohm")
        _num(imp.get("X_ohm"), rid + " impedance.X_ohm")
    elif imp["status"] != "NOT_MEASURED_PENDING_P2_CHAIN":
        raise P1RecordError("%s: impedance.status must be MEASURED or NOT_MEASURED_PENDING_P2_CHAIN" % rid)
    temps = rec["temperatures"]
    _req(temps, REQUIRED_TEMPERATURES, rid + " temperatures")
    for k in REQUIRED_TEMPERATURES:
        _num(temps[k], rid + " temperatures." + k)
    if rec["rf_pickup_check"] not in ("DONE", "NOT_DONE"):
        raise P1RecordError("%s: rf_pickup_check must be DONE or NOT_DONE" % rid)
    # extraction electrode vs Hall state: with the Hall discharge OFF the H-1 anode cannot be the electron sink
    # (a positively biased H-1 anode with Ar flowing is a Hall discharge); with it ON the electrons close through
    # the H-1 anode (ICD ICP-45; anchor TK-40)
    allowed = EXTRACTION_ELECTRODES_BY_HALL_STATE[rec["hall_discharge_state"]]
    if electrode not in allowed:
        raise ExtractionTopologyError("%s: electron_collecting_electrode %r is inconsistent with Hall discharge %s "
                                      "(allowed %s)" % (rid, electrode, rec["hall_discharge_state"], allowed))
    if "h1_point_id" in rec and (not isinstance(rec["h1_point_id"], str) or not rec["h1_point_id"].strip()):
        raise P1RecordError("%s: h1_point_id, when present, must be a non-empty registered H-1 point id" % rid)
    # terminals
    terms = rec["terminals"]
    need = REQUIRED_TERMINALS[(rec["hall_discharge_state"], electrode)]
    if not isinstance(terms, dict):
        raise MissingInputError("%s: terminals must be an object" % rid)
    for name in need:
        t = terms.get(name)
        if not isinstance(t, dict) or t.get("basis") not in TERMINAL_BASES:
            raise MissingInputError("%s: current-path terminal '%s' missing or without basis %s (Kirchhoff closure "
                                    "needs every terminal of the isolated network)" % (rid, name, TERMINAL_BASES))
    for name in sorted(terms):                  # every terminal, required or additional (A9.5: any other terminal)
        t = terms[name]
        if not isinstance(t, dict) or t.get("basis") not in TERMINAL_BASES:
            raise MissingInputError("%s: terminal '%s' without basis %s" % (rid, name, TERMINAL_BASES))
        if t["basis"] == "NOT_MEASURED":
            # an unavailable channel is declared, never silently set to zero (A9.5 P1Q-15)
            if t.get("I_A") is not None:
                raise P1RecordError("%s: terminal '%s' declared NOT_MEASURED but carries I_A = %r; an unavailable "
                                    "channel carries no value (never a silent zero, A9.5 P1Q-15)" % (rid, name, t["I_A"]))
            continue
        _num(t.get("I_A"), "%s terminals.%s.I_A" % (rid, name))
        if t["basis"] == "OPEN_CIRCUIT_BY_CONSTRUCTION" and float(t["I_A"]) != 0.0:
            raise P1RecordError("%s: terminal '%s' declared open circuit but carries %r A" % (rid, name, t["I_A"]))
    if terms["collector_supply"]["basis"] != "MEASURED":
        raise MissingInputError("%s: terminal 'collector_supply' must be MEASURED (it carries I_e, P1-IT-42)" % rid)
    # the H-1 anode terminal basis follows the registered anode state
    want = ANODE_TERMINAL_BASIS[h1e["anode_state"]]
    if terms["hall_anode"]["basis"] != want:
        raise P1RecordError("%s: terminal 'hall_anode' basis %r inconsistent with anode_state %r (expected %s)"
                            % (rid, terms["hall_anode"]["basis"], h1e["anode_state"], want))
    # I_e and the collector_supply terminal are the same current (I_E_SIGN_CONVENTION): cross-check
    cs = float(terms["collector_supply"]["I_A"])
    if abs(cs - i_e) > res:
        raise P1RecordError("%s: collector.I_e_A = %r A and terminals.collector_supply.I_A = %r A differ by more "
                            "than the channel resolution %r A (same current under %s)"
                            % (rid, i_e, cs, res, I_E_SIGN_CONVENTION))
    if rc == CAPACITY_LABEL:
        _check_capacity_record(rec, rid)
    return None


def _check_capacity_record(rec, rid):
    """A9.4 P1Q-10 / P1Q-13 configuration of an ICP45_CAPACITY record; raises (refuses) on any violation."""
    if rec["stage_id"] not in ICP45A_CAPACITY_STAGES:
        raise CapacityConfigurationError("%s: ICP45_CAPACITY records belong to the capacity stages %s, not %r"
                                         % (rid, ICP45A_CAPACITY_STAGES, rec["stage_id"]))
    h1e = rec["h1_electrical"]
    if h1e["anode_state"] != "DISCONNECTED_FLOATING":
        raise CapacityConfigurationError("%s: capacity record with anode_state %r refused: the H-1 anode is physically "
                                         "disconnected from the discharge supply and left floating "
                                         "(OPEN_CIRCUIT_BY_CONSTRUCTION) during ICP-45 capacity measurements (A9.4 "
                                         "P1Q-13)" % (rid, h1e["anode_state"]))
    if rec["terminals"]["hall_anode"]["basis"] != "OPEN_CIRCUIT_BY_CONSTRUCTION":
        raise CapacityConfigurationError("%s: capacity record: terminal hall_anode must be OPEN_CIRCUIT_BY_CONSTRUCTION"
                                         % rid)
    if rec["extraction"]["electron_collecting_electrode"] != "DEDICATED_ELECTRON_COLLECTOR_TARGET":
        raise CapacityConfigurationError("%s: capacity record: electrons must be extracted to the dedicated, isolated, "
                                         "instrumented electron-collecting electrode (A9.4 P1Q-10); got %r"
                                         % (rid, rec["extraction"]["electron_collecting_electrode"]))
    cm = rec.get("capacity_monitoring")
    if not isinstance(cm, dict):
        raise CapacityConfigurationError("%s: capacity record without capacity_monitoring (A9.4 P1Q-13: continuous "
                                         "I_body->ground, V_anode on a high-impedance isolated channel, ICP body and "
                                         "collector potentials)" % rid)
    for k in CAPACITY_MONITORING_REQUIRED:
        if k not in cm or cm[k] is None:
            raise CapacityConfigurationError("%s: capacity_monitoring.%s missing (A9.4 P1Q-13); record refused"
                                             % (rid, k))
    if cm["h1_body_ground_config"] != H1_BODY_GROUND_CONFIG:
        raise CapacityConfigurationError("%s: H-1 body / magnetic circuit must have exactly one deliberate facility-"
                                         "ground connection through a metered return (%s); got %r"
                                         % (rid, H1_BODY_GROUND_CONFIG, cm["h1_body_ground_config"]))
    if cm["I_body_to_ground_continuous"] is not True:
        raise CapacityConfigurationError("%s: I_body->ground must be measured continuously during capacity records "
                                         "(A9.4 P1Q-13)" % rid)
    if cm["V_anode_channel"] != V_ANODE_CHANNEL:
        raise CapacityConfigurationError("%s: V_anode must be recorded on a %s channel (A9.4 P1Q-13); got %r"
                                         % (rid, V_ANODE_CHANNEL, cm["V_anode_channel"]))
    _num(cm["V_icp_body_V"], rid + " capacity_monitoring.V_icp_body_V")
    _num(cm["V_electron_collector_V"], rid + " capacity_monitoring.V_electron_collector_V")
    if not isinstance(cm["sign_convention_id"], str) or not cm["sign_convention_id"].strip():
        raise CapacityConfigurationError("%s: capacity_monitoring.sign_convention_id must name the registered "
                                         "Kirchhoff sign convention" % rid)
    if not isinstance(cm["unintended_ground_path_found"], bool):
        raise CapacityConfigurationError("%s: capacity_monitoring.unintended_ground_path_found must be recorded true "
                                         "or false (A9.5 P1Q-15 exclusion; A9.4 P1Q-13 single-point ground)" % rid)
    if not isinstance(cm["ground_path_check_id"], str) or not cm["ground_path_check_id"].strip():
        raise CapacityConfigurationError("%s: capacity_monitoring.ground_path_check_id must name the recorded "
                                         "unintended-ground-path check" % rid)
    terms = rec["terminals"]
    for name in CAPACITY_EXTRA_TERMINALS + ("electron_collector",):
        t = terms.get(name)
        if not isinstance(t, dict) or t.get("basis") != "MEASURED":
            raise CapacityConfigurationError("%s: capacity record needs terminal %r with basis MEASURED (A9.4 P1Q-13: "
                                             "I_body->ground measured continuously; dedicated collector current is "
                                             "the capacity measurand)" % (rid, name))
        _num(t.get("I_A"), "%s terminals.%s.I_A" % (rid, name))


# ------------------------------------------------------------------------------------------------ derived quantities
def derive_rf(rec):
    """|Gamma|, VSWR and P_RF,delivered at the A9.2 reference plane. Arithmetic only."""
    rf = rec["rf"]
    pf, pr = float(rf["P_fwd_W"]), float(rf["P_refl_W"])
    loss = rf["line_match_loss"]
    if not isinstance(loss, dict) or loss.get("status") not in LOSS_STATUSES:
        raise LineMatchLossError("record %r: line/match loss neither MEASURED nor FLAGGED_NOT_MEASURED"
                                 % rec.get("record_id"))
    if pf == 0.0:
        if pr != 0.0:
            raise RFConsistencyError("record %r: P_refl > 0 with P_fwd = 0" % rec.get("record_id"))
        return {"rf_state": "RF_OFF", "P_fwd_W": pf, "P_refl_W": pr, "gamma_abs": None, "VSWR": None,
                "P_delivered_W": None, "P_delivered_kind": "RF_OFF_NOT_DEFINED", "reference_plane": RF_REFERENCE_PLANE,
                "note": "RF OFF: P_delivered, |Gamma|, VSWR and C_e are undefined"}
    gamma = math.sqrt(pr / pf)
    vswr = (1.0 + gamma) / (1.0 - gamma)
    if loss["status"] == "MEASURED":
        lw = float(loss["value_W"])
        if lw > pf - pr:
            raise RFConsistencyError("record %r: MEASURED line/match loss exceeds P_fwd - P_refl" % rec.get("record_id"))
        p_del = pf - pr - lw
        kind = "P_RF_DELIVERED"
    else:
        p_del = pf - pr
        kind = "P_RF_DELIVERED_UPPER_BOUND_LOSS_NOT_MEASURED"
    return {"rf_state": "RF_ON", "P_fwd_W": pf, "P_refl_W": pr, "gamma_abs": gamma, "VSWR": vswr,
            "P_delivered_W": p_del, "P_delivered_kind": kind, "reference_plane": RF_REFERENCE_PLANE,
            "note": "P_fwd is never P_plasma (A9.2)"}


def electron_cost(rec, rf_derived):
    """C_e and C_e,DC with boundary labels (A9.3 OQ-RFQ-06). Undefined (None + reason) for I_e <= 0."""
    i_e = float(rec["collector"]["I_e_A"])
    gen = rec["generator"]
    out = {"I_e_A": i_e}
    reason = None
    if rf_derived["rf_state"] == "RF_OFF":
        reason = "RF OFF: electron cost undefined (any collected current is not RF-produced; see P1-D-07)"
    elif i_e <= 0.0:
        reason = "I_e <= 0: electron cost undefined"
    if reason is not None:
        out.update({"C_e_W_per_A": None, "C_e_kind": None, "C_e_boundary": None, "C_e_reason": reason,
                    "C_e_DC_W_per_A": None, "C_e_DC_boundary": None, "C_e_DC_reason": reason})
        return out
    if rf_derived["P_delivered_kind"] == "P_RF_DELIVERED":
        out.update({"C_e_W_per_A": rf_derived["P_delivered_W"] / i_e, "C_e_kind": "C_e",
                    "C_e_boundary": BOUNDARY_C_E, "C_e_reason": None})
    else:
        out.update({"C_e_W_per_A": rf_derived["P_delivered_W"] / i_e, "C_e_kind": "C_e_UPPER_BOUND",
                    "C_e_boundary": BOUNDARY_C_E_UPPER, "C_e_reason": "line/match loss flagged, not measured"})
    out.update({"C_e_DC_W_per_A": float(gen["P_generator_input_W"]) / i_e,
                "C_e_DC_boundary": BOUNDARY_C_E_DC[gen["generator_class"]],
                "C_e_DC_input_boundary_as_recorded": gen["input_boundary"], "C_e_DC_reason": None})
    return out


def current_closure(rec):
    """DESCRIPTIVE Kirchhoff sum of the isolated electrical network (P1-D-06, every record): sum of signed terminal
    currents (positive = conventional current INTO the network) and that sum normalised by the largest terminal
    magnitude. Never an admission test: ICP45_CAPACITY points are admitted only by kirchhoff_closure (A9.5 P1Q-15).
    A NOT_MEASURED terminal is never summed as zero (sum None, state NOT_EVALUABLE_UNMEASURED_CHANNEL); an all-zero
    set of terminal currents is reported as such, never as 'closed'."""
    terms = rec["terminals"]
    names = sorted(terms)
    unmeasured = [n for n in names if terms[n]["basis"] == "NOT_MEASURED"]
    note = ("descriptive residual (P1-D-06); ICP45_CAPACITY admission uses the owner rule A9.5 P1Q-15 "
            "(kirchhoff_closure: |R_I| <= 3 u_R and |R_I| / max(I_e,collector, I_scale,min) <= 0.02)")
    if unmeasured:
        return {"terminals": names, "sum_A": None, "scale_A": None, "residual_rel": None,
                "unmeasured_terminals": unmeasured, "closure_state": "NOT_EVALUABLE_UNMEASURED_CHANNEL", "note": note}
    vals = np.array([float(terms[n]["I_A"]) for n in names], dtype=float)
    total = float(vals.sum())
    scale = float(np.max(np.abs(vals))) if vals.size else 0.0
    return {"terminals": names, "sum_A": total, "scale_A": scale,
            "residual_rel": (total / scale) if scale > 0 else None, "unmeasured_terminals": [],
            "closure_state": "COMPUTED" if scale > 0 else "ALL_TERMINAL_CURRENTS_ZERO_NOT_A_CLOSURE_RESULT",
            "note": note}


# ------------------------------------------------------------------------------------------------ A9.5 P1Q-15
def _check_closure_rule(closure_rule):
    """Registered inputs of the owner Kirchhoff rule (A9.5 P1Q-15): rule_id, the owner's sign convention and its
    registration id, I_scale,min (instrument-capability denominator floor, > 0, with its basis; no default) and an
    optional registered channel correlation (covariance form). The factor 3 and the 2 % are owner constants and are
    never accepted from a caller (any other key is refused). Returns a normalised copy or raises."""
    if not isinstance(closure_rule, dict):
        raise MissingInputError("closure_rule: expected an object, got %r" % type(closure_rule).__name__)
    extra = sorted(set(closure_rule) - set(CLOSURE_RULE_ALLOWED))
    if extra:
        raise ClosureRuleError("closure_rule keys %s refused: the statistical factor %g and the fractional limit %g are "
                               "owner constants (%s) and are never set or widened by a caller; the registered inputs "
                               "are %s" % (extra, CLOSURE_K_SIGMA, CLOSURE_FRACTION_MAX, A95_REF,
                                           list(CLOSURE_RULE_ALLOWED)))
    _req(closure_rule, CLOSURE_RULE_REQUIRED, "closure_rule")
    if closure_rule["sign_convention"] != KIRCHHOFF_SIGN_CONVENTION:
        raise ClosureRuleError("closure_rule.sign_convention %r is not the owner's global convention %s (%s)"
                               % (closure_rule["sign_convention"], KIRCHHOFF_SIGN_CONVENTION, A95_REF))
    for k in ("rule_id", "sign_convention_id", "I_scale_min_basis"):
        if not isinstance(closure_rule[k], str) or not closure_rule[k].strip():
            raise MissingInputError("closure_rule.%s must be a non-empty registered string" % k)
    floor = _num(closure_rule["I_scale_min_A"], "closure_rule.I_scale_min_A", allow_negative=False)
    if floor <= 0.0:
        raise MissingInputError("closure_rule.I_scale_min_A must be > 0 (registered instrument-capability floor)")
    out = dict(closure_rule)
    out["I_scale_min_A"] = floor
    cov = closure_rule.get("covariance")
    if cov is not None:
        _req(cov, COVARIANCE_REQUIRED, "closure_rule.covariance")
        names = cov["terminals"]
        if (not isinstance(names, list) or not names or len(set(names)) != len(names)
                or not all(isinstance(n, str) and n.strip() for n in names)):
            raise ClosureRuleError("closure_rule.covariance.terminals must be a non-empty list of distinct terminal "
                                   "names")
        rho = cov["correlation"]
        if not isinstance(rho, list) or len(rho) != len(names) or not all(
                isinstance(r, list) and len(r) == len(names) for r in rho):
            raise ClosureRuleError("closure_rule.covariance.correlation must be a %dx%d matrix" % (len(names),
                                                                                                   len(names)))
        m = np.array([[_num(x, "closure_rule.covariance.correlation") for x in r] for r in rho], dtype=float)
        if not np.allclose(m, m.T, rtol=0.0, atol=1e-12) or not np.allclose(np.diag(m), 1.0, rtol=0.0, atol=1e-12) \
                or np.any(np.abs(m) > 1.0 + 1e-12):
            raise ClosureRuleError("closure_rule.covariance.correlation must be symmetric with unit diagonal and "
                                   "|r_ij| <= 1")
        if float(np.min(np.linalg.eigvalsh(m))) < -1e-10:
            raise ClosureRuleError("closure_rule.covariance.correlation is not positive semi-definite")
        if not isinstance(cov["covariance_id"], str) or not cov["covariance_id"].strip():
            raise MissingInputError("closure_rule.covariance.covariance_id must be the registered id")
        out["covariance"] = {"covariance_id": cov["covariance_id"], "terminals": list(names),
                             "correlation": m.tolist()}
    return out


def _channel_uncertainty(t, name):
    """u(I_k) of one MEASURED channel: root-sum-square of its registered components (A9.5 P1Q-15). Returns
    (u_A, components, None) or (None, None, reason) - a missing component never defaults to zero."""
    u = t.get("uncertainty")
    if not isinstance(u, dict):
        return None, None, ("u(I_k) unavailable for terminal %r (no uncertainty object with %s): the point cannot be "
                            "evaluated (A9.5 P1Q-15 / P1Q-16 condition 3)" % (name, list(U_COMPONENTS)))
    parts, comps = [], {}
    for c in U_COMPONENTS:
        v = u.get(c)
        if isinstance(v, str) and U_EXPLICIT_ABSENT.get(c) == v:
            comps[c] = v
            continue
        if v is None or isinstance(v, (bool, str)) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) \
                or v < 0:
            return None, None, ("u(I_k) unavailable for terminal %r: component %s is %r (required: a non-negative "
                                "number%s); the point cannot be evaluated (A9.5 P1Q-15 / P1Q-16 condition 3)"
                                % (name, c, v, (" or the explicit token %r" % U_EXPLICIT_ABSENT[c])
                                   if c in U_EXPLICIT_ABSENT else ""))
        comps[c] = float(v)
        parts.append(float(v))
    if comps["u_resolution_A"] <= 0.0:
        return None, None, ("u(I_k) unavailable for terminal %r: u_resolution_A must be > 0 (channel resolution from "
                            "its certificate)" % name)
    return math.sqrt(sum(p * p for p in parts)), comps, None


def kirchhoff_closure(rec, closure_rule):
    """Owner Kirchhoff current-closure rule for one ICP45_CAPACITY record (A9.5 P1Q-15).

    R_I = sum_k I_k over every terminal crossing the registered network boundary (signed, conventional current INTO
    the network positive; OPEN_CIRCUIT_BY_CONSTRUCTION terminals contribute I = 0 and u = 0 by construction, e.g. the
    floating H-1 anode, whose potential is still recorded). u_R = sqrt(sum_k u^2(I_k)) for independent channels, or
    sqrt(sum_ij r_ij u(I_i) u(I_j)) with a registered correlation (full covariance form). closure_valid only if
    |R_I| <= 3 u_R AND |R_I| / max(I_e,collector, I_scale,min) <= 0.02. instrument_adequate = 3 u_R <= 0.02
    I_e,collector (applied by icp45a_candidates at the RF-ON candidate point). Structural reasons (sign conventions
    differ, a NOT_MEASURED intentional return path, missing u(I_k), unintended ground path) make the record
    non-evaluable; no residual is then formed. Pure arithmetic on recorded values; never widens a tolerance."""
    rule = _check_closure_rule(closure_rule)
    rid = rec.get("record_id")
    terms = rec["terminals"]
    cm = rec.get("capacity_monitoring") or {}
    reasons = []
    u_ok = True
    if cm.get("sign_convention_id") != rule["sign_convention_id"]:
        reasons.append("sign convention %r differs from the closure rule's registered convention %r (rule %r): "
                       "residuals not comparable, capacity point invalid (A9.5 P1Q-15: current sign conventions "
                       "differ)" % (cm.get("sign_convention_id"), rule["sign_convention_id"], rule["rule_id"]))
    if cm.get("unintended_ground_path_found") is not False:
        reasons.append("unintended ground path found or its check not recorded (capacity_monitoring."
                       "unintended_ground_path_found = %r, check %r; A9.5 P1Q-15 exclusion)"
                       % (cm.get("unintended_ground_path_found"), cm.get("ground_path_check_id")))
    channels = {}
    for name in sorted(terms):
        t = terms[name]
        basis = t["basis"]
        if basis == "OPEN_CIRCUIT_BY_CONSTRUCTION":
            channels[name] = {"basis": basis, "I_A": 0.0, "u_A": 0.0, "u_basis": "ZERO_BY_CONSTRUCTION"}
        elif basis == "NOT_MEASURED":
            channels[name] = {"basis": basis, "I_A": None, "u_A": None}
            reasons.append("intentional return path unmeasured: terminal %r declared NOT_MEASURED; an unavailable "
                           "channel is never set to zero (A9.5 P1Q-15)" % name)
        else:
            sc = t.get("sign_convention_id")
            if not isinstance(sc, str) or not sc.strip():
                reasons.append("terminal %r declares no sign_convention_id: the channel is not shown transformed "
                               "into the registered convention; the point cannot be evaluated" % name)
            elif sc != rule["sign_convention_id"]:
                reasons.append("current sign conventions differ between channels: terminal %r in %r, registered %r "
                               "(A9.5 P1Q-15)" % (name, sc, rule["sign_convention_id"]))
            u, comps, why = _channel_uncertainty(t, name)
            if why:
                reasons.append(why)
                u_ok = False
            channels[name] = {"basis": basis, "I_A": float(t["I_A"]), "u_A": u, "u_components": comps,
                              "sign_convention_id": sc}
    ec = terms.get("electron_collector")
    if not isinstance(ec, dict) or ec.get("basis") != "MEASURED":
        reasons.append("dedicated electron-collector terminal not MEASURED: I_e,collector unavailable")
    out = {"record_id": rid, "rule_id": rule["rule_id"], "sign_convention": KIRCHHOFF_SIGN_CONVENTION,
           "sign_convention_id": rule["sign_convention_id"], "k_sigma": CLOSURE_K_SIGMA,
           "fraction_max": CLOSURE_FRACTION_MAX, "owner_source": A95_REF, "I_scale_min_A": rule["I_scale_min_A"],
           "channels": channels, "uncertainties_available": u_ok,
           "V_anode_V": float(rec["h1_electrical"]["V_anode_V"])}
    if not reasons:
        meas = [n for n in sorted(channels) if channels[n]["basis"] == "MEASURED"]
        cov = rule.get("covariance")
        if cov is None:
            u_r = math.sqrt(sum(channels[n]["u_A"] ** 2 for n in meas))
            method = "INDEPENDENT_CHANNELS: u_R = sqrt(sum_k u^2(I_k))"
        else:
            idx = {n: i for i, n in enumerate(cov["terminals"])}
            missing = [n for n in meas if n not in idx]
            if missing:
                reasons.append("registered covariance %r does not cover measured terminal(s) %s: u_R cannot be "
                               "evaluated" % (cov["covariance_id"], missing))
                u_ok = False
                out["uncertainties_available"] = False
            else:
                corr = np.array(cov["correlation"], dtype=float)
                s = float(sum(corr[idx[a], idx[b]] * channels[a]["u_A"] * channels[b]["u_A"]
                              for a in meas for b in meas))
                if not s > 0.0:
                    reasons.append("combined covariance-form variance %r is not positive" % s)
                u_r = math.sqrt(s) if s > 0.0 else None
                method = ("FULL_COVARIANCE (registered %s): u_R^2 = sum_ij r_ij u(I_i) u(I_j)"
                          % cov["covariance_id"])
    if reasons:
        out.update({"evaluable": False, "R_I_A": None, "u_R_A": None, "I_e_collector_A": None,
                    "statistical_ok": None, "fractional_ok": None, "closure_valid": False,
                    "instrument_adequate": None, "reasons": reasons})
        return out
    r_i = sum(channels[n]["I_A"] for n in sorted(channels))
    i_col = -channels["electron_collector"]["I_A"]
    denom = max(i_col, rule["I_scale_min_A"])
    frac = abs(r_i) / denom
    stat_ok = abs(r_i) <= CLOSURE_K_SIGMA * u_r
    frac_ok = frac <= CLOSURE_FRACTION_MAX
    fails = []
    if not stat_ok:
        fails.append("statistical closure fails: |R_I| = %.6g A > %g u_R = %.6g A (A9.5 P1Q-15)"
                     % (abs(r_i), CLOSURE_K_SIGMA, CLOSURE_K_SIGMA * u_r))
    if not frac_ok:
        fails.append("fractional closure exceeds 2 %%: |R_I| / max(I_e,collector, I_scale,min) = %.6g > %g "
                     "(A9.5 P1Q-15)" % (frac, CLOSURE_FRACTION_MAX))
    out.update({"evaluable": True, "R_I_A": r_i, "u_R_A": u_r, "u_R_method": method, "I_e_collector_A": i_col,
                "denominator_A": denom, "fraction": frac, "statistical_ok": stat_ok, "fractional_ok": frac_ok,
                "closure_valid": stat_ok and frac_ok,
                "instrument_adequate": CLOSURE_K_SIGMA * u_r <= CLOSURE_FRACTION_MAX * i_col,
                "reasons": fails})
    return out


def i_e_cap_signed(i_e_collector_rf_on_A, i_e_collector_rf_off_A):
    """I_e,cap = I_e,collector,RFON - I_e,collector,RFOFF (A9.4 P1Q-10; confirmed A9.5 P1Q-16): signed currents under
    the same registered convention; no absolute-value correction and no zero-clipping (a negative result stays
    negative)."""
    return i_e_collector_rf_on_A - i_e_collector_rf_off_A


FACILITY_MATCH_REQUIRED = ("criteria_id", "p_chamber_rel_tol")


def facility_electron_check(rf_on, rf_off, match=None):
    """Facility-electron contribution (P1-D-07): collector current with the ICP RF OFF at the same point divided by
    the current with RF ON. 'Same point' = identical V_collector and its reference, mdot_Ar,H1, mdot_ICP,dedicated,
    gas_mode, record_class, Hall discharge state, stage and extraction topology, and p_chamber within the caller-supplied relative
    tolerance (match['p_chamber_rel_tol']; TBD - frozen at P1-G0, P1-IT-37; no default). Descriptive; no threshold."""
    for r in (rf_on, rf_off):
        validate_operating_point(r)
    if match is None:
        raise MissingInputError("facility-electron check: the pressure-match rule (criteria_id, p_chamber_rel_tol) "
                                "is required - TBD, frozen at P1-G0 (P1-IT-37); no default")
    _req(match, FACILITY_MATCH_REQUIRED, "facility match rule")
    tol = _num(match["p_chamber_rel_tol"], "facility match rule p_chamber_rel_tol", allow_negative=False)
    if float(rf_on["rf"]["P_fwd_W"]) <= 0.0:
        raise P1RecordError("facility-electron check: the RF-ON record has P_fwd = %r W" % rf_on["rf"]["P_fwd_W"])
    if float(rf_off["rf"]["P_fwd_W"]) != 0.0:
        raise P1RecordError("facility-electron check: the RF-OFF record has P_fwd = %r W" % rf_off["rf"]["P_fwd_W"])
    for path in (("collector", "V_collector_V"), ("collector", "reference_potential"),
                 ("flows", "mdot_Ar_H1_mg_s"), ("flows", "mdot_icp_dedicated_mg_s"),
                 ("extraction", "topology_id"), ("extraction", "electron_collecting_electrode"),
                 ("gas_mode",), ("record_class",), ("hall_discharge_state",), ("stage_id",), ("h1_point_id",),
                 ("h1_electrical", "config_id"), ("h1_electrical", "anode_state")):
        a, b = rf_on, rf_off
        for k in path:
            a = a.get(k) if isinstance(a, dict) else None
            b = b.get(k) if isinstance(b, dict) else None
        if a != b:
            raise P1RecordError("facility-electron check: %s differs between records (%r vs %r)"
                                % (".".join(path), a, b))
    p_on, p_off = float(rf_on["pressures"]["p_chamber_Pa"]), float(rf_off["pressures"]["p_chamber_Pa"])
    p_ref = max(abs(p_on), abs(p_off))
    p_dev = abs(p_on - p_off) / p_ref if p_ref > 0 else 0.0
    if p_dev > tol:
        raise P1RecordError("facility-electron check: p_chamber differs by %.6g (relative) > tolerance %r of rule %r "
                            "(%r vs %r Pa)" % (p_dev, tol, match["criteria_id"], p_on, p_off))
    i_on, i_off = float(rf_on["collector"]["I_e_A"]), float(rf_off["collector"]["I_e_A"])
    out = {"I_e_rf_on_A": i_on, "I_e_rf_off_A": i_off,
           "I_e_icp_corrected_A": i_on - i_off,
           "facility_fraction": (i_off / i_on) if i_on != 0 else None,
           "p_chamber_rel_dev": p_dev, "match_rule_id": match["criteria_id"],
           "records": [rf_on["record_id"], rf_off["record_id"]]}
    # A9.4 P1Q-10 capacity measurand: the dedicated electron-collector terminal current (electrons collected = -I_A
    # under the registered sign convention), RF ON minus the matched RF OFF record, SIGNED (A9.5 P1Q-16: no
    # absolute-value correction, no zero-clipping). Only MEASURED channels form it (never a NOT_MEASURED channel as 0).
    ec_on, ec_off = rf_on["terminals"].get("electron_collector"), rf_off["terminals"].get("electron_collector")
    if isinstance(ec_on, dict) and isinstance(ec_off, dict) and ec_on.get("basis") == "MEASURED" \
            and ec_off.get("basis") == "MEASURED":
        c_on, c_off = -float(ec_on["I_A"]), -float(ec_off["I_A"])
        out.update({"I_e_collector_rf_on_A": c_on, "I_e_collector_rf_off_A": c_off,
                    "I_e_collector_corrected_A": i_e_cap_signed(c_on, c_off)})
    return out


def dwell_metrics(dwell):
    """Stability metrics over one dwell: {t_s, I_e_A, P_refl_W, (optional) R_ohm, X_ohm}. Arithmetic only."""
    _req(dwell, ("t_s", "I_e_A", "P_refl_W"), "dwell")
    t = np.asarray(dwell["t_s"], dtype=float)
    if t.size < 3 or not np.all(np.diff(t) > 0):
        raise MissingInputError("dwell: need >= 3 strictly increasing time samples")
    out = {"duration_s": float(t[-1] - t[0]), "n": int(t.size)}
    for key in ("I_e_A", "P_refl_W", "R_ohm", "X_ohm"):
        if key not in dwell or dwell[key] is None:
            out[key] = None
            continue
        y = np.asarray(dwell[key], dtype=float)
        if y.shape != t.shape or not np.all(np.isfinite(y)):
            raise MissingInputError("dwell: series %s has a wrong length or non-finite values" % key)
        mean = float(y.mean())
        slope = float(np.polyfit(t, y, 1)[0])
        steps = np.abs(np.diff(y))
        std = float(y.std(ddof=1))
        out[key] = {"mean": mean, "std": std, "drift_total": slope * float(t[-1] - t[0]),
                    "drift_rel": (slope * float(t[-1] - t[0]) / abs(mean)) if mean != 0 else None,
                    "max_step": float(steps.max()), "max_step_over_std": (float(steps.max()) / std) if std > 0 else None}
    return out


def classify_stable_region(metrics, criteria=None, ignition=None):
    """Apply OWNER-SUPPLIED stable-region criteria. Without criteria: NOT_EVALUATED (values are TBD / PROPOSED)."""
    if criteria is None:
        return {"verdict": "NOT_EVALUATED", "reason": "stable-region criteria not frozen (owner question P1Q-01)"}
    _req(criteria, ("criteria_id", "max_abs_drift_rel_I_e", "max_abs_drift_rel_P_refl", "max_step_over_std",
                    "min_duration_s", "min_ignition_success_fraction"), "criteria")
    if ignition is None:
        raise MissingInputError("stable region: ignition repeatability record required with criteria")
    _req(ignition, ("attempts", "successes"), "ignition")
    fails = []
    if metrics["duration_s"] < float(criteria["min_duration_s"]):
        fails.append("duration")
    for key, lim in (("I_e_A", "max_abs_drift_rel_I_e"), ("P_refl_W", "max_abs_drift_rel_P_refl")):
        m = metrics.get(key)
        if m is None or m["drift_rel"] is None or abs(m["drift_rel"]) > float(criteria[lim]):
            fails.append("drift " + key)
        if m is not None and m["max_step_over_std"] is not None and m["max_step_over_std"] > float(
                criteria["max_step_over_std"]):
            fails.append("mode-jump " + key)
    frac = ignition["successes"] / ignition["attempts"] if ignition["attempts"] else 0.0
    if frac < float(criteria["min_ignition_success_fraction"]):
        fails.append("ignition repeatability")
    return {"verdict": "WITHIN_OWNER_CRITERIA" if not fails else "OUTSIDE_OWNER_CRITERIA",
            "criteria_id": criteria["criteria_id"], "failed": fails, "ignition_success_fraction": frac,
            "note": "engineering handoff classification for P2 only; not an architecture gate"}


REGISTRATION_REQUIRED = ("registration_id", "I_d_max_H1_A", "basis", "source", "registered_point_ids")
MARGIN_RULE_REQUIRED = ("rule_id", "k_one_sided", "u_I_e_A", "u_I_d_max_A")


def _check_registration(registration, margin_rule):
    _req(registration, REGISTRATION_REQUIRED, "registration")
    if registration["basis"] != REGISTRATION_BASIS:
        raise RegistrationError("I_d,max,H1 basis %r refused: only %s (the 8.33 A stand ceiling and the 7.5 A "
                                "power-envelope bound are not the ICP-45 requirement, A9.3 OQ-A907-02)"
                                % (registration["basis"], REGISTRATION_BASIS))
    pts = registration["registered_point_ids"]
    if not isinstance(pts, list) or not pts or not all(isinstance(x, str) and x.strip() for x in pts):
        raise RegistrationError("registration.registered_point_ids must be a non-empty list of registered H-1 "
                                "point ids")
    if margin_rule is None:
        raise RegistrationError("ICP-45A needs the preregistered one-sided margin rule (k_one_sided, u_I_e_A, "
                                "rule_id); none supplied")
    _req(margin_rule, MARGIN_RULE_REQUIRED, "margin_rule")
    idm = _num(registration["I_d_max_H1_A"], "registration.I_d_max_H1_A", allow_negative=False)
    if idm <= 0:
        raise RegistrationError("I_d,max,H1 must be > 0")
    k = _num(margin_rule["k_one_sided"], "margin_rule.k_one_sided", allow_negative=False)
    ue = _num(margin_rule["u_I_e_A"], "margin_rule.u_I_e_A", allow_negative=False)
    ud = _num(margin_rule["u_I_d_max_A"], "margin_rule.u_I_d_max_A", allow_negative=False)
    return idm, k, ue, ud


def icp45a_margin(i_e_cap_A, idm, k, ue, ud):
    """Pure arithmetic of the owner M_n form (A9.1 UBQ-02 / UBQ-07): M_n = I_e,cap / I_d,max,H1 - 1 and its
    one-sided lower bound. It carries no status: only icp45a_evaluate decides whether the inputs are admissible."""
    m_n = i_e_cap_A / idm - 1.0
    u_m = math.sqrt((ue / idm) ** 2 + (i_e_cap_A * ud / idm ** 2) ** 2)
    return {"M_n": m_n, "u_M_n": u_m, "M_n_lower": m_n - k * u_m}


def _point_eligibility(fc_ok, ev_on, ev_off, closure_ok):
    return {"1_capacity_point_passes_current_closure": bool(closure_ok),
            "2_matched_rf_off_correction_valid": bool(fc_ok),
            "3_required_channel_uncertainties_available": bool(ev_on is not None and ev_off is not None
                                                               and ev_on["uncertainties_available"]
                                                               and ev_off["uncertainties_available"]),
            "4_I_d_max_H1_registered": True}


def icp45a_candidates(records, registration, facility_checks, closure_rule=None):
    """Split validated operating-point records into I_e,cap CAPACITY candidates, NOT_EVALUATED_INSTRUMENT points and
    exclusions (I_E_CAP_DEFINITION; A9.5 P1Q-15 / P1Q-16). facility_checks: {rf_on_record_id:
    facility_electron_check(...) result}. closure_rule: the registered inputs of the owner Kirchhoff rule
    {rule_id, sign_convention, sign_convention_id, I_scale_min_A, I_scale_min_basis (, covariance)}; when None no
    capacity point can be closure-validated and it is excluded. Every excluded point keeps its reasons (and, where
    formed, its closure record). Returns (candidates, excluded, not_evaluated_instrument)."""
    pts = set(registration["registered_point_ids"])
    by_id = {r["record_id"]: r for r in records}
    rule = _check_closure_rule(closure_rule) if closure_rule is not None else None
    cands, excluded, instrument = [], [], []
    for rec in records:
        why = []
        if rec["record_class"] != CAPACITY_LABEL:
            why.append("record_class %r is not %s (Hall-ON records are %s; diagnostic variants never feed I_e,cap)"
                       % (rec["record_class"], CAPACITY_LABEL, CONSISTENCY_LABEL))
        if rec["stage_id"] not in ICP45A_CAPACITY_STAGES:
            why.append("stage %r is not a capacity stage %s" % (rec["stage_id"], ICP45A_CAPACITY_STAGES))
        if rec["hall_discharge_state"] != "OFF":
            why.append("Hall discharge supply ON: H-1 anode sink, current continuity bounds the ICP current by I_d; "
                       "NEUTRALIZATION_CONSISTENCY record, not a capacity record")
        h1e = rec["h1_electrical"]
        if h1e["anode_state"] != "DISCONNECTED_FLOATING" or h1e["discharge_supply_connection"] != \
                "PHYSICALLY_DISCONNECTED" or rec["terminals"]["hall_anode"]["basis"] != "OPEN_CIRCUIT_BY_CONSTRUCTION":
            why.append("H-1 anode not physically disconnected / floating (anode_state %r, supply %r; A9.5 P1Q-15 "
                       "exclusion, A9.4 P1Q-13)" % (h1e["anode_state"], h1e["discharge_supply_connection"]))
        if rec["extraction"]["electron_collecting_electrode"] != "DEDICATED_ELECTRON_COLLECTOR_TARGET":
            why.append("electron sink %r is not the dedicated electron-collecting electrode (A9.4 P1Q-10)"
                       % rec["extraction"]["electron_collecting_electrode"])
        if rec["gas_mode"] != "G-REUSE":
            why.append("gas_mode %r (a dedicated feed is diagnostic only, A9.3 OQ-RFQ-10)" % rec["gas_mode"])
        if float(rec["rf"]["P_fwd_W"]) <= 0.0:
            why.append("RF OFF (not ICP-supplied current)")
        if rec["rf_pickup_check"] != "DONE":
            why.append("rf_pickup_check NOT_DONE")
        if rec.get("h1_point_id") not in pts:
            why.append("h1_point_id %r not a registered H-1 point" % rec.get("h1_point_id"))
        if why:
            excluded.append({"record_id": rec["record_id"], "outcome": "EXCLUDED", "reasons": why})
            continue
        # from here on: an RF-ON ICP45_CAPACITY candidate point (eligibility conditions 1-3 of A9.5 P1Q-16)
        fc = facility_checks.get(rec["record_id"])
        fc_ok = fc is not None and "I_e_collector_corrected_A" in fc
        if fc is None:
            why.append("no matched RF-OFF facility pair: facility-electron correction missing; RF-ON/RF-OFF pairing "
                       "not matched (P1-D-07; A9.5 P1Q-15 / P1Q-16 condition 2)")
        elif not fc_ok:
            why.append("dedicated electron-collector current missing (or not MEASURED) in the RF-ON / RF-OFF pair")
        if fc is not None and bool(by_id[fc["records"][1]]["synthetic"]) != bool(rec["synthetic"]):
            why.append("synthetic and measured evidence mixed in the RF-ON / RF-OFF pair (A9.5 P1Q-15 exclusion)")
        ev_on = ev_off = None
        closure = None
        if fc is not None:
            off_id = fc["records"][1]
            if rule is None:
                why.append("Kirchhoff closure rule not registered (P1-IT-47 / P1-IT-48: registered sign convention id "
                           "and I_scale,min; A9.5 P1Q-15): the capacity point cannot be validated")
            else:
                ev_on, ev_off = kirchhoff_closure(rec, rule), kirchhoff_closure(by_id[off_id], rule)
                closure = {rec["record_id"]: ev_on, off_id: ev_off}
                for tag, ev in (("RF-ON", ev_on), ("matched RF-OFF", ev_off)):
                    why += ["%s record %r: %s" % (tag, ev["record_id"], r_) for r_ in ev["reasons"]]
        closure_ok = ev_on is not None and ev_on["closure_valid"] and ev_off["closure_valid"]
        elig = _point_eligibility(fc_ok, ev_on, ev_off, closure_ok)
        entry = {"record_id": rec["record_id"], "closure": closure, "eligibility": elig}
        if why:
            if ev_on is not None and ev_on["instrument_adequate"] is False:
                why.append("also NOT_EVALUATED_INSTRUMENT at this point: 3 u_R = %.6g A > 0.02 I_e,collector = "
                           "%.6g A (the tolerance is never widened)" % (CLOSURE_K_SIGMA * ev_on["u_R_A"],
                                                                         CLOSURE_FRACTION_MAX * ev_on["I_e_collector_A"]))
            entry.update({"outcome": "EXCLUDED", "reasons": why})
            excluded.append(entry)
            continue
        if not ev_on["instrument_adequate"]:
            entry.update({"outcome": "NOT_EVALUATED_INSTRUMENT",
                          "reasons": ["instrument adequacy: 3 u_R = %.6g A > 0.02 I_e,collector = %.6g A at this "
                                      "candidate qualification point: the instrumentation cannot establish the 2 %% "
                                      "closure; the tolerance is never widened (A9.5 P1Q-15)"
                                      % (CLOSURE_K_SIGMA * ev_on["u_R_A"],
                                         CLOSURE_FRACTION_MAX * ev_on["I_e_collector_A"])]})
            instrument.append(entry)
            continue
        c_on, c_off = fc["I_e_collector_rf_on_A"], fc["I_e_collector_rf_off_A"]
        u_on = ev_on["channels"]["electron_collector"]["u_A"]
        u_off = ev_off["channels"]["electron_collector"]["u_A"]
        cands.append({"record_id": rec["record_id"], "label": CAPACITY_LABEL, "outcome": "CLOSURE_VALID_CANDIDATE",
                      "synthetic": rec["synthetic"], "h1_point_id": rec["h1_point_id"], "stage_id": rec["stage_id"],
                      "electron_collecting_electrode": rec["extraction"]["electron_collecting_electrode"],
                      "rf_off_record_id": fc["records"][1],
                      "I_e_collector_rf_on_A": c_on, "I_e_collector_rf_off_A": c_off,
                      "I_e_collector_corrected_A": fc["I_e_collector_corrected_A"],
                      "I_e_cap_A": i_e_cap_signed(c_on, c_off),
                      "u_I_e_collector_rf_on_A": u_on, "u_I_e_collector_rf_off_A": u_off,
                      "u_I_e_cap_from_channels_A": math.sqrt(u_on ** 2 + u_off ** 2),
                      "closure": closure, "closure_rule_id": rule["rule_id"], "eligibility": elig})
    return cands, excluded, instrument


def neutralization_consistency(records, facility_checks, registered_point_ids=None):
    """Hall-ON follow-up (P1-S7H, H-1 anode sink; A9.4 P1Q-10): records labelled NEUTRALIZATION_CONSISTENCY, never
    ICP45_CAPACITY. Reports the verification items the owner listed - sustainment, current closure, neutralization
    behaviour (ICP-supplied current vs the Hall anode current), collector/reference potentials and RF power; stability
    comes from the dwell metrics (P1-D-08). Descriptive; never a gate and never I_e,cap."""
    pts = set(registered_point_ids or [])
    rows = []
    for rec in records:
        if rec["record_class"] != CONSISTENCY_LABEL or rec["hall_discharge_state"] != "ON":
            continue
        if rec["stage_id"] != ICP45A_CONSISTENCY_STAGE or float(rec["rf"]["P_fwd_W"]) <= 0.0:
            continue
        fc = facility_checks.get(rec["record_id"])
        i_icp = fc["I_e_icp_corrected_A"] if fc is not None else float(rec["collector"]["I_e_A"])
        i_d = abs(float(rec["terminals"]["hall_anode"]["I_A"]))
        cl = current_closure(rec)
        rows.append({"record_id": rec["record_id"], "label": CONSISTENCY_LABEL, "synthetic": rec["synthetic"],
                     "h1_point_id": rec.get("h1_point_id"),
                     "at_registered_point": rec.get("h1_point_id") in pts,
                     "hall_discharge_sustained": rec["hall_discharge_sustained"],
                     "I_e_icp_A": i_icp, "I_e_icp_basis": ("FACILITY_CORRECTED" if fc is not None
                                                           else "UNCORRECTED_NO_RF_OFF_PAIR"),
                     "I_d_anode_terminal_abs_A": i_d, "ratio_I_e_icp_to_I_d": (i_icp / i_d) if i_d > 0 else None,
                     "closure_residual_rel": cl["residual_rel"],
                     "V_collector_V": float(rec["collector"]["V_collector_V"]),
                     "collector_reference": rec["collector"]["reference_potential"],
                     "V_anode_V": float(rec["h1_electrical"]["V_anode_V"]),
                     "P_fwd_W": float(rec["rf"]["P_fwd_W"]), "P_refl_W": float(rec["rf"]["P_refl_W"]),
                     "stability": "from the dwell metrics of this point (P1-D-08)",
                     "status": "DESCRIPTIVE_CONSISTENCY_CHECK_NOT_A_GATE"})
    return rows


def icp45a_evaluate(records, registration=None, margin_rule=None, facility_checks=None, closure_rule=None):
    """ICP-45A (Ar, engineering-only) condition I_e,cap >= I_d,max,H1 with the one-sided lower bound of M_n above zero
    (A9.1 ICP-45, UBQ-02; A9.3 OQ-A907-02; A9.4 P1Q-10; A9.5 P1Q-15 / P1Q-16). Eligible only when (1) the capacity
    point passes the owner Kirchhoff closure, (2) the matched RF-OFF correction is valid, (3) all required
    uncertainties are available (u(I_k) of every channel; u_I_e_A and u_I_d_max_A of the margin rule) and (4)
    I_d,max,H1 is registered from the H-1 envelope and measured behaviour (never the 8.33 A bench ceiling); until all
    four exist the status is exactly NOT_EVALUATED; never PASS / FAIL. Per capacity point the outcome is one of
    POINT_OUTCOMES (NOT_EVALUATED_INSTRUMENT when 3 u_R > 0.02 I_e,collector). Hall-ON records only feed the
    NEUTRALIZATION_CONSISTENCY list."""
    base = {"i_e_cap_definition": I_E_CAP_DEFINITION, "capacity_label": CAPACITY_LABEL,
            "consistency_label": CONSISTENCY_LABEL, "status_vocabulary": list(ICP45A_STATUSES),
            "point_outcome_vocabulary": list(POINT_OUTCOMES),
            "closure_owner_rule": {"source": A95_REF, "sign_convention": KIRCHHOFF_SIGN_CONVENTION,
                                   "residual": "R_I = sum_k I_k", "k_sigma": CLOSURE_K_SIGMA,
                                   "fraction_max": CLOSURE_FRACTION_MAX,
                                   "instrument_adequacy": "3 u_R <= 0.02 I_e,collector at the candidate point, "
                                                          "else NOT_EVALUATED_INSTRUMENT"}}
    facility_checks = facility_checks or {}
    if registration is None:
        base.update({"status": "NOT_EVALUATED", "condition_met": None,
                     "eligibility": {"4_I_d_max_H1_registered": False},
                     "reason": "I_d,max,H1 not registered (A9.3 OQ-A907-02; A9.4 execution_decisions.i_d_max_h1: "
                               "established from the registered H-1 operating envelope and measured H-1 behaviour, "
                               "never from the 8.33 A bench design ceiling); ICP45 = NOT_EVALUATED, not PASS or FAIL "
                               "(A9.5 P1Q-16 condition 4); the surface is reported instead",
                     "neutralization_consistency": neutralization_consistency(records, facility_checks)})
        return base
    idm, k, ue, ud = _check_registration(registration, margin_rule)
    cands, excluded, instrument = icp45a_candidates(records, registration, facility_checks, closure_rule)
    points = [{"record_id": c["record_id"], "outcome": c["outcome"]} for c in cands]
    points += [{"record_id": e["record_id"], "outcome": e["outcome"]} for e in instrument]
    points += [{"record_id": e["record_id"], "outcome": e["outcome"]} for e in excluded if "eligibility" in e]
    base.update({"registration_id": registration["registration_id"], "rule_id": margin_rule["rule_id"],
                 "closure_rule_id": closure_rule["rule_id"] if closure_rule is not None else None,
                 "I_d_max_H1_A": idm, "excluded_records": excluded, "not_evaluated_instrument_records": instrument,
                 "capacity_point_outcomes": sorted(points, key=lambda p: p["record_id"]),
                 "neutralization_consistency": neutralization_consistency(
                     records, facility_checks, registration["registered_point_ids"])})
    if not cands:
        base.update({"status": "NOT_EVALUATED", "condition_met": None,
                     "reason": "no admissible ICP45_CAPACITY point: conditions (1) owner Kirchhoff closure, (2) matched "
                               "RF-OFF correction, (3) required uncertainties are not all met at any point (dedicated "
                               "collector, discharge supply OFF and disconnected, floating anode, registered H-1 point, "
                               "registered closure rule; %d point(s) NOT_EVALUATED_INSTRUMENT; see excluded_records); "
                               "ICP45 = NOT_EVALUATED (A9.5 P1Q-16), never a FAIL" % len(instrument)})
        return base
    if len({bool(c["synthetic"]) for c in cands}) > 1:
        raise P1RecordError("ICP45_CAPACITY candidates mix synthetic fixtures %s with measured records %s: refused "
                            "(a synthetic record must never suppress or substitute a measured evaluation)"
                            % (sorted(c["record_id"] for c in cands if c["synthetic"]),
                               sorted(c["record_id"] for c in cands if not c["synthetic"])))
    best = max(cands, key=lambda c: (c["I_e_cap_A"], c["record_id"]))
    i_cap = best["I_e_cap_A"]                       # signed; never clipped (A9.5 P1Q-16)
    base.update(icp45a_margin(i_cap, idm, k, ue, ud))
    flags = []
    if i_cap < 0.0:
        flags.append("I_E_CAP_NEGATIVE: the RF-OFF (facility/background) collector current exceeds the RF-ON value; "
                     "reported signed, no absolute-value correction and no zero-clipping (A9.5 P1Q-16)")
    if ue < best["u_I_e_cap_from_channels_A"]:
        flags.append("REGISTERED_u_I_e_BELOW_CHANNEL_PROPAGATION: margin_rule.u_I_e_A = %.6g A < sqrt(u^2(I_col,ON) + "
                     "u^2(I_col,OFF)) = %.6g A; the preregistered value is used unchanged (owner question P1Q-19)"
                     % (ue, best["u_I_e_cap_from_channels_A"]))
    base.update({"I_e_cap_A": i_cap, "I_e_cap_record": best["record_id"], "candidates": cands,
                 "u_I_e_cap_used_A": ue, "u_I_e_cap_used_basis": "margin_rule.u_I_e_A (preregistered, P1-IT-29)",
                 "u_I_e_cap_from_channels_A": best["u_I_e_cap_from_channels_A"],
                 "eligibility": dict(best["eligibility"]), "flags": flags})
    if any(c["synthetic"] for c in cands):
        base.update({"status": "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE", "condition_met": None,
                     "arithmetic_lower_bound_positive": bool(base["M_n_lower"] > 0.0),
                     "note": "synthetic candidates: arithmetic check only, never an ICP-45A evaluation"})
        return base
    base.update({"status": "EVALUATED_ENGINEERING_ONLY", "condition_met": bool(base["M_n_lower"] > 0.0),
                 "evidence_class": REQUIRED_LABEL,
                 "note": "ICP-45A is Ar engineering-only evidence (A9.1); ICP-45N on N2 is still required before any "
                         "score-bearing hall_icp_neutralizer point; I_e,cap definition OWNER_DECIDED (A9.4 P1Q-10) and "
                         "formula OWNER_CONFIRMED (A9.5 P1Q-16); condition_met = (M_n,LB > 0); the Hall-ON follow-up "
                         "(P1-S7H, NEUTRALIZATION_CONSISTENCY) must still show the capacity operates in the real Hall "
                         "loop; never an architecture PASS"})
    return base


# ------------------------------------------------------------------------------------------------ reducers
def _row_flags(rec, rf):
    flags = []
    if rec["rf_pickup_check"] != "DONE":
        flags.append("RF_PICKUP_CHECK_NOT_DONE: floating / Hall channel readings not verified against RF pickup "
                     "(owner row 64; ICD ICP-17)")
    if rf["P_delivered_kind"] == "P_RF_DELIVERED_UPPER_BOUND_LOSS_NOT_MEASURED":
        flags.append("LINE_MATCH_LOSS_NOT_MEASURED: P_delivered and C_e are upper bounds")
    if rf["rf_state"] == "RF_OFF":
        flags.append("RF_OFF: facility / non-ICP current record (P1-D-07)")
    if float(rec["collector"]["I_e_A"]) < 0.0:
        flags.append("I_E_NEGATIVE: net ion collection at this bias, or a sensor orientation inconsistent with "
                     "the declared sign convention - verify before use")
    unmeasured = sorted(n for n, t in rec["terminals"].items() if t["basis"] == "NOT_MEASURED")
    if unmeasured:
        flags.append("TERMINAL_NOT_MEASURED: %s declared unavailable; never summed as zero, no Kirchhoff residual "
                     "formed (A9.5 P1Q-15)" % unmeasured)
    if rec["synthetic"]:
        flags.append("SYNTHETIC_TEST_FIXTURE: not data")
    return flags


def reduce_operating_points(records, registration=None, margin_rule=None, facility_pairs=None, facility_match=None,
                            closure_rule=None):
    """Surface table + summaries for a list of 'icp_operating_point' records. facility_pairs = [[rf_on_id,
    rf_off_id], ...] (each checked with facility_electron_check under facility_match). closure_rule = registered
    registered inputs of the owner Kirchhoff rule for capacity points {rule_id, sign_convention, sign_convention_id,
    I_scale_min_A, I_scale_min_basis (, covariance)} (A9.5 P1Q-15; no default; the factor 3 and the 2 % are owner
    constants, never inputs)."""
    if not isinstance(records, list) or not records:
        raise MissingInputError("reduce_operating_points: a non-empty list of records is required")
    rows = []
    ids = set()
    for rec in records:
        validate_operating_point(rec)
        if rec["record_id"] in ids:
            raise P1RecordError("duplicate record_id %r" % rec["record_id"])
        ids.add(rec["record_id"])
    by_id = {r["record_id"]: r for r in records}
    fac = []
    for pair in facility_pairs or []:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2 or pair[0] not in by_id or pair[1] not in by_id:
            raise MissingInputError("facility pair %r refers to unknown records" % (pair,))
        fac.append(facility_electron_check(by_id[pair[0]], by_id[pair[1]], facility_match))
    fac_by_on = {}
    for f in fac:
        if f["records"][0] in fac_by_on:
            raise P1RecordError("RF-ON record %r appears in more than one facility pair" % f["records"][0])
        fac_by_on[f["records"][0]] = f
    for rec in records:
        rf = derive_rf(rec)
        ce = electron_cost(rec, rf)
        cl = current_closure(rec)
        imp = rec["impedance"]
        ext = rec["extraction"]
        rows.append({
            "record_id": rec["record_id"], "run_id": rec["run_id"], "stage_id": rec["stage_id"],
            "record_class": rec["record_class"], "synthetic": rec["synthetic"], "labels": sorted(rec["labels"]), "gas": rec["gas"],
            "gas_mode": rec["gas_mode"], "hall_discharge_state": rec["hall_discharge_state"],
            "hall_discharge_sustained": rec["hall_discharge_sustained"],
            "h1_electrical": {"config_id": rec["h1_electrical"]["config_id"],
                              "anode_state": rec["h1_electrical"]["anode_state"],
                              "V_anode_V": float(rec["h1_electrical"]["V_anode_V"]),
                              "discharge_supply_connection": rec["h1_electrical"]["discharge_supply_connection"]},
            "h1_point_id": rec.get("h1_point_id"), "rf_state": rf["rf_state"],
            "factors": {"P_fwd_W": rf["P_fwd_W"], "P_delivered_W": rf["P_delivered_W"],
                        "P_delivered_kind": rf["P_delivered_kind"],
                        "p_chamber_Pa": float(rec["pressures"]["p_chamber_Pa"]),
                        "mdot_Ar_H1_mg_s": float(rec["flows"]["mdot_Ar_H1_mg_s"]),
                        "mdot_icp_dedicated_mg_s": float(rec["flows"]["mdot_icp_dedicated_mg_s"]),
                        "Z_ICP": ({"R_ohm": float(imp["R_ohm"]), "X_ohm": float(imp["X_ohm"])}
                                  if imp["status"] == "MEASURED" else None),
                        "V_collector_V": float(rec["collector"]["V_collector_V"]),
                        "collector_reference": rec["collector"]["reference_potential"],
                        "extraction_topology_id": ext["topology_id"],
                        "electron_collecting_electrode": ext["electron_collecting_electrode"],
                        "match_setting_id": rec["rf"]["match_setting_id"]},
            "I_e_A": ce["I_e_A"], "gamma_abs": rf["gamma_abs"], "VSWR": rf["VSWR"], "P_refl_W": rf["P_refl_W"],
            "C_e_W_per_A": ce["C_e_W_per_A"], "C_e_kind": ce["C_e_kind"], "C_e_boundary": ce["C_e_boundary"],
            "C_e_reason": ce["C_e_reason"],
            "C_e_DC_W_per_A": ce["C_e_DC_W_per_A"], "C_e_DC_boundary": ce["C_e_DC_boundary"],
            "closure_residual_rel": cl["residual_rel"], "closure_sum_A": cl["sum_A"],
            "closure_state": cl["closure_state"],
            "rf_pickup_check": rec["rf_pickup_check"], "flags": _row_flags(rec, rf),
            "temperatures_C": dict(sorted(rec["temperatures"].items())),
            "thermal_status": "RECORDED_ONLY - ICP_COUPLED_THERMAL = UNRESOLVED (A9.2); never a thermal PASS",
        })
    rows.sort(key=lambda r: r["record_id"])
    i_e = np.array([r["I_e_A"] for r in rows], dtype=float)
    return {
        "schema": "p1_reduction_v1",
        "any_synthetic": any(r["synthetic"] for r in rows),
        "evidence_class": REQUIRED_LABEL,
        "surface_definition": "I_e = f(P_RF, p, mdot, Z_ICP, V_collector) (A9.3 OQ-A907-02)",
        "surface": rows,
        "facility_electron_checks": fac,
        "summary": {"n_records": len(rows),
                    "I_e_max_recorded_A": float(i_e.max()),
                    "I_e_max_recorded_note": "descriptive maximum over ALL records (any stage, RF state, gas mode); "
                                             "NOT I_e,cap and never an ICP-45 result",
                    "icp45a": icp45a_evaluate(records, registration, margin_rule, fac_by_on, closure_rule)},
        "not_p_bus": "C_e,DC uses the laboratory generator input (GROUND/FACILITY_ONLY); P_bus is never produced here",
    }


def reduce_topology_control(seq):
    """OQ-VI-05 seven-step Ar topology-control record -> observation class (never PASS/FAIL)."""
    rid = "sequence %r" % (seq.get("record_id") if isinstance(seq, dict) else None)
    _req(seq, SEQUENCE_REQUIRED, rid)
    if seq["schema"] != SCHEMA_ID or seq["record_kind"] != "topology_control_sequence":
        raise P1RecordError("%s: schema/record_kind mismatch" % rid)
    if seq["gas"] not in P1_GASES:
        raise P1RecordError("%s: OQ-VI-05 sequence is an Ar sequence (A9.3); got %r" % (rid, seq["gas"]))
    _labels_ok(seq, rid)
    if seq["classification"] != TOPOLOGY_CONTROL_LABEL:
        raise LabelError("%s: classification must be %s (A9.3 OQ-VI-05)" % (rid, TOPOLOGY_CONTROL_LABEL))
    if seq["c1_disconnected"] is not True:
        raise SequenceError("%s: step 2 requires C1 disconnected / not supplying electrons" % rid)
    if not isinstance(seq["hall_start_registration_id"], str) or not seq["hall_start_registration_id"].strip():
        raise SequenceError("%s: the Hall start attempt must be preregistered inside registered limits (step 4); "
                            "no registration id" % rid)
    steps = seq["steps"]
    if not isinstance(steps, list) or [s.get("step") for s in steps] != [n for n, _ in SEQUENCE_STEPS]:
        raise SequenceError("%s: steps must be exactly 1..7 in order (A9.3 OQ-VI-05)" % rid)
    for (n, text), s in zip(SEQUENCE_STEPS, steps):
        if s.get("text") != text:
            raise SequenceError("%s: step %d text must be the owner's verbatim text %r" % (rid, n, text))
        sig = s.get("signals")
        _req(sig, SEQUENCE_SIGNALS, "%s step %d signals" % (rid, n))
        t = np.asarray(sig["t_s"], dtype=float)
        if t.size < 1:
            raise MissingInputError("%s step %d: empty signal record" % (rid, n))
        for k in SEQUENCE_SIGNALS[1:]:
            if len(sig[k]) != t.size:
                raise MissingInputError("%s step %d: signal %s length mismatch" % (rid, n, k))
    for n in (5, 7):
        if not isinstance(steps[n - 1].get("sustained_discharge_observed"), bool):
            raise MissingInputError("%s: step %d needs sustained_discharge_observed (true/false) recorded against "
                                    "the registered sustainment definition" % (rid, n))
    if not isinstance(steps[4].get("sustainment_definition_id"), str) or not steps[4]["sustainment_definition_id"]:
        raise SequenceError("%s: step 5 needs the registered sustainment definition id (owner question P1Q-03)" % rid)
    icp_off = steps[4]["sustained_discharge_observed"]
    icp_on = steps[6]["sustained_discharge_observed"]
    if not icp_off and icp_on:
        obs, branch = "TAKAHASHI_LIKE_OBSERVATION", None
    elif icp_off:
        obs, branch = "UNEXPECTED_SUSTAINED_DISCHARGE_ICP_OFF", "CURRENT_PATH_DIAGNOSIS_REQUIRED (P1-S6D)"
    else:
        obs, branch = "NO_SUSTAINED_DISCHARGE_WITH_ICP_ON", "RECORD_AND_REVIEW (no verdict)"
    return {"record_id": seq["record_id"], "synthetic": seq["synthetic"], "classification": TOPOLOGY_CONTROL_LABEL,
            "observation": obs, "branch": branch, "sustained_icp_off": icp_off, "sustained_icp_on": icp_on,
            "note": "not a PASS/FAIL gate; 'Hall must not run without ICP' is NOT a requirement (A9.3 OQ-VI-05)"}


def reduce(bundle, registration=None, margin_rule=None, stable_criteria=None, facility_match=None, closure_rule=None):
    """Top-level reducer. bundle = {"operating_points": [...], "topology_control": [...] (optional),
    "dwells": [{"record_id", "dwell", "ignition"}] (optional), "facility_pairs": [[on_id, off_id]] (optional)}.
    facility_match = {"criteria_id", "p_chamber_rel_tol"} is required whenever facility_pairs are given (P1-IT-37);
    closure_rule = {"rule_id", "sign_convention", "sign_convention_id", "I_scale_min_A", "I_scale_min_basis"
    (, "covariance")} carries the registered inputs of the owner Kirchhoff rule for capacity points (A9.5 P1Q-15;
    P1-IT-47 / P1-IT-48)."""
    _req(bundle, ("operating_points",), "bundle")
    ops = reduce_operating_points(bundle["operating_points"], registration, margin_rule,
                                  bundle.get("facility_pairs"), facility_match, closure_rule)
    dwells = []
    for d in bundle.get("dwells") or []:
        _req(d, ("record_id", "dwell"), "dwell entry")
        m = dwell_metrics(d["dwell"])
        dwells.append({"record_id": d["record_id"], "metrics": m,
                       "stable_region": classify_stable_region(m, stable_criteria, d.get("ignition"))})
    topo = [reduce_topology_control(s) for s in bundle.get("topology_control") or []]
    return {"operating_points": ops, "facility_electron_checks": ops["facility_electron_checks"], "dwells": dwells,
            "topology_control": topo,
            "any_synthetic": ops["any_synthetic"] or any(t["synthetic"] for t in topo)}
