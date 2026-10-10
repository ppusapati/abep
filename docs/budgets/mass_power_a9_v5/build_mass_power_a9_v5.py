#!/usr/bin/env python3
"""A9.26 mass-budget policy for the bid baseline (mass_power_a9_v5) - a SUCCESSOR of the immutable mass / power v4.

Lane: A9.26 (owner decision 2026-10-05, recorded verbatim in
docs/decisions/OD_2026_10_05_A9_26_MASS_BUDGET_OWNER_DECISIONS.md, message 2 MASS_BUDGET_DECISIONS_PRE_BID_FREEZE;
companion json). Deterministic; standard library only; no Julia; well under a second. No raw-physics change.

v4 (docs/budgets/mass_power_a9_v4/) is pinned by sha256 and read as DATA (its JSON); the v3 builder is pinned and
imported only for its unchanged fail-closed rule functions (line_mev_value / harness_row60 / closure_state /
_unresolved / rollup / system_margin / rk); v4, v3 and v2 are never edited. v5 = v4 with exactly these changes:

  * SYSTEM MARGIN (A9.26 section 1): the ACTIVE proposal / bid basis uses a 10 % system-level mass margin on the
    current pre-margin nominal dry (it supersedes the A9.14 MQ-02 20 % reading for the bid baseline only). The 20 %
    LINE-LEVEL planning uplift on the floor-derived lines AL-04 / AL-07 / AL-08 is kept (line values unchanged:
    4.2048 / 6.0 / 5.9148 kg); effective line x system factor 1.20 x 1.10 = 1.32 (not 1.44). The former 20 %
    system-margin roll-up is preserved as a labelled HISTORICAL / CONSERVATIVE SENSITIVITY (recomputed with AL-09 =
    1.0 kg by the pinned v3 rollup(), plus the v4 AL-09-excluded figure as history).
  * AL-09 (A9.26 section 2): controls / electronics / valve drivers / flight sensors = 1.0 kg,
    PROVISIONAL_OWNER_ALLOCATION / NOT_CBE / NOT_MEASURED; harness stays separate under the row-60 5/95 rule;
    MPV3Q-01 closed (OWNER_DECIDED A9.26); no compensating reduction on any other line (fail closed).
  * the roll-up is recomputed by the builder (A9.26 section 3; never hard-coded) and checked against the owner's
    approximate arithmetic: a material difference raises (STOP). HARD_40_WET is evaluated per loaded Xe case (2 / 5 /
    10 kg; no relaxation, section 4) with the maximum allowable dry mass and the reduction needed.
  * new labelled blocks: proposal design target (section 5: nominal dry <= 34.0 kg, 10 %, 2 kg Xe planning reference
    -> 39.4 kg wet; DESIGN TARGET, not evidence), internal allocation target (section 6: AL-09 1.0 kg, harness 5/95,
    10 %; INTERNAL ALLOCATION TARGET, NOT EVIDENCE OF MASS COMPLIANCE; the 24 kg + 20 % = 28.8 kg budget reference is
    kept as HISTORICAL / INTERNAL ALLOCATION PROVENANCE), margin audit, mass-closure actions (section 7), mass status
    MASS INCOMPLETE_EVIDENCE / NOT_YET_CLOSED (no PASS).

Nothing else changes: every other line, the AFI-01 / AFI-01-S1 / AFI-02 / C1 records, BOM, power, Xe import, retired
C1 history column and owner citations are v4's (copied from the pinned JSON).

    python docs/budgets/mass_power_a9_v5/build_mass_power_a9_v5.py          # (re)write JSON and Markdown
    python docs/budgets/mass_power_a9_v5/build_mass_power_a9_v5.py --check  # exit 1 unless reproduced byte for byte
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

LANE_REL = "docs/budgets/mass_power_a9_v5"
SCRIPT_REL = LANE_REL + "/build_mass_power_a9_v5.py"
JSON_NAME = "mass_power_a9_v5.json"
MD_NAME = "MASS_POWER_A9_V5.md"
TEST_REL = "tests/test_mass_power_a9_v5.py"
SCHEMA_ID = "mass_power_a9_v5"
BASE_COMMIT = "7fdc9db0a6fa696b532f4f11b1a8f982a8d03ed5"
DATE = "2026-10-05"
FLIGHT = "hall_icp_neutralizer"

# immutable inputs (read as data / code, never edited)
PINS = {
    "V4_JSON": ("docs/budgets/mass_power_a9_v4/mass_power_a9_v4.json",
                "37264ab6c7cf5c422cb93356fcd9a8e67323f73b1257e1eb1426410229c8a6c4"),
    "V4_MD": ("docs/budgets/mass_power_a9_v4/MASS_POWER_A9_V4.md",
              "cd68ed11de08183efe2a3698ed87f62959ec7d4b84db307378dcca2769472de7"),
    "V4_BUILDER": ("docs/budgets/mass_power_a9_v4/build_mass_power_a9_v4.py",
                   "6eccc6e7ee443bee77513ad51f141cb36e6ad9fe40949bb5d0a2809d59fe6597"),
    "V3_BUILDER": ("docs/budgets/mass_power_a9_v3/build_mass_power_a9_v3.py",
                   "b1df7537456d5334e8b051bb6ed9bca9626933497b3b52e916c9997338e6a572"),
    # A9.26 (owner decision 2026-10-05, verbatim record + companion json)
    "A9_26_MD": ("docs/decisions/OD_2026_10_05_A9_26_MASS_BUDGET_OWNER_DECISIONS.md",
                 "5f40294de9ab736cedd7a24a393b0333823c2624e3469f6b1f775250a85803e5"),
    "A9_26_JSON": ("docs/decisions/OD_2026_10_05_A9_26_mass_budget_owner_decisions.json",
                   "18dada24a90fb1a5d17e903bf8eb9f77af622106f9ddfc59ea1f182054b80b76"),
}
A9_26_MESSAGE = {"n": 2, "key": "MASS_BUDGET_DECISIONS_PRE_BID_FREEZE",
                 "text_sha256": "c240fca3b8109078ac0113cdb3526d729e3f13c41a8e8639b802b463f535633f"}
# verbatim owner text applied here (whitespace-normalised; every quote is checked against the message text)
Q = {
    "margin": (1, "SYSTEM-LEVEL MASS MARGIN = 10%"),
    "historical": (1, "The earlier 20% system-margin treatment remains historical / conservative internal provenance "
                      "only and must not remain the active bid mass-margin policy."),
    "line_uplift": (1, "Keep the existing 20% LINE-LEVEL planning uplift on floor-derived lines: AL-04 AL-07 AL-08 for "
                       "this bid freeze."),
    "factor": (1, "1.20 x 1.10 = 1.32"),
    "floors_unchanged": (1, "Do not alter the line-floor values themselves in this step."),
    "sensitivity": (1, "HISTORICAL / CONSERVATIVE SENSITIVITY"),
    "al09": (2, "AL-09 controls / electronics / valve drivers / flight sensors = 1.0 kg"),
    "al09_status": (2, "PROVISIONAL_OWNER_ALLOCATION NOT_CBE NOT_MEASURED"),
    "harness": (2, "Harness remains separate under the existing 5/95 rule."),
    "mpv3q01": (2, "Close: MPV3Q-01 accordingly."),
    "no_compensation": (2, "Do not reduce another line to compensate for this allocation."),
    "al09_cbe": (2, "Replace AL-09 with a design-derived CBE when available."),
    "recompute": (3, "Recompute these from the builder; do not hard-code these rounded values."),
    "stop": (3, "If the governed builder gives materially different results, STOP and report."),
    "status": (4, "INCOMPLETE_EVIDENCE / NOT_YET_CLOSED"),
    "no_pass": (4, "Do not claim PASS."),
    "target": (5, "nominal dry <= 34.0 kg"),
    "target_arith": (5, "34.0 x 1.10 + 2.0 = 39.4 kg wet"),
    "target_label": (5, "This is a DESIGN TARGET, not achieved evidence."),
    "xe_reference": (5, "The 2 kg Xe case is a planning/reference case only."),
    "xe_not_selected": (5, "Do not call it the final selected Xe load."),
    "xe_sensitivities": (5, "Continue carrying 5 kg and 10 kg as sensitivities."),
    "row54": (6, "24 kg + 20% = 28.8 kg"),
    "row54_history": (6, "Preserve that as historical/internal allocation provenance."),
    "alloc_label": (6, "INTERNAL ALLOCATION TARGET NOT EVIDENCE OF MASS COMPLIANCE"),
    "alloc_not_target": (6, "Do not confuse it with the <=34 kg proposal nominal-dry target."),
    "no_compliance": (7, "Do not claim current mass compliance."),
}
# A9.26 section 3: the owner's approximate arithmetic (cross-check only; the builder computes every value)
EXPECTED_ROLLUP = {"nonharness_known_kg": 33.1196, "harness_kg": 1.7431, "nominal_dry_known_kg": 34.8627,
                   "system_margin_kg": 3.4863, "dry_known_kg": 38.3490}
EXPECTED_WET = {2.0: 40.3490, 5.0: 43.3490, 10.0: 48.3490}
MATERIAL_KG = 6e-5                                     # the owner values are rounded to 4 decimals
SYSTEM_MARGIN_BID = 0.1                                # A9.26 section 1 (active proposal / bid basis)
LINE_UPLIFT_LINES = {"AL-04": 4.2048, "AL-07": 6.0, "AL-08": 5.9148}   # values unchanged (A9.26 section 1)
AL09_KG = 1.0                                          # A9.26 section 2
AL09_STATUS = ["PROVISIONAL_OWNER_ALLOCATION", "NOT_CBE", "NOT_MEASURED"]
PROPOSAL_TARGET = {"nominal_dry_max_kg": 34.0, "xe_reference_kg": 2.0, "wet_reference_kg": 39.4}  # A9.26 section 5
HARD = "HARD_40_WET"
MASS_STATUS = "MASS INCOMPLETE_EVIDENCE / NOT_YET_CLOSED"
CLOSURE_ACTIONS = [
    ("MCA-01", "AL-07", "current cathodeless PPU CBE / requote", "AL-07 current cathodeless PPU CBE/requote;",
     "AFI-02-RA1 (OPEN): re-base the 6.0 kg owner analog floor on the hall_icp_neutralizer load / converter CBE or a "
     "cathodeless PPU quotation (RFQ3-HALLEL)"),
    ("MCA-02", "AL-08", "quote / design rebase", "AL-08 quote/design rebase;",
     "the 5.9148 kg MEV planning floor (A9.21 PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN) is replaced by quotations / design "
     "(RFQ3-GAS rev1; tank, regulator, valves, plumbing, mounting / thermal)"),
    ("MCA-03", "AL-04", "completed Hall-head CBE", "AL-04 completed Hall-head CBE;",
     "the 4.2048 kg MEV planning floor covers magnetic parts only (channel ceramics, anode / distributor, body, "
     "fasteners TBD); replaced by 1.20 x the completed H-1 CBE (MQ-03)"),
    ("MCA-04", "AL-09", "design-derived CBE", "AL-09 design-derived CBE;",
     "the 1.0 kg PROVISIONAL_OWNER_ALLOCATION is replaced by a design-derived CBE when available (A9.26 section 2)"),
    ("MCA-05", "AL-HAR", "actual routed harness", "actual routed harness;",
     "the row-60 5/95 harness rule (MQ-06) is replaced by the routed-harness mass"),
    ("MCA-06", "system", "subsystem integration / structural optimisation",
     "subsystem integration / structural optimization.",
     "integration and structural optimisation across AL-01 .. AL-10 (MQ-10: reduce actual subsystem CBE; no requirement "
     "relaxation, no removal of qualified hardware solely to force < 40 kg)"),
]


class PinError(RuntimeError):
    """A pinned immutable input does not match its recorded sha256."""


class MassPolicyError(ValueError):
    """A refused reading, a changed line, or a result materially different from the owner's arithmetic (STOP)."""


