"""A9.19 / A9.20 owner decisions applied to the A9 requirement-verification matrix (RVM).

A9.19 (docs/decisions/OD_2026_10_01_A9_19_*; amends A9.15 on the ROLE of xenon only):
    flight thruster architecture = ONE Hall accelerator + ONE RF/ICP electron-source/neutralizer (cathodeless /
    electrodeless) serving both atmospheric gases and xenon; TWO propellant supply modes with separate tanks / paths -
    ambient atmospheric propellant (primary) and xenon (contingency / emergency supply mode, not a parallel co-equal
    propellant; the RFP-required Xe capability is retained, RFP-P17-05 / RFP-P18-08); NO conventional hollow cathode.
A9.20 (docs/decisions/OD_2026_10_01_A9_20_*): C1 (heated Xe-fed LaB6) is a GROUND-ONLY laboratory reference (H-1
    I_d,max,H1,Ar characterization, A9.10 S3.5; bench control in the C1-vs-ICP comparison); never flight hardware, never
    in the flight mass / power / Xe budgets. hall_c1_reference is no longer a candidate flight configuration; its matrix
    cells are kept only as the labelled ground / laboratory reference.
Unchanged: the A9.1 ICP feed-gas baseline (G-REUSE primary, G-XE declared variant).

What this module adds (statuses still come from rvm_rules.assign_status; nothing becomes PASS):
  * rows RVM-28 (flight architecture), RVM-29 (two supply modes, separate tanks, Xe contingency / emergency role) and
    RVM-30 (C1 ground-only, outside every flight budget);
  * a9_19 records on the rows whose carried text treats C1 as a flight element or Xe as co-equal (RVM-04, -10, -11,
    -12, -14, -15); the A9.16 records stay as history (a later owner addendum, never a rewrite);
  * one RECORDER_PROPOSAL_OPEN_FOR_OWNER entry (the recorder's ICP go / no-go before LOCK-1) - NOT a requirement and
    NOT an owner decision;
  * owner_answers_applied entries citing A9.19 / A9.20 by path + json sha256 (+ verbatim md sha256; the md governs).

stdlib only; deterministic; fail closed on any changed decision file or a missing verbatim token.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARTIFACT = "docs/requirements/rvm_a9/rvm_a9_v1.json"
TEST = "tests/test_rvm_a9.py"
APPLY_DATE = "2026-10-01"

DECISIONS = {
    "A9.19": {"json": "docs/decisions/OD_2026_10_01_A9_19_architecture_xe_contingency_owner_decision.json",
              "json_sha256": "20364847febc240d06779d26dbca0236059ab4471754df4452401eb0ed050b16",
              "md": "docs/decisions/OD_2026_10_01_A9_19_ARCHITECTURE_XE_CONTINGENCY_OWNER_DECISION.md",
              "md_sha256": "d3eae1d65f9b679a8538ce4a7c701a40a3f5d3b07d72baae944b685256931749",
              "decision": "A9_19_SINGLE_HALL_ICP_NEUTRALIZER_NO_HOLLOW_CATHODE_XE_CONTINGENCY"},
    "A9.20": {"json": "docs/decisions/OD_2026_10_01_A9_20_c1_ground_only_owner_decision.json",
              "json_sha256": "9b88e441b5c3454a20c4696897c525ef5818f0cfd9f32c7a3b4fa8e1a204dcc6",
              "md": "docs/decisions/OD_2026_10_01_A9_20_C1_GROUND_ONLY_OWNER_DECISION.md",
              "md_sha256": "2b90a7a7f851ac571791ea6ba2fbafac8cf69a086a4a3724e2f66196b6b4d60c",
              "decision": "C1_GROUND_ONLY_LABORATORY_REFERENCE"},
}
# verbatim owner text (checked against the .md, whitespace-normalized; the .md governs)
VERBATIM = {
    "A9.19": {
        "architecture": "One Hall accelerator. One RF/ICP electron-source/neutralizer. Two propellant supply modes. No "
                        "conventional hollow cathode.",
        "cathodeless": "our thruster architecture should be cathode/electrodless for both the atmosphere gases and xenon",
        "xenon_role": "xenon is not a parllel gas its just a contigency and emergency gas",
        "c1_mass": "check C1 mass",
    },
    "A9.20": {
        "answer": "will go with your recommended",
        "option": "Ground-only reference (Recommended)",
        "role_asked": "It's currently planned for the H-1 baseline characterization that registers I_d,max,H1 (your "
                      "S3.5) and as the control in the C1-vs-ICP bench comparison.",
        "owner_question": "is it good to remove hollow cathode",
    },
}
FLIGHT_ARCHITECTURE = ("one Hall accelerator + one RF/ICP electron-source/neutralizer (cathodeless / electrodeless) "
                       "serving both atmospheric gases and Xe; two propellant supply modes with separate tanks / paths "
                       "- ambient atmospheric propellant (primary) and Xe (contingency / emergency supply mode); no "
                       "conventional hollow cathode")
CONFIGURATION_ROLES = {
    "hall_icp_neutralizer": "FLIGHT ARCHITECTURE (A9.19): " + FLIGHT_ARCHITECTURE + "; still "
                            "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE until evidence (A9)",
    "hall_c1_reference": "GROUND_ONLY_LABORATORY_REFERENCE (A9.20): not a candidate flight configuration (A9.19); its "
                         "cells are kept only as the labelled ground / laboratory reference (H-1 I_d,max,H1,Ar "
                         "characterization, A9.10 S3.5; C1-vs-ICP bench control) and are never flight compliance "
                         "evidence",
}
CELL_APPLICABILITY_C1 = ("GROUND_ONLY_LABORATORY_REFERENCE (A9.20): not a flight configuration (A9.19); this cell is "
                         "carried for the labelled ground / laboratory comparison only and is never flight compliance "
                         "evidence")


class A919Error(RuntimeError):
    pass


def _sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def _norm(s: str) -> str:
    return " ".join(s.split())


def load() -> dict:
    """Verify both decision files (json + verbatim md) and every verbatim token; return the parsed json."""
    out = {}
    for key, d in DECISIONS.items():
        for f in ("json", "md"):
            got = _sha(d[f])
            if got != d[f + "_sha256"]:
                raise A919Error(f"{key} {d[f]} changed: sha256 {got}")
        js = json.loads((ROOT / d["json"]).read_text(encoding="utf-8"))
        if js.get("decided_by") != "owner" or js.get("decision") != d["decision"]:
            raise A919Error(f"{key}: unexpected decision record")
        md = _norm((ROOT / d["md"]).read_text(encoding="utf-8"))
        for tok, q in VERBATIM[key].items():
            if _norm(q) not in md:
                raise A919Error(f"{key} verbatim token {tok!r} not found in {d['md']}")
        out[key] = js
    a19 = out["A9.19"]
    if a19["architecture"]["hall_accelerators"] != 1 or "NONE" not in a19["architecture"]["conventional_hollow_cathode"]:
        raise A919Error("A9.19 architecture record changed")
    if not a19["xenon_role"].startswith("CONTINGENCY_AND_EMERGENCY"):
        raise A919Error("A9.19 xenon_role changed")
    return out


def cite(key: str) -> str:
    d = DECISIONS[key]
    return f"{key} ({d['json']} sha256 {d['json_sha256']}; verbatim {d['md']} sha256 {d['md_sha256']})"


def source(key: str, field: str) -> dict:
    """RVM source record (kind owner_decision) carrying the owner's verbatim words."""
    d = DECISIONS[key]
    return {"kind": "owner_decision", "path": d["json"], "decision_id": key + " " + d["decision"], "key": field,
            "sha256_of_file": d["json_sha256"], "verbatim_md": d["md"], "verbatim_md_sha256": d["md_sha256"],
            "text": VERBATIM[key][field]}


