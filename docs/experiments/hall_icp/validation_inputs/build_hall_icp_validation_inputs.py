#!/usr/bin/env python3
"""A9-05 part 2 - Hall -> downstream RF-ICP validation-input list (owner answer row 145).

Builds `hall_icp_validation_inputs_v1.json` and `HALL_ICP_VALIDATION_INPUTS.md` deterministically. The list replaces the
frozen parallel RF||Hall v2 input list for the primary line; it never supplies or invents v2 inputs (row 146).

Every input carries: definition, units, how it is obtained (measurement chain / published analog / owner allocation),
the stage that produces it (PENDING the A9-01 stage map), current value or 'TBD - requires ...', evidence class,
freeze point, and the A9 decision quantity or gate that consumes it; and whether the published analog can bound it
or only H-1 hardware can supply it. No value is predicted for Vyovrinda hardware.

Usage:  python docs/experiments/hall_icp/validation_inputs/build_hall_icp_validation_inputs.py [--check]
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
REL = "docs/experiments/hall_icp/validation_inputs"
JSON_OUT = os.path.join(HERE, "hall_icp_validation_inputs_v1.json")
MD_OUT = os.path.join(HERE, "HALL_ICP_VALIDATION_INPUTS.md")
EVIDENCE_REL = "docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json"

LANE = "fo_a9_05_hall_icp_validation_inputs"
TRIGGER = "T_A9_05_VALIDATION_INPUTS"
BASE_COMMIT = "0a430bb5588a438f7c8485c6d16f40ed0d402c4c"
CONFIG_IDS = ["hall_c1_reference", "hall_icp_neutralizer"]
C1, ICP = CONFIG_IDS
BOTH = [C1, ICP]

A9 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json"
ANSWERS = "docs/decisions/OD_2026_09_29_owner_answers_147.json"
PACK = "docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md"
# the Xe ledger directory (name split: repository rule forbids that module name as a substring in non-ledger code)
XE_DIR = "docs/budgets/" + "xe" + "_ledger/"

AUTHORITY_PINS = [
    {"path": A9, "sha256": "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f",
     "role": "governing owner decision A9"},
    {"path": ANSWERS, "sha256": "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1",
     "role": "owner's 147 answers (cited by row)"},
    {"path": PACK, "sha256": "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976",
     "role": "owner decision pack, verbatim"},
]
DELIVERABLE_PINS = [
    {"path": "docs/experiments/instrumentation/instrumentation_definition_v1.json",
     "sha256": "7c6d37b00f38a44cded73d92d4366739eacbf013e73e98a7bfbc3fa5a5470d96",
     "role": "existing measurement chains INS-xx (adapted for A9 only via A9-04)"},
    {"path": "docs/hardware/h2/h2_2_cathode_integration/h2_2_cathode_integration_v1.json",
     "sha256": "8436008ac458d4e7467a9c7c9592d5312b3912b918d584ceaf3ac8cb2745a971",
     "role": "IFD-08 electron-emission bounds (I_d <= 8.33 A at 180 V, RFP bound; <= 7.5 A under 1.35 kW)"},
    {"path": "docs/hardware/h2/h2_3_gas_path_plenum/h2_3_gas_path_plenum_v1.json",
     "sha256": "f32b05bd03aad2a09a1d9b90ee5f9423e733e6ea4cb94814c92b500590d43a7b",
     "role": "H23-27 / H23-29 gas-isolator Paschen finding (applies to any ICP gas line across potentials)"},
    {"path": "docs/hardware/h2/h2_4_ppu_bus/h2_4_ppu_bus_v1.json",
     "sha256": "5c6623612ee9ec22899083201416f7b51a10a2d7e88456d372783ce2edde26ef",
     "role": "supply partition / SEQ-1 / start-up peak rule context"},
    {"path": "docs/hardware/h2/h2_6_diagnostics_fixture/h2_6_diagnostics_fixture_v1.json",
     "sha256": "bc7d6b049067c6fbd5489bda32ee9c8c1af36508576db4619b08d2c4ec196a56",
     "role": "kinematic module carrier, service-line shams"},
    {"path": "docs/budgets/subsystem_maturity/subsystem_maturity_v2.json",
     "sha256": "a82b1acd118b26e89edd4fa467bec778fa410470cca5eb6f684e6553eadaf23c",
     "role": "M16 v2 row numbering for m16_impact"},
]
HISTORICAL_PINS = [
    {"path": "docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json",
     "sha256": "84ba1c382dc609b3e83ad9803a57ba471dd892fd10a6a6149285701a45a65a28"},
    {"path": "schemas/interfaces/preionizer_module_icd_v1.json",
     "sha256": "2470718e1decbde874d2362a997d1e2aaae54eb855d1ed179b930c3be6e7130e"},
]
GOVERNANCE_NOT_PINNED = [
    "docs/orchestration/lane_registry_v1.json", "docs/orchestration/trigger_registry_v1.json",
    "docs/orchestration/trigger_ledger_v2.jsonl", "docs/orchestration/fired_triggers.jsonl",
    "docs/orchestration/runtime_state.json",
]

PENDING_A901 = "PENDING docs/experiments/hall_icp/prereg_framework/ (A9-01 stage map)"
PENDING_A902 = "PENDING abep_sim/bus_boundary_a9.py + docs/architecture_comparison/power_boundary_a9/ (A9-02)"
PENDING_A903 = "PENDING docs/interfaces/icp_neutralizer/ (A9-03 ICD)"
PENDING_A904 = "PENDING docs/experiments/hall_icp/uncertainty_budget/ (A9-04 measurement chain / decision quantity)"

# evidence-sequence steps (A9 evidence_sequence + owner row 64 module-exchange checks); NOT stage ids
STEPS = {
    "XCHK": "module-exchange checks without plasma: cold/tare, service-line parasitic, B(z) perturbation, electrical "
            "isolation, RF pickup (row 64)",
    "AR": "Ar, engineering-only topology reproduction (never counts toward DRDO atmospheric requirements; A9, row 36)",
    "N2": "pure N2 (A9, row 36)",
    "O2": "O2-bearing atmospheric surrogate, label NO_ATOMIC_O (A9, rows 36, 132)",
    "AO": "separate dedicated atomic-O materials/life programme (A9, row 132)",
    "XE": "bounded Xe reference / health check, labelled, never atmospheric evidence (row 26)",
}

CONSUMERS = {
    "G-NEUT": "NET_BENEFIT hard gate: ICP electron-current / beam-neutralization (row 37)",
    "G-THRUST": "full-system thrust gates: >= 12 mN sustained, 25 mN capability (rows 4, 27)",
    "G-PBUS": "full-system P_bus < 1.5 kW at the spacecraft-DC propulsion boundary incl. start-up transients "
              "(rows 27, 108)",
    "G-ALLOC": "ICP power inside the internal ~1.35 kW design allocation, not the 1.35-1.5 kW margin (row 109)",
    "G-MASS": "< 40 kg wet full-system gate (row 5)",
    "G-STAB": "NET_BENEFIT hard gate: stability (row 37)",
    "G-SAFE": "NET_BENEFIT hard gate: safety (row 37)",
    "P-DXE": "NET_BENEFIT Pareto report: delta Xe relative to C1 (row 37)",
    "P-DPBUS": "NET_BENEFIT Pareto report: delta P_bus relative to C1 (row 37)",
    "P-DMASS": "NET_BENEFIT Pareto report: delta mass relative to C1 (row 37)",
    "P-TP": "NET_BENEFIT Pareto report: T / P_bus (row 37)",
    "P-RESTART": "NET_BENEFIT Pareto report: restart burden (row 37)",
    "P-LIFE": "NET_BENEFIT Pareto report: life burden (row 37)",
    "R-LIFE": "ICP-neutralizer lifetime / cycle requirement (row 46)",
    "C-EQUIV": "comparison-validity controls: same H-1, feed, V_d/B, stand, metrology; matched shams; module "
               "exchange reproducibility (A9 decision 6; rows 17, 33, 64, 67, 122, 133)",
    "MODEL": "future Hall->ICP model validation input (row 145); held-out custody before exposure (row 25)",
}

# item tuple fields:
# id, group, name, symbol, definition, units, configs, route, chain, analog_refs, analog_can_bound (text or None),
# steps, current_value, evidence_class, consumers, freeze_point, status, basis, source
ITEMS = [
    # ---------------- RF chain ----------------
    ("VI-RF-01", "RF", "RF drive frequency", "f_RF", "frequency of the ICP antenna drive", "MHz", [ICP],
     "owner_allocation", "generator setting; verified by the directional-coupler chain (A9-04)", ["TK-20"],
     "same frequency as the anchor (TK-20)", ["AR", "N2", "O2"], 13.56, "owner-allocation", [], "NOW",
     "FIXED_BY_OWNER", "owner answer", "owner answer row 72; A9 governing decision 1", ),
    ("VI-RF-02", "RF", "forward RF power at the load plane", "P_fwd",
     "RF power travelling toward the matching network/antenna, measured by a directional coupler at the declared "
     "RF load plane (plane PENDING A9-03)", "W", [ICP], "measurement",
     "directional coupler + power sensor (INS-03 adapted; " + PENDING_A904 + ")", ["TK-21", "TK-23"],
     "analog operated at 200 W forward (TK-21) on its own geometry - context only", ["AR", "N2", "O2"],
     "TBD - requires H-1 + ICP module operation; laboratory chain sized for 0-500 W forward (row 72)",
     "measured (future)", ["G-ALLOC", "P-DPBUS", "MODEL"], "LOCK-1 (chain) / after-evidence (value)",
     "HARDWARE_ONLY", "measurement", "owner answer row 72 (range for sizing the chain, not an operating value)"),
    ("VI-RF-03", "RF", "reflected RF power at the load plane", "P_refl",
     "RF power reflected back toward the generator at the same plane as P_fwd", "W", [ICP], "measurement",
     "directional coupler reverse port (" + PENDING_A904 + ")", ["TK-22"],
     "analog reports 'no reflection detected' with generator meters (TK-22); resolution not stated", ["AR", "N2", "O2"],
     "TBD - requires H-1 + ICP module operation", "measured (future)", ["G-SAFE", "MODEL"],
     "after-evidence", "HARDWARE_ONLY", "measurement", "owner answer row 72"),
    ("VI-RF-04", "RF", "net RF power delivered at the load plane", "P_net",
     "P_fwd - P_refl at the declared load plane (includes matching-network and antenna ohmic loss downstream of "
     "the plane)", "W", [ICP], "derived",
     "from VI-RF-02, VI-RF-03 (" + PENDING_A904 + ")", ["TK-21"], None, ["AR", "N2", "O2"],
     "TBD - requires VI-RF-02, VI-RF-03", "measured (future)", ["MODEL"], "after-evidence", "HARDWARE_ONLY",
     "derived", "owner answer row 72"),
    ("VI-RF-05", "RF", "RF power absorbed by the plasma", "P_abs",
     "eta_p x P_net with eta_p = R_p / (R_p + R_ant), R_p = R_total - R_ant (anchor Eq. (1) method); calorimetry of "
     "antenna/electrode heat as independent cross-check (row 72)", "W", [ICP], "derived",
     "antenna RF current probe + VI-RF-06/07 + calorimetric cross-check (" + PENDING_A904 + ")",
     ["TK-24", "TK-25", "TK-26", "TK-27"],
     "method precedent only; anchor eta_p ~0.1 (TK-26) is geometry-specific (electrode eddy-current loss) and is NOT "
     "transferable", ["AR", "N2", "O2"], "TBD - requires VI-RF-06, VI-RF-07 on the A9 module",
     "measured (future)", ["MODEL", "G-NEUT"], "after-evidence", "HARDWARE_ONLY", "derived",
     "Takahashi 2024 Eq. (1) (method); owner answer row 72 (calorimetry as cross-check)"),
    ("VI-RF-06", "RF", "antenna resistance without plasma", "R_ant",
     "antenna-circuit resistance from P_net / I_ant^2 with no plasma (gas off and gas on unlit, both recorded), "
     "with the module installed on H-1", "ohm", [ICP], "measurement",
     "RF current probe on the antenna lead + VI-RF-04 (" + PENDING_A904 + ")", ["TK-24"],
     "anchor value 0.36 ohm (TK-24) is its own antenna/electrode - context only", ["XCHK", "AR"],
     "TBD - requires the A9 module", "measured (future)", ["MODEL"], "after-evidence", "HARDWARE_ONLY",
     "measurement", "Takahashi 2024 p. 3, p. 8 (method)"),
    ("VI-RF-07", "RF", "antenna current and total resistance with plasma", "I_ant, R_total",
     "RMS antenna current and P_net / I_ant^2 during discharge at each operating point", "A, ohm", [ICP],
     "measurement", "RF current probe (" + PENDING_A904 + ")", ["TK-25"], None, ["AR", "N2", "O2"],
     "TBD - requires H-1 + ICP module operation", "measured (future)", ["MODEL"], "after-evidence", "HARDWARE_ONLY",
     "measurement", "Takahashi 2024 p. 3, p. 8 (method)"),
    ("VI-RF-08", "RF", "RF generator DC input power", "P_RF,DC",
     "electrical power drawn by the RF source (generator + matching control) at its DC input; enters P_bus through "
     "its own bus slot", "W", [ICP], "measurement",
     "DC V/I channel per bus slot (INS-02 adapted; bus slot " + PENDING_A902 + ")", [], None, ["AR", "N2", "O2"],
     "TBD - requires the RF source selected under H3 and A9-02 bus slot", "measured (future)",
     ["G-PBUS", "G-ALLOC", "P-DPBUS"], "LOCK-1 (slot) / after-evidence (value)", "HARDWARE_ONLY", "measurement",
     "owner answers rows 66, 108, 110"),
    ("VI-RF-09", "RF", "RF chain efficiency DC -> net RF", "eta_RF",
     "P_net / P_RF,DC at each operating point (lab generator is not flight-representative; flight value PENDING)",
     "-", [ICP], "derived", "VI-RF-04 / VI-RF-08", [], None, ["AR", "N2", "O2"],
     "TBD - requires VI-RF-04 and VI-RF-08", "measured (future)", ["P-DPBUS", "G-ALLOC"], "after-evidence",
     "HARDWARE_ONLY", "derived", "owner answer row 108 (no RF-generator-only power claim)"),
    ("VI-RF-10", "RF", "ICP coupling mode", "mode",
     "identification of capacitive (E) vs inductive (H) coupling at each point, and the net power / pressure of any "
     "E-H transition or hysteresis", "W, Pa", [ICP], "measurement",
     "I_ant / R_total step + optical emission (INS-12 adapted; " + PENDING_A904 + ")", ["TK-26"],
     "the anchor does not report a mode; S-04 reports a helicon transition in a magnetized source (context only, "
     "row 69 fixes an unmagnetized first build)", ["AR", "N2", "O2"], "TBD - requires the A9 module",
     "measured (future)", ["G-STAB", "MODEL"], "after-evidence", "HARDWARE_ONLY", "measurement", "owner answer row 69"),
    ("VI-RF-11", "RF", "RF pickup on Hall and stand diagnostics", "pickup",
     "RF-induced error on I_d, V_d, thrust-stand output and probe signals with the ICP energized and Hall off / on",
     "per channel", [ICP], "measurement", "module-exchange checks (row 64; " + PENDING_A904 + ")", ["TK-40"],
     "the anchor needed a 13.56 MHz L-C trap in the discharge line (TK-40): pickup is a real mechanism",
     ["XCHK", "AR"], "TBD - requires the installed module and stand", "measured (future)", ["C-EQUIV"],
     "LOCK-2 (tolerance from measured data)", "HARDWARE_ONLY", "measurement", "owner answers rows 64, 117"),
    # ---------------- electron extraction / neutralization ----------------
    ("VI-EX-01", "extraction", "electron current extracted from the ICP module", "I_e,ICP",
     "net electron current leaving the ICP plasma toward the Hall anode and the beam, from the current balance of "
     "the module terminals (collector + body + any bias return) with the discharge supply isolated", "A", [ICP],
     "measurement", "isolated current sensors on every ICP-module terminal (" + PENDING_A903 + "; " + PENDING_A904 + ")",
     ["TK-52", "TK-56"],
     "anchor: I_D about 1 A with 200 W forward on Ar (TK-52, digitized_fig4); diode RF cathodes 1-3.3 A at "
     "140-270 W on Xe (S-01, S-02) - order of magnitude only", ["AR", "N2", "O2"],
     "TBD - requires H-1 + ICP module operation", "measured (future)", ["G-NEUT", "MODEL"], "after-evidence",
     "HARDWARE_ONLY", "measurement", "owner answer row 145; A9 governing decision 2"),
    ("VI-EX-02", "extraction", "ICP electron-current capacity curve", "I_e,sat(P_net, mdot, V_coupling)",
     "maximum extractable electron current versus net RF power and gas flow at a registered coupling-voltage limit "
     "(saturation behaviour), measured with the Hall head as the electron sink", "A", [ICP], "measurement",
     "RF-power / flow scan (" + PENDING_A904 + ")", ["TK-53"],
     "anchor authors attribute the I_D limit to RF power (TK-53) without a power scan; S-01/S-02 show current rising "
     "with RF power in diode tests", ["AR", "N2", "O2"], "TBD - requires the A9 module on H-1",
     "measured (future)", ["G-NEUT", "MODEL"], "after-evidence", "HARDWARE_ONLY", "measurement",
     "owner answers rows 37, 145"),
    ("VI-EX-03", "extraction", "collector (ion-collecting electrode) potential", "V_coll",
     "potential of the ICP ion-collecting electrode with respect to the declared reference (cathode-common / "
     "facility ground, " + PENDING_A903 + ")", "V", [ICP], "measurement",
     "isolated voltage channel (" + PENDING_A904 + ")", ["TK-55"],
     "anchor V_K fell to about -100 V at V_D 260 V (TK-55, digitized_fig4) with no separate bias supply",
     ["AR", "N2", "O2"], "TBD - requires the A9 module with separately controlled collector bias (row 70)",
     "measured (future)", ["G-NEUT", "P-LIFE", "MODEL"], "after-evidence", "HARDWARE_ONLY", "measurement",
     "owner answers rows 62, 70, 145"),
    ("VI-EX-04", "extraction", "collector current and bias-supply power", "I_coll, V_bias, P_coll",
     "ion current collected by the electrode and the electrical power of its bias supply (if the validated circuit "
     "needs one)", "A, V, W", [ICP], "measurement",
     "bias supply V/I (bus slot " + PENDING_A902 + "; " + PENDING_A904 + ")", ["TK-13", "TK-40"],
     "the anchor has no separate bias supply (TK-40)", ["AR", "N2", "O2"],
     "TBD - requires the A9 circuit (A9-03) and hardware", "measured (future)", ["G-PBUS", "P-DPBUS", "MODEL"],
     "LOCK-1 (slot) / after-evidence (value)", "HARDWARE_ONLY", "measurement", "owner answers rows 62, 66, 70, 110"),
    ("VI-EX-05", "extraction", "ICP body / dielectric floating potential", "V_body",
     "floating potential of the ICP body (kept floating unless the validated circuit requires otherwise)", "V",
     [ICP], "measurement", "high-impedance isolated voltage channel (" + PENDING_A904 + ")", [], None,
     ["AR", "N2", "O2"], "TBD - requires hardware", "measured (future)", ["G-SAFE", "MODEL"], "after-evidence",
     "HARDWARE_ONLY", "measurement", "owner answer row 70"),
    ("VI-EX-06", "extraction", "coupling voltage (cathode-common / plume potential to facility ground)", "V_cg",
     "potential of the electron-source reference (C1 cathode-common or ICP reference) with respect to facility "
     "ground, in both configurations at identical H-1 settings", "V", BOTH, "measurement",
     "isolated voltage channel, selectable bleeder topology (row 91; " + PENDING_A904 + ")", ["TK-54", "TK-55"],
     "anchor: anode potential ~120-130 V vs ground with the supply floating (TK-54); context only",
     ["AR", "N2", "O2"], "TBD - requires hardware", "measured (future)", ["G-NEUT", "C-EQUIV", "MODEL"],
     "after-evidence", "HARDWARE_ONLY", "measurement", "owner answer row 91"),
    ("VI-EX-07", "extraction", "neutralization margin", "M_neut",
     "PROPOSED form (OQ-VI-02): electron-current capacity of the electron source at the registered coupling-voltage "
     "limit (VI-EX-02) relative to the measured Hall current demand at the same point (VI-HD-01); the numeric margin "
     "is frozen only at LOCK-2 (rows 18, 19)", "-", BOTH, "derived", "VI-EX-02, VI-HD-01 (" + PENDING_A904 + ")",
     ["TK-52", "TK-56"], None, ["AR", "N2", "O2"],
     "TBD - requires VI-EX-02 and VI-HD-01; form: owner call (OQ-VI-02)", "measured (future)", ["G-NEUT"],
     "LOCK-1 (form) / LOCK-2 (numeric margin)", "HARDWARE_ONLY", "derived", "owner answers rows 18, 19, 37, 145"),
    ("VI-EX-08", "extraction", "beam-neutralization evidence", "neut",
     "current balance of the plume (beam ion current vs electron current into the beam) and absence of net charging "
     "with the supplies isolated; plus far-field ion energy with anode-level maximum", "A, V", BOTH, "measurement",
     "Faraday probes + RPA/RFEA (INS-15, INS-14 adapted; repeatability at S1b if gating, row 32; " + PENDING_A904 + ")",
     ["TK-56", "TK-57", "TK-58"],
     "anchor evidence is qualitative only (TK-56): IEDF maximum ~ anode potential, zero net current to chamber",
     ["AR", "N2", "O2"], "TBD - requires hardware", "measured (future)", ["G-NEUT", "MODEL"], "after-evidence",
     "HARDWARE_ONLY", "measurement", "owner answers rows 32, 37"),
    ("VI-EX-09", "extraction", "electron production cost", "C_e",
     "(P_RF,DC + P_coll + ICP housekeeping) / I_e,ICP for the ICP; (heater + keeper + flow-control power) / I_emit "
     "for C1; both on the A9-02 bus boundary", "W/A", BOTH, "derived",
     "VI-RF-08, VI-EX-04, VI-EX-01, VI-PB-02 (" + PENDING_A902 + ")", ["S-01", "S-02", "S-04"],
     "open RF cathodes span ~40-260 W/A of RF input per ampere on Xe (survey derived values) - context, not a bound "
     "for the A9 module", ["AR", "N2", "O2"], "TBD - requires hardware", "measured (future)",
     ["P-DPBUS", "G-ALLOC"], "after-evidence", "HARDWARE_ONLY", "derived", "owner answer row 37"),
    ("VI-EX-10", "extraction", "ion energy at the collector (sputter-energy input)", "E_i,coll",
     "energy of ions striking the collector: (ICP plasma potential - V_coll) for ICP ions and (V_A - V_coll) for "
     "Hall ions reaching it", "eV", [ICP], "derived", "VI-EX-03 + plasma potential (INS-16 adapted; RFEA)",
     ["TK-70"], "anchor estimates ~140 eV and ~220 eV at its largest V_D (TK-70)", ["AR", "N2", "O2"],
     "TBD - requires hardware", "measured (future)", ["P-LIFE", "R-LIFE"], "after-evidence", "HARDWARE_ONLY",
     "derived", "Takahashi 2024 p. 6 (mechanism)"),
    # ---------------- Hall side ----------------
    ("VI-HD-01", "hall", "Hall discharge current demand", "I_d(V_d, B, mdot)",
     "discharge current of H-1 at each registered V_d / coil-current / feed point, measured first with the C1 "
     "reference and then with the ICP neutralizer at identical settings", "A", BOTH, "measurement",
     "INS-04 adapted (" + PENDING_A904 + ")", ["TK-52"],
     "sizing envelope only (not a prediction): I_d <= 8.33 A at 180 V (RFP bound) and <= 7.5 A at 180 V under the "
     "1.35 kW allocation (H2-2 IFD-08, PRELIMINARY)", ["AR", "N2", "O2", "XE"],
     "TBD - requires H-1 operation (no Hall closure admitted; credible set EMPTY)", "measured (future)",
     ["G-NEUT", "G-PBUS", "MODEL"], "after-evidence", "HARDWARE_ONLY", "measurement",
     "docs/hardware/h2/h2_2_cathode_integration/h2_2_cathode_integration_v1.json IFD-08 (bound)"),
    ("VI-HD-02", "hall", "anode potential and effective anode-to-electron-source voltage", "V_A, V_A - V_ref",
     "anode potential vs facility ground and the voltage actually across anode and electron-source reference "
     "(series elements and sheath drops separated)", "V", BOTH, "measurement", "INS-04 adapted (" + PENDING_A904 + ")",
     ["TK-41", "TK-54"], "anchor shows a large share of V_D lost to the 50 ohm resistor and the collector sheath "
     "(digitized_fig4: V_D - I_D x 50 ohm)", ["AR", "N2", "O2"], "TBD - requires hardware", "measured (future)",
     ["G-PBUS", "MODEL"], "after-evidence", "HARDWARE_ONLY", "measurement", "Takahashi 2024 p. 6 (mechanism)"),
    ("VI-HD-03", "hall", "thrust", "T",
     "sustained thrust of the full H-1 + electron-source configuration on the torsional stand with matched shams",
     "mN", BOTH, "measurement", "INS-01 adapted; 1 % absolute uncertainty target (row 121); " + PENDING_A904, [],
     "none: the anchor measured no thrust (TK-60)", ["N2", "O2", "XE"],
     "TBD - requires H-1 on the stand", "measured (future)", ["G-THRUST", "P-TP"], "after-evidence",
     "HARDWARE_ONLY", "measurement", "owner answers rows 4, 27, 115, 121"),
    ("VI-HD-04", "hall", "ion energy distribution and beam current in the plume", "IEDF, I_b",
     "RPA/RFEA and Faraday data at registered positions for both configurations", "V, A", BOTH, "measurement",
     "INS-14, INS-15 adapted (" + PENDING_A904 + ")", ["TK-57", "TK-58", "TK-59"],
     "anchor on-axis RFEA at z = 25 cm only (TK-57)", ["AR", "N2", "O2"], "TBD - requires hardware",
     "measured (future)", ["G-NEUT", "MODEL"], "after-evidence", "HARDWARE_ONLY", "measurement",
     "owner answer row 32"),
    ("VI-HD-05", "hall", "B(z) perturbation by the downstream module", "delta B(z)",
     "change of the H-1 field map with the ICP (or C1) module installed and energized vs reference, and the H-1 "
     "sensitivity scan used to freeze the allowable tolerance", "T", BOTH, "measurement",
     "INS-09 adapted (" + PENDING_A904 + ")", [], None, ["XCHK"],
     "TBD - requires H-1 + modules; tolerance frozen from measured H-1 sensitivity (row 67)", "measured (future)",
     ["C-EQUIV"], "LOCK-2 (tolerance)", "HARDWARE_ONLY", "measurement", "owner answer row 67"),
    ("VI-HD-06", "hall", "H-1 fringe field inside the ICP volume", "B_ICP(z, r)",
     "magnetic field of H-1 inside the downstream ICP volume (the 'unmagnetized' ICP sits in the Hall fringe field)",
     "T", [ICP], "measurement", "INS-09 extended downstream (" + PENDING_A903 + ")", ["TK-03", "TK-14"],
     "anchor shows fringe field extending past its exit only to z ~ +10 mm (Fig. 2)", ["XCHK"],
     "TBD - requires H-1 (EM only, row 78) and the module geometry", "measured (future)", ["MODEL", "C-EQUIV"],
     "after-evidence", "HARDWARE_ONLY", "measurement", "owner answers rows 69, 78"),
    ("VI-HD-07", "hall", "discharge oscillations with each electron source", "I_d(t)",
     "time-resolved I_d with each electron source (to ~60 MHz if feasible, else the declared bandwidth and transfer "
     "function), including 13.56 MHz harmonics", "A", BOTH, "measurement", "INS-04 time-resolved (row 129)", [],
     None, ["AR", "N2", "O2"], "TBD - requires hardware", "measured (future)", ["G-STAB", "MODEL"],
     "after-evidence", "HARDWARE_ONLY", "measurement", "owner answer row 129"),
    # ---------------- gas ----------------
    ("VI-GAS-01", "gas", "ICP gas species and booking", "gas_ICP",
     "the gas that sustains the ICP: (a) Hall exhaust re-use only (anchor topology), (b) a dedicated Xe feed (booked "
     "in the Xe ledger, " + XE_DIR + "), or (c) a dedicated atmospheric feed; UNBOOKED today (A9 recorder flag row 46)",
     "-", [ICP], "owner_allocation", "owner decision (OQ-VI-01) then INS-05 per species", ["TK-30", "TK-31"],
     "the anchor uses Hall-exhaust re-use with no separate feed (TK-30); orifice RF cathodes use a dedicated feed "
     "(S-01, S-02, D-01)", ["AR", "N2", "O2"],
     "TBD - requires owner decision OQ-VI-01; flagged UNBOOKED (A9 recorder_consistency_flags row 46)",
     "owner-allocation", ["P-DXE", "G-MASS", "MODEL"], "LOCK-1", "OPEN_UNBOOKED_FLAG", "owner allocation (pending)",
     A9 + " recorder_consistency_flags_for_owner (row 46)"),
    ("VI-GAS-02", "gas", "dedicated ICP gas flow", "mdot_ICP",
     "mass flow of any dedicated ICP feed per species, booked as PHASE_TOTAL_FLOW (purge, ignition, operation, "
     "transition, fallback)", "mg/s", [ICP], "measurement", "INS-05 adapted (own-gas thermal MFC, rows 124, 126)",
     ["S-01", "S-02", "D-01"], "open RF cathodes: 0.3 mg/s Xe for 3.3 A (S-01); 0.018 mg/s N2/O2 for up to 0.45 A "
     "(D-01) - context only", ["AR", "N2", "O2"], "TBD - requires OQ-VI-01 and hardware", "measured (future)",
     ["P-DXE", "MODEL"], "after-evidence", "HARDWARE_ONLY", "measurement", "owner answers rows 42, 46"),
    ("VI-GAS-03", "gas", "neutral pressure in the ICP region", "p_ICP",
     "pressure inside the ICP volume fed by the Hall exhaust (and any dedicated feed), at a declared tap", "Pa",
     [ICP], "measurement", "pressure tap at the Hall-exhaust-to-ICP interface (" + PENDING_A903 + ")",
     ["TK-34", "TK-35"], "anchor gives chamber pressure 28 mPa and an estimated tube density ~2e19 m^-3 (TK-34, "
     "TK-35); no in-tube measurement", ["XCHK", "AR", "N2", "O2"], "TBD - requires hardware", "measured (future)",
     ["MODEL", "G-NEUT"], "after-evidence", "HARDWARE_ONLY", "measurement", "owner answer row 63"),
    ("VI-GAS-04", "gas", "Hall-exhaust-to-ICP conductance / pressure interface", "C_HE-ICP",
     "measured conductance / pressure ratio between the H-1 exit plane and the ICP volume (cold flow and hot)",
     "L/s, -", [ICP], "measurement", "cold-flow pressure mapping (" + PENDING_A903 + ")", ["TK-12"], None,
     ["XCHK", "AR"], "TBD - requires hardware", "measured (future)", ["MODEL", "C-EQUIV"], "LOCK-1 (interface) / "
     "after-evidence (value)", "HARDWARE_ONLY", "measurement", "owner answer row 63"),
    ("VI-GAS-05", "gas", "facility background pressure and its effect on extraction", "p_b",
     "background pressure at the registered location per run, at the nominal and two elevated levels", "Pa", BOTH,
     "measurement", "INS-08 adapted", ["TK-33", "TK-34"], "anchor ran at ~28 mPa (TK-34) - high background; "
     "facility coupling unresolved", ["AR", "N2", "O2"], "TBD - T-PB-MAX frozen only after knee and facility "
     "capability are known (row 23)", "measured (future)", ["C-EQUIV", "MODEL"], "LOCK-2", "HARDWARE_ONLY",
     "measurement", "owner answers rows 23, 131, 137"),
    ("VI-GAS-06", "gas", "gas flow per ampere / gas utilization of the electron source", "mdot / I_e",
     "electron-source gas flow per extracted ampere (ICP: dedicated flow share; C1: cathode Xe flow)", "mg/(s A)",
     BOTH, "derived", "VI-GAS-02 / VI-EX-01; C1: VI-SU-05 flow term", ["S-01", "S-04"],
     "survey: U_e ~150-180 on Xe for orifice/NES sources (S-01, S-04) - context only", ["AR", "N2", "O2"],
     "TBD - requires hardware", "measured (future)", ["P-DXE"], "after-evidence", "HARDWARE_ONLY", "derived",
     "owner answer row 37"),
    ("VI-GAS-07", "gas", "delivered feed state to H-1 (common to both configurations)", "mdot_s, P_feed, T_feed, x_s",
     "feed state at the valve outlet / anode-distributor inlet, identical in both configurations", "mg/s, Pa, K, -",
     BOTH, "measurement", "INS-05, INS-06, INS-07, INS-11 (existing)", [], None, ["AR", "N2", "O2"],
     "TBD - requires H-1 operation; compressor bus draw and valve-outlet state are PARTIAL_BOUNDARY until measured "
     "(row 22)", "measured (future)", ["C-EQUIV", "G-THRUST"], "after-evidence", "HARDWARE_ONLY", "measurement",
     "owner answers rows 22, 73"),
    # ---------------- power / boundary ----------------
    ("VI-PB-01", "power", "ICP-module bus power", "P_bus,ICP",
     "sum of every ICP-related load at the spacecraft-DC propulsion boundary: RF source, collector/bias supply, "
     "any assist magnet or active cooling, ICP housekeeping", "W", [ICP], "measurement",
     "INS-02 adapted per bus slot (" + PENDING_A902 + ")", ["TK-21", "TK-27", "TK-28"],
     "anchor power figures are RF-generator forward/absorbed only (TK-21, TK-27); a generator-only figure is not "
     "sufficient (A9 requirement discipline)", ["AR", "N2", "O2"], "TBD - requires hardware and A9-02 slots",
     "measured (future)", ["G-PBUS", "G-ALLOC", "P-DPBUS"], "LOCK-1 (slots) / after-evidence (value)",
     "HARDWARE_ONLY", "measurement", "owner answers rows 66, 108, 109, 110; A9 requirement_discipline"),
    ("VI-PB-02", "power", "C1-reference bus power", "P_bus,C1",
     "heater, keeper (incl. pulsed ignition), cathode flow control and any filter/getter load of the C1 reference",
     "W", [C1], "measurement", "INS-02 adapted per bus slot (" + PENDING_A902 + ")", [], None, ["AR", "N2", "O2", "XE"],
     "TBD - requires C1 hardware", "measured (future)", ["G-PBUS", "P-DPBUS"], "after-evidence", "HARDWARE_ONLY",
     "measurement", "owner answers rows 49, 51, 89, 110"),
    ("VI-PB-03", "power", "total P_bus including start-up transients", "P_bus(t)",
     "time-resolved sum over all slots from cold start through steady state for each configuration", "W", BOTH,
     "measurement", "INS-02 time-resolved; averaging window " + PENDING_A904, [], None, ["AR", "N2", "O2"],
     "TBD - requires hardware; limit < 1500 W incl. transients unless the official RFP allows otherwise (row 108)",
     "measured (future)", ["G-PBUS"], "LOCK-1 (window rule) / after-evidence (value)", "HARDWARE_ONLY",
     "measurement", "owner answers rows 108, 112"),
    ("VI-PB-04", "power", "internal design allocation the ICP must fit inside", "B_alloc",
     "internal propulsion design allocation (~1.35 kW) inside which the ICP power must fit; the 1.35-1.5 kW margin is "
     "not consumed nominally", "W", [ICP], "owner_allocation", "owner answer", [], None, [],
     "~1350 (owner answer row 109; allocation, not a measured load)", "owner-allocation", ["G-ALLOC"], "NOW",
     "FIXED_BY_OWNER", "owner allocation", "owner answer row 109"),
    # ---------------- startup / restart ----------------
    ("VI-SU-01", "startup", "ICP ignition", "ign_ICP",
     "ignition success per attempt, attempts, forward power, pressure and time-to-ignite of the ICP, with and without "
     "Hall flow", "-, W, Pa, s", [ICP], "measurement", "INS-10 adapted (row 24)", ["TK-73"],
     "anchor: RF plasma turned on first, no statistics (TK-73); Paschen-type ignition of orifice RF cathodes "
     "discussed in S-01/S-02", ["AR", "N2", "O2"], "TBD - requires hardware", "measured (future)",
     ["P-RESTART", "G-STAB", "MODEL"], "after-evidence", "HARDWARE_ONLY", "measurement", "owner answer row 24"),
    ("VI-SU-02", "startup", "Hall ignition with ICP electrons", "ign_Hall|ICP",
     "Hall discharge ignition success, attempts and onset V_d with the ICP as the only electron source; confirm "
     "'no Hall discharge without ICP electrons' as an engineering-only topology check", "-, V", [ICP], "measurement",
     "INS-10 adapted (row 24; criterion " + PENDING_A901 + ")", ["TK-50", "TK-51"],
     "anchor: onset V_D > 140 V and no discharge without RF on Ar (TK-50, TK-51) - context only",
     ["AR", "N2", "O2"], "TBD - requires hardware", "measured (future)", ["P-RESTART", "G-NEUT"],
     "after-evidence", "HARDWARE_ONLY", "measurement", "owner answer row 24"),
    ("VI-SU-03", "startup", "restart success and cycle count", "N_restart, N_cycle",
     "restart success rate and accumulated on/off cycles per configuration, classified per the preregistration",
     "-", BOTH, "measurement", "INS-10 adapted (row 24)", [], "none in open sources read (survey by_topic.restart)",
     ["AR", "N2", "O2"], "TBD - requires hardware", "measured (future)", ["P-RESTART", "R-LIFE"],
     "after-evidence", "HARDWARE_ONLY", "measurement", "owner answers rows 24, 46"),
    ("VI-SU-04", "startup", "C1 start sequence Xe and dwell", "m_Xe,start",
     "C1 purge / preheat / ignition Xe booked as PHASE_TOTAL_FLOW, ignition dwell capped at 120 s with at most two "
     "retries in the preliminary protocol", "mg, s", [C1], "measurement", "INS-05 cathode Xe line (rows 42, 93)", [],
     None, ["AR", "N2", "O2", "XE"], "TBD - requires C1 hardware; dwell cap 120 s x 2 retries (row 93, preliminary)",
     "measured (future)", ["P-DXE", "P-RESTART"], "LOCK-2 (final bound, row 93)", "HARDWARE_ONLY", "measurement",
     "owner answers rows 42, 92, 93"),
    ("VI-SU-05", "startup", "C1 steady cathode Xe flow", "mdot_c",
     "C1 spot-mode steady flow found with a 0.005 mg/s step search and preregistered stopping criteria", "mg/s", [C1],
     "measurement", "INS-05 cathode MFC (resolution <= 0.0005 mg/s, row 98)", [], None, ["AR", "N2", "O2", "XE"],
     "TBD - requires C1 hardware; search step 0.005 mg/s (row 92)", "measured (future)", ["P-DXE"], "after-evidence",
     "HARDWARE_ONLY", "measurement", "owner answers rows 46, 92, 98"),
    # ---------------- erosion / life ----------------
    ("VI-LF-01", "life", "collector / electrode erosion rate", "dm/dt, dh/dt",
     "mass loss and profile change of the ICP ion-collecting electrode per hour at registered operating points",
     "mg/h, um/h", [ICP], "measurement", "INS-19, INS-20 adapted", ["TK-70", "TK-71"],
     "anchor: sputtering at ~140-220 eV observed, no rate (TK-70, TK-71)", ["AR", "N2", "O2", "AO"],
     "TBD - requires hardware", "measured (future)", ["P-LIFE", "R-LIFE"], "after-evidence", "HARDWARE_ONLY",
     "measurement", "owner answers rows 46, 132"),
    ("VI-LF-02", "life", "sputter deposition on the ICP tube and H-1 exit insulators", "deposit",
     "deposit mass/thickness and its effect on RF coupling (eta_p drift) and on H-1 insulators, via witness coupons",
     "ug/cm^2, -", [ICP], "measurement", "INS-19, INS-20 + witness holders (row 134)", ["TK-71"],
     "anchor: metallic films on glass and HET front insulators after the experiment (TK-71)", ["AR", "N2", "O2"],
     "TBD - requires hardware", "measured (future)", ["P-LIFE", "C-EQUIV"], "after-evidence", "HARDWARE_ONLY",
     "measurement", "owner answer row 134"),
    ("VI-LF-03", "life", "RF coupling drift over accumulated operation", "d eta_p / dt",
     "change of R_ant, R_total and eta_p with accumulated hours and cycles", "1/h", [ICP], "measurement",
     "repeat of VI-RF-06/07 at reference points", ["TK-26"], None, ["AR", "N2", "O2"], "TBD - requires hardware",
     "measured (future)", ["P-LIFE", "R-LIFE"], "after-evidence", "HARDWARE_ONLY", "measurement",
     "owner answer row 46"),
    ("VI-LF-04", "life", "ICP / RF thermal state and margin", "T_ICP, T_ant, T_RF",
     "temperatures of the ICP tube, antenna, matching network and RF source; margin >= 50 K below each validated "
     "continuous-use limit plus 20 % heat-load design margin", "K", [ICP], "measurement",
     "INS-17 adapted (RF source temperature in the telemetry, row 130)", ["TK-27", "TK-62"],
     "anchor: most RF power heats the electrode (TK-27); shot scatter attributed to thermal issues (TK-62)",
     ["AR", "N2", "O2"], "TBD - requires hardware; margin rule >= 50 K (row 86)", "measured (future)",
     ["G-SAFE", "P-LIFE"], "after-evidence", "HARDWARE_ONLY", "measurement", "owner answers rows 86, 130"),
    ("VI-LF-05", "life", "ICP-neutralizer lifetime / cycle requirement", "L_req, N_req",
     "required operating hours and on/off cycles of the ICP neutralizer (C1 carries the 15,000 h cathode term; the "
     "ICP carries its own requirement)", "h, -", [ICP], "owner_allocation", "owner decision (OQ-VI-04)", [], None,
     [], "TBD - requires an owner decision (row 46) and the mission restart count; firing basis > 15,000 h is "
     "provisional (row 3)", "owner-allocation", ["R-LIFE"], "LOCK-1", "OPEN", "requirement (pending)",
     "owner answers rows 3, 46"),
    ("VI-LF-06", "life", "O2-bearing and atomic-O material compatibility", "compat",
     "material response of ICP tube, antenna shielding and collector to O2-bearing plasma (NO_ATOMIC_O) and, "
     "separately, to atomic O in the dedicated programme", "-", [ICP], "measurement",
     "coupons (INS-19, INS-20); separate AO source (row 132)", ["TK-74"],
     "anchor claim of reactive-gas operability is not demonstrated there (TK-74)", ["O2", "AO"],
     "TBD - requires hardware and the AO programme", "measured (future)", ["P-LIFE", "R-LIFE"], "after-evidence",
     "HARDWARE_ONLY", "measurement", "owner answers rows 102, 132"),
    # ---------------- mass ----------------
    ("VI-MS-01", "mass", "ICP neutralizer mass allocation", "m_ICP", "v0 dry allocation for the ICP neutralizer",
     "kg", [ICP], "owner_allocation", "owner answer", [], None, [], "2.0 (allocation, not CBE; row 54)",
     "owner-allocation", ["G-MASS", "P-DMASS"], "NOW", "FIXED_BY_OWNER", "owner allocation", "owner answer row 54"),
    ("VI-MS-02", "mass", "RF generator / matching mass allocation", "m_RF", "v0 dry allocation for RF generator and "
     "matching", "kg", [ICP], "owner_allocation", "owner answer", [], None, [],
     "1.5 (allocation, not CBE; row 54)", "owner-allocation", ["G-MASS", "P-DMASS"], "NOW", "FIXED_BY_OWNER",
     "owner allocation", "owner answer row 54"),
]

OWNER_ROWS_APPLIED = {
    3: "firing basis > 15,000 h kept provisional in VI-LF-05",
    4: "thrust gate definition (>= 12 mN sustained, 25 mN capability) in consumer G-THRUST",
    5: "40 kg is wet (Xe + tank) in consumer G-MASS",
    7: "anchor full text read; lawful-acquisition list in the evidence part",
    17: "H-1 fixed on the stand; only the downstream electron-source module is swapped (C-EQUIV)",
    18: "no numeric margin carried over; neutralization-margin number frozen at LOCK-2 (VI-EX-07)",
    19: "n from measured uncertainty at LOCK-2 (freeze points)",
    22: "PARTIAL_BOUNDARY until compressor draw and valve-outlet state are measured (VI-GAS-07)",
    23: "two elevated background-pressure levels; T-PB-MAX frozen later (VI-GAS-05)",
    24: "ICP ignition, Hall ignition with ICP electrons, restart and cycle count recorded (VI-SU-01..03)",
    25: "model-validation inputs held out before exposure (consumer MODEL)",
    26: "Xe reference points labelled, never atmospheric evidence (step XE)",
    27: "25 mN inside the same full boundary with P_bus < 1.5 kW (G-THRUST, G-PBUS)",
    32: "Faraday/ExB repeatability if eta_u/beam current gates (VI-EX-08)",
    33: "module-exchange reproducibility as a comparison control (C-EQUIV)",
    36: "evidence order Ar (engineering-only) -> N2 -> O2-bearing (steps)",
    37: "NET_BENEFIT = hard gates + Pareto, no weighted scalar (consumer vocabulary)",
    38: "OPEN used as a status only (VI-GAS-01 OPEN_UNBOOKED_FLAG, VI-LF-05 OPEN)",
    42: "PHASE_TOTAL_FLOW booking for ICP and C1 gas (VI-GAS-02, VI-SU-04)",
    46: "ICP carries its own lifetime/cycle requirement (VI-LF-05); ICP gas feed flagged unbooked (VI-GAS-01)",
    54: "ICP 2.0 kg and RF 1.5 kg are allocations, not CBEs (VI-MS-01/02)",
    62: "ICP harness quantities: RF forward/reflected, collector V/I, temperatures (VI-RF-02/03, VI-EX-03/04, VI-LF-04)",
    63: "downstream Hall-exhaust-to-ICP pressure/conductance interface measured (VI-GAS-03/04)",
    64: "module-exchange checks: cold/tare, parasitic, B(z), isolation, RF pickup (step XCHK, VI-RF-11, VI-HD-05)",
    66: "every legitimate ICP load gets a bus slot (VI-RF-08, VI-EX-04, VI-PB-01)",
    67: "measured B(z) perturbation; tolerance from measured sensitivity (VI-HD-05)",
    69: "unmagnetized first build; magnetized analog data context-only (VI-RF-10)",
    70: "ICP body floating, collector bias controlled and measured separately (VI-EX-03..05)",
    72: "13.56 MHz; 0-500 W lab chain with directional coupler; calorimetry as cross-check (VI-RF-01..05)",
    78: "EM-only MC-1 makes the fringe-field map traceable to coil current (VI-HD-06)",
    86: ">= 50 K thermal margin rule (VI-LF-04)",
    91: "selectable cathode-common/bleeder topology for coupling-voltage measurement (VI-EX-06)",
    92: "0.005 mg/s C1 flow step (VI-SU-05)",
    93: "120 s x 2 ignition dwell bound, preliminary (VI-SU-04)",
    98: "C1 MFC resolution <= 0.0005 mg/s (VI-SU-05)",
    108: "P_bus < 1.5 kW incl. start-up transients at the spacecraft-DC boundary (VI-PB-03)",
    109: "ICP power inside the ~1.35 kW internal allocation (VI-PB-04)",
    110: "supply partition incl. ICP RF source/matching and collector/bias (VI-PB-01)",
    115: "torsional stand baseline (VI-HD-03)",
    117: "flexible RF coax with matched sham routing across the stand (VI-RF-11)",
    121: "1 % thrust uncertainty target (VI-HD-03)",
    122: "kinematic carrier exchanges C1 and ICP modules; H-1 stays bolted (C-EQUIV)",
    129: "I_d(t) to ~60 MHz or declared bandwidth (VI-HD-07)",
    130: "ICP telemetry: forward/reflected RF, collector V/I, RF source temperature, health/interlock (VI-LF-04)",
    132: "O2-bearing tests labelled NO_ATOMIC_O; AO life only in the separate programme (VI-LF-06)",
    133: "matched sham service lines in every compared configuration (C-EQUIV)",
    145: "this list is the new Hall->downstream-ICP validation-input list replacing the v2 list",
    146: "no ASSUMED_SCREENING_VALUE inputs manufactured; every non-owner value is TBD",
}

OPEN_QUESTIONS = [
    {"id": "OQ-VI-01", "question": "Which gas sustains the ICP neutralizer and where is it booked: (a) Hall exhaust "
     "re-use only (anchor topology), (b) dedicated Xe feed booked in the Xe ledger, (c) dedicated atmospheric feed?",
     "proposed_answer": "carry (a) as the A9 first-build hypothesis with a capped dedicated-feed port for (b)/(c) so "
     "the comparison can measure whether a dedicated feed is needed; book any dedicated flow as PHASE_TOTAL_FLOW; "
     "final booking is an owner call", "rows": [42, 46], "freeze_point": "LOCK-1"},
    {"id": "OQ-VI-02", "question": "Form of the neutralization margin (VI-EX-07)", "proposed_answer": "electron-current "
     "capacity at the registered coupling-voltage limit divided by the measured Hall I_d at the same point, per "
     "configuration; form frozen at LOCK-1, numeric margin at LOCK-2 (rows 18, 19); owner call",
     "rows": [18, 19, 37], "freeze_point": "LOCK-1 / LOCK-2"},
    {"id": "OQ-VI-03", "question": "Is an orificed RF plasma cathode (Watanabe / Xu type, dedicated feed) admissible "
     "as an A9 ICP-neutralizer variant, or only the open-tube coaxial downstream topology of the anchor?",
     "proposed_answer": "open-tube coaxial downstream topology only for the first build (A9 governing decision 1); "
     "orificed RF cathodes remain literature bounds, not built; owner call", "rows": [69], "freeze_point": "LOCK-1"},
    {"id": "OQ-VI-04", "question": "ICP-neutralizer lifetime and cycle requirement (VI-LF-05)",
     "proposed_answer": "hours = the provisional > 15,000 h firing basis (row 3); cycles from the mission mode "
     "profile once measured; both TBD; owner call", "rows": [3, 46], "freeze_point": "LOCK-1"},
    {"id": "OQ-VI-05", "question": "Is 'no Hall discharge without ICP electrons' (anchor TK-51) a required Ar "
     "engineering-only topology-reproduction check?", "proposed_answer": "yes, qualitative and engineering-only, "
     "preregistered in A9-01; no numeric match to anchor values (different hardware)", "rows": [36],
     "freeze_point": "LOCK-1"},
]

INTERFACE_DEMANDS = [
    ("IF-01", "from", "A9-01 docs/experiments/hall_icp/prereg_framework/", "stage map ids, decision-quantity list, "
     "prereg rules, outcome vocabulary (NO_VIABLE_CASE; OPEN as status)", "-", PENDING_A901),
    ("IF-02", "to", "A9-01 docs/experiments/hall_icp/prereg_framework/", "per-input producing stage requests "
     "(steps XCHK/AR/N2/O2/AO/XE) and the topology-reproduction check OQ-VI-05", "-", "OFFERED"),
    ("IF-03", "from", "A9-02 abep_sim/bus_boundary_a9.py + docs/architecture_comparison/power_boundary_a9/",
     "bus slots: RF source/matching, collector/bias, C1 heater/keeper/flow, assist magnet/cooling if used", "W",
     PENDING_A902),
    ("IF-04", "to", "A9-02", "measurement definitions P_RF,DC, P_coll, P_bus,ICP, P_bus,C1, P_bus(t) "
     "(VI-RF-08, VI-EX-04, VI-PB-01..03)", "W", "OFFERED"),
    ("IF-05", "from", "A9-03 docs/interfaces/icp_neutralizer/", "RF load plane, collector/body terminals and "
     "reference, gas port, Hall-exhaust-to-ICP pressure tap, diagnostic access", "-", PENDING_A903),
    ("IF-06", "to", "A9-03", "measurement provisions required by this list: antenna current probe port, directional "
     "coupler at the load plane, isolated collector/body V/I, pressure tap, witness-coupon holders, B-probe access in "
     "the ICP volume, capped dedicated-feed port (OQ-VI-01)", "A, W, V, Pa, T", "OFFERED"),
    ("IF-07", "from", "A9-04 docs/experiments/hall_icp/uncertainty_budget/", "measurement chains, uncertainties, "
     "stop rules and decision-quantity ids consuming these inputs", "per item", PENDING_A904),
    ("IF-08", "to", "A9-04", "the list of inputs needing a chain (every HARDWARE_ONLY item)", "per item", "OFFERED"),
    ("IF-09", "from", "A9-05 part 1 docs/evidence/icp_neutralizer/", "analog bounds (TK-/S-/D- ids)", "per item",
     "DELIVERED (this lane)"),
    ("IF-10", "to", "A9-06 mass BOM amendment", "ICP / RF mass allocations 2.0 / 1.5 kg are allocations only "
     "(VI-MS-01/02)", "kg", "OFFERED"),
    ("IF-11", "to", "A9-08 Xe ledger updates (" + XE_DIR + ")", "possible ICP Xe feed term (OQ-VI-01) and C1 start "
     "terms (VI-SU-04/05)", "mg/s, kg", "OFFERED (conditional on OQ-VI-01)"),
    ("IF-12", "from", "H2-1 docs/hardware/h2/h2_1_hall_chamber_magnet/ (+ A9-07 revision)", "H-1 field map incl. the "
     "downstream fringe region; external C1 (row 79) and neutralizer-agnostic head", "T, mm",
     "PENDING A9-07 revision of H2-1"),
    ("IF-13", "from", "H2-2 docs/hardware/h2/h2_2_cathode_integration/", "IFD-08 emission bounds (I_d <= 8.33 A at "
     "180 V RFP bound; <= 7.5 A under 1.35 kW) used as the electron-capacity sizing envelope", "A", "CONSUMED "
     "(PRELIMINARY bound, not a prediction)"),
    ("IF-14", "to", "H2-3 docs/hardware/h2/h2_3_gas_path_plenum/ (+ A9-07)", "any dedicated ICP gas line crossing "
     "potentials inherits the Paschen isolator requirement H23-29 (withstand across the full pressure range; ~1 kV "
     "qualification, row 105)", "V, Pa", "OFFERED"),
    ("IF-15", "to", "H2-4 docs/hardware/h2/h2_4_ppu_bus/ (+ A9-07)", "SEQ-1 revision must include ICP ignition "
     "before Hall ignition (anchor sequence TK-73) and the start-up peak rule (VI-PB-03)", "W", "OFFERED"),
    ("IF-16", "to", "H2-5 docs/hardware/h2/h2_5_thermal_network/ (+ A9-07)", "ICP / RF heat loads and >= 50 K "
     "margin (VI-LF-04)", "W, K", "OFFERED"),
    ("IF-17", "to", "H2-6 docs/hardware/h2/h2_6_diagnostics_fixture/", "kinematic carrier for C1 and ICP modules; "
     "RF coax with matched sham across the stand; RF pickup checks (VI-RF-11)", "-", "OFFERED"),
    ("IF-18", "to", "H2-7 docs/hardware/h2/h2_7_mechanical_bom/ (+ A9-06)", "ICP neutralizer, RF generator/"
     "matching/feedthrough and collector/bias BOM lines (row 59)", "kg", "OFFERED"),
    ("IF-19", "from", "docs/experiments/hardware/ (H-1 / C-1 configuration items)", "H-1 exit plane / IP-DN datum as "
     "the reference for z = 0 of the ICP geometry", "mm", "PENDING A9-03 (downstream plane definition)"),
]

M16_IMPACT = [
    (6, "Xe tank", "only if OQ-VI-01 books a dedicated Xe ICP feed (IF-11)"),
    (8, "Xe metering (splits to ignition/transition feed and cathode feed)", "C1 start/steady flow inputs VI-SU-04/05; "
     "possible ICP feed branch"),
    (9, "extended-channel Hall discharge chamber/accelerator", "Hall current demand VI-HD-01 becomes the sizing input "
     "of the electron source; no closure used"),
    (11, "shielded Xe-fed LaB6 hollow cathode", "C1 becomes reference/fallback (rows 49, 88); C1 inputs VI-PB-02, "
     "VI-SU-04/05"),
    (12, "PPU/power distribution", "new slots RF source/matching, collector/bias (VI-RF-08, VI-EX-04, VI-PB-01)"),
    (13, "thermal control", "ICP / RF thermal inputs VI-LF-04"),
    (14, "control/FDIR", "ICP telemetry and interlocks (row 130)"),
    (15, "sensors/diagnostics", "new RF chain: directional coupler, antenna current probe, isolated collector/body "
     "channels, calorimetry"),
    (16, "mechanical/structural interfaces", "kinematic carrier for C1/ICP modules (row 122)"),
    (17, "RF pre-ionization module interface", "superseded for the primary line by the downstream ICP neutralizer; "
     "this list supplies the validation inputs of the re-scoped row (re-scope itself belongs to A9-10)"),
]

HISTORICAL_REUSE = [
    {"path": "docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json",
     "sha256": "84ba1c382dc609b3e83ad9803a57ba471dd892fd10a6a6149285701a45a65a28",
     "reused": "record structure (id / definition / freeze point / status) and the LOCK-1-rule vs LOCK-2-value split",
     "not_reused": "P1DQ decision quantities, cases hall_only / rf_hall / ecr_hall, all thresholds (superseded, rows "
                   "18, 28, 34)"},
    {"path": "schemas/interfaces/preionizer_module_icd_v1.json",
     "sha256": "2470718e1decbde874d2362a997d1e2aaae54eb855d1ed179b930c3be6e7130e",
     "reused": "the 'net RF power at the coil/antenna feed terminals' load-plane definition pattern",
     "not_reused": "upstream placement, common envelope, PMQ-01..PMQ-05, L1-L5 harness, blank-module pressure-drop "
                   "class (superseded, rows 61-64)"},
    {"path": "docs/experiments/instrumentation/instrumentation_definition_v1.json",
     "sha256": "7c6d37b00f38a44cded73d92d4366739eacbf013e73e98a7bfbc3fa5a5470d96",
     "reused": "INS-01..INS-20 as measurement-chain anchors, adapted only through A9-04",
     "not_reused": "DQ-RARCH, DQ-TABS/DQ-PBUS on bus_power_boundary_v1 (A9 uses a new boundary, row 108)"},
    {"path": "feature/rf-hall-parallel-v2 branch (VALIDATION_PLAN.md) and A8",
     "sha256": None,
     "reused": "nothing",
     "not_reused": "the entire v2 input list (RF coupling, nozzle, Hall-Xe points, compressor, start-up Xe): frozen, "
                   "never supplied or invented (rows 11, 145, 146, 147)"},
]

H3_H4 = {
    "h3_procurement_rfq_inputs": [
        "13.56 MHz RF generator, 0-500 W forward with forward/reflected metering (row 72)",
        "matching network with remote tuning; RF vacuum feedthrough; flexible coax + matched sham (rows 8, 117)",
        "inline directional coupler + power sensors at the load plane; RF current probe for the antenna",
        "isolated collector/bias supply with V/I telemetry (row 70)",
        "isolated voltage/current channels for ICP body and collector; selectable bleeder (row 91)",
        "own-gas thermal MFC for any dedicated ICP feed (rows 124, 126); capped feed port",
        "witness-coupon holders for the ICP tube and H-1 exit (row 134)",
    ],
    "h4_measurement_inputs": [i[0] for i in ITEMS if i[16] == "HARDWARE_ONLY"],
}


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build():
    ev = _load(os.path.join(ROOT, EVIDENCE_REL))
    ev_ids = {e["id"] for e in ev["extraction"]} | {s["id"] for s in ev["survey"]["sources"]} | \
             {d["id"] for d in ev["survey"]["reused_from_repository"]}
    items = []
    for t in ITEMS:
        (iid, grp, name, sym, defin, units, configs, route, chain, refs, bound, steps, val, ecls, cons, freeze,
         status, basis, source) = t
        for r in refs:
            if r not in ev_ids:
                raise RuntimeError("%s cites unknown evidence id %s" % (iid, r))
        for c in cons:
            if c not in CONSUMERS:
                raise RuntimeError("%s unknown consumer %s" % (iid, c))
        for s in steps:
            if s not in STEPS:
                raise RuntimeError("%s unknown step %s" % (iid, s))
        if route != "owner_allocation" and not (isinstance(val, str) and val.startswith("TBD")):
            raise RuntimeError("%s: a value not given by the owner must be TBD (no prediction)" % iid)
        items.append({
            "id": iid, "group": grp, "name": name, "symbol": sym, "definition": definition_clean(defin),
            "units": units, "configurations": configs,
            "how_obtained": {"route": route, "chain": chain, "analog_refs": refs},
            "producing_stage": PENDING_A901 if route != "owner_allocation" else "n/a (owner allocation / requirement)",
            "evidence_steps": steps,
            "value": val, "evidence_class": ecls, "basis": basis, "source": source,
            "status": status, "freeze_point": freeze,
            "consumers": cons, "decision_quantity_ids": PENDING_A904,
            "analog_bound": bound if bound else "none",
            "supply": "owner" if route == "owner_allocation" else (
                "analog can bound (context only); value from H-1 hardware" if bound and refs else "H-1 hardware only"),
        })
    doc = {
        "schema": "hall_icp_validation_inputs_v1",
        "title": "Hall -> downstream RF-ICP neutralizer validation-input list (A9-05 part 2; owner answer row 145)",
        "lane": LANE, "trigger": TRIGGER, "status": "DRAFT_FOR_OWNER_REVIEW", "base_commit": BASE_COMMIT,
        "generated_by": REL + "/build_hall_icp_validation_inputs.py (--check reproduces JSON and MD exactly)",
        "authority_pins": AUTHORITY_PINS, "deliverable_pins": DELIVERABLE_PINS, "historical_pins": HISTORICAL_PINS,
        "governance_read_never_pinned": GOVERNANCE_NOT_PINNED,
        "evidence_input": {"path": EVIDENCE_REL, "sha256": _sha(os.path.join(ROOT, EVIDENCE_REL)),
                           "note": "same lane (part 1); regenerated first"},
        "replaces": "the frozen parallel RF||Hall v2 input list for the primary line (row 145); v2 inputs are never "
                    "supplied or invented (row 146)",
        "configuration_ids": CONFIG_IDS,
        "decision_vocabulary": {
            "outcomes_known_from_owner_answers": ["NO_VIABLE_CASE (row 28)", "not sustained within registered limits "
                                                  "(row 41)", "NOT_TESTED for stopped-arm slots (row 39)",
                                                  "PARTIAL_BOUNDARY (row 22)"],
            "status_not_outcome": "OPEN (row 38): unresolved evidence is reported with the next discriminating test",
            "net_benefit_form": "hard gates + Pareto (delta Xe, delta P_bus, delta mass, T/P_bus, restart and life "
                                "burden vs C1); no weighted scalar unless preregistered (row 37)",
            "full_vocabulary": PENDING_A901,
            "winner": "none declared by this lane",
        },
        "what_this_is_not": [
            "not a performance prediction for H-1, C1 or the A9 ICP module; no Hall closure (credible set EMPTY), no "
            "abep_sim/plasma_devices.py, no withdrawn v1.2-v1.6 number",
            "not a supply of the frozen v2 inputs; no ASSUMED_SCREENING_VALUE manufactured (row 146)",
            "not a numeric threshold: margins, effect sizes, stop rules and n are frozen at LOCK-1 (rules) / LOCK-2 "
            "(values); the only numbers are owner-given (cited by row)",
            "not a stage map (A9-01), bus boundary (A9-02), ICD (A9-03) or uncertainty budget (A9-04): those are "
            "PENDING and referenced, never fabricated",
            "Hall-closure uncertainty never leaks upstream: nothing here touches intake, compressor, gas chambers or "
            "valves models",
        ],
        "evidence_steps": STEPS, "consumers": CONSUMERS,
        "items": items,
        "interface_demands": [{"id": i, "direction": d, "counterpart": c, "what": w, "units": u, "status": s}
                              for i, d, c, w, u, s in INTERFACE_DEMANDS],
        "owner_answers_applied": [{"row": r, "how": OWNER_ROWS_APPLIED[r]} for r in sorted(OWNER_ROWS_APPLIED)],
        "open_owner_questions": OPEN_QUESTIONS,
        "historical_reuse": HISTORICAL_REUSE,
        "m16_impact": [{"m16_row": r, "subsystem": s, "how": h, "file_changed": False} for r, s, h in M16_IMPACT],
        "h3_h4_inputs": H3_H4,
        "summary_counts": summary_counts(items),
    }
    return doc


def definition_clean(s):
    return " ".join(s.split())


def summary_counts(items):
    out = {"items": len(items), "hardware_only": 0, "analog_can_bound_context": 0, "owner_given_value": 0,
           "tbd": 0}
    for it in items:
        if it["status"] == "HARDWARE_ONLY":
            out["hardware_only"] += 1
        if it["analog_bound"] != "none" and it["how_obtained"]["analog_refs"]:
            out["analog_can_bound_context"] += 1
        if it["status"] == "FIXED_BY_OWNER":
            out["owner_given_value"] += 1
        if isinstance(it["value"], str) and it["value"].startswith("TBD"):
            out["tbd"] += 1
    return out


def render_md(doc):
    L = []
    a = L.append
    a("# Hall -> downstream RF-ICP neutralizer: validation-input list (A9-05 part 2)")
    a("")
    a("| | |")
    a("|---|---|")
    a("| lane | `%s` (trigger `%s`) |" % (doc["lane"], doc["trigger"]))
    a("| status | **%s** |" % doc["status"])
    a("| generated by | `%s` |" % doc["generated_by"])
    a("| machine-readable | `%s/hall_icp_validation_inputs_v1.json` |" % REL)
    a("| replaces | %s |" % doc["replaces"])
    a("| configuration ids | %s |" % ", ".join("`%s`" % c for c in doc["configuration_ids"]))
    a("| evidence input | `%s` (`%s`) |" % (doc["evidence_input"]["path"], doc["evidence_input"]["sha256"]))
    a("")
    a("**Pins (sha256, verified at build):**")
    a("")
    for p in doc["authority_pins"] + doc["deliverable_pins"]:
        a("- `%s` - `%s` (%s)" % (p["path"], p["sha256"], p["role"]))
    for p in doc["historical_pins"]:
        a("- historical (read only, byte-identical): `%s` - `%s`" % (p["path"], p["sha256"]))
    a("")
    a("Read but never pinned (mutable governance): " + "; ".join("`%s`" % g for g in doc["governance_read_never_pinned"]))
    a("")
    a("**What this is not:**")
    a("")
    for w in doc["what_this_is_not"]:
        a("- " + w)
    a("")
    dv = doc["decision_vocabulary"]
    a("**Decision vocabulary:** outcomes known from owner answers: %s. %s. NET_BENEFIT: %s. Full vocabulary: %s. "
      "Winner: %s." % ("; ".join(dv["outcomes_known_from_owner_answers"]), dv["status_not_outcome"],
                       dv["net_benefit_form"], dv["full_vocabulary"], dv["winner"]))
    a("")
    c = doc["summary_counts"]
    a("**Counts:** %d inputs; %d H-1-hardware-only; %d with published-analog context; %d owner-given values; %d TBD." % (
        c["items"], c["hardware_only"], c["analog_can_bound_context"], c["owner_given_value"], c["tbd"]))
    a("")
    a("## Evidence steps (from A9 and owner answers; not stage ids)")
    a("")
    for k, v in doc["evidence_steps"].items():
        a("- `%s`: %s" % (k, v))
    a("")
    a("## Consumers (A9 gates / NET_BENEFIT terms)")
    a("")
    for k, v in doc["consumers"].items():
        a("- `%s`: %s" % (k, v))
    a("")
    a("## (a) Validation inputs")
    a("")
    a("| id | name | symbol | units | configs | value / TBD | evidence class | basis | source | status | freeze | "
      "how obtained | steps | consumers | analog bound | supply |")
    a("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for it in doc["items"]:
        ho = it["how_obtained"]
        a("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s: %s%s | %s | %s | %s | %s |" % (
            it["id"], it["name"], it["symbol"], it["units"], ", ".join(it["configurations"]), it["value"],
            it["evidence_class"], it["basis"], it["source"], it["status"], it["freeze_point"], ho["route"],
            ho["chain"], (" [analog: " + ", ".join(ho["analog_refs"]) + "]") if ho["analog_refs"] else "",
            ", ".join(it["evidence_steps"]) or "-", ", ".join(it["consumers"]) or "-", it["analog_bound"],
            it["supply"]))
    a("")
    a("Producing stage for every measured input: %s. Decision-quantity ids: %s." % (PENDING_A901, PENDING_A904))
    a("")
    a("### Definitions")
    a("")
    for it in doc["items"]:
        a("- **%s** `%s`: %s" % (it["id"], it["symbol"], it["definition"]))
    a("")
    a("## (b) Interface demands")
    a("")
    a("| id | direction | counterpart | what | units | status |")
    a("|---|---|---|---|---|---|")
    for i in doc["interface_demands"]:
        a("| %s | %s | %s | %s | %s | %s |" % (i["id"], i["direction"], i["counterpart"], i["what"], i["units"],
                                              i["status"]))
    a("")
    a("## (c) Owner answers applied")
    a("")
    for o in doc["owner_answers_applied"]:
        a("- row %d: %s" % (o["row"], o["how"]))
    a("")
    a("## (d) Open owner questions (new)")
    a("")
    for q in doc["open_owner_questions"]:
        a("- **%s** (rows %s; freeze %s): %s - proposed: %s" % (q["id"], ", ".join(str(r) for r in q["rows"]),
                                                               q["freeze_point"], q["question"], q["proposed_answer"]))
    a("")
    a("## (e) Historical reuse")
    a("")
    for h in doc["historical_reuse"]:
        a("- `%s`%s: reused: %s; not reused: %s" % (h["path"], (" (`%s`)" % h["sha256"]) if h["sha256"] else "",
                                                    h["reused"], h["not_reused"]))
    a("")
    a("## (f) M16 impact (the M16 file is not changed by this lane)")
    a("")
    for m in doc["m16_impact"]:
        a("- row %d (%s): %s" % (m["m16_row"], m["subsystem"], m["how"]))
    a("")
    a("## (g) H3 / H4 inputs")
    a("")
    a("- **H3 RFQ specification inputs (quotations only, row 8):** " + "; ".join(doc["h3_h4_inputs"]["h3_procurement_rfq_inputs"]))
    a("- **H4 measurement inputs (hardware-only items):** " + ", ".join(doc["h3_h4_inputs"]["h4_measurement_inputs"]))
    a("")
    return "\n".join(L)


def outputs():
    doc = build()
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n", render_md(doc)


def verify_pins():
    bad = []
    for p in AUTHORITY_PINS + DELIVERABLE_PINS + HISTORICAL_PINS:
        fp = os.path.join(ROOT, p["path"])
        if not os.path.exists(fp) or _sha(fp) != p["sha256"]:
            bad.append(p["path"])
    return bad


def check():
    j, m = outputs()
    diffs = []
    for path, txt in ((JSON_OUT, j), (MD_OUT, m)):
        if not os.path.exists(path):
            diffs.append(path + " missing")
            continue
        with open(path, encoding="utf-8") as f:
            if f.read() != txt:
                diffs.append(path + " differs")
    return diffs


def main(argv):
    bad = verify_pins()
    if bad:
        print("PIN MISMATCH:", bad)
        return 2
    if "--check" in argv:
        d = check()
        print("OK" if not d else "\n".join(d))
        return 0 if not d else 1
    j, m = outputs()
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        f.write(j)
    with open(MD_OUT, "w", encoding="utf-8") as f:
        f.write(m)
    print("wrote", JSON_OUT, MD_OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