def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def verify_pins() -> None:
    bad = [f"{p} (expected {s[:12]}, got {_sha(p)[:12]})" for p, s in PINS.values() if s and _sha(p) != s]
    if bad:
        raise PinError("pinned immutable inputs changed: " + "; ".join(bad))


def _load(rel: str):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _module(key: str, name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / PINS[key][0])
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def v3_module():
    return _module("V3_BUILDER", "build_mass_power_a9_v3_pinned_v5")


def v4_module():
    return _module("V4_BUILDER", "build_mass_power_a9_v4_pinned_v5")


def a9_26_message2() -> dict:
    """The A9.26 message 2 owner record: verbatim text sha256 and every quote this successor applies (fail closed)."""
    md = (REPO / PINS["A9_26_MD"][0]).read_text(encoding="utf-8")
    head = f"## Message {A9_26_MESSAGE['n']} — {A9_26_MESSAGE['key']} — "
    if md.count(head) != 1:
        raise MassPolicyError("A9.26 message 2 heading not found exactly once")
    body = md.split(head, 1)[1]
    if f"text sha256 `{A9_26_MESSAGE['text_sha256']}`" not in body.splitlines()[0]:
        raise MassPolicyError("A9.26 message 2 text sha256 changed")
    text = body.split("````text\n", 1)[1].split("\n````", 1)[0]
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != A9_26_MESSAGE["text_sha256"]:
        raise MassPolicyError("A9.26 message 2 verbatim text does not reproduce its recorded sha256")
    flat = " ".join(text.split())
    for k, (_sec, quote) in Q.items():
        if quote not in flat:
            raise MassPolicyError(f"A9.26 message 2 quote {k!r} not found verbatim: {quote!r}")
    for _i, _l, _a, quote, _n in CLOSURE_ACTIONS:
        if quote not in flat:
            raise MassPolicyError(f"A9.26 message 2 closure action not found verbatim: {quote!r}")
    js = _load(PINS["A9_26_JSON"][0])
    m2 = [m for m in js["messages"] if m["n"] == A9_26_MESSAGE["n"]]
    if len(m2) != 1 or m2[0]["key"] != A9_26_MESSAGE["key"] or m2[0]["text_sha256"] != A9_26_MESSAGE["text_sha256"]:
        raise MassPolicyError("A9.26 JSON message 2 record does not match the verbatim record")
    if js["verbatim"]["sha256"] != PINS["A9_26_MD"][1]:
        raise MassPolicyError("A9.26 JSON does not pin the verbatim record")
    return {"decision": "A9.26", "id": js["id"], "message": A9_26_MESSAGE["n"], "key": A9_26_MESSAGE["key"],
            "utc": m2[0]["utc"], "text_sha256": A9_26_MESSAGE["text_sha256"],
            "md": PINS["A9_26_MD"][0], "md_sha256": PINS["A9_26_MD"][1],
            "json": PINS["A9_26_JSON"][0], "json_sha256": PINS["A9_26_JSON"][1],
            "supersedes": js["supersedes"]}


def q(key: str) -> dict:
    sec, quote = Q[key]
    return {"section": sec, "quote": quote}


def cite_a926(sections) -> str:
    s = "/".join(str(x) for x in sections)
    return (f"A9.26 message 2 section {s} ({PINS['A9_26_JSON'][0]} sha256 {PINS['A9_26_JSON'][1][:12]}; verbatim "
            f"{PINS['A9_26_MD'][0]} sha256 {PINS['A9_26_MD'][1][:12]})")


# ======================================================================== fail-closed rule functions (A9.26)
def assert_bid_margin_reading(reading: dict) -> None:
    """A9.26 section 1 (+ A9.14 MQ-01 / MQ-09 / MQ-10): the ACTIVE bid reading is MEV allocations, a 10 % system margin
    on the current pre-margin nominal dry, no reserve, loaded Xe. Anything else is refused (the 20 % reading is only
    the labelled historical / conservative sensitivity, evaluated by the pinned v3 rules)."""
    want = {"allocations": "MEV", "system_margin": SYSTEM_MARGIN_BID, "reserve_kg": 0.0, "xe_case": "LOADED"}
    if reading != want:
        raise MassPolicyError(f"bid closure reading {reading!r} refused: only {want} (A9.26 section 1)")


def system_margin_bid(m, pre_margin_kg, fraction=SYSTEM_MARGIN_BID, reserve_kg=0.0) -> dict:
    """A9.26 section 1: bid-basis system margin = 10 % of the CURRENT pre-margin sum (no reserve, never both)."""
    if fraction != SYSTEM_MARGIN_BID:
        raise MassPolicyError("the active bid system margin is 0.10 (A9.26 section 1); the 0.20 reading is the "
                              "historical / conservative sensitivity (pinned v3 rules) and nothing else is admitted")
    if reserve_kg not in (0, 0.0):
        raise MassPolicyError("no fixed reserve on top of the system margin (A9.14 MQ-02 rule kept)")
    p = m._kg(pre_margin_kg, "pre-margin sum")
    return {"pre_margin_kg": m.rk(p), "system_margin_kg": m.rk(fraction * p), "total_kg": m.rk(p * (1.0 + fraction))}