NA_ROWS = ("RVM-28", "RVM-29", "RVM-30")   # flight-architecture rows: hall_c1_reference cell = NA marker (RV19-10)


def na_ground_reference(B, rid: str) -> dict:
    """The only artifact of a hall_c1_reference cell on a flight-architecture row (RV19-10): the ground-only C1
    laboratory reference is not evaluated against flight-architecture requirements (A9.19 / A9.20). Non-evaluating,
    never compliance evidence; rvm_rules refuses to mix it with evidence artifacts."""
    d = DECISIONS["A9.20"]
    return B._art(d["json"], f"A9.20:{rid}:NOT_APPLICABLE_GROUND_REFERENCE", "DETERMINING",
                  "NOT_APPLICABLE_GROUND_REFERENCE",
                  "NOT_APPLICABLE_GROUND_REFERENCE - hall_c1_reference is a ground-only laboratory reference (A9.20), "
                  "not a flight configuration (A9.19); this flight-architecture requirement is not evaluated against "
                  "it and the cell is never compliance evidence")


# ------------------------------------------------------------------------------------------------ rows
def build_rows(B, ctx) -> list:
    """RVM-28..RVM-30 (A9.19 / A9.20). Called by build_rvm_a9.build_doc with the builder module as B."""
    load()
    plan, absent = B.plan, B.absent
    # verbatim tokens of the registered RFP clauses this lane traces to (fail closed if the transcription changed)
    ctx.rfp("RFP-P17-05", "an extra input system to take care any problems on board unforeseen problems")
    ctx.rfp("RFP-P17-05", "ionize N2, atomic oxygen in same thruster")
    ctx.rfp("RFP-P18-08", "Two separate propellant tanks for ambient air and xenon")
    rows = []

    def cells(fn_icp, rid):
        return {"hall_icp_neutralizer": fn_icp(), "hall_c1_reference": [na_ground_reference(B, rid)]}

    # RVM-28 ---------------------------------------------------------------------------------------- architecture
    arch_absent = lambda: absent(  # noqa: E731
        ctx, "RFP-P17-05", "inspection of the frozen flight design baseline (Milestone C) showing exactly one Hall "
                           "accelerator, one RF/ICP electron-source/neutralizer serving both the atmospheric and the Xe "
                           "supply modes, and no conventional hollow cathode; plus the ICP-45 discharge-OFF capacity "
                           "and Xe-mode operation records of that one ICP", ":A9_19_ARCHITECTURE")
    rows.append({
        "id": "RVM-28", "key": "FLIGHT_ARCHITECTURE_SINGLE_HALL_ICP_NO_HOLLOW_CATHODE",
        "category": "owner_architecture_decision",
        "title": "Flight thruster architecture: one Hall accelerator + one RF/ICP electron-source/neutralizer for both "
                 "atmospheric gases and Xe; no conventional hollow cathode (A9.19)",
        "requirement_text": "The flight propulsion system has exactly ONE Hall accelerator and ONE RF/ICP "
                            "electron-source/neutralizer (cathodeless / electrodeless) that serves BOTH the ambient "
                            "atmospheric supply mode and the Xe supply mode; there is NO conventional hollow cathode in "
                            "the flight architecture (A9.19 owner decision). The single-thruster reading is consistent "
                            "with the registered RFP clauses RFP-P17-05 ('in same thruster'; Xe as 'an extra input "
                            "system') and RFP-P18-08 (two separate tanks), which do not themselves prescribe the "
                            "electron source. C1 is ground-only laboratory equipment (A9.20, RVM-30).",
        "sources": [source("A9.19", "architecture"), source("A9.19", "cathodeless")],
        "requirement_basis": "OWNER_ARCHITECTURE_DECISION " + cite("A9.19") + " - owner-given design architecture, not "
                             "an RFP gate; traced to RFP-P17-05 / RFP-P18-08 (verbatim in rfp_trace)",
        "requirement_frozen": True,
        "limit": {"quantity": "flight Hall accelerators / RF-ICP neutralizers / conventional hollow cathodes",
                  "comparator": "==", "value": [1, 1, 0], "units": "count"},
        "verification_methods": ["inspection", "demonstration"],
        "verification_note": "inspection of the frozen flight design baseline (none exists: A9 is "
                             "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE) and demonstration that the "
                             "one ICP serves both supply modes (ICP-45 capacity PENDING_ICP45; Xe operation of the ICP "
                             "not yet measured); a design intent is not verification evidence",
        "open_readings": [], "rtm_xref": [], "lane24_gates": [], "m16_rows": [],
        "configuration_applicability": {"hall_icp_neutralizer": "FLIGHT (A9.19)",
                                        "hall_c1_reference": CELL_APPLICABILITY_C1},
        "rfp_trace": [ctx.rfp("RFP-P17-05"), ctx.rfp("RFP-P18-08")],
        "artifacts": cells(
            lambda: [arch_absent(), plan(ctx, "ICD", "@doc", role="SUPPORTING", why="one ICP neutralizer interface"),
                     plan(ctx, "P1", "P1-S7", role="SUPPORTING", why="ICP-45A capacity (PENDING_ICP45)")],
            "RVM-28"),
    })
    # RVM-29 ---------------------------------------------------------------------------------------- supply modes
    sup_absent = lambda: absent(  # noqa: E731
        ctx, "RFP-P18-08", "inspection of the frozen flight feed-system design showing separate ambient-air and Xe "
                           "tanks / paths feeding the one Hall + ICP, a mode-selection record (atmospheric primary, Xe "
                           "contingency / emergency) and a demonstrated, booked Xe contingency-mode operation",
        ":A9_19_SUPPLY_MODES")
    rows.append({
        "id": "RVM-29", "key": "TWO_SUPPLY_MODES_SEPARATE_TANKS_XE_CONTINGENCY",
        "category": "rfp_registered",
        "title": "Two propellant supply modes with separate tanks / paths: ambient atmospheric propellant (primary) and "
                 "Xe (contingency / emergency supply mode) (RFP-P18-08, RFP-P17-05; A9.19)",
        "requirement_text": "Two separate propellant supply modes with separate tanks / paths feed the one Hall "
                            "accelerator + RF/ICP neutralizer: ambient atmospheric propellant at 180-230 km (primary "
                            "mode) and Xe (contingency / emergency supply mode - the RFP's 'extra input system to take "
                            "care any problems on board unforeseen problems', RFP-P17-05; 'Two separate propellant "
                            "tanks for ambient air and xenon', RFP-P18-08). Xe is not a parallel co-equal propellant "
                            "(A9.19, amending A9.15 on the ROLE of Xe); the Xe capability itself stays required "
                            "(RVM-10). The A9.1 ICP feed-gas baseline is unchanged (G-REUSE primary; G-XE a declared "
                            "variant).",
        "sources": [source("A9.19", "xenon_role"), source("A9.19", "architecture")],
        "requirement_basis": B.RFP_BASIS + "; Xe ROLE = owner decision " + cite("A9.19"), "requirement_frozen": False,
        "limit": {"quantity": "propellant supply modes / tanks", "comparator": "is",
                  "value": "2 separate (ambient air primary; Xe contingency / emergency)", "units": "-"},
        "verification_methods": ["inspection", "demonstration"],
        "verification_note": "inspection of the frozen feed-system design (none exists; the ambient-air storage / feed "
                             "path belongs to the upstream-architecture lanes) and a demonstrated, booked Xe "
                             "contingency-mode operation on the one Hall + ICP (RVM-10)",
        "open_readings": [], "rtm_xref": [ctx.rtm("RFP-XE-OP")], "lane24_gates": ["G7_air_xenon"], "m16_rows": [],
        "configuration_applicability": {"hall_icp_neutralizer": "FLIGHT (A9.19)",
                                        "hall_c1_reference": CELL_APPLICABILITY_C1},
        "artifacts": cells(
            lambda: [sup_absent(), B.probe_xe(ctx, "hall_icp_neutralizer"),
                     plan(ctx, "FSC", "@doc", role="SUPPORTING", why="delivered atmospheric feed state (primary mode)")],
            "RVM-29"),
    })
    # RVM-30 ---------------------------------------------------------------------------------------- C1 ground-only
    rows.append({
        "id": "RVM-30", "key": "C1_GROUND_ONLY_LAB_REFERENCE_NOT_IN_FLIGHT_BUDGETS",
        "category": "owner_architecture_decision",
        "title": "C1 (heated Xe-fed LaB6) is a ground-only laboratory reference: never flight hardware, never in the "
                 "flight mass / power / Xe budgets (A9.20)",
        "requirement_text": "C1 is used only on the ground: (i) the dedicated H-1 reference characterization that "
                            "registers I_d,max,H1,Ar independently of the ICP (A9.10 S3.5 P1Q-07) and (ii) the bench "
                            "control in the C1-vs-ICP comparison. C1 is never flight hardware or a flight fallback, and "
                            "no C1 mass, power or Xe (heater, keeper, ignition dwell, C1 Xe branch, AL-C1, C1 getter) is "
                            "booked in any flight budget (A9.19 / A9.20). C1 laboratory Xe is test-campaign Xe.",
        "sources": [source("A9.20", "answer"), source("A9.20", "option"), source("A9.20", "role_asked"),
                    source("A9.19", "c1_mass")],
        "requirement_basis": "OWNER_ARCHITECTURE_DECISION " + cite("A9.20") + " + " + cite("A9.19"),
        "requirement_frozen": True,
        "limit": {"quantity": "C1 mass / power / Xe booked in flight budgets", "comparator": "==", "value": 0,
                  "units": "kg / W / kg"},
        "verification_methods": ["inspection"],
        "verification_note": "inspection of the flight mass / power and Xe accounting v3 (mass_power_a9_v3 / "
                             "xe_accounting_a9_v3) refreshed for A9.19 / A9.20 by the budgets lane (the immutable v2 "
                             "budgets still book hall_c1_reference and are history only, never evidence here) "
                             "and of the RFQ v3 classification RFQ3-HALLEL-N03 (procurement, never evidence)",
        "open_readings": [], "rtm_xref": [], "lane24_gates": [], "m16_rows": [],
        "configuration_applicability": {"hall_icp_neutralizer": "FLIGHT budgets must exclude C1 (A9.20)",
                                        "hall_c1_reference": CELL_APPLICABILITY_C1},
        "artifacts": cells(
            lambda: [plan(ctx, "MP3", "@doc", why="flight mass / power v3, to be refreshed for A9.19 / A9.20 without C1 "
                                                  "(budgets lane); the immutable v2 still books hall_c1_reference as "
                                                  "history and is not evidence here"),
                     plan(ctx, "XE3", "@doc", why="flight Xe accounting v3, to be refreshed for A9.19 / A9.20 without C1 "
                                                  "Xe (budgets lane); the immutable v2 is history, not evidence here"),
                     plan(ctx, "RFQ3", "RFQ3-HALLEL-N03", role="SUPPORTING",
                          why="RFQ v3 RFQ3-HALLEL-N03 classifies every C1 line GROUND_ONLY_LAB_EQUIPMENT "
                              "(procurement, never evidence)")],
            "RVM-30"),
    })
    return rows


