"""A9.16 step 1 (integration lane): owner decisions applied to the H-1 freeze-candidate record (F5).

Applied (each cites the decision file + its json sha256 + the question id; the verbatim .md governs):
  A9.14 F5-OQ-01 (S7.1) FEMM-class analysis points authorised as ANALYSIS_POINTS, not a selection -> FEMM_AUTHORISED_NOT_RUN
  A9.14 F5-OQ-02 (S7.2) engineering channel point selected on non-performance criteria; ENGINEERING_FREEZE_CANDIDATE once
                        selected, pending FEMM (no point is selected here)
  A9.14 F5-OQ-03 (S7.3) 754 degC = conservative NECESSARY Curie ceiling of the pure iron, never the usable limit
  A9.14 F5-OQ-04 (S7.4) FREEZE_CANDIDATE set = LOCK-1 release basis; every OPEN / TBD item is an explicit release blocker;
                        release needs drawing id + revision + content hash (lock1_release_status, fail closed)
  A9.14 F5-OQ-05 (S7.5) r_Le <= 0.1 h band (T_e 10-30 eV) accepted as the FEMM magnetic-design target band
  A9.14 OQ-A907-04 (S8.16) plain ceramic-insulated copper coil baseline; Ni-clad / Kulgrid contingency variant only
  A9.14 MQ-03 (S8.8) AL-04 rebased from the actual H-1 CBE (>= 1.20 x CBE); 4.2048 kg = today's incomplete MEV floor
  A9.12 OQ-A907-05 / -06 / -08 (S5.3 / S5.4 / S5.5) provisional supplier ratings, 50 W governing mount-heat allocation,
                        coating node limit OPEN until sourced
No Hall performance, no PASS, no selection; numbers used are owner-supplied only (754 degC, 50 / 100 / 25 W, 1.20,
4.2048 kg).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "docs" / "decisions" / "application"))
import a9_16_lib as L  # noqa: E402

ARTIFACT = "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json"
TEST = "tests/test_h1_freeze_candidate.py"
CURIE_NECESSARY_CEILING_C = 754  # owner-supplied (A9.14 F5-OQ-03)
MOUNT_HEAT_ALLOCATION_W = {"governing_provisional": 50, "contingency_sensitivity_ceiling": 100, "stretch": 25}
FEMM_STATUS = "FEMM_AUTHORISED_NOT_RUN"
RELEASE_STATUSES = ("RELEASE_BLOCKED", "RELEASE_BASIS_COMPLETE_PENDING_OWNER_RELEASE")


def dsrc(qid: str) -> dict:
    a = L.answer(qid)
    return {"path": a["decision_json"], "pointer": f"/decisions/{qid}", "sha256": a["decision_json_sha256"],
            "note": f"{a['decision']} {qid} ({a['sequenced_no']}); verbatim {a['decision_md']}"}


def _a916(qids, **kw) -> dict:
    out = {"decisions": [L.cite(q) for q in qids], "decision_codes": {q: L.answer(q)["decision_code"] for q in qids}}
    out.update(kw)
    return out


def apply_to_parameters(params: list, femm_text: str, coupled_text: str) -> list:
    """Apply the record-level owner decisions to the parameter rows (in place); return the touched ids."""
    by_id = {p["id"]: p for p in params}
    touched = []

    p = by_id["H1F-CH-11"]
    p["value"] = ("TBD - engineering point to be selected on non-performance criteria (FEMM feasibility, thermal "
                  "margin, packaging, mass, manufacturability, adjustable-anode / insert capability) after the "
                  "authorised FEMM analysis points are run; not selected yet")
    p["source"] = p["source"] + [dsrc("F5-OQ-01"), dsrc("F5-OQ-02")]
    p["basis"] = p["basis"] + "; A9.14 F5-OQ-01 / F5-OQ-02 (selection rule owner-given, point not yet selected)"
    p["freeze_status"] = "TBD_AFTER_EVIDENCE"
    p["evidence_to_freeze_candidate"] = [femm_text + " at the authorised ANALYSIS_POINTS (femm_analysis_points)",
                                         coupled_text,
                                         "engineering-point selection record on the owner's non-performance criteria"]
    p["a9_16"] = _a916(["F5-OQ-01", "F5-OQ-02"], point_status="NOT_SELECTED_PENDING_FEMM",
                       status_when_selected="ENGINEERING_FREEZE_CANDIDATE",
                       selection_criteria=["FEMM feasibility", "thermal margin", "packaging", "mass",
                                           "manufacturability", "existing adjustable-anode / insert capability"],
                       thrust="determined by Phase-1 / Phase-3 measurement, never a selection input")
    touched.append(p["id"])

    p = by_id["H1F-MA-04"]
    p["source"] = p["source"] + [dsrc("F5-OQ-03")]
    p["evidence_to_freeze_candidate"] = [e for e in p["evidence_to_freeze_candidate"] if "CC-07" not in e]
    p["a9_16"] = _a916(["F5-OQ-03"], necessary_curie_ceiling_C=CURIE_NECESSARY_CEILING_C,
                       role="NECESSARY_CEILING_NOT_USABLE_LIMIT",
                       rule="754 degC is used until the exact iron grade has sourced temperature-dependent magnetic "
                            "data; B_sat(T), permeability and validated material behaviour govern the usable limit")
    touched.append(p["id"])

    p = by_id["H1F-BZ-03"]
    p["source"] = p["source"] + [dsrc("F5-OQ-05")]
    p["evidence_to_freeze_candidate"] = [e for e in p["evidence_to_freeze_candidate"] if "F5-OQ-05" not in e]
    p["a9_16"] = _a916(["F5-OQ-05"], role="FEMM_MAGNETIC_DESIGN_TARGET_BAND_NOT_TRANSPORT_OPTIMUM",
                       narrowing="only after measured H-1 magnetic / performance evidence exists")
    touched.append(p["id"])

    p = by_id["H1F-CO-08"]
    p["value"] = ("plain ceramic-insulated copper (baseline); Ni-clad / Kulgrid copper only as a contingency variant "
                  "if oxidation, supplier availability or manufacturing demands it, then with measured resistance and "
                  "magnetic-perturbation evidence")
    p["tolerance"] = "n/a (decision / rule)"
    p["evidence_class"] = "owner-allocation"
    p["source"] = [s for s in p["source"] if "owner_questions_state_v4" not in s["path"]] + [dsrc("OQ-A907-04")]
    p["basis"] = "row 77; A9.14 OQ-A907-04 (S8.16)"
    p["freeze_status"] = "FREEZE_CANDIDATE"
    p["evidence_to_freeze_candidate"] = []
    p["a9_16"] = _a916(["OQ-A907-04"], baseline="PLAIN_CERAMIC_INSULATED_COPPER",
                       contingency_variant="NI_CLAD_KULGRID_ON_TRIGGER_ONLY",
                       contingency_requires=["measured resistance", "magnetic-perturbation evidence (HW-MC-12)"])
    touched.append(p["id"])

    p = by_id["H1F-MC-08"]
    p["source"] = p["source"] + [dsrc("MQ-03")]
    p["evidence_to_freeze_candidate"] = [
        ("AL-04 rebased by the owner (A9.14 MQ-03): AL-04 >= 1.20 x the actual H-1 CBE; 4.2048 kg MEV is today's "
         "incomplete planning floor (channel / anode / body / fasteners not yet included)")
        if "MQ-03" in e else e for e in p["evidence_to_freeze_candidate"]]
    touched.append(p["id"])

    p = by_id["H1F-TH-02"]
    p["value"] = ("TBD - spacecraft thermal ICD; until it exists the owner allocation governs provisionally for steady "
                  "heat conducted into the mount: 50 W governing, 100 W contingency / sensitivity ceiling only, 25 W "
                  "stretch (a design meeting only 100 W is not thermally closed); 20 / 40 / 60 degC interface cases "
                  "carried")
    p["source"] = p["source"] + [dsrc("OQ-A907-06")]
    p["basis"] = "owner row 85; A9.12 OQ-A907-06 (S5.4): isolated mount + dedicated radiator"
    p["freeze_status"] = "TBD_AFTER_EVIDENCE"
    p["evidence_to_freeze_candidate"] = ["spacecraft / PDR thermal ICD (replaces the owner allocation)"]
    p["a9_16"] = _a916(["OQ-A907-06"], mount_heat_allocation_W=dict(MOUNT_HEAT_ALLOCATION_W),
                       label="owner design allocation, not a spacecraft requirement")
    touched.append(p["id"])

    p = by_id["H1F-MA-06"]
    p["source"] = p["source"] + [dsrc("OQ-A907-08")]
    p["a9_16"] = _a916(["OQ-A907-08"], coating_limit_status="OPEN_COATING_LIMIT_NOT_SOURCED",
                       rule="T_operating <= T_validated,continuous - 50 K for the actual coating / substrate / "
                            "application system once sourced; no thermal closure relying on the coating before that")
    touched.append(p["id"])

    p = by_id["H1F-CO-11"]
    p["source"] = p["source"] + [dsrc("OQ-A907-05")]
    p["a9_16"] = _a916(["OQ-A907-05"], limit_class="SUPPLIER_PROVISIONAL",
                       admissible_uses=["preliminary thermal screening", "equipment protection", "design sensitivity",
                                        "procurement down-selection"],
                       dependent_margin_status="UNRESOLVED_CONDITIONAL_ON_PROVISIONAL_LIMIT")
    touched.append(p["id"])
    return touched


def femm_analysis_points(probe_rows: list) -> dict:
    names = []
    for r in probe_rows:
        if r["probe"] not in names:
            names.append(r["probe"])
    pts = []
    for n in names:
        st = {r["assumptions"]: r["status"] for r in probe_rows if r["probe"] == n}
        worst_ok = st.get("worst_case_assumptions") == "WITHIN_DECLARED_GEOMETRIC_WINDOWS"
        pts.append({"probe": n, "geometric_status": st,
                    "authorised_analysis_point": worst_ok,
                    "note": None if worst_ok else "the solid-core inner-coil floor does not admit this corner under "
                                                  "worst-case assumptions; not in the authorised set (owner may add)",
                    "femm_status": FEMM_STATUS if worst_ok else "NOT_AUTHORISED"})
    return {"status": FEMM_STATUS, "role": "ANALYSIS_POINTS_NOT_SELECTION", "decision": L.cite("F5-OQ-01"),
            "decision_code": L.answer("F5-OQ-01")["decision_code"],
            "rules": ["FEMM-class axisymmetric magnetostatics at the RP-1 anchor and the admissible window corners",
                      "use actual / sourced B-H data when available; preserve geometry ids and solver configuration",
                      "do not infer Hall performance from magnetic feasibility alone"],
            "target_band": "H1F-BZ-03 r_Le <= 0.1 h over T_e 10-30 eV (A9.14 F5-OQ-05)",
            "points": pts, "results": []}


def lock1_release_status(params: list, drawing: dict | None) -> dict:
    """A9.14 F5-OQ-04: the FREEZE_CANDIDATE set is the LOCK-1 release basis; every non-FREEZE_CANDIDATE item blocks the
    release, and a release needs the drawing id, revision and content hash. Never PASS; fail closed."""
    blockers = [{"id": p["id"], "freeze_status": p["freeze_status"]} for p in params
                if p["freeze_status"] != "FREEZE_CANDIDATE"]
    drawing = drawing or {}
    missing = [k for k in ("drawing_id", "revision", "content_sha256") if not drawing.get(k)]
    sha = drawing.get("content_sha256") or ""
    if sha and (len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha)):
        missing.append("content_sha256 (not a sha256 hex digest)")
    status = RELEASE_STATUSES[0] if (blockers or missing) else RELEASE_STATUSES[1]
    return {"status": status, "decision": L.cite("F5-OQ-04"), "decision_code": L.answer("F5-OQ-04")["decision_code"],
            "release_basis": "FREEZE_CANDIDATE items of this definition",
            "drawing": {k: drawing.get(k) for k in ("drawing_id", "revision", "content_sha256")},
            "missing_drawing_fields": missing, "blocker_count": len(blockers), "blockers": blockers,
            "rule": "no OPEN / TBD item is promoted because surrounding geometry is frozen; the release itself is an "
                    "owner act with the released drawing id, revision and content hash"}


def answered_open_questions(oqs: list) -> list:
    out = []
    for q in oqs:
        a = L.answer(q["id"])
        q = dict(q)
        q.update({"status_when_raised": "TBD_OWNER", "status": "OWNER_DECIDED", "decision": L.cite(q["id"]),
                  "decision_code": a["decision_code"], "answer_verbatim": a["verbatim_excerpt"]})
        out.append(q)
    return out


def owner_answers_applied() -> list:
    rows = [
        L.applied_row("F5-OQ-01", ARTIFACT, ["femm_analysis_points", "H1F-CH-11"],
                      "FEMM analysis points recorded as ANALYSIS_POINTS_NOT_SELECTION, status FEMM_AUTHORISED_NOT_RUN "
                      "(no FEMM run here; results empty)", [TEST]),
        L.applied_row("F5-OQ-02", ARTIFACT, ["H1F-CH-11"],
                      "selection rule on non-performance criteria recorded; point NOT_SELECTED_PENDING_FEMM, status "
                      "when selected ENGINEERING_FREEZE_CANDIDATE; freeze_status TBD_OWNER -> TBD_AFTER_EVIDENCE", [TEST]),
        L.applied_row("F5-OQ-03", ARTIFACT, ["H1F-MA-04", "CC-07"],
                      "754 degC necessary Curie ceiling (not the usable limit); the CC-07 discrepancy stays recorded, "
                      "its resolution is the owner's conservative choice", [TEST]),
        L.applied_row("F5-OQ-04", ARTIFACT, ["lock1_release"],
                      "lock1_release_status: FREEZE_CANDIDATE set is the release basis, every other item a blocker, "
                      "drawing id / revision / content hash required; status RELEASE_BLOCKED", [TEST]),
        L.applied_row("F5-OQ-05", ARTIFACT, ["H1F-BZ-03"], "r_Le <= 0.1 h band accepted as FEMM target band", [TEST]),
        L.applied_row("OQ-A907-04", ARTIFACT, ["H1F-CO-08"],
                      "plain ceramic-insulated copper baseline (FREEZE_CANDIDATE); Ni-clad contingency on trigger only",
                      [TEST]),
        L.applied_row("MQ-03", ARTIFACT, ["H1F-MC-08"], "AL-04 >= 1.20 x H-1 CBE; 4.2048 kg incomplete MEV floor cited",
                      [TEST]),
        L.applied_row("OQ-A907-05", ARTIFACT, ["H1F-CO-11"], "supplier coil rating labelled SUPPLIER_PROVISIONAL", [TEST]),
        L.applied_row("OQ-A907-06", ARTIFACT, ["H1F-TH-02"], "50 W governing / 100 W contingency / 25 W stretch "
                      "owner allocation until the spacecraft thermal ICD; TBD_OWNER -> TBD_AFTER_EVIDENCE", [TEST]),
        L.applied_row("OQ-A907-08", ARTIFACT, ["H1F-MA-06"], "coating limit OPEN_COATING_LIMIT_NOT_SOURCED", [TEST]),
        L.a915_row(ARTIFACT, ["(review)"], "reviewed: the H-1 record has no 'Xe contingency-only for C1' wording; "
                   "nothing to amend", [TEST]),
    ]
    return rows
