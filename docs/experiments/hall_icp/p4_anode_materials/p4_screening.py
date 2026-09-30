"""P4 anode / collector materials: pure, fail-closed hard-gate screening and Pareto view (fo_a9_6_p4_anode_materials).

Standard library only. No I/O, no defaults, no weighted scalar, no selection.

Rules implemented here (owner A9.2 sec. 3-4, A9.6 sec. 10, owner rows 86/87/106):
  * a hard gate is APPLIED only when BOTH the requirement and the property value are evidenced; otherwise the gate
    outcome is INCOMPLETE_EVIDENCE (never PASS). A property whose applicability domain does not cover the requirement's
    domain gives OUT_OF_DOMAIN (distinct from a gate violation);
  * the continuous-use-temperature gate uses T_operating <= T_validated,continuous - margin (margin 50 K, owner row 87 /
    A9.2); it is applied only when the thermal closure status is on the allow-list RESOLVED_THERMAL_STATUSES and
    T_operating is a quantity record in K with evidence class and source; while ANODE_THERMAL_CLOSURE (anode) or
    ICP_COUPLED_THERMAL (collector) is UNRESOLVED (or any other status) the gate is INCOMPLETE_EVIDENCE whatever numbers
    are supplied;
  * non-finite numbers are never evidence; applicability domains are non-empty lists of strings;
  * a satisfied gate is reported as GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN, never PASS; a candidate whose gates are all
    satisfied is NOT_SCREENED_OUT, never SELECTED;
  * the final material status is OPEN for every input (final_material_status); no function in this module selects;
  * synthetic records are refused unless the caller explicitly runs in synthetic mode, and synthetic and measured /
    published records are never mixed;
  * the Pareto view compares only candidates whose compared values are all populated at the SAME condition; the rest
    are listed as NOT_COMPARABLE_INCOMPLETE_EVIDENCE. It is informational, never a selection.
"""
from __future__ import annotations

import math

GATE_OUTCOMES = (
    "INCOMPLETE_EVIDENCE",
    "OUT_OF_DOMAIN",
    "GATE_VIOLATED_BY_EVIDENCE",
    "GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN",
)
CANDIDATE_SCREENING_STATES = ("INCOMPLETE_EVIDENCE", "SCREENED_OUT_BY_EVIDENCE", "NOT_SCREENED_OUT")
FORBIDDEN_WORDS = ("PASS", "SELECTED", "WINNER", "QUALIFIED")
EVIDENCED_REQUIREMENT_STATUSES = ("OWNER_GIVEN", "DEFINED_FROM_EVIDENCE")
UNRESOLVED_THERMAL = "UNRESOLVED"
# allow-list (consolidated verification TH-03): only an explicitly resolved thermal closure lets the continuous-use-
# temperature gate be applied; UNRESOLVED, PENDING, TBD, OPEN, any spelling variant -> INCOMPLETE_EVIDENCE
RESOLVED_THERMAL_STATUSES = ("CLOSED_BY_EVIDENCE",)
# T_operating must be a quantity record in K with provenance (never a bare number: a degC value passed as K would be
# accepted silently); evidence classes admissible for a gate input (CLAUDE.md rule 10 / docs/EVIDENCE.md)
T_OPERATING_FIELDS = ("value_si", "unit_si", "evidence_class", "source")
T_OPERATING_EVIDENCE_CLASSES = ("measured", "model-derived")
FINAL_MATERIAL_STATUS = "OPEN"
PARETO_LABEL = "INFORMATIONAL_NOT_A_SELECTION"
NOT_COMPARABLE = "NOT_COMPARABLE_INCOMPLETE_EVIDENCE"

REQUIREMENT_FIELDS = ("id", "criterion", "application", "property", "kind", "value", "unit", "status", "source",
                      "domain")
PROPERTY_FIELDS = ("id", "candidate", "property", "value_si", "unit_si", "condition", "domain", "source_id",
                   "locator", "quantity_type", "evidence_level", "admissible_for_gate", "synthetic")
GATE_KINDS = ("min", "max", "min_with_margin")


class ScreeningError(ValueError):
    """Raised for malformed input. Missing inputs raise; nothing is defaulted."""


def _require(rec, fields, what):
    if not isinstance(rec, dict):
        raise ScreeningError(f"{what}: record must be a dict")
    missing = [f for f in fields if f not in rec]
    if missing:
        raise ScreeningError(f"{what} {rec.get('id', '?')}: missing fields {missing}")