# ------------------------------------------------------------------------------------------------ rebase table
REBASE = {
    "RVM-28": dict(origin="OWNER_ALLOCATION", related=["RFP-P17-05", "RFP-P18-08", "RFP-P18-07"],
                   note="A9.19 owner architecture decision (one Hall + one RF/ICP neutralizer, no conventional hollow "
                        "cathode); the RFP clauses are traced verbatim (rfp_trace) but do not prescribe the electron "
                        "source; OWNER_ALLOCATION here means an owner-given design decision, not an RFP gate"),
    "RVM-29": dict(origin="RFP_CLAUSE", clauses=[("RFP-P18-08", "Two separate propellant tanks for ambient air and "
                                                                "xenon"),
                                                 ("RFP-P17-05", "an extra input system to take care any problems on "
                                                                "board unforeseen problems")],
                   related=["RFP-P16-02"], category="rfp_registered",
                   note="the Xe contingency / emergency ROLE is the owner's A9.19 decision, consistent with the RFP's "
                        "stated purpose of the Xe input (DISC-06); the capability stays mandatory (A9.15, RVM-10)"),
    "RVM-30": dict(origin="OWNER_ALLOCATION", related=[],
                   note="A9.20 owner decision (C1 ground-only laboratory reference); not an RFP requirement"),
}


