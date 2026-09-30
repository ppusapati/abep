"""Status-assignment rules of the A9 system requirement-verification matrix (follow-on fo_a9_6_rvm; owner directive
A9.6 sec. 15). Pure functions, standard library only, no I/O.

The six allowed states are exactly those of A9.6 sec. 15 (docs/decisions/OD_2026_09_30_A9_6_implementation_first_
directive.json summary.rvm_states). Implementation completeness is never compliance: a framework, an allocation, a
prediction-free budget, a plan, a published analog or an owner decision can never yield PASS. PASS needs a verified,
measured, non-synthetic, in-domain determining artifact that meets the requirement, covers it, and a requirement basis
that is frozen (the official RFP wording or an owner-given basis).

Every artifact record must carry every field of ARTIFACT_FIELDS (no hidden defaults); a missing or ill-typed field
raises RvmError. Synthetic evidence is refused outright (never mixed with measured evidence).
"""
from __future__ import annotations

STATUSES = ("PASS", "FAIL", "NOT_EVALUATED", "OUT_OF_DOMAIN", "INCOMPLETE_EVIDENCE", "NUMERICAL_FAILURE")

ROLES = ("DETERMINING", "SUPPORTING", "CONTEXT")

ARTIFACT_KINDS = (
    "MEASUREMENT",            # a hardware measurement record (the only kind that can PASS)
    "VALIDATED_ANALYSIS",     # analysis with an admitted / validated model (Hall: credible set empty -> unavailable)
    "BUDGET_EVALUATION",      # prediction-free ledger / roll-up evaluation (mass, power, Xe)
    "FRAMEWORK_EVALUATION",   # fail-closed framework run on the inputs that exist (P3 thermal, P4 materials)
    "PLAN_OR_FRAMEWORK",      # test plan, pre-registration framework, ICD, schema, reducer: evaluates nothing
    "PUBLISHED_ANALOG",       # another device / another gas: context only
    "PROCUREMENT",            # RFQ package: never evidence of compliance
)
EVALUATING_KINDS = ("MEASUREMENT", "VALIDATED_ANALYSIS", "BUDGET_EVALUATION", "FRAMEWORK_EVALUATION")

ARTIFACT_FIELDS = {
    "path": str, "id": str, "role": str, "kind": str, "evidence_state": str,
    "evaluated": bool, "verified": bool, "measured": bool, "synthetic": bool,
    "in_domain": (bool, type(None)), "meets": (bool, type(None)), "coverage_complete": bool,
    "evidenced_terms": int, "numerical_failure": bool, "lower_bound_verified": bool,
    "exceeds_limit_every_reading": (bool, type(None)),
}

RULES = {
    "R0-SYNTHETIC": "synthetic evidence is refused (raises); synthetic and measured evidence are never mixed",
    "R1-NUMERICAL": "a determining evaluation reports non-convergence and no verified measurement exists -> "
                    "NUMERICAL_FAILURE",
    "R2-FAIL-MEASURED": "a verified, measured, in-domain determining measurement violates the requirement -> FAIL",
    "R3-PASS": "every verified, measured, in-domain determining measurement meets the requirement, at least one "
               "covers it completely, and the requirement basis is frozen -> PASS",
    "R3b-BASIS-NOT-FROZEN": "measurements would pass but the requirement basis is not frozen (official RFP not "
                            "obtained, owner rows 1-3) -> INCOMPLETE_EVIDENCE",
    "R3c-COVERAGE": "verified measurements exist but none covers the requirement completely -> INCOMPLETE_EVIDENCE",
    "R4-FAIL-FLOOR": "a determining budget evaluation whose floor is a VERIFIED lower bound exceeds the limit under "
                     "EVERY admissible open reading -> FAIL",
    "R5-OUT-OF-DOMAIN": "determining evaluations exist and every one lies outside its applicability domain -> "
                        "OUT_OF_DOMAIN",
    "R6-INCOMPLETE": "a determining evaluation was run in domain with at least one evidenced (non-allocation, "
                     "non-TBD) term but cannot conclude -> INCOMPLETE_EVIDENCE",
    "R7-NOT-EVALUATED": "no determining evaluation with evidenced terms exists (plans, frameworks, allocations, "
                        "analogs or unavailable analyses only) -> NOT_EVALUATED",
}


