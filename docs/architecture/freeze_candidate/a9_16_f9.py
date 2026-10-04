"""A9.16 step 1 (integration lane): owner decisions applied to the F9 architecture freeze-candidate record.

Record-level changes only (no optimizer / model code changes; those are PENDING_STEP_3_ARCHITECTURE or, for A9.9,
PENDING_STEP_2_MODEL_CHANGE):
  A9.13 F9-OQ-03 (S6.22)  AG-01 .. AG-15 approved with the determining-evidence closure standard (gate_closes);
                          AG-03 via a separately preregistered successor held-out validation (P5-N2 v1 stays INCONCLUSIVE);
                          AG-12 = statewise feed-state sufficiency (S6.21); AG-13 = statewise T - D >= 0 (S6.15);
                          AG-15 = official RFP registered with immutable provenance / hash + RVM re-based (status
                          derived by ag15_f9.assess from the registration record and the RVM re-base; F9 lane F9)
  A9.13 F9-OQ-02 (S6.21)  no fixed flight mass-flow gate: 0.38 mg/s and ~1.3 mg/s are not requirements; 0.38-3.2 mg/s is
                          characterization coverage only; AG-12 NOT_EVALUATED until the validated H-1 thrust-vs-feed map
  A9.13 F9-OQ-01 (S6.20)  the robust Pareto set is carried to LOCK-1; no representative is selected
  A9.13 / A9.14 / A9.12 / A9.8 / A9.15 answers that settle F9 rows (filter placement, setpoint policy, delta_B_acc,
                          isolation class, redundancy, mass lines, Xe cases, start sequence, Xe capability)
  A9.9 F1Q-01 / UPSTREAM_ICD-Q7 / F9-OQ-04  model-change candidates MCC-01..07 owner-authorised, PENDING_STEP_2
No PASS; no representative; the step-1 label OWNER_STATED_PENDING_RFP_REGISTRATION set here is re-based afterwards onto
the registered clause ids by rfp_citations_f9 (kept there as rfp_citation_status_as_applied; AG-15 itself is evaluated
from the registered RFP, ag15_f9).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "docs" / "decisions" / "application"))
import a9_16_lib as L  # noqa: E402

ARTIFACT = "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json"
TEST = "tests/test_decision_application_a9_16.py"
CHARACTERIZATION_COVERAGE_MG_S = (0.38, 3.2)  # owner row 73 range; coverage only (A9.13 F9-OQ-02)

# determining-evidence classes by gate kind (A9.13 S6.22 verbatim list)
DETERMINING = {
    "performance": {"MEASURED_TEST_EVIDENCE", "CORRELATED_VALIDATED_ANALYSIS_PERMITTED_BY_METHOD"},
    "hardware": {"INSPECTED_WEIGHED_CERTIFIED_CONFIGURATION", "MEASURED_TEST_EVIDENCE"},
    "requirement": {"OFFICIAL_SOURCE_DOCUMENT_REGISTERED"},
    "validation": {"PREREGISTERED_HELD_OUT_PREDICTIVE_VALIDATION_ADMITTING_A_MEMBER"},
}
NOT_DETERMINING = ("ASSUMPTION", "PARAMETRIC_SENSITIVITY", "ANALOG_VALUE", "CODE_DEFAULT", "SUPPLIER_MARKETING_VALUE",
                   "EVIDENCE_SEEMS_SUFFICIENT")
GATE_KIND = {"AG-01": "requirement", "AG-02": "validation", "AG-03": "validation", "AG-04": "performance",
             "AG-05": "performance", "AG-06": "performance", "AG-07": "hardware", "AG-08": "performance",
             "AG-09": "performance", "AG-10": "performance", "AG-11": "hardware", "AG-12": "performance",
             "AG-13": "performance", "AG-14": "hardware", "AG-15": "requirement"}


def dsrc(qid: str) -> dict:
    a = L.answer(qid)
    return {"path": a["decision_json"], "pointer": f"/decisions/{qid}", "sha256": a["decision_json_sha256"],
            "pinned": True, "note": f"{a['decision']} {qid} ({a['sequenced_no']})"}


def a915src() -> dict:
    a = L.LOADED["A9.15"]
    return {"path": a["json"], "pointer": "/governing_rule", "sha256": a["json_sha256"], "pinned": True,
            "note": "A9.15 RFP-compliant propellant policy (governs every 'Xe contingency-only for C1' reading)"}


def gate_closes(gate_id: str, evidence: list) -> dict:
    """A9.13 F9-OQ-03: a gate closes only on determining evidence appropriate to that gate. Fail closed."""
    kind = GATE_KIND[gate_id]
    refused = [e for e in evidence if e.get("class") in NOT_DETERMINING or e.get("class") not in DETERMINING[kind]]
    ok = [e for e in evidence if e.get("class") in DETERMINING[kind] and e.get("source")]
    if gate_id == "AG-15" and not any(e.get("sha256") and e.get("provenance") for e in ok):
        ok = []
    if gate_id == "AG-03" and any(e.get("rewrites_p5_n2_v1") for e in evidence):
        return {"gate": gate_id, "closes": False, "status": "REFUSED_P5_N2_V1_IS_IMMUTABLE", "refused": evidence}
    closes = bool(ok) and not refused
    return {"gate": gate_id, "closes": closes,
            "status": "DETERMINING_EVIDENCE_PRESENT" if closes else "NOT_CLOSED_NO_DETERMINING_EVIDENCE",
            "refused": refused}


def ag12_feed_state_sufficiency(states: list, h1_map_validated: bool, fixed_flow_gate_mg_s=None) -> dict:
    """A9.13 F9-OQ-02 / S6.21: per state, the upstream chain must deliver at least the feed state that the measured /
    validated H-1 map needs for the drag-compensation thrust within the admitted power / thermal envelope."""
    if fixed_flow_gate_mg_s is not None:
        return {"status": "REFUSED_FIXED_MASS_FLOW_GATE", "reason": "no fixed mg/s flight gate (0.38 / ~1.3 mg/s are "
                                                                    "not requirements)"}
    if not h1_map_validated:
        return {"status": "NOT_EVALUATED", "reason": "the validated H-1 thrust-versus-feed map does not exist"}
    fields = ("mdot", "pressure", "temperature", "composition", "transient_quality")
    per = []
    for s in states:
        req, dlv = s.get("required"), s.get("delivered")
        if not req or not dlv or any(dlv.get(f) is None or req.get(f) is None for f in fields):
            per.append({"state": s.get("state"), "status": "NOT_EVALUATED_INCOMPLETE_FEED_STATE_RECORD"})
            continue
        ok = dlv["mdot"] >= req["mdot"] and dlv["transient_quality"] == "WITHIN_H1_TOLERANCE"
        per.append({"state": s.get("state"), "status": "FEED_STATE_SUFFICIENT" if ok else "FEED_STATE_INSUFFICIENT"})
    if not per or any(p["status"].startswith("NOT_EVALUATED") for p in per):
        return {"status": "NOT_EVALUATED", "per_state": per}
    return {"status": "STATEWISE_SUFFICIENT" if all(p["status"] == "FEED_STATE_SUFFICIENT" for p in per)
            else "STATEWISE_INSUFFICIENT", "per_state": per}


def ag13_statewise(states: list, spacecraft_icd_registered: bool) -> dict:
    """A9.13 OQ-F78-01 / S6.15: T_available(state) - D_spacecraft(state) >= 0 at EVERY required state; worst-state and
    orbit-averaged margins reported additionally; an orbit average never hides a statewise deficit."""
    if not spacecraft_icd_registered:
        return {"status": "NOT_EVALUATED", "reason": "actual host-spacecraft ICD not registered (OQ-F78-04); "
                                                      "D_spacecraft and T - D are NOT_EVALUATED for freeze purposes"}
    if not states or any(s.get("T_N") is None or s.get("D_N") is None for s in states):
        return {"status": "NOT_EVALUATED", "reason": "thrust or drag missing at a required state"}
    m = [s["T_N"] - s["D_N"] for s in states]
    w = [s.get("weight", 1.0) for s in states]
    avg = sum(a * b for a, b in zip(m, w)) / sum(w)
    worst = min(m)
    return {"status": "STATEWISE_DEFICIT" if worst < 0 else "STATEWISE_NON_NEGATIVE",
            "worst_state_margin_N": worst, "orbit_average_margin_N": avg,
            "per_state_margin_N": m, "rule": "hard statewise constraint; the orbit average is reported only"}


def apply_gates(gates: list, ref, upstream_frontier_mg_s: float) -> list:
    by = {g["id"]: g for g in gates}
    for g in gates:
        g["owner_approved"] = {"decision": L.cite("F9-OQ-03"),
                               "decision_code": L.answer("F9-OQ-03")["decision_code"]}
        g["closure_standard"] = {"kind": GATE_KIND[g["id"]], "determining_evidence": sorted(DETERMINING[GATE_KIND[g["id"]]]),
                                 "never_determining": list(NOT_DETERMINING)}
    g = by["AG-03"]
    g["gate"] = "Hall-transport validation (successor held-out predictive validation; P5-N2 v1 unchanged)"
    g["blocking_evidence"] = ("P5-N2 v1 stays INCONCLUSIVE and is never rewritten; closure needs a separately "
                              "preregistered successor held-out predictive validation that admits a Hall-transport member "
                              "(A9.13 F9-OQ-03 AG-03 clarification)")
    g["sources"] = g["sources"] + [dsrc("F9-OQ-03")]
    g = by["AG-12"]
    g["gate"] = "statewise feed-state sufficiency (performance-derived; A9.13 F9-OQ-02)"
    g["current_status"] = "NOT_EVALUATED (validated H-1 thrust-versus-feed map does not exist)"
    g["blocking_evidence"] = {
        "summary": "NOT_EVALUATED until the validated H-1 thrust-versus-feed map exists; statewise feed-state "
                   "sufficiency replaces the fixed 0.38 mg/s gate (0.38-3.2 mg/s = characterization coverage only)",
        "rule": ["for each required orbit / environment state: required drag-compensation thrust from the registered "
                 "spacecraft drag basis", "minimum feed state from the measured / validated H-1 map for the actual "
                 "atmospheric composition within the admitted power / thermal envelope",
                 "upstream chain delivers at least that feed state"],
        "feed_state_record": ["mass flow", "pressure", "temperature", "species composition",
                              "transient / ripple quality"],
        "removed": "the 0.38 mg/s (and ~1.3 mg/s) fixed-number gate: not flight requirements",
        "characterization_coverage_mg_s": list(CHARACTERIZATION_COVERAGE_MG_S),
        "characterization_coverage_role": "CHARACTERIZATION_COVERAGE_ONLY_NOT_A_PASS_FAIL_REQUIREMENT",
        "engineering_warning": f"the parametric upstream frontier ({upstream_frontier_mg_s} mg/s all-state, single "
                               "setpoint; read from the current F7 outputs by the F9 builder) is low relative to the "
                               "ground-characterization envelope: an engineering warning, not a demonstrated requirement failure (A9.13 owner_statements.flight_flow_requirement)",
        "evaluator": "a9_16_f9.ag12_feed_state_sufficiency (fail closed; refuses a fixed mg/s gate)",
        "rfp_citation_status": L.RFP_PENDING}
    g["sources"] = g["sources"] + [dsrc("F9-OQ-02"), dsrc("OQ-F4-04")]
    g = by["AG-13"]
    g["gate"] = "statewise drag compensation T_available(state) - D_spacecraft(state) >= 0 (A9.13 OQ-F78-01)"
    g["blocking_evidence"] = {
        "summary": "statewise T - D >= 0 at every required state; NOT_EVALUATED (no admitted thrust, no host-"
                   "spacecraft ICD for D_spacecraft)",
        "rule": "hard constraint at every required evaluated flight / environment state in the 180-230 km envelope, "
                "thrust and drag at the same state; worst-state and orbit-averaged margins reported additionally; the "
                "orbit average never hides a statewise deficit",
        "missing": ["thrust (AG-02)", "actual host-spacecraft ICD for D_spacecraft (OQ-F78-04: sourced reference "
                    "geometry is REFERENCE/PARAMETRIC only)"],
        "evaluator": "a9_16_f9.ag13_statewise (fail closed)"}
    g["sources"] = g["sources"] + [dsrc("OQ-F78-01"), dsrc("OQ-F78-04")]
    g = by["AG-15"]
    # status and blocking evidence come from the registered RFP + RVM re-base (build_gates -> ag15_f9.assess); the
    # A9.13 clarification is recorded with the gate, never overriding the derived status
    if not isinstance(g["blocking_evidence"], dict) or "assessment" not in g["blocking_evidence"]:
        raise SystemExit("REFUSED: AG-15 carries no registration assessment (ag15_f9)")
    g["blocking_evidence"]["a9_13_clarification"] = (
        "register the official RFP in the repository evidence system with immutable provenance / sha256 and re-base "
        "the RVM requirements against it; secondary transcriptions are not enough (A9.13 F9-OQ-03 AG-15 clarification)")
    g["sources"] = g["sources"] + [dsrc("F9-OQ-03")]
    a15 = g["blocking_evidence"]["assessment"]
    for gg in gates:
        if gg["id"] == "AG-15" and gg["evidence_sufficient_for_freeze"]:
            # only on the owner closure record (A9.22 G3; ag15_f9 fail-closed check) and determining evidence
            assert a15["closes"] and a15["determining_evidence"]["closes"], "AG-15"
            assert "owner_closure_recorded" in a15["evidence_parts"], "AG-15"
            continue
        assert gg["evidence_sufficient_for_freeze"] is False, gg["id"]
    return gates


def _set(p, **kw):
    for k, v in kw.items():
        p[k] = v


def apply_rows(rows: list, ref, get) -> list:
    by = {r["id"]: r for r in rows}
    touched = []

    def note(r, qids, **kw):
        r["a9_16"] = {"decisions": [L.cite(q) if not q.startswith("A9.15") else "A9.15 governing_rule (" +
                                    L.LOADED["A9.15"]["json"] + " sha256 " + L.LOADED["A9.15"]["json_sha256"] + ")"
                                    for q in qids], **kw}
        touched.append(r["id"])

    r = by["AFC-UP-IN-05"]
    _set(r, value="TBD - sourced / buildable intake structural definition required before LOCK-1; until then wall "
                  "material / thickness, AO coating and support fraction only as labelled PARAMETRIC_SENSITIVITY "
                  "budgeting assumptions (no CBE, no frozen mass, no structural qualification)",
         basis=r["basis"] + "; A9.13 F1Q-02", freeze_status="TBD_AFTER_EVIDENCE",
         evidence_to_advance=["sourced design: material, wall thickness, manufacturing method, support / frame "
                              "geometry, AO protection, coating thickness / density, tolerances, mass calculation, "
                              "structural / thermal evidence (before LOCK-1)"])
    r["source"] = r["source"] + [dsrc("F1Q-02")]
    note(r, ["F1Q-02"])

    r = by["AFC-UP-IN-07"]
    _set(r, value="TBD - spacecraft / AOCS relative-wind pointing envelope (interface requirement); 0 / 2 / 5 deg are a "
                  "sensitivity set only, 5 deg is not a validated maximum",
         basis=r["basis"] + "; A9.13 F1Q-03", freeze_status="TBD_AFTER_EVIDENCE",
         evidence_to_advance=["registered AOCS pointing envelope", "intake surface v2 over that envelope (A9.9 F1Q-04, "
                              "PENDING_STEP_2_MODEL_CHANGE); direct TPMC meanwhile; no extrapolation"])
    r["source"] = r["source"] + [dsrc("F1Q-03")]
    note(r, ["F1Q-03", "F1Q-04"])

    r = by["AFC-UP-FI-01"]
    _set(r, value="TBD - baseline function decided: non-propellant particulate / debris protection with high propellant "
                  "transmission and low O recombination (inert / low-recombination, catalytic O->O2 only as a "
                  "separate research variant; FC-00 'none' = analytical reference bound only); concept not selected",
         basis=r["basis"] + "; A9.13 F2-OQ-01 / F2-OQ-02 / F2-OQ-03", freeze_status="TBD_AFTER_EVIDENCE",
         evidence_to_advance=["quantitative filter acceptance pre-registered before LOCK-1 (capture efficiency vs "
                              "particle class, species-resolved transmission, pressure-loss / conductance penalty, O "
                              "recombination probability, retained capacity, AO erosion / durability, effect on AG-12)",
                              "evidenced filter records for a concept (P4 APP-FILTER)"])
    r["source"] = r["source"] + [dsrc("F2-OQ-01"), dsrc("F2-OQ-02"), dsrc("F2-OQ-03")]
    note(r, ["F2-OQ-01", "F2-OQ-02", "F2-OQ-03"])

    r = by["AFC-UP-FI-02"]
    _set(r, value="intake / channel array -> filter -> compressor inlet (downstream of the primary intake / "
                  "collimator, upstream of the compressor); axial location, area and thermal state stay design variables",
         tolerance="n/a (decision / rule)", evidence_class="owner-allocation", value_label="RULE",
         basis="A9.13 F2-OQ-04 (S6.6)", freeze_status="FREEZE_CANDIDATE", evidence_to_advance=[])
    r["source"] = r["source"] + [dsrc("F2-OQ-04")]
    note(r, ["F2-OQ-04"], separate_element="A9.13 UPSTREAM_ICD-Q1: the filter is a distinct production-path element "
                                           "(code change PENDING_STEP_3_ARCHITECTURE)")

    r = by["AFC-UP-CO-04"]
    _set(r, basis=r["basis"] + "; A9.9 OQ-F3-01 / F9-OQ-04 MCC-03: registered rotor-strength basis required "
                               "(PENDING_STEP_2_MODEL_CHANGE)",
         freeze_status="TBD_AFTER_EVIDENCE",
         evidence_to_advance=["registered rotor-strength basis record (alloy spec, product form, heat treatment, "
                              "section, design temperature, cited statistical allowable basis, yield and ultimate vs "
                              "temperature, density, design / test factors, max speed, proof-spin basis); until then "
                              "rotor qualification NOT_EVALUATED_MATERIAL_BASIS; factor 2.0 only a labelled legacy "
                              "sensitivity case"])
    r["source"] = r["source"] + [dsrc("OQ-F3-01")]
    note(r, ["OQ-F3-01", "F9-OQ-04"], application_status="PENDING_STEP_2_MODEL_CHANGE")

    r = by["AFC-UP-PL-03"]
    _set(r, value="orbit-state-scheduled plenum setpoint = baseline control architecture (schedule only on measurable / "
                  "estimable flight states); fixed setpoint = robustness / degraded-mode fallback and comparison "
                  "reference; the schedule itself not frozen until compressor / feed / H-1 validated domains exist",
         tolerance="n/a (decision / rule)", evidence_class="owner-allocation", value_label="RULE",
         basis="A9.13 OQ-F4-01 (S6.10)", freeze_status="FREEZE_CANDIDATE", evidence_to_advance=[])
    r["source"] = r["source"] + [dsrc("OQ-F4-01")]
    note(r, ["OQ-F4-01"])

    r = by["AFC-PR-ICP-05"]
    _set(r, value="delta_B_acc = max_ROI |B_H1+ICP - B_H1| / max_ROI |B_H1| over the preregistered H-1 acceleration-"
                  "region ROI and relevant magnet states; provisional design requirement delta_B_acc <= 0.05 (owner "
                  "engineering allocation, may be tightened, never relaxed post hoc); absolute stray field at IP-EXIT "
                  "and through the ICP volume reported",
         tolerance="n/a (decision / rule)", evidence_class="owner-allocation", value_label="RULE",
         basis="A9.14 F6-OQ-04 (S7.9)", freeze_status="OPEN",
         evidence_to_advance=["FEMM of MC-1 covering the ICP region (F6-IF-N02) to evaluate delta_B_acc",
                              "later H-1 sensitivity evidence (may tighten the provisional 0.05, never relax it)"])
    r["source"] = r["source"] + [dsrc("F6-OQ-04")]
    note(r, ["F6-OQ-04"], evaluation="NOT_EVALUATED until FEMM of MC-1 covering the ICP region (F6-IF-N02)")

    r = by["AFC-PR-CL-04"]
    _set(r, units="V (350 V operating class)", tolerance="n/a (decision / rule)",
         basis="owner row 81; A9.8 OQ-RFQV2-06 / OQ-RFQV2-08: >= 525 V design withstand, 1.05 kV DC / 60 s initial "
               "DWV (supplier certificate + in-house assembled test, per-path leakage limit pre-registered); RF, "
               "Paschen and combined RF+DC stress separately qualified",
         freeze_status="FREEZE_CANDIDATE", evidence_to_advance=[])
    r["source"] = r["source"] + [dsrc("OQ-RFQV2-06"), dsrc("OQ-RFQV2-08")]
    note(r, ["OQ-RFQV2-06", "OQ-RFQV2-08"], design_withstand_V_min=525, initial_dwv="1.05 kV DC / 60 s",
         reverification="700 V DC / 60 s triggered only (A9.14 P1Q-17)")

    r = by["AFC-SY-PPU-07"]
    _set(r, value="TBD - redundant / independent critical control, power-switching, telemetry and sensor paths where an "
                  "individual failure would defeat the mission / safe state, proven by the single-point-failure "
                  "analysis; no duplicate thrusters, ICP modules or complete mechanical chains required; row-55 limited "
                  "redundancy remains for the physical thruster / ICP hardware only",
         evidence_class=None, tolerance="TBD",
         basis="owner row 55; A9.14 RVMQ-01 (S9.13) / OD12 (S9.11); RFP clause owner-stated, pending registration (AG-15)",
         freeze_status="TBD_AFTER_EVIDENCE",
         evidence_to_advance=["single-point-failure / FMEA analysis of electronics and sensors",
                              "official RFP registered (AG-15)"])
    r["source"] = r["source"] + [dsrc("RVMQ-01"), dsrc("OD12")]
    note(r, ["RVMQ-01", "OD12"], rfp_citation_status=L.RFP_PENDING)

    mp3_lines = {"AFC-SY-MASS-AL-04": (3, "MQ-03", 4.2048), "AFC-SY-MASS-AL-07": (6, "MQ-04", 6.0),
                 "AFC-SY-MASS-AL-08": (7, "MQ-05", 5.9148)}      # A9.24 AFI-01 re-base (mass / power v4)
    for rid, (idx, qid, floor) in mp3_lines.items():
        r = by[rid]
        line = get("MP4", f"/lines/hall_icp_neutralizer/{idx}")
        assert line["line"] == rid.split("-", 3)[-1], rid
        part = [x for x in get("MP4", "/rollups/0/parts") if x["line"] == line["line"]][0]
        assert part["used"] == "MEV_PLANNING_FLOOR" and math.isclose(part["kg"], floor), (rid, part)
        _set(r, value=floor, units="kg (MEV planning floor)", tolerance="n/a (planning floor, not a CBE)",
             evidence_class="owner-allocation", value_label="ALLOCATION",
             basis=f"A9.14 {qid}: MEV planning floor (owner-stated); replaced by 1.20 x the actual CBE when it exists "
                   "(mass / power v4" + ("; A9.24 AFI-01: cathode-feed PFCV removed from the 6.0528 kg owner floor, "
                                         "second series latch kept (AFI-01-S1 OWNER_DECIDED_KEEP_SECOND_SERIES_LATCH, "
                                         "A9.25 message 8)" if qid == "MQ-05" else "") + ")",
             freeze_status="OPEN", evidence_to_advance=["CBE (then weighed article) for the line"])
        r["source"] = r["source"] + [ref("MP4", f"/lines/hall_icp_neutralizer/{idx}"), dsrc(qid)]
        note(r, [qid, "MQ-01"])

    r = by["AFC-SY-MASS-ROLL"]
    roll = get("MP4", "/rollups/0")
    _set(r, value={"reading": roll["reading"], "dry_known_kg": roll["dry_known_kg"],
                   "system_margin_kg": roll["system_margin_kg"], "reserve_kg": roll["reserve_kg"],
                   "lines_without_value": roll["lines_without_value"],
                   "wet_vs_40kg": {str(w["xe_case_kg"]): w["state"] for w in roll["wet"]
                                   if w["reference"] == "HARD_40_WET"}},
         basis="mass / power v4 (v3 + A9.24 AFI-01 AL-08 re-base) single MEV reading (A9.14 MQ-01 / MQ-02 / MQ-10): "
               "20 % system margin replaces the 4 kg "
               "reserve; mass closure by redesign, never by margin relaxation",
         note="evidence-based wet mass does not close against 40 kg at 2 / 5 / 10 kg loaded Xe (MQ-10: reduce actual "
              "CBE; no margin relaxation)",
         freeze_status="TBD_AFTER_EVIDENCE",
         evidence_to_advance=["CBE for every BOM line", "controls line AL-09 allocation (MPV3Q-01, TBD_OWNER)"])
    r["source"] = r["source"] + [ref("MP4", "/rollups/0"), dsrc("MQ-02"), dsrc("MQ-10")]
    note(r, ["MQ-01", "MQ-02", "MQ-10"])

    r = by["AFC-SY-CTL-01"]
    _set(r, value=["establish gas / plenum / feed state", "set H-1 magnet state", "ignite / stabilize ICP",
                   "verify electron-source / current condition", "apply Hall discharge voltage",
                   "verify sustained Hall discharge"],
         evidence_class="owner-allocation", evidence_note="owner baseline atmospheric start sequence; maximum one "
                                                           "initial attempt + two retries under registered dwell / "
                                                           "thermal limits; a C1-selected variant uses its own "
                                                           "qualified heater / keeper sequence",
         basis="SEQUENCE OWNER_DECIDED (A9.14 OD5, S9.9); dwell / thermal limits PENDING_REGISTRATION from the actual "
               "hardware (A9.10 P1Q-02; no number set for the ICP-first sequence - the 120 s / 360 s C1 dwell booking "
               "applies to the C1-selected variant only); A9-02 template carried as the implementation reference",
         freeze_status="OPEN", evidence_to_advance=["measured start-up transient record (1 ms gate)",
                                                    "registered dwell / thermal limits (A9.10 P1Q-02)"])
    r["source"] = r["source"] + [dsrc("OD5"), dsrc("P1Q-02")]
    note(r, ["OD5", "OQ-A907-01", "P1Q-02"], max_attempts=3, sequence_status="OWNER_DECIDED (A9.14 OD5)",
         dwell_thermal_limits="PENDING_REGISTRATION (A9.10 P1Q-02; NOT_EVALUATED_REGISTRATION until registered)",
         why_open="the decided sequence becomes a design value only with the registered dwell / thermal limits and "
                  "the measured start-up transient (A9.16 repair F8)")

    r = by["AFC-SY-CTL-04"]
    _set(r, value="scheduled plenum setpoint baseline (fixed setpoint fallback); F4 transient metrics (2 % band, 60 s "
                  "window, E0..E7, orbit-modulation cases) accepted provisionally as the pre-LOCK-2 engineering "
                  "framework, not final H-1 tolerances",
         evidence_class="owner-allocation", tolerance="n/a (decision / rule)", value_label="RULE",
         basis="A9.13 OQ-F4-01 / OQ-F4-03", freeze_status="OPEN",
         evidence_to_advance=["H-1 measured feed sensitivity at LOCK-2 (governs if tighter than the F4 metric)"])
    r["source"] = r["source"] + [dsrc("OQ-F4-01"), dsrc("OQ-F4-03")]
    note(r, ["OQ-F4-01", "OQ-F4-03"])

    r = by["AFC-SY-XE-01"]
    _set(r, value="RFP-required system Xenon propulsion capability in both configurations, independent of C1: the "
                  "system supports ambient atmospheric propellant (180-230 km) AND Xenon as separate selectable "
                  "operating modes with separate ambient-air and Xe tanks / paths (not a premix); Xe is not a "
                  "contingency; events, duration and flow TBD",
         basis="owner row 6; A9.15 governing_rule; A9.14 XA9Q-07 / OD6 as amended by A9.15; RFP content owner-stated, "
               "pending registration (AG-15)")
    r["source"] = r["source"] + [a915src(), dsrc("XA9Q-07"), dsrc("OD6")]
    note(r, ["A9.15", "XA9Q-07", "OD6"], rfp_citation_status=L.RFP_PENDING,
         icp_gas_mode="unchanged: A9.1 G-REUSE primary; G-XE a declared ICP-feed variant")

    r = by["AFC-SY-XE-03"]
    _set(r, basis="owner row 48; A9.14 XA9Q-01 / MQ-09 / OQ-A910-01: LOADED Xe cases, M_loaded = M_mission_usable + "
                  "M_reserve + M_residual (residual never added again)",
         value_label="ALLOCATION", freeze_status="FREEZE_CANDIDATE", evidence_to_advance=[])
    r["source"] = r["source"] + [dsrc("XA9Q-01"), dsrc("MQ-09"), dsrc("OQ-A910-01")]
    note(r, ["XA9Q-01", "MQ-09", "OQ-A910-01"])

    r = by["AFC-SY-XE-06"]
    _set(r, basis="Xe accounting; A9.14 XA9Q-06 / OQ-RFQ-09: 75-bar placeholder retired; suppliers propose MEOP and "
                  "design / proof factors against the 323 K loaded-Xe cases; basis selected after comparing compliant "
                  "certified quotations",
         evidence_to_advance=["tank / regulator quotations (RFQ v3) and the selected certified solution"])
    r["source"] = r["source"] + [dsrc("XA9Q-06"), dsrc("OQ-RFQ-09")]
    note(r, ["XA9Q-06", "OQ-RFQ-09"])

    r = by["AFC-SY-XE-08"]
    al08 = get("MP4", "/lines/hall_icp_neutralizer/7")
    assert al08["line"] == "AL-08" and math.isclose(al08["value"]["value_kg"], 5.9148), al08["value"]
    _set(r, value={"AL-08_MEV_planning_floor_kg": al08["value"]["value_kg"],
                   "evidence_floor_cbe_kg": al08["evidence_floor_cbe_kg"]},
         basis="A9.14 MQ-05: AL-08 = complete Xe storage / flow hardware (tank, regulator, valves, plumbing, mounting, "
               "thermal); planning floor replaced by quotations / design; A9.24 AFI-01 (mass / power v4): the C1 "
               "cathode-feed PFCV removed from the v3 6.0528 / 5.044 kg floor; valves 0.455 kg = latch #1 0.170 + "
               "latch #2 0.170 (SECOND SERIES FLIGHT XE ISOLATION VALVE, row 55 dual series isolation; AFI-01-S1 "
               "OWNER_DECIDED_KEEP_SECOND_SERIES_LATCH, A9.25 message 8) + PFCV 0.115; no conventional "
               "hollow-cathode hardware remains in flight AL-08; PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN",
         freeze_status="OPEN", evidence_to_advance=["quotations / design CBE for the complete Xe hardware"])
    r["source"] = r["source"] + [ref("MP4", "/lines/hall_icp_neutralizer/7"), dsrc("MQ-05")]
    note(r, ["MQ-05"])

    # A9.16 repair F8: the Xe rows are re-pointed to the current Xe accounting v3 / mass-power v3 (the v2 / state-v4
    # sources stay listed as the A9.7 basis, marked history); a state-v4 row source gets its state-v5 row beside it
    def _find(key, lst_ptr, field, value):
        lst = get(key, lst_ptr)
        hits = [i for i, x in enumerate(lst) if isinstance(x, dict) and x.get(field) == value]
        if len(hits) != 1:
            raise SystemExit(f"REFUSED: {key}{lst_ptr}: {field}={value!r} found {len(hits)} times")
        return f"{lst_ptr}/{hits[0]}"
    xe3_ptrs = {"AFC-SY-XE-01": ["/propellant_policy"], "AFC-SY-XE-02": [_find("XE3", "/items", "id", "XV2-21")],
                "AFC-SY-XE-03": [_find("XE3", "/items", "id", "XV2-30"), "/design_cases/loaded_split"],
                "AFC-SY-XE-04": [_find("XE3", "/items", "id", "XV2-23"), _find("XE3", "/items", "id", "XV2-24")],
                "AFC-SY-XE-05": [_find("XE3", "/items", "id", "XV2-25")],
                "AFC-SY-XE-06": [_find("XE3", "/items", "id", "XV2-28"), _find("XE3", "/items", "id", "XV2-29")],
                "AFC-SY-XE-07": [_find("XE3", "/items", "id", "XV2-39")],
                "AFC-SY-XE-08": [_find("MP4", "/lines/hall_icp_neutralizer", "line", "AL-08")]}
    for rid, ptrs in xe3_ptrs.items():
        r = by[rid]
        key = "MP4" if rid == "AFC-SY-XE-08" else "XE3"
        hist = []
        for x in r["source"]:
            if isinstance(x, dict) and x.get("path", "").endswith(("xe_accounting_a9_v2.json",
                                                                  "mass_power_a9_v2.json",
                                                                  "owner_questions_state_v4.json")):
                x["role"] = "HISTORY (A9.7 basis); the current source is listed in current_sources"
                hist.append(x["path"])
        cur = [ref(key, p) for p in ptrs]
        for x in r["source"]:
            if isinstance(x, dict) and x.get("path", "").endswith("owner_questions_state_v4.json"):
                rid4 = x.get("pointer", "")
                v4row = get("OQ4", rid4) if rid4.startswith("/rows/") else None
                if isinstance(v4row, dict) and v4row.get("id"):
                    cur.append(ref("OQ5", _find("OQ5", "/rows", "id", v4row["id"])))
        r["source"] = r["source"] + cur
        r["current_sources"] = [c["path"] + c["pointer"] for c in cur]
        r.setdefault("a9_16", {})["current_source_rule"] = (
            "xe_accounting_a9_v3 / mass_power_a9_v4 / state v5 govern; the v2 / v4 sources are history (A9.16 "
            "repair F8; mass / power v4 since A9.24 AFI-01)")
        if rid not in touched:
            touched.append(rid)
    return touched


def apply_upstream_pareto(up: dict) -> dict:
    up["representative"] = {"status": "DEFERRED_BY_OWNER", "owner_question": "F9-OQ-01", "selected": None,
                            "decision": L.cite("F9-OQ-01"), "decision_code": L.answer("F9-OQ-01")["decision_code"]}
    up["carried_to_lock1_as_set"] = True
    up["regenerate_before_freeze_after"] = ["S2 production-model corrections (A9.9)", "intake-surface v2",
                                            "filter implementation / evidence",
                                            "compressor search expanded beyond the inherited F3-front subset",
                                            "T-1 / T-2 data", "DI-1.3 surface evidence"]
    up["single_point_studies"] = ("evaluate all remaining Pareto members, or label a selected member an engineering "
                                  "reference, not the frozen architecture")
    up["robust_rule_owner"] = {"decision": L.cite("OQ-F78-02"),
                               "rule": "robust over every presently admitted Maxwell / CLL and accommodation scenario "
                                       "until DI-1.3 narrows it (preregistered mapping)"}
    return up


MCC_AUTH = {"MCC-01": "F1Q-01", "MCC-02": "F9-OQ-04", "MCC-03": "F9-OQ-04", "MCC-04": "UPSTREAM_ICD-Q7",
            "MCC-05": "F9-OQ-04", "MCC-06": "F9-OQ-04", "MCC-07": "F9-OQ-04", "MCC-08": "F9-OQ-04"}
# MCC-08 (DIV-04, max_hits_cap < 1) was not named in the F9-OQ-04 question; the owner's verbatim MCC-05 answer covers it:
MCC08_BASIS = "`max_hits` and related hit-budget parameters shall have valid positive integer domains."


def apply_mcc(mccs: list) -> list:
    for m in mccs:
        q = MCC_AUTH[m["id"]]
        m["status"] = "OWNER_AUTHORISED_PENDING_STEP_2_MODEL_CHANGE"
        m["owner_authorisation"] = {"decision": L.cite(q), "decision_code": L.answer(q)["decision_code"]}
        if m["id"] == "MCC-08":
            if MCC08_BASIS not in L.answer(q)["verbatim_excerpt"]:
                raise SystemExit("MCC-08: the owner's MCC-05 wording on related hit-budget parameters is missing")
            m["owner_authorisation"]["basis_verbatim"] = MCC08_BASIS
            m["owner_authorisation"]["note"] = ("not named in the F9-OQ-04 question; covered by the owner's MCC-05 "
                                                "answer on related hit-budget parameters (max_hits_cap)")
        m["implemented_here"] = False
    return mccs


def answered_f9_questions(qs: list) -> list:
    out = []
    for q in qs:
        a = L.answer(q["id"])
        q = dict(q)
        q.update({"status_when_raised": q["status"], "status": "OWNER_DECIDED", "decision": L.cite(q["id"]),
                  "decision_code": a["decision_code"], "answer_verbatim": a["verbatim_excerpt"]})
        if a["rfp_citation_status"]:
            q["rfp_citation_status"] = a["rfp_citation_status"]
        if a["decision"] == "A9.9":
            q["application_status"] = "PENDING_STEP_2_MODEL_CHANGE"
        out.append(q)
    return out


def rollup_v5(rollup: dict, v5: dict, v5_ref) -> dict:
    by = {}
    for r in v5["rows"]:
        if r.get("kind") == "a9_7_lane_question" or r.get("v4_status") == "TBD_OWNER" or r["status"] == "TBD_OWNER":
            by[r["id"]] = r["status"]
    rollup["state_v5"] = {"source": v5_ref, "tbd_owner_count": v5["tbd_owner_count"],
                          "open_owner_questions": v5["open_owner_questions"],
                          "status_of_rolled_up_questions": {
                              **{q["id"]: by[q["id"]] for q in rollup["state_v4_tbd_owner"]},
                              **{q["id"]: by[q["id"]] for q in rollup["a9_7_lane_questions"]},
                              **{q["id"]: by[q["id"]] for q in rollup["other_existing_open_questions_cited"]},
                              **{qid: by[qid] for qid in rollup["new_f9_questions"]}}}
    rollup["rule_v5"] = ("answers come only from the owner (A9.8 .. A9.15, recorded in owner_questions_state_v5); this "
                         "roll-up reports their status and answers nothing itself")
    return rollup


def owner_answers_applied() -> list:
    A = ARTIFACT
    # how_applied texts are the A9.16 step-1 application record (history, consumed verbatim by the A9.16 application
    # matrix); the current AG-15 status is derived in build_gates from the registered RFP (ag15_f9)
    rows = [L.applied_row("F9-OQ-03", A, ["architecture_gates[*].owner_approved", "AG-03", "AG-12", "AG-13", "AG-15"],
                          "AG-01..AG-15 approved with the determining-evidence standard (gate_closes, fail closed); "
                          "AG-03 successor held-out validation; AG-15 BLOCKED_RFP_NOT_REGISTERED", [TEST]),
            L.applied_row("F9-OQ-02", A, ["AG-12"], "AG-12 = statewise feed-state sufficiency, NOT_EVALUATED until the "
                          "validated H-1 thrust-vs-feed map; 0.38 mg/s gate removed, 0.38-3.2 mg/s coverage only "
                          "(ag12_feed_state_sufficiency refuses a fixed gate)", [TEST]),
            L.applied_row("OQ-F78-01", A, ["AG-13"], "statewise T - D >= 0 (ag13_statewise; orbit average reported "
                          "only)", [TEST]),
            L.applied_row("OQ-F78-04", A, ["AG-13"], "D_spacecraft NOT_EVALUATED for freeze until the actual ICD", [TEST]),
            L.applied_row("F9-OQ-01", A, ["upstream_pareto.representative"], "robust Pareto set carried; no "
                          "representative (DEFERRED_BY_OWNER)", [TEST]),
            L.applied_row("OQ-F78-02", A, ["upstream_pareto.robust_rule_owner"], "all admitted surface scenarios", [TEST]),
            L.applied_row("F9-OQ-04", A, ["MCC-02", "MCC-03", "MCC-05", "MCC-06", "MCC-07", "MCC-08"],
                          "owner-authorised; PENDING_STEP_2_MODEL_CHANGE (not implemented here)", [TEST]),
            L.applied_row("F1Q-01", A, ["MCC-01"], "owner-authorised; PENDING_STEP_2_MODEL_CHANGE", [TEST]),
            L.applied_row("UPSTREAM_ICD-Q7", A, ["MCC-04"], "owner-authorised; PENDING_STEP_2_MODEL_CHANGE", [TEST])]
    for qid, rec in (("F1Q-02", "AFC-UP-IN-05"), ("F1Q-03", "AFC-UP-IN-07"), ("F2-OQ-01", "AFC-UP-FI-01"),
                     ("F2-OQ-02", "AFC-UP-FI-01"), ("F2-OQ-03", "AFC-UP-FI-01"), ("F2-OQ-04", "AFC-UP-FI-02"),
                     ("OQ-F3-01", "AFC-UP-CO-04"), ("OQ-F4-01", "AFC-UP-PL-03"), ("F6-OQ-04", "AFC-PR-ICP-05"),
                     ("OQ-RFQV2-06", "AFC-PR-CL-04"), ("OQ-RFQV2-08", "AFC-PR-CL-04"), ("RVMQ-01", "AFC-SY-PPU-07"),
                     ("OD12", "AFC-SY-PPU-07"), ("MQ-03", "AFC-SY-MASS-AL-04"), ("MQ-04", "AFC-SY-MASS-AL-07"),
                     ("MQ-05", "AFC-SY-MASS-AL-08"), ("MQ-01", "AFC-SY-MASS-ROLL"), ("MQ-02", "AFC-SY-MASS-ROLL"),
                     ("MQ-10", "AFC-SY-MASS-ROLL"), ("OD5", "AFC-SY-CTL-01"), ("OQ-F4-03", "AFC-SY-CTL-04"),
                     ("XA9Q-07", "AFC-SY-XE-01"), ("OD6", "AFC-SY-XE-01"), ("XA9Q-01", "AFC-SY-XE-03"),
                     ("MQ-09", "AFC-SY-XE-03"), ("OQ-A910-01", "AFC-SY-XE-03"), ("XA9Q-06", "AFC-SY-XE-06"),
                     ("OQ-RFQ-09", "AFC-SY-XE-06")):
        rows.append(L.applied_row(qid, A, [rec], "parameter row updated (value / basis / freeze status / evidence to "
                                  "advance) with the decision source", [TEST]))
    rows.append(L.a915_row(A, ["AFC-SY-XE-01", "configuration"], "Xe = RFP-required system capability in both "
                           "configurations, separate air / Xe tanks and modes; C1 Xe only if a selected C1 needs it; "
                           "ICP gas mode G-REUSE unchanged", [TEST]))
    return rows
