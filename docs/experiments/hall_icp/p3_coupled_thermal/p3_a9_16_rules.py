#!/usr/bin/env python3
"""A9.16 step 1 - owner rules of 2026-10-01 for the P3 coupled H-1 / ICP thermal framework (pure functions).

Implements, fail-closed, the owner decisions A9.8 P3Q-01 and A9.12 ICPQ-10, OQ-A907-03, OQ-A907-05, OQ-A907-06,
OQ-A907-08, OQ-A907-09, OQ-A907-10, OQ-A910-06, P3Q-02 (verbatim records under docs/decisions/; the verbatim .md
governs over the json summary). No file I/O, no global state, not wired into abep_sim/archengine.py.

Owner-supplied numbers used here, and only these: heat-load design margin 1.20 on dissipated loads (row 86; A9.12
S5.1 / S5.6 / S5.8), >= 50 K below T_validated,continuous (row 86; A9.12 S5.2 / S5.5), mount-heat allocations 50 W
governing provisional / 100 W contingency / 25 W stretch (A9.12 S5.4), 10 K SEARCH_SENSITIVE screen (A9.12 S5.7),
Q_RF,allocation = 500 W x 1.20 = 600 W temporary (A9.12 S5.8). Every number the owner deferred to a later
registration (correlation residual band, cross-check agreement criterion, search allowance, admissible-corner
exclusions, ...) is a registration slot: an unregistered slot refuses (RuleRefusal with a NOT_EVALUATED_* / OPEN /
INCOMPLETE_EVIDENCE code) - nothing is defaulted here. Nothing here ever returns a thermal PASS; ICP_COUPLED_THERMAL
and ANODE_THERMAL_CLOSURE stay UNRESOLVED (A9.2, A9.6).
"""
from __future__ import annotations

import itertools
import math

# ------------------------------------------------------------------------------------------------ owner numbers
HEAT_LOAD_MARGIN = 1.20                 # row 86; A9.12 S5.1 / S5.6 / S5.8 - never relaxed
TEMPERATURE_MARGIN_K = 50.0             # row 86; A9.12 S5.2 / S5.5 - never relaxed
MOUNT_HEAT_ALLOCATION_W = {"stretch": 25.0, "governing_provisional": 50.0, "contingency_sensitivity": 100.0}
SEARCH_SENSITIVE_SCREEN_K = 10.0        # A9.12 S5.7 - screening label only
RF_ALLOCATION_BASE_W = 500.0            # A9.12 S5.8 (A9.2 rf_500W allocation term, not a rating)
Q_RF_ALLOCATION_W = 600.0               # = 500 W x 1.20 (A9.12 S5.8)
BUS_CEILING_W = 1500.0                  # spacecraft / bus ceiling: NEVER an ICP-43 thermal bound (A9.12 S5.1)

RF_ALLOCATION_LABELS = ("not a component rating", "not a demonstrated flight operating point",
                        "not the ICP-43 total-module bound", "not a substitute for measured delivered RF power")
MOUNT_HEAT_LABEL = ("owner design allocation until the spacecraft thermal ICD exists - not a claimed spacecraft "
                    "requirement (A9.12 S5.4)")

DISSIPATED_CATEGORIES = ("discharge", "rf_match", "coil", "cathode", "collector", "plume_interception",
                         "other_dissipative")
ENVIRONMENTAL_CATEGORIES = ("solar", "albedo", "outgoing_ir")
LIMIT_CLASSES = ("SUPPLIER_PROVISIONAL", "T_VALIDATED_CONTINUOUS")
PROVISIONAL_ALLOWED_USES = ("preliminary_thermal_screening", "equipment_protection", "design_sensitivity",
                            "procurement_down_selection")
CLOSURE_USES = ("design_closure", "flight_closure", "lock1_thermal_closure")
INDEPENDENT_BOUND_METHODS = ("global_optimization", "interval_bounding_analysis", "exhaustive_admissible_grid",
                             "demonstrated_bounding_method")
EXCLUSION_REASONS = ("MUTUALLY_EXCLUSIVE_STATES", "KNOWN_CORRELATED_EXTREMES")
CALORIMETRY_ELEMENTS = ("calibrated_temperature_measurements", "registered_thermal_conductances",
                        "registered_thermal_mass", "rf_on_off_comparison", "collector_current_bias_steps")
CORRELATION_PLAN_SLOTS = ("sensor_locations", "measurement_uncertainty", "comparison_quantities",
                          "residual_band", "sensor_placement_contact_treatment")
MODEL_CLASS_A = "LUMPED_H2_5_NETWORK_PLUS_P3_RADIOSITY_ENCLOSURE"