def unresolved_v5(m, rec: dict) -> list:
    """v3 _unresolved, with the A9.26 AL-09 provisional owner allocation named for what it is."""
    if rec["line"] == "AL-09" and rec["value"]["value_kg"] is not None:
        return [f"AL-09: {' / '.join(AL09_STATUS)} {rec['value']['value_kg']:g} kg (A9.26 section 2); replace with a "
                "design-derived CBE"]
    return m._unresolved(rec)


def rollup_v5(m, cfg: str, lines: list, xe_split: dict, refs: list, fraction: float) -> dict:
    """The v3 rollup() arithmetic with the system-margin fraction as the only free input: 0.10 (A9.26 bid basis) or
    the v3 0.20 (historical / conservative sensitivity; checked identical to v3 rollup() in build_doc)."""
    if fraction == m.SYSTEM_MARGIN:
        m.assert_no_margin_relaxation({"allocations": "MEV", "system_margin": fraction, "reserve_kg": 0.0,
                                       "xe_case": "LOADED"})
        reading = "MEV_LEVEL_EVIDENCE_BASED (the single owner reading)"
        rule = ("MQ-10: reduce actual subsystem CBE (redesign, integration, lighter qualified parts); the margin "
                "reading is not relaxed; the lines without a value add to this need when known")
    else:
        assert_bid_margin_reading({"allocations": "MEV", "system_margin": fraction, "reserve_kg": 0.0,
                                   "xe_case": "LOADED"})
        reading = ("MEV_LEVEL_EVIDENCE_BASED (the single owner reading; A9.26: 10 % system margin, active proposal / "
                   "bid basis)")
        rule = ("MQ-10 / A9.26: reduce actual subsystem CBE (redesign, integration, lighter qualified parts); the 40 kg "
                "requirement and the A9.26 margin policy are not relaxed further")
    parts, tbd, missing = [], [], []
    for rec in lines:
        if rec["line"] == "AL-HAR":
            continue
        v = rec["value"]["value_kg"]
        parts.append({"line": rec["line"], "used": rec["value"]["governs"], "kg": v})
        tbd += unresolved_v5(m, rec) if fraction != m.SYSTEM_MARGIN else m._unresolved(rec)
        if v is None:
            missing.append(rec["line"])
    nh = m.rk(sum(p["kg"] for p in parts if p["kg"] is not None))
    har = m.harness_row60(nh)
    parts.append({"line": "AL-HAR", "used": "HARNESS_POLICY_ROW60", "kg": har,
                  "partial": bool(missing), "note": "computed on the known non-harness part only" if missing else None})
    tbd += m._unresolved(next(r for r in lines if r["line"] == "AL-HAR"))
    nominal = m.rk(nh + har)
    sm = m.system_margin(nominal) if fraction == m.SYSTEM_MARGIN else system_margin_bid(m, nominal, fraction)
    dry = sm["total_kg"]
    out = {"configuration": cfg, "reading": reading,
           "parts": parts, "nonharness_known_kg": nh, "harness_kg": har, "nominal_dry_known_kg": nominal,
           "system_margin_kg": sm["system_margin_kg"], "reserve_kg": 0.0, "dry_known_kg": dry,
           "lines_without_value": missing, "tbd": tbd, "all_terms_resolved": False, "wet": []}
    for case_kg, sp in sorted(xe_split.items()):
        if sp["loaded_kg"] != case_kg:
            raise MassPolicyError("Xe case is not LOADED (the residual would be counted twice)")
        wet = m.rk(dry + sp["loaded_kg"])
        for name, ref, strict in refs:
            st = m.closure_state(wet, ref, strict, all_resolved=False)
            row = {"xe_case_kg": case_kg, "xe_loaded_kg": sp["loaded_kg"], "residual_inside_case_kg": sp["residual_kg"],
                   "residual_added_on_top_kg": 0.0, "wet_known_kg": wet, "reference": name, "reference_kg": ref,
                   "comparator": "<" if strict else "<=", "state": st}
            if st == "DOES_NOT_CLOSE":
                nh_max = (ref - sp["loaded_kg"]) * (1.0 - m.HARNESS_FRACTION) / (1.0 + fraction)
                row["exceedance_kg"] = m.rk(wet - ref)
                row["redesign_need"] = {"nonharness_nominal_reduction_kg_at_least": m.rk(nh - nh_max),
                                        "nonharness_nominal_max_kg": m.rk(nh_max), "rule": rule}
            else:
                row["margin_to_reference_kg"] = m.rk(ref - wet)
            out["wet"].append(row)
    return out


def _strip(r: dict, *keys) -> dict:
    return {k: v for k, v in r.items() if k not in ("note",) + keys}


# ------------------------------------------------------------------------------------------------ lines
def set_al09(line: dict, m) -> dict:
    """A9.26 section 2: AL-09 = 1.0 kg PROVISIONAL_OWNER_ALLOCATION (owner MEV allocation, MQ-01); harness separate."""
    if line["line"] != "AL-09" or line["value"]["value_kg"] is not None or line.get("row54_combined_allocation_kg") != 1.0:
        raise MassPolicyError("v4 AL-09 is not the TBD_OWNER (MPV3Q-01) line this decision answers")
    new = copy.deepcopy(line)
    v = m.line_mev_value(AL09_KG, None, None)
    if v["governs"] != "ALLOCATION_MEV" or v["value_kg"] != AL09_KG:
        raise MassPolicyError(f"AL-09 owner allocation did not become a {AL09_KG} kg MEV allocation: {v}")
    new.update(
        owner_allocation_kg=AL09_KG,
        owner_allocation_status=list(AL09_STATUS),
        allocation_status=(f"PROVISIONAL_OWNER_ALLOCATION / NOT_CBE / NOT_MEASURED: {AL09_KG:g} kg owner allocation for "
                           "controls / electronics / valve drivers / flight sensors (A9.26 message 2 section 2; "
                           "MPV3Q-01 OWNER_DECIDED A9.26); harness separate (AL-HAR, row-60 5/95 rule); not a row-54 "
                           "value (row 54 gave 1.0 kg to controls + harness combined, kept in "
                           "row54_combined_allocation_kg as history)"),
        allocation_status_v4=line["allocation_status"],
        cbe_status="TBD - replace with a design-derived CBE when available (A9.26 section 2)",
        harness="SEPARATE: AL-HAR by the row-60 5/95 rule (A9.26 section 2; MQ-06); never inside AL-09",
        value=v,
        evidence_class_of_value="owner-allocation (A9.26 PROVISIONAL_OWNER_ALLOCATION, MEV-level per MQ-01; not a CBE, "
                                "not measured)")
    new["owner_answers_applied"] = line["owner_answers_applied"] + [cite_a926([2])]
    return new


