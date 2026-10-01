#!/usr/bin/env python3
"""A9.16 step 1 - owner rules of 2026-10-01 for the P4 anode / collector / filter materials programme (pure functions).

Implements, fail-closed, the owner decisions A9.12 P4-OQ-01 .. P4-OQ-05 (S5.10 .. S5.14) and A9.13 F2-OQ-04 (S6.6,
APP-FILTER; with the S6.3 / S6.4 filter baseline it refers to). The verbatim records under docs/decisions/ govern over
their json summaries. No file I/O, no global state, not wired into abep_sim/archengine.py.

Owner-supplied numbers used here: none beyond the existing 50 K margin of p4_screening (row 87 / row 86). Every
number the owner deferred to a later registration - the stage-1 exposure conditions and acceptance metrics, the LOCK-2
thresholds (resistance rise, mass loss / recession, sputter / erosion acceptance, duration / fluence, uncertainty
treatment, acceptance logic), the metrology capability, the FeCrAl grade, the graphite grade, the MMO coating system
and substrate, the collector bias magnitude, the filter acceptance values - is a registration slot: an unregistered
slot refuses (RuleRefusal with a NOT_EVALUATED_* / NOT_ADMITTED_* / INCOMPLETE_EVIDENCE code). Nothing here selects a
material, and nothing here ever returns PASS; the final anode / collector / filter material stays OPEN.
"""
from __future__ import annotations

import math

# ============================================================================ vocabulary
# A9.12 S5.10 P4-OQ-01 - staged evidence hierarchy for T_validated,continuous
STAGE_1 = "STAGE_1_COUPON_SCREENING"
STAGE_2 = "STAGE_2_INTEGRATED_REPLACEABLE_COMPONENT_CONFIRMATION"
STAGE_3 = "STAGE_3_QUALIFICATION_LIFE_EVIDENCE"
STAGES = (STAGE_1, STAGE_2, STAGE_3)
STAGE_RESULT = {
    STAGE_1: "COUPON_SUPPORTED_PROVISIONAL_LIMIT",   # design screening only; not a flight-life qualification
    STAGE_2: "T_VALIDATED_CONTINUOUS",               # usable for the P3 / LOCK-1 material-temperature closure
    STAGE_3: "FLIGHT_LIFE_QUALIFIED_LIMIT",          # needed before a final flight-life claim
}
STAGE_1_CONDITIONS = ("atmosphere_species", "temperature", "electrical_bias_current_condition", "exposure_duration",
                      "thermal_cycling")
STAGE_1_METRICS = ("electrical", "oxidation_recession", "mass_loss", "surface_material")
STAGE_2_ENVIRONMENT = ("plasma_environment", "electrical_environment", "thermal_environment")
NON_VALIDATION_BASES = ("MELTING_POINT", "SHORT_VENDOR_EXPOSURE", "GENERIC_AIR_USE_TEMPERATURE", "BRIEF_COUPON_TEST",
                        "SUPPLIER_CONTINUOUS_RATING")
LIMIT_USES = {
    "design_screening": STAGE_1,
    "p3_lock1_material_temperature_closure": STAGE_2,
    "final_flight_life_claim": STAGE_3,
}
APPLICATIONS_STAGE_2 = ("APP-ANODE", "APP-COLLECTOR")

# A9.12 S5.11 P4-OQ-02 - Q0 screening matrix
Q0_ROLES = ("CANDIDATE", "ADDITIONAL_COMPARISON_IF_READILY_AVAILABLE", "ENGINEERING_REFERENCE_CONTROL_ONLY",
            "NEGATIVE_REFERENCE_CONTROL_ONLY", "REFERENCE_CONTROL")
CONTROL_ROLES = ("ENGINEERING_REFERENCE_CONTROL_ONLY", "NEGATIVE_REFERENCE_CONTROL_ONLY", "REFERENCE_CONTROL")
COATING_RECORD_FIELDS = ("coating_composition", "thickness", "deposition_process", "substrate",
                         "surface_preparation", "lot_process_provenance")