class RvmError(ValueError):
    pass


def validate_artifact(a):
    if not isinstance(a, dict):
        raise RvmError(f"artifact must be a dict, got {type(a).__name__}")
    for k, typ in ARTIFACT_FIELDS.items():
        if k not in a:
            raise RvmError(f"artifact {a.get('id', '?')}: missing field {k!r} (no default)")
        v = a[k]
        if typ is int:
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                raise RvmError(f"artifact {a.get('id')}: {k} must be a non-negative int")
        elif not isinstance(v, typ):
            raise RvmError(f"artifact {a.get('id')}: {k} has type {type(v).__name__}")
    if not a["path"] or not a["id"]:
        raise RvmError("artifact path and id must be non-empty")
    if a["role"] not in ROLES:
        raise RvmError(f"artifact {a['id']}: role {a['role']!r} not in {ROLES}")
    if a["kind"] not in ARTIFACT_KINDS:
        raise RvmError(f"artifact {a['id']}: kind {a['kind']!r} not in {ARTIFACT_KINDS}")
    if a["synthetic"]:
        raise RvmError(f"artifact {a['id']}: synthetic evidence refused (R0-SYNTHETIC)")
    if a["measured"] and a["kind"] != "MEASUREMENT":
        raise RvmError(f"artifact {a['id']}: measured=True only for kind MEASUREMENT")
    if a["kind"] == "MEASUREMENT" and not a["measured"]:
        raise RvmError(f"artifact {a['id']}: kind MEASUREMENT requires measured=True")
    if a["evaluated"] and a["kind"] not in EVALUATING_KINDS:
        raise RvmError(f"artifact {a['id']}: kind {a['kind']} cannot be an evaluation")
    if a["meets"] is not None and not a["evaluated"]:
        raise RvmError(f"artifact {a['id']}: meets set on an artifact that evaluated nothing")
    if a["kind"] != "MEASUREMENT" and a["meets"] is True:
        raise RvmError(f"artifact {a['id']}: only a measurement can meet a requirement (implementation completeness "
                       f"is never compliance)")
    if a["lower_bound_verified"] and a["kind"] != "BUDGET_EVALUATION":
        raise RvmError(f"artifact {a['id']}: lower_bound_verified applies to BUDGET_EVALUATION only")
    if a["exceeds_limit_every_reading"] is not None and a["kind"] != "BUDGET_EVALUATION":
        raise RvmError(f"artifact {a['id']}: exceeds_limit_every_reading applies to BUDGET_EVALUATION only")
    return a