class RuleRefusal(ValueError):
    """An owner rule refuses the request; .code is the fail-closed status (e.g. INCOMPLETE_EVIDENCE,
    NOT_EVALUATED_CORRELATION_PLAN_TBD, OPEN_COATING_LIMIT_NOT_SOURCED)."""

    def __init__(self, code, msg):
        self.code = code
        super().__init__(f"{code}: {msg}")


def _num(rec, key, ctx, units=None):
    if not isinstance(rec, dict) or key not in rec:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", f"{ctx}: {key} missing")
    v = rec[key]
    if v is None or (isinstance(v, str) and v.strip().upper().startswith(("TBD", "PENDING", "REFUSED",
                                                                          "NOT_AVAILABLE"))):
        raise RuleRefusal("INCOMPLETE_EVIDENCE", f"{ctx}: {key} not registered ({v!r})")
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
        raise RuleRefusal("INCOMPLETE_EVIDENCE", f"{ctx}: {key} is not a finite real number ({v!r})")
    if units is not None and rec.get("units") != units:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", f"{ctx}: units {rec.get('units')!r} != {units!r}")
    return float(v)


def _registered(rec, ctx, need=("source",)):
    if not isinstance(rec, dict):
        raise RuleRefusal("INCOMPLETE_EVIDENCE", f"{ctx}: no registered record")
    miss = [k for k in need if not rec.get(k)]
    if miss:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", f"{ctx}: registration incomplete, missing {miss}")
    return rec


def _margin_fixed(margin):
    if margin != HEAT_LOAD_MARGIN:
        raise RuleRefusal("OWNER_RULE_VIOLATION", f"heat-load margin {margin!r} != {HEAT_LOAD_MARGIN} (row 86; "
                          "never relaxed or changed - A9.12 S5.1 / S5.6 / S5.8)")


# ============================================================================ A9.8 P3Q-01 - Q_collector evidence routes
def q_collector_evidence(calorimetric=None, probe_cross_check=None):
    """A9.8 S1.7 P3Q-01 option C: the calorimetric collector energy balance is the PRIMARY Q_collector evidence
    (calibrated temperatures, registered conductances / thermal mass, RF-ON / RF-OFF, collector-current / bias steps);
    the Langmuir-probe sheath-model route (T_e, plasma potential) is an independent CROSS-CHECK only.

    calorimetric: {'route': 'CALORIMETRIC_ENERGY_BALANCE', 'Q_collector_W', 'units': 'W', 'u_W', 'source',
                   <every CALORIMETRY_ELEMENTS key -> registration reference>}
    probe_cross_check: optional {'route': 'PROBE_SHEATH_MODEL', 'Q_collector_W', 'u_W', 'units', 'source',
                       'matched_diagnostic_run': bool}
    A probe record offered as the primary route is refused; the cross-check comparison itself needs a registered
    agreement criterion (q_collector_cross_check)."""
    if calorimetric is None:
        if probe_cross_check is not None:
            raise RuleRefusal("PROBE_ROUTE_IS_CROSS_CHECK_ONLY", "the probe / sheath-model route never replaces the "
                              "calorimetric primary Q_collector evidence (A9.8 P3Q-01)")
        raise RuleRefusal("INCOMPLETE_EVIDENCE", "no calorimetric Q_collector record (primary route, A9.8 P3Q-01)")
    if calorimetric.get("route") != "CALORIMETRIC_ENERGY_BALANCE":
        raise RuleRefusal("PROBE_ROUTE_IS_CROSS_CHECK_ONLY" if calorimetric.get("route") == "PROBE_SHEATH_MODEL"
                          else "INCOMPLETE_EVIDENCE",
                          f"primary route must be CALORIMETRIC_ENERGY_BALANCE, got {calorimetric.get('route')!r}")
    _registered(calorimetric, "calorimetric Q_collector", ("source",) + CALORIMETRY_ELEMENTS)
    q = _num(calorimetric, "Q_collector_W", "calorimetric Q_collector", "W")
    u = _num(calorimetric, "u_W", "calorimetric Q_collector uncertainty")
    out = {"primary_route": "CALORIMETRIC_ENERGY_BALANCE", "Q_collector_W": q, "u_W": u,
           "status": "COMPUTED_CONDITIONAL", "cross_check": "NOT_PERFORMED"}
    if probe_cross_check is not None:
        if probe_cross_check.get("route") != "PROBE_SHEATH_MODEL":
            raise RuleRefusal("INCOMPLETE_EVIDENCE", "cross-check record must be route PROBE_SHEATH_MODEL")
        out["cross_check"] = "PROBE_SHEATH_MODEL_RECORDED"
        out["cross_check_matched_diagnostic_run"] = bool(probe_cross_check.get("matched_diagnostic_run"))
        if not out["cross_check_matched_diagnostic_run"]:
            out["cross_check_note"] = ("probe not taken in a matched diagnostic run (owner preference: matched runs, "
                                       "A9.8 P3Q-01) - recorded, never used to replace the calorimetric value")
    return out