# ------------------------------------------------------------------------------------------------ row records
ROW_RECORDS = {
    "RVM-04": {"c1_supplies": "C1 supplies (heater, keeper) are NOT flight bus loads: there is no conventional "
                              "hollow cathode in the flight architecture (A9.19); C1 is ground-only (A9.20). The "
                              "requirement text as carried lists 'C1 supplies' for the hall_c1_reference ground "
                              "reference only."},
    "RVM-10": {"xe_role": "CONTINGENCY_AND_EMERGENCY supply mode (A9.19, amending A9.15 on the ROLE of Xe): Xe is not "
                          "a parallel co-equal propellant; the RFP-required Xe capability, separate tank / path and a "
                          "bounded functional Xe-capable mode on the one Hall + RF/ICP neutralizer stay required "
                          "(RFP-P17-05, RFP-P18-08)",
               "supersedes": "the a9_16 record's 'never a contingency interpretation' wording on the ROLE of Xe "
                             "(kept as history); the a9_16 'configurations' reading (Xe capability in "
                             "hall_c1_reference; C1 Xe booked inside the system Xe accounting) is superseded by A9.20: "
                             "hall_c1_reference is a ground-only reference and C1 Xe is never flight Xe",
               "icp_gas_mode": "unchanged: A9.1 G-REUSE primary; G-XE a declared ICP-feed variant"},
    "RVM-11": {"architecture": "the one Hall accelerator of the A9.19 flight architecture (RVM-28)"},
    "RVM-12": {"c1_life_basis": "the C1 15,000 h cathode basis in the carried text applies to no flight element (no "
                                "conventional hollow cathode, A9.19); the flight life basis is the H-1 and the one ICP "
                                "neutralizer (>= 15,000 h cumulative energized, A9.16 record)"},
    "RVM-14": {"c1_variant": "NOT A FLIGHT VARIANT (A9.19: no conventional hollow cathode; A9.20: C1 ground-only). The "
                             "carried C1 ignition-dwell booking (3 x <= 120 s, 360 s) applies only to the ground C1 "
                             "laboratory reference and its test-campaign Xe, never to a flight budget"},
    "RVM-15": {"hall_c1_reference": "ground-only bench control (C1-vs-ICP comparison, A9.20); the carried "
                                    "'CONTROL_FALLBACK' sizing is not a flight fallback (A9.19). Flight "
                                    "neutralization is the one RF/ICP neutralizer only (ICP-45 capacity, "
                                    "PENDING_ICP45)"},
}

