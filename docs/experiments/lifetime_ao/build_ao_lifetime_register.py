"""Build the H-1 lifetime / atomic-oxygen degradation register (fo_ao_lifetime_register), DRAFT for owner review.

Lane: fo_ao_lifetime_register (trigger T_PIVOT_AO_LIFETIME_REGISTER, owner disposition od_hardware_pivot,
execution directive 2026-09-27, controls C5 "AO early" and C6 "no extrapolation").

What this script does (and nothing else):
* holds the hand-written register content (mechanisms, witness coupons, requirements, W3/W4 interface table) as data;
* computes ONE derived block deterministically: the external ram atomic-oxygen environment at 180/200/230 km from the
  FROZEN NRLMSIS 2.1 dataset (abep_sim/data/atmosphere_msis21_v1.csv, sha256-pinned below, read with the csv module)
  times circular orbital velocity, plus illustrative recession-equivalents from MISSE 2 flight erosion yields
  (NASA/TM-2006-214482 Table 4). Every derived number is labelled model-derived with its flags;
* writes ao_lifetime_register_v1.json and AO_LIFETIME_REGISTER.md next to itself.

Pure: standard library only; imports nothing from abep_sim or hallthruster_bridge; nothing is wired into archengine;
no Hall closure, screening candidate or withdrawn 0-D number is read or used. No life number is derived (control C6).

Usage:  python docs/experiments/lifetime_ao/build_ao_lifetime_register.py [--check]
        --check regenerates in memory and exits 1 if either committed file differs (deterministic build).
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT_JSON = os.path.join(HERE, "ao_lifetime_register_v1.json")
OUT_MD = os.path.join(HERE, "AO_LIFETIME_REGISTER.md")
SCHEMA_REL = "docs/experiments/lifetime_ao/ao_lifetime_register_v1.schema.json"

# ---------------------------------------------------------------------------------------------------------------------
# Pinned computational input (frozen data; CLAUDE.md rule 1). The build refuses a different file.
# ---------------------------------------------------------------------------------------------------------------------
ATMOSPHERE_CSV_REL = "abep_sim/data/atmosphere_msis21_v1.csv"
ATMOSPHERE_CSV_SHA256 = "5e108c6e5cb7c03ed9b741233fafbc71c7813987e1ff3d0596b04c99c4a9bff7"

# Constants transcribed from abep_sim/constants.py (read-only; the test checks they still match). They are the
# repository's own constants so that the derived flux is consistent with abep_sim.atmosphere (n_O = rho fO / m_O,
# V = sqrt(mu / (R_E + h))).
AMU_KG = 1.66053906660e-27
M_O_AMU = 16.0
MU_EARTH_M3_S2 = 3.986004418e14
R_EARTH_M = 6371.0e3
E_CHARGE_C = 1.602176634e-19
RFP_MISSION_H = 26000.0     # abep_sim.constants.RFP.mission_hours (RFP: 26,000 h mission)
RFP_FIRING_H = 15000.0      # abep_sim.constants.RFP.ignition_hours (RFP: > 15,000 h firing)

ALTITUDES_KM = (180, 200, 230)                       # RFP envelope 180-230 km
MISSE2_FLUENCE_ATOMS_CM2 = 8.43e21                   # NASA/TM-2006-214482 p. 15 (Kapton H witness mass loss)

# MISSE 2 PEACE flight erosion yields, NASA/TM-2006-214482 Table 4 (printed p. 17), transcribed exactly.
# Only materials with a plausible thruster-exterior / harness / MLI role are carried; the full table has 41 polymers.
MISSE2_YIELDS = [
    # (id, material as printed, abbreviation as printed, erosion yield cm^3/atom, role on an EP unit (our reading))
    ("MISSE2-2-E5-30", "Polyimide (PMDA)", "PI (Kapton H)", 3.00e-24, "MLI / harness film; the AO fluence witness"),
    ("MISSE2-2-E5-31", "Polyimide (PMDA)", "PI (Kapton HN)", 2.81e-24, "MLI / harness film"),
    ("MISSE2-2-E5-32", "Polyimide (BPDA)", "PI (Upilex-S)", 9.22e-25, "MLI / harness film"),
    ("MISSE2-2-E5-37", "Polyetheretherkeytone", "PEEK", 2.99e-24, "structural / connector polymer"),
    ("MISSE2-2-E5-42", "Fluorinated ethylene propylene", "FEP", 2.00e-25, "MLI outer layer / wire insulation"),
    ("MISSE2-2-E5-43", "Polytetrafluoroethylene", "PTFE", 1.42e-25, "wire insulation / spacers"),
    ("MISSE2-2-E5-41", "Tetrafluorethylene-ethylene copolymer", "ETFE (Tefzel)", 9.61e-25, "wire insulation"),
    ("MISSE2-2-E5-25", "Graphite", "PG", 4.15e-25, "graphite / carbon parts (pyrolytic graphite sample)"),
]

# ---------------------------------------------------------------------------------------------------------------------
# Sources actually accessed by this lane (2026-09-27) and repository inputs referenced by path.
# ---------------------------------------------------------------------------------------------------------------------
SOURCES = {
    "ANDREUSSI2022": {
        "citation": "T. Andreussi, E. Ferrato, V. Giannetti, 'A review of air-breathing electric propulsion: from mission "
                    "studies to technology verification', J. Electr. Propuls. 1:31 (2022)",
        "doi": "10.1007/s44205-022-00024-9",
        "urls_accessed": ["https://link.springer.com/content/pdf/10.1007/s44205-022-00024-9.pdf"],
        "access": "open_full_text",
        "license": "CC BY 4.0",
        "sha256_of_accessed_file": "490ca6f6b763fe4ee1089d9815d4075a94223ec74d577f61d67986708c3ce3b7",
        "accessed_on": "2026-09-27",
        "note": "Springer copy (57 pages; locators 'Page N of 57'). lane HSUS recorded the IRIS copy "
                "(sha256 092befad...), same article, different bytes. Review: evidence level 5 for what it reports "
                "second-hand.",
    },
    "CIFALI2011": {
        "citation": "G. Cifali, T. Misuri, P. Rossetti, M. Andrenucci, D. Valentian, D. Feili, B. Lotz, 'Experimental "
                    "characterization of HET and RIT with atmospheric propellants', IEPC-2011-224 (2011)",
        "doi": None,
        "urls_accessed": ["https://electricrocket.org/IEPC/IEPC-2011-224.pdf"],
        "access": "open_full_text",
        "license": "ERPS (open repository)",
        "sha256_of_accessed_file": "44b0fc265f35bbf707b1d99f8cbbdcf938aef48831ad28f97350550803254d11",
        "accessed_on": "2026-09-27",
        "note": "same bytes as recorded by lane HSUS (docs/evidence/hall_sustainment/). Page locators are the printed "
                "page numbers.",
    },
    "CIFALI2012": {
        "citation": "G. Cifali et al., 'Completion of HET and RIT characterization with atmospheric propellants', "
                    "Space Propulsion 2012, SP2012-2355386 (as identified by lane HSUS; ANDREUSSI2022 ref. [97])",
        "doi": None,
        "urls_accessed": [],
        "access": "not_accessed",
        "license": "unknown",
        "sha256_of_accessed_file": None,
        "accessed_on": None,
        "note": "primary of the 314 h endurance result; not located openly. Content used only as reported by "
                "ANDREUSSI2022 Page 24 of 57. Acquisition candidate for the closed-access list (control C4).",
    },
    "DEGROH2006": {
        "citation": "K. K. de Groh, B. A. Banks, C. E. McCarthy, R. N. Rucker, L. M. Roberts, L. A. Berger, 'MISSE PEACE "
                    "Polymers Atomic Oxygen Erosion Results', NASA/TM-2006-214482 (November 2006)",
        "doi": None,
        "urls_accessed": ["https://ntrs.nasa.gov/api/citations/20070002707/downloads/20070002707.pdf"],
        "access": "open_full_text",
        "license": "NASA technical report (NTRS, public)",
        "sha256_of_accessed_file": "e3111dafbf5a34567581c6d3dbf5cba99fe2f4429fdd3166516a05551b546564",
        "accessed_on": "2026-09-27",
        "note": "Locators are the printed page numbers ('NASA/TM-2006-214482 N'). Flight: MISSE 2 PEC 2 tray 1 (E5) on "
                "the ISS exterior, installed 16 Aug 2001, nearly 4 years (pp. 1, 9); mission planning assumed a 400 km "
                "circular orbit at 51.6 deg (p. 5). Exposure included solar and charged-particle radiation (p. 16). "
                "The accessed text does not state the AO impact energy.",
    },
}

REPO_REFERENCES = {
    "od_hardware_pivot": "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json",
    "evidence_policy": "docs/EVIDENCE.md",
    "hall_sustainment_matrix": "docs/evidence/hall_sustainment/hall_sustainment_matrix.json",
    "wall_life_db": "docs/evidence/wall_life/sputter_yield_db_v1.json",
    "wall_life_md": "docs/evidence/wall_life/WALL_LIFE_EVIDENCE.md",
    "cathode_dossier": "docs/evidence/cathode/cathode_evidence_v1.json",
    "cathode_dossier_md": "docs/evidence/cathode/CATHODE_DOSSIER.md",
    "cathode_integration": "docs/architecture_comparison/cathode_integration/CATHODE_INTEGRATION.md",
    "thermal_life_framework": "docs/thermal_life/THERMAL_LIFE_FRAMEWORK.md",
    "thermal_life_limits": "schemas/thermal_life/limits_v1.json",
    "thermal_life_inputs": "schemas/thermal_life/inputs_v1.json",
    "veto_layer": "docs/architecture_comparison/veto_layer/veto_layer_v1.json",
    "hard_gates": "docs/architecture_comparison/hard_gates/HARD_GATES.md",
    "hallmap_spec": "docs/hallmap/HALLMAP_PRODUCTION_SPEC.md",
    "hallmap_provenance_schema": "schemas/hallmap/hallmap_provenance_v1.json",
    "atmosphere_frozen": ATMOSPHERE_CSV_REL,
}

PLANNED_PATHS = {
    "W1_feed_state_closure": "docs/architecture_comparison/feed_state_closure/",
    "W2_lock1": "docs/architecture_comparison/lock1/",
    "W3_hardware_definition": "docs/experiments/hardware/",
    "W4_instrumentation": "docs/experiments/instrumentation/",
    "W5_validation_prereg": "docs/validation/hall_transport_v2_prereg/",
    "W7_o_o2_chemistry": "docs/chemistry/o_o2/v0/",
    "fo_magnet_coil_qualification": "planned path not published at this base (lane registry title only)",
    "fo_hallmap_schema_v2_registry": "planned path not published at this base (lane registry title only)",
    "fo_s1_readiness_gate": "planned path not published at this base (lane registry title only)",
}

EVIDENCE_CLASSES = ["measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"]
LIFE_STATUSES = ["measured_vyovrinda_hardware", "literature_other_device", "TBD"]


def _sha256_file(rel):
    with open(os.path.join(ROOT, rel), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _g(x, n=6):
    """Deterministic rounding to n significant figures (stored numbers)."""
    return float(f"{x:.{n}g}")


# ---------------------------------------------------------------------------------------------------------------------
# Derived block: external ram AO environment (model-derived) from the frozen atmosphere
# ---------------------------------------------------------------------------------------------------------------------
def compute_ao_environment():
    sha = _sha256_file(ATMOSPHERE_CSV_REL)
    if sha != ATMOSPHERE_CSV_SHA256:
        raise RuntimeError(f"{ATMOSPHERE_CSV_REL} sha256 {sha} != pinned {ATMOSPHERE_CSV_SHA256}; the frozen "
                           "atmosphere changed. Re-pin only after an intentional, logged rebuild (CLAUDE.md rule 1).")
    rows = {}
    with open(os.path.join(ROOT, ATMOSPHERE_CSV_REL), newline="") as f:
        for r in csv.DictReader(f):
            rows[(round(float(r["alt_km"]), 6), round(float(r["f107"]), 6))] = r
    f107s = sorted({k[1] for k in rows})
    m_o = M_O_AMU * AMU_KG
    table = []
    for alt in ALTITUDES_KM:
        v = math.sqrt(MU_EARTH_M3_S2 / (R_EARTH_M + alt * 1e3))
        e_ram_ev = 0.5 * m_o * v * v / E_CHARGE_C
        for f107 in f107s:
            key = (round(float(alt), 6), f107)
            if key not in rows:
                raise RuntimeError(f"frozen atmosphere has no grid row at {alt} km / F10.7 {f107}; no interpolation "
                                   "is performed by this builder")
            r = rows[key]
            rho, fo = float(r["rho"]), float(r["fO"])
            n_o_m3 = rho * fo / m_o
            flux_m2s = n_o_m3 * v
            flux_cm2s = flux_m2s * 1e-4
            fl_1000h = flux_cm2s * 1000.0 * 3600.0
            fl_mission = flux_cm2s * RFP_MISSION_H * 3600.0
            table.append({
                "alt_km": alt,
                "f107": f107,
                "rho_kg_m3": _g(rho),
                "fO_mass_fraction": _g(fo),
                "n_O_m3": _g(n_o_m3),
                "V_orb_m_s": _g(v),
                "E_ram_O_eV": _g(e_ram_ev, 4),
                "ram_flux_atoms_cm2_s": _g(flux_cm2s, 4),
                "fluence_per_1000h_atoms_cm2": _g(fl_1000h, 4),
                "fluence_rfp_mission_26000h_atoms_cm2": _g(fl_mission, 4),
                "ratio_to_misse2_fluence": _g(fl_mission / MISSE2_FLUENCE_ATOMS_CM2, 3),
            })
    # illustrative recession-equivalents at the envelope extremes of the mission fluence
    fl_all = [t["fluence_rfp_mission_26000h_atoms_cm2"] for t in table]
    fl_min, fl_max = min(fl_all), max(fl_all)
    recession = []
    for mid, mat, abbr, ey, role in MISSE2_YIELDS:
        recession.append({
            "id": mid,
            "material": mat,
            "abbreviation": abbr,
            "role_on_ep_unit": role,
            "misse2_erosion_yield_cm3_per_atom": ey,
            "yield_source": {"source_id": "DEGROH2006", "locator": "Table 4, p. 17", "evidence_level": 3,
                             "evidence_class": "measured",
                             "note": "flight mass loss / (area x density x Kapton-H-witness fluence), Eq. (1)-(3) p. 2; "
                                     "Kapton H yield itself is the reference 3.0e-24 cm3/atom (p. 2, citing Banks "
                                     "1997 [4]), so every yield is relative to that calibration"},
            "illustrative_recession_um_at_min_mission_fluence": _g(ey * fl_min * 1e4, 3),
            "illustrative_recession_um_at_max_mission_fluence": _g(ey * fl_max * 1e4, 3),
        })
    return {
        "status": "model-derived; ILLUSTRATIVE (sets the witness-exposure target scale; not a design value, not a verdict)",
        "evidence_class": "model-derived",
        "evidence_level": 6,
        "inputs": {
            "atmosphere": {"path": ATMOSPHERE_CSV_REL, "sha256": ATMOSPHERE_CSV_SHA256,
                           "model": "NRLMSIS 2.1 frozen scenario (abep_sim/data/atmosphere_msis21_v1.json): epoch "
                                    "2028-03-21T12:00, ap 15, F10.7A = F10.7, orbit-averaged lat -60..60 x 4 longitudes"},
            "constants": {"amu_kg": AMU_KG, "m_O_amu": M_O_AMU, "mu_earth_m3_s2": MU_EARTH_M3_S2,
                          "R_earth_m": R_EARTH_M, "e_C": E_CHARGE_C, "source": "abep_sim/constants.py (read-only)"},
            "rfp_mission_h": RFP_MISSION_H,
            "misse2_fluence_atoms_cm2": {"value": MISSE2_FLUENCE_ATOMS_CM2, "source_id": "DEGROH2006",
                                         "locator": "p. 15", "evidence_class": "measured",
                                         "note": "from two Kapton H witness samples; ISS exterior, ~4 years"},
        },
        "equations": {
            "n_O": "n_O = rho * fO / m_O  (same relation as abep_sim.atmosphere 'n_O')",
            "V_orb": "V = sqrt(mu / (R_E + h))  (abep_sim.atmosphere.orbital_velocity)",
            "E_ram": "E = 0.5 * m_O * V^2 / e  (kinetic energy of an O atom in the spacecraft frame, co-rotation and "
                     "thermal motion neglected)",
            "flux": "Gamma = n_O * V  (ram-normal surface)",
            "fluence": "F = Gamma * t",
            "recession_equivalent": "x = E_y * F  (linear, fluence-independent yield ASSUMED)",
        },
        "flags": [
            "RAM_NORMAL_UPPER_BOUND: flux onto a surface facing the ram direction at normal incidence. An ABEP thruster "
            "sits behind the intake; the actual exposure of each H-1 exterior surface is TBD - requires the spacecraft "
            "layout and a free-molecular / DSMC view-factor analysis (owner/system design).",
            "NO_COROTATION_NO_THERMAL: atmospheric co-rotation and O thermal motion are neglected (they change the "
            "relative speed and let non-ram surfaces receive flux).",
            "FROZEN_SCENARIO_ONLY: one epoch, orbit-averaged; no solar-cycle-averaged mission profile. The F10.7 "
            "70-230 columns bracket activity; the mission F10.7 history is TBD - requires the mission profile.",
            "COMPOSITION_SUM: fO is the O mass fraction of O+N2+O2 while rho includes the dropped species (He, H, Ar, N; "
            "< 2 % by mass at 180-230 km per the frozen metadata), so n_O is high by at most that share.",
            "OTHER_ENVIRONMENT (recession only): MISSE 2 yields are ISS-exterior values (planning orbit 400 km, 51.6 "
            "deg; AO with solar UV and charged particles). The AO energy there is not stated in the accessed text; "
            "E_ram here is model-derived. No energy or synergy correction is applied.",
            "FLUENCE_EXTRAPOLATION (recession only): mission fluences exceed the MISSE 2 fluence by the "
            "'ratio_to_misse2_fluence' factor; a linear yield beyond the tested fluence is ASSUMED.",
        ],
        "table": table,
        "illustrative_recession_equivalents": {
            "status": "ILLUSTRATIVE, OUT_OF_DOMAIN (flags above). Shows only that polymer exterior parts on a "
                      "ram-exposed surface would not survive the mission fluence unprotected; it is never a design "
                      "margin, a coating thickness or a verdict. Metals, BN, alumina and other ceramics: no open "
                      "erosion yield accessed by this lane -> TBD (AOL-EX-01).",
            "mission_fluence_range_atoms_cm2": [fl_min, fl_max],
            "rows": recession,
        },
    }


# ---------------------------------------------------------------------------------------------------------------------
# Register content (hand-written data). Every numeric value carries a source and an evidence class, or is TBD.
# ---------------------------------------------------------------------------------------------------------------------
def _ev(statement, source_id, locator, level, cls, applicability, *, verified_by_this_lane, value=None, unit=None):
    return {"statement": statement, "source_id": source_id, "locator": locator, "evidence_level": level,
            "evidence_class": cls, "value": value, "unit": unit, "applicability": applicability,
            "verified_by_this_lane": verified_by_this_lane,
            "transfer": "literature on another device or environment: recorded, NOT transferred to H-1 as a verdict"}


def _repo(statement, path, locator, level, cls):
    return {"statement": statement, "source_id": "REPO", "repo_path": path, "locator": locator, "evidence_level": level,
            "evidence_class": cls, "value": None, "unit": None, "applicability": "as stated by the referenced lane",
            "verified_by_this_lane": False,
            "transfer": "referenced lane record; NOT transferred to H-1 as a verdict"}


def _life(status, statement, **kw):
    d = {"status": status, "statement": statement, "value": kw.get("value"), "unit": kw.get("unit"),
         "source_id": kw.get("source_id"), "locator": kw.get("locator"), "device": kw.get("device"),
         "evidence_class": kw.get("evidence_class"), "evidence_level": kw.get("evidence_level")}
    return d


MECHANISMS = [
    {
        "id": "AOL-M01",
        "title": "Anode / gas-distributor oxidation",
        "components": ["H-1 anode", "H-1 gas distributor"],
        "species": ["O2", "O", "O+ / O2+ (near-anode, if present)", "NO/NOx (TBD)"],
        "energy_regime": "thermal_neutral_internal",
        "energy_statement": "Chemical oxidation by the O-bearing anode feed and discharge-produced atomic O at the anode "
                            "temperature (TBD - requires H-1 thermal design / S1 anode thermocouple, W3 HW-H1-07). Ion "
                            "bombardment of the anode is not identified as the driver in any accessed source.",
        "degradation_mode": "oxide growth on the anode surface; rising electrical (contact) resistance; anomalous "
                            "discharge behaviour and spontaneous flame-outs in the one recorded endurance test",
        "measurable_quantities": [
            "anode mass change (pre/post, dehydrated protocol)",
            "oxide thickness and composition (SEM cross-section, EDS, XPS)",
            "anode-to-terminal electrical resistance (4-wire, pre/post and in situ if designed in)",
            "flame-out count and time stamps; I_d oscillation statistics during O-bearing operation",
            "anode temperature during firing",
            "visual / photographic state at each inspection (borescope if in situ)",
        ],
        "evidence": [
            _ev("After a 10 h N2/O2 firing of the PPS1350-TSD the anode 'seems rusty', explained by reaction with "
                "oxygen; 'with respect to a future endurance test the anode oxidation with the consequent increase in "
                "electrical resistance is the main concern'.", "CIFALI2011", "p. 5", 3, "measured",
                "PPS1350-TSD, 305 V, 2.75 mg/s 1.27N2 + O2, Xe start and Xe cathode, facility-fed, 10 h; visual "
                "inspection only (qualitative)", verified_by_this_lane=True, value=10, unit="h (test duration)"),
            _ev("'In order to limit anode oxidation', the planned pure-O2 test of the PPS1350-TSD was replaced by the "
                "1.27N2 + O2 mixture.", "CIFALI2011", "p. 2", 3, "measured",
                "test-planning statement (no oxidation measurement)", verified_by_this_lane=True),
            _ev("PPS1350 on N2/O2 + 10 % Xe mass flow, 305 V, 2.75 mg/s: steady for 'about 314 hours' at 3.8-4 A; "
                "then 'severe oxidation of the anode produced anomalous discharge behavior and a spontaneous flame-out' "
                "and a refurbishment (cleaning); 'in the subsequent 75 hrs of firing several flame-outs occurred likely "
                "linked to the oxidation of the anode surface and the test was prematurely stopped'. The authors "
                "suggest oxidation-resistant anode materials.", "ANDREUSSI2022", "Page 24 of 57 (citing ref. [97], "
                "CIFALI2012)", 5, "measured",
                "PPS1350 (flight-type SPT, not H-1), 10 % Xe in the anode flow, facility-fed, Xe start; second-hand "
                "(primary CIFALI2012 not accessed); anode material not stated in the accessed text",
                verified_by_this_lane=True, value=314, unit="h (steady duration before first flame-out)"),
            _repo("Same datum recorded as hall-sustainment E07 and veto-layer RI-LIFE-HALL-ANODE-OXIDATION; W3 draft "
                  "HW-H1-05 already requires anode inspection after O-bearing operation.",
                  "docs/evidence/hall_sustainment/hall_sustainment_matrix.json", "entries[E07]", 5, "measured"),
        ],
        "evidence_status": "OTHER_DEVICE_LITERATURE",
        "life_number": _life("literature_other_device",
                             "~314 h to first flame-out on a PPS1350 with 10 % Xe (second-hand). A duration on another "
                             "device and feed; not an H-1 life and not extrapolated.",
                             value=314, unit="h", source_id="ANDREUSSI2022", locator="Page 24 of 57",
                             device="PPS1350 (N2/O2 + 10 % Xe)", evidence_class="measured", evidence_level=5),
        "required_experiment": {
            "ground_ao_source": "Anode-material coupons (H-1 anode material plus owner-selected oxidation-resistant "
                                "candidates; no candidate is sourced here) exposed to O2 and to an atomic-O source at "
                                "the anode temperature range (TBD, from S1): mass, oxide thickness, XPS, resistance "
                                "(AOL-EX-02).",
            "in_thruster_witness": "Replaceable, serialized anode with baseline metrology (AOL-RC-01); anode-material "
                                   "witness coupons at the distributor outlet region if the design allows without "
                                   "changing the flow path (AOL-WC-02); in-situ resistance lead (AOL-RC-02); flame-out "
                                   "logging (AOL-CX-06, AOL-DC-02).",
            "post_test_metrology": "AOL-PM-01, AOL-PM-02, AOL-PM-04, AOL-PM-06",
        },
        "architecture_scope": "common_mode (the anode is part of the common H-1); a pre-ionizer may change the atomic-O "
                              "share reaching the anode (W7 / lane 19 note) - TBD, measured per arm by AOL-WC-05",
        "cross_refs": ["RI-LIFE-HALL-ANODE-OXIDATION", "hall-sustainment E06, E07", "W3 draft HW-H1-05"],
        "linked_requirements": ["AOL-RC-01", "AOL-RC-02", "AOL-WC-02", "AOL-WC-05", "AOL-CX-06", "AOL-PM-01",
                                "AOL-PM-02", "AOL-PM-04", "AOL-PM-06", "AOL-EX-02", "AOL-DC-02"],
    },
    {
        "id": "AOL-M02",
        "title": "Channel-wall physical sputtering by N+, N2+, O+, O2+ and Xe+ (incl. multiply charged)",
        "components": ["H-1 channel walls (BN, BN-SiO2 or alternative grade; owner decision)", "exit-region chamfers"],
        "species": ["N+", "N2+", "O+", "O2+", "Xe+ (start / transition / reference points)", "N2+ / N++ / O++ (TBD)"],
        "energy_regime": "sheath_accelerated_ions",
        "energy_statement": "Wall impact energy = sheath drop plus the ion's axial energy and angle; the solver's "
                            "WallSheath value Z*phi_s + T_e/2 omits both and is not a validated erosion input "
                            "(lane 32 use restriction 1). Lane 32 proposes coupon tests at 20-300 eV, 0-85 deg (H1). "
                            "H-1 values: TBD - requires near-wall diagnostics (lane 32 H7) or an ADMITTED closure.",
        "degradation_mode": "wall recession profile, exit chamfer growth, eventual pole-piece exposure",
        "measurable_quantities": [
            "wall erosion profile (contact or optical profilometry / laser scan against fiducials) at every stage",
            "wall-ring mass change (dehydrated protocol; BN is hygroscopic-sensitive: moisture uptake flagged by "
            "lane 32 SURFACE_STATE)",
            "surface roughness and grain detachment (SEM)",
            "wall temperature map",
        ],
        "evidence": [
            _repo("No measured N+, N2+, O+ or O2+ sputter yield on BN, BN-SiO2 or SiC was located; Xe+ on BN differs "
                  "up to 11.8x between laboratories; thresholds are not identified; any N/O lookup on the primary wall "
                  "materials is OUT_OF_DOMAIN -> NOT_DEMONSTRATED.", "docs/evidence/wall_life/WALL_LIFE_EVIDENCE.md",
                  "sections 1-3, 6, 6a", 3, "measured"),
            _ev("PPS1350 on N2/O2 + 10 % Xe: 'the ceramic erosion was still compatible with a 7000-9500 hrs lifetime' "
                "(authors' estimate; method not given in the review).", "ANDREUSSI2022", "Page 24 of 57", 5,
                "model-derived", "PPS1350, 10 % Xe, second-hand; wear-model extrapolation of unknown method",
                verified_by_this_lane=True, value=[7000, 9500], unit="h"),
            _repo("Counter-indicator: magnetically shielded SITAEL HT5k DM2 on N2/O2, shielding 'seems effective', "
                  "no critical damage after a cumulative 10 h air test (qualitative).",
                  "docs/architecture_comparison/veto_layer/veto_layer_v1.json", "RI-LIFE-HALL-SHIELDED-COUNTER", 3,
                  "measured"),
        ],
        "evidence_status": "NO_N_O_EVIDENCE_ON_WALL_GRADES",
        "life_number": _life("literature_other_device",
                             "7000-9500 h authors' erosion-compatible estimate on a PPS1350 (second-hand, "
                             "model-derived). Not an H-1 life; lane 24 basis engineering_estimate, never verdict-bearing. "
                             "H-1 wall life: TBD - requires measured N/O yields on the H-1 grade plus a measured H-1 "
                             "erosion profile (no admitted closure exists).",
                             value=[7000, 9500], unit="h", source_id="ANDREUSSI2022", locator="Page 24 of 57",
                             device="PPS1350 (N2/O2 + 10 % Xe)", evidence_class="model-derived", evidence_level=5),
        "required_experiment": {
            "ground_ao_source": "Not an AO-source test: ion-beam coupons of the H-1 wall grade with N+, N2+, O+, O2+ "
                                "(lane 32 H1-H3, H5, H8) in a coupon facility; ground-AO source only for the combined "
                                "chemistry case (AOL-M03).",
            "in_thruster_witness": "Replaceable exit-region wall rings with fiducials (AOL-RC-03); owner-optional "
                                   "sector inserts of alternative grades (AOL-RC-04); wall thermocouples (AOL-CX-07).",
            "post_test_metrology": "AOL-PM-01, AOL-PM-03, AOL-PM-04, AOL-PM-02",
        },
        "architecture_scope": "common_mode (wall is common); pre-ionization may change the species/energy mix at the "
                              "wall (veto layer TR-16) - measured, never assumed",
        "cross_refs": ["RI-LIFE-HALL-CHANNEL-AIR-EROSION", "RI-LIFE-HALL-SHIELDED-COUNTER", "RI-LIFE-SCALE-WALL-FLUX",
                       "lane 32 H1-H9, G1-G11", "W3 draft HW-H1-04"],
        "linked_requirements": ["AOL-RC-03", "AOL-RC-04", "AOL-CX-07", "AOL-PM-01", "AOL-PM-02", "AOL-PM-03",
                                "AOL-PM-04", "AOL-LF-01"],
    },
    {
        "id": "AOL-M03",
        "title": "Channel-wall chemical erosion / oxidation and N implantation (O, O+, N, N+ on B, Si, C constituents)",
        "components": ["H-1 channel walls"],
        "species": ["O", "O+", "O2", "N", "N+"],
        "energy_regime": "mixed_thermal_and_sheath_ions",
        "energy_statement": "Thermal neutrals at wall temperature plus sheath-accelerated ions; wall temperature TBD "
                            "(S1). The manufacturer oxidizing-atmosphere use limit recorded by lane 15 for HeBoSint "
                            "BN grades (~900 degC, datasheet guide value, no plasma / AO coverage) is context only.",
        "degradation_mode": "B2O3 / SiO2 surface layer formation, volatilization, altered sputter yield and SEE yield",
        "measurable_quantities": ["surface composition (XPS) and depth profile", "oxide layer morphology (SEM/EDS)",
                                  "wall temperature", "SEE yield before/after exposure (lane 32 H9)"],
        "evidence": [
            _repo("Reactive chemistry is outside every yield entry; O oxidizes B (B2O3), Si and C; physical-sputtering "
                  "yields cannot bound N/O erosion from either side. O on B vs O on B2O3 (TRIM.SP proxies) differ ~20x "
                  "at 150 eV.", "docs/evidence/wall_life/WALL_LIFE_EVIDENCE.md", "section 3, section 5", 4,
                  "model-derived"),
            _ev("After the 10 h N2/O2 PPS1350-TSD test, 'the signs of operation with oxygen are also visible on the "
                "ceramics'.", "CIFALI2011", "p. 5", 3, "measured", "visual only, 10 h", verified_by_this_lane=True),
            _repo("HeBoSint BN grades: 'Use Temperature max.' ~900 degC in oxidizing atmosphere (manufacturer guide "
                  "value; does not cover plasma bombardment or atomic oxygen).", "schemas/thermal_life/limits_v1.json",
                  "records bn_hebosint_*", 5, "assumed"),
        ],
        "evidence_status": "QUALITATIVE_OBSERVATION_ONLY",
        "life_number": _life("TBD", "TBD - requires lane 32 H4 (combined ion + atomic-O + N2 exposure at 30-600 degC "
                                    "with XPS/SEM) and the H-1 witness rings."),
        "required_experiment": {
            "ground_ao_source": "Wall-grade coupons in a combined ion + atomic-O facility at wall temperature "
                                "(lane 32 H4; AOL-EX-02).",
            "in_thruster_witness": "Exit-region rings (AOL-RC-03) and near-exit wall-grade coupons (AOL-WC-01).",
            "post_test_metrology": "AOL-PM-04 (XPS depth profile, SEM/EDS), AOL-PM-07 (SEE yield, if facility allows)",
        },
        "architecture_scope": "common_mode",
        "cross_refs": ["lane 32 H4, H9", "fo_hallmap_schema_v2_registry (SEE yield field)"],
        "linked_requirements": ["AOL-RC-03", "AOL-WC-01", "AOL-PM-04", "AOL-PM-07", "AOL-EX-02"],
    },
    {
        "id": "AOL-M04",
        "title": "Cathode emitter poisoning by O / O2 / H2O (LaB6 baseline; BaO-W, C12A7 alternatives)",
        "components": ["C-1 emitter (insert)", "C-1 orifice"],
        "species": ["O2", "O", "H2O", "N2 / N (effect unknown)"],
        "energy_regime": "thermal_neutral_internal",
        "energy_statement": "Neutral back-flow from the plume and facility background to the hot emitter; emitter-region "
                            "O partial pressure TBD - not measurable directly (lane 10 G02; W3 draft HW-C1-03).",
        "degradation_mode": "work-function rise, higher emitter temperature or heater power needed, ignition failure, "
                            "plume-mode growth (and hence Xe consumption, lane 19)",
        "measurable_quantities": ["keeper voltage and coupling voltage at a fixed Xe reference condition (daily)",
                                  "heater power and time-to-ignition at every start", "emitter temperature (pyrometer or "
                                  "thermocouple, if designed in)", "RGA partial pressures near the cathode",
                                  "post-test insert surface composition (XPS/EDS)"],
        "evidence": [
            _repo("LaB6: O2 at ~1e-5 Torr degrades emission below 1440 degC; tolerates up to 1e-4 Torr at 1570 degC "
                  "(textbook statement of diode tests). BaO-W: ~1e-7 Torr O2 fully poisons at 1100 degC. No atomic-O "
                  "or N2 data for either.", "docs/evidence/cathode/CATHODE_DOSSIER.md", "sections 3.1, 3.2, U03-U05", 5,
                  "measured"),
            _ev("HC20h hollow cathode (LaB6 emitter) characterized with N2 and N2/O2 mixtures (AETHER): 8-20 A on N2; "
                "after the atmospheric-mixture test, 'severe erosion and embrittlement of the cathode tube and of some "
                "ceramic elements, suggesting the incompatibility of the HC20h design with oxygen propellant'.",
                "ANDREUSSI2022", "Page 38 of 57", 5, "measured",
                "cathode FED with the atmospheric mixture (not the Xe-fed C-1 baseline); second-hand review",
                verified_by_this_lane=True),
            _repo("RAM-HET cathode (Kaufman & Robinson SHC 1000) could not be ignited after two days of N2/O2 testing; "
                  "the accessed text does not attribute this to poisoning (IEPC-2017-377 pp. 7-8).",
                  "docs/architecture_comparison/cathode_integration/CATHODE_INTEGRATION.md", "section 6", 3,
                  "measured"),
        ],
        "evidence_status": "OTHER_DEVICE_LITERATURE",
        "life_number": _life("TBD", "TBD - requires lane 10 G02/G04 and the C-1 exposure log (AOL-CX-01..06). "
                                    "Xe-only vacuum life data (e.g. 27,800 h / 51,184 h BaO-W tests in lane 10) are "
                                    "another environment and are not transferred."),
        "required_experiment": {
            "ground_ao_source": "Emitter coupons (LaB6 and, if kept as alternatives, BaO-W / C12A7) heated to operating "
                                "temperature under controlled O2 and atomic-O partial pressure: emission, work function, "
                                "recovery (lane 10 G02, G03; AOL-EX-03).",
            "in_thruster_witness": "C-1 exposure monitoring AOL-CX-01..06; cathode-vicinity witness coupons AOL-WC-03.",
            "post_test_metrology": "AOL-PM-05 (insert, orifice, keeper), AOL-PM-04",
        },
        "architecture_scope": "common_mode; a pre-ionizer may raise the atomic-O share of the back-flow "
                              "(RI-LIFE-CATHODE-AIR-EXPOSURE architecture_modulation: TBD) - measured per arm",
        "cross_refs": ["RI-LIFE-CATHODE-AIR-EXPOSURE", "lane 10 G02-G05, U03-U05", "lane 19", "W3 draft HW-C1-03"],
        "linked_requirements": ["AOL-CX-01", "AOL-CX-02", "AOL-CX-03", "AOL-CX-04", "AOL-CX-05", "AOL-CX-06",
                                "AOL-WC-03", "AOL-PM-04", "AOL-PM-05", "AOL-EX-03"],
    },
    {
        "id": "AOL-M05",
        "title": "Cathode keeper / orifice / tube erosion in an N/O plume",
        "components": ["C-1 keeper", "C-1 orifice plate", "C-1 cathode tube and ceramic insulators"],
        "species": ["N+", "N2+", "O+", "O2+", "Xe+", "O (chemical)"],
        "energy_regime": "plume_ions_backflow",
        "energy_statement": "Ions accelerated by the keeper / cathode sheath and plume potential structure; energies TBD "
                            "(RPA near the cathode if feasible, W4 draft INS-14).",
        "degradation_mode": "keeper-face and orifice erosion, embrittlement, deposits",
        "measurable_quantities": ["orifice diameter and keeper-face profile (pre/post)", "keeper mass",
                                  "SEM/EDS of keeper and tube", "keeper voltage trend"],
        "evidence": [
            _ev("HC20h on N2/O2 mixtures: severe erosion and embrittlement of cathode tube and ceramic elements.",
                "ANDREUSSI2022", "Page 38 of 57", 5, "measured", "O-fed cathode; second-hand",
                verified_by_this_lane=True),
            _repo("NSTAR ELT (Xe only): keeper fully eroded; test length 30,352 h (chapter text) / 30,152 h (figure caption), "
                  "a source-internal inconsistency carried by lane 10 (U13).",
                  "docs/evidence/cathode/CATHODE_DOSSIER.md", "section 3.2", 5, "measured"),
        ],
        "evidence_status": "OTHER_DEVICE_LITERATURE",
        "life_number": _life("TBD", "TBD - requires lane 10 G04 wear test in a representative mixed-gas background."),
        "required_experiment": {
            "ground_ao_source": "Keeper-material coupons in combined ion + O exposure (AOL-EX-02).",
            "in_thruster_witness": "Keeper-material witness coupons near C-1 (AOL-WC-03); keeper voltage trend "
                                   "(AOL-CX-01).",
            "post_test_metrology": "AOL-PM-05",
        },
        "architecture_scope": "common_mode",
        "cross_refs": ["lane 10 G04", "W3 draft HW-C1-05"],
        "linked_requirements": ["AOL-WC-03", "AOL-CX-01", "AOL-PM-05", "AOL-EX-02"],
    },
    {
        "id": "AOL-M06",
        "title": "Magnetic-circuit materials: oxidation, temperature and demagnetization",
        "components": ["pole pieces and magnetic core (soft-magnetic material TBD)", "permanent magnets if used",
                       "coil windings"],
        "species": ["O", "O2 (plume / back-flow neutrals)", "N+ / O+ on exposed pole faces"],
        "energy_regime": "mixed_thermal_and_sheath_ions",
        "energy_statement": "Thermal neutral oxidation of exposed ferromagnetic surfaces; ion bombardment of pole faces "
                            "if the plume reaches them; temperature-driven reversible/irreversible magnetic loss.",
        "degradation_mode": "B(z) drift at constant coil current, pole-face oxidation / erosion, irreversible "
                            "demagnetization of permanent magnets above the knee (lane 15 relation "
                            "irreversible_loss_criterion)",
        "measurable_quantities": ["B(z) at recorded coil currents before/after every block series (W3 draft HW-MC-03)",
                                  "fixed reference field sensor during firing (W3 draft HW-MC-04)",
                                  "coil resistance / temperature", "pole-face oxide (XPS/SEM) on witness coupons"],
        "evidence": [
            _repo("Permanent-magnet reversible temperature coefficients (MMPA 0100-00, manufacturer datasheets) and "
                  "the irreversible-loss criterion are recorded as grade/family typical values (level 5); they carry "
                  "no oxidation data.", "schemas/thermal_life/limits_v1.json", "records pm_*; relations "
                                                                                "irreversible_loss_criterion",
                  5, "measured"),
        ],
        "evidence_status": "NO_EVIDENCE",
        "life_number": _life("TBD", "TBD - requires fo_magnet_coil_qualification (actual candidate grades) and the "
                                    "H-1 B(z) drift record; no oxidation evidence for magnetic materials in an N/O plume "
                                    "was accessed by this lane."),
        "required_experiment": {
            "ground_ao_source": "Pole-piece / magnet-grade coupons in O2 and atomic-O at the magnetic-circuit "
                                "temperature (TBD, S1): mass, oxide, magnetic properties (AOL-EX-02).",
            "in_thruster_witness": "Pole-material witness coupons at plume-exposed and shadowed positions "
                                   "(AOL-WC-04); B(z) drift monitoring (adopt W3 HW-MC-03/04).",
            "post_test_metrology": "AOL-PM-08 (B(z) re-map, magnet inspection), AOL-PM-04",
        },
        "architecture_scope": "common_mode (MC-1 is common); an ECR arm adds its own ecr_magnet (module-specific)",
        "cross_refs": ["fo_magnet_coil_qualification", "W3 draft HW-MC-03, HW-MC-04", "lane 15 limits pm_*"],
        "linked_requirements": ["AOL-WC-04", "AOL-PM-08", "AOL-PM-04", "AOL-EX-02"],
    },
    {
        "id": "AOL-M07",
        "title": "Electrical insulation: conductive deposits, oxidation and thermal ageing",
        "components": ["anode isolator ceramics", "coil insulation", "harness / connectors", "cathode heater "
                                                                                             "insulation"],
        "species": ["sputtered wall / module material (deposit)", "O", "O2"],
        "energy_regime": "mixed_thermal_and_sheath_ions",
        "energy_statement": "Deposition of sputter products (wall, keeper, pre-ionizer module) on insulating surfaces; "
                            "oxidation at temperature; thermal class limits (IEC 60085, lane 15) for coil insulation.",
        "degradation_mode": "leakage current, insulation-resistance drop, arcing",
        "measurable_quantities": ["insulation resistance (pre/post, and between blocks)", "leakage current during "
                                  "firing (if the power topology allows)", "deposit thickness / composition on "
                                  "insulator witness coupons (EDS)"],
        "evidence": [
            _repo("AMPCAT microwave cathode on O2/N2: antenna erosion and MoOx deposition within ~1 h, mitigated by "
                  "alumina isolation (another device; deposition in an O environment).",
                  "docs/evidence/cathode/CATHODE_DOSSIER.md", "section 3.5", 3, "measured"),
            _repo("Only statements on RF-source erosion are a design claim and a review judgement; dielectric-tube "
                  "erosion and O recombination over > 15,000 h are not addressed by any accessed measurement.",
                  "docs/architecture_comparison/veto_layer/veto_layer_v1.json", "RI-LIFE-RF-DIELECTRIC", 5,
                  "assumed"),
        ],
        "evidence_status": "NO_EVIDENCE",
        "life_number": _life("TBD", "TBD - requires insulation-resistance trend and deposit metrology on H-1."),
        "required_experiment": {
            "ground_ao_source": "Not primary; isolator material coupons may join AOL-EX-02.",
            "in_thruster_witness": "Insulator-material witness coupons near the anode isolator and at the module "
                                   "interface (AOL-WC-05, AOL-WC-06).",
            "post_test_metrology": "AOL-PM-06 (resistance), AOL-PM-04 (EDS of deposits)",
        },
        "architecture_scope": "common_mode plus module-specific deposits in rf_hall / ecr_hall",
        "cross_refs": ["RI-LIFE-RF-DIELECTRIC", "W3 draft HW-PIM-10", "lane 15 iec60085_thermal_classes"],
        "linked_requirements": ["AOL-WC-05", "AOL-WC-06", "AOL-PM-04", "AOL-PM-06"],
    },
    {
        "id": "AOL-M08",
        "title": "Coatings and surface treatments (anode coatings, thermal-control finishes, emissivity change)",
        "components": ["anode (if coated)", "thruster body / radiator finishes", "MLI"],
        "species": ["O (internal and external)", "deposits"],
        "energy_regime": "mixed_thermal_and_ram",
        "energy_statement": "Internal: discharge-produced O at component temperature. External: ram AO "
                            "(AOL-M09 energy).",
        "degradation_mode": "coating loss or conversion, changed emissivity / absorptance (thermal balance), "
                            "changed electrical contact",
        "measurable_quantities": ["coating thickness / mass", "hemispherical emissivity and solar absorptance "
                                  "(optical)", "XPS of coating surface"],
        "evidence": [
            _ev("Authors suggest 'alternative, oxidation-resistant anode materials could solve the observed lifetime "
                "issues' (suggestion; no material named or tested in the accessed text).", "ANDREUSSI2022",
                "Page 24 of 57", 5, "assumed", "authors' suggestion", verified_by_this_lane=True),
            _ev("RIT10 (gridded ion engine): grid erosion after 10 h on pure O2 'noticeably higher' than after N2, "
                "'likely due to chemical reactions ... between oxygen and the graphite'; titanium grids later showed "
                "much lower erosion.", "ANDREUSSI2022", "Page 24 of 57", 5, "measured",
                "ion-engine grids, another device class; qualitative material hint for carbon parts in O plasma",
                verified_by_this_lane=True),
        ],
        "evidence_status": "NO_EVIDENCE",
        "life_number": _life("TBD", "TBD - requires owner-selected coating/material candidates and AOL-EX-01/02."),
        "required_experiment": {
            "ground_ao_source": "Coated / treated coupons alongside uncoated references with a Kapton H fluence "
                                "witness (AOL-EX-01, AOL-EX-02).",
            "in_thruster_witness": "Coated and uncoated coupon pairs in the same holder (AOL-WC-01, AOL-WC-02).",
            "post_test_metrology": "AOL-PM-04, AOL-PM-09 (optical properties)",
        },
        "architecture_scope": "common_mode",
        "cross_refs": ["lane 15 thermal rejection ledger (emissivity inputs)"],
        "linked_requirements": ["AOL-WC-01", "AOL-WC-02", "AOL-EX-01", "AOL-EX-02", "AOL-PM-04", "AOL-PM-09"],
    },
    {
        "id": "AOL-M09",
        "title": "External atomic-oxygen exposure of the thruster exterior in VLEO (ram AO)",
        "components": ["H-1 / C-1 exterior surfaces", "MLI, harness, connectors", "exposed polymer / graphite parts"],
        "species": ["O (ground-state atomic oxygen, ram)"],
        "energy_regime": "thermal_neutral_ram_AO",
        "energy_statement": "Ram impact energy E = 0.5 m_O V^2 (model-derived; values per altitude in "
                            "derived.ao_environment.table E_ram_O_eV); thermal spread and co-rotation neglected.",
        "degradation_mode": "polymer recession / mass loss, graphite erosion, metal oxidation, optical property change",
        "measurable_quantities": ["mass loss (dehydrated protocol)", "recession depth (profilometry against a "
                                  "protected reference)", "surface texture (SEM)", "XPS", "optical properties"],
        "evidence": [
            _ev("MISSE 2 flight erosion yields (Table 4), e.g. Kapton H 3.00E-24, FEP 2.00E-25, PTFE 1.42E-25, "
                "pyrolytic graphite 4.15E-25 cm3/atom; fluence 8.43E21 atoms/cm2 from Kapton H witnesses.",
                "DEGROH2006", "Table 4 p. 17; p. 15", 3, "measured",
                "ISS exterior (~4 years), AO + solar UV + charged particles; polymers and graphite only",
                verified_by_this_lane=True, value=3.00e-24, unit="cm3/atom (Kapton H)"),
            _ev("Method: erosion yield from mass loss with a Kapton H witness for fluence (Eqs. 1-3); Kapton absorbs "
                "up to 2 % of its weight in moisture, so samples are dehydrated in a vacuum desiccator before pre- "
                "and post-flight weighing (60-100 mtorr, >= 4 days, 3 readings averaged).", "DEGROH2006",
                "pp. 2-3, p. 7", 3, "measured", "measurement protocol (transferable as a METHOD, not as a value)",
                verified_by_this_lane=True),
        ],
        "evidence_status": "OTHER_ENVIRONMENT_LITERATURE",
        "life_number": _life("TBD", "TBD - requires the H-1 exterior material list, the exposure geometry "
                                    "(RAM_NORMAL_UPPER_BOUND flag) and AOL-EX-01 ground exposure. The recession-"
                                    "equivalents in derived.ao_environment are illustrative only."),
        "required_experiment": {
            "ground_ao_source": "Exterior-material coupons in a ground AO facility with a Kapton H fluence witness, "
                                "to a fluence set from derived.ao_environment (AOL-EX-01).",
            "in_thruster_witness": "Not applicable (a vacuum test facility does not reproduce ram AO); facility "
                                   "background witness only (AOL-WC-06).",
            "post_test_metrology": "AOL-PM-02 (dehydrated mass), AOL-PM-04, AOL-PM-09",
        },
        "architecture_scope": "common_mode (exterior of the common H-1/C-1); module exteriors add their own "
                              "materials",
        "cross_refs": ["derived.ao_environment"],
        "linked_requirements": ["AOL-EX-01", "AOL-PM-02", "AOL-PM-04", "AOL-PM-09", "AOL-WC-06"],
    },
    {
        "id": "AOL-M10",
        "title": "Pre-ionizer module erosion products and extra atomic O reaching H-1 / C-1 (rf_hall, ecr_hall)",
        "components": ["RF dielectric tube / antenna", "ECR window / chamber", "H-1 inlet and walls (deposits)"],
        "species": ["O (from O2 dissociation in the source)", "module sputter products"],
        "energy_regime": "mixed_thermal_and_sheath_ions",
        "energy_statement": "Source-plasma sheath ions on module surfaces; neutral O carried into H-1.",
        "degradation_mode": "module erosion, deposits on H-1 (changing the common hardware between arms), higher "
                            "anode / cathode O exposure",
        "measurable_quantities": ["deposit mass / composition on interstage witness coupons per arm",
                                  "module surface inspection pre/post (W3 draft HW-PIM-10)",
                                  "O / O2 composition at the H-1 inlet (OES / RGA, W4 draft INS-11/12)"],
        "evidence": [
            _repo("Plasma-facing module materials must be O2-compatible; no accessed source measures RF tube, antenna "
                  "or shield erosion; modules are inspected before and after and deposits on H-1 recorded.",
                  "docs/architecture_comparison/veto_layer/veto_layer_v1.json", "RI-LIFE-RF-DIELECTRIC", 5,
                  "assumed"),
        ],
        "evidence_status": "NO_EVIDENCE",
        "life_number": _life("TBD", "TBD - module life is module-specific and requires module endurance data."),
        "required_experiment": {
            "ground_ao_source": "Not primary.",
            "in_thruster_witness": "Per-arm interstage witness set (AOL-WC-05), exchanged at arm boundaries only.",
            "post_test_metrology": "AOL-PM-04",
        },
        "architecture_scope": "module_specific (rf_hall, ecr_hall); it can contaminate the paired comparison, "
                              "so it is monitored, never assumed zero",
        "cross_refs": ["RI-LIFE-RF-DIELECTRIC", "W3 draft HW-PIM-10", "W3 draft section 6 (extra atomic O at H-1/C-1)"],
        "linked_requirements": ["AOL-WC-05", "AOL-PM-04"],
    },
    {
        "id": "AOL-M11",
        "title": "Facility-induced confounders: back-sputtered deposits and background gas",
        "components": ["all witness coupons", "H-1 surfaces"],
        "species": ["beam-dump / chamber-wall sputter products", "background O2 / H2O / N2"],
        "energy_regime": "facility_background",
        "energy_statement": "Not a flight mechanism: facility back-sputter and background can add or remove mass on "
                            "witnesses and mask or mimic flight degradation.",
        "degradation_mode": "false mass gain / loss on witnesses, emitter exposure not representative of flight",
        "measurable_quantities": ["deposition on beam-dump-facing and shadowed control coupons",
                                  "background composition (RGA) and pressure (W4 draft INS-08/INS-11)"],
        "evidence": [],
        "evidence_status": "NO_EVIDENCE",
        "life_number": _life("TBD", "not a life mechanism; a confounder control"),
        "required_experiment": {
            "ground_ao_source": "Not applicable.",
            "in_thruster_witness": "Control coupons AOL-WC-06 (facility background, shadowed, lab-stored).",
            "post_test_metrology": "AOL-PM-04 (EDS of deposits distinguishes facility materials)",
        },
        "architecture_scope": "facility (common to all arms; must be recorded per block)",
        "cross_refs": ["lane 10 G09 (facility-to-flight transfer)", "W4 draft INS-08, INS-11"],
        "linked_requirements": ["AOL-WC-06", "AOL-PM-04"],
    },
]

# Witness coupons / samples: placement, material, exposure, pre/post metrology
WITNESS_COUPONS = [
    {"id": "AOL-WC-01", "name": "Near-exit plume witness array",
     "placement": "fixed holder on the stand / chamber, outside the beam core, at pre-registered angles and distance "
                  "from the H-1 exit (positions TBD - W3 layout; must not change B(z), flow or the thrust-stand "
                  "tare, checked per AOL-PM-08 and W4 stand calibration)",
     "materials": ["H-1 wall grade", "H-1 anode material", "H-1 pole-piece material", "owner-selected coated / "
                   "alternative candidates (pairs coated/uncoated)"],
     "exposure": "all O-bearing and N2 operation of the block series it is installed for; exposure log per AOL-DC-01",
     "pre_metrology": ["dehydrated mass", "profilometry with masked reference region", "SEM/EDS", "XPS",
                       "photographs"],
     "post_metrology": ["dehydrated mass", "step height vs masked region", "SEM/EDS", "XPS depth profile"],
     "mechanisms": ["AOL-M02", "AOL-M03", "AOL-M08", "AOL-M11"]},
    {"id": "AOL-WC-02", "name": "Anode-material witness near the gas distributor",
     "placement": "inside H-1 at the distributor region ONLY if W3 can place it without altering the flow path or "
                  "anode area (otherwise omitted and the replaceable anode AOL-RC-01 is the witness)",
     "materials": ["H-1 anode material", "owner-selected oxidation-resistant candidates"],
     "exposure": "anode-side O-bearing feed at anode temperature",
     "pre_metrology": ["dehydrated mass", "SEM", "XPS", "4-wire resistance"],
     "post_metrology": ["dehydrated mass", "SEM cross-section (oxide thickness)", "EDS", "XPS", "4-wire resistance"],
     "mechanisms": ["AOL-M01", "AOL-M08"]},
    {"id": "AOL-WC-03", "name": "Cathode-vicinity witness set",
     "placement": "on the C-1 mount, facing the keeper region, not in the cathode plume core; fixed positions that do "
                  "not move when a module is exchanged (consistent with W3 draft HW-C1-01)",
     "materials": ["keeper material", "unheated emitter-material coupon (LaB6)", "cathode insulator ceramic"],
     "exposure": "all operation; the unheated emitter coupon records deposition / oxidation at ambient, NOT emitter "
                 "poisoning (a heated emitter witness is an owner decision, AOL-OQ-04)",
     "pre_metrology": ["mass", "SEM/EDS", "XPS"],
     "post_metrology": ["mass", "SEM/EDS", "XPS"],
     "mechanisms": ["AOL-M04", "AOL-M05"]},
    {"id": "AOL-WC-04", "name": "Magnetic-circuit material witness pair",
     "placement": "one pole-material coupon at a plume-exposed position near the outer pole face, one at a shadowed "
                  "position on the magnetic circuit",
     "materials": ["H-1 pole / core material (grade from fo_magnet_coil_qualification)", "permanent-magnet grade if "
                   "used (encapsulated as in the design)"],
     "exposure": "all operation; thermocouple next to each coupon",
     "pre_metrology": ["mass", "XPS", "SEM", "magnetic properties if the lab allows (TBD)"],
     "post_metrology": ["mass", "XPS", "SEM/EDS"],
     "mechanisms": ["AOL-M06"]},
    {"id": "AOL-WC-05", "name": "Interstage / module-interface witness set (per arm)",
     "placement": "at the pre-ionizer module outlet / H-1 inlet interface, identical position in HW-0 (blank module "
                  "position) and in HW-RF / HW-ECR; exchanged only at arm boundaries",
     "materials": ["H-1 wall grade", "anode material", "insulator ceramic"],
     "exposure": "one set per arm block series, so arm-specific deposits and O exposure are attributable",
     "pre_metrology": ["mass", "SEM/EDS", "XPS"],
     "post_metrology": ["mass", "SEM/EDS", "XPS"],
     "mechanisms": ["AOL-M01", "AOL-M07", "AOL-M10"]},
    {"id": "AOL-WC-06", "name": "Control coupons (facility background, shadowed, lab-stored)",
     "placement": "(a) chamber wall far from the plume, (b) facing the beam dump, (c) shadowed next to AOL-WC-01, "
                  "(d) lab-stored in a dry container, never in the chamber",
     "materials": ["same lot as AOL-WC-01 and AOL-WC-03 coupons"],
     "exposure": "(a)-(c) chamber exposure without direct plume; (d) handling-only",
     "pre_metrology": ["same as the coupons they control"],
     "post_metrology": ["same as the coupons they control"],
     "mechanisms": ["AOL-M11", "AOL-M09", "AOL-M07"]},
]

# Requirements W3 / W4 can adopt. Status PROPOSED. Verification methods: I inspection, A analysis, D demonstration, T test.
R = []


def _req(rid, cat, title, text, rationale, mechs, adopter, phase, vmethod, vstatement):
    R.append({"id": rid, "category": cat, "title": title, "requirement": text, "rationale": rationale,
              "mechanisms": mechs, "adopter": adopter, "install_phase": phase, "verification_method": vmethod,
              "verification": vstatement, "status": "PROPOSED"})


_req("AOL-WC-01", "witness_coupon", "Near-exit plume witness array",
     "H-1 test installation shall provide a fixed witness holder carrying coupons of the wall grade, anode material, "
     "pole material and owner-selected candidates at pre-registered positions outside the beam core.",
     "Only in-plume coupons of the actual H-1 materials give N/O-environment erosion and oxidation evidence; lane 32 "
     "has no N/O yield on BN, BN-SiO2 or SiC.", ["AOL-M02", "AOL-M03", "AOL-M08"], "W3 (mount) + W4 (metrology)",
     "design-in before S1; installed from first ignition", "I + T",
     "Inspection: holder drawing and position record; Test: B(z) re-map and thrust-stand tare with the holder "
     "installed show no change beyond W4 instrument uncertainty (value TBD - W4).")
_req("AOL-WC-02", "witness_coupon", "Anode-material witness at the distributor",
     "If W3 can place it without altering the flow path or anode area, H-1 shall carry an anode-material witness at the "
     "distributor region; otherwise W3 records why not and AOL-RC-01 is the anode witness.",
     "Anode oxidation is the recorded endurance limiter on an N2/O2 SPT (AOL-M01).", ["AOL-M01", "AOL-M08"], "W3",
     "design-in before S1", "I + A", "Inspection of the drawing; analysis that flow path and anode area are unchanged.")
_req("AOL-WC-03", "witness_coupon", "Cathode-vicinity witness set",
     "The C-1 mount shall carry keeper-material, unheated LaB6 and insulator-ceramic witness coupons at fixed positions.",
     "Cathode exposure to N/O plume back-flow is unquantified (lane 10 U03-U05).", ["AOL-M04", "AOL-M05"], "W3 + W4",
     "design-in before S1", "I", "Inspection of mount drawing and installed positions (photographic record).")
_req("AOL-WC-04", "witness_coupon", "Magnetic-circuit material witness pair",
     "MC-1 shall carry a plume-exposed and a shadowed pole-material coupon, each with a thermocouple.",
     "No oxidation evidence for magnetic materials in an N/O plume was accessed (AOL-M06).", ["AOL-M06"], "W3 + W4",
     "design-in before S1", "I", "Inspection; thermocouple channels listed in the W4 channel map.")
_req("AOL-WC-05", "witness_coupon", "Per-arm interstage witness set",
     "The module interface shall carry an interstage witness set at an identical position in HW-0, HW-RF and HW-ECR, "
     "exchanged only at arm boundaries under the W3 installation-reproducibility procedure.",
     "Module erosion products and extra atomic O could alter the common hardware between arms (AOL-M10).",
     ["AOL-M01", "AOL-M07", "AOL-M10"], "W3", "design-in before S1 (HW-0 blank position exists from S1)", "I + D",
     "Demonstration: exchange procedure executed in S1 without changing the HW-0 reference beyond the LOCK-2 "
     "repeatability (TBD - LOCK-2).")
_req("AOL-WC-06", "witness_coupon", "Control coupons",
     "Every witness lot shall have facility-background, beam-dump-facing, shadowed and lab-stored controls.",
     "Separates facility deposits and handling from plume effects (AOL-M11).", ["AOL-M11"], "W4 (+ facility)",
     "S1", "I", "Inspection of the coupon register (serials, lot, positions).")
_req("AOL-RC-01", "replaceable_component", "Replaceable, serialized anode",
     "The H-1 anode (and distributor if integral) shall be removable and re-installable with a documented torque / "
     "alignment procedure, serialized, with baseline metrology before first ignition.",
     "Anode oxidation needs direct post-test metrology; the PPS1350 anode required refurbishment after ~314 h "
     "(AOL-M01). Per W3 draft HW-H1-02 any replacement downstream of IP-DN creates H-1' with a new HW-0 reference; "
     "removal is therefore scheduled only at pre-registered phase boundaries.", ["AOL-M01"], "W3",
     "design-in before S1", "I + D", "Inspection of drawings; demonstration of one remove/re-install cycle before "
     "S1 with B(z) and HW-0 reference re-measured.")
_req("AOL-RC-02", "replaceable_component", "In-situ anode resistance lead",
     "H-1 shall provide a separate sense lead so that anode-to-terminal resistance can be measured 4-wire between "
     "blocks without disassembly.",
     "Cifali 2011 names the resistance increase from anode oxidation as the main endurance concern (p. 5).",
     ["AOL-M01"], "W3 + W4", "design-in before S1", "T", "Test: resistance measured at S1 baseline with stated "
     "uncertainty (TBD - W4).")
_req("AOL-RC-03", "replaceable_component", "Replaceable exit-region wall rings with fiducials",
     "The exit-region channel wall shall be separate replaceable rings carrying fiducial reference marks for "
     "profilometry, with as-built geometry recorded (W3 draft HW-H1-03).",
     "Wall erosion on N/O is unquantified for every grade (AOL-M02, AOL-M03); rings allow profile and mass metrology "
     "without destroying H-1.", ["AOL-M02", "AOL-M03"], "W3", "design-in before S1", "I + T",
     "Inspection of drawings; profilometry baseline repeatability measured at S1 (value TBD - W4).")
_req("AOL-RC-04", "replaceable_component", "Optional alternative-grade sector inserts (owner decision)",
     "If the owner approves, small wall sector inserts of alternative grades shall be identical in all arms and "
     "recorded as part of the H-1 configuration.",
     "Would give comparative N/O wall data in the same plasma; it changes H-1 design-representativeness (W3 draft "
     "HW-H1-01), so it is an owner decision (AOL-OQ-02).", ["AOL-M02"], "owner -> W3", "only if approved before "
     "LOCK-1", "I", "Inspection of configuration record.")
_req("AOL-CX-01", "cathode_exposure", "Daily Xe reference check of C-1",
     "C-1 keeper and coupling voltage shall be recorded daily at a fixed Xe reference condition.",
     "Trend detection of emitter degradation (AOL-M04, AOL-M05); aligns with W3 draft HW-C1-03 / D-15-B.",
     ["AOL-M04", "AOL-M05"], "W3 + W4", "S1", "T", "Test record per day; reference condition frozen in LOCK-1.")
_req("AOL-CX-02", "cathode_exposure", "Start log",
     "Every C-1 start shall log heater power, heater time to ignition, keeper ignition voltage and outcome.",
     "Ignition degradation was the observed failure mode of the RAM-HET cathode (not attributed to poisoning).",
     ["AOL-M04"], "W4", "S1", "T", "DAQ record for every start.")
_req("AOL-CX-03", "cathode_exposure", "Cathode gas-composition sampling",
     "A sampling point near C-1 shall feed the RGA (W4 draft INS-11) so O2 / H2O / N2 partial pressures near the "
     "cathode are logged during O-bearing operation.",
     "Emitter-region O partial pressure is not measurable directly (lane 10 G02); a near-cathode proxy is the minimum.",
     ["AOL-M04"], "W4", "design-in before S1", "D", "Demonstration of calibrated RGA sampling at S1 (calibration TBD).")
_req("AOL-CX-04", "cathode_exposure", "Emitter / cathode temperature",
     "C-1 emitter or cathode-tube temperature shall be measured (pyrometer or thermocouple, per W4) during firing.",
     "LaB6 O2 tolerance depends on emitter temperature (lane 10 section 3.1).", ["AOL-M04"], "W4 + W3",
     "design-in before S1", "T", "Channel in the W4 map with stated uncertainty (TBD).")
_req("AOL-CX-05", "cathode_exposure", "Hot-emitter O-exposure interlock log",
     "Every interval during which the emitter is hot while O2 is present in the chamber or feed shall be logged, with "
     "Xe cathode flow state (W3 draft HW-C1-03 rule).", "Exposure dose accounting for C-1.", ["AOL-M04"], "W4",
     "S1", "D", "Log exists for every block; interlock states recorded.")
_req("AOL-CX-06", "cathode_exposure", "Flame-out and anomaly log",
     "Every spontaneous extinction, ignition failure and anomalous-discharge episode shall be time-stamped with feed "
     "composition, I_d trace and cathode state.",
     "Flame-outs were the observable symptom of anode oxidation on the PPS1350 (AOL-M01).", ["AOL-M01", "AOL-M04"],
     "W4", "S1", "T", "Extinction detection (W4 draft INS-10) record per block.")
_req("AOL-CX-07", "cathode_exposure", "Wall and anode thermocouples for life mechanisms",
     "Thermocouples shall exist on the anode, the exit-region wall rings and next to each witness coupon.",
     "Oxidation and sputter yields depend on temperature (lane 32 section 3; lane 15 BN oxidizing limit).",
     ["AOL-M01", "AOL-M02", "AOL-M03"], "W3 + W4", "design-in before S1", "I", "Channel map and drawing.")
_req("AOL-PM-01", "post_test_metrology", "Baseline metrology before first ignition",
     "Every witness coupon, replaceable part, anode, wall ring and C-1 keeper shall be measured before first ignition "
     "(mass, profile, SEM/EDS, XPS as listed per item, resistance, photographs), with instrument, uncertainty and "
     "operator recorded.", "Without a baseline no post-test difference is interpretable.",
     ["AOL-M01", "AOL-M02", "AOL-M03", "AOL-M04", "AOL-M05", "AOL-M06"], "W4 (+ metrology lab)",
     "before S1 first ignition", "I", "Baseline records exist for every serialized item.")
_req("AOL-PM-02", "post_test_metrology", "Dehydrated mass protocol",
     "Mass measurements of hygroscopic items (polymers, BN) shall follow a dehydrated protocol (vacuum desiccator, "
     "fixed time under vacuum, repeated readings averaged, room temperature and humidity logged) identical pre and "
     "post; parameters TBD - W4 / metrology lab.",
     "Kapton absorbs up to 2 % of its weight in moisture (NASA/TM-2006-214482 p. 3); lane 32 flags moisture uptake for "
     "BN (SURFACE_STATE).", ["AOL-M02", "AOL-M09", "AOL-M01"], "W4", "S1", "D",
     "Repeatability of a control coupon demonstrated before S1 (value TBD).")
_req("AOL-PM-03", "post_test_metrology", "Channel erosion profile at each stage",
     "The wall-ring profile shall be measured against fiducials at S1 end, at each phase boundary and at campaign end.",
     "W3 draft HW-H1-04 requires an erosion profile at each stage; lane 32 H6 needs it.", ["AOL-M02"], "W3 + W4",
     "S1 onwards", "T", "Profile data with uncertainty per stage.")
_req("AOL-PM-04", "post_test_metrology", "Surface analysis",
     "Post-test SEM/EDS (morphology, deposits), XPS (oxidation state, depth profile) shall be applied to the items "
     "listed per coupon; samples transferred in sealed dry containers with custody record.",
     "Distinguishes oxidation, nitridation, deposits and facility contamination.",
     ["AOL-M01", "AOL-M03", "AOL-M04", "AOL-M06", "AOL-M07", "AOL-M10", "AOL-M11"], "W4 (+ metrology lab)",
     "after each removal", "T", "Analysis report per item referencing its baseline.")
_req("AOL-PM-05", "post_test_metrology", "Cathode post-test inspection",
     "At campaign end (or C-1 retirement), insert, orifice and keeper shall be inspected: orifice diameter, keeper-face "
     "profile, SEM/EDS and XPS of the insert surface.", "Lane 10 G02/G04.", ["AOL-M04", "AOL-M05"], "W4",
     "campaign end", "T", "Inspection report.")
_req("AOL-PM-06", "post_test_metrology", "Electrical resistance and insulation tests",
     "Anode resistance (AOL-RC-02) and insulation resistance of anode isolator, coils and harness shall be measured "
     "at baseline, every phase boundary and campaign end.", "AOL-M01, AOL-M07.", ["AOL-M01", "AOL-M07"], "W4",
     "S1 onwards", "T", "Measurement record with uncertainty (TBD).")
_req("AOL-PM-07", "post_test_metrology", "SEE yield of wall material (if facility allows)",
     "SEE yield of wall-ring / coupon material before and after N/O exposure shall be measured if an accessible "
     "facility exists (lane 32 H9).", "SEE sets the sheath and hence impact energy; also a Hall-map schema v2 field.",
     ["AOL-M03"], "owner (facility choice)", "campaign end", "T", "Report or recorded as not feasible.")
_req("AOL-PM-08", "post_test_metrology", "B(z) re-map and magnetic-circuit inspection",
     "Adopt W3 draft HW-MC-03 and HW-MC-04 (B(z) at actual coil currents before/after each block series, reference sensor "
     "during firing) and add a visual / XPS inspection of the pole faces at campaign end.",
     "AOL-M06 degradation shows as B(z) drift.", ["AOL-M06"], "W3 + W4", "S1 onwards", "T", "Map records.")
_req("AOL-PM-09", "post_test_metrology", "Optical properties",
     "Solar absorptance and hemispherical emissivity of exterior / coated coupons shall be measured pre and post "
     "ground AO exposure.", "AOL-M08, AOL-M09 thermal consequences.", ["AOL-M08", "AOL-M09"], "owner (lab)",
     "with AOL-EX-01", "T", "Measurement report.")
_req("AOL-EX-01", "ground_ao_exposure", "Ground AO exposure of exterior materials",
     "H-1 / C-1 exterior material candidates shall be exposed in a ground AO facility with a Kapton H fluence witness "
     "(DEGROH2006 Eqs. 1-3 method) to a target fluence chosen by the owner from derived.ao_environment; facility and "
     "AO energy TBD - owner channel.", "Mission ram fluence exceeds the MISSE 2 flight fluence by the tabulated factor; "
     "no open erosion yield for BN, alumina or metals was accessed.", ["AOL-M08", "AOL-M09"], "owner (facility)",
     "parallel to S1; not on the S1 critical path", "T", "Exposure report with fluence witness.")
_req("AOL-EX-02", "ground_ao_exposure", "Combined ion + atomic-O coupon exposure of internal materials",
     "Wall grade, anode material and candidates, keeper, pole and insulator materials shall be exposed to controlled "
     "O2 / atomic-O (and ions where available) at their operating temperatures (lane 32 H4).",
     "Separates chemistry from the plasma environment of H-1.", ["AOL-M01", "AOL-M03", "AOL-M05", "AOL-M06",
                                                                  "AOL-M08"],
     "owner (facility)", "parallel to S1", "T", "Exposure reports.")
_req("AOL-EX-03", "ground_ao_exposure", "Heated emitter exposure",
     "LaB6 (and alternatives if kept) emitter coupons shall be exposed hot to O2 / atomic O / H2O with emission "
     "measured (lane 10 G02, G03).", "Only O2 / H2O diode data exist; no atomic-O data.", ["AOL-M04"],
     "owner (facility)", "parallel to S1", "T", "Exposure report.")
_req("AOL-DC-01", "data_custody", "Exposure log and coupon register",
     "A coupon/part register (serial, lot, material, position, install/remove timestamps, cumulative exposure per "
     "feed composition, arm and block) shall be kept under the W5 data-custody plan; metrology operators receive "
     "coded sample IDs (PROPOSED).", "Attribution per arm and per mechanism; blinding against expectation bias.",
     ["AOL-M01", "AOL-M02", "AOL-M10", "AOL-M11"], "W4 + W5", "S1", "I", "Register audit before LOCK-2.")
_req("AOL-DC-02", "data_custody", "Evidence records compatible with thermal_life measured_hardware",
     "Every life-relevant measurement shall be recorded with the fields test_article, facility, document, "
     "measurement_method, uncertainty, operating_point, applicability_domain (schemas/thermal_life/inputs_v1.json "
     "measured_hardware) so it can later enter abep_sim/thermal_life.py without an admitted closure.",
     "The only non-closure path for wall-flux / life inputs in thermal_life is measured_hardware.",
     ["AOL-M01", "AOL-M02", "AOL-M04"], "W4", "S1", "I", "Schema check of records.")
_req("AOL-LF-01", "life_discipline", "No life extrapolation from an unadmitted closure (C6)",
     "No H-1 life number shall be computed from a Hall map, screening candidate (sgb-screen-*) or withdrawn 0-D "
     "result; life statements are measured on H-1, literature for another device (labelled), or TBD.",
     "Credible set is empty (gate 3 FAIL); control C6.", ["AOL-M01", "AOL-M02", "AOL-M03", "AOL-M04"], "all lanes",
     "always", "I", "Review; the register test asserts it for this register.")
_req("AOL-LF-02", "life_discipline", "Endurance durations and acceptance pre-registered",
     "Any wear / endurance segment and its acceptance criteria shall be pre-registered before data (duration TBD - "
     "owner); S1 results never alter a pre-registered decision threshold.", "Execution directive LOCK-2 rule; lane 10 "
     "G04.", ["AOL-M01", "AOL-M02", "AOL-M04"], "owner + W5", "before any endurance segment", "I",
     "Pre-registration document exists before data.")

REQUIREMENTS = R

# Interface table (control C5). 'observed_related_ids' were read (read-only) from unmerged in-flight W3/W4 drafts on
# 2026-09-27; they are hints, not dependencies, and may change at merge.
INTERFACE = [
    # req, adopter, target, related ids observed in drafts, action, note
    ("AOL-WC-01", "W3", "H-1 test installation / stand layout (new HW item)", ["HW-H1-04"], "ADD",
     "W3 draft has no witness-coupon mount"),
    ("AOL-WC-01", "W4", "metrology section (new INS item: coupon metrology)", ["INS-17"], "ADD",
     "W4 draft has no witness metrology instrument"),
    ("AOL-WC-02", "W3", "section 4.1 H-1 (anode/distributor)", ["HW-H1-05", "HW-H1-06"], "AMEND", ""),
    ("AOL-WC-03", "W3", "section 4.3 C-1 mount", ["HW-C1-01", "HW-C1-03"], "ADD", "fixed positions per HW-C1-01"),
    ("AOL-WC-04", "W3", "section 4.2 MC-1", ["HW-MC-03", "HW-MC-04"], "ADD", ""),
    ("AOL-WC-05", "W3", "section 4.5 removable modules / section 4.7 installation reproducibility",
     ["HW-PIM-10", "HW-H1-02"], "ADD",
     "CONFLICT CHECK: coupon exchange at arm boundaries must be classified by W3 as non-functional (not creating "
     "H-1') - AOL-OQ-01"),
    ("AOL-WC-06", "W4", "facility / background section", ["INS-08", "INS-11"], "ADD", ""),
    ("AOL-RC-01", "W3", "section 4.1 H-1", ["HW-H1-02", "HW-H1-05"], "AMEND",
     "consistent with HW-H1-02: removal only at pre-registered phase boundaries, each creates H-1' with a new HW-0 "
     "reference"),
    ("AOL-RC-02", "W3", "section 4.6 electrical interfaces", ["HW-ELEC-01"], "ADD", ""),
    ("AOL-RC-02", "W4", "INS-04 neighbourhood (resistance measurement)", ["INS-04"], "ADD", ""),
    ("AOL-RC-03", "W3", "section 4.1 H-1 wall", ["HW-H1-03", "HW-H1-04"], "AMEND", ""),
    ("AOL-RC-04", "W3", "section 7 owner questions", ["HW-H1-01"], "OWNER_DECISION", "AOL-OQ-02"),
    ("AOL-CX-01", "W3", "section 4.3 C-1", ["HW-C1-03"], "ALIGN", "already present in W3 draft (daily Xe check)"),
    ("AOL-CX-01", "W4", "INS-04 / INS-18 logging", ["INS-04", "INS-18"], "ALIGN", ""),
    ("AOL-CX-02", "W4", "INS-18 DAQ", ["INS-18"], "ADD", ""),
    ("AOL-CX-03", "W4", "INS-11 RGA", ["INS-11"], "AMEND", "add a near-cathode sampling point"),
    ("AOL-CX-04", "W4", "INS-17 temperatures", ["INS-17"], "AMEND", "cathode emitter / tube channel"),
    ("AOL-CX-05", "W4", "INS-18 DAQ + W3 HW-C1-03 interlock", ["INS-18", "HW-C1-03"], "ADD", ""),
    ("AOL-CX-06", "W4", "INS-10 stability / extinction", ["INS-10"], "ALIGN", "add feed composition + cathode state "
                                                                          "to each extinction record"),
    ("AOL-CX-07", "W3", "section 4.1 HW-H1-07 thermocouples", ["HW-H1-07"], "AMEND", "add wall-ring and coupon TCs"),
    ("AOL-CX-07", "W4", "INS-17 temperatures", ["INS-17"], "AMEND", ""),
    ("AOL-PM-01", "W4", "new metrology section", [], "ADD", ""),
    ("AOL-PM-02", "W4", "new metrology section", [], "ADD", ""),
    ("AOL-PM-03", "W3", "HW-H1-04 erosion profile", ["HW-H1-04"], "ALIGN", ""),
    ("AOL-PM-04", "W4", "new metrology section", [], "ADD", ""),
    ("AOL-PM-05", "W4", "new metrology section", ["HW-C1-05"], "ADD", ""),
    ("AOL-PM-06", "W4", "new metrology section", [], "ADD", ""),
    ("AOL-PM-07", "W2", "LOCK-1 facility choice", [], "OWNER_DECISION", ""),
    ("AOL-PM-08", "W3", "HW-MC-03/04", ["HW-MC-03", "HW-MC-04"], "ALIGN", "add pole-face inspection"),
    ("AOL-PM-08", "W4", "INS-09 B(z)", ["INS-09"], "ALIGN", ""),
    ("AOL-PM-09", "W2", "LOCK-1 facility / lab choice", [], "OWNER_DECISION", ""),
    ("AOL-EX-01", "W2", "owner facility channel", [], "OWNER_DECISION", "not on the S1 critical path"),
    ("AOL-EX-02", "W2", "owner facility channel", [], "OWNER_DECISION", "not on the S1 critical path"),
    ("AOL-EX-03", "W2", "owner facility channel", [], "OWNER_DECISION", "not on the S1 critical path"),
    ("AOL-DC-01", "W5", "data custody / blinding plan", [], "ADD", "W5 decides whether any metrology is held-out"),
    ("AOL-DC-01", "W4", "INS-18 DAQ", ["INS-18"], "ADD", ""),
    ("AOL-DC-02", "W4", "record format", [], "ADD", ""),
    ("AOL-LF-01", "W3", "section 9 compliance", [], "ALIGN", ""),
    ("AOL-LF-01", "W4", "compliance", [], "ALIGN", ""),
    ("AOL-LF-02", "W5", "pre-registration", [], "ADD", ""),
]

OPEN_QUESTIONS = [
    {"id": "AOL-OQ-01", "to": "owner + W3",
     "question": "Classify witness coupons and their mounts as non-functional exchangeable items that do NOT create a "
                 "new unit H-1' when exchanged at arm boundaries (W3 draft HW-H1-02), provided B(z) and the HW-0 "
                 "reference are unchanged within LOCK-2 repeatability?"},
    {"id": "AOL-OQ-02", "to": "owner", "question": "Approve alternative-grade wall sector inserts (AOL-RC-04)? They "
                                                   "add comparative N/O wall data but change H-1 design-"
                                                   "representativeness."},
    {"id": "AOL-OQ-03", "to": "owner", "question": "Candidate oxidation-resistant anode materials and coatings to put "
                                                   "on coupons (no candidate is sourced in this register)."},
    {"id": "AOL-OQ-04", "to": "owner", "question": "Heated emitter witness near C-1 (adds a heater load to the bus "
                                                   "boundary metering) or ground-only AOL-EX-03?"},
    {"id": "AOL-OQ-05", "to": "owner", "question": "Ground AO facility and target fluence for AOL-EX-01 (and whether "
                                                   "a legitimately acquired closed-access standard or paper is used, "
                                                   "per control C4)."},
    {"id": "AOL-OQ-06", "to": "owner", "question": "Acquire CIFALI2012 (primary of the 314 h endurance result) and "
                                                   "Espy 1993 (lane 32 highest priority) under the C4 rule."},
]

PROPOSED_THRESHOLDS = [
    {"id": "AOL-PT-01", "status": "PROPOSED (not in the RFP)",
     "rule": "Any spontaneous flame-out during O-bearing operation stops the block at its end and triggers an "
             "anode inspection (borescope if designed in; removal only at a pre-registered boundary).",
     "value": 1, "unit": "flame-out", "basis": "AOL-M01 symptom (ANDREUSSI2022 Page 24 of 57); owner to confirm"},
    {"id": "AOL-PT-02", "status": "PROPOSED (not in the RFP)",
     "rule": "Anode-resistance change that triggers inspection", "value": None, "unit": "ohm",
     "basis": "TBD - requires S1 baseline scatter (LOCK-2)"},
    {"id": "AOL-PT-03", "status": "PROPOSED (not in the RFP)",
     "rule": "C-1 daily Xe reference keeper/coupling voltage shift that triggers a cathode review", "value": None,
     "unit": "V", "basis": "TBD - requires S1 day-to-day scatter (LOCK-2)"},
    {"id": "AOL-PT-04", "status": "PROPOSED (not in the RFP)",
     "rule": "Witness removal cadence: at S1 end, at each phase boundary and at arm boundaries (AOL-WC-05 only)",
     "value": None, "unit": None, "basis": "structure only; no number"},
]

MILESTONES = {
    "supports": ["A", "C"],
    "A": "Supplies the life/AO conditions a CONDITIONAL_BASELINE(X) must carry (all common-mode, so they do not "
         "discriminate hall_only / rf_hall / ecr_hall): (1) anode material/design whose oxidation on the delivered "
         "composition does not change the discharge over the firing life (AOL-M01); (2) wall grade N/O erosion life "
         "demonstrated (AOL-M02/M03); (3) C-1 tolerance of the measured cathode-region exposure (AOL-M04/M05); "
         "(4) exterior materials compatible with the mission AO fluence (AOL-M09). It eliminates nothing.",
    "B": "Not a performance input. Wall/erosion evidence stays evidence-only until an admitted closure exists "
         "(credible set empty) or H-1 near-wall data exist.",
    "C": "Defines the witness / replaceable-part / metrology provisions without which no H-1 life evidence can be "
         "produced for the PDR life closure (G4_firing_life, P2_cathode).",
    "to_reach_next": [
        "owner review of this DRAFT and of AOL-OQ-01..06",
        "W3 and W4 adopt the interface-table rows before W3 merges (control C5 integration check)",
        "LOCK-1: facility and metrology-lab choice; coupon positions frozen",
        "S1: baselines (AOL-PM-01) and first exposure data; LOCK-2 sets AOL-PT-02/03",
        "C: pre-registered endurance segment (AOL-LF-02) plus AOL-EX-01..03 results",
    ],
}

HARD_STATEMENTS = [
    "DRAFT for owner review. Every requirement is PROPOSED; every threshold not in the RFP is PROPOSED.",
    "No life number for H-1 exists. Life entries are literature on another device (labelled, not transferred as a "
    "verdict) or TBD (control C6). No 15,000 h extrapolation is made from any Hall closure; the credible set is empty.",
    "No Hall map, screening candidate (sgb-screen-*), unadmitted closure or withdrawn 0-D number is used anywhere.",
    "Witness and metrology data are not model-promotion evidence until the W5 pre-registration is frozen "
    "(execution directive data_rule); the same data never both select and validate a closure (control C1).",
    "Nothing here is a design variable of the intake, compressor, gas chambers or valves; Hall-closure uncertainty "
    "does not leak upstream.",
    "No architecture is ranked or eliminated: every mechanism is common-mode except AOL-M10 (module-specific, "
    "monitored).",
    "Nothing is wired into archengine or any abep_sim module; goldens are untouched.",
]


def build_register():
    derived = {"ao_environment": compute_ao_environment()}
    reg = {
        "schema": "ao_lifetime_register_v1",
        "schema_file": SCHEMA_REL,
        "id": "fo_ao_lifetime_register",
        "title": "H-1 lifetime / atomic-oxygen degradation register and witness / coupon / metrology provisions",
        "status": "DRAFT_FOR_OWNER_REVIEW",
        "date": "2026-09-27",
        "lane": {"id": "fo_ao_lifetime_register", "trigger": "T_PIVOT_AO_LIFETIME_REGISTER",
                 "owner_disposition": "od_hardware_pivot",
                 "directive": "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json execution_directive_2026_09_27",
                 "controls": ["C1", "C4", "C5", "C6"]},
        "builder": "docs/experiments/lifetime_ao/build_ao_lifetime_register.py",
        "milestones": MILESTONES,
        "hard_statements": HARD_STATEMENTS,
        "vocabulary": {
            "evidence_class": EVIDENCE_CLASSES,
            "evidence_level": "1-7 per docs/EVIDENCE.md (source strength and proximity)",
            "life_number_status": LIFE_STATUSES,
            "verification_method": {"I": "inspection", "A": "analysis", "D": "demonstration", "T": "test"},
            "merge_action": {"ADD": "new item in the adopting register", "AMEND": "extend an existing item",
                             "ALIGN": "already covered; cross-reference only",
                             "OWNER_DECISION": "needs an owner decision before adoption"},
        },
        "sources": SOURCES,
        "repository_references": REPO_REFERENCES,
        "planned_paths_not_read": PLANNED_PATHS,
        "mechanisms": MECHANISMS,
        "witness_coupons": WITNESS_COUPONS,
        "requirements": REQUIREMENTS,
        "interface_table": {
            "control": "C5_AO_early",
            "note": "Related ids were observed read-only in unmerged in-flight W3/W4 drafts on 2026-09-27; they are "
                    "hints for merging and may change. This register does not depend on them.",
            "rows": [{"requirement": r, "adopter": a, "target": t, "observed_related_ids": ids, "action": act,
                      "note": n} for (r, a, t, ids, act, n) in INTERFACE],
        },
        "proposed_thresholds": PROPOSED_THRESHOLDS,
        "open_owner_questions": OPEN_QUESTIONS,
        "derived": derived,
    }
    return reg


# ---------------------------------------------------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------------------------------------------------
def _fmt(x):
    if x is None:
        return "TBD"
    if isinstance(x, list):
        return "–".join(_fmt(v) for v in x)
    if isinstance(x, float):
        return f"{x:.4g}"
    return str(x)


def render_md(reg):
    L = []
    a = L.append
    a("# H-1 lifetime / atomic-oxygen degradation register (fo_ao_lifetime_register) — DRAFT")
    a("")
    a("Generated by `build_ao_lifetime_register.py` from the same data as "
      "[`ao_lifetime_register_v1.json`](ao_lifetime_register_v1.json) (schema "
      "[`ao_lifetime_register_v1.schema.json`](ao_lifetime_register_v1.schema.json)). Do not edit by hand; run "
      "`python docs/experiments/lifetime_ao/build_ao_lifetime_register.py` (and `--check` in CI). The JSON wins.")
    a("")
    a("**Status: DRAFT for owner review.** Lane `fo_ao_lifetime_register`, trigger `T_PIVOT_AO_LIFETIME_REGISTER`, "
      "owner disposition `od_hardware_pivot` (execution directive 2026-09-27; controls C1, C4, C5, C6). Separate from "
      "thrust performance.")
    a("")
    a("## 0. Hard statements")
    for s in reg["hard_statements"]:
        a(f"- {s}")
    a("")
    a("## 1. Milestones")
    m = reg["milestones"]
    a(f"Supports **{', '.join(m['supports'])}**.")
    a("")
    for k in ("A", "B", "C"):
        a(f"- **{k}:** {m[k]}")
    a("- **To reach the next milestone:**")
    for s in m["to_reach_next"]:
        a(f"  - {s}")
    a("")
    a("## 2. Primary output: provisions H-1 must carry from the start (W3 / W4 adoptable)")
    a("")
    a("| id | category | title | adopter | install phase | verification |")
    a("|---|---|---|---|---|---|")
    for r in reg["requirements"]:
        a(f"| {r['id']} | {r['category']} | {r['title']} | {r['adopter']} | {r['install_phase']} | "
          f"{r['verification_method']}: {r['verification']} |")
    a("")
    for r in reg["requirements"]:
        a(f"- **{r['id']} ({r['status']}).** {r['requirement']} *Rationale:* {r['rationale']} "
          f"*Mechanisms:* {', '.join(r['mechanisms'])}.")
    a("")
    a("### 2.1 Witness coupons and samples")
    a("")
    a("| id | placement | materials | exposure | pre-test metrology | post-test metrology | mechanisms |")
    a("|---|---|---|---|---|---|---|")
    for w in reg["witness_coupons"]:
        a(f"| {w['id']} {w['name']} | {w['placement']} | {'; '.join(w['materials'])} | {w['exposure']} | "
          f"{'; '.join(w['pre_metrology'])} | {'; '.join(w['post_metrology'])} | {', '.join(w['mechanisms'])} |")
    a("")
    a("## 3. Interface table for W3 / W4 (control C5)")
    a("")
    a(reg["interface_table"]["note"])
    a("")
    a("| requirement | adopter | target | related ids (unmerged drafts) | action | note |")
    a("|---|---|---|---|---|---|")
    for row in reg["interface_table"]["rows"]:
        a(f"| {row['requirement']} | {row['adopter']} | {row['target']} | {', '.join(row['observed_related_ids']) or '-'}"
          f" | {row['action']} | {row['note'] or '-'} |")
    a("")
    a("## 4. Degradation register (H-1 DEGRADATION REGISTER)")
    a("")
    a("| id | mechanism | components | species | energy regime | evidence status | life number |")
    a("|---|---|---|---|---|---|---|")
    for mm in reg["mechanisms"]:
        ln = mm["life_number"]
        lnv = ln["status"] if ln["value"] is None else f"{ln['status']}: {_fmt(ln['value'])} {ln['unit']} ({ln['device']})"
        a(f"| {mm['id']} | {mm['title']} | {'; '.join(mm['components'])} | {', '.join(mm['species'])} | "
          f"{mm['energy_regime']} | {mm['evidence_status']} | {lnv} |")
    a("")
    for mm in reg["mechanisms"]:
        a(f"### {mm['id']} — {mm['title']}")
        a(f"- **Energy regime:** `{mm['energy_regime']}`. {mm['energy_statement']}")
        a(f"- **Degradation mode:** {mm['degradation_mode']}")
        a(f"- **Measurable quantities:** {'; '.join(mm['measurable_quantities'])}")
        a("- **Evidence:**" + ("" if mm["evidence"] else " none accessed."))
        for e in mm["evidence"]:
            src = e["source_id"] if e["source_id"] != "REPO" else f"`{e['repo_path']}`"
            val = "" if e["value"] is None else f" [{_fmt(e['value'])} {e['unit']}]"
            chk = "verified by this lane" if e["verified_by_this_lane"] else "as recorded by the referenced lane"
            a(f"  - {e['statement']}{val} — {src}, {e['locator']}; level {e['evidence_level']}, {e['evidence_class']}; "
              f"{e['applicability']}; {chk}. {e['transfer']}.")
        a(f"- **Life number:** {mm['life_number']['status']} — {mm['life_number']['statement']}")
        re_ = mm["required_experiment"]
        a(f"- **Required experiment.** Ground AO source: {re_['ground_ao_source']} In-thruster witness: "
          f"{re_['in_thruster_witness']} Post-test metrology: {re_['post_test_metrology']}.")
        a(f"- **Scope:** {mm['architecture_scope']}. **Cross-refs:** {', '.join(mm['cross_refs'])}.")
        a("")
    a("## 5. Derived: external ram atomic-oxygen environment (model-derived, illustrative)")
    ao = reg["derived"]["ao_environment"]
    a("")
    a(f"Status: {ao['status']}. Evidence level {ao['evidence_level']}, {ao['evidence_class']}. Input: "
      f"`{ao['inputs']['atmosphere']['path']}` (sha256 `{ao['inputs']['atmosphere']['sha256'][:16]}…`), "
      f"{ao['inputs']['atmosphere']['model']}.")
    a("")
    for k, v in ao["equations"].items():
        a(f"- `{k}`: {v}")
    a("")
    a("| alt km | F10.7 | n_O m⁻³ | V m/s | E_ram eV | ram flux cm⁻²s⁻¹ | fluence / 1000 h cm⁻² | fluence 26,000 h cm⁻² | × MISSE 2 fluence |")
    a("|---|---|---|---|---|---|---|---|---|")
    for t in ao["table"]:
        a(f"| {t['alt_km']} | {t['f107']:g} | {t['n_O_m3']:.4g} | {t['V_orb_m_s']:.5g} | {t['E_ram_O_eV']:.4g} | "
          f"{t['ram_flux_atoms_cm2_s']:.4g} | {t['fluence_per_1000h_atoms_cm2']:.4g} | "
          f"{t['fluence_rfp_mission_26000h_atoms_cm2']:.4g} | {t['ratio_to_misse2_fluence']:.3g} |")
    a("")
    a("Flags:")
    for f_ in ao["flags"]:
        a(f"- {f_}")
    a("")
    rr = ao["illustrative_recession_equivalents"]
    a(f"**Illustrative recession-equivalents** ({rr['status']}) over the mission-fluence range "
      f"{rr['mission_fluence_range_atoms_cm2'][0]:.4g}–{rr['mission_fluence_range_atoms_cm2'][1]:.4g} atoms/cm²:")
    a("")
    a("| MISSE 2 sample | material | E_y cm³/atom (Table 4) | role | recession µm (min–max fluence) |")
    a("|---|---|---|---|---|")
    for r in rr["rows"]:
        a(f"| {r['id']} | {r['abbreviation']} | {r['misse2_erosion_yield_cm3_per_atom']:.3g} | {r['role_on_ep_unit']} | "
          f"{r['illustrative_recession_um_at_min_mission_fluence']:.3g}–"
          f"{r['illustrative_recession_um_at_max_mission_fluence']:.3g} |")
    a("")
    a("## 6. Proposed thresholds (not in the RFP)")
    for p in reg["proposed_thresholds"]:
        a(f"- **{p['id']}** ({p['status']}): {p['rule']} — value {_fmt(p['value'])}"
          f"{'' if p['unit'] is None else ' ' + p['unit']}; basis: {p['basis']}.")
    a("")
    a("## 7. Open owner questions")
    for q in reg["open_owner_questions"]:
        a(f"- **{q['id']}** ({q['to']}): {q['question']}")
    a("")
    a("## 8. Sources accessed by this lane")
    for k, s in reg["sources"].items():
        urls = ", ".join(s["urls_accessed"]) or "none"
        doi = f" doi:{s['doi']}." if s["doi"] else ""
        sha = f" sha256 `{s['sha256_of_accessed_file']}`." if s["sha256_of_accessed_file"] else ""
        a(f"- **{k}** — {s['citation']}.{doi} Access: {s['access']} ({s['license']}); URLs: {urls}.{sha} "
          f"{s['note']}")
    a("")
    a("Repository files referenced (read-only): " + ", ".join(f"`{v}`" for v in reg["repository_references"].values())
      + ".")
    a("")
    a("Parallel workstreams referenced by planned path only (not read as inputs): " +
      "; ".join(f"{k} `{v}`" if v.endswith("/") else f"{k} ({v})" for k, v in reg["planned_paths_not_read"].items())
      + ".")
    a("")
    return "\n".join(L)


def render_json(reg):
    return json.dumps(reg, indent=1, ensure_ascii=False) + "\n"


def main(argv):
    reg = build_register()
    js, md = render_json(reg), render_md(reg)
    if "--check" in argv:
        bad = []
        for path, text in ((OUT_JSON, js), (OUT_MD, md)):
            try:
                with open(path, encoding="utf-8") as f:
                    if f.read() != text:
                        bad.append(path)
            except FileNotFoundError:
                bad.append(path)
        if bad:
            print("OUT OF DATE: " + ", ".join(os.path.relpath(p, ROOT) for p in bad))
            return 1
        print("OK: ao_lifetime_register_v1.json and AO_LIFETIME_REGISTER.md are up to date")
        return 0
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        f.write(js)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {os.path.relpath(OUT_JSON, ROOT)} and {os.path.relpath(OUT_MD, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