def _finite_number(v):
    """A finite real number (bool, NaN and +/-inf are never evidence: consolidated verification SW-05)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def _check_domain(dom, what):
    """An applicability domain is a non-empty list of non-empty strings (a bare string would be compared character by
    character and an empty requirement domain would be covered by anything: SW-05)."""
    if not isinstance(dom, list) or not dom or not all(isinstance(x, str) and x.strip() for x in dom):
        raise ScreeningError(f"{what}: domain must be a non-empty list of non-empty strings, got {dom!r}")
    return set(dom)


def requirement_evidenced(req):
    """A requirement is evidenced only with a finite numeric value, an evidenced status and a source."""
    _require(req, REQUIREMENT_FIELDS, "requirement")
    if req["kind"] not in GATE_KINDS:
        raise ScreeningError(f"requirement {req['id']}: unknown gate kind {req['kind']!r}")
    return (_finite_number(req["value"]) and req["status"] in EVIDENCED_REQUIREMENT_STATUSES and bool(req["source"]))


def property_evidenced(prop):
    """A property is evidenced only with a finite numeric SI value, a source, a locator and admissible_for_gate True."""
    _require(prop, PROPERTY_FIELDS, "property")
    return (_finite_number(prop["value_si"]) and bool(prop["source_id"])
            and bool(prop["locator"]) and prop["admissible_for_gate"] is True)


def operating_temperature_evidenced(t_op):
    """(ok, reason): T_operating is a quantity record {value_si, unit_si 'K', evidence_class, source} with a finite
    value > 0 K and an admissible evidence class; a bare number or anything else is not evidence (TH-03)."""
    if t_op is None:
        return False, "T_operating not evidenced (no quantity record)"
    if not isinstance(t_op, dict):
        return False, f"T_operating must be a quantity record {list(T_OPERATING_FIELDS)}, got {type(t_op).__name__}"
    miss = [k for k in T_OPERATING_FIELDS if t_op.get(k) in (None, "")]
    if miss:
        return False, f"T_operating record lacks {miss}"
    if t_op["unit_si"] != "K":
        return False, f"T_operating unit {t_op['unit_si']!r} is not K (no silent conversion)"
    if not _finite_number(t_op["value_si"]) or t_op["value_si"] <= 0:
        return False, f"T_operating value {t_op['value_si']!r} is not a finite absolute temperature"
    if t_op["evidence_class"] not in T_OPERATING_EVIDENCE_CLASSES:
        return False, f"T_operating evidence class {t_op['evidence_class']!r} not in {T_OPERATING_EVIDENCE_CLASSES}"
    return True, ""


def check_evidence_mode(props, synthetic_mode):
    """Refuse synthetic records outside synthetic mode, and any mix of synthetic and non-synthetic records."""
    flags = set()
    for p in props:
        _require(p, PROPERTY_FIELDS, "property")
        if not isinstance(p["synthetic"], bool):
            raise ScreeningError(f"property {p['id']}: 'synthetic' must be a bool")
        flags.add(p["synthetic"])
    if len(flags) > 1:
        raise ScreeningError("synthetic and measured/published evidence mixed: refused")
    if True in flags and not synthetic_mode:
        raise ScreeningError("synthetic evidence supplied outside synthetic mode: refused")
    if False in flags and synthetic_mode:
        raise ScreeningError("synthetic mode run on non-synthetic evidence: refused")


def evaluate_gate(req, prop, thermal_closure_status=None, operating_temperature=None):
    """Return (outcome, reason). Fail closed: anything not evidenced -> INCOMPLETE_EVIDENCE.

    kind 'min'            : property >= requirement value
    kind 'max'            : property <= requirement value
    kind 'min_with_margin': property - requirement value >= operating_temperature (the continuous-use-temperature gate,
                            requirement value = margin in K, operating_temperature = evidenced T_operating quantity
                            record in K); applied only when thermal_closure_status is in RESOLVED_THERMAL_STATUSES
                            (allow-list; anything else -> INCOMPLETE_EVIDENCE).
    Non-finite values are never evidence; domains must be non-empty lists of strings.
    """
    _require(req, REQUIREMENT_FIELDS, "requirement")
    if prop is None:
        return "INCOMPLETE_EVIDENCE", "property value missing (no record)"
    _require(prop, PROPERTY_FIELDS, "property")
    if prop["property"] != req["property"]:
        raise ScreeningError(f"gate {req['id']}: property {prop['property']} does not match the requirement")
    if not requirement_evidenced(req):
        return "INCOMPLETE_EVIDENCE", f"requirement {req['id']} not evidenced (status {req['status']})"
    if not property_evidenced(prop):
        return "INCOMPLETE_EVIDENCE", f"property {prop['id']} not admissible/evidenced for a gate"
    if req["unit"] != prop["unit_si"]:
        raise ScreeningError(f"gate {req['id']}: unit {req['unit']!r} != property unit {prop['unit_si']!r} (no silent "
                             f"conversion)")
    if not _check_domain(req["domain"], f"requirement {req['id']}") <= _check_domain(prop["domain"],
                                                                                      f"property {prop['id']}"):
        return "OUT_OF_DOMAIN", (f"property domain {sorted(prop['domain'])} does not cover requirement domain "
                                 f"{sorted(req['domain'])}")
    if req["kind"] == "min_with_margin":
        if thermal_closure_status is None:
            raise ScreeningError(f"gate {req['id']}: thermal closure status must be supplied (no default)")
        if thermal_closure_status not in RESOLVED_THERMAL_STATUSES:
            return "INCOMPLETE_EVIDENCE", (f"thermal closure {thermal_closure_status!r} not in "
                                           f"{RESOLVED_THERMAL_STATUSES}: T_operating not evidenced")
        ok_t, why_t = operating_temperature_evidenced(operating_temperature)
        if not ok_t:
            return "INCOMPLETE_EVIDENCE", why_t
        ok = operating_temperature["value_si"] <= prop["value_si"] - req["value"]
    elif req["kind"] == "min":
        ok = prop["value_si"] >= req["value"]
    else:
        ok = prop["value_si"] <= req["value"]
    if ok:
        return "GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN", "both sides evidenced; not a selection"
    return "GATE_VIOLATED_BY_EVIDENCE", "both sides evidenced; gate violated"


def candidate_screening_state(outcomes):
    """Roll per-gate outcomes into a candidate screening state. Never PASS / SELECTED.

    Any violated gate -> SCREENED_OUT_BY_EVIDENCE; else any gate not satisfied (incomplete / out of domain) ->
    INCOMPLETE_EVIDENCE; else NOT_SCREENED_OUT. An empty gate list is INCOMPLETE_EVIDENCE.
    """
    outcomes = list(outcomes)
    for o in outcomes:
        if o not in GATE_OUTCOMES:
            raise ScreeningError(f"unknown gate outcome {o!r}")
    if not outcomes:
        return "INCOMPLETE_EVIDENCE"
    if "GATE_VIOLATED_BY_EVIDENCE" in outcomes:
        return "SCREENED_OUT_BY_EVIDENCE"
    if any(o != "GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN" for o in outcomes):
        return "INCOMPLETE_EVIDENCE"
    return "NOT_SCREENED_OUT"


def final_material_status(_screening_states=None):
    """The final anode / collector material is OPEN for every input (A9.2, A9.6 fixed statuses; owner row 106)."""
    return FINAL_MATERIAL_STATUS


def pareto_view(candidates, values, senses):
    """Non-dominated set over the given objectives. Informational only.

    candidates: list of candidate ids; values: {candidate: {objective: number or None}}; senses: {objective: 'min'|'max'}.
    Candidates with any None / missing objective are NOT_COMPARABLE_INCOMPLETE_EVIDENCE. Returns a dict with
    'label', 'compared', 'non_dominated', 'dominated' ({cand: [dominators]}), 'not_comparable'.
    """
    if not senses:
        raise ScreeningError("pareto_view: no objectives")
    for s in senses.values():
        if s not in ("min", "max"):
            raise ScreeningError(f"pareto_view: unknown sense {s!r}")
    comp, notc = [], []
    for c in candidates:
        row = values.get(c, {})
        if all(isinstance(row.get(o), (int, float)) and not isinstance(row.get(o), bool) for o in senses):
            comp.append(c)
        else:
            notc.append(c)

    def better_or_equal(a, b, o):
        return values[a][o] <= values[b][o] if senses[o] == "min" else values[a][o] >= values[b][o]

    def strictly_better(a, b, o):
        return values[a][o] < values[b][o] if senses[o] == "min" else values[a][o] > values[b][o]

    dominated = {}
    for b in comp:
        doms = [a for a in comp if a != b and all(better_or_equal(a, b, o) for o in senses)
                and any(strictly_better(a, b, o) for o in senses)]
        if doms:
            dominated[b] = sorted(doms)
    nd = [c for c in comp if c not in dominated]
    return {"label": PARETO_LABEL, "objectives": dict(sorted(senses.items())), "compared": sorted(comp),
            "non_dominated": sorted(nd), "dominated": dict(sorted(dominated.items())),
            "not_comparable": {c: NOT_COMPARABLE for c in sorted(notc)}}


def assert_no_forbidden_status(obj, path="$"):
    """Recursively refuse any status-like string equal to a forbidden word (PASS, SELECTED, ...)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert_no_forbidden_status(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            assert_no_forbidden_status(v, f"{path}[{i}]")
    elif isinstance(obj, str) and obj.strip().upper() in FORBIDDEN_WORDS:
        raise ScreeningError(f"forbidden status {obj!r} at {path}")