RECORDER_PROPOSALS = [{
    "id": "RP-A919-01",
    "status": "RECORDER_PROPOSAL_OPEN_FOR_OWNER",
    "is_requirement": False, "is_owner_decision": False,
    "proposal": "ICP go / no-go before LOCK-1 for the single Hall + RF/ICP flight architecture (no hollow-cathode "
                "fallback exists after A9.19): (a) measured ICP electron-current capacity I_e,cap >= I_d,max with a "
                "pre-registered margin; (b) RF power per extracted ampere (W/A) within the power budget; (c) repeatable "
                "ignition on N2 and on Xe.",
    "why_raised": "A9.19 removes the conventional hollow cathode from the flight architecture, so the ICP is the only "
                  "flight electron source; the owner also asked (A9.20 verbatim) 'is it good to remove hollow "
                  "cathode'. The recorder suggests this gate for the owner's consideration only.",
    "numbers": "none proposed: the margin, the W/A budget and the ignition repeatability criterion would be owner / "
               "pre-registration values; nothing is invented here",
    "handling": "carried for the owner; not a row, not a limit, not a gate in this RVM; no status depends on it",
    "related_rows": ["RVM-15", "RVM-28", "RVM-04", "RVM-14"],
}]


def applied_entries() -> list:
    def e(key, rec, rows, how):
        d = DECISIONS[key]
        return {"decision": key, "question_id": rec, "decision_code": d["decision"], "decision_json": d["json"],
                "decision_json_sha256": d["json_sha256"], "decision_md": d["md"], "decision_md_sha256": d["md_sha256"],
                "artifact": ARTIFACT, "record_ids": rows, "how_applied": how, "tests": [TEST]}
    return [
        e("A9.19", "architecture", ["RVM-28", "RVM-11", "configurations"],
          "new row RVM-28: one Hall accelerator + one RF/ICP electron-source/neutralizer for both supply modes, no "
          "conventional hollow cathode (OWNER_ALLOCATION = owner architecture decision; RFP-P17-05 / RFP-P18-08 traced "
          "verbatim); hall_icp_neutralizer labelled the flight architecture"),
        e("A9.19", "xenon_role", ["RVM-29", "RVM-10"],
          "new row RVM-29 (RFP_CLAUSE RFP-P18-08 + RFP-P17-05): two supply modes with separate tanks / paths, ambient "
          "atmospheric primary, Xe contingency / emergency; RVM-10 a9_19 record supersedes the A9.16 'never a "
          "contingency' wording on the ROLE of Xe (capability still required)"),
        e("A9.19", "amends", ["RVM-04", "RVM-12", "RVM-14", "RVM-15", "configurations"],
          "no C1 flight variant: C1 supplies, the C1 15,000 h cathode basis, the C1 ignition-dwell Xe booking and the "
          "C1 CONTROL_FALLBACK sizing are recorded as non-flight; hall_c1_reference is not a candidate flight "
          "configuration"),
        e("A9.20", "option", ["RVM-28", "RVM-29", "RVM-30"],
          "hall_c1_reference cells of the flight-architecture rows RVM-28..30 are NOT_APPLICABLE_GROUND_REFERENCE "
          "markers (no flight requirement is evaluated against the ground-only C1 reference); RVM-30 evidence points at "
          "the v3 budgets (mass_power_a9_v3 / xe_accounting_a9_v3) refreshed for A9.19 / A9.20, never at the "
          "immutable v2 budgets (repair RV19-10)"),
        e("A9.20", "answer", ["RVM-30", "configurations", "RVM-10", "RVM-15"],
          "new row RVM-30: C1 ground-only laboratory reference (H-1 I_d,max,H1,Ar characterization A9.10 S3.5; C1-vs-ICP "
          "bench control); never flight hardware, never in the flight mass / power / Xe budgets; hall_c1_reference "
          "cells labelled GROUND_ONLY_LABORATORY_REFERENCE"),
    ]


