#!/usr/bin/env python3
"""Deterministic builder of the A9.7 F2 filter-stage interface record (lane fo_a9_7_f2_filter_stage).

Writes
  docs/design_synthesis/f2_filter/f2_filter_stage_v1.json   (machine-readable deliverable)
  docs/design_synthesis/f2_filter/F2_FILTER_STAGE.md        (companion document, rendered from the same data)

What it is
  The record of the explicit filter-stage interface implemented in abep_sim/design/filter_stage.py: the parameter
  template (every physical value TBD until evidenced), the repository's present filter numbers recorded as
  PLACEHOLDER_NOT_A_FLIGHT_DESIGN with their locations, candidate filter concepts found in open literature (listed,
  never selected), deterministic demonstration cases of the interface (no-filter identity, fail-closed refusal of a
  TBD concept, the repository placeholder law as an explicitly labelled parametric sensitivity case), the conservation
  checks, interface demands to the other A9.7 lanes, new owner questions and the M16 impact.

What it is not: no filter design, no selection or ranking, no PASS, no performance prediction, no change to any
existing module, golden benchmark or the production path (UPSTREAM_ICD G-01 stays open for the production path).

Usage
  python docs/design_synthesis/f2_filter/build_f2_filter.py           # write both files
  python docs/design_synthesis/f2_filter/build_f2_filter.py --check   # exit 1 if either differs from a fresh build
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from abep_sim.design import filter_stage as fs  # noqa: E402
from abep_sim.design import owner_state as ost  # noqa: E402

LANE_DIR = "docs/design_synthesis/f2_filter/"
OUT_JSON = LANE_DIR + "f2_filter_stage_v1.json"
OUT_MD = LANE_DIR + "F2_FILTER_STAGE.md"
BUILDER = LANE_DIR + "build_f2_filter.py"
MODULE = "abep_sim/design/filter_stage.py"
TEST = "tests/test_design_f2_filter.py"
BASE_COMMIT = "1c9d7a648cd4ce739e587248693271e5115698e1"
DATE = "2026-10-01"
SPECIES = ("O", "N2", "O2")

# Immutable inputs only (owner decision records are immutable after commit). The sha256 is computed at build time and
# written to the JSON, so --check fails if a pinned file ever changes.
PINS = {
    "A97_MD": ("docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md",
               "owner directive A9.7 (verbatim)"),
    "A97": ("docs/decisions/OD_2026_10_01_A9_7_architecture_freeze_design_synthesis.json", "owner directive A9.7"),
    "ANS": ("docs/decisions/OD_2026_09_29_owner_answers_147.json", "147 owner answers (machine-readable)"),
}

REFERENCED_NOT_PINNED = (
    ("abep_sim/intake_tpmc.py", "placeholder filter defaults and law (mutable module; locations recorded by search)"),
    ("abep_sim/intake.py", "IntakeParams.filter and the production-path filter mass"),
    ("abep_sim/system.py", "BOM filter line"),
    ("abep_sim/mass_bom.py", "filter BOM item (TBD record)"),
    ("docs/interfaces/UPSTREAM_ICD.md", "IF-A1 / IF-A2 fields, gap G-01, open questions 1 and 5"),
    ("schemas/interfaces/upstream_icd_v1.json", "IF-A2 field definitions"),
    ("docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json", "A9B-02 protective / filter stage; AL-01 allocation"),
    ("docs/experiments/hall_icp/integration/m16_v4/subsystem_maturity_v4.json", "M16 row 2 'filter'"),
    ("docs/experiments/hall_icp/p4_anode_materials/p4_screening.py", "AO / material evidence vocabulary"),
    ("docs/experiments/lifetime_ao/ao_lifetime_register_v5.json", "AO / lifetime mechanisms AOL-M01..M11"),
    ("docs/requirements/rvm_a9/rvm_a9_v1.json", "RVM-08 atmospheric propellant, RVM-09 nascent O"),
    ("docs/EVIDENCE.md", "evidence levels 1-7 and quantity types"),
)

# --------------------------------------------------------------------------------------------------------------------
# repository placeholders: exact text searched in the (unmodified) modules; line numbers found at build time
# --------------------------------------------------------------------------------------------------------------------
PLACEHOLDER_PATTERNS = (
    ("PH-01", "abep_sim/intake_tpmc.py", "    filter: bool = False", "False", "-",
     "IntakeGeometry.filter switch (filter branch of the direct TPMC); default off"),
    ("PH-02", "abep_sim/intake_tpmc.py", "    filter_open_frac: float = 0.7", "0.7", "-",
     "open-area fraction of the filter element; multiplies eta_c and the passive-compression area"),
    ("PH-03", "abep_sim/intake_tpmc.py", "    filter_transmission: float = 0.6", "0.6", "-",
     "'thermal Clausing factor of the filter element' (code comment); no source"),
    ("PH-04", "abep_sim/intake_tpmc.py", "    filter_mass_per_m2: float = 0.8", "0.8", "kg/m^2",
     "filter areal mass; no source"),
    ("PH-05", "abep_sim/intake_tpmc.py",
     "        eta_c *= geom.filter_open_frac * geom.filter_transmission ** 0.5", "law", "-",
     "forward law 'hyperthermal, mostly transmitted' (code comment): eta_c x open_frac x transmission^0.5; no source"),
    ("PH-06", "abep_sim/intake_tpmc.py", "        K_back *= geom.filter_transmission", "law", "-",
     "backflow law: K_back x transmission; no source"),
    ("PH-07", "abep_sim/intake_tpmc.py", "        phi_eff = geom.phi * geom.filter_open_frac", "law", "-",
     "effective open fraction for the passive compression ratio"),
    ("PH-08", "abep_sim/intake_tpmc.py",
     "(geom.filter_mass_per_m2 * geom.area_m2 if geom.filter else 0.0)", "law", "kg",
     "filter mass added to the intake mass (direct TPMC)"),
    ("PH-09", "abep_sim/intake.py", "    filter: bool = False", "False", "-",
     "IntakeParams.filter switch (production path); default off"),
    ("PH-10", "abep_sim/intake.py", "            m_int += 0.8 * intake.area_m2", "0.8", "kg/m^2",
     "production path adds filter MASS only (no flow effect: UPSTREAM_ICD G-01)"),
    ("PH-11", "abep_sim/system.py", '"filter": 0.8 * cfg.intake.area_m2 if cfg.intake.filter else 0.0', "0.8",
     "kg/m^2", "BOM filter line in system.evaluate"),
)
ENABLE_SCAN_DIRS = ("abep_sim", "scripts")
ENABLE_PATTERNS = ("filter=True", ".filter = True")


def sha256_file(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def find_line(rel: str, text: str) -> int:
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    hits = [i + 1 for i, ln in enumerate(lines) if text in ln]
    if len(hits) != 1:
        raise SystemExit(f"placeholder pattern {text!r} found {len(hits)} times in {rel} (expected exactly 1)")
    return hits[0]


def scan_enabled() -> list:
    out = []
    for d in ENABLE_SCAN_DIRS:
        for p in sorted((REPO / d).rglob("*.py")):
            rel = p.relative_to(REPO).as_posix()
            if rel.startswith("abep_sim/design/"):
                continue
            for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines()):
                if any(k in ln for k in ENABLE_PATTERNS):
                    out.append(f"{rel}:{i + 1}")
    return out


def placeholders() -> list:
    vals = fs.repository_placeholder_values()
    out = []
    for pid, rel, text, value, units, what in PLACEHOLDER_PATTERNS:
        out.append({"id": pid, "location": f"{rel}:{find_line(rel, text)}", "file": rel, "text": text.strip(),
                    "value": value, "units": units, "what": what, "source": "none in the repository (unsourced)",
                    "evidence_class": "assumed", "status": fs.PLACEHOLDER,
                    "used_by_f2": "never silently; only through filter_stage.placeholder_sensitivity_case "
                                  "(label PARAMETRIC_SENSITIVITY / PLACEHOLDER_NOT_A_FLIGHT_DESIGN)"})
    return out, vals


# --------------------------------------------------------------------------------------------------------------------
# sources
# --------------------------------------------------------------------------------------------------------------------
SOURCES = {
    "LIVESEY1998": {
        "citation": "R. G. Livesey, 'Flow of gases through tubes and orifices', chapter 2 in J. M. Lafferty (ed.), "
                    "Foundations of Vacuum Science and Technology, John Wiley & Sons, 1998, ISBN 0-471-17593-5, "
                    "pp. 81-140",
        "url": "https://atomoptics-nas.uoregon.edu/~tbrown/files/strontium_vacuum_system/Research%20Papers/"
               "Livesey_mod.pdf",
        "accessed": DATE, "retrieved_pdf_sha256": "9afa467667464ef5a06a6e5fece4e87cf01ce2979312a9999e1cecce89445d0b",
        "access": "openly reachable PDF (scan with text layer) on a university server; copyright Wiley; short "
                  "quotations and a numeric table transcription only",
        "locators": {"Table 2.1 (p. 82)": "Molecular Kn > 0.5; Transitional 0.5 > Kn > 0.01; Continuum Kn < 0.01",
                     "Sec. 2.2 (p. 86)": "conductance of a duct = entrance aperture conductance multiplied by the "
                                         "transmission probability (Eq. 2.14); aperture conductance Eq. 2.15 "
                                         "(rate of impingement over the aperture area, i.e. A cbar / 4)",
                     "Sec. 2.2 (p. 86) text": "'If N2 molecules arrive at the entrance plane of a duct then the "
                                              "number of these which reach the exit plane is N2 alpha, and N2 (1 - "
                                              "alpha) return to the entrance. Similarly, of N1 molecules striking "
                                              "the exit plane (from a downstream chamber), N1 alpha reach the "
                                              "entrance.'",
                     "Table 2.5 (p. 89)": "transmission probabilities for cylindrical tubes, Cole [11] column, "
                                          "l/d 0.05 - 500"},
        "evidence_level": 4, "quantity_type": "model-derived (tabulated computation) / published convention",
    },
    "ANDREUSSI2022": {
        "citation": "T. Andreussi, E. Ferrato, V. Giannetti, 'A review of air-breathing electric propulsion: from "
                    "mission studies to technology verification', J. Electr. Propuls. 1:31 (2022)",
        "doi": "10.1007/s44205-022-00024-9",
        "url": "https://link.springer.com/content/pdf/10.1007/s44205-022-00024-9.pdf",
        "accessed": DATE, "retrieved_pdf_sha256": "490ca6f6b763fe4ee1089d9815d4075a94223ec74d577f61d67986708c3ce3b7",
        "access": "open access, CC BY 4.0 (statement on p. 1)",
        "evidence_level": 5, "quantity_type": "qualitative (review / secondary)",
    },
    "DICARA2007": {
        "citation": "D. Di Cara, J. Gonzalez del Amo, A. Santovincenzo, B. Carnicero Dominguez, M. Arcioni, "
                    "A. Caldwell, I. Roma, 'RAM Electric Propulsion for Low Earth Orbit Operation: an ESA study', "
                    "30th International Electric Propulsion Conference, Florence, IEPC-2007-162 (2007)",
        "url": "https://electricrocket.org/IEPC/IEPC-2007-162.pdf",
        "accessed": DATE, "retrieved_pdf_sha256": "5b738b6c3f4f478b0f82fdf0ec2b406435c21845385469b09aad43660428e960",
        "access": "open (ERPS IEPC archive)",
        "evidence_level": 5, "quantity_type": "qualitative (system concept study)",
    },
    "PFEIFFER_TMP_SCREEN": {
        "citation": "Pfeiffer Vacuum, 'The 10 Most Common Mistakes When Using Turbomolecular Vacuum Pumps and How to "
                    "Avoid Them' (knowledge web page), section on protective screens / splinter shields",
        "url": "https://www.pfeiffervacuum.com/be/en/knowledge/mistakes-using-turbomolecular-vacuum-pumps.html",
        "accessed": DATE, "retrieved_pdf_sha256": None,
        "access": "open web page read through a fetch-tool summary (quotes as returned by the tool; verify against "
                  "the page); no contact with the supplier",
        "evidence_level": 5, "quantity_type": "published analog (ground vacuum pump; supplier statement)",
    },
}


def concepts() -> list:
    base_tbd = "all F2 interface parameters TBD (FilterStage.tbd): apply() refuses in evidence mode"
    return [
        {"id": "FC-00", "name": "no filter stage ('none')", "function": "trade-study reference: definitional identity "
         "(tau = 1, nothing lost, no pressure effect, zero mass)", "sources": [],
         "evidence": "definition", "interface_status": "NUMERIC by definition (FilterStage.none)",
         "admissibility": f"{ost.status_label('F2-OQ-03')} (F2-OQ-03): reference bound only, never an admissible "
                          "architecture option (the RFP chain names a filter stage)",
         "ao_applicability": "not applicable (no element)", "candidate_status": "LISTED_ONLY_NO_SELECTION"},
        {"id": "FC-01", "name": "inlet grid system at the collector entrance",
         "function": "stated: 'to stop the particles at the entrance of the collector'. Whether 'particles' means "
                     "contaminant particulates or gas molecules (a backflow-limiting grid) is not stated: AMBIGUOUS",
         "sources": [{"id": "DICARA2007", "locator": "Sec. E 'Collector Design', p. 5",
                      "quote": "a higher surface area of 0.6m2 was allocated to the collector intake, to take into "
                               "account the grid system used to stop the particles at the entrance of the collector, "
                               "and an extra design margin"},
                     {"id": "ANDREUSSI2022", "locator": "p. 17", "quote": "A grid system was used to stop the "
                                                                          "particles at the inlet."}],
         "evidence": "level 5, qualitative; the 0.6 m2 vs 0.15 m2 area allocation combines the grid and a design "
                     "margin and cannot be separated (no transmission, mass or material given)",
         "interface_status": base_tbd, "ao_applicability": "INCOMPLETE_EVIDENCE (no material stated)",
         "candidate_status": "LISTED_ONLY_NO_SELECTION"},
        {"id": "FC-02", "name": "perforated plate / multi-hole molecular screen (generic vacuum element)",
         "function": "geometric screen in free-molecular flow; its conductance follows from hole geometry "
                     "(filter_stage.perforated_plate_alpha: open fraction x Cole alpha(l/d))",
         "sources": [{"id": "LIVESEY1998", "locator": "Eqs. 2.14-2.15, Table 2.1, Table 2.5",
                      "quote": "conductance of a duct ... is given by the entrance aperture conductance multiplied by "
                               "the transmission probability"}],
         "evidence": "level 4 model for the diffuse-incidence transmission and conductance of a defined geometry; "
                     "capture, conversion (O recombination), mass and protection efficiency are not given by it",
         "interface_status": "alpha_conductance and diffuse tau can be MODEL_DERIVED once a geometry is defined; "
                             "capture / conversion / mass / Kn remain TBD -> apply() refuses",
         "ao_applicability": "INCOMPLETE_EVIDENCE (material OPEN)", "candidate_status": "LISTED_ONLY_NO_SELECTION"},
        {"id": "FC-03", "name": "wire-mesh protective screen ('splinter shield') ahead of a rotating pump stage",
         "function": "keeps solid objects out of a turbomolecular rotor (relevant analog for the F3 compressor "
                     "rotor); costs conductance",
         "sources": [{"id": "PFEIFFER_TMP_SCREEN", "locator": "protective screens / splinter shields",
                      "quote": "Foreign objects falling into the turbopump rotor can cause irreparable damage. ... "
                               "fit a splinter shield or protective screen in the inlet flange of the turbopump. ... "
                               "the pumping speed to be reduced - by up to 30% depending on the gas type."}],
         "evidence": "level 5 published analog (ground pump, supplier statement): 'up to 30 %' pumping-speed "
                     "reduction depending on gas; not transferable as a flight value",
         "interface_status": base_tbd, "ao_applicability": "INCOMPLETE_EVIDENCE",
         "candidate_status": "LISTED_ONLY_NO_SELECTION"},
        {"id": "FC-04", "name": "charged-particle (ion) filter ahead of the neutral path",
         "function": "separates charged particles from neutrals (ground instrument precedent); for ABEP it would "
                     "reject ambient ions / electrons; the need is not evaluated here",
         "sources": [{"id": "ANDREUSSI2022", "locator": "p. 44 (DISCOVERER facility detection system)",
                      "quote": "The detection system is composed of four stages: an ion filter used to separate "
                               "charged particles from the neutral ones, followed by an ioniser, a time-of-flight and "
                               "an analyser."}],
         "evidence": "level 5, qualitative, ground diagnostic instrument (not a propellant-path element)",
         "interface_status": base_tbd + "; ambient charged-particle flux at IF-A1 is TBD",
         "ao_applicability": "INCOMPLETE_EVIDENCE", "candidate_status": "LISTED_ONLY_NO_SELECTION"},
        {"id": "FC-05", "name": "thick collimating grid passing only near-axial velocities",
         "function": "direction filter (ground AO-source precedent); a honeycomb intake already acts similarly",
         "sources": [{"id": "ANDREUSSI2022", "locator": "p. 42 (JAXA AO source)",
                      "quote": "The source has a compact design, with a transverse magnetic field and a thick grid in "
                               "front to filter only the particles with an axial velocity."}],
         "evidence": "level 5, qualitative, facility device",
         "interface_status": base_tbd + " (forward incidence hyperthermal_directed)",
         "ao_applicability": "INCOMPLETE_EVIDENCE", "candidate_status": "LISTED_ONLY_NO_SELECTION"},
        {"id": "FC-06", "name": "catalytic atomic-O recombination element (deliberate O -> O2 conversion)",
         "function": "would protect downstream surfaces from atomic O by converting it; conflicts with the owner "
                     "row-102 baseline (inert / low-recombination lining, preserve the representative atomic-O "
                     "fraction)",
         "sources": [], "source_status": "TBD - no open-literature source for an ABEP filter of this kind was located "
                                         "in this lane; abep_sim/aochem.py RECOMB_GAMMA values carry no per-entry "
                                         "source and are not used",
         "evidence": "none", "interface_status": base_tbd, "ao_applicability": "INCOMPLETE_EVIDENCE",
         "candidate_status": f"LISTED_ONLY_NO_SELECTION (admissibility {ost.status_label('F2-OQ-02')}, F2-OQ-02: not "
                             "the baseline)"},
        {"id": "FC-07", "name": "Xe cathode-line filter / getter (owner row 51)",
         "function": "Xe purity for the C1 LaB6 branch - Xe path, NOT the atmospheric filter stage",
         "sources": [{"id": "owner row 51", "locator": "docs/decisions/OD_2026_09_29_owner_answers_147.json",
                      "quote": "include the filter/getter with explicit <=17 W-class load only after vendor/spec "
                               "verification"}],
         "evidence": "owner-stated scope", "interface_status": "out of F2 scope (listed to avoid confusion)",
         "ao_applicability": "not applicable", "candidate_status": "OUT_OF_SCOPE_XE_PATH"},
    ]


# --------------------------------------------------------------------------------------------------------------------
# demonstration cases (deterministic, normalized inputs only)
# --------------------------------------------------------------------------------------------------------------------
def normalized_inlet(incidence: str) -> fs.InletState:
    return fs.InletState(
        mdot_forward_kgps={s: 1.0 for s in SPECIES}, mdot_back_incident_kgps={s: 0.0 for s in SPECIES},
        back_incident_basis="normalized demonstration: no downstream incident flux (the coupled plenum flux is "
                            "abep_sim/design/plenum_feed.py, F4-ID-03/04); not a state",
        T_gas_K=None, incidence=incidence, knudsen_number=None, label="NORMALIZED_UNIT_INPUT",
        provenance="unit mass flow per species (1 kg/s each) to expose fractions; not an IF-A1 state")


def _round(o, nd=12):
    if isinstance(o, float):
        return float(f"{o:.{nd}g}")
    if isinstance(o, dict):
        return {k: _round(v, nd) for k, v in o.items()}
    if isinstance(o, list):
        return [_round(v, nd) for v in o]
    return o


def placeholder_stage() -> fs.FilterStage:
    return fs.FilterStage.tbd("F2-PLACEHOLDER", "FC-REPO", species=SPECIES, forward_incidence="hyperthermal_directed",
                              description="repository filter law (PLACEHOLDER_NOT_A_FLIGHT_DESIGN) as a stage whose "
                                          "parameters are all TBD; numbers only via the labelled sensitivity case")


def demonstrations() -> list:
    out = []
    r = fs.FilterStage.none(SPECIES).apply(normalized_inlet("diffuse_thermal"))
    out.append({"id": "DC-01", "what": "FC-00 no-filter identity on a normalized inlet", "result": r.to_dict(),
                "f3_record": r.to_f3_record()})
    tbd = fs.FilterStage.tbd("F2-TBD", "FC-02", species=SPECIES)
    r = tbd.apply(normalized_inlet("diffuse_thermal"))
    out.append({"id": "DC-02", "what": "any listed concept with TBD parameters, evidence mode: fail closed",
                "result": {"status": r.status, "label": r.label, "n_missing": len(r.missing),
                           "missing_parameters": [m["parameter"] for m in r.missing]},
                "f3_record": r.to_f3_record(), "backflow_coupling": tbd.backflow_coupling(None)})
    st = placeholder_stage()
    case = fs.placeholder_sensitivity_case(st)
    r = st.apply(normalized_inlet("hyperthermal_directed"), case)
    out.append({"id": "DC-03", "what": "repository placeholder law as an explicit labelled sensitivity case "
                                       "(PARAMETRIC_SENSITIVITY / PLACEHOLDER_NOT_A_FLIGHT_DESIGN)",
                "case": {"case_id": case.case_id, "label": case.label, "rationale": case.rationale,
                         "regime_assumption": case.regime_assumption,
                         "temperature_override_K": case.temperature_override_K},
                "result": r.to_dict(), "f3_record": r.to_f3_record(), "f1_record": r.to_f1_record(),
                "backflow_coupling": st.backflow_coupling(case.temperature_override_K, case)})
    r = tbd.apply(normalized_inlet("hyperthermal_directed"))
    out.append({"id": "DC-04", "what": "incidence mismatch (tau_f declared for diffuse_thermal, inlet hyperthermal)",
                "result": {"status": r.status, "missing": r.missing}})
    return [_round(x) for x in out]


def parameter_template() -> list:
    st = fs.FilterStage.tbd("F2-TEMPLATE", "any", species=SPECIES)
    items = []
    for pid, ev in st.parameters().items():
        d = ev.to_dict()
        items.append({"id": pid, "value": d["value"], "units": d["units"], "basis": d["requires"],
                      "source": "TBD", "evidence_class": "TBD", "status": d["status"]})
    items.append({"id": "knudsen_criterion", "value": fs.KN_MOLECULAR_MIN, "units": "-",
                  "basis": "free-molecular laws (transmission probability, conductance) applied only for Kn > 0.5; "
                           "otherwise OUT_OF_DOMAIN", "source": fs.KN_SOURCE,
                  "evidence_class": "published convention", "status": "EVIDENCED"})
    items.append({"id": "conductance_law", "value": "C_s = alpha_s * A * cbar_s / 4; cbar_s = sqrt(8 k T / (pi m_s))",
                  "units": "m^3/s", "basis": "free molecular; dp_s = Q_s / C_s for the net throughput",
                  "source": "LIVESEY1998 Eqs. 2.14-2.15 and Sec. 2.2", "evidence_class": "model-derived",
                  "status": "MODEL_DERIVED"})
    items.append({"id": "conversion_channels", "value": {k: v for k, v in fs.CONVERSION_PRODUCTS.items()},
                  "units": "mass yield", "basis": "definitional stoichiometry O + O -> O2; fraction converted is TBD",
                  "source": "definition", "evidence_class": "definition", "status": "DEFINITION"})
    items.append({"id": "AL-01_allocation_share", "value": "TBD", "units": "kg",
                  "basis": "owner row 54 allocates 3.5 kg to 'intake/filter/duct' jointly (allocation, not a CBE); "
                           "no filter share is defined", "source": "docs/decisions/OD_2026_09_29_owner_answers_147.json "
                                                                  "row 54", "evidence_class": "owner-allocation",
                  "status": "TBD"})
    return items


def interface_demands() -> list:
    return [
        {"id": "F2-IF-01", "direction": "F2 <- F1", "counterpart": "abep_sim/design/intake_synthesis.py (F1-ID-01; IF-A1 "
                                                                    "records if_a1_record())",
         "content": "per-species mass flow arriving at the filter inlet face (IF-A1), forward incidence "
                    "(diffuse_thermal | hyperthermal_directed), gas temperature, Knudsen number at the filter (mean "
                    "free path and characteristic dimension), intake exit area, evidence labels",
         "units": "kg/s; K; -; m^2", "status": "PROVIDED BY F1 (F1-ID-01); consumed through F4 (F4-ID-01, F4-ID-03)"},
        {"id": "F2-IF-02", "direction": "F2 -> F1", "counterpart": "abep_sim/design/intake_synthesis.py (F1-ID-02)",
         "content": "FilterResult.to_f1_record(): per-species gross mass flow returned upstream (forward reflection + "
                    "backflow transmission + upstream conversion products); it changes the intake back-pressure "
                    "and K_back seen by F1", "units": "kg/s", "status": "DEFINED (numbers only when apply is NUMERIC)"},
        {"id": "F2-IF-03", "direction": "F2 -> F3", "counterpart": "abep_sim/design/compressor_synthesis.py (IFD-F3-02)",
         "content": "FilterResult.to_f3_record(): per-species net / gross mass flow at the compressor inlet, "
                    "w_s / x_s, conductance and pressure difference per species, retained mass rate, "
                    "filter_flow_effect_applied, filter mass, labels and overrides (UPSTREAM_ICD IF-A2 fields)",
         "units": "kg/s; -; m^3/s; Pa; kg", "status": "DEFINED (NOT_EVALUATED while any input is TBD)"},
        {"id": "F2-IF-04", "direction": "F2 <- F3", "counterpart": "abep_sim/design/compressor_synthesis.py (IFD-F3-03)",
         "content": "compressor inlet face area, per-species backstreaming flux from the compressor inlet, wear / "
                    "debris emission of the rotor (protection target sputter_wear_products), particulate tolerance "
                    "of the rotor (what the filter must stop)", "units": "m^2; kg/s; -",
         "status": "TBD_AFTER_EVIDENCE"},
        {"id": "F2-IF-05", "direction": "F2 <-> F4", "counterpart": "abep_sim/design/plenum_feed.py (F4-ID-03, "
                                                                    "F4-ID-04)",
         "content": "FilterStage.backflow_coupling(): per unit mass flow arriving at the outlet face, fractions to "
                    "upstream / reflected to plenum / captured / converted, and C_s; F4 returns the downstream "
                    "incident flux per species (InletState.mdot_back_incident_kgps, required, never defaulted)",
         "units": "-; m^3/s; kg/s", "status": "DEFINED (numbers only when the records are usable)"},
        {"id": "F2-IF-06", "direction": "F2 -> F7", "counterpart": "abep_sim/design/architecture_optimizer.py (F78-ID-03, "
                                                                  "context axis)",
         "content": "x_filter design-vector component: concept id + geometry design variables; result labels "
                    "propagate (a sensitivity label is never a design value)", "units": "-", "status": "DEFINED"},
        {"id": "F2-IF-07", "direction": "F2 -> mass budget",
         "counterpart": "docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json (A9B-02, AL-01)",
         "content": "filter mass = areal mass x face area (TBD); AL-01 3.5 kg covers intake/filter/duct jointly",
         "units": "kg", "status": "TBD_AFTER_EVIDENCE"},
        {"id": "F2-IF-08", "direction": "F2 -> P4 materials",
         "counterpart": "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json",
         "content": "an APP-FILTER application (O / AO exposure at filter temperature, recombination probability "
                    "and erosion yield criteria) would be needed; P4 today screens APP-ANODE and APP-COLLECTOR only",
         "units": "-", "status": f"{ost.status_label('F2-OQ-04')} (F2-OQ-04: filter at the compressor inlet; "
                                  "P4 adds APP-FILTER)"},
        {"id": "F2-IF-09", "direction": "F2 -> AO / lifetime register",
         "counterpart": "docs/experiments/lifetime_ao/ao_lifetime_register_v5.json",
         "content": "no AOL mechanism covers a filter element (AOL-M01..M11); a future register revision would add "
                    "filter erosion / recombination and filter-emitted contamination", "units": "-",
         "status": "TBD_AFTER_EVIDENCE"},
        {"id": "F2-IF-10", "direction": "F2 -> upstream ICD", "counterpart": "docs/interfaces/UPSTREAM_ICD.md "
                                                                             "IF-A1 / IF-A2, gap G-01",
         "content": "this design-layer interface supplies a separate filter element with its own transmission; "
                    "the production path (intake.collection) is unchanged, so G-01 stays open there (moving it is a "
                    "model change: UPSTREAM_ICD open question 1)", "units": "-", "status": "DEFINED"},
        {"id": "F2-IF-11", "direction": "F2 -> F0", "counterpart": "docs/performance/PERFORMANCE_BASELINE_98fbbb9.json",
         "content": "the filter stage is O(n_species) arithmetic; not a profiling hotspot, not a Rust candidate",
         "units": "-", "status": "DEFINED"},
    ]


def open_owner_questions() -> list:
    """As raised by the lane (status_as_raised TBD_OWNER) with the owner_questions_state_v5 answer applied (RVF-02)."""
    return ost.apply_to_questions(_open_owner_questions_as_raised())


def _open_owner_questions_as_raised() -> list:
    return [
        {"id": "F2-OQ-01", "question": "Which protection functions must the RFP filter stage provide (particulates / "
         "debris, compressor wear products, atomic O to downstream surfaces, ambient charged particles, backflow "
         "limitation), and against which quantitative acceptance?",
         "why": "the RFP chain names a filter but no function or acceptance is recorded in the repository; every "
                "capture efficiency is TBD", "status": "TBD_OWNER"},
        {"id": "F2-OQ-02", "question": "Is a deliberately catalytic (O -> O2 converting) filter element admissible, "
         "given owner row 102 (inert / low-recombination lining baseline to preserve the representative atomic-O "
         "fraction)?", "why": "FC-06 would trade downstream AO protection against the delivered species state",
         "status": "TBD_OWNER"},
        {"id": "F2-OQ-03", "question": "May trade studies carry 'no filter' (FC-00) as an admissible architecture "
         "option, or only as a reference bound because the RFP chain names a filter stage?",
         "why": "the RFP architecture text is recorded only as a secondary transcription (RVM-08, verify)",
         "status": "TBD_OWNER"},
        {"id": "F2-OQ-04", "question": "Where does the filter sit (ahead of the intake collimator, in the intake "
         "chamber, or at the compressor inlet), and should P4 add an APP-FILTER application for its material?",
         "why": "placement fixes the forward incidence (hyperthermal vs thermalised), the face area and the O "
                "exposure; P4 screens only anode and collector", "status": "TBD_OWNER"},
    ]


def related_existing_open() -> list:
    return [
        {"ref": "docs/interfaces/UPSTREAM_ICD.md sec. 9 question 1 (G-01)", "topic": "filter as a separate element on "
         "the production path (model change; could move goldens)", "relation": "not answered here; F2 is design-layer"},
        {"ref": "docs/interfaces/UPSTREAM_ICD.md sec. 9 question 5 (G-11)", "topic": "contamination scope",
         "relation": "F2 protection targets use it; not answered here"},
        {"ref": "owner_questions_state_v4 XA9Q-05", "topic": "Xe getter for a G-XE ICP feed",
         "relation": "Xe path; out of F2 scope"},
    ]


def owner_answers_applied() -> list:
    a = {r["row"]: r for r in json.loads((REPO / PINS["ANS"][0]).read_text(encoding="utf-8"))["answers"]}
    how = {54: "AL-01 'intake/filter/duct' 3.5 kg is a joint allocation, not a CBE; filter mass stays TBD",
           102: "never assume O survival: O capture / conversion on the filter are TBD; catalytic concept FC-06 "
                "flagged (F2-OQ-02)",
           132: "material AO evidence from N2 + O2 exposure is labelled NO_ATOMIC_O and is never AO proof "
                "(MaterialApplicability refuses it)",
           51: "the Xe cathode-line filter / getter is a Xe-path item (FC-07, out of F2 scope)"}
    return [{"row": r, "covers_ids": a[r]["covers_ids"],
             "answer_sha256": hashlib.sha256(a[r]["owner_answer_verbatim"].encode("utf-8")).hexdigest(),
             "how_applied": h} for r, h in how.items()]


def build() -> dict:
    phs, ph_vals = placeholders()
    enabled = scan_enabled()
    cole = [{"l_over_d": x, "alpha": y} for x, y in fs.COLE_TABLE_2_5]
    doc = {
        "schema": "abep.a9_7.f2_filter_stage.v1",
        "id": "F2_FILTER_STAGE_V1",
        "title": "A9.7 F2 - explicit filter-stage interface (intake exit -> compressor inlet)",
        "lane": "fo_a9_7_f2_filter_stage",
        "directive": "docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md sec. F2",
        "date": DATE, "base_commit": BASE_COMMIT, "generated_by": BUILDER, "module": MODULE,
        "companion_document": OUT_MD, "test": TEST,
        "status": "INTERFACE_IMPLEMENTED_NO_FILTER_DESIGN_NO_SELECTION",
        "a9_status": "INVESTIGATION_HYPOTHESIS (architecture); filter concept OPEN",
        "what_this_is_not": [
            "not a filter design, sizing or selection; no concept is ranked",
            "not evidence: demonstration cases use normalized unit inputs; the placeholder case is a labelled "
            "parametric sensitivity",
            "not a change to the production path: abep_sim/intake.py, intake_tpmc.py, system.py are unmodified and "
            "UPSTREAM_ICD G-01 stays open there; goldens do not move",
            "no PASS, SELECTED, WINNER or QUALIFIED status anywhere",
        ],
        "pins": {k: {"path": p, "sha256": sha256_file(p), "role": role} for k, (p, role) in PINS.items()},
        "referenced_not_pinned": [{"path": p, "why": w} for p, w in REFERENCED_NOT_PINNED],
        "vocabulary": {"quantity_types": list(fs.QUANTITY_TYPES), "ev_statuses": list(fs.EV_STATUSES),
                       "usable_statuses": list(fs.USABLE_STATUSES), "ao_gate_outcomes": list(fs.AO_GATE_OUTCOMES),
                       "surrogate_labels": list(fs.SURROGATE_LABELS), "protection_targets": list(fs.PROTECTION_TARGETS),
                       "incidences": list(fs.INCIDENCES), "result_statuses": list(fs.RESULT_STATUSES),
                       "result_labels": [fs.LABEL_EVIDENCE, fs.LABEL_SENSITIVITY, fs.LABEL_NORMALIZED],
                       "never_emitted_as_status": list(fs.FORBIDDEN_STATUS_WORDS)},
        "interface_model": {
            "per_species_direction": "for d in {forward (inlet face), backflow (outlet face)}: transmitted + "
                                     "reflected + captured + converted = 1; reflected derived = 1 - tau - capture - "
                                     "conversion (refused if negative); lost = captured + converted",
            "products": "converted mass of s is added to its product species (CONVERSION_PRODUCTS) and routed to the "
                        "outlet face with product_to_outlet (TBD), the rest to the inlet face",
            "outlet": "gross_downstream = forward transmitted + backflow reflected + products to outlet; "
                      "net_downstream = gross_downstream - backflow incident; gross_upstream = forward reflected + "
                      "backflow transmitted + products to inlet",
            "pressure": "free molecular only (Kn > 0.5): C_s = alpha_s A cbar_s / 4; dp_s = (mdot_net,s / m_s) k T "
                        "/ C_s",
            "mass": "face area x areal mass",
            "fail_closed": "evidence mode refuses (REFUSED_TBD) when any needed record is TBD, a placeholder or "
                           "assumed; OUT_OF_DOMAIN for Kn <= 0.5 or an incidence mismatch; numbers with TBD inputs "
                           "only through a SensitivityCase (label PARAMETRIC_SENSITIVITY_NOT_EVIDENCE)",
            "none_option": "FilterStage.none(): definitional identity for trade studies",
            "conservation_tolerance": fs.CONSERVATION_TOL,
        },
        "items": parameter_template(),
        "cole_table_2_5": {"source": fs.COLE_SOURCE, "rows": cole,
                           "use": "cole_transmission_probability(l/d); exact at tabulated points, log-log "
                                  "interpolation between, refusal outside [0.05, 500]"},
        "repository_placeholders": {
            "rule": "recorded as PLACEHOLDER_NOT_A_FLIGHT_DESIGN; never used silently",
            "values_read_from_IntakeGeometry_defaults": ph_vals,
            "filter_enabled_anywhere": enabled or "no (scan of abep_sim/ (excluding design/) and scripts/ for "
                                                  "'filter=True' / '.filter = True')",
            "records": phs,
            "related_unsourced_priors_not_used": [
                "abep_sim/aochem.py RECOMB_GAMMA and EROSION_YIELD_CM3_PER_ATOM ('literature-class priors' without "
                "per-entry sources): not filter values, not used by F2"],
        },
        "candidate_concepts": concepts(),
        "source_register": SOURCES,
        "demonstration_cases": demonstrations(),
        "interface_demands": interface_demands(),
        "open_owner_questions": open_owner_questions(),
        "related_existing_open_questions": related_existing_open(),
        "owner_answers_applied": owner_answers_applied(),
        "m16_impact": [{"m16_row": 2, "key": "filter", "how_touched": "an explicit design-layer filter-stage "
                        "interface, placeholder register and concept list now exist (software / documentation only)",
                        "readiness_change": "NONE - row stays BLOCKED; no filter concept, geometry, material or "
                                            "measured property exists; framework implementation is not evidence"}],
        "findings": [
            "The repository's only filter numbers (open fraction 0.7, transmission 0.6, 0.8 kg/m2, the "
            "open_frac x transmission^0.5 forward law) are unsourced and the filter is disabled everywhere; they are "
            "recorded as PLACEHOLDER_NOT_A_FLIGHT_DESIGN.",
            "No open-literature ABEP source located here gives a filter transmission, capture efficiency, mass or "
            "material; the ESA RAM-EP study mentions a grid 'to stop the particles' without numbers.",
            "Free-molecular conductance of a defined geometric screen is model-derivable (Livesey / Cole); capture, "
            "O conversion and protection efficiency are not, so every real concept fails closed today.",
            "The 'none' option is the exact identity; whether it is admissible against the RFP chain is an owner "
            "question.",
        ],
    }
    return doc


# --------------------------------------------------------------------------------------------------------------------
# markdown
# --------------------------------------------------------------------------------------------------------------------
def render_md(doc: dict) -> str:
    L = []
    a = L.append
    a(f"# {doc['title']}")
    a("")
    a(f"Generated by `{doc['generated_by']}` from `{OUT_JSON}` (do not edit by hand; `--check` verifies). "
      f"Lane `{doc['lane']}`, directive {doc['directive']}. Status **{doc['status']}**; {doc['a9_status']}.")
    a("")
    a("## What this is not")
    for x in doc["what_this_is_not"]:
        a(f"- {x}")
    a("")
    a("## Interface model")
    for k, v in doc["interface_model"].items():
        a(f"- **{k}**: {v}")
    a("")
    a(f"Module: `{doc['module']}`. Test: `{doc['test']}`.")
    a("")
    a("## Parameters (template: every physical value TBD until evidenced)")
    a("")
    a("| id | value | units | status | evidence class | source / requires |")
    a("|---|---|---|---|---|---|")
    for it in doc["items"]:
        v = it["value"] if not isinstance(it["value"], dict) else json.dumps(it["value"])
        src = it["source"] if it["source"] != "TBD" else f"TBD - {it['basis']}"
        a(f"| {it['id']} | {v} | {it['units']} | {it['status']} | {it['evidence_class']} | {src} |")
    a("")
    a("## Repository placeholders (PLACEHOLDER_NOT_A_FLIGHT_DESIGN)")
    a("")
    rp = doc["repository_placeholders"]
    a(f"Rule: {rp['rule']}. Filter enabled anywhere: {rp['filter_enabled_anywhere']}.")
    a("")
    a("| id | location | value | units | what |")
    a("|---|---|---|---|---|")
    for p in rp["records"]:
        a(f"| {p['id']} | `{p['location']}` | {p['value']} | {p['units']} | {p['what']} |")
    a("")
    for x in rp["related_unsourced_priors_not_used"]:
        a(f"- related, not used: {x}")
    a("")
    a("## Candidate filter concepts (open literature; listed only, no selection)")
    a("")
    for c in doc["candidate_concepts"]:
        a(f"### {c['id']} - {c['name']}")
        a(f"- function: {c['function']}")
        if c["sources"]:
            for s in c["sources"]:
                a(f"- source {s['id']} ({s['locator']}): \"{s['quote']}\"")
        else:
            a(f"- source: {c.get('source_status', 'none (definition)')}")
        a(f"- evidence: {c['evidence']}")
        a(f"- interface status: {c['interface_status']}")
        a(f"- AO applicability: {c['ao_applicability']}")
        a(f"- candidate status: {c['candidate_status']}")
        a("")
    a("## Demonstration cases (normalized unit inputs; not physical states)")
    a("")
    a("| id | what | status | label |")
    a("|---|---|---|---|")
    for d in doc["demonstration_cases"]:
        r = d["result"]
        a(f"| {d['id']} | {d['what']} | {r.get('status')} | {r.get('label', '-')} |")
    a("")
    dc3 = [d for d in doc["demonstration_cases"] if d["id"] == "DC-03"][0]
    a("DC-03 per-species forward fractions (repository placeholder law, sensitivity only):")
    a("")
    a("| species | transmitted | reflected | lost | conductance m^3/s |")
    a("|---|---|---|---|---|")
    for s, v in dc3["result"]["species"].items():
        f = v["fractions_forward"]
        a(f"| {s} | {f['transmitted']:.6g} | {f['reflected']:.6g} | {f['lost']:.6g} | "
          f"{v['conductance_m3_s']:.6g} |")
    a("")
    a("## Cole transmission probabilities (Livesey 1998 Table 2.5)")
    a("")
    a(" ".join(f"{r['l_over_d']}: {r['alpha']};" for r in doc["cole_table_2_5"]["rows"]))
    a("")
    a("## Interface demands")
    a("")
    a("| id | direction | counterpart | content | status |")
    a("|---|---|---|---|---|")
    for d in doc["interface_demands"]:
        a(f"| {d['id']} | {d['direction']} | {d['counterpart']} | {d['content'].replace('|', '/')} | "
          f"{d['status']} |")
    a("")
    a("## Owner questions raised by this lane")
    a("")
    a(f"Status from `{ost.OQ5_REL}` (as raised: TBD_OWNER).")
    a("")
    for q in doc["open_owner_questions"]:
        a(f"- **{q['id']}** ({q['status']}): {q['question']} Why: {q['why']}")
    a("")
    a("Related existing open questions (not answered here):")
    for q in doc["related_existing_open_questions"]:
        a(f"- {q['ref']}: {q['topic']} - {q['relation']}")
    a("")
    a("## Owner answers applied")
    a("")
    for x in doc["owner_answers_applied"]:
        a(f"- row {x['row']} ({', '.join(x['covers_ids'])}, `{x['answer_sha256'][:16]}`): {x['how_applied']}")
    a("")
    a("## M16 impact")
    for m in doc["m16_impact"]:
        a(f"- row {m['m16_row']} `{m['key']}`: {m['how_touched']}; readiness change: {m['readiness_change']}")
    a("")
    a("## Sources")
    for k, s in doc["source_register"].items():
        a(f"- **{k}**: {s['citation']}. {s['url']} (accessed {s['accessed']}; {s['access']}; evidence level "
          f"{s['evidence_level']}, {s['quantity_type']})")
    a("")
    a("## Findings")
    for f in doc["findings"]:
        a(f"- {f}")
    a("")
    a("## Pins (immutable inputs)")
    for k, p in doc["pins"].items():
        a(f"- {k}: `{p['path']}` sha256 `{p['sha256']}` ({p['role']})")
    a("")
    return "\n".join(L)


def outputs() -> tuple[str, str]:
    doc = build()
    js = json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=False) + "\n"
    return js, render_md(doc) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the committed outputs differ from a fresh build")
    args = ap.parse_args(argv)
    js, md = outputs()
    if args.check:
        bad = [p for p, c in ((OUT_JSON, js), (OUT_MD, md))
               if not (REPO / p).exists() or (REPO / p).read_text(encoding="utf-8") != c]
        if bad:
            print("OUT OF DATE: " + ", ".join(bad))
            return 1
        print("OK")
        return 0
    (REPO / OUT_JSON).write_text(js, encoding="utf-8")
    (REPO / OUT_MD).write_text(md, encoding="utf-8")
    print(f"wrote {OUT_JSON}, {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
