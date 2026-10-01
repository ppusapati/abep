"""A9.19 / A9.20 owner decisions applied to the F5 H-1 freeze-candidate record (design + experiments lane).

A9.19: the flight thruster is ONE Hall accelerator (H-1) + ONE RF/ICP electron source / neutralizer serving both supply
modes (AIR_PRIMARY, XE_CONTINGENCY); no conventional hollow cathode. A9.20: C1 is a GROUND-ONLY laboratory reference
(H-1 I_d,max,H1,Ar characterization, A9.10 S3.5; bench control in the C1-vs-ICP comparison). For H-1 this means:
  * H1F-EX-02 (no C1 bore / mount, neutralizer-agnostic head) is consistent with A9.19 and now also cites it;
  * H1F-EX-05 IP-C1 (stray field at the C1 orifice) is a GROUND-BENCH quantity only (the C1 bench configuration);
  * H1F-CH-05 'external C1' note: C1 is ground-only; flight has no hollow cathode;
  * standing fact a9: C1 GROUND_ONLY_LAB_EQUIPMENT (no longer CONTROL_FALLBACK).
No geometry value changes. Pinned decision records: abep_sim/design/a9_19_architecture.py. No PASS.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from abep_sim.design import a9_19_architecture as A  # noqa: E402

ARTIFACT = "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json"
TEST = "tests/test_h1_freeze_candidate.py"
A9_STANDING = ("OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE; A9.19 flight: one Hall + one RF/ICP "
               "neutralizer for AIR_PRIMARY and XE_CONTINGENCY, no conventional hollow cathode; A9.20: C1 "
               "GROUND_ONLY_LAB_EQUIPMENT (was CONTROL_FALLBACK)")


def _src() -> list:
    return [{"path": c["json"], "pointer": "/", "sha256": c["json_sha256"], "pinned": True,
             "note": f"{c['decision']} {c['decision_code']} (verbatim {c['md']} sha256 {c['md_sha256']})"}
            for c in A.cite("A9.19", "A9.20")]


def apply_to_parameters(params: list) -> list:
    by = {p["id"]: p for p in params}
    touched = []
    p = by["H1F-EX-02"]
    p["source"] = p["source"] + _src()
    p["basis"] = p["basis"] + ("; A9.19 (no conventional hollow cathode in flight: the ICP neutralizer is the only "
                               "electron source); A9.20 (C1 ground-only, mounted off H-1 on the bench)")
    p["a9_19"] = {"decisions": ["A9.19", "A9.20"]}
    touched.append(p["id"])

    p = by["H1F-EX-05"]
    p["source"] = p["source"] + _src()
    p["note"] = ((p.get("note") + "; ") if p.get("note") else "") + (
        "IP-C1 is a GROUND-BENCH quantity only (C1 = GROUND_ONLY_LAB_EQUIPMENT in the C1-vs-ICP bench comparison and "
        "the I_d,max,H1,Ar characterization, A9.20); the flight configuration has no C1 (A9.19)")
    p["a9_19"] = {"decisions": ["A9.19", "A9.20"], "ip_c1_scope": "GROUND_BENCH_ONLY"}
    touched.append(p["id"])

    p = by["H1F-CH-05"]
    if "external C1" not in (p.get("note") or ""):
        raise SystemExit("REFUSED: H1F-CH-05 note no longer cites the external C1 (REV-01)")
    p["source"] = p["source"] + _src()
    p["note"] = p["note"] + ("; A9.19 / A9.20: the external C1 is a ground-only laboratory reference, flight has no "
                             "hollow cathode, so the floor removal stands")
    p["a9_19"] = {"decisions": ["A9.19", "A9.20"]}
    touched.append(p["id"])
    return touched


def owner_answers_applied() -> list:
    t = [TEST, "tests/test_design_a9_19_architecture.py"]
    return [
        A.applied_row("A9.19", ARTIFACT, ["standing_facts.a9", "flight_architecture", "H1F-EX-02"],
                      "H-1 is the single Hall accelerator of the flight architecture (one Hall + one RF/ICP "
                      "neutralizer, supply modes AIR_PRIMARY / XE_CONTINGENCY, no hollow cathode); no geometry value "
                      "changed", t, "architecture"),
        A.applied_row("A9.20", ARTIFACT, ["standing_facts.a9", "H1F-EX-05", "H1F-CH-05"],
                      "C1 GROUND_ONLY_LAB_EQUIPMENT: IP-C1 stray field is a ground-bench quantity; C1 not "
                      "CONTROL_FALLBACK", t, "c1_role"),
    ]