def q_collector_cross_check(primary, probe, criterion):
    """Agreement of the probe / sheath-model Q_collector with the calorimetric primary value. The owner set no
    agreement criterion: criterion must be a REGISTERED {'k': number > 0, 'source', 'registered_before_data': True};
    otherwise NOT_EVALUATED_CROSS_CHECK_CRITERION_TBD. A disagreement never replaces or averages the primary."""
    if not isinstance(criterion, dict) or criterion.get("registered_before_data") is not True or \
            not criterion.get("source"):
        raise RuleRefusal("NOT_EVALUATED_CROSS_CHECK_CRITERION_TBD", "probe vs calorimetry agreement criterion not "
                          "registered before the data (owner fixed no number; none is invented)")
    k = _num(criterion, "k", "cross-check criterion")
    if k <= 0:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", "criterion k must be > 0")
    a, ua = _num(primary, "Q_collector_W", "primary"), _num(primary, "u_W", "primary")
    b, ub = _num(probe, "Q_collector_W", "probe"), _num(probe, "u_W", "probe")
    uc = math.hypot(ua, ub)
    if uc <= 0:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", "zero combined uncertainty")
    z = abs(a - b) / uc
    return {"z": z, "k": k, "agreement": "AGREEMENT" if z <= k else "SHEATH_MODEL_DISAGREEMENT",
            "Q_collector_governing_W": a, "governing_route": "CALORIMETRIC_ENERGY_BALANCE",
            "note": "the calorimetric value governs; a disagreement is investigated, never averaged (A9.8 P3Q-01)"}


def icp45_record_probe_admissibility(record):
    """A9.8 P3Q-01: a Langmuir probe must not contaminate an ICP45 capacity record unless its perturbation has first
    been shown negligible. record: {'probe_present': bool, 'perturbation_negligible_evidence': ref or None}."""
    if "probe_present" not in record or not isinstance(record["probe_present"], bool):
        raise RuleRefusal("INCOMPLETE_EVIDENCE", "ICP45 record must declare probe_present (true / false)")
    if not record["probe_present"]:
        return {"icp45_record_admissible_wrt_probe": True, "basis": "no probe present"}
    ev = record.get("perturbation_negligible_evidence")
    if not ev:
        raise RuleRefusal("PROBE_PERTURBATION_NOT_SHOWN_NEGLIGIBLE", "probe present during an ICP45 capacity record "
                          "without prior evidence that its perturbation is negligible (A9.8 P3Q-01)")
    return {"icp45_record_admissible_wrt_probe": True, "basis": "probe perturbation shown negligible: " + str(ev)}


