#!/usr/bin/env python3
"""H2-7 mechanical envelope / evolving mass model (fo_h2_7_mechanical_bom, trigger T_H2_7_MECHANICAL_BOM, owner A7).

Deterministic builder. It reads the pinned owner decisions and verified deliverables (sha256-checked; a mismatch
raises), the hand-transcribed external analog data below (each value with source, locator and evidence class), and,
LAZILY, the outputs of the parallel lanes when they are present in the checkout. It writes

    docs/hardware/h2/h2_7_mechanical_bom/h2_7_mechanical_bom_v1.json
    docs/hardware/h2/h2_7_mechanical_bom/H2_7_MECHANICAL_BOM.md

Nothing here predicts thrust, efficiency, discharge current or plasma state. Masses of other hardware (analogs) are
never predictions of Vyovrinda hardware; A5 numbers are allocations or requirements. No mass is invented: every CBE is
a sourced analog value, a derivation from stated inputs, a policy fraction from the adopted margin policy, or TBD.
The module is pure: it is not imported by abep_sim and is not wired into archengine.

Usage:
    python docs/hardware/h2/h2_7_mechanical_bom/build_h2_7_mechanical_bom.py            # write JSON + MD
    python docs/hardware/h2/h2_7_mechanical_bom/build_h2_7_mechanical_bom.py --check    # compare, exit 1 if stale
    python docs/hardware/h2/h2_7_mechanical_bom/build_h2_7_mechanical_bom.py --lane-root DIR --stdout
        # integration preview: consume parallel-lane outputs found under DIR (never used for the committed files)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LANE_DIR_REL = "docs/hardware/h2/h2_7_mechanical_bom"
JSON_NAME = "h2_7_mechanical_bom_v1.json"
MD_NAME = "H2_7_MECHANICAL_BOM.md"
BASE_COMMIT = "8ea7e4bc882d39bb0bce61308e7a1f5b8c0ecd2e"
DATE = "2026-09-29"

ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
FLIGHT_STATUS = ("FLIGHT-REPRESENTATIVE", "H-1 TEST-ARTICLE-ONLY", "GROUND/FACILITY-ONLY")
H27_ALIASES = ("H2-7", "H2_7", "fo_h2_7_mechanical_bom", "h2_7_mechanical_bom")
M16_STATES = ("READY", "RUNNING", "BLOCKED", "VERIFIED")
ROLLUP_CATEGORIES = ("architecture blocker", "hardware-definition blocker", "procurement blocker",
                     "test-readiness blocker", "proposal-only documentation gap")
FORBIDDEN_KEYS = ("screening_candidate", "sgb-screen", "ensemble_member_id", "p5_registration", "coil_shape",
                  "beam_efficiency_reading", "facility_ingestion_interpretation", "plasma_devices")

# --------------------------------------------------------------------------------------------- pinned inputs
# Only immutable inputs are pinned (owner decisions, G0 record, verified/merged deliverables). Mutable governance files
# (lane_registry_v1.json, trigger_registry_v1.json, trigger ledgers, runtime_state.json) are never pinned or read.
PINS = {
    "OD": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json",
           "5a5adb8116eecee418992977c239f198a88835c739f357f13a8bddd51778c2ac",
           "hardware-pivot owner disposition that A5-A7 amend"),
    "A5": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json",
           "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621",
           "16 baseline subsystem names, reserved RF interface, Xe allocation terms, mass allocation <= 34-36 kg"),
    "A6": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json",
           "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180",
           "m_Xe_subsystem decomposition; not_authorized list"),
    "A7": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json",
           "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925",
           "H2 scope, architecture-changing blockers 1-3, M16 execution states and rollup categories"),
    "G0": ("docs/decisions/verification/A5_BASELINE_VERIFICATION.json",
           "4bd0fb4312fba97b18bba92ca0726133947ea6d86327f5e1360ea6af2b163523",
           "G0 verdict CLEAN: downstream artifacts may pin A5"),
    "MASSBOM": ("docs/architecture_comparison/mass_bom/mass_bom_v1.json",
                "8ab97ff93f507899508374d4ce8116e7066c31e3fbe2c79300f5b55372ba7313",
                "margin policy (MGA categories, system margin, harness and residual fractions) and item ids reused"),
    "HWDEF": ("docs/experiments/hardware/hardware_requirements_v1.json",
              "0b75be0a0ddc4888eb157c20e2b22dd4fce2a4bb94c4d6402cbe716ec73b0aa0",
              "H-1 configuration items and interface planes; RFP basis"),
    "XELEDGER": ("docs/budgets/xe_ledger/xe_ledger_v1.json",
                 "965fdafa60ae9c3ee1e36189f22ef00198ae3f8a906696213bec13bdcbfb09ad",
                 "verified parametric Xe ledger (T_A5_XE_LEDGER VERIFIED, merged 732bbde): cathode term, missing terms"),
    "W4": ("docs/experiments/instrumentation/instrumentation_definition_v1.json",
           "7c6d37b00f38a44cded73d92d4366739eacbf013e73e98a7bfbc3fa5a5470d96",
           "H-1 ground instrument list INS-01..INS-24 (excluded from the flight mass model)"),
    "CDS": ("docs/architecture_comparison/compressor_downselect/compressor_downselect_v1.json",
            "79f6b28f65243b54894dc78172b708693f96c639089f472d91d070012a0e4a52",
            "compressor concept status (mass TBD for every surveyed concept)"),
}
NEVER_PINNED = [
    "docs/orchestration/lane_registry_v1.json", "docs/orchestration/trigger_registry_v1.json",
    "docs/orchestration/fired_triggers.jsonl", "docs/orchestration/trigger_ledger_v2.jsonl",
    "docs/orchestration/runtime_state.json", "CLAUDE.md (referenced by path for the ECHT geometry only)",
    "docs/EVIDENCE.md (referenced by path only)", "docs/interfaces/UPSTREAM_ICD.md (referenced by path only)",
]

# Parallel lanes, resolved lazily at build time. Nothing is imported; a missing directory means PENDING.
LANES = {
    "H2-1": ("fo_h2_1_hall_chamber_magnet", "docs/hardware/h2/h2_1_hall_chamber_magnet"),
    "H2-2": ("fo_h2_2_cathode_integration", "docs/hardware/h2/h2_2_cathode_integration"),
    "H2-3": ("fo_h2_3_gas_path_plenum", "docs/hardware/h2/h2_3_gas_path_plenum"),
    "H2-4": ("fo_h2_4_ppu_bus", "docs/hardware/h2/h2_4_ppu_bus"),
    "H2-5": ("fo_h2_5_thermal_network", "docs/hardware/h2/h2_5_thermal_network"),
    "H2-6": ("fo_h2_6_diagnostics_fixture", "docs/hardware/h2/h2_6_diagnostics_fixture"),
    "PIM-ICD": ("fo_preionizer_module_icd", "docs/interfaces/preionizer_module"),
    "M16": ("fo_subsystem_maturity_matrix", "docs/budgets/subsystem_maturity"),
    "P1-PREG": ("fo_phase1_prereg_framework", "docs/experiments/phase1_prereg_framework"),
}


def pending(lane_key: str) -> str:
    return "PENDING " + LANES[lane_key][1] + "/"


# ------------------------------------------------------------------------------------------ external sources
# Accessed 2026-09-29 by this lane. PDFs: sha256 of the bytes as fetched. HTML pages: read through the fetch tool
# (no stable bytes; exact wording to be verified on the page). Nobody was contacted.
SOURCES = {
    "SRC-BUSEK-BHT600": {
        "citation": "Busek Co. Inc., 'BHT-600 Hall Effect Thruster' datasheet, Version 1.0, released August 2021",
        "url": "https://satcatalog.s3.amazonaws.com/components/940/SatCatalog_-_Busek_-_BHT-600_-_Datasheet.pdf?lastmod=20211014052402",
        "also": "identical bytes inside https://www.busek.com/s/Busek-Hall-Thrusters-Datasheets-v10.zip (BHT_600_v1.0.pdf)",
        "sha256_as_fetched": "a8fa215f7ae59fe0f9931a2fa57f9604028b200dfb387c497da65c2484880e7d",
        "access": "open PDF, text extracted with pdftotext", "kind": "manufacturer datasheet"},
    "SRC-BUSEK-BHT1500": {
        "citation": "Busek Co. Inc., 'BHT-1500 Hall Effect Thruster' datasheet, Version 1.0 (2021)",
        "url": "https://www.busek.com/s/Busek-Hall-Thrusters-Datasheets-v10.zip",
        "member": "BHT_1500_v1.0.pdf (zip sha256 2f3808f8bc993f15f33a991535e8c8f79a9d3c7469ecbe25824361b4c710d7a5)",
        "sha256_as_fetched": "99b65f415ad225b2711d2442155b73d0016a8c77cc96a1dabf328e479471361e",
        "access": "open zip of PDFs from the manufacturer site, text extracted with pdftotext",
        "kind": "manufacturer datasheet"},
    "SRC-SAFRAN-PPS1350": {
        "citation": "Safran Aircraft Engines, 'PPS(R)1350 [Stationary plasma thruster]' datasheet (2 pages, code '205-17')",
        "url": "https://www.safran-group.com/sites/default/files/2022-09/PPS1350%20-%20Safran%20Spacecraft%20Propulsion%20-%20Datasheet.pdf",
        "sha256_as_fetched": "b8167eff385d042b04507e786e19235ae5b1363e6f361b7f4f34a322e5fe223d",
        "access": "open PDF, text extracted with pdftotext; drawing labels read from the text layer (axis assignment: verify)",
        "kind": "manufacturer datasheet"},
    "SRC-NASA-LOWMASS-HALL": {
        "citation": "NASA, 'Low-Mass, Low-Power Hall Thruster System - For radioisotope electric propulsion (REP)', SBIR "
                    "fact sheet (Busek Company, Inc.), in NASA/TM-2015-218829, p. 3 (NTRS 20160005342)",
        "url": "https://ntrs.nasa.gov/api/citations/20160005342/downloads/20160005342.pdf",
        "sha256_as_fetched": "fb3ae447a19abe82e19b48b3ce96c2a1eb4aa61c2830ae866fab796fadb0fc0e",
        "access": "open PDF, text extracted with pdftotext", "kind": "agency fact sheet (development TARGETS only)"},
    "SRC-TAS-PPU-2019": {
        "citation": "E. Bourguignon and S. Fraselle, 'Power Processing Unit Activities at Thales Alenia Space in Belgium', "
                    "IEPC-2019-584, 36th International Electric Propulsion Conference, Vienna, 15-20 September 2019",
        "url": "https://electricrocket.org/2019/584.pdf",
        "sha256_as_fetched": "c47f3c83427665811263823e65123ec8352d40e2d646a9a4dbbdca6f65363d6f",
        "access": "open PDF, text extracted with pdftotext", "kind": "developer conference paper"},
    "SRC-SATSEARCH-SETS-PPU": {
        "citation": "satsearch listing 'Power Processing Unit (PPU)' by SETS (Space Electric Thruster Systems)",
        "url": "https://satsearch.co/products/sets-space-power-processing-unit-ppu",
        "sha256_as_fetched": None,
        "access": "open HTML read through the fetch tool; third-party marketplace listing (verify on the page)",
        "kind": "secondary product listing"},
    "SRC-MOOG-PFCV": {
        "citation": "Moog Inc., 'Electric Propulsion Proportional Flow Control Valve (PFCV)' 51E339 datasheet, "
                    "Form 500-1119 0620",
        "url": "https://www.moog.com/content/dam/moog/literature/sdg/space/propulsion/moog-proportional-flow-control-valve-datasheet.pdf",
        "sha256_as_fetched": "f9124de96f217ac8153cbcd2d94e751a9662b2978abaed6e9a520ae0a6062a2b",
        "access": "open PDF, text extracted with pdftotext", "kind": "manufacturer datasheet"},
    "SRC-MOOG-ISO": {
        "citation": "Moog Inc., 'Electric Propulsion Isolation Valves' datasheet",
        "url": "https://www.moog.com/content/dam/moog/literature/sdg/space/propulsion/moog-electric-propulsion-isolation-valve-datasheet.pdf",
        "sha256_as_fetched": "b501398e7d95800299ebdb00e3750a08ed516f6d67c171d4682094124de3655c",
        "access": "open PDF, text extracted with pdftotext", "kind": "manufacturer datasheet"},
    "SRC-MOOG-XFC": {
        "citation": "Moog Inc., 'Xenon Flow Controller (XFC)' product page",
        "url": "https://www.moog.com/products/propulsion/space-propulsion/spacecraft-propulsion/systems-and-subsystems/xenon-flow-controller.html",
        "sha256_as_fetched": None,
        "access": "open HTML read through the fetch tool (quoted strings; verify on the page)",
        "kind": "manufacturer product page"},
    "SRC-ARIANE-XRFS": {
        "citation": "ArianeGroup, 'Xenon Regulator and Feed System (XRFS)', page 'Pressure Regulator for Ion Space "
                    "Propulsion Systems'",
        "url": "https://www.space-propulsion.com/spacecraft-propulsion/valves/pressure-regulator.html",
        "sha256_as_fetched": None,
        "access": "open HTML read through the fetch tool (quoted strings; verify on the page)",
        "kind": "manufacturer product page"},
    "SRC-MT-TANKS": {
        "citation": "MT Aerospace AG, 'Spacecraft Propellant Tanks' catalogue (15 pages; PDF created 2019-04-30)",
        "url": "https://www.mt-aerospace.de/files/mta/tankkatalog/MT-Tankkatalog.pdf",
        "sha256_as_fetched": "076144193c73875b719890252da74fd66f8edbc4004956cd22577f4bf0cedb30",
        "access": "open PDF, text extracted with pdftotext", "kind": "manufacturer catalogue"},
    "SRC-NIST-XE": {
        "citation": "NIST Chemistry WebBook, SRD 69, Thermophysical Properties of Fluid Systems: xenon, isothermal "
                    "properties at 293.15 K",
        "url": "https://webbook.nist.gov/cgi/fluid.cgi?Action=Load&ID=C7440633&Type=IsoTherm&Digits=5&PLow=50&PHigh=150&PInc=25&T=293.15&RefState=DEF&TUnit=K&PUnit=bar&DUnit=kg%2Fm3&HUnit=kJ%2Fkg&WUnit=m%2Fs&VisUnit=uPa*s&STUnit=N%2Fm",
        "sha256_as_fetched": None,
        "access": "open HTML table read through the fetch tool (verify)", "kind": "evaluated reference data"},
    "SRC-ECHT-REPO": {
        "citation": "ECHT geometry as recorded in the repository: CLAUDE.md 'Superseded / withdrawn' ('true ECHT: 86 mm "
                    "long, 10 mm wide, 100 mm OD') and docs/EVIDENCE.md register row 'ECHT geometry (thesis Sec. 4.1.1, "
                    "p. 63)' (F. Marchioni, MSc thesis, 2020)",
        "url": None, "sha256_as_fetched": None,
        "access": "repository documents referenced by path (mutable, never pinned); thesis not re-accessed by this lane",
        "kind": "published analog geometry (evidence level 3 per docs/EVIDENCE.md)"},
}

UNIT = {"KG_PER_G": 1e-3, "KG_PER_LBM": 0.45359237, "M3_PER_L": 1e-3, "S_PER_H": 3600.0, "KG_PER_MG": 1e-6}
UNIT_NOTES = {"KG_PER_LBM": "international avoirdupois pound, exact by definition (from memory: verify against NIST "
                            "SP 811 Appendix B)"}

# ------------------------------------------------------------------------------------------------ analog data
# Values of OTHER hardware. Transcribed by hand from the accessed sources (locator given). Never Vyovrinda predictions.
ANALOGS = {
    "AN-BHT600-THR": dict(device="Busek BHT-600 (Xe Hall thruster, 600 W discharge, 300-800 W throttle)",
                          quantity="thruster mass", value=2.6, unit="kg", evidence_class="measured",
                          stated_as="manufacturer specification", source="SRC-BUSEK-BHT600",
                          locator="p. 1 'Table: Standard Specifications': 'Thruster Mass: 2.6 kg'",
                          includes="thruster incl. its magnetic circuit; cathode listed separately"),
    "AN-BHT600-CATH": dict(device="Busek BHT-600 cathode", quantity="cathode mass", value=0.2, unit="kg",
                           evidence_class="measured", stated_as="manufacturer specification",
                           source="SRC-BUSEK-BHT600", locator="p. 1 'Cathode Mass: 0.2 kg'",
                           includes="cathode; emitter type and mount not stated"),
    "AN-BHT1500-THR": dict(device="Busek BHT-1500 (Xe Hall thruster, 1500 W discharge, 1000-2700 W throttle, centre-"
                                  "mounted cathode)", quantity="thruster mass", value=6.3, unit="kg",
                           evidence_class="measured", stated_as="manufacturer specification",
                           source="SRC-BUSEK-BHT1500", locator="p. 1 'Table: Standard Specifications': 'Thruster "
                                                               "Mass: 6.3 kg'",
                           includes="thruster incl. its magnetic circuit; cathode listed separately"),
    "AN-BHT1500-CATH": dict(device="Busek BHT-1500 cathode", quantity="cathode mass", value=0.3, unit="kg",
                            evidence_class="measured", stated_as="manufacturer specification",
                            source="SRC-BUSEK-BHT1500", locator="p. 1 'Cathode Mass: 0.3 kg'",
                            includes="cathode; emitter type and mount not stated"),
    "AN-PPS1350-MASS": dict(device="Safran PPS1350-S / -E (Xe Hall thruster, 1500 / 2500 W)",
                            quantity="weight including xenon flow control system", value=4.8, unit="kg",
                            evidence_class="measured", stated_as="manufacturer specification",
                            source="SRC-SAFRAN-PPS1350",
                            locator="p. 2 SPECIFICATIONS: 'Weight (including xenon flow control system) (kg) 4.8'",
                            includes="thruster, two cathodes (drawing labels 'Cathode 1', 'Cathode 2') and xenon flow "
                                     "control system; context only (inside the Hall row range)"),
    "AN-PPS1350-DIMS": dict(device="Safran PPS1350", quantity="drawing dimension labels", value=[104.0, 135.0, 210.0],
                            unit="mm", evidence_class="measured", stated_as="manufacturer drawing ('max' labels)",
                            source="SRC-SAFRAN-PPS1350",
                            locator="p. 2 drawing labels '104 mm max', '135 mm max', '210 mm max' (which label is "
                                    "axial vs transverse is read from the drawing: verify)",
                            includes="envelope analog only"),
    "AN-NASA-LM-PPU-TARGET": dict(device="low-mass PPU development for a 1 kW-class Hall system (NASA SBIR, Busek)",
                                  quantity="PPU target mass", value=2.0, unit="kg", evidence_class="assumed",
                                  stated_as="development TARGET (not a demonstrated mass)",
                                  source="SRC-NASA-LOWMASS-HALL",
                                  locator="p. 3: 'the target mass of 1 kg for the thruster and 2 kg for the power "
                                          "processing unit (PPU)'; system 'input power up to 1,000 W'",
                                  includes="PPU; undemonstrated target (owner question H27-Q5)"),
    "AN-TAS-PPUMK1-MASS": dict(device="Thales Alenia Space Belgium PPU Mk1 (for 1.5 kW Hall thrusters PPS1350-G and "
                                      "SPT-100; flight heritage)", quantity="mass including the Thruster Selection "
                                                                            "Unit", value=10.9, unit="kg",
                               evidence_class="measured", stated_as="developer statement",
                               source="SRC-TAS-PPU-2019",
                               locator="Sec. I 'PPU Mk1': 'Mass of PPU Mk1 including TSU: 10.9 kg.'",
                               includes="discharge, magnet, heater, ignitor supplies, valve driver, thermothrottle, "
                                        "sequencer, TC/TM interface, TSU for one of two thrusters"),
    "AN-TAS-PPUMK1-DIMS": dict(device="Thales Alenia Space Belgium PPU Mk1", quantity="dimensions",
                               value=[390.0, 190.0, 186.0], unit="mm", evidence_class="measured",
                               stated_as="developer statement", source="SRC-TAS-PPU-2019",
                               locator="Sec. I 'PPU Mk1': 'Dimensions: 390 mm x 190 mm x 186 mm.'",
                               includes="envelope analog only"),
    "AN-SETS-PPU": dict(device="SETS PPU (Hall thruster 100-500 W)", quantity="mass", value=5.0, unit="kg",
                        evidence_class="measured", stated_as="secondary listing of a product specification",
                        source="SRC-SATSEARCH-SETS-PPU", locator="listing: 'Mass: 5 kg'; 'Width 321 mm, Length 255 mm, "
                                                                  "Height 94 mm'; '100W to 500W'",
                        includes="context only (500 W class; secondary source); not a range end"),
    "AN-MOOG-PFCV": dict(device="Moog 51E339 proportional flow control valve (Xe)", quantity="mass", value=115.0,
                         unit="g", evidence_class="measured", stated_as="manufacturer maximum ('115 g (0.25 lbm) "
                                                                         "max')",
                         source="SRC-MOOG-PFCV", locator="SPECIFICATIONS table, row 'Mass'",
                         includes="flow range '0 - 30 mg/s Xe typical'; MEOP 186 bar"),
    "AN-MOOG-LATCH-18": dict(device="Moog 1/8 inch latching solenoid isolation valve", quantity="weight", value=170.0,
                             unit="g", evidence_class="measured",
                             stated_as="manufacturer upper limit ('< 0.375 (170) lbm (g)')", source="SRC-MOOG-ISO",
                             locator="table row 'Weight', first column; row 'Cycle Life' 18,000 cycles; MEOP 186 bar",
                             includes="isolation valve (column assignment 1/8 inch latching: verify on the PDF)"),
    "AN-MOOG-XFC": dict(device="Moog Xenon Flow Controller (XFC)", quantity="mass", value=974.0, unit="g",
                        evidence_class="measured", stated_as="manufacturer upper limit ('< 2.2 lbm (<974 g)')",
                        source="SRC-MOOG-XFC", locator="product page, 'Mass'",
                        includes="complete single-thruster Xe flow controller (regulation + flow control), flow '3- 23 "
                                 "mg/sec GXe', '186 bar (2700 psia) capable'; 2.2 lbm = 0.998 kg, so the two unit "
                                 "statements differ by 2.4 %; the gram statement is used for this LOW range end"),
    "AN-XRFS": dict(device="ArianeGroup Xenon Regulator and Feed System (XRFS)", quantity="mass", value=5.9, unit="kg",
                    evidence_class="measured", stated_as="manufacturer upper limit ('< 5.9 kg')",
                    source="SRC-ARIANE-XRFS", locator="product page, 'Mass'",
                    includes="bang-bang regulator + feed system; inlet '3 to 120 bar', outlet '2.65 bar +- 0.2 bar', "
                             "flow '> 6 mg/s gaseous xenon'"),
    "AN-MT-XSXTA": dict(device="MT Aerospace XS-XTA 1-7 l xenon tank family (Ti-6Al-4V shell; UNDER DEVELOPMENT)",
                        quantity="tank dry mass", value=3.5, unit="kg", evidence_class="assumed",
                        stated_as="catalogue upper limit of a family under development ('<=3,5 kg')",
                        source="SRC-MT-TANKS",
                        locator="catalogue p. 11 'XS-XTA / 1 - 7l Family': TOTAL VOLUME 1-7 l, TANK DRY MASS '<=3,5 "
                                "kg', DIAMETER 242 mm, LENGTH '<=386 mm'; MEOP field blank; 'UNDER DELELOPMENT' [sic]",
                        includes="tank only; MEOP not stated (capacity is derived below from a PROPOSED minimum MEOP)"),
    "AN-MT-XSXTA-ENV": dict(device="MT Aerospace XS-XTA 1-7 l", quantity="diameter / max length", value=[242.0, 386.0],
                            unit="mm", evidence_class="assumed", stated_as="catalogue values (family under development)",
                            source="SRC-MT-TANKS", locator="catalogue p. 11", includes="envelope analog"),
    "AN-MT-SXTA40": dict(device="MT Aerospace S-XTA 40 l xenon tank (COPV, Ti-6Al-4V liner, CFRP T800; MEOP 187 bar)",
                         quantity="predicted structural mass", value=6.3, unit="kg", evidence_class="model-derived",
                         stated_as="supplier prediction ('mStruct_pred=6.3 kg')", source="SRC-MT-TANKS",
                         locator="catalogue p. 12 'S-XTA / 40-120l Family' size table: V=40 l, L=446 mm, "
                                 "mStruct_pred=6.3 kg, MXe_max=73 kg; diameter 440 mm",
                         includes="oversized for the present Xe term (73 kg capacity): conservative high end only"),
    "AN-MT-SXTA40-CAP": dict(device="MT Aerospace S-XTA 40 l", quantity="maximum Xe load", value=73.0, unit="kg",
                             evidence_class="model-derived", stated_as="supplier table ('MXe_max=73 kg')",
                             source="SRC-MT-TANKS", locator="catalogue p. 12 size table", includes="context"),
    "AN-NIST-XE-RHO": dict(device="xenon (fluid property)", quantity="density at 293.15 K and 75 / 100 / 125 / 150 bar",
                           value=[1675.7, 1867.9, 1971.2, 2045.5], unit="kg m^-3", evidence_class="model-derived",
                           stated_as="evaluated equation-of-state values (supercritical)", source="SRC-NIST-XE",
                           locator="isotherm table rows 293.15 K at 75.000 / 100.00 / 125.00 / 150.00 bar",
                           includes="storage-volume parameter sweep"),
    "AN-ECHT-GEOM": dict(device="ECHT extended-channel Hall thruster (laboratory device on N2)",
                         quantity="BN chamber length / channel width / outer diameter", value=[86.0, 10.0, 100.0],
                         unit="mm", evidence_class="measured", stated_as="design dimensions as recorded in the repo",
                         source="SRC-ECHT-REPO", locator="CLAUDE.md 'Superseded / withdrawn'; docs/EVIDENCE.md row "
                                                         "'ECHT geometry'",
                         includes="published analog of an extended channel; no ECHT mass is published; never a "
                                  "Vyovrinda design value"),
}
ANALOG_PRESSURES_BAR = [75.0, 100.0, 125.0, 150.0]

# PROPOSED minimal single-string Xe metering set (A5: 'Xe metering (splits to ignition/transition feed and cathode feed)')
N_XE_BRANCHES = 2
VALVES_PER_BRANCH = {"AN-MOOG-LATCH-18": 1, "AN-MOOG-PFCV": 1}


def analog_kg(aid: str) -> float:
    a = ANALOGS[aid]
    if a["unit"] == "kg":
        return float(a["value"])
    if a["unit"] == "g":
        return float(a["value"]) * UNIT["KG_PER_G"]
    raise ValueError(f"{aid}: not a mass")


# -------------------------------------------------------------------------------------------------- utilities
def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_pinned(repo: Path, key: str) -> dict:
    rel, sha, _ = PINS[key]
    p = repo / rel
    if not p.is_file():
        raise FileNotFoundError(f"pinned input missing: {rel}")
    got = sha256_file(p)
    if got != sha:
        raise ValueError(f"pinned input {rel} changed: sha256 {got} != pinned {sha}")
    return json.loads(p.read_text())


def r6(x):
    if x is None:
        return None
    if isinstance(x, float):
        v = round(x, 6)
        return 0.0 if v == 0 else v
    return x


def rnd(o):
    if isinstance(o, dict):
        return {k: rnd(v) for k, v in o.items()}
    if isinstance(o, list):
        return [rnd(v) for v in o]
    return r6(o)


def parse_range_kg(text: str) -> list[float]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*kg", text)
    if not m:
        raise ValueError(f"cannot parse a kg range from {text!r}")
    return [float(m.group(1)), float(m.group(2))]


def parse_hours(text: str) -> float:
    m = re.search(r"(\d{1,3}(?:,\d{3})+|\d+)\s*h", text)
    if not m:
        raise ValueError(f"cannot parse hours from {text!r}")
    return float(m.group(1).replace(",", ""))


def a5_alloc(a5: dict, quantity: str) -> dict:
    for row in a5["allocations_and_requirements"]:
        if row["quantity"] == quantity:
            return row
    raise KeyError(quantity)


# ------------------------------------------------------------------------------------------------ the mass model
def a5_subsystems(a5: dict) -> list[tuple[str, str]]:
    arch = a5["architecture"]
    out = []
    for grp in ("atmospheric_branch", "xe_branch", "propulsion", "support"):
        out += [(grp, name) for name in arch[grp]]
    if len(out) != arch["baseline_subsystem_count"]:
        raise ValueError(f"A5 lists {len(out)} subsystems, count field says {arch['baseline_subsystem_count']}")
    return out


def row_specs(a5: dict) -> list[dict]:
    """Rows R01-R16 (A5 names, exact, read from the pinned A5 file) + R17 reserved interface. Each carries line items.

    cbe kinds: analog_range (low/high analog ids), derived_valves, fixed_design_term, fraction_of_item,
    included_in (0 kg additional, flagged), tbd.
    """
    subs = a5_subsystems(a5)
    names = [n for _, n in subs]
    expected = ["intake", "protective/filter stage", "compressor", "buffer/plenum", "atmospheric metering valve",
                "Xe tank", "Xe regulator", "Xe metering (splits to ignition/transition feed and cathode feed)",
                "extended-channel Hall discharge chamber/accelerator", "magnetic circuit",
                "shielded Xe-fed LaB6 hollow cathode", "PPU/power distribution", "thermal control", "control/FDIR",
                "sensors/diagnostics", "mechanical/structural interfaces"]
    if names != expected:
        raise ValueError(f"A5 subsystem names changed: {names}")
    grp = {n: g for g, n in subs}
    FR, TA, GO = FLIGHT_STATUS

    def tbd(requires, lane=None):
        return {"kind": "tbd", "requires": requires, "pending_lane": lane}

    rows = [
        dict(row_id="R01", a5_subsystem=names[0], mass_bom_items=["intake"], flight_status=FR,
             h1_counterpart={"items": ["FS-C"], "status": GO, "note": "no intake on H-1: FS-C bottles and MFCs emulate "
                                                                      "the delivered feed at the valve outlet (IF-A5)"},
             line_items=[dict(id="R01.m_intake", param_id="H27-01", name="intake structure (collector / collimator)",
                              mass_class="dry", cbe=tbd("Vyovrinda intake geometry (feed_state_closure owner decisions "
                                                        "DI-1.1 area sizing rule, DI-1.2 intake geometry) and a sourced "
                                                        "material density, or a measured mass"))]),
        dict(row_id="R02", a5_subsystem=names[1], mass_bom_items=["filter"], flight_status=FR,
             h1_counterpart={"items": ["FS-C"], "status": GO, "note": "no filter on H-1"},
             line_items=[dict(id="R02.m_filter", param_id="H27-02", name="protective / filter stage", mass_class="dry",
                              cbe=tbd("a filter concept and geometry (the code lumps the filter into the intake; "
                                      "docs/interfaces/UPSTREAM_ICD.md IF-A1) or a measured mass"))]),
        dict(row_id="R03", a5_subsystem=names[2], mass_bom_items=["compressor"], flight_status=FR,
             h1_counterpart={"items": ["FS-C"], "status": GO, "note": "no compressor on H-1"},
             line_items=[dict(id="R03.m_compressor", param_id="H27-03", name="compressor incl. motor and isolation valve",
                              mass_class="dry",
                              cbe=tbd("DI-1.4 compressor concept freeze and an ABEP-scale design or breadboard mass "
                                      "(compressor_downselect_v1: mass TBD for every surveyed concept; primary PROPOSED "
                                      "concept C1)"))]),
        dict(row_id="R04", a5_subsystem=names[3], mass_bom_items=["atmospheric_gas_chamber"], flight_status=FR,
             h1_counterpart={"items": ["FS-C"], "status": GO, "note": "FS-C manifold stands in for the plenum"},
             line_items=[dict(id="R04.m_plenum", param_id="H27-04", name="buffer / plenum vessel", mass_class="dry",
                              cbe=tbd("plenum volume, pressure and wall material (DI-1.5)", "H2-3"))]),
        dict(row_id="R05", a5_subsystem=names[4], mass_bom_items=["atmospheric_valve"], flight_status=FR,
             h1_counterpart={"items": ["FS-C"], "status": GO, "note": "FS-C MFCs meter the anode gas on the ground"},
             line_items=[dict(id="R05.m_atm_valve", param_id="H27-05", name="atmospheric metering + isolation valves",
                              mass_class="dry",
                              cbe=tbd("low-pressure atmospheric metering valve concept (the accessed Xe valves are "
                                      "specified for 2.8-186 bar inlet and are not a transferable analog)", "H2-3"))]),
        dict(row_id="R06", a5_subsystem=names[5], mass_bom_items=["xe_tank", "xe_load", "xe_residual"],
             flight_status=FR,
             h1_counterpart={"items": ["FS-C"], "status": GO, "note": "Xe bottles and MFCs on the ground"},
             line_items=[
                 dict(id="R06.m_Xe_cathode", param_id="H27-06", name="Xe load: cathode design term (A5 / A6)",
                      mass_class="propellant", xe_term="m_cathode", cbe={"kind": "fixed_design_term"}),
                 dict(id="R06.m_Xe_other", param_id="H27-07",
                      name="Xe load: m_startup + m_transition + m_fallback + m_reserve", mass_class="propellant",
                      xe_term="m_startup + m_transition + m_fallback + m_reserve",
                      cbe=tbd("xe_ledger_v1 terms N_starts, t_startup, mdot_startup, N_transitions, t_transition, "
                              "mdot_transition, t_fallback_max, mdot_fallback, reserve_policy (A6: not freezable "
                              "without H-1/C-1 evidence)")),
                 dict(id="R06.m_Xe_residual", param_id="H27-08",
                      name="Xe residuals (policy fraction of the Xe load; known part only)", mass_class="propellant",
                      xe_term="(outside the five-term ledger; mass_bom xe_residual)",
                      cbe={"kind": "fraction_of_item", "of": ["R06.m_Xe_cathode", "R06.m_Xe_other"]}),
                 dict(id="R06.m_tank", param_id="H27-09", name="Xe tank", mass_class="dry", xe_term="m_tank",
                      cbe={"kind": "analog_range", "low": "AN-MT-XSXTA", "high": "AN-MT-SXTA40"}),
                 dict(id="R06.m_mounting_thermal", param_id="H27-10", name="Xe tank mounting and thermal hardware",
                      mass_class="dry", xe_term="m_mounting/thermal",
                      cbe=tbd("tank selection, launch loads and the tank thermal-control design", "H2-5")),
             ]),
        dict(row_id="R07", a5_subsystem=names[6], mass_bom_items=["xe_valve_and_flow_control"], flight_status=FR,
             h1_counterpart={"items": ["FS-C"], "status": GO, "note": "bottle regulators are facility hardware"},
             line_items=[dict(id="R07.m_regulator", param_id="H27-11", name="Xe pressure regulator", mass_class="dry",
                              xe_term="m_regulator",
                              cbe={"kind": "analog_range", "low": "AN-MOOG-XFC", "high": "AN-XRFS"})]),
        dict(row_id="R08", a5_subsystem=names[7], mass_bom_items=["xe_valve_and_flow_control"], flight_status=FR,
             h1_counterpart={"items": ["FS-C"], "status": GO, "note": "Xe anode and Xe cathode MFCs on the ground"},
             line_items=[
                 dict(id="R08.m_valves", param_id="H27-12",
                      name="Xe metering: isolation latch valve + proportional flow control valve per branch",
                      mass_class="dry", xe_term="m_valves", cbe={"kind": "derived_valves"}),
                 dict(id="R08.m_plumbing", param_id="H27-13", name="Xe plumbing, filters, fittings, pressure transducers",
                      mass_class="dry", xe_term="m_plumbing",
                      cbe=tbd("Xe line routing, lengths and component selection", "H2-3")),
             ]),
        dict(row_id="R09", a5_subsystem=names[8], mass_bom_items=["hall_thruster_head"], flight_status=FR,
             h1_counterpart={"items": ["H-1"], "status": FR,
                             "note": "H-1 is the flight-representative test article; test-article-only provisions "
                                     "(thermocouple points, diagnostic ports) are excluded from the flight row"},
             line_items=[dict(id="R09.m_hall_head_incl_mc", param_id="H27-14",
                              name="Hall discharge chamber/accelerator INCLUDING magnetic circuit (analog thrusters "
                                   "are quoted with their magnetic circuit)", mass_class="dry",
                              cbe={"kind": "analog_range", "low": "AN-BHT600-THR", "high": "AN-BHT1500-THR"},
                              pending_lane="H2-1")]),
        dict(row_id="R10", a5_subsystem=names[9], mass_bom_items=["hall_magnets"], flight_status=FR,
             h1_counterpart={"items": ["MC-1"], "status": FR, "note": "coil supplies are PS-C (ground)"},
             line_items=[dict(id="R10.m_magnetic_circuit", param_id="H27-15",
                              name="magnetic circuit (coils / magnets, pole pieces, yoke)", mass_class="dry",
                              cbe={"kind": "included_in", "item": "R09.m_hall_head_incl_mc"}, pending_lane="H2-1")]),
        dict(row_id="R11", a5_subsystem=names[10], mass_bom_items=["cathode"], flight_status=FR,
             h1_counterpart={"items": ["C-1"], "status": FR, "note": "C-1 supplies are PS-C (ground)"},
             line_items=[
                 dict(id="R11.m_cathode_unit", param_id="H27-16", name="hollow cathode unit (with heater and keeper)",
                      mass_class="dry", cbe={"kind": "analog_range", "low": "AN-BHT600-CATH", "high": "AN-BHT1500-CATH"},
                      pending_lane="H2-2"),
                 dict(id="R11.m_cathode_shield_mount", param_id="H27-17",
                      name="cathode shield / O-isolation / mount", mass_class="dry",
                      cbe=tbd("cathode location, shielding and isolation design", "H2-2")),
             ]),
        dict(row_id="R12", a5_subsystem=names[11], mass_bom_items=["ppu"], flight_status=FR,
             h1_counterpart={"items": ["PS-C"], "status": GO, "note": "laboratory supplies on the ground"},
             line_items=[dict(id="R12.m_ppu", param_id="H27-18", name="PPU / power distribution",
                              mass_class="dry", cbe={"kind": "analog_range", "low": "AN-NASA-LM-PPU-TARGET",
                                                     "high": "AN-TAS-PPUMK1-MASS"}, pending_lane="H2-4")]),
        dict(row_id="R13", a5_subsystem=names[12], mass_bom_items=["thermal_hardware"], flight_status=FR,
             h1_counterpart={"items": ["H-1"], "status": TA, "note": "facility thermal environment differs"},
             line_items=[dict(id="R13.m_thermal", param_id="H27-19",
                              name="thermal-control hardware (radiators, heaters, MLI, heat paths)", mass_class="dry",
                              cbe=tbd("thermal network, rejection area and materials", "H2-5"))]),
        dict(row_id="R14", a5_subsystem=names[13], mass_bom_items=["ppu"], flight_status=FR,
             h1_counterpart={"items": ["PS-C"], "status": GO, "note": "laboratory sequencing and interlocks"},
             line_items=[dict(id="R14.m_control_fdir", param_id="H27-20", name="control / FDIR electronics",
                              mass_class="dry", cbe={"kind": "included_in", "item": "R12.m_ppu"},
                              pending_lane="H2-4")]),
        dict(row_id="R15", a5_subsystem=names[14], mass_bom_items=[], flight_status=FR,
             h1_counterpart={"items": ["INS-01..INS-24"], "status": GO,
                             "note": "H-1 ground diagnostics are EXCLUDED from the flight mass model (listed below)"},
             line_items=[dict(id="R15.m_flight_sensors", param_id="H27-21",
                              name="flight telemetry sensors (flight subset only)", mass_class="dry",
                              cbe=tbd("flight sensor selection for the telemetry subset TM-01..TM-10", "H2-6"))]),
        dict(row_id="R16", a5_subsystem=names[15], mass_bom_items=["structure"], flight_status=FR,
             h1_counterpart={"items": ["H-1"], "status": TA, "note": "thrust-stand mount is facility hardware"},
             line_items=[dict(id="R16.m_structure", param_id="H27-22",
                              name="propulsion-module structure, brackets, spacecraft interface", mass_class="dry",
                              cbe=tbd("spacecraft configuration and launch-load environment (not defined in the "
                                      "repository) and a structural design"))]),
        dict(row_id="R17", a5_subsystem="RF pre-ionization module interface (A5 reserved_interface)",
             mass_bom_items=[], flight_status=FR, reserved_interface=True,
             h1_counterpart={"items": ["IP-UP", "IP-DN", "PIM-0"], "status": TA,
                             "note": "PIM-0 spacer is H-1 test-article-only; the interface geometry is reserved in "
                                     "the flight design, the module is not baseline flight hardware"},
             line_items=[dict(id="R17.m_interface_provision", param_id="H27-23",
                              name="flight interface provision (flange / spacer length, connector and gas-port "
                                   "provisions); NO module hardware", mass_class="dry",
                              cbe=tbd("pre-ionizer module ICD mechanical envelope and flight interface definition",
                                      "PIM-ICD"))]),
        dict(row_id="SYS-H", a5_subsystem="(system-level) harness", mass_bom_items=["harness"], flight_status=FR,
             system_level=True, h1_counterpart={"items": ["SVC-1"], "status": GO, "note": "stand service lines"},
             line_items=[dict(id="SYS-H.m_harness", param_id="H27-24",
                              name="harness (policy allocation on the nominal dry mass)", mass_class="dry",
                              cbe={"kind": "fraction_of_nominal_dry"})]),
    ]
    for r in rows:
        r["a5_group"] = grp.get(r["a5_subsystem"], "reserved_interface" if r.get("reserved_interface") else "system")
    return rows


def resolve_cbe(li: dict, ctx: dict) -> dict:
    """Return {'low','high','basis','evidence_class','sources','status', ...} for a non-derived-of-others item."""
    c = li["cbe"]
    k = c["kind"]
    if k == "analog_range":
        lo, hi = analog_kg(c["low"]), analog_kg(c["high"])
        if not 0 <= lo <= hi:
            raise ValueError(f"{li['id']}: bad analog range {lo}..{hi}")
        lane = li.get("pending_lane")
        return dict(low=lo, high=hi, basis="analog", evidence_class="inferred",
                    analogs=[c["low"], c["high"]],
                    status=("PRELIMINARY (analog planning range; " + pending(lane) + ")") if lane else
                    "PRELIMINARY (analog planning range)",
                    note="published masses of other hardware transferred as a planning range (evidence class of the "
                         "transfer: inferred); never a prediction of Vyovrinda hardware")
    if k == "derived_valves":
        per = sum(n * analog_kg(a) for a, n in VALVES_PER_BRANCH.items())
        m = N_XE_BRANCHES * per
        return dict(low=m, high=m, basis="derived", evidence_class="inferred", analogs=list(VALVES_PER_BRANCH),
                    formula=f"N_branches ({N_XE_BRANCHES}) x sum(count x manufacturer max mass) = "
                            f"{N_XE_BRANCHES} x ({' + '.join(f'{n} x {analog_kg(a):.3f}' for a, n in VALVES_PER_BRANCH.items())}) kg",
                    status="PRELIMINARY (PROPOSED minimal single-string set; " + pending("H2-3") + ")",
                    note="applicability gap: the published PFCV range '0 - 30 mg/s Xe typical' does not show control "
                         "at the 0.10 mg/s cathode design flow (H3 specification gap)")
    if k == "fixed_design_term":
        m = ctx["m_cathode_kg"]
        return dict(low=m, high=m, basis="allocation", evidence_class="assumed",
                    formula=ctx["cathode_arithmetic"],
                    status="FIXED_DESIGN_TERM (A5 allocation; not a demonstrated flow)",
                    note="the only fixed Xe design term (A5 xe_mass_allocation; xe_ledger_v1 cathode_term.design_term)")
    if k == "included_in":
        return dict(low=0.0, high=0.0, basis="analog", evidence_class="inferred", included_in=c["item"],
                    status="PRELIMINARY (0 kg additional: included in " + c["item"] + " analog; "
                           + pending(li["pending_lane"]) + " for the split)",
                    note="booked inside the parent analog to avoid double counting; the split is an H2 deliverable")
    if k == "tbd":
        lane = c.get("pending_lane")
        st = ("TBD - requires " + c["requires"]) + ((" (" + pending(lane) + ")") if lane else "")
        return dict(low=None, high=None, basis="pending" if lane else "TBD", evidence_class=None, status=st,
                    requires=c["requires"], pending_lane=LANES[lane][1] + "/" if lane else None)
    raise ValueError(f"{li['id']}: unresolvable kind {k} here")


def lane_consumption(lane_root: Path | None) -> dict:
    """Scan the parallel-lane directories (lazily). A demand to H2-7 is ADOPTED only if it satisfies the contract."""
    out = {"lane_root": "repository checkout" if lane_root is None else "external preview root (not committed)",
           "contract": ("A demand is ADOPTED only if: (1) its 'to' names H2-7 (" + ", ".join(H27_ALIASES) + "); "
                        "(2) 'h2_7_line_item' names an existing line item id; (3) 'units' == 'kg'; (4) numeric "
                        "'value' >= 0 or 'range' [lo, hi] with 0 <= lo <= hi; (5) 'status' does not start with "
                        "PENDING or TBD; (6) 'evidence_class' is one of the six docs/EVIDENCE.md classes and 'basis' "
                        "is non-empty. It then replaces that line item's CBE (basis 'preliminary geometry from "
                        "<lane>'); the analog range is kept as 'superseded_analog'. Other demands to H2-7 are listed "
                        "unadopted for the integration pass."),
           "lanes": {}, "demands": []}
    for key, (lane, rel) in LANES.items():
        d = (lane_root or REPO) / rel
        if not d.is_dir():
            out["lanes"][key] = {"lane": lane, "path": rel + "/", "state": "ABSENT", "status": pending(key)}
            continue
        files = sorted(p for p in d.glob("*.json") if p.is_file())
        rec = {"lane": lane, "path": rel + "/", "state": "PRESENT",
               "files": [{"name": p.name, "sha256_observed": sha256_file(p)} for p in files]}
        n = 0
        for p in files:
            try:
                doc = json.loads(p.read_text())
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                rec.setdefault("unreadable", []).append({"name": p.name, "error": type(e).__name__})
                continue
            dem = doc.get("interface_demands") if isinstance(doc, dict) else None
            if not isinstance(dem, list):
                continue
            for x in dem:
                if not isinstance(x, dict):
                    continue
                to = str(x.get("to", ""))
                if not any(a in to for a in H27_ALIASES):
                    continue
                n += 1
                out["demands"].append({"lane": key, "file": p.name, "demand": x})
        rec["n_demands_to_h2_7"] = n
        out["lanes"][key] = rec
    return out


def adopt(demand: dict, line_ids: set) -> tuple[bool, str]:
    x = demand
    lid = x.get("h2_7_line_item")
    if lid not in line_ids:
        return False, "no 'h2_7_line_item' naming an existing line item"
    if x.get("units") != "kg":
        return False, "units are not 'kg'"
    st = str(x.get("status", ""))
    if not st or st.upper().startswith(("PENDING", "TBD")):
        return False, "status is PENDING/TBD or missing"
    if x.get("evidence_class") not in EVIDENCE_CLASSES:
        return False, "evidence_class missing or not one of the six classes"
    if not str(x.get("basis", "")).strip():
        return False, "basis missing"
    v, r = x.get("value"), x.get("range")
    if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0:
        return True, "value"
    if (isinstance(r, list) and len(r) == 2 and all(isinstance(t, (int, float)) and not isinstance(t, bool)
                                                   and math.isfinite(t) for t in r) and 0 <= r[0] <= r[1]):
        return True, "range"
    return False, "no numeric value >= 0 or valid range"


def rollup(lines: dict, mga_of: dict, sm: float, f_h: float, case: str) -> dict:
    """Partial roll-up over resolved lines for one case ('low' / 'high'). Mirrors mass_bom.rollup: harness is the
    fraction f_h of the TOTAL nominal dry mass (harness included); system margin = sm x nominal dry; propellant carries
    neither MGA nor system margin."""
    dry_nom, dry_cbe, prop, missing = 0.0, 0.0, 0.0, []
    for lid, ln in lines.items():
        if lid == "SYS-H.m_harness":
            continue
        v = ln[case]
        if v is None:
            missing.append(lid)
            continue
        if ln["mass_class"] == "propellant":
            prop += v
        else:
            dry_cbe += v
            dry_nom += v * (1.0 + mga_of[lid])
    harness = f_h / (1.0 - f_h) * dry_nom  # harness MGA 0 (policy_allocation_nominal)
    nom = dry_nom + harness
    smk = sm * nom
    mev = nom + smk + prop
    return {"case": case, "complete": not missing, "n_tbd_lines": len(missing), "tbd_lines": missing,
            "cbe_dry_kg": dry_cbe + harness, "cbe_dry_excl_harness_kg": dry_cbe, "mga_kg": dry_nom - dry_cbe,
            "harness_kg": harness, "nominal_dry_kg": nom, "system_margin_fraction": sm, "system_margin_kg": smk,
            "propellant_kg": prop, "cbe_total_kg": dry_cbe + harness + prop,
            "mev_known_lines_kg": mev,
            "note": "sums over resolved lines only; NOT an MEV of the system while TBD lines exist"}


def build_document(repo: Path = REPO, lane_root: Path | None = None) -> dict:
    od = load_pinned(repo, "OD")
    a5 = load_pinned(repo, "A5")
    a6 = load_pinned(repo, "A6")
    a7 = load_pinned(repo, "A7")
    g0 = load_pinned(repo, "G0")
    mb = load_pinned(repo, "MASSBOM")
    hw = load_pinned(repo, "HWDEF")
    xl = load_pinned(repo, "XELEDGER")
    w4 = load_pinned(repo, "W4")
    cds = load_pinned(repo, "CDS")
    del od
    if g0.get("verdict") != "CLEAN" or g0.get("a5_sha256") != PINS["A5"][1]:
        raise ValueError("G0 baseline is not CLEAN for the pinned A5")

    # ---- values read from pinned inputs (never retyped)
    mass_alloc = a5_alloc(a5, "system mass design allocation")
    alloc_lo, alloc_hi = parse_range_kg(mass_alloc["value"])
    rfp_mass = float(hw["rfp_basis"]["mass_max_kg"]["value"])
    if rfp_mass != float(mb["plausibility_screen"]["threshold_kg"]):
        raise ValueError("RFP mass differs between HWDEF and mass BOM")
    firing_h = parse_hours(a5_alloc(a5, "firing life")["value"])
    design_life_h = parse_hours(a5_alloc(a5, "internal design life target")["value"])
    mdot_c = float(a5["xe_mass_allocation"]["cathode_flow_design_target_mg_s"])
    mdot_c_up = float(a5["xe_mass_allocation"]["cathode_flow_experimental_upper_test_point_mg_s"])
    ref = a5["xe_mass_allocation"]["reference_arithmetic_15000h"]
    m_cath = mdot_c * UNIT["KG_PER_MG"] * firing_h * UNIT["S_PER_H"]
    m_cath_up = mdot_c_up * UNIT["KG_PER_MG"] * firing_h * UNIT["S_PER_H"]
    if not (math.isclose(m_cath, ref["0.10_mg_s_kg"], rel_tol=1e-9) and
            math.isclose(m_cath_up, ref["0.15_mg_s_kg"], rel_tol=1e-9) and
            math.isclose(m_cath, xl["cathode_term"]["design_term"]["m_cathode_kg"], rel_tol=1e-9)):
        raise ValueError("cathode Xe term disagrees with A5 / xe_ledger")
    m_cath_life = mdot_c * UNIT["KG_PER_MG"] * design_life_h * UNIT["S_PER_H"]
    cats = mb["margin_policy"]["maturity_categories"]
    mga_d = float(cats["ecss_d_new_or_major_modification"]["mga"])
    mga_p = float(cats["propellant_not_equipment"]["mga"])
    sm_prop = float(mb["system_margin"]["proposed_fraction"])
    sm_alt = [float(a["fraction"]) for a in mb["system_margin"]["alternatives"]]
    items = {it["id"]: it for it in mb["items"]}
    f_h = float(items["harness"]["cbe"]["fraction"]["value"])
    f_res = float(items["xe_residual"]["cbe"]["fraction"]["value"])
    ctx = {"m_cathode_kg": m_cath,
           "cathode_arithmetic": f"{mdot_c} mg/s x 1e-6 kg/mg x {firing_h:.0f} h x 3600 s/h = {m_cath:.6g} kg"}

    # ---- rows and line items
    rows = row_specs(a5)
    for r in rows:
        for mbi in r["mass_bom_items"]:
            if mbi not in items:
                raise ValueError(f"{r['row_id']}: unknown mass_bom item {mbi}")
    lines: dict[str, dict] = {}
    for r in rows:
        for li in r["line_items"]:
            if li["cbe"]["kind"] in ("fraction_of_item", "fraction_of_nominal_dry"):
                continue
            res = resolve_cbe(li, ctx)
            lines[li["id"]] = dict(res, mass_class=li["mass_class"])
    # consumption of parallel lanes (lazy)
    cons = lane_consumption(lane_root)
    all_ids = {li["id"] for r in rows for li in r["line_items"]}
    adoptable = {i for i in all_ids if lines.get(i, {}).get("basis") not in ("allocation",)} - {
        "R06.m_Xe_residual", "SYS-H.m_harness"}
    adopted = []
    for d in cons["demands"]:
        ok, why = adopt(d["demand"], adoptable)
        d["adopted"], d["reason"] = ok, why
        if ok:
            x, lid = d["demand"], d["demand"]["h2_7_line_item"]
            lo, hi = (x["value"], x["value"]) if why == "value" else tuple(x["range"])
            prev = {k: lines[lid].get(k) for k in ("low", "high", "basis", "status", "analogs")}
            lines[lid].update(low=float(lo), high=float(hi), basis="preliminary geometry from " + d["lane"],
                              evidence_class=x["evidence_class"], status="PRELIMINARY (adopted from "
                              + LANES[d["lane"]][1] + "/)", superseded_analog=prev, adopted_from=d["lane"])
            adopted.append(lid)
    # residual: policy fraction of the Xe load (known part only while m_Xe_other is TBD)
    xe_known = [lines[i]["low"] for i in ("R06.m_Xe_cathode", "R06.m_Xe_other") if lines[i]["low"] is not None]
    res_m = f_res * sum(xe_known)
    lines["R06.m_Xe_residual"] = dict(low=res_m, high=res_m, basis="derived", evidence_class="assumed",
                                      mass_class="propellant",
                                      formula=f"{f_res} x (known Xe load {sum(xe_known):.6g} kg); grows with m_Xe_other",
                                      status="PRELIMINARY (policy fraction on the known Xe load only; a floor)",
                                      note="mass_bom_v1 xe_residual: ESA R-M1-6 2 % of propellant (as cited there); "
                                           "outside the five-term xe_ledger (owner question H27-Q6)")
    lines["SYS-H.m_harness"] = dict(low=None, high=None, basis="derived", evidence_class="assumed", mass_class="dry",
                                    formula=f"{f_h} of the total nominal dry mass (mass_bom_v1 harness, ESA R-M1-7 as "
                                            f"cited there); computed per case in the roll-up",
                                    status="PRELIMINARY (policy allocation; computed on the known dry lines only)")
    mga_of = {}
    for r in rows:
        for li in r["line_items"]:
            lid = li["id"]
            if li["mass_class"] == "propellant":
                mga_of[lid], cat = mga_p, "propellant_not_equipment"
            elif lid == "SYS-H.m_harness":
                mga_of[lid], cat = float(cats["policy_allocation_nominal"]["mga"]), "policy_allocation_nominal"
            else:
                mga_of[lid], cat = mga_d, "ecss_d_new_or_major_modification"
            ln = lines[lid]
            ln["maturity_category"] = cat
            ln["maturity_status"] = "PROPOSED (mass_bom_v1 OD-M2: ECSS D for every dry equipment item until a part " \
                                    "is selected)" if cat.startswith("ecss") else "per mass_bom_v1 margin policy"
            ln["mga"] = mga_of[lid]
            for case in ("low", "high"):
                v = ln[case]
                ln["mev_" + case + "_kg"] = None if v is None else v * (1.0 + mga_of[lid])
            li["resolved"] = ln

    # ---- roll-ups
    cases = {}
    for sm_name, sm in [("proposed_20pct", sm_prop)] + [(f"alt_{int(round(s * 100))}pct", s) for s in sm_alt]:
        cases[sm_name] = {c: rollup(lines, mga_of, sm, f_h, c) for c in ("low", "high")}
    base = cases["proposed_20pct"]
    for c in ("low", "high"):
        lines["SYS-H.m_harness"][c] = base[c]["harness_kg"]
        lines["SYS-H.m_harness"]["mev_" + c + "_kg"] = base[c]["harness_kg"]
    refs = [("A5_alloc_34kg", alloc_lo, "allocation (A5 lower end)"),
            ("A5_alloc_36kg", alloc_hi, "allocation (A5 upper end)"),
            ("RFP_40kg", rfp_mass, "requirement (RFP as recorded; verify)")]
    factor = (1.0 + mga_d) * (1.0 + sm_prop) / (1.0 - f_h)
    checks = []
    for rid, val, kind in refs:
        for c in ("low", "high"):
            mev = base[c]["mev_known_lines_kg"]
            margin = val - mev
            checks.append({"reference": rid, "reference_kg": val, "kind": kind, "case": c,
                           "mev_known_lines_kg": mev, "remaining_kg": margin,
                           "remaining_share": margin / val,
                           "cbe_available_to_tbd_dry_lines_kg": margin / factor if margin > 0 else 0.0,
                           "state": ("OPEN_PARTIAL (known lines inside the reference; %d TBD lines remain)"
                                     % base[c]["n_tbd_lines"]) if margin > 0 else
                           "KNOWN_LINES_EXCEED_REFERENCE (planning case, not a lower bound: no veto)"})
    contrib = []
    for lid, ln in lines.items():
        if ln["low"] is None:
            contrib.append({"line_item": lid, "spread_mev_kg": None, "kind": "UNBOUNDED (TBD)",
                            "status": ln["status"]})
        elif ln["high"] > ln["low"]:
            k = factor if ln["mass_class"] == "dry" else 1.0
            contrib.append({"line_item": lid, "spread_mev_kg": (ln["high"] - ln["low"]) * k,
                            "kind": "analog planning spread x (1+MGA)(1+system margin)/(1-harness fraction)",
                            "cbe_low_kg": ln["low"], "cbe_high_kg": ln["high"]})
    contrib.sort(key=lambda x: (x["spread_mev_kg"] is not None, -(x["spread_mev_kg"] or 0.0), x["line_item"]))
    bounded = [c for c in contrib if c["spread_mev_kg"] is not None]
    floor = lines["R06.m_Xe_cathode"]["low"] + lines["R06.m_Xe_residual"]["low"]

    # ---- Xe subsystem (A6 decomposition)
    xe_terms = [("m_Xe (cathode, fixed)", "R06.m_Xe_cathode"), ("m_Xe (startup+transition+fallback+reserve)",
                                                                  "R06.m_Xe_other"),
                ("m_Xe residual (policy, outside ledger)", "R06.m_Xe_residual"), ("m_tank", "R06.m_tank"),
                ("m_regulator", "R07.m_regulator"), ("m_valves", "R08.m_valves"), ("m_plumbing", "R08.m_plumbing"),
                ("m_mounting/thermal", "R06.m_mounting_thermal")]
    xe_rows = [{"term": t, "line_item": lid, "cbe_low_kg": lines[lid]["low"], "cbe_high_kg": lines[lid]["high"],
                "status": lines[lid]["status"]} for t, lid in xe_terms]
    xe_known_lo = sum(x["cbe_low_kg"] for x in xe_rows if x["cbe_low_kg"] is not None)
    xe_known_hi = sum(x["cbe_high_kg"] for x in xe_rows if x["cbe_high_kg"] is not None)
    xe_load_known = lines["R06.m_Xe_cathode"]["low"] * (1 + f_res)
    rho = dict(zip(ANALOG_PRESSURES_BAR, ANALOGS["AN-NIST-XE-RHO"]["value"]))
    vol = [{"p_bar": p, "rho_kg_m3": rho[p], "V_l": xe_load_known / rho[p] / UNIT["M3_PER_L"]}
           for p in ANALOG_PRESSURES_BAR]
    cap7 = [{"p_bar": p, "capacity_kg_7l": 7.0 * UNIT["M3_PER_L"] * rho[p]} for p in ANALOG_PRESSURES_BAR]

    xe_block = {
        "a6_text": a6["authorized_now"]["fo_xe_system_ledger"],
        "m_Xe_subsystem_definition": "m_Xe + m_tank + m_regulator + m_valves + m_plumbing + m_mounting/thermal (A6)",
        "linked_ledger": {"path": PINS["XELEDGER"][0], "sha256": PINS["XELEDGER"][1],
                          "state": xl["status"], "ledger_missing_terms": xl["ledger_state"]["missing"],
                          "m_Xe_total_value_A5": a5["xe_mass_allocation"]["m_Xe_total_value"]},
        "fixed_design_term": {"mdot_mg_s": mdot_c, "t_firing_h": firing_h, "m_cathode_kg": m_cath,
                              "arithmetic": ctx["cathode_arithmetic"],
                              "status": "the ONLY fixed Xe design term (A5 allocation, not a demonstrated flow)"},
        "terms": xe_rows,
        "known_lines_cbe_kg": {"low": xe_known_lo, "high": xe_known_hi,
                               "note": "Sum of the known lines only; NOT m_Xe_subsystem (xe_ledger refuses it while TBD terms "
                                       "exist; A6 not_authorized: freezing total Xe mass)"},
        "sensitivities": {
            "upper_test_point_0p15": {"m_cathode_kg": m_cath_up, "delta_kg": m_cath_up - m_cath,
                                      "status": "A5 test point only; never the allocation"},
            "design_life_target": {"t_h": design_life_h, "m_cathode_kg": m_cath_life,
                                   "delta_kg": m_cath_life - m_cath,
                                   "status": "sensitivity only; A5 books the term over the RFP 15,000 h "
                                             "(xe_ledger OD-XE-5)"}},
        "storage_volume_for_known_load": {"load_kg": xe_load_known,
                                          "basis": "cathode term + policy residual at 293.15 K (storage temperature "
                                                   "is a parameter: PENDING docs/hardware/h2/h2_5_thermal_network/)",
                                          "rows": vol},
        "xs_xta_capacity_check": {"volume_l": 7.0, "rows": cap7,
                                  "statement": "A 7 l tank holds the known load at every tabulated pressure >= 75 bar; "
                                               "the XS-XTA MEOP is blank in the catalogue, so a MEOP >= 75 bar at the "
                                               "maximum storage temperature is a PROPOSED procurement requirement "
                                               "(H3-01), and the total load stays PENDING the ledger"},
    }

    # ---- diagnostics
    ins = [{"id": x["id"], "name": x.get("name"), "flight_status": "GROUND/FACILITY-ONLY",
            "in_flight_mass_model": False} for x in w4["instruments"]]
    telemetry = [
        ("TM-01", "discharge voltage and current", "R12 (inside PPU)", "INS-04"),
        ("TM-02", "magnet coil current(s) (none if permanent magnets)", "R12 (inside PPU)", "INS-24"),
        ("TM-03", "cathode keeper and heater voltage / current", "R12 (inside PPU)", None),
        ("TM-04", "Xe tank pressure", "R15", None),
        ("TM-05", "Xe tank temperature (Xe density near the critical region is temperature-sensitive)", "R15", None),
        ("TM-06", "regulated Xe pressure (regulator outlet)", "R15", None),
        ("TM-07", "plenum / feed pressure P_feed (flight low-pressure sensing is a specification gap)", "R15",
         "INS-06"),
        ("TM-08", "feed temperature T_feed", "R15", "INS-07"),
        ("TM-09", "thruster body / magnet / PPU baseplate temperatures", "R15", "INS-17"),
        ("TM-10", "compressor speed and motor current", "R15", None),
    ]
    diag = {"flight_telemetry_subset_IN": [{"id": a, "quantity": b, "carrier_row": c, "ground_counterpart": d,
                                            "status": "PROPOSED", "flight_status": "FLIGHT-REPRESENTATIVE"}
                                           for a, b, c, d in telemetry],
            "h1_ground_diagnostics_EXCLUDED": ins,
            "rule": "only the flight telemetry subset is carried (R15, or inside the PPU); every H-1 ground instrument "
                    "INS-01..INS-24 (docs/experiments/instrumentation/instrumentation_definition_v1.json) is excluded "
                    "from the flight mass model; their stand mass is an H2-6 fixture input (ID-09)"}

    # ---- mechanical envelope
    env = {
        "overall_volume_and_length": {
            "status": "TBD - requires preliminary geometry from H2-1..H2-5, the intake design (DI-1.1 / DI-1.2) and "
                      "the compressor concept (DI-1.4); the intake frontal area and the axial stack intake -> "
                      "compressor -> plenum -> valve -> [pre-ionizer interface] -> H-1 set the length",
            "analog_envelopes": [
                {"item": "Hall head (analog)", "analog": "AN-PPS1350-DIMS", "value_mm": ANALOGS["AN-PPS1350-DIMS"]["value"],
                 "note": "PPS1350 drawing 'max' labels; axis assignment: verify"},
                {"item": "extended channel (analog)", "analog": "AN-ECHT-GEOM", "value_mm": ANALOGS["AN-ECHT-GEOM"]["value"],
                 "note": "ECHT BN chamber length / channel width / OD; published analog only"},
                {"item": "PPU (analog)", "analog": "AN-TAS-PPUMK1-DIMS", "value_mm": ANALOGS["AN-TAS-PPUMK1-DIMS"]["value"],
                 "box_volume_l": math.prod(ANALOGS["AN-TAS-PPUMK1-DIMS"]["value"]) * 1e-6},
                {"item": "Xe tank (analog, small family)", "analog": "AN-MT-XSXTA-ENV",
                 "value_mm": ANALOGS["AN-MT-XSXTA-ENV"]["value"],
                 "cylinder_envelope_volume_l": math.pi / 4 * ANALOGS["AN-MT-XSXTA-ENV"]["value"][0] ** 2
                 * ANALOGS["AN-MT-XSXTA-ENV"]["value"][1] * 1e-6},
            ],
            "flight_status": "FLIGHT-REPRESENTATIVE"},
        "thruster_axis_alignment": {
            "status": "PROPOSED",
            "statement": "thrust axis parallel to the anti-ram direction, collinear with the intake drag axis and passing "
                         "through the spacecraft centre of mass; lateral-offset and angular tolerances TBD - require "
                         "the spacecraft AOCS disturbance-torque budget. The flight mount carries a surveyable alignment "
                         "reference (datum surfaces or optical cube).",
            "flight_status": "FLIGHT-REPRESENTATIVE"},
        "cg_estimate": {
            "status": "NOT_COMPUTABLE",
            "statement": "no line item has a layout position yet (no preliminary geometry, no spacecraft configuration). "
                         "CG = sum(m_i r_i) / sum(m_i) once every mass-bearing line carries a position. Xe depletion "
                         "moves the system CG by dr = m_Xe_used x (r_CG - r_tank) / (M - m_Xe_used); with the fixed "
                         "cathode term the consumed mass is %.4g kg, so a tank centroid offset d from the CG gives "
                         "|dr| = %.4g kg x d / (M - %.4g kg). PROPOSED rule: Xe tank centroid on the thrust axis and "
                         "as close to the spacecraft CG as the layout allows." % (m_cath, m_cath, m_cath),
            "flight_status": "FLIGHT-REPRESENTATIVE"},
        "spacecraft_mounting_interface": [
            {"id": "MI-01", "item": "propulsion-module mounting plane to the spacecraft structure (bolt pattern, "
                                    "fastener size, preload TBD - spacecraft)", "status": "PROPOSED"},
            {"id": "MI-02", "item": "thruster mount with alignment reference and shimming; electrically isolating if the "
                                    "thruster body floats (HWDEF grounding requirements; H2-4)", "status": "PROPOSED"},
            {"id": "MI-03", "item": "thermal interface of the thruster mount (conductive / isolating) per the thermal "
                                    "network (PENDING docs/hardware/h2/h2_5_thermal_network/)", "status": "PENDING"},
            {"id": "MI-04", "item": "Xe tank mount on the module structure near the CG (launch loads TBD)",
             "status": "PROPOSED"},
            {"id": "MI-05", "item": "PPU baseplate on a radiating or spacecraft-conductive surface (PENDING H2-4 / H2-5)",
             "status": "PENDING"},
        ],
        "intake_to_thruster_layout_constraints": [
            {"id": "LC-01", "constraint": "intake faces ram; thruster exhausts anti-ram; one common axis", "status": "PROPOSED"},
            {"id": "LC-02", "constraint": "series order intake -> filter -> compressor -> plenum -> atmospheric metering "
                                          "valve -> IP-UP -> [reserved pre-ionizer interface] -> IP-DN -> H-1 "
                                          "(HALL_INLET_Z0), as in A5 and HWDEF", "status": "PROPOSED"},
            {"id": "LC-03", "constraint": "axial length between IP-UP and IP-DN reserved in the flight layout for the "
                                          "pre-ionizer interface (baseline carries only the interface provision)",
             "status": "PENDING docs/interfaces/preionizer_module/"},
            {"id": "LC-04", "constraint": "plenum close to the thruster inlet to limit line volume and pressure drop",
             "status": "PENDING docs/hardware/h2/h2_3_gas_path_plenum/"},
            {"id": "LC-05", "constraint": "cathode location shielded from the ram flow and from direct atmospheric "
                                          "plume / O exposure (A5 risk 3)",
             "status": "PENDING docs/hardware/h2/h2_2_cathode_integration/"},
            {"id": "LC-06", "constraint": "no exposed structure in the intake field of view or in the plume cone "
                                          "(divergence envelope TBD - requires H-1 plume measurement)", "status": "TBD"},
            {"id": "LC-07", "constraint": "PPU close to the thruster to shorten the discharge harness (PENDING H2-4)",
             "status": "PENDING docs/hardware/h2/h2_4_ppu_bus/"},
            {"id": "LC-08", "constraint": "radiators with a clear view to space, away from the ram face (PENDING H2-5)",
             "status": "PENDING docs/hardware/h2/h2_5_thermal_network/"},
        ],
    }

    # ---- design-parameter table
    dp = []
    for r in rows:
        for li in r["line_items"]:
            ln = lines[li["id"]]
            val = None if ln["low"] is None else ([ln["low"], ln["high"]] if ln["high"] != ln["low"] else ln["low"])
            src = []
            for a in ln.get("analogs", []) or []:
                src.append(f"{a}: {ANALOGS[a]['source']} {ANALOGS[a]['locator']}")
            if li["id"] == "R06.m_Xe_cathode":
                src.append(PINS["A5"][0] + " xe_mass_allocation; " + PINS["XELEDGER"][0] + " cathode_term.design_term")
            if li["id"] == "R06.m_Xe_residual":
                src.append(PINS["MASSBOM"][0] + " items[xe_residual].cbe.fraction")
            if li["id"] == "SYS-H.m_harness":
                src.append(PINS["MASSBOM"][0] + " items[harness].cbe.fraction")
            if ln.get("included_in"):
                src.append("included in " + ln["included_in"])
            if ln["low"] is None:
                src.append("none (TBD)")
            dp.append({"id": li["param_id"], "line_item": li["id"], "name": li["name"], "value": val, "units": "kg",
                       "basis": ln["basis"], "source": src, "evidence_class": ln["evidence_class"],
                       "status": ln["status"], "flight_status": r["flight_status"]})
    extra = [
        ("H27-25", "A5 system mass design allocation", [alloc_lo, alloc_hi], "kg", "allocation",
         [PINS["A5"][0] + " allocations_and_requirements 'system mass design allocation'"], "assumed",
         "ALLOCATION (not a prediction)"),
        ("H27-26", "RFP system mass limit", rfp_mass, "kg", "requirement",
         [PINS["HWDEF"][0] + " rfp_basis.mass_max_kg (verify against the RFP)"], "assumed", "REQUIREMENT"),
        ("H27-27", "maturity growth allowance (dry equipment, ECSS D)", mga_d, "1", "assumed",
         [PINS["MASSBOM"][0] + " margin_policy.maturity_categories.ecss_d_new_or_major_modification"], "assumed",
         "PROPOSED (mass_bom OD-M2)"),
        ("H27-28", "system margin", sm_prop, "1", "assumed", [PINS["MASSBOM"][0] + " system_margin.proposed_fraction"],
         "assumed", "PROPOSED (mass_bom OD-M1; 10 % alternative also reported)"),
        ("H27-29", "harness fraction of nominal dry mass", f_h, "1", "assumed",
         [PINS["MASSBOM"][0] + " items[harness]"], "assumed", "PROPOSED (mass_bom OD-M6)"),
        ("H27-30", "Xe residual fraction", f_res, "1", "assumed", [PINS["MASSBOM"][0] + " items[xe_residual]"],
         "assumed", "PROPOSED (mass_bom policy)"),
        ("H27-31", "number of metered Xe branches", N_XE_BRANCHES, "1", "allocation",
         [PINS["A5"][0] + " architecture.xe_branch 'Xe metering (splits to ignition/transition feed and cathode feed)'"],
         "assumed", "PRELIMINARY (" + pending("H2-3") + ")"),
        ("H27-32", "valves per metered branch (latch + PFCV), single string", sum(VALVES_PER_BRANCH.values()), "1",
         "assumed", ["this lane (PROPOSED minimal set; redundancy owner question H27-Q4)"], "assumed",
         "PRELIMINARY (" + pending("H2-3") + ")"),
        ("H27-33", "Xe storage temperature for the volume sweep", 293.15, "K", "assumed",
         ["this lane (parameter; NIST isotherm read at this temperature)"], "assumed",
         "PRELIMINARY (" + pending("H2-5") + ")"),
        ("H27-34", "PROPOSED minimum Xe tank MEOP for the 7 l capacity check", 75.0, "bar", "assumed",
         ["this lane (lowest tabulated supercritical pressure in AN-NIST-XE-RHO)"], "assumed",
         "PROPOSED (H3-01 procurement requirement)"),
        ("H27-35", "overall module length / volume", None, "mm / l", "pending", ["none"], None,
         "TBD - requires H2-1..H2-5 geometry and the intake / compressor designs"),
        ("H27-36", "CG location", None, "mm", "pending", ["none"], None,
         "TBD - requires line-item positions (NOT_COMPUTABLE)"),
    ]
    for pid, name, val, u, basis, src, ev, st in extra:
        dp.append({"id": pid, "line_item": None, "name": name, "value": val, "units": u, "basis": basis, "source": src,
                   "evidence_class": ev, "status": st, "flight_status": "FLIGHT-REPRESENTATIVE"})

    # ---- contingency modules (never in the baseline total)
    contingency = [
        {"id": "CM-RF", "architecture": "rf_hall", "h1_item": "PIM-RF",
         "name": "RF pre-ionizer module + off-module chain (primary contingency; A5 reserved interface)",
         "mass_bom_items": ["rf_source", "rf_generator", "rf_matching_network"],
         "flight_status": "H-1 TEST-ARTICLE-ONLY (flight hardware only if Phase-1 outcome B)",
         "cbe": None, "status": "TBD - requires RF source, generator and matching-network design or supplier data "
                                "(mass_bom_v1 items TBD); " + pending("PIM-ICD"),
         "in_baseline_total": False},
        {"id": "CM-ECR", "architecture": "ecr_hall", "h1_item": "PIM-ECR",
         "name": "ECR pre-ionizer module + off-module chain (alternate test module only; A5)",
         "mass_bom_items": ["ecr_source", "microwave_source", "waveguide", "ecr_magnets"],
         "flight_status": "H-1 TEST-ARTICLE-ONLY (flight hardware only if Phase-1 outcome C)",
         "cbe": None, "status": "TBD - requires ECR source, microwave generator, transmission line and ECR magnet design "
                                "or supplier data (mass_bom_v1 items TBD); " + pending("PIM-ICD"),
         "in_baseline_total": False},
    ]
    module_room = [{"reference": c["reference"], "case": c["case"],
                    "mev_room_for_module_and_TBD_rows_kg": c["remaining_kg"]} for c in checks]

    # ---- interface demands (both directions)
    L = {k: LANES[k][1] + "/" for k in LANES}
    idem = [
        dict(id="ID-01", **{"from": "H2-7"}, to="H2-1 " + L["H2-1"],
             quantity="mass of the discharge chamber/accelerator and of the magnetic circuit, separately, with basis "
                      "and evidence class (h2_7_line_item R09.m_hall_head_incl_mc / R10.m_magnetic_circuit)",
             value=None, range=[analog_kg("AN-BHT600-THR"), analog_kg("AN-BHT1500-THR")], units="kg",
             status="PENDING " + L["H2-1"]),
        dict(id="ID-02", **{"from": "H2-7"}, to="H2-1 " + L["H2-1"],
             quantity="thruster envelope (max OD, axial length incl. cathode), CG and mounting interface",
             value=None, range=None, units="mm",
             analog="PPS1350 drawing labels 104 / 135 / 210 mm (axis: verify); ECHT channel 86 mm long, 100 mm OD",
             status="PENDING " + L["H2-1"]),
        dict(id="ID-03", **{"from": "H2-7"}, to="H2-2 " + L["H2-2"],
             quantity="cathode unit mass and shield / isolation / mount mass; cathode position envelope",
             value=None, range=[analog_kg("AN-BHT600-CATH"), analog_kg("AN-BHT1500-CATH")], units="kg",
             status="PENDING " + L["H2-2"]),
        dict(id="ID-04", **{"from": "H2-7"}, to="H2-3 " + L["H2-3"],
             quantity="masses of plenum, atmospheric metering/isolation valves, Xe regulator, Xe valves and plumbing; "
                      "line lengths and routing; valve redundancy scheme",
             value=None, range=None, units="kg / mm",
             analog="Xe regulator 0.974-5.9 kg (Moog XFC / ArianeGroup XRFS); Xe metering 0.57 kg (PROPOSED set)",
             status="PENDING " + L["H2-3"]),
        dict(id="ID-05", **{"from": "H2-3"}, to="H2-7",
             quantity="plenum envelope / mass allocation (sets the plenum maximum volume)", value=None,
             range=None, units="kg / m^3",
             status="TBD - requires an owner split of the residual allocation; H2-7 can state only the collective "
                    "room for all TBD rows (rollup.allocation_checks)"),
        dict(id="ID-06", **{"from": "H2-7"}, to="H2-4 " + L["H2-4"],
             quantity="PPU mass incl. control/FDIR electronics and redundancy; PPU envelope; harness lengths and "
                      "currents (to replace the 5 % policy harness)",
             value=None, range=[analog_kg("AN-NASA-LM-PPU-TARGET"), analog_kg("AN-TAS-PPUMK1-MASS")], units="kg",
             status="PENDING " + L["H2-4"]),
        dict(id="ID-07", **{"from": "H2-7"}, to="H2-5 " + L["H2-5"],
             quantity="thermal-control hardware mass (radiator area x areal mass, heaters, MLI); Xe tank thermal "
                      "control and storage-temperature range", value=None, range=None, units="kg / K",
             status="PENDING " + L["H2-5"]),
        dict(id="ID-08", **{"from": "H2-7"}, to="H2-6 " + L["H2-6"],
             quantity="flight telemetry sensor list and masses (TM-01..TM-10); confirmation that H-1 ground "
                      "diagnostics stay out of the flight model", value=None, range=None, units="kg",
             status="PENDING " + L["H2-6"]),
        dict(id="ID-09", **{"from": "H2-7"}, to="H2-6 " + L["H2-6"],
             quantity="installed stand payload mass and CG (H-1 + MC-1 + C-1 + module + diagnostics) for the "
                      "thrust-stand load rating", value=None, range=None, units="kg / mm",
             status="TBD - requires H-1 as-built mass (S1a, HW-ENV-08 inspection)"),
        dict(id="ID-10", **{"from": "H2-7"}, to="PIM-ICD " + L["PIM-ICD"],
             quantity="flight interface-provision mass/envelope at IP-UP/IP-DN; RF and ECR module masses (contingency "
                      "block only)", value=None, range=None, units="kg / mm", status="PENDING " + L["PIM-ICD"]),
        dict(id="ID-11", **{"from": "H2-7"}, to="fo_xe_system_ledger docs/budgets/xe_ledger/",
             quantity="analog planning ranges for m_tank, m_regulator, m_valves (for information; the ledger keeps "
                      "them TBD until a selection)",
             value=None, range=[lines["R06.m_tank"]["low"] + lines["R07.m_regulator"]["low"] + lines["R08.m_valves"]["low"],
                                lines["R06.m_tank"]["high"] + lines["R07.m_regulator"]["high"] + lines["R08.m_valves"]["high"]],
             units="kg", status="PRELIMINARY (analog)"),
        dict(id="ID-12", **{"from": "fo_xe_system_ledger"}, to="H2-7",
             quantity="m_Xe_total (startup, transition, fallback, reserve terms)", value=None, range=None, units="kg",
             status="TBD - requires H-1/C-1 measurements and an owner decision (A6 not_authorized: freezing total Xe "
                    "mass)"),
        dict(id="ID-13", **{"from": "H2-7"}, to="H-1 / MC-1 / C-1 (hardware_requirements_v1)",
             quantity="as-built masses of H-1, MC-1, C-1 and each module at the S1a inspection, with test-article-only "
                      "provisions weighed separately", value=None, range=None, units="kg",
             status="TBD - requires S1a (HW-ENV-08)"),
        dict(id="ID-14", **{"from": "H2-7"}, to="M16 " + L["M16"],
             quantity="mass / envelope attribute state of the 16 A5 subsystems + reserved interface (m16_rows)",
             value=None, range=None, units="-", status="PRELIMINARY (proposed states in m16_rows)"),
    ]

    hic = {
        "result": "NONE_FOUND",
        "checked": [
            {"id": "HI-01", "check": "sourced floor of the system mass vs the 40 kg requirement and the 34-36 kg "
                                     "allocation",
             "evidence": f"floor = fixed cathode Xe term {m_cath:.4g} kg + policy residual "
                         f"{lines['R06.m_Xe_residual']['low']:.4g} kg = {floor:.4g} kg; analog masses are NOT lower "
                         "bounds (Vyovrinda hardware can be lighter or heavier)", "evidence_class": "assumed",
             "finding": "no veto: floor < 34 kg"},
            {"id": "HI-02", "check": "high-end analog planning case vs the references",
             "evidence": "known-line MEV (high case) %.4g kg vs 40 kg; planning spread only" %
                         base["high"]["mev_known_lines_kg"], "evidence_class": "inferred",
             "finding": "not a hard incompatibility (analogs are not bounds); recorded as a mass-closure risk on A5 "
                        "architecture-closing risk 4"},
            {"id": "HI-03", "check": "cathode Xe term at the A5 upper test point 0.15 mg/s",
             "evidence": f"{m_cath_up:.4g} kg (+{m_cath_up - m_cath:.4g} kg)", "evidence_class": "assumed",
             "finding": "no veto; affordability stays with the Xe ledger (A5: test point only)"},
            {"id": "HI-04", "check": "Xe storage volume for the known load vs the smallest accessed tank family",
             "evidence": "%.3g-%.3g l at 75-150 bar (293.15 K) vs XS-XTA 1-7 l" %
                         (vol[-1]["V_l"], vol[0]["V_l"]), "evidence_class": "model-derived",
             "finding": "compatible for the known load; total load PENDING the ledger"},
            {"id": "HI-05", "check": "overall envelope vs a launcher / spacecraft envelope",
             "evidence": "no launcher or spacecraft envelope is defined in the repository", "evidence_class": None,
             "finding": "not checkable (TBD)"},
        ],
        "architecture_veto": False,
    }
    blockers = [
        {"blocker": 1, "text": a7["architecture_changing_blockers"][0], "touched": False,
         "how": "none: the mass model never estimates sustainment; the feed state and the Hall-only knee are H-1 "
                "Phase-1 results"},
        {"blocker": 2, "text": a7["architecture_changing_blockers"][1], "touched": True,
         "how": "mass side only: RF and ECR module masses sit in a separate contingency block (never in the baseline "
                "total) and rollup.module_room shows the MEV room left for any module plus the TBD rows; the power "
                "side is bus_power_boundary_v1's"},
        {"blocker": 3, "text": a7["architecture_changing_blockers"][2], "touched": True,
         "how": "the fixed cathode Xe term is booked explicitly, the complete stored-Xe subsystem is assembled per A6 "
                "(known lines + TBD terms), and the 0.15 mg/s and 18,000 h sensitivities are reported; continuous Xe "
                "augmentation is not a nominal mode and has no mass line"},
    ]

    def m16(rid, name, state, item=None, cat=None, note=""):
        d = {"row_id": rid, "a5_subsystem": name, "attribute": "mass / envelope (H2-7)", "proposed_state": state,
             "note": note}
        if state == "BLOCKED":
            d["blocking_item"], d["rollup_category"] = item, cat
        return d
    n = [r["a5_subsystem"] for r in rows]
    m16_rows = [
        m16("R01", n[0], "BLOCKED", "owner decisions DI-1.1 / DI-1.2 (intake area sizing rule and geometry)",
            "hardware-definition blocker"),
        m16("R02", n[1], "BLOCKED", "filter concept definition (no filter model or geometry in the repository)",
            "hardware-definition blocker"),
        m16("R03", n[2], "BLOCKED", "owner decision DI-1.4 (compressor concept and parameters)",
            "hardware-definition blocker"),
        m16("R04", n[3], "RUNNING", note="plenum sizing in " + L["H2-3"]),
        m16("R05", n[4], "RUNNING", note="valve concept in " + L["H2-3"]),
        m16("R06", n[5], "BLOCKED", "m_Xe_total (startup/transition/fallback/reserve need H-1/C-1 evidence; A6 "
                                     "not_authorized to freeze)", "architecture blocker",
            note="A7 blocker 3; tank analog range carried meanwhile"),
        m16("R07", n[6], "READY", note="analog range in hand; ready for H3 regulator specification once MEOP is set"),
        m16("R08", n[7], "BLOCKED", "a low-flow Xe flow control part demonstrated at 0.10 mg/s (specification gap)",
            "procurement blocker"),
        m16("R09", n[8], "RUNNING", note="H-1 geometry in " + L["H2-1"]),
        m16("R10", n[9], "RUNNING", note="MC-1 sizing in " + L["H2-1"]),
        m16("R11", n[10], "RUNNING", note="C-1 integration in " + L["H2-2"]),
        m16("R12", n[11], "RUNNING", note="PPU / bus allocation in " + L["H2-4"]),
        m16("R13", n[12], "RUNNING", note="thermal network in " + L["H2-5"]),
        m16("R14", n[13], "RUNNING", note="booked inside the PPU analog; split in " + L["H2-4"]),
        m16("R15", n[14], "RUNNING", note="flight telemetry subset PROPOSED here; sensor list with " + L["H2-6"]),
        m16("R16", n[15], "BLOCKED", "spacecraft configuration and launch-load environment (not defined)",
            "proposal-only documentation gap"),
        m16("R17", n[16], "RUNNING", note="interface definition in " + L["PIM-ICD"]),
    ]
    h3 = [
        {"id": "H3-01", "item": "Xe storage tank", "long_lead": True,
         "spec_level_needed": "usable capacity >= m_Xe_total (PENDING ledger) x (1 + residual fraction); internal volume "
                              "from rho(T_storage,max, MEOP); MEOP >= 75 bar PROPOSED; temperature range; envelope; "
                              "mounting (polar or skirt)",
         "reference_data": "MT Aerospace XS-XTA 1-7 l (<= 3.5 kg, 242 mm dia, <= 386 mm, under development); S-XTA 40 l "
                           "(6.3 kg predicted, 73 kg Xe, MEOP 187 bar) - catalogue reference only",
         "status": "TBD - requires m_Xe_total and MEOP"},
        {"id": "H3-02", "item": "Xe pressure regulator", "long_lead": True,
         "spec_level_needed": "inlet range up to MEOP; outlet pressure for the metering valves; flow range covering "
                              "0.10 mg/s cathode + ignition/transition flows; leakage; redundancy",
         "reference_data": "Moog XFC < 974 g (3-23 mg/s); ArianeGroup XRFS < 5.9 kg (3-120 bar in, 2.65 bar out, "
                           "> 6 mg/s)", "status": "PRELIMINARY"},
        {"id": "H3-03", "item": "low-flow Xe proportional flow control for the cathode branch", "long_lead": True,
         "spec_level_needed": "controllable flow at and around 0.10 mg/s and the 0.15 mg/s test point with the accuracy "
                              "the Xe ledger needs",
         "reference_data": "Moog PFCV 115 g max ('0 - 30 mg/s Xe typical'): control at 0.10 mg/s not shown",
         "status": "TBD - specification gap"},
        {"id": "H3-04", "item": "Xe isolation latch valves", "long_lead": False,
         "spec_level_needed": "line size, MEOP, cycle life >= N_starts (PENDING ledger)",
         "reference_data": "Moog 1/8 inch latching < 170 g, 18,000 cycles, MEOP 186 bar", "status": "PRELIMINARY"},
        {"id": "H3-05", "item": "LaB6 hollow cathode (C-1 and flight)", "long_lead": True,
         "spec_level_needed": "emission current, Xe flow <= 0.10 mg/s design target, O-exposure tolerance, start "
                              "cycles; mass and envelope", "reference_data": "Busek cathodes 0.2 / 0.3 kg (Xe)",
         "status": "PENDING " + L["H2-2"]},
        {"id": "H3-06", "item": "magnet materials / coil wire for MC-1", "long_lead": True,
         "spec_level_needed": "from the H2-1 magnetic design", "reference_data": "none accessed by this lane",
         "status": "PENDING " + L["H2-1"]},
        {"id": "H3-07", "item": "flight low-pressure sensing for the plenum (TM-07)", "long_lead": True,
         "spec_level_needed": "range at the plenum pressure (PENDING H2-3), mass, power, radiation tolerance",
         "reference_data": "none accessed (gap)", "status": "TBD - specification gap"},
    ]
    h4 = [
        {"id": "H4-01", "stage": "S1a", "measure": "as-built masses of H-1, MC-1, C-1 and each module (HW-ENV-08 "
                                                    "inspection), test-article-only provisions weighed separately",
         "closes": ["R09.m_hall_head_incl_mc", "R10.m_magnetic_circuit", "R11.m_cathode_unit"]},
        {"id": "H4-02", "stage": "S1a", "measure": "installed stand payload mass and CG", "closes": ["ID-09"]},
        {"id": "H4-03", "stage": "S1 / S1b", "measure": "cathode Xe flow in spot mode at 0.10 mg/s and at the 0.15 mg/s "
                                                        "test point at the required emission current (A5 risk 3)",
         "closes": ["R06.m_Xe_cathode (confirmation of the design term)"]},
        {"id": "H4-04", "stage": "S1 / Phase 1", "measure": "Xe per ignition / startup and per transition",
         "closes": ["R06.m_Xe_other"]},
        {"id": "H4-05", "stage": "S1a", "measure": "coil currents and temperatures at the design B(z) (magnet_coil "
                                                    "qualification)", "closes": ["R10.m_magnetic_circuit"]},
        {"id": "H4-06", "stage": "S1 / Phase 1", "measure": "per-component bus power and component temperatures "
                                                            "(INS-02, INS-17, INS-23, INS-24): PPU and thermal sizing",
         "closes": ["R12.m_ppu", "R13.m_thermal"]},
        {"id": "H4-07", "stage": "Phase 1", "measure": "plume divergence envelope (for LC-06 layout keep-out)",
         "closes": ["LC-06"]},
    ]
    milestones = {
        "supports": ["A"],
        "A": "Supported: one evolving mass model and mechanical envelope for the A5 proposal reference, with the fixed Xe "
             "design term, analog planning ranges, the room left under 34/36/40 kg for TBD rows and the RF/ECR modules "
             "as a separate contingency. It needs no Hall performance number and selects no architecture.",
        "B": "Needs: preliminary-geometry CBEs from H2-1..H2-6 for every row, m_Xe_total from the Xe ledger, a selected "
             "tank and MEOP, intake and compressor designs (DI-1.1/1.2/1.4), mass BOM owner decisions OD-M1..OD-M7, "
             "and the RF module mass if Phase-1 outcome B.",
        "C": "Needs: PDR design masses (H-1/C-1 as-built masses as the first measured points), structure from the "
             "spacecraft configuration and launch loads, a designed harness, integrated thermal hardware, a layout "
             "with positions (CG, alignment) and the integrated mass/power/thermal/life closure."}
    owner_q = [
        {"id": "H27-Q1", "question": "Evaluate the allocation at both ends of '<= 34-36 kg' (done here) or fix one?"},
        {"id": "H27-Q2", "question": "System margin 20 % (PROPOSED in mass_bom_v1) or 10 % (recorded RFP R3, verify)? "
                                     "Both are reported."},
        {"id": "H27-Q3", "question": "Does the 40 kg include the Xe load and tank (mass_bom OD-M7)? Included here."},
        {"id": "H27-Q4", "question": "Redundancy policy for valves, cathode and PPU (single string here)."},
        {"id": "H27-Q5", "question": "Accept the PPU low end as the NASA SBIR 2 kg development TARGET (undemonstrated, "
                                     "labelled 'assumed') until H2-4 delivers a CBE?"},
        {"id": "H27-Q6", "question": "Keep the 2 % Xe residual (mass_bom policy) as a separate line outside the five-term "
                                     "Xe ledger, or fold it into m_reserve?"},
    ]

    doc = {
        "schema": "h2_7_mechanical_bom_v1", "id": "fo_h2_7_mechanical_bom_v1", "lane": "fo_h2_7_mechanical_bom",
        "trigger": "T_H2_7_MECHANICAL_BOM", "owner_addendum": "A7",
        "title": "H2-7 mechanical envelope / evolving mass model (A5 proposal reference architecture)",
        "status": "DRAFT_PENDING_OWNER", "date": DATE, "base_commit": BASE_COMMIT,
        "generated_by": LANE_DIR_REL + "/build_h2_7_mechanical_bom.py",
        "companion_document": LANE_DIR_REL + "/" + MD_NAME, "test": "tests/test_h2_7_mechanical_bom.py",
        "architectures": list(ARCHITECTURES),
        "lane_scope": a7["h2_scope"],
        "what_this_is_not": ["not a performance prediction (no thrust, efficiency, discharge current or plasma state)",
                             "not an architecture selection or ranking; no winner among " + ", ".join(ARCHITECTURES),
                             "not a frozen Xe mass (A6 not_authorized); Bundle 1 stays NO_BASELINE_YET",
                             "analog masses are published values of OTHER hardware, never predictions of Vyovrinda "
                             "hardware; A5 numbers are allocations or requirements"],
        "decision_pins": [{"path": PINS[k][0], "sha256": PINS[k][1], "why": PINS[k][2]}
                          for k in ("OD", "A5", "A6", "A7", "G0")],
        "input_pins": [{"path": PINS[k][0], "sha256": PINS[k][1], "why": PINS[k][2]}
                       for k in ("MASSBOM", "HWDEF", "XELEDGER", "W4", "CDS")],
        "never_pinned": NEVER_PINNED,
        "sources": SOURCES, "unit_identities": UNIT, "unit_notes": UNIT_NOTES, "analog_data": ANALOGS,
        "margin_policy_reused": {
            "from": PINS["MASSBOM"][0], "mev_definition": mb["mev_definition"],
            "standard": mb["sources"][mb["margin_policy"]["source"]]["citation"],
            "standard_url": mb["sources"][mb["margin_policy"]["source"]]["url"],
            "mga_dry_equipment_ecss_d": mga_d, "mga_propellant": mga_p, "system_margin_proposed": sm_prop,
            "system_margin_alternatives": sm_alt, "harness_fraction": f_h, "xe_residual_fraction": f_res,
            "note": "mass_bom_v1 margin policy reused unchanged (not re-accessed by this lane)"},
        "h1_configuration_items": [
            {"id": c["id"], "name": c["name"],
             "flight_status": {"H-1": "FLIGHT-REPRESENTATIVE", "MC-1": "FLIGHT-REPRESENTATIVE",
                               "C-1": "FLIGHT-REPRESENTATIVE", "FS-C": "GROUND/FACILITY-ONLY",
                               "PS-C": "GROUND/FACILITY-ONLY", "SVC-1": "GROUND/FACILITY-ONLY",
                               "PIM-0": "H-1 TEST-ARTICLE-ONLY", "PIM-RF": "H-1 TEST-ARTICLE-ONLY",
                               "PIM-ECR": "H-1 TEST-ARTICLE-ONLY", "DIV-1": "H-1 TEST-ARTICLE-ONLY"}[c["id"]]}
            for c in hw["configuration_items"]],
        "interface_planes": [{"id": p["id"], "definition": p["definition"]} for p in hw["interface_planes"]],
        "design_parameters": dp,
        "rows": [{k: v for k, v in r.items()} for r in rows],
        "xe_subsystem": xe_block,
        "contingency_modules": contingency,
        "diagnostics": diag,
        "rollup": {
            "policy": "partial roll-up over resolved lines per case; low case = low analog ends, high case = high "
                      "analog ends; TBD lines excluded and listed; never an MEV of the system while TBD lines exist",
            "cases": cases,
            "allocation_checks": checks,
            "cbe_to_mev_factor_dry": factor,
            "largest_uncertainty_contributors": contrib,
            "largest_bounded_contributors_top3": [c["line_item"] for c in bounded[:3]],
            "sourced_floor_kg": floor,
            "module_room": module_room,
            "compressor_downselect_status": cds["status"],
        },
        "mechanical_envelope": env,
        "lane_consumption": {**cons, "adopted_line_items": adopted},
        "interface_demands": idem,
        "hard_incompatibility_check": hic,
        "architecture_changing_blockers_touched": blockers,
        "m16_rows": m16_rows,
        "h3_procurement_inputs": h3,
        "h4_test_inputs": h4,
        "milestones": milestones,
        "owner_questions": owner_q,
        "not_used": ["withdrawn repository masses (docs/HISTORY.md v0.5 / Phase-4 tables; 110-120 kg) and every "
                     "v1.2-v1.6 absolute Hall result (CLAUDE.md 'Superseded / withdrawn')",
                     "abep_sim/mass_bom.py legacy sizing defaults and legacy MGA dict (uncited; mass_bom OD-M3)",
                     "abep_sim/archengine.py Ionizer mass defaults (unsourced)",
                     "any Hall transport closure, screening candidate or abep_sim/plasma_devices.py output",
                     "P5 calibration-nuisance items (never a design variable)",
                     "in-progress drafts of parallel lanes in other worktrees (never consumed for the committed output; --lane-root is a preview only)"],
    }
    s = json.dumps(doc)
    for k in FORBIDDEN_KEYS:
        if f'"{k}"' in s:
            raise ValueError(f"forbidden key {k} in output")
    return rnd(doc)


# ------------------------------------------------------------------------------------------------ markdown
def fmt(v, nd=3):
    if v is None:
        return "TBD"
    if isinstance(v, list):
        return "–".join(fmt(x, nd) for x in v)
    if isinstance(v, float):
        return f"{v:.{nd}f}".rstrip("0").rstrip(".") if abs(v) < 1e6 else f"{v:.4g}"
    return str(v)


def render_md(doc: dict) -> str:
    o = []
    w = o.append
    w("# H2-7 — Mechanical envelope and evolving mass model\n")
    w(f"Lane `{doc['lane']}` (trigger `{doc['trigger']}`, owner addendum A7). Status **{doc['status']}**. "
      f"Generated by `{doc['generated_by']}`; do not edit by hand. Machine-readable twin: `{JSON_NAME}`.\n")
    w("This is an H2 hardware-design / preliminary-sizing lane, **not** an architecture-selection lane. Nothing "
      "here predicts thrust, efficiency, discharge current or plasma state, and no branch among `hall_only`, `rf_hall` "
      "and `ecr_hall` is selected. Analog masses are published values of other hardware, not predictions of "
      "Vyovrinda hardware. A5 numbers are allocations or requirements. Bundle 1 stays NO_BASELINE_YET, and the "
      "credible Hall set is empty.\n")
    w("## Pinned inputs\n")
    w("| path | sha256 | why |\n|---|---|---|")
    for p in doc["decision_pins"] + doc["input_pins"]:
        w(f"| `{p['path']}` | `{p['sha256'][:16]}…` | {p['why']} |")
    w("\nMutable governance files are never pinned: " + "; ".join(f"`{x}`" for x in doc["never_pinned"][:5]) + ".\n")
    mp = doc["margin_policy_reused"]
    w("## Margin policy (reused from mass_bom_v1)\n")
    w(f"MEV definition: {mp['mev_definition']}. Standard: {mp['standard']}. Values used here: dry-equipment MGA "
      f"{fmt(mp['mga_dry_equipment_ecss_d'])} (ECSS D, PROPOSED), propellant MGA {fmt(mp['mga_propellant'])}, "
      f"system margin {fmt(mp['system_margin_proposed'])} (alternative {fmt(mp['system_margin_alternatives'])}), "
      f"harness {fmt(mp['harness_fraction'])} of the nominal dry mass, Xe residual {fmt(mp['xe_residual_fraction'])}.\n")
    w("## Mass model: A5 rows\n")
    w("CBE is a range [low, high] in kg. It is an analog planning range, a fixed design term, a policy fraction or "
      "TBD. MEV per line is CBE × (1 + MGA).\n")
    w("| row | A5 subsystem | line item | CBE low–high (kg) | basis | ev. class | MGA | status | flight status |")
    w("|---|---|---|---|---|---|---|---|---|")
    for r in doc["rows"]:
        for li in r["line_items"]:
            ln = li["resolved"]
            cb = "TBD" if ln["low"] is None else (fmt(ln["low"]) if ln["low"] == ln["high"] else
                                                  f"{fmt(ln['low'])}–{fmt(ln['high'])}")
            w(f"| {r['row_id']} | {r['a5_subsystem']} | `{li['id']}` {li['name']} | {cb} | {ln['basis']} | "
              f"{ln['evidence_class'] or '—'} | {fmt(ln['mga'])} | {ln['status']} | {r['flight_status']} |")
    w("\nH-1 counterparts: " + "; ".join(f"{r['row_id']} → {', '.join(r['h1_counterpart']['items'])} "
                                         f"({r['h1_counterpart']['status']})" for r in doc["rows"]) + ".\n")
    w("## Analog data (other hardware; never predictions)\n")
    w("| id | device | quantity | value | ev. class | source / locator |\n|---|---|---|---|---|---|")
    for k, a in doc["analog_data"].items():
        w(f"| {k} | {a['device']} | {a['quantity']} | {fmt(a['value'])} {a['unit']} | {a['evidence_class']} | "
          f"{a['source']}: {a['locator']} |")
    w("\nSources, accessed 2026-09-29. PDFs are hashed as fetched. HTML pages were read through a fetch tool, so "
      "verify their wording on the page:\n")
    for k, s in doc["sources"].items():
        w(f"- **{k}**: {s['citation']}. {s['url'] or ''} "
          f"{('(sha256 ' + s['sha256_as_fetched'][:16] + '…)') if s.get('sha256_as_fetched') else ''}")
    x = doc["xe_subsystem"]
    w("\n## Xe subsystem (A6 decomposition)\n")
    w(f"{x['m_Xe_subsystem_definition']}. Linked ledger: `{x['linked_ledger']['path']}` (state: "
      f"{x['linked_ledger']['state']}). The only fixed Xe design term is {x['fixed_design_term']['arithmetic']}.\n")
    w("| term | line item | CBE low (kg) | CBE high (kg) | status |\n|---|---|---|---|---|")
    for t in x["terms"]:
        w(f"| {t['term']} | `{t['line_item']}` | {fmt(t['cbe_low_kg'])} | {fmt(t['cbe_high_kg'])} | {t['status']} |")
    k = x["known_lines_cbe_kg"]
    w(f"\nKnown lines: {fmt(k['low'])}–{fmt(k['high'])} kg CBE. {k['note']}.\n")
    s = x["sensitivities"]
    w(f"Sensitivities: at the 0.15 mg/s test point the cathode term is {fmt(s['upper_test_point_0p15']['m_cathode_kg'])} kg "
      f"(+{fmt(s['upper_test_point_0p15']['delta_kg'])} kg). Over the 18,000 h design-life target it is "
      f"{fmt(s['design_life_target']['m_cathode_kg'])} kg (+{fmt(s['design_life_target']['delta_kg'])} kg). "
      "Both are sensitivities only.\n")
    w("Storage volume for the known load (" + fmt(x["storage_volume_for_known_load"]["load_kg"]) + " kg): " +
      ", ".join(f"{fmt(v['V_l'])} l at {fmt(v['p_bar'])} bar" for v in x["storage_volume_for_known_load"]["rows"]) +
      " (293.15 K, NIST). " + x["xs_xta_capacity_check"]["statement"] + ".\n")
    w("## Contingency modules (never in the baseline total)\n")
    for c in doc["contingency_modules"]:
        w(f"- **{c['id']}** ({c['architecture']}, {c['h1_item']}): {c['name']}. {c['flight_status']}. {c['status']}.")
    w("\n## Diagnostics\n")
    w("The mass model includes only the flight telemetry subset:\n")
    for t in doc["diagnostics"]["flight_telemetry_subset_IN"]:
        w(f"- {t['id']} {t['quantity']} → {t['carrier_row']}")
    w("\nThe H-1 ground diagnostics are **excluded** from the flight mass model (GROUND/FACILITY-ONLY): " +
      ", ".join(f"{i['id']} {i['name']}" for i in doc["diagnostics"]["h1_ground_diagnostics_EXCLUDED"]) + ".\n")
    ro = doc["rollup"]
    w("## Roll-up (partial) and allocation check\n")
    w(ro["policy"] + ".\n")
    w("| system margin | case | CBE dry | MGA | harness | nominal dry | sys. margin | propellant | MEV (known lines) | TBD lines |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for smn, cs in ro["cases"].items():
        for c in ("low", "high"):
            q = cs[c]
            w(f"| {smn} | {c} | {fmt(q['cbe_dry_kg'])} | {fmt(q['mga_kg'])} | {fmt(q['harness_kg'])} | "
              f"{fmt(q['nominal_dry_kg'])} | {fmt(q['system_margin_kg'])} | {fmt(q['propellant_kg'])} | "
              f"**{fmt(q['mev_known_lines_kg'])}** | {q['n_tbd_lines']} |")
    w("\nThe allocation check below uses the proposed 20 % system margin. Room left for the TBD lines is shown as "
      f"MEV and as dry CBE (MEV ÷ {fmt(ro['cbe_to_mev_factor_dry'])}):\n")
    w("| reference | kg | case | MEV known | remaining (kg) | share | CBE room for TBD dry lines | state |")
    w("|---|---|---|---|---|---|---|---|")
    for c in ro["allocation_checks"]:
        w(f"| {c['reference']} ({c['kind']}) | {fmt(c['reference_kg'])} | {c['case']} | {fmt(c['mev_known_lines_kg'])} | "
          f"{fmt(c['remaining_kg'])} | {fmt(c['remaining_share'])} | {fmt(c['cbe_available_to_tbd_dry_lines_kg'])} | "
          f"{c['state']} |")
    w(f"\nThe sourced floor is {fmt(ro['sourced_floor_kg'])} kg: the fixed cathode Xe term plus the policy residual. "
      "Analog values are not lower bounds.\n")
    w("Largest uncertainty contributors: every TBD line is unbounded. The largest bounded spreads, in MEV kg, are:\n")
    for c in [c for c in ro["largest_uncertainty_contributors"] if c["spread_mev_kg"] is not None]:
        w(f"- `{c['line_item']}`: {fmt(c['spread_mev_kg'])} kg (CBE {fmt(c['cbe_low_kg'])}–{fmt(c['cbe_high_kg'])})")
    w("\nUnbounded (TBD): " + ", ".join(f"`{c['line_item']}`" for c in ro["largest_uncertainty_contributors"]
                                        if c["spread_mev_kg"] is None) + ".\n")
    e = doc["mechanical_envelope"]
    w("## Mechanical envelope\n")
    w("- Overall volume and length: " + e["overall_volume_and_length"]["status"] + ".")
    for a in e["overall_volume_and_length"]["analog_envelopes"]:
        extra = ""
        if "box_volume_l" in a:
            extra = f" (box {fmt(a['box_volume_l'])} l)"
        if "cylinder_envelope_volume_l" in a:
            extra = f" (cylinder envelope {fmt(a['cylinder_envelope_volume_l'])} l)"
        w(f"  - {a['item']}: {fmt(a['value_mm'])} mm{extra} [{a['analog']}]")
    w("- Thruster-axis alignment (" + e["thruster_axis_alignment"]["status"] + "): " +
      e["thruster_axis_alignment"]["statement"])
    w("- CG (" + e["cg_estimate"]["status"] + "): " + e["cg_estimate"]["statement"])
    w("- Spacecraft mounting interface: " + "; ".join(f"{m['id']} {m['item']} [{m['status']}]"
                                                      for m in e["spacecraft_mounting_interface"]))
    w("- Intake-to-thruster layout constraints: " + "; ".join(f"{m['id']} {m['constraint']} [{m['status']}]"
                                                              for m in e["intake_to_thruster_layout_constraints"]))
    lc = doc["lane_consumption"]
    w("\n## Parallel-lane consumption (lazy)\n")
    w(lc["contract"] + "\n")
    w("| lane | path | state | demands to H2-7 |\n|---|---|---|---|")
    for key, v in lc["lanes"].items():
        w(f"| {key} | `{v['path']}` | {v['state']} | {v.get('n_demands_to_h2_7', '—')} |")
    w(f"\nAdopted line items: {', '.join(lc['adopted_line_items']) or 'none'}.\n")
    w("## Design-parameter table\n")
    w("| id | name | value | units | basis | ev. class | status | flight status |\n|---|---|---|---|---|---|---|---|")
    for p in doc["design_parameters"]:
        w(f"| {p['id']} | {p['name']} | {fmt(p['value'])} | {p['units']} | {p['basis']} | {p['evidence_class'] or '—'} | "
          f"{p['status']} | {p['flight_status']} |")
    w("\n## Interface demands\n")
    w("| id | from | to | quantity | range | units | status |\n|---|---|---|---|---|---|---|")
    for d in doc["interface_demands"]:
        w(f"| {d['id']} | {d['from']} | {d['to']} | {d['quantity']} | {fmt(d.get('range'))} | {d['units']} | {d['status']} |")
    h = doc["hard_incompatibility_check"]
    w(f"\n## Hard-incompatibility check: {h['result']} (architecture veto: {h['architecture_veto']})\n")
    for c in h["checked"]:
        w(f"- {c['id']} {c['check']}: {c['evidence']} ({c['evidence_class'] or 'n/a'}). **{c['finding']}**.")
    w("\n## Architecture-changing blockers touched (A7)\n")
    for b in doc["architecture_changing_blockers_touched"]:
        w(f"- Blocker {b['blocker']} ({'touched' if b['touched'] else 'not touched'}): {b['how']}.")
    w("\n## M16 rows (proposed execution state, mass/envelope attribute)\n")
    w("| row | A5 subsystem | state | blocking item | rollup category | note |\n|---|---|---|---|---|---|")
    for m in doc["m16_rows"]:
        w(f"| {m['row_id']} | {m['a5_subsystem']} | {m['proposed_state']} | {m.get('blocking_item', '—')} | "
          f"{m.get('rollup_category', '—')} | {m['note']} |")
    w("\n## H3 procurement inputs (published data are reference only; no supplier was contacted)\n")
    for p in doc["h3_procurement_inputs"]:
        w(f"- **{p['id']} {p['item']}** (long lead: {p['long_lead']}): {p['spec_level_needed']}. Reference: "
          f"{p['reference_data']}. Status: {p['status']}.")
    w("\n## H4 test inputs\n")
    for t in doc["h4_test_inputs"]:
        w(f"- **{t['id']}** ({t['stage']}): {t['measure']}. Closes {', '.join(t['closes'])}.")
    w("\n## Milestones\n")
    for kk in ("A", "B", "C"):
        w(f"- **{kk}**: {doc['milestones'][kk]}")
    w("\n## Owner questions\n")
    for q in doc["owner_questions"]:
        w(f"- {q['id']}: {q['question']}")
    w("\n## Not used\n")
    for n_ in doc["not_used"]:
        w(f"- {n_}")
    return "\n".join(o) + "\n"


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the committed files are stale")
    ap.add_argument("--lane-root", type=Path, default=None, help="preview: consume lane outputs under this root")
    ap.add_argument("--stdout", action="store_true", help="print JSON to stdout instead of writing files")
    a = ap.parse_args(argv)
    doc = build_document(REPO, a.lane_root)
    js, md = dump(doc), render_md(doc)
    if a.stdout:
        sys.stdout.write(js)
        return 0
    if a.lane_root is not None:
        print("refusing to write committed files from an external --lane-root preview; use --stdout", file=sys.stderr)
        return 2
    jp, mp = HERE / JSON_NAME, HERE / MD_NAME
    if a.check:
        ok = jp.is_file() and mp.is_file() and jp.read_text() == js and mp.read_text() == md
        print("OK" if ok else "STALE: regenerate with python " + LANE_DIR_REL + "/build_h2_7_mechanical_bom.py")
        return 0 if ok else 1
    jp.write_text(js)
    mp.write_text(md)
    print(f"wrote {jp.relative_to(REPO)} and {mp.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