# (q0 id, R8 coupon, material, role, declaration needed before admission, coating?, candidate id in the P4 framework)
Q0_MATRIX = (
    ("Q0-C01", "R8-C01", "316L", "ENGINEERING_REFERENCE_CONTROL_ONLY", None, False, "CAND-01"),
    ("Q0-C02-IN600", "R8-C02", "INCONEL alloy 600", "CANDIDATE", None, False, "CAND-02A"),
    ("Q0-C02-IN625", "R8-C02", "INCONEL alloy 625", "CANDIDATE", None, False, "CAND-02B"),
    ("Q0-C02-H230", "R8-C02", "Haynes 230", "CANDIDATE", None, False, "CAND-02C"),
    ("Q0-C02-X750", "R8-C02", "INCONEL alloy X-750", "ADDITIONAL_COMPARISON_IF_READILY_AVAILABLE",
     "availability", False, "CAND-02D"),
    ("Q0-C03-IN601", "R8-C03", "INCONEL alloy 601", "CANDIDATE", None, False, "CAND-03A"),
    ("Q0-C03-H214", "R8-C03", "Haynes 214", "CANDIDATE", None, False, "CAND-03C"),
    ("Q0-C03-FECRAL", "R8-C03", "FeCrAl (one explicitly specified grade)", "CANDIDATE", "exact_grade", False,
     "CAND-03B"),
    ("Q0-C04", "R8-C04", "Rh-coated 316L", "CANDIDATE", None, True, "CAND-04"),
    ("Q0-C05", "R8-C05", "Pt-clad / plated 316L", "CANDIDATE", None, True, "CAND-05"),
    ("Q0-C06", "R8-C06", "Cr-plated 316L", "CANDIDATE", None, True, "CAND-06"),
    ("Q0-C07", "R8-C07", "IrO2 / RuO2-type conductive-oxide / MMO coating", "CANDIDATE", "coating_system_and_substrate",
     True, "CAND-07"),
    ("Q0-C08", "R8-C08", "bare tungsten", "NEGATIVE_REFERENCE_CONTROL_ONLY", None, False, "CAND-08"),
    ("Q0-C09", "R8-C09", "isotropic graphite (specified grade)", "REFERENCE_CONTROL", "exact_grade", False, "CAND-09"),
)
# (id, material, P4 candidate id) - never in the baseline Q0 / Q1 campaign now; activation needs a specific hypothesis
RESERVE = (
    ("RES-TI", "titanium", "CAND-13"),
    ("RES-TIN-ZRN", "TiN / ZrN coatings", "CAND-14"),
    ("RES-CU", "bulk copper", "CAND-11"),
    ("RES-IR", "bulk iridium", "CAND-12"),
)
# generic Hastelloy without an exact grade is never admitted (owner: "an exact grade must be declared before admission")
GENERIC_GRADE_REFUSED = (("Q0-C02-HASTELLOY", "R8-C02", "Hastelloy (generic, no exact grade)", "CAND-02E"),)

# A9.12 S5.12 P4-OQ-03 - LOCK-2 after metrology commissioning, before acceptance-bearing exposure
METROLOGY_SLOTS = ("resistance_repeatability_resolution", "mass_change_detection_limit",
                   "profilometry_recession_resolution", "sem_xps_capability", "coupon_to_coupon_process_repeatability",
                   "ao_ion_exposure_dosimetry")
COMMISSIONING_ARTICLES = ("standard", "blank", "control", "sacrificial_commissioning_coupon")
LOCK2_THRESHOLD_SLOTS = ("resistance_rise_threshold", "mass_loss_recession_limits", "sputtering_erosion_acceptance",
                         "exposure_duration_fluence", "uncertainty_treatment", "acceptance_rejection_logic")
LOCK2_NUMERIC_SLOTS = ("resistance_rise_threshold", "mass_loss_recession_limits", "sputtering_erosion_acceptance",
                       "exposure_duration_fluence")
# which metrology capability must resolve which numeric threshold (necessary condition only)
THRESHOLD_METROLOGY = {
    "resistance_rise_threshold": "resistance_repeatability_resolution",
    "mass_loss_recession_limits": "mass_change_detection_limit",
    "sputtering_erosion_acceptance": "profilometry_recession_resolution",
    "exposure_duration_fluence": "ao_ion_exposure_dosimetry",
}

# A9.12 S5.13 P4-OQ-04 - species-resolved sputtering data: BOTH acquisition and project measurement
ACQUISITION_SPECIES = ("N+", "N2+", "O+", "O2+")
LAWFUL_ROUTES = ("library_access", "inter_library_loan", "publisher_purchase", "institutional_subscription",
                 "other_legitimate_licensed_route")
LITERATURE_USES = ("prior_bounds", "test_matrix_selection", "comparison", "model_initialization")
CANDIDATE_EVIDENCE_USE = "candidate_specific_evidence"
SPUTTER_CONDITION_FIELDS = ("species", "energy_eV", "angle_deg", "target_material")
TARGET_KINDS = ("ELEMENTAL", "ALLOY", "COATING")

# A9.12 S5.14 P4-OQ-05 - collector coupons: negative bias + floating control; polarity frozen
COLLECTOR_SETS = ("NEGATIVE_BIAS_ION_COLLECTING", "FLOATING_MATCHED_CONTROL")
COLLECTOR_POLARITY = "NEGATIVE"

# A9.13 S6.6 F2-OQ-04 (+ S6.3 / S6.4 baseline) - APP-FILTER
FILTER_PLACEMENT = "intake / channel array -> filter -> compressor inlet"
FILTER_TESTS = ("ao_o_exposure", "erosion", "catalytic_recombination_behavior", "particulate_retention",
                "thermal_cycling", "transmission_conductance_effects")