# ------------------------------------------------------------------------------------------------ build
def build_doc() -> dict:
    verify_pins()
    v4 = _load(PINS["V4_JSON"][0])
    m = v3_module()
    m4 = v4_module()
    a926 = a9_26_message2()
    split, refs, roll_v4 = m4._split_and_refs(v4)
    lines_v4 = v4["lines"][FLIGHT]

    # identity 1: the v5 roll-up arithmetic at the v3 0.20 fraction reproduces the committed v4 roll-up bit for bit
    again = rollup_v5(m, FLIGHT, copy.deepcopy(lines_v4), split, refs, m.SYSTEM_MARGIN)
    if _strip(again) != _strip(roll_v4):
        raise MassPolicyError("identity check failed: rollup_v5(0.20) does not reproduce the committed v4 roll-up")

    lines = []
    for ln in lines_v4:
        if ln["line"] == "AL-09":
            ln = set_al09(ln, m)
        lines.append(ln)
    # A9.26 sections 1-2: no line other than AL-09 changes (no compensating reduction, line floors unchanged)
    for a, b in zip(lines, lines_v4):
        if a["line"] != b["line"] or (a["line"] != "AL-09" and a != b):
            raise MassPolicyError(f"{a['line']}: a line other than AL-09 changed (A9.26: no compensating reduction)")
    for lid, kg in LINE_UPLIFT_LINES.items():
        ln = next(x for x in lines if x["line"] == lid)
        if ln["value"]["value_kg"] != kg or ln["value"]["governs"] != "MEV_PLANNING_FLOOR":
            raise MassPolicyError(f"{lid}: line-floor value {ln['value']} != {kg} kg MEV planning floor (A9.26 s1)")

    roll = rollup_v5(m, FLIGHT, copy.deepcopy(lines), split, refs, SYSTEM_MARGIN_BID)
    roll["note"] = roll_v4["note"] + "; v5: AL-09 1.0 kg (A9.26), 10 % system margin (A9.26 bid basis)"
    roll["system_margin_fraction"] = SYSTEM_MARGIN_BID
    roll["system_margin_basis"] = ("A9.26 message 2 section 1: 10 % system-level mass margin for the proposal / bid "
                                   "baseline (supersedes the A9.14 MQ-02 20 % reading for the bid baseline only)")
    # identity 2: the historical / conservative 20 % sensitivity is the pinned v3 rollup() on the v5 lines
    hist = rollup_v5(m, FLIGHT, copy.deepcopy(lines), split, refs, m.SYSTEM_MARGIN)
    hist_v3 = m.rollup(FLIGHT, copy.deepcopy(lines), split, refs)
    if _strip(hist) != _strip(hist_v3):
        raise MassPolicyError("identity check failed: rollup_v5(0.20) != pinned v3 rollup() on the v5 lines")

    # A9.26 section 3: owner arithmetic cross-check (STOP if materially different)
    got = {k: roll[k] for k in EXPECTED_ROLLUP}
    hard = {w["xe_case_kg"]: w for w in roll["wet"] if w["reference"] == HARD}
    diffs = [f"{k} {got[k]} vs ~{v}" for k, v in EXPECTED_ROLLUP.items() if abs(got[k] - v) > MATERIAL_KG]
    diffs += [f"wet {c} kg Xe {hard[c]['wet_known_kg']} vs ~{v}" for c, v in EXPECTED_WET.items()
              if abs(hard[c]["wet_known_kg"] - v) > MATERIAL_KG]
    if diffs or roll["lines_without_value"]:
        raise MassPolicyError("STOP (A9.26 section 3): the governed builder differs materially from the owner's "
                              f"arithmetic: {diffs or roll['lines_without_value']}")
    if any(w["state"] != "DOES_NOT_CLOSE" for w in hard.values()):
        raise MassPolicyError("STOP: a HARD_40_WET case no longer DOES_NOT_CLOSE (A9.26 section 4 expects all three)")

    hard_v4 = {w["xe_case_kg"]: w for w in roll_v4["wet"] if w["reference"] == HARD}
    hard_hist = {w["xe_case_kg"]: w for w in hist["wet"] if w["reference"] == HARD}

    # ---- closure vs 40 kg per loaded Xe case (A9.26 section 4; message 1 item 5)
    closure = []
    for c in sorted(hard):
        w = hard[c]
        max_dry = m.rk(w["reference_kg"] - c)
        max_nominal = m.rk(max_dry / (1.0 + SYSTEM_MARGIN_BID))
        closure.append({
            "xe_case_kg": c, "xe_case_role": ("PLANNING / REFERENCE CASE (not the selected Xe load)" if c == 2.0
                                              else "SENSITIVITY CASE"),
            "requirement": "complete flight wet mass < 40 kg (HARD_40_WET; not relaxed)",
            "max_allowable_dry_kg_strictly_below": max_dry,
            "max_allowable_nominal_dry_kg_strictly_below": max_nominal,
            "dry_planning_kg": roll["dry_known_kg"], "wet_planning_kg": w["wet_known_kg"], "state": w["state"],
            "exceedance_kg": w.get("exceedance_kg"),
            "dry_reduction_needed_kg_more_than": m.rk(roll["dry_known_kg"] - max_dry),
            "nominal_dry_reduction_needed_kg_more_than": m.rk(roll["nominal_dry_known_kg"] - max_nominal),
            "nonharness_nominal_reduction_kg_at_least": w["redesign_need"]["nonharness_nominal_reduction_kg_at_least"],
            "rule": "the reduction comes from CBE / quotation / design re-base, integration and structural "
                    "optimisation (mass-closure actions); never from requirement relaxation, margin relaxation or "
                    "selecting the Xe load to make compliance easier"})

    # ---- proposal design target (A9.26 section 5)
    pt_dry = m.rk(PROPOSAL_TARGET["nominal_dry_max_kg"] * (1.0 + SYSTEM_MARGIN_BID))
    pt_cases = []
    for c in sorted(hard):
        wet = m.rk(pt_dry + c)
        pt_cases.append({"xe_case_kg": c, "role": ("PLANNING / REFERENCE CASE (not the selected Xe load)" if c == 2.0
                                                   else "SENSITIVITY CASE"),
                         "wet_target_kg": wet, "vs_40kg": "BELOW_40_KG" if wet < 40.0 else "AT_OR_ABOVE_40_KG",
                         "difference_to_40kg_kg": m.rk(40.0 - wet),
                         "nominal_dry_needed_for_lt_40kg_kg_strictly_below": m.rk((40.0 - c) / (1.0 + SYSTEM_MARGIN_BID))})
    pt_ref = next(x for x in pt_cases if x["xe_case_kg"] == PROPOSAL_TARGET["xe_reference_kg"])
    if pt_ref["wet_target_kg"] != PROPOSAL_TARGET["wet_reference_kg"]:
        raise MassPolicyError(f"proposal target arithmetic {pt_ref['wet_target_kg']} != owner 39.4 kg (A9.26 s5)")
    proposal_target = {
        "label": "PROPOSAL DESIGN TARGET - DESIGN TARGET, NOT ACHIEVED EVIDENCE (A9.26 section 5)",
        "nominal_dry_max_kg": PROPOSAL_TARGET["nominal_dry_max_kg"], "comparator": "<=",
        "system_margin_fraction": SYSTEM_MARGIN_BID, "dry_target_kg": pt_dry,
        "xe_reference_case_kg": PROPOSAL_TARGET["xe_reference_kg"],
        "wet_target_at_reference_kg": pt_ref["wet_target_kg"],
        "arithmetic": f"{PROPOSAL_TARGET['nominal_dry_max_kg']:g} x 1.10 + {PROPOSAL_TARGET['xe_reference_kg']:g} = "
                      f"{pt_ref['wet_target_kg']:g} kg wet",
        "by_xe_case": pt_cases,
        "gap_from_current_planning_rollup": {
            "nominal_dry_reduction_needed_kg": m.rk(roll["nominal_dry_known_kg"] - PROPOSAL_TARGET["nominal_dry_max_kg"]),
            "dry_reduction_needed_kg": m.rk(roll["dry_known_kg"] - pt_dry),
            "basis": "current provisional planning / evidence roll-up (this record) minus the design target"},
        "xe_rule": "the 2 kg Xe case is a planning / reference case only, not the final selected Xe load; 5 kg and "
                   "10 kg are carried as sensitivities (the flight Xe load is not yet frozen)",
        "not": ["achieved evidence", "a CBE", "a mass-compliance PASS", "the internal allocation target",
                "a selected Xe load"],
        "owner_quotes": [q("target"), q("target_arith"), q("target_label"), q("xe_reference"), q("xe_not_selected"),
                         q("xe_sensitivities")]}

    # ---- internal allocation target (A9.26 section 6)
    br = v4["budget_reference"]
    alloc = []
    for ln in lines:
        if ln["line"] == "AL-HAR":
            continue
        kg = ln["row54_allocation_kg"] if ln["line"] != "AL-09" else ln["owner_allocation_kg"]
        alloc.append({"line": ln["line"], "allocation_kg": kg,
                      "basis": "A9.26 PROVISIONAL_OWNER_ALLOCATION (controls only; harness separate)"
                      if ln["line"] == "AL-09" else "owner row-54 allocation (MEV-level, MQ-01)"})
    a_sum = m.rk(sum(a["allocation_kg"] for a in alloc))
    if a_sum != br["row54_allocation_sum_kg"]:
        raise MassPolicyError(f"allocation sum {a_sum} != row-54 sum {br['row54_allocation_sum_kg']} (AL-09 controls "
                              "1.0 kg replaces the row-54 controls + harness 1.0 kg one for one)")
    a_har = m.harness_row60(a_sum)
    a_nom = m.rk(a_sum + a_har)
    a_sm = system_margin_bid(m, a_nom)
    internal_target = {
        "label": "INTERNAL ALLOCATION TARGET - NOT EVIDENCE OF MASS COMPLIANCE (A9.26 section 6)",
        "lines": alloc, "nonharness_allocation_sum_kg": a_sum, "harness_kg": a_har,
        "harness_rule": "row 60 / MQ-06: 0.05/0.95 x the non-harness allocation sum (harness separate from AL-09)",
        "nominal_dry_kg": a_nom, "system_margin_fraction": SYSTEM_MARGIN_BID, "system_margin_kg": a_sm["system_margin_kg"],
        "dry_kg": a_sm["total_kg"],
        "wet_by_loaded_case": [{"xe_case_kg": c, "wet_kg": m.rk(a_sm["total_kg"] + c)} for c in sorted(hard)],
        "not": ["evidence of mass compliance", "the <= 34 kg proposal nominal-dry target", "a CBE",
                "the current planning / evidence roll-up (the AL-04 / AL-07 / AL-08 evidence floors exceed their "
                "row-54 allocations)"],
        "historical_provenance": {"label": "HISTORICAL / INTERNAL ALLOCATION PROVENANCE (A9.26 section 6; not the "
                                           "active bid mass basis)",
                                  "row54_allocation_sum_kg": br["row54_allocation_sum_kg"],
                                  "system_margin_kg": br["system_margin_kg"], "dry_budget_kg": br["dry_budget_kg"],
                                  "arithmetic": "24 kg + 20 % = 28.8 kg (A9.14 MQ-02; row-54 controls + harness 1.0 kg "
                                                "line, no separate harness)",
                                  "source": "budget_reference (carried from v4 unchanged)"},
        "owner_quotes": [q("row54"), q("row54_history"), q("alloc_label"), q("alloc_not_target")]}
    budget_reference = dict(br, a9_26_status="HISTORICAL / INTERNAL ALLOCATION PROVENANCE (A9.26 section 6): the "
                                             "24 kg + 20 % = 28.8 kg owner budget reference is not the active bid "
                                             "mass basis; the current allocation view is internal_allocation_target")

    # ---- margin audit (A9.26 section 1; message 1 item 3)
    fac_bid = m.rk((1.0 + m.EQUIPMENT_MARGIN) * (1.0 + SYSTEM_MARGIN_BID))
    fac_hist = m.rk((1.0 + m.EQUIPMENT_MARGIN) * (1.0 + m.SYSTEM_MARGIN))
    if (fac_bid, fac_hist) != (1.32, 1.44):
        raise MassPolicyError(f"effective factors {fac_bid} / {fac_hist} != owner 1.32 / 1.44 (A9.26 section 1)")
    audit = []
    for ln in lines:
        v = ln["value"]
        if ln["line"] == "AL-HAR":
            audit.append({"line": "AL-HAR", "value_kg": roll["harness_kg"], "governs": "HARNESS_POLICY_ROW60",
                          "contains_line_uplift": False, "line_uplift_factor": None,
                          "system_margin_factor": 1.0 + SYSTEM_MARGIN_BID, "effective_factor": None,
                          "note": "rule value (5/95 of the non-harness nominal), then the 10 % system margin"})
            continue
        floor = v["governs"] == "MEV_PLANNING_FLOOR"
        audit.append({"line": ln["line"], "value_kg": v["value_kg"], "governs": v["governs"],
                      "evidence_floor_cbe_kg": ln["evidence_floor_cbe_kg"],
                      "contains_line_uplift": floor,
                      "line_uplift_factor": 1.0 + m.EQUIPMENT_MARGIN if floor else None,
                      "system_margin_factor": 1.0 + SYSTEM_MARGIN_BID,
                      "effective_factor": fac_bid if floor else 1.0 + SYSTEM_MARGIN_BID,
                      "effective_factor_historical_20pct": fac_hist if floor else 1.0 + m.SYSTEM_MARGIN,
                      "value_after_system_margin_kg": m.rk(v["value_kg"] * (1.0 + SYSTEM_MARGIN_BID)),
                      "margin_contained": ("20 % LINE-LEVEL planning uplift (MEV planning floor = 1.20 x evidence floor; "
                                           "not a CBE)" if floor else
                                           "owner MEV allocation (MQ-01: equipment margin inside; no row-57 uplift "
                                           "added)" + (" - A9.26 PROVISIONAL_OWNER_ALLOCATION" if ln["line"] == "AL-09"
                                                       else ""))})
    margin_audit = {
        "decision": ("INTENTIONAL_GOVERNANCE (A9.26 section 1): the 20 % line-level uplift is kept on the floor-derived "
                     "lines AL-04 / AL-07 / AL-08 and the system margin is 10 % for the bid basis; effective line x "
                     f"system factor {fac_bid:g} (not {fac_hist:g}, the historical 20 % reading)"),
        "line_uplift_lines": sorted(LINE_UPLIFT_LINES), "line_uplift_fraction": m.EQUIPMENT_MARGIN,
        "system_margin_fraction": SYSTEM_MARGIN_BID, "effective_factor_floor_lines": fac_bid,
        "effective_factor_floor_lines_historical": fac_hist,
        "harness_note": "the row-60 harness (5/95) applies to every line before the system margin",
        "lines": audit,
        "owner_quotes": [q("line_uplift"), q("factor"), q("floors_unchanged"), q("margin"), q("historical")]}

    # ---- historical / conservative sensitivity (20 %)
    historical = {
        "label": "HISTORICAL / CONSERVATIVE SENSITIVITY (A9.14 MQ-02 20 % system margin; superseded for the proposal / "
                 "bid baseline by A9.26 section 1; NOT the active bid basis)",
        "recomputed_with_al09": {**{k: hist[k] for k in ("nonharness_known_kg", "harness_kg",
                                                          "nominal_dry_known_kg", "system_margin_kg", "dry_known_kg",
                                                          "lines_without_value")},
                                 "reading": "HISTORICAL / CONSERVATIVE SENSITIVITY - " + hist["reading"],
                                 "role": "HISTORICAL / CONSERVATIVE SENSITIVITY (never the active roll-up; the "
                                         "active bid roll-up is rollups[0])",
                                 "system_margin_fraction": m.SYSTEM_MARGIN,
                                 "wet_by_loaded_case": [{"xe_case_kg": c, "wet_known_kg": w["wet_known_kg"],
                                                         "state": w["state"], "exceedance_kg": w.get("exceedance_kg")}
                                                        for c, w in sorted(hard_hist.items())],
                                 "basis": "pinned v3 rollup() (0.20 system margin, row-60 harness, LOADED Xe) on the v5 "
                                          "lines (AL-09 = 1.0 kg); identical to the v5 arithmetic at 0.20"},
        "v4_al09_excluded_history": {
            "dry_known_kg": roll_v4["dry_known_kg"], "nonharness_known_kg": roll_v4["nonharness_known_kg"],
            "harness_kg": roll_v4["harness_kg"], "nominal_dry_known_kg": roll_v4["nominal_dry_known_kg"],
            "system_margin_kg": roll_v4["system_margin_kg"], "lines_without_value": roll_v4["lines_without_value"],
            "wet_by_loaded_case": [{"xe_case_kg": c, "wet_known_kg": w["wet_known_kg"], "state": w["state"]}
                                   for c, w in sorted(hard_v4.items())],
            "label": "HISTORICAL (mass_power_a9_v4): dry_known_partial - AL-09 had no value and was excluded; not "
                     "a complete dry mass; never the active roll-up",
            "source": {"path": PINS["V4_JSON"][0], "sha256": PINS["V4_JSON"][1]}},
        "owner_quotes": [q("sensitivity"), q("historical")]}

    # ---- old -> new (v4 -> v5)
    changes = [{"quantity": "AL-09 value (kg)", "old": None, "new": AL09_KG,
                "basis": "A9.26 section 2 (MPV3Q-01 closed)"},
               {"quantity": "system margin fraction (active bid basis)", "old": m.SYSTEM_MARGIN, "new": SYSTEM_MARGIN_BID,
                "basis": "A9.26 section 1 (20 % kept as historical / conservative sensitivity)"},
               {"quantity": "lines_without_value", "old": roll_v4["lines_without_value"],
                "new": roll["lines_without_value"]}]
    for k in ("nonharness_known_kg", "harness_kg", "nominal_dry_known_kg", "system_margin_kg", "dry_known_kg"):
        changes.append({"quantity": k, "old": roll_v4[k], "new": roll[k]})
    for w_old, w_new in zip(roll_v4["wet"], roll["wet"]):
        if (w_old["xe_case_kg"], w_old["reference"]) != (w_new["xe_case_kg"], w_new["reference"]):
            raise MassPolicyError("v4 / v5 wet rows are not aligned")
        tag = f"({w_new['reference']}, {w_new['xe_case_kg']:g} kg Xe)"
        changes.append({"quantity": f"wet_known_kg {tag}", "old": w_old["wet_known_kg"], "new": w_new["wet_known_kg"],
                        "state_old": w_old["state"], "state_new": w_new["state"]})
        for k in ("exceedance_kg", "margin_to_reference_kg"):
            if k in w_old or k in w_new:
                changes.append({"quantity": f"{k} {tag}", "old": w_old.get(k), "new": w_new.get(k)})
        ro, rn = w_old.get("redesign_need") or {}, w_new.get("redesign_need") or {}
        if ro or rn:
            changes.append({"quantity": f"non-harness nominal reduction needed {tag}",
                            "old": ro.get("nonharness_nominal_reduction_kg_at_least"),
                            "new": rn.get("nonharness_nominal_reduction_kg_at_least")})

    hierarchy = {
        "requirement": "complete flight wet mass < 40 kg (HARD_40_WET; not relaxed)",
        "proposal_design_target": f"nominal dry <= {PROPOSAL_TARGET['nominal_dry_max_kg']:g} kg, 10 % system margin, "
                                  f"{PROPOSAL_TARGET['xe_reference_kg']:g} kg Xe planning reference -> "
                                  f"~{pt_ref['wet_target_kg']:g} kg wet (DESIGN TARGET, not achieved evidence)",
        "current_provisional_planning_rollup": (
            f"~{roll['dry_known_kg']:.2f} kg dry after the 10 % system margin; ~"
            + " / ".join(f"{hard[c]['wet_known_kg']:.2f}" for c in sorted(hard)) + " kg wet for "
            + " / ".join(f"{c:g}" for c in sorted(hard)) + " kg Xe planning cases"),
        "current_status": MASS_STATUS,
        "mass_closure_actions": [a[2] if a[1] in ("AL-HAR", "system") else f"{a[1]} {a[2]}" for a in CLOSURE_ACTIONS],
        "rule": "do not claim current mass compliance (A9.26 section 7)"}
    mass_status = {
        "status": MASS_STATUS,
        "reading": ("CURRENT PROVISIONAL PLANNING / EVIDENCE FLOOR (not a complete CBE: the lines are owner MEV "
                    "allocations, MEV planning floors from analog / preliminary-design floors and the A9.26 provisional "
                    "AL-09 allocation; no CBE, no measured mass; A9.26 sections 3-4, 7)"),
        "mass_compliance": ("INCOMPLETE_EVIDENCE / NOT_YET_CLOSED: no PASS; the requirement complete flight wet mass < "
                            "40 kg is not relaxed; the 2 kg Xe planning / reference case is "
                            f"{hard[2.0]['exceedance_kg']:.4f} kg above it under the present preliminary roll-up "
                            "(A9.26 section 4)"),
        "xe_cases": ("loaded Xe 2 / 5 / 10 kg: 2 kg is a PLANNING / REFERENCE CASE, 5 and 10 kg are SENSITIVITY CASES; "
                     "the flight Xe load is NOT YET FROZEN and none of them is the selected Xe load (A9.26 section 5; "
                     "A9.25 message 8 section 7)"),
        "bid_hierarchy": hierarchy,
        "source": "A9.26 message 2 (mass_power_a9_v5 is the active flight mass source)",
        "v4_mass_status_history": v4["mass_status"],
        "owner_quotes": [q("status"), q("no_pass"), q("no_compliance")]}

    st = v4["statuses"]
    items_v3 = copy.deepcopy(v4["items_v3"])
    for it in items_v3:
        if it["id"] == "MPV3-01":
            it["v5_status"] = ("SUPERSEDED_FOR_THE_PROPOSAL_BID_BASELINE_ONLY by MPV5-01 (A9.26 section 1: 10 %); the "
                               "0.20 reading is the HISTORICAL / CONSERVATIVE SENSITIVITY")
        elif it["id"] == "MPV3-06":
            it["v5_status"] = "ANSWERED by MPV5-02 (A9.26 section 2: 1.0 kg PROVISIONAL_OWNER_ALLOCATION; MPV3Q-01 closed)"
    items_v5 = [
        {"id": "MPV5-01", "name": "system margin, active proposal / bid basis (fraction of the current pre-margin "
                                  "nominal dry)", "value": SYSTEM_MARGIN_BID, "units": "1",
         "evidence_class": "owner-allocation", "source": [cite_a926([1])],
         "status": "OWNER_DECIDED_A9_26 (bid basis; the 20 % MPV3-01 reading is kept as historical / conservative "
                   "sensitivity)", "replaces": "MPV3-01 (0.2) for the proposal / bid baseline only"},
        {"id": "MPV5-02", "name": "AL-09 controls / electronics / valve drivers / flight sensors allocation (harness "
                                  "separate)", "value": AL09_KG, "units": "kg", "evidence_class": "owner-allocation",
         "source": [cite_a926([2])], "status": " / ".join(AL09_STATUS),
         "replaces": "MPV3-06 (TBD_OWNER, MPV3Q-01)"},
        {"id": "MPV5-03", "name": "proposal design target: nominal dry mass", "value": PROPOSAL_TARGET["nominal_dry_max_kg"],
         "units": "kg (<=)", "evidence_class": "owner-allocation", "source": [cite_a926([5])],
         "status": "DESIGN_TARGET_NOT_ACHIEVED_EVIDENCE"}]
    margin_convention = dict(v4["margin_convention"],
                             system_margin="0.10 x the current nominal dry (A9.26 section 1, active proposal / bid "
                                           "basis); no reserve",
                             system_margin_historical="0.20 x the current nominal dry (A9.14 MQ-02): HISTORICAL / "
                                                      "CONSERVATIVE SENSITIVITY only (historical_conservative_"
                                                      "sensitivity_20pct)",
                             line_uplift="20 % line-level planning uplift kept on the floor-derived lines AL-04 / "
                                         "AL-07 / AL-08 (MEV planning floors, not CBEs); effective line x system factor "
                                         "1.32 (A9.26 section 1)")
    open_register = dict(v4["open_register_status"],
                         **{"MQ-02": "OWNER_DECIDED (A9.14); SUPERSEDED_FOR_THE_PROPOSAL_BID_BASELINE_ONLY by A9.26 "
                                     "section 1 (10 % system margin); the 20 % reading is kept as historical / "
                                     "conservative sensitivity",
                            "MPV3Q-01": "OWNER_DECIDED (A9.26 message 2 section 2: AL-09 = 1.0 kg "
                                        "PROVISIONAL_OWNER_ALLOCATION / NOT_CBE / NOT_MEASURED; harness separate)"})
    oq = copy.deepcopy(v4["open_owner_questions"])
    for x in oq:
        if x["id"] == "MPV3Q-01":
            x.update(status="CLOSED_OWNER_DECIDED_A9_26",
                     answer=f"AL-09 = {AL09_KG:g} kg, {' / '.join(AL09_STATUS)}; harness separate under the 5/95 rule; "
                            "no compensating reduction on another line; replace with a design-derived CBE when "
                            "available", decided_by=cite_a926([2]))
    owner_answers = v4["owner_answers_applied"] + [
        dict(key="A9.26", id=f"message 2 section {sec}", quote=quote, path=PINS["A9_26_MD"][0],
             md_sha256=PINS["A9_26_MD"][1], json_path=PINS["A9_26_JSON"][0], json_sha256=PINS["A9_26_JSON"][1],
             how_applied=how)
        for sec, quote, how in (
            (1, Q["margin"][1], "rollup_v5 / system_margin_bid: 10 % of the current pre-margin nominal dry (active bid "
                                "basis); 20 % roll-up kept as historical_conservative_sensitivity_20pct"),
            (1, Q["line_uplift"][1], "AL-04 / AL-07 / AL-08 MEV planning floors unchanged (4.2048 / 6.0 / 5.9148 kg); "
                                     "margin_audit effective factor 1.32"),
            (2, Q["al09"][1], "AL-09 value 1.0 kg ALLOCATION_MEV (owner_allocation_kg); MPV3Q-01 closed"),
            (2, Q["harness"][1], "AL-HAR stays the row-60 5/95 rule on the non-harness nominal"),
            (5, Q["target"][1], "proposal_design_target"),
            (6, Q["alloc_label"][1], "internal_allocation_target; budget_reference relabelled historical provenance"),
        )]

    d = copy.deepcopy(v4)
    d.update({
        "schema": SCHEMA_ID, "id": SCHEMA_ID, "lane": "a9_26_mass_budget_policy",
        "directive": "A9.26 message 2 MASS_BUDGET_DECISIONS_PRE_BID_FREEZE (owner 2026-10-05): 10 % system margin for "
                     "the proposal / bid basis (20 % kept as historical / conservative sensitivity), 20 % line uplift "
                     "kept on AL-04 / AL-07 / AL-08, AL-09 = 1.0 kg PROVISIONAL_OWNER_ALLOCATION (MPV3Q-01 closed), "
                     "40 kg wet requirement not relaxed, proposal design target, internal allocation target",
        "title": "A9 mass + power integration v5: v4 with the A9.26 bid mass policy (10 % system margin, AL-09 1.0 kg "
                 "provisional owner allocation); roll-ups recomputed; MASS INCOMPLETE_EVIDENCE / NOT_YET_CLOSED",
        "status": "A9_26_MASS_POLICY_APPLIED_PROVISIONAL_PLANNING_FLOOR_MASS_NOT_YET_CLOSED",
        "date": DATE, "base_commit": BASE_COMMIT, "generated_by": SCRIPT_REL,
        "companion_document": f"{LANE_REL}/{MD_NAME}", "test": TEST_REL,
        "revision_of": {"path": PINS["V4_JSON"][0], "sha256": PINS["V4_JSON"][1], "md": PINS["V4_MD"][0],
                        "md_sha256": PINS["V4_MD"][1], "builder": PINS["V4_BUILDER"][0],
                        "builder_sha256": PINS["V4_BUILDER"][1],
                        "rule": "v4 immutable history: read as data (JSON); v3 rule functions reused (pinned builder); "
                                "v4 / v3 / v2 never edited",
                        "v4_revision_of": v4["revision_of"]},
        "a9_26": dict(a926, quotes={k: q(k) for k in Q}),
        "items_v3": items_v3, "items_v5": items_v5,
        "margin_convention": margin_convention,
        "lines": {FLIGHT: lines},
        "rollups": [roll],
        "flight_rollup_vs_40kg": [{
            "configuration": FLIGHT, "dry_known_kg": roll["dry_known_kg"],
            "nominal_dry_known_kg": roll["nominal_dry_known_kg"], "system_margin_fraction": SYSTEM_MARGIN_BID,
            "wet_known_kg_by_loaded_case": {str(c): w["wet_known_kg"] for c, w in sorted(hard.items())},
            "hard_40_wet_state_by_loaded_case": {str(c): w["state"] for c, w in sorted(hard.items())},
            "label": "CURRENT PROVISIONAL PLANNING / EVIDENCE FLOOR (not a complete CBE)",
            "numerically_unchanged_vs_v4": False,
            "v4": {"dry_known_kg": roll_v4["dry_known_kg"],
                   "label": "HISTORICAL (mass_power_a9_v4): dry_known_partial (AL-09 excluded; 20 % margin)",
                   "wet_known_kg_by_loaded_case": {str(c): w["wet_known_kg"] for c, w in sorted(hard_v4.items())}},
            "basis": "rollup_v5 (v3 rule functions, 10 % system margin, A9.26) on the v4 lines with AL-09 = 1.0 kg"}],
        "closure_vs_40kg": closure,
        "proposal_design_target": proposal_target,
        "internal_allocation_target": internal_target,
        "budget_reference": budget_reference,
        "margin_audit": margin_audit,
        "historical_conservative_sensitivity_20pct": historical,
        "mass_closure_actions": [{"id": i, "line": ln, "action": a, "owner_quote": quote, "detail": det,
                                  "state": "OPEN"} for i, ln, a, quote, det in CLOSURE_ACTIONS],
        "a9_26_changes_old_new": changes,
        "mass_status": mass_status,
        "open_register_status": open_register,
        "open_owner_questions": oq,
        "owner_answers_applied": owner_answers,
    })
    d["what_this_is_not"] = [
        x.replace("not a CBE: every value is an owner MEV allocation, an owner-stated MEV planning floor or TBD",
                  "not a CBE: every value is an owner MEV allocation, an owner-stated MEV planning floor or the A9.26 "
                  "AL-09 provisional owner allocation")
         .replace("not a margin relaxation: the 40 kg exceedance is reported with the redesign need (MQ-10)",
                  "not a builder-side margin relaxation: the 10 % system margin is the owner's A9.26 bid-basis policy "
                  "(the 20 % roll-up is kept as historical / conservative sensitivity); the 40 kg exceedance is "
                  "reported with the reduction needed (MQ-10)")
        for x in v4["what_this_is_not"]] + ["not a mass-compliance claim: MASS INCOMPLETE_EVIDENCE / NOT_YET_CLOSED "
                                            "(A9.26 sections 4 and 7)"]
    d["recorder_flags"] = v4["recorder_flags"] + [
        "A9.26 (v5): MPV3Q-01 is closed here (OWNER_DECIDED A9.26); the owner-question state record "
        "docs/budgets/owner_decisions/owner_questions_state_v5.json (built from the immutable mass / power v3) still "
        "lists it as TBD_OWNER until an owner-question state successor applies A9.26 (not done in this lane)",
        "A9.26 (v5): the AL-04 / AL-07 / AL-08 line uplift (1.20) plus the 10 % system margin is intentional governance "
        "(effective 1.32), not an accidental double margin"]
    d["compliance"] = dict(v4["compliance"],
                           no_new_numbers="every number is copied from pinned v4 / A9.26 or is deterministic "
                                          "arithmetic on those (v3 rule functions; the owner's approximate values are "
                                          "only cross-checked)",
                           no_margin_relaxation="assert_bid_margin_reading admits only the A9.26 10 % bid reading; "
                                                "the pinned v3 assert_no_margin_relaxation governs the 20 % sensitivity",
                           no_compensating_reduction="every line other than AL-09 is byte-identical to v4 (fail closed)",
                           no_pass="no mass PASS (MASS INCOMPLETE_EVIDENCE / NOT_YET_CLOSED); no PASS for thermal, RF "
                                   "ratings, anode, ICP capacity; the power gate stays NOT_EVALUABLE",
                           pure="not wired into archengine; no frozen data, goldens, abep_sim physics module or v4 / "
                                "v3 / v2 file touched")
    return d