# ============================================================================ A9.12 S5.1 ICPQ-10 - ICP-43 total-module bound
def icp43_total_module_bound(P_fwd_max, P_d_max, margin=HEAT_LOAD_MARGIN, measured_coupled_terms=None):
    """Q_ICP,bound = 1.20 x (P_fwd,max + P_d,max) (A9.12 S5.1, alternative A).

    P_fwd_max: {'value', 'units': 'W', 'source', 'registration': <registered ICP / P2 envelope id>} - the maximum
    ADMITTED RF forward-power operating point of the registered ICP / P2 envelope.
    P_d_max: {'value', 'units': 'W', 'source', 'registration': <registered H-1 discharge-power bound id>}.
    Either missing / TBD -> INCOMPLETE_EVIDENCE. A record whose basis is the 1.5 kW bus ceiling is refused
    (never 1.20 x 1.5 kW). measured_coupled_terms (once P1 / P2 / P3 deposition and loss terms exist): {term: W record}
    replaces the bounding decomposition, with the same 1.20 margin (never relaxed)."""
    _margin_fixed(margin)
    if measured_coupled_terms is not None:
        if not measured_coupled_terms:
            raise RuleRefusal("INCOMPLETE_EVIDENCE", "empty measured coupled-heat-term set")
        tot = 0.0
        for k, rec in sorted(measured_coupled_terms.items()):
            _registered(rec, f"measured term {k}", ("source",))
            if rec.get("evidence_class") != "measured":
                raise RuleRefusal("INCOMPLETE_EVIDENCE", f"term {k} is not a measured deposition / loss term")
            tot += _num(rec, "value", f"measured term {k}", "W")
        return {"basis": "MEASURED_COUPLED_HEAT_TERMS", "Q_ICP_bound_W": HEAT_LOAD_MARGIN * tot,
                "margin": HEAT_LOAD_MARGIN, "status": "COMPUTED_CONDITIONAL",
                "note": "bounding decomposition replaced by measured coupled heat terms; 20 % margin not relaxed"}
    for name, rec in (("P_fwd,max", P_fwd_max), ("P_d,max", P_d_max)):
        _registered(rec, name, ("source", "registration"))
        if rec.get("basis") == "BUS_CEILING" or "1.5 kW" in str(rec.get("source", "")) and \
                "bus" in str(rec.get("source", "")).lower():
            raise RuleRefusal("OWNER_RULE_VIOLATION", f"{name}: the 1.5 kW spacecraft / bus ceiling never becomes an "
                              "ICP thermal bound (A9.12 S5.1: never 1.20 x 1.5 kW)")
    pf = _num(P_fwd_max, "value", "P_fwd,max", "W")
    pd = _num(P_d_max, "value", "P_d,max", "W")
    if pf < 0 or pd < 0:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", "negative power bound")
    return {"basis": "BOUNDING_DECOMPOSITION_1_20_X_PFWD_MAX_PLUS_PD_MAX", "P_fwd_max_W": pf, "P_d_max_W": pd,
            "Q_ICP_bound_W": HEAT_LOAD_MARGIN * (pf + pd), "margin": HEAT_LOAD_MARGIN,
            "status": "COMPUTED_CONDITIONAL",
            "note": "deliberately conservative thermal bounding rule, not a statement that all electrical input power "
                    "is deposited in one ICP component (A9.12 S5.1)"}


# ============================================================================ A9.12 S5.6 OQ-A907-09 - margin on dissipated loads only
def apply_heat_load_margin(loads, margin=HEAT_LOAD_MARGIN):
    """loads: [{'name', 'category', 'value', 'units': 'W', 'source', ('envelope_case' for environmental),
    ('enlarged_bound_source' optional)}]. Dissipated categories x 1.20; environmental categories are NOT multiplied
    and must name their registered hot / cold envelope case; an untagged load is refused; an environmental load with a
    margin request is refused (an inadequate environmental bound is enlarged explicitly via its own record)."""
    _margin_fixed(margin)
    out = []
    for ld in loads:
        _registered(ld, f"load {ld.get('name')!r}", ("name", "source"))
        cat = ld.get("category")
        v = _num(ld, "value", f"load {ld['name']}", "W")
        if cat in DISSIPATED_CATEGORIES:
            out.append({"name": ld["name"], "category": cat, "value_W": v, "design_W": HEAT_LOAD_MARGIN * v,
                        "treatment": "x1.20 (dissipated / internal load)"})
        elif cat in ENVIRONMENTAL_CATEGORIES:
            if ld.get("apply_margin"):
                raise RuleRefusal("OWNER_RULE_VIOLATION", f"{ld['name']}: no blanket 1.20 on environmental loads "
                                  "(A9.12 S5.6); enlarge the registered bound explicitly instead")
            if not ld.get("envelope_case"):
                raise RuleRefusal("INCOMPLETE_EVIDENCE", f"{ld['name']}: environmental load must name its registered "
                                  "hot / cold envelope case")
            out.append({"name": ld["name"], "category": cat, "value_W": v, "design_W": v,
                        "treatment": "registered hot / cold envelope case " + str(ld["envelope_case"]) +
                                     ("; explicitly enlarged bound: " + ld["enlarged_bound_source"]
                                      if ld.get("enlarged_bound_source") else "")})
        else:
            raise RuleRefusal("INCOMPLETE_EVIDENCE", f"{ld['name']}: category {cat!r} not declared dissipated "
                              f"{DISSIPATED_CATEGORIES} or environmental {ENVIRONMENTAL_CATEGORIES}")
    return out