FILTER_BASELINE = "INERT_LOW_RECOMBINATION"
FILTER_CATALYTIC_VARIANT = "CATALYTIC_O_TO_O2_RESEARCH_VARIANT"
CATALYTIC_VARIANT_REQUIREMENTS = ("species_conversion_measurement", "flow_conductance_measurement",
                                  "thermal_material_qualification", "h1_performance_map_on_converted_composition")
FILTER_ACCEPTANCE_SLOTS = ("capture_efficiency_vs_contaminant_class", "species_resolved_propellant_transmission",
                           "pressure_loss_conductance_penalty", "o_recombination_conversion_probability",
                           "retained_contaminant_capacity", "ao_erosion_material_durability", "ag12_feed_state_effect")


class RuleRefusal(ValueError):
    """An owner rule refuses the request; .code is the fail-closed status."""

    def __init__(self, code, msg):
        self.code = code
        super().__init__(f"{code}: {msg}")


def _num(v, ctx):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
        raise RuleRefusal("INCOMPLETE_EVIDENCE", f"{ctx}: not a finite real number ({v!r})")
    return float(v)


def _filled(v):
    if v is None:
        return False
    if isinstance(v, str):
        s = v.strip()
        return bool(s) and not s.upper().startswith(("TBD", "PENDING", "NOT_", "OPEN"))
    return True


def _missing(rec, fields):
    if not isinstance(rec, dict):
        return list(fields)
    return [f for f in fields if not _filled(rec.get(f))]


# ============================================================================ A9.12 S5.10 P4-OQ-01 - staged T_validated
def validation_stage_record(rec):
    """Classify one continuous-use-temperature evidence record under the owner's staged hierarchy.

    rec: {'basis': one of STAGES (or a NON_VALIDATION_BASES value), 'material', 'T_limit_K', 'source',
          'preregistered_acceptance' (LOCK-2 registration ref), 'criteria_met': True,
          stage 1: 'conditions' {STAGE_1_CONDITIONS -> registration ref ('NOT_APPLICABLE' allowed only for
                   thermal_cycling)}, 'metrics' {STAGE_1_METRICS -> ref}, 'preregistered_exposure_duration_h',
                   'exposure_duration_h' (>= the pre-registered duration, else a brief coupon test);
          stage 2: 'stage_1_record' (an accepted stage-1 classification), 'down_selected': True,
                   'configuration': 'REPLACEABLE_ANODE' | 'REPLACEABLE_COLLECTOR', 'article': 'H-1' | 'H-1/ICP',
                   'environment' {STAGE_2_ENVIRONMENT -> ref}, 'at_intended_continuous_use_condition': True;
          stage 3: 'stage_2_record', 'life_basis': 'FULL_DURATION' | 'JUSTIFIED_ACCELERATED', 'justification'
                   (for accelerated)}.
    Returns {'stage', 'limit_class', 'T_limit_K', 'usable_for': [...]}; refuses otherwise."""
    if not isinstance(rec, dict):
        raise RuleRefusal("INCOMPLETE_EVIDENCE", "no evidence record")
    basis = rec.get("basis")
    if basis in NON_VALIDATION_BASES:
        raise RuleRefusal("NOT_CONTINUOUS_USE_VALIDATION", f"{basis} is never continuous-use validation (A9.12 "
                          "S5.10: melting point, short vendor exposure, generic air-use temperature or a brief coupon "
                          "test; A9.12 S5.3: supplier ratings are provisional only)")
    if basis not in STAGES:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", f"unknown evidence basis {basis!r}")
    miss = _missing(rec, ("material", "source", "preregistered_acceptance"))
    if miss:
        raise RuleRefusal("NOT_EVALUATED_ACCEPTANCE_NOT_PREREGISTERED" if "preregistered_acceptance" in miss
                          else "INCOMPLETE_EVIDENCE", f"{basis}: missing {miss}")
    t = _num(rec.get("T_limit_K"), f"{basis} T_limit_K")
    if t <= 0:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", "T_limit_K must be an absolute temperature")
    if rec.get("criteria_met") is not True:
        raise RuleRefusal("NOT_EVALUATED_CRITERIA_NOT_MET", f"{basis}: the pre-registered criteria are not shown met")
    if basis == STAGE_1:
        cond = rec.get("conditions") or {}
        cmiss = [c for c in STAGE_1_CONDITIONS
                 if not (_filled(cond.get(c)) or (c == "thermal_cycling" and cond.get(c) == "NOT_APPLICABLE"))]
        mmiss = _missing(rec.get("metrics"), STAGE_1_METRICS)
        if cmiss or mmiss:
            raise RuleRefusal("NOT_EVALUATED_STAGE_1_CONDITIONS_TBD", f"service-representative conditions {cmiss} / "
                              f"pre-registered metrics {mmiss} not registered")
        pre = _num(rec.get("preregistered_exposure_duration_h"), "pre-registered exposure duration")
        got = _num(rec.get("exposure_duration_h"), "exposure duration")
        if pre <= 0 or got < pre:
            raise RuleRefusal("NOT_CONTINUOUS_USE_VALIDATION", f"exposure {got} h shorter than the pre-registered "
                              f"{pre} h: a brief coupon test")
    elif basis == STAGE_2:
        s1 = rec.get("stage_1_record")
        if not isinstance(s1, dict) or s1.get("stage") != STAGE_1:
            raise RuleRefusal("NOT_EVALUATED_STAGE_1_MISSING", "stage 2 confirms a down-selected stage-1 material")
        if s1.get("material") != rec["material"]:
            raise RuleRefusal("INCOMPLETE_EVIDENCE", "stage-1 record is for a different material")
        if rec.get("down_selected") is not True:
            raise RuleRefusal("NOT_EVALUATED_NOT_DOWN_SELECTED", "stage 2 is for the down-selected material only")
        if rec.get("configuration") not in ("REPLACEABLE_ANODE", "REPLACEABLE_COLLECTOR") or \
                rec.get("article") not in ("H-1", "H-1/ICP"):
            raise RuleRefusal("INCOMPLETE_EVIDENCE", "stage 2 needs a replaceable anode / collector configuration on "
                              "the H-1 / ICP article")
        emiss = _missing(rec.get("environment"), STAGE_2_ENVIRONMENT)
        if emiss or rec.get("at_intended_continuous_use_condition") is not True:
            raise RuleRefusal("INCOMPLETE_EVIDENCE", f"stage 2 environment {emiss} / intended continuous-use condition "
                              "not demonstrated")
    else:
        s2 = rec.get("stage_2_record")
        if not isinstance(s2, dict) or s2.get("stage") != STAGE_2 or s2.get("material") != rec["material"]:
            raise RuleRefusal("NOT_EVALUATED_STAGE_2_MISSING", "stage 3 follows stage-2 confirmation of the material")
        lb = rec.get("life_basis")
        if lb not in ("FULL_DURATION", "JUSTIFIED_ACCELERATED") or \
                (lb == "JUSTIFIED_ACCELERATED" and not _filled(rec.get("justification"))):
            raise RuleRefusal("INCOMPLETE_EVIDENCE", "stage 3 needs full-duration or justified accelerated-life "
                              "evidence")
    usable = [u for u, need in LIMIT_USES.items() if STAGES.index(need) <= STAGES.index(basis)]
    return {"stage": basis, "material": rec["material"], "limit_class": STAGE_RESULT[basis], "T_limit_K": t,
            "usable_for": usable}


