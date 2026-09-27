#!/usr/bin/env python3
"""Parametric Xe mass ledger + stored-Xe subsystem ledger v1 (follow-on fo_xe_system_ledger; trigger T_A5_XE_LEDGER;
owner addenda A5 and A6).

What it is: the A6 ledger m_Xe_total = m_cathode + m_startup + m_transition + m_fallback + m_reserve and the stored-Xe
subsystem m_Xe_subsystem = m_Xe_total + m_tank + m_regulator + m_valves + m_plumbing + m_mounting_thermal, evaluated with
abep_sim/xe_ledger.py (pure, not wired into archengine). Only the A5 cathode design term is fixed (0.10 mg/s over 15,000
firing hours). Every other input is TBD, so the ledger total and the subsystem mass are REFUSED. Named scenarios and
sensitivity surfaces show how the TBD inputs drive the stored-Xe subsystem against the RFP 40 kg requirement and the A5
34-36 kg design allocation, always as a share, never as a prediction.

What it is not: a Xe allocation (A6 not_authorized: freezing total Xe mass), a frozen startup/transition/fallback value,
a Hall performance number or an architecture ranking. hall_only / rf_hall / ecr_hall share one Xe allocation (A5).

Inputs: the owner decision files and the G0 verification record (immutable, sha256-pinned; the build refuses on any
mismatch) and abep_sim.constants (RFP values, MU_EARTH, R_EARTH; read only). Analogue values are transcribed below with
path + locator from the base-commit evidence deliverables (tests/test_xe_ledger.py cross-checks every transcription
against those files). One web source (ESA L-XTA project page, accessed 2026-09-27) is hard-coded with its URL.

Deterministic, standard library only, no Julia, well under a second.

Usage:
  python docs/budgets/xe_ledger/build_xe_ledger.py          # (re)write xe_ledger_v1.json and XE_LEDGER.md
  python docs/budgets/xe_ledger/build_xe_ledger.py --check  # exit 1 unless both are reproduced byte for byte
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from abep_sim import xe_ledger as xl                      # noqa: E402
from abep_sim.constants import MU_EARTH, R_EARTH, RFP      # noqa: E402

OUT_DIR_REL = "docs/budgets/xe_ledger"
SCRIPT_REL = f"{OUT_DIR_REL}/build_xe_ledger.py"
JSON_NAME = "xe_ledger_v1.json"
MD_NAME = "XE_LEDGER.md"
SCHEMA_ID = "xe_ledger_v1"
VERSION = "1.0.0"
BASE_COMMIT = "302e1c94b3bddeb005f17bb189407f2e4641519a"
ARCHS = list(xl.ARCHITECTURES)

A5_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json"
A6_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json"
G0_REL = "docs/decisions/verification/A5_BASELINE_VERIFICATION.json"
OD_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json"
# Immutable owner decision files and the G0 record: pinned by sha256 (never mutable governance files).
DECISION_PINS = {
    OD_REL: "5a5adb8116eecee418992977c239f198a88835c739f357f13a8bddd51778c2ac",
    A5_REL: "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621",
    A6_REL: "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180",
    G0_REL: "4bd0fb4312fba97b18bba92ca0726133947ea6d86327f5e1360ea6af2b163523",
}

CATHINT_REL = "docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json"
HSUST_REL = "docs/evidence/hall_sustainment/hall_sustainment_matrix.json"
DOSSIER_REL = "docs/evidence/cathode/CATHODE_DOSSIER.md"
MASSBOM_REL = "docs/architecture_comparison/mass_bom/MASS_BOM.md"
VETO_REL = "docs/architecture_comparison/veto_layer/veto_layer_v1.json"
DUALFEED_REL = "docs/controls/DUAL_FEED_STATES.md"

LABEL_SCEN = "scenario / illustrative: not an allocation, not a prediction, not frozen (A6 not_authorized)"
LABEL_AXIS = "sensitivity axis value (not evidence, not a threshold)"
LABEL_ANALOGUE = "analogue / illustrative: another thruster or cathode; never the allocation"
SHARE_AXIS = (0.25, 0.5, 1.0)
SHARE_AXIS_NOTE = ("share axis: 0.25 = lane-19 PROPOSED 'dominance_fraction' (cathode_integration_data_v1.json "
                   "proposed_thresholds.dominance_fraction; not in the RFP; owner decides); 0.5 = axis value; 1.0 = the "
                   "whole reference (the subsystem can never exceed the whole system). The owner's share threshold is "
                   "OD-XE-3 (PROPOSED)")


# ---------------------------------------------------------------------------------------------------------- helpers
def r6(x):
    return None if x is None else float(f"{x:.6g}")


def sha256(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def verify_pins() -> None:
    for rel, h in DECISION_PINS.items():
        got = sha256(rel)
        if got != h:
            raise RuntimeError(f"pinned decision file changed: {rel} sha256 {got} != {h}")


def Q(value, unit, source, evidence_class):
    return xl.Quantity(value, unit, source, evidence_class)


def qdict(q: xl.Quantity, **extra) -> dict:
    d = {"value": q.value, "unit": q.unit, "source": q.source, "evidence_class": q.evidence_class}
    d.update(extra)
    return d


# ---------------------------------------------------------------------------------------------------------- A5 / RFP
def a5_basis() -> dict:
    a5 = json.loads((REPO / A5_REL).read_text())
    a6 = json.loads((REPO / A6_REL).read_text())
    g0 = json.loads((REPO / G0_REL).read_text())
    xa = a5["xe_mass_allocation"]
    alloc = [e for e in a5["allocations_and_requirements"] if e["quantity"] == "system mass design allocation"]
    if len(alloc) != 1 or alloc[0]["value"] != "<= 34-36 kg":
        raise RuntimeError("A5 system mass design allocation is not the expected '<= 34-36 kg' entry")
    if (xa["cathode_flow_design_target_mg_s"], xa["cathode_flow_experimental_upper_test_point_mg_s"]) != (0.10, 0.15):
        raise RuntimeError("A5 cathode flows changed")
    if g0["verdict"] != "CLEAN" or g0["a5_sha256"] != DECISION_PINS[A5_REL]:
        raise RuntimeError("G0 record does not certify the pinned A5 file")
    if RFP.mass_max_kg != 40.0 or RFP.ignition_hours != 15000.0 or RFP.mission_hours != 26000.0:
        raise RuntimeError("abep_sim.constants RFP values differ from the recorded RFP envelope")
    return {"a5": a5, "a6": a6, "g0": g0, "xa": xa, "alloc": alloc[0]}


SRC_A5_TARGET = f"{A5_REL} xe_mass_allocation.cathode_flow_design_target_mg_s (owner allocation: design target)"
SRC_A5_UPPER = f"{A5_REL} xe_mass_allocation.cathode_flow_experimental_upper_test_point_mg_s (test point only)"
SRC_RFP_FIRING = ("RFP '> 15,000 h firing' used as the minimum (abep_sim/constants.py RFPConstraints.ignition_hours; "
                  "A5 xe_mass_allocation.reference_arithmetic_15000h)")
MASS_REFERENCES = [
    {"id": "RFP_40kg", "value_kg": 40.0, "kind": "requirement",
     "source": "RFP '< 40 kg' total system mass (abep_sim/constants.py RFPConstraints.mass_max_kg; CLAUDE.md; A5 "
               "allocations_and_requirements 'the 40 kg requirement'); verify against the RFP document"},
    {"id": "A5_alloc_36kg", "value_kg": 36.0, "kind": "allocation",
     "source": f"{A5_REL} allocations_and_requirements 'system mass design allocation <= 34-36 kg' (upper end)"},
    {"id": "A5_alloc_34kg", "value_kg": 34.0, "kind": "allocation",
     "source": f"{A5_REL} allocations_and_requirements 'system mass design allocation <= 34-36 kg' (lower end)"},
]


def mdot_c(v):
    return Q(v, "mg/s", SRC_A5_TARGET if v == 0.10 else SRC_A5_UPPER, "assumed")


def t_firing(hours=15000.0, src=SRC_RFP_FIRING):
    return Q(hours, "h", src, "assumed")


def cathode_kg(mdot_q, t_q) -> float:
    return xl.product_term_kg({"mdot_cathode": mdot_q, "t_firing": t_q}, "m_cathode")


# ---------------------------------------------------------------------------------------------------------- analogues
def analogues() -> list:
    """Transcribed analogue values (ILLUSTRATIVE only). Each carries path + pointer; the test cross-checks them."""
    return [
        {"id": "AN-01", "topic": "cathode Xe flows of other cathodes (context for the fixed cathode term)",
         "label": LABEL_ANALOGUE,
         "values": [
             {"name": "P5 cathode Xe flow setpoint", "value": 0.44, "unit": "mg/s", "evidence_class": "measured",
              "evidence_level": 3, "pointer": f"{CATHINT_REL} parameters.p5_cathode_xe_flow_mg_s.value",
              "source": "brabston_2025_repo (Brabston et al., JPP 2025, Tables 2/4, as frozen in the repository)",
              "applicability": "P5 (3-5 kW class) with its own cathode; a setpoint, not a minimum flow"},
             {"name": "SITAEL HC1 design flow range", "value": [0.08, 0.5], "unit": "mg/s",
              "evidence_class": "measured", "evidence_level": 3,
              "pointer": f"{CATHINT_REL} parameters.hc1_design_flow_range_mg_s.value",
              "source": "pedrini_2017_iepc365 (IEPC-2017-365), abstract p. 1 and Sec. IV.A p. 5",
              "applicability": "HC1 LaB6, 0.3-1 A (developer statement)"},
             {"name": "SITAEL HC3 design flow range", "value": [0.08, 1.0], "unit": "mg/s",
              "evidence_class": "measured", "evidence_level": 3,
              "pointer": f"{CATHINT_REL} parameters.hc3_design_flow_range_mg_s.value",
              "source": "pedrini_2017_iepc365, Sec. V p. 8 (abstract states 0.08-0.5; inconsistency kept)",
              "applicability": "HC3 LaB6, 1-3 A (developer statement)"},
             {"name": "HC3 minimum spot-mode flow (diode, 2.5-4 A)", "value": 0.6, "unit": "mg/s",
              "evidence_class": "measured", "evidence_level": 3,
              "pointer": f"{CATHINT_REL} parameters.hc3_diode_spot_mode_min_flow_mg_s.value",
              "source": "pedrini_2017_iepc365, Sec. V p. 9",
              "applicability": "diode mode, no thruster magnetic field, Xe only"},
             {"name": "HC1 diode flow below which plume mode appeared", "value": 0.8, "unit": "mg/s",
              "evidence_class": "measured", "evidence_level": 3,
              "pointer": f"{CATHINT_REL} parameters.hc1_diode_flow_mg_s.value",
              "source": "pedrini_2017_iepc365, Sec. IV.B p. 7", "applicability": "diode mode, 1.25-1.5 A"},
         ],
         "reading": "The A5 design target 0.10 mg/s sits at the low end of the developer design ranges (0.08 mg/s) and "
                    "below every measured diode-mode minimum flow (0.6-0.8 mg/s). The veto layer carries this as "
                    "RI-MASS-CATHODE-XE (straddles the 40 kg limit; not verdict-bearing). The 5.4 kg term therefore rests "
                    "on a design target that C-1 must demonstrate."},
        {"id": "AN-02", "topic": "Xe flow at discharge ignition (start-then-transition)", "label": LABEL_ANALOGUE,
         "values": [
             {"name": "HT5k DM2 ignition: anode Xe", "value": 10.0, "unit": "mg/s", "evidence_class": "measured",
              "evidence_level": 3, "pointer": f"{HSUST_REL} entries[id=E09].ignition.statement",
              "source": "ANDREUSSI2022_IEPC435 (IEPC-2022-435) p. 3",
              "applicability": "SITAEL HT5k DM2, 5 kW class (1.2-5.2 kW), magnetically shielded; out of the A5 "
                               "power class (<= 1.30-1.35 kW bus allocation)"},
             {"name": "HT5k DM2 ignition: cathode Xe", "value": 1.0, "unit": "mg/s", "evidence_class": "measured",
              "evidence_level": 3, "pointer": f"{HSUST_REL} entries[id=E09].ignition.statement",
              "source": "ANDREUSSI2022_IEPC435 p. 3", "applicability": "HC20h hollow cathode, as above"},
         ],
         "reading": "The only ignition Xe flows recorded in the base. The PPS1350 (E05/E06, ~1 kW class, the closest "
                    "class) also ignited on Xe and then transitioned the anode to N2 or N2/O2 (CIFALI2011 p. 2), but "
                    "the Xe flow and the duration of the Xe phase are not reported in the accessed text. No accessed "
                    "source reports an ignition dwell or a transition duration."},
        {"id": "AN-03", "topic": "cathode preheat durations (start sequence)", "label": LABEL_ANALOGUE,
         "values": [
             {"name": "HC1 preheat to ~1460 K", "value": [600.0, 200.0], "unit": "s",
              "value_display": "600 (at ~45 W) / 200 (at ~60 W)",
              "paired_with": "heater power [45, 60] W ('about')", "evidence_class": "measured", "evidence_level": 3,
              "pointer": f"{CATHINT_REL} parameters.hc1_heating_time_s.value",
              "source": "pedrini_2017_iepc365, Sec. IV.A p. 5", "applicability": "SITAEL HC1 (0.3-1 A)"},
             {"name": "JPL 1.5-cm LaB6 preheat", "value": [18.0, 20.0], "unit": "min", "evidence_class": "measured",
              "evidence_level": 3, "pointer": f"{CATHINT_REL} parameters.jpl_1p5cm_preheat_min.value",
              "source": "goebel_2017_iepc276 (IEPC-2017-276) p. 3",
              "applicability": "1.5-cm LaB6 cathode (HERMeS class), a larger cathode"},
         ],
         "reading": "Heater durations, not Xe quantities: whether and how much Xe flows during preheat is not stated in "
                    "these sources. The repository dual-feed state machine (docs/controls/DUAL_FEED_STATES.md, "
                    "CATHODE_CONDITIONING) books mdot_Xe_cathode during conditioning; that is a design proposal, not "
                    "evidence."},
        {"id": "AN-04", "topic": "demonstrated start/ignition counts of other cathodes", "label": LABEL_ANALOGUE,
         "values": [
             {"name": "JPL H6 LaB6 cathode heater starts (lower bound)", "value": 1000.0, "unit": "1",
              "evidence_class": "measured", "evidence_level": 3,
              "pointer": f"{CATHINT_REL} parameters.jpl_h6_heater_starts_min.value",
              "source": "goebel_polk_2015_iepc43 (IEPC-2015-43) Sec. 4 p. 3 ('over 1000 starts to date')",
              "applicability": "0.63-cm LaB6 cathode of a ~6 kW Hall thruster; laboratory"},
             {"name": "SITAEL HC1 ignitions", "value": "120-ignition test and > 350 ignitions", "unit": "1",
              "evidence_class": "measured", "evidence_level": 3,
              "pointer": f"{CATHINT_REL} parameters.hc1_ignition_keeper_voltage_V.validation_status",
              "source": "pedrini_2017_iepc365 Sec. IV.B pp. 6-7", "applicability": "HC1"},
             {"name": "heaterless LaB6 ignitions", "value": "25,000 (title only, verify)", "unit": "1",
              "evidence_class": "measured", "evidence_level": 5,
              "pointer": f"{DOSSIER_REL} section 3.1 'A heaterless design reports 25,000 ignitions (title only, verify)'",
              "source": "cathode dossier (title-level record; primary not read)",
              "applicability": "not used numerically anywhere in this ledger"},
         ],
         "reading": "Qualification-type cycle counts of other hardware, not mission start counts. The mission start "
                    "count comes from the operations concept (cathode_integration tbd 'starts', milestone C); the "
                    "start-cycle qualification is cathode dossier gap G05."},
        {"id": "AN-05", "topic": "Xe tank mass vs Xe capacity (tankage fraction)", "label": LABEL_ANALOGUE,
         "values": [
             {"name": "ESA L-XTA 300 L: tank mass", "value": 44.0, "unit": "kg", "evidence_class": "measured",
              "evidence_level": 5, "note": "developer-stated product figure ('weighs merely 44 kg'); measurement basis "
                                           "not stated", "pointer": "web: see source"},
             {"name": "ESA L-XTA 300 L: Xe carried", "value": 516.0, "unit": "kg", "evidence_class": "measured",
              "evidence_level": 5, "note": "developer-stated", "pointer": "web: see source"},
             {"name": "ESA L-XTA 900 L: empty tank mass (upper bound)", "value": "< 104", "unit": "kg",
              "evidence_class": "measured", "evidence_level": 5, "note": "'less than 104 kg'", "pointer": "web"},
             {"name": "ESA L-XTA 900 L: Xe carried", "value": 1548.0, "unit": "kg", "evidence_class": "measured",
              "evidence_level": 5, "note": "developer-stated; MEOP 177 bar; Ti-lined COPV", "pointer": "web"},
             {"name": "tankage fraction, 300 L", "value": r6(44.0 / 516.0), "unit": "1", "evidence_class": "inferred",
              "evidence_level": 5, "note": "our arithmetic 44/516", "pointer": "derived here"},
             {"name": "tankage fraction, 900 L (upper bound)", "value": f"< {r6(104.0 / 1548.0)}", "unit": "1",
              "evidence_class": "inferred", "evidence_level": 5, "note": "our arithmetic 104/1548", "pointer": "derived"},
         ],
         "source": {"citation": "ESA, 'L-XTA - Large Xenon Tank Assembly' project page (status date 02/09/2021)",
                    "url": "https://resilience.esa.int/archives/projects/l-xta-large-xenon-tank-assembly",
                    "access": "open web page (project summary)", "accessed": "2026-09-27"},
         "reading": "OUT OF APPLICABILITY: these tanks carry 516-1548 kg Xe, 30-300 times the Xe loads in this ledger. "
                    "On this one family the fraction rises as the tank shrinks (0.085 at 300 L vs < 0.067 at 900 L), "
                    "so it is not transferable to a ~5-30 kg load. Scale context only; the tank mass stays TBD "
                    "(procurement selection)."},
    ]


# ---------------------------------------------------------------------------------------------------------- parameters
TBD_HW = "TBD — requires procurement selection (supplier mass of the selected part at the declared Xe load, MEOP and flow)"


def parameter_table(a5b: dict) -> list:
    c10, c15 = mdot_c(0.10), mdot_c(0.15)
    return [
        {"id": "mdot_cathode", "term": "m_cathode", "unit": "mg/s", "nature": "allocation (A5 design target)",
         "status": "FIXED_DESIGN_TERM — A5 design target, not a demonstrated flow",
         **qdict(c10), "upper_test_point": qdict(c15, status="A5 experimental upper test point only, until this "
                                                             "ledger demonstrates it is affordable"),
         "closes_with": "C-1 measured spot-mode minimum Xe flow at the required emission current, with the thruster "
                        "magnetic field and an air-fed anode (cathode_integration tbd 'cathode_min_flow'; cathode dossier "
                        "G06; A5 architecture-closing risk rank 3)", "milestone": "B", "analogues": ["AN-01"]},
        {"id": "t_firing", "term": "m_cathode", "unit": "h", "nature": "requirement (RFP minimum firing)",
         "status": "FIXED — A5 books the cathode term over the RFP 15,000 firing hours",
         **qdict(t_firing()),
         "sensitivity": "A5 internal design life target >= 18,000 h ('design margin target, not evidenced'): see "
                        "cathode_term.firing_hours_sensitivity; the basis is owner decision OD-XE-5",
         "closes_with": "fixed by A5/RFP; the owner may rebase it on the design-life target (OD-XE-5)",
         "milestone": "A", "analogues": []},
        {"id": "N_starts", "term": "m_startup", "unit": "1", "nature": "parameter",
         "status": "TBD — requires the mission operations concept (eclipse/duty cycling, anomaly restarts) and FDIR",
         "closes_with": "operations concept + FDIR restart policy (cathode_integration tbd 'starts', milestone C); "
                        "start-cycle qualification of C-1 (cathode dossier G05)", "milestone": "C",
         "analogues": ["AN-04"]},
        {"id": "t_startup", "term": "m_startup", "unit": "s", "nature": "parameter",
         "status": "TBD — requires H-1/C-1 measurement of the start sequence (Xe-flowing preheat/conditioning + Xe "
                   "discharge ignition dwell)",
         "closes_with": "H-1/C-1 start-sequence test with Xe flow logged per phase", "milestone": "B",
         "analogues": ["AN-03"]},
        {"id": "mdot_startup", "term": "m_startup", "unit": "mg/s", "nature": "parameter",
         "status": "TBD — requires H-1/C-1 measurement (time-averaged Xe flow over t_startup, per the accounting "
                   "convention)",
         "closes_with": "H-1/C-1 start-sequence test (integrated Xe per start = t_startup x mdot_startup)",
         "milestone": "B", "analogues": ["AN-02"]},
        {"id": "N_transitions", "term": "m_transition", "unit": "1", "nature": "parameter",
         "status": "TBD — requires the operations concept (one per start plus one per recovery from Xe fallback) "
                   "and FDIR", "closes_with": "operations concept + FDIR", "milestone": "C", "analogues": []},
        {"id": "t_transition", "term": "m_transition", "unit": "s", "nature": "parameter",
         "status": "TBD — requires H-1 measurement of the Xe-to-atmosphere transfer ('brief transition support', A5)",
         "closes_with": "H-1 Phase 1 transfer profile (no accessed source reports a transition duration)",
         "milestone": "B", "analogues": ["AN-02"]},
        {"id": "mdot_transition", "term": "m_transition", "unit": "mg/s", "nature": "parameter",
         "status": "TBD — requires H-1 measurement (time-averaged Xe flow during the transfer)",
         "closes_with": "H-1 Phase 1 transfer profile", "milestone": "B", "analogues": ["AN-02"]},
        {"id": "t_fallback_max", "term": "m_fallback", "unit": "h", "nature": "parameter (owner/FDIR limit)",
         "status": "TBD — requires the owner/FDIR maximum cumulative Xe-contingency duration (A5: every Xe-consuming "
                   "mode carries an explicit maximum duration)",
         "closes_with": "owner decision informed by sensitivity surface SS-3; FDIR design", "milestone": "B",
         "analogues": []},
        {"id": "mdot_fallback", "term": "m_fallback", "unit": "mg/s", "nature": "parameter",
         "status": "TBD — requires H-1 measurement of the Xe-fed discharge flow at the fallback operating point",
         "closes_with": "H-1 Xe reference/fallback point on the H-1 accelerator", "milestone": "B",
         "analogues": ["AN-02"]},
        {"id": "reserve_policy", "term": "m_reserve", "unit": "1 or kg", "nature": "owner policy",
         "status": "TBD — requires the owner's reserve policy: form (fraction_of_other_terms | absolute_mass) and value",
         "closes_with": "owner decision OD-XE-2", "milestone": "B", "analogues": []},
        {"id": "tank_model", "term": "m_tank", "unit": "1 or kg", "nature": "hardware (explicit tank model input)",
         "status": "TBD — requires procurement selection (supplier tank mass at the declared Xe load and MEOP) or a "
                   "sourced tank sizing model (form tankage_fraction | tank_mass)",
         "closes_with": "tank selection; mass_bom xe_tank item (G3 lower-bound relation thin_wall_sphere_min_mass_kg "
                        "exists there for FAIL screening only)", "milestone": "B", "analogues": ["AN-05"]},
        {"id": "m_regulator", "term": "hardware", "unit": "kg", "nature": "hardware", "status": TBD_HW,
         "closes_with": "Xe regulator selection (upstream ICD gap G-12: no regulator model)", "milestone": "B",
         "analogues": []},
        {"id": "m_valves", "term": "hardware", "unit": "kg", "nature": "hardware", "status": TBD_HW,
         "closes_with": "Xe isolation/metering valve selection (A5 Xe branch: metering splits to ignition/transition "
                        "feed and cathode feed)", "milestone": "B", "analogues": []},
        {"id": "m_plumbing", "term": "hardware", "unit": "kg", "nature": "hardware", "status": TBD_HW,
         "closes_with": "Xe feed-line layout (filters, lines, fittings, fill/drain, pressure transducers)",
         "milestone": "B", "analogues": []},
        {"id": "m_mounting_thermal", "term": "hardware", "unit": "kg", "nature": "hardware", "status": TBD_HW,
         "closes_with": "tank mounts/brackets and Xe-path thermal hardware (heaters, insulation); boundary with "
                        "mass_bom structure/thermal_hardware is OD-XE-7", "milestone": "B", "analogues": []},
    ]


def ledger_state_inputs() -> dict:
    """The actual ledger inputs today: the A5 cathode term explicit, everything else TBD (what closes it)."""
    inp = {"architecture_scope": ARCHS, "accounting_convention": "PHASE_TOTAL_FLOW",
           "mdot_cathode": mdot_c(0.10), "t_firing": t_firing()}
    for p in parameter_table(None):
        if p["id"] not in ("mdot_cathode", "t_firing"):
            inp[p["id"]] = xl.TBD(p["status"])
    return inp


# ---------------------------------------------------------------------------------------------------------- cathode term
def cathode_term(a5b: dict) -> dict:
    a5_ref = a5b["xa"]["reference_arithmetic_15000h"]
    t15 = t_firing()
    m10, m15 = cathode_kg(mdot_c(0.10), t15), cathode_kg(mdot_c(0.15), t15)
    whole = xl.flow_consuming_mass_mg_s(40.0, t15)
    t18 = t_firing(18000.0, f"{A5_REL} allocations_and_requirements 'internal design life target >= 18,000 h' "
                            "(design margin target, not evidenced)")
    ctx = []
    for name, v in (("HC1/HC3 design range, lower end", 0.08), ("A5 design target", 0.10),
                    ("A5 experimental upper test point", 0.15), ("P5 cathode setpoint", 0.44),
                    ("HC1 upper design / HC3 endurance flow", 0.5), ("HC3 minimum spot-mode flow (diode)", 0.6),
                    ("HC1 diode plume-mode onset", 0.8), ("HC3 upper design flow", 1.0)):
        q = Q(v, "mg/s", "AN-01 / A5 as named", "measured" if name not in ("A5 design target",
                                                                           "A5 experimental upper test point")
              else "assumed")
        m = cathode_kg(q, t15)
        ctx.append({"flow_name": name, "mdot_mg_s": v, "m_cathode_kg_15000h": r6(m),
                    "shares": [{"id": s["id"], "share": r6(s["share"])} for s in xl.allocation_shares(m, MASS_REFERENCES)]})
    flow_for_share = []
    for ref in MASS_REFERENCES:
        for s in SHARE_AXIS:
            flow_for_share.append({"reference": ref["id"], "share": s, "cap_kg": r6(s * ref["value_kg"]),
                                   "mdot_mg_s_consuming_cap_alone": r6(xl.flow_consuming_mass_mg_s(s * ref["value_kg"], t15))})
    return {
        "formula": "m_cathode = mdot_cathode x t_firing",
        "design_term": {"mdot_mg_s": 0.10, "t_firing_h": 15000.0, "m_cathode_kg": r6(m10),
                        "a5_reference_kg": a5_ref["0.10_mg_s_kg"],
                        "arithmetic": "0.10e-6 kg/s x 15,000 h x 3600 s/h = 5.4 kg",
                        "status": "FIXED_DESIGN_TERM (A5 allocation; not a demonstrated flow)",
                        "shares": [dict(s, share=r6(s["share"])) for s in xl.allocation_shares(m10, MASS_REFERENCES)]},
        "upper_test_point": {"mdot_mg_s": 0.15, "t_firing_h": 15000.0, "m_cathode_kg": r6(m15),
                             "a5_reference_kg": a5_ref["0.15_mg_s_kg"],
                             "arithmetic": "0.15e-6 kg/s x 5.4e7 s = 8.1 kg",
                             "status": "A5 experimental upper test point only; never the allocation",
                             "shares": [dict(s, share=r6(s["share"])) for s in xl.allocation_shares(m15, MASS_REFERENCES)]},
        "rejection_illustration": {"flow_consuming_40kg_in_15000h_mg_s": r6(whole),
                                   "a5_statement": "0.74 mg/s over 15,000 h consumes the whole 40 kg (A5; illustrates "
                                                   "rejection only, never an allowable allocation)",
                                   "check_0p74_kg": r6(cathode_kg(Q(0.74, "mg/s", "A5 rejection_illustration",
                                                                    "assumed"), t15))},
        "firing_hours_sensitivity": {
            "label": "sensitivity only; A5 fixes the cathode term at 15,000 h (OD-XE-5)",
            "t_firing_h": 18000.0, "m_cathode_kg_at_0p10": r6(cathode_kg(mdot_c(0.10), t18)),
            "m_cathode_kg_at_0p15": r6(cathode_kg(mdot_c(0.15), t18))},
        "cathode_flow_context": {"label": "AN-01 flows of other cathodes and the A5 flows over 15,000 h (arithmetic); "
                                          "never a Vyovrinda value", "rows": ctx},
        "flow_consuming_share_alone": {"note": SHARE_AXIS_NOTE, "rows": flow_for_share},
    }


# ---------------------------------------------------------------------------------------------------------- scenarios
def orbit_period_h(alt_km: float) -> float:
    a = R_EARTH + alt_km * 1.0e3
    return 2.0 * math.pi * math.sqrt(a ** 3 / MU_EARTH) / 3600.0


SRC_SCEN = "scenario assumption of this ledger (no source fixes it; H-1/C-1 or the owner replaces it)"
SRC_E09_IGN = (f"AN-02: E09 ignition 10 mg/s anode + 1 mg/s cathode Xe ({HSUST_REL} E09, ANDREUSSI2022_IEPC435 p. 3; "
               "5 kW class, out of the A5 power class)")
SRC_HC1_PREHEAT = f"AN-03: HC1 preheat 'about 600 s at about 45 W' ({CATHINT_REL} parameters.hc1_heating_time_s)"


def per_event_values() -> dict:
    t_pre, t_ign = 600.0, 60.0
    mdot_pre, mdot_ign = 0.10, 11.0
    per_start_g = (t_pre * mdot_pre + t_ign * mdot_ign) * 1.0e-3
    t_start = t_pre + t_ign
    mdot_start = per_start_g * 1.0e3 / t_start
    t_tr = 60.0
    mdot_tr = (mdot_ign + mdot_pre) / 2.0
    return {
        "derivation": [
            {"quantity": "t_preheat", "value": t_pre, "unit": "s", "source": SRC_HC1_PREHEAT,
             "evidence_class": "measured", "role": "analogue duration (level 3)"},
            {"quantity": "mdot during preheat/conditioning", "value": mdot_pre, "unit": "mg/s",
             "source": f"A5 cathode design target applied during conditioning (booking per {DUALFEED_REL} "
                       "CATHODE_CONDITIONING, a design proposal)", "evidence_class": "assumed"},
            {"quantity": "mdot at Xe discharge ignition", "value": mdot_ign, "unit": "mg/s", "source": SRC_E09_IGN,
             "evidence_class": "measured", "role": "analogue flow (level 3), out of power class"},
            {"quantity": "t_ignition_dwell", "value": t_ign, "unit": "s", "source": SRC_SCEN,
             "evidence_class": "assumed", "role": "no accessed source reports an ignition dwell"},
            {"quantity": "t_startup = t_preheat + t_ignition_dwell", "value": t_start, "unit": "s",
             "evidence_class": "model-derived", "source": "arithmetic on the rows above"},
            {"quantity": "Xe per start = t_preheat x mdot_pre + t_ign x mdot_ign", "value": r6(per_start_g),
             "unit": "g", "evidence_class": "model-derived", "source": "arithmetic on the rows above"},
            {"quantity": "mdot_startup = Xe per start / t_startup (time average)", "value": r6(mdot_start),
             "unit": "mg/s", "evidence_class": "model-derived", "source": "arithmetic on the rows above"},
            {"quantity": "t_transition", "value": t_tr, "unit": "s", "source": SRC_SCEN, "evidence_class": "assumed",
             "role": "E05 'smooth' and E09 'gradual' transitions report no duration"},
            {"quantity": "mdot_transition = (mdot_ign + mdot_pre)/2", "value": r6(mdot_tr), "unit": "mg/s",
             "evidence_class": "model-derived",
             "source": "linear ramp from the ignition flow to the A5 nominal cathode flow (ramp shape assumed)"},
            {"quantity": "Xe per transition", "value": r6(t_tr * mdot_tr * 1.0e-3), "unit": "g",
             "evidence_class": "model-derived", "source": "arithmetic"},
        ],
        "t_startup_s": t_start, "mdot_startup_mg_s": mdot_start, "t_transition_s": t_tr,
        "mdot_transition_mg_s": mdot_tr, "mdot_fallback_mg_s": mdot_ign,
        "per_start_g": per_start_g, "per_transition_g": t_tr * mdot_tr * 1.0e-3,
    }


SRC_OFF = "scenario assumption: term switched off in this scenario (N = 0 or t = 0)"
SRC_FB_SEPARATE = "scenario assumption: fallback booked separately (SC-3 solves its limit)"
SRC_N_SC1 = ("scenario assumption anchored on AN-04: > 1000 heater starts demonstrated on the JPL H6 LaB6 cathode "
             "(goebel_polk_2015_iepc43 Sec. 4 p. 3); a demonstrated cycle count of another cathode, not a mission "
             "start count")
SRC_N_SC2 = ("model-derived under an assumed ops concept: one start per orbit over the 26,000 h mission, orbital period "
             "at 180 km from abep_sim/constants.py MU_EARTH, R_EARTH (see N_starts_derivation)")


def scenario_inputs(n_starts: float, n_source: str, n_class: str, reserve: dict, pe: dict, *, t_fb_h: float,
                    fb_source: str, zero_events: bool = False) -> dict:
    src_derived = "model-derived per-event value (scenario derivation above)"
    src_scen_or_off = SRC_OFF if zero_events else SRC_SCEN
    inp = {"architecture_scope": ARCHS, "accounting_convention": "PHASE_TOTAL_FLOW",
           "mdot_cathode": mdot_c(0.10), "t_firing": t_firing(),
           "N_starts": Q(n_starts, "1", n_source, n_class),
           "t_startup": Q(0.0 if zero_events else pe["t_startup_s"], "s",
                          SRC_OFF if zero_events else src_derived, "assumed" if zero_events else "model-derived"),
           "mdot_startup": Q(0.0 if zero_events else pe["mdot_startup_mg_s"], "mg/s",
                             SRC_OFF if zero_events else src_derived, "assumed" if zero_events else "model-derived"),
           "N_transitions": Q(n_starts, "1", "scenario assumption: one Xe-to-atmosphere transfer per start (A5 "
                                             "sequence)", "assumed"),
           "t_transition": Q(0.0 if zero_events else pe["t_transition_s"], "s", src_scen_or_off, "assumed"),
           "mdot_transition": Q(0.0 if zero_events else pe["mdot_transition_mg_s"], "mg/s",
                                SRC_OFF if zero_events else src_derived,
                                "assumed" if zero_events else "model-derived"),
           "t_fallback_max": Q(t_fb_h, "h", fb_source, "assumed"),
           "mdot_fallback": Q(0.0 if zero_events else pe["mdot_fallback_mg_s"], "mg/s",
                              SRC_OFF if zero_events else SRC_E09_IGN, "assumed" if zero_events else "measured"),
           "reserve_policy": reserve}
    return inp


def headroom_rows(m_xe: float) -> list:
    rows = []
    for ref in MASS_REFERENCES:
        for s in SHARE_AXIS:
            cap = s * ref["value_kg"]
            h = cap - m_xe
            rows.append({"reference": ref["id"], "share": s, "cap_kg": r6(cap),
                         "hardware_headroom_kg": r6(h) if h >= 0 else None,
                         "status": "HEADROOM" if h >= 0 else "PROPELLANT_ALONE_EXCEEDS_SHARE",
                         "max_tankage_fraction_if_no_other_hardware": r6(h / m_xe) if h >= 0 and m_xe > 0 else None})
    return rows


def scenarios() -> list:
    pe = per_event_values()
    t_orbit = orbit_period_h(RFP.alt_min_km)
    n_orbit = float(math.floor(RFP.mission_hours / t_orbit))
    res0 = {"form": "absolute_mass", "value": Q(0.0, "kg", "scenario assumption: reserve excluded to isolate the "
                                                            "fixed term (not a recommendation)", "assumed")}
    res10 = {"form": "fraction_of_other_terms",
             "value": Q(0.10, "1", "scenario assumption (owner reserve policy TBD, OD-XE-2; SS-1 shows 0 / 0.10 / "
                                   "0.25)", "assumed")}
    defs = [
        ("SC-0", "cathode_only_minimum",
         "Isolates the A5 fixed term: no start, transition, fallback or reserve. Not an operating scenario (at least "
         "one Xe start is needed); a floor under the A5 design target, not a lower bound on flight Xe.",
         scenario_inputs(0.0, SRC_OFF, "assumed", res0, pe, t_fb_h=0.0, fb_source=SRC_OFF, zero_events=True), {}),
        ("SC-1", "nominal_restart",
         "1000 starts, each followed by one transfer; N anchored on the > 1000 heater starts demonstrated on the JPL "
         "H6 LaB6 cathode (AN-04: a demonstrated cycle count of another cathode, NOT a mission start count). "
         "Fallback evaluated separately (SC-3).",
         scenario_inputs(1000.0, SRC_N_SC1, "assumed", res10, pe, t_fb_h=0.0, fb_source=SRC_FB_SEPARATE), {}),
        ("SC-2", "heavy_restart",
         "One start per orbit over the whole mission (eclipse/duty cycling every orbit, assumed ops concept): N = "
         "floor(mission hours / orbital period at 180 km). Same per-event Xe as SC-1, so only N changes.",
         scenario_inputs(n_orbit, SRC_N_SC2, "model-derived", res10, pe, t_fb_h=0.0, fb_source=SRC_FB_SEPARATE),
         {"N_starts_derivation": {"orbital_period_h_180km": r6(t_orbit), "mission_hours": RFP.mission_hours,
                                  "N_starts": n_orbit, "evidence_class": "model-derived",
                                  "source": "two-body circular orbit, T = 2 pi sqrt(a^3/MU_EARTH), a = R_EARTH + 180 km "
                                            "(abep_sim/constants.py); J2 and decay ignored (altitude held by the "
                                            "thruster); ops concept assumed"}}),
    ]
    out = []
    for sid, name, purpose, inp, extra in defs:
        ev = xl.evaluate(inp, level="xe_total")
        m = ev["m_Xe_total_kg"]
        out.append({
            "id": sid, "name": name, "label": LABEL_SCEN, "purpose": purpose, "architecture_scope": ARCHS,
            "accounting_convention": inp["accounting_convention"],
            "parameters": {k: (qdict(v) if isinstance(v, xl.Quantity) else
                               {"form": v["form"], **qdict(v["value"])})
                           for k, v in inp.items() if k not in ("architecture_scope", "accounting_convention")},
            **extra,
            "results": {"terms_kg": {k: r6(v) for k, v in ev["terms_kg"].items()},
                        "m_Xe_total_kg_scenario": r6(m),
                        "propellant_shares": [{"id": s["id"], "kind": s["kind"], "share": r6(s["share"])}
                                              for s in xl.allocation_shares(m, MASS_REFERENCES)],
                        "hardware_headroom": {"meaning": "largest m_tank + m_regulator + m_valves + m_plumbing + "
                                                         "m_mounting_thermal that keeps m_Xe_subsystem <= share x "
                                                         "reference (hardware masses are TBD; nothing is assumed "
                                                         "for them)", "note": SHARE_AXIS_NOTE,
                                              "rows": headroom_rows(m)}},
        })
    # SC-3: nominal restarts, fallback duration SOLVED to the limit (never frozen)
    base = scenario_inputs(1000.0, SRC_N_SC1, "assumed", res10, pe, t_fb_h=0.0, fb_source=SRC_FB_SEPARATE)
    base["t_fallback_max"] = xl.TBD("solved for in this scenario")
    rows = []
    for ref in MASS_REFERENCES:
        for s in SHARE_AXIS:
            for f_tank in (0.0, 0.10, 0.25):
                inp = dict(base)
                inp["tank_model"] = {"form": "tankage_fraction", "value": Q(f_tank, "1", LABEL_AXIS, "assumed")}
                for h in xl.HARDWARE_ITEMS:
                    inp[h] = Q(0.0, "kg", "bounding axis value: zero other hardware (any real part only lowers the "
                                          "allowance)", "assumed")
                a = xl.max_allowance(inp, "t_fallback_max", s * ref["value_kg"])
                rows.append({"reference": ref["id"], "share": s, "cap_kg": r6(s * ref["value_kg"]),
                             "f_tank_axis": f_tank, "status": a["status"],
                             "t_fallback_max_allowable_h": r6(a["value"]),
                             "fallback_xe_allowance_kg": r6(a["term_allowance_kg"])})
    out.append({
        "id": "SC-3", "name": "fallback_limited", "label": LABEL_SCEN,
        "purpose": "SC-1 restarts plus the LONGEST cumulative Xe fallback the cap allows, at the E09 analogue flow "
                   "(11 mg/s, out of power class). Regulator, valves, plumbing and mounting are set to 0 kg (bounding: "
                   "a real part only shortens the allowance). The result is an upper bound on t_fallback_max for these "
                   "inputs, never a frozen value; SS-3 covers other flows.",
        "architecture_scope": ARCHS, "accounting_convention": "PHASE_TOTAL_FLOW",
        "parameters": {k: (qdict(v) if isinstance(v, xl.Quantity) else
                           ({"tbd": v.requires} if isinstance(v, xl.TBD) else {"form": v["form"], **qdict(v["value"])}))
                       for k, v in base.items() if k not in ("architecture_scope", "accounting_convention")},
        "results": {"solved_for": "t_fallback_max", "note": SHARE_AXIS_NOTE, "rows": rows},
    })
    return out, pe


# ---------------------------------------------------------------------------------------------------------- surfaces
def surfaces(pe: dict, n_heavy: float) -> list:
    m10, m15 = cathode_kg(mdot_c(0.10), t_firing()), cathode_kg(mdot_c(0.15), t_firing())
    ss1 = []
    for ref in MASS_REFERENCES:
        for s in SHARE_AXIS:
            for f_tank in (0.0, 0.10, 0.25):
                for m_hw in (0.0, 2.0, 4.0):
                    for f_r in (0.0, 0.10, 0.25):
                        inp = {"reserve_policy": {"form": "fraction_of_other_terms", "value": Q(f_r, "1", LABEL_AXIS, "assumed")},
                               "tank_model": {"form": "tankage_fraction", "value": Q(f_tank, "1", LABEL_AXIS, "assumed")},
                               "m_regulator": Q(m_hw, "kg", LABEL_AXIS + ": lumped non-tank hardware", "assumed"),
                               "m_valves": Q(0.0, "kg", "lumped into m_regulator row", "assumed"),
                               "m_plumbing": Q(0.0, "kg", "lumped into m_regulator row", "assumed"),
                               "m_mounting_thermal": Q(0.0, "kg", "lumped into m_regulator row", "assumed")}
                        smax = xl.xe_sum_cap_kg(inp, s * ref["value_kg"])
                        ss1.append({"reference": ref["id"], "share": s, "f_tank": f_tank, "m_hw_nontank_kg": m_hw,
                                    "f_reserve": f_r, "S_max_kg": r6(smax),
                                    "H_kg_at_0p10": r6(smax - m10), "H_kg_at_0p15": r6(smax - m15)})
    hs = (0.5, 1.0, 2.0, 4.0, 8.0)
    cycles_g = (0.03, 0.1, 0.3, 1.0, 3.0)
    ss2 = [{"H_kg": h, "xe_per_cycle_g": c, "N_starts_max": math.floor(h * 1000.0 / c + 1e-9)}
           for h in hs for c in cycles_g]
    flows = (0.5, 1.0, 2.0, 5.0, 11.0)
    ss3 = [{"H_kg": h, "mdot_fallback_mg_s": f, "t_fallback_max_h": r6(h / (f * 1.0e-6) / 3600.0)}
           for h in hs for f in flows]
    per_kg = [{"mdot_fallback_mg_s": f, "hours_of_xe_fed_discharge_per_kg": r6(1.0 / (f * 1.0e-6) / 3600.0)}
              for f in flows]
    ss5 = [{"H_kg": h, "N_cycles": n, "xe_per_cycle_max_g": r6(h * 1000.0 / n)}
           for h in hs for n in (1000.0, n_heavy)]
    per_cycle_sc1 = pe["per_start_g"] + pe["per_transition_g"]
    return [
        {"id": "SS-1", "title": "Xe sum cap S_max and non-cathode headroom H",
         "formula": "S_max = (share x M - m_hw_nontank) / ((1 + f_tank) (1 + f_reserve));  H = S_max - m_cathode "
                    "(tankage-fraction tank model, reserve as a fraction of the other four terms; other forms: "
                    "abep_sim.xe_ledger.xe_sum_cap_kg)",
         "meaning": "S_max = the largest m_cathode + m_startup + m_transition + m_fallback that keeps m_Xe_subsystem "
                    "<= share x M. H = what remains for startup + transition + fallback after the cathode term "
                    "(5.4 kg at 0.10 mg/s, 8.1 kg at 0.15 mg/s). Negative H: the cathode term with that tank, "
                    "hardware and reserve already exceeds the cap.",
         "axes": {"reference_M": [r["id"] for r in MASS_REFERENCES], "share": list(SHARE_AXIS),
                  "f_tank": [0.0, 0.10, 0.25], "m_hw_nontank_kg": [0.0, 2.0, 4.0], "f_reserve": [0.0, 0.10, 0.25]},
         "axes_label": LABEL_AXIS + "; f_tank = 0 and m_hw = 0 are bounding (physically unattainable) values",
         "rows": ss1},
        {"id": "SS-2", "title": "maximum starts for a given headroom and Xe per start+transition cycle",
         "formula": "N_starts_max = floor(H_s / (t_startup mdot_startup + t_transition mdot_transition)), with "
                    "N_transitions = N_starts and H_s = H - m_fallback",
         "axes_label": LABEL_AXIS,
         "reference_point": {"xe_per_cycle_g_SC1": r6(per_cycle_sc1), "label": LABEL_SCEN},
         "rows": ss2},
        {"id": "SS-3", "title": "maximum cumulative Xe fallback duration for a given headroom and fallback flow",
         "formula": "t_fallback_max_allowable = H_f / mdot_fallback, with H_f = H - m_startup - m_transition; "
                    "hours per kg = 277.78 / mdot_fallback[mg/s]",
         "axes_label": LABEL_AXIS + "; 11 mg/s = AN-02 E09 ignition flow (5 kW class, out of power class)",
         "rows": ss3, "hours_per_kg": per_kg},
        {"id": "SS-4", "title": "combined start / fallback trade line",
         "formula": "N_starts x (Xe per start+transition cycle) + t_fallback_max x mdot_fallback <= H  "
                    "(linear; every point on the line spends the same headroom)",
         "meaning": "exchange rate: fallback hours that cost the same Xe as 1000 start+transition cycles at the SC-1 "
                    "per-cycle Xe (scenario value)",
         "axes_label": LABEL_AXIS,
         "rows": [{"mdot_fallback_mg_s": f, "xe_per_cycle_g": r6(per_cycle_sc1),
                   "fallback_h_equivalent_to_1000_cycles": r6(1000.0 * per_cycle_sc1 * 1.0e-3 / (f * 1.0e-6) / 3600.0)}
                  for f in flows]},
        {"id": "SS-5", "title": "Xe-per-cycle ceiling for a planned number of start+transition cycles",
         "formula": "xe_per_cycle_max = H / N_cycles",
         "axes_label": LABEL_AXIS + "; N = 1000 (SC-1) and the SC-2 per-orbit count",
         "meaning": "a candidate H-1/C-1 test requirement (PROPOSED, owner decides), not a prediction: the start and "
                    "transfer Xe per cycle that the ops concept can afford",
         "rows": ss5},
    ]


# ---------------------------------------------------------------------------------------------------------- document
def open_decisions(cath: dict) -> list:
    fh = cath["firing_hours_sensitivity"]
    return [
        {"id": "OD-XE-1", "topic": "accounting convention of the phase terms",
         "options": list(xl.ACCOUNTING_CONVENTIONS),
         "proposed": "PHASE_TOTAL_FLOW (conservative: overlap with t_firing books the cathode flow twice, at most "
                     "mdot_cathode x overlap hours); every scenario declares it explicitly"},
        {"id": "OD-XE-2", "topic": "reserve policy (form and value)", "options": list(xl.RESERVE_FORMS),
         "proposed": "none; the reserve is always its own term (A6); scenarios use explicit assumed values"},
        {"id": "OD-XE-3", "topic": "share of the mass reference the stored-Xe subsystem may take",
         "proposed": "PROPOSED screening level 0.25 (lane-19 dominance_fraction); the surfaces carry 0.25 / 0.5 / 1.0"},
        {"id": "OD-XE-4", "topic": "residual (unusable) Xe",
         "note": f"A5/A6 define no residual term. {MASSBOM_REL} books xe_residual = 0.02 x xe_load (ESA R-M1-6, a "
                 "margin policy) as its own propellant item. The owner decides whether it enters this ledger as a "
                 "separate term in a revision or stays in mass_bom only; it is never folded silently into m_reserve "
                 "or any other term, and it must not be booked twice."},
        {"id": "OD-XE-5", "topic": "firing-hours basis of the cathode term",
         "note": f"A5 fixes 15,000 h ({cath['design_term']['m_cathode_kg']} kg at 0.10 mg/s); the A5 internal design "
                 f"life target of {fh['t_firing_h']:,.0f} h would give {fh['m_cathode_kg_at_0p10']} kg (sensitivity only)"},
        {"id": "OD-XE-6", "topic": "RFP 'air + Xe' Xe-mode operation",
         "note": "The hard-gate matrix carries G7.xenon_operation and a 25 mN peak with Xe (OD1 reading ii). If the "
                 "RFP requires Xe-mode operation for a duration that consumes stored Xe beyond ignition, cathode and "
                 "contingency, it becomes a new explicit ledger term (owner decision); it is never folded into "
                 "m_fallback."},
        {"id": "OD-XE-7", "topic": "hardware boundary with mass_bom",
         "note": "m_regulator / m_valves / m_plumbing map to mass_bom xe_valve_and_flow_control, m_tank to xe_tank, "
                 "m_mounting_thermal to parts of structure and thermal_hardware (PROPOSED mapping). Hardware inputs "
                 "here are margin-free (CBE) unless their source says otherwise; MGA and system margin stay in "
                 "mass_bom (G3 roll-up)."},
        {"id": "OD-XE-8", "topic": "whether the 40 kg includes the Xe load",
         "note": "mass_bom OD-M7: included as propellant (R3 as recorded; verify against the RFP). This ledger "
                 "reports shares of 40 kg on that reading."},
    ]


def not_authorized_compliance(a6: dict) -> list:
    how = {
        "freezing total Xe mass": "ledger_state.m_Xe_total_kg is null (REFUSED); scenario totals carry the label "
                                  "'scenario / illustrative' and are never an allocation",
        "freezing startup/transition/fallback quantities without evidence": "all eight inputs are TBD in the "
                                                                            "parameter table; scenario values are "
                                                                            "labelled assumptions or analogues",
        "freezing Phase-1 numeric thresholds": "not touched (the share axis is PROPOSED for the owner; no Phase-1 "
                                               "threshold is set)",
        "changing Bundle 1 from NO_BASELINE_YET": "not touched; Bundle 1 stays NO_BASELINE_YET",
        "further broad Hall-transport sensitivity research": "none; no Hall closure enters the Xe path",
        "another facility simulation campaign": "none",
    }
    return [{"item": i, "respected_by": how[i]} for i in a6["not_authorized"]]


def build() -> dict:
    verify_pins()
    a5b = a5_basis()
    params = parameter_table(a5b)
    state = xl.evaluate(ledger_state_inputs(), level="subsystem", allow_partial=True)
    scen, pe = scenarios()
    n_heavy = next(s for s in scen if s["id"] == "SC-2")["N_starts_derivation"]["N_starts"]
    cath = cathode_term(a5b)
    doc = {
        "schema": SCHEMA_ID, "version": VERSION, "ledger_version": xl.LEDGER_VERSION,
        "follow_on": "fo_xe_system_ledger", "trigger": "T_A5_XE_LEDGER",
        "status": "PARAMETRIC_LEDGER — total Xe mass and stored-Xe subsystem mass REFUSED (TBD inputs); nothing frozen",
        "generated_by": SCRIPT_REL, "module": "abep_sim/xe_ledger.py", "base_commit": BASE_COMMIT,
        "decision_pins": DECISION_PINS,
        "g0_precondition": {"record": G0_REL, "verdict": a5b["g0"]["verdict"],
                            "verified_commit": a5b["g0"]["verified_commit"], "a5_sha256": a5b["g0"]["a5_sha256"],
                            "consequence": a5b["g0"]["consequence"]},
        "a5_basis": {"ledger": a5b["xa"]["ledger"], "m_Xe_total_value": a5b["xa"]["m_Xe_total_value"],
                     "mode_rules": a5b["a5"]["operating_modes"]["rules"],
                     "system_mass_design_allocation": a5b["alloc"]},
        "architectures": ARCHS,
        "architecture_neutrality": "COMMON_MODE: hall_only, rf_hall and ecr_hall draw on the one A5 Xe allocation "
                                   "with the same ledger. A branch can modulate the ledger only through measured "
                                   "per-event startup/transition Xe (e.g. whether a pre-ionizer changes the Xe "
                                   "ignition need): TBD, H-1 Phase 1. Nothing here ranks or eliminates a branch.",
        "hall_closure_isolation": "The Xe path is upstream of the discharge: no Hall-transport closure, ensemble "
                                  "member, screening candidate or P5 calibration-nuisance variable enters it "
                                  "(abep_sim.xe_ledger.reject_forbidden_keys). Credible set: empty.",
        "equations": {
            "m_cathode": "mdot_cathode x t_firing",
            "m_startup": "N_starts x t_startup x mdot_startup",
            "m_transition": "N_transitions x t_transition x mdot_transition",
            "m_fallback": "t_fallback_max x mdot_fallback",
            "m_reserve": "explicit policy term, one of: " + " OR ".join(f"{k}: {v}" for k, v in xl.RESERVE_FORMS.items()),
            "m_Xe_total": "m_cathode + m_startup + m_transition + m_fallback + m_reserve",
            "m_tank": "explicit tank model, one of: " + " OR ".join(f"{k}: {v}" for k, v in xl.TANK_FORMS.items()),
            "m_Xe_subsystem": "m_Xe_total + m_tank + m_regulator + m_valves + m_plumbing + m_mounting_thermal",
        },
        "accounting_conventions": xl.ACCOUNTING_CONVENTIONS,
        "mass_references": MASS_REFERENCES,
        "reporting_rule": "masses are reported as a share of each reference, never as a prediction or a verdict",
        "parameters": params,
        "cathode_term": cath,
        "ledger_state": {
            "label": "the ledger as it stands: only the A5 cathode design term is explicit",
            "terms_kg": {k: r6(v) for k, v in state["terms_kg"].items()},
            "m_Xe_total_kg": state["m_Xe_total_kg"], "m_tank_kg": state["m_tank_kg"],
            "m_Xe_subsystem_kg": state["m_Xe_subsystem_kg"],
            "refused": True, "n_missing": len(state["missing"]),
            "subsystem_share_report": "REFUSED: m_Xe_subsystem is not closed, so no share of 40 / 36 / 34 kg is "
                                      "reported for it. Shares are reported for the fixed cathode term "
                                      "(cathode_term.design_term.shares) and, per scenario, for the propellant with "
                                      "the hardware headroom left inside each share (scenarios[*].results).",
            "missing": [m["field"] for m in state["missing"]],
        },
        "scenario_per_event_derivation": pe["derivation"],
        "scenarios": scen,
        "sensitivity_surfaces": surfaces(pe, n_heavy),
        "illustrative_analogues": analogues(),
        "open_owner_decisions": open_decisions(cath),
        "a6_not_authorized_compliance": not_authorized_compliance(a5b["a6"]),
        "milestones": {
            "supports": ["A"],
            "A": "Conditional-selection support: one Xe ledger and stored-Xe subsystem structure common to hall_only, "
                 "rf_hall and ecr_hall, with the conditions (surfaces SS-1..SS-5) under which the stored-Xe subsystem "
                 "stays within a stated share of the 40 kg requirement or the A5 34-36 kg allocation. No total is "
                 "frozen; Bundle 1 stays NO_BASELINE_YET.",
            "to_B": "C-1 measured cathode flow at <= 0.10 mg/s (or the owner re-books the term); H-1/C-1 measured Xe "
                    "per start and per transfer and the Xe-fallback flow; owner reserve policy and share (OD-XE-2/3); "
                    "tank, regulator, valves and plumbing selected with supplier masses.",
            "to_C": "operations concept (N_starts, N_transitions), FDIR maximum fallback duration, qualified hardware "
                    "masses, cathode start-cycle qualification (dossier G05) and integrated mass closure through "
                    "mass_bom (MGA, system margin, residual per OD-XE-4).",
        },
        "evidence_basis": [CATHINT_REL, HSUST_REL, DOSSIER_REL, MASSBOM_REL, VETO_REL + " (RI-MASS-CATHODE-XE)",
                           DUALFEED_REL],
    }
    return doc


# ---------------------------------------------------------------------------------------------------------- markdown
def fmt(x, nd=3):
    if x is None:
        return "—"
    if isinstance(x, str):
        return x
    if isinstance(x, float) and x.is_integer() and abs(x) < 1e7:
        return f"{int(x):,}"
    return f"{x:.{nd}g}" if abs(x) < 1e3 else f"{x:,.0f}"


def pct(x):
    return "—" if x is None else f"{100.0 * x:.2f} %"


def render_md(doc: dict) -> str:
    c = doc["cathode_term"]
    dt, up = c["design_term"], c["upper_test_point"]
    L = []
    a = L.append
    a("# Parametric Xe ledger and stored-Xe subsystem ledger v1")
    a("")
    a(f"**Follow-on:** `fo_xe_system_ledger` (trigger `T_A5_XE_LEDGER`, owner addendum A6). **Status:** "
      f"{doc['status']}. **Milestone support:** A (conditional selection); see the milestone statement.")
    a(f"**Data:** [`xe_ledger_v1.json`](xe_ledger_v1.json), written by `python {SCRIPT_REL}` and checked with "
      f"`--check`. **Code:** `abep_sim/xe_ledger.py` (pure; not wired into `archengine`). **Tests:** "
      "`tests/test_xe_ledger.py`. This file is generated; edit the builder, not this file.")
    a("")
    a("**Owner basis (immutable, sha256-pinned):**")
    a("")
    a("| file | sha256 |")
    a("|---|---|")
    for rel, h in doc["decision_pins"].items():
        a(f"| `{rel}` | `{h}` |")
    a("")
    g = doc["g0_precondition"]
    a(f"G0 precondition: verdict **{g['verdict']}** at `{g['verified_commit']}` ({g['consequence']}).")
    a("")
    a("## Result in one paragraph")
    a(f"Only the A5 cathode design term is fixed: 0.10 mg/s over 15,000 firing hours = **{fmt(dt['m_cathode_kg'])} kg** "
      f"({pct(dt['shares'][0]['share'])} of the 40 kg requirement, {pct(dt['shares'][1]['share'])} / "
      f"{pct(dt['shares'][2]['share'])} of the 36 / 34 kg A5 allocation). The 0.15 mg/s upper test point would take "
      f"{fmt(up['m_cathode_kg'])} kg ({pct(up['shares'][0]['share'])} / {pct(up['shares'][1]['share'])} / "
      f"{pct(up['shares'][2]['share'])}). Startup, transition, fallback, reserve, tank, regulator, valves, plumbing "
      f"and mounting/thermal are TBD, so **m_Xe_total and m_Xe_subsystem are refused** "
      f"({doc['ledger_state']['n_missing']} inputs TBD). The scenarios and surfaces show what the TBD inputs must "
      "satisfy. Three findings follow from them:")
    sc3 = next(s for s in doc["scenarios"] if s["id"] == "SC-3")
    row = next(r for r in sc3["results"]["rows"]
               if r["reference"] == "A5_alloc_34kg" and r["share"] == 0.25 and r["f_tank_axis"] == 0.0)
    ff = next(r for r in c["flow_consuming_share_alone"]["rows"] if r["reference"] == "A5_alloc_34kg" and r["share"] == 0.25)
    sc2 = next(s for s in doc["scenarios"] if s["id"] == "SC-2")
    ss3 = next(s for s in doc["sensitivity_surfaces"] if s["id"] == "SS-3")
    h11 = next(r for r in ss3["hours_per_kg"] if r["mdot_fallback_mg_s"] == 11.0)
    a(f"- At the PROPOSED 25 % share of 34 kg ({fmt(ff['cap_kg'])} kg), the 0.15 mg/s cathode alone takes "
      f"{fmt(up['m_cathode_kg'])} kg; the cathode flow that alone fills that share is "
      f"{fmt(ff['mdot_mg_s_consuming_cap_alone'])} mg/s. At 0.10 mg/s, {fmt(r6(ff['cap_kg'] - dt['m_cathode_kg']))} kg "
      "remain for the tank, feed hardware, starts, transfers, fallback and reserve.")
    a(f"- A Xe-fed discharge burns its allowance fast: 1 kg lasts 277.8 / ṁ[mg/s] hours "
      f"({fmt(h11['hours_of_xe_fed_discharge_per_kg'])} h at the 11 mg/s ignition flow of the HT5k analogue). With "
      f"SC-1 restarts, the SC-1 reserve and no tank or feed hardware (bounding), the longest cumulative fallback inside "
      f"25 % of 34 kg is {fmt(row['t_fallback_max_allowable_h'])} h. That is tens of hours, about three orders of "
      "magnitude below the 15,000 firing hours, so a Xe fallback can never be a sustained mode (consistent with the A5 "
      "rule).")
    a(f"- Restart frequency dominates the non-cathode Xe. Per-orbit restarts ({fmt(sc2['N_starts_derivation']['N_starts'])} "
      f"over 26,000 h at 180 km) with the SC-1 per-cycle Xe need {fmt(sc2['results']['m_Xe_total_kg_scenario'])} kg "
      "of Xe (scenario 10 % reserve included) before any tank or feed hardware. Per-orbit cycling fits only if each start + transfer uses tens of milligrams to a few "
      "tenths of a gram (SS-5), which is a candidate H-1/C-1 test requirement, not a prediction.")
    a("")
    a("## Ledger equations (A6, implemented exactly)")
    a("")
    a("| term | definition |")
    a("|---|---|")
    for k, v in doc["equations"].items():
        a(f"| `{k}` | {v} |")
    a("")
    a("The reserve is always its own term. The tankage fraction applies to the loaded Xe (all five terms). No "
      "default exists for any input: a missing or TBD input makes `evaluate` raise `LedgerIncomplete` and list every "
      "blocker, and a partial evaluation returns `null` for every total it cannot close.")
    a("")
    a("**Accounting convention (explicit input, OD-XE-1):**")
    for k, v in doc["accounting_conventions"].items():
        a(f"- `{k}`: {v}")
    a("")
    a("## The fixed term: cathode Xe (A5)")
    a("")
    a("| case | ṁ (mg/s) | t_firing (h) | m_cathode (kg) | A5 reference (kg) | share of 40 / 36 / 34 kg | status |")
    a("|---|---|---|---|---|---|---|")
    for lab, d in (("design term", dt), ("upper test point", up)):
        sh = " / ".join(pct(s["share"]) for s in d["shares"])
        a(f"| {lab} | {d['mdot_mg_s']} | {fmt(d['t_firing_h'])} | {fmt(d['m_cathode_kg'])} | {d['a5_reference_kg']} | "
          f"{sh} | {d['status']} |")
    rj = c["rejection_illustration"]
    a("")
    a(f"- Arithmetic: {dt['arithmetic']}; {up['arithmetic']}.")
    a(f"- A5 rejection illustration: the flow that consumes 40 kg in 15,000 h is {fmt(rj['flow_consuming_40kg_in_15000h_mg_s'], 4)} "
      f"mg/s (0.74 mg/s gives {fmt(rj['check_0p74_kg'], 4)} kg). This illustrates rejection only.")
    fh = c["firing_hours_sensitivity"]
    a(f"- Firing-hours sensitivity ({fh['label']}): at {fmt(fh['t_firing_h'])} h the term is "
      f"{fmt(fh['m_cathode_kg_at_0p10'])} kg (0.10 mg/s) or {fmt(fh['m_cathode_kg_at_0p15'])} kg (0.15 mg/s).")
    a("")
    a("Context: the cathode flows of other cathodes over 15,000 h (AN-01, level 3). These are never a Vyovrinda "
      "value. The veto layer carries them as RI-MASS-CATHODE-XE, which straddles the limit and is not verdict-bearing.")
    a("")
    a("| flow | ṁ (mg/s) | m over 15,000 h (kg) | share of 40 / 36 / 34 kg |")
    a("|---|---|---|---|")
    for r in c["cathode_flow_context"]["rows"]:
        a(f"| {r['flow_name']} | {r['mdot_mg_s']} | {fmt(r['m_cathode_kg_15000h'])} | "
          f"{' / '.join(pct(s['share']) for s in r['shares'])} |")
    a("")
    a("Cathode flow that alone fills a share of a reference over 15,000 h:")
    a("")
    a("| reference | share | cap (kg) | ṁ (mg/s) |")
    a("|---|---|---|---|")
    for r in c["flow_consuming_share_alone"]["rows"]:
        a(f"| {r['reference']} | {r['share']} | {fmt(r['cap_kg'])} | {fmt(r['mdot_mg_s_consuming_cap_alone'], 4)} |")
    a("")
    a("## Parameters")
    a("")
    a("| id | term | unit | status | value (source, evidence class) | what closes it | milestone | analogues |")
    a("|---|---|---|---|---|---|---|---|")
    for p in doc["parameters"]:
        val = f"{fmt(p['value'])} ({p['source']}; {p['evidence_class']})" if "value" in p else "—"
        a(f"| `{p['id']}` | {p['term']} | {p['unit']} | {p['status'].replace('|', '/')} | {val} | "
          f"{p['closes_with']} | "
          f"{p['milestone']} | {', '.join(p['analogues']) or '—'} |")
    a("")
    ls = doc["ledger_state"]
    a("## Ledger state today")
    a("")
    a(f"m_cathode = {fmt(ls['terms_kg']['m_cathode'])} kg. The other terms, m_Xe_total and m_Xe_subsystem are "
      f"**null (refused)**. There are {ls['n_missing']} blocking inputs: {', '.join(f'`{m}`' for m in ls['missing'])}.")
    a("")
    a(ls["subsystem_share_report"])
    a("")
    a("## Scenarios")
    a("")
    a(f"*Label:* {LABEL_SCEN}.")
    a("")
    a("All scenarios use `PHASE_TOTAL_FLOW`, the A5 cathode design term and all three branches. Per-event Xe for "
      "SC-1 to SC-3 is derived below; each row gives its source and evidence class.")
    a("")
    a("| quantity | value | unit | evidence class | source |")
    a("|---|---|---|---|---|")
    for d in doc["scenario_per_event_derivation"]:
        a(f"| {d['quantity']} | {fmt(d['value'], 4)} | {d['unit']} | {d['evidence_class']} | {d['source']} |")
    a("")
    a("| id | name | N_starts | m_cathode | m_startup | m_transition | m_fallback | m_reserve | m_Xe_total (scenario) "
      "| share of 40 / 36 / 34 kg |")
    a("|---|---|---|---|---|---|---|---|---|---|")
    for s in doc["scenarios"]:
        if s["id"] == "SC-3":
            continue
        t = s["results"]["terms_kg"]
        a(f"| {s['id']} | `{s['name']}` | {fmt(s['parameters']['N_starts']['value'])} | {fmt(t['m_cathode'])} | "
          f"{fmt(t['m_startup'])} | {fmt(t['m_transition'])} | {fmt(t['m_fallback'])} | {fmt(t['m_reserve'])} | "
          f"{fmt(s['results']['m_Xe_total_kg_scenario'])} | "
          f"{' / '.join(pct(x['share']) for x in s['results']['propellant_shares'])} |")
    a("")
    for s in doc["scenarios"]:
        a(f"- **{s['id']} `{s['name']}`**: {s['purpose']}")
    a("")
    a("Hardware headroom is the largest tank + regulator + valves + plumbing + mounting/thermal mass that keeps the "
      "subsystem within the share. Hardware masses are TBD, and none is assumed.")
    a("")
    a("| scenario | reference | share | cap (kg) | headroom (kg) | status |")
    a("|---|---|---|---|---|---|")
    for s in doc["scenarios"]:
        if s["id"] == "SC-3":
            continue
        for r in s["results"]["hardware_headroom"]["rows"]:
            a(f"| {s['id']} | {r['reference']} | {r['share']} | {fmt(r['cap_kg'])} | {fmt(r['hardware_headroom_kg'])} "
              f"| {r['status']} |")
    a("")
    a("SC-3 `fallback_limited` gives the longest cumulative Xe fallback at 11 mg/s (E09 analogue), with SC-1 restarts, "
      "the SC-1 reserve and zero non-tank hardware. It is an upper bound for these inputs, never a frozen value.")
    a("")
    a("| reference | share | cap (kg) | f_tank (axis) | status | t_fallback_max allowable (h) | Xe allowance (kg) |")
    a("|---|---|---|---|---|---|---|")
    for r in sc3["results"]["rows"]:
        a(f"| {r['reference']} | {r['share']} | {fmt(r['cap_kg'])} | {r['f_tank_axis']} | {r['status']} | "
          f"{fmt(r['t_fallback_max_allowable_h'])} | {fmt(r['fallback_xe_allowance_kg'])} |")
    a("")
    a(f"{SHARE_AXIS_NOTE[0].upper()}{SHARE_AXIS_NOTE[1:]}.")
    a("")
    a("## Sensitivity surfaces")
    a("")
    for ss in doc["sensitivity_surfaces"]:
        a(f"### {ss['id']}: {ss['title']}")
        a(f"`{ss['formula']}`")
        if ss.get("meaning"):
            a("")
            a(ss["meaning"])
        a("")
        if ss["id"] == "SS-1":
            a("The table below is a subset: no reserve, and the A5 34 kg allocation. All 243 rows are in the JSON.")
            a("")
            a("| share | f_tank | m_hw non-tank (kg) | S_max (kg) | H at 0.10 mg/s (kg) | H at 0.15 mg/s (kg) |")
            a("|---|---|---|---|---|---|")
            for r in ss["rows"]:
                if r["reference"] == "A5_alloc_34kg" and r["f_reserve"] == 0.0:
                    a(f"| {r['share']} | {r['f_tank']} | {fmt(r['m_hw_nontank_kg'])} | {fmt(r['S_max_kg'])} | "
                      f"{fmt(r['H_kg_at_0p10'])} | {fmt(r['H_kg_at_0p15'])} |")
        elif ss["id"] == "SS-2":
            cyc = sorted({r["xe_per_cycle_g"] for r in ss["rows"]})
            a(f"SC-1 per-cycle Xe for reference: {fmt(ss['reference_point']['xe_per_cycle_g_SC1'], 4)} g.")
            a("")
            a("| H (kg) | " + " | ".join(f"{c} g/cycle" for c in cyc) + " |")
            a("|---|" + "---|" * len(cyc))
            for h in sorted({r["H_kg"] for r in ss["rows"]}):
                a(f"| {h} | " + " | ".join(fmt(float(r["N_starts_max"])) for r in ss["rows"] if r["H_kg"] == h) + " |")
        elif ss["id"] == "SS-3":
            fl = sorted({r["mdot_fallback_mg_s"] for r in ss["rows"]})
            a("| H (kg) | " + " | ".join(f"{f} mg/s" for f in fl) + " |")
            a("|---|" + "---|" * len(fl))
            for h in sorted({r["H_kg"] for r in ss["rows"]}):
                a(f"| {h} | " + " | ".join(f"{fmt(r['t_fallback_max_h'])} h" for r in ss["rows"] if r["H_kg"] == h) + " |")
            a("")
            a("Hours of Xe-fed discharge per kg: " + "; ".join(
                f"{r['mdot_fallback_mg_s']} mg/s → {fmt(r['hours_of_xe_fed_discharge_per_kg'])} h" for r in ss["hours_per_kg"]))
        elif ss["id"] == "SS-4":
            a("| ṁ_fallback (mg/s) | fallback hours ≡ 1000 cycles |")
            a("|---|---|")
            for r in ss["rows"]:
                a(f"| {r['mdot_fallback_mg_s']} | {fmt(r['fallback_h_equivalent_to_1000_cycles'])} h |")
        elif ss["id"] == "SS-5":
            ns = sorted({r["N_cycles"] for r in ss["rows"]})
            a("| H (kg) | " + " | ".join(f"N = {fmt(n)}" for n in ns) + " |")
            a("|---|" + "---|" * len(ns))
            for h in sorted({r["H_kg"] for r in ss["rows"]}):
                a(f"| {h} | " + " | ".join(f"{fmt(r['xe_per_cycle_max_g'])} g" for r in ss["rows"] if r["H_kg"] == h) + " |")
        a("")
        if ss.get("axes_label"):
            a(f"*Axes:* {ss['axes_label']}.")
            a("")
    a("## Illustrative analogues (never the allocation)")
    a("")
    for an in doc["illustrative_analogues"]:
        a(f"**{an['id']} — {an['topic']}.** {an['reading']}")
        a("")
        a("| quantity | value | unit | evidence class (level) | source / pointer |")
        a("|---|---|---|---|---|")
        for v in an["values"]:
            val = v.get("value_display") or (v["value"] if not isinstance(v["value"], list)
                                              else " – ".join(fmt(x) for x in v["value"]))
            src = v.get("source", an.get("source", {}).get("url", ""))
            a(f"| {v['name']} | {fmt(val) if not isinstance(val, str) else val} | {v['unit']} | "
              f"{v['evidence_class']} ({v['evidence_level']}) | {src}; `{v['pointer']}` |")
        if "source" in an:
            s = an["source"]
            a("")
            a(f"Source: {s['citation']}, <{s['url']}> ({s['access']}, accessed {s['accessed']}).")
        a("")
    a("## Open owner decisions")
    a("")
    for o in doc["open_owner_decisions"]:
        body = o.get("proposed") or o.get("note")
        a(f"- **{o['id']}** ({o['topic']}): {body}")
    a("")
    a("## A6 `not_authorized`: how it is respected")
    a("")
    for n in doc["a6_not_authorized_compliance"]:
        a(f"- *{n['item']}*: {n['respected_by']}.")
    a("")
    a("## Milestone statement")
    m = doc["milestones"]
    a(f"- **A (supported):** {m['A']}")
    a(f"- **To reach B:** {m['to_B']}")
    a(f"- **To reach C:** {m['to_C']}")
    a("")
    a("## Scope and neutrality")
    a(f"- {doc['architecture_neutrality']}")
    a(f"- {doc['hall_closure_isolation']}")
    a("")
    a("## Reproduction")
    a(f"`python {SCRIPT_REL}` rewrites both files. `--check` exits 1 unless both are reproduced byte for byte. The run "
      "is deterministic, uses the standard library only and takes well under a second. Base commit: "
      f"`{doc['base_commit']}`.")
    a("")
    return "\n".join(L)


def dumps(obj: dict) -> str:
    return json.dumps(obj, indent=1, sort_keys=False, ensure_ascii=False) + "\n"


def main(argv: list) -> int:
    doc = build()
    outs = {REPO / OUT_DIR_REL / JSON_NAME: dumps(doc), REPO / OUT_DIR_REL / MD_NAME: render_md(doc)}
    if "--check" in argv:
        ok = True
        for p, text in outs.items():
            if not p.is_file() or p.read_text() != text:
                print(f"MISMATCH: {p.relative_to(REPO)} is not reproduced by {SCRIPT_REL}")
                ok = False
        print("OK" if ok else "FAILED")
        return 0 if ok else 1
    for p, text in outs.items():
        p.write_text(text)
        print(f"wrote {p.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
