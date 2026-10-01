"""A9.19 / A9.20 owner decisions applied to the F9 architecture freeze-candidate record (design + experiments lane).

A9.19 (verbatim: "One Hall accelerator. One RF/ICP electron-source/neutralizer. Two propellant supply modes. No
conventional hollow cathode."; Xe = contingency / emergency, amends A9.15 on the ROLE of Xe) and A9.20 (C1 is a
GROUND-ONLY laboratory reference) change the F9 record as follows:
  * configuration: flight = hall_icp_neutralizer only (one Hall + one ICP neutralizer for both supply modes
    AIR_PRIMARY / XE_CONTINGENCY); hall_c1_reference is no longer the control / fallback flight configuration and is
    carried only as a labelled GROUND_REFERENCE (C1 = GROUND_ONLY_LAB_EQUIPMENT) where a comparison needs it;
  * AFC-SY-XE-01: Xe capability required (RFP-P17-05 / RFP-P18-08), role contingency / emergency; no C1 Xe branch;
  * AFC-SY-CTL-01: no C1-selected flight start variant (the C1 heater / keeper sequence is a ground bench item);
  * RVM AG-01 rows: the flight column only; any C1 column of the RVM is shown as the ground reference.
The pinned decision records live in abep_sim/design/a9_19_architecture.py (json + verbatim md sha256). No PASS.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from abep_sim.design import a9_19_architecture as A  # noqa: E402

ARTIFACT = "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json"
TEST = "tests/test_architecture_freeze_candidate.py"
FLIGHT = A.FLIGHT_CONFIGURATION
GROUND_REFERENCE = A.GROUND_REFERENCE_CONFIGURATION


def _replace(r: dict, field: str, old: str, new: str) -> None:
    if old not in r[field]:
        raise SystemExit(f"REFUSED: {r['id']}.{field}: expected text not found ({old[:60]!r})")
    r[field] = r[field].replace(old, new)


def _src() -> list:
    return [{"path": c["json"], "pointer": "/", "sha256": c["json_sha256"], "pinned": True,
             "note": f"{c['decision']} {c['decision_code']} (verbatim {c['md']} sha256 {c['md_sha256']})"}
            for c in A.cite("A9.19", "A9.20")]


def configuration_block(a9_status: str) -> dict:
    return {"flight": FLIGHT, "flight_configurations": list(A.FLIGHT_CONFIGURATIONS),
            "flight_architecture": A.FLIGHT_ARCHITECTURE,
            "ground_reference": {"configuration": GROUND_REFERENCE, "label": A.GROUND_REFERENCE_LABEL,
                                 "c1_status": A.GROUND_ONLY_LAB_EQUIPMENT, "flight_candidate": False,
                                 "uses": A.C1_ROLE["uses"]},
            "a9_status": a9_status,
            "rule": "the candidate is defined for the single flight configuration (one Hall + one RF/ICP neutralizer, "
                    "two supply modes AIR_PRIMARY / XE_CONTINGENCY, no conventional hollow cathode; A9.19); "
                    "hall_c1_reference is not a flight candidate and appears only as the labelled GROUND_REFERENCE "
                    "(C1 ground-only laboratory reference, never in flight mass / power / Xe budgets; A9.20)",
            "authority": A.cite("A9.19", "A9.20")}


def rvm_row_status(cfg: dict) -> dict:
    """Flight status; a C1 column of the RVM (if the RVM still carries one) is shown as the ground reference."""
    out = {FLIGHT: cfg[FLIGHT]["status"]}
    if GROUND_REFERENCE in cfg:
        out["ground_reference (" + GROUND_REFERENCE + ")"] = cfg[GROUND_REFERENCE]["status"]
    return out


def apply_rows(rows: list) -> list:
    by = {r["id"]: r for r in rows}
    touched = []

    r = by["AFC-SY-XE-01"]
    r["value"] = ("RFP-required Xenon propulsion capability (RFP-P17-05 'an extra input system to take care any "
                  "problems on board unforeseen problems'; RFP-P18-08 two separate tanks) provided as the "
                  "XE_CONTINGENCY supply mode (contingency / emergency role, A9.19) of the single Hall + single RF/ICP "
                  "neutralizer; ambient atmospheric propellant (180-230 km) is the AIR_PRIMARY mode; separate "
                  "ambient-air and Xe tanks / paths (not a premix); no hollow cathode and no C1 Xe branch in flight "
                  "(A9.20: C1 ground-only); events, duration and flow TBD")
    r["basis"] = r["basis"] + "; A9.19 amends A9.15 on the ROLE of Xe (contingency / emergency; capability required)"
    r["source"] = r["source"] + _src()
    r["a9_19"] = {"decisions": ["A9.19", "A9.20"], "supply_modes": list(A.SUPPLY_MODES),
                  "xe_path_role": A.XE_PATH_ROLE, "icp_gas_mode": A.ICP_FEED_GAS_BASELINE["status"]}
    touched.append(r["id"])

    r = by["AFC-SY-CTL-01"]
    _replace(r, "evidence_note", "a C1-selected variant uses its own qualified heater / keeper sequence",
             "no C1-selected flight variant (A9.19: no conventional hollow cathode; the C1 heater / keeper sequence "
             "is a ground bench item, A9.20)")
    _replace(r, "basis", "the 120 s / 360 s C1 dwell booking applies to the C1-selected variant only",
             "the 120 s / 360 s C1 dwell booking applies to the ground-only C1 bench reference, never to flight "
             "(A9.20)")
    r["source"] = r["source"] + _src()
    r["a9_19"] = {"decisions": ["A9.19", "A9.20"], "flight_start_variants": ["ICP_NEUTRALIZER_BASELINE"]}
    touched.append(r["id"])
    return touched


def owner_answers_applied() -> list:
    t = [TEST, "tests/test_design_a9_19_architecture.py"]
    return [
        A.applied_row("A9.19", ARTIFACT, ["configuration"], "flight configuration = hall_icp_neutralizer only (one "
                      "Hall + one RF/ICP neutralizer, two supply modes AIR_PRIMARY / XE_CONTINGENCY, no conventional "
                      "hollow cathode); control_fallback hall_c1_reference removed", t, "architecture"),
        A.applied_row("A9.19", ARTIFACT, ["AFC-SY-XE-01"], "Xe = XE_CONTINGENCY supply mode (contingency / "
                      "emergency role; capability required by RFP-P17-05 / RFP-P18-08; separate tanks / paths); "
                      "amends the A9.15 'not a contingency' wording on the ROLE of Xe only", t, "xenon_role"),
        A.applied_row("A9.19", ARTIFACT, ["AFC-SY-CTL-01"], "no C1-selected flight start variant", t,
                      "amends A9.14 S8.33 MPQ-01 / S8.17 OQ-A907-07"),
        A.applied_row("A9.20", ARTIFACT, ["configuration.ground_reference", "AG-01 RVM rows", "AFC-SY-CTL-01"],
                      "C1 = GROUND_ONLY_LAB_EQUIPMENT: hall_c1_reference carried only as the labelled GROUND_REFERENCE "
                      "(I_d,max,H1,Ar characterization, A9.10 S3.5; C1-vs-ICP bench control); never flight hardware "
                      "or in flight budgets", t, "c1_role"),
    ]