def limit_use_check(classified, use):
    """Refuse a use the record's stage does not support: a stage-1 coupon-supported provisional limit is design
    screening only; P3 / LOCK-1 closure needs stage 2; a final flight-life claim needs stage 3."""
    if use not in LIMIT_USES:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", f"unknown use {use!r}")
    if not isinstance(classified, dict) or classified.get("stage") not in STAGES:
        raise RuleRefusal("NOT_CONTINUOUS_USE_VALIDATION", "record not classified by validation_stage_record")
    need = LIMIT_USES[use]
    if STAGES.index(classified["stage"]) < STAGES.index(need):
        raise RuleRefusal("LIMIT_STAGE_INSUFFICIENT_FOR_USE", f"{classified['limit_class']} cannot serve {use} "
                          f"(requires {need})")
    return {"use": use, "limit_class": classified["limit_class"], "T_limit_K": classified["T_limit_K"]}


def gate_admissible_t_validated(prop):
    """For the p4_screening CR-01 gate: a T_validated_continuous property record is gate-admissible only with
    'validation_stage' at stage 2 or later (A9.12 S5.10); returns (ok, reason)."""
    st = prop.get("validation_stage") if isinstance(prop, dict) else None
    if st not in (STAGE_2, STAGE_3):
        return False, (f"validation stage {st!r}: only stage-2 integrated replaceable-component confirmation (or "
                       "later) gives T_validated,continuous for the P3 / LOCK-1 closure (A9.12 P4-OQ-01); a stage-1 "
                       "coupon-supported provisional limit is screening only")
    return True, ""