# ============================================================================ A9.12 S5.3 OQ-A907-05 / S5.5 OQ-A907-08 - node limits
def node_limit(limit):
    """A temperature-limit record: {'node', 'limit_class' in LIMIT_CLASSES, 'T_limit_C', 'source'} ('T_limit_C' may
    be TBD). Coating nodes additionally need 'coating_system' = {'coating', 'substrate', 'application'} (the actual
    selected system, not a generic family name); otherwise the coating limit is OPEN."""
    node = limit.get("node")
    if limit.get("is_coating"):
        cs = limit.get("coating_system") or {}
        miss = [k for k in ("coating", "substrate", "application") if not cs.get(k)]
        if miss or limit.get("T_limit_C") is None or isinstance(limit.get("T_limit_C"), str):
            return {"node": node, "limit_state": "OPEN_COATING_LIMIT_NOT_SOURCED", "missing": miss,
                    "note": "coating node limit T_op <= T_validated,continuous - 50 K applies once sourced / validated "
                            "for the actual coating / substrate / application system (A9.12 S5.5)"}
    if limit.get("limit_class") not in LIMIT_CLASSES:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", f"{node}: limit_class {limit.get('limit_class')!r} not in "
                          f"{LIMIT_CLASSES}")
    t = limit.get("T_limit_C")
    if t is None or isinstance(t, str):
        return {"node": node, "limit_state": "OPEN_LIMIT_NOT_REGISTERED"}
    _registered(limit, f"limit {node}", ("source",))
    if limit["limit_class"] == "SUPPLIER_PROVISIONAL":
        return {"node": node, "limit_state": "PROVISIONAL_SUPPLIER_RATING", "T_limit_C": float(t),
                "allowed_uses": list(PROVISIONAL_ALLOWED_USES),
                "note": "never T_validated,continuous; dependent results UNRESOLVED / conditional (A9.12 S5.3)"}
    if not limit.get("validation_evidence"):
        raise RuleRefusal("INCOMPLETE_EVIDENCE", f"{node}: T_VALIDATED_CONTINUOUS needs validation_evidence")
    return {"node": node, "limit_state": "T_VALIDATED_CONTINUOUS", "T_limit_C": float(t)}


def limit_use_check(limit_state, use):
    """A9.12 S5.3: a provisional supplier rating may serve screening / equipment protection / sensitivity /
    procurement down-selection only - never design / flight / LOCK-1 closure."""
    st = limit_state["limit_state"]
    if use in CLOSURE_USES and st != "T_VALIDATED_CONTINUOUS":
        raise RuleRefusal("UNRESOLVED_PROVISIONAL_OR_OPEN_LIMIT", f"{limit_state['node']}: {st} cannot support {use}")
    if st == "PROVISIONAL_SUPPLIER_RATING" and use not in PROVISIONAL_ALLOWED_USES + CLOSURE_USES:
        raise RuleRefusal("OWNER_RULE_VIOLATION", f"use {use!r} not an allowed provisional use")
    return True


def node_margin(T_op_C, limit_state, margin_K=TEMPERATURE_MARGIN_K):
    """Per-node >= 50 K margin evaluation. Never PASS: MARGIN_MET_CONDITIONAL / MARGIN_NOT_MET, or
    UNRESOLVED_* when the limit is provisional / open (OQ-A907-05 / OQ-A907-08)."""
    if margin_K != TEMPERATURE_MARGIN_K:
        raise RuleRefusal("OWNER_RULE_VIOLATION", "the 50 K margin is never relaxed (A9.12 S5.2)")
    st = limit_state["limit_state"]
    if st.startswith("OPEN"):
        return {"node": limit_state["node"], "margin_class": "UNRESOLVED_LIMIT_OPEN", "limit_state": st}
    margin = limit_state["T_limit_C"] - TEMPERATURE_MARGIN_K - T_op_C
    cls = "MARGIN_MET_CONDITIONAL" if margin >= 0 else "MARGIN_NOT_MET"
    if st == "PROVISIONAL_SUPPLIER_RATING":
        cls = "UNRESOLVED_CONDITIONAL_ON_PROVISIONAL_LIMIT" + ("" if margin >= 0 else "_MARGIN_NOT_MET")
    return {"node": limit_state["node"], "T_op_C": T_op_C, "design_ceiling_C": limit_state["T_limit_C"] -
            TEMPERATURE_MARGIN_K, "margin_to_ceiling_K": margin, "margin_class": cls, "limit_state": st}


