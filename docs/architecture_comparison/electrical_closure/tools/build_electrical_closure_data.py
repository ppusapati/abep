#!/usr/bin/env python3
"""Build electrical_closure_data_v1.json and worked_example_v1.json (lane PPUMAG, electrical closure v1).

Deterministic: transcribed source values live in this file (each with its source id and locator); every derived number
is computed here; the only file input is the committed vector extraction
``sources/rhodes2024_slide11_discharge_efficiency.csv`` (made by ``digitize_rhodes2024_slide11.py``).
Output is written with sorted keys and fixed rounding so that a rerun is byte-identical
(``tests/test_electrical_closure.py`` checks this).

    python docs/architecture_comparison/electrical_closure/tools/build_electrical_closure_data.py          # write
    python docs/architecture_comparison/electrical_closure/tools/build_electrical_closure_data.py --check  # compare

Nothing produced here is a code default: callers read these entries, choose one, and carry its evidence attributes.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT_DIR = HERE.parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
from abep_sim import magnet_power as mp  # noqa: E402

DATA_OUT = ROOT_DIR / "electrical_closure_data_v1.json"
EXAMPLE_OUT = ROOT_DIR / "worked_example_v1.json"
CSV_RHODES = ROOT_DIR / "sources" / "rhodes2024_slide11_discharge_efficiency.csv"
REL = "docs/architecture_comparison/electrical_closure"
WRITTEN_AGAINST = "c53b75aece86c91db48443761574b7bf07df6070"
ACCESSED = "2026-09-26"

COMPONENTS = ("hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater", "flow_control", "compressor",
              "thermal_control", "housekeeping", "rf_source", "ecr_source", "ecr_magnet")
ARCHS = {"hall_only": (), "rf_hall": ("rf_source",), "ecr_hall": ("ecr_source", "ecr_magnet")}


def r(x, nd=6):
    """fixed rounding for byte-stable JSON"""
    return float(f"{x:.{nd}g}")


# ---------------------------------------------------------------------------------------------------------- sources
SOURCES = {
    "S-RHODES24": {
        "citation": "C. R. Rhodes, G. F. Benavides, L. R. Pinero, 'Sub-kW Class Hall-Effect Thruster Power Processing Unit "
                    "for Wide Output Range Applications', IEPC-2024-331, 38th IEPC, Toulouse, 2024 (presentation slides, "
                    "NASA NTRS 20240006846)",
        "url": "https://ntrs.nasa.gov/api/citations/20240006846/downloads/Rhodes%20-%20IEPC%202024%20Presentation_v2.pdf",
        "access": "open", "sha256_accessed": "9f5a6c7bb36ac2ffc45026e004150304a592dadb1419284917341623588e21d9"},
    "S-MANZELLA96": {
        "citation": "D. Manzella, S. Oleson, J. Sankovic, T. Haag, 'Evaluation of Low Power Hall Thruster Propulsion', "
                    "NASA TM-107326 / AIAA-96-2736 (1996)",
        "url": "https://ntrs.nasa.gov/api/citations/19970001691/downloads/19970001691.pdf",
        "access": "open", "sha256_accessed": "2ea300ad29d507f69d323904c5761921bc49efd17a71d093d05352d19191b6cd"},
    "S-NIKRANT22": {
        "citation": "A. W. Nikrant et al., 'Overview and Performance Characterization of Northrop Grumman's 1 kW Hall "
                    "Thruster String', IEPC-2022-303, 37th IEPC, Boston (2022)",
        "url": "https://ntrs.nasa.gov/api/citations/20220007774/downloads/20220513%20IEPC-2022-303_FINAL.pdf",
        "access": "open", "sha256_accessed": "425c0d1dae3959b51aa8699d2dd89b42f19ea487658d09b3206646abbf06cf6c"},
    "S-GOEBEL08": {
        "citation": "D. M. Goebel, I. Katz, 'Fundamentals of Electric Propulsion: Ion and Hall Thrusters', JPL Space "
                    "Science and Technology Series, 2008 (DESCANSO edition)",
        "url": "https://descanso.jpl.nasa.gov/SciTechBook/series1/Goebel__cmprsd_opt.pdf",
        "access": "open", "sha256_accessed": "a373c8a26137b7c7cd989880c303c4f6c1f84f20a11a02770047f6ba4c249e4e"},
    "S-PEDRINI17": {
        "citation": "D. Pedrini, F. Cannelli, C. Tellini, C. Ducci, T. Misuri, F. Paganucci, 'Hollow Cathodes for "
                    "Low-Power Hall Effect Thrusters', IEPC-2017-365, 35th IEPC, Atlanta (2017)",
        "url": "https://electricrocket.org/IEPC/IEPC_2017_365.pdf",
        "access": "open", "sha256_accessed": "d98374b080642877ed0b2aa2428173b104fa4ff4a633c6dc523203c5b6f81cf6"},
    "S-MONTERO24": {
        "citation": "A. Montero Barriga, T. Perrotin, J. Navarro Cavalle, X. Chen, 'Design, assembly and validation test "
                    "of a sub-1Amp LaB6 hollow cathode', IEPC-2024-805, 38th IEPC, Toulouse (2024)",
        "url": "https://ep2.uc3m.es/assets/docs/pubs/conference_proceedings/Mont24a.pdf",
        "access": "open", "sha256_accessed": "031712c977a34d8991799b7b78665cd0ff1b8ad11c2f3e14cdc095e56b35d141"},
    "S-MOOG-PFCV": {
        "citation": "Moog Space and Defense, 'Electric Propulsion Proportional Flow Control Valve (PFCV)', model 51E339 "
                    "datasheet, Form 500-1119 0620 (2020)",
        "url": "https://www.moog.com/content/dam/moog/literature/sdg/space/propulsion/moog-proportional-flow-control-valve-datasheet.pdf",
        "access": "open", "sha256_accessed": "f9124de96f217ac8153cbcd2d94e751a9662b2978abaed6e9a520ae0a6062a2b"},
    "S-NEWORBIT25": {
        "citation": "A. Schwertheim et al., 'Air-Breathing Electric Propulsion Developments at NewOrbit Space', "
                    "IEPC-2025-378, 39th IEPC, London (2025); Research Square preprint rs-9039885 v1 (CC BY 4.0)",
        "url": "https://www.researchsquare.com/article/rs-9039885/v1", "doi": "10.21203/rs.3.rs-9039885/v1",
        "access": "open", "sha256_accessed": "d121e9dfa7891706a21f0034a06ebdaecf21ec03b12945e6484dd355bd543c6f"},
    "S-VOLKMAR18": {
        "citation": "C. Volkmar, C. Geile, K. Hannemann, 'Radio-Frequency Ion Thrusters - Power Measurement and Power "
                    "Distribution Modeling', J. Propulsion and Power (2018); authors' preprint at DLR elib",
        "url": "https://elib.dlr.de/120608/1/Volkmar_JPP_preprint.pdf", "doi": "10.2514/1.B36868",
        "access": "open (preprint)", "sha256_accessed": "17528c30c6fe96c766959969f02ca319e4cd0ea67968876a16c2371e856a1798"},
    "S-KUNINAKA09": {
        "citation": "H. Kuninaka et al., 'Hayabusa Asteroid Explorer Powered by Ion Engines on the way to Earth', "
                    "IEPC-2009-267, 31st IEPC, Ann Arbor (2009)",
        "url": "https://electricrocket.org/IEPC/IEPC-2009-267.pdf",
        "access": "open", "sha256_accessed": "36621c381e13a25b839f73b71064fe8dfcec0b331ad16541cf76bd79d4e77803"},
    "S-NAKATANI15": {
        "citation": "K. Nakatani, T. Ishizaki, 'A 2.4 GHz-Band 100 W GaN-HEMT High-Efficiency Power Amplifier for "
                    "Microwave Heating', J. Electromagn. Eng. Sci. 15(2), 82-88 (2015)",
        "url": "https://www.jees.kr/upload/pdf/jees-15-2-82.pdf", "doi": "10.5515/JKIEES.2015.15.2.82",
        "access": "open", "sha256_accessed": "858e5a71c81c00aa6f6967bd6fda90dbf5d56787d02a8035f2487afc3eed7bc2"},
    "S-KAZAKEVICH24": {
        "citation": "G. Kazakevich, R. P. Johnson, T. Khabiboulline, G. Romanov, V. Yakovlev, Ya. Derbenev, Yu. Eidelman, "
                    "'On forced RF generation of CW magnetrons for SRF accelerators', arXiv:2404.16249 (2024)",
        "url": "https://arxiv.org/pdf/2404.16249",
        "access": "open (preprint)", "sha256_accessed": "928a053d0d18f6266694191fabd32d527a9f8fe0be75af24f452548209f759fc"},
    "S-NBS-HB100": {
        "citation": "National Bureau of Standards Handbook 100, 'Copper Wire Tables' (1966)",
        "url": "https://nvlpubs.nist.gov/nistpubs/Legacy/hb/nbshandbook100.pdf",
        "access": "open", "sha256_accessed": "3128aaa9fac5688c4e2c4ea9e1b0bb9e20aead7c71039772790859c7fa571af0"},
    "S-KIRTLEY-6007": {
        "citation": "J. L. Kirtley Jr., 'Magnetic Circuit Analog to Electric Circuits', MIT 6.007 supplemental class "
                    "notes (2010), MIT OpenCourseWare",
        "url": "https://ocw.mit.edu/courses/6-007-electromagnetic-energy-from-motors-to-lasers-spring-2011/3ca50847f907d44a148504a778d1a5f5_MIT6_007S11_circuits.pdf",
        "access": "open", "sha256_accessed": "3ada5374030ffde860dd171b7e2ae0fd961ff9acb25f4a4a6af035ea37d32519"},
    "S-KIRTLEY-6061": {
        "citation": "J. L. Kirtley Jr., 'Permanent Magnet \"Brushless DC\" Motors', MIT 6.061 class notes chapter 12, "
                    "MIT OpenCourseWare",
        "url": "https://ocw.mit.edu/courses/6-061-introduction-to-electric-power-systems-spring-2011/36e8b4e86968267bc7030941f020b2af_MIT6_061S11_ch12.pdf",
        "access": "open", "sha256_accessed": "d02c5214fffbf56dd13029bc0925e1e39c61bf5e7ed9d877d9f6543266d4d7ab"},
    "S-CODATA22": {
        "citation": "CODATA 2022 recommended values of the fundamental physical constants, NIST Reference on Constants "
                    "(mu0, m_e, e)",
        "url": "https://physics.nist.gov/cgi-bin/cuu/Value?mu0",
        "access": "open", "sha256_accessed": None},
    "S-REPO": {
        "citation": "this repository at the written-against commit (code values, not evidence)",
        "url": f"git:{WRITTEN_AGAINST}", "access": "repository", "sha256_accessed": None},
}
for sid, s in SOURCES.items():
    s["accessed"] = ACCESSED

# ------------------------------------------------------------------------------------------- transcribed values
# (source id, locator, verbatim/near-verbatim wording) -- every number below appears in the cited location.
T_MOOG = {"R_coil_ohm": 74.5, "R_tol_ohm": 2.0, "R_temp_C": 21.0, "I_max_mA": 140.0, "I_open_mA": 75.0,
          "flow_typ_mg_s": [0.0, 30.0], "T_op_C": [-34.0, 100.0], "mass_g": 115.0}
T_HAYABUSA = {"P_rf_ion_W": 32.0, "P_rf_neut_W": 8.0, "P_dc_W": 110.0, "f_GHz": 4.2}
T_NAKATANI = {"Pout_dBm": 50.4, "drain_eff": 0.729, "pae": 0.640, "f_GHz": 2.45, "Vds_V": 30.0}
T_KAZ = {"eta": 0.54, "P_nom_W": 945.0, "U_kV": 3.69, "f_GHz": 2.45}
T_NEWORBIT = {"eta": 0.92, "bus_V": [26.0, 32.0], "f_thruster_MHz": [1.0, 5.0], "f_cathode_MHz": [3.0, 7.0],
              "P_trfg_in_W": [65.0, 250.0]}
T_VOLKMAR = {"loss_frac": [0.30, 0.40], "f_MHz": 2.0}
T_CODATA = {"mu0": mp.MU0_N_PER_A2, "m_e": 9.1093837139e-31, "e": 1.602176634e-19}


def load_rhodes():
    rows = []
    with CSV_RHODES.open() as fh:
        for rec in csv.DictReader(fh):
            rows.append({"plot": rec["plot"], "V_in_V": int(rec["V_in_V"]), "V_out_V": int(rec["V_out_V"]),
                         "P_out_W": float(rec["P_out_W"]), "efficiency": round(float(rec["efficiency_pct"]) / 100.0, 4)})
    if len(rows) != 54:
        raise SystemExit(f"expected 54 digitized points in {CSV_RHODES}, found {len(rows)}")
    return rows


def entry(**kw):
    base = {"applicability": {}, "derivation": None, "tbd_requires": None, "locator": None, "source_ids": [],
            "units": None, "value": None}
    base.update(kw)
    return base


def tbd(eid, quantity, requires, role, notes="", source_ids=(), locator=None):
    stage = "bus input terminal -> load plane" if role == "efficiency-candidate" else "load plane"
    return entry(id=eid, role=role, quantity=quantity, chain_stage=stage, value_kind="tbd", evidence_class="tbd",
                 evidence_level=None,
                 reporting="none", source_ids=list(source_ids), locator=locator,
                 transformation_chain="none (no usable value accessed)", uncertainty="not quantifiable",
                 validation_status="not applicable", tbd_requires=requires,
                 applicability={"notes": notes} if notes else {})


def build_data():
    rh = load_rhodes()
    comps = {c: {"entries": []} for c in COMPONENTS}

    # ---------------------------------------------------------------- hall_discharge
    E = comps["hall_discharge"]["entries"]
    for vout in (250, 400):
        for vin in (25, 28, 34):
            pts = [p for p in rh if p["V_out_V"] == vout and p["V_in_V"] == vin]
            E.append(entry(
                id=f"HD-RH24-{vout}V-{vin}Vin", role="efficiency-candidate",
                quantity=f"discharge-supply efficiency P_out/P_in, LCC resonant converter, {vin} V input, {vout} V output",
                chain_stage="bus input terminal -> discharge-supply output terminals (harness/filters to the thruster excluded)",
                value_kind="series", value=[{"P_out_W": p["P_out_W"], "efficiency": p["efficiency"]} for p in pts],
                units="fraction vs W", evidence_class="digitized", evidence_level=3, reporting="measurement",
                source_ids=["S-RHODES24"], locator="slide 11, 'Efficiency at 250 V Output' / 'Efficiency at 400 V Output'",
                transformation_chain="bench measurement (source) -> vector scatter plot -> vector extraction "
                                     f"({REL}/tools/digitize_rhodes2024_slide11.py; calibration residual <= 0.0072 %-pt, "
                                     f"<= 0.2 W) -> {REL}/sources/rhodes2024_slide11_discharge_efficiency.csv",
                uncertainty="measurement uncertainty and efficiency definition not stated on the slide (TBD, full paper); "
                            "extraction <= 0.01 %-pt",
                validation_status="breadboard bench test on resistive/electronic load (load type not stated); "
                                  "not validated for Vyovrinda hardware",
                applicability={"power_class_W": [200, 1000], "bus_V": [24, 34], "output_V": [200, 500],
                               "notes": "NASA SSEP sub-kW PPU breadboard (28 V small-spacecraft bus). Efficiency is "
                                        "operating-point dependent (part load, output voltage, input voltage): use the "
                                        "point matching the evaluated mode; above 1 kW discharge output it is an "
                                        "extrapolation (not measured)."}))
    E.append(entry(
        id="HD-MANZELLA96-EST", role="context-only", quantity="whole-PPU efficiency assumed in a low-power Hall system study",
        chain_stage="whole PPU", value_kind="number", value=0.90, units="fraction", evidence_class="assumed",
        evidence_level=7, reporting="estimate", source_ids=["S-MANZELLA96"], locator="section 'Power Processing Unit'",
        transformation_chain="study assumption ('PPU efficiencies were estimated to be 0.90'; 'will likely remain near 0.90') -> transcribed",
        uncertainty="none stated (an estimate)", validation_status="not a measurement; context only",
        applicability={"notes": "SPT-50 / D-38 class (~0.1-0.7 kW) study, 1996; never use as a ledger efficiency"}))

    # ---------------------------------------------------------------- hall_magnet
    E = comps["hall_magnet"]["entries"]
    E.append(entry(
        id="HM-MODEL", role="load-model", quantity="coil-terminal load P = I^2 R from the required gap field",
        chain_stage="load plane (coil terminals)", value_kind="qualitative",
        value="computed by the caller with abep_sim.magnet_power.electromagnet(...) from its own B_gap, magnetic-circuit "
              "geometry, core data, leakage factor, winding window, fill factor, wire and coil temperature",
        evidence_class="model-derived", evidence_level=6, reporting="derivation",
        source_ids=["S-KIRTLEY-6007", "S-NBS-HB100", "S-CODATA22"],
        locator="Kirtley 6.007 Sec. 3.2-3.5; NBS HB100 pp. 1-3, 6, Table 6; CODATA 2022 mu0",
        transformation_chain="lumped magnetic circuit (Ampere) -> ampere-turns -> coil I^2 R with IACS copper R(T)",
        uncertainty="dominated by the caller's leakage factor, geometry and coil temperature; copper model linear "
                    "0-200 C only (refused outside)",
        validation_status="equations verified against NBS HB100 Table 6 in tests; no Vyovrinda magnet exists",
        applicability={"notes": "linear (unsaturated) cores only; saturation above the caller's B_max is refused"}))
    E.append(entry(
        id="HM-G&K-PIN", role="definition", quantity="Hall total input power includes the magnet power",
        chain_stage="thruster input", value_kind="qualitative",
        value="P_in = P_d + P_k + P_mag (Eq. 7.3-6); electrical utilization P_d/(P_d + P_k + P_mag) (Eq. 7.3-7)",
        evidence_class="definition", evidence_level=5, reporting="textbook-typical", source_ids=["S-GOEBEL08"],
        locator="Sec. 7.3, p. 342, Eqs. 7.3-6/7.3-7", transformation_chain="textbook -> transcribed",
        uncertainty="n/a", validation_status="definition",
        applicability={"notes": "supports carrying hall_magnet as its own component, never folded into discharge"}))
    E.append(entry(
        id="HM-G&K-B", role="analysis-input", quantity="typical Hall radial magnetic field strength (illustrative)",
        chain_stage="load driver", value_kind="number", value=0.015, units="T", evidence_class="assumed", evidence_level=5,
        reporting="textbook-typical", source_ids=["S-GOEBEL08"], locator="Sec. 7.2, p. 331 ('a typical radial magnetic "
        "field strength of 150 G')", transformation_chain="textbook example value -> 150 G = 0.015 T (unit conversion)",
        uncertainty="illustrative only; the Vyovrinda field is a design output (TBD)",
        validation_status="not a design value",
        applicability={"notes": "used only in the worked example to exercise the model; never a design input"}))
    E.append(tbd("HM-SUPPLY-EFF", "magnet-supply efficiency (bus -> coil terminals) at the operating point",
                 "a measured magnet-supply efficiency at the coil's current/voltage (sub-100 W, 28 V-class bus)",
                 role="efficiency-candidate",
                 notes="Rhodes 2024 slide 3 gives only the rating of its electromagnet supply (24-34 V in, 1-12 V, 1-5 A, "
                       "60 W max; two-switch forward, shared design with the heater supply); no efficiency is published "
                       "there. Do not back per-supply efficiencies out of whole-PPU totals.",
                 source_ids=["S-RHODES24"], locator="slide 3"))
    E.append(entry(
        id="HM-PM-OPTION", role="definition", quantity="permanent-magnet Hall circuit: electrical load",
        chain_stage="load plane", value_kind="number", value=0.0, units="W", evidence_class="definition", evidence_level=None,
        reporting="derivation", source_ids=["S-PEDRINI17"], locator="Sec. I ('HT100 is a permanent-magnets thruster')",
        transformation_chain="boundary convention: pass 0 W with efficiency 1.0 explicitly; mass via "
                             "abep_sim.magnet_power.permanent_magnet(...) (caller supplies magnet data-sheet values)",
        uncertainty="n/a (mass and B_r(T) thermal drift move to the mass/thermal ledgers)",
        validation_status="existence of permanent-magnet Hall thrusters at 100-250 W (SITAEL HT100) shown by the source",
        applicability={"notes": "no magnet-material data is carried here: B_r, recoil permeability, knee field, "
                                "temperature coefficient and density come from the caller's data sheet"}))
    E.append(entry(
        id="HM-REPO-25W", role="context-only", quantity="fixed magnet load in archengine", value_kind="number", value=25.0,
        units="W", chain_stage="load", evidence_class="assumed", evidence_level=7, reporting="none",
        source_ids=["S-REPO"], locator="abep_sim/archengine.py:627 (P_mag = 25.0); abep_sim/ppu.py:95 (12 V magnet converter)",
        transformation_chain="unsourced code constant", uncertainty="unknown",
        validation_status="never evidence; recorded so it is not mistaken for data",
        applicability={"notes": "independent of the magnetic design; superseded for callers by HM-MODEL"}))

    # ---------------------------------------------------------------- cathode_keeper
    E = comps["cathode_keeper"]["entries"]
    E.append(entry(
        id="CK-G&K-OFF", role="load-bracket", quantity="keeper use in Hall thrusters (steady state)",
        chain_stage="load plane", value_kind="qualitative",
        value="'The keeper is also normally used only during start-up and is turned off once the thruster is ignited.'",
        evidence_class="qualitative", evidence_level=5, reporting="textbook-typical", source_ids=["S-GOEBEL08"],
        locator="Sec. 7.2.3, p. 337", transformation_chain="textbook statement -> quoted",
        uncertainty="'normally': design-specific", validation_status="general practice, not Vyovrinda",
        applicability={"notes": "a steady keeper may be kept on for stability or contamination margin in an ABEP "
                                "background (cathode lane decision); then its load is TBD"}))
    E.append(entry(
        id="CK-PEDRINI17-HC3", role="load-bracket",
        quantity="keeper-discharge power, LaB6 cathode HC3 (1-3 A class) operated with the keeper as the only anode",
        chain_stage="load plane", value_kind="range", value={"min": 25.0, "max": 60.0}, units="W",
        evidence_class="measured", evidence_level=3, reporting="measurement", source_ids=["S-PEDRINI17"],
        locator="Sec. V ('the discharge power ranges from about 25 to 60 W, corresponding to a discharge voltage settling "
                "in the range 14 - 35 V'), Fig. 11a", transformation_chain="measurement -> text -> transcribed",
        uncertainty="'about'; per-point values only in Fig. 11a (not digitized)",
        validation_status="stand-alone cathode test on xenon; keeper-only mode, not keeper power with a thruster running",
        applicability={"gas": "Xe", "cathode_current_A": "keeper-only; cathode class 1-3 A (diode 2.5-4 A)",
                       "notes": "upper bracket for a keeper used as the sustaining anode (start-up, dark channel)"}))
    E.append(entry(
        id="CK-PEDRINI17-HC1", role="load-bracket",
        quantity="keeper-discharge power, LaB6 cathode HC1 (0.3-1 A class) with keeper only",
        chain_stage="load plane", value_kind="range", value={"min": 9.0, "max": 20.0}, units="W",
        evidence_class="measured", evidence_level=6, reporting="measurement", source_ids=["S-PEDRINI17"],
        locator="Sec. IV.B ('The power consumption of HC1 settles in the range from 9 to 20 W'), Fig. 8a",
        transformation_chain="measurement -> text -> transcribed", uncertainty="range as stated",
        validation_status="stand-alone; coupled to HT100 with the keeper floating; 350 h with MSHT100 at 0.5 A keeper "
                          "current (keeper power not stated)",
        applicability={"gas": "Xe", "notes": "current class below a 1.5 kW Hall cathode (extrapolation, level 6)"}))
    E.append(tbd("CK-SUPPLY-EFF", "keeper-supply efficiency at the operating point",
                 "a measured keeper-supply efficiency at the keeper current/voltage used by the cathode policy",
                 role="efficiency-candidate",
                 notes="Rhodes 2024 slide 3 rating only: flyback keeper supply, 24-34 V in, 0.5-1 A, 5-40 V, 25 W max, "
                       "DC-ramp ignition up to 300 V open circuit (slide 10)", source_ids=["S-RHODES24"],
                 locator="slides 3 and 10"))

    # ---------------------------------------------------------------- cathode_heater
    E = comps["cathode_heater"]["entries"]
    E.append(entry(
        id="CH-G&K-STEADY-OFF", role="load-bracket", quantity="heater use in steady Hall operation",
        chain_stage="load plane", value_kind="qualitative",
        value="'the cathode heater is turned off once the discharge supply is turned on, and the cathode runs in a "
              "self-heating mode'", evidence_class="qualitative", evidence_level=5, reporting="textbook-typical",
        source_ids=["S-GOEBEL08"], locator="Sec. 7.2.3, p. 337", transformation_chain="textbook statement -> quoted",
        uncertainty="design-specific", validation_status="general practice",
        applicability={"notes": "steady-mode ledger: heater 0 W with efficiency 1.0 (explicit) if the cathode "
                                "self-heats; the start-up mode carries the heater load"}))
    E.append(entry(
        id="CH-PEDRINI17-HC3", role="load-bracket", quantity="ignition heater power, LaB6 HC3 (1-3 A class, first-generation heater)",
        chain_stage="load plane (start-up mode)", value_kind="number", value=60.0, units="W", evidence_class="measured",
        evidence_level=3, reporting="measurement", source_ids=["S-PEDRINI17"],
        locator="Sec. V ('a heater power of about 60 W allowed for ignitions at keeper voltages lower than 300 V')",
        transformation_chain="measurement -> text -> transcribed", uncertainty="'about'",
        validation_status="> 60 ignitions on xenon", applicability={"gas": "Xe", "notes": "0.4-0.8 mg/s Xe at ignition"}))
    E.append(entry(
        id="CH-PEDRINI17-HC1", role="load-bracket", quantity="ignition heater power, LaB6 HC1 (0.3-1 A class)",
        chain_stage="load plane (start-up mode)", value_kind="number", value=45.0, units="W", evidence_class="measured",
        evidence_level=6, reporting="measurement", source_ids=["S-PEDRINI17"],
        locator="Sec. IV.A-B ('about 45 W'; emitter ~1460 K in about 600 s; 120 ignitions)",
        transformation_chain="measurement -> text -> transcribed", uncertainty="'about'",
        validation_status="120-ignition test", applicability={"gas": "Xe", "notes": "current class below target (level 6)"}))
    E.append(entry(
        id="CH-MONTERO24", role="load-bracket", quantity="ignition heating power, sub-1 A LaB6 cathode (UC3M)",
        chain_stage="load plane (start-up mode)", value_kind="range", value={"min": 267.0, "max": 305.0}, units="W",
        evidence_class="measured", evidence_level=6, reporting="measurement", source_ids=["S-MONTERO24"],
        locator="Sec. V.A and Table 8 ('the HC ignites within 10 - 15 sccm, consuming 267 - 305 W of heating power')",
        transformation_chain="measurement -> text/table -> transcribed",
        uncertainty="steady state never reached during ignition (source)",
        validation_status="> 5 xenon ignitions; self-sustained afterwards with heater off and keeper floating",
        applicability={"gas": "Xe", "notes": "shows the design spread of heater power (45-305 W across three LaB6 "
                                             "designs); keeper ignition 550-850 V"}))
    E.append(tbd("CH-SUPPLY-EFF", "heater-supply efficiency at the operating point",
                 "a measured heater-supply efficiency at the heater current/voltage of the selected cathode",
                 role="efficiency-candidate",
                 notes="Rhodes 2024 slide 3 rating only: 24-34 V in, 1-8 A, 1-12 V, 80 W max", source_ids=["S-RHODES24"],
                 locator="slide 3"))

    # ---------------------------------------------------------------- flow_control
    E = comps["flow_control"]["entries"]
    E.append(entry(
        id="FC-MOOG-SPEC", role="load-input", quantity="PFCV 51E339 coil resistance and drive current",
        chain_stage="load plane (valve coil terminals)", value_kind="list",
        value={"R_coil_ohm": T_MOOG["R_coil_ohm"], "R_tolerance_ohm": T_MOOG["R_tol_ohm"], "R_at_C": T_MOOG["R_temp_C"],
               "I_max_sustained_mA": T_MOOG["I_max_mA"], "I_min_opening_mA": T_MOOG["I_open_mA"]},
        units="ohm, C, mA", evidence_class="measured", evidence_level=3, reporting="specification",
        source_ids=["S-MOOG-PFCV"], locator="SPECIFICATIONS table (Coil Resistance; Input Current Range)",
        transformation_chain="datasheet specification -> transcribed", uncertainty="+-2 ohm at 21 C; coil material "
        "and its temperature coefficient not stated", validation_status="flight heritage listed by the source",
        applicability={"gas": "Xe", "flow_mg_s": T_MOOG["flow_typ_mg_s"], "T_op_C": T_MOOG["T_op_C"],
                       "notes": "Xe-path valve after the Xe chamber; air-path valve (after the atmospheric gas chamber, "
                                "low inlet pressure, O/N2) is TBD"}))
    pfcv = {}
    for tag, I_mA in (("open", T_MOOG["I_open_mA"]), ("max", T_MOOG["I_max_mA"])):
        I = I_mA * 1e-3
        pfcv[tag] = {"P_W": r(I * I * T_MOOG["R_coil_ohm"], 4),
                     "P_min_W": r(I * I * (T_MOOG["R_coil_ohm"] - T_MOOG["R_tol_ohm"]), 4),
                     "P_max_W": r(I * I * (T_MOOG["R_coil_ohm"] + T_MOOG["R_tol_ohm"]), 4)}
    E.append(entry(
        id="FC-MOOG-I2R", role="load-candidate", quantity="PFCV coil dissipation at 21 C (per valve)",
        chain_stage="load plane", value_kind="range",
        value={"min": pfcv["open"]["P_W"], "max": pfcv["max"]["P_W"]}, units="W", evidence_class="inferred",
        evidence_level=3, reporting="derivation", source_ids=["S-MOOG-PFCV"], locator="SPECIFICATIONS table",
        derivation={"formula": "P = I^2 R_coil", "inputs": {"I_A": [T_MOOG["I_open_mA"] / 1e3, T_MOOG["I_max_mA"] / 1e3],
                                                            "R_coil_ohm": T_MOOG["R_coil_ohm"]},
                    "tolerance_band_W": {"at_75mA": [pfcv["open"]["P_min_W"], pfcv["open"]["P_max_W"]],
                                         "at_140mA": [pfcv["max"]["P_min_W"], pfcv["max"]["P_max_W"]]}},
        transformation_chain="datasheet R and I -> our I^2 R (this script)",
        uncertainty="+-2.7 % from the resistance tolerance; coil heating raises R (coefficient not stated, TBD); "
                    "valve-driver loss excluded",
        validation_status="not measured as power by the source",
        applicability={"gas": "Xe", "notes": "per valve; the number of simultaneously energized valves per "
                                             "architecture and mode is TBD (ICD)"}))
    E.append(tbd("FC-DRIVER-EFF", "valve-driver efficiency (bus -> valve coil)",
                 "valve-driver circuit data (linear vs switched current source) at the coil current",
                 role="efficiency-candidate"))
    E.append(tbd("FC-AIR-VALVE", "air-path valve load (after the atmospheric gas chamber)",
                 "the air-path valve selection and its drive current/resistance (upstream ICD, schemas/interfaces/)",
                 role="load-candidate"))

    # ---------------------------------------------------------------- compressor
    E = comps["compressor"]["entries"]
    E.append(entry(
        id="CP-REPO-MODEL", role="load-model", quantity="compressor motor-drive electrical input P_el",
        chain_stage="load plane (motor-drive electrical input)", value_kind="qualitative",
        value="abep_sim.compressor.DragCompressor.run(...)['P_el_W'] = (P_gas + P_bear)/eta_motor + P_ctrl_W",
        evidence_class="model-derived", evidence_level=7, reporting="derivation", source_ids=["S-REPO"],
        locator="abep_sim/compressor.py module docstring and _run_once (P_el = (P_gas + P_bear) / eta_motor + P_ctrl_W)",
        transformation_chain="free-molecular drag-shear model with unsourced dataclass parameters",
        uncertainty="the model's eta_motor = 0.80, P_ctrl_W = 8.0 and k_bear_W_per_rads = 3e-4 are unsourced code "
                    "defaults (assumed); no value is taken from it here",
        validation_status="not validated against a compressor measurement",
        applicability={"notes": "a model exists, so the load is computable once its inputs are sourced; the upstream "
                                "flow comes from the intake/ICD and never from Hall-closure uncertainty"}))
    E.append(tbd("CP-LOAD", "compressor electrical load at the evaluated mode",
                 "a sized compressor design (flow from the upstream ICD), a sourced motor + drive efficiency and bearing "
                 "loss, then abep_sim.compressor evaluated at those inputs", role="load-candidate"))
    E.append(tbd("CP-CONV-EFF", "motor-bus converter efficiency", "converter data at the motor-drive input power",
                 role="efficiency-candidate"))

    # ---------------------------------------------------------------- thermal_control / housekeeping
    comps["thermal_control"]["entries"].append(tbd(
        "TC-LOAD", "propulsion-subsystem heater / active thermal load in the evaluated mode",
        "the thermal model and heater duty cycle (abep_sim/thermal_life.py lane; Xe tank/line/valve and gas-chamber "
        "heaters)", role="load-candidate"))
    comps["thermal_control"]["entries"].append(tbd(
        "TC-EFF", "heater switch / converter efficiency", "heater-switch topology data", role="efficiency-candidate"))
    comps["housekeeping"]["entries"].append(tbd(
        "HK-LOAD", "propulsion controller / PPU control / sensors / telemetry load",
        "controller and telemetry electronics selection and their measured power", role="load-candidate",
        notes="the Mitsubishi 250 mN PPU and the NGC 1 kW string list a separate housekeeping/microcontroller supply "
              "(taxonomy only; no value); repository ppu.py controller 8 W + sensors 4 W are unsourced",
        source_ids=["S-NIKRANT22", "S-REPO"], locator="IEPC-2022-303 PPU description ('discharge supply module; heater-ignitor-keeper supply; magnet supply; PFCV supply; microcontroller; and AUX supply'); abep_sim/ppu.py:52-54"))
    comps["housekeeping"]["entries"].append(tbd(
        "HK-EFF", "housekeeping converter efficiency", "converter data at the housekeeping load", role="efficiency-candidate"))

    # ---------------------------------------------------------------- rf_source
    E = comps["rf_source"]["entries"]
    E.append(entry(
        id="RF-NEWORBIT25", role="efficiency-candidate", quantity="RF generator efficiency, unregulated bus -> RF",
        chain_stage="bus -> RF generator output", value_kind="number", value=T_NEWORBIT["eta"], units="fraction",
        evidence_class="measured", evidence_level=3, reporting="nominal",
        source_ids=["S-NEWORBIT25"], locator="Sec. II.C ('The RFGs operate at a nominal power efficiency of 92% (from "
        "the unregulated bus to RF) in both the cathode and the thruster.')",
        transformation_chain="developer-reported nominal value -> transcribed",
        uncertainty="method, load range and dependence on plasma impedance not stated; 'nominal'",
        validation_status="flight-oriented electronics on an air-fed RF thruster test campaign",
        applicability={"bus_V": T_NEWORBIT["bus_V"], "frequency_Hz": [1e6, 5e6], "power_class_W": T_NEWORBIT["P_trfg_in_W"],
                       "gas": "50:50 N2/O2 and Xe",
                       "notes": "RF thruster coil (gridded ABEP thruster), not a Hall pre-ionizer; matching and cable "
                                "losses inside or outside the 92 % are not stated (verify); the source also reports "
                                "retuning to lower frequency at low flow/power and generator voltage limits"}))
    lo, hi = T_VOLKMAR["loss_frac"]
    E.append(entry(
        id="RF-VOLKMAR18", role="efficiency-candidate",
        quantity="DC input -> forwarded RF at the coil (RF generator + feed cables), low mass flow",
        chain_stage="RFG DC input -> coil feed terminals", value_kind="range",
        value={"min": r(1 - hi, 4), "max": r(1 - lo, 4)}, units="fraction", evidence_class="inferred", evidence_level=6,
        reporting="derivation", source_ids=["S-VOLKMAR18"],
        locator="Sec. V (Conclusion): 'a difference of about 30 - 40 % between DC input and forwarded RF power'; Fig. 11b",
        derivation={"formula": "eta = 1 - difference/DC input (difference read as a fraction of DC input)",
                    "inputs": {"difference_fraction": T_VOLKMAR["loss_frac"]}},
        transformation_chain="measured DC input and phase-resolved coil V/I (source) -> text -> our reading as eta",
        uncertainty="interpretation of 'difference of 30-40 %' as a fraction of DC input; Fig. 11b coupling efficiency "
                    "axis spans 60-75 % (not digitized)",
        validation_status="measured on RIT-10 with xenon; efficiency falls as load resistance drops at low flow",
        applicability={"frequency_Hz": [1e6, 2e6], "gas": "Xe",
                       "notes": "gridded RIT load, ~2 MHz; excludes the bus -> RFG DC supply stage"}))
    E.append(tbd("RF-MATCH-LOSS", "matching-network and RF cable loss (separately)",
                 "forward/reflected power and matchbox/cable loss measured at the pre-ionizer coil across the ABEP flow "
                 "range", role="efficiency-candidate"))
    E.append(tbd("RF-LOAD", "net RF power at the pre-ionizer coil feed terminals",
                 "pre-ionizer physics at the admitted operating point (ionization block; conditional on gate 3 for the "
                 "coupled Hall stage)", role="load-candidate"))

    # ---------------------------------------------------------------- ecr_source
    E = comps["ecr_source"]["entries"]
    hay = (T_HAYABUSA["P_rf_ion_W"] + T_HAYABUSA["P_rf_neut_W"]) / T_HAYABUSA["P_dc_W"]
    E.append(entry(
        id="EC-HAYABUSA-TWTA", role="efficiency-candidate",
        quantity="microwave power amplifier (TWT) RF out / DC consumption, flight ECR ion-engine system",
        chain_stage="amplifier DC input -> RF outputs (ion source + neutralizer)", value_kind="number", value=r(hay, 4),
        units="fraction", evidence_class="inferred", evidence_level=3, reporting="derivation",
        source_ids=["S-KUNINAKA09"], locator="Table 1 (Microwave Power Amplifiers: '32 W for an ion generator, 8 W for a "
        "neutralizer, 110 W total power consumption'; TWT, 4.2 GHz)",
        derivation={"formula": "(P_rf_ion + P_rf_neut) / P_dc", "inputs": {"P_rf_ion_W": T_HAYABUSA["P_rf_ion_W"],
                    "P_rf_neut_W": T_HAYABUSA["P_rf_neut_W"], "P_dc_W": T_HAYABUSA["P_dc_W"]}},
        transformation_chain="flight specification table -> our ratio",
        uncertainty="assumes the 110 W covers all amplifier losses and both outputs; specification values",
        validation_status="flight heritage (Hayabusa)",
        applicability={"frequency_Hz": 4.2e9, "power_class_W": [40, 110],
                       "notes": "TWT, tens-of-W class; system-level (closest to the bus->coupling-plane chain of all ECR "
                                "entries); feed-line loss to the antenna not separated"}))
    pout_W = 10 ** (T_NAKATANI["Pout_dBm"] / 10) / 1000
    E.append(entry(
        id="EC-NAKATANI15-GAN", role="efficiency-candidate",
        quantity="GaN-HEMT amplifier stage: drain efficiency and power-added efficiency, CW",
        chain_stage="amplifier stage only (DC drain -> RF out)", value_kind="list",
        value={"drain_efficiency": T_NAKATANI["drain_eff"], "PAE": T_NAKATANI["pae"],
               "P_out_W": r(pout_W, 4)}, units="fraction, W", evidence_class="measured", evidence_level=6,
        reporting="measurement", source_ids=["S-NAKATANI15"],
        locator="Abstract and Sec. IV ('output power of 50.4 dBm, a drain efficiency of 72.9%, and a power added "
                "efficiency (PAE) of 64.0% at 2.45 GHz for continuous wave operation'; Vds 30 V)",
        derivation={"formula": "P_out_W = 10^(dBm/10) / 1000", "inputs": {"P_out_dBm": T_NAKATANI["Pout_dBm"]}},
        transformation_chain="measurement -> text -> transcribed (+ our dBm -> W)",
        uncertainty="stage only: excludes driver DC, gate bias, bus DC-DC, isolator/circulator, feed",
        validation_status="laboratory amplifier for microwave heating; not space-qualified",
        applicability={"frequency_Hz": 2.45e9, "power_class_W": [100, 115], "bus_V": "Vds 30 V"}))
    E.append(entry(
        id="EC-KAZAKEVICH24-MAG", role="efficiency-candidate",
        quantity="CW magnetron (2M219G, 945 W nominal) conversion efficiency, free run, filament power neglected",
        chain_stage="magnetron anode DC -> RF out (tube only)", value_kind="number", value=T_KAZ["eta"], units="fraction",
        evidence_class="measured", evidence_level=6, reporting="measurement", source_ids=["S-KAZAKEVICH24"],
        locator="section on Stimulated generation, discussion of Fig. 9 ('the measured conversion efficiency ... in the "
                "free run mode (U_Mag ~3.69 kV, P_Lock = 0) at the nominal tube power is ~54%')",
        transformation_chain="measurement -> text -> transcribed", uncertainty="approximate ('~'); filament excluded",
        validation_status="accelerator R&D test", applicability={"frequency_Hz": 2.45e9, "power_class_W": [945, 945],
        "notes": "kW-class tube needing a ~3.7 kV anode supply; excludes HV supply, filament, isolator, feed"}))
    E.append(tbd("EC-ISOLATOR-FEED", "isolator/circulator and feed-line loss",
                 "measured insertion loss of the selected isolator/circulator and feed at the ECR frequency",
                 role="efficiency-candidate"))
    E.append(tbd("EC-LOAD", "net microwave power at the ECR coupling structure",
                 "pre-ionizer physics at the admitted operating point", role="load-candidate"))

    # ---------------------------------------------------------------- ecr_magnet
    E = comps["ecr_magnet"]["entries"]
    fields = {}
    for f_GHz in (2.45, 4.2):
        fields[str(f_GHz)] = r(mp.ecr_resonance_field_T(f_GHz * 1e9, T_CODATA["m_e"], T_CODATA["e"]), 6)
    E.append(entry(
        id="EM-RESONANCE-B", role="load-driver", quantity="ECR resonance field B = 2 pi f m_e / e",
        chain_stage="field requirement", value_kind="list", value={"2.45GHz_T": fields["2.45"], "4.2GHz_T": fields["4.2"]},
        units="T", evidence_class="model-derived", evidence_level=4, reporting="derivation", source_ids=["S-CODATA22"],
        locator="CODATA 2022 m_e = 9.1093837139e-31 kg, e = 1.602176634e-19 C (exact)",
        derivation={"formula": "B = 2 pi f m_e / e", "inputs": {"f_Hz": [2.45e9, 4.2e9], "m_e_kg": T_CODATA["m_e"],
                                                               "e_C": T_CODATA["e"]}},
        transformation_chain="constants -> our evaluation (abep_sim.magnet_power.ecr_resonance_field_T)",
        uncertainty="negligible (constants); where the resonance zone sits is a design choice",
        validation_status="physics identity", applicability={"notes": "non-relativistic electrons"}))
    E.append(entry(
        id="EM-MODEL", role="load-model", quantity="ECR electromagnet coil load (if not a permanent magnet)",
        chain_stage="load plane (coil terminals)", value_kind="qualitative",
        value="abep_sim.magnet_power.electromagnet(...) with B at the resonance zone; P scales with B^2 at fixed geometry",
        evidence_class="model-derived", evidence_level=6, reporting="derivation",
        source_ids=["S-KIRTLEY-6007", "S-NBS-HB100", "S-CODATA22"], locator="as HM-MODEL",
        transformation_chain="as HM-MODEL", uncertainty="as HM-MODEL", validation_status="as HM-MODEL"))
    E.append(entry(
        id="EM-PM-OPTION", role="definition", quantity="permanent-magnet ECR circuit: electrical load",
        chain_stage="load plane", value_kind="number", value=0.0, units="W", evidence_class="definition",
        evidence_level=None, reporting="derivation", source_ids=["S-KIRTLEY-6061"],
        locator="Sec. 4.3 (permanent-magnet circuit, unit permeance)",
        transformation_chain="boundary convention: 0 W with efficiency 1.0, explicit; mass via magnet_power.permanent_magnet",
        uncertainty="n/a", validation_status="definition"))
    E.append(tbd("EM-SUPPLY-EFF", "ECR magnet-supply efficiency", "as HM-SUPPLY-EFF, at the ECR coil operating point",
                 role="efficiency-candidate"))

    # ---------------------------------------------------------------- per-component status
    load_plane = {
        "hall_discharge": "anode-cathode terminals (V_d x I_d)", "hall_magnet": "Hall coil terminals (I^2 R)",
        "cathode_keeper": "keeper terminals", "cathode_heater": "heater terminals (evaluated mode)",
        "flow_control": "propellant-feed actuator terminals (air-path and Xe-path valves)",
        "compressor": "compressor motor-drive electrical input", "thermal_control": "propulsion heater terminals",
        "housekeeping": "propulsion controller / PPU control / sensors / TM-TC",
        "rf_source": "net RF power at the RF pre-ionizer coil feed", "ecr_source": "net microwave power at the ECR coupling input",
        "ecr_magnet": "ECR resonance-field coil terminals"}
    for c in COMPONENTS:
        comps[c]["load_plane"] = load_plane[c]
        comps[c]["in_architectures"] = [a for a, pre in ARCHS.items() if c in pre or c not in ("rf_source", "ecr_source", "ecr_magnet")]
        ents = comps[c]["entries"]
        comps[c]["efficiency_evidence"] = sorted(e["id"] for e in ents if e["role"] == "efficiency-candidate" and e["value_kind"] != "tbd")
        comps[c]["efficiency_status"] = "evidence-range" if comps[c]["efficiency_evidence"] else "TBD"
        comps[c]["load_status"] = ("model-available" if any(e["role"] == "load-model" for e in ents) else
                                   "brackets-only" if any(e["role"] in ("load-bracket", "load-candidate") and e["value_kind"] != "tbd" for e in ents)
                                   else "TBD")
    comps["hall_discharge"]["load_status"] = "TBD (absolute Hall discharge power withdrawn; needs an admitted closure, gate 3)"
    comps["hall_magnet"]["load_status"] = "model-available (abep_sim.magnet_power; design inputs TBD)"
    comps["ecr_magnet"]["load_status"] = "model-available (abep_sim.magnet_power; design inputs TBD) or 0 W permanent magnet"
    comps["compressor"]["load_status"] = "TBD (model exists in abep_sim.compressor, but its motor/overhead inputs are unsourced)"
    comps["flow_control"]["load_status"] = "brackets-only (Xe PFCV coil I^2R; air-path valve TBD)"
    comps["cathode_keeper"]["load_status"] = "brackets-only (policy-dependent; 0 W if off in the mode)"
    comps["cathode_heater"]["load_status"] = "brackets-only (start-up mode); 0 W in steady mode if self-heating"

    return {
        "schema_version": "electrical_closure_v1",
        "boundary_version": "bus_power_boundary_v1",
        "status": "DRAFT for the owner: evidence DATA for callers of the bus-power boundary; never code defaults",
        "written_against_commit": WRITTEN_AGAINST,
        "generated_by": f"{REL}/tools/build_electrical_closure_data.py",
        "accessed": ACCESSED,
        "milestones": {
            "supports": ["A"],
            "A": "conditional selection: supplies the evidence ranges and the explicit TBD list that the conditions "
                 "'demonstrate X at the operating point' must close; no winner is implied",
            "to_reach_B": "admitted Hall transport closure (discharge load), measured supply efficiencies at the Vyovrinda "
                          "operating points (magnet, keeper, heater, valve driver, RF/microwave chain incl. matching/"
                          "isolator), sized compressor and thermal loads",
            "to_reach_C": "flight PPU design with integrated mass, thermal, life, start-up sequence, cathode policy and "
                          "mission closure on the same boundary"},
        "rules": [
            "Pick entries at the evaluated operating point and mode; a nameplate or peak value applied at part load breaks the boundary.",
            "Carry evidence_class, evidence_level, source_ids and uncertainty with every value used; TBD stays TBD (an explicitly labelled assumption with a sensitivity range is the only alternative).",
            "Entries with role 'context-only' are never ledger inputs.",
            "Stage-only efficiencies (amplifier stage, magnetron tube) are upper bounds on the bus->coupling-plane chain, not chain values.",
            "Hall-closure uncertainty never enters flow_control, compressor, thermal_control upstream of the ionization block.",
        ],
        "evidence_class_enum": ["measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                                "definition", "qualitative", "tbd"],
        "sources": SOURCES,
        "reference_constants": {"mu0_N_per_A2": T_CODATA["mu0"], "m_e_kg": T_CODATA["m_e"], "e_C": T_CODATA["e"],
                                "source_id": "S-CODATA22"},
        "components": comps,
        "open_questions_for_owner": [
            "Which boundary does the RFP '< 1.5 kW' refer to (propulsion bus input or other)? (also raised by the boundary lane)",
            "Target bus voltage: the only sub-kW discharge-supply efficiency data found is 24-34 V (28 V class).",
            "Hall magnet: electromagnet or permanent magnet? ECR resonance field: electromagnet or permanent magnet?",
            "Cathode policy: keeper on in steady state (ABEP background) or off; heater only at start-up?",
            "Is a measured supply-efficiency campaign (magnet, keeper, heater, valve driver) acceptable as a milestone-B condition?",
        ],
    }


# ------------------------------------------------------------------------------------------------ worked example
def build_example(data):
    rh = load_rhodes()
    disc = []
    for p in rh:
        if p["V_in_V"] != 28:
            continue
        P_bus = p["P_out_W"] / p["efficiency"]
        disc.append({"V_out_V": p["V_out_V"], "P_load_W": p["P_out_W"], "efficiency": p["efficiency"],
                     "P_bus_W": r(P_bus, 6), "P_loss_W": r(P_bus - p["P_out_W"], 5)})
    effs = [p["efficiency"] for p in rh if p["V_in_V"] == 28]
    effs_500 = [p["efficiency"] for p in rh if p["V_in_V"] == 28 and p["P_out_W"] >= 500]

    comp = data["components"]
    rf_vals = [comp["rf_source"]["entries"][0]["value"], comp["rf_source"]["entries"][1]["value"]["min"],
               comp["rf_source"]["entries"][1]["value"]["max"]]
    ec = comp["ecr_source"]["entries"]
    ec_vals = {"hayabusa_twta_system": ec[0]["value"], "gan_stage_drain": ec[1]["value"]["drain_efficiency"],
               "gan_stage_pae": ec[1]["value"]["PAE"], "magnetron_tube": ec[2]["value"]}

    def per100(eta):
        return r(100.0 / eta, 5)
    spreads = {
        "hall_discharge_28Vin_200_1000W": {"min": min(effs), "max": max(effs), "bus_draw_ratio_max_over_min": r(max(effs) / min(effs), 4)},
        "hall_discharge_28Vin_500_1000W": {"min": min(effs_500), "max": max(effs_500), "bus_draw_ratio_max_over_min": r(max(effs_500) / min(effs_500), 4)},
        "rf_source": {"min": min(rf_vals), "max": max(rf_vals), "bus_draw_ratio_max_over_min": r(max(rf_vals) / min(rf_vals), 4),
                      "bus_W_per_100W_delivered": {"at_max": per100(max(rf_vals)), "at_min": per100(min(rf_vals))}},
        "ecr_source": {"values": ec_vals, "bus_draw_ratio_max_over_min": r(max(ec_vals.values()) / min(ec_vals.values()), 4),
                       "bus_W_per_100W_delivered": {k: per100(v) for k, v in ec_vals.items()},
                       "note": "stage-only values (GaN, magnetron) are upper bounds on the chain; only the Hayabusa value is system-level"},
    }

    # magnet: analysis inputs (assumed) + textbook-typical B, to exercise the model only
    analysis = {"B_gap_T": 0.015, "gap_length_m": 0.02, "gap_area_m2": 2.0e-3, "leakage_factor": 1.5,
                "core": {"length_m": 0.2, "area_m2": 1.0e-3, "mu_r": 1000.0, "B_max_T": 1.0},
                "window_area_m2": 1.0e-4, "fill_factor": 0.5, "mean_turn_length_m": 0.2, "awg": 24}
    core = (mp.CoreSegment("return path", analysis["core"]["length_m"], analysis["core"]["area_m2"],
                           analysis["core"]["mu_r"], analysis["core"]["B_max_T"]),)
    mag_rows = []
    for T in (20.0, 100.0, 200.0):
        em = mp.electromagnet(analysis["B_gap_T"], analysis["gap_length_m"], analysis["gap_area_m2"], core,
                              analysis["leakage_factor"], analysis["window_area_m2"], analysis["fill_factor"],
                              analysis["mean_turn_length_m"], mp.awg_diameter_m(analysis["awg"]), mp.ANNEALED_COPPER_IACS, T)
        mag_rows.append({"T_C": T, "NI_A": r(em["circuit"]["NI_A"], 6), "N_turns": em["coil"]["N_turns"],
                         "I_A": r(em["coil"]["I_A"], 5), "R_ohm": r(em["coil"]["R_ohm"], 5), "P_load_W": r(em["P_load_W"], 5),
                         "P_continuous_limit_W": r(em["P_continuous_limit_W"], 5),
                         "copper_mass_kg": r(em["coil"]["copper_mass_kg"], 4)})
    B_ecr = comp["ecr_magnet"]["entries"][0]["value"]["2.45GHz_T"]
    em_ecr = mp.electromagnet(B_ecr, analysis["gap_length_m"], analysis["gap_area_m2"], core, analysis["leakage_factor"],
                              analysis["window_area_m2"], analysis["fill_factor"], analysis["mean_turn_length_m"],
                              mp.awg_diameter_m(analysis["awg"]), mp.ANNEALED_COPPER_IACS, 20.0)
    status = {}
    for arch, pre in ARCHS.items():
        comps = [c for c in COMPONENTS if c not in ("rf_source", "ecr_source", "ecr_magnet")] + list(pre)
        status[arch] = {
            "components": comps,
            "efficiency_evidence_available": [c for c in comps if comp[c]["efficiency_status"] != "TBD"],
            "efficiency_TBD": [c for c in comps if comp[c]["efficiency_status"] == "TBD"],
            "load_status": {c: comp[c]["load_status"] for c in comps},
            "ledger_closes_today": False,
            "reason": "bus_power_ledger requires every component's load and efficiency; the TBD lists are non-empty",
        }
    return {
        "schema_version": "electrical_closure_worked_example_v1",
        "generated_by": f"{REL}/tools/build_electrical_closure_data.py",
        "label": "WORKED EXAMPLE - sourced numbers and explicitly labelled analysis inputs only; NOT predictions for Vyovrinda",
        "discharge_28Vin_measured_points": {
            "note": "loads are the source's measured test points (no interpolation); efficiency from S-RHODES24 slide 11",
            "rows": disc},
        "efficiency_spreads": spreads,
        "magnet_model_exercise": {
            "analysis_inputs": analysis,
            "analysis_inputs_evidence": "assumed (analysis inputs chosen only to exercise the equations), except "
                                        "B_gap_T = 0.015 T = 'typical radial field 150 G' (S-GOEBEL08 p. 331, illustrative)",
            "hall_rows": mag_rows,
            "ecr_same_geometry_2p45GHz": {"B_gap_T": B_ecr, "P_load_W": r(em_ecr["P_load_W"], 5),
                                          "ratio_to_hall_20C": r(em_ecr["P_load_W"] / mag_rows[0]["P_load_W"], 5),
                                          "note": "P scales with B^2 at fixed geometry and linear core (E5)"}},
        "flow_control_pfcv_per_valve_W": comp["flow_control"]["entries"][1]["value"],
        "ledger_closure_status": status,
    }


def dumps(obj):
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="compare with the committed files instead of writing")
    a = ap.parse_args(argv)
    data = build_data()
    ex = build_example(data)
    outs = {DATA_OUT: dumps(data), EXAMPLE_OUT: dumps(ex)}
    if a.check:
        bad = [str(p) for p, txt in outs.items() if not p.exists() or p.read_text() != txt]
        if bad:
            print("stale: " + ", ".join(bad), file=sys.stderr)
            return 1
        print("up to date")
        return 0
    for p, txt in outs.items():
        p.write_text(txt)
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