# ============================================================================ A9.12 S5.11 P4-OQ-02 - Q0 matrix / Q1 down-select
def q0_entry(q0_id):
    for e in Q0_MATRIX:
        if e[0] == q0_id:
            return {"q0_id": e[0], "r8_coupon": e[1], "material": e[2], "role": e[3], "declaration_needed": e[4],
                    "coating": e[5], "candidate": e[6]}
    for e in GENERIC_GRADE_REFUSED:
        if e[0] == q0_id:
            raise RuleRefusal("NOT_ADMITTED_EXACT_GRADE_REQUIRED", f"{e[2]}: no unspecified generic Hastelloy; an "
                              "exact grade must be declared before admission (A9.12 S5.11)")
    for e in RESERVE:
        if e[0] == q0_id:
            raise RuleRefusal("RESERVE_ONLY_NOT_IN_BASELINE_CAMPAIGN", f"{e[1]} is a reserve candidate, not in the "
                              "baseline Q0 / Q1 campaign (A9.12 S5.11)")
    raise RuleRefusal("NOT_IN_OWNER_Q0_MATRIX", f"{q0_id!r} is not in the owner's Q0 matrix")


def q0_admission(q0_id, declaration=None):
    """Admit one Q0 coupon entry. declaration: {'exact_grade', 'availability' (evidence ref that the material is
    readily available), 'coating_system', 'substrate', 'source', and for coatings every COATING_RECORD_FIELDS}.
    Refuses an undeclared grade / coating system, an unavailable X-750, an incomplete coating record. A control role
    is reported as a control, never as a baseline anode candidate."""
    e = q0_entry(q0_id)
    d = declaration or {}
    need = e["declaration_needed"]
    if need == "exact_grade" and not _filled(d.get("exact_grade")):
        raise RuleRefusal("NOT_ADMITTED_GRADE_TBD", f"{e['material']}: the grade must be explicitly declared before "
                          "admission (none is invented)")
    if need == "availability" and not _filled(d.get("availability")):
        raise RuleRefusal("NOT_ADMITTED_AVAILABILITY_TBD", "X-750 is an additional Q0 comparison only if readily "
                          "available (evidence of availability required)")
    if need == "coating_system_and_substrate" and (not _filled(d.get("coating_system")) or
                                                   not _filled(d.get("substrate"))):
        raise RuleRefusal("NOT_ADMITTED_COATING_SYSTEM_TBD", "IrO2 / RuO2 MMO: the exact coating system and substrate "
                          "must be declared")
    if e["coating"]:
        miss = _missing(d, COATING_RECORD_FIELDS)
        if miss:
            raise RuleRefusal("NOT_ADMITTED_COATING_RECORD_INCOMPLETE", f"{e['material']}: coating record lacks {miss}; a "
                              "coating family name alone is insufficient")
    if need is not None and not _filled(d.get("source")):
        raise RuleRefusal("INCOMPLETE_EVIDENCE", f"{e['material']}: declaration has no source")
    return dict(e, status="ADMITTED_TO_Q0", is_control=e["role"] in CONTROL_ROLES,
                baseline_anode_candidate=False if e["role"] in CONTROL_ROLES else "OPEN_PENDING_EVIDENCE")


def reserve_activation(res_id, hypothesis=None):
    """Reserve candidates (Ti, TiN / ZrN, bulk Cu, bulk Ir) need a specific registered hypothesis / need before
    activation; even then they stay outside the baseline Q0 / Q1 campaign."""
    r = [x for x in RESERVE if x[0] == res_id]
    if not r:
        raise RuleRefusal("NOT_IN_OWNER_Q0_MATRIX", f"{res_id!r} is not a reserve candidate")
    if _missing(hypothesis, ("hypothesis", "need", "source")):
        raise RuleRefusal("RESERVE_ONLY_NOT_IN_BASELINE_CAMPAIGN", f"{r[0][1]}: no registered specific hypothesis / "
                          "need")
    return {"reserve": res_id, "material": r[0][1], "status": "RESERVE_ACTIVATION_REQUESTED_OUTSIDE_BASELINE",
            "hypothesis": hypothesis["hypothesis"]}


def q1_admission(q0_admitted, q0_result):
    """Q1 (electrically loaded plasma exposure, biased / floating) admits only Q0 survivors that meet the
    pre-registered screening criteria. q0_result: {'outcome': 'MEETS_PREREGISTERED_SCREENING_CRITERIA' |
    'FAILS_...' | ..., 'lock2_registration': ref, 'source'}."""
    if not isinstance(q0_admitted, dict) or q0_admitted.get("status") != "ADMITTED_TO_Q0":
        raise RuleRefusal("NOT_ADMITTED_TO_Q0", "Q1 entry requires a Q0-admitted coupon")
    if _missing(q0_result, ("lock2_registration", "source")):
        raise RuleRefusal("NOT_EVALUATED_LOCK2_TBD", "Q0 screening criteria not pre-registered (LOCK-2)")
    if q0_result.get("outcome") != "MEETS_PREREGISTERED_SCREENING_CRITERIA":
        raise RuleRefusal("NOT_A_Q0_SURVIVOR", f"Q0 outcome {q0_result.get('outcome')!r}")
    return {"q0_id": q0_admitted["q0_id"], "status": "ADMITTED_TO_Q1", "is_control": q0_admitted["is_control"],
            "configurations": "biased / floating (applicable to the application)"}


