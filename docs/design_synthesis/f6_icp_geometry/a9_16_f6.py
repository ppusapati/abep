"""A9.16 step 1 (integration lane): owner decisions A9.14 S7.6 - S7.9 applied to the F6 ICP-geometry record.

  F6-OQ-01 (S7.6) eight objectives and directions approved; fail-closed Pareto (REFUSED_INCOMPLETE on any missing objective)
  F6-OQ-02 (S7.7) the KC-1 / ICP LOCK-1 drawing envelope = hard design-variable bounds; the registered P1 / P2 geometry
                  matrix = which points inside it have evidence; a test matrix never enlarges the envelope
  F6-OQ-03 (S7.8) multi-geometry bench matrix first; F6 evaluates BUILT geometries; a geometry-response surrogate only
                  after a separate predictive validation (no surrogate today)
  F6-OQ-04 (S7.9) delta_B_acc = max_ROI |B_H1+ICP - B_H1| / max_ROI |B_H1| over the preregistered acceleration-region ROI
                  and relevant magnet states; provisional requirement delta_B_acc <= 0.05 (owner allocation; may be
                  tightened, never relaxed post hoc); absolute stray field at IP-EXIT and through the ICP volume reported
The production module abep_sim/design/icp_geometry_synthesis.py is not changed here (record-level application; a module
change would be PENDING_STEP_3_ARCHITECTURE). No PASS.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "docs" / "decisions" / "application"))
import a9_16_lib as L  # noqa: E402

ARTIFACT = "docs/design_synthesis/f6_icp_geometry/f6_icp_geometry_v1.json"
TEST = "tests/test_decision_application_a9_16.py"
DELTA_B_ACC_MAX = 0.05  # owner-supplied provisional allocation (A9.14 F6-OQ-04)
STATUSES = ("NOT_EVALUATED_ROI_NOT_PREREGISTERED", "NOT_EVALUATED_STRAY_FIELD_NOT_REPORTED", "NOT_EVALUATED_NO_FIELD_DATA",
            "REFUSED_THRESHOLD_RELAXATION", "WITHIN_PROVISIONAL_ALLOCATION", "EXCEEDS_PROVISIONAL_ALLOCATION")


class F6A16Error(ValueError):
    pass


def delta_b_acc(roi: dict | None, b_h1: list | None, b_h1_icp: list | None, stray: dict | None,
                threshold: float = DELTA_B_ACC_MAX) -> dict:
    """A9.14 F6-OQ-04. b_h1 / b_h1_icp: |B| samples (same ROI points, same magnet state) without / with the ICP module.
    Fail closed: no preregistered ROI -> NOT_EVALUATED; no stray-field report -> NOT_EVALUATED; a threshold above the
    owner's 0.05 -> REFUSED. Never PASS."""
    if threshold > DELTA_B_ACC_MAX:
        return {"status": "REFUSED_THRESHOLD_RELAXATION", "reason": "0.05 may be tightened, never relaxed post hoc"}
    if not roi or not roi.get("roi_id") or not roi.get("frozen_utc") or not roi.get("magnet_states"):
        return {"status": "NOT_EVALUATED_ROI_NOT_PREREGISTERED"}
    if not b_h1 or not b_h1_icp:
        return {"status": "NOT_EVALUATED_NO_FIELD_DATA"}
    if len(b_h1) != len(b_h1_icp):
        raise F6A16Error("B samples must be at the same ROI points")
    for v in list(b_h1) + list(b_h1_icp):
        if not isinstance(v, (int, float)) or not math.isfinite(v):
            raise F6A16Error("non-finite B sample")
    if not stray or stray.get("ip_exit_T") is None or stray.get("icp_volume_max_T") is None:
        return {"status": "NOT_EVALUATED_STRAY_FIELD_NOT_REPORTED"}
    den = max(abs(b) for b in b_h1)
    if den <= 0:
        raise F6A16Error("max_ROI |B_H1| must be > 0")
    d = max(abs(a - b) for a, b in zip(b_h1_icp, b_h1)) / den
    return {"status": "WITHIN_PROVISIONAL_ALLOCATION" if d <= threshold else "EXCEEDS_PROVISIONAL_ALLOCATION",
            "delta_B_acc": d, "threshold": threshold, "roi_id": roi["roi_id"], "stray_field": dict(stray),
            "label": "owner engineering allocation, not experimental proof"}


