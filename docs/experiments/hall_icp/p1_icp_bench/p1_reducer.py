"""P1 ICP electron-source bench - pure, deterministic analysis reducer (lane fo_a9_p1_icp_bench, A9.3 P1).

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
* It never treats P_mains,in (laboratory generator mains input, GROUND/FACILITY_ONLY) as P_bus.
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
P1_GASES = ("Ar",)
GAS_MODES = ("G-REUSE", "DIAGNOSTIC_DEDICATED_FEED")
HALL_STATES = ("OFF", "ON")
RF_REFERENCE_PLANE = "GENERATOR_50OHM_SIDE_OF_LOCAL_MATCH"
LOSS_STATUSES = ("MEASURED", "FLAGGED_NOT_MEASURED")
GENERATOR_CLASSES = ("GROUND_FACILITY_ONLY_MAINS", "FLIGHT_REPRESENTATIVE_DC_RF_SOURCE")
TERMINAL_BASES = ("MEASURED", "OPEN_CIRCUIT_BY_CONSTRUCTION")
REQUIRED_TERMINALS = {
    "OFF": ("collector_supply", "icp_body", "facility_ground"),
    "ON": ("collector_supply", "icp_body", "facility_ground", "hall_anode"),
}
REQUIRED_TEMPERATURES = ("T_icp_dielectric_C", "T_antenna_C", "T_collector_C", "T_match_C", "T_rf_source_C",
                         "T_h1_pole_inner_C", "T_h1_pole_outer_C", "T_sink_C")
PRESSURE_FIELDS = ("p_chamber_Pa",)
REGISTRATION_BASIS = "MEASURED_REGISTERED_H1_OPERATION"
REFUSED_REGISTRATION_BASES = ("STAND_CEILING", "SUPPLY_RATING", "POWER_ENVELOPE_BOUND", "ASSUMED")

OPERATING_POINT_REQUIRED = (
    "schema", "record_kind", "record_id", "run_id", "stage_id", "timestamp_utc", "synthetic", "labels", "gas",
    "gas_mode", "hall_discharge_state", "rf", "generator", "collector", "pressures", "flows", "impedance",
    "terminals", "temperatures", "rf_pickup_check",
)
RF_REQUIRED = ("reference_plane", "P_fwd_W", "P_refl_W", "line_match_loss", "match_setting_id")
GENERATOR_REQUIRED = ("generator_class", "P_generator_input_W", "input_boundary", "instrument")
COLLECTOR_REQUIRED = ("I_e_A", "V_collector_V", "reference_potential")
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
    "FLIGHT_REPRESENTATIVE_DC_RF_SOURCE": ("P_DC,in: DC input of a FLIGHT_REPRESENTATIVE_DC_RF_SOURCE (A9.3 "
                                           "OQ-RFQ-06, later programme); one term of P_bus only, never P_bus "
                                           "itself"),
}


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
    bad = [lab for lab in labels if lab in FORBIDDEN_LABELS]
    if bad:
        raise LabelError("%s: P1 records are non-scoring; forbidden label(s) %s" % (where, bad))


def _refuse_p_bus_claim(rec, where):
    for key in ("P_bus_W", "p_bus_W", "P_bus"):
        if key in rec or key in (rec.get("generator") or {}):
            raise PMainsNotPBusError("%s: field '%s' present; a P1 bench record never carries P_bus - the laboratory "
                                     "generator input is P_mains,in (GROUND/FACILITY_ONLY, A9.3 OQ-RFQ-06)"
                                     % (where, key))


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
    if pf > 0 and pr >= pf:
        raise P1RecordError("%s: P_refl >= P_fwd (%r >= %r) is not a physical reading of a passive load" % (rid, pr, pf))
    loss = rf["line_match_loss"]
    if not isinstance(loss, dict) or loss.get("status") not in LOSS_STATUSES:
        raise LineMatchLossError("%s: P_delivered needs the line/match loss term either MEASURED or explicitly "
                                 "FLAGGED_NOT_MEASURED (A9.2); got %r" % (rid, loss))
    if loss["status"] == "MEASURED":
        _num(loss.get("value_W"), rid + " rf.line_match_loss.value_W", allow_negative=False)
        if not loss.get("source"):
            raise MissingInputError("%s: a MEASURED line/match loss needs its source (S1 dummy-load / two-port "
                                    "characterization id)" % rid)
    # generator
    gen = rec["generator"]
    _req(gen, GENERATOR_REQUIRED, rid + " generator")
    if gen["generator_class"] not in GENERATOR_CLASSES:
        raise P1RecordError("%s: generator_class %r not in %s" % (rid, gen["generator_class"], GENERATOR_CLASSES))
    _num(gen["P_generator_input_W"], rid + " generator.P_generator_input_W", allow_negative=False)
    # collector
    col = rec["collector"]
    _req(col, COLLECTOR_REQUIRED, rid + " collector")
    _num(col["I_e_A"], rid + " collector.I_e_A")
    _num(col["V_collector_V"], rid + " collector.V_collector_V")
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
    # terminals
    terms = rec["terminals"]
    need = REQUIRED_TERMINALS[rec["hall_discharge_state"]]
    if not isinstance(terms, dict):
        raise MissingInputError("%s: terminals must be an object" % rid)
    for name in need:
        t = terms.get(name)
        if not isinstance(t, dict) or t.get("basis") not in TERMINAL_BASES:
            raise MissingInputError("%s: current-path terminal '%s' missing or without basis %s (Kirchhoff closure "
                                    "needs every terminal of the isolated network)" % (rid, name, TERMINAL_BASES))
        _num(t.get("I_A"), "%s terminals.%s.I_A" % (rid, name))
        if t["basis"] == "OPEN_CIRCUIT_BY_CONSTRUCTION" and float(t["I_A"]) != 0.0:
            raise P1RecordError("%s: terminal '%s' declared open circuit but carries %r A" % (rid, name, t["I_A"]))
    return None


# ------------------------------------------------------------------------------------------------ derived quantities
def derive_rf(rec):
    """|Gamma|, VSWR and P_RF,delivered at the A9.2 reference plane. Arithmetic only."""
    rf = rec["rf"]
    pf, pr = float(rf["P_fwd_W"]), float(rf["P_refl_W"])
    loss = rf["line_match_loss"]
    if not isinstance(loss, dict) or loss.get("status") not in LOSS_STATUSES:
        raise LineMatchLossError("record %r: line/match loss neither MEASURED nor FLAGGED_NOT_MEASURED"
                                 % rec.get("record_id"))
    gamma = math.sqrt(pr / pf) if pf > 0 else None
    vswr = (1.0 + gamma) / (1.0 - gamma) if gamma is not None else None
    if loss["status"] == "MEASURED":
        p_del = pf - pr - float(loss["value_W"])
        kind = "P_RF_DELIVERED"
    else:
        p_del = pf - pr
        kind = "P_RF_DELIVERED_UPPER_BOUND_LOSS_NOT_MEASURED"
    return {"P_fwd_W": pf, "P_refl_W": pr, "gamma_abs": gamma, "VSWR": vswr, "P_delivered_W": p_del,
            "P_delivered_kind": kind, "reference_plane": RF_REFERENCE_PLANE,
            "note": "P_fwd is never P_plasma (A9.2)"}


def electron_cost(rec, rf_derived):
    """C_e and C_e,DC with boundary labels (A9.3 OQ-RFQ-06). Undefined (None + reason) for I_e <= 0."""
    i_e = float(rec["collector"]["I_e_A"])
    gen = rec["generator"]
    out = {"I_e_A": i_e}
    if i_e <= 0.0:
        reason = "I_e <= 0: electron cost undefined"
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
    """Kirchhoff closure of the isolated electrical network: sum of signed terminal currents (positive = conventional
    current INTO the network) should vanish; residual normalised by the largest terminal magnitude."""
    terms = rec["terminals"]
    names = sorted(terms)
    vals = np.array([float(terms[n]["I_A"]) for n in names], dtype=float)
    total = float(vals.sum())
    scale = float(np.max(np.abs(vals))) if vals.size else 0.0
    return {"terminals": names, "sum_A": total, "scale_A": scale,
            "residual_rel": (total / scale) if scale > 0 else None,
            "note": "descriptive residual; acceptance limit TBD - frozen at LOCK-2 from S1b-type readings "
                    "(A9-04 UB-N-07 form)"}


def facility_electron_check(rf_on, rf_off):
    """Facility-electron contribution: collector current with the ICP RF OFF at the same bias/flow/pressure point
    divided by the current with RF ON. Descriptive; no threshold."""
    for r in (rf_on, rf_off):
        validate_operating_point(r)
    if float(rf_off["rf"]["P_fwd_W"]) != 0.0:
        raise P1RecordError("facility-electron check: the RF-OFF record has P_fwd = %r W" % rf_off["rf"]["P_fwd_W"])
    for path in (("collector", "V_collector_V"), ("flows", "mdot_Ar_H1_mg_s")):
        a, b = rf_on[path[0]][path[1]], rf_off[path[0]][path[1]]
        if float(a) != float(b):
            raise P1RecordError("facility-electron check: %s differs between records (%r vs %r)" % (".".join(path), a, b))
    i_on, i_off = float(rf_on["collector"]["I_e_A"]), float(rf_off["collector"]["I_e_A"])
    return {"I_e_rf_on_A": i_on, "I_e_rf_off_A": i_off,
            "facility_fraction": (i_off / i_on) if i_on != 0 else None,
            "records": [rf_on["record_id"], rf_off["record_id"]]}


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


def icp45a_condition(max_i_e_A, registration=None, margin_rule=None):
    """ICP-45A (Ar, engineering-only) condition I_e,cap >= I_d,max,H1 with a one-sided margin (A9.1 ICP-45, UBQ-02;
    A9.3 OQ-A907-02). NOT_EVALUATED until I_d,max,H1 is registered from measured H-1 operation."""
    if registration is None:
        return {"status": "NOT_EVALUATED",
                "reason": "I_d,max,H1 not registered (A9.3 OQ-A907-02: I_e,required = I_d,max,H1 from measured/"
                          "registered H-1 operation); the surface is reported instead; reaching 1 A, 2 A, ... is "
                          "never a PASS"}
    _req(registration, ("registration_id", "I_d_max_H1_A", "basis", "source"), "registration")
    if registration["basis"] != REGISTRATION_BASIS:
        raise RegistrationError("I_d,max,H1 basis %r refused: only %s (the 8.33 A stand ceiling and the 7.5 A "
                                "power-envelope bound are not the ICP-45 requirement, A9.3 OQ-A907-02)"
                                % (registration["basis"], REGISTRATION_BASIS))
    if margin_rule is None:
        raise RegistrationError("ICP-45A needs the preregistered one-sided margin rule (k_one_sided, u_I_e_A, "
                                "rule_id); none supplied")
    _req(margin_rule, ("rule_id", "k_one_sided", "u_I_e_A", "u_I_d_max_A"), "margin_rule")
    idm = _num(registration["I_d_max_H1_A"], "registration.I_d_max_H1_A", allow_negative=False)
    if idm <= 0:
        raise RegistrationError("I_d,max,H1 must be > 0")
    k = _num(margin_rule["k_one_sided"], "margin_rule.k_one_sided", allow_negative=False)
    ue = _num(margin_rule["u_I_e_A"], "margin_rule.u_I_e_A", allow_negative=False)
    ud = _num(margin_rule["u_I_d_max_A"], "margin_rule.u_I_d_max_A", allow_negative=False)
    m_n = max_i_e_A / idm - 1.0
    u_m = math.sqrt((ue / idm) ** 2 + (max_i_e_A * ud / idm ** 2) ** 2)
    lower = m_n - k * u_m
    return {"status": "EVALUATED_ENGINEERING_ONLY", "registration_id": registration["registration_id"],
            "rule_id": margin_rule["rule_id"], "I_e_cap_observed_A": max_i_e_A, "I_d_max_H1_A": idm,
            "M_n": m_n, "u_M_n": u_m, "M_n_lower": lower,
            "condition_met": bool(lower > 0.0),
            "evidence_class": REQUIRED_LABEL,
            "note": "ICP-45A is Ar engineering-only evidence (A9.1); ICP-45N on N2 is still required before any "
                    "score-bearing hall_icp_neutralizer point; never an architecture PASS"}


# ------------------------------------------------------------------------------------------------ reducers
def reduce_operating_points(records, registration=None, margin_rule=None):
    """Surface table + summaries for a list of 'icp_operating_point' records."""
    if not isinstance(records, list) or not records:
        raise MissingInputError("reduce_operating_points: a non-empty list of records is required")
    rows = []
    ids = set()
    for rec in records:
        validate_operating_point(rec)
        if rec["record_id"] in ids:
            raise P1RecordError("duplicate record_id %r" % rec["record_id"])
        ids.add(rec["record_id"])
        rf = derive_rf(rec)
        ce = electron_cost(rec, rf)
        cl = current_closure(rec)
        imp = rec["impedance"]
        rows.append({
            "record_id": rec["record_id"], "run_id": rec["run_id"], "stage_id": rec["stage_id"],
            "synthetic": rec["synthetic"], "labels": sorted(rec["labels"]), "gas": rec["gas"],
            "gas_mode": rec["gas_mode"], "hall_discharge_state": rec["hall_discharge_state"],
            "factors": {"P_fwd_W": rf["P_fwd_W"], "P_delivered_W": rf["P_delivered_W"],
                        "P_delivered_kind": rf["P_delivered_kind"],
                        "p_chamber_Pa": float(rec["pressures"]["p_chamber_Pa"]),
                        "mdot_Ar_H1_mg_s": float(rec["flows"]["mdot_Ar_H1_mg_s"]),
                        "mdot_icp_dedicated_mg_s": float(rec["flows"]["mdot_icp_dedicated_mg_s"]),
                        "Z_ICP": ({"R_ohm": float(imp["R_ohm"]), "X_ohm": float(imp["X_ohm"])}
                                  if imp["status"] == "MEASURED" else None),
                        "V_collector_V": float(rec["collector"]["V_collector_V"]),
                        "collector_reference": rec["collector"]["reference_potential"],
                        "match_setting_id": rec["rf"]["match_setting_id"]},
            "I_e_A": ce["I_e_A"], "gamma_abs": rf["gamma_abs"], "VSWR": rf["VSWR"], "P_refl_W": rf["P_refl_W"],
            "C_e_W_per_A": ce["C_e_W_per_A"], "C_e_kind": ce["C_e_kind"], "C_e_boundary": ce["C_e_boundary"],
            "C_e_DC_W_per_A": ce["C_e_DC_W_per_A"], "C_e_DC_boundary": ce["C_e_DC_boundary"],
            "closure_residual_rel": cl["residual_rel"], "closure_sum_A": cl["sum_A"],
            "temperatures_C": dict(sorted(rec["temperatures"].items())),
            "thermal_status": "RECORDED_ONLY - ICP_COUPLED_THERMAL = UNRESOLVED (A9.2); never a thermal PASS",
        })
    rows.sort(key=lambda r: r["record_id"])
    i_e = np.array([r["I_e_A"] for r in rows], dtype=float)
    max_ie = float(i_e.max())
    return {
        "schema": "p1_reduction_v1",
        "any_synthetic": any(r["synthetic"] for r in rows),
        "evidence_class": REQUIRED_LABEL,
        "surface_definition": "I_e = f(P_RF, p, mdot, Z_ICP, V_collector) (A9.3 OQ-A907-02)",
        "surface": rows,
        "summary": {"n_records": len(rows), "I_e_max_observed_A": max_ie,
                    "I_e_max_record": rows[int(np.argmax(i_e))]["record_id"],
                    "icp45a": icp45a_condition(max_ie, registration, margin_rule)},
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


def reduce(bundle, registration=None, margin_rule=None, stable_criteria=None):
    """Top-level reducer. bundle = {"operating_points": [...], "topology_control": [...] (optional),
    "dwells": [{"record_id", "dwell", "ignition"}] (optional), "facility_pairs": [[on_id, off_id]] (optional)}."""
    _req(bundle, ("operating_points",), "bundle")
    ops = reduce_operating_points(bundle["operating_points"], registration, margin_rule)
    by_id = {r["record_id"]: r for r in bundle["operating_points"]}
    fac = []
    for pair in bundle.get("facility_pairs") or []:
        if len(pair) != 2 or pair[0] not in by_id or pair[1] not in by_id:
            raise MissingInputError("facility pair %r refers to unknown records" % (pair,))
        fac.append(facility_electron_check(by_id[pair[0]], by_id[pair[1]]))
    dwells = []
    for d in bundle.get("dwells") or []:
        _req(d, ("record_id", "dwell"), "dwell entry")
        m = dwell_metrics(d["dwell"])
        dwells.append({"record_id": d["record_id"], "metrics": m,
                       "stable_region": classify_stable_region(m, stable_criteria, d.get("ignition"))})
    topo = [reduce_topology_control(s) for s in bundle.get("topology_control") or []]
    return {"operating_points": ops, "facility_electron_checks": fac, "dwells": dwells, "topology_control": topo,
            "any_synthetic": ops["any_synthetic"] or any(t["synthetic"] for t in topo)}