# ============================================================================ A9.12 S5.12 P4-OQ-03 - LOCK-2
def metrology_commissioning(records):
    """records: {slot -> {'capability': number, 'units', 'source', 'articles': [COMMISSIONING_ARTICLES...]}} for every
    METROLOGY_SLOTS ('sem_xps_capability' may be 'NOT_APPLICABLE'). Candidate coupons never serve commissioning."""
    if not isinstance(records, dict):
        raise RuleRefusal("NOT_EVALUATED_METROLOGY_COMMISSIONING_TBD", "no metrology commissioning record")
    out = {}
    for s in METROLOGY_SLOTS:
        r = records.get(s)
        if s == "sem_xps_capability" and r == "NOT_APPLICABLE":
            out[s] = "NOT_APPLICABLE"
            continue
        if _missing(r, ("units", "source")) or not r.get("articles"):
            raise RuleRefusal("NOT_EVALUATED_METROLOGY_COMMISSIONING_TBD", f"slot {s} not commissioned")
        bad = [a for a in r["articles"] if a not in COMMISSIONING_ARTICLES]
        if bad:
            raise RuleRefusal("COMMISSIONING_ON_CANDIDATE_COUPON_REFUSED", f"slot {s}: commissioning articles {bad} "
                              f"(only {COMMISSIONING_ARTICLES})")
        out[s] = {"capability": _num(r.get("capability"), f"metrology {s}"), "units": r["units"],
                  "source": r["source"]}
    return {"status": "COMMISSIONED", "slots": out}


def lock2_freeze(commissioned, thresholds, acceptance_exposures_before=()):
    """Freeze the numerical acceptance at LOCK-2: after commissioning, before ANY acceptance-bearing candidate
    exposure. thresholds: {slot -> {'value' (numeric slots), 'units', 'source', 'derived_from': [...]}}.
    Refuses: commissioning missing; an acceptance-bearing exposure already performed; a threshold derived from
    candidate coupon performance; a threshold the commissioned metrology cannot resolve (NOT_EVALUATED_METROLOGY -
    the criterion is never widened to fit the instrument)."""
    if not isinstance(commissioned, dict) or commissioned.get("status") != "COMMISSIONED":
        raise RuleRefusal("NOT_EVALUATED_METROLOGY_COMMISSIONING_TBD", "LOCK-2 follows metrology commissioning")
    if acceptance_exposures_before:
        raise RuleRefusal("ACCEPTANCE_EXPOSURE_BEFORE_LOCK2_REFUSED", f"acceptance-bearing exposures "
                          f"{list(acceptance_exposures_before)} precede the freeze")
    if not isinstance(thresholds, dict):
        raise RuleRefusal("NOT_EVALUATED_LOCK2_TBD", "no threshold registration")
    frozen = {}
    for s in LOCK2_THRESHOLD_SLOTS:
        t = thresholds.get(s)
        if _missing(t, ("source",)):
            raise RuleRefusal("NOT_EVALUATED_LOCK2_TBD", f"threshold slot {s} not registered (none is invented)")
        der = [str(x) for x in (t.get("derived_from") or [])]
        if any("CANDIDATE" in x.upper() for x in der):
            raise RuleRefusal("THRESHOLD_FROM_CANDIDATE_PERFORMANCE_REFUSED", f"{s} derived from {der}: candidate "
                              "coupon performance never sets the thresholds it must pass")
        if s in LOCK2_NUMERIC_SLOTS:
            v = _num(t.get("value"), f"threshold {s}")
            if v <= 0:
                raise RuleRefusal("INCOMPLETE_EVIDENCE", f"{s} must be > 0")
            m = commissioned["slots"].get(THRESHOLD_METROLOGY[s])
            if not isinstance(m, dict) or m.get("units") != t.get("units"):
                raise RuleRefusal("NOT_EVALUATED_METROLOGY", f"{s}: no commissioned capability in units "
                                  f"{t.get('units')!r}")
            if m["capability"] > v:
                raise RuleRefusal("NOT_EVALUATED_METROLOGY", f"{s}: metrology capability {m['capability']} cannot "
                                  f"resolve the criterion {v} (criterion not widened)")
            frozen[s] = {"value": v, "units": t["units"], "source": t["source"]}
        else:
            frozen[s] = {"rule": t.get("rule"), "source": t["source"]}
            if not _filled(t.get("rule")):
                raise RuleRefusal("NOT_EVALUATED_LOCK2_TBD", f"{s}: rule text not registered")
    return {"status": "LOCK2_FROZEN", "thresholds": frozen}