def apply(doc: dict) -> dict:
    """Record-level application on the evaluated matrix (before the RFP re-base)."""
    load()
    by = {r["id"]: r for r in doc["rows"]}
    for rid in ("RVM-28", "RVM-29", "RVM-30"):
        if rid not in by:
            raise A919Error(f"{rid} missing (build_rows not called)")
    for rid, rec in ROW_RECORDS.items():
        by[rid]["a9_19"] = {"decisions": [cite("A9.19")] + ([cite("A9.20")] if rid in ("RVM-04", "RVM-10", "RVM-12",
                                                                                        "RVM-14", "RVM-15") else []),
                            **rec}
    for rid in ("RVM-28", "RVM-29", "RVM-30"):
        by[rid]["a9_19"] = {"decisions": [cite("A9.19"), cite("A9.20")], "added": APPLY_DATE}
    for rid in NA_ROWS:
        cell = by[rid]["configurations"]["hall_c1_reference"]
        if cell.get("applicability_marker") != "NOT_APPLICABLE_GROUND_REFERENCE":
            raise A919Error(f"{rid}: hall_c1_reference cell is not the NOT_APPLICABLE_GROUND_REFERENCE marker")
    for r in doc["rows"]:
        r["configurations"]["hall_c1_reference"]["applicability"] = CELL_APPLICABILITY_C1
    doc["configurations_as_carried_a9_16"] = doc["configurations"]
    doc["configurations"] = dict(CONFIGURATION_ROLES)
    doc["a9_19_20"] = {
        "decisions": [cite("A9.19"), cite("A9.20")],
        "amends": "A9.15 on the ROLE of Xe only (capability retained); A9 C1 CONTROL_FALLBACK; A9.14 S8.33 MPQ-01 / "
                  "S8.17 OQ-A907-07 (no C1 flight variant)",
        "flight_architecture": FLIGHT_ARCHITECTURE,
        "unchanged": "A9.1 ICP feed-gas baseline (G-REUSE primary, G-XE declared variant); every status still from "
                     "rvm_rules (no PASS)",
        "a9_2_status_note": "a9_2_statuses_carried['C1 conventional reference'] = CONTROL_FALLBACK is immutable A9.2 "
                            "history; A9.19 removes C1 as a flight fallback and A9.20 makes it ground-only",
        "rows_added": ["RVM-28", "RVM-29", "RVM-30"], "rows_recorded": sorted(ROW_RECORDS),
        "not_applicable_ground_reference_cells": [{"row": rid, "configuration": "hall_c1_reference",
                                                   "marker": "NOT_APPLICABLE_GROUND_REFERENCE"} for rid in NA_ROWS],
        "na_note": "flight-architecture rows RVM-28..30 are not evaluated against the ground-only hall_c1_reference "
                   "(RV19-10); the cell keeps a vocabulary status (rvm_rules, R7) but carries applicability_marker "
                   "NOT_APPLICABLE_GROUND_REFERENCE and counts_as_compliance_evidence = false",
        "owner_open_note": "A9.20 verbatim also asks 'is it good to remove hollow cathode' - recorded for the owner, "
                           "not answered here (see recorder_proposals_open_for_owner)",
        "downstream": "docs/requirements/rfp_official/rfp_registration_v1.json rvm_mapping is rebuilt from this RVM by "
                      "its own builder (rfp_clauses_v1.py; outside this lane)",
    }
    doc["recorder_proposals_open_for_owner"] = [dict(p) for p in RECORDER_PROPOSALS]
    doc["a9_19_owner_answers_applied"] = applied_entries()
    return doc
