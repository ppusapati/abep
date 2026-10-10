"""A9.19 / A9.20 owner decisions applied to the P2 impedance-map preparation (design + experiments lane).

A9.19 (verbatim .md governs): "One Hall accelerator. One RF/ICP electron-source/neutralizer. Two propellant supply
modes. No conventional hollow cathode." Xe = contingency / emergency supply mode (capability required, RFP-P17-05 /
RFP-P18-08). A9.20: C1 is a GROUND-ONLY laboratory reference; never flight hardware.

For P2 this means:
  * the ONE ICP is mapped for both supply modes: the record evidence tag now distinguishes Xe records
    (TAG_XE, XE_CONTINGENCY supply mode; the A9.1 ICP feed-gas baseline G-REUSE primary / G-XE declared variant is
    unchanged) from unclassified gases, and N2 / O2-bearing records map to AIR_PRIMARY
    (p2_impedance_reducer.supply_mode_of_tag); an optional factors.supply_mode must agree with the gas;
  * C1 appears in P2 only as GROUND_ONLY_LAB_EQUIPMENT (P2 does not operate C1); C1 is not CONTROL_FALLBACK.
Cross-lane pair texts (XL-nn) and P2 ids are unchanged. No rating, no PASS.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from abep_sim.design import a9_19_architecture as A  # noqa: E402

ARTIFACT = "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json"
TESTS = ["tests/test_p2_a9_19_owner_rules.py"]


def decision_pins() -> dict:
    out = {}
    for k in ("A9.19", "A9.20"):
        d = A.DECISIONS[k]
        key = "A" + k[1:].replace(".", "")
        out[key] = (d["json"], d["json_sha256"], f"{k} owner decision (json)")
        out[key + "MD"] = (d["md"], d["md_sha256"], f"{k} owner decision (verbatim md, governs)")
    return out


def incorporation(red) -> dict:
    assert red.SUPPLY_MODES == A.SUPPLY_MODES and red.C1_LAB_STATUS == A.GROUND_ONLY_LAB_EQUIPMENT
    return {
        "decisions": A.cite("A9.19", "A9.20"),
        "reading_rule": "the verbatim .md of A9.19 / A9.20 was read in full and governs; A9.19 amends A9.15 on the "
                        "ROLE of Xe only",
        "flight_architecture": A.FLIGHT_ARCHITECTURE,
        "evidence_tag_supply_modes": {t: red.supply_mode_of_tag(t) for t in red.EVIDENCE_TAGS},
        "rule": "the one ICP is mapped for both supply modes; an Xe HOT_MAP record is tagged XE_CONTINGENCY (no longer "
                "OTHER_GAS_UNCLASSIFIED); the mismatch envelope never mixes tags (unchanged); factors.supply_mode, "
                "when given, must agree with factors.gas",
        "c1": {"status": red.C1_LAB_STATUS, "p2_operates_c1": False},
        "icp_feed_gas_baseline": A.ICP_FEED_GAS_BASELINE,
        "statuses": "RF_COMPONENT_RATINGS TBD_AFTER_IMPEDANCE_MAP; ICP_COUPLED_THERMAL UNRESOLVED; anode OPEN; ICP45 "
                    "NOT_EVALUATED; C1 GROUND_ONLY_LAB_EQUIPMENT; no PASS anywhere",
    }


def owner_answer_rows() -> list:
    def row(dec, item, how):
        d = A.DECISIONS[dec]
        return {"ref": {"kind": "owner_decision", "decision": dec, "item": item, "json": d["json"],
                        "json_sha256": d["json_sha256"], "md": d["md"], "md_sha256": d["md_sha256"],
                        "decision_code": d["decision_code"]},
                "how": how, "artifact": ARTIFACT, "tests": TESTS}
    return [
        row("A9.19", "supply_modes", "one ICP for both supply modes: evidence tag TAG_XE (XE_CONTINGENCY) for Xe "
            "records, N2 / O2-bearing tags map to AIR_PRIMARY (p2_impedance_reducer.supply_mode_of_tag); optional "
            "factors.supply_mode checked against the gas; ICP feed-gas baseline G-REUSE / G-XE unchanged"),
        row("A9.20", "c1_role", "C1 = GROUND_ONLY_LAB_EQUIPMENT (P2 does not operate C1); not CONTROL_FALLBACK"),
    ]