def threshold_revision(frozen, slot, new_value):
    """After LOCK-2 a threshold is not revised to fit the instrument or the candidates; any change is refused here
    (a genuine model / programme change is a new owner decision and a new registration)."""
    if not isinstance(frozen, dict) or frozen.get("status") != "LOCK2_FROZEN":
        raise RuleRefusal("NOT_EVALUATED_LOCK2_TBD", "no frozen LOCK-2 set")
    old = frozen["thresholds"].get(slot, {}).get("value")
    raise RuleRefusal("THRESHOLD_CHANGE_AFTER_LOCK2_REFUSED", f"{slot}: {old} -> {new_value} refused (A9.12 S5.12)")


# ============================================================================ A9.12 S5.13 P4-OQ-04 - sputter data
def sputter_record_use(rec, use, target_kind):
    """rec: {'origin': 'LITERATURE_ACQUIRED' | 'PROJECT_ION_BEAM_MEASUREMENT', 'route' (literature), 'species',
    'energy_eV', 'angle_deg', 'target_material', 'record_target_kind' in TARGET_KINDS, 'source',
    'materiality_assessment' (optional {'verdict': 'NOT_MATERIAL', 'source'})}; use in LITERATURE_USES or
    CANDIDATE_EVIDENCE_USE; target_kind = kind of the P4 candidate the value is used for.
    Literature serves priors / matrix selection / comparison / model initialisation only; candidate-specific evidence
    comes from project measurement on that candidate. An elemental-target record is never silently used for an alloy
    / coating: without a registered NOT_MATERIAL assessment it is refused; with one it is an explicitly labelled proxy
    for literature uses only."""
    if target_kind not in TARGET_KINDS:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", f"target kind {target_kind!r}")
    miss = _missing(rec, SPUTTER_CONDITION_FIELDS + ("source", "origin", "record_target_kind"))
    if miss:
        raise RuleRefusal("NOT_SPECIES_RESOLVED" if "species" in miss else "INCOMPLETE_EVIDENCE",
                          f"sputter record lacks {miss} (species / energy / angle / material condition required)")
    if rec["species"] not in ACQUISITION_SPECIES + ("Xe+", "Ar+"):
        raise RuleRefusal("NOT_SPECIES_RESOLVED", f"species {rec['species']!r} is not a resolved ion species")
    _num(rec["energy_eV"], "energy_eV")
    _num(rec["angle_deg"], "angle_deg")
    label = []
    if rec["species"] == "Ar+":
        label.append("ENGINEERING_ONLY_AR")
    if rec["origin"] == "LITERATURE_ACQUIRED":
        if rec.get("route") not in LAWFUL_ROUTES:
            raise RuleRefusal("ACQUISITION_ROUTE_NOT_LAWFUL", f"route {rec.get('route')!r} not in {LAWFUL_ROUTES}")
        if use == CANDIDATE_EVIDENCE_USE:
            raise RuleRefusal("LITERATURE_NOT_CANDIDATE_EVIDENCE", "literature yields are priors / matrix selection / "
                              "comparison / model initialisation; candidate-specific evidence is project measurement")
        if use not in LITERATURE_USES:
            raise RuleRefusal("INCOMPLETE_EVIDENCE", f"unknown use {use!r}")
    elif rec["origin"] == "PROJECT_ION_BEAM_MEASUREMENT":
        if use not in LITERATURE_USES + (CANDIDATE_EVIDENCE_USE,):
            raise RuleRefusal("INCOMPLETE_EVIDENCE", f"unknown use {use!r}")
    else:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", f"origin {rec['origin']!r}")
    if target_kind in ("ALLOY", "COATING") and rec["record_target_kind"] == "ELEMENTAL":
        ma = rec.get("materiality_assessment")
        if not isinstance(ma, dict) or ma.get("verdict") != "NOT_MATERIAL" or not _filled(ma.get("source")):
            raise RuleRefusal("ELEMENTAL_SUBSTITUTION_REFUSED", "elemental-target yield used for an alloy / coating "
                              "without a registered assessment that composition / surface chemistry does not "
                              "materially change the interaction")
        if use == CANDIDATE_EVIDENCE_USE:
            raise RuleRefusal("LITERATURE_NOT_CANDIDATE_EVIDENCE", "an elemental proxy is never candidate evidence")
        label.append("EXPLICIT_ELEMENTAL_PROXY")
    elif rec["record_target_kind"] != target_kind and rec["origin"] == "PROJECT_ION_BEAM_MEASUREMENT":
        raise RuleRefusal("INCOMPLETE_EVIDENCE", "project measurement is on a different target kind")
    return {"use": use, "origin": rec["origin"], "species": rec["species"], "labels": label,
            "status": "ADMISSIBLE_FOR_USE_CONDITIONAL"}


