"""Owner decisions A9.19 / A9.20 / A9.21 applied to the M16 v4 subsystem-maturity record (record-level overlay).

  A9.19  flight = ONE configuration hall_icp_neutralizer: one Hall accelerator + one RF/ICP electron-source /
         neutralizer for air and Xe, two supply modes (ambient atmospheric primary, Xe contingency / emergency), no
         conventional hollow cathode; C1 is not a flight fallback.
  A9.20  C1 = GROUND_ONLY_LAB_REFERENCE (H-1 I_d,max,H1,Ar characterization; C1-vs-ICP bench control); never flight
         hardware, never in the flight budgets. hall_c1_reference is retired as a flight configuration.
  A9.21  hardware-programme order (H-1 S7.1 -> S7.2; H-1 + C1 reference before P1-S7; ICP Ar -> air/N2 ICP-45 -> Xe
         mode; P2 after the V/I calibration; coupled thermal -> P4; measured thrust / feed map -> AG-12 -> AG-13), the
         mandatory ICP go / no-go before LOCK-1 (no numerical criterion approved), AL-08 provisional until quotations,
         external inputs (AOCS pointing, inclination / LTAN, host drag ICD) staying TBD.

What it changes: per-row labels only. Rows whose recorder / lane text treats C1 or hall_c1_reference as a flight /
fallback element get an 'a9_19_20' record (configuration status, the affected statements marked as pre-A9.19
history); requirement status per RVM row is split into the one flight configuration and the labelled ground
reference; A9.21 programme items are attached to the rows they sequence. No readiness state changes (R-M16V4-01..08
unchanged; the scheduler blocking items stay carried - re-deriving them is the M16 v5 follow-on), quoted owner-question
text stays verbatim, the A9.2 statuses stay verbatim (R-M16V4-06; CONTROL_FALLBACK is immutable A9.2 history).
Fail closed: a row whose text mentions C1 / hall_c1_reference / a fallback without a reviewed entry here raises.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "docs" / "decisions" / "application"))
import a9_later_lib as X  # noqa: E402

ARTIFACT = "docs/experiments/hall_icp/integration/m16_v4/subsystem_maturity_v4.json"
TEST = "tests/test_m16_v4.py"
FLIGHT = X.FLIGHT_CONFIGURATION
GROUND = X.GROUND_REFERENCE
C1_ROLE = X.C1_ROLE

CONFIGURATIONS = {
    FLIGHT: "FLIGHT (A9.19): the one flight configuration - one Hall accelerator + one RF/ICP electron-source / "
            "neutralizer for air and Xe, two supply modes (ambient atmospheric primary, Xe contingency / emergency), no "
            "conventional hollow cathode; A9 stays OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE",
    GROUND: C1_ROLE + " (A9.20): retired as a flight configuration (A9.19); carried only as the labelled ground / "
            "laboratory reference (H-1 I_d,max,H1,Ar characterization, C1-vs-ICP bench control); never flight "
            "compliance evidence",
}
# rows whose recorder / lane text names C1, hall_c1_reference, a cathode or a fallback (checked against SCAN below)
C1_PATTERN = re.compile(r"hall_c1_reference|(?<![A-Za-z])C-?1(?![0-9])|cathode|fallback|both configurations", re.I)
ROW_C1 = {
    6: ("FLIGHT_SUBSYSTEM (" + FLIGHT + "; Xe contingency / emergency supply mode, A9.19)",
        "the C1 cathode Xe term / C1 keeper line and 'Xe hardware in both configurations' come from the pre-A9.19 "
        "deliverables (hall_c1_reference column): ground-reference history, never a flight Xe budget line (A9.20)"),
    7: ("FLIGHT_SUBSYSTEM (" + FLIGHT + "; Xe contingency / emergency supply mode, A9.19)",
        "the carried v3 blocking item 'specification gap at the C1 flow range' concerns the ground C1 reference only "
        "(A9.20); it is kept unchanged as the scheduler item (re-deriving blocking items is the M16 v5 follow-on) and is "
        "not a flight Xe-regulator requirement"),
    8: ("FLIGHT_SUBSYSTEM (" + FLIGHT + "; Xe contingency / emergency supply mode, A9.19)",
        "the cathode-feed split in the (verbatim v3) row name and the C1 branch lines / C1 FCUs / C1 controllers are "
        "ground C1 reference items (A9.20); the flight Xe metering serves the Hall Xe supply mode (ICP feed variants "
        "per A9.1 unchanged)"),
    11: (C1_ROLE + " (A9.20): NOT_A_FLIGHT_SUBSYSTEM (A9.19: no conventional hollow cathode)",
         "scheduled only as the ground C1 reference: H-1 + C1 characterization registers I_d,max,H1,Ar before P1-S7 "
         "(A9.10 S3.5, approved again by A9.21) and C1 is the C1-vs-ICP bench control; 'C1 remains CONTROL_FALLBACK' "
         "(lane text) and the '/ fallback' in the owner-accepted role name are pre-A9.19 history"),
}
SCAN_FIELDS = ("name", "a9_6_implemented[].what", "a9_6_lanes[].how", "blocking_item.text", "owner.functional_role",
               "a9_2_statuses")

# A9.21 hardware-programme / open items attached to the rows they sequence: (A9.21 item, md block start, rows)
PROGRAMME = [
    ("HW_PROGRAMME", "6. H-1 engineering build", (9, 10)),
    ("HW_PROGRAMME", "7. C1 ground reference", (11,)),
    ("HW_PROGRAMME", "8. ICP programme", (18,)),
    ("ICP_GATE", "4. ICP go/no-go", (18,)),
    ("HW_PROGRAMME", "9. P2 impedance map", (15, 19)),
    ("HW_PROGRAMME", "10. Coupled H-1 + ICP", (13, 20, 21)),
    ("HW_PROGRAMME", "11. Measured H-1 thrust/feed map", (9,)),
    ("AL08", "2. Xe-hardware floor", (6, 7, 8)),
]
EXTERNAL = ("* AOCS pointing envelope: needs the actual spacecraft/AOCS requirement.",
            "* Inclination and LTAN: not specified by the RFP; do not use the old code default as mission truth.")
EXTERNAL_ROWS = (1,)


class A919M16Error(RuntimeError):
    pass


def _scan(row: dict) -> list:
    out = []

    def add(ptr, text):
        if isinstance(text, str) and C1_PATTERN.search(text):
            out.append({"pointer": ptr, "text": text})
    add("/name", row["name"])
    for i, im in enumerate(row["a9_6_implemented"]):
        add(f"/a9_6_implemented/{i}/what", im["what"])
    for i, ln in enumerate(row["a9_6_lanes"]):
        add(f"/a9_6_lanes/{i}/how", ln["how"])
    add("/blocking_item/text", (row.get("blocking_item") or {}).get("text"))
    add("/owner/functional_role", row["owner"].get("functional_role"))
    for k, v in row["a9_2_statuses"].items():
        add(f"/a9_2_statuses/{k}", v)
    return out


STATEMENT_CLASSES = {
    "CONSISTENT_WITH_A9_19_20": "the text already states the A9.19 / A9.20 reading",
    "SUPERSEDED_FOR_FLIGHT_PRE_A9_19": "pre-A9.19 text treating C1 / hall_c1_reference as a flight configuration, a "
                                       "flight line or a fallback: history only (A9.19 / A9.20)",
    "GROUND_REFERENCE_ITEM": "a C1 item that now reads as a ground-only laboratory reference item (A9.20)",
}
_SUPERSEDED = re.compile(r"fallback|hall_c1_reference|both configurations|AL-C1", re.I)


def classify(text: str) -> str:
    if re.search(r"A9\.19|A9\.20|GROUND_ONLY", text):
        return "CONSISTENT_WITH_A9_19_20"
    if _SUPERSEDED.search(text):
        return "SUPERSEDED_FOR_FLIGHT_PRE_A9_19"
    return "GROUND_REFERENCE_ITEM"


def check_rvm_configurations(rvm: dict) -> None:
    conf = rvm.get("configurations", {})
    if set(conf) != {FLIGHT, GROUND} or not str(conf[GROUND]).startswith("GROUND_ONLY_LABORATORY_REFERENCE") \
            or not str(conf[FLIGHT]).startswith("FLIGHT ARCHITECTURE (A9.19)"):
        raise A919M16Error("RVM configurations are not the A9.19 / A9.20 roles (one flight configuration + the ground "
                           "reference); rebuild the RVM first")


def split_rvm_status(status: dict) -> dict:
    """{configuration: status} -> flight status + labelled ground-reference status (fail closed on other keys)."""
    if set(status) != {FLIGHT, GROUND}:
        raise A919M16Error(f"RVM status configurations {sorted(status)} != [{FLIGHT}, {GROUND}]")
    return {"status": {FLIGHT: status[FLIGHT]},
            "ground_reference_status": {GROUND: status[GROUND]},
            "ground_reference_role": C1_ROLE + " (A9.20): never flight compliance evidence"}


def apply(rows: list) -> dict:
    flagged = {}
    for r in rows:
        hits = _scan(r)
        if hits:
            flagged[r["row"]] = hits
    if sorted(flagged) != sorted(ROW_C1):
        raise A919M16Error(f"rows naming C1 / hall_c1_reference / a fallback {sorted(flagged)} != reviewed rows "
                           f"{sorted(ROW_C1)} (review the A9.19 / A9.20 labels)")
    cites = [X.cite("A9.19"), X.cite("A9.20")]
    for r in rows:
        n = r["row"]
        if n in ROW_C1:
            status, note = ROW_C1[n]
            r["a9_19_20"] = {"configuration_status": status, "flight_configuration": FLIGHT,
                             "c1_role": C1_ROLE + " (A9.20)", "note": note,
                             "statements": [dict(h, classification=classify(h["text"])) for h in flagged[n]],
                             "decisions": cites,
                             "execution_state_effect": "none (labels only; R-M16V4-01..08 unchanged)"}
        if r["row"] == 11:
            r["a9_19_20"]["a9_2_status_note"] = ("'C1 conventional reference' = CONTROL_FALLBACK is carried verbatim "
                                                 "(R-M16V4-06; immutable A9.2 history); for use it is superseded: C1 "
                                                 "is not a flight fallback (A9.19) and is a ground-only laboratory "
                                                 "reference (A9.20)")
            r["a9_19_20"]["functional_role_note"] = ("owner-accepted role name carried verbatim (A9.14 M16-V3-Q-01); "
                                                     "its '/ fallback' part is superseded (A9.19 / A9.20)")
        r["a9_21"] = []
    by = {r["row"]: r for r in rows}
    for item, start, nums in PROGRAMME:
        rec = {"decision": "A9.21", "item": item, "pointer": X.pointer("A9.21", item),
               "decision_json_sha256": X.LOADED["A9.21"]["json_sha256"],
               "verbatim_excerpt": X.block("A9.21", start, extra=1 if item == "ICP_GATE" else 0),
               "effect": "sequencing / scope only; no readiness state change"}
        for n in nums:
            by[n]["a9_21"].append(rec)
    ext = {"decision": "A9.21", "item": "EXTERNAL_INPUTS", "pointer": X.pointer("A9.21", "EXTERNAL_INPUTS"),
           "decision_json_sha256": X.LOADED["A9.21"]["json_sha256"],
           "verbatim_excerpt": " ".join(X.verbatim("A9.21", t) for t in EXTERNAL),
           "effect": "the external inputs stay TBD (no code default as mission truth); no readiness state change"}
    for n in EXTERNAL_ROWS:
        by[n]["a9_21"].append(ext)
    return {"rows_labelled": sorted(ROW_C1), "rows_with_a9_21": sorted(n for n, r in by.items() if r["a9_21"])}


def owner_answers_applied(summary: dict) -> list:
    def e(key, item, ids, how):
        d = X.LOADED[key]
        return {"decision": key, "question_id": item, "decision_code": X.decision_code(key, item),
                "decision_json": d["json"], "decision_json_sha256": d["json_sha256"], "decision_md": d["md"],
                "decision_md_sha256": d["md_sha256"], "artifact": ARTIFACT, "record_ids": ids, "how_applied": how,
                "tests": [TEST]}
    rows = [f"rows[{n}].a9_19_20" for n in summary["rows_labelled"]]
    return [
        e("A9.19", "architecture", ["configurations", "flight_configurations"] + rows,
          "one flight configuration hall_icp_neutralizer; rows naming C1 / hall_c1_reference / a fallback labelled "
          "(configuration_status; pre-A9.19 statements marked history); requirement status per RVM row split into the "
          "flight configuration and the labelled ground reference"),
        e("A9.19", "amends/A9 C1 CONTROL_FALLBACK", ["rows[11].a9_19_20.a9_2_status_note", "a9_2_status_notes"],
          "C1 CONTROL_FALLBACK (A9.2) carried verbatim as history; superseded for use (not a flight fallback)"),
        e("A9.20", "answer", ["configurations", "rows[11].a9_19_20"] + rows,
          "C1 = GROUND_ONLY_LAB_REFERENCE: row 11 is not a flight subsystem; C1 items of rows 6 / 7 / 8 are ground "
          "reference items, never flight budget lines"),
        e("A9.21", "HW_PROGRAMME", [f"rows[{n}].a9_21" for n in summary["rows_with_a9_21"]],
          "programme order attached to the rows it sequences (H-1 S7.1 -> S7.2; H-1 + C1 reference before P1-S7; ICP "
          "Ar -> air/N2 ICP-45 -> Xe mode; P2 after the V/I calibration; coupled thermal -> P4; thrust / feed map -> "
          "AG-12 -> AG-13); no state change"),
        e("A9.21", "ICP_GATE", ["rows[18].a9_21"], "mandatory ICP go / no-go before LOCK-1 attached to row 18 (fail "
          "closed; no numerical criterion approved)"),
        e("A9.21", "AL08", ["rows[6].a9_21", "rows[7].a9_21", "rows[8].a9_21"],
          "AL-08 6.05 kg a provisional planning floor until quotations (rows 6-8)"),
        e("A9.21", "EXTERNAL_INPUTS", ["rows[1].a9_21"], "AOCS pointing envelope and inclination / LTAN stay TBD (row 1)"),
    ]
