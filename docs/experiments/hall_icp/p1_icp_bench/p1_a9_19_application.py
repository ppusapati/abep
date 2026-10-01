"""A9.19 / A9.20 owner decisions applied to the P1 ICP bench package (design + experiments lane).

A9.19 (verbatim .md governs): "One Hall accelerator. One RF/ICP electron-source/neutralizer. Two propellant supply
modes. No conventional hollow cathode." Xe = contingency / emergency supply mode (capability required, RFP-P17-05 /
RFP-P18-08). A9.20: C1 is a GROUND-ONLY laboratory reference (registers I_d,max,H1,Ar on H-1 independently of the ICP,
A9.10 S3.5; bench control in the C1-vs-ICP comparison); never flight hardware; never in flight budgets.

For P1 this means:
  * C1 appears only as GROUND_ONLY_LAB_EQUIPMENT (the dedicated H-1 + C1 HI-AR characterization that registers
    I_d,max,H1,Ar, A9.10 P1Q-07 / S3.5, and the bench control of the later C1-vs-ICP comparison); it is no longer the
    CONTROL_FALLBACK flight configuration. The P1-S6 C1_NOT_INSTALLED / C1_INSTALLED_DISCONNECTED logic is unchanged.
  * ICP ignition / operation records carry an optional ``supply_mode`` (AIR_PRIMARY for N2-family / atmospheric gases,
    XE_CONTINGENCY for Xe, BENCH_AR_ENGINEERING_GROUND_ONLY for Ar) checked against the gas
    (p1_reducer.icp_supply_mode). Both flight supply modes are valid ICP record modes because the ONE ICP serves both;
    P1 itself stays the Ar step (A9.3 P1 authorization; A9 evidence order), so an N2-family or Xe record is refused by
    P1 with the stage that reduces it, never silently re-labelled.
  * The A9.1 ICP feed-gas baseline (G-REUSE primary, G-XE declared variant) is unchanged.
Item texts read back by the immutable RFQ v2 builder (hardware_readiness.item, measurement quantity / status) are not
edited; the C1 status is carried in separate fields. No PASS anywhere.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from abep_sim.design import a9_19_architecture as A  # noqa: E402

ARTIFACT = "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json"
TESTS = ["tests/test_p1_a9_19_owner_rules.py"]
C1_STATUS_TEXT = ("GROUND_ONLY_LAB_EQUIPMENT (A9.20): H-1 I_d,max,H1,Ar characterization (A9.10 S3.5 / P1Q-07) and "
                  "bench control in the C1-vs-ICP comparison; never flight hardware, never in flight budgets; "
                  "not CONTROL_FALLBACK (A9.19)")


def pins() -> list:
    out = []
    for k in ("A9.19", "A9.20"):
        d = A.DECISIONS[k]
        out.append((d["json"], d["json_sha256"], f"owner decision {k} (json)"))
        out.append((d["md"], d["md_sha256"], f"owner decision {k} (verbatim md, governs)"))
    return out


def configurations() -> list:
    return [f"{A.FLIGHT_CONFIGURATION} (the flight configuration: one Hall + one RF/ICP neutralizer serving "
            "AIR_PRIMARY and XE_CONTINGENCY, no conventional hollow cathode, A9.19; P1 builds its ICP module)",
            f"{A.GROUND_REFERENCE_CONFIGURATION} as {A.GROUND_REFERENCE_LABEL} only (C1 = GROUND_ONLY_LAB_EQUIPMENT, "
            "A9.20: not installed or disconnected in P1-S6, A9.10 OQ-RFQV2-09; used for the I_d,max,H1,Ar "
            "characterization gate, A9.10 P1Q-07 / S3.5, and as the C1-vs-ICP bench control; never a flight "
            "candidate)"]


def incorporation(red) -> dict:
    assert red.SUPPLY_MODES == A.SUPPLY_MODES and red.C1_LAB_STATUS == A.GROUND_ONLY_LAB_EQUIPMENT
    assert red.P1_SUPPLY_MODE == A.BENCH_SUPPLY_MODE
    return {
        "decisions": A.cite("A9.19", "A9.20"),
        "reading_rule": "the verbatim .md of A9.19 / A9.20 was read in full and governs; A9.19 amends A9.15 on the "
                        "ROLE of Xe only (capability and two separate tanks stay)",
        "flight_architecture": A.FLIGHT_ARCHITECTURE,
        "c1": {"status": red.C1_LAB_STATUS, "uses": A.C1_ROLE["uses"], "never": A.C1_ROLE["never"],
               "p1_s6_configurations_unchanged": list(red.C1_CONFIGURATIONS),
               "i_d_max_electron_source": red.I_D_MAX_ELECTRON_SOURCE},
        "icp_record_supply_modes": {"modes": list(red.ICP_RECORD_SUPPLY_MODES),
                                    "gases": {k: list(v) for k, v in red.SUPPLY_MODE_GASES.items()},
                                    "stage": dict(red.SUPPLY_MODE_STAGE),
                                    "rule": "an ICP ignition / operation record may declare supply_mode; it must agree "
                                            "with the gas (SupplyModeError otherwise); both flight modes are valid "
                                            "ICP record modes (one ICP for both); P1 reduces the Ar bench mode only"},
        "icp_feed_gas_baseline": A.ICP_FEED_GAS_BASELINE,
        "not_changed": ["P1 stage gas (Ar only, A9.3)", "P1-S6 C1_NOT_INSTALLED logic (A9.10 OQ-RFQV2-09)",
                        "I_d,max,H1,Ar registration via the dedicated H-1 + C1 characterization (A9.10 P1Q-07)",
                        "hardware_readiness item texts and measurement quantities read back by RFQ v2 (immutable)"],
        "statuses": "ICP45 = NOT_EVALUATED until registered; ICP_COUPLED_THERMAL UNRESOLVED; RF ratings "
                    "TBD_AFTER_IMPEDANCE_MAP; anode material OPEN; C1 GROUND_ONLY_LAB_EQUIPMENT; no PASS anywhere",
    }


def owner_answer_rows() -> list:
    def row(dec, item, recs, how):
        r = A.applied_row(dec, ARTIFACT, recs, how, TESTS, item)
        r.update({"id": f"{dec} {item}", "kind": "decision"})
        return r
    return [
        row("A9.19", "architecture", ["scope.configurations", "a9_19_incorporation.flight_architecture"],
            "flight configuration = hall_icp_neutralizer only (one Hall + one RF/ICP neutralizer for AIR_PRIMARY and "
            "XE_CONTINGENCY, no conventional hollow cathode); hall_c1_reference listed only as GROUND_REFERENCE"),
        row("A9.19", "supply_modes", ["record_schema ignition_attempt.supply_mode",
                                      "record_schema icp_operating_point.supply_mode", "p1_reducer.icp_supply_mode"],
            "ICP ignition / operation records allow both supply modes (AIR_PRIMARY N2-family, XE_CONTINGENCY Xe) "
            "via an optional supply_mode checked against the gas; P1 stays the Ar step and refuses N2 / Xe records "
            "naming the stage that reduces them; ICP feed-gas baseline G-REUSE / G-XE unchanged"),
        row("A9.20", "c1_role", ["IF-P1-21", "P1-HW-32.c1_status", "m16_impact row 11",
                                 "a9_19_incorporation.c1"],
            "C1 = GROUND_ONLY_LAB_EQUIPMENT (H-1 I_d,max,H1,Ar characterization, A9.10 S3.5; C1-vs-ICP bench "
            "control); not CONTROL_FALLBACK; P1-S6 C1_NOT_INSTALLED logic unchanged"),
    ]