# ============================================================================ A9.12 S5.14 P4-OQ-05 - collector coupons
def collector_coupon_exposure(rec):
    """rec: {'set': COLLECTOR_SETS, 'polarity' ('NEGATIVE' for the biased set), 'acceptance_bearing': bool,
    'bias_magnitude_source' {'p1_collector_envelope': ref, 'plasma_sheath_evidence': ref} (acceptance-bearing biased
    exposure), 'p1_complete': bool}. Polarity is frozen negative; the floating set is the matched control; the bias
    magnitude comes from the measured P1 collector envelope and plasma / sheath evidence (never invented); a pre-P1
    biased exposure is fixture / process verification, ENGINEERING_ONLY."""
    if not isinstance(rec, dict) or rec.get("set") not in COLLECTOR_SETS:
        raise RuleRefusal("INCOMPLETE_EVIDENCE", f"collector coupon set must be one of {COLLECTOR_SETS}")
    if rec["set"] == "FLOATING_MATCHED_CONTROL":
        if rec.get("polarity") not in (None, "FLOATING"):
            raise RuleRefusal("POLARITY_FROZEN", "the floating control is not biased")
        return {"set": rec["set"], "classification": "MATCHED_CONTROL"}
    if rec.get("polarity") != COLLECTOR_POLARITY:
        raise RuleRefusal("POLARITY_FROZEN", f"collector coupon polarity is frozen NEGATIVE (ion-collecting service "
                          f"condition), got {rec.get('polarity')!r}")
    if rec.get("p1_complete") is not True:
        if rec.get("acceptance_bearing"):
            raise RuleRefusal("NOT_EVALUATED_BIAS_MAGNITUDE_TBD_P1", "acceptance-bearing biased exposure before the "
                              "P1 collector envelope exists")
        return {"set": rec["set"], "classification": "ENGINEERING_ONLY_FIXTURE_PROCESS_VERIFICATION",
                "note": "not the final service-condition qualification (A9.12 S5.14)"}
    if _missing(rec.get("bias_magnitude_source"), ("p1_collector_envelope", "plasma_sheath_evidence")):
        if rec.get("acceptance_bearing"):
            raise RuleRefusal("NOT_EVALUATED_BIAS_MAGNITUDE_TBD_P1", "bias magnitude / ion energy not derived from the "
                              "measured P1 collector envelope and plasma / sheath evidence")
        return {"set": rec["set"], "classification": "ENGINEERING_ONLY_FIXTURE_PROCESS_VERIFICATION"}
    return {"set": rec["set"], "classification": "ACCEPTANCE_BEARING_SERVICE_POLARITY_CONDITIONAL",
            "bias_magnitude_source": rec["bias_magnitude_source"]}


# ============================================================================ A9.13 S6.6 F2-OQ-04 - APP-FILTER
def filter_material_role(rec):
    """rec: {'recombination_intent': 'INERT_LOW_RECOMBINATION' | 'CATALYTIC_O_TO_O2', 'placement', ...}.
    The baseline filter is inert / low-recombination at intake -> filter -> compressor inlet (A9.13 S6.3 / S6.4 /
    S6.6); a catalytic O -> O2 element is only a separately labelled research variant that needs its own conversion,
    flow / conductance, thermal / material qualification and H-1 map, and never replaces the baseline composition."""
    if not isinstance(rec, dict):
        raise RuleRefusal("INCOMPLETE_EVIDENCE", "no filter material record")
    intent = rec.get("recombination_intent")
    if intent == "INERT_LOW_RECOMBINATION":
        if rec.get("placement") not in (None, FILTER_PLACEMENT):
            raise RuleRefusal("FILTER_PLACEMENT_NOT_BASELINE", f"baseline placement is '{FILTER_PLACEMENT}'")
        return {"role": "APP-FILTER_BASELINE_CANDIDATE", "baseline": FILTER_BASELINE, "tests": list(FILTER_TESTS)}
    if intent == "CATALYTIC_O_TO_O2":
        if rec.get("baseline") is True:
            raise RuleRefusal("CATALYTIC_FILTER_NOT_BASELINE", "a catalytic O -> O2 filter is excluded from the "
                              "baseline (A9.13 S6.4)")
        return {"role": FILTER_CATALYTIC_VARIANT, "baseline": False,
                "requires_own": list(CATALYTIC_VARIANT_REQUIREMENTS), "tests": list(FILTER_TESTS)}
    raise RuleRefusal("INCOMPLETE_EVIDENCE", f"recombination intent {intent!r} not declared")


def filter_acceptance(registration):
    """Quantitative APP-FILTER acceptance is pre-registered before LOCK-1 from the defined contamination environment,
    the H-1 feed requirement and measured filter material / geometry (A9.13 S6.3); no number is defaulted."""
    slots = FILTER_ACCEPTANCE_SLOTS
    miss = _missing(registration, slots)
    if miss:
        raise RuleRefusal("NOT_EVALUATED_FILTER_ACCEPTANCE_TBD", f"filter acceptance slots {miss} not registered "
                          "before LOCK-1")
    return {"status": "FILTER_ACCEPTANCE_REGISTERED", "slots": {s: registration[s] for s in slots}}