def geometry_scope(geometry: dict, envelope: dict | None, matrix_ids: set) -> dict:
    """A9.14 F6-OQ-02 / F6-OQ-03: a geometry is evaluated only if it lies inside the drawing envelope (hard bounds, same
    revision, every variable bounded) and is a registered, BUILT bench geometry; surrogate points are refused."""
    if geometry.get("source") == "SURROGATE" and not geometry.get("surrogate_predictive_validation_id"):
        return {"status": "REFUSED_SURROGATE_NOT_VALIDATED"}
    if envelope is None:
        return {"status": "NOT_EVALUATED_REGISTRATION", "reason": "no LOCK-1 drawing envelope registered"}
    if geometry.get("drawing_revision") != envelope.get("revision"):
        return {"status": "REFUSED_OTHER_DRAWING_REVISION"}
    for k, v in geometry.get("variables", {}).items():
        b = envelope.get("bounds", {}).get(k)
        if b is None:
            return {"status": "REFUSED_VARIABLE_NOT_BOUNDED_BY_DRAWING", "variable": k}
        if not (b[0] <= v <= b[1]):
            return {"status": "REFUSED_OUTSIDE_DRAWING_ENVELOPE", "variable": k}
    if geometry.get("geometry_id") not in matrix_ids:
        return {"status": "OUT_OF_DOMAIN_NOT_IN_REGISTERED_BENCH_MATRIX"}
    return {"status": "MEASURED_GEOMETRY" if geometry.get("measured") else "NOT_YET_MEASURED"}


def section(required_objectives: list) -> dict:
    return {
        "objectives": {"status": "OWNER_APPROVED", "decision": L.cite("F6-OQ-01"),
                       "required": list(required_objectives),
                       "pareto_rule": "fail closed: REFUSED_INCOMPLETE while any required objective is missing; no "
                                      "ranking from an incomplete subset"},
        "bounds": {"status": "OWNER_DECIDED", "decision": L.cite("F6-OQ-02"),
                   "hard_bounds": "KC-1 / ICP LOCK-1 drawing envelope (not yet registered: NOT_EVALUATED_REGISTRATION)",
                   "evidence_points": "registered P1 / P2 geometry matrix (P1 icp_geometry_matrix slot, P1-IT-61)",
                   "rule": "a test matrix never enlarges the mechanical envelope without a drawing revision",
                   "evaluator": "docs/design_synthesis/f6_icp_geometry/a9_16_f6.py:geometry_scope"},
        "search_scope": {"status": "BUILT_GEOMETRIES_ONLY", "decision": L.cite("F6-OQ-03"),
                         "surrogate": "none; a geometry-response surrogate only after a separate predictive validation"},
        "hall_b_field_disturbance": {"status": "OWNER_DEFINED_PROVISIONAL", "decision": L.cite("F6-OQ-04"),
                                     "metric": "delta_B_acc = max_ROI |B_H1+ICP - B_H1| / max_ROI |B_H1|",
                                     "provisional_max": DELTA_B_ACC_MAX,
                                     "also_report": ["absolute stray field at IP-EXIT",
                                                     "absolute stray field through the ICP volume"],
                                     "roi": "preregistered H-1 acceleration-region ROI and relevant magnet states (TBD)",
                                     "today": "NOT_EVALUATED (no FEMM of MC-1 covering the ICP region; F6-IF-N02)",
                                     "evaluator": "docs/design_synthesis/f6_icp_geometry/a9_16_f6.py:delta_b_acc",
                                     "module_change": "PENDING_STEP_3_ARCHITECTURE (abep_sim/design/"
                                                      "icp_geometry_synthesis.b_field_objective keeps its contract)"},
    }


def answered(qs: list) -> list:
    out = []
    for q in qs:
        a = L.answer(q["id"])
        q = dict(q)
        q.update({"status_when_raised": q["status"], "status": "OWNER_DECIDED", "decision": L.cite(q["id"]),
                  "decision_code": a["decision_code"], "answer_verbatim": a["verbatim_excerpt"]})
        out.append(q)
    return out


def owner_answers_applied() -> list:
    return [L.applied_row("F6-OQ-01", ARTIFACT, ["a9_16_owner_decisions.objectives"], "eight objectives approved; "
                          "fail-closed Pareto kept", [TEST]),
            L.applied_row("F6-OQ-02", ARTIFACT, ["a9_16_owner_decisions.bounds"], "drawing envelope = hard bounds, "
                          "bench matrix = evidence points (geometry_scope refuses points outside / unbounded / other "
                          "revision)", [TEST]),
            L.applied_row("F6-OQ-03", ARTIFACT, ["a9_16_owner_decisions.search_scope"], "F6 evaluates built "
                          "geometries; surrogate refused until predictively validated", [TEST]),
            L.applied_row("F6-OQ-04", ARTIFACT, ["a9_16_owner_decisions.hall_b_field_disturbance"], "delta_B_acc "
                          "metric, provisional <= 0.05, stray field at IP-EXIT and ICP volume reported (delta_b_acc, "
                          "fail closed)", [TEST]),
            L.a915_row(ARTIFACT, ["(review)"], "reviewed: no Xe wording in F6; nothing to amend", [TEST])]
