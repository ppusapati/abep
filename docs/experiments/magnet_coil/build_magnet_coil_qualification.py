"""Build the H-1 magnet/coil qualification basis (fo_magnet_coil_qualification), DRAFT for owner review.

    python docs/experiments/magnet_coil/build_magnet_coil_qualification.py          # (re)write the JSON
    python docs/experiments/magnet_coil/build_magnet_coil_qualification.py --check  # verify the committed JSON

What this is: a candidate matrix of ACTUAL supplier grades / products for the H-1 magnetic circuit (permanent magnets,
magnet wire / conductors, winding-insulation systems), the qualification tests each needs, and requirement IDs that W3
(hardware definition), W4 (instrumentation), the AO/lifetime lane and lane 15 (abep_sim/thermal_life.py) can adopt.

What this is not: no qualification verdict, no lifetime verdict, no H-1 design value, no architecture ranking. Every
transcribed value is typed in by hand from a source listed in SOURCES (accessed 2026-09-27; the sha256 of the accessed
file is recorded). Every value that did not come straight out of a source is computed in `derived()` below. Generic MIL
class-C derating (NASA EEE-INST-002) and generic MMPA family values are carried as REFERENCE EVIDENCE ONLY and never
produce a lifetime verdict. Thresholds that are not in the RFP are PROPOSED for the owner.

Pure standard library; not imported by abep_sim; no network access at build time.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "magnet_coil_qualification_v1.json"
SCHEMA_FILE = "docs/experiments/magnet_coil/magnet_coil_qualification_v1.schema.json"
ACCESSED = "2026-09-27"

QUANTITY_TYPES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")

# ----------------------------------------------------------------------------------------------------------- sources
SOURCES = {
    "arnold_recoma_combined": {
        "citation": "Arnold Magnetic Technologies, Recoma Sintered Samarium Cobalt Magnets - combined grade datasheets "
                    "(summary table 'Summary of main grades of SmCo5 and Sm2Co17' and per-grade sheets; (c) 2014; "
                    "Recoma 33E sheet Rev. 140403a)",
        "url": "https://www.arnoldmagnetics.com/wp-content/uploads/2017/10/Recoma-Combined-160301.pdf",
        "access": "manufacturer datasheet, openly accessible; states data are typical, for general reference only, "
                  "not guaranteed",
        "sha256_accessed": "4da6cbd3eced4ffca114f2756163ea2767aecfec5033a227d71b4b50b308e79e",
        "locator_convention": "physical PDF page",
    },
    "arnold_recoma_ht": {
        "citation": "G. Martinek, U. Wyss (Arnold Magnetic Technologies), RECOMA HT - Rare Earth Magnets for High "
                    "Temperatures (application note)",
        "url": "https://www.arnoldmagnetics.com/wp-content/uploads/2020/05/Recoma-HT.pdf",
        "access": "manufacturer application note, openly accessible; demagnetization curves are graphical only",
        "sha256_accessed": "2ceb8c12e65c342e751a58027b98e6ade2ef7fced8ccd1ab856b93e2934a9215",
        "locator_convention": "printed page number ('Arnold Magnetic Technologies | n')",
    },
    "eec_uht_smco_page": {
        "citation": "Electron Energy Corporation, 'Ultra-High Temperature Samarium Cobalt Magnets' (product web page)",
        "url": "https://www.electronenergy.com/ultra-high-temperature-samarium-cobalt-magnets/",
        "access": "manufacturer web page, openly accessible; no grade datasheet with demagnetization curves was accessed",
        "sha256_accessed": "28fc90de7eedeac0947c9e874c347f58ee82c132eb8be137f43a29f9e003b08f",
        "locator_convention": "web page body text",
    },
    "arnold_neo_catalog": {
        "citation": "Arnold Magnetic Technologies, Neodymium-Iron-Boron Magnet Grades - Summary Product List & Reference "
                    "Guide, Rev. 181031 (file name Catalog-151021.pdf)",
        "url": "https://www.arnoldmagnetics.com/wp-content/uploads/2017/10/Catalog-151021.pdf",
        "access": "manufacturer catalog, openly accessible; the column heading 'Tw max' is not defined in the "
                  "accessed text",
        "sha256_accessed": "9e4ca93492b7bb43b175dcdf681d7c541f952ed1667eaec86cdd20aeef47c202",
        "locator_convention": "physical PDF page",
    },
    "arnold_n35eh": {
        "citation": "Arnold Magnetic Technologies, N35EH sintered NdFeB datasheet, Rev. 210607",
        "url": "https://www.arnoldmagnetics.com/wp-content/uploads/2017/11/N35EH-151021.pdf",
        "access": "manufacturer datasheet, openly accessible; demagnetization curves (-40 to 220 C) graphical only; "
                  "no maximum-use row",
        "sha256_accessed": "981d77c484b1ba37c108aaec10b055f8f2c5b114c8b2ae10a59ad3c200e4cf7c",
        "locator_convention": "single-page datasheet",
    },
    "arnold_n42sh": {
        "citation": "Arnold Magnetic Technologies, N42SH sintered NdFeB datasheet (re-accessed; same file as lane 15 "
                    "source arnold_n42sh in schemas/thermal_life/limits_v1.json)",
        "url": "https://www.arnoldmagnetics.com/wp-content/uploads/2017/11/N42SH-151021.pdf",
        "access": "manufacturer datasheet, openly accessible; no maximum-use row",
        "sha256_accessed": "c0bd4c03ba5896d2de9cbdd4d5ac9a1e16da4815a4cfdd8bcb132918c8953a36",
        "locator_convention": "single-page datasheet",
    },
    "mmpa_0100_00": {
        "citation": "Magnetic Materials Producers Association, MMPA Standard No. 0100-00, Standard Specifications for "
                    "Permanent Magnet Materials (re-accessed; same source as lane 15 mmpa_0100_00; publication year "
                    "not printed in the accessed copy: verify)",
        "url": "https://allianceorg.com/pdfs/MMPA_0100-00.pdf",
        "access": "full text on a third-party host (Alliance LLC); page 20 was rendered as an image and inspected on "
                  "2026-09-27",
        "sha256_accessed": "3d83974ac1f08635311a415d9245fc3183bc0c2aab540cf8bd77afecb5892792",
        "locator_convention": "printed page number",
    },
    "remington_mw16c": {
        "citation": "Remington Industries, Polyimide-Enameled Copper Magnet Wire MW 16-C Data Sheet (drawn AG 10/13/21)",
        "url": "https://www.remingtonindustries.com/content/Polyimide%20Magnet%20Wire%20Data%20Sheet.pdf",
        "access": "supplier datasheet, openly accessible (a distributor, not the enamel manufacturer)",
        "sha256_accessed": "ba3d5e2284da9b9267e68aa0918cd07361e8f3a96c07036b5a56470daa44d7b6",
        "locator_convention": "single-page datasheet",
    },
    "nema_mw1000_annex_c": {
        "citation": "ANSI/NEMA MW 1000-2016, Annex C (informative): Cross Reference of NEMA and IEC Magnet Wire "
                    "Specifications",
        "url": "https://www.nema.org/docs/default-source/products-document-library/"
               "ansi-nema-mw-1000-2016---annex-c.pdf",
        "access": "publisher-posted annex, openly accessible; the standard itself was not accessed",
        "sha256_accessed": "cb8e2b060fb59597497c63497b7c42d8888b2e7380c49ae06c685750dd415c04",
        "locator_convention": "physical PDF page",
    },
    "ceramawire_ht": {
        "citation": "Ceramawire, High Temperature Magnet Wire - Technical Specifications (HT Wire)",
        "url": "https://www.motionsensors.com/wp-content/uploads/2022/07/ceramaTechspec.pdf",
        "access": "manufacturer technical specification, accessed via a distributor copy (Motion Sensors Inc.); the "
                  "manufacturer host ceramawire.com returned a proxy 502 on 2026-09-27 and was not retried by other "
                  "means",
        "sha256_accessed": "dde43a06de652f483f004b5f89be91284fedd60d56fca902018a0be1929948f5",
        "locator_convention": "physical PDF page",
    },
    "honeywell_us9508486": {
        "citation": "J. Piascik et al. (Honeywell International Inc.), High temperature electromagnetic coil "
                    "assemblies, US Patent 9,508,486 B2, 29 Nov 2016 (division of US 8,572,838)",
        "url": "https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9508486",
        "access": "USPTO image PDF, openly accessible; only the front page (abstract) was read (no text layer, no OCR)",
        "sha256_accessed": "befa4064fa439f168d0fa23f11066375ca6c7aae1e21f4fd61cf782183a38a7b",
        "locator_convention": "front page, item (57) Abstract",
    },
    "nasa_myers_2016_hermes": {
        "citation": "J. Myers, H. Kamhawi, J. Yim, L. Clayman, Hall Thruster Thermal Modeling and Test Data "
                    "Correlation, AIAA Propulsion and Energy Conference, Salt Lake City, July 2016 (NTRS 20170000961)",
        "url": "https://ntrs.nasa.gov/api/citations/20170000961/downloads/20170000961.pdf",
        "access": "full text, openly accessible (NASA NTRS)",
        "sha256_accessed": "8a9f79089c8630123b2e1ec8ad0740dcd3141377d897462ca1ebcbf7d5c8e85f",
        "locator_convention": "physical PDF page",
    },
    "nasa_kamhawi_2013_300ms": {
        "citation": "H. Kamhawi et al., Performance and Thermal Characterization of the NASA-300MS 20 kW Hall Effect "
                    "Thruster, IEPC-2013-444, 33rd IEPC, Washington DC, 2013 (NTRS 20140017775)",
        "url": "https://ntrs.nasa.gov/api/citations/20140017775/downloads/20140017775.pdf",
        "access": "full text, openly accessible (NASA NTRS); Table 4 read from the rendered page image",
        "sha256_accessed": "9e71d7ce85f7f4bca153ddd5dec03b0ee7e782f880e324ed205859eb260bd97e",
        "locator_convention": "physical PDF page",
    },
    "nasa_jankovsky_1999": {
        "citation": "R. S. Jankovsky, Preliminary Evaluation of a 10 kW Hall Thruster, NASA/TM-1999-209075, "
                    "AIAA-99-0456",
        "url": "https://ntrs.nasa.gov/api/citations/19990046494/downloads/19990046494.pdf",
        "access": "full text, openly accessible (NASA NTRS)",
        "sha256_accessed": "e99645c2dd5a7a3c8a92329cd8af97096e1245c37f03028e414001806b922cb1",
        "locator_convention": "physical PDF page",
    },
    "nasa_scialdone_e595": {
        "citation": "J. Scialdone, P. Isaac, C. Clatterbuck, R. Hunkeler (NASA Goddard Space Flight Center), "
                    "Outgassing total mass loss obtained with micro-CVCM and other vacuum systems (NTRS 20000053099; "
                    "year from the NTRS id only: verify)",
        "url": "https://ntrs.nasa.gov/api/citations/20000053099/downloads/20000053099.pdf",
        "access": "full text, openly accessible (NASA NTRS); ASTM E595 itself was not accessed (paywalled)",
        "sha256_accessed": "b076afacf7f302a0dc15439d15f123db8facd74d70868459a0f7bebe391bbdfe",
        "locator_convention": "physical PDF page",
    },
    "iec60216_1_2013_preview": {
        "citation": "IEC 60216-1:2013, Edition 6.0 (2013-03), Electrical insulating materials - Thermal endurance "
                    "properties - Part 1: Ageing procedures and evaluation of test results",
        "url": "https://cdn.standards.iteh.ai/samples/18941/ba48414dc4b3407fbd71fde050f9dbb7/IEC-60216-1-2013.pdf",
        "access": "publisher-sanctioned sample (iTeh Standards), introduction, scope and clause 3 only; the standard was "
                  "not purchased; an IEC 60216-1:2025 edition is listed by iTeh (not accessed; edition currency: "
                  "verify)",
        "sha256_accessed": "ac51afe3d23cf4d98a01bb57ac0de8dcc2d3c5adf1e5781172a0bc223b2c07a0",
        "locator_convention": "printed page number",
    },
    "ul_1446_workshop": {
        "citation": "UL Performance Materials, Electrical Insulation Systems: UL 1446 - Understanding, Specifying and "
                    "Evaluating Electrical Insulation Systems for UL Certified Applications (workshop description)",
        "url": "https://code-authorities.ul.com/wp-content/uploads/sites/2/2015/08/electrical-insulation-systems-ul1446.pdf",
        "access": "UL flyer, openly accessible; UL 1446 itself was not accessed (not purchased)",
        "sha256_accessed": "ae0ca59af4abfcf9919547cb405c2d4c9cc79334bcc779e050646920870743f8",
        "locator_convention": "single page",
    },
    "psma_eaton_2023": {
        "citation": "D. Eaton (Triad Magnetics), Addressing Temperature Ratings and Safety Agency Regulations in "
                    "Magnetics Design, PSMA Magnetics Workshop 2023 (slides)",
        "url": "https://www.psma.com/sites/default/files/uploads/2023MagneticsWorkshopPresentations/"
               "Addressing_Temperature_Ratings_and_Safety_Agency_Regulations_In_Magnetics_Design_Eaton_Triad%20S.pdf",
        "access": "workshop slides, openly accessible (secondary source for the UL 1446 class letters)",
        "sha256_accessed": "15c15162290f69c47a935f6433e01e359c66341a11914288fa20f30cc8927b4b",
        "locator_convention": "slide number",
    },
}

# Access attempts that did not yield usable evidence (recorded so nobody re-tries blindly or assumes absence of data).
ACCESS_FAILURES = [
    {"what": "Ceramawire manufacturer host (technical-information page and PDF)",
     "url": "https://www.ceramawire.com/technical-information/ceramaTechspec.pdf",
     "result": "proxy 502 Bad Gateway on 2026-09-27; a distributor copy of the same specification was used instead"},
    {"what": "Fermilab paper on mineral-insulated hollow conductor for magnets",
     "url": "https://lss.fnal.gov/conf/C720919/p456.pdf",
     "result": "HTTP 403 on 2026-09-27; not bypassed. No MI-conductor source is carried"},
    {"what": "Google Patents text of US 9,508,486 B2 / US 8,572,838 B2",
     "url": "https://patents.google.com/patent/US9508486B2/en",
     "result": "HTTP 503 on 2026-09-27; the USPTO image PDF front page was read instead; the description text (which "
               "a search snippet says contains anodized-Al temperature statements) was NOT read, so no temperature "
               "value is taken from the patent"},
    {"what": "NASA outgassing database (ASTM E595 values per material)",
     "url": "https://outgassing.nasa.gov/",
     "result": "interactive web application; no per-material E595 record for any candidate EIS material was "
               "retrieved in this lane. E595 values stay TBD"},
    {"what": "IEC 60085 edition history",
     "url": "https://www.document-center.com/standards/show/IEC-60085/history/",
     "result": "HTTP 403 on 2026-09-27; a web search found no edition later than Ed. 4.0 (2007) but this is not "
               "conclusive (verify)"},
]

# Repository files this lane read (present in the base commit) and planned paths of parallel workstreams that it only
# references by path. Nothing here is imported; the test checks that the 'present_in_base' files exist.
REPOSITORY_REFERENCES = [
    {"path": "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json", "role": "owner disposition od_hardware_pivot incl. "
     "controls_addendum_2026_09_27 and execution_directive_2026_09_27 (this lane's mandate)", "present_in_base": True},
    {"path": "docs/thermal_life/THERMAL_LIFE_FRAMEWORK.md", "role": "lane 15 framework; open questions answered in "
     "lane15_answers", "present_in_base": True},
    {"path": "schemas/thermal_life/limits_v1.json", "role": "lane 15 sourced limits (pm_*, iec60085_thermal_classes, "
     "eee_inst_002_magnetics, copper records, irreversible_loss_criterion)", "present_in_base": True},
    {"path": "schemas/thermal_life/inputs_v1.json", "role": "lane 15 input contract (hall_magnet, ecr_magnet inputs)",
     "present_in_base": True},
    {"path": "docs/architecture_comparison/hall_reference/HALL_ACCELERATOR_REFERENCE.md", "role": "lane 17 B(z) "
     "interface, EV-B2/EV-B4 field-magnitude evidence, INV-B1..B3, forbidden design-value sources",
     "present_in_base": True},
    {"path": "docs/architecture_comparison/electrical_closure/ELECTRICAL_CLOSURE.md", "role": "lane 20 magnet power "
     "model (abep_sim/magnet_power.py), EM-RESONANCE-B, HM-PM-OPTION", "present_in_base": True},
    {"path": "docs/architecture_comparison/experiment_protocol/EXPERIMENT_PROTOCOL_DRAFT.md", "role": "lane 06 "
     "INV-MAG, CONFOUNDED_MAGNETIC, magnet_supplies metering", "present_in_base": True},
    {"path": "docs/architecture_comparison/experiment_package/EXPERIMENT_PACKAGE.md", "role": "lane 25 REQ-HW-06 "
     "(B(z) mapping), TR-09", "present_in_base": True},
    {"path": "docs/architecture_comparison/cathode_integration/CATHODE_INTEGRATION.md", "role": "lane 19 start-up "
     "order incl. hall_magnet / ecr_magnet", "present_in_base": True},
    {"path": "docs/evidence/wall_life/WALL_LIFE_EVIDENCE.md", "role": "lane 32 wall-life evidence (context only)",
     "present_in_base": True},
    {"path": "docs/EVIDENCE.md", "role": "evidence levels and quantity types", "present_in_base": True},
]
PLANNED_PATHS = [
    {"path": "docs/architecture_comparison/feed_state_closure/", "workstream": "W1 feed-state closure",
     "use_here": "none (the coil/magnet basis does not depend on feed state)"},
    {"path": "docs/architecture_comparison/lock1/", "workstream": "W2 LOCK-1",
     "use_here": "owner questions MCQ-OQ-* are candidates for LOCK-1 items"},
    {"path": "docs/experiments/hardware/", "workstream": "W3 hardware definition",
     "use_here": "requirements MCQ-W3-* are written for adoption by W3; the W3 draft IDs HW-MC-01..05, HW-PIM-03/04 "
                 "and HWQ-05 are referenced as read from a sibling worktree draft (read-only, may change)"},
    {"path": "docs/experiments/instrumentation/", "workstream": "W4 instrumentation",
     "use_here": "requirements MCQ-W4-* (coil temperature and B(z) measurement)"},
    {"path": "docs/validation/hall_transport_v2_prereg/", "workstream": "W5 held-out validation pre-registration",
     "use_here": "B(z) at actual coil currents and temperature is a W5 held-out candidate; this lane only requires "
                 "that it is recorded (MCQ-W4-03)"},
    {"path": "docs/chemistry/o_o2/v0/", "workstream": "W7 O/O2 chemistry", "use_here": "none"},
    {"path": "docs/experiments/lifetime_ao/", "workstream": "fo_ao_lifetime_register (AO/lifetime lane)",
     "use_here": "AO coordination: AOL-M06, AOL-M07, AOL-WC-04, AOL-EX-02, AOL-PM-06, AOL-PM-08 are referenced as "
                 "read from a sibling worktree draft (read-only, may change); MCQ-AO-* map this lane's tests to them"},
    {"path": "(fo_s1_readiness_gate output, path not yet known)", "workstream": "fo_s1_readiness_gate",
     "use_here": "s1_gate_items lists the magnet/coil items that the S1-readiness gate can report as missing"},
]


# ------------------------------------------------------------------------------------------------------ helpers
def val(value, unit, as_published, source, locator, level, qtype, uncertainty, domain, status):
    assert qtype in QUANTITY_TYPES, qtype
    assert source in SOURCES or source.startswith("repo:") or source == "derived", source
    return {
        "value": value, "unit": unit, "as_published": as_published, "source_id": source, "locator": locator,
        "evidence_level": level, "quantity_type": qtype, "uncertainty": uncertainty,
        "applicability_domain": domain, "validation_status": status,
    }


def tbd(requires):
    return {"value": None, "TBD": "TBD - requires " + requires}


NOT_VALIDATED = "not validated on Vyovrinda hardware; supplier typical value"
TYP = "typical value, not guaranteed; may vary with shape and size (supplier statement)"


# -------------------------------------------------------------------------------------------- candidate matrix
def permanent_magnet_candidates():
    rc = "arnold_recoma_combined"
    ht = "arnold_recoma_ht"
    cat = "arnold_neo_catalog"
    return [
        {
            "id": "MCQ-PM-01", "kind": "permanent_magnet", "family": "Sm2Co17 (sintered)",
            "product": "Arnold Recoma 33E", "supplier": "Arnold Magnetic Technologies",
            "possible_roles": ["hall_circuit_permanent_magnet (option)", "ecr_magnet (HW-ECR, permanent-magnet option)"],
            "values": {
                "Br_nominal_20C": val(1.16, "T", "Br nominal 1.16 Tesla (min. 1.14)", rc, "p. 17 (Recoma 33E sheet)",
                                      5, "measured", TYP, "Recoma 33E, 20 C", NOT_VALIDATED),
                "Br_min_20C": val(1.14, "T", "Br min. 1.14 Tesla", rc, "p. 17", 5, "measured", TYP,
                                  "Recoma 33E, 20 C", NOT_VALIDATED),
                "HcJ_min_20C": val(1750.0, "kA/m", "HcJ min. 1,750 kA/m (22,000 Oe)", rc, "p. 17", 5, "measured",
                                   TYP, "Recoma 33E, 20 C", NOT_VALIDATED),
                "HcB_min_20C": val(845.0, "kA/m", "HcB min. 845 kA/m", rc, "p. 17", 5, "measured", TYP,
                                   "Recoma 33E, 20 C", NOT_VALIDATED),
                "alpha_Br": val(-0.035, "%/degC", "alpha(Br) -0.035 %/C", rc, "p. 17, note (1)", 5, "measured", TYP,
                                "coefficients measured between 20 and 200 C (note 1)", NOT_VALIDATED),
                "alpha_HcJ": val(-0.25, "%/degC", "alpha(Hcj) -0.25 %/C", rc, "p. 17, note (1)", 5, "measured", TYP,
                                 "coefficients measured between 20 and 200 C (note 1)", NOT_VALIDATED),
                "coeff_range_C": val([20.0, 200.0], "degC", "(1) Coefficients measured between 20 and 200 C", rc,
                                     "p. 17, note (1)", 5, "measured", TYP, "Recoma 33E", NOT_VALIDATED),
                "max_recommended_use_T": val(350.0, "degC", "Max. Recommended Use Temperature 350 C", rc,
                                             "p. 17; also p. 2 summary table 'Maximum Operating Temperature' 350", 5,
                                             "assumed",
                                             "manufacturer recommendation; p. 2 footnote (3): 'In the presence of "
                                             "strong demagnetizing fields or if the magnets operate on a low "
                                             "loadline, the maximum temperature may be considerably lower'",
                                             "load line not stated", NOT_VALIDATED),
                "curie_T": val(825.0, "degC", "Curie Temperature, Tc 825 C", rc, "p. 17", 5, "measured", TYP,
                               "Recoma 33E", NOT_VALIDATED),
            },
            "demagnetization_curves": {
                "published": "graphical, intrinsic and normal curves at 20, 100, 150, 200, 250, 300 and 350 C with "
                             "permeance-coefficient scale (p. 17); curves show nominal Br and Hcj",
                "digitized": False,
                "knee_field_vs_T": tbd("digitization of the p. 17 curves at the H-1 magnet temperature, or the supplier's "
                                       "tabulated knee field H_K at >= the magnet temperature (lane 15 "
                                       "irreversible_loss_criterion)"),
            },
            "vacuum_outgassing": "Sintered metal; no ASTM E595 value accessed. Arnold RECOMA HT note p. 1: 'Coated "
                                 "Sm2Co17-type magnets are the preferred choice for space applications or in "
                                 "in-vacuum applications' (manufacturer statement, level 5). Coating type and its "
                                 "E595 data: TBD - requires the supplier coating datasheet.",
            "oxidation_AO": "RECOMA HT note p. 7: additional protection (encapsulation or coating) is necessary above "
                            "400 C in oxidizing atmosphere. No N/O-plume or atomic-oxygen data accessed (AOL-M06).",
            "qualification_tests": ["MCQ-QT-02", "MCQ-QT-03", "MCQ-QT-04", "MCQ-QT-07", "MCQ-QT-09"],
            "status": "CANDIDATE",
            "lifetime_verdict": None,
        },
        {
            "id": "MCQ-PM-02", "kind": "permanent_magnet", "family": "Sm2Co17 (sintered)",
            "product": "Arnold Recoma 35E", "supplier": "Arnold Magnetic Technologies",
            "possible_roles": ["hall_circuit_permanent_magnet (option)", "ecr_magnet (HW-ECR, permanent-magnet option)"],
            "values": {
                "max_operating_T_summary_table": val(
                    300.0, "degC", "Recoma 35E ... Maximum Operating Temperature 300 C", rc, "p. 2 summary table", 5,
                    "assumed", "manufacturer recommendation; footnote (3) as for MCQ-PM-01",
                    "load line not stated", NOT_VALIDATED),
                "grade_record": val("pm_sm2co17_recoma35e", "-", "lane 15 record (Br, HcJ, alpha, 300 C max use)",
                                    "repo:schemas/thermal_life/limits_v1.json", "records.pm_sm2co17_recoma35e", 5,
                                    "measured", "as in the lane 15 record", "as in the lane 15 record",
                                    "the p. 2 summary table value (300 C) agrees with the lane 15 datasheet record"),
            },
            "demagnetization_curves": {"published": "graphical (p. 18)", "digitized": False,
                                       "knee_field_vs_T": tbd("digitization or supplier knee-field table")},
            "vacuum_outgassing": "as MCQ-PM-01",
            "oxidation_AO": "as MCQ-PM-01",
            "qualification_tests": ["MCQ-QT-02", "MCQ-QT-03", "MCQ-QT-04", "MCQ-QT-07", "MCQ-QT-09"],
            "status": "CANDIDATE",
            "lifetime_verdict": None,
        },
        {
            "id": "MCQ-PM-03", "kind": "permanent_magnet", "family": "Sm2Co17 high-temperature (sintered, "
                                                                     "isostatically pressed)",
            "product": "Arnold Recoma HT360 / HT420 / HT470 / HT520", "supplier": "Arnold Magnetic Technologies",
            "possible_roles": ["hall_circuit_permanent_magnet (option)", "ecr_magnet (HW-ECR, option if the ECR "
                               "magnet runs hot)"],
            "values": {
                "grades_table": val(
                    [
                        {"grade": "Recoma 28HE", "Br_typ_T": 1.10, "Br_min_T": 1.06, "HcJ_typ_kA_m": ">2000",
                         "HcJ_min_kA_m": 1500, "max_operating_T_C": 290},
                        {"grade": "Recoma HT360", "Br_typ_T": 1.06, "Br_min_T": 1.01, "HcJ_typ_kA_m": 1900,
                         "HcJ_min_kA_m": 1600, "max_operating_T_C": 360},
                        {"grade": "Recoma HT420", "Br_typ_T": 1.02, "Br_min_T": 0.98, "HcJ_typ_kA_m": 1900,
                         "HcJ_min_kA_m": 1600, "max_operating_T_C": 420},
                        {"grade": "Recoma HT470", "Br_typ_T": 0.97, "Br_min_T": 0.92, "HcJ_typ_kA_m": 1900,
                         "HcJ_min_kA_m": 1600, "max_operating_T_C": 470},
                        {"grade": "Recoma HT520", "Br_typ_T": 0.94, "Br_min_T": 0.89, "HcJ_typ_kA_m": 1800,
                         "HcJ_min_kA_m": 1600, "max_operating_T_C": 520},
                    ],
                    "-", "table 'Typical room temperature values for isostatically pressed Recoma HT magnets'; "
                         "Max. Operating Temp. [C] (1); (1) Operating at a very low load line",
                    ht, "p. 4", 5, "measured",
                    "room-temperature typical/min values; the maximum operating temperature is 'operating at a very "
                    "low load line' (footnote 1), i.e. it is NOT a limit at an arbitrary permeance coefficient",
                    "isostatically pressed Recoma HT grades", NOT_VALIDATED),
                "rtc_HcJ_HT520": val(-0.14, "%/K", "Recoma HT520 shows only 0.14%/K (RTC(HcJ), 20 to 300 C, "
                                                   "compared with about 0.26%/K for Recoma 28HE)",
                                     ht, "p. 3", 5, "measured", "stated as a magnitude ('only 0.14%/K'); sign "
                                     "(decrease with temperature) from the surrounding text",
                                     "20-300 C (stated for 28HE; the HT520 range is read from the same sentence: "
                                     "verify)", NOT_VALIDATED),
                "batch_qualification_practice": val(
                    "each material batch qualified by measuring irreversible losses at the nominal operating "
                    "temperature", "-", "Each material batch is qualified by measuring the irreversible losses at "
                    "the nominal operating temperature.", ht, "p. 8 'Qualification'", 5, "assumed",
                    "manufacturer practice statement; test method and acceptance limit not published",
                    "Recoma HT grades", NOT_VALIDATED),
                "applications_listed": val("Ion thrusters (among permanent magnet drives, sensors, travelling wave "
                                           "tubes)", "-", "Applications ... Ion thrusters", ht, "p. 7", 5, "assumed",
                                           "manufacturer marketing list; no specific thruster or duty cited",
                                           "not Hall-thruster specific", "not evidence of Hall-thruster qualification"),
            },
            "demagnetization_curves": {"published": "graphical demagnetization curves (pp. 5-6), temperatures not "
                                                     "extracted from the text layer", "digitized": False,
                                       "knee_field_vs_T": tbd("supplier curves at the H-1 magnet temperature; "
                                                              "batch-specific data if the grade is selected")},
            "vacuum_outgassing": "p. 1: coated Sm2Co17 preferred for space / in-vacuum use (manufacturer statement). "
                                 "Coating E595 data TBD.",
            "oxidation_AO": "p. 7: protection needed above 400 C in oxidizing atmosphere; Fig. 4 shows moment loss of "
                            "HT520 cylinders after air exposure at 500 C (graphical, not digitized).",
            "qualification_tests": ["MCQ-QT-02", "MCQ-QT-03", "MCQ-QT-04", "MCQ-QT-07", "MCQ-QT-09"],
            "status": "CANDIDATE",
            "lifetime_verdict": None,
        },
        {
            "id": "MCQ-PM-04", "kind": "permanent_magnet", "family": "Sm2Co17 ultra-high-temperature",
            "product": "Electron Energy Corporation UHT SmCo", "supplier": "Electron Energy Corporation",
            "possible_roles": ["hall_circuit_permanent_magnet (option)", "ecr_magnet (option)"],
            "values": {
                "use_temperature_up_to": val(550.0, "degC", "a new class of Sm2Co17 magnets ... for use at "
                                             "temperatures up to 550 C", "eec_uht_smco_page", "page body", 5,
                                             "assumed", "manufacturer marketing statement; no grade, load line or "
                                             "demagnetization curve given", "UHT SmCo class", NOT_VALIDATED),
                "heritage_claim": val("used in the Deep Space 1 ion propulsion engines (Hughes Electron Dynamics)",
                                      "-", "When NASA launched Deep Space 1 ... EEC's UHT SmCo magnets were used ... "
                                      "ion propulsion engines", "eec_uht_smco_page", "page body", 5, "assumed",
                                      "manufacturer claim, not independently verified here (verify)",
                                      "gridded ion engine, not a Hall thruster", "not verified"),
            },
            "demagnetization_curves": {"published": "not accessed", "digitized": False,
                                       "knee_field_vs_T": tbd("an EEC UHT grade datasheet with demagnetization curves "
                                                              "(not accessed)")},
            "vacuum_outgassing": "TBD - requires supplier coating/E595 data",
            "oxidation_AO": "TBD",
            "qualification_tests": ["MCQ-QT-02", "MCQ-QT-03", "MCQ-QT-04", "MCQ-QT-07", "MCQ-QT-09"],
            "status": "CANDIDATE_INCOMPLETE_DATA",
            "lifetime_verdict": None,
        },
        {
            "id": "MCQ-PM-05", "kind": "permanent_magnet", "family": "NdFeB (sintered), SH grade",
            "product": "Arnold N42SH", "supplier": "Arnold Magnetic Technologies",
            "possible_roles": ["ecr_magnet (HW-ECR, only if the magnet stays cool)", "hall_circuit_permanent_magnet "
                               "(only if the circuit stays cool)"],
            "values": {
                "grade_record": val("pm_ndfeb_n42sh_arnold", "-", "lane 15 record (Br 1.31 T, HcJ min 1592 kA/m, "
                                    "alpha(Br) -0.12, alpha(HcJ) -0.55 %/C, 20-150 C)",
                                    "repo:schemas/thermal_life/limits_v1.json", "records.pm_ndfeb_n42sh_arnold", 5,
                                    "measured", "as in the lane 15 record", "as in the lane 15 record",
                                    "re-accessed datasheet identical (sha256 recorded)"),
                "Tw_max_catalog": val(150.0, "degC", "N42SH ... Tw max 150 (column 'Tw max', unit C)", cat,
                                      "p. 1, 'Basic Grades' table", 5, "assumed",
                                      "the catalog does not define 'Tw' in the accessed text; reading it as the "
                                      "maximum working temperature is an inference (verify); load line not stated",
                                      "N42SH; Arnold catalog Rev. 181031", NOT_VALIDATED),
                "alpha_HcJ_catalog": val(-0.549, "%/degC", "alpha(HcJ) -0.549", cat, "p. 1", 5, "measured", TYP,
                                         "coefficient range not stated in the catalog; the datasheet states 20-150 C",
                                         "catalog -0.549 vs datasheet -0.55: consistent to rounding"),
            },
            "demagnetization_curves": {"published": "graphical on the datasheet (lane 15 source)", "digitized": False,
                                       "knee_field_vs_T": tbd("digitization or supplier knee table at >= magnet T")},
            "vacuum_outgassing": "Datasheet: 'contact Arnold ... for recommendations for protective coating'. Coating "
                                 "and its E595 data: TBD.",
            "oxidation_AO": "No N/O-plume data accessed (AOL-M06); coating mandatory by proposal MCQ-W3-04.",
            "qualification_tests": ["MCQ-QT-02", "MCQ-QT-03", "MCQ-QT-04", "MCQ-QT-07", "MCQ-QT-09"],
            "status": "CANDIDATE",
            "lifetime_verdict": None,
        },
        {
            "id": "MCQ-PM-06", "kind": "permanent_magnet", "family": "NdFeB (sintered), EH grade",
            "product": "Arnold N35EH", "supplier": "Arnold Magnetic Technologies",
            "possible_roles": ["ecr_magnet (HW-ECR)", "hall_circuit_permanent_magnet (option)"],
            "values": {
                "Br_nominal_20C": val(1.20, "T", "Br nominal 1200 mT (min. 1170, max. 1230)", "arnold_n35eh",
                                      "magnetic-properties table", 5, "measured", TYP, "N35EH, 20 C", NOT_VALIDATED),
                "HcJ_min_20C": val(2388.0, "kA/m", "HcJ min. 2,388 kA/m (30,000 Oe)", "arnold_n35eh",
                                   "magnetic-properties table", 5, "measured", TYP, "N35EH, 20 C", NOT_VALIDATED),
                "alpha_Br": val(-0.12, "%/degC", "alpha(Br) -0.12 %/C", "arnold_n35eh", "thermal properties, note (1)",
                                5, "measured", TYP, "coefficients measured between 20 and 200 C (note 1)",
                                NOT_VALIDATED),
                "alpha_HcJ": val(-0.47, "%/degC", "alpha(Hcj) -0.47 %/C", "arnold_n35eh",
                                 "thermal properties, note (1)", 5, "measured", TYP,
                                 "coefficients measured between 20 and 200 C (note 1)", NOT_VALIDATED),
                "coeff_range_C": val([20.0, 200.0], "degC", "(1) Coefficients measured between 20 and 200 C",
                                     "arnold_n35eh", "note (1)", 5, "measured", TYP, "N35EH", NOT_VALIDATED),
                "curie_T": val(310.0, "degC", "Curie Temperature, Tc 310 C", "arnold_n35eh", "thermal properties", 5,
                               "measured", TYP, "N35EH", NOT_VALIDATED),
                "Tw_max_catalog": val(200.0, "degC", "N35EH ... Tw max 200", cat, "p. 2", 5, "assumed",
                                      "'Tw' undefined in the accessed catalog text (inference: maximum working "
                                      "temperature, verify); load line not stated", "N35EH", NOT_VALIDATED),
            },
            "demagnetization_curves": {"published": "graphical, -40, 20, 60, 80, 100, 120, 150, 180, 200, 220 C with "
                                                    "Pc = B/H lines 0.5-5; curves show nominal Br and MINIMUM Hcj",
                                       "digitized": False,
                                       "knee_field_vs_T": tbd("digitization of the N35EH curve at >= magnet T")},
            "vacuum_outgassing": "Datasheet: 'recommendations for protective coating' from the supplier. Coating E595 "
                                 "data TBD.",
            "oxidation_AO": "as MCQ-PM-05",
            "qualification_tests": ["MCQ-QT-02", "MCQ-QT-03", "MCQ-QT-04", "MCQ-QT-07", "MCQ-QT-09"],
            "status": "CANDIDATE",
            "lifetime_verdict": None,
        },
        {
            "id": "MCQ-PM-07", "kind": "permanent_magnet", "family": "NdFeB (sintered), AH grade",
            "product": "Arnold N38AH", "supplier": "Arnold Magnetic Technologies",
            "possible_roles": ["ecr_magnet (HW-ECR)", "hall_circuit_permanent_magnet (option)"],
            "values": {
                "Br_typ_20C": val(1.240, "T", "N38AH Br typical 1240 mT", cat, "p. 2", 5, "measured", TYP,
                                  "N38AH, 20 C", NOT_VALIDATED),
                "HcJ_min_20C": val(2626.0, "kA/m", "HcJ min 2626 kA/m (33000 Oe)", cat, "p. 2", 5, "measured", TYP,
                                   "N38AH, 20 C", NOT_VALIDATED),
                "alpha_Br": val(-0.12, "%/degC", "alpha(Br) -0.12", cat, "p. 2", 5, "measured", TYP,
                                "coefficient range not stated in the catalog", NOT_VALIDATED),
                "alpha_HcJ": val(-0.393, "%/degC", "alpha(HcJ) -0.393", cat, "p. 2", 5, "measured", TYP,
                                 "coefficient range not stated in the catalog", NOT_VALIDATED),
                "Tw_max_catalog": val(220.0, "degC", "N38AH ... Tw max 220", cat, "p. 2", 5, "assumed",
                                      "'Tw' undefined in the accessed catalog text (verify); load line not stated",
                                      "N38AH", NOT_VALIDATED),
            },
            "demagnetization_curves": {"published": "not accessed (grade datasheet not retrieved)", "digitized": False,
                                       "knee_field_vs_T": tbd("the N38AH grade datasheet with demagnetization "
                                                              "curves")},
            "vacuum_outgassing": "coating required (supplier recommendation route as MCQ-PM-06); E595 TBD",
            "oxidation_AO": "as MCQ-PM-05",
            "qualification_tests": ["MCQ-QT-02", "MCQ-QT-03", "MCQ-QT-04", "MCQ-QT-07", "MCQ-QT-09"],
            "status": "CANDIDATE_INCOMPLETE_DATA",
            "lifetime_verdict": None,
        },
    ]


def electromagnet_candidates():
    cw = "ceramawire_ht"
    return [
        {
            "id": "MCQ-EM-01", "kind": "magnet_wire", "conductor": "copper (solid, bare)",
            "insulation": "aromatic polyimide enamel, heavy build (NEMA MW 16-C)",
            "product": "Remington Industries MW 16-C polyimide magnet wire (e.g. 16H240)",
            "supplier": "Remington Industries (distributor)",
            "possible_roles": ["hall_magnet coil winding", "ecr_magnet coil winding (electromagnet option)"],
            "values": {
                "thermal_class": val(240.0, "degC", "Thermal Classification: Class 240 C (ASTM D 2307)",
                                     "remington_mw16c", "datasheet, specification list", 5, "assumed",
                                     "a magnet-wire (material) thermal class from ASTM D2307 thermal endurance; it is "
                                     "NOT an electrical-insulation-SYSTEM class (IEC 60085 clause 4-5: an EIM class "
                                     "does not imply the EIS class, lane 15 record iec60085_thermal_classes)",
                                     "enamelled round copper wire, air ageing per the test standard; vacuum, "
                                     "radiation, thermal cycling not covered", NOT_VALIDATED),
                "nema_class_cross_reference": val(240.0, "degC", "Polyimide MW 16-C thermal class 240; IEC 60317-46",
                                                  "nema_mw1000_annex_c", "p. 1", 5, "assumed",
                                                  "standard designation (informative annex)", "round wire",
                                                  "normative designation, not a test result"),
                "cut_through": val(">=500", "degC", "Thermoplastic Flow (Cut-Through): 500 C+", "remington_mw16c",
                                   "datasheet", 5, "measured", "supplier value; method not stated",
                                   "MW 16-C", NOT_VALIDATED),
                "heat_shock": val(300.0, "deg (unit not printed; C inferred from the sheet's C ratings: verify)",
                                  "Heat Shock: Passes 300 heat shock", "remington_mw16c", "datasheet",
                                  5, "measured", "pass/fail statement; method and unit not stated", "MW 16-C", NOT_VALIDATED),
                "outgassing_E595": tbd("an ASTM E595 (TML, CVCM) record for the actual polyimide enamel (NASA "
                                       "outgassing database or supplier test) - none retrieved"),
                "thermal_endurance_life_basis": tbd("the ASTM D2307 / IEC 60172 thermal-endurance curve (TI, HIC) of "
                                                    "the actual enamel lot and an EIS evaluation of the complete coil "
                                                    "(MCQ-QT-01)"),
            },
            "hot_spot_note": "Class 240 C applies to the hottest winding point (hot spot), not the average from the "
                             "resistance method; the offset is measured, not assumed (MCQ-W4-01).",
            "qualification_tests": ["MCQ-QT-01", "MCQ-QT-03", "MCQ-QT-05", "MCQ-QT-06", "MCQ-QT-08", "MCQ-QT-04"],
            "status": "CANDIDATE",
            "lifetime_verdict": None,
        },
        {
            "id": "MCQ-EM-02", "kind": "magnet_wire", "conductor": "copper",
            "insulation": "glass fiber / silicone varnish (NEMA MW 44-C)",
            "product": "generic MW 44-C (no supplier datasheet accessed)", "supplier": "TBD",
            "possible_roles": ["hall_magnet coil winding"],
            "values": {
                "nema_class_cross_reference": val(200.0, "degC", "Glass fiber/silicone varnish MW 44-C 200; IEC "
                                                  "60317-50 (IEC thermal class differs: '**')",
                                                  "nema_mw1000_annex_c", "p. 2", 5, "assumed",
                                                  "standard designation; the '**' marker means the IEC class differs "
                                                  "(footnote text not transcribed here: verify)", "round wire",
                                                  "normative designation"),
                "outgassing_E595": tbd("E595 data of the silicone varnish (silicones are a known contamination "
                                       "concern in vacuum: verify with a sourced statement before use)"),
            },
            "hot_spot_note": "as MCQ-EM-01",
            "qualification_tests": ["MCQ-QT-01", "MCQ-QT-03", "MCQ-QT-05", "MCQ-QT-06", "MCQ-QT-08"],
            "status": "CANDIDATE_INCOMPLETE_DATA",
            "lifetime_verdict": None,
        },
        {
            "id": "MCQ-EM-03", "kind": "magnet_wire", "conductor": "27 % nickel-clad copper (Kulgrid 28)",
            "insulation": "vitreous (ceramic) enamel film, fully cured at 1400-1500 F (proprietary formulation)",
            "product": "Ceramawire HT Wire, Kulgrid conductor", "supplier": "Ceramawire",
            "possible_roles": ["hall_magnet coil winding (high-temperature option)", "ecr_magnet coil winding"],
            "values": {
                "continuous_T_range_F": val([-450.0, 1000.0], "degF", "-450 F to +1000 F continuous operation; up to "
                                            "1500 F for short periods of time", cw, "p. 1", 5, "assumed",
                                            "manufacturer rating; basis not published", "HT Wire (both conductors)",
                                            NOT_VALIDATED),
                "short_term_T_F": val(1500.0, "degF", "up to 1500 F for short periods of time", cw, "p. 1", 5,
                                      "assumed", "'short periods' not quantified", "HT Wire", NOT_VALIDATED),
                "dielectric_rating_small": val(150.0, "V DC", "150 volts D.C. for wire diameters up to .008\" (#32)",
                                               cw, "p. 2", 5, "measured", "method not stated",
                                               "wire diameter <= 0.008 in", NOT_VALIDATED),
                "dielectric_rating_large": val(200.0, "V DC", "200 volts D.C. for larger diameter wires", cw, "p. 2",
                                               5, "measured", "method not stated", "wire diameter > 0.008 in",
                                               NOT_VALIDATED),
                "resistance_500F": val(26.9, "ohm/circ-mil-ft", "Electrical resistance of Kulgrid HT Wire is 26.9 "
                                       "ohms/circ mil ft at 500 F", cw, "p. 2", 5, "measured", "method not stated",
                                       "Kulgrid HT Wire", NOT_VALIDATED),
                "resistance_1000F": val(42.3, "ohm/circ-mil-ft", "and 42.3 ohms at 1000 F", cw, "p. 2", 5, "measured",
                                        "method not stated", "Kulgrid HT Wire", NOT_VALIDATED),
                "porosity_bakeout": val("coating is porous and absorbs moisture; bake out at 125 C for 12 hours on a "
                                        "metal spool", "-", "Coating is porous and will absorb moisture ... Wire can "
                                        "be baked out at 125 C for 12 hours on a metal spool.", cw, "p. 2", 5,
                                        "assumed", "handling instruction", "HT Wire", NOT_VALIDATED),
                "nickel_migration": val("Kulgrid subject to nickel migration above 600 F; noticeable on wire "
                                        "diameters below 0.006 in (#34) after prolonged use", "-",
                                        "Kulgrid HT Wire is subject to nickel migration at temperatures above 600 F",
                                        cw, "p. 3", 5, "assumed", "qualitative", "Kulgrid HT Wire", NOT_VALIDATED),
                "service_life_statement": val("> 2500 h at 1000 F and above; increases significantly at lower "
                                              "temperature", "-", "life expectancy greater than 2500 hours at "
                                              "1000 F and above. Service life significantly increases with a decrease "
                                              "in operating temperature.", cw, "p. 3", 5, "assumed",
                                              "manufacturer statement; end-point criterion and test not published; "
                                              "NOT a life basis for 15,000 h (reference only)", "HT Wire",
                                              "no lifetime verdict may be drawn"),
                "flexibility": val("7X mandrel warranted (5X typical)", "-", "Coating is warranted to not crack when "
                                   "wound on a form 7X diameter of wire", cw, "p. 1", 5, "assumed",
                                   "supplier warranty statement", "HT Wire", NOT_VALIDATED),
                "outgassing_E595": tbd("E595 test of the vitreous enamel after the supplier bake-out (inorganic film, "
                                       "but moisture uptake is stated; MCQ-QT-03)"),
            },
            "hot_spot_note": "The coating is thin ('.0003\" - .0006\" (increase in diameter), depending on size', p. 1); turn-to-turn voltage "
                             "must stay below the 150/200 V DC dielectric rating with margin (MCQ-W3-06).",
            "qualification_tests": ["MCQ-QT-01", "MCQ-QT-03", "MCQ-QT-05", "MCQ-QT-06", "MCQ-QT-08"],
            "status": "CANDIDATE",
            "lifetime_verdict": None,
        },
        {
            "id": "MCQ-EM-04", "kind": "magnet_wire", "conductor": "all nickel (Nickel 205)",
            "insulation": "vitreous (ceramic) enamel film (Ceramawire HT)",
            "product": "Ceramawire HT Wire, All Nickel conductor", "supplier": "Ceramawire",
            "possible_roles": ["hall_magnet coil (only if the Kulgrid limit is exceeded; high resistance)"],
            "values": {
                "conductor_specific_limit": tbd("a conductor-specific temperature limit for All Nickel (the accessed specification gives one continuous range for HT Wire; a per-conductor limit seen in a web-search snippet was NOT in the accessed document and is not used)"),
                "resistance_500F": val(138.0, "ohm/circ-mil-ft", "All Nickel HT Wire has an electrical resistance of "
                                       "138 ohms/circ mil ft at 500 F", cw, "p. 2", 5, "measured",
                                       "method not stated", "All Nickel HT Wire", NOT_VALIDATED),
                "resistance_1000F": val(228.0, "ohm/circ-mil-ft", "and 228 ohms at 1000 F", cw, "p. 2", 5, "measured",
                                        "method not stated", "All Nickel HT Wire", NOT_VALIDATED),
                "nickel_migration": val("unaffected", "-", "All Nickel HT Wire is unaffected by migration.", cw,
                                        "p. 3", 5, "assumed", "qualitative", "All Nickel HT Wire", NOT_VALIDATED),
            },
            "hot_spot_note": "Nickel is ferromagnetic (general physics: verify its effect on B(z) with the MC-1 "
                             "magnetostatic model before selection); resistance ratio vs Kulgrid in derived D-02.",
            "qualification_tests": ["MCQ-QT-01", "MCQ-QT-03", "MCQ-QT-05", "MCQ-QT-06", "MCQ-QT-08", "MCQ-QT-07"],
            "status": "CANDIDATE",
            "lifetime_verdict": None,
        },
        {
            "id": "MCQ-EM-05", "kind": "coil_construction_concept", "conductor": "anodized aluminium wire",
            "insulation": "anodic alumina + electrically insulative high-CTE ceramic body (potting)",
            "product": "concept per US 9,508,486 B2 (no product datasheet)", "supplier": "TBD",
            "possible_roles": ["hall_magnet coil (concept only)"],
            "values": {
                "construction": val("coiled anodized aluminum wire embedded in an electrically-insulative ceramic "
                                    "body whose CTE is > 10 ppm/C and < the CTE of the coiled wire", "-",
                                    "the high temperature electromagnetic coil assembly includes a coiled anodized "
                                    "aluminum wire and an electrically-insulative, high thermal expansion ceramic "
                                    "body ... coefficient of thermal expansion greater than 10 parts per million per "
                                    "degree Celsius and less than the coefficient of thermal expansion of the coiled "
                                    "anodized aluminum wire", "honeywell_us9508486", "front page, (57) Abstract", 6,
                                    "assumed", "patent claim language; not a qualified product",
                                    "patent embodiment", "no test data read"),
                "temperature_rating": tbd("a supplier datasheet or a published test for anodized-Al coils (the patent "
                                          "description was not read; no value is taken from a search snippet)"),
            },
            "hot_spot_note": "Aluminium conductivity lower than copper (general knowledge, verify with a sourced "
                             "resistivity before any sizing).",
            "qualification_tests": ["MCQ-QT-01", "MCQ-QT-03", "MCQ-QT-05", "MCQ-QT-06", "MCQ-QT-08"],
            "status": "NOT_SOURCED_FOR_SELECTION",
            "lifetime_verdict": None,
        },
        {
            "id": "MCQ-EM-06", "kind": "magnet_wire", "conductor": "copper or nickel in a metal sheath",
            "insulation": "mineral insulation (compacted MgO), MI conductor",
            "product": "none accessed", "supplier": "TBD",
            "possible_roles": ["hall_magnet coil (option named in the lane brief)"],
            "values": {
                "all": tbd("a supplier datasheet for an MI conductor suitable for coil winding (bend radius, "
                           "temperature rating, fill factor, vacuum bake/outgassing, moisture sealing of ends); the one "
                           "open paper found returned HTTP 403"),
            },
            "hot_spot_note": "not assessed",
            "qualification_tests": ["MCQ-QT-01", "MCQ-QT-03", "MCQ-QT-05", "MCQ-QT-06", "MCQ-QT-08"],
            "status": "NOT_SOURCED_FOR_SELECTION",
            "lifetime_verdict": None,
        },
        {
            "id": "MCQ-EIS-01", "kind": "winding_potting_practice", "conductor": "(any of MCQ-EM-01..06)",
            "insulation": "ceramic potting between windings",
            "product": "NASA HERMeS coil practice (compound not named in the source)", "supplier": "TBD",
            "possible_roles": ["hall_magnet coil assembly"],
            "values": {
                "practice": val("coils potted with a ceramic material during winding to raise winding-to-winding "
                                "conductance and reduce hot spots; potting cracks from startup gradients and the "
                                "ceramic/copper CTE mismatch", "-", "During the winding process the coils were potted "
                                "with a ceramic material to increase thermal conductance between the windings and "
                                "thereby reduce thermal gradients (hot spots) within the coils ... the ceramic potting "
                                "compound suffers from cracks due to the large startup gradients ... and the large "
                                "difference in CTE", "nasa_myers_2016_hermes", "p. 5", 5, "assumed",
                                "design-practice statement for a 12.5 kW xenon thruster; compound and crack extent "
                                "not given", "HERMeS development thruster",
                                "not transferable as a value; motivates MCQ-QT-05"),
                "coil_is_limiting_component": val("the inner electromagnet coil is the component with the lowest "
                                                  "maximum temperature limit (electrical insulation)", "-",
                                                  "the electrical insulation on the coil windings has the lowest "
                                                  "material temperature limit", "nasa_myers_2016_hermes",
                                                  "p. 5; p. 14", 5, "assumed", "qualitative statement",
                                                  "HERMeS", "context only"),
            },
            "hot_spot_note": "Potting changes the hot-spot/average offset; it must be measured on the built coil.",
            "qualification_tests": ["MCQ-QT-01", "MCQ-QT-03", "MCQ-QT-05", "MCQ-QT-06"],
            "status": "CANDIDATE_INCOMPLETE_DATA",
            "lifetime_verdict": None,
        },
    ]


# ------------------------------------------------------------------------------------ reference-only evidence
REFERENCE_ONLY = [
    {"id": "MCQ-REF-01", "source_ids": ["repo:schemas/thermal_life/limits_v1.json"], "what": "NASA EEE-INST-002 Section M1 Table 4 magnetics derating (class C '-20 C', custom "
     "0.75 factor, +10 C hot-spot convention, MIL-PRF-27 resistance-rise formula)",
     "where": "repo:schemas/thermal_life/limits_v1.json records.eee_inst_002_magnetics, "
              "relations.winding_temperature_rise_mil_prf_27",
     "may_be_used_for": "a derating policy option (owner decision) and the resistance-rise arithmetic",
     "never_produces_lifetime_verdict": True,
     "reason": "MIL-style EEE parts guidance; a Hall coil is a custom device; its 50,000 h basis is inferred, not "
               "stated, for custom devices (lane 15 repair 2026-09-27)"},
    {"id": "MCQ-REF-02", "source_ids": ["mmpa_0100_00", "repo:schemas/thermal_life/limits_v1.json"], "what": "MMPA 0100-00 Table IV-4 family values (1-5, 2-17, NdFeB max. service temperature, "
     "reversible coefficients)", "where": "repo:schemas/thermal_life/limits_v1.json records.pm_*_mmpa",
     "may_be_used_for": "family-level context and cross-checks only",
     "never_produces_lifetime_verdict": True,
     "reason": "alloy-family typical values, not a grade; Tmax is defined (p. 27) as the maximum temperature 'with no "
               "significant long range instability or structural changes', without a load line or a time basis"},
    {"id": "MCQ-REF-03", "source_ids": ["repo:schemas/thermal_life/limits_v1.json", "iec60216_1_2013_preview"], "what": "IEC 60085 thermal classes", "where": "repo:schemas/thermal_life/limits_v1.json "
     "records.iec60085_thermal_classes", "may_be_used_for": "designating an EIS class once the EIS is evaluated",
     "never_produces_lifetime_verdict": True,
     "reason": "a class is a recommended maximum continuous use temperature with no life basis (3.11 NOTE 1)"},
    {"id": "MCQ-REF-04", "source_ids": ["psma_eaton_2023", "ul_1446_workshop"], "what": "UL 1446 letter classes (E 120, B 130, F 155, H 180, N 200, R 220, S 240, C over 240)",
     "where": "psma_eaton_2023 slide 10", "may_be_used_for": "reading supplier EIS recognitions",
     "never_produces_lifetime_verdict": True,
     "reason": "secondary source (slides); UL 1446 itself not accessed; a UL recognition is a terrestrial safety "
               "rating of a specific material combination, not a vacuum/thruster life basis"},
    {"id": "MCQ-REF-05", "source_ids": ["nasa_kamhawi_2013_300ms"], "what": "Published large-Hall-thruster coil temperatures (NASA-300M / 300MS, 10-20 kW, "
     "xenon; derived D-05)", "where": "nasa_kamhawi_2013_300ms p. 21 Table 4",
     "may_be_used_for": "showing that coil temperatures in Hall thrusters can exceed polymer magnet-wire classes; "
                        "motivating a measured H-1 coil temperature",
     "never_produces_lifetime_verdict": True,
     "reason": "different power class (10-20 kW vs < 1.5 kW), different geometry, magnetic shielding; application to "
               "H-1 is extrapolation (level 6)"},
]


# ----------------------------------------------------------------------------------- H-1 requirement basis
def h1_basis():
    return {
        "B_magnitude_class": {
            "statement": "No Vyovrinda B_max exists (lane 17: B_max_T and magnet_setting_schedule TBD - requires the "
                         "Vyovrinda magnetic-circuit computation or measurement). The magnitude class used for "
                         "screening magnet and coil options is the published order of magnitude only.",
            "evidence": [
                val(0.015, "T", "typical radial magnetic field strength of 150 G (textbook example)",
                    "repo:docs/architecture_comparison/hall_reference/HALL_ACCELERATOR_REFERENCE.md",
                    "EV-B2 (Goebel & Katz pp. 330-331, illustrative)", 5, "assumed",
                    "illustrative textbook value", "xenon Hall thrusters in general", "not an H-1 design value"),
                val(0.02, "T", "the xenon database operates at typically about 200 G",
                    "repo:docs/architecture_comparison/hall_reference/HALL_ACCELERATOR_REFERENCE.md",
                    "EV-B4 (Dannenmayer & Mazouffre 2011 p. 242)", 5, "assumed", "'typically about'",
                    "xenon Hall thruster database", "not an H-1 design value"),
                val(0.08752, "T", "0.08752 T at 2.45 GHz (B = 2 pi f m_e / e)",
                    "repo:docs/architecture_comparison/electrical_closure/ELECTRICAL_CLOSURE.md",
                    "EM-RESONANCE-B", 4, "model-derived", "CODATA 2022 constants", "fundamental ECR at 2.45 GHz",
                    "physics; ECR frequency itself is an open design choice"),
            ],
            "forbidden_sources": "P5 B_ref_T / p5_vacuum_Br_centerline_*.csv / ECHT digitized field / 0-D "
                                 "HallChannel.B_max_T are never design values (lane 17 section 4); P5 calibration "
                                 "nuisance (registration, coil shape) is never a magnet variable",
            "consequence_for_candidates": "The ECR resonance field is ~4-6x the Hall-channel magnitude class "
                                          "(derived D-06), so an ECR magnet is the strongest local source near "
                                          "the Hall circuit; its fringe field in the channel is governed by lane 17 "
                                          "INV-B3 and its own demagnetization exposure by MCQ-QT-09.",
        },
        "operating_temperatures": {
            "hall_coil_hot_spot_C": tbd("the H-1 thruster thermal model (lane 15 hall_magnet inputs: coil_current_A, "
                                        "coil_resistance_ref_ohm and _T_C, external_heat_W, rejection_paths, "
                                        "copper_model) and then the S1 measurement (MCQ-W4-01)"),
            "hall_coil_average_C": tbd("same; measured by the resistance method in S1"),
            "hall_circuit_permanent_magnet_C": tbd("only if a permanent-magnet Hall circuit is chosen (owner "
                                                   "question MCQ-OQ-01); needs a magnet node that lane 15 does not "
                                                   "have yet (MCQ-L15-06)"),
            "ecr_magnet_C": tbd("ECR source design heat fraction to magnets (lane 15 ecr_magnet inputs: "
                                "heat_fraction_to_magnets, ecr_rf_power_W, rejection_paths) and the HW-ECR module "
                                "thermal design"),
            "pole_piece_C": tbd("H-1 thermal model; pole material grade is not selected in this lane (MCQ-OQ-05)"),
            "reference_context": "Published 10-20 kW xenon Hall-thruster inner-coil outer-layer thermocouples read "
                                 "374.8-535.6 C (derived D-05; REFERENCE ONLY, MCQ-REF-05). No temperature for a "
                                 "< 1.5 kW air-breathing H-1 is inferred from them.",
        },
        "ecr_hall_interaction": {
            "statements": [
                "INV-B1/B2 (lane 17): identical Hall-channel B(z) and magnet-setting schedule across arms.",
                "INV-B3 (lane 17) / INV-MAG and CONFOUNDED_MAGNETIC (lane 06): in ecr_hall the combined channel field, "
                "including any ecr_magnet fringe, must equal the reference B(z) within an owner tolerance "
                "(inv_mag_peak_tol, inv_mag_loc_tol: TBD).",
                "W3 draft HW-PIM-03 (non-ferromagnetic module structures) and HW-PIM-04 / HWQ-05 (ECR electromagnet vs "
                "permanent magnet; a permanent magnet makes M0b = M0c).",
                "Permanent ECR magnets sit in the Hall circuit's field and near its heat: their demagnetization "
                "exposure is the combined opposing field (own circuit + Hall circuit at the maximum coil current) at "
                "the magnet temperature (MCQ-QT-09).",
                "Nickel conductors (MCQ-EM-04) and any ferromagnetic fastener are field-shaping; excluded unless "
                "the magnetostatic model and an M0 vs M0b map show the effect (MCQ-W3-07).",
            ],
        },
    }


# ---------------------------------------------------------------------------------------- qualification tests
QUALIFICATION_TESTS = [
    {"id": "MCQ-QT-01", "source_ids": ["iec60216_1_2013_preview", "ul_1446_workshop", "remington_mw16c"], "name": "EIS thermal endurance (coil life basis)",
     "applies_to": ["MCQ-EM-01", "MCQ-EM-02", "MCQ-EM-03", "MCQ-EM-04", "MCQ-EM-05", "MCQ-EM-06", "MCQ-EIS-01"],
     "purpose": "give the winding insulation a STATED life basis at the H-1 hot-spot temperature (lane 15 "
                "insulation-life check stays NOT_DEMONSTRATED until this exists)",
     "method": "(a) material level: thermal-endurance data of the enamel/insulation per IEC 60216-1 (TI at 20 000 h "
               "or another specified time, and HIC; Arrhenius form, valid only without a first-order transition in the "
               "test range, IEC 60216-1:2013 pp. 6-8); (b) system level: evaluation of the complete EIS (wire + "
               "potting + ground insulation + leads) by a system method (UL 1446 or the IEC EIS series named in UL's "
               "flyer, IEC 61857: verify applicability), or (c) a coil life test on H-1-representative coils in "
               "vacuum at >= the measured hot-spot temperature with the pre-registered end-point",
     "end_point": "PROPOSED: insulation resistance and turn-to-turn / ground dielectric withstand at the H-1 "
                  "operating voltages (values TBD - requires the coil electrical design), plus resistance drift",
     "phase": "starts before S1 (material data); system/coil life test runs in parallel with S1 and completes before "
              "Milestone C",
     "owner_threshold": "PROPOSED: life basis >= RFP firing time (> 15,000 h) at hot-spot temperature plus a margin "
                        "(margin TBD - owner)"},
    {"id": "MCQ-QT-02", "source_ids": ["arnold_recoma_ht", "arnold_recoma_combined"], "name": "Permanent-magnet demagnetization exposure and irreversible-loss test",
     "applies_to": ["MCQ-PM-01", "MCQ-PM-02", "MCQ-PM-03", "MCQ-PM-04", "MCQ-PM-05", "MCQ-PM-06", "MCQ-PM-07"],
     "purpose": "demonstrate that the working point at the maximum magnet temperature stays on the linear part of the "
                "demagnetization curve (lane 15 irreversible_loss_criterion) at the actual permeance coefficient",
     "method": "magnetize the actual magnet (shape as built), measure moment/flux at 20 C, soak at T_max_design + "
               "margin in the actual circuit (or at the design permeance coefficient) for a pre-registered duration, "
               "return to 20 C, re-measure; per-batch, following the supplier's practice of measuring irreversible "
               "losses at the nominal operating temperature (Recoma HT note p. 8)",
     "end_point": "PROPOSED: irreversible loss <= TBD % (owner) and B(z) change within the INV-B tolerance",
     "phase": "before S1 for any permanent magnet installed on H-1 or PIM-ECR",
     "owner_threshold": "PROPOSED (not in the RFP)"},
    {"id": "MCQ-QT-03", "source_ids": ["nasa_scialdone_e595", "ceramawire_ht"], "name": "Vacuum bake-out and outgassing screen",
     "applies_to": ["all candidates", "coatings", "potting", "lead insulation"],
     "purpose": "avoid contamination and pressure spikes; remove absorbed moisture (ceramic enamel is porous, "
                "Ceramawire p. 2)",
     "method": "ASTM E595-type screen for every organic or porous element (125 C, 24 h, ~1e-6 torr, collector at 25 "
               "C, per Scialdone et al. p. 1) using supplier or database records where they exist; plus a vacuum "
               "bake of the complete coil/magnet assembly before first firing with residual-gas monitoring",
     "end_point": "PROPOSED: TML < 1 % and condensable (VCM/CVCM) < 0.1 % (the acceptance criterion reported by "
                  "Scialdone et al. p. 1 as 'total mass loss (TML) is less than 1 percent and the volatile condensable "
                  "mass (VCM) is less than 0.1 percent'; not an RFP requirement); bake profile TBD - requires the H-1 "
                  "materials list",
     "phase": "before S1 (materials) and at H-1 integration",
     "owner_threshold": "PROPOSED"},
    {"id": "MCQ-QT-04", "source_ids": [], "name": "Oxygen / atomic-oxygen exposure (coordinated with the AO lane)",
     "applies_to": ["MCQ-PM-01..07 (coated)", "MCQ-EM-01 (polyimide)", "pole material (MCQ-OQ-05)"],
     "purpose": "polyimide and uncoated magnets are oxidation-sensitive in principle; no N/O-plume evidence was "
                "accessed (AOL-M06, AOL-M07)",
     "method": "adopt AO lane AOL-EX-02 (coupons at operating temperature in O2 / atomic O) and AOL-WC-04 (in-thruster "
               "pole/magnet witness pair) with this lane's candidate grades",
     "end_point": "mass, oxide (XPS/SEM), magnetic properties where the lab allows (AOL-WC-04 note)",
     "phase": "coupons before/with S1; in-thruster witnesses from S1 onwards",
     "owner_threshold": "TBD - AO lane"},
    {"id": "MCQ-QT-05", "source_ids": ["nasa_myers_2016_hermes"], "name": "Thermal cycling of the potted coil",
     "applies_to": ["MCQ-EM-01..06", "MCQ-EIS-01"],
     "purpose": "HERMeS reports potting cracks from startup gradients and CTE mismatch (Myers et al. p. 5)",
     "method": "cycles between ambient and the measured operating temperature at the start-up rate expected in "
               "S1/flight; inspect (CT or sectioning of a sacrificial coil), measure insulation resistance and "
               "winding resistance before/after",
     "end_point": "PROPOSED: no insulation-resistance drop beyond TBD, no resistance step; cycle count TBD - "
                  "requires the S1 and mission operations concept",
     "phase": "before S1 on a sacrificial coil",
     "owner_threshold": "PROPOSED"},
    {"id": "MCQ-QT-06", "source_ids": ["nasa_jankovsky_1999", "nasa_myers_2016_hermes", "nasa_kamhawi_2013_300ms", "ceramawire_ht"], "name": "Coil temperature measurement qualification (average vs hot spot)",
     "applies_to": ["all electromagnet candidates"],
     "purpose": "the class limit applies to the hot spot; the resistance method gives the average",
     "method": "average by 4-wire resistance (potential probes at the winding, as in Jankovsky 1999 p. 4) with "
               "R = R0[1 + a(T - T0)] (NBS HB100 alpha20 = 0.00393/K, lane 15 copper records; HERMeS used a = "
               "0.00386, Myers et al. p. 7; the nickel-clad and nickel conductors need their own R(T): Ceramawire p. 2 "
               "gives two points only); hot spot by thermocouples embedded at the predicted hottest locations (type-K "
               "on coil outer layer and downstream/upstream positions were used on NASA-300MS, Kamhawi et al. p. 11, "
               "p. 21); the hot-spot minus average offset is then MEASURED on the built coil",
     "end_point": "PROPOSED: offset determined with stated uncertainty; replaces the lane 15 hot_spot_allowance_K "
                  "input (EEE-INST-002 +10 C convention is reference only, MCQ-REF-01)",
     "phase": "bench (energized coil in vacuum) before S1; confirmed in S1 hot operation",
     "owner_threshold": "PROPOSED"},
    {"id": "MCQ-QT-07", "source_ids": [], "name": "B(z) versus temperature and coil current (cold and hot)",
     "applies_to": ["all candidates"],
     "purpose": "reversible magnet loss (alpha_Br), coil resistance rise at constant current (current-controlled "
                "supplies keep NI constant) and pole permeability change shift B(z)",
     "method": "adopt W3 draft HW-MC-03 (map at actual coil currents per configuration before/after each block series) "
               "and HW-MC-04 (hot-state difference, reference sensor during firing); add a heated-soak map of the "
               "magnetic circuit at the measured operating temperature before S1",
     "end_point": "PROPOSED: hot-cold difference quantified with uncertainty; feeds INV-B tolerances",
     "phase": "before S1 (cold + heated soak), during S1 (hot reference sensor)",
     "owner_threshold": "PROPOSED"},
    {"id": "MCQ-QT-08", "source_ids": ["ceramawire_ht"], "name": "Insulation resistance and dielectric withstand tracking",
     "applies_to": ["all electromagnet candidates"],
     "purpose": "detect ageing, deposits and moisture; AOL-PM-06 baseline and trend",
     "method": "insulation resistance coil-to-ground and between coils, and a withstand test at a PROPOSED voltage "
               "below the wire rating (Ceramawire: 150/200 V DC; polyimide rating not in the accessed datasheet) at "
               "baseline, after bake, after every phase boundary and at campaign end",
     "end_point": "PROPOSED: trend limits TBD - requires the coil electrical design and baseline data",
     "phase": "baseline before S1; repeated per AOL-PM-06",
     "owner_threshold": "PROPOSED"},
    {"id": "MCQ-QT-09", "source_ids": [], "name": "ECR magnet / Hall circuit interaction (HW-ECR)",
     "applies_to": ["ECR magnet option (any MCQ-PM-* or electromagnet)", "PIM-ECR"],
     "purpose": "(i) fringe field of the ECR magnet in the Hall channel (INV-B3); (ii) demagnetization exposure of a "
                "permanent ECR magnet to the Hall circuit field and heat",
     "method": "magnetostatic model of MC-1 + PIM-ECR at the maximum Hall coil current; B(z) map M0 vs M0b vs M0c "
               "(W3 draft); combined opposing field at the ECR magnet compared with the knee field at the ECR magnet "
               "temperature (lane 15 ecr_magnet inputs demag_field_max_A_per_m, knee_field_A_per_m, "
               "knee_field_at_T_C)",
     "end_point": "INV-B3 tolerance (owner, TBD); irreversible loss per MCQ-QT-02",
     "phase": "design analysis before LOCK-1 input on HWQ-05; map before S1 Phase 2 readiness",
     "owner_threshold": "TBD - owner (INV-B3)"},
]


# ---------------------------------------------------------------------------------------------- requirements
REQUIREMENTS = [
    # W3 hardware definition
    {"id": "MCQ-W3-01", "adopter": "W3", "status": "PROPOSED",
     "statement": "The H-1 winding insulation system shall be selected from candidates with a supplier-stated "
                  "thermal class AND a thermal-endurance basis (MCQ-QT-01); the class shall be compared with the "
                  "MEASURED hot-spot temperature, never with the resistance-method average.",
     "rationale": "IEC 60085 classes carry no life basis; lane 15 insulation-life check needs a stated basis",
     "verification": "MCQ-QT-01, MCQ-QT-06"},
    {"id": "MCQ-W3-02", "adopter": "W3", "status": "PROPOSED",
     "statement": "Coil hot-spot design limit = EIS class minus a margin; the margin is an owner decision "
                  "(EEE-INST-002 derating may be chosen as a policy but is reference evidence only).",
     "rationale": "no RFP value; MCQ-REF-01", "verification": "analysis + MCQ-QT-06"},
    {"id": "MCQ-W3-03", "adopter": "W3", "status": "PROPOSED",
     "statement": "Any permanent magnet (Hall circuit or PIM-ECR) shall have its grade, coating, magnetization lot and "
                  "design permeance coefficient recorded; its maximum temperature shall be below the supplier "
                  "maximum use/operating temperature AND the working point at that temperature shall lie above the "
                  "knee of the supplier demagnetization curve quoted at >= that temperature.",
     "rationale": "supplier maxima assume a low/unspecified load line (Recoma p. 2 footnote 3; Recoma HT p. 4 "
                  "footnote 1); lane 15 irreversible_loss_criterion",
     "verification": "MCQ-QT-02"},
    {"id": "MCQ-W3-04", "adopter": "W3", "status": "PROPOSED",
     "statement": "Permanent magnets shall be coated or encapsulated for vacuum and oxygen exposure (SmCo per Arnold "
                  "RECOMA HT pp. 1, 7; NdFeB per the supplier coating recommendation), with the coating's outgassing "
                  "screened (MCQ-QT-03).",
     "rationale": "manufacturer statements; N/O plume back-flow unquantified (AOL-M06)",
     "verification": "inspection + MCQ-QT-03 + MCQ-QT-04"},
    {"id": "MCQ-W3-05", "adopter": "W3", "status": "PROPOSED",
     "statement": "Porous ceramic-insulated windings (MCQ-EM-03/04) shall be baked out per the supplier instruction "
                  "(125 C, 12 h) before vacuum use and stored with desiccant; the coil bake profile is part of the "
                  "H-1 integration procedure.",
     "rationale": "Ceramawire p. 2 (porosity, bake-out) and p. 3 (storage)", "verification": "MCQ-QT-03"},
    {"id": "MCQ-W3-06", "adopter": "W3", "status": "PROPOSED",
     "statement": "Coil electrical design shall keep turn-to-turn and layer-to-layer voltage below the wire's "
                  "dielectric rating with a margin (owner) and provide ground insulation independent of the enamel.",
     "rationale": "Ceramawire rating 150 V DC (<= #32) / 200 V DC (larger), p. 2", "verification": "MCQ-QT-08"},
    {"id": "MCQ-W3-07", "adopter": "W3", "status": "PROPOSED",
     "statement": "No ferromagnetic conductor, fastener or module structure near MC-1 unless the magnetostatic model "
                  "and an M0 vs M0b B(z) comparison show its effect within the INV-B tolerance.",
     "rationale": "lane 17 INV-B1/B3; W3 draft HW-PIM-03; nickel conductor option MCQ-EM-04",
     "verification": "MCQ-QT-07, MCQ-QT-09"},
    {"id": "MCQ-W3-08", "adopter": "W3", "status": "PROPOSED",
     "statement": "The ECR magnet choice (electromagnet vs permanent magnet, HWQ-05) shall be taken with the MCQ-QT-09 "
                  "analysis in hand: fringe field in the channel and demagnetization exposure of a permanent ECR "
                  "magnet at the maximum Hall coil current and the ECR magnet temperature.",
     "rationale": "ECR resonance field ~4-6x the Hall magnitude class (D-06)", "verification": "MCQ-QT-09"},
    # W4 instrumentation
    {"id": "MCQ-W4-01", "adopter": "W4", "status": "PROPOSED",
     "statement": "Each H-1 coil shall have a 4-wire (potential-probe) resistance measurement for the average winding "
                  "temperature and thermocouples at the predicted hot spots; both recorded with every reading.",
     "rationale": "Jankovsky 1999 p. 4; Kamhawi et al. 2013 pp. 11, 21; MCQ-QT-06", "verification": "channel map"},
    {"id": "MCQ-W4-02", "adopter": "W4", "status": "PROPOSED",
     "statement": "Coil currents shall be recorded per reading (current-controlled supplies), with the coil voltage, "
                  "so that coil power (hall_magnet / ecr_magnet bus rows) and R(T) come from the same record.",
     "rationale": "lane 06 magnet_supplies metering; lane 20 magnet power", "verification": "channel map"},
    {"id": "MCQ-W4-03", "adopter": "W4", "status": "PROPOSED",
     "statement": "B(z) maps shall carry the coil currents, the coil average and hot-spot temperatures and the magnet "
                  "temperatures at the time of mapping.",
     "rationale": "MCQ-QT-07; W5 may pre-register B(z) at actual coil currents as held-out evidence",
     "verification": "map record schema"},
    # lane 15 thermal_life
    {"id": "MCQ-TL-01", "adopter": "lane_15_thermal_life", "status": "PROPOSED",
     "statement": "Add grade records for the candidates MCQ-PM-01, -03, -06, -07 (and the N42SH Tw max, MCQ-L15-01) "
                  "to schemas/thermal_life/limits_v1.json, transcribed from the sources listed here, with the "
                  "'load line not stated' limitation carried in applicability_domain.",
     "rationale": "lane 15 has only Recoma 35E, N42SH (no max) and RTC-slide grades",
     "verification": "lane 15 'every limit sourced' test"},
    {"id": "MCQ-TL-02", "adopter": "lane_15_thermal_life", "status": "PROPOSED",
     "statement": "Replace the hall_magnet input 'insulation_class_C' semantics by an EIS record that distinguishes a "
                  "magnet-wire (material) class (e.g. MW 16-C 240 C per ASTM D2307) from an EIS class (IEC 60085 / "
                  "UL 1446) and carries the life basis from MCQ-QT-01 when it exists.",
     "rationale": "material class != EIS class (IEC 60085 clauses 4-5)", "verification": "lane 15 refusal tests"},
    {"id": "MCQ-TL-03", "adopter": "lane_15_thermal_life", "status": "PROPOSED",
     "statement": "Take hot_spot_allowance_K from the MCQ-QT-06 measured offset (evidence level 1 once measured on "
                  "H-1); until then keep it an explicit TBD input rather than the EEE-INST-002 +10 C convention.",
     "rationale": "MCQ-REF-01 is reference only", "verification": "MCQ-QT-06"},
    {"id": "MCQ-TL-04", "adopter": "lane_15_thermal_life", "status": "PROPOSED",
     "statement": "Add a non-copper conductor resistance model only from a sourced R(T) table of the chosen conductor "
                  "(Ceramawire gives two points per conductor; a 2-point linear model outside 500-1000 F would be "
                  "extrapolation and must be refused).",
     "rationale": "lane 15 copper models are copper-only; no silent extrapolation", "verification": "lane 15 tests"},
    {"id": "MCQ-TL-05", "adopter": "lane_15_thermal_life", "status": "PROPOSED",
     "statement": "Provide a node for a permanent-magnet Hall circuit and for an ECR electromagnet, or state that "
                  "they are out of scope, since the W3 draft allows both (HW-PIM-04, HWQ-05) and lane 15's "
                  "ecr_magnet node requires 0 W (permanent magnets only) while hall_magnet is electromagnet-only.",
     "rationale": "coverage gap found by this lane (MCQ-L15-06)", "verification": "lane 15 framework update"},
    # AO lane coordination
    {"id": "MCQ-AO-01", "adopter": "fo_ao_lifetime_register", "status": "PROPOSED",
     "statement": "AOL-WC-04 witness pair shall use the selected pole material and the selected permanent-magnet "
                  "grade with its flight coating; AOL-EX-02 coupons shall include the selected magnet-wire enamel "
                  "(polyimide or vitreous) at the measured coil temperature.",
     "rationale": "AOL-M06 / AOL-M07 have NO_EVIDENCE; this lane supplies the actual grades",
     "verification": "MCQ-QT-04"},
    {"id": "MCQ-AO-02", "adopter": "fo_ao_lifetime_register", "status": "PROPOSED",
     "statement": "AOL-PM-06 insulation-resistance tracking shall use the MCQ-QT-08 procedure and voltage so that one "
                  "data series serves both the AO register and coil qualification.",
     "rationale": "avoid duplicate, incompatible measurements", "verification": "procedure cross-reference"},
]

PROPOSED_THRESHOLDS = [
    {"id": "MCQ-PT-01", "quantity": "coil hot-spot margin below EIS class", "value": None,
     "status": "PROPOSED", "note": "TBD - owner; EEE-INST-002 '-20 C' or '0.75 x' are reference options only"},
    {"id": "MCQ-PT-02", "quantity": "permanent-magnet irreversible loss after MCQ-QT-02 soak", "value": None,
     "status": "PROPOSED", "note": "TBD - owner; tied to the INV-B tolerance"},
    {"id": "MCQ-PT-03", "quantity": "outgassing screen TML / CVCM", "value": [1.0, 0.10], "unit": "% / %",
     "status": "PROPOSED",
     "note": "criterion as reported by Scialdone et al. (NASA GSFC) p. 1 ('TML is less than 1 percent and the "
             "volatile condensable mass (VCM) is less than 0.1 percent'); not an RFP requirement; source_id "
             "nasa_scialdone_e595"},
    {"id": "MCQ-PT-04", "quantity": "EIS life basis at hot-spot temperature", "value": None, "status": "PROPOSED",
     "note": ">= RFP firing time (> 15,000 h) plus an owner margin; the 15,000 h is the RFP value, the margin is TBD"},
]


# ---------------------------------------------------------------------------------- lane 15 open questions
LANE15_ANSWERS = [
    {"id": "MCQ-L15-01", "question": "pm_ndfeb_n42sh_arnold.T_max_use_C (N42SH has no maximum-use row on its "
     "datasheet)", "status": "PARTIAL",
     "answer": "Arnold's NdFeB catalog Rev. 181031 lists N42SH with 'Tw max' 150 (C), p. 1. The column heading 'Tw' "
               "is not defined in the accessed text, so reading it as the maximum working temperature is an inference "
               "(verify), and no load line is stated. Proposed for lane 15 as a sourced 'assumed' value with that "
               "limitation (MCQ-TL-01); lane 15 decides whether to un-gate it."},
    {"id": "MCQ-L15-02", "question": "pm_ndfeb_mmpa.T_max_use_C: the '**' footnote to the NdFeB 150 C value",
     "status": "REMAINS_TBD",
     "answer": "Page 20 of the accessed open copy (sha256 3d83974a...) was rendered and inspected as an image: the "
               "markers '*' (column heading) and '**' (NdFeB 150) are printed, but NO footnote text exists on the "
               "page or elsewhere in the document's text. The lane 15 premise 'not legible' should read 'footnote "
               "text absent from the accessed copy'. The value stays gated. A different, complete copy of MMPA "
               "0100-00 is required."},
    {"id": "MCQ-L15-03", "question": "iec60085_thermal_classes.life_basis_h", "status": "REMAINS_TBD",
     "answer": "Not derivable from any accessed source: IEC 60216-1 defines TI (temperature at 20 000 h or another "
               "specified time) and HIC for MATERIALS (pp. 6-8), and a magnet-wire class (e.g. MW 16-C 240 C per ASTM "
               "D2307) is a material class. The EIS life basis needs MCQ-QT-01 (EIS evaluation or a coil life test "
               "at the H-1 hot spot)."},
    {"id": "MCQ-L15-04", "question": "IEC 60085 edition currency", "status": "REMAINS_TBD",
     "answer": "A search on 2026-09-27 found no edition later than Ed. 4.0 (2007); the edition-history page returned "
               "HTTP 403. Not conclusive (verify)."},
    {"id": "MCQ-L15-05", "question": "EEE-INST-002 note 1/c inference and the class-C analogy", "status": "UNCHANGED_REFERENCE_ONLY",
     "answer": "By the owner directive these remain reference evidence and never produce a lifetime verdict "
               "(MCQ-REF-01). This lane offers the measured alternative (MCQ-QT-01, MCQ-QT-06) instead of resolving "
               "the inference."},
    {"id": "MCQ-L15-06", "question": "(found by this lane) node coverage for a permanent-magnet Hall circuit and an "
     "ECR electromagnet", "status": "GAP_REPORTED",
     "answer": "lane 15 inputs_v1.json: ecr_magnet requires bus allocation 0 W (permanent magnets only) and "
               "hall_magnet is an electromagnet winding; the W3 draft allows an ECR electromagnet (HW-PIM-04) and "
               "lane 20 allows a permanent-magnet Hall circuit (HM-PM-OPTION). Proposed repair MCQ-TL-05."},
    {"id": "MCQ-L15-07", "question": "coefficient range of the grade maxima (all pm_* records)", "status": "PARTIAL",
     "answer": "Supplier maxima are stated without (Recoma 33E/35E p. 2 footnote 3: may be considerably lower at a "
               "low load line) or with an extreme load line (Recoma HT p. 4 footnote 1: 'operating at a very low load "
               "line'). They are upper bounds of the grade, not limits at the H-1 permeance coefficient; MCQ-QT-02 "
               "closes this per design."},
]

S1_GATE_ITEMS = [
    {"id": "MCQ-S1-01", "item": "H-1 coil EIS selected, with material thermal class and supplier data on file",
     "requirements": ["MCQ-W3-01"], "state": "MISSING"},
    {"id": "MCQ-S1-02", "item": "coil temperature instrumentation (4-wire + hot-spot TCs) installed and the "
     "hot-spot/average offset measured on the bench", "requirements": ["MCQ-W4-01", "MCQ-QT-06"], "state": "MISSING"},
    {"id": "MCQ-S1-03", "item": "sacrificial-coil thermal cycling done (MCQ-QT-05)", "requirements": ["MCQ-QT-05"],
     "state": "MISSING"},
    {"id": "MCQ-S1-04", "item": "vacuum bake / outgassing screen of coil, potting, leads and magnet coatings",
     "requirements": ["MCQ-QT-03", "MCQ-W3-05"], "state": "MISSING"},
    {"id": "MCQ-S1-05", "item": "permanent magnets (if any on H-1 or PIM-ECR): per-lot irreversible-loss test at "
     "design temperature", "requirements": ["MCQ-QT-02", "MCQ-W3-03"], "state": "MISSING"},
    {"id": "MCQ-S1-06", "item": "cold and heated-soak B(z) maps at actual coil currents, with temperatures recorded",
     "requirements": ["MCQ-QT-07", "MCQ-W4-03"], "state": "MISSING"},
    {"id": "MCQ-S1-07", "item": "insulation-resistance / withstand baseline", "requirements": ["MCQ-QT-08"],
     "state": "MISSING"},
    {"id": "MCQ-S1-08", "item": "coil and magnet safety/operational limits (max coil current, max hot-spot and "
     "magnet temperature, abort rule) defined for the S1 run sheet", "requirements": ["MCQ-W3-02", "MCQ-W3-03"],
     "state": "MISSING",
     "note": "S1 readiness condition 'safety / operational limits defined' (execution directive)"},
]

OPEN_OWNER_QUESTIONS = [
    {"id": "MCQ-OQ-01", "question": "H-1 Hall circuit: electromagnet only (traceable B(z) vs coil current, needed for "
     "W5 held-out B(z) evidence and the S_B scan HW-MC-05) or permanent-magnet assisted?"},
    {"id": "MCQ-OQ-02", "question": "Coil conductor/insulation family for S1: polyimide/Cu (MCQ-EM-01, class 240 C) "
     "or vitreous-enamel Ni-clad Cu (MCQ-EM-03, 1000 F continuous rating), decided once the H-1 thermal model gives "
     "a hot-spot estimate?"},
    {"id": "MCQ-OQ-03", "question": "Coil hot-spot margin policy (MCQ-PT-01) and whether EEE-INST-002 derating is "
     "adopted as a policy (reference only)."},
    {"id": "MCQ-OQ-04", "question": "Evidence-access route for ASTM E595 records and supplier coating data (open "
     "NASA database queries vs supplier requests through the owner's channel)."},
    {"id": "MCQ-OQ-05", "question": "Pole/core soft-magnetic material grade for MC-1 (not selected here; needed by "
     "AOL-WC-04 and the B(z)-vs-temperature test)."},
    {"id": "MCQ-OQ-06", "question": "ECR magnet type (HWQ-05) given MCQ-QT-09."},
]

MILESTONES = {
    "supports": ["A", "C"],
    "A": "Supports conditional selection only as a CONDITION LIST: 'architecture X is baseline provided H-1 "
         "(and, for ecr_hall, the PIM-ECR magnet) passes MCQ-QT-01..09 at the measured temperatures'. The magnet/coil "
         "set is common to all three arms (hall_only, rf_hall, ecr_hall) except the ecr_magnet, so it does not "
         "discriminate architectures; it gates S1 readiness (S1_gate_items) on the path S1 -> LOCK-2 -> HW-0/HW-RF/"
         "HW-ECR.",
    "B": "Not supported directly. It enables B-relevant evidence: B(z) at actual coil currents and temperatures "
         "(MCQ-W4-03) is a W5 held-out candidate; no Hall transport closure is used or needed here.",
    "C": "Supports the proposal/PDR freeze for the magnet/coil life and thermal items (lane 15 hall_magnet and "
         "ecr_magnet nodes).",
    "to_reach_next": [
        "S1: all MCQ-S1-* items delivered, owner answers MCQ-OQ-01..03 and MCQ-OQ-06",
        "Milestone C: MCQ-QT-01 life basis at the measured hot spot, MCQ-QT-04 AO results, lane 15 records adopted "
        "(MCQ-TL-*), H-1 thermal model correlated to S1 data",
    ],
}

HARD_STATEMENTS = [
    "DRAFT for owner review. No candidate is qualified, selected, passed or failed.",
    "No lifetime verdict is produced; every candidate has lifetime_verdict = null.",
    "Generic MIL class-C derating (EEE-INST-002) and generic MMPA family values are REFERENCE EVIDENCE ONLY.",
    "Thresholds not in the RFP are PROPOSED.",
    "No Hall transport closure, screening candidate or P5 value is used as a design or performance value.",
    "No architecture winner is declared; the magnet/coil set is common to hall_only, rf_hall and ecr_hall except the "
    "ecr_magnet.",
    "No 15,000 h extrapolation from an unadmitted Hall closure (control C6).",
]


# ------------------------------------------------------------------------------------------------ derived
def f_to_c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


def derived():
    out = []
    # D-01: Ceramawire temperatures in C
    for label, f in (("continuous_min", -450.0), ("continuous_max", 1000.0), ("short_term_max", 1500.0),
                     ("cure_min", 1400.0), ("cure_max", 1500.0),
                     ("nickel_migration_onset", 600.0)):
        out.append({"id": f"MCQ-D-01-{label}", "quantity": f"Ceramawire {label.replace('_', ' ')} temperature",
                    "value": round(f_to_c(f), 2), "unit": "degC", "inputs": {"degF": f},
                    "formula": "C = (F - 32) * 5/9", "source_id": "ceramawire_ht", "quantity_type": "inferred",
                    "evidence_level": 5, "note": "unit conversion only; level unchanged"})
    # D-02: all-nickel / Kulgrid resistance ratio
    for tf, ni, kg in ((500.0, 138.0, 26.9), (1000.0, 228.0, 42.3)):
        out.append({"id": f"MCQ-D-02-{int(tf)}F", "quantity": f"All-Nickel / Kulgrid resistance ratio at {int(tf)} F",
                    "value": round(ni / kg, 3), "unit": "-", "inputs": {"all_nickel": ni, "kulgrid": kg},
                    "formula": "ratio of the two published resistances", "source_id": "ceramawire_ht",
                    "quantity_type": "inferred", "evidence_level": 5,
                    "note": "at equal geometry and current, I^2R scales by this ratio (coil power penalty)"})
    # D-03 / D-04: reversible Br factor and linear-RTC HcJ estimate at the upper end of each coefficient range
    grades = (
        ("Recoma 33E", -0.035, -0.25, 20.0, 200.0, 1750.0, "arnold_recoma_combined"),
        ("N35EH", -0.12, -0.47, 20.0, 200.0, 2388.0, "arnold_n35eh"),
        ("N42SH", -0.12, -0.55, 20.0, 150.0, 1592.0, "arnold_n42sh"),
    )
    for name, a_br, a_hcj, t0, t1, hcj_min, src in grades:
        f_br = 1.0 + a_br * (t1 - t0) / 100.0
        f_hcj = 1.0 + a_hcj * (t1 - t0) / 100.0
        slug = name.replace(" ", "_")
        out.append({"id": f"MCQ-D-03-{slug}", "quantity": f"{name} Br(T)/Br(20 C) at {t1:g} C (upper end of the "
                    "coefficient range)", "value": round(f_br, 4), "unit": "-",
                    "inputs": {"alpha_Br_pct_per_C": a_br, "T_C": t1, "T_ref_C": t0},
                    "formula": "1 + alpha (T - 20)/100 (lane 15 relation reversible_temperature_coefficient)",
                    "source_id": src, "quantity_type": "model-derived", "evidence_level": 5,
                    "note": "inside the stated coefficient range only; approximate away from 20 C (Arnold RTC "
                            "slides); reversible loss, not irreversible"})
        out.append({"id": f"MCQ-D-04-{slug}", "quantity": f"{name} linear-RTC HcJ estimate at {t1:g} C from HcJ min",
                    "value": round(hcj_min * f_hcj, 1), "unit": "kA/m",
                    "inputs": {"HcJ_min_20C_kA_m": hcj_min, "alpha_HcJ_pct_per_C": a_hcj, "T_C": t1},
                    "formula": "HcJ_min * (1 + alpha_HcJ (T - 20)/100)", "source_id": src,
                    "quantity_type": "model-derived", "evidence_level": 5,
                    "note": "consistency check only; it is NOT a knee field and must not be used as one "
                            "(lane 15 irreversible_loss_criterion requires H_knee(T) from the curve)"})
    # D-05: published large Hall coil outer-layer temperatures vs the MW 16-C class
    readings = [  # (thruster, P_kW, V, downstream TC C) from Table 4, p. 21
        ("300MS", 10, 400, 375.6), ("300MS", 15, 500, 421.7), ("300MS", 20, 400, 438.0), ("300MS", 20, 600, 448.0),
        ("300M", 10, 300, 374.8), ("300M", 20, 400, 529.9), ("300M", 20, 500, 535.6),
    ]
    temps = [r[3] for r in readings]
    out.append({"id": "MCQ-D-05", "quantity": "NASA-300M/300MS inner-coil outer-layer downstream thermocouple range "
                "and excess over the MW 16-C 240 C class", "value": {"min_C": min(temps), "max_C": max(temps),
                "min_excess_over_240C_K": round(min(temps) - 240.0, 1)}, "unit": "degC / K",
                "inputs": {"readings": [{"thruster": r[0], "P_kW": r[1], "V_d": r[2], "T_C": r[3]} for r in readings],
                           "mw16c_class_C": 240.0},
                "formula": "min / max of the published readings; min - 240", "source_id": "nasa_kamhawi_2013_300ms",
                "quantity_type": "inferred", "evidence_level": 6,
                "note": "REFERENCE ONLY (MCQ-REF-05): 10-20 kW xenon thrusters, outer-layer surface readings (not hot "
                        "spots); applying them to H-1 is extrapolation; motivates measurement, not a limit"})
    # D-06: ECR resonance field vs Hall magnitude class
    e_c = 1.602176634e-19
    m_e = 9.1093837139e-31
    b_res = 2.0 * math.pi * 2.45e9 * m_e / e_c
    for label, b in (("EV-B2_150G", 0.015), ("EV-B4_200G", 0.02)):
        out.append({"id": f"MCQ-D-06-{label}", "quantity": f"ECR 2.45 GHz resonance field / Hall magnitude class "
                    f"({label})", "value": round(b_res / b, 2), "unit": "-",
                    "inputs": {"B_res_T": round(b_res, 6), "B_hall_class_T": b},
                    "formula": "B_res = 2 pi f m_e / e (CODATA 2022), ratio to the lane 17 magnitude class",
                    "source_id": "derived", "quantity_type": "model-derived", "evidence_level": 5,
                    "note": "order-of-magnitude screening; the Hall class values are illustrative/typical, not H-1"})
    return out


# -------------------------------------------------------------------------------------------------- assemble
def build():
    return {
        "schema": "magnet_coil_qualification_v1",
        "schema_file": SCHEMA_FILE,
        "id": "fo_magnet_coil_qualification",
        "title": "H-1 magnet/coil qualification basis (candidate grades, insulation systems, conductors)",
        "status": "DRAFT_FOR_OWNER_REVIEW",
        "date": ACCESSED,
        "lane": {"id": "fo_magnet_coil_qualification", "trigger": "T_PIVOT_MAGNET_COIL_QUALIFICATION",
                 "owner_disposition": "od_hardware_pivot",
                 "decision_file": "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json"},
        "builder": "docs/experiments/magnet_coil/build_magnet_coil_qualification.py",
        "milestones": MILESTONES,
        "hard_statements": HARD_STATEMENTS,
        "vocabulary": {
            "evidence_level": "1-7 as defined in docs/EVIDENCE.md (source strength and proximity)",
            "quantity_type": list(QUANTITY_TYPES),
            "status_candidate": {"CANDIDATE": "sourced enough to enter qualification planning",
                                 "CANDIDATE_INCOMPLETE_DATA": "a key datum (curves, E595, rating) is not sourced",
                                 "NOT_SOURCED_FOR_SELECTION": "named option without usable supplier data"},
            "TBD": "a value null with a 'TBD - requires ...' string: not given by any accessed source; never filled",
        },
        "sources": SOURCES,
        "access_failures": ACCESS_FAILURES,
        "repository_references": REPOSITORY_REFERENCES,
        "planned_paths_referenced_only": PLANNED_PATHS,
        "h1_requirement_basis": h1_basis(),
        "candidates": permanent_magnet_candidates() + electromagnet_candidates(),
        "reference_only_evidence": REFERENCE_ONLY,
        "qualification_tests": QUALIFICATION_TESTS,
        "requirements": REQUIREMENTS,
        "proposed_thresholds": PROPOSED_THRESHOLDS,
        "lane15_answers": LANE15_ANSWERS,
        "s1_gate_items": S1_GATE_ITEMS,
        "open_owner_questions": OPEN_OWNER_QUESTIONS,
        "derived": derived(),
    }


def render(doc) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def main(argv):
    text = render(build())
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print("magnet_coil_qualification_v1.json is stale: rerun the builder", file=sys.stderr)
            return 1
        print("OK")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
