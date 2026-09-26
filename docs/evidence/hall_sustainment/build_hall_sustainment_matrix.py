"""Build hall_sustainment_matrix.json: published evidence on Hall-discharge ignition / sustainment on N2, O2, air.

Evidence audit only (lane HSUS). Nothing is simulated, scored or tuned here, and no simulator input is changed.

* Literature entries are transcribed below from the sources listed in SOURCES. Each number carries its source, a locator,
  an evidence class and an uncertainty (or "not stated"). Page locators are the page numbers printed on the source unless
  the locator says "pdf p.".
* Repository-derived entries (P5-N2, ECHT-N2) are computed here from the frozen repository audit files, so they are
  re-runnable and checked by tests/test_hall_sustainment_evidence.py.
* A few arithmetic consistency checks on published numbers (unit conversions, flow fractions) are computed here too and
  are labelled "inferred (our arithmetic)".
* The P5-N2 v1 vacuum campaign status counts are carried ONLY as context. They are model results; they are never used as
  evidence that a discharge physically ignites or sustains (v1 is INCONCLUSIVE).

Usage: python docs/evidence/hall_sustainment/build_hall_sustainment_matrix.py [--check]
Writes docs/evidence/hall_sustainment/hall_sustainment_matrix.json and the generated section of
HALL_SUSTAINMENT_EVIDENCE.md (deterministic; --check only compares).
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "hall_sustainment_matrix.json")

REPO_FILES = {
    "p5_audit": "hallthruster_bridge/identification/brabston_p5_n2_measurement_audit_v1.json",
    "p5_findings": "hallthruster_bridge/identification/p5_n2_measurement_audit_findings_v1.json",
    "echt_audit": "hallthruster_bridge/identification/echt_n2/echt_n2_evidence_audit_v1.json",
    "echt_tables": "hallthruster_bridge/identification/echt_n2/echt_table_checks_v1.json",
    "evidence_policy": "docs/EVIDENCE.md",
    "v1_scores": "hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores.json",
}

# Molar masses (g/mol) used only for the arithmetic consistency checks below (IUPAC standard atomic weights, rounded).
M_N2, M_O2 = 28.0134, 31.998
SCCM_TO_MOL_S = 1.0 / 22413.97 / 60.0   # 1 sccm = 1 cm^3/min at 0 degC, 1 atm (ideal gas, 22413.97 cm^3/mol)

ABEP_REGIME_TBD = ("TBD - requires the upstream ICD (intake/compressor/gas-chamber/valve delivered mass flow, pressure, "
                   "number density and composition at the thruster inlet, including transients). No comparison of this "
                   "test regime with the ABEP delivered regime is made here.")

EVIDENCE_CLASSES = ["measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"]


def _load(key):
    with open(os.path.join(ROOT, REPO_FILES[key])) as f:
        return json.load(f)


def _sha256(key):
    with open(os.path.join(ROOT, REPO_FILES[key]), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def q(name, value, unit, cls, source, locator, uncertainty="not stated", note=None):
    """One quantity. value: number, [lo, hi], or a string ('not reported ...' / 'TBD - requires ...')."""
    assert cls in EVIDENCE_CLASSES, cls
    d = {"name": name, "value": value, "unit": unit, "uncertainty": uncertainty, "evidence_class": cls,
         "source": source, "locator": locator}
    if note:
        d["note"] = note
    return d


def nr(name, unit, source, what="not reported in the accessed text"):
    return {"name": name, "value": what, "unit": unit, "uncertainty": "n/a", "evidence_class": "measured",
            "source": source, "locator": "n/a"}


def r4(x):
    return round(float(x), 4)


# ----------------------------------------------------------------------------------------------------------------------
# Sources (what was actually accessed, how, and under which terms)
# ----------------------------------------------------------------------------------------------------------------------
SOURCES = {
    "BRABSTON2025": {
        "citation": "W. P. Brabston, L. A. Marino, D. Lev, M. L. R. Walker, 'Hall Thruster Performance and Efficiency "
                    "Analysis of a Molecular Propellant', J. Propuls. Power 41(6):676-689 (2025)",
        "doi": "10.2514/1.B39623", "urls_accessed": [],
        "access": "licensed_full_text_sha_pinned",
        "access_note": "Full text read from a local copy whose sha256 equals the pin used by the repository audit "
                       "(scripts/audit_p5_n2_measurements.py); publisher terms apply; not redistributed. Numeric values "
                       "are taken from the repository audit files, not re-transcribed.",
        "sha256": "14db7e8c1a0e7e4cae472038184a79b88ef4de6cb52071edb2a406d6a52e4d9d", "license": "AIAA (publisher)"},
    "BRABSTON_IEPC2024": {
        "citation": "W. P. Brabston, L. A. Marino, D. Lev, M. L. R. Walker, 'Analysis of the Ionization and Acceleration "
                    "Efficiencies of Molecular Nitrogen in a Hall Effect Thruster', IEPC-2024-297 (2024)",
        "doi": None, "urls_accessed": ["https://hpepl.ae.gatech.edu/sites/default/files/gbb-uploads/IEPC-24-297.pdf"],
        "access": "open_full_text",
        "access_note": "Same P5 N2/Ar/Xe campaign as BRABSTON2025; used only as corroboration (no separate values).",
        "sha256": "ea9e763be1cd0ae2fe357c9de6717eca8e2a194c08a95d4c284f3f6a18b2f226", "license": "ERPS copyright"},
    "REPO_P5_N2_AUDIT": {
        "citation": "Repository audit of the P5-N2 measurements (values from BRABSTON2025 Table 2, Table 5, Figs. 5, 8-10)",
        "doi": None, "urls_accessed": [],
        "repository_files": [REPO_FILES["p5_audit"], REPO_FILES["p5_findings"], REPO_FILES["evidence_policy"]],
        "access": "repository_audit_file", "access_note": "frozen repository files (sha256 recorded in meta)",
        "sha256": None, "license": "repository"},
    "REPO_ECHT_AUDIT": {
        "citation": "Repository ECHT-N2 evidence audit v1 (values from MARCHIONI2020 Tables 6.1-6.3, Figs. 4.7/4.8)",
        "doi": None, "urls_accessed": [],
        "repository_files": [REPO_FILES["echt_audit"], REPO_FILES["echt_tables"]],
        "access": "repository_audit_file", "access_note": "frozen repository files (sha256 recorded in meta)",
        "sha256": None, "license": "repository"},
    "MARCHIONI2020": {
        "citation": "F. Marchioni, 'Design and Performance Measurements of a Long Channel Hall Thruster for Air-Breathing "
                    "Electric Propulsion', MSc thesis, Politecnico di Torino / Stanford (2020)",
        "doi": None, "urls_accessed": ["https://webthesis.biblio.polito.it/14618/"],
        "access": "open_full_text_restrictive_license",
        "access_note": "Open institutional repository; CC BY-NC-ND 3.0: cited for numbers and short factual statements "
                       "only, never redistributed. Text read from the copy downloaded by the repository ECHT audit "
                       "(sha256 below = the audit's pin).",
        "sha256": "d3b3ea9927792fedafaec013a9b0db169aeea6901a314933adfc425b9c9d7652", "license": "CC BY-NC-ND 3.0"},
    "MARCHIONI2021": {
        "citation": "F. Marchioni, M. A. Cappelli, 'Extended channel Hall thruster for air-breathing electric "
                    "propulsion', J. Appl. Phys. 130, 053306 (2021)",
        "doi": "10.1063/5.0048283", "urls_accessed": ["https://api.crossref.org/works/10.1063/5.0048283"],
        "access": "abstract_only", "access_note": "paywalled (publisher 403); abstract only, as recorded by the repository "
                                                 "ECHT audit", "sha256": None, "license": "publisher"},
    "CIFALI2011": {
        "citation": "G. Cifali, T. Misuri, P. Rossetti, M. Andrenucci, D. Valentian, D. Feili, B. Lotz, 'Experimental "
                    "characterization of HET and RIT with atmospheric propellants', IEPC-2011-224 (2011)",
        "doi": None, "urls_accessed": ["https://electricrocket.org/IEPC/IEPC-2011-224.pdf"],
        "access": "open_full_text", "access_note": "ERPS IEPC repository",
        "sha256": "44b0fc265f35bbf707b1d99f8cbbdcf938aef48831ad28f97350550803254d11", "license": "ERPS"},
    "CIFALI2012": {
        "citation": "G. Cifali et al., 'Completion of HET and RIT characterization with atmospheric propellants', "
                    "Space Propulsion 2012, SP2012-2355386",
        "doi": None, "urls_accessed": [], "access": "not_accessed",
        "access_note": "primary not located openly; content taken only as reported by ANDREUSSI2022 (secondary)",
        "sha256": None, "license": "unknown"},
    "ANDREUSSI2022": {
        "citation": "T. Andreussi, E. Ferrato, V. Giannetti, 'A review of air-breathing electric propulsion: from mission "
                    "studies to technology verification', J. Electr. Propuls. 1:31 (2022)",
        "doi": "10.1007/s44205-022-00024-9",
        "urls_accessed": ["https://www.iris.sssup.it/retrieve/ea75eb42-2e80-462b-be1e-588ed43871e3/Andreussi%20et.al.%202022.pdf",
                          "https://link.springer.com/content/pdf/10.1007/s44205-022-00024-9.pdf"],
        "access": "open_full_text",
        "access_note": "review (evidence level 5 for anything it reports second-hand); page locators are 'Page N of 57'. "
                       "sha256 is of the IRIS copy (the Springer PDF bytes differ; same article)",
        "sha256": "092befade9a4dc9cb50ec9b54cb2401e9d66cd3ef2fd9d10c8eb87a16b50c02d", "license": "CC BY 4.0"},
    "FERRATO2019_IEPC886": {
        "citation": "E. Ferrato, V. Giannetti, A. Piragino, M. Andrenucci, T. Andreussi, C. A. Paissoni, 'Development "
                    "Roadmap of SITAEL's RAM-EP System', IEPC-2019-886 (2019)",
        "doi": None, "urls_accessed": ["https://electricrocket.org/2019/886.pdf"],
        "access": "open_full_text", "access_note": "ERPS IEPC repository",
        "sha256": "cba16dc5e56246e89b9116933d0d12e6037cdc99b1c4b2d27a695199e381ed99", "license": "ERPS"},
    "ANDREUSSI2022_IEPC435": {
        "citation": "T. Andreussi, E. Ferrato, A. Kitaeva, et al., 'Characterization of an Atmospheric Propellant-fed "
                    "Hall Thruster as a VLEO Simulator', IEPC-2022-435 (2022)",
        "doi": None,
        "urls_accessed": ["https://www.jotform.com/uploads/electricrocket/220994246997171/5305264492529551410/IEPC_2022_AETHER_final.pdf"],
        "access": "open_full_text",
        "access_note": "ERPS conference upload host; the AETHER-project copy (aether-h2020.eu) answered with a captcha "
                       "and was not bypassed",
        "sha256": "525d3ad2ebbd9335fabeed44ccea9bce63b2530a2f159bbb39696e0dc22083b4", "license": "ERPS"},
    "FERRATO2022_PSST": {
        "citation": "E. Ferrato, V. Giannetti, F. Califano, T. Andreussi, 'Atmospheric propellant fed Hall thruster "
                    "discharges: 0D-hybrid model and experimental results', Plasma Sources Sci. Technol. 31, 075003 (2022)",
        "doi": "10.1088/1361-6595/ac7904", "urls_accessed": ["https://api.crossref.org/works/10.1088/1361-6595/ac7904"],
        "access": "abstract_only", "access_note": "abstract via Crossref metadata only", "sha256": None,
        "license": "IOP"},
    "ANDREUSSI2017_IEPC377": {
        "citation": "T. Andreussi et al., 'Development and Experimental Validation of a Hall Effect Thruster RAM-EP "
                    "Concept', IEPC-2017-377 (2017)",
        "doi": None, "urls_accessed": [], "access": "not_accessed",
        "access_note": "content taken only as reported by ANDREUSSI2022 (secondary)", "sha256": None,
        "license": "unknown"},
    "MOSKOVITZ2026": {
        "citation": "J. A. Moskovitz, M. Rubanovich, W. P. Brabston, D. Lev, M. L. R. Walker, V. Balabanov, 'Performance "
                    "comparison and analysis of low-power hall thruster operation on atomic and molecular propellants', "
                    "J. Electr. Propuls. 5:32 (2026)",
        "doi": "10.1007/s44205-026-00199-5",
        "urls_accessed": ["https://link.springer.com/content/pdf/10.1007/s44205-026-00199-5.pdf"],
        "access": "open_full_text", "access_note": "several inline symbols are lost in the PDF text layer; values used "
                                                   "here are those legible in tables/text",
        "sha256": "44954c17649b9beb62b2e3112791d6a0b22c957be70901cb8804a9aa549f918b", "license": "CC BY 4.0"},
    "MUNRO2023": {
        "citation": "T. F. Munro-O'Brien, C. N. Ryan, 'Performance of a low power Hall effect thruster with several "
                    "gaseous propellants', Acta Astronaut. 206:257-273 (2023)",
        "doi": "10.1016/j.actaastro.2023.01.033",
        "urls_accessed": ["https://api.openalex.org/works/doi:10.1016/j.actaastro.2023.01.033"],
        "access": "abstract_only",
        "access_note": "CC BY 4.0 per Crossref, but ScienceDirect and the Southampton ePrints copy answered 403 to "
                       "automated access; abstract (OpenAlex) only. Statements on N2 ignition and component failure "
                       "are second-hand via MOSKOVITZ2026", "sha256": None, "license": "CC BY 4.0"},
    "GURCIULLO2020": {
        "citation": "A. Gurciullo, 'Electric propulsion technologies for enabling the use of molecular propellants', "
                    "PhD thesis, University of Surrey (2020)",
        "doi": "10.15126/thesis.00850793",
        "urls_accessed": ["https://doi.org/10.15126/thesis.00850793",
                          "https://openresearch.surrey.ac.uk/esploro/outputs/doctoral/Electric-propulsion-technologies-for-enabling-the/99511796902346"],
        "access": "open_full_text_restrictive_license",
        "access_note": "Surrey Open Research, CC BY-NC-SA 4.0 (cover page); numbers and short statements only; locators "
                       "are printed page numbers (pdf page = printed + 25)",
        "sha256": "085e514c9c5a2eddae5de628f83a61c4ceced05b980b2fd21524e56190186f4e", "license": "CC BY-NC-SA 4.0"},
    "GURCIULLO2019": {
        "citation": "A. Gurciullo, A. Lucca Fabris, M. A. Cappelli, 'Ion plume investigation of a Hall effect thruster "
                    "operating with Xe/N2 and Xe/air mixtures', J. Phys. D 52, 464003 (2019)",
        "doi": "10.1088/1361-6463/ab36c5", "urls_accessed": ["https://api.crossref.org/works/10.1088/1361-6463/ab36c5"],
        "access": "abstract_only", "access_note": "abstract via Crossref; the same measurements are read from GURCIULLO2020",
        "sha256": None, "license": "IOP"},
    "SEMENKIN1995": {
        "citation": "A. V. Semenkin, G. O. Chislov, 'Study of anode layer thruster operation with gas mixtures', "
                    "IEPC-95-78 (1995)",
        "doi": None, "urls_accessed": ["https://electricrocket.org/IEPC/IEPC1995-78.pdf"],
        "access": "open_full_text", "access_note": "scanned proceedings; figure data are not legible in the text layer",
        "sha256": "b566bb807016f0ba39bb7612ce31e92e8848cbdaa5d9686e12609f16a60f7935", "license": "ERPS"},
    "HRUBY2022": {
        "citation": "V. Hruby, K. Hohman, J. Szabo, 'Air Breathing Hall Effect Thruster Design Studies and Experiments', "
                    "IEPC-2022-446 (2022)",
        "doi": None, "urls_accessed": [], "access": "not_accessed",
        "access_note": "not located in an open copy during this audit; content taken only as reported by ANDREUSSI2022",
        "sha256": None, "license": "unknown"},
    "SHABSHELOWITZ2014": {
        "citation": "A. Shabshelowitz, A. D. Gallimore, P. Y. Peterson, 'Performance of a Helicon Hall Thruster Operating "
                    "with Xenon, Argon, and Nitrogen', J. Propuls. Power 30(3):664-671 (2014)",
        "doi": "10.2514/1.B35041", "urls_accessed": ["https://hdl.handle.net/2027.42/140449"],
        "access": "not_accessed",
        "access_note": "listed green OA (Deep Blue) but the repository answered 403 to automated access; content taken "
                       "only as reported by ANDREUSSI2022", "sha256": None, "license": "unknown"},
    "DUKHOPELNIKOV2021": {
        "citation": "D. V. Dukhopelnikov et al., 'Investigation of the laboratory model of a thruster with anode layer "
                    "operating with air and nitrogen-oxygen mixture', AIP Conf. Proc. 2318, 040006 (2021)",
        "doi": "10.1063/5.0036251", "urls_accessed": ["https://api.semanticscholar.org/graph/v1/paper/DOI:10.1063/5.0036251?fields=title,abstract"],
        "access": "abstract_only", "access_note": "abstract (Semantic Scholar) plus the ANDREUSSI2022 summary",
        "sha256": None, "license": "publisher"},
    "DIAMANT2010": {
        "citation": "K. Diamant, 'A 2-Stage Cylindrical Hall Thruster for Air Breathing Electric Propulsion', "
                    "AIAA 2010-6522 (2010)",
        "doi": "10.2514/6.2010-6522", "urls_accessed": [], "access": "not_accessed",
        "access_note": "closed; content taken only as reported by ANDREUSSI2022", "sha256": None, "license": "publisher"},
}


# ----------------------------------------------------------------------------------------------------------------------
# Repository-derived entries
# ----------------------------------------------------------------------------------------------------------------------
def p5_entries():
    a = _load("p5_audit")
    pts = a["points"]
    names = sorted(pts)
    t2 = {k: pts[k]["table2"] for k in names}
    mdot = [t2[k]["mdot_anode_mg_s"] for k in names]
    vd = [t2[k]["V_d"] for k in names]
    pd = [t2[k]["P_d_kW"] for k in names]
    pc = [t2[k]["p_chamber_Torr_N2"] for k in names]
    bpk = sorted({t2[k]["B_peak_G"] for k in names})
    mc = sorted({t2[k]["mdot_cathode_Xe_mg_s"] for k in names})
    idr = [pts[k]["I_d_raw_A"] for k in names]
    tc = [pts[k]["T_corr_mN"] for k in names]
    ing = [pts[k]["mdot_ingested_eq13_mg_s"] for k in names]
    frac_c = [t2[k]["mdot_cathode_Xe_mg_s"] / t2[k]["mdot_anode_mg_s"] for k in names]
    frac_i = [pts[k]["mdot_ingested_eq13_mg_s"] / t2[k]["mdot_anode_mg_s"] for k in names]
    S, B = "REPO_P5_N2_AUDIT", "BRABSTON2025"
    quantities = [
        q("anode N2 mass flow (N1-N5)", [min(mdot), max(mdot)], "mg/s", "measured", S, "Table 2 via audit points.*.table2",
          "MFC 1 % of setpoint (max 0.05 mg/s)"),
        q("cathode Xe mass flow", mc[0] if len(mc) == 1 else [mc[0], mc[-1]], "mg/s", "measured", S,
          "Table 2 (4.5 sccm)", "MFC 1 % of setpoint"),
        q("cathode Xe / anode N2 mass-flow ratio", [r4(min(frac_c)), r4(max(frac_c))], "1", "inferred", S,
          "our arithmetic on Table 2", "propagated from MFC 1 % (each)"),
        q("discharge voltage", [min(vd), max(vd)], "V", "measured", S, "Table 2", "not stated"),
        q("discharge power", [min(pd), max(pd)], "kW", "measured", S, "Table 2", "rounding 0.005 kW (3 s.f.)"),
        q("discharge current, raw = P_d/V_d", [r4(min(idr)), r4(max(idr))], "A", "inferred", S,
          "audit points.*.I_d_raw_A", "P_d rounding 0.10-0.16 %; no I_d uncertainty stated by the source"),
        q("peak radial B at channel centre, exit plane", bpk[0] if len(bpk) == 1 else bpk, "G", "measured", S, "Table 2",
          "not stated; B(z) shape and coil currents unpublished (layer-1 hypotheses)"),
        q("chamber pressure (N2-corrected ion gauge)", [min(pc), max(pc)], "Torr", "measured", S, "Table 2", "not stated"),
        q("ingested background N2 flow, Eq. (13)", [r4(min(ing)), r4(max(ing))], "mg/s", "inferred", S,
          "audit points.*.mdot_ingested_eq13_mg_s", "engineering correlation (evidence level 6)"),
        q("ingested / anode flow", [r4(min(frac_i)), r4(max(frac_i))], "1", "inferred", S, "our arithmetic",
          "inherits Eq. (13) uncertainty"),
        q("thrust, ingestion-corrected (N1..N5)", [min(tc), max(tc)], "mN", "reconstructed", S,
          "abstract end-points (N1, N5); Fig. 5 digitized (N2-N4)", 2.6),
        q("discharge channel length", [32, 38], "mm", "measured", S,
          "docs/EVIDENCE.md register: 32 mm (Brabston 2025) vs 38 mm (Peterson 2001, Hofer 2004)",
          "conflicting sources; carried as hypotheses"),
    ]
    common = {
        "sources": [S, B, "BRABSTON_IEPC2024"],
        "evidence_level": 3,
        "thruster": {"name": "P5 (5 kW-class laboratory Hall thruster)",
                     "family": "single-stage Hall (SPT-type)", "power_class_kW": [3.08, 4.81],
                     "geometry_note": "channel length 32 mm (Brabston) vs 38 mm (historical); coil currents unpublished"},
        "propellant": {"anode_gas": "N2 (pure)", "cathode_gas": "Xe", "xenon_in_anode_flow": False},
        "preionizer": {"present": False, "type": None, "note": "single-stage Hall; hollow cathode (Xe) is the electron source"},
        "repository_derived": True,
    }
    e1 = dict(common)
    e1.update({
        "id": "E01", "title": "P5 on pure N2, five setpoints N1-N5 (GT VTF-1)",
        "evidence_class": "measured",
        "ignition": {"mode": "not_reported", "evidence_class": "measured",
                     "statement": "The start-up / ignition procedure (gas at ignition) is not described in the accessed "
                                  "text (verify in the full paper if needed)."},
        "flow": quantities[0], "voltage": quantities[3], "magnetic_field": quantities[6],
        "outcome": "sustained",
        "outcome_statement": "All five N2 setpoints were operated and measured (thrust, plume probes at N1-N3). Coils were "
                             "tuned at N3 to minimise I_d and its peak-to-peak oscillation, then held fixed. The Xe "
                             "cathode flow (4.5 sccm) was chosen as the lowest that kept stable operation on all propellants.",
        "observations": {
            "oscillation_modes": "qualitative only: B tuned to minimise I_d peak-to-peak oscillation; no amplitudes or "
                                 "spectra published (repository findings F6; BRABSTON2025 p.6)",
            "extinction": "see E02 (voltage window)",
            "erosion": "not reported",
            "cathode": "Xe hollow cathode at 0.44 mg/s; paper assumes the Xe contribution negligible (no resolvable Xe in "
                       "E x B spectra; findings F5)"},
        "quantities": quantities,
        "implication": {
            "direction": "operation_without_preionizer_demonstrated",
            "statement": "A single-stage Hall discharge without a dedicated pre-ionization stage sustained on a pure N2 anode "
                         "flow of 5.0-5.4 mg/s at 232-279 V and 130 G in this thruster and facility.",
            "uncertainty": ("Electron supply and possibly ionization are assisted by a Xe cathode flow of %.1f-%.1f %% of "
                            "the anode mass flow, and by ingested background N2 (%.1f-%.1f %% of the anode flow, Eq. (13) "
                            "correlation). The start-up gas is not reported, so this entry says nothing about Xe-free "
                            "ignition." % (100 * min(frac_c), 100 * max(frac_c), 100 * min(frac_i), 100 * max(frac_i))),
            "applicability_limits": "5 kW-class channel (32 or 38 mm long), 3.1-4.8 kW, 1.1-2.1e-5 Torr facility "
                                    "background, Xe cathode; not a flight or intake-fed condition.",
            "abep_regime": ABEP_REGIME_TBD},
    })
    f = _load("p5_findings")
    e2 = dict(common)
    e2.update({
        "id": "E02", "title": "P5 on pure N2 outside about 225-275 V (operating-window statement)",
        "evidence_class": "measured",
        "ignition": {"mode": "not_reported", "evidence_class": "measured",
                     "statement": "not described in the accessed text"},
        "flow": nr("anode N2 mass flow at the window boundary", "mg/s", S,
                   "not reported for the boundary (the window is stated generally for nitrogen)"),
        "voltage": q("stated N2 stability window", [225, 275], "V", "measured", B,
                     "BRABSTON2025 p.6; repository findings F4",
                     "approximate: setpoints N3-N5 were run at 275.7-278.6 V (above the stated 275 V)"),
        "magnetic_field": quantities[6],
        "outcome": "extinguished",
        "outcome_statement": "The paper states that above 275 V and below 225 V the thruster becomes unstable and cannot "
                             "sustain a discharge on nitrogen (text statement, no boundary data). "
                             + f["admissible_targets"]["sustained_discharge"]["evidence"],
        "observations": {"oscillation_modes": "not quantified", "extinction": "loss of discharge outside the window",
                         "erosion": "not reported", "cathode": "Xe hollow cathode 0.44 mg/s"},
        "quantities": [quantities[3]],
        "implication": {
            "direction": "operation_bounded_extinction_observed",
            "statement": "Without a pre-ionizer, sustained N2 operation of this thruster was confined to a narrow voltage "
                         "window at about 5 mg/s and fixed B.",
            "uncertainty": "Boundary is a text statement (no data, no B or flow scan at the boundary); whether a "
                           "pre-ionizer, a different B, or more flow widens the window is not tested.",
            "applicability_limits": "same as E01",
            "abep_regime": ABEP_REGIME_TBD},
    })
    return [e1, e2]


def echt_entries():
    a = _load("echt_audit")
    v = a["values"]
    rows = v["operating_points_table_6_1"]["rows"]   # [Vd, Id, Imag, mdot_a, mdot_c(Ar), Pa/Ptot, p]
    vd = [r[0] for r in rows]
    idd = [r[1] for r in rows]
    im = [r[2] for r in rows]
    ma = sorted({r[3] for r in rows})
    mc = [r[4] for r in rows]
    pc = [r[6] for r in rows]
    frac = [r[4] / r[3] for r in rows]
    perf = v["performance_table_6_2"]["rows"]
    t1 = [p["T_mN"] for p in perf]
    tav = [p["T_avg_mN"] for p in perf if p["T_avg_mN"] is not None]
    pa = [p["P_anode_W"] for p in perf]
    unstable = v["performance_table_6_2"]["unstable_runs"]
    plateau = v["magnetic_field"]["measured_Bz_at_2A"]["plateau_mean_4.7_8.3cm_G"]
    geo = v["geometry"]
    S, T = "REPO_ECHT_AUDIT", "MARCHIONI2020"
    quantities = [
        q("anode N2 mass flow", ma[0] if len(ma) == 1 else ma, "mg/s", "measured", S, "S2 Table 6.1 p.98",
          "1 % ambiguity (99 vs 100 sccm = 2.06 vs 2.083 mg/s); possible feed-line leakage"),
        q("discharge voltage", [min(vd), max(vd)], "V", "measured", S, "S2 Table 6.1", "not stated"),
        q("discharge current", [min(idd), max(idd)], "A", "measured", S, "S2 Table 6.1", "2 s.f. (rounding +-0.05 A)"),
        q("magnet coil current", [min(im), max(im)], "A", "measured", S, "S2 Table 6.1", "not stated"),
        q("measured centreline B plateau at 2 A coil current", plateau, "G", "digitized", S,
          "S2 Fig. 4.7 p.66 (digitized by the repository audit)", "reading +-0.2 G; probe uncertainty not stated"),
        q("cathode Ar mass flow", [min(mc), max(mc)], "mg/s", "measured", S, "S2 Table 6.1", "not stated"),
        q("cathode Ar / anode N2 mass-flow ratio", [r4(min(frac)), r4(max(frac))], "1", "inferred", S,
          "our arithmetic on Table 6.1", "inherits the 2.06/2.083 mg/s ambiguity"),
        q("chamber pressure (ion gauge)", [min(pc), max(pc)], "Torr", "measured", S, "S2 Table 6.1",
          "gauge location and gas correction not stated"),
        q("anode power, thrust runs", [min(pa), max(pa)], "W", "inferred", S, "V_d x I_d, S2 Table 6.2", "from 2 s.f. I_d"),
        q("thrust, one-side reduction (7 runs)", [min(t1), max(t1)], "mN", "measured", S, "S2 Table 6.2 p.101",
          "published +- are calibration-fit only (0.02-2.66 mN)"),
        q("thrust, averaged reduction (4 runs)", [min(tav), max(tav)], "mN", "measured", S, "S2 Table 6.3 p.108",
          "published +- 2.68-4.56 mN; 6-18 % below one-side"),
        q("channel length", geo["channel_length"]["value_mm"], "mm", "measured", S, "S2 Sec. 4.1.1 p.63",
          "not stated (design dimension)"),
        q("channel height", geo["channel_height"]["value_mm"], "mm", "measured", S, "S2 Sec. 4.1.1 p.63",
          "not stated (design dimension)"),
    ]
    thr = {"name": "ECHT (Stanford extended-channel Hall thruster)", "family": "single-stage Hall (SPT-type, extended channel)",
           "power_class_kW": [min(pa) / 1000.0, max(pa) / 1000.0],
           "geometry_note": "86 mm channel length, 10 mm channel height, '100 mm outer diameter' ambiguous "
                            "(channel OD vs BN piece OD); flat B plateau over about 4.7-8.6 cm, not exit-peaked"}
    common = {"sources": [S, T, "MARCHIONI2021"], "evidence_level": 3, "thruster": thr,
              "propellant": {"anode_gas": "N2 (pure)", "cathode_gas": "Ar", "xenon_in_anode_flow": False},
              "preionizer": {"present": False, "type": None,
                             "note": "single-stage; Ar-fed BaO hollow cathode (IonTech HCN-252) is the electron source"},
              "repository_derived": True}
    e3 = dict(common)
    e3.update({
        "id": "E03", "title": "ECHT on pure N2 with an argon cathode, 180-220 V (SPPL LVF)",
        "evidence_class": "measured",
        "ignition": {"mode": "direct_on_atmospheric_gas", "evidence_class": "measured",
                     "statement": "S2 pp.84-85 give an ignition procedure with N2 set on the anode and Ar on the cathode "
                                  "(cathode puff, low B at ignition, B applied after the anode stabilises); S2 p.97 states "
                                  "a stable discharge was maintained on 100 % nitrogen with no xenon present."},
        "flow": quantities[0], "voltage": quantities[1], "magnetic_field": quantities[4],
        "outcome": "sustained",
        "outcome_statement": "13 operating points (Table 6.1) and 7 thrust runs (Table 6.2) on pure N2 at 2.06 mg/s. "
                             "Runs " + ", ".join(r.replace("Run ", "") for r in unstable) +
                             " are flagged 'strong instability during calibration'; mode changes and quenching were "
                             "attributed by the author to a degraded BaO cathode.",
        "observations": {
            "oscillation_modes": v["stability_oscillations"]["value"],
            "extinction": "quenching linked to keeper-voltage runaway (30-40 V) of a degraded emitter; cathode flow raised "
                          "ad hoc to keep the cathode running (repository audit, cathode.flow_mgps note; S2 p.98)",
            "erosion": "not reported",
            "cathode": "argon, %g-%g mg/s (Table 6.1)" % (min(mc), max(mc))},
        "quantities": quantities,
        "implication": {
            "direction": "operation_without_preionizer_demonstrated",
            "statement": "The only accessed Hall case that both ignited and ran on a pure N2 anode flow with no xenon "
                         "anywhere (Ar cathode) and no pre-ionization stage, at about 2 mg/s in an 86 mm channel.",
            "uncertainty": ("Argon cathode flow was large (%.1f-%.1f %% of anode mass) and co-varied with the best points; "
                            "facility background %.1e-%.1e Torr (inferred ingestion %s of anode flow, repository audit); "
                            "%d of %d thrust runs strongly unstable; per-point I_d to 2 s.f.; no oscillation data."
                            % (100 * min(frac), 100 * max(frac), min(pc), max(pc),
                               v["derived_checks"]["ingestion_order_of_magnitude"]["fraction_of_anode_flow"],
                               len(unstable), len(perf))),
            "applicability_limits": ("%.2f-%.2f kW, %g-%g V only (300 V supply limit, no data above 220 V), one flow "
                                     "(%g mg/s), elevated facility pressure; MSc-thesis measurement with fit-only thrust "
                                     "uncertainty." % (min(pa) / 1000.0, max(pa) / 1000.0, min(vd), max(vd), ma[0])),
            "abep_regime": ABEP_REGIME_TBD},
    })
    e4 = dict(common)
    e4.update({
        "id": "E04", "title": "ECHT on pure N2 below about 80 sccm (1.6 mg/s)",
        "evidence_class": "measured",
        "ignition": {"mode": "direct_on_atmospheric_gas", "evidence_class": "measured", "statement": "as E03"},
        "flow": q("anode N2 flow below which the discharge was unstable / quenched", 1.6, "mg/s", "measured", S,
                  "repository audit values.stability_oscillations (S2 p.98, p.104, p.107-110)",
                  "approximate text value ('~80 sccm'); no scan data"),
        "voltage": nr("discharge voltage at the flow boundary", "V", S),
        "magnetic_field": nr("B at the flow boundary", "G", S),
        "outcome": "extinguished",
        "outcome_statement": "Qualitative: the discharge was unstable / quenched below about 80 sccm (1.6 mg/s) N2.",
        "observations": {"oscillation_modes": "not quantified", "extinction": "flow floor about 1.6 mg/s",
                         "erosion": "not reported", "cathode": "Ar, degraded BaO emitter"},
        "quantities": [],
        "implication": {
            "direction": "operation_bounded_extinction_observed",
            "statement": "Even with an 86 mm channel, pure-N2 operation without a pre-ionizer had a flow floor near "
                         "1.6 mg/s in this set-up.",
            "uncertainty": "Single approximate statement; voltage, B and cathode state at the boundary not given; the "
                           "degraded cathode may have set the floor.",
            "applicability_limits": "as E03", "abep_regime": ABEP_REGIME_TBD},
    })
    return [e3, e4]


# ----------------------------------------------------------------------------------------------------------------------
# Arithmetic consistency checks on published numbers (labelled inferred)
# ----------------------------------------------------------------------------------------------------------------------
def derived_checks():
    x_n2 = 1.27 / 2.27
    w_n2 = 1.27 * M_N2 / (1.27 * M_N2 + M_O2)
    sccm_n2 = SCCM_TO_MOL_S * M_N2 * 1000.0    # mg/s per sccm
    return {
        "composition_1p27N2_O2_mole_fraction_N2": r4(x_n2),
        "composition_1p27N2_O2_mass_fraction_N2": r4(w_n2),
        "composition_note": "CIFALI2011 and FERRATO2019_IEPC886 give '1.27N2 + O2' (molecular composition); ANDREUSSI2022, "
                            "ANDREUSSI2022_IEPC435 and FERRATO2022_PSST give '0.56N2 + 0.44O2'. 1.27:1 is a N2 mole "
                            "fraction of 0.559 (mass fraction 0.526), so '0.56/0.44' reads as mole fractions (inferred, "
                            "verify; the SITAEL papers do not state the basis).",
        "n2_mg_s_per_sccm": r4(sccm_n2),
        "moskovitz_n2_55sccm_mg_s": r4(55.0 * sccm_n2),
        "moskovitz_n2_75p4sccm_mg_s": r4(75.4 * sccm_n2),
        "moskovitz_note": "MOSKOVITZ2026 Table 5/6 list 55.0-75.4 sccm = 1.144-1.568 mg/s; our 0 degC/1 atm conversion "
                          "gives the values above (0.1-0.2 % higher; the paper's reference conditions are not stated).",
        "gurciullo_min_xe_mass_fraction": [r4(0.16 / (0.16 + 1.39)), r4(0.16 / (0.16 + 1.33))],
        "gurciullo_note": "lowest Xe 0.16 mg/s with N2 1.33-1.39 mg/s (GURCIULLO2020 p.177): Xe mass fraction of the "
                          "anode flow 10.3-10.7 % (our arithmetic).",
        "shabshelowitz_cathode_fraction": r4(1.0 / 2.6),
        "shabshelowitz_note": "ANDREUSSI2022 p.27: 1 mg/s Xe cathode with 2.6 mg/s N2 anode, 'a 38.4 % cathode flow "
                              "fraction' (1/2.6 = 0.385, our arithmetic).",
    }


# ----------------------------------------------------------------------------------------------------------------------
# Literature entries (transcribed)
# ----------------------------------------------------------------------------------------------------------------------
def literature_entries(dc):
    E = []
    C = "CIFALI2011"
    E.append({
        "id": "E05", "title": "PPS1350-TSD on pure N2 (Alta IV10, ESA contract)",
        "sources": [C, "ANDREUSSI2022"], "evidence_level": 3, "evidence_class": "measured",
        "thruster": {"name": "Snecma PPS1350-TSD (reconverted to PPS1350 configuration)", "family": "single-stage Hall (SPT-type)",
                     "power_class_kW": "about 1 (limits 350 V, 1.4 kW)", "geometry_note": "flight-type 1.5 kW-class "
                     "SPT; eroded channel from earlier TSD campaigns (about 554 h)"},
        "propellant": {"anode_gas": "N2 (pure)", "cathode_gas": "Xe", "xenon_in_anode_flow": False},
        "preionizer": {"present": False, "type": None, "note": "single-stage"},
        "ignition": {"mode": "xenon_start_then_transition", "evidence_class": "measured",
                     "statement": "Always ignited with xenon, then a smooth anode transition from 100 % Xe to 100 % N2; "
                                  "the cathode stayed on xenon (CIFALI2011 p.2)."},
        "flow": q("anode N2 flow, characterization", [2.3, 2.85], "mg/s", "measured", C, "Fig. 5/6 legends p.4"),
        "voltage": q("discharge voltage, characterization", "not tabulated (Fig. 5 axis 200-360 V; 305 and 350 V named "
                     "in text)", "V", "measured", C, "p.3-4, Fig. 5"),
        "magnetic_field": nr("B", "G", C),
        "outcome": "sustained",
        "outcome_statement": "Operated over 2.3-2.85 mg/s N2; 10 h long firing at 305 V, 3 A 'very stable', thrust always "
                             "19-21 mN; Xe performance afterwards substantially unaffected.",
        "observations": {"oscillation_modes": "not reported", "extinction": "none reported",
                         "erosion": "visual inspection after the campaign (see E06)",
                         "cathode": "Xe hollow cathode throughout"},
        "quantities": [
            q("reference point: voltage", 305, "V", "measured", C, "p.3"),
            q("reference point: discharge current", 3.48, "A", "measured", C, "p.3"),
            q("reference point: power-to-thrust", 41.6, "W/mN", "inferred", C, "p.3", note="ratio computed by the authors"),
            q("long firing: discharge current", 3, "A", "measured", C, "p.4"),
            q("long firing: duration", 10, "h", "measured", C, "p.4"),
            q("long firing: thrust band", [19, 21], "mN", "measured", C, "p.4", "stand accuracy 1 % of full scale "
              "(range 5-300 mN), resolution 1 mN (p.2)"),
            q("long firing: anode N2 flow", 2.65, "mg/s", "measured", C, "p.5"),
            q("chamber pressure during N2 long firing", "< 6.0e-6", "mbar", "measured", C, "p.2", "upper bound as stated"),
        ],
        "implication": {
            "direction": "operation_without_preionizer_demonstrated_xenon_start",
            "statement": "Steady single-stage operation on pure N2 without a pre-ionizer, once lit on xenon and with a Xe "
                         "cathode.",
            "uncertainty": "Ignition on N2 itself was not attempted/reported; B, oscillations and plume not measured; "
                           "performance only from the stand.",
            "applicability_limits": "about 1 kW, 2.3-2.85 mg/s, facility < 6e-6 mbar, Xe cathode.",
            "abep_regime": ABEP_REGIME_TBD},
        "repository_derived": False})
    E.append({
        "id": "E06", "title": "PPS1350-TSD on N2/O2 mixture 1.27N2 + O2 (200 km-representative)",
        "sources": [C, "ANDREUSSI2022"], "evidence_level": 3, "evidence_class": "measured",
        "thruster": E[-1]["thruster"],
        "propellant": {"anode_gas": "N2/O2, 1.27N2 + O2 (molecular composition)", "cathode_gas": "Xe",
                       "xenon_in_anode_flow": False},
        "preionizer": {"present": False, "type": None, "note": "single-stage"},
        "ignition": {"mode": "xenon_start_then_transition", "evidence_class": "measured",
                     "statement": "as E05 (always ignited with xenon, CIFALI2011 p.2)"},
        "flow": q("minimum stable mixture flow", 2.1, "mg/s", "measured", C, "p.5", "not stated"),
        "voltage": q("discharge voltages scanned", [220, 350], "V", "measured", C, "Fig. 8/9 legends (220, 263, 305, 350 V)"),
        "magnetic_field": nr("B", "G", C),
        "outcome": "sustained",
        "outcome_statement": "Stable operation down to 2.1 mg/s; 10 h stable test at 305 V, 2.75 mg/s, thrust 24 mN.",
        "observations": {"oscillation_modes": "flow-controller perturbations 'induced by oscillations on the main discharge "
                                              "circuit' mentioned for the Xe re-check after the mixture test (p.5); not "
                                              "quantified",
                         "extinction": "none reported",
                         "erosion": "anode 'rusty' (oxidation) and signs of oxygen operation on the ceramics after the "
                                    "test; anode oxidation named the main concern for endurance (p.5)",
                         "cathode": "Xe"},
        "quantities": [
            q("long firing: flow", 2.75, "mg/s", "measured", C, "p.5 / Fig. 7 caption"),
            q("long firing: voltage", 305, "V", "measured", C, "Fig. 7 caption p.4"),
            q("long firing: thrust", 24, "mN", "measured", C, "p.5", "stand accuracy 1 % of full scale"),
            q("long firing: duration", 10, "h", "measured", C, "p.5"),
            q("N2 mole fraction of 1.27N2 + O2", dc["composition_1p27N2_O2_mole_fraction_N2"], "1", "inferred", C,
              "our arithmetic", "exact for the stated ratio"),
        ],
        "implication": {
            "direction": "operation_without_preionizer_demonstrated_xenon_start",
            "statement": "Steady operation on an N2/O2 anode flow without a pre-ionizer after a xenon start; O2 addition "
                         "did not degrade sustainment at low flow in this test (stable to 2.1 mg/s).",
            "uncertainty": "Xe start and Xe cathode; no B data; oxidation of the anode is a separate life issue (E07).",
            "applicability_limits": "about 1 kW, 2.1-4 mg/s, 220-350 V, facility-fed gas, no atomic oxygen.",
            "abep_regime": ABEP_REGIME_TBD},
        "repository_derived": False})
    A = "ANDREUSSI2022"
    E.append({
        "id": "E07", "title": "PPS1350 endurance on N2/O2 + 10 % Xe (secondary report)",
        "sources": [A, "CIFALI2012"], "evidence_level": 5, "evidence_class": "measured",
        "thruster": E[-1]["thruster"],
        "propellant": {"anode_gas": "N2/O2 mixture with a 10 % xenon mass-flow addition", "cathode_gas": "not reported",
                       "xenon_in_anode_flow": True},
        "preionizer": {"present": False, "type": None, "note": "single-stage"},
        "ignition": {"mode": "not_reported", "evidence_class": "measured", "statement": "not reported in the review"},
        "flow": q("mixture flow", 2.75, "mg/s", "measured", A, "Page 24 of 57"),
        "voltage": q("discharge voltage", 305, "V", "measured", A, "Page 24 of 57"),
        "magnetic_field": nr("B", "G", A),
        "outcome": "extinguished",
        "outcome_statement": "Steady for about 314 h at 3.8-4 A; then severe anode oxidation produced anomalous discharge "
                             "behaviour and a spontaneous flame-out; after refurbishment, several flame-outs in the next "
                             "75 h and the test was stopped early.",
        "observations": {"oscillation_modes": "anomalous discharge behaviour (not quantified)",
                         "extinction": "flame-outs attributed to anode oxidation",
                         "erosion": "ceramic erosion reported compatible with 7000-9500 h lifetime; anode oxidation "
                                    "life-limiting", "cathode": "not reported"},
        "quantities": [
            q("steady duration before first flame-out", 314, "h", "measured", A, "Page 24 of 57", "'about'"),
            q("discharge current during steady phase", [3.8, 4.0], "A", "measured", A, "Page 24 of 57"),
            q("subsequent firing with several flame-outs", 75, "h", "measured", A, "Page 24 of 57"),
            q("ceramic-erosion-compatible lifetime (authors' estimate)", [7000, 9500], "h", "model-derived", A,
              "Page 24 of 57", "extrapolation method not given in the review"),
            q("effect of the 10 % Xe addition on I_d (characterization)", [17, 40], "%", "measured", A, "Page 23 of 57"),
            q("effect of the 10 % Xe addition on thrust (characterization)", [4, 40], "%", "measured", A, "Page 23 of 57"),
        ],
        "implication": {
            "direction": "not_informative",
            "statement": "Says nothing on pre-ionization; shows that with oxygen in the anode flow, sustainment over "
                         "hundreds of hours was limited by anode oxidation (flame-outs), with 10 % Xe already added.",
            "uncertainty": "Second-hand (primary SP2012 paper not accessed).",
            "applicability_limits": "PPS1350, 305 V, 2.75 mg/s, facility-fed N2/O2 + Xe.",
            "abep_regime": ABEP_REGIME_TBD},
        "repository_derived": False})
    F = "FERRATO2019_IEPC886"
    E.append({
        "id": "E08", "title": "SITAEL HT5k (first development model) as particle-flow generator on N2/O2 (2017)",
        "sources": [A, F, "ANDREUSSI2017_IEPC377"], "evidence_level": 5, "evidence_class": "measured",
        "thruster": {"name": "SITAEL HT5k (first development model)", "family": "single-stage Hall (SPT-type)",
                     "power_class_kW": 2.4, "geometry_note": "not reported"},
        "propellant": {"anode_gas": "0.56N2/0.44O2 (= 1.27N2 + O2)", "cathode_gas": "Xe", "xenon_in_anode_flow": False},
        "preionizer": {"present": False, "type": None, "note": "single-stage"},
        "ignition": {"mode": "not_reported", "evidence_class": "measured", "statement": "not reported"},
        "flow": q("anode mixture flow", [4.3, 4.7], "mg/s", "measured", A, "Page 24 of 57",
                  note="FERRATO2019_IEPC886 Fig. 2 caption (p.3): 4.7 mg/s of 1.27N2 + O2"),
        "voltage": q("discharge voltage", 225, "V", "measured", A, "Page 24 of 57"),
        "magnetic_field": nr("B", "G", A),
        "outcome": "sustained",
        "outcome_statement": "Stable operation verified at 225 V, 4.3-4.7 mg/s; 64 mN at 2.4 kW; plume half-angle "
                             "divergence 52 deg (review p.43).",
        "observations": {"oscillation_modes": "not reported", "extinction": "not reported", "erosion": "not reported",
                         "cathode": "Xe"},
        "quantities": [q("thrust", 64, "mN", "measured", A, "Page 24 of 57"),
                       q("discharge power", 2.4, "kW", "measured", A, "Page 24 of 57"),
                       q("plume half-angle divergence", 52, "deg", "measured", A, "Page 43 of 57")],
        "implication": {
            "direction": "operation_without_preionizer_demonstrated",
            "statement": "Single-stage operation on an N2/O2 anode flow without a pre-ionizer at 4.3-4.7 mg/s.",
            "uncertainty": "Second-hand for the performance values (IEPC-2017-377 not accessed); ignition gas not reported; "
                           "Xe cathode.",
            "applicability_limits": "5 kW-class, 225 V, facility-fed gas.",
            "abep_regime": ABEP_REGIME_TBD},
        "repository_derived": False})
    I = "ANDREUSSI2022_IEPC435"
    E.append({
        "id": "E09", "title": "SITAEL HT5k DM2 (magnetically shielded), AETHER particle-flow generator, N2/O2 anode and "
                              "N2 cathode (Nov 2021)",
        "sources": [I, "FERRATO2022_PSST", A], "evidence_level": 3, "evidence_class": "measured",
        "thruster": {"name": "SITAEL HT5k DM2 with HC20h hollow cathode", "family": "magnetically shielded Hall",
                     "power_class_kW": [1.2, 5.2], "geometry_note": "not reported; centrally mounted cathode"},
        "propellant": {"anode_gas": "0.56N2 + 0.44O2", "cathode_gas": "N2 (after transition from Xe)",
                       "xenon_in_anode_flow": False},
        "preionizer": {"present": False, "type": None, "note": "single-stage"},
        "ignition": {"mode": "xenon_start_then_transition", "evidence_class": "measured",
                     "statement": "Ignited at 225 V on 10 mg/s Xe (anode) + 1 mg/s Xe (cathode); anode switched gradually "
                                  "to 6 mg/s N2/O2; then cathode Xe reduced to 0 while N2 raised to 0.6 mg/s (p.3)."},
        "flow": q("anode N2/O2 flow", [5, 7], "mg/s", "measured", I, "p.2, p.5"),
        "voltage": q("discharge voltage (stability demonstrated)", [225, 300], "V", "measured", I, "p.5",
                     note="test description (p.2) says characterization in the 225-375 V range; results (p.5) report "
                          "stability at 225 and 300 V"),
        "magnetic_field": nr("B", "G", I),
        "outcome": "sustained",
        "outcome_statement": "Discharge and thermal stability demonstrated at 225 V and 300 V, 5-7 mg/s, with the N2-fed "
                             "cathode (xenon-free steady state after the xenon start); six operating conditions; "
                             "cumulative 10 h on atmospheric propellant; Xe reference tests before/after repeatable.",
        "observations": {
            "oscillation_modes": "I_d acquired at 10 MHz; the review reports the discharge current signal stable in all "
                                 "points (Page 25 of 57); no spectra published",
            "extinction": "none reported",
            "erosion": "magnetic shielding 'seems effective'; plasma detachment from channel walls visible (p.5); no "
                       "PFG critical damage after the air test",
            "cathode": "HC20h (LaB6) on N2 0.5-0.7 mg/s (PSST abstract); N2 cathode reduced I_d, thrust and efficiency vs "
                       "Xe cathode at the same V_d and anode flow (p.5). The review reports severe erosion/embrittlement "
                       "of the HC20h after tests with the N2/O2 mixture (Page 38 of 57)"},
        "quantities": [
            q("thrust range", [30, 120], "mN", "measured", I, "p.5", "stand accuracy +-3 mN (p.3)"),
            q("discharge power range", [1.2, 5.2], "kW", "measured", I, "p.5"),
            q("anodic efficiency range", [10, 20], "%", "inferred", I, "p.5",
              "FERRATO2022_PSST abstract gives 8-18 % (discrepancy not resolved)"),
            q("specific impulse range", [600, 1600], "s", "inferred", I, "p.5"),
            q("cathode N2 flow", [0.5, 0.7], "mg/s", "measured", "FERRATO2022_PSST", "abstract"),
            q("cathode/anode flow ratio (held during the scan)", 0.1, "1", "measured", I, "p.3"),
            q("facility pressure (ITR90, 3 m downstream)", "< 2.5e-5", "mbar", "measured", I, "p.2", "upper bound"),
            q("cumulative firing on atmospheric propellant", 10, "h", "measured", I, "p.5"),
        ],
        "implication": {
            "direction": "operation_without_preionizer_demonstrated_xenon_start",
            "statement": "After a xenon start, a single-stage magnetically shielded Hall discharge was sustained with no "
                         "xenon anywhere (N2/O2 anode, N2 cathode) and no pre-ionizer at 5-7 mg/s.",
            "uncertainty": "Ignition itself used xenon; B and geometry not published; only 10 h; efficiency range differs "
                           "between the two SITAEL sources.",
            "applicability_limits": "5 kW class, 1.2-5.2 kW, 225-300 V, facility < 2.5e-5 mbar, lab-fed gas (no atomic O).",
            "abep_regime": ABEP_REGIME_TBD},
        "repository_derived": False})
    M = "MOSKOVITZ2026"
    cam = {"name": "Simplified CAMILA (ASRI Technion)", "family": "single-stage Hall with coaxial anodes extending into the "
                                                              "channel (low power)",
           "power_class_kW": [0.212, 0.452], "geometry_note": "channel mean diameter 49 mm, width 12 mm (Table 3)"}
    E.append({
        "id": "E10", "title": "Simplified CAMILA low-power Hall thruster on pure N2 (inside its operating envelope)",
        "sources": [M], "evidence_level": 3, "evidence_class": "measured", "thruster": cam,
        "propellant": {"anode_gas": "N2 (pure)", "cathode_gas": "Xe", "xenon_in_anode_flow": False},
        "preionizer": {"present": False, "type": None, "note": "single-stage; BaO hollow cathode on Xe"},
        "ignition": {"mode": "direct_on_atmospheric_gas", "evidence_class": "inferred",
                     "statement": "The thruster was ignited at known stable points and re-ignited after shutdowns with a "
                                  "higher flow (p.9); the gas at ignition is not stated explicitly, read here as direct "
                                  "ignition on the N2 anode flow with a Xe cathode (inferred, verify)."},
        "flow": q("anode N2 flow range operated", [1.144, 1.568], "mg/s", "measured", M, "Table 5 p.8",
                  "MFC 1 % of full scale (0-1.96 mg/s)", "55.0-75.4 sccm"),
        "voltage": q("discharge voltage range operated", [180, 250], "V", "measured", M, "Table 5 p.8"),
        "magnetic_field": q("B required relative to Xe/Kr", 1.48, "ratio to Xe/Kr field", "measured", M, "abstract; p.13 ('48 %')",
                            "not stated; the N2 B range is not legible in Table 5 of the accessed text layer"),
        "outcome": "sustained",
        "outcome_statement": "Operated on N2 within an envelope (stability = discharge sustained > 5 min); the authors "
                             "call N2 the narrowest envelope and note numerous spontaneous shutdowns with light gases.",
        "observations": {
            "oscillation_modes": "not quantified; I_d/I_b described as highly sensitive to changes (p.9)",
            "extinction": "see E11",
            "erosion": "not measured (endurance recommended as future work, p.21)",
            "cathode": "Xe only, 0.15 or 0.20 mg/s; 2.00 sccm for Ar/CO2/N2 vs 1.50 sccm for Xe/Kr (p.6, p.14)"},
        "quantities": [
            q("power range", [212, 452], "W", "measured", M, "Table 5 p.8"),
            q("peak anode efficiency point: voltage", 250, "V", "measured", M, "Table 6 p.11"),
            q("peak anode efficiency point: flow", 1.144, "mg/s", "measured", M, "Table 6 p.11"),
            q("peak anode efficiency point: power", 400, "W", "measured", M, "Table 6 p.11"),
            q("peak anode efficiency point: thrust", 8.20, "mN", "measured", M, "Table 6 p.11",
              "stand accuracy stated per range on p.7 (symbols lost in text layer)"),
            q("peak anode efficiency", 7.35, "%", "inferred", M, "Table 6 p.11"),
            q("fixed-power points: N2 flow at 350/400/450 W", [1.340, 1.475, 1.543], "mg/s", "measured", M,
              "Table 7 p.16", note="Table 7 title says 200 V, Fig. 8 caption says 250 V (inconsistent; verify)"),
            q("fixed-power points: thrust at 350/400/450 W", [7.25, 8.60, 9.70], "mN", "measured", M, "Table 7 p.16"),
            q("fixed-power points: mass utilization", [24, 25, 27], "%", "inferred", M, "Table 7 p.16", "Faraday probe 10 %"),
            q("channel mean diameter", 49, "mm", "measured", M, "Table 3 p.6"),
            q("channel width", 12, "mm", "measured", M, "Table 3 p.6"),
            q("N2 flow conversion check 55.0 sccm", dc["moskovitz_n2_55sccm_mg_s"], "mg/s", "inferred", M, "our arithmetic",
              "reference conditions of the paper not stated"),
        ],
        "implication": {
            "direction": "operation_without_preionizer_demonstrated",
            "statement": "A low-power single-stage Hall thruster sustained pure-N2 discharges without a pre-ionizer at "
                         "1.1-1.6 mg/s, but only with about 1.48x the Xe magnetic field and within a narrow, "
                         "voltage-dependent flow envelope.",
            "uncertainty": "Ignition gas inferred, not stated; Xe cathode; facility pressure effect addressed only in an "
                           "appendix; envelope minima are in a figure only (TBD digitization).",
            "applicability_limits": "0.2-0.45 kW, 180-250 V, coaxial-anode geometry (not a conventional SPT).",
            "abep_regime": ABEP_REGIME_TBD},
        "repository_derived": False})
    E.append({
        "id": "E11", "title": "Simplified CAMILA on pure N2 below its minimum voltage/flow envelope",
        "sources": [M], "evidence_level": 3, "evidence_class": "measured", "thruster": cam,
        "propellant": {"anode_gas": "N2 (pure)", "cathode_gas": "Xe", "xenon_in_anode_flow": False},
        "preionizer": {"present": False, "type": None, "note": "single-stage"},
        "ignition": {"mode": "direct_on_atmospheric_gas", "evidence_class": "inferred", "statement": "as E10"},
        "flow": q("minimum N2 flow for > 5 min operation vs voltage", "TBD - requires digitization of Fig. 6 (p.11); "
                  "values not tabulated", "mg/s", "digitized", M, "Fig. 6 p.11"),
        "voltage": q("minimum discharge voltage for > 5 min operation", "TBD - requires digitization of Fig. 6 (p.11)",
                     "V", "digitized", M, "Fig. 6 p.11"),
        "magnetic_field": nr("B at the boundary", "G", M, "not legible / not reported per point"),
        "outcome": "extinguished",
        "outcome_statement": "Below the minimum voltage/flow combination the discharge shut down spontaneously; lower "
                             "voltages required more flow, and the boundary slope is steepest for light gases.",
        "observations": {"oscillation_modes": "not quantified", "extinction": "spontaneous shutdowns; restart needed a "
                         "more stable parameter set", "erosion": "not measured", "cathode": "Xe"},
        "quantities": [q("boundary probe step in voltage", [0.5, 5.0], "V", "measured", M, "p.9",
                         note="flow steps 0.1-2.0 sccm, at least 1 min apart; stability = sustained > 5 min")],
        "implication": {
            "direction": "operation_bounded_extinction_observed",
            "statement": "Without a pre-ionizer, pure-N2 sustainment in this thruster has a voltage-dependent minimum flow.",
            "uncertainty": "Boundary values need digitization; 5-min stability criterion only.",
            "applicability_limits": "as E10", "abep_regime": ABEP_REGIME_TBD},
        "repository_derived": False})
    U = "MUNRO2023"
    E.append({
        "id": "E12", "title": "MaSHEKT-100 low-power magnetically shielded Hall thruster on N2 (abstract only)",
        "sources": [U, M], "evidence_level": 3, "evidence_class": "measured",
        "thruster": {"name": "MaSHEKT-100 (Southampton)", "family": "magnetically shielded Hall (low power)",
                     "power_class_kW": "0.03-0.81 across all propellants", "geometry_note": "not accessed"},
        "propellant": {"anode_gas": "N2 (pure)", "cathode_gas": "not accessed", "xenon_in_anode_flow": False},
        "preionizer": {"present": False, "type": None, "note": "single-stage (from the abstract)"},
        "ignition": {"mode": "direct_on_atmospheric_gas", "evidence_class": "measured",
                     "statement": "Second-hand: MOSKOVITZ2026 p.4 reports that the thruster could 'eventually' be ignited "
                                  "with pure N2, and that only three N2 data points were collected because of a component "
                                  "failure (verify in the primary)."},
        "flow": nr("anode N2 flow", "mg/s", U, "not accessed (abstract only)"),
        "voltage": nr("discharge voltage", "V", U, "not accessed (abstract only)"),
        "magnetic_field": nr("B", "G", U, "not accessed (abstract only)"),
        "outcome": "sustained",
        "outcome_statement": "The abstract states that the thruster was operated on diatomic nitrogen successfully (neon: "
                             "unstable).",
        "observations": {"oscillation_modes": "not accessed", "extinction": "not accessed", "erosion": "not accessed",
                         "cathode": "not accessed"},
        "quantities": [q("peak thrust on N2", 5.7, "mN", "measured", U, "abstract"),
                       q("peak anode efficiency on N2", 5.4, "%", "inferred", U, "abstract"),
                       q("peak specific impulse on N2", 1000, "s", "inferred", U, "abstract")],
        "implication": {
            "direction": "operation_without_preionizer_demonstrated",
            "statement": "Indicates direct N2 ignition and operation of a ~100 W single-stage Hall thruster without a "
                         "pre-ionizer, but with few points.",
            "uncertainty": "Abstract plus second-hand statements only; flow, voltage, cathode gas and stability not accessed.",
            "applicability_limits": "about 0.1 kW class; unknown flow regime.",
            "abep_regime": ABEP_REGIME_TBD},
        "repository_derived": False})
    G = "GURCIULLO2020"
    z70 = {"name": "Z-70 (Stanford, refurbished)", "family": "single-stage Hall (SPT-type)",
           "power_class_kW": [0.394, 0.745],
           "geometry_note": "BN channel OD 72 mm, ID 42 mm, depth 23 mm (p.148); 135 G at channel centreline, exit plane, "
                            "at 1.5 A (p.148)"}
    E.append({
        "id": "E13", "title": "Z-70 on Xe/N2 mixtures: xenon needed to sustain the discharge at <= about 0.7 kW",
        "sources": [G, "GURCIULLO2019", A], "evidence_level": 3, "evidence_class": "measured", "thruster": z70,
        "propellant": {"anode_gas": "Xe/N2 mixtures (Xe mass fraction down to about 10 %); pure N2 not sustained",
                       "cathode_gas": "Xe", "xenon_in_anode_flow": True},
        "preionizer": {"present": False, "type": None, "note": "single-stage"},
        "ignition": {"mode": "xenon_admixture_required", "evidence_class": "measured",
                     "statement": "A share of xenon was used because the discharge could not be sustained at the anode "
                                  "power investigated, which was limited by the 300 V supply (p.126)."},
        "flow": q("lowest Xe flow with N2 1.33-1.39 mg/s", 0.16, "mg/s", "measured", G, "p.177", "not stated"),
        "voltage": q("anode voltage", 290, "V", "measured", G, "p.177, Tables 4.6/4.7 pp.198-199"),
        "magnetic_field": q("radial B at channel centreline, exit plane", 135, "G", "measured", G, "p.148"),
        "outcome": "extinguished",
        "outcome_statement": "With Xe reduced below 0.16 mg/s at this power range the discharge became unstable and "
                             "eventually ceased (p.177); pure N2 was not operated at the available power.",
        "observations": {"oscillation_modes": "not reported", "extinction": "loss of discharge below 0.16 mg/s Xe",
                         "erosion": "not reported", "cathode": "IonTech HC-252 (BaO) on Xe, 0.46 mg/s (p.148)"},
        "quantities": [
            q("anode power at the lowest-Xe points", [603.2, 681.5], "W", "measured", G, "Tables 4.6/4.7 captions"),
            q("anode current at the lowest-Xe points", [2.08, 2.35], "A", "measured", G, "Tables 4.6/4.7 captions"),
            q("Xe mass fraction of anode flow at the lowest-Xe points", dc["gurciullo_min_xe_mass_fraction"], "1",
              "inferred", G, "our arithmetic on p.177 values"),
            q("cathode Xe flow", 0.46, "mg/s", "measured", G, "p.148"),
            q("anode supply voltage limit", 300, "V", "measured", G, "p.147"),
        ],
        "implication": {
            "direction": "xenon_admixture_required_in_tested_regime",
            "statement": "In a short (23 mm) xenon-optimized channel at <= 0.7 kW and 290 V, pure-N2 operation without a "
                         "pre-ionizer was not achieved; about 10 % Xe by mass was the lowest admixture that sustained.",
            "uncertainty": "The author attributes the limit to available power (supply voltage), and states pure N2/air "
                           "would be possible at higher power (citing CIFALI2011); not tested here.",
            "applicability_limits": "0.4-0.75 kW, 270-290 V, 23 mm channel, facility 6.5e-5 Torr on Xe (p.147).",
            "abep_regime": ABEP_REGIME_TBD},
        "repository_derived": False})
    E.append({
        "id": "E14", "title": "Z-70 on Xe/air mixtures (sustained with xenon admixture)",
        "sources": [G, "GURCIULLO2019", A], "evidence_level": 3, "evidence_class": "measured", "thruster": z70,
        "propellant": {"anode_gas": "Xe/air mixtures (Xe mass fraction 48-96 % per ANDREUSSI2022 p.26)",
                       "cathode_gas": "Xe", "xenon_in_anode_flow": True},
        "preionizer": {"present": False, "type": None, "note": "single-stage"},
        "ignition": {"mode": "xenon_admixture_required", "evidence_class": "measured", "statement": "as E13"},
        "flow": q("Xe + air flows (runs XeAir-3/4)", [0.78, 0.83], "mg/s", "measured", G, "Table 4.10 p.201",
                  note="0.78 mg/s Xe + 0.83 mg/s air"),
        "voltage": q("anode voltage", 290, "V", "measured", G, "Table 4.10 p.201"),
        "magnetic_field": q("radial B at channel exit (XeAir-3 / XeAir-4)", [135, 160], "G", "measured", G, "p.201"),
        "outcome": "sustained",
        "outcome_statement": "Operated on Xe/air mixtures down to about 48 % Xe (review) / 0.78 mg/s Xe with 0.83 mg/s air "
                             "(thesis); the author reports better performance with air than with N2.",
        "observations": {"oscillation_modes": "not reported", "extinction": "not reported for air",
                         "erosion": "not reported", "cathode": "Xe 0.46 mg/s"},
        "quantities": [q("anode current XeAir-3 (135 G)", 2.57, "A", "measured", G, "Table 4.10 p.201"),
                       q("anode current XeAir-4 (160 G)", 2.45, "A", "measured", G, "Table 4.10 p.201")],
        "implication": {
            "direction": "xenon_admixture_required_in_tested_regime",
            "statement": "Air operation in this thruster was only shown with substantial xenon admixture; no pre-ionizer "
                         "was used and pure air was not attempted at the available power.",
            "uncertainty": "Minimum Xe share for air not reported in the thesis text read here.",
            "applicability_limits": "as E13", "abep_regime": ABEP_REGIME_TBD},
        "repository_derived": False})
    SM = "SEMENKIN1995"
    E.append({
        "id": "E15", "title": "TsNIIMASH anode-layer thrusters on Xe + air mixtures (1995)",
        "sources": [SM, A], "evidence_level": 3, "evidence_class": "measured",
        "thruster": {"name": "TsNIIMASH anode-layer thrusters, 27 mm and 55 mm (D-55) anode diameter",
                     "family": "anode-layer Hall (TAL)", "power_class_kW": "not legible",
                     "geometry_note": "xenon designs, unmodified"},
        "propellant": {"anode_gas": "Xe + air mixtures (fractions not legible in the accessed scan)", "cathode_gas": "not reported",
                       "xenon_in_anode_flow": True},
        "preionizer": {"present": False, "type": None, "note": "single-stage TAL"},
        "ignition": {"mode": "xenon_admixture_required", "evidence_class": "measured",
                     "statement": "Xe addition to light propellants changed the operating mode and enabled the 'acceleration "
                                  "mode' (pp.3-4); pure-air operation is not characterized in the text."},
        "flow": nr("flows", "sccm", SM, "figure data not legible in the accessed scan"),
        "voltage": nr("voltages", "V", SM, "figure data not legible in the accessed scan"),
        "magnetic_field": nr("B", "G", SM),
        "outcome": "sustained",
        "outcome_statement": "Volt-ampere characteristics for Xe + air were measured; Xe additions allowed an effective "
                             "'acceleration mode' (p.4).",
        "observations": {"oscillation_modes": "not reported", "extinction": "not reported", "erosion": "not reported",
                         "cathode": "not reported"},
        "quantities": [],
        "implication": {
            "direction": "xenon_admixture_required_in_tested_regime",
            "statement": "Early evidence that a heavy-gas (Xe) discharge acts as the ionizer for light gases in a TAL; it "
                         "does not test pure air or a separate pre-ionizer.",
            "uncertainty": "Qualitative; figures illegible; mixture ratios for air unknown.",
            "applicability_limits": "TAL geometry, 1995 laboratory conditions.",
            "abep_regime": ABEP_REGIME_TBD},
        "repository_derived": False})
    H = "HRUBY2022"
    E.append({
        "id": "E16", "title": "Busek 2 kW-class BHT on 'air simulant' 68.3 % N2 / 6.7 % O2 / 25 % Ar (2005; secondary)",
        "sources": [A, H], "evidence_level": 5, "evidence_class": "measured",
        "thruster": {"name": "Busek BHT (2 kW nominal)", "family": "single-stage Hall (SPT-type)", "power_class_kW": [1, 5.5],
                     "geometry_note": "not reported"},
        "propellant": {"anode_gas": "air simulant 68.3 % N2, 6.7 % O2, 25 % Ar (Ar as surrogate for atomic O)",
                       "cathode_gas": "not reported", "xenon_in_anode_flow": False},
        "preionizer": {"present": False, "type": None, "note": "conventional single-stage"},
        "ignition": {"mode": "not_reported", "evidence_class": "measured", "statement": "not reported in the review"},
        "flow": q("best-efficiency point flow", 2.94, "mg/s", "measured", A, "Page 25 of 57"),
        "voltage": q("discharge voltage range", [200, 350], "V", "measured", A, "Page 25 of 57"),
        "magnetic_field": nr("B", "G", A),
        "outcome": "sustained",
        "outcome_statement": "Tested over 200-350 V and 1-5.5 kW; best anodic efficiency about 27 % at 350 V, 2.94 mg/s.",
        "observations": {"oscillation_modes": "not reported", "extinction": "not reported", "erosion": "not reported",
                         "cathode": "not reported"},
        "quantities": [q("discharge power range", [1, 5.5], "kW", "measured", A, "Page 25 of 57"),
                       q("best anodic efficiency", 27, "%", "inferred", A, "Page 25 of 57", "'about'")],
        "implication": {
            "direction": "operation_without_preionizer_demonstrated",
            "statement": "A conventional Hall thruster ran on an N2-rich simulant without a pre-ionizer.",
            "uncertainty": "Second-hand; 25 % argon (not atomic O) in the feed eases ionization; ignition and cathode gas "
                           "unknown.",
            "applicability_limits": "2 kW class, 1-5.5 kW, lab-fed gas.", "abep_regime": ABEP_REGIME_TBD},
        "repository_derived": False})
    E.append({
        "id": "E17", "title": "Busek ABHET prototype fed by duct / RF-Hall-generated flow (secondary)",
        "sources": [A, H], "evidence_level": 5, "evidence_class": "measured",
        "thruster": {"name": "Busek ABHET LX2 prototype", "family": "single-stage Hall (open-ended, extended channel per "
                     "patent; details unpublished)", "power_class_kW": "not reported", "geometry_note": "not reported"},
        "propellant": {"anode_gas": "air simulant in an inlet duct, or collected flow from an RF Hall source",
                       "cathode_gas": "not reported (the RF Hall source used a Xe cathode)", "xenon_in_anode_flow": False},
        "preionizer": {"present": False, "type": None,
                       "note": "the upstream RF Hall flow source delivers a partly ionized flow (large ion fraction), "
                               "i.e. the incoming flow is not neutral"},
        "ignition": {"mode": "not_reported", "evidence_class": "measured", "statement": "not reported"},
        "flow": nr("flow", "mg/s", A), "voltage": nr("voltage", "V", A), "magnetic_field": nr("B", "G", A),
        "outcome": "sustained",
        "outcome_statement": "The review states the ABHET was able to operate with the simulated VLEO flow; no "
                             "performance data (stand impingement, facility > 1e-4 Torr).",
        "observations": {"oscillation_modes": "not reported", "extinction": "not reported", "erosion": "not reported",
                         "cathode": "not reported"},
        "quantities": [q("facility pressure during operation", "> 1e-4", "Torr", "measured", A, "Page 35 of 57")],
        "implication": {
            "direction": "not_informative",
            "statement": "Qualitative operation with a pre-ionized upstream flow source; cannot separate the role of the "
                         "incoming ions from the thruster's own ionization.",
            "uncertainty": "Second-hand, qualitative, high facility pressure.",
            "applicability_limits": "unknown", "abep_regime": ABEP_REGIME_TBD},
        "repository_derived": False})
    E.append({
        "id": "E18", "title": "SITAEL RAM-EP double-stage thruster, end-to-end with intake and PFG (2017)",
        "sources": [F, A, "ANDREUSSI2017_IEPC377"], "evidence_level": 3, "evidence_class": "measured",
        "thruster": {"name": "SITAEL RAM-EP prototype", "family": "two-stage Hall (ionization stage + Hall-like acceleration stage)",
                     "power_class_kW": "not reported", "geometry_note": "not reported"},
        "propellant": {"anode_gas": "intake-collected flow from the HT5k PFG (4.7 mg/s 1.27N2 + O2 at the PFG); PFG also "
                                    "run on Xe", "cathode_gas": "Xe (hollow cathode neutralizer)", "xenon_in_anode_flow": False},
        "preionizer": {"present": True, "type": "dedicated first (ionization) stage of a double-stage device",
                       "note": "the collected flow from the PFG also contains ions"},
        "ignition": {"mode": "not_reported", "evidence_class": "measured",
                     "statement": "'first ignition and stable operation' of the full system is claimed (IEPC-2019-886 p.3); "
                                  "procedure not given"},
        "flow": q("PFG anode flow (upstream source, not the thruster inlet flow)", 4.7, "mg/s", "measured", F,
                  "Fig. 2 caption p.3", note="intake-delivered flow at the RAM-EP inlet was not measured (review p.46)"),
        "voltage": nr("RAM-EP stage voltages", "V", F), "magnetic_field": nr("B", "G", F),
        "outcome": "sustained",
        "outcome_statement": "The integrated system operated on the collected flow; 'good ionization capability', "
                             "acceleration stage below expectations.",
        "observations": {"oscillation_modes": "not reported", "extinction": "not reported", "erosion": "not reported",
                         "cathode": "conventional Xe-fed hollow cathode"},
        "quantities": [q("thrust produced by the system on the collected flow", 6, "mN", "measured", F,
                         "Fig. 1b caption and text p.3", 1),
                       q("drag on system with thruster off", 26, "mN", "measured", F, "Fig. 1b caption and text p.3", 1),
                       q("PFG-to-intake distance", 500, "mm", "measured", F, "Fig. 2 caption p.3")],
        "implication": {
            "direction": "preionization_stage_present_effect_not_isolated",
            "statement": "The only accessed intake-fed Hall-type operation used a dedicated ionization stage; it does not "
                         "show whether that stage was necessary.",
            "uncertainty": "Inlet density/flow not measured; upstream source partly ionized; Xe cathode; no single-stage "
                           "control case.",
            "applicability_limits": "ground end-to-end test at 500 mm from a Hall-thruster flow source.",
            "abep_regime": ABEP_REGIME_TBD},
        "repository_derived": False})
    SH = "SHABSHELOWITZ2014"
    E.append({
        "id": "E19", "title": "Michigan helicon Hall thruster on N2: single-stage vs RF-assisted (secondary)",
        "sources": [A, SH], "evidence_level": 5, "evidence_class": "measured",
        "thruster": {"name": "Helicon Hall thruster (HHT)", "family": "two-stage Hall (helicon RF first stage + Hall stage)",
                     "power_class_kW": "about 1.75 (review Table 3)", "geometry_note": "not accessed"},
        "propellant": {"anode_gas": "N2 (pure)", "cathode_gas": "Xe", "xenon_in_anode_flow": False},
        "preionizer": {"present": True, "type": "helicon RF stage (0-302 W)", "note": "operated both off and on"},
        "ignition": {"mode": "not_reported", "evidence_class": "measured", "statement": "not reported in the review"},
        "flow": q("anode N2 flow", 2.6, "mg/s", "measured", A, "Page 27 of 57"),
        "voltage": q("discharge voltage", 200, "V", "measured", A, "Page 27 of 57"),
        "magnetic_field": nr("B", "G", A),
        "outcome": "sustained",
        "outcome_statement": "Operated on N2 in single-stage mode (RF off) and with RF up to 302 W. RF produced a minor "
                             "thrust increase while thrust-to-power and anode efficiency decreased consistently.",
        "observations": {"oscillation_modes": "not reported", "extinction": "not reported", "erosion": "not reported",
                         "cathode": "Xe 1 mg/s (38.4 % cathode flow fraction per the review)"},
        "quantities": [q("RF power range", [0, 302], "W", "measured", A, "Page 27 of 57"),
                       q("cathode Xe flow", 1, "mg/s", "measured", A, "Page 27 of 57"),
                       q("cathode/anode flow ratio", dc["shabshelowitz_cathode_fraction"], "1", "inferred", A,
                         "our arithmetic"),
                       q("single-stage propellant utilization", 0.10, "1", "inferred", A, "Page 28 of 57", "'~'"),
                       q("single-stage beam divergence efficiency", 0.60, "1", "inferred", A, "Page 28 of 57", "'~'")],
        "implication": {
            "direction": "preionization_stage_tested_no_net_benefit_reported",
            "statement": "The single-stage Hall mode sustained on N2 without the RF stage; adding RF pre-ionization raised "
                         "utilization slightly but did not pay for its power in this device.",
            "uncertainty": "Second-hand (primary not accessible); very large Xe cathode fraction (about 38 %) may have "
                           "assisted sustainment.",
            "applicability_limits": "one flow (2.6 mg/s), 200 V, laboratory facility.",
            "abep_regime": ABEP_REGIME_TBD},
        "repository_derived": False})
    D = "DUKHOPELNIKOV2021"
    E.append({
        "id": "E20", "title": "Laboratory closed-drift thruster (38 mm mean channel diameter) on air and 2:1 N2/O2",
        "sources": [D, A], "evidence_level": 5, "evidence_class": "measured",
        "thruster": {"name": "laboratory model, Moscow State Technical University per review Table 3 (xenon design)", "family": "anode-layer / closed-drift Hall "
                     "(title: 'thruster with anode layer')", "power_class_kW": "not reported",
                     "geometry_note": "38 mm average channel diameter (review p.26)"},
        "propellant": {"anode_gas": "air; N2/O2 2:1", "cathode_gas": "Xe", "xenon_in_anode_flow": False},
        "preionizer": {"present": False, "type": None, "note": "single-stage"},
        "ignition": {"mode": "not_reported", "evidence_class": "measured", "statement": "not reported"},
        "flow": q("total mass flow", [0.8, 1.0], "mg/s", "measured", A, "Page 26 of 57", note="0.8, 0.9, 1.0 mg/s"),
        "voltage": q("discharge voltage", "from below 100 up to 350", "V", "measured", A, "Page 26 of 57"),
        "magnetic_field": nr("B", "G", A),
        "outcome": "sustained",
        "outcome_statement": "Operated on air and N2/O2; I_d-V plateau 50-100 V higher than Xe; I_d 2.1-2.4x (air) and "
                             "1.9-2.7x (N2/O2) the Xe value at 200-350 V; mass utilization on average 2.3x lower than Xe.",
        "observations": {"oscillation_modes": "not reported", "extinction": "not reported", "erosion": "not reported",
                         "cathode": "Xe 0.19 mg/s"},
        "quantities": [q("cathode Xe flow", 0.19, "mg/s", "measured", A, "Page 26 of 57"),
                       q("I_d ratio air/Xe (200-350 V)", [2.1, 2.4], "1", "measured", A, "Page 27 of 57"),
                       q("thrust estimate basis: assumed voltage utilization", 0.75, "1", "assumed", A, "Page 26 of 57",
                         note="thrust was not measured; estimated from Faraday data")],
        "implication": {
            "direction": "operation_without_preionizer_demonstrated",
            "statement": "A small xenon-design closed-drift thruster operated on air and N2/O2 at about 1 mg/s without a "
                         "pre-ionizer (Xe cathode).",
            "uncertainty": "Abstract + review only; thrust inferred with an assumed voltage utilization; ignition not reported.",
            "applicability_limits": "small TAL-type device, 0.8-1.0 mg/s.", "abep_regime": ABEP_REGIME_TBD},
        "repository_derived": False})
    E.append({
        "id": "E21", "title": "Aerospace Corp. 2-stage air-breathing cylindrical Hall thruster (ECR + CHT) - xenon only",
        "sources": [A, "DIAMANT2010"], "evidence_level": 5, "evidence_class": "measured",
        "thruster": {"name": "ABCHT prototype", "family": "two-stage Hall (ECR ionization + cylindrical Hall acceleration)",
                     "power_class_kW": "not reported", "geometry_note": "not reported"},
        "propellant": {"anode_gas": "xenon only (no atmospheric gas test reported)", "cathode_gas": "not reported "
                       "(1 % thoriated W filament selected for the concept, review p.38)", "xenon_in_anode_flow": True},
        "preionizer": {"present": True, "type": "ECR stage", "note": "designed for low-pressure air ionization"},
        "ignition": {"mode": "not_reported", "evidence_class": "measured", "statement": "not reported"},
        "flow": nr("flow", "mg/s", A), "voltage": nr("voltage", "V", A), "magnetic_field": nr("B", "G", A),
        "outcome": "not_reported",
        "outcome_statement": "Prototype assembled but only tested with xenon (review p.37).",
        "observations": {"oscillation_modes": "not reported", "extinction": "not reported", "erosion": "not reported",
                         "cathode": "filament"},
        "quantities": [],
        "implication": {
            "direction": "not_informative",
            "statement": "No atmospheric-gas evidence; a pre-ionizer concept without a test on N2/O2/air.",
            "uncertainty": "Second-hand; no atmospheric-gas data exist in the accessed record.",
            "applicability_limits": "none for N2/O2/air (xenon tests only).", "abep_regime": ABEP_REGIME_TBD},
        "repository_derived": False})
    return E


EXCLUDED = [
    {"item": "MCFT-2139 multi-cusped field thruster on N2 (Hu et al., Vacuum 190, 110275, 2021, doi:10.1016/j.vacuum.2021.110275)",
     "reason": "cusped-field device, not a Hall (closed E x B drift) thruster; outside the Hall-only lane (reported in "
               "ANDREUSSI2022 p.27)"},
    {"item": "RIT-10 on N2 and O2 (CIFALI2011 section III)", "reason": "gridded ion engine, not Hall"},
    {"item": "JAXA ABIE (ECR + grids), IRS IPT/IPG6-S (RF, magnetic nozzle), helicon double layer, MET, PPT",
     "reason": "not Hall discharges"},
    {"item": "Cha 2015 simulations of N2 in the SHT (cited in MARCHIONI2020)", "reason": "model results, not evidence of "
     "physical sustainment"},
    {"item": "P5-N2 v1 vacuum simulation campaign (this repository)", "reason": "model results (INCONCLUSIVE); kept only "
     "as context_not_evidence"},
]


def v1_context():
    s = _load("v1_scores")
    return {
        "status": "CONTEXT ONLY - NOT EVIDENCE. These are counts of simulated run x reading evaluations of the P5-N2 v1 "
                  "vacuum campaign. They are model results and say nothing about whether a physical discharge ignites "
                  "or sustains. v1 is INCONCLUSIVE; no candidate is admitted; the credible set is empty.",
        "file": REPO_FILES["v1_scores"],
        "n_records": s["n_records"],
        "vacuum_status_counts": s["status_counts"]["vacuum"],
    }


def build():
    dc = derived_checks()
    entries = p5_entries() + echt_entries() + literature_entries(dc)
    entries.sort(key=lambda e: int(e["id"][1:]))
    return {
        "id": "hall_sustainment_matrix_v1",
        "date": "2026-09-26",
        "lane": "HSUS - Hall-only sustainment / ignition evidence on N2, O2, air",
        "status": "EVIDENCE AUDIT ONLY. Nothing simulated, scored, tuned or admitted. No architecture conclusion.",
        "schema": "hall_sustainment_matrix.schema.json",
        "builder": "docs/evidence/hall_sustainment/build_hall_sustainment_matrix.py",
        "definitions": {
            "preionizer": "a dedicated ionization stage separate from the Hall acceleration discharge (RF/helicon/ECR "
                          "stage, first stage of a two-stage device). The hollow cathode is recorded separately and is not "
                          "counted as a pre-ionizer; its gas (Xe/Ar/N2) is recorded because it may assist ionization.",
            "ignition_modes": {
                "direct_on_atmospheric_gas": "discharge started with the atmospheric gas on the anode (cathode gas recorded separately)",
                "xenon_start_then_transition": "discharge started on xenon, then the anode (and possibly cathode) moved to atmospheric gas",
                "xenon_admixture_required": "xenon kept in the anode flow because the atmospheric gas alone did not sustain",
                "not_reported": "the accessed text does not say"},
            "outcomes": {
                "sustained": "discharge operated steadily at the reported condition(s)",
                "extinguished": "discharge could not be sustained / ceased / flamed out at the reported condition",
                "unstable": "operated but reported as unstable without loss of discharge",
                "not_reported": "no atmospheric-gas outcome reported"},
            "evidence_level": "docs/EVIDENCE.md hierarchy (1 = in-house hardware ... 7 = assumption); second-hand "
                              "reports via a review are level 5",
            "evidence_class": EVIDENCE_CLASSES,
        },
        "meta": {"repository_inputs": {k: {"path": p, "sha256": _sha256(k)} for k, p in sorted(REPO_FILES.items())}},
        "sources": SOURCES,
        "derived_checks": dc,
        "entries": entries,
        "excluded": EXCLUDED,
        "context_not_evidence": {"p5_n2_v1_vacuum": v1_context()},
    }


MD = os.path.join(HERE, "HALL_SUSTAINMENT_EVIDENCE.md")
BEGIN, END = "<!-- BEGIN GENERATED: build_hall_sustainment_matrix.py -->", "<!-- END GENERATED -->"


def _fmt(v):
    if isinstance(v, list):
        return "-".join("%g" % x for x in v) if len(v) == 2 else ", ".join("%g" % x for x in v)
    if isinstance(v, (int, float)):
        return "%g" % v
    return str(v)


def _qfmt(qd):
    return "n/r" if isinstance(qd["value"], str) else "%s %s" % (_fmt(qd["value"]), qd["unit"])


def render_md(m):
    """Generated part of HALL_SUSTAINMENT_EVIDENCE.md (summary table and per-entry statements)."""
    L = [BEGIN, "", "### Summary matrix", "",
         "| id | thruster (family) | anode gas / cathode gas | ignition | flow | voltage | B | outcome | level | "
         "pre-ionization implication |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for e in m["entries"]:
        L.append("| %s | %s (%s) | %s / %s | %s | %s | %s | %s | **%s** | %d | %s |" % (
            e["id"], e["thruster"]["name"], e["thruster"]["family"], e["propellant"]["anode_gas"],
            e["propellant"]["cathode_gas"], e["ignition"]["mode"], _qfmt(e["flow"]), _qfmt(e["voltage"]),
            _qfmt(e["magnetic_field"]), e["outcome"], e["evidence_level"], e["implication"]["direction"]))
    L += ["", "n/r = not reported in the accessed text (or TBD); ranges are min-max over the reported points.", "",
          "### Per-item statements", ""]
    for e in m["entries"]:
        srcs = ", ".join("%s (%s)" % (k, m["sources"][k]["access"]) for k in e["sources"])
        L += ["#### %s - %s" % (e["id"], e["title"]), "",
              "- Sources / access: %s. Evidence level %d; outcome evidence class: %s%s." % (
                  srcs, e["evidence_level"], e["evidence_class"],
                  "; repository-derived values recomputed by the builder" if e["repository_derived"] else ""),
              "- Pre-ionizer: %s. Ignition (%s, %s): %s" % (
                  "yes - " + e["preionizer"]["type"] if e["preionizer"]["present"] else "none",
                  e["ignition"]["mode"], e["ignition"]["evidence_class"], e["ignition"]["statement"]),
              "- Outcome: **%s**. %s" % (e["outcome"], e["outcome_statement"]),
              "- Observations: oscillations: %s; extinction: %s; erosion: %s; cathode: %s." % (
                  e["observations"]["oscillation_modes"], e["observations"]["extinction"],
                  e["observations"]["erosion"], e["observations"]["cathode"]),
              "- **Implication for 'is pre-ionization required?'** (%s): %s" % (
                  e["implication"]["direction"], e["implication"]["statement"]),
              "  - Uncertainty: %s" % e["implication"]["uncertainty"],
              "  - Applicability limits: %s" % e["implication"]["applicability_limits"],
              "  - ABEP flow/density regime: %s" % e["implication"]["abep_regime"], ""]
        if e["quantities"]:
            L += ["  | quantity | value | unit | class | uncertainty | source, locator |", "  |---|---|---|---|---|---|"]
            for qd in e["quantities"]:
                L.append("  | %s | %s | %s | %s | %s | %s, %s |" % (
                    qd["name"], _fmt(qd["value"]), qd["unit"], qd["evidence_class"], _fmt(qd["uncertainty"]),
                    qd["source"], qd["locator"]))
            L.append("")
    L.append(END)
    return "\n".join(L)


def splice_md(md_text, generated):
    a, b = md_text.index(BEGIN), md_text.index(END) + len(END)
    return md_text[:a] + generated + md_text[b:]


def dumps(d):
    return json.dumps(d, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv):
    m = build()
    text = dumps(m)
    with open(MD) as f:
        md_old = f.read()
    md_new = splice_md(md_old, render_md(m))
    if "--check" in argv:
        with open(OUT) as f:
            same = f.read() == text and md_old == md_new
        print("OK" if same else "DIFFERS")
        return 0 if same else 1
    with open(OUT, "w") as f:
        f.write(text)
    with open(MD, "w") as f:
        f.write(md_new)
    print("wrote", os.path.relpath(OUT, ROOT), "and the generated section of", os.path.relpath(MD, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