def assign_status(artifacts, requirement_frozen):
    """Return (status, rule_id, reason). Deterministic; order of the rules is the order of RULES."""
    if not isinstance(requirement_frozen, bool):
        raise RvmError("requirement_frozen must be bool")
    if not artifacts:
        raise RvmError("no artifacts: every row/configuration needs at least one determining artifact")
    for a in artifacts:
        validate_artifact(a)
    det = [a for a in artifacts if a["role"] == "DETERMINING"]
    if not det:
        raise RvmError("no DETERMINING artifact (a row must name what would verify it)")
    meas = [a for a in det if a["kind"] == "MEASUREMENT" and a["evaluated"] and a["verified"]
            and a["in_domain"] is True]
    num = [a for a in det if a["evaluated"] and a["numerical_failure"]]
    if num and not meas:
        return "NUMERICAL_FAILURE", "R1-NUMERICAL", "non-converged evaluation: " + ", ".join(a["id"] for a in num)
    if meas:
        bad = [a for a in meas if a["meets"] is False]
        if bad:
            return "FAIL", "R2-FAIL-MEASURED", "verified measurement violates the requirement: " + ", ".join(
                a["id"] for a in bad)
        if all(a["meets"] is True for a in meas) and any(a["coverage_complete"] for a in meas):
            if requirement_frozen:
                return "PASS", "R3-PASS", "verified measurement meets and covers the requirement: " + ", ".join(
                    a["id"] for a in meas)
            return ("INCOMPLETE_EVIDENCE", "R3b-BASIS-NOT-FROZEN",
                    "measurements meet the recorded requirement but its basis is not frozen")
        return ("INCOMPLETE_EVIDENCE", "R3c-COVERAGE",
                "verified measurements exist but do not cover the requirement completely")
    floor_fail = [a for a in det if a["kind"] == "BUDGET_EVALUATION" and a["evaluated"]
                  and a["lower_bound_verified"] and a["exceeds_limit_every_reading"] is True]
    if floor_fail:
        return "FAIL", "R4-FAIL-FLOOR", "verified lower bound exceeds the limit under every admissible reading: " + \
            ", ".join(a["id"] for a in floor_fail)
    evals = [a for a in det if a["evaluated"]]
    if evals and all(a["in_domain"] is False for a in evals):
        return "OUT_OF_DOMAIN", "R5-OUT-OF-DOMAIN", "every determining evaluation is outside its domain: " + \
            ", ".join(a["id"] for a in evals)
    partial = [a for a in evals if a["in_domain"] is not False and a["evidenced_terms"] > 0]
    if partial:
        return ("INCOMPLETE_EVIDENCE", "R6-INCOMPLETE",
                "evaluation run with evidenced terms but inconclusive: " + ", ".join(
                    f"{a['id']} ({a['evidenced_terms']} evidenced term(s))" for a in partial))
    return ("NOT_EVALUATED", "R7-NOT-EVALUATED",
            "no determining evaluation with evidenced terms: " + ", ".join(
                f"{a['id']} [{a['kind']}]" for a in det))


def floor_fail_check(readings, limit, strict):
    """Mass FAIL admissibility from floor-only sums.

    readings: list of {"reading": str, "floor_only_kg": float}; limit in kg; strict True for '<' (value >= limit
    violates). Returns {"exceeds_every_reading": bool, "n_readings": int, "n_exceeding": int, "min_floor_kg": float,
    "max_floor_kg": float}. Raises on an empty list or a non-finite value.
    """
    if not readings:
        raise RvmError("floor_fail_check: no readings")
    vals = []
    for r in readings:
        v = r["floor_only_kg"]
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v != v or v in (float("inf"), float("-inf")):
            raise RvmError(f"floor_fail_check: bad value in reading {r.get('reading')}")
        vals.append(float(v))
    exceeding = [v for v in vals if (v >= limit if strict else v > limit)]
    return {"exceeds_every_reading": len(exceeding) == len(vals), "n_readings": len(vals),
            "n_exceeding": len(exceeding), "min_floor_kg": round(min(vals), 6), "max_floor_kg": round(max(vals), 6)}


def assert_status_vocabulary(doc):
    """Every status in the matrix is one of the six; the declared vocabulary is exactly the six."""
    if tuple(doc["status_vocabulary"]) != STATUSES:
        raise RvmError("status vocabulary differs from the six A9.6 states")
    for row in doc["rows"]:
        for cfg, cell in row["configurations"].items():
            if cell["status"] not in STATUSES:
                raise RvmError(f"{row['id']}/{cfg}: status {cell['status']!r} not allowed")


def assert_no_pass_without_measurement(doc):
    for row in doc["rows"]:
        for cfg, cell in row["configurations"].items():
            if cell["status"] == "PASS":
                ok = [a for a in cell["artifacts"] if a["role"] == "DETERMINING" and a["kind"] == "MEASUREMENT"
                      and a["measured"] and a["verified"] and a["evaluated"] and a["meets"] is True
                      and not a["synthetic"]]
                if not ok:
                    raise RvmError(f"{row['id']}/{cfg}: PASS without a cited verified measurement artifact")