# ============================================================================ A9.12 S5.2 OQ-A907-03 - admissible bounding corners
def admissible_corners(factors, declaration):
    """factors: {factor: (adverse levels...)} ; declaration: {'registered_before_evaluation': True, 'source',
    'exclusions': [{'when': {factor: level, ...}, 'reason' in EXCLUSION_REASONS, 'source'}]}.
    Returns (admissible, excluded) corner lists. Combinations are excluded ONLY by a registered exclusion with a
    reason (mutually exclusive states / known correlated extremes) and a source; an unregistered declaration refuses
    (NOT_EVALUATED_ADMISSIBILITY_TBD)."""
    if not isinstance(declaration, dict) or declaration.get("registered_before_evaluation") is not True or \
            not declaration.get("source"):
        raise RuleRefusal("NOT_EVALUATED_ADMISSIBILITY_TBD", "joint-state admissibility declaration not registered "
                          "before the bounding evaluation (A9.12 S5.2)")
    if not factors:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", "no bounding factors registered")
    excl = declaration.get("exclusions", [])
    for e in excl:
        if e.get("reason") not in EXCLUSION_REASONS or not e.get("source") or not e.get("when"):
            raise RuleRefusal("INCOMPLETE_EVIDENCE", f"exclusion {e!r} needs 'when', a reason in {EXCLUSION_REASONS} "
                              "and a source")
        for f, lv in e["when"].items():
            if f not in factors or lv not in factors[f]:
                raise RuleRefusal("INCOMPLETE_EVIDENCE", f"exclusion refers to unknown factor / level {f}={lv!r}")
    names = sorted(factors)
    adm, exc = [], []
    for combo in itertools.product(*(factors[n] for n in names)):
        c = dict(zip(names, combo))
        hit = [e for e in excl if all(c[f] == lv for f, lv in e["when"].items())]
        (exc if hit else adm).append({"corner": c, "excluded_by": [h["reason"] + " (" + h["source"] + ")"
                                                                    for h in hit]} if hit else c)
    if not adm:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", "every corner excluded: declaration inconsistent")
    return adm, exc


def bounding_case_evaluation(case, temperature_limited_nodes, node_temperatures_C, limits, margin=HEAT_LOAD_MARGIN):
    """One admissible bounding case (A9.12 S5.2): the registered dissipated-load margin applied, the environmental
    hot / cold boundary named, EVERY temperature-limited node evaluated against T_validated,continuous - 50 K.
    case: {'corner': {...}, 'dissipated_margin_applied': 1.20, 'environment_boundary': 'HOT'|'COLD'}."""
    _margin_fixed(case.get("dissipated_margin_applied"))
    _margin_fixed(margin)
    if case.get("environment_boundary") not in ("HOT", "COLD"):
        raise RuleRefusal("INCOMPLETE_EVIDENCE", "environmental hot / cold boundary not named")
    if not temperature_limited_nodes:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", "no temperature-limited node list registered")
    miss = [n for n in temperature_limited_nodes if n not in node_temperatures_C or n not in limits]
    if miss:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", f"temperature-limited nodes not evaluated: {miss}")
    rows = [node_margin(float(node_temperatures_C[n]), node_limit(limits[n])) for n in temperature_limited_nodes]
    return {"corner": case.get("corner"), "environment_boundary": case["environment_boundary"], "nodes": rows,
            "status": "COMPUTED_CONDITIONAL", "closure": "UNRESOLVED"}


# ============================================================================ A9.12 S5.4 OQ-A907-06 - mount heat
def mount_heat_report(Q_mount_W, spacecraft_icd=None):
    """Reports a steady conducted mount heat against all three owner allocations (25 / 50 / 100 W); the 50 W
    allocation governs (provisional) until the spacecraft thermal ICD supplies the allowable interface heat
    (spacecraft_icd = {'value', 'units': 'W', 'source'}). Meeting only 100 W is NOT closed. Never PASS."""
    q = float(Q_mount_W)
    if not math.isfinite(q) or q < 0:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", "mount heat must be a finite non-negative W value")
    cases = {k: {"allocation_W": v, "within": q <= v} for k, v in MOUNT_HEAT_ALLOCATION_W.items()}
    if spacecraft_icd is not None:
        _registered(spacecraft_icd, "spacecraft thermal ICD", ("source",))
        gov = _num(spacecraft_icd, "value", "spacecraft thermal ICD", "W")
        gov_src = "SPACECRAFT_THERMAL_ICD"
    else:
        gov, gov_src = MOUNT_HEAT_ALLOCATION_W["governing_provisional"], "OWNER_ALLOCATION_50W_PROVISIONAL"
    if q <= gov:
        cls = "WITHIN_GOVERNING_ALLOCATION_CONDITIONAL"
    elif q <= MOUNT_HEAT_ALLOCATION_W["contingency_sensitivity"]:
        cls = "ONLY_WITHIN_100W_CONTINGENCY_NOT_CLOSED"
    else:
        cls = "EXCEEDS_100W_CONTINGENCY"
    return {"Q_mount_W": q, "governing_W": gov, "governing_source": gov_src, "classification": cls,
            "sensitivity_cases": cases, "label": MOUNT_HEAT_LABEL, "status": "COMPUTED_CONDITIONAL"}


