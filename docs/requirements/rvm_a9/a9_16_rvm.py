"""A9.16 step 1 (integration lane): owner decisions applied to the A9 requirement-verification matrix (RVM).

Record-level application (row statuses are still assigned by rvm_rules.assign_status; nothing becomes PASS):
  A9.14 OD2 (S9.7)     statewise envelope quantifier: every required state of the frozen 180-230 km mission /
                       environment dataset satisfies the hard requirements; worst state and orbit average reported too
  A9.14 OD3 (S9.8)     design atmosphere states from the versioned orbit-resolved frozen dataset (authorised by A9.13
                       OQ-F4-05; built: atmosphere_msis21_orbit_v1_design_states_v2, A9.17); no hand-picked F10.7 /
                       density points. The statewise evaluation over that set is NOT_EVALUATED here: the design-layer
                       consumers still evaluate the five orbit-averaged ENVELOPE_STATES (A9.16 repair RVF-03)
  A9.14 OD6 (S9.10) + A9.15   'air + Xe' = the system provides BOTH ambient-air and Xenon operating capability (separate
                       selectable modes, separate tanks / paths, not a premix); never a contingency reading
  A9.14 XA9Q-07 + A9.15       Xe capability applies to hall_icp_neutralizer (and hall_c1_reference), independent of C1
  A9.14 OD12 (S9.11)   explicit compliance gates: indigenous content (75 % project target; subsystem targets thruster
                       > 80 %, intake > 80 %, compressor / storage > 60 %, power electronics > 70 %; RFP > 60 % statement
                       discrepancy recorded for DRDO clarification), single-point-failure FMEA gate for electronics /
                       sensors, N2 + atomic-O operation qualification
  A9.14 OD14 (S9.12)   atmospheric off-state ignition = DERIVED_PROJECT_REQUIREMENT, not RFP_EXPLICIT
  A9.14 RVMQ-01 (S9.13) RVM-19 re-based on the RFP electronics / sensor redundancy clause; no full thruster / ICP
                       duplication
  A9.14 OQ-VI-04 (S8.5) ICP life basis >= 15,000 h cumulative energized operation (literal RFP 'Ignition Time' wording
                       preserved); restart / cycle count from the frozen mission profile (TBD, not invented)
  A9.14 OD5 / OQ-A907-01 / XA9Q-02, XA9Q-01, A9.12 OQ-A907-03 / -05 / -09 / -10: open readings of rows carried as
                       OWNER_DECIDED with their decision.
RFP citations (A9.16 repair RFP-03 / RVF-04): the official RFP is registered by hash with a verbatim clause transcription
(docs/requirements/rfp_official/rfp_registration_v1.json, A9.17 RFP), so every RFP-cited fact of a re-based row carries
rfp_citation_status REGISTERED_CLAUSE with the clause ids (registered_rfp_citations, run after the rfp_rebase); the
step-1 label OWNER_STATED_PENDING_RFP_REGISTRATION is kept as history (rfp_citation_status_as_applied). AG-15 closure is
the owner's, so requirement_frozen stays false for RFP rows.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "docs" / "decisions" / "application"))
import a9_16_lib as L  # noqa: E402

ARTIFACT = "docs/requirements/rvm_a9/rvm_a9_v1.json"
# A9.14 S9.8 OD3 design-state set, built from the frozen orbit-resolved dataset (A9.17 ORBIT; rule-1 frozen data, read
# only). The design-layer statewise evaluators (abep_sim/design: intake_synthesis ENVELOPE_STATES -> F1-F8 architecture
# optimizer, HC-09 / AG-12 / AG-13) do not consume it yet (A9.16 repair RVF-03)
DESIGN_STATES_REL = "abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json"
DESIGN_STATES_ID = "atmosphere_msis21_orbit_v1_design_states_v2"
DESIGN_CONSUMERS_PENDING = ("abep_sim/design/intake_synthesis.py ENVELOPE_STATES (h200_f150 + four alt x F10.7 corners "
                            "of the orbit-averaged atmosphere_msis21_v1)",
                            "abep_sim/design/architecture_optimizer.py STATES = isy.ENVELOPE_STATES (F1-F8; HC-09 "
                            "'every orbit state', AG-12 / AG-13 statewise constraints)")
REGISTRATION_REL = "docs/requirements/rfp_official/rfp_registration_v1.json"
REGISTERED = "REGISTERED_CLAUSE"
TEST = "tests/test_rvm_a9.py"
V5 = "docs/budgets/owner_decisions/owner_questions_state_v5.json"
STATEWISE_STATUSES = ("NOT_EVALUATED_DESIGN_STATES_NOT_REGISTERED", "NOT_EVALUATED_STATE_MISSING",
                      "STATEWISE_VIOLATION", "ALL_REQUIRED_STATES_SATISFIED")
IC_SUBSYSTEM_TARGETS = {"thruster": "> 80 %", "intake": "> 80 %", "compressor_storage": "> 60 %",
                        "power_electronics": "> 70 %"}


def statewise_envelope(required_states: list | None, results: dict, comparator) -> dict:
    """A9.14 OD2: every required state must satisfy the requirement; an orbit average never hides a violation.
    required_states: registered state ids of the frozen orbit-resolved dataset (None -> not registered)."""
    if not required_states:
        return {"status": "NOT_EVALUATED_DESIGN_STATES_NOT_REGISTERED"}
    missing = [s for s in required_states if results.get(s) is None]
    if missing:
        return {"status": "NOT_EVALUATED_STATE_MISSING", "missing": missing}
    bad = [s for s in required_states if not comparator(results[s])]
    vals = [results[s] for s in required_states]
    out = {"status": "STATEWISE_VIOLATION" if bad else "ALL_REQUIRED_STATES_SATISFIED", "violating_states": bad,
           "worst_state_value": min(vals), "orbit_average_value": sum(vals) / len(vals)}
    return out


def design_state_set() -> dict:
    """The built A9.14 OD3 design-state set (identity, sha256, size), read from the frozen file; fails closed."""
    p = ROOT / DESIGN_STATES_REL
    if not p.exists():
        raise RuntimeError(f"design-state set missing: {DESIGN_STATES_REL}")
    raw = p.read_bytes()
    d = json.loads(raw)
    if d.get("design_state_set_id") != DESIGN_STATES_ID:
        raise RuntimeError(f"design-state set identity changed: {d.get('design_state_set_id')!r}")
    if d["n_states"] != len(d["states"]) or not d["states"]:
        raise RuntimeError("design-state set state count inconsistent")
    return {"path": DESIGN_STATES_REL, "id": DESIGN_STATES_ID, "sha256": hashlib.sha256(raw).hexdigest(),
            "dataset_id": d["dataset_id"], "dataset_sha256": d["dataset_sha256"], "n_states": d["n_states"],
            "n_required": sum(1 for x in d["states"] if x.get("required")), "orbit_basis": d["orbit_basis"]["status"]}


def ignition_requirement_class(source_text_has_rfp_clause: bool) -> str:
    """A9.14 OD14: no RFP ignition / restart clause is recorded, so the requirement is project-derived."""
    return "RFP_EXPLICIT" if source_text_has_rfp_clause else "DERIVED_PROJECT_REQUIREMENT"


def _decided(o: dict) -> dict:
    qid = o["id"]
    a = L.answer(qid)
    o = dict(o)
    o["status_when_carried"] = o["status"]
    o["status"] = "OWNER_DECIDED"
    o["current_register"] = V5
    o["decision"] = L.cite(qid)
    o["decision_code"] = a["decision_code"]
    o["handling"] = ("answered by the owner (" + a["decision"] + " " + a["sequenced_no"] + "); applied in this row's "
                     "a9_16 record; the row status still follows rvm_rules (no PASS without a verified measurement)")
    if "amended_by" in a:
        o["governing_reading"] = a["amended_by"]["verbatim_excerpt"]
    if a["rfp_citation_status"]:
        o["rfp_citation_status"] = a["rfp_citation_status"]
    return o


ROW_RECORDS = {
    "RVM-01": (["OD2", "OD3"], {
        "envelope_quantifier": "EVERY_REQUIRED_ENVIRONMENT_STATE_FAIL_CLOSED (worst state and orbit average reported "
                               "additionally; an orbit average cannot conceal a statewise violation)",
        "design_states": "REGISTERED_NOT_YET_CONSUMED: " + DESIGN_STATES_ID + " (" + DESIGN_STATES_REL + "; nominal "
                         "states and physical extrema of density / species / temperature / local time / solar activity "
                         "from the frozen orbit-resolved dataset atmosphere_msis21_orbit_v1, A9.17 ORBIT; no hand-picked "
                         "points); the statewise evaluation over it is NOT_EVALUATED because the design-layer consumers "
                         "still evaluate the five orbit-averaged ENVELOPE_STATES",
        "design_state_set": "@design_state_set",
        "design_state_consumers_pending": list(DESIGN_CONSUMERS_PENDING),
        "statewise_status": "NOT_EVALUATED_STATE_MISSING (no design-state result exists for any registered state)",
        "evaluator": "docs/requirements/rvm_a9/a9_16_rvm.py:statewise_envelope"},
        "Operate the ABEP propulsion system in very low Earth orbit over the altitude band 180-230 km: every required "
        "state of the frozen 180-230 km mission / environment dataset must satisfy the applicable hard requirements "
        "(A9.14 OD2); design atmosphere states come from the versioned orbit-resolved dataset (A9.14 OD3; built as "
        "atmosphere_msis21_orbit_v1_design_states_v2, not yet consumed by the design-layer statewise evaluators)."),
    "RVM-08": (["OD12"], {"compliance_gate": "N2_PLUS_ATOMIC_O_OPERATION_QUALIFICATION (A9.14 OD12): evidence that the "
                                             "same propulsion architecture ionizes / operates on the required atmospheric "
                                             "species, not only Ar / Xe"}, None),
    "RVM-09": (["OD12"], {"compliance_gate": "N2_PLUS_ATOMIC_O_OPERATION_QUALIFICATION (A9.14 OD12)",
                          "rfp_citation_status": L.RFP_PENDING,
                          "note": "the owner's statement that the RFP requires ionizing N2 and nascent / atomic O "
                                  "(A9.13 S6.3, A9.15) is confirmed by the registered clauses RFP-P17-05 / RFP-P17-02 "
                                  "(AG-15 closure is the owner's)"}, None),
    "RVM-10": (["XA9Q-07", "XA9Q-01", "OD6"], {
        "propellant_policy": "A9.15 governing rule: " + L.a915_governing_statement(),
        "air_plus_xe": "DUAL_PROPELLANT_CAPABILITY: separate selectable ambient-air and Xenon operating modes with "
                       "separate tanks / paths (not a premix unless an experiment intentionally studies mixing); never "
                       "a contingency interpretation",
        "configurations": "applies to hall_icp_neutralizer and hall_c1_reference; presence or absence of C1 never "
                          "removes it; C1 Xe only if a selected C1 needs it, booked inside the system Xe accounting",
        "icp_gas_mode": "unchanged: A9.1 G-REUSE primary; G-XE a declared ICP-feed variant",
        "rfp_citation_status": L.RFP_PENDING},
        "Provide RFP-required Xenon propulsion capability alongside ambient atmospheric propellant (A9.15): separate "
        "selectable ambient-air and Xe operating modes with separate tanks / paths, in both configurations and "
        "independent of C1; demonstrate a bounded functional Xe-capable operating mode beyond bookkeeping and book every "
        "Xe use (PHASE_TOTAL_FLOW, LOADED cases); Xe reference / health checks are labelled and never atmospheric "
        "evidence."),
    "RVM-12": (["OQ-VI-04"], {
        "icp_life_basis": ">= 15,000 h cumulative energized operating life (conservative design basis pending "
                          "clarification); the literal RFP entry 'Ignition Time' > 15,000 h is preserved verbatim in the "
                          "requirement record",
        "icp_cycles": "TBD from the frozen mission-mode profile (not invented)",
        "rfp_citation_status": L.RFP_PENDING}, None),
    "RVM-14": (["OD5", "OD14", "OQ-A907-01", "XA9Q-02"], {
        "requirement_class": "DERIVED_PROJECT_REQUIREMENT (atmospheric off-state ignition / restart; not RFP_EXPLICIT; "
                             "A9.14 OD14)",
        "baseline_start_sequence": ["establish gas / plenum / feed state", "set H-1 magnet state",
                                    "ignite / stabilize ICP", "verify electron-source / current condition",
                                    "apply Hall discharge voltage", "verify sustained Hall discharge"],
        # A9.16 repair F3: OD5 limits the ICP-first atmospheric sequence only by 'registered dwell / thermal limits';
        # the 120 s per-dwell cap / 360 s booking belong to the C1 ignition dwell for Xe booking (S9.1 XA9Q-02 /
        # S8.15 OQ-A907-01, owner row 93 'H. Cathode C-1') and to the C1-selected variant only
        "attempts": ("max 1 initial attempt + 2 retries under registered dwell / thermal limits (values registered from "
                     "the actual hardware before P1-S6, A9.10 P1Q-02; NOT_EVALUATED_REGISTRATION until registered; no "
                     "dwell number is set for the ICP-first sequence)"),
        "c1_variant": ("a C1-selected variant uses its separately qualified heater / keeper sequence; its Xe booking "
                       "uses 3 C1 ignition dwells (1 + 2 retries), each <= 120 s, 360 s maximum booking (A9.14 "
                       "OQ-A907-01 / XA9Q-02; applies to the C1 variant only)")}, None),
    "RVM-17": (["OQ-A907-03", "OQ-A907-05", "OQ-A907-09", "OQ-A907-10"], {
        "bounding_corner": "physically admissible joint states only; 1.20 on dissipated loads, environmental loads by "
                           "the registered hot / cold envelope; >= 50 K never relaxed",
        "supplier_ratings": "SUPPLIER_PROVISIONAL only (no design / flight closure)",
        "search_sensitive": "10 K screen label; independent bound before LOCK-1",
        "thermal_status": "UNRESOLVED (never PASS)"}, None),
    "RVM-18": (["OD12"], {
        "compliance_gate": "INDIGENOUS_CONTENT (A9.14 OD12)",
        "project_target_total": ">= 75 %", "subsystem_targets": dict(IC_SUBSYSTEM_TARGETS),
        "source_discrepancy": "the RFP contains a > 60 % statement on one page and a more specific minimum 75 % "
                              "project-deliverable target with subsystem targets; the stricter / more specific targets are "
                              "used internally and the discrepancy is recorded for DRDO clarification",
        "rfp_citation_status": L.RFP_PENDING},
        "Total indigenous content >= 75 % (project target) with subsystem targets thruster > 80 %, intake > 80 %, "
        "compressor / storage > 60 %, power electronics > 70 % (A9.14 OD12; registered RFP-P19-05; the RFP's > 60 % "
        "statement RFP-P18-03 is a recorded discrepancy DISC-03 for DRDO clarification)."),
    "RVM-19": (["RVMQ-01", "OD12"], {
        "rebased_on": "RFP electronics single-point-failure clause RFP-P18-09 and electronics / sensor redundancy "
                      "clause RFP-P18-02 (registered, verbatim in rfp_registration_v1)",
        "compliance_gate": "SINGLE_POINT_FAILURE_FMEA_ELECTRONICS_SENSORS (A9.14 OD12)",
        "required": "redundant / independent critical control, power-switching, telemetry and sensor paths where an "
                    "individual failure would defeat the mission / safe state, proven by the single-point-failure "
                    "analysis",
        "not_required": "duplicate thrusters, duplicate ICP modules or duplicate complete mechanical propulsion chains",
        "row55": "limited redundancy may remain for the physical thruster / ICP hardware, never as a waiver of "
                 "electronics / sensor redundancy",
        "rfp_citation_status": L.RFP_PENDING},
        "Electronics and sensors: no single-point failure that defeats the mission / safe state (registered RFP clauses "
        "RFP-P18-09 / RFP-P18-02): redundant / independent critical control, power-switching, telemetry and sensor paths, "
        "proven by a single-point-failure / FMEA analysis; duplicate thrusters, ICP modules or complete mechanical chains "
        "are not required (A9.14 RVMQ-01)."),
}


def apply(doc: dict) -> dict:
    by = {r["id"]: r for r in doc["rows"]}
    for rid, (qids, rec, text) in ROW_RECORDS.items():
        r = by[rid]
        r["a9_16"] = {"decisions": [L.cite(q) for q in qids], **rec}
        if r["a9_16"].get("design_state_set") == "@design_state_set":
            r["a9_16"]["design_state_set"] = design_state_set()
        if text:
            r["requirement_text_as_carried"] = r["requirement_text"]
            r["requirement_text"] = text
    for r in doc["rows"]:
        r["open_readings"] = [_decided(o) if o["status"] == "TBD_OWNER" else o for o in r["open_readings"]]
    q = doc["open_owner_questions"][0]
    assert q["id"] == "RVMQ-01"
    # 'status' keeps the AS-RAISED value (the immutable state-v4 builder reads it back and accepts only OPEN /
    # TBD_OWNER; A9.16 repair COR-01); status_current governs
    doc["open_owner_questions"] = [dict(q, status_when_raised=q["status"], status=q["status"],
                                        status_current="OWNER_DECIDED",
                                        status_note="'status' = status AS RAISED (state-v4 read-back contract); "
                                                    "answered by the owner - status_current / decision govern",
                                        decision=L.cite("RVMQ-01"),
                                        decision_code=L.answer("RVMQ-01")["decision_code"],
                                        answer_verbatim=L.answer("RVMQ-01")["verbatim_excerpt"])]
    doc["a9_16_compliance_gates"] = [
        {"id": "CG-IC", "gate": "indigenous content", "rvm_row": "RVM-18", "status": "NOT_EVALUATED",
         "decision": L.cite("OD12")},
        {"id": "CG-SPF", "gate": "single-point-failure / FMEA for electronics and sensors", "rvm_row": "RVM-19",
         "status": "NOT_EVALUATED", "decision": L.cite("OD12")},
        {"id": "CG-N2-AO", "gate": "N2 + nascent / atomic O operation qualification", "rvm_row": "RVM-08 / RVM-09",
         "status": "NOT_EVALUATED", "decision": L.cite("OD12")},
    ]
    doc["a9_16_rfp_rule_as_applied"] = (L.RFP_PENDING_NOTE + "; requirement_frozen stays false for every RFP row until "
                                        "AG-15 closes")
    doc["a9_16_rfp_rule"] = ("the official RFP is registered by hash with a verbatim clause transcription (" +
                             REGISTRATION_REL + ", A9.17 RFP); RFP-cited facts carry rfp_citation_status " + REGISTERED +
                             " with the registered clause ids (the step-1 label " + L.RFP_PENDING + " is kept as "
                             "rfp_citation_status_as_applied history); AG-15 closure is the owner's, so "
                             "requirement_frozen stays false for every RFP row until the owner closes AG-15")
    doc["a9_16_owner_answers_applied"] = (
        [L.applied_row(q, ARTIFACT, [rid], "row a9_16 record; open reading OWNER_DECIDED", [TEST])
         for rid, (qids, _, _) in ROW_RECORDS.items() for q in qids]
        + [L.a915_row(ARTIFACT, ["RVM-10"], "'air + Xe' = both ambient-air and Xenon operating capability, separate "
                      "tanks / modes, both configurations; never a contingency reading", [TEST])])
    return doc


def _row_clauses(r: dict) -> list:
    return list(r.get("rfp_clauses") or r.get("related_rfp_clauses") or [])


def _registered(rec: dict, clauses: list, where: str) -> None:
    if rec.get("rfp_citation_status") != L.RFP_PENDING:
        return
    if not clauses:
        raise RuntimeError(f"{where}: an RFP-cited fact maps to no registered clause")
    rec["rfp_citation_status_as_applied"] = L.RFP_PENDING
    rec["rfp_citation_status"] = REGISTERED
    rec["rfp_clause_ids"] = list(clauses)
    rec["rfp_citation_note"] = ("registered clause(s) " + ", ".join(clauses) + " (" + REGISTRATION_REL + "); AG-15 "
                                "closure is the owner's, requirement_frozen stays false")


def registered_rfp_citations(doc: dict) -> dict:
    """A9.16 repair RFP-03 / RVF-04: after the rfp_rebase, every step-1 'OWNER_STATED_PENDING_RFP_REGISTRATION' label
    on a re-based row (a9_16 record, owner-decided open readings) and in a9_16_owner_answers_applied becomes
    REGISTERED_CLAUSE with the row's registered clause ids (determining clauses, else related clauses); the step-1 label
    is kept as rfp_citation_status_as_applied. Fails closed if a label maps to no clause or one survives."""
    if "rfp_rebase" not in doc:
        raise RuntimeError("registered_rfp_citations runs after the rfp_rebase")
    by = {r["id"]: r for r in doc["rows"]}
    for r in doc["rows"]:
        cl = _row_clauses(r)
        if "a9_16" in r:
            _registered(r["a9_16"], cl, r["id"] + " a9_16")
        for o in r["open_readings"]:
            _registered(o, cl, r["id"] + " " + o["id"])
    for a in doc["a9_16_owner_answers_applied"]:
        cl = []
        for rid in a["record_ids"]:
            cl += [c for c in _row_clauses(by[rid]) if c not in cl]
        _registered(a, cl, "a9_16_owner_answers_applied " + a["question_id"])
    left = json.dumps({k: doc[k] for k in ("rows", "a9_16_owner_answers_applied")})
    if '"rfp_citation_status": "' + L.RFP_PENDING + '"' in left:
        raise RuntimeError("an OWNER_STATED_PENDING_RFP_REGISTRATION citation status survived the re-base")
    return doc