# ------------------------------------------------------------------------------------------------ markdown
def render_md(d: dict) -> str:
    m4 = v4_module()
    T, C = m4._table, m4._cell
    r = d["rollups"][0]
    a = d["a9_26"]
    h = d["mass_status"]["bid_hierarchy"]
    L = ["# A9 mass + power integration v5 (A9.26 bid mass policy)", "",
         f"Generated by `{d['generated_by']}` from `{LANE_REL}/{JSON_NAME}` (do not edit by hand; `--check` verifies). "
         f"Status `{d['status']}`. Base commit `{d['base_commit']}`. Successor of `{d['revision_of']['path']}` "
         f"(sha256 `{d['revision_of']['sha256']}`, immutable; every section not listed here is v4's). Test "
         f"`{d['test']}`.", "",
         f"Authorization: {a['decision']} message {a['message']} {a['key']} ({a['utc']}, text sha256 "
         f"`{a['text_sha256'][:12]}...`; `{a['md']}`, `{a['json']}`).", "",
         f"## Mass status: **{d['mass_status']['status']}**", "",
         f"* Requirement: {h['requirement']}.",
         f"* Proposal design target: {h['proposal_design_target']}.",
         f"* Current provisional planning / evidence roll-up: {h['current_provisional_planning_rollup']}.",
         f"* Current status: **{h['current_status']}** - {d['mass_status']['mass_compliance']}.",
         f"* Xe cases: {d['mass_status']['xe_cases']}.",
         f"* Reading: {d['mass_status']['reading']}.",
         "* Mass-closure actions: " + "; ".join(h["mass_closure_actions"]) + ".",
         f"* Rule: {h['rule']}.", "",
         f"## Current provisional planning / evidence roll-up - `{FLIGHT}` (10 % system margin, A9.26)", ""]
    au = {x["line"]: x for x in d["margin_audit"]["lines"]}
    rows = []
    for ln in d["lines"][FLIGHT]:
        x = au[ln["line"]]
        if ln["line"] == "AL-HAR":
            rows.append([ln["line"], ln["name"], r["harness_kg"], "HARNESS_POLICY_ROW60 (5/95)", "-", "rule (not a CBE)",
                         "-"])
            continue
        rows.append([ln["line"], ln["name"], ln["value"]["value_kg"], ln["value"]["governs"],
                     f"x{x['line_uplift_factor']:g} line uplift" if x["line_uplift_factor"] else "none (MEV allocation)",
                     ln.get("evidence_class_of_value"), ln["evidence_floor_cbe_kg"]])
    L += T(["line", "name", "value used (kg)", "basis", "line uplift", "evidence class", "evidence floor (CBE level)"],
           rows)
    L += [f"non-harness {r['nonharness_known_kg']:g} kg + harness {r['harness_kg']:g} kg = nominal dry "
          f"{r['nominal_dry_known_kg']:g} kg; + 10 % system margin {r['system_margin_kg']:g} kg = **dry planning mass "
          f"{r['dry_known_kg']:g} kg** (reserve 0). Lines without a value: "
          f"{', '.join(r['lines_without_value']) or 'none'}.", ""]
    L += T(["loaded Xe kg", "residual inside", "wet kg", "reference", "state", "exceedance kg",
            "non-harness nominal reduction needed (kg, at least)"],
           [[w["xe_case_kg"], w["residual_inside_case_kg"], w["wet_known_kg"],
             f"{w['reference']} ({w['comparator']} {w['reference_kg']:g})", w["state"], w.get("exceedance_kg"),
             (w.get("redesign_need") or {}).get("nonharness_nominal_reduction_kg_at_least")] for w in r["wet"]])
    L += ["## 40 kg closure per loaded Xe case (HARD_40_WET, not relaxed)", ""]
    L += T(["Xe kg", "role", "max dry (kg, <)", "dry planning kg", "wet kg", "state", "dry reduction needed (kg, >)",
            "nominal dry max (kg, <)", "nominal reduction needed (kg, >)"],
           [[c["xe_case_kg"], c["xe_case_role"], c["max_allowable_dry_kg_strictly_below"], c["dry_planning_kg"],
             c["wet_planning_kg"], c["state"], c["dry_reduction_needed_kg_more_than"],
             c["max_allowable_nominal_dry_kg_strictly_below"], c["nominal_dry_reduction_needed_kg_more_than"]]
            for c in d["closure_vs_40kg"]])
    L += [d["closure_vs_40kg"][0]["rule"] + ".", ""]
    p = d["proposal_design_target"]
    L += [f"## {p['label']}", "",
          f"nominal dry <= {p['nominal_dry_max_kg']:g} kg, 10 % system margin -> dry {p['dry_target_kg']:g} kg; "
          f"{p['arithmetic']} at the {p['xe_reference_case_kg']:g} kg Xe planning / reference case. {p['xe_rule']}. "
          f"Gap from the current planning roll-up: nominal dry "
          f"{p['gap_from_current_planning_rollup']['nominal_dry_reduction_needed_kg']:g} kg, dry "
          f"{p['gap_from_current_planning_rollup']['dry_reduction_needed_kg']:g} kg. Not: {', '.join(p['not'])}.", ""]
    L += T(["Xe kg", "role", "wet target kg", "vs 40 kg", "40 kg minus wet target",
            "nominal dry needed for < 40 kg (kg, <)"],
           [[x["xe_case_kg"], x["role"], x["wet_target_kg"], x["vs_40kg"], x["difference_to_40kg_kg"],
             x["nominal_dry_needed_for_lt_40kg_kg_strictly_below"]] for x in p["by_xe_case"]])
    t = d["internal_allocation_target"]
    L += [f"## {t['label']}", ""]
    L += T(["line", "allocation kg", "basis"], [[x["line"], x["allocation_kg"], x["basis"]] for x in t["lines"]])
    L += [f"non-harness allocation sum {t['nonharness_allocation_sum_kg']:g} kg + harness {t['harness_kg']:g} kg "
          f"({t['harness_rule']}) = nominal {t['nominal_dry_kg']:g} kg; + 10 % {t['system_margin_kg']:g} kg = dry "
          f"{t['dry_kg']:g} kg; wet " + " / ".join(f"{x['wet_kg']:g}" for x in t["wet_by_loaded_case"]) +
          " kg at " + " / ".join(f"{x['xe_case_kg']:g}" for x in t["wet_by_loaded_case"]) + " kg Xe. Not: "
          + "; ".join(t["not"]) + ".", "",
          f"{t['historical_provenance']['label']}: {t['historical_provenance']['arithmetic']} (dry budget "
          f"{t['historical_provenance']['dry_budget_kg']:g} kg).", ""]
    ma = d["margin_audit"]
    L += ["## Margin audit (line uplift vs system margin)", "", ma["decision"] + ".", ""]
    L += T(["line", "value kg", "governs", "contains line uplift", "line factor", "system factor", "effective factor",
            "historical 20 % effective", "margin contained"],
           [[x["line"], x["value_kg"], x["governs"], x["contains_line_uplift"], x["line_uplift_factor"],
             x["system_margin_factor"], x["effective_factor"], x.get("effective_factor_historical_20pct"),
             x.get("margin_contained", x.get("note"))] for x in ma["lines"]])
    hs = d["historical_conservative_sensitivity_20pct"]
    hr, hv = hs["recomputed_with_al09"], hs["v4_al09_excluded_history"]
    L += [f"## {hs['label']}", "",
          f"* Recomputed with AL-09 = 1.0 kg: nominal {hr['nominal_dry_known_kg']:g} kg + 20 % "
          f"{hr['system_margin_kg']:g} kg = dry {hr['dry_known_kg']:g} kg; wet "
          + " / ".join(f"{x['wet_known_kg']:g} ({x['state']})" for x in hr["wet_by_loaded_case"]) + f" kg. {hr['basis']}.",
          f"* {hv['label']}: dry {hv['dry_known_kg']:g} kg; wet "
          + " / ".join(f"{x['wet_known_kg']:g}" for x in hv["wet_by_loaded_case"]) + " kg.", ""]
    L += ["## Old -> new (v4 -> v5)", ""]
    L += T(["quantity", "old (v4)", "new (v5)", "state old", "state new"],
           [[c["quantity"], c["old"], c["new"], c.get("state_old"), c.get("state_new")]
            for c in d["a9_26_changes_old_new"]])
    L += ["## Mass-closure actions (A9.26 section 7)", ""]
    L += T(["id", "line", "action", "detail", "state"],
           [[x["id"], x["line"], x["action"], x["detail"], x["state"]] for x in d["mass_closure_actions"]])
    L += ["## Unresolved mass terms", ""] + [f"* {x}" for x in r["tbd"]] + [""]
    L += ["## Carried unchanged from v4", "",
          f"* AFI-01-S1: {d['open_register_status']['AFI-01-S1']}; AFI-02-RA1: "
          f"{d['open_register_status']['AFI-02-RA1']}; MPV3Q-01: {d['open_register_status']['MPV3Q-01']}.",
          f"* AL-07: {d['afi_corrections']['AFI-02']['a9_25_confirmation']}.",
          f"* C1: {d['statuses']['current_statuses']['C1 conventional reference']}.", "",
          "## Recorder flags", ""] + [f"* {C(f)}" for f in d["recorder_flags"]] + [""]
    return "\n".join(L)


def render():
    doc = build_doc()
    return (json.dumps(doc, indent=1, ensure_ascii=False) + "\n", render_md(doc))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify outputs are up to date; write nothing")
    args = ap.parse_args(argv)
    js, md = render()
    files = {HERE / JSON_NAME: js, HERE / MD_NAME: md}
    if args.check:
        bad = [p.name for p, t in files.items() if not p.exists() or p.read_text(encoding="utf-8") != t]
        if bad:
            print("STALE: " + ", ".join(bad))
            return 1
        print(f"OK: {len(files)} outputs reproduce")
        return 0
    for p, t in files.items():
        p.write_text(t, encoding="utf-8")
    print(f"wrote {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