# ============================================================================ A9.12 S5.7 OQ-A907-10 - SEARCH_SENSITIVE
def search_sensitivity(result_status, margin_to_ceiling_after_allowance_K, allowance):
    """Label only: margin after the REGISTERED search allowance < 10 K -> SEARCH_SENSITIVE; the status is returned
    unchanged; no new 10 K requirement. allowance = {'value_K', 'registered_before_outcome': True, 'source'}."""
    if not isinstance(allowance, dict) or allowance.get("registered_before_outcome") is not True or \
            not allowance.get("source"):
        raise RuleRefusal("NOT_EVALUATED_SEARCH_ALLOWANCE_TBD", "search allowance not registered before the outcome")
    _num(allowance, "value_K", "search allowance")
    m = float(margin_to_ceiling_after_allowance_K)
    return {"status": result_status, "labels": ["SEARCH_SENSITIVE"] if m < SEARCH_SENSITIVE_SCREEN_K else [],
            "margin_after_allowance_K": m, "screen_K": SEARCH_SENSITIVE_SCREEN_K,
            "note": "screening label only: status unchanged, does not replace the 50 K margin, no 10 K requirement"}


def lock1_use_of_search_result(labelled, independent_bound=None, allowance_used_K=None, allowance=None):
    """Before LOCK-1 use, a SEARCH_SENSITIVE result needs an independent bounding check (global optimisation /
    interval bounding / exhaustive admissible grid / demonstrated bounding method); the more adverse margin governs;
    the search allowance is never increased after the outcome."""
    if allowance is not None and allowance_used_K is not None and \
            float(allowance_used_K) > float(allowance.get("value_K", math.inf)):
        raise RuleRefusal("OWNER_RULE_VIOLATION", "search allowance increased after the outcome (A9.12 S5.7)")
    if "SEARCH_SENSITIVE" not in labelled["labels"]:
        return {"lock1_usable_wrt_search": True, "governing_margin_K": labelled["margin_after_allowance_K"],
                "status": labelled["status"]}
    if not isinstance(independent_bound, dict) or independent_bound.get("method") not in INDEPENDENT_BOUND_METHODS \
            or not independent_bound.get("source"):
        raise RuleRefusal("NOT_EVALUATED_INDEPENDENT_BOUND_REQUIRED", "SEARCH_SENSITIVE result without an "
                          f"independent bounding check by one of {INDEPENDENT_BOUND_METHODS}")
    mb = _num(independent_bound, "margin_K", "independent bound")
    gov = min(mb, labelled["margin_after_allowance_K"])
    return {"lock1_usable_wrt_search": True, "governing_margin_K": gov,
            "governing_source": "independent_bound" if mb < labelled["margin_after_allowance_K"] else "search",
            "status": labelled["status"]}


# ============================================================================ A9.12 S5.8 OQ-A910-06 - RF-path heat allocation
def rf_allocation_record():
    return {"Q_RF_allocation_W": Q_RF_ALLOCATION_W, "derivation": "500 W x 1.20 = 600 W",
            "status": "TEMPORARY_ALLOCATION_UNTIL_P2", "labels": list(RF_ALLOCATION_LABELS),
            "additional": "P_line/match,loss remains additional where applicable",
            "superseded_by": "P2-derived RF thermal envelope (P_delivered, line / matching losses, antenna / plasma "
                             "loading, uncertainty) x 1.20"}


RF_ALLOCATION_FORBIDDEN_USES = ("component_rating", "flight_operating_point", "icp43_total_module_bound",
                                "delivered_rf_power")


def rf_thermal_basis(p2_envelope=None, P_line_match_loss=None, use="rf_path_thermal_input"):
    """RF-path thermal input. Before P2: the temporary 600 W allocation PLUS P_line/match,loss (registered record;
    missing -> INCOMPLETE_EVIDENCE for the total). After P2 (p2_envelope with VERIFIED P_delivered, line / matching
    loss and antenna / plasma loading records, each with an upper bound including its uncertainty): 1.20 x
    (P_delivered upper + loss upper); the 600 W allocation is superseded. The allocation is never used as a rating,
    flight point, ICP-43 bound or delivered power."""
    if use in RF_ALLOCATION_FORBIDDEN_USES:
        raise RuleRefusal("OWNER_RULE_VIOLATION", f"the 600 W allocation is not usable as {use} (A9.12 S5.8)")
    if p2_envelope is not None:
        need = ("P_delivered", "line_match_loss", "antenna_plasma_loading")
        miss = [k for k in need if k not in p2_envelope]
        if miss:
            raise RuleRefusal("INCOMPLETE_EVIDENCE", f"P2 RF thermal envelope incomplete: {miss}")
        for k in need:
            r = p2_envelope[k]
            _registered(r, f"P2 {k}", ("source", "uncertainty_basis"))
            if r.get("status") != "VERIFIED":
                raise RuleRefusal("INCOMPLETE_EVIDENCE", f"P2 {k} not VERIFIED (status {r.get('status')!r})")
        pdel = _num(p2_envelope["P_delivered"], "upper_bound_incl_uncertainty_W", "P2 P_delivered")
        loss = _num(p2_envelope["line_match_loss"], "upper_bound_incl_uncertainty_W", "P2 line / match loss")
        return {"basis": "P2_DERIVED_RF_THERMAL_ENVELOPE", "Q_RF_thermal_W": HEAT_LOAD_MARGIN * (pdel + loss),
                "allocation_600W": "SUPERSEDED", "status": "COMPUTED_CONDITIONAL",
                "note": "antenna / plasma loading locates P_delivered; it is not added again"}
    rec = rf_allocation_record()
    if P_line_match_loss is None:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", "600 W allocation + P_line/match,loss: the loss term is not "
                          "registered (TBD_AFTER_IMPEDANCE_MAP); the allocation alone is not the RF-path total")
    pl = _num(P_line_match_loss, "value", "P_line/match,loss", "W")
    return dict(rec, basis="TEMPORARY_600W_ALLOCATION_PLUS_LINE_MATCH_LOSS",
                Q_RF_thermal_W=Q_RF_ALLOCATION_W + pl, status="COMPUTED_CONDITIONAL")


# ============================================================================ A9.12 S5.9 P3Q-02 - model class A + correlation
def correlation_plan_check(plan):
    """Model class A (lumped H2-5 network + P3 radiosity enclosure) is accepted for LOCK-1 conditionally. The
    correlation plan must register, BEFORE the correlation data are evaluated: sensor locations, measurement
    uncertainty, model-to-test comparison quantities, admissible residual band, sensor placement / contact treatment.
    Missing -> NOT_EVALUATED_CORRELATION_PLAN_TBD (no band is invented here)."""
    if not isinstance(plan, dict):
        raise RuleRefusal("NOT_EVALUATED_CORRELATION_PLAN_TBD", "no correlation plan registered")
    miss = [s for s in CORRELATION_PLAN_SLOTS if plan.get(s) in (None, "", [], {}) or
            (isinstance(plan.get(s), str) and plan[s].upper().startswith("TBD"))]
    if miss or plan.get("registered_before_correlation_data") is not True:
        raise RuleRefusal("NOT_EVALUATED_CORRELATION_PLAN_TBD",
                          f"correlation plan slots not registered before the data: {miss or ['registration time']}")
    band = plan["residual_band"]
    if not isinstance(band, dict) or "abs_K" not in band or not isinstance(band["abs_K"], (int, float)) or \
            band["abs_K"] <= 0:
        raise RuleRefusal("NOT_EVALUATED_CORRELATION_PLAN_TBD", "residual band must be a registered {'abs_K': > 0}")
    return {"model_class": MODEL_CLASS_A, "plan": "REGISTERED"}


def correlation_outcome(plan, residuals_K, unrepresentable_gradients_or_hot_spots):
    """Correlation of model class A against the integrated test article. Any |residual| beyond the registered band
    or demonstrated gradients / hot spots the lumped nodes cannot represent -> ESCALATE_TO_FINER_MODEL_MANDATORY
    (a finer multi-node / FE model before any LOCK-1 thermal closure claim). Never a PASS."""
    correlation_plan_check(plan)
    if not isinstance(unrepresentable_gradients_or_hot_spots, bool):
        raise RuleRefusal("INCOMPLETE_EVIDENCE", "gradient / hot-spot finding must be declared true / false")
    if not residuals_K:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", "no residuals at the registered comparison quantities")
    missing = [k for k in plan["comparison_quantities"] if k not in residuals_K]
    if missing:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", f"comparison quantities without residual: {missing}")
    band = float(plan["residual_band"]["abs_K"])
    out = [k for k, r in residuals_K.items() if abs(float(r)) > band]
    if out or unrepresentable_gradients_or_hot_spots:
        return {"outcome": "ESCALATE_TO_FINER_MODEL_MANDATORY", "outside_band": sorted(out),
                "unrepresentable_gradients_or_hot_spots": unrepresentable_gradients_or_hot_spots,
                "lock1_thermal_closure_with_model_class_A": "BLOCKED", "status": "COMPUTED_CONDITIONAL"}
    return {"outcome": "CORRELATED_WITHIN_REGISTERED_BAND", "outside_band": [],
            "lock1_thermal_closure_with_model_class_A": "ADMISSIBLE_MODEL_CLASS (closure itself still needs every "
                                                        "other gate; ICP_COUPLED_THERMAL UNRESOLVED until then)",
            "status": "COMPUTED_CONDITIONAL"}
